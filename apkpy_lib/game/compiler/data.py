"""Data tables at build time: every row checked against its @dataclass, every Ref[...] against
the table it points to, then written to the bundle (tables/PATH.json).

The class is the schema: no schema file to keep in step. Errors name the file and the path
inside it (data/species/ember_fox.json: moves[2]: ...).
"""
import difflib
import json
import os

from ..errors import GameError
from .._pycompat import subscript_slice
from .scripts import base


def check_tables(program):
    """[(TableVar, rows)] for every table of the game, checked; raises GameError (G13xx)."""
    records = {r.name: r for m in program.all_modules() for r in m.records}
    found, by_record = [], {}
    for module in program.all_modules():
        for v in module.tables.values():
            rows, files = _read(program.root, v, module)
            record = records[v.record]
            if "id" not in record.fields or record.fields["id"][0] != "str":
                raise GameError("G1306", "%s has no 'id: str' field, so it cannot be a table" % v.record,
                                module.source, v.line,
                                cause="A table finds its rows by id: SPECIES.get(\"ember_fox\").",
                                fix="Add  id: str  as the first field of %s." % v.record)
            ids = {}
            for row, where in zip(rows, files):
                _check(row, v.record, records, where, "")
                rid = row["id"]
                if rid in ids:
                    raise GameError("G1305", "the id \"%s\" is used twice in %s (also in %s)" % (rid, v.path, ids[rid]),
                                    where)
                ids[rid] = where
            if v.record in by_record:
                raise GameError("G1306", "%s has two tables (%s and %s)" % (v.record, by_record[v.record][0], v.path),
                                module.source, v.line, fix="One table per @dataclass: a Ref[...] has to know where to look.")
            by_record[v.record] = (v.path, ids)
            found.append((v, rows, files))
    for v, rows, files in found:
        for row, where in zip(rows, files):
            _check_refs(row, v.record, records, by_record, where, "")
    return [(v, rows) for v, rows, _ in found]


def _read(root, v, module):
    single = os.path.join(root, *v.path.split("/")) + ".json"
    folder = os.path.join(root, *v.path.split("/"))
    if not os.path.isfile(single) and not os.path.isdir(folder):
        raise GameError("G1301", "there is no %s.json nor a folder %s/" % (v.path, v.path), module.source, v.line,
                        cause="table(\"%s\", ...) reads %s.json (a list of rows) or %s/*.json (a row per file)."
                              % (v.path, v.path, v.path))
    if os.path.isfile(single):
        rows = _load(single, v.path + ".json")
        if not isinstance(rows, list):
            raise GameError("G1303", "a table file holds a list of rows: [ {...}, {...} ]", v.path + ".json")
        files = ["%s.json: [%d]" % (v.path, i) for i in range(len(rows))]
    else:
        names = [n for n in sorted(os.listdir(folder)) if n.endswith(".json")]      # the order of _data.read_rows
        rows, files = [], []
        for n in names:
            shown = "%s/%s" % (v.path, n)
            row = _load(os.path.join(folder, n), shown)
            for i, one in enumerate(row if isinstance(row, list) else [row]):
                rows.append(one)
                files.append("%s: [%d]" % (shown, i) if isinstance(row, list) else shown)
    for row, where in zip(rows, files):
        if not isinstance(row, dict):
            raise GameError("G1303", "a row is a JSON object { ... }", where)
    return rows, files


def _load(path, shown):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as e:
        raise GameError("G1302", "not valid JSON: %s (column %d)" % (e.msg, e.colno), shown, e.lineno)


def _check(value, t, records, where, path):
    """value (parsed JSON) is of type t, or a G1303/G1304 naming where and the path inside."""
    def wrong(expected):
        raise GameError("G1303", "%s: expected %s, got %s" % (path or "the row", expected, json.dumps(value)), where)

    if t.endswith("?"):
        if value is None:
            return
        t = base(t)
    if t in records:
        if not isinstance(value, dict):
            wrong("an object (%s)" % t)
        fields = records[t].fields
        for key in value:
            if key not in fields:
                hits = difflib.get_close_matches(key, list(fields), n=1)
                raise GameError("G1304", "%s: %s has no field '%s'" % (path or "the row", t, key), where,
                                fix=("Did you mean %s?" % hits[0]) if hits else "Fields: %s" % ", ".join(fields))
        for name, (ft, default, _) in fields.items():
            if name in value:
                _check(value[name], ft, records, where, (path + "." if path else "") + name)
            elif default is None:
                raise GameError("G1304", "%s: '%s' is missing (%s has no default for it)"
                                % (path or "the row", name, t), where)
    elif t == "int":
        if isinstance(value, bool) or not (isinstance(value, int) or isinstance(value, float) and value.is_integer()):
            wrong("a whole number")
    elif t == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            wrong("a number")
    elif t == "bool":
        if not isinstance(value, bool):
            wrong("true or false")
    elif t in ("str", "Sound"):
        if not isinstance(value, str):
            wrong("a text")
    elif t.startswith("list["):
        if not isinstance(value, list):
            wrong("a list")
        for i, x in enumerate(value):
            _check(x, t[5:-1], records, where, "%s[%d]" % (path, i))
    elif t.startswith("dict["):
        if not isinstance(value, dict):
            wrong("an object")
        for k, x in value.items():
            _check(x, t[5:-1], records, where, "%s.%s" % (path, k))
    else:
        raise GameError("G1303", "%s: a %s cannot come from JSON" % (path, t), where)


def _check_refs(value, t, records, tables, where, path):
    t = base(t)
    if value is None or t not in records:
        return
    r = records[t]
    for name, (ft, _, _) in r.fields.items():
        if name not in value:
            continue
        p = (path + "." if path else "") + name
        target = getattr(r, "refs", {}).get(name)
        if target is not None:
            if target not in tables:
                raise GameError("G1306", "%s.%s is a Ref[%s], but %s has no table" % (t, name, target, target), where,
                                fix="Add  ... = table(\"data/...\", %s)  in a game module." % target)
            path_of, ids = tables[target]
            items = value[name] if isinstance(value[name], list) else list(value[name].values()) \
                if isinstance(value[name], dict) else [value[name]]
            for i, x in enumerate(items):
                if x is not None and x not in ids:
                    hits = difflib.get_close_matches(str(x), list(ids), n=1)
                    raise GameError("G1307", "%s: \"%s\" is not in %s" % (p, x, path_of), where,
                                    fix=("Did you mean \"%s\"?" % hits[0]) if hits else "")
            continue
        sub = base(ft)
        if sub.startswith("list[") and base(sub[5:-1]) in records:
            for i, x in enumerate(value[name]):
                _check_refs(x, sub[5:-1], records, tables, where, "%s[%d]" % (p, i))
        elif sub.startswith("dict[") and base(sub[5:-1]) in records:
            for k, x in value[name].items():
                _check_refs(x, sub[5:-1], records, tables, where, "%s.%s" % (p, k))
        elif sub in records:
            _check_refs(value[name], sub, records, tables, where, p)


def ref_target(annotation):
    """Move for Ref[Move], list[Ref[Move]], Optional[Ref[Move]], dict[str, Ref[Move]]; else None."""
    import ast
    node = annotation
    while isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        name = node.value.id
        inside = subscript_slice(node)
        args = inside.elts if isinstance(inside, ast.Tuple) else [inside]
        if name == "Ref" and len(args) == 1 and isinstance(args[0], ast.Name):
            return args[0].id
        if name == "Ref" and len(args) == 1 and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
            return args[0].value                             # Ref["Species"]: the class being defined
        if name in ("list", "Optional") and len(args) == 1:
            node = args[0]
        elif name == "dict" and len(args) == 2:
            node = args[1]
        else:
            return None
    if isinstance(node, ast.BinOp):                         # Ref[Move] | None
        return ref_target(node.left) or ref_target(node.right)
    return None
