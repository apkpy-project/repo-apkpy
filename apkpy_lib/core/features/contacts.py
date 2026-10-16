"""Contacts contract and conditional native generation. No broad write access."""
from __future__ import annotations
import ast
import json
import re
from pathlib import Path
from ...diagnostics import ApkpyError

VERBS = ("pick", "list", "get", "create", "edit", "settings")
COMMAND_TYPES = frozenset("contacts_" + v for v in VERBS)
REASONS = {
    "cancelled": "No contact was selected.",
    "permission_denied": "Reading the address book was not allowed.",
    "permission_blocked": "Allow Contacts in app settings before trying again.",
    "not_found": "This contact no longer exists.",
    "unsupported": "No compatible contacts application is available.",
    "busy": "Finish the current contacts operation first.",
    "invalid": "Check the contact reference, picker kind or page bounds.",
    "unavailable": "Contacts requires an active foreground screen.",
    "unknown": "Contacts failed; technical details are in the log.",
}
FIELDS = ("id", "uri", "name", "phone", "email", "phones", "emails")
SPECS = {
    "pick": (("kind",), {"kind": "phone"}),
    "list": (("query", "limit", "offset"), {"query": "", "limit": 50, "offset": 0}),
    "get": (("id",), {}),
    "create": (("name", "phone", "email"), {"name": "", "phone": "", "email": ""}),
    "edit": (("id",), {}),
    "settings": ((), {}),
}

def positional_slots(verb):
    """Os lugares que uma chamada pode preencher por posicao, pela ordem.

    Uma funcao e nao uma conta feita a mao em dois sitios: o teste de paridade
    em tests/features/test_contacts.py le isto, por isso se alguem tirar daqui
    o on_result o teste fica vermelho em vez de continuar a concordar consigo
    proprio."""
    return SPECS[verb][0] + ("on_result",)

def named(call):
    return isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == "contacts"

def is_call(call):
    return named(call) and call.func.attr in VERBS

def fail(message, node):
    raise ApkpyError(message, code="U2033", line=getattr(node, "lineno", 0),
        expected="contacts." + ", contacts.".join(v + "()" for v in VERBS),
        suggestions=["Use contacts.pick(on_result=picked); picked accepts (ok, value)."],
        docs="https://repo-apkpy.pages.dev/guides/contacts/")

def arguments(call):
    verb = call.func.attr
    if verb not in SPECS:
        fail("Unknown contacts method: " + verb, call)
    names, defaults = SPECS[verb]
    # `on_result` e o ultimo lugar posicional, como na assinatura que a lib
    # expoe: contacts.pick(kind="phone", on_result=None). SPECS so guarda os
    # nomes das opcoes, por isso o compilador aceitava um argumento a menos
    # que o Previewer e `contacts.pick("phone", picked)` corria no computador
    # e parava o build. Ninguem decidiu isso -- faltava o callback na conta.
    slots = positional_slots(verb)
    if len(call.args) > len(slots):
        fail("contacts." + verb + "() takes at most " + str(len(slots))
             + " arguments (" + ", ".join(slots) + "), and this call passes "
             + str(len(call.args)), call)
    args = dict(zip(slots, call.args))
    for kw in call.keywords:
        if kw.arg not in slots or kw.arg in args:
            fail("Unknown or repeated contacts argument: " + str(kw.arg), call)
        args[kw.arg] = kw.value
    for key in names:
        if key not in args:
            if key not in defaults:
                fail("contacts." + verb + " needs " + key, call)
            args[key] = ast.Constant(value=defaults[key])
    for key, node in args.items():
        if key == "on_result": continue
        try: value = ast.literal_eval(node)
        except (ValueError, TypeError): continue
        if key in ("limit", "offset"):
            if type(value) is not int or (not 1 <= value <= 100 if key == "limit" else value < 0 or value > 100000):
                fail("Contacts limit must be 1..100; offset must be 0..100000", node)
        elif key == "id":
            if not isinstance(value, (str, int)) or isinstance(value, bool):
                fail("A contact id must be text or an integer", node)
        elif not isinstance(value, str):
            fail("Contacts " + key + " must be text", node)
        if key == "kind" and value not in ("phone", "email"):
            fail("Choose contacts.pick(kind='phone') or kind='email'", node)
    return args

def validate(tree):
    definitions = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for call in ast.walk(tree):
        if not named(call): continue
        node = arguments(call).get("on_result")
        if node is None or isinstance(node, ast.Constant) and node.value is None: continue
        function = node if isinstance(node, ast.Lambda) else definitions.get(node.id) if isinstance(node, ast.Name) else None
        if function is None:
            fail("Contacts callback must name a function in this file or a two-argument lambda", node)
        a = function.args
        if len(a.args) != 2 or a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg:
            fail("Contacts callbacks must accept (ok, value)", node)

def parse_call(t, call):
    args = arguments(call)
    if call.func.attr in ("list", "get") and "READ_CONTACTS" not in t.declared_permissions:
        t.declared_permissions.append("READ_CONTACTS")
    command = {"type": "contacts_" + call.func.attr, "line": call.lineno,
               "args": {k: v for k, v in args.items() if k != "on_result"}}
    node = args.get("on_result")
    if node is not None and not (isinstance(node, ast.Constant) and node.value is None):
        if isinstance(node, ast.Lambda):
            cb = t._unique_function_name("contacts_result")
            params = [a.arg for a in node.args.args]
            body = ast.fix_missing_locations(ast.Expr(value=node.body))
            t.functions[cb] = {"args": params, "cmds": t._parse_statements([body]), "string_args": set(params[1:])}
            # A direct adapter lambda must not turn False into the text "false"
            # (which is truthy to a string-typed destination callback).
            forwarded = node.body
            if (isinstance(forwarded, ast.Call) and isinstance(forwarded.func, ast.Name)
                    and forwarded.args and isinstance(forwarded.args[0], ast.Name)
                    and forwarded.args[0].id == params[0]):
                t.boolean_first_arg_callbacks.add(forwarded.func.id)
        else: cb = node.id
        t.boolean_first_arg_callbacks.add(cb)
        command["callback"] = cb
    return command

def used(tree):
    return any(named(n) for n in ast.walk(tree))

def emit_command(lines, indent, c, val, scope="activity"):
    if scope != "activity":
        fail("Contacts calls require a foreground screen, not a background job", ast.Constant(value=None, lineno=c["line"]))
    lines.append(indent + "{")
    lines.append(indent + "    android.os.Bundle _contactOptions = new android.os.Bundle();")
    for k, v in c["args"].items():
        lines.append(indent + '    _contactOptions.putString(%s, String.valueOf(%s));' % (json.dumps(k), val(v)))
    lines.append(indent + '    _contacts.call(%s, _contactOptions, %s);' % (json.dumps(c["type"][9:]), json.dumps(c.get("callback", ""))))
    lines.append(indent + "}")

def shared_class_java(package):
    return Path(__file__).with_name("contacts_android.java").read_text(encoding="utf-8").replace("__PACKAGE__", package)

def integrate_activity(source):
    if "_contacts.call(" not in source: return source
    callbacks = sorted(set(re.findall(r'private void pythonCallback_(\w+)\(boolean\s+\w+,\s*String\s+\w+\)', source)))
    arms = "\n".join('case %s: pythonCallback_%s(ok, value); return;' % (json.dumps(n), n) for n in callbacks)
    helper = '''
    private final ApkpyContacts _contacts = new ApkpyContacts(this, (name, ok, value) -> {
        switch (name) { __ARMS__ }
    });
'''.replace("__ARMS__", arms)
    source = source.replace("        super.onCreate(savedInstanceState);", "        super.onCreate(savedInstanceState);\n        _contacts.restore(savedInstanceState);", 1)
    if "protected void onSaveInstanceState(" in source:
        source = source.replace("        super.onSaveInstanceState(outState);", "        _contacts.save(outState);\n        super.onSaveInstanceState(outState);", 1)
    else:
        helper += "\n    @Override protected void onSaveInstanceState(android.os.Bundle outState) { _contacts.save(outState); super.onSaveInstanceState(outState); }\n"
    at = source.rfind("}")
    return source[:at] + helper + source[at:]
