# -*- coding: utf-8 -*-
"""Classes: written out as functions and an object store, before translating.

    class Task:                            def Task(title):
        def __init__(self, title):             self = __apkpy_new__("Task")
            self.title = title                 _apkpy_Task___init__(self, title)
            self.done = False                  return self

        def toggle(self):                  def _apkpy_Task___init__(self, title):
            self.done = not self.done          _apkpy_o1 = __apkpy_setattr__(self, "title", title)
                                               _apkpy_o2 = __apkpy_setattr__(self, "done", False)
    t = Task("milk")
    t.toggle()                             def _apkpy_Task_toggle(self):
    t.title                                    _apkpy_o3 = __apkpy_setattr__(
                                                   self, "done", not __apkpy_getattr__(self, "done"))

On the phone every value is text. An object is one too: the text CPython shows
for it without a ``__str__`` (``<__main__.Task object at 0x7f3a5c000040>``),
which is also the key of its fields in the app's object store (ApkpyObjects).
Every name that holds it reaches the same fields, so ``tasks[0].done = True``
changes the object every other name sees, as in CPython; ``==`` and ``is`` are
the same object, and it is true in an ``if``.

A ``@dataclass`` is first written out as the plain class CPython makes of it
(``_rewrite_dataclasses``): an ``__init__`` with a parameter per field, a
``__repr__`` and an ``__eq__``. A class that extends an error
(``class TooLong(ValueError): pass``) is not an object at all: it leaves the
module as the name of one more error for raise and except (``_split_errors``).

What the other passes and the compiler see is functions of the module and five
calls of the store: ``__apkpy_new__``, ``__apkpy_getattr__``,
``__apkpy_setattr__`` (given to a name of its own, ``_apkpy_oN``: an
assignment is what every generator already writes), ``__apkpy_isinstance__``
and ``__apkpy_classof__``.

A method becomes ``_apkpy_<Class>_<name>(self, ...)``. Where the source says
which class an object is -- ``self``, a name given ``Task(...)``, an item of a
list of them, a parameter every caller passes one to -- the call goes straight
to the method that class runs; where it does not, or a subclass has its own,
``_apkpy_call_<name>`` picks it by the object's class when the app runs.

A field is read as the kind every assignment to it gives, when that is one
kind: ``int(...)``, ``float(...)``, ``str(...)`` or ``list(...)`` around the
read, which the compiler already knows how to read. ``self.price * self.qty``
is then arithmetic. Only when it is certain: a wrong yes would glue numbers as
text without a word.

An object made at the top of the file (``cart = Cart()``) is made once, by the
first function that uses it: each such function starts with
``_apkpy_ensure()``, and a lambda reads it through ``_apkpy_mod_<name>()``.
"""

import ast
import copy

NEW = "__apkpy_new__"
GETATTR = "__apkpy_getattr__"
SETATTR = "__apkpy_setattr__"
ISA = "__apkpy_isinstance__"
CLASSOF = "__apkpy_classof__"
INTRINSICS = (NEW, GETATTR, SETATTR, ISA, CLASSOF)

ENSURE = "_apkpy_ensure"
INIT = "_apkpy_init"
READY = "_apkpy_ready"

# What the last desugar found, for the compiler: whether to write
# ApkpyObjects.java, each class's parent for isinstance(), and the error classes
# of the app (name -> parent error, name -> the message raise Name() gives).
STATE = {'used': False, 'parents': {}, 'errors': {}, 'error_defaults': {}}

_DUNDERS = ('__init__', '__str__', '__repr__', '__eq__')

# Methods a value has: on a receiver the source says nothing about, a method of
# a class with one of these names could be either.
_VALUE_METHODS = frozenset((
    'upper', 'lower', 'strip', 'lstrip', 'rstrip', 'replace', 'title', 'find',
    'rfind', 'count', 'join', 'split', 'rsplit', 'splitlines', 'startswith',
    'endswith', 'format', 'capitalize', 'swapcase', 'isdigit', 'isalpha',
    'isalnum', 'isspace', 'isnumeric', 'isdecimal', 'isupper', 'islower',
    'zfill', 'center', 'ljust', 'rjust', 'index', 'rindex', 'partition',
    'rpartition', 'casefold', 'removeprefix', 'removesuffix',
    'append', 'extend', 'insert', 'remove', 'pop', 'clear', 'sort', 'reverse',
    'copy', 'get', 'keys', 'values', 'items', 'update', 'setdefault',
))

# Methods that change a list or a dict held in a field.
_MUTATORS = ('append', 'extend', 'insert', 'remove', 'pop', 'clear', 'sort',
             'reverse', 'update', 'setdefault')

_BOTTOM = "<nothing yet>"

# Set on a field read that is always a number, but not always a whole one:
# self.total = 0 and later self.total += 2.5. It is read as text (no int() or
# float() fits both), and a key of sorted() reads the mark to compare it as
# the number it is (features/sort_key.py, _sort_key_java in the compiler).
NUMBER = "_apkpy_number"
_NUMBER_KINDS = ('int', 'float', 'num')


def _join_number(a, b):
    """'int', 'float' or 'num' (both) while every value is a number; None otherwise."""
    if a == _BOTTOM:
        return b if b == _BOTTOM or b in _NUMBER_KINDS else None
    if b == _BOTTOM:
        return a
    if a in _NUMBER_KINDS and b in _NUMBER_KINDS:
        return a if a == b else 'num'
    return None


# --- small helpers -----------------------------------------------------------

def _loc(node, like):
    return ast.copy_location(node, like)


def _name(id_, like, store=False):
    return _loc(ast.Name(id=id_, ctx=ast.Store() if store else ast.Load()), like)


def _const(value, like):
    return _loc(ast.Constant(value=value), like)


def _call(func, args, like, keywords=None):
    if isinstance(func, str):
        func = _name(func, like)
    return _loc(ast.Call(func=func, args=list(args), keywords=list(keywords or [])), like)


# Set on an int()/float() this module writes around a field it knows holds a
# number: the compiler reads the text back with Long.parseLong/Double.parseDouble.
READ_BACK = '_apkpy_read_back'


def _read_back(call):
    setattr(call, READ_BACK, True)
    return call


def _assign(target, value, like):
    if isinstance(target, str):
        target = _name(target, like, store=True)
    return _loc(ast.Assign(targets=[target], value=value, type_comment=None), like)


def _expr(value, like):
    return _loc(ast.Expr(value=value), like)


def _refuse(node, cause, suggestions=(), received=''):
    from ..unsupported import raise_unsupported
    raise_unsupported(node, cause=cause, suggestions=list(suggestions), received=received)


def _is_literal(node):
    try:
        ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return False
    return True


def _args_of(fn):
    a = fn.args
    return list(getattr(a, 'posonlyargs', [])) + list(a.args)


_TEXT_INPUTS = ('text', 'password', 'search', 'email')


def _text_widgets(tree):
    """Names made once at the top of the file by label(...) or a text inputs(...):
    their get_value() is the text on the screen. A checkbox answers "true", a
    range a number, so only these."""
    stores = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            stores[n.id] = stores.get(n.id, 0) + 1
    out = set()
    for stmt in tree.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name) and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Name)):
            continue
        call, name = stmt.value, stmt.targets[0].id
        if stores.get(name) != 1:
            continue
        if call.func.id == 'label':
            out.add(name)
        elif call.func.id == 'inputs':
            kind = next((k.value for k in call.keywords if k.arg == 'type'), None)
            if kind is None and len(call.args) > 2:
                kind = call.args[2]
            if kind is None or (isinstance(kind, ast.Constant) and kind.value in _TEXT_INPUTS):
                out.add(name)
    return out


def _always_returns(body):
    """True when every way through *body* ends in a return or a raise."""
    if not body:
        return False
    last = body[-1]
    if isinstance(last, (ast.Return, ast.Raise)):
        return True
    if isinstance(last, ast.If):
        return _always_returns(last.body) and _always_returns(last.orelse)
    if isinstance(last, ast.Try):
        if last.finalbody and _always_returns(last.finalbody):
            return True
        main = _always_returns(last.body) or _always_returns(last.orelse)
        return main and all(_always_returns(h.body) for h in last.handlers)
    if isinstance(last, ast.With):
        return _always_returns(last.body)
    return False


def _own_walk(statements):
    """Every node of *statements*; a function, lambda or class met inside is
    given but not gone into."""
    stack = list(reversed(statements))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _super_class(call, cls):
    """The class a super() call is about, for super() and super(C, self)."""
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == 'super'):
        return None
    if not call.args:
        return cls
    if len(call.args) == 2 and isinstance(call.args[0], ast.Name):
        return call.args[0].id
    return None


# --- the classes of the module -----------------------------------------------

class _Class(object):
    def __init__(self, node, base):
        self.node = node
        self.name = node.name
        self.base = base
        self.methods = {}       # name -> FunctionDef
        self.kind = {}          # name -> 'method' | 'static' | 'property'
        self.attrs = {}         # class attribute -> literal node
        self.children = []


def _check_method(cls_name, stmt):
    if isinstance(stmt, ast.AsyncFunctionDef):
        _refuse(stmt, 'An async method is not translated.',
                ['Write it as a plain method.'], received='async def %s' % stmt.name)
    kind = 'method'
    for deco in stmt.decorator_list:
        if isinstance(deco, ast.Name) and deco.id == 'staticmethod':
            kind = 'static'
        elif isinstance(deco, ast.Name) and deco.id == 'property':
            kind = 'property'
        else:
            what = ast.dump(deco) if not isinstance(deco, (ast.Name, ast.Attribute)) else (
                deco.id if isinstance(deco, ast.Name) else '%s.%s' % (
                    getattr(deco.value, 'id', '...'), deco.attr))
            _refuse(deco,
                    '@%s on a method is not translated. ApkPy translates plain methods, '
                    '@staticmethod and @property.' % what,
                    ['Write it as a plain method, or as a function of the module.'],
                    received='@%s' % what)
    params = _args_of(stmt)
    if stmt.args.vararg or stmt.args.kwarg or stmt.args.kwonlyargs:
        _refuse(stmt, '*args, **kwargs and keyword-only parameters on a method are not '
                'translated yet.', ['Give the method plain parameters, with defaults '
                                    'where they are optional.'],
                received='def %s(...)' % stmt.name)
    if kind != 'static' and not params:
        _refuse(stmt, 'A method needs self as its first parameter.',
                ['Write def %s(self, ...):' % stmt.name], received='def %s()' % stmt.name)
    if kind == 'property' and len(params) != 1:
        _refuse(stmt, 'A @property takes only self.', [], received='def %s(...)' % stmt.name)
    name = stmt.name
    if name.startswith('__') and name.endswith('__') and name not in _DUNDERS:
        _refuse(stmt,
                '%s.%s is not translated yet. Of the special methods, ApkPy translates '
                '__init__, __str__, __repr__ and __eq__.' % (cls_name, name),
                ['Write it as a method with a name of its own and call it.'],
                received='def %s' % name)
    if name in _DUNDERS and kind != 'method':
        _refuse(stmt, '%s cannot be a @staticmethod or a @property.' % name, [])
    return kind


def _collect(tree):
    """{name: _Class} for the classes at the top of the file, in order."""
    classes = {}
    order = []
    imported = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                imported.add((alias.asname or alias.name).split('.')[0])
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name in imported:
            _refuse(node, '%s is also a name imported at the top of the file. The class would '
                    'hide it.' % node.name, ['Give the class another name.'],
                    received='class %s' % node.name)
        if node.decorator_list:
            deco = node.decorator_list[0]
            label = getattr(deco, 'id', None) or getattr(deco, 'attr', None) \
                or getattr(getattr(deco, 'func', None), 'id', '...')
            _refuse(deco, '@%s on a class is not translated yet.' % label,
                    ['Write the __init__ yourself: def __init__(self, title, done=False): ...'],
                    received='@%s' % label)
        if node.keywords:
            _refuse(node, 'A class with keywords (metaclass=...) is not translated.', [],
                    received='class %s(...)' % node.name)
        base = None
        bases = [b for b in node.bases
                 if not (isinstance(b, ast.Name) and b.id == 'object')]
        if len(bases) > 1:
            _refuse(node, 'A class with more than one parent is not translated.',
                    ['Keep one parent, and move what the others gave into it.'],
                    received='class %s(...)' % node.name)
        if bases:
            b = bases[0]
            if isinstance(b, ast.Name) and b.id in classes:
                base = b.id
            else:
                label = b.id if isinstance(b, ast.Name) else ast.dump(b)
                if isinstance(b, ast.Name) and (b.id.endswith('Error') or b.id.endswith('Exception')):
                    cause = ('%s extends %s, which is neither one of Python\'s built-in errors '
                             'nor an error class written above it in this file.'
                             % (node.name, label))
                    tips = ['Extend Exception or one of Python\'s errors: class %s(ValueError): '
                            'pass' % node.name,
                            'Or write class %s(Exception): pass above it.' % label]
                else:
                    cause = ('%s extends %s, which is not a class of this file. A class can extend '
                             'another class written above it.' % (node.name, label))
                    tips = ['Write %s above it in this file, or leave the parent out.' % label]
                _refuse(node, cause, tips, received='class %s(%s)' % (node.name, label))
        cls = _Class(node, base)
        for stmt in node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) \
                    and isinstance(stmt.value.value, str):
                continue                       # the docstring
            if isinstance(stmt, ast.Pass):
                continue
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cls.kind[stmt.name] = _check_method(node.name, stmt)
                cls.methods[stmt.name] = stmt
                continue
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                if stmt.value is None:
                    continue                   # an annotation only: nothing in CPython either
                stmt = _assign(stmt.target.id, stmt.value, stmt)
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                    and isinstance(stmt.targets[0], ast.Name):
                value = stmt.value
                if not _is_literal(value) or isinstance(value, (ast.List, ast.Dict, ast.Set)):
                    _refuse(stmt,
                            'A class attribute is translated when it is a number, text, True, '
                            'False, None or a tuple of those. A list or a dict here is one '
                            'object shared by every instance, and a value worked out here runs '
                            'once when the class is made.',
                            ['Give each object its own in __init__: self.%s = []'
                             % stmt.targets[0].id],
                            received='%s = ...' % stmt.targets[0].id)
                cls.attrs[stmt.targets[0].id] = value
                continue
            _refuse(stmt, 'Inside a class, ApkPy translates methods, class attributes written '
                    'out and a docstring.', ['Move this line into a method, or out of the class.'])
        if base:
            classes[base].children.append(node.name)
        classes[node.name] = cls
        order.append(node.name)
    return classes, order


# --- @dataclass ---------------------------------------------------------------
# A dataclass is written out as the class CPython makes of it: an __init__ with
# a parameter per field, a __repr__ and an __eq__ -- each only when the class
# does not write its own, as dataclasses does. The rest of this file then sees
# a plain class.

POST_INIT = '_apkpy_post_init'

# @dataclass(...) options. These three change what is written; match_args only
# matters to a match statement.
_DATACLASS_OPTIONS = ('init', 'repr', 'eq', 'match_args')
_DATACLASS_REFUSED = {
    'frozen': ('A frozen dataclass is not translated yet.',
               'Leave frozen=True out: the app behaves the same as long as nothing '
               'assigns to a field after the object is made.'),
    'order': ('order=True is not translated yet: it writes <, <=, > and >= for the class.',
              'Compare a field instead: sorted(items, key=lambda i: i.price).'),
    'kw_only': ('kw_only=True is not translated yet.',
                'Leave it out and pass the fields by name anyway: Item(name="a", price=2).'),
    'unsafe_hash': ('unsafe_hash=True is not translated.', 'Leave it out.'),
    'slots': ('slots=True is not translated yet.', 'Leave it out.'),
    'weakref_slot': ('weakref_slot=True is not translated.', 'Leave it out.'),
}
# field(...) keywords: metadata and hash change nothing the app does.
_FIELD_OPTIONS = ('default', 'default_factory', 'init', 'repr', 'compare', 'metadata', 'hash')
# default_factory= names that make an empty value.
_FACTORIES = {'list': lambda like: _loc(ast.List(elts=[], ctx=ast.Load()), like),
              'dict': lambda like: _loc(ast.Dict(keys=[], values=[]), like),
              'str': lambda like: _const('', like),
              'int': lambda like: _const(0, like),
              'float': lambda like: _const(0.0, like),
              'bool': lambda like: _const(False, like)}


def _dataclass_names(tree):
    """The names this file gives dataclass, field and the dataclasses module."""
    deco, field, module = set(), set(), set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == 'dataclasses' and not node.level:
            for alias in node.names:
                if alias.name == 'dataclass':
                    deco.add(alias.asname or alias.name)
                elif alias.name == 'field':
                    field.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == 'dataclasses':
                    module.add(alias.asname or alias.name)
    return deco, field, module


def _named(node, names, module, attr):
    """node is `name` (from dataclasses import name) or `dataclasses.attr`."""
    return (isinstance(node, ast.Name) and node.id in names) or (
        isinstance(node, ast.Attribute) and node.attr == attr
        and isinstance(node.value, ast.Name) and node.value.id in module)


def _bool_option(kw, what):
    if not (isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, bool)):
        _refuse(kw.value, '%s=%s takes True or False written out.' % (what, kw.arg),
                [], received='%s=...' % kw.arg)
    return kw.value.value


def _annotation_is(ann, names):
    """ClassVar / InitVar, bare, typing.X or X[...]."""
    if isinstance(ann, ast.Subscript):
        ann = ann.value
    if isinstance(ann, ast.Name):
        return ann.id in names
    if isinstance(ann, ast.Attribute):
        return ann.attr in names
    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        return ann.value.split('[')[0].split('.')[-1].strip() in names
    return False


def _mutable_default(value):
    for node_type, word in ((ast.List, 'list'), (ast.ListComp, 'list'), (ast.Dict, 'dict'),
                            (ast.DictComp, 'dict'), (ast.Set, 'set'), (ast.SetComp, 'set')):
        if isinstance(value, node_type):
            return word
    return None


def _factory_value(node, field_name):
    """What default_factory= makes, as a value written out."""
    if isinstance(node, ast.Name) and node.id in _FACTORIES:
        return _FACTORIES[node.id](node)
    if isinstance(node, ast.Lambda) and not _args_of(node) and not node.args.vararg \
            and not node.args.kwarg and _is_literal(node.body):
        return copy.deepcopy(node.body)
    _refuse(node, 'default_factory= is translated with list, dict, str, int, float or bool, or '
            'a lambda that returns a value written out.',
            ['field(default_factory=list), or field(default_factory=lambda: ["a", "b"]).'],
            received='%s: ... = field(default_factory=...)' % field_name)


def _dataclass_field(stmt, field_names, module):
    """One field: {'name', 'ann', 'default', 'factory', 'init', 'repr', 'compare', 'node'}."""
    name = stmt.target.id
    f = {'name': name, 'ann': stmt.annotation, 'default': None, 'factory': None,
         'init': True, 'repr': True, 'compare': True, 'node': stmt}
    value = stmt.value
    if value is None:
        return f
    if isinstance(value, ast.Call) and _named(value.func, field_names, module, 'field'):
        if value.args:
            _refuse(value, 'field() takes its options by name.',
                    ['field(default=0), field(default_factory=list).'], received='field(...)')
        for kw in value.keywords:
            if kw.arg not in _FIELD_OPTIONS:
                _refuse(kw.value if kw.arg else value,
                        'field(%s=...) is not translated. ApkPy translates default, '
                        'default_factory, init, repr and compare.' % (kw.arg or '**'),
                        [], received='field(%s=...)' % (kw.arg or '**'))
            if kw.arg == 'default':
                f['default'] = kw.value
            elif kw.arg == 'default_factory':
                f['factory'] = _factory_value(kw.value, name)
            elif kw.arg in ('init', 'repr', 'compare'):
                f[kw.arg] = _bool_option(kw, 'field')
        if f['default'] is not None and f['factory'] is not None:
            _refuse(value, 'A field cannot have both default= and default_factory= '
                    '(CPython stops with the same error).', ['Keep one of them.'],
                    received='%s: ... = field(...)' % name)
    else:
        f['default'] = value
    default = f['default']
    if default is not None:
        word = _mutable_default(default)
        if word:
            _refuse(default, 'mutable default <class \'%s\'> for field %s is not allowed: use '
                    'default_factory (CPython stops with the same error: one %s would be '
                    'shared by every object).' % (word, name, word),
                    ['%s: %s = field(default_factory=%s)' % (name, word, word)],
                    received='%s: ... = %s' % (name, ast_text(default)))
        if not (_is_literal(default) or isinstance(default, ast.Name)):
            _refuse(default, 'A field\'s default is translated when it is a value written out '
                    'or the name of a constant.',
                    ['Work the value out in __post_init__(self), or pass it when making '
                     'the object.'], received='%s: ... = %s' % (name, ast_text(default)))
    return f


def _self_attr(name, like, store=False):
    return _loc(ast.Attribute(value=_name('self', like), attr=name,
                              ctx=ast.Store() if store else ast.Load()), like)


def _dataclass_init(node, fields, post_init):
    like = node
    params, defaults, body = [ast.arg(arg='self', annotation=None)], [], []
    for f in fields:
        if f['init']:
            params.append(_loc(ast.arg(arg=f['name'], annotation=copy.deepcopy(f['ann'])), like))
            start = f['default'] if f['default'] is not None else f['factory']
            if start is not None:
                defaults.append(copy.deepcopy(start))
            value = _name(f['name'], like)
        elif f['default'] is not None or f['factory'] is not None:
            value = copy.deepcopy(f['default'] if f['default'] is not None else f['factory'])
        else:
            continue                        # init=False and no default: never set, as in CPython
        body.append(_assign(_self_attr(f['name'], like, store=True), value, like))
    if post_init:
        body.append(_expr(_call(_loc(ast.Attribute(value=_name('self', like), attr=POST_INIT,
                                                   ctx=ast.Load()), like), [], like), like))
    if not body:
        body = [_loc(ast.Pass(), like)]
    args = ast.arguments(posonlyargs=[], args=params, vararg=None, kwonlyargs=[],
                         kw_defaults=[], kwarg=None, defaults=defaults)
    return _loc(ast.FunctionDef(name='__init__', args=args, body=body, decorator_list=[],
                                returns=None, type_comment=None), like)


def _class_name_of(value, like):
    """type(value).__name__"""
    return _loc(ast.Attribute(value=_call('type', [value], like), attr='__name__',
                              ctx=ast.Load()), like)


def _dataclass_repr(node, fields):
    """Item(name='milk', price=2.5): type(self).__name__, then each field by its repr."""
    like = node
    parts = [_loc(ast.FormattedValue(value=_class_name_of(_name('self', like), like),
                                     conversion=-1, format_spec=None), like), _const('(', like)]
    first = True
    for f in fields:
        if not f['repr']:
            continue
        parts.append(_const(('' if first else ', ') + f['name'] + '=', like))
        parts.append(_loc(ast.FormattedValue(value=_self_attr(f['name'], like), conversion=114,
                                             format_spec=None), like))
        first = False
    parts.append(_const(')', like))
    # Neighbouring texts as one, the way the parser gives an f-string.
    merged = []
    for p in parts:
        if merged and isinstance(p, ast.Constant) and isinstance(merged[-1], ast.Constant):
            merged[-1] = _const(merged[-1].value + p.value, like)
        else:
            merged.append(p)
    body = [_loc(ast.Return(value=_loc(ast.JoinedStr(values=merged), like)), like)]
    return _loc(ast.FunctionDef(name='__repr__', args=_no_args(['self']), body=body,
                                decorator_list=[], returns=None, type_comment=None), like)


def _dataclass_eq(node, fields):
    """Equal when the other is of the very same class and every compared field is."""
    like = node
    other_class = _loc(ast.Compare(left=_class_name_of(_name('other', like), like),
                                   ops=[ast.NotEq()],
                                   comparators=[_class_name_of(_name('self', like), like)]), like)
    body = [_loc(ast.If(test=other_class, body=[_loc(ast.Return(value=_const(False, like)), like)],
                        orelse=[]), like)]
    tests = [_loc(ast.Compare(left=_self_attr(f['name'], like), ops=[ast.Eq()],
                              comparators=[_loc(ast.Attribute(value=_name('other', like),
                                                              attr=f['name'], ctx=ast.Load()),
                                                like)]), like)
             for f in fields if f['compare']]
    result = _const(True, like) if not tests else (
        tests[0] if len(tests) == 1 else _loc(ast.BoolOp(op=ast.And(), values=tests), like))
    body.append(_loc(ast.Return(value=result), like))
    return _loc(ast.FunctionDef(name='__eq__', args=_no_args(['self', 'other']), body=body,
                                decorator_list=[], returns=None, type_comment=None), like)


def _rewrite_dataclasses(tree):
    """Each @dataclass class of the file, as the plain class CPython makes of it."""
    deco_names, field_names, module = _dataclass_names(tree)
    if not (deco_names or module):
        return
    fields_of, post_inits = {}, set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        decos = [d for d in node.decorator_list
                 if _named(d.func if isinstance(d, ast.Call) else d, deco_names, module,
                           'dataclass')]
        if not decos:
            continue
        deco = decos[0]
        node.decorator_list.remove(deco)
        options = {'init': True, 'repr': True, 'eq': True}
        if isinstance(deco, ast.Call):
            if deco.args:
                _refuse(deco, '@dataclass takes its options by name.', [],
                        received='@dataclass(...)')
            for kw in deco.keywords:
                if kw.arg in _DATACLASS_REFUSED:
                    if not _bool_option(kw, 'dataclass'):
                        continue                    # frozen=False and the like: the default
                    cause, tip = _DATACLASS_REFUSED[kw.arg]
                    _refuse(kw.value, cause, [tip], received='@dataclass(%s=True)' % kw.arg)
                if kw.arg not in _DATACLASS_OPTIONS:
                    _refuse(kw.value if kw.arg else deco,
                            '@dataclass(%s=...) is not translated. ApkPy translates init, repr '
                            'and eq.' % (kw.arg or '**'), [],
                            received='@dataclass(%s=...)' % (kw.arg or '**'))
                value = _bool_option(kw, 'dataclass')
                if kw.arg in options:
                    options[kw.arg] = value

        bases = [b for b in node.bases if not (isinstance(b, ast.Name) and b.id == 'object')]
        parent = bases[0].id if len(bases) == 1 and isinstance(bases[0], ast.Name) else None
        # A dataclass's fields start with its dataclass parent's, in their order;
        # one written again keeps its place and takes the new default.
        fields = [dict(f) for f in fields_of.get(parent, [])]
        body = []
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) \
                    and not _annotation_is(stmt.annotation, ('ClassVar',)):
                if _annotation_is(stmt.annotation, ('InitVar',)):
                    _refuse(stmt, 'InitVar fields are not translated yet.',
                            ['Make it a field, or pass the value to a method after making '
                             'the object.'], received='%s: InitVar[...]' % stmt.target.id)
                f = _dataclass_field(stmt, field_names, module)
                at = next((i for i, old in enumerate(fields) if old['name'] == f['name']), None)
                if at is None:
                    fields.append(f)
                else:
                    fields[at] = f
                continue
            if isinstance(stmt, ast.FunctionDef) and stmt.name == '__post_init__':
                if len(_args_of(stmt)) != 1 or stmt.args.vararg or stmt.args.kwarg:
                    _refuse(stmt, '__post_init__ takes only self here: InitVar fields are not '
                            'translated yet.', ['Write def __post_init__(self):'],
                            received='def __post_init__(...)')
                stmt.name = POST_INIT
                post_inits.add(node.name)
            body.append(stmt)

        after_default = None
        for f in fields:
            if not f['init']:
                continue
            if f['default'] is None and f['factory'] is None:
                if after_default:
                    _refuse(f['node'], "non-default argument '%s' follows default argument "
                            "'%s': a field without a default cannot come after one with a "
                            "default (CPython stops with the same error)."
                            % (f['name'], after_default),
                            ['Move %s above %s, or give it a default.'
                             % (f['name'], after_default)], received='%s: ...' % f['name'])
            else:
                after_default = f['name']
        fields_of[node.name] = fields
        if parent in post_inits:
            post_inits.add(node.name)

        written = {s.name for s in body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))}
        made = []
        if options['init'] and '__init__' not in written:
            made.append(_dataclass_init(node, fields, node.name in post_inits))
        if options['repr'] and '__repr__' not in written:
            made.append(_dataclass_repr(node, fields))
        if options['eq'] and '__eq__' not in written:
            made.append(_dataclass_eq(node, fields))
        node.body = made + body or [_loc(ast.Pass(), node)]
    ast.fix_missing_locations(tree)


# --- errors of your own -------------------------------------------------------
# class TooLong(ValueError): pass is not an object of the app: it is the name of
# one more error, which raise and except take as they take Python's own. The
# compiler writes its parent into ApkpyValues' family tree (STATE['errors']), so
# except ValueError catches it, and except TooLong catches its own subclasses.


def _forwarding_init(stmt, parent_names):
    """def __init__(self, message="..."): super().__init__(message) -> (True, default)."""
    params = _args_of(stmt)
    if stmt.decorator_list or stmt.args.vararg or stmt.args.kwarg or stmt.args.kwonlyargs \
            or len(params) != 2 or len(stmt.body) != 1:
        return False, None
    default = stmt.args.defaults[0] if stmt.args.defaults else None
    if default is not None and not (isinstance(default, ast.Constant)
                                    and isinstance(default.value, str)):
        return False, None
    call = stmt.body[0].value if isinstance(stmt.body[0], ast.Expr) else None
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            and call.func.attr == '__init__' and not call.keywords):
        return False, None
    message = params[1].arg
    owner = call.func.value
    if isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name) \
            and owner.func.id == 'super' and not owner.args:
        args = call.args
    elif isinstance(owner, ast.Name) and owner.id in parent_names and call.args \
            and isinstance(call.args[0], ast.Name) and call.args[0].id == params[0].arg:
        args = call.args[1:]                # Parent.__init__(self, message)
    else:
        return False, None
    if len(args) != 1 or not (isinstance(args[0], ast.Name) and args[0].id == message):
        return False, None
    return True, default


def _split_errors(tree):
    """Take the error classes out of the module: ({name: parent}, {name: default message})."""
    from .. import compiler
    builtin, aliases = compiler._PY_ERRORS, compiler._ERROR_ALIASES
    errors, defaults, keep = {}, {}, []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            keep.append(node)
            continue
        bases = [b for b in node.bases if not (isinstance(b, ast.Name) and b.id == 'object')]
        names = [aliases.get(b.id, b.id) if isinstance(b, ast.Name) else None for b in bases]
        known = [n for n in names if n in builtin or n in errors]
        if not known:
            keep.append(node)
            continue
        if len(bases) > 1:
            _refuse(node, 'An error class with more than one parent is not translated.',
                    ['Keep one parent: class %s(%s): pass' % (node.name, known[0])],
                    received='class %s(...)' % node.name)
        parent = known[0]
        if node.name in builtin or node.name in aliases:
            _refuse(node, 'class %s would hide Python\'s own %s.' % (node.name, node.name),
                    ['Give the error a name of its own.'], received='class %s' % node.name)
        if node.decorator_list or node.keywords:
            _refuse(node.decorator_list[0] if node.decorator_list else node,
                    'An error class is translated without decorators or keywords.', [],
                    received='class %s(...)' % node.name)
        default = None
        for stmt in node.body:
            if isinstance(stmt, ast.Pass) or (isinstance(stmt, ast.Expr)
                                              and isinstance(stmt.value, ast.Constant)
                                              and isinstance(stmt.value.value, (str, type(Ellipsis)))):
                continue                        # pass, a docstring or ...
            if isinstance(stmt, ast.FunctionDef) and stmt.name == '__init__':
                ok, default = _forwarding_init(stmt, (bases[0].id,))
                if ok:
                    continue
            _refuse(stmt,
                    'An error class of your own is translated when its body is pass or a '
                    'docstring -- its message is the text given to raise -- or an __init__ '
                    'that only hands the message on with super().__init__(message). Fields '
                    'and methods on an error are not translated yet.',
                    ['Put the detail in the message: raise %s(f"{code}: not found").'
                     % node.name, 'Or keep the value in a variable next to the raise.'],
                    received=ast_text(stmt) if not isinstance(stmt, ast.FunctionDef)
                    else 'def %s(...)' % stmt.name)
        errors[node.name] = parent
        if default is not None:
            defaults[node.name] = default.value
    tree.body = keep
    return errors, defaults


def error_parent(name):
    """The parent of an error class of the app, or None."""
    return STATE.get('errors', {}).get(name)


def error_chain(name):
    """name and its parents up to Python's own error it extends."""
    out = [name]
    while out[-1] in STATE.get('errors', {}):
        out.append(STATE['errors'][out[-1]])
    return out


def error_default(name):
    """The message raise Name() gives: the default of a forwarding __init__ in the chain."""
    for c in error_chain(name):
        if c in STATE.get('error_defaults', {}):
            return STATE['error_defaults'][c]
    return None


# --- kinds -------------------------------------------------------------------
# 'int', 'float', 'bool', 'str', 'none', 'dict', 'tuple', ('list', item kind),
# ('obj', class name: that class or one of its subclasses), None (not known),
# and _BOTTOM (nothing seen yet, while the analysis settles).

def _is_obj(kind):
    return isinstance(kind, tuple) and kind[0] == 'obj'


def _is_list(kind):
    return isinstance(kind, tuple) and kind[0] == 'list'


class _Analysis(object):
    """What each name, parameter, return and field holds, as far as the source says."""

    def __init__(self, tree, classes):
        self.tree = tree
        self.classes = classes
        self.module_defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.text_widgets = _text_widgets(tree)
        self.functions = []                    # every FunctionDef: module, methods, nested
        self.parent = {}                       # function -> enclosing function or None
        self.owner = {}                        # method -> class name
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self._add_function(node, None, None)
            elif isinstance(node, ast.ClassDef) and node.name in classes:
                for stmt in node.body:
                    if isinstance(stmt, ast.FunctionDef):
                        self._add_function(stmt, None, node.name)
        self.params = {fn: {} for fn in self.functions}
        self.locals = {fn: {} for fn in self.functions}
        self.locals[None] = {}
        self.returns = {fn: _BOTTOM for fn in self.functions}
        self.fields = {}                       # (root class, field) -> kind
        self.numbers = {}                      # (root class, field) -> _join_number
        self.poisoned_fields = set()
        self.callbacks = set()                 # functions handed around as values
        self.kit_names = set()
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    self.kit_names.add((alias.asname or alias.name).split('.')[0])
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
                    and isinstance(node.value.func, ast.Name) \
                    and node.value.func.id not in classes \
                    and node.value.func.id not in self.module_defs:
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self.kit_names.add(t.id)
        self._find_callbacks()
        self.hints = {fn: {} for fn in self.functions}
        self.lambda_owner = {}
        for fn in [None] + self.functions:
            body = self.tree.body if fn is None else fn.body
            for node in _own_walk(body):
                if isinstance(node, ast.Lambda):
                    self.lambda_owner[node] = fn
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Lambda):
                for sub in ast.walk(node.body):
                    if isinstance(sub, ast.Lambda) and sub not in self.lambda_owner:
                        self.lambda_owner[sub] = self.lambda_owner.get(node)

    def _add_function(self, fn, parent, owner):
        self.functions.append(fn)
        self.parent[fn] = parent
        if owner:
            self.owner[fn] = owner
        for node in _own_walk(fn.body):
            if isinstance(node, ast.FunctionDef):
                self._add_function(node, fn, None)

    def _find_callbacks(self):
        """Functions named without being called: buttons, on_result=, ... call them."""
        called = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                called.add(id(node.func))
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) \
                    and id(node) not in called and node.id in self.module_defs:
                self.callbacks.add(self.module_defs[node.id])

    # classes ---------------------------------------------------------------

    def chain(self, cls):
        out = []
        while cls:
            out.append(cls)
            cls = self.classes[cls].base
        return out

    def root(self, cls):
        return self.chain(cls)[-1]

    def family(self, cls):
        """cls and every class under it."""
        out = [cls]
        for child in self.classes[cls].children:
            out.extend(self.family(child))
        return out

    def find(self, cls, name):
        """(class that defines it, FunctionDef) for a method cls runs, or None."""
        for c in self.chain(cls):
            if name in self.classes[c].methods:
                return c, self.classes[c].methods[name]
        return None

    def attr(self, cls, name):
        for c in self.chain(cls):
            if name in self.classes[c].attrs:
                return c, self.classes[c].attrs[name]
        return None

    def implementations(self, cls, name):
        """{concrete class: (defining class, FunctionDef)} for cls and its subclasses."""
        out = {}
        for c in self.family(cls):
            found = self.find(c, name)
            if found:
                out[c] = found
        return out

    def common(self, a, b):
        chain = self.chain(a)
        for c in self.chain(b):
            if c in chain:
                return c
        return None

    # kinds -----------------------------------------------------------------

    def join(self, a, b):
        if a == _BOTTOM:
            return b
        if b == _BOTTOM:
            return a
        if a == b:
            return a
        if _is_list(a) and _is_list(b):
            return ('list', self.join(a[1], b[1]))
        if _is_obj(a) and _is_obj(b):
            c = self.common(a[1], b[1])
            return ('obj', c) if c else None
        return None

    def name_kind(self, name, fn):
        while True:
            if fn is None:
                return self.locals[None].get(name, None)
            if name in self.params[fn]:
                return self.params[fn][name]
            if name in self.locals[fn]:
                return self.locals[fn][name]
            fn = self.parent[fn]

    def field_kind(self, cls, name):
        if name in self.poisoned_fields:
            return None
        return self.fields.get((self.root(cls), name), _BOTTOM)

    def field_number(self, cls, name):
        """'num' when every value the field is given is a number, whole or not."""
        if name in self.poisoned_fields:
            return None
        return self.numbers.get((self.root(cls), name))

    def field_classes(self, name):
        """Roots of the classes that set *name* on their objects."""
        return [root for (root, field) in self.fields if field == name]

    def is_field(self, name):
        return any(field == name for (_, field) in self.fields)

    def _kind(self, node, fn):
        if isinstance(node, ast.Constant):
            v = node.value
            if isinstance(v, bool):
                return 'bool'
            if isinstance(v, int):
                return 'int'
            if isinstance(v, float):
                return 'float'
            if isinstance(v, str):
                return 'str'
            if v is None:
                return 'none'
            return None
        if isinstance(node, ast.JoinedStr):
            return 'str'
        if isinstance(node, ast.List):
            item = _BOTTOM
            for elt in node.elts:
                if isinstance(elt, ast.Starred):
                    return ('list', None)
                item = self.join(item, self._kind(elt, fn))
            return ('list', item)
        if isinstance(node, ast.ListComp):
            return ('list', None)
        if isinstance(node, ast.Tuple):
            return 'tuple'
        if isinstance(node, (ast.Dict, ast.DictComp)):
            return 'dict'
        if isinstance(node, ast.Name):
            return self.name_kind(node.id, fn)
        if isinstance(node, ast.Compare):
            return 'bool'
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                return 'bool'
            inner = self._kind(node.operand, fn)
            return inner if inner in ('int', 'float', _BOTTOM) else None
        if isinstance(node, ast.BoolOp):
            out = _BOTTOM
            for v in node.values:
                out = self.join(out, self._kind(v, fn))
            return out
        if isinstance(node, ast.IfExp):
            return self.join(self._kind(node.body, fn), self._kind(node.orelse, fn))
        if isinstance(node, ast.BinOp):
            left = self._kind(node.left, fn)
            right = self._kind(node.right, fn)
            if _BOTTOM in (left, right):
                return _BOTTOM if None not in (left, right) else None
            nums = ('int', 'float')
            if left in nums and right in nums:
                if isinstance(node.op, ast.Div):
                    return 'float'
                if isinstance(node.op, ast.Pow):
                    if 'float' in (left, right):
                        return 'float'
                    r = node.right
                    if isinstance(r, ast.Constant) and isinstance(r.value, int) and r.value >= 0:
                        return 'int'
                    return None
                if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Mod, ast.FloorDiv)):
                    return 'float' if 'float' in (left, right) else 'int'
                return None
            if isinstance(node.op, ast.Add):
                if left == 'str' and right == 'str':
                    return 'str'
                if _is_list(left) and _is_list(right):
                    return ('list', self.join(left[1], right[1]))
                return None
            if isinstance(node.op, ast.Mult) and {left, right} == {'str', 'int'}:
                return 'str'
            if isinstance(node.op, ast.Mod) and left == 'str':
                return 'str'
            return None
        if isinstance(node, ast.Attribute):
            return self._attribute_kind(node, fn)
        if isinstance(node, ast.Call):
            return self._call_kind(node, fn)
        if isinstance(node, ast.Subscript):
            container = self._kind(node.value, fn)
            if _is_list(container):
                return container if isinstance(node.slice, ast.Slice) else container[1]
            if container == 'str':
                return 'str'
            return None
        return None

    def _attribute_kind(self, node, fn):
        recv = node.value
        if isinstance(recv, ast.Name) and recv.id in self.classes:
            found = self.attr(recv.id, node.attr)
            return self._kind(found[1], fn) if found else None
        rk = self._kind(recv, fn)
        if _is_obj(rk):
            cls = rk[1]
            if self.find(cls, node.attr) and self.classes[self.find(cls, node.attr)[0]].kind.get(
                    node.attr) == 'property':
                return self._returns_of(cls, node.attr)
            if (self.root(cls), node.attr) in self.fields or node.attr in self.poisoned_fields:
                return self.field_kind(cls, node.attr)
            found = self.attr(cls, node.attr)
            if found:
                return self._kind(found[1], fn)
            return _BOTTOM
        if rk is None and not self._kit(recv):
            roots = self.field_classes(node.attr)
            if roots and node.attr not in self.poisoned_fields:
                out = _BOTTOM
                for root in roots:
                    out = self.join(out, self.fields[(root, node.attr)])
                return out
        return None

    def _returns_of(self, cls, name):
        out = _BOTTOM
        for _, (_, impl) in self.implementations(cls, name).items():
            out = self.join(out, self.returns.get(impl, None))
        return out

    def _call_kind(self, node, fn):
        f = node.func
        if isinstance(f, ast.Name):
            if f.id in self.classes:
                return ('obj', f.id)
            if f.id in ('int', 'len', 'ord'):
                return 'int'
            if f.id == 'round':
                return 'int' if len(node.args) == 1 else None
            if f.id == 'float':
                return 'float'
            if f.id in ('str', 'repr', 'chr', 'format'):
                return 'str'
            if f.id in ('bool', 'isinstance', 'callable', 'hasattr'):
                return 'bool'
            if f.id in ('list', 'sorted'):
                if node.args:
                    inner = self._kind(node.args[0], fn)
                    if _is_list(inner):
                        return inner
                return ('list', None)
            if f.id == 'dict':
                return 'dict'
            if f.id in self.module_defs:
                return self.returns.get(self.module_defs[f.id], None)
            return None
        if isinstance(f, ast.Attribute):
            cls = _super_class(f.value, self.owner.get(self._method_of(fn)))
            if cls is not None and cls in self.classes and self.classes[cls].base:
                found = self.find(self.classes[cls].base, f.attr)
                return self.returns.get(found[1], None) if found else None
            if isinstance(f.value, ast.Name) and f.value.id in self.classes:
                found = self.find(f.value.id, f.attr)
                return self.returns.get(found[1], None) if found else None
            if f.attr == 'get_value' and not node.args and isinstance(f.value, ast.Name) \
                    and f.value.id in self.text_widgets:
                return 'str'
            rk = self._kind(f.value, fn)
            if _is_obj(rk):
                return self._returns_of(rk[1], f.attr)
            if rk == 'str':
                if f.attr in ('split', 'rsplit', 'splitlines'):
                    return ('list', 'str')
                if f.attr in ('find', 'rfind', 'count', 'index', 'rindex'):
                    return 'int'
                if f.attr in ('startswith', 'endswith', 'isdigit', 'isalpha', 'isalnum',
                              'isspace', 'isupper', 'islower'):
                    return 'bool'
                if f.attr in _VALUE_METHODS:
                    return 'str'
            if rk is None and not self._kit(f.value) and f.attr not in _VALUE_METHODS:
                out = _BOTTOM
                hit = False
                for cls in self.classes:
                    if f.attr in self.classes[cls].methods:
                        hit = True
                        out = self.join(out, self.returns.get(self.classes[cls].methods[f.attr], None))
                if hit:
                    return out
        return None

    def _method_of(self, fn):
        while fn is not None and fn not in self.owner:
            fn = self.parent.get(fn)
        return fn

    def _kit(self, node):
        """A name of the app's toolkit or a module: not an object of a class."""
        return isinstance(node, ast.Name) and node.id in self.kit_names \
            and self.locals[None].get(node.id) is None

    # where calls go ---------------------------------------------------------

    def targets(self, call, fn):
        """[(FunctionDef, how many parameters the call does not fill)] for a call."""
        f = call.func
        if isinstance(f, ast.Name):
            if f.id in self.classes:
                found = self.find(f.id, '__init__')
                return [(found[1], 1)] if found else []
            if f.id in self.module_defs:
                return [(self.module_defs[f.id], 0)]
            return []
        if not isinstance(f, ast.Attribute):
            return []
        cls = _super_class(f.value, self.owner.get(self._method_of(fn)))
        if cls is not None:
            if cls in self.classes and self.classes[cls].base:
                found = self.find(self.classes[cls].base, f.attr)
                if found:
                    return [(found[1], 1)]
            return []
        if isinstance(f.value, ast.Name) and f.value.id in self.classes:
            found = self.find(f.value.id, f.attr)
            return [(found[1], 0)] if found else []
        rk = self._kind(f.value, fn)
        if _is_obj(rk):
            impls = self.implementations(rk[1], f.attr)
        elif rk is None and not self._kit(f.value) and f.attr not in _VALUE_METHODS:
            impls = {}
            for cls in self.classes:
                found = self.find(cls, f.attr)
                if found:
                    impls[cls] = found
        else:
            return []
        out, seen = [], set()
        for _, (owner, impl) in impls.items():
            if id(impl) in seen:
                continue
            seen.add(id(impl))
            skip = 0 if self.classes[owner].kind.get(f.attr) == 'static' else 1
            out.append((impl, skip))
        return out

    # settling ---------------------------------------------------------------

    def run(self):
        for fn in self.functions:
            params = _args_of(fn)
            defaults = fn.args.defaults
            first = len(params) - len(defaults)
            for i, p in enumerate(params):
                kind = _BOTTOM
                if i >= first:
                    kind = self._kind(defaults[i - first], None)
                self.params[fn][p.arg] = kind
            for p in fn.args.kwonlyargs:
                self.params[fn][p.arg] = None
            for p in (fn.args.vararg, fn.args.kwarg):
                if p is not None:
                    self.params[fn][p.arg] = None
            owner = self.owner.get(fn)
            if owner and params and self.classes[owner].kind.get(fn.name) != 'static':
                self.params[fn][params[0].arg] = ('obj', owner)
            for p in params + list(fn.args.kwonlyargs):
                hint = self._hint(p.annotation)
                if hint is not None:
                    self.hints[fn][p.arg] = hint
            if fn in self.callbacks or (self.parent[fn] is not None):
                for p in params:
                    if not (owner and p is params[0]):
                        self.params[fn][p.arg] = None
        for _ in range(30):
            before = self._snapshot()
            self._pass()
            if self._snapshot() == before:
                break
        self._settle()

    def _hint(self, ann):
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            try:
                from .. import ast_compat
                ann = ast_compat.normalise(ast.parse(ann.value, mode='eval')).body
            except SyntaxError:
                return None
        if isinstance(ann, ast.Name):
            if ann.id in self.classes:
                return ('obj', ann.id)
            if ann.id in ('dict', 'str'):
                return ann.id
            if ann.id == 'list':
                return ('list', None)
        if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name) \
                and ann.value.id in ('list', 'List'):
            inner = ann.slice
            if isinstance(inner, getattr(ast, 'Index', ())):
                inner = inner.value
            return ('list', self._hint(inner))
        return None

    def _snapshot(self):
        return (repr(sorted((id(f), sorted(p.items(), key=repr)) for f, p in self.params.items())),
                repr(sorted((id(f) if f else 0, sorted(v.items(), key=repr))
                            for f, v in self.locals.items())),
                repr(sorted((id(f), r) for f, r in self.returns.items())),
                repr(sorted(self.fields.items(), key=repr)), repr(sorted(self.poisoned_fields)),
                repr(sorted(self.numbers.items(), key=repr)))

    def _scopes(self):
        yield None, [s for s in self.tree.body
                     if not isinstance(s, (ast.FunctionDef, ast.ClassDef))]
        for fn in self.functions:
            yield fn, fn.body

    def _pass(self):
        for fn, body in self._scopes():
            loc = self.locals[fn]
            has_return = False
            for node in _own_walk(body):
                if isinstance(node, ast.Assign):
                    value = self._kind(node.value, fn)
                    number = self._number(node.value, fn)
                    for target in node.targets:
                        self._bind(target, node.value, value, fn, loc, number)
                elif isinstance(node, ast.AnnAssign) and node.value is not None:
                    self._bind(node.target, node.value, self._kind(node.value, fn), fn, loc,
                               self._number(node.value, fn))
                elif isinstance(node, ast.AugAssign):
                    sum_ = ast.BinOp(left=_aug_read(node.target), op=node.op, right=node.value)
                    new = self._kind(sum_, fn)
                    self._bind(node.target, None, new, fn, loc, self._number(sum_, fn))
                elif isinstance(node, (ast.For, ast.comprehension)):
                    it = self._kind(node.iter, fn)
                    item = None
                    if _is_list(it):
                        item = it[1]
                    elif it == 'str':
                        item = 'str'
                    elif isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) \
                            and node.iter.func.id == 'range':
                        item = 'int'
                    self._bind(node.target, None, item, fn, loc)
                elif isinstance(node, (ast.With, getattr(ast, 'NamedExpr', ast.With))):
                    for sub in ast.walk(node):
                        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                            loc[sub.id] = None
                elif isinstance(node, ast.ExceptHandler) and node.name:
                    loc[node.name] = None
                elif isinstance(node, ast.Return) and fn is not None:
                    has_return = True
                    value = 'none' if node.value is None else self._kind(node.value, fn)
                    self.returns[fn] = self.join(self.returns[fn], value)
                elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    self._mutation(node.value, fn)
                if isinstance(node, ast.Call):
                    self._call_site(node, fn)
            if fn is not None:
                if not has_return or not _always_returns(fn.body):
                    self.returns[fn] = self.join(self.returns[fn], 'none')
        # Lambdas: their parameters are not known, and their calls still count.
        for node, fn in self.lambda_owner.items():
            for sub in ast.walk(node.body):
                if isinstance(sub, ast.Call):
                    self._call_site(sub, fn)

    def _bind(self, target, value_node, kind, fn, loc, number=None):
        if isinstance(target, ast.Name):
            loc[target.id] = self.join(loc.get(target.id, _BOTTOM), kind)
        elif isinstance(target, ast.Attribute):
            self._store_field(target, kind, fn, number)
        elif isinstance(target, (ast.Tuple, ast.List)):
            values = value_node.elts if isinstance(value_node, (ast.Tuple, ast.List)) \
                and len(value_node.elts) == len(target.elts) else None
            for i, elt in enumerate(target.elts):
                if isinstance(elt, ast.Starred):
                    elt = elt.value
                sub = self._kind(values[i], fn) if values else None
                self._bind(elt, values[i] if values else None, sub, fn, loc)
        elif isinstance(target, ast.Subscript):
            base = target.value
            if isinstance(base, ast.Attribute):
                rk = self._kind(base.value, fn)
                if _is_obj(rk):
                    current = self.field_kind(rk[1], base.attr)
                    if _is_list(current):
                        self._store_field(base, ('list', self.join(current[1], kind)), fn)

    def _number(self, node, fn):
        """'int', 'float' or 'num' when *node* is always a number; _BOTTOM while
        that is not known yet; None when it may be something else.

        Not _kind: self.total + price, with total given 0 and 2.5, is no one
        kind, and still always a number -- the field reads its own NUMBER.
        """
        if isinstance(node, ast.BinOp) and isinstance(node.op, (
                ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)):
            a, b = self._number(node.left, fn), self._number(node.right, fn)
            if a is None or b is None:
                return None
            if _BOTTOM in (a, b):
                return _BOTTOM
            if isinstance(node.op, ast.Div):
                return 'float'
            return a if a == b else 'num'
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return self._number(node.operand, fn)
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            rk = self._kind(node.value, fn)
            if _is_obj(rk) and (self.root(rk[1]), node.attr) in self.fields:
                return self.field_number(rk[1], node.attr) or None
        kind = self._kind(node, fn)
        return kind if kind == _BOTTOM or kind in _NUMBER_KINDS else None

    def _store_field(self, target, kind, fn, number=None):
        number = kind if number is None else number
        rk = self._kind(target.value, fn)
        if isinstance(target.value, ast.Name) and target.value.id in self.classes:
            return                              # Cls.attr = ...: a class attribute
        if _is_obj(rk):
            key = (self.root(rk[1]), target.attr)
            self.fields[key] = self.join(self.fields.get(key, _BOTTOM), kind)
            self.numbers[key] = _join_number(self.numbers.get(key, _BOTTOM), number)
        elif rk is None and not self._kit(target.value):
            # An object of a class the source does not say: the value counts
            # for that field of every class it could be.
            for cls, info in self.classes.items():
                if info.base is None:
                    key = (cls, target.attr)
                    self.fields[key] = self.join(self.fields.get(key, _BOTTOM), kind)
                    self.numbers[key] = _join_number(self.numbers.get(key, _BOTTOM), number)

    def _mutation(self, call, fn):
        f = call.func
        if isinstance(f, ast.Attribute) and f.attr in ('append', 'insert', 'extend') \
                and isinstance(f.value, ast.Name) and call.args:
            self._name_mutation(f, call, fn)
            return
        if not (isinstance(f, ast.Attribute) and f.attr in ('append', 'insert', 'extend')
                and isinstance(f.value, ast.Attribute)):
            return
        rk = self._kind(f.value.value, fn)
        if not _is_obj(rk) or not call.args:
            return
        current = self.field_kind(rk[1], f.value.attr)
        if f.attr == 'extend':
            added = self._kind(call.args[0], fn)
            item = added[1] if _is_list(added) else None
        else:
            item = self._kind(call.args[-1], fn)
        if _is_list(current) or current == _BOTTOM:
            self._store_field(f.value, ('list', self.join(
                current[1] if _is_list(current) else _BOTTOM, item)), fn)

    def _name_mutation(self, f, call, fn):
        """xs.append(x) on a name: join x into the items of the list the name holds."""
        name = f.value.id
        if f.attr == 'extend':
            added = self._kind(call.args[0], fn)
            item = added[1] if _is_list(added) else None
        else:
            item = self._kind(call.args[-1], fn)
        scope = fn
        while scope is not None:
            if name in self.params[scope]:
                return                     # a parameter: the caller's list
            if name in self.locals[scope]:
                break
            scope = self.parent[scope]
        loc = self.locals[scope]
        current = loc.get(name, _BOTTOM)
        if current == _BOTTOM or _is_list(current):
            loc[name] = self.join(current, ('list', self.join(
                current[1] if _is_list(current) else _BOTTOM, item)))

    def _call_site(self, call, fn):
        targets = self.targets(call, fn)
        if not targets:
            return
        starred = any(isinstance(a, ast.Starred) for a in call.args) \
            or any(k.arg is None for k in call.keywords)
        for impl, skip in targets:
            params = _args_of(impl)[skip:]
            if starred:
                for p in params:
                    self.params[impl][p.arg] = None
                continue
            for i, arg in enumerate(call.args):
                if i < len(params):
                    name = params[i].arg
                    self.params[impl][name] = self.join(self.params[impl].get(name, _BOTTOM),
                                                        self._kind(arg, fn))
            for kw in call.keywords:
                if kw.arg in self.params[impl]:
                    self.params[impl][kw.arg] = self.join(self.params[impl][kw.arg],
                                                          self._kind(kw.value, fn))

    def _settle(self):
        def done(kind):
            if kind == _BOTTOM:
                return None
            if _is_list(kind):
                return ('list', done(kind[1]))
            return kind
        for fn in list(self.params):
            self.params[fn] = {k: done(v) for k, v in self.params[fn].items()}
        for fn in list(self.locals):
            self.locals[fn] = {k: done(v) for k, v in self.locals[fn].items()}
        self.returns = {f: done(v) for f, v in self.returns.items()}
        self.fields = {k: done(v) for k, v in self.fields.items()}
        self.numbers = {k: done(v) for k, v in self.numbers.items()}


def _aug_read(target):
    node = copy.copy(target)
    node.ctx = ast.Load()
    return node


class _ListShow(object):
    """'[' + ', '.join([...]) + ']' with the list put in by .args = [list]."""

    def __init__(self, node, comp):
        self.node = node
        self.comp = comp

    @property
    def args(self):
        return [self.comp.generators[0].iter]

    @args.setter
    def args(self, value):
        self.comp.generators[0].iter = value[0]


def _shown(found):
    return found.node if isinstance(found, _ListShow) else found


# --- writing it out ----------------------------------------------------------

def _method_name(cls, name):
    return "_apkpy_%s_%s" % (cls, name)


def _class_attr_name(cls, name):
    return "_apkpy_%s_%s" % (cls, name)


class _Writer(object):
    def __init__(self, tree, classes, order, analysis):
        self.tree = tree
        self.classes = classes
        self.order = order
        self.a = analysis
        self.temps = 0
        self.dispatchers = {}                  # method name -> needed
        self.shows = set()                     # '__str__' / '__repr__' dispatchers needed
        self.module_objects = set()
        self.getters = set()
        self.fn = None                         # the function being written, or None
        self.lambda_names = []                 # parameters of the lambdas we are in
        self.global_needs = set()              # class attributes the function writes
        self.written_attrs = set()             # (cls, attr) written anywhere

    def temp(self, prefix):
        self.temps += 1
        return "_apkpy_%s%d" % (prefix, self.temps)

    # what a receiver is -----------------------------------------------------

    def kind(self, node):
        if isinstance(node, ast.Name):
            for names in reversed(self.lambda_names):
                if node.id in names:
                    return None
        k = self.a._kind(node, self.fn)
        if k == _BOTTOM:
            k = None
        if k is None and isinstance(node, ast.Name) and self.fn is not None:
            fn = self.fn
            while fn is not None:
                if node.id in self.a.hints.get(fn, {}):
                    return self.a.hints[fn][node.id]
                if node.id in self.a.params.get(fn, {}) or node.id in self.a.locals.get(fn, {}):
                    break
                fn = self.a.parent.get(fn)
        return k

    def kit(self, node):
        if isinstance(node, ast.Name) and self.kind(node) is not None:
            return False
        if isinstance(node, ast.Name):
            for names in reversed(self.lambda_names):
                if node.id in names:
                    return False
            if self.fn is not None and self.a.name_kind(node.id, self.fn) is not None:
                return False
            if self.fn is not None and node.id in self.a.params.get(self.fn, {}):
                return self.fn in self.a.callbacks
        return self.a._kit(node)

    def is_class_ref(self, node):
        return isinstance(node, ast.Name) and node.id in self.classes \
            and not any(node.id in names for names in self.lambda_names)

    def framework_param(self, node):
        """A parameter of a function the toolkit calls: it could be anything."""
        if not isinstance(node, ast.Name) or self.fn is None:
            return False
        fn = self.fn
        return fn in self.a.callbacks and node.id in self.a.params.get(fn, {}) \
            and self.a.params[fn].get(node.id) is None

    # reads ------------------------------------------------------------------

    def read(self, recv, attr, like, cls=None):
        """recv.attr as the store's read, as the kind the field always holds."""
        node = _call(GETATTR, [recv, _const(attr, like)], like)
        if cls is not None:
            kind = self.a.field_kind(cls, attr)
            number = self.a.field_number(cls, attr)
            if kind == _BOTTOM:
                kind = None
        else:
            kind = number = None
            roots = self.a.field_classes(attr)
            if roots and attr not in self.a.poisoned_fields:
                kind = number = _BOTTOM
                for root in roots:
                    kind = self.a.join(kind, self.a.fields[(root, attr)])
                    number = _join_number(number, self.a.numbers.get((root, attr)))
                if kind == _BOTTOM:
                    kind = None
        node = self.wrap(node, kind, like)
        if kind is None and number == 'num':
            setattr(node, NUMBER, True)
        return node

    def wrap(self, node, kind, like):
        # A field that only ever holds numbers is read back as one: the text
        # is the app's own number, so the compiler parses it as it is and
        # not as Python's int()/float() of a text (READ_BACK).
        if kind == 'int':
            return _read_back(_call('int', [node], like))
        if kind == 'float':
            return _read_back(_call('float', [node], like))
        if kind == 'str':
            return _call('str', [node], like)
        if _is_list(kind):
            return _call('list', [node], like)
        if kind == 'tuple':
            from . import tuples
            setattr(node, tuples.TUPLE, True)
        return node

    def method_call(self, cls, name, recv, args, keywords, like):
        """recv.name(args) for an object of cls or one of its subclasses."""
        impls = self.a.implementations(cls, name)
        if not impls:
            if self.a.is_field(name):
                _refuse(like, 'Calling a function kept in a field (self.%s()) is not '
                        'translated.' % name, ['Call the function by its name.'])
            _refuse(like, "'%s' object has no attribute '%s'" % (cls, name),
                    ['Check the name of the method.'], received='.%s()' % name)
        distinct = {id(impl): owner for _, (owner, impl) in impls.items()}
        if len(distinct) == 1:
            owner = list(distinct.values())[0]
            if self.classes[owner].kind.get(name) == 'static':
                return _call(_method_name(owner, name), args, like, keywords)
            return _call(_method_name(owner, name), [recv] + list(args), like, keywords)
        self.dispatchers[name] = True
        return _call("_apkpy_call_%s" % name, [recv] + list(args), like, keywords)

    def any_method_call(self, name, recv, args, keywords, like):
        """recv.name(args) where the source does not say which class recv is."""
        owners = [c for c in self.order if name in self.classes[c].methods]
        impls = {}
        for c in self.order:
            found = self.a.find(c, name)
            if found:
                impls[id(found[1])] = found[0]
        if len(impls) == 1:
            owner = list(impls.values())[0]
            if self.classes[owner].kind.get(name) == 'static':
                return _call(_method_name(owner, name), args, like, keywords)
            return _call(_method_name(owner, name), [recv] + list(args), like, keywords)
        if owners:
            self.dispatchers[name] = True
            return _call("_apkpy_call_%s" % name, [recv] + list(args), like, keywords)
        return None

    def show(self, value, which, like):
        """str(obj) / repr(obj) for an object of a class: its __str__ or __repr__.

        A list of them shows each one by its __repr__, as CPython's str() of a
        list does: '[' + ', '.join([repr(x) for x in xs]) + ']'."""
        k = self.kind(value)
        if _is_list(k) and _is_obj(k[1]) and any(self.a.find(c, '__repr__')
                                                for c in self.a.family(k[1][1])):
            self.shows.add('repr')
            item = self.temp('e')
            comp = _loc(ast.ListComp(
                elt=_call("_apkpy_show_repr", [_name(item, like)], like),
                generators=[ast.comprehension(target=_name(item, like, store=True),
                                              iter=_name('_apkpy_LIST_', like), ifs=[],
                                              is_async=0)]), like)
            joined = _call(_loc(ast.Attribute(value=_const(', ', like), attr='join',
                                              ctx=ast.Load()), like), [comp], like)
            return _ListShow(_loc(ast.BinOp(left=_loc(ast.BinOp(
                left=_const('[', like), op=ast.Add(), right=joined), like),
                op=ast.Add(), right=_const(']', like)), like), comp)
        if k is None and self.any_show(which) and not (
                isinstance(value, ast.Name) and self.kit(value)):
            self.shows.add(which)
            return _call("_apkpy_show_%s" % which, [value], like)
        if not _is_obj(k):
            return None
        wanted = ('__str__', '__repr__') if which == 'str' else ('__repr__',)
        has = any(self.a.find(c, w) for c in self.a.family(k[1]) for w in wanted)
        if not has:
            return None
        picked = set()
        for c in self.a.family(k[1]):
            for w in wanted:
                found = self.a.find(c, w)
                if found:
                    picked.add((found[0], w))
                    break
            else:
                picked.add(None)
        if len(picked) == 1 and None not in picked:
            owner, name = next(iter(picked))
            return _call(_method_name(owner, name), [value], like)
        self.shows.add(which)
        return _call("_apkpy_show_%s" % which, [value], like)

    def any_show(self, which):
        wanted = ('__str__', '__repr__') if which == 'str' else ('__repr__',)
        return any(w in self.classes[c].methods for c in self.order for w in wanted)

    # expressions -------------------------------------------------------------

    def expr(self, node):
        return _Exprs(self).visit(node)


class _Exprs(ast.NodeTransformer):
    def __init__(self, writer):
        self.w = writer

    def visit_Lambda(self, node):
        node.args.defaults = [self.visit(d) for d in node.args.defaults]
        names = {a.arg for a in _args_of(node)}
        if node.args.vararg:
            names.add(node.args.vararg.arg)
        self.w.lambda_names.append(names)
        try:
            node.body = self.visit(node.body)
        finally:
            self.w.lambda_names.pop()
        return node

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and self.w.lambda_names \
                and node.id in self.w.module_objects \
                and not any(node.id in n for n in self.w.lambda_names):
            self.w.getters.add(node.id)
            return _call("_apkpy_mod_%s" % node.id, [], node)
        return node

    def visit_Attribute(self, node):
        w = self.w
        if not isinstance(node.ctx, ast.Load):
            return self.generic_visit(node)
        if node.attr == '__name__':
            v = node.value
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == 'type' \
                    and len(v.args) == 1:
                return _call(CLASSOF, [self.visit(v.args[0])], node)
            if isinstance(v, ast.Attribute) and v.attr == '__class__':
                return _call(CLASSOF, [self.visit(v.value)], node)
        recv = node.value
        attr = node.attr
        if w.is_class_ref(recv):
            cls = recv.id
            found = w.a.attr(cls, attr)
            if found:
                return _name(_class_attr_name(found[0], attr), node)
            method = w.a.find(cls, attr)
            if method and w.classes[method[0]].kind.get(attr) == 'static':
                return _name(_method_name(method[0], attr), node)
            _refuse(node, "%s.%s is not translated: ApkPy reads a class's attributes written "
                    "out and its static methods by the class name." % (cls, attr), [])
        if w.kit(recv):
            return self.generic_visit(node)
        k = w.kind(recv)
        new_recv = self.visit(recv)
        if _is_obj(k):
            cls = k[1]
            found = w.a.find(cls, attr)
            if found and w.classes[found[0]].kind.get(attr) == 'property':
                return w.method_call(cls, attr, new_recv, [], [], node)
            if found and not (w.a.root(cls), attr) in w.a.fields:
                return self._bound(cls, attr, new_recv, found[1], node)
            if (w.a.root(cls), attr) not in w.a.fields and attr not in w.a.poisoned_fields:
                const = w.a.attr(cls, attr)
                if const:
                    return _name(_class_attr_name(const[0], attr), node)
            return w.read(new_recv, attr, node, cls)
        if k is None and not w.framework_param(recv):
            if w.a.is_field(attr) or attr in w.a.poisoned_fields:
                return w.read(new_recv, attr, node)
            props = [c for c in w.order if w.classes[c].kind.get(attr) == 'property']
            if props:
                return w.any_method_call(attr, new_recv, [], [], node)
            owners = [c for c in w.order if attr in w.classes[c].methods
                      and w.classes[c].kind.get(attr) == 'method']
            if owners and attr not in _VALUE_METHODS:
                impl = w.classes[owners[0]].methods[attr]
                return self._bound(None, attr, new_recv, impl, node)
        node.value = new_recv
        return node

    def _bound(self, cls, attr, recv, impl, like):
        """obj.method without a call: command=cart.clear. A lambda that calls it."""
        params = [a.arg for a in _args_of(impl)[1:]]
        if isinstance(recv, ast.Name) and recv.id in self.w.module_objects:
            self.w.getters.add(recv.id)
            recv = _call("_apkpy_mod_%s" % recv.id, [], like)
        args = [_name(p, like) for p in params]
        if cls is not None:
            call = self.w.method_call(cls, attr, recv, args, [], like)
        else:
            call = self.w.any_method_call(attr, recv, args, [], like)
        lam = ast.Lambda(args=ast.arguments(posonlyargs=[], args=[ast.arg(arg=p, annotation=None)
                                                                   for p in params],
                                            vararg=None, kwonlyargs=[], kw_defaults=[],
                                            kwarg=None, defaults=[]),
                         body=call)
        return _loc(lam, like)

    def visit_Call(self, node):
        w = self.w
        f = node.func
        if isinstance(f, ast.Name):
            if f.id == 'isinstance' and len(node.args) == 2:
                return self._isinstance(node)
            if f.id in ('str', 'repr') and len(node.args) == 1 and not node.keywords:
                arg = self.visit(node.args[0])
                shown = w.show(node.args[0], f.id, node)
                if shown is not None:
                    shown.args = [arg]
                    return _shown(shown)
                node.args = [arg]
                return node
            if f.id == 'print':
                new_args = []
                for a in node.args:
                    shown = w.show(a, 'str', a) if not isinstance(a, ast.Starred) else None
                    va = self.visit(a)
                    if shown is not None:
                        shown.args = [va]
                        va = _shown(shown)
                    new_args.append(va)
                node.args = new_args
                node.keywords = [self.visit(k) for k in node.keywords]
                return node
            if f.id == 'super':
                _refuse(node, 'super() is translated as the receiver of a call: '
                        'super().__init__(...) or super().name(...).', [])
            if f.id in ('getattr', 'setattr', 'hasattr', 'delattr', 'vars') \
                    and node.args and _is_obj(w.kind(node.args[0])):
                _refuse(node, '%s() of an object is not translated: the name of the field '
                        'is only known when the app runs.' % f.id,
                        ['Write the field out: obj.title.'])
            return self.generic_visit(node)
        if not isinstance(f, ast.Attribute):
            return self.generic_visit(node)
        recv, m = f.value, f.attr
        args = [self.visit(a) for a in node.args]
        keywords = [self.visit(k) for k in node.keywords]
        owner_fn = w.a._method_of(w.fn)
        sup = _super_class(recv, w.a.owner.get(owner_fn))
        if sup is not None:
            if sup not in w.classes or not w.classes[sup].base:
                _refuse(node, 'super() here has no class of this file above it.', [])
            found = w.a.find(w.classes[sup].base, m)
            if not found:
                if m == '__init__':
                    return _const(None, node)  # object.__init__(): nothing to run
                _refuse(node, "super().%s(): no class above %s has it." % (m, sup), [])
            self_arg = _args_of(owner_fn)[0].arg if owner_fn and _args_of(owner_fn) else 'self'
            if w.classes[found[0]].kind.get(m) == 'static':
                return _call(_method_name(found[0], m), args, node, keywords)
            return _call(_method_name(found[0], m), [_name(self_arg, node)] + args, node, keywords)
        if w.is_class_ref(recv):
            found = w.a.find(recv.id, m)
            if not found:
                _refuse(node, "%s has no method %s." % (recv.id, m), [])
            return _call(_method_name(found[0], m), args, node, keywords)
        if w.kit(recv):
            f.value = self.visit(recv)
            node.args, node.keywords = args, keywords
            return node
        k = w.kind(recv)
        if _is_obj(k):
            return w.method_call(k[1], m, self.visit(recv), args, keywords, node)
        if k is None and not w.framework_param(recv):
            is_method = any(m in w.classes[c].methods for c in w.order)
            if is_method and m not in _VALUE_METHODS:
                call = w.any_method_call(m, self.visit(recv), args, keywords, node)
                if call is not None:
                    return call
            elif is_method and m in _VALUE_METHODS and not isinstance(recv, ast.Attribute):
                owners = [c for c in w.order if m in w.classes[c].methods]
                _refuse(node,
                        'ApkPy cannot tell whether %s is a %s or a value with its own %s(): '
                        'the source does not say which.' % (ast_text(recv), owners[0], m),
                        ['Say it with a type: def f(x: %s):' % owners[0],
                         'Or give the method a name of its own.'])
        f.value = self.visit(recv)
        node.args, node.keywords = args, keywords
        return node

    def _isinstance(self, node):
        w = self.w
        value, types = node.args
        names = types.elts if isinstance(types, ast.Tuple) else [types]
        mine = [n for n in names if w.is_class_ref(n)]
        if not mine:
            return self.generic_visit(node)
        if len(mine) != len(names):
            _refuse(node, 'isinstance() with a class of this file and a type of Python together '
                    'is not translated yet.', ['Ask about each one on its own: '
                                                'isinstance(x, Task) or isinstance(x, str).'])
        v = self.visit(value)
        tests = [_call(ISA, [v if i == 0 else copy.deepcopy(v), _const(n.id, node)], node)
                 for i, n in enumerate(mine)]
        if len(tests) == 1:
            return tests[0]
        return _loc(ast.BoolOp(op=ast.Or(), values=tests), node)

    def visit_Compare(self, node):
        w = self.w
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Is, ast.IsNot)):
            left, right = node.left, node.comparators[0]
            singleton = any(isinstance(x, ast.Constant) and (x.value is None or isinstance(x.value, bool))
                            for x in (left, right))
            if not singleton and (_is_obj(w.kind(left)) or _is_obj(w.kind(right))):
                # The same object is the same text: is, without __eq__.
                op = ast.Eq() if isinstance(node.ops[0], ast.Is) else ast.NotEq()
                return _loc(ast.Compare(left=self.visit(left), ops=[op],
                                        comparators=[self.visit(right)]), node)
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq)):
            k = w.kind(node.left)
            if _is_obj(k) and any(w.a.find(c, '__eq__') for c in w.a.family(k[1])):
                w.dispatchers['__eq__'] = True
                call = _call("_apkpy_call___eq__", [self.visit(node.left),
                                                     self.visit(node.comparators[0])], node)
                if isinstance(node.ops[0], ast.NotEq):
                    return _loc(ast.UnaryOp(op=ast.Not(), operand=call), node)
                return call
        return self.generic_visit(node)

    def visit_FormattedValue(self, node):
        w = self.w
        if node.format_spec is None and node.conversion in (-1, 115, 114):
            which = 'repr' if node.conversion == 114 else 'str'
            shown = w.show(node.value, which, node)
            if shown is not None:
                shown.args = [self.visit(node.value)]
                node.value = _shown(shown)
                node.conversion = -1
                return node
        return self.generic_visit(node)


def ast_text(node):
    from ..unsupported import describe
    return describe(node)


# --- statements ----------------------------------------------------------------

def _field_target(w, target):
    """(receiver, attr, class or None) when target is an object's field."""
    if not isinstance(target, ast.Attribute):
        return None
    recv = target.value
    if w.is_class_ref(recv):
        return None
    if w.kit(recv):
        return None
    k = w.kind(recv)
    if _is_obj(k):
        return recv, target.attr, k[1]
    if k is None and not w.framework_param(recv) and (w.a.is_field(target.attr)
                                                         or target.attr in w.a.poisoned_fields):
        return recv, target.attr, None
    return None


def _root_field(w, node):
    """For obj.f[k]... or obj.f: (obj, f, cls, [subscripts], the obj.f node)."""
    keys = []
    while isinstance(node, ast.Subscript):
        keys.append(node)
        node = node.value
    found = _field_target(w, node)
    if found is None:
        return None
    return found + (list(reversed(keys)), node)


def _replace_root(node, root_attr, temp_name, w=None):
    """A copy of obj.f[k]... with obj.f replaced by the temporary name."""
    if node is root_attr:
        return _name(temp_name, node)
    new = copy.copy(node)
    new.value = _replace_root(node.value, root_attr, temp_name, w)
    if w is not None and isinstance(new, ast.Subscript):
        new.slice = w.expr(new.slice)
    return new


class _Statements(object):
    def __init__(self, writer):
        self.w = writer

    def block(self, statements):
        out = []
        for stmt in statements:
            out.extend(self.statement(stmt))
        return out

    def _sink(self, recv, attr, value, like, cls):
        """_apkpy_oN = __apkpy_setattr__(recv, "attr", value)"""
        call = _call(SETATTR, [recv, _const(attr, like), value], like)
        return _assign(self.w.temp('o'), call, like)

    def _receiver(self, recv, like, out):
        """recv as a name read once: itself if it is one, else a temporary."""
        new = self.w.expr(recv)
        if isinstance(new, ast.Name):
            return new
        t = self.w.temp('r')
        out.append(_assign(t, new, like))
        return _name(t, like)

    def _class_attr_write(self, target, value_node, like, aug_op=None):
        w = self.w
        cls = target.value.id
        found = w.a.attr(cls, target.attr)
        owner = found[0] if found else cls
        if not found:
            _refuse(like, 'Giving a class a new attribute from outside it (%s.%s = ...) is not '
                    'translated.' % (cls, target.attr),
                    ['Write it in the class: class %s: %s = 0' % (cls, target.attr)])
        name = _class_attr_name(owner, target.attr)
        w.global_needs.add(name)
        if aug_op is not None:
            return [_loc(ast.AugAssign(target=_name(name, like, store=True), op=aug_op,
                                       value=w.expr(value_node)), like)]
        return [_assign(name, w.expr(value_node), like)]

    def statement(self, stmt):
        w = self.w
        for field in ('body', 'orelse', 'finalbody'):
            inner = getattr(stmt, field, None)
            if isinstance(inner, list) and inner and isinstance(inner[0], ast.stmt) \
                    and not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                setattr(stmt, field, self.block(inner))
        for handler in getattr(stmt, 'handlers', []) or []:
            handler.body = self.block(handler.body)
            if handler.type is not None:
                handler.type = w.expr(handler.type)

        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return [stmt]                      # written on its own (nested functions too)

        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            target = stmt.targets[0]
            if isinstance(target, ast.Attribute) and w.is_class_ref(target.value):
                return self._class_attr_write(target, stmt.value, stmt)
            found = _field_target(w, target)
            if found:
                recv, attr, cls = found
                out = []
                value = w.expr(stmt.value)
                if not isinstance(recv, ast.Name):
                    t = w.temp('v')
                    out.append(_assign(t, value, stmt))
                    value = _name(t, stmt)
                    recv = self._receiver(recv, stmt, out)
                else:
                    recv = w.expr(recv)
                out.append(self._sink(recv, attr, value, stmt, cls))
                return out
            if isinstance(target, (ast.Tuple, ast.List)) and any(
                    _field_target(w, e) or _root_field(w, e) for e in target.elts
                    if not isinstance(e, ast.Starred)):
                temps = [w.temp('u') for _ in target.elts]
                if any(isinstance(e, ast.Starred) for e in target.elts):
                    _refuse(stmt, 'Unpacking into fields with a * is not translated.', [])
                out = [_assign(_loc(ast.Tuple(elts=[_name(t, stmt, store=True) for t in temps],
                                              ctx=ast.Store()), stmt), w.expr(stmt.value), stmt)]
                for elt, t in zip(target.elts, temps):
                    out.extend(self.statement(_assign(elt, _name(t, stmt), stmt)))
                return out
            rooted = _root_field(w, target) if isinstance(target, ast.Subscript) else None
            if rooted:
                return self._through_temp(stmt, rooted, lambda t, root: _assign(
                    _replace_root(target, root, t, w), w.expr(stmt.value), stmt))
            if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Attribute) \
                    and stmt.value.func.attr in _MUTATORS:
                rooted = _root_field(w, stmt.value.func.value)
                if rooted:
                    return self._through_temp(stmt, rooted, lambda t, root: _assign(
                        target, _mutator_call(w, stmt.value, root, t), stmt))
            stmt.value = w.expr(stmt.value)
            return [stmt]

        if isinstance(stmt, ast.AugAssign):
            target = stmt.target
            if isinstance(target, ast.Attribute) and w.is_class_ref(target.value):
                return self._class_attr_write(target, stmt.value, stmt, aug_op=stmt.op)
            found = _field_target(w, target)
            if found:
                recv, attr, cls = found
                out = []
                recv = self._receiver(recv, stmt, out)
                current = w.read(recv, attr, stmt, cls)
                new = _loc(ast.BinOp(left=current, op=stmt.op, right=w.expr(stmt.value)), stmt)
                out.append(self._sink(copy.copy(recv), attr, new, stmt, cls))
                return out
            rooted = _root_field(w, target) if isinstance(target, ast.Subscript) else None
            if rooted:
                return self._through_temp(stmt, rooted, lambda t, root: _loc(ast.AugAssign(
                    target=_replace_root(target, root, t, w), op=stmt.op,
                    value=w.expr(stmt.value)), stmt))
            stmt.value = w.expr(stmt.value)
            return [stmt]

        if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            return self.statement(_assign(stmt.target, stmt.value, stmt))

        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call) \
                and isinstance(stmt.value.func, ast.Attribute) \
                and stmt.value.func.attr in _MUTATORS:
            rooted = _root_field(w, stmt.value.func.value)
            if rooted:
                return self._through_temp(stmt, rooted, lambda t, root: _expr(
                    _mutator_call(w, stmt.value, root, t), stmt))

        if isinstance(stmt, ast.Delete):
            for target in stmt.targets:
                if _field_target(w, target):
                    _refuse(stmt, 'del of an object\'s field is not translated.',
                            ['Give it None instead: obj.%s = None' % target.attr])
            if len(stmt.targets) == 1:
                rooted = _root_field(w, stmt.targets[0])
                if rooted and rooted[3]:
                    return self._through_temp(stmt, rooted, lambda t, root: _loc(ast.Delete(
                        targets=[_replace_root(stmt.targets[0], root, t, w)]), stmt))

        if isinstance(stmt, (ast.For, ast.AsyncFor)) and (
                _field_target(w, stmt.target) or (isinstance(stmt.target, ast.Tuple) and any(
                    _field_target(w, e) for e in stmt.target.elts))):
            _refuse(stmt, 'A for loop that walks into an object\'s field is not translated.',
                    ['Walk into a name, and give the field its value inside the loop.'])

        return [self._expressions(stmt)]

    def _through_temp(self, stmt, rooted, make):
        """t = obj.f; <the statement on t>; obj.f = t"""
        w = self.w
        recv, attr, cls, keys, root = rooted
        out = []
        recv = self._receiver(recv, stmt, out)
        t = w.temp('t')
        out.append(_assign(t, w.read(recv, attr, stmt, cls), stmt))
        out.append(make(t, root))
        out.append(self._sink(copy.copy(recv), attr, _name(t, stmt), stmt, cls))
        return out

    def _expressions(self, stmt):
        w = self.w
        for field, value in ast.iter_fields(stmt):
            if isinstance(value, ast.expr):
                setattr(stmt, field, w.expr(value))
            elif isinstance(value, list) and value and isinstance(value[0], ast.expr):
                setattr(stmt, field, [w.expr(v) for v in value])
            elif isinstance(value, list) and value and isinstance(value[0], ast.withitem):
                for item in value:
                    item.context_expr = w.expr(item.context_expr)
        return stmt


def _mutator_call(w, call, root, temp):
    """obj.f.append(x) / obj.f[k].append(x) with obj.f as the temporary."""
    func = call.func
    receiver = _replace_root(func.value, root, temp, w) if func.value is not root \
        else _name(temp, call)
    new = copy.copy(call)
    new.func = _loc(ast.Attribute(value=receiver, attr=func.attr, ctx=ast.Load()), func)
    new.args = [w.expr(a) for a in call.args]
    new.keywords = [w.expr(k) for k in call.keywords]
    return new


# --- the module ------------------------------------------------------------------

_UI_CALLS = frozenset((
    'button', 'inputs', 'input_field', 'label', 'container', 'card', 'image', 'video',
    'camera_view', 'map_view', 'avatar', 'list_row', 'list_view', 'virtual_collection',
    'markdown', 'rich_text', 'tree_view', 'carousel', 'grid', 'spinner', 'skeleton',
    'empty_state', 'error_state', 'upload_button', 'pager', 'tab', 'chart', 'chips',
    'segmented', 'bottom_sheet', 'modal', 'menu', 'popup_menu', 'context_menu',
    'date_picker', 'time_picker', 'drawer', 'app_bar', 'sliver_app_bar', 'Screen',
    'responsive', 'tooltip', 'lifecycle', 'run', 'Theme', 'state'))


def _handed_methods(stmt, classes, analysis):
    """The receivers of command=cart.clear in a line that builds the screen: the
    method is called on a click, so the object is not read when the screen is made."""
    skip = set()
    for node in _own_walk([stmt]):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _UI_CALLS):
            continue
        for kw in node.keywords:
            v = kw.value
            if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) \
                    and not analysis.is_field(v.attr) \
                    and any(classes[c].kind.get(v.attr) == 'method' for c in classes):
                skip.add(id(v.value))
    return skip


def _touches(stmt, classes, module_objects, analysis):
    """True when a module-level statement makes or reads an object outside a lambda."""
    skip = _handed_methods(stmt, classes, analysis)
    for node in _own_walk([stmt]):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in classes:
            return True
        if isinstance(node, ast.Name) and node.id in module_objects and id(node) not in skip:
            return True
    if isinstance(stmt, ast.Assign):
        k = analysis._kind(stmt.value, None)
        if _is_obj(k) or (_is_list(k) and _is_obj(k[1])):
            return True
    return False


def _builds_ui(stmt):
    for node in _own_walk([stmt]):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in _UI_CALLS:
            return True
    return False


def _placeholder(kind, like):
    if kind == 'int':
        return _const(0, like)
    if kind == 'float':
        return _const(0.0, like)
    if kind == 'bool':
        return _const(False, like)
    if _is_list(kind):
        return _loc(ast.List(elts=[], ctx=ast.Load()), like)
    if kind == 'dict':
        return _loc(ast.Dict(keys=[], values=[]), like)
    return _const("", like)


def _references(fn, names):
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and node.id in names:
            return True
    return False


def _strip_ensure_targets(fn_name):
    return fn_name in (ENSURE, INIT) or fn_name.startswith("_apkpy_mod_")


def desugar(tree):
    """Rewrite the module's classes as functions of the module and object-store calls."""
    STATE['used'] = False
    STATE['parents'] = {}
    STATE['errors'], STATE['error_defaults'] = {}, {}
    if not any(isinstance(n, ast.ClassDef) for n in tree.body):
        return tree
    _rewrite_dataclasses(tree)
    STATE['errors'], STATE['error_defaults'] = _split_errors(tree)
    if not any(isinstance(n, ast.ClassDef) for n in tree.body):
        return tree
    classes, order = _collect(tree)
    analysis = _Analysis(tree, classes)
    analysis.run()
    w = _Writer(tree, classes, order, analysis)
    stmts = _Statements(w)

    # Class attributes that something writes (Cls.count += 1) become globals.
    written = set()
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) \
                    and t.value.id in classes:
                found = analysis.attr(t.value.id, t.attr)
                if found:
                    written.add(_class_attr_name(found[0], t.attr))
    # An attribute both of the class and of its objects: each object starts with
    # the class's value, which is what reading it before setting it gives.
    shadowed = {}
    for cls in order:
        for attr in classes[cls].attrs:
            if (analysis.root(cls), attr) in analysis.fields:
                if _class_attr_name(cls, attr) in written:
                    _refuse(classes[cls].node, '%s.%s is both a class attribute that changes '
                            'and an attribute of each object.' % (cls, attr),
                            ['Give one of them another name.'])
                shadowed.setdefault(cls, []).append(attr)

    # Module level: what makes or uses objects runs once, in _apkpy_init.
    moved, kept = [], []
    module_objects = set()
    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
            kept.append(stmt)
            continue
        if isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Compare) \
                and isinstance(stmt.test.left, ast.Name) and stmt.test.left.id == '__name__':
            kept.append(stmt)
            continue
        if _touches(stmt, classes, module_objects, analysis):
            if _builds_ui(stmt):
                _refuse(stmt, 'This line builds a part of the screen from an object. The screen '
                        'is made from the top of the file before any object exists on the '
                        'phone.', ['Set the value when the screen opens: '
                                   'lifecycle(home, on_mount=fill) with fill() calling '
                                   'set_value().', 'Or pass a lambda: command=lambda: cart.clear().'])
            moved.append(stmt)
            for node in ast.walk(stmt):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    if isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                        module_objects.add(node.id)
            kept.append(('moved', stmt))
            continue
        kept.append(stmt)
    w.module_objects = module_objects
    module_names = {t.id for s in tree.body if isinstance(s, (ast.Assign, ast.AnnAssign))
                    for t in (s.targets if isinstance(s, ast.Assign) else [s.target])
                    if isinstance(t, ast.Name)}
    ensure_names = set(module_objects)
    for stmt in moved:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and node.id in module_names:
                ensure_names.add(node.id)

    head = []
    # The class attributes, as module names.
    for cls in order:
        for attr, value in classes[cls].attrs.items():
            head.append(_assign(_class_attr_name(cls, attr), copy.deepcopy(value),
                                classes[cls].node))
    out = []
    placed = set()
    for item in kept:
        if isinstance(item, tuple):
            stmt = item[1]
            if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for node in ast.walk(stmt):
                    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) \
                            and node.id not in placed:
                        placed.add(node.id)
                        out.append(_assign(node.id, _placeholder(
                            analysis.locals[None].get(node.id), stmt), stmt))
            continue
        if isinstance(item, ast.ClassDef):
            continue
        out.append(item)

    # The functions of the module, written with the objects in mind.
    for fn in [n for n in out if isinstance(n, ast.FunctionDef)]:
        _write_function(w, stmts, fn)
    # Lambdas at the top of the file (command=lambda: cart.clear()).
    w.fn = None
    for i, stmt in enumerate(out):
        if isinstance(stmt, ast.FunctionDef):
            continue
        out[i] = stmts._expressions(stmt) if not isinstance(stmt, (ast.Import, ast.ImportFrom)) \
            else stmt

    # Methods, constructors.
    generated = []
    for cls in order:
        info = classes[cls]
        for name, method in info.methods.items():
            fn = method
            fn.decorator_list = []
            fn.name = _method_name(cls, name)
            _write_function(w, stmts, fn, original=method)
            generated.append(fn)
        generated.append(_constructor(analysis, cls, shadowed))

    # _apkpy_init: what the top of the file did with objects, in order.
    if moved:
        w.fn = None
        body = []
        for stmt in moved:
            body.extend(stmts.statement(stmt))
        names = sorted(module_objects | w.global_needs)
        w.global_needs = set()
        init_body = ([_loc(ast.Global(names=names), moved[0])] if names else []) + body
        init = _loc(ast.FunctionDef(name=INIT, args=_no_args(), body=init_body,
                                    decorator_list=[], returns=None, type_comment=None),
                    moved[0])
        generated.append(init)

    # Dispatchers.
    for name in sorted(w.dispatchers):
        generated.append(_dispatcher(analysis, order, name, tree))
    for which in sorted(w.shows):
        generated.append(_show_dispatcher(analysis, order, which, tree))

    # _apkpy_ensure() at the top of each function that uses an object of the module.
    if moved:
        like = moved[0]
        head.insert(0, _assign(READY, _const(False, like), like))
        every = [n for n in out if isinstance(n, ast.FunctionDef)] + generated
        for fn in every:
            if not _strip_ensure_targets(fn.name) and _references(fn, ensure_names):
                fn.body.insert(0, _expr(_call(ENSURE, [], fn), fn))
        for name in sorted(w.getters):
            generated.append(_getter(name, like))
        generated.insert(0, _ensure_function(like))

    # Imports, the class attributes, the functions written here, then the
    # module in its own order.
    imports = [s for s in out if isinstance(s, (ast.Import, ast.ImportFrom))]
    rest = [s for s in out if not isinstance(s, (ast.Import, ast.ImportFrom))]
    tree.body = imports + head + generated + rest
    STATE['used'] = True
    STATE['parents'] = {c: classes[c].base for c in order if classes[c].base}
    ast.fix_missing_locations(tree)
    return tree


def _no_args(params=(), defaults=()):
    return ast.arguments(posonlyargs=[], args=[ast.arg(arg=p, annotation=None) for p in params],
                         vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None,
                         defaults=list(defaults))


def _write_function(w, stmts, fn, original=None):
    w.fn = original if original is not None else fn
    w.global_needs = set()
    fn.body = stmts.block(fn.body)
    for arg in _args_of(fn):
        arg.annotation = None
    fn.returns = None
    if w.global_needs:
        already = set()
        for node in fn.body:
            if isinstance(node, ast.Global):
                already.update(node.names)
        missing = sorted(w.global_needs - already)
        if missing:
            fn.body.insert(0, _loc(ast.Global(names=missing), fn))
    # Functions written inside this one keep their own bodies: write them too.
    for node in _own_walk(fn.body):
        if isinstance(node, ast.FunctionDef):
            saved = w.fn
            _write_function(w, stmts, node)
            w.fn = saved
    w.fn = None


def _constructor(analysis, cls, shadowed):
    info = analysis.classes[cls]
    like = info.node
    found = analysis.find(cls, '__init__')
    params, defaults = [], []
    if found:
        init = found[1]
        params = [a.arg for a in _args_of(init)[1:]]
        defaults = [copy.deepcopy(d) for d in init.args.defaults]
    body = [_assign('self', _call(NEW, [_const(cls, like)], like), like)]
    for c in reversed(analysis.chain(cls)):
        for attr in shadowed.get(c, []):
            body.append(_assign('_apkpy_s_%s' % attr, _call(
                SETATTR, [_name('self', like), _const(attr, like),
                          _name(_class_attr_name(c, attr), like)], like), like))
    if found:
        body.append(_expr(_call(_method_name(found[0], '__init__'),
                                [_name('self', like)] + [_name(p, like) for p in params], like),
                          like))
    body.append(_loc(ast.Return(value=_name('self', like)), like))
    return _loc(ast.FunctionDef(name=cls, args=_no_args(params, defaults), body=body,
                                decorator_list=[], returns=None, type_comment=None), like)


def _dispatcher(analysis, order, name, tree):
    """_apkpy_call_name(self, ...): the method of the object's class."""
    impls = {}
    for c in order:
        found = analysis.find(c, name)
        if found:
            impls.setdefault(id(found[1]), (found, []))[1].append(c)
    first = list(impls.values())[0][0][1]
    params = [a.arg for a in _args_of(first)]
    for (owner, impl), _ in impls.values():
        other = [a.arg for a in _args_of(impl)]
        if len(other) != len(params) or len(impl.args.defaults) != len(first.args.defaults) \
                or any(ast.dump(x) != ast.dump(y) for x, y in zip(impl.args.defaults,
                                                                 first.args.defaults)):
            _refuse(impl, 'Two classes have a method %s() with different parameters, and the '
                    'object it is called on could be either.' % name,
                    ['Give both the same parameters and defaults.'])
    like = first
    body = [_assign('_apkpy_c', _call(CLASSOF, [_name(params[0], like)], like), like)]
    for (owner, impl), classes in impls.values():
        test = _loc(ast.BoolOp(op=ast.Or(), values=[
            _loc(ast.Compare(left=_name('_apkpy_c', like), ops=[ast.Eq()],
                             comparators=[_const(c, like)]), like) for c in classes]), like) \
            if len(classes) > 1 else _loc(ast.Compare(left=_name('_apkpy_c', like), ops=[ast.Eq()],
                                                      comparators=[_const(classes[0], like)]), like)
        call = _call(_method_name(owner, name), [_name(p, like) for p in params], like)
        body.append(_loc(ast.If(test=test, body=[_loc(ast.Return(value=call), like)], orelse=[]),
                         like))
    if name == '__eq__':
        body.append(_loc(ast.Return(value=_loc(ast.Compare(
            left=_name(params[0], like), ops=[ast.Eq()],
            comparators=[_name(params[1], like)]), like)), like))
    else:
        body.append(_loc(ast.Raise(exc=_call('AttributeError', [_loc(ast.BinOp(
            left=_const("'", like), op=ast.Add(), right=_loc(ast.BinOp(
                left=_name('_apkpy_c', like), op=ast.Add(),
                right=_const("' object has no attribute '%s'" % name, like)), like)), like)], like),
            cause=None), like))
    return _loc(ast.FunctionDef(name="_apkpy_call_%s" % name,
                                args=_no_args(params, [copy.deepcopy(d) for d in first.args.defaults]),
                                body=body, decorator_list=[], returns=None, type_comment=None),
                tree.body[0])


def _show_dispatcher(analysis, order, which, tree):
    """_apkpy_show_str(x) / _apkpy_show_repr(x): __str__/__repr__, or CPython's default."""
    like = tree.body[0]
    body = [_assign('_apkpy_c', _call(CLASSOF, [_name('x', like)], like), like)]
    groups = {}
    for c in order:
        found = analysis.find(c, '__str__') if which == 'str' else None
        method = '__str__'
        if not found:
            found = analysis.find(c, '__repr__')
            method = '__repr__'
        if found:
            groups.setdefault((found[0], method), []).append(c)
    for (owner, method), classes in groups.items():
        tests = [_loc(ast.Compare(left=_name('_apkpy_c', like), ops=[ast.Eq()],
                                  comparators=[_const(c, like)]), like) for c in classes]
        test = tests[0] if len(tests) == 1 else _loc(ast.BoolOp(op=ast.Or(), values=tests), like)
        call = _call(_method_name(owner, method), [_name('x', like)], like)
        body.append(_loc(ast.If(test=test, body=[_loc(ast.Return(value=call), like)], orelse=[]),
                         like))
    body.append(_loc(ast.Return(value=_call('str', [_name('x', like)], like)), like))
    return _loc(ast.FunctionDef(name="_apkpy_show_%s" % which, args=_no_args(['x']), body=body,
                                decorator_list=[], returns=None, type_comment=None), like)


def _ensure_function(like):
    body = [
        _loc(ast.Global(names=[READY]), like),
        _loc(ast.If(test=_loc(ast.UnaryOp(op=ast.Not(), operand=_name(READY, like)), like),
                    body=[_assign(READY, _const(True, like), like),
                          _expr(_call(INIT, [], like), like)],
                    orelse=[]), like),
    ]
    return _loc(ast.FunctionDef(name=ENSURE, args=_no_args(), body=body, decorator_list=[],
                                returns=None, type_comment=None), like)


def _getter(name, like):
    body = [_expr(_call(ENSURE, [], like), like),
            _loc(ast.Return(value=_name(name, like)), like)]
    return _loc(ast.FunctionDef(name="_apkpy_mod_%s" % name, args=_no_args(), body=body,
                                decorator_list=[], returns=None, type_comment=None), like)


# --- the store, in Java --------------------------------------------------------

def value_java(node, val_to_java, rhs_java):
    """The Java of one of the five calls of the store."""
    name = node.func.id
    args = node.args
    if name == NEW:
        return 'ApkpyObjects.create("%s")' % args[0].value
    if name == GETATTR:
        return 'ApkpyObjects.get(String.valueOf(%s), "%s")' % (val_to_java(args[0]), args[1].value)
    if name == SETATTR:
        return 'ApkpyObjects.set(String.valueOf(%s), "%s", String.valueOf(%s))' % (
            val_to_java(args[0]), args[1].value, rhs_java(args[2], val_to_java))
    if name == ISA:
        return ('(ApkpyObjects.isInstance(String.valueOf(%s), "%s") ? ApkpyValues.TRUE '
                ': ApkpyValues.FALSE)' % (val_to_java(args[0]), args[1].value))
    if name == CLASSOF:
        return 'ApkpyObjects.classOf(String.valueOf(%s))' % val_to_java(args[0])
    raise ValueError(name)


def is_intrinsic(node):
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
        and node.func.id in INTRINSICS


def objects_java(package):
    """ApkpyObjects.java: the fields of every object, by the text the object is."""
    parents = "".join('        PARENTS.put("%s", "%s");\n' % (c, p)
                      for c, p in sorted(STATE['parents'].items()))
    return '''package %(package)s;

import java.util.HashMap;

/** The objects of the app's classes, kept as CPython keeps them: one per
 *  constructor call, changed in place, reached from every value that is it.
 *  The value is the text CPython shows for an object without __str__,
 *  <__main__.Task object at 0x...>, and the key of its fields here. */
public final class ApkpyObjects {
    private static final HashMap<String, HashMap<String, String>> FIELDS = new HashMap<>();
    private static final HashMap<String, String> CLASSES = new HashMap<>();
    private static final HashMap<String, String> PARENTS = new HashMap<>();
    private static long next = 0x7f3a5c000000L;

    static {
%(parents)s    }

    private ApkpyObjects() { }

    public static synchronized String create(String cls) {
        next += 0x40;
        String handle = "<__main__." + cls + " object at 0x" + Long.toHexString(next) + ">";
        FIELDS.put(handle, new HashMap<String, String>());
        CLASSES.put(handle, cls);
        return handle;
    }

    public static synchronized String get(String handle, String name) {
        HashMap<String, String> fields = FIELDS.get(handle);
        if (fields == null || !fields.containsKey(name)) {
            throw new ApkpyValues.Raised("AttributeError",
                    "'" + typeName(handle) + "' object has no attribute '" + name + "'");
        }
        return fields.get(name);
    }

    public static synchronized String set(String handle, String name, String value) {
        HashMap<String, String> fields = FIELDS.get(handle);
        if (fields == null) {
            throw new ApkpyValues.Raised("AttributeError",
                    "'" + typeName(handle) + "' object has no attribute '" + name + "'");
        }
        fields.put(name, value == null ? ApkpyValues.NONE : value);
        return handle;
    }

    public static synchronized boolean isInstance(String value, String cls) {
        String c = CLASSES.get(value);
        while (c != null) {
            if (c.equals(cls)) return true;
            c = PARENTS.get(c);
        }
        return false;
    }

    public static synchronized String classOf(String value) {
        return typeName(value);
    }

    private static String typeName(String value) {
        String c = CLASSES.get(value);
        return c != null ? c : ApkpyValues.pyType(value);
    }
}
''' % {'package': package, 'parents': parents}
