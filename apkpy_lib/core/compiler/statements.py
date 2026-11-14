"""A Python statement, written as Java: loops, try, raise, print, appends."""
import ast
import json
import os
import re

from ..features import modules as modules_feature
from ..features import sort_key as sort_key_feature
from ..features import classes as classes_feature
from ...diagnostics import ApkpyError, Diagnostic, report_diagnostic
from .. import unsupported

from .state import (
    _ASSET_BASE_DIR, _BODY_KEYS, _GLOBALS, _MODULE_LISTS, _MUTATED_LISTS, _RAW_LOOP_VARS,
)
from .kinds import _dict_receiver, _int_literal, _kind_from, _literal_number_kind, _static_kind
from .expressions import (
    _ALWAYS_NUMBERS, _cond_to_java, _escape_java_literal, _item_read, _json_node_to_java,
    _json_value_java, _mutated_list_key, _mutated_list_read, _popped_item, _raw_item_java,
    _text_value_java, _typed_json_java,
)


def _emit_language_set(lines, indent, tag_java):
    """``language.set("pt")`` while the app is running.

    ``setApplicationLocales`` is AppCompat's own, available since 1.6.0 (we
    pin 1.6.1), and it recreates the started activities itself -- the same way
    a theme change does. Calling recreate() here as well would run onCreate
    twice. The choice is stored first because AppCompat persists it only from
    API 33 up; below that the app has to put it back on the next launch, and
    reading it in onCreate is what makes "opens the way it was left" true on
    every phone rather than only on the newest ones.
    """
    lines.append(f'{indent}_apkpyStorageSet("__apkpy_language", '
                 f'String.valueOf({tag_java}));')
    lines.append(f'{indent}androidx.appcompat.app.AppCompatDelegate'
                 f'.setApplicationLocales(')
    lines.append(f'{indent}        androidx.core.os.LocaleListCompat'
                 f'.forLanguageTags(String.valueOf({tag_java})));')


# A ordem dos parametros de service.every/once no Previewer (ui.ServiceAPI):
# os argumentos posicionais leem-se por esta ordem, como o Python os le.
_SERVICE_PARAMS = {
    'every': ('run', 'minutes', 'id', 'only_on_wifi', 'only_when_charging'),
    'once': ('run', 'after_minutes', 'id', 'only_on_wifi', 'only_when_charging'),
}


def _refuse_missing_service_function(svc, verb):
    """service.every(run=x) naming no function in this file used to be
    skipped with a `continue`: no Worker, no word."""
    raise ApkpyError(
        'service.%s(run=%s) - the function %s() was not found in this file.'
        % (verb, svc['function_name'], svc['function_name']),
        code="J7002",
        line=svc.get('line', 0),
        received="run=%s" % svc['function_name'],
        expected="a module-level def %s(): in this file" % svc['function_name'],
    )


def _files_download_now_java():
    """O download em si, escrito UMA vez para as duas classes que o usam.

    A Activity chama-o numa thread e entrega o resultado na UI thread; o
    Worker de um background_job ja esta fora da UI thread e chama-o direto,
    para a linha seguinte do job ver o ficheiro. Devolve o caminho absoluto,
    ou "" se falhou.
    """
    return [
        "    private String _filesDownloadNow(String url, String name) {",
        "        java.io.InputStream in = null;",
        "        java.io.FileOutputStream out = null;",
        "        try {",
        "            java.io.File outFile = new java.io.File(getApplicationContext().getFilesDir(), name);",
        "            java.net.HttpURLConnection conn = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();",
        "            conn.setConnectTimeout(15000);",
        "            conn.setReadTimeout(20000);",
        "            conn.setInstanceFollowRedirects(true);",
        "            conn.connect();",
        "            in = conn.getInputStream();",
        "            out = new java.io.FileOutputStream(outFile);",
        "            byte[] buf = new byte[8192];",
        "            int n;",
        "            while ((n = in.read(buf)) != -1) { out.write(buf, 0, n); }",
        "            out.flush();",
        "            return outFile.getAbsolutePath();",
        "        } catch (Exception e) {",
        "            return \"\";",
        "        } finally {",
        "            try { if (out != null) out.close(); } catch (Exception e) {}",
        "            try { if (in != null) in.close(); } catch (Exception e) {}",
        "        }",
        "    }",
    ]


def _stamp_commands(cmds, stamped, stmt):
    """Give the commands a statement produced its line, and its helper file.

    *stamped* is a one-item list holding how many of *cmds* already have one.
    A command that set its own line (a call to a function) keeps it.
    """
    if stmt is not None:
        line = getattr(stmt, 'lineno', 0)
        path = modules_feature.source_file(stmt)
        for command in cmds[stamped[0]:]:
            if isinstance(command, dict):
                command.setdefault('lineno', line)
                if path:
                    command.setdefault('_apkpy_file', path)
    stamped[0] = len(cmds)


# A crash on the phone names a line of the Java; `apkpy logs` shows the line
# of Python it came from. Each command leaves a mark before the Java it writes,
# and _take_line_marks takes the marks out at the end into apkpy/lines.json:
# the Java the app is built from is the same as without them. \x00 closes the
# mark too, so one that ended up inside a line is still found and taken out.
_LINE_MARK = "\x00apkpy-line:"
_LINE_MARK_RE = re.compile(r"\x00apkpy-line:(\d+):(\d+):([^\x00]*)\x00")


def _line_mark(lines, c, indent):
    """Mark where the Java of command *c* starts (see _LINE_MARK)."""
    if isinstance(c, dict) and c.get('lineno'):
        lines.append("%s%d:%d:%s\x00" % (_LINE_MARK, len(indent), c['lineno'],
                                          c.get('_apkpy_file', '')))


def _take_line_marks(output_files, source_name):
    """Take the marks out of the Java files, and say where their lines came
    from: {"Screen_homeActivity.java": [[java_line, python_line, file], ...]},
    each entry for the run of Java lines that starts there (python_line 0
    when the run is the Java's own: a method of ApkPy's, the screen setup).

    A command's Java is the lines after its mark that are indented at least
    as deep as the command; the closing brace of the method ends it.
    """
    found = {}
    for name in list(output_files):
        body = output_files[name]
        if not (name.endswith('.java') and isinstance(body, str) and _LINE_MARK in body):
            continue
        kept, runs, marks = [], [], []
        for text in body.split('\n'):
            hit = _LINE_MARK_RE.fullmatch(text.strip())
            if hit:
                depth = int(hit.group(1))
                while marks and marks[-1][0] >= depth:
                    marks.pop()
                marks.append((depth, int(hit.group(2)), hit.group(3) or source_name))
                continue
            text = _LINE_MARK_RE.sub('', text)
            words = text.lstrip(' ')
            if words.strip():
                depth = len(text) - len(words)
                while marks and marks[-1][0] > depth:
                    marks.pop()
            kept.append(text)
            where = [marks[-1][1], marks[-1][2]] if marks else [0, ""]
            if not runs or runs[-1][1:] != where:
                runs.append([len(kept)] + where)
        output_files[name] = '\n'.join(kept)
        found[name.rsplit('/', 1)[-1]] = runs
    return found


def _lines_json(lines_map, source_name, python_code):
    """apkpy/lines.json: the map of _take_line_marks, and the text of each
    Python line it names as it was when the app was built (the file may have
    changed by the time the phone crashes). The CLI keeps it out of the
    project, under ~/.apkpy/lines/."""
    used = {}
    for runs in lines_map.values():
        for _java_line, line, path in runs:
            if line:
                used.setdefault(path, set()).add(line)
    text = {}
    for path, numbers in used.items():
        if path == source_name:
            source = python_code
        else:
            try:
                with open(os.path.join(_ASSET_BASE_DIR[0] or '.', path),
                          encoding='utf-8') as f:
                    source = f.read()
            except (OSError, UnicodeDecodeError):
                continue
        rows = source.splitlines()
        text[path] = {str(n): rows[n - 1].strip() for n in sorted(numbers)
                      if 0 < n <= len(rows)}
    return json.dumps({'version': 1, 'java': lines_map, 'text': text},
                      ensure_ascii=False, separators=(',', ':'))


def _seed_items_from_state(lines, indent, jv, comp):
    """Fill a list from the shared store instead of from baked-in literals.

    A module-level list the app appends to grows while the app runs. Writing
    its *starting* values into ``onCreate`` meant that leaving the screen and
    coming back put the original list back on top of the one that had grown --
    the Previewer kept the new rows and the phone lost them, with nothing said.

    Lists nobody appends to are untouched: their values are constants, and
    reading them from a store at runtime would be slower for no reason.
    """
    name = comp.get('_items_var')
    if not name or name not in _MUTATED_LISTS[0]:
        return False
    _emit_json_set_items(
        lines, indent, jv, _mutated_list_read(name),
        comp.get('title_key'), comp.get('subtitle_key'),
        abs(hash(jv)) & 0xFFFF,
        image_key=comp.get('image_key'), rich=bool(comp.get('rich')),
    )
    return True


def _emit_json_set_items(lines, indent, jv, src_java, title_key, subtitle_key, sfx, image_key=None, rich=False):
    """
    Emite o Java que converte uma string JSON (resultado de db.query / https)
    nos itens de um list_view em runtime — "title — subtitle" por linha,
    com fallback para arrays de valores simples. Erros de parse deixam a
    lista vazia em vez de rebentar a app. Se `rich`, também enche a lista
    paralela `{jv}_imgs` com o URL da capa (campo `image_key`).
    """
    t_key = (title_key or 'title').replace('"', '\\"')
    s_key = (subtitle_key or 'subtitle').replace('"', '\\"')
    i_key = (image_key or 'image').replace('"', '\\"')
    lines.append(f"{indent}try {{")
    lines.append(f"{indent}    org.json.JSONArray _ja_{sfx} = new org.json.JSONArray(String.valueOf({src_java}));")
    lines.append(f"{indent}    for (int _i_{sfx} = 0; _i_{sfx} < _ja_{sfx}.length(); _i_{sfx}++) {{")
    lines.append(f"{indent}        Object _o_{sfx} = _ja_{sfx}.get(_i_{sfx});")
    lines.append(f"{indent}        if (_o_{sfx} instanceof org.json.JSONObject) {{")
    lines.append(f"{indent}            org.json.JSONObject _jo_{sfx} = (org.json.JSONObject) _o_{sfx};")
    lines.append(f'{indent}            String _t_{sfx} = _jo_{sfx}.optString("{t_key}", "");')
    lines.append(f'{indent}            String _s_{sfx} = _jo_{sfx}.optString("{s_key}", "");')
    # The row keeps every column the query returned, plus the title and
    # subtitle the adapter draws: a tapped row's callback reads item["id"]
    # as the Previewer's does. It used to keep only the text shown.
    lines.append(f"{indent}            org.json.JSONObject _no_{sfx} = new org.json.JSONObject(_jo_{sfx}.toString());")
    lines.append(f'{indent}            _no_{sfx}.put("title", _t_{sfx});')
    lines.append(f'{indent}            _no_{sfx}.put("subtitle", _s_{sfx});')
    if rich:
        lines.append(f'{indent}            _no_{sfx}.put("image", _jo_{sfx}.optString("{i_key}", ""));')
    lines.append(f"{indent}            {jv}_items.add(_no_{sfx}.toString());")
    lines.append(f"{indent}        }} else {{")
    if rich:
        lines.append(f"{indent}            org.json.JSONObject _no2_{sfx} = new org.json.JSONObject();")
        lines.append(f'{indent}            _no2_{sfx}.put("title", String.valueOf(_o_{sfx}));')
        lines.append(f"{indent}            {jv}_items.add(_no2_{sfx}.toString());")
    else:
        lines.append(f"{indent}            {jv}_items.add(String.valueOf(_o_{sfx}));")
    lines.append(f"{indent}        }}")
    lines.append(f"{indent}    }}")
    lines.append(f"{indent}}} catch (Exception _e_{sfx}) {{ }}")


def _emit_apps_cmd(lines, indent, c, val_to_java):
    """Emite a chamada Java de um comando apps.* (list/permissions/extract/hash).
    list/permissions devolvem uma String JSON (1 arg); extract/hash devolvem
    (success, resultado). Sem callback → no-op seguro."""
    cb = c.get('callback')
    t = c['type']
    if t == 'apps_list':
        body = f"pythonCallback_{cb}(_j)" if cb else "{}"
        lines.append(f"{indent}_appsList(_j -> {body});")
        return
    pkg = f"String.valueOf({val_to_java(c['pkg_node'])})" if c.get('pkg_node') else '""'
    if t == 'apps_permissions':
        body = f"pythonCallback_{cb}(_j)" if cb else "{}"
        lines.append(f"{indent}_appsPermissions({pkg}, _j -> {body});")
    else:  # apps_extract / apps_hash — callback (success, resultado)
        method = '_appsExtract' if t == 'apps_extract' else '_appsHash'
        body = f"pythonCallback_{cb}(success, path)" if cb else "{}"
        lines.append(f"{indent}{method}({pkg}, (success, path) -> {body});")


class _SearchUntranslatable(Exception):
    """Sinaliza um filtro de pesquisa (on_change) que o compilador não sabe
    traduzir para Java — nesse caso a pesquisa em tempo real é simplesmente
    omitida no Android (com aviso), em vez de gerar Java inválido."""
    pass


def _search_str_expr(node, query_param, item_var):
    """Traduz uma sub-expressão STRING de um filtro de pesquisa para Java, no
    contexto de um TextWatcher: a query (`query_param`) vira a variável local
    `_q` e `item["chave"]`/`item.get("chave")` vira `_jsonGet(_row, "chave")`.
    Suporta .lower()/.upper()/.strip() e literais. Levanta
    _SearchUntranslatable em qualquer outra forma."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return '"' + _escape_java_literal(node.value) + '"'
    if isinstance(node, ast.Name):
        if node.id == query_param:
            return "_q"
        raise _SearchUntranslatable("name:" + node.id)
    # item["chave"]
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
            and node.value.id == item_var and isinstance(node.slice, ast.Constant):
        return f'_jsonGet(_row, "{_escape_java_literal(str(node.slice.value))}")'
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        attr = node.func.attr
        # item.get("chave") / item.get("chave", default)
        if attr == 'get' and isinstance(node.func.value, ast.Name) \
                and node.func.value.id == item_var and node.args \
                and isinstance(node.args[0], ast.Constant):
            return f'_jsonGet(_row, "{_escape_java_literal(str(node.args[0].value))}")'
        base = _search_str_expr(node.func.value, query_param, item_var)
        if attr == 'lower':
            return f"({base}).toLowerCase()"
        if attr == 'upper':
            return f"({base}).toUpperCase()"
        if attr == 'strip':
            return f"({base}).trim()"
        raise _SearchUntranslatable("call:" + attr)
    raise _SearchUntranslatable(type(node).__name__)


def _search_cond_java(node, query_param, item_var):
    """Traduz a CONDIÇÃO booleana de um filtro de pesquisa para Java.
    `a in b` → `(b).contains(a)`; `and/or/not`, `==`/`!=` e
    `.startswith()/.endswith()` também são suportados."""
    if isinstance(node, ast.BoolOp):
        op = '&&' if isinstance(node.op, ast.And) else '||'
        parts = [_search_cond_java(v, query_param, item_var) for v in node.values]
        return "(" + f" {op} ".join(parts) + ")"
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return "(!" + _search_cond_java(node.operand, query_param, item_var) + ")"
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        op = node.ops[0]
        if isinstance(op, (ast.In, ast.NotIn)):
            needle = _search_str_expr(node.left, query_param, item_var)
            hay = _search_str_expr(node.comparators[0], query_param, item_var)
            expr = f"({hay}).contains({needle})"
            return ("(!" + expr + ")") if isinstance(op, ast.NotIn) else expr
        if isinstance(op, (ast.Eq, ast.NotEq)):
            a = _search_str_expr(node.left, query_param, item_var)
            b = _search_str_expr(node.comparators[0], query_param, item_var)
            expr = f"({a}).equals({b})"
            return ("(!" + expr + ")") if isinstance(op, ast.NotEq) else expr
        raise _SearchUntranslatable("compare")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ('startswith', 'endswith'):
        base = _search_str_expr(node.func.value, query_param, item_var)
        arg = _search_str_expr(node.args[0], query_param, item_var) if node.args else '""'
        m = 'startsWith' if node.func.attr == 'startswith' else 'endsWith'
        return f"({base}).{m}({arg})"
    raise _SearchUntranslatable("cond:" + type(node).__name__)


_SEARCH_CONSTRUCTS = {
    "name": "a variable that is neither the query nor the item",
    "call": "a method call ApkPy cannot express in Java",
    "compare": "a comparison other than ==, != or in",
    "cond": "a condition shape ApkPy cannot express in Java",
}


def _report_untranslatable_search(error, search):
    """Explain a search filter that the Android generator had to drop.

    The Previewer runs the lambda in Python, so it keeps filtering.  The APK
    would silently stop filtering, which is exactly the Preview/Android
    divergence that is hardest to notice, so it is reported as a diagnostic
    rather than a one-line note.
    """
    detail = str(error)
    kind, _, subject = detail.partition(":")
    construct = _SEARCH_CONSTRUCTS.get(kind, "a construct ApkPy cannot express in Java")
    received = detail if subject else kind
    target = search.get("target") or "the list"
    report_diagnostic(Diagnostic(
        code="C4002",
        title="A real-time search filter was not translated to Android",
        message=(
            "The search filter for %s stays active in the Previewer but is "
            "omitted from the APK." % target
        ),
        context="Android multi-screen compiler",
        cause=(
            "Real-time search becomes a Java TextWatcher, so the lambda has to "
            "be translated statement by statement. This one uses %s, which has "
            "no equivalent the generator can emit, so the field is generated "
            "without the filter instead of with a wrong one." % construct
        ),
        received=received,
        expected=(
            "a lambda comparing the query with item fields, e.g. "
            "lambda q: results.set_items([n for n in notes "
            "if q.lower() in n['title'].lower()])"
        ),
        suggestions=[
            "Keep the condition to item fields, the query, and in / == / != / startswith / endswith.",
            "Use .lower(), .upper() or .strip() for case handling; other methods are not translated.",
            "Move any extra computation out of the lambda and into the list you pass to set_items().",
        ],
        docs="https://repo-apkpy.pages.dev/troubleshooting/#the-previewer-works-but-android-differs",
        technical="untranslatable search construct: %s" % detail,
    ))

def _parse_search_onchange(on_change_node):
    """Se `on_change_node` for uma lambda da forma
        lambda q: ALVO.set_items([x for x in FONTE if COND])
    devolve {'target', 'query_param', 'item_var', 'cond'} (cond pode ser None).
    Caso contrário devolve None — a pesquisa em tempo real só é gerada para
    este padrão (o mesmo que o previewer suporta)."""
    if not isinstance(on_change_node, ast.Lambda):
        return None
    args = on_change_node.args.args
    query_param = args[0].arg if args else 'q'
    body = on_change_node.body
    # ALVO.set_items(<listcomp>)
    if not (isinstance(body, ast.Call) and isinstance(body.func, ast.Attribute)
            and body.func.attr == 'set_items' and isinstance(body.func.value, ast.Name)
            and body.args):
        return None
    target = body.func.value.id
    comp = body.args[0]
    if not (isinstance(comp, ast.ListComp) and comp.generators):
        return None
    gen = comp.generators[0]
    if not isinstance(gen.target, ast.Name):
        return None
    cond = gen.ifs[0] if gen.ifs else None
    return {'target': target, 'query_param': query_param,
            'item_var': gen.target.id, 'cond': cond}


def _change_lambda(transpiler, node, hint):
    """``on_change=lambda value: ...`` of a field, as the name of a function
    the view calls with the new value.

    A named function was kept and a lambda was dropped without a word -- the
    field got no listener, and typing did nothing on a phone while the
    Previewer, which runs the lambda as Python, did what was written. The
    body becomes the body of a function named after the field, which is what
    chips() and segmented() already did with theirs.
    """
    arguments = node.args
    params = [a.arg for a in arguments.posonlyargs + arguments.args]
    if len(params) != 1 or arguments.vararg or arguments.kwarg or arguments.kwonlyargs:
        unsupported.raise_unsupported(
            node,
            cause=('on_change= is called with one thing, the new value, so '
                   'its lambda takes one parameter. With any other number '
                   'the Previewer calls it, fails, and shows nothing.'),
            suggestions=['Write it as on_change=lambda value: ...',
                         'Or name a function: on_change=changed, with '
                         'def changed(value): above.'],
            received=unsupported.describe(node)[:90])
    body = node.body
    if isinstance(body, ast.IfExp):
        # `a() if test else b()` is two statements under an if; a branch that
        # is only a value (None, "") is the branch that does nothing.
        does = [None if isinstance(branch, ast.Constant) else ast.Expr(value=branch)
                for branch in (body.body, body.orelse)]
        if does[0] is None and does[1] is None:
            statements = []
        elif does[0] is None:
            statements = [ast.If(test=ast.UnaryOp(op=ast.Not(), operand=body.test),
                                 body=[does[1]], orelse=[])]
        else:
            statements = [ast.If(test=body.test, body=[does[0]],
                                 orelse=[does[1]] if does[1] is not None else [])]
    else:
        statements = [ast.Expr(value=body)]
    for statement in statements:
        ast.copy_location(statement, node)
        ast.fix_missing_locations(statement)
    name = transpiler._unique_function_name(str(hint or 'input') + '_change')
    transpiler.functions[name] = {
        'args': params,
        'cmds': transpiler._parse_statements(statements),
        'string_args': set(params),
        'returns_value': False,
    }
    return name


_CHANGING_METHODS = frozenset((
    'append', 'extend', 'insert', 'pop', 'remove', 'sort', 'reverse', 'clear',
    'update', 'setdefault', 'popitem', 'add', 'discard'))


def _changes_name(body, name):
    """Whether these statements give *name* a new value or change what it holds:
    an assignment, a for or an except of that name, x[i] = v, del, x.append()...
    A def or a lambda inside is its own scope and is not looked into."""
    stack = list(body or [])
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Name) and node.id == name \
                and isinstance(node.ctx, (ast.Store, ast.Del)):
            return True
        if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            return True
        if isinstance(node, ast.ExceptHandler) and node.name == name:
            return True
        if isinstance(node, (ast.Subscript, ast.Attribute)) \
                and isinstance(node.ctx, (ast.Store, ast.Del)) \
                and isinstance(node.value, ast.Name) and node.value.id == name:
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in _CHANGING_METHODS \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == name:
            return True
        stack.extend(ast.iter_child_nodes(node))
    return False


# A name whose every value in its function is an item, `name = d[k]` or
# `name = xs[i]`: the Java keeps the item as the JSON holds it beside its
# text. k = data["n"] then json.dumps({"k": k}) wrote "5" for a 5. The reads
# carry one of these attributes, holding the name:
#   _ITEM_SHARED  the name is read by no lambda, nested def or comprehension:
#                 one Object for the whole method, given each item in turn;
#   _ITEM_ONCE    it is, and it is given one value: an Object declared there,
#                 never changed (a Java lambda may read it), seen in its block.
_ITEM_ONCE = '_apkpy_item_once'
_ITEM_SHARED = '_apkpy_item_shared'
# (name, what _RAW_LOOP_VARS held before) for each name while the Java block
# that declares its item is written; see _gen_cmds.
_ITEM_STACK = [[]]
# name -> its Object in the method being written (_ITEM_SHARED).
_ITEM_SHARED_JAVA = [{}]
_ITEM_COUNT = [0]


def _names_an_item(value, name):
    """True when ``name = value`` gives *name* an item the JSON holds with
    its type: d[k] / xs[i], d.get(k, default), or the item pop() takes.
    last = xs.pop() then [last] was ['9'] where CPython has [9]."""
    if _item_read(value) is not None:
        return True
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) \
            and value.func.attr == 'get' and 1 <= len(value.args) <= 2 \
            and not value.keywords \
            and not any(isinstance(a, ast.Starred) for a in value.args) \
            and _dict_receiver(value.func.value):
        return True
    popped = _popped_item(value)
    # x = x.pop(): the item is read again after the name has changed.
    return popped is not None and not (
        isinstance(popped.args[1], ast.Name) and popped.args[1].id == name)


def _mark_item_names(fn):
    """Mark ``name = d[k]`` / ``name = xs[i]`` in *fn* when every binding of
    *name* there is one of these: not a parameter, not global, not given
    another value, not changed through x[i] = v or x.append() -- anywhere in
    the function, nested functions and comprehensions counted, so a binding
    of any other kind leaves the name as it was."""
    args = fn.args
    params = {a.arg for a in list(getattr(args, 'posonlyargs', [])) + args.args + args.kwonlyargs}
    for extra in (args.vararg, args.kwarg):
        if extra is not None:
            params.add(extra.arg)
    bindings = {}

    def bind(name, weight=1):
        bindings[name] = bindings.get(name, 0) + weight

    for node in ast.walk(fn):
        if node is fn:
            continue
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bind(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bind(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bind(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                bind(name, 2)
        elif isinstance(node, (ast.Subscript, ast.Attribute)) \
                and isinstance(node.ctx, (ast.Store, ast.Del)) \
                and isinstance(node.value, ast.Name):
            bind(node.value.id, 2)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in _CHANGING_METHODS \
                and isinstance(node.func.value, ast.Name):
            bind(node.func.value.id, 2)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bind((alias.asname or alias.name).split('.')[0], 2)
    # Names a lambda, a nested def or a comprehension reads: a Java lambda
    # can only read a local that never changes.
    captured = set()
    for node in ast.walk(fn):
        if node is not fn and isinstance(node, (
                ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            captured.update(inner.id for inner in ast.walk(node) if isinstance(inner, ast.Name))
    # The statements of the function and of its blocks (for, while, if, try,
    # with), where `name = d[k]` may stand.
    reads = {}
    blocks = [fn.body]
    while blocks:
        for statement in blocks.pop():
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for field in ('body', 'orelse', 'finalbody'):
                inner = getattr(statement, field, None)
                if isinstance(inner, list):
                    blocks.append(inner)
            for handler in getattr(statement, 'handlers', None) or ():
                blocks.append(handler.body)
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1 \
                    and isinstance(statement.targets[0], ast.Name) \
                    and _names_an_item(statement.value, statement.targets[0].id):
                reads.setdefault(statement.targets[0].id, []).append(statement.value)
    for name, values in reads.items():
        if name in params or bindings.get(name) != len(values):
            continue
        if name not in captured:
            for value in values:
                setattr(value, _ITEM_SHARED, name)
        elif len(values) == 1:
            setattr(values[0], _ITEM_ONCE, name)


def _shared_item_names(cmds):
    """The _ITEM_SHARED names these commands give an item, in order."""
    found = []
    stack = [list(cmds or [])]
    while stack:
        for command in stack.pop():
            if not isinstance(command, dict):
                continue
            if command.get('type') == 'local_string_assign' \
                    and getattr(command.get('val_node'), _ITEM_SHARED, None) == command.get('var') \
                    and command['var'] not in found:
                found.append(command['var'])
            for value in command.values():
                if isinstance(value, list):
                    stack.append(value)
    return found


def _item_names_hide():
    """A new Java method starts: the item names of the one being written are
    not declared in it. Returns what _item_names_show() puts back."""
    held = _ITEM_STACK[0]
    current = [(name, _RAW_LOOP_VARS[0].get(name)) for name, _before in held]
    for name, before in reversed(held):
        _raw_loop_leave(name, before)
    _ITEM_STACK[0] = []
    shared = _ITEM_SHARED_JAVA[0]
    _ITEM_SHARED_JAVA[0] = {}
    return held, current, shared


def _item_names_show(hidden):
    held, current, shared = hidden
    _ITEM_STACK[0] = held
    _ITEM_SHARED_JAVA[0] = shared
    for name, value in current:
        if value is not None:
            _RAW_LOOP_VARS[0][name] = value


def _item_names_leave(mark):
    """The Java block that declared these items ends."""
    while len(_ITEM_STACK[0]) > mark:
        name, before = _ITEM_STACK[0].pop()
        _raw_loop_leave(name, before)


def _raw_loop_enter(var, raw_name):
    """The name *var* reads *raw_name* (or nothing) while a for body is written."""
    before = _RAW_LOOP_VARS[0].get(var)
    if raw_name is None:
        _RAW_LOOP_VARS[0].pop(var, None)
    else:
        _RAW_LOOP_VARS[0][var] = raw_name
    return before


def _raw_loop_leave(var, before):
    if before is None:
        _RAW_LOOP_VARS[0].pop(var, None)
    else:
        _RAW_LOOP_VARS[0][var] = before


def _mixed_data_literal(node, val_to_java):
    """A list or tuple written out with data of more than one kind:
    ``[[], {}, "", 0, None]``. As an array of texts its items lost what they
    were -- [] became the text "[]", true in an `if` -- so it is walked as
    JSON instead. A list of names (``for w in [title, footer]``) stays as it
    was: those are the app's own things, not data.
    """
    if not node.elts or _literal_number_kind(node) is not None:
        return False
    plain_text = True
    for item in node.elts:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            continue
        if isinstance(item, (ast.List, ast.Dict, ast.Tuple)) or (
                isinstance(item, ast.Constant) and not isinstance(item.value, bytes)):
            plain_text = False
            continue
        if _kind_from(val_to_java, item) == 'text':
            continue
        return False
    return not plain_text


def _known_number_kind(node, val_to_java):
    """_literal_number_kind for a list written out with numbers and names the
    source knows are numbers: for x in [n, 4]."""
    numeric = getattr(val_to_java, 'numeric', None) if val_to_java is not None else None
    if numeric is None or not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
        return None
    kinds = set()
    for item in node.elts:
        literal = _literal_number_kind(ast.List(elts=[item], ctx=ast.Load()))
        if literal is not None:
            kinds.add(literal)
            continue
        known = numeric(item)
        if known is None:
            return None
        kinds.add('float' if known[1] else 'int')
    return kinds.pop() if len(kinds) == 1 else 'mixed'


def _number_loop_enter(c, var, it, numeric_vars, mixed=True, val_to_java=None):
    """for x in [4, 15, 7]: x is a number of that kind while the body is
    written, as range()'s is; for x in [1, 2.5] each item is the number it is.
    Nothing when the body gives x another value. Returns what to undo."""
    kind = _literal_number_kind(it) or _known_number_kind(it, val_to_java)
    body = c.get('body_ast')
    if kind is None or body is None or _changes_name(body, var):
        return None
    if kind == 'mixed' or numeric_vars is None:
        if not mixed:
            return None
        return ('raw', _raw_loop_enter(var, "_apkpyNumberOf(%s)" % var))
    had = var in numeric_vars
    was = numeric_vars.get(var)
    numeric_vars[var] = (kind == 'float')
    return ('num', had, was)


def _number_loop_leave(var, undo, numeric_vars):
    if undo is None:
        return
    if undo[0] == 'raw':
        _raw_loop_leave(var, undo[1])
    elif undo[1]:
        numeric_vars[var] = undo[2]
    else:
        numeric_vars.pop(var, None)


def _emit_for_loop(lines, indent, c, val_to_java, gen_body, json_iter_vars,
                   numeric_vars=None):
    """
    Emite o Java de um `for` Python. Três formas suportadas:

      for x in ["a", "b"]:   → for (String x : new String[]{...})
      for i in range(a, b):  → for clássico com contador (i vem como String,
                               mas conta como int em *numeric_vars*)
      for row in rows:       → loop sobre org.json.JSONArray — `rows` é a
                               string JSON de db.query()/https; cada `row`
                               fica registado em *json_iter_vars* para que
                               row["chave"] compile para _jsonGet(row, "chave").

    JSON inválido (ou não-array) não rebenta: o try/catch deixa o loop sem
    iterações, igual ao Previewer.
    """
    var = c['var']
    it = c['iter_node']
    sfx = id(c) & 0xFFFF
    if isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == 'range':
        if len(it.args) >= 2:
            start, stop = val_to_java(it.args[0]), val_to_java(it.args[1])
        else:
            start, stop = '0', (val_to_java(it.args[0]) if it.args else '0')
        # The end is worked out once, as Python does: re-reading it on every
        # pass ran `for i in range(len(items))` for ever when the body
        # appended to items. And the step was dropped -- range(0, 10, 2) went
        # 0, 1, 2, ... on the phone.
        first = f"int _i_{sfx} = Integer.parseInt(String.valueOf({start})), _e_{sfx} = Integer.parseInt(String.valueOf({stop}))"
        step_node = it.args[2] if len(it.args) >= 3 else None
        step = _int_literal(step_node) if step_node is not None else 1
        if step_node is not None and step == 0:
            unsupported.raise_unsupported(
                it, cause='Python stops here with ValueError: range() arg 3 must not be zero.',
                suggestions=['Give the step you mean, such as 2, or -1 to count down.'])
        if step is None:
            lines.append(
                f"{indent}for ({first}, _s_{sfx} = _apkpyRangeStep(String.valueOf({val_to_java(step_node)})); "
                f"_s_{sfx} > 0 ? _i_{sfx} < _e_{sfx} : _i_{sfx} > _e_{sfx}; _i_{sfx} += _s_{sfx}) {{")
        elif step == 1:
            lines.append(f"{indent}for ({first}; _i_{sfx} < _e_{sfx}; _i_{sfx}++) {{")
        elif step > 0:
            lines.append(f"{indent}for ({first}; _i_{sfx} < _e_{sfx}; _i_{sfx} += {step}) {{")
        else:
            lines.append(f"{indent}for ({first}; _i_{sfx} > _e_{sfx}; _i_{sfx} -= {-step}) {{")
        lines.append(f"{indent}    String {var} = String.valueOf(_i_{sfx});")
        # range() da ints. Sem o dizer, i + 1 era "0" + "1" -- "01" no
        # telemovel e 1 no Previewer -- e i % 2 nao tinha traducao nenhuma.
        _had = numeric_vars is not None and var in numeric_vars
        _was = numeric_vars.get(var) if _had else None
        if numeric_vars is not None:
            numeric_vars[var] = False
        _raw_before = _raw_loop_enter(var, None)
        gen_body(c['body'], indent + "    ")
        _raw_loop_leave(var, _raw_before)
        if numeric_vars is not None:
            if _had:
                numeric_vars[var] = _was
            else:
                numeric_vars.pop(var, None)
        lines.append(f"{indent}}}")
    elif isinstance(it, (ast.List, ast.Tuple)) and not _mixed_data_literal(it, val_to_java):
        elems = ", ".join(f"String.valueOf({val_to_java(e)})" for e in it.elts)
        lines.append(f"{indent}for (String {var} : new String[]{{{elems}}}) {{")
        _raw_before = _raw_loop_enter(var, None)
        if it.elts and all(_static_kind(e) in ('list', 'dict') for e in it.elts):
            # for g in [[1], [2]]: each g is a list, as for g in grid would say;
            # grown.append(g) kept the JSON text of it.
            json_iter_vars.add(var)
        # for x in [4, 15, 7]: x.append'd went in as '4'. And for x in [n, 4]
        # with n a number: x * 3 stopped the build.
        _undo = _number_loop_enter(c, var, it, numeric_vars, val_to_java=val_to_java)
        gen_body(c['body'], indent + "    ")
        _number_loop_leave(var, _undo, numeric_vars)
        _raw_loop_leave(var, _raw_before)
        lines.append(f"{indent}}}")
    else:
        # Qualquer outra expressão = string JSON (db.query / resposta https /
        # variável com lista). Cada elemento vem como String: objetos JSON
        # ficam como o seu texto JSON — row["k"] lê-os via _jsonGet.
        # A list written at the top of the file and never changed has no
        # Java field: its name alone was a cannot-find-symbol inside any
        # function. The loop walks its literal, as `x in NAMES` already does.
        # One a function rebinds with `global` lives in the shared store, and
        # its literal is only what it held before that function ran.
        if (isinstance(it, ast.Name) and it.id not in _MUTATED_LISTS[0]
                and it.id not in _GLOBALS[0]
                and isinstance(_MODULE_LISTS[0].get(it.id), ast.List)):
            it = _MODULE_LISTS[0][it.id]
        # What Python walks depends on what the value is: a list its items, a
        # dict its keys, text its characters. The loop used to parse every
        # value as a JSON list inside a try that swallowed the failure, so
        # `for k in PRICES` and `for ch in name` ran no times -- and an error
        # raised by the body itself vanished with it. The kind comes from the
        # source where the source says (_static_kind); otherwise
        # _apkpyItems decides from the JSON shape, and nothing is swallowed.
        kind_of = getattr(val_to_java, 'kind_of', None)
        kind = kind_of(it) if kind_of is not None else _static_kind(it)
        src = val_to_java(it)
        if kind == 'dict':
            walk = f"_apkpyKeys(String.valueOf({src}))"
        elif kind == 'text':
            walk = f"_apkpyChars(String.valueOf({src}))"
        else:
            walk = f"_apkpyItems(String.valueOf({src}))"
            json_iter_vars.add(var)
        # The item as the JSON holds it, beside its text, while the body does
        # not change the name: a copy of the list, a comparison or a dumps()
        # of it keeps 12 a number and "12" text.
        raw_name = None
        if walk.startswith("_apkpyItems(") and c.get('body_ast') is not None \
                and not _changes_name(c['body_ast'], var):
            raw_name = f"_fr_{sfx}"
        lines.append(f"{indent}{{")
        lines.append(f"{indent}    org.json.JSONArray _fa_{sfx} = {walk};")
        lines.append(f"{indent}    for (int _fi_{sfx} = 0; _fi_{sfx} < _fa_{sfx}.length(); _fi_{sfx}++) {{")
        if raw_name is not None:
            lines.append(f"{indent}        Object {raw_name} = _fa_{sfx}.opt(_fi_{sfx});")
            lines.append(f"{indent}        String {var} = _apkpyFromJson({raw_name});")
        else:
            lines.append(f"{indent}        String {var} = _apkpyFromJson(_fa_{sfx}.opt(_fi_{sfx}));")
        _raw_before = _raw_loop_enter(var, raw_name)
        # The literal of a module list of numbers: its items are numbers.
        _undo = _number_loop_enter(c, var, it, numeric_vars, mixed=False) \
            if walk.startswith("_apkpyItems(") else None
        gen_body(c['body'], indent + "        ")
        _number_loop_leave(var, _undo, numeric_vars)
        _raw_loop_leave(var, _raw_before)
        lines.append(f"{indent}    }}")
        lines.append(f"{indent}}}")


def _append_value_java(node, val_to_java):
    """What xs.append(x) puts in the list when x is not a literal.

    A number the source knows is one goes in as a number, and an item read
    from JSON as the JSON holds it: [len(w) for w in words] held '2' and
    '12', and sorted() put '12' first. A float too, as d[k] = x stores it:
    as text it showed quotes in str(xs), sorted() stopped on str < float and
    json.dumps() wrote "3.0". The JSON of the phone writes a whole 5.0 as 5,
    as it does for [5.0] written out.
    """
    if isinstance(node, ast.Constant):
        return val_to_java(node)             # True stays True, as before
    numeric = getattr(val_to_java, 'numeric', None)
    known = numeric(node) if numeric is not None else None
    if known is not None:
        return ("Double.valueOf(%s)" if known[1] else "Long.valueOf(%s)") % known[0]
    if known is None:
        if _kind_from(val_to_java, node) in ('list', 'dict'):
            # [sorted(g) for g in groups]: a list of lists, not of their JSON text.
            return "_apkpyJsonVal(String.valueOf(%s))" % val_to_java(node)
        typed = _typed_json_java(node, val_to_java)
        if typed is not None:
            return typed
        raw = _raw_item_java(node, val_to_java)
        if raw is not None:
            return raw
    return val_to_java(node)


def _sort_key_java(node, val_to_java):
    """A key of sorted()/min()/max(), as it is compared: a float as a number too."""
    numeric = getattr(val_to_java, 'numeric', None)
    if numeric is not None and numeric(node) is None and isinstance(node, ast.Call) \
            and isinstance(node.func, ast.Name) and (
                (node.func.id in _ALWAYS_NUMBERS and not node.keywords)
                # obj.total, given 0 and later 2.5 (features/classes.py)
                or getattr(node, classes_feature.NUMBER, False)):
        return "_apkpyNumberOf(String.valueOf(%s))" % val_to_java(node)
    return _json_value_java(node, val_to_java)


def _known_plain(node, val_to_java):
    """A name known here to hold a number or text. The names of the for loops
    over JSON stay in their set after the loop, and in the next function too:
    for x in [4, 11] then put '4' in a list, because another function had
    walked a list with an x of its own."""
    numeric = getattr(val_to_java, 'numeric', None)
    if numeric is not None and numeric(node) is not None:
        return True
    return _kind_from(val_to_java, node) == 'text'


def _emit_list_append(lines, indent, c, val_to_java, json_iter_vars=()):
    """``lista.append(x)``.

    A list is JSON text on the phone, so appending writes the variable again
    instead of changing an object in place. A dict or a list being appended
    goes through the JSON builder so its types survive the trip -- appending
    ``{"title": "You"}`` has to produce an object, not a quoted blob that
    ``row["title"]`` could never read back.

    **Text stays text.** An earlier version passed everything through
    ``_apkpyJsonVal``, which reads anything shaped like JSON back into a
    structure -- so somebody typing ``[1, 2]`` into a field had a *list*
    appended where Python would have appended the eight characters they typed.
    Only a value the generator knows is a structure is restored as one: a row
    from ``for row in rows:`` is a dict in Python and must stay a dict here.
    """
    node = c['val_node']
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id == sort_key_feature.SORTKEY and len(node.args) == 1:
        # A key of sorted()/min()/max(): compared, never shown, so a float
        # goes in as a number too.
        value = _sort_key_java(node.args[0], val_to_java)
    elif isinstance(node, (ast.Dict, ast.List, ast.Tuple)):
        value = _json_node_to_java(node, val_to_java)
    elif isinstance(node, ast.Name) and node.id in _RAW_LOOP_VARS[0]:
        # The item of a for over a list, as the JSON holds it: 12 a number,
        # "12" text, a row a dict. As text, [x for x in SCORES] was ['9', '12'].
        value = _RAW_LOOP_VARS[0][node.id]
    elif isinstance(node, ast.Name) and node.id in (json_iter_vars or ()) \
            and not _known_plain(node, val_to_java):
        value = "_apkpyJsonVal(String.valueOf(%s))" % val_to_java(node)
    else:
        value = _append_value_java(node, val_to_java)
    target = c['var']
    if target in _MUTATED_LISTS[0]:
        # Lista de módulo: uma só por processo, como em Python. Uma cópia por
        # Activity faria o ecrã seguinte abrir com a lista antiga.
        lines.append(
            f'{indent}ApkpyReactiveState.set("{_mutated_list_key(target)}", '
            f'_apkpyListAppend(String.valueOf({_mutated_list_read(target)}), {value}));')
    else:
        lines.append(f"{indent}{target} = _apkpyListAppend(String.valueOf({target}), {value});")


# Python's built-in errors that ``except`` and ``raise`` name. Their family
# tree is ApkpyValues.parent() on the phone.
_PY_ERRORS = frozenset((
    'BaseException', 'Exception', 'ArithmeticError', 'ZeroDivisionError',
    'OverflowError', 'FloatingPointError', 'LookupError', 'KeyError',
    'IndexError', 'ValueError', 'UnicodeError', 'TypeError', 'AttributeError',
    'NameError', 'RuntimeError', 'RecursionError', 'NotImplementedError',
    'AssertionError', 'MemoryError', 'OSError', 'FileNotFoundError',
    'PermissionError', 'FileExistsError', 'TimeoutError', 'ConnectionError',
    'IsADirectoryError', 'NotADirectoryError', 'ImportError',
    'ModuleNotFoundError', 'StopIteration', 'EOFError'))
_ERROR_ALIASES = {'IOError': 'OSError', 'EnvironmentError': 'OSError'}
# An except naming one of these also catches a missing key or index, so
# inside its try d[k] and xs[i] raise (ApkpyValues.strict).
_LOOKUP_CATCHERS = frozenset(('KeyError', 'IndexError', 'LookupError',
                              'Exception', 'BaseException'))


def _error_name(node):
    """The error *node* names -- one of Python's (IOError is OSError) or an error
    class the app writes at the top of the file -- or None."""
    if isinstance(node, ast.Name):
        name = _ERROR_ALIASES.get(node.id, node.id)
        if name in _PY_ERRORS or classes_feature.error_parent(name):
            return name
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
            and node.value.id == 'json' and node.attr == 'JSONDecodeError':
        return 'JSONDecodeError'             # a ValueError (ApkpyValues.parent)
    return None


def _refuse_error_name(node, where):
    unsupported.raise_unsupported(
        node,
        cause=('This %s names %s, which is not an error ApkPy knows. It knows '
               'Python\'s built-in errors by name -- ValueError, KeyError, '
               'IndexError, TypeError, ZeroDivisionError, OSError, Exception and the '
               'rest -- and the error classes written at the top of the file.'
               % (where, unsupported.describe(node))),
        suggestions=['Write the error at the top of the file: class %s(Exception): pass'
                     % (unsupported.describe(node) if isinstance(node, ast.Name)
                        else 'MyError'),
                     'Or use the built-in error closest to it: raise ValueError("...").'],
    )


def _except_types(node):
    """The errors an except catches, by name; None for a bare except."""
    if node is None:
        return None
    parts = node.elts if isinstance(node, ast.Tuple) else [node]
    names = []
    for part in parts:
        name = _error_name(part)
        if name is None:
            _refuse_error_name(part, 'except')
        names.append(name)
    return names


def _raise_command(stmt, handlers):
    """``raise X(msg)``, or a bare ``raise`` / ``raise e`` inside an except.

    *handlers* is the stack of excepts the statement is in, innermost last,
    as (Java name of the caught error, the ``as`` name).
    """
    exc = stmt.exc
    if exc is None:
        if not handlers:
            unsupported.raise_unsupported(
                stmt,
                cause=('raise on its own throws again the error being handled, '
                       'so it only means something inside an except.'),
                suggestions=['Name the error: raise ValueError("...").'],
            )
        return {'type': 'raise', 'rethrow': handlers[-1][0]}
    if isinstance(exc, ast.Name):
        caught = [err for err, name in handlers if name == exc.id]
        if caught:
            return {'type': 'raise', 'rethrow': caught[-1]}
    call = exc if isinstance(exc, ast.Call) else None
    target = call.func if call is not None else exc
    name = _error_name(target)
    if name is None:
        _refuse_error_name(target, 'raise')
    if call is not None and (call.keywords or len(call.args) > 1
                             or any(isinstance(a, ast.Starred) for a in call.args)):
        unsupported.raise_unsupported(
            exc,
            cause=('An error raised with more than one value shows them as a '
                   'tuple, and ApkPy keeps one text per error.'),
            suggestions=['Put it in one text: raise ValueError(f"{name}: {value}").'],
        )
    message = call.args[0] if call is not None and call.args else None
    if message is None and classes_feature.error_default(name) is not None:
        # raise NotFound() of a class whose __init__ has message="Not found".
        message = ast.copy_location(ast.Constant(value=classes_feature.error_default(name)), stmt)
    return {'type': 'raise', 'kind': name, 'msg_node': message}


def _emit_raise(lines, indent, c, val_to_java, numeric):
    """``raise``. Written as ``if (true) throw``: Java refuses a line after a
    throw as unreachable, and the generator writes some (a global written
    back, a closing return) without knowing a raise came before them."""
    if c.get('rethrow'):
        lines.append(f"{indent}if (true) throw ApkpyValues.rethrow({c['rethrow']});")
        return
    node = c.get('msg_node')
    message = '""' if node is None else _text_value_java(node, val_to_java)
    if 'KeyError' in classes_feature.error_chain(c['kind']) and node is not None \
            and numeric(node) is None:
        # str(KeyError("k")) is 'k', quotes and all -- and a KeyError of the app's own.
        message = f"_apkpyRepr({message})"
    lines.append(f'{indent}if (true) throw new ApkpyValues.Raised("{c["kind"]}", {message});')


def _emit_print(lines, indent, c, val_to_java):
    """``print(a, b, sep=..., end=...)``: each value as str() shows it, joined
    by sep, to ApkpyValues.print (Logcat)."""
    parts = []
    for arg in c['args']:
        shown = ast.copy_location(ast.Call(func=ast.Name(id='str', ctx=ast.Load()),
                                           args=[arg], keywords=[]), arg)
        parts.append(val_to_java(shown))
    sep = '" "' if c.get('sep') is None else f"String.valueOf({val_to_java(c['sep'])})"
    end = '"\\n"' if c.get('end') is None else f"String.valueOf({val_to_java(c['end'])})"
    text = f" + {sep} + ".join(parts) if parts else '""'
    lines.append(f"{indent}ApkpyValues.print({text}, {end});")


def _print_command(call):
    """The command for a print() call, or a refusal for what it cannot keep."""
    keywords = {kw.arg: kw.value for kw in call.keywords}
    unknown = sorted(k for k in keywords if k not in ('sep', 'end', 'flush'))
    if unknown or any(isinstance(a, ast.Starred) for a in call.args) or None in keywords:
        unsupported.raise_unsupported(
            call,
            cause=('print() goes to Logcat on the phone, so only sep= and end= '
                   'mean anything there; a file= has nowhere to go.'),
            suggestions=['Write the text with files.write(name, text), or show it '
                         'with toast() or a label.'],
        )

    def given(name):
        value = keywords.get(name)
        if isinstance(value, ast.Constant) and value.value is None:
            return None      # sep=None and end=None are the defaults
        return value
    return {'type': 'print', 'args': list(call.args), 'sep': given('sep'), 'end': given('end')}


def _emit_try_block(lines, indent, c, gen_body, declared=()):
    """``try`` / ``except`` / ``finally``, with Python's error types.

    One Java catch, and in it each except in order, tested by the error's
    Python type (ApkpyValues.isA, which knows the family: LookupError catches
    KeyError). The helpers throw their errors by Python name, and the Java
    errors that stand for one are read as it -- NumberFormatException is
    int("x")'s ValueError. An error no except names is thrown again, as in
    Python. A try with only a finally has no catch.

    When an except catches a missing key or index, the body runs with
    ApkpyValues.strict on, so ``d[k]`` raises the KeyError it is waiting for;
    outside such a try the empty text of before stays, and an app that
    worked keeps working.

    ``except ... as e`` binds a **String** (ApkpyValues.message), because
    that is what every use of it does here: show it, store it, send it.

    Variables assigned inside any block are declared before it by
    :func:`_hoist_branch_assignments` -- Java scopes them to the braces and
    Python does not, and the difference is a cannot-find-symbol on the line
    after the block.
    """
    err = c.get('err') or f"_te_{id(c) & 0xFFFF}"
    clauses = c.get('handler') or []
    inner = indent + "    "
    lines.append(f"{indent}try {{")
    if clauses and c.get('strict'):
        lines.append(f"{inner}ApkpyValues.strict(1);")
        lines.append(f"{inner}try {{")
        gen_body(c.get('body'), inner + "    ")
        lines.append(f"{inner}}} finally {{")
        lines.append(f"{inner}    ApkpyValues.strict(-1);")
        lines.append(f"{inner}}}")
    else:
        gen_body(c.get('body'), inner)
    if clauses:
        lines.append(f"{indent}}} catch (Throwable {err}) {{")
        for i, clause in enumerate(clauses):
            names = ", ".join('"%s"' % n for n in (clause.get('types') or ['BaseException']))
            opening = "if" if i == 0 else "} else if"
            lines.append(f"{inner}{opening} (ApkpyValues.isA({err}, {names})) {{")
            name = clause.get('name')
            if name:
                # Um nome já declarado neste método não pode ser redeclarado aqui.
                prefix = "" if name in declared else "String "
                lines.append(f"{inner}    {prefix}{name} = ApkpyValues.message({err});")
            gen_body(clause.get('body'), inner + "    ")
        lines.append(f"{inner}}} else {{")
        lines.append(f"{inner}    throw ApkpyValues.rethrow({err});")
        lines.append(f"{inner}}}")
    if c.get('final'):
        lines.append(f"{indent}}} finally {{")
        gen_body(c.get('final'), inner)
    lines.append(f"{indent}}}")


# Tecto de segurança do `while` no Android: o código corre na UI thread, por isso
# um loop que nunca termina daria ANR (app congelada). Loops normais terminam
# muito antes deste limite; só um loop verdadeiramente infinito (que seria um bug
# na app) é cortado. O previewer (Python) não tem este tecto — diverge só nesse
# caso patológico.
_WHILE_GUARD_MAX = 10_000_000


def _assign_rhs_java(val_node, val_to_java):
    """RHS de uma atribuição local `x = <val>` no modelo "tudo é String".

    Um literal numérico nu (`i = 0`) tem de virar a String "0" — senão geraria
    `String i = 0;`, que é Java inválido. Os restantes casos já saem como String
    do val_to_java (BinOp → String.valueOf(...), chamadas, f-strings, etc.)."""
    if isinstance(val_node, ast.Constant) and (val_node.value is None
                                               or isinstance(val_node.value, bool)):
        return _text_value_java(val_node, val_to_java)
    if isinstance(val_node, ast.Constant) and isinstance(val_node.value, (int, float)) \
            and not isinstance(val_node.value, bool):
        return f'"{val_node.value}"'
    if isinstance(val_node, ast.UnaryOp) and isinstance(val_node.op, (ast.USub, ast.UAdd)):
        # `x = -1` é o mesmo caso: sem aspas saía `String x = -1;`.
        try:
            literal = ast.literal_eval(val_node)
        except (TypeError, ValueError, SyntaxError):
            literal = None
        if isinstance(literal, (int, float)) and not isinstance(literal, bool):
            return f'"{literal}"'
    return val_to_java(val_node)


def _emit_while_loop(lines, indent, c, val_to_java, gen_body, bool_names=()):
    """Emite o Java de um `while <cond>:` Python.

    A condição reutiliza `_cond_to_java` (comparações, and/or/not, truthiness de
    nome, bool literal) — a MESMA dos `if`, por isso o comportamento é consistente.
    Traz o contador anti-ANR _WHILE_GUARD_MAX (ver comentário acima)."""
    cond = _cond_to_java(c['test'], val_to_java, bool_names) or "false"
    sfx = id(c) & 0xFFFF
    guard = f"_wg_{sfx}"
    lines.append(f"{indent}long {guard} = 0L;")
    lines.append(f"{indent}while (({cond}) && {guard}++ < {_WHILE_GUARD_MAX}L) {{")
    gen_body(c['body'], indent + "    ")
    lines.append(f"{indent}}}")


def _fn_cmds(entry):
    """The command list of a ``functions_map`` entry.

    Entries are ``{'args': ..., 'cmds': [...]}``; older call sites also pass a
    bare list, so both shapes are accepted.
    """
    if isinstance(entry, dict):
        return entry.get('cmds') or []
    return entry or []


def _cmds_contain_transition(cmds, kind):
    """True when a navigate asks for this screen transition."""
    for command in cmds or []:
        if not isinstance(command, dict):
            continue
        if command.get('type') == 'navigate' and command.get('transition') == kind:
            return True
        for body_key in _BODY_KEYS:
            if command.get(body_key) and _cmds_contain_transition(command[body_key], kind):
                return True
    return False


# Assignment commands, and the Java type each one declares.
_ASSIGN_COMMAND_TYPES = {
    'storage_get_assign': ('String', '""'),
    'db_query_assign': ('String', '""'),
    'local_string_assign': ('String', '""'),
    'crypto_verify_assign': ('boolean', 'false'),
}


def _branch_assigned_vars(command):
    """Variables a branch of this command assigns, at any depth."""
    found = []

    def walk(cmds):
        for entry in cmds or []:
            if not isinstance(entry, dict):
                continue
            if entry.get('type') in _ASSIGN_COMMAND_TYPES and entry.get('var'):
                found.append((entry['var'], entry['type']))
            for body_key in _BODY_KEYS:
                walk(entry.get(body_key))

    if not isinstance(command, dict):
        return found
    for body_key in _BODY_KEYS:
        walk(command.get(body_key))
    return found


def _hoist_branch_assignments(command, lines, indent, declared):
    """Declare, before the block, any variable a branch assigns.

    Python has no block scope: a name bound inside an ``if`` is still there
    afterwards. Java does, so the declaration was emitted inside the branch
    and the next line could not see it -- the app failed to compile with
    "cannot find symbol", after running fine in the Previewer.
    """
    for var, kind in _branch_assigned_vars(command):
        if var in declared:
            continue
        java_type, empty = _ASSIGN_COMMAND_TYPES[kind]
        lines.append(f"{indent}{java_type} {var} = {empty};")
        declared.add(var)


def _cmds_contain(cmds, type_name):
    """True when a command of this type appears anywhere, branches included."""
    for command in cmds or []:
        if not isinstance(command, dict):
            continue
        if command.get('type') == type_name:
            return True
        for body_key in _BODY_KEYS:
            if command.get(body_key) and _cmds_contain(command[body_key], type_name):
                return True
    return False
