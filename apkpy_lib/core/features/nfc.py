"""NFC contract, portable NDEF decoding and small Android compiler hooks."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from ...diagnostics import ApkpyError

VERBS = ("status", "start", "stop", "write", "cancel_write", "settings")
COMMAND_TYPES = frozenset("nfc_" + verb for verb in VERBS)
REASONS = {
    "unsupported": "This device has no NFC radio.",
    "off": "NFC is switched off. Enable it in system Settings.",
    "not_started": "Call nfc.start() before arming a write.",
    "no_ndef": "The tag is neither NDEF nor NDEF-formatable.",
    "read_only": "The tag does not accept writes.",
    "too_small": "The encoded NDEF message exceeds the tag capacity.",
    "tag_lost": "Keep the tag against the phone until the operation finishes.",
    "unknown": "The operation failed. Technical details are in the log.",
}
# NFC Forum URI RTD, codes 0x00 through 0x23, inclusive.
URI_PREFIXES = (
    "", "http://www.", "https://www.", "http://", "https://", "tel:",
    "mailto:", "ftp://anonymous:anonymous@", "ftp://ftp.", "ftps://", "sftp://",
    "smb://", "nfs://", "ftp://", "dav://", "news:", "telnet://", "imap:",
    "rtsp://", "urn:", "pop:", "sip:", "sips:", "tftp:", "btspp://",
    "btl2cap://", "btgoep://", "tcpobex://", "irdaobex://", "file://",
    "urn:epc:id:", "urn:epc:tag:", "urn:epc:pat:", "urn:epc:raw:",
    "urn:epc:", "urn:nfc:",
)


def _readable(payload, encoding="utf-8"):
    try:
        data = bytes(payload)
        if encoding == "utf-16":
            if data.startswith(b"\xff\xfe"):
                data, encoding = data[2:], "utf-16-le"
            else:
                if data.startswith(b"\xfe\xff"):
                    data = data[2:]
                encoding = "utf-16-be"  # UTF-16 without a BOM defaults to BE.
        text = data.decode(encoding, errors="strict")
    except (UnicodeError, ValueError):
        return ""
    return text if all(ord(c) >= 32 and not 127 <= ord(c) <= 159 or c in "\t\r\n" for c in text) else ""


def decode_tag(tag_id, kind, writable, size, used, tech, records):
    """Record tuples are (TNF, type bytes, payload bytes); always all fields."""
    text = url = ""
    have_text = have_url = have_type = False
    for tnf, record_type, payload in records:
        payload = bytes(payload)
        if tnf == 1 and record_type == b"T" and not have_text:
            have_text = True
            if payload:
                offset = 1 + (payload[0] & 63)
                if offset <= len(payload):
                    text = _readable(payload[offset:], "utf-16" if payload[0] & 128 else "utf-8")
        elif tnf == 1 and record_type == b"U" and not have_url:
            have_url = True
            if payload and payload[0] < len(URI_PREFIXES):
                suffix = _readable(payload[1:])
                if suffix or len(payload) == 1:
                    url = URI_PREFIXES[payload[0]] + suffix
        elif tnf in (2, 4):
            if not have_type:
                kind = _readable(record_type) or kind
                have_type = True
            if not have_text:
                candidate = _readable(payload)
                if candidate or not payload:
                    text, have_text = candidate, True
    return {"id": bytes(tag_id).hex().upper(), "type": kind, "text": text,
            "url": url, "records": len(records), "writable": writable,
            "size": str(size), "used": str(used), "tech": tech}


def write_record(kind, value):
    """Mirror Android createTextRecord('en', ...) / createUri(...)."""
    if not isinstance(value, str):
        raise ValueError("NFC text and URL must be strings")
    if kind == "text":
        return (1, b"T", b"\x02en" + value.encode("utf-8"))
    if not value:
        raise ValueError("NFC URL cannot be empty")
    value = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*:", lambda m: m[0].lower(), value)
    prefix = next((i for i, p in enumerate(URI_PREFIXES[1:], 1) if value.startswith(p)), 0)
    return (1, b"U", bytes([prefix]) + value[len(URI_PREFIXES[prefix]):].encode("utf-8"))


def named(call):
    return (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name) and call.func.value.id == "nfc")


def is_call(call):
    return named(call) and call.func.attr in VERBS


def fail(message, node):
    raise ApkpyError(message, code="U2033", line=getattr(node, "lineno", 0),
                     expected="nfc." + ", nfc.".join(v + "()" for v in VERBS),
                     suggestions=["Use nfc.start(on_tag=read_tag, on_error=failed); both callbacks accept (ok, value)."],
                     docs="https://repo-apkpy.pages.dev/guides/nfc/")


def arguments(call):
    verb = call.func.attr
    if verb not in VERBS:
        fail("Unknown NFC method: nfc." + verb, call)
    positional = {"status": ("on_result",), "start": ("on_tag", "on_error")}.get(verb, ())
    allowed = set(positional) | ({"text", "url", "on_result"} if verb == "write" else set())
    if len(call.args) > len(positional):
        fail("Unexpected positional argument to nfc." + verb, call)
    args = dict(zip(positional, call.args))
    for kw in call.keywords:
        if kw.arg not in allowed or kw.arg in args:
            fail("Unknown or repeated NFC argument: " + str(kw.arg), call)
        args[kw.arg] = kw.value
    if verb == "write":
        for key in ("text", "url"):
            if isinstance(args.get(key), ast.Constant) and args[key].value is None:
                args.pop(key)
        if len(set(args) & {"text", "url"}) != 1:
            fail("nfc.write() needs exactly one of text= or url=", call)
        value = args.get("text", args.get("url"))
        if isinstance(value, ast.Constant) and not isinstance(value.value, str):
            fail("NFC text and URL must be strings", value)
    return args


def validate(tree):
    definitions = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for call in ast.walk(tree):
        if not named(call):
            continue
        args = arguments(call)
        for name in ("on_tag", "on_error", "on_result"):
            node = args.get(name)
            if node is None or isinstance(node, ast.Constant) and node.value is None:
                continue
            if not isinstance(node, (ast.Name, ast.Lambda)):
                fail("NFC callbacks must be functions or two-argument lambdas", node)
            function = node if isinstance(node, ast.Lambda) else definitions.get(node.id)
            if function is None:
                fail("NFC callback must name a function defined in this file", node)
            a = function.args
            if len(a.args) != 2 or a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg:
                fail("NFC " + name + " callback must accept (ok, value)", node)


def parse_call(t, call):
    args = arguments(call)
    if "NFC" not in t.declared_permissions:
        t.declared_permissions.append("NFC")
    command = {"type": "nfc_" + call.func.attr, "line": call.lineno}
    for name, node in args.items():
        if name in ("text", "url"):
            command["value"] = node
            command["kind"] = name
        else:
            if isinstance(node, ast.Constant) and node.value is None:
                continue
            if isinstance(node, ast.Lambda):
                cb = t._unique_function_name("nfc_" + name)
                params = [a.arg for a in node.args.args]
                body = ast.fix_missing_locations(ast.Expr(value=node.body))
                t.functions[cb] = {"args": params, "cmds": t._parse_statements([body]),
                                   "string_args": set(params[1:])}
            else:
                cb = node.id
            t.boolean_first_arg_callbacks.add(cb)
            command[name] = cb
    return command


def commands_use_nfc(functions_map, module_init_cmds=None):
    def uses(value):
        if isinstance(value, dict):
            return value.get("type") in COMMAND_TYPES or any(uses(v) for v in value.values())
        return isinstance(value, (list, tuple)) and any(uses(v) for v in value)
    return uses(module_init_cmds) or any(uses(f.get("cmds", [])) for f in (functions_map or {}).values() if f)


def emit_command(lines, indent, c, val, functions_map=None, scope="activity"):
    verb = c["type"][4:]
    if scope == "worker":
        if verb in ("stop", "cancel_write"):
            lines.append(indent + "ApkpyNfc." + ("stopAll" if verb == "stop" else "cancelAllWrites") + "();")
            return
        fail("nfc." + verb + "() requires a foreground screen, not a background job", ast.Constant(value=None, lineno=c["line"]))
    def cb(key):
        name = c.get(key)
        # A nested lambda cannot reuse an enclosing callback's parameter names.
        # An explicit method scope can, and cannot collide with user locals.
        return ("new ApkpyNfc.Listener() { public void onResult(boolean ok, String value) { "
                "pythonCallback_%s(ok, value); } }" % name) if name else "null"
    if verb == "start":
        expression = "start(%s, %s)" % (cb("on_tag"), cb("on_error"))
    elif verb == "status":
        expression = "status(%s)" % cb("on_result")
    elif verb == "write":
        expression = 'write(%s, String.valueOf(%s), %s)' % (json.dumps(c["kind"]), val(c["value"]), cb("on_result"))
    else:
        expression = {"stop": "stop()", "cancel_write": "cancelWrite()", "settings": "settings()"}[verb]
    lines.append(indent + "_nfc." + expression + ";")


def activity_runtime_java(package):
    return "    private final ApkpyNfc _nfc = new ApkpyNfc(this);"


def shared_class_java(package):
    source = Path(__file__).with_name("nfc_android.java").read_text(encoding="utf-8")
    source = source.replace("__PACKAGE__", package).replace("__URI_PREFIXES__", ", ".join(json.dumps(v) for v in URI_PREFIXES))
    constants = "\n".join('    private static final String %s = %s;' % (k.upper(), json.dumps(k)) for k in REASONS)
    return source.replace("__REASONS__", constants)


def integrate_manifest(source):
    return source.replace("<application", '<uses-feature android:name="android.hardware.nfc" android:required="false" />\n    <application', 1)
