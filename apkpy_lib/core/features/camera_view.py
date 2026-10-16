"""Embedded photo view contract and narrow compiler hooks."""
import ast
import json
from pathlib import Path
from . import camera

DEFAULTS = dict(lens='back', flash='off', zoom=1.0, mirror=True,
                fit='cover', aspect_ratio='4:3', autostart=True)
METHODS = {'capture': 0, 'start': 0, 'stop': 0, 'flip': 0,
           'set_zoom': 1, 'set_flash': 1, 'set_torch': 1}
CALLBACKS = {'on_ready': 0, 'on_capture': 2, 'on_error': 1}


def validate(options):
    if set(options)-set(DEFAULTS):
        raise ValueError('Unknown camera_view option: '+sorted(set(options)-set(DEFAULTS))[0])
    out = dict(DEFAULTS, **options)
    camera.validate({k: v for k, v in out.items() if k in camera.OPTIONS})
    if out['fit'] not in ('cover', 'contain'):
        raise ValueError('camera_view fit must be cover or contain')
    if not isinstance(out['autostart'], bool):
        raise ValueError('camera_view autostart must be True or False')
    return out


def used(tree):
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == 'camera_view' for n in ast.walk(tree))


def validate_callbacks(tree):
    definitions = {n.name:n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)}
    for n in ast.walk(tree):
        if not (isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='camera_view'):
            continue
        for kw in n.keywords:
            if kw.arg in CALLBACKS and isinstance(kw.value,ast.Name) and kw.value.id in definitions:
                args=definitions[kw.value.id].args
                if len(args.args)!=CALLBACKS[kw.arg] or args.vararg or args.kwarg or args.kwonlyargs:
                    camera.fail('camera_view '+kw.arg+' must accept '+str(CALLBACKS[kw.arg])+' arguments',kw.value)


def parse_component(t, call, comp):
    if call.args:
        camera.fail('Use named arguments for camera_view()',call)
    options={}
    for kw in call.keywords:
        if kw.arg in DEFAULTS:
            try: options[kw.arg]=ast.literal_eval(kw.value)
            except (ValueError,TypeError): camera.fail('camera_view initial options must be literals; use methods to change them',kw.value)
        elif kw.arg not in set(CALLBACKS)|{'id','screen','parent'}:
            camera.fail('Unknown camera_view argument: '+str(kw.arg),call)
    try: comp['camera_options']=validate(options)
    except ValueError as exc: camera.fail(str(exc),call)
    comp['id']=t._kw(call.keywords,'id')
    for key, count in CALLBACKS.items():
        comp[key]=camera.callback(t,t._kw_node(call.keywords,key),count,'view_'+key)
    if 'CAMERA' not in t.declared_permissions: t.declared_permissions.append('CAMERA')


def parse_control(t, call):
    action=call.func.attr
    if action not in METHODS or len(call.args)!=METHODS[action] or call.keywords:
        camera.fail('camera_view supports capture(), start(), stop(), flip(), set_zoom(value), set_flash(value), set_torch(value)',call)
    if call.args:
        try: value=ast.literal_eval(call.args[0])
        except (ValueError,TypeError): pass
        else:
            try:
                if action=='set_torch':
                    if not isinstance(value,bool): raise ValueError('set_torch expects True or False')
                else: validate({action[4:]:value})
            except ValueError as exc: camera.fail(str(exc),call)
    return dict(type='camera_view_control',py_var=call.func.value.id,action=action,args=call.args,line=call.lineno)


def emit_control(lines, indent, command, resolve, val):
    jv=resolve(command['py_var'])
    if not jv:
        # The compiler also emits unreferenced global callback copies into
        # other Activities. Those copies must not reference this screen's View.
        return
    names={'capture':'capture','start':'start','stop':'stop','flip':'flip',
           'set_zoom':'setZoom','set_flash':'setFlash','set_torch':'setTorch'}
    args=[val(n) for n in command['args']]
    if command['action']=='set_zoom': args=['String.valueOf('+args[0]+')']
    if command['action']=='set_torch': args=['String.valueOf('+args[0]+')']
    if command['action']=='set_flash': args=['String.valueOf('+args[0]+')']
    lines.append(f"{indent}if ({jv} != null) {jv}.{names[command['action']]}({', '.join(args)});")


def emit_init(lines,indent,comp):
    jv=comp['_java_var']; opts=json.dumps(json.dumps(comp['camera_options']))
    cb=lambda key,params: ('('+params+') -> pythonCallback_'+comp[key]+'('+params+')') if comp.get(key) else 'null'
    lines.append(f'{indent}{jv} = findViewById(R.id.{jv});')
    lines.append(f'{indent}{jv}.configure(this, {opts}, {cb("on_ready", "")}, {cb("on_capture", "ok, path")}, {cb("on_error", "reason")});')


def files(package):
    return {'java/ApkpyCameraView.java':Path(__file__).with_name('camera_view_android.java').read_text(encoding='utf-8').replace('__PACKAGE__',package)}
