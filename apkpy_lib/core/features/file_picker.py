"""Compiler support for picking any file, and for ``upload_button``.

The Storage Access Framework already reaches the existing upload engine
untouched: ``_uploadMultipart`` branches on ``content://`` and reads the name,
size and MIME type through ``ContentResolver``.  What was missing was the
picker, because ``_galleryPick`` hardcodes ``"image/*"``.

Two things are generated here:

* ``files.pick(on_result=..., types=[...])`` -> an
  ``ActivityResultContracts.OpenDocument`` launcher whose result lambda reports
  ``(success, path, name, size, mime)``;
* ``upload_button(...)`` -> plain sugar.  It synthesises an ordinary ``button``
  plus two functions at parse time, so the emitter never sees a chained
  command and ``_emit_upload_cmd`` stays exactly as it is.
"""

from __future__ import annotations

import ast
import mimetypes

from ...theme import normalize_button_variant


COMMAND_TYPES = frozenset({"files_pick"})

ANY_MIME = "*/*"
ALL_FILES = ("All files", "*.*")

# The curated table wins over ``mimetypes.guess_type`` on purpose.  On Windows
# ``mimetypes`` reads HKEY_CLASSES_ROOT, so a machine with Acrobat installed
# would answer differently from a clean CI box -- and a transpiler's output has
# to be reproducible.
_EXTENSION_MIME = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "odt": "application/vnd.oasis.opendocument.text",
    "ods": "application/vnd.oasis.opendocument.spreadsheet",
    "rtf": "application/rtf",
    "csv": "text/csv",
    "txt": "text/plain",
    "md": "text/markdown",
    "json": "application/json",
    "xml": "text/xml",
    "html": "text/html",
    "zip": "application/zip",
    "rar": "application/vnd.rar",
    "7z": "application/x-7z-compressed",
    "tar": "application/x-tar",
    "gz": "application/gzip",
    "apk": "application/vnd.android.package-archive",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "mkv": "video/x-matroska",
    "webm": "video/webm",
    "avi": "video/x-msvideo",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "bmp": "image/bmp",
    "svg": "image/svg+xml",
    "heic": "image/heic",
}

# ``image/*`` and friends are legal for EXTRA_MIME_TYPES but tkinter needs real
# extensions, so each family carries its own desktop list.
_WILDCARD_EXTENSIONS = {
    "image/*": ["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "heic"],
    "audio/*": ["mp3", "wav", "m4a", "aac", "flac", "ogg"],
    "video/*": ["mp4", "mov", "mkv", "webm", "avi"],
    "text/*": ["txt", "csv", "json", "xml", "md", "html"],
}


def _extensions_for_mime(mime):
    if mime in _WILDCARD_EXTENSIONS:
        return list(_WILDCARD_EXTENSIONS[mime])
    found = [ext for ext, value in _EXTENSION_MIME.items() if value == mime]
    return found


def _mime_for_extension(extension):
    if extension in _EXTENSION_MIME:
        return _EXTENSION_MIME[extension]
    guessed = mimetypes.guess_type("file." + extension, strict=True)[0]
    return guessed or ANY_MIME


def normalise_types(values):
    """Resolve ``types=`` into ``(android_mime_types, desktop_filetypes)``.

    Accepts bare or dotted extensions (``"pdf"``, ``".pdf"``), complete MIME
    types (``"application/pdf"``), families (``"image/*"``) and ``"*/*"``.
    Both halves are resolved here, in Python, so the two runtimes can never
    disagree about what a name means.
    """
    if values is None:
        values = []
    if isinstance(values, str):
        values = [values]

    mimes = []
    filetypes = []
    for raw in values:
        text = str(raw or "").strip().lower()
        if not text:
            continue
        if text == ANY_MIME or text == "*":
            mimes.append(ANY_MIME)
            continue
        if "/" in text:
            mime = text
            extensions = _extensions_for_mime(mime)
        else:
            extension = text.lstrip(".")
            if not extension:
                continue
            mime = _mime_for_extension(extension)
            extensions = [extension]
        mimes.append(mime)
        if extensions:
            filetypes.append((text, " ".join("*." + e for e in extensions)))

    # ``*/*`` absorbs everything: keeping a narrower type beside it would
    # promise a filter the picker is not applying.
    if not mimes or ANY_MIME in mimes:
        return [ANY_MIME], [ALL_FILES]

    ordered = list(dict.fromkeys(mimes))
    # The desktop dialog must never be stricter than the phone: many
    # DocumentsProviders ignore EXTRA_MIME_TYPES entirely, so the escape hatch
    # stays available on both sides.
    return ordered, list(dict.fromkeys(filetypes)) + [ALL_FILES]


# ─── Parsing ──────────────────────────────────────────────────────────────────

_PICK_PARAMS = ("success", "path", "name", "size", "mime")


def is_call(call):
    """``files.pick(...)``"""
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "pick"
        and isinstance(func.value, ast.Name)
        and func.value.id == "files"
    )


def _register_callback(transpiler, node, tag):
    """Accept a named function or a lambda of up to five parameters."""
    if isinstance(node, ast.Name):
        transpiler.boolean_first_arg_callbacks.add(node.id)
        return node.id
    if isinstance(node, ast.Lambda):
        params = [argument.arg for argument in node.args.args]
        params = (params + list(_PICK_PARAMS))[:max(1, len(params) or 5)]
        name = transpiler._unique_function_name(tag)
        body = ast.Expr(value=node.body)
        ast.fix_missing_locations(body)
        transpiler.functions[name] = {
            "args": params,
            "cmds": transpiler._parse_statements([body]),
            "string_args": set(params[1:]),
        }
        transpiler.boolean_first_arg_callbacks.add(name)
        return name
    return None


def _register_plain_callback(transpiler, node, tag, default_params):
    """Register a callback whose parameters are all Strings (no success flag)."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Lambda):
        params = [argument.arg for argument in node.args.args]
        params = (params + list(default_params))[:max(1, len(params) or len(default_params))]
        name = transpiler._unique_function_name(tag)
        body = ast.Expr(value=node.body)
        ast.fix_missing_locations(body)
        transpiler.functions[name] = {
            "args": params,
            "cmds": transpiler._parse_statements([body]),
            "string_args": set(params),
        }
        return name
    return None


def _types_from_call(transpiler, call):
    node = transpiler._kw_node(call.keywords, "types")
    if node is None:
        return normalise_types(None)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return normalise_types([node.value])
    values = transpiler._literal_string_list(node)
    if not values:
        # A runtime expression cannot be resolved at build time; accepting
        # everything is the only honest fallback.
        return normalise_types(None)
    return normalise_types(values)


def parse_call(transpiler, call):
    mime_types, _ = _types_from_call(transpiler, call)
    callback = _register_callback(
        transpiler, transpiler._kw_node(call.keywords, "on_result"), "files_pick_cb",
    )
    return {"type": "files_pick", "callback": callback, "mime_types": mime_types}


def parse_upload_button(transpiler, call, comp, py_var):
    """Expand ``upload_button(...)`` into a plain button plus two functions.

    Nothing new reaches the emitter: the picked path travels as the Java
    parameter of the synthesised result callback, so the existing
    ``upload_multipart`` command emits unchanged.
    """
    comp["text"] = call.args[0].value if call.args else ""
    comp["id"] = transpiler._kw(call.keywords, "id", py_var)
    comp["variant"] = normalize_button_variant(transpiler._kw(call.keywords, "variant"))
    comp["icon"] = transpiler._kw(call.keywords, "icon")

    base = py_var or comp.get("id") or "upload_button"
    mime_types, _ = _types_from_call(transpiler, call)

    url_node = transpiler._kw_node(call.keywords, "url")
    if url_node is None and len(call.args) > 1:
        url_node = call.args[1]

    task_node = transpiler._kw_node(call.keywords, "task_id")
    if task_node is None:
        # A stable id makes a double tap restart the upload instead of racing
        # two of them, and makes uploads.cancel(...) usable.
        task_node = ast.Constant(value=str(comp.get("id") or base))
        ast.fix_missing_locations(task_node)

    fields_node = transpiler._kw_node(call.keywords, "fields")
    if isinstance(fields_node, ast.Name):
        fields_node = transpiler.dict_assignments.get(fields_node.id, fields_node)
    headers_node = transpiler._kw_node(call.keywords, "headers")
    if isinstance(headers_node, ast.Name):
        headers_node = transpiler.dict_assignments.get(headers_node.id, headers_node)

    picked_name = transpiler._unique_function_name(base + "_picked")
    transpiler._upload_command_count += 1

    upload_command = {
        "type": "upload_multipart",
        "seq": transpiler._upload_command_count,
        "task_node": task_node,
        "url_node": url_node,
        # Resolves to the Java parameter named ``path`` of picked_name.
        "path_node": ast.Name(id="path", ctx=ast.Load()),
        "field_node": transpiler._kw_node(call.keywords, "field"),
        "fields_node": fields_node,
        "headers_node": headers_node,
        "content_type_node": transpiler._kw_node(call.keywords, "content_type"),
        "progress_callback": transpiler._register_upload_progress_callback(
            transpiler._kw_node(call.keywords, "on_progress"),
        ),
        "result_callback": transpiler._register_result_callback(
            transpiler._kw_node(call.keywords, "on_result"), True, base + "_done",
        ),
    }
    ast.fix_missing_locations(upload_command["path_node"])

    chosen = []
    # on_file only fires once a file was chosen, so it carries no success flag:
    # every parameter is a String and it must stay out of
    # boolean_first_arg_callbacks.
    on_file = _register_plain_callback(
        transpiler, transpiler._kw_node(call.keywords, "on_file"), base + "_file",
        _PICK_PARAMS[1:],
    )
    if on_file:
        args_nodes = [ast.Name(id=p, ctx=ast.Load()) for p in _PICK_PARAMS[1:]]
        for node in args_nodes:
            ast.fix_missing_locations(node)
        chosen.append({
            "type": "function_call", "name": on_file, "args_nodes": args_nodes,
        })
    chosen.append(upload_command)

    cancelled = []
    on_cancel = transpiler._kw(call.keywords, "on_cancel")
    if isinstance(on_cancel, str):
        cancelled.append(
            {"type": "function_call", "name": on_cancel, "args_nodes": []},
        )

    transpiler.functions[picked_name] = {
        "args": list(_PICK_PARAMS),
        "cmds": [{
            "type": "if_var",
            "var": "success",
            "true_body": chosen,
            "false_body": cancelled,
        }],
        "string_args": set(_PICK_PARAMS[1:]),
    }
    transpiler.boolean_first_arg_callbacks.add(picked_name)

    command_name = transpiler._unique_function_name(base + "_cmd")
    transpiler.functions[command_name] = {
        "args": [],
        "cmds": [{
            "type": "files_pick",
            "callback": picked_name,
            "mime_types": mime_types,
        }],
        "string_args": set(),
    }
    comp["command"] = command_name

    if "INTERNET" not in transpiler.declared_permissions:
        transpiler.declared_permissions.append("INTERNET")
    return True


def commands_use_picker(functions_map, module_init_cmds=None):
    def walk(commands):
        for command in commands or []:
            if not isinstance(command, dict):
                continue
            if command.get("type") in COMMAND_TYPES:
                return True
            for key in ("true_body", "false_body", "body"):
                if walk(command.get(key, [])):
                    return True
        return False

    return walk(module_init_cmds) or any(
        walk(info.get("cmds", [])) for info in (functions_map or {}).values() if info
    )


# ─── Emission ─────────────────────────────────────────────────────────────────

# Java forbids a lambda parameter from shadowing an enclosing parameter or
# local, so these are mangled rather than named success/path/name/size/mime.
_LAMBDA_PARAMS = ("_fpOk", "_fpPath", "_fpName", "_fpSize", "_fpMime")


def _mime_array(mime_types):
    values = list(mime_types or [ANY_MIME]) or [ANY_MIME]
    return "new String[]{%s}" % ", ".join('"%s"' % value for value in values)


def emit_command(lines, indent, command, val_to_java, functions_map=None):
    if command.get("type") != "files_pick":
        return False
    array = _mime_array(command.get("mime_types"))
    callback = command.get("callback")
    if not callback:
        lines.append("%s_filePick(%s, null);" % (indent, array))
        return True
    declared = len(((functions_map or {}).get(callback) or {}).get("args", [])) or 5
    forwarded = ", ".join(_LAMBDA_PARAMS[:max(1, min(5, declared))])
    lines.append("%s_filePick(%s, (%s) -> pythonCallback_%s(%s));" % (
        indent, array, ", ".join(_LAMBDA_PARAMS), callback, forwarded,
    ))
    return True


def callback_interface_java():
    return (
        "    private interface FilePickResultCallback "
        "{ void onResult(boolean success, String path, String name, "
        "String size, String mime); }"
    )


def launcher_java():
    """The launcher field, registered before the Activity reaches STARTED."""
    return '''
    private FilePickResultCallback _pendingFilePickCallback;
    private final ActivityResultLauncher<String[]> _filePickLauncher = registerForActivityResult(
            new ActivityResultContracts.OpenDocument(),
            uri -> {
                final FilePickResultCallback cb = _pendingFilePickCallback;
                _pendingFilePickCallback = null;
                if (cb == null) return;
                if (uri == null) { cb.onResult(false, "", "", "0", ""); return; }
                // A provider backed by Drive or OneDrive can block on the
                // network answering this query, so it never runs on the UI
                // thread.
                new Thread(new Runnable() { public void run() {
                    String pickedName = "", pickedSize = "0", pickedMime = "";
                    android.database.Cursor cursor = null;
                    try {
                        cursor = getContentResolver().query(uri, new String[]{
                                android.provider.OpenableColumns.DISPLAY_NAME,
                                android.provider.OpenableColumns.SIZE}, null, null, null);
                        if (cursor != null && cursor.moveToFirst()) {
                            int nameIndex = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME);
                            int sizeIndex = cursor.getColumnIndex(android.provider.OpenableColumns.SIZE);
                            if (nameIndex >= 0 && !cursor.isNull(nameIndex)) pickedName = cursor.getString(nameIndex);
                            if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) pickedSize = String.valueOf(cursor.getLong(sizeIndex));
                        }
                    } catch (Exception ignored) {
                    } finally {
                        try { if (cursor != null) cursor.close(); } catch (Exception ignored) {}
                    }
                    String type = getContentResolver().getType(uri);
                    if (type != null) pickedMime = type;
                    if (pickedName.isEmpty()) {
                        String last = uri.getLastPathSegment();
                        pickedName = (last == null) ? "file" : last.substring(last.lastIndexOf('/') + 1);
                    }
                    final String finalName = pickedName, finalSize = pickedSize, finalMime = pickedMime;
                    runOnUiThread(new Runnable() { public void run() {
                        if (!isDestroyed()) cb.onResult(true, uri.toString(), finalName, finalSize, finalMime);
                    }});
                }}).start();
            });
'''


def activity_runtime_java():
    """The helper the emitted commands call."""
    return '''
    private void _filePick(final String[] mimeTypes, final FilePickResultCallback cb) {
        _pendingFilePickCallback = cb;
        try {
            _filePickLauncher.launch(mimeTypes == null || mimeTypes.length == 0
                    ? new String[]{"*/*"} : mimeTypes);
        } catch (Exception e) {
            // Stripped AOSP and Android Go images can ship without DocumentsUI.
            _pendingFilePickCallback = null;
            if (cb != null) cb.onResult(false, "", "", "0", "");
        }
    }
'''
