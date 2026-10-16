"""AST collection and Android code generation for ApkPy Data Core.

The compiler imports this module, but projects that never call ``db.model`` do
not receive any of the generated classes below.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re

from . import data_reactive


MODEL_METHODS = {"insert", "insert_many", "get", "find", "update", "delete", "count"}
OBSERVER_METHODS = {"refresh", "update_query", "close"}
COMMAND_TYPES = {
    "data_model", "data_transaction", "data_tx", "data_tx_assign",
    "data_observer",
}
FIELD_TYPES = {"integer", "real", "text", "boolean", "datetime", "json", "blob"}


def initialize(transpiler):
    transpiler.data_models = {}
    transpiler.data_relations = {}
    transpiler.data_observers = {}
    transpiler.data_migrations = {}
    transpiler.data_schema = None
    transpiler._data_command_count = 0
    # Numera as declaracoes escritas dentro do proprio db.schema().
    transpiler._data_inline_count = 0


def _kw_node(call, name):
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _literal(node, default=None):
    if node is None:
        return default
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return default


def _call_is(node, owner, name):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == owner
        and node.func.attr == name
    )


def _field_spec(node):
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "db"
        and node.func.attr in FIELD_TYPES
    ):
        raise ValueError("Data fields must use db.integer(), db.text(), and related factories")
    spec = {"kind": node.func.attr}
    for keyword in node.keywords:
        if keyword.arg == "default" and _call_is(keyword.value, "db", "now"):
            spec["default"] = {"factory": "now"}
        else:
            value = _literal(keyword.value, None)
            if keyword.arg == "choices" and value is not None:
                value = list(value)
            spec[keyword.arg] = value
    return spec


def _index_spec(node):
    if not _call_is(node, "db", "index"):
        raise ValueError("Indexes must use db.index()")
    name = _literal(node.args[0] if node.args else _kw_node(node, "name"), "")
    fields_node = node.args[1] if len(node.args) > 1 else _kw_node(node, "fields")
    fields = list(_literal(fields_node, []) or [])
    return {
        "name": str(name), "fields": fields,
        "unique": bool(_literal(_kw_node(node, "unique"), False)),
    }


def _declared_vars(transpiler, node, helper, argument):
    """The declarations listed in a db.schema() argument, by variable name.

    ``models=[notes]`` points at a declaration made further up. ``models=[
    db.model(...)]`` makes it right there -- ordinary Python, and what the
    Previewer accepts. This used to collect names and nothing else, so an
    inline call was dropped without a word: the table was never created, the
    foreign key never written, the migration never generated, and the app
    worked at the desk and not on the phone.

    Written inline it is now read on the spot, by the same parser the
    assignment path uses, under a name nobody can reference. Anything that is
    neither a name nor a ``db.<helper>()`` call stops the build, because the
    one thing it must never do again is disappear.
    """
    names = []
    for item in getattr(node, "elts", []):
        if isinstance(item, ast.Name):
            names.append(item.id)
            continue
        if _call_is(item, "db", helper):
            transpiler._data_inline_count += 1
            var_name = "_apkpy_inline_%s_%d" % (helper,
                                                transpiler._data_inline_count)
            parse_assignment(transpiler, var_name, item)
            names.append(var_name)
            continue
        raise ValueError(
            "db.schema(%s=[...]) takes a db.%s() call or the name of one, "
            "and one entry is neither" % (argument, helper))
    return names


def parse_assignment(transpiler, var_name, call):
    """Collect a top-level model/migration/schema declaration."""
    if _call_is(call, "db", "model"):
        name = _literal(call.args[0] if call.args else _kw_node(call, "name"), var_name)
        fields_node = _kw_node(call, "fields")
        if fields_node is None and len(call.args) > 1:
            fields_node = call.args[1]
        if not isinstance(fields_node, ast.Dict):
            raise ValueError(f"db.model('{name}') requires a literal fields dictionary")
        fields = {}
        for key, value in zip(fields_node.keys, fields_node.values):
            field_name = _literal(key)
            if not isinstance(field_name, str):
                raise ValueError(f"Model '{name}' contains a non-string field name")
            fields[field_name] = _field_spec(value)
        indexes_node = _kw_node(call, "indexes")
        indexes = []
        if isinstance(indexes_node, (ast.List, ast.Tuple)):
            indexes = [_index_spec(item) for item in indexes_node.elts]
        transpiler.data_models[var_name] = {
            "var": var_name, "name": str(name), "fields": fields, "indexes": indexes,
            # Kept so a later generation failure can point at this declaration
            # in writehere.py instead of at ApkPy's own source.
            "line": int(getattr(call, "lineno", 0) or 0),
        }
        return True

    if _call_is(call, "db", "relation"):
        name = _literal(call.args[0] if call.args else _kw_node(call, "name"), var_name)
        parent_node = call.args[1] if len(call.args) > 1 else _kw_node(call, "parent")
        child_node = call.args[2] if len(call.args) > 2 else _kw_node(call, "child")
        foreign_node = call.args[3] if len(call.args) > 3 else _kw_node(call, "foreign_key")
        parent_as_node = call.args[4] if len(call.args) > 4 else _kw_node(call, "parent_as")
        children_as_node = call.args[5] if len(call.args) > 5 else _kw_node(call, "children_as")
        parent_var = _model_var(parent_node)
        child_var = _model_var(child_node)
        if parent_var not in transpiler.data_models or child_var not in transpiler.data_models:
            raise ValueError(f"db.relation('{name}') requires declared parent and child models")
        if parent_var == child_var:
            raise ValueError(
                f"db.relation('{name}') cannot relate a model to itself in ApkPy 1.3.1"
            )
        parent_model = transpiler.data_models[parent_var]
        child_model = transpiler.data_models[child_var]
        foreign_key = str(_literal(foreign_node, ""))
        parent_keys = [
            field_name for field_name, spec in parent_model["fields"].items()
            if spec.get("primary_key")
        ]
        if len(parent_keys) != 1:
            raise ValueError(
                f"db.relation('{name}') parent model must have one primary key"
            )
        if foreign_key not in child_model["fields"]:
            raise ValueError(
                f"db.relation('{name}') foreign key '{foreign_key}' does not exist"
            )
        if child_model["fields"][foreign_key]["kind"] != parent_model["fields"][parent_keys[0]]["kind"]:
            raise ValueError(
                f"db.relation('{name}') primary and foreign key types do not match"
            )
        parent_as = str(_literal(parent_as_node, ""))
        children_as = str(_literal(children_as_node, ""))
        if not parent_as or not children_as or parent_as == children_as:
            raise ValueError(
                f"db.relation('{name}') requires distinct parent_as and children_as aliases"
            )
        on_delete = str(_literal(_kw_node(call, "on_delete"), "restrict")).lower()
        if on_delete not in {"restrict", "cascade", "set_null"}:
            raise ValueError(
                "db.relation() on_delete must be restrict, cascade, or set_null"
            )
        if on_delete == "set_null" and not child_model["fields"][foreign_key].get("optional"):
            raise ValueError(
                f"db.relation('{name}') set_null requires an optional foreign key"
            )
        for existing in transpiler.data_relations.values():
            if existing["name"] == str(name):
                raise ValueError(f"Duplicate relation name '{name}'")
            if parent_as in (existing["parent_as"], existing["children_as"]) or children_as in (
                existing["parent_as"], existing["children_as"],
            ):
                raise ValueError("Relation aliases must be unique")
        relation = {
            "var": var_name, "name": str(name),
            "parent_var": parent_var, "child_var": child_var,
            "parent": transpiler.data_models[parent_var]["name"],
            "child": transpiler.data_models[child_var]["name"],
            "foreign_key": foreign_key,
            "parent_as": parent_as,
            "children_as": children_as,
            "on_delete": on_delete,
        }
        transpiler.data_relations[var_name] = relation
        return True

    if _call_is(call, "db", "migration"):
        from_node = _kw_node(call, "from_version")
        to_node = _kw_node(call, "to_version")
        if from_node is None and call.args:
            from_node = call.args[0]
        if to_node is None and len(call.args) > 1:
            to_node = call.args[1]
        operations_node = _kw_node(call, "operations")
        if operations_node is None and len(call.args) > 2:
            operations_node = call.args[2]
        operations = []
        if isinstance(operations_node, (ast.List, ast.Tuple)):
            operations = [_migration_operation(transpiler, item) for item in operations_node.elts]
        transpiler.data_migrations[var_name] = {
            "var": var_name,
            "from": int(_literal(from_node, 0)),
            "to": int(_literal(to_node, 0)),
            "operations": operations,
            "destructive": bool(_literal(_kw_node(call, "destructive"), False)),
        }
        return True

    if _call_is(call, "db", "schema"):
        name = _literal(call.args[0] if call.args else _kw_node(call, "name"), "apkpy_app")
        version_node = _kw_node(call, "version")
        if version_node is None and len(call.args) > 1:
            version_node = call.args[1]
        models_node = _kw_node(call, "models")
        if models_node is None and len(call.args) > 2:
            models_node = call.args[2]
        migrations_node = _kw_node(call, "migrations")
        relations_node = _kw_node(call, "relations")
        database_name = _literal(_kw_node(call, "database_name"), "apkpy_app.db")
        database_name = str(database_name or "apkpy_app.db")
        if not database_name.endswith(".db"):
            database_name += ".db"
        # Os modelos primeiro: uma relacao e uma migracao referem-nos.
        model_vars = _declared_vars(transpiler, models_node, "model", "models")
        migration_vars = _declared_vars(transpiler, migrations_node, "migration",
                                        "migrations")
        relation_vars = _declared_vars(transpiler, relations_node, "relation",
                                       "relations")
        schema = {
            "var": var_name, "name": str(name),
            "version": int(_literal(version_node, 1)),
            "model_vars": model_vars, "migration_vars": migration_vars,
            "relation_vars": relation_vars,
            "database_name": database_name,
        }
        schema["models"] = [transpiler.data_models[item] for item in model_vars if item in transpiler.data_models]
        schema["migrations"] = [transpiler.data_migrations[item] for item in migration_vars if item in transpiler.data_migrations]
        schema["relations"] = [transpiler.data_relations[item] for item in relation_vars if item in transpiler.data_relations]
        selected_models = {item["name"] for item in schema["models"]}
        for relation in schema["relations"]:
            if relation["parent"] not in selected_models or relation["child"] not in selected_models:
                raise ValueError(
                    f"Relation '{relation['name']}' references a model outside this schema"
                )
        payload = {
            "name": schema["name"], "models": schema["models"],
            "relations": schema["relations"],
        }
        schema["hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        ).hexdigest()
        transpiler.data_schema = schema
        return True

    func = call.func
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in transpiler.data_models
        and func.attr == "observe"
    ):
        screen_node = _kw_node(call, "screen")
        screen_var = screen_node.id if isinstance(screen_node, ast.Name) else None
        screen_id = transpiler.screens.get(screen_var) if screen_var else None
        if not screen_id:
            raise ValueError("model.observe(screen=...) requires a declared Screen")
        observer = {
            "var": var_name, "model_var": func.value.id,
            "model": transpiler.data_models[func.value.id]["name"],
            "screen_id": screen_id,
            "filters_node": _resolve_assignment(transpiler, _kw_node(call, "filters")),
            "order_node": _resolve_assignment(transpiler, _kw_node(call, "order_by")),
            "include_node": _resolve_assignment(transpiler, _kw_node(call, "include")),
            "limit_node": _kw_node(call, "limit"),
            "offset_node": _kw_node(call, "offset"),
            "on_change": _callback(transpiler, _kw_node(call, "on_change"), f"data_observe_{var_name}"),
            "on_error": _callback(transpiler, _kw_node(call, "on_error"), f"data_observe_error_{var_name}"),
        }
        if not observer["on_change"]:
            raise ValueError("model.observe(on_change=...) requires a callback")
        transpiler.json_item_callbacks.add(observer["on_change"])
        transpiler.data_observers[var_name] = observer
        return True
    return False


def _model_var(node):
    return node.id if isinstance(node, ast.Name) else None


def _migration_operation(transpiler, node):
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "db"
    ):
        raise ValueError("Invalid Data Core migration operation")
    kind = node.func.attr
    model_var = _model_var(node.args[0]) if node.args else _model_var(_kw_node(node, "model"))
    model_name = transpiler.data_models.get(model_var, {}).get("name", model_var)
    result = {"operation": kind, "model": model_name}
    if kind == "create_table":
        return result
    if kind == "add_column":
        result["name"] = _literal(node.args[1] if len(node.args) > 1 else _kw_node(node, "name"))
        definition = node.args[2] if len(node.args) > 2 else _kw_node(node, "definition")
        result["field"] = _field_spec(definition)
    elif kind in ("rename_column", "rename_index"):
        result["name"] = _literal(node.args[1] if len(node.args) > 1 else _kw_node(node, "name"))
        result["new_name"] = _literal(node.args[2] if len(node.args) > 2 else _kw_node(node, "new_name"))
    elif kind == "create_index":
        result["name"] = _literal(node.args[1] if len(node.args) > 1 else _kw_node(node, "name"))
        fields_node = node.args[2] if len(node.args) > 2 else _kw_node(node, "fields")
        result["fields"] = list(_literal(fields_node, []) or [])
        result["unique"] = bool(_literal(_kw_node(node, "unique"), False))
    elif kind == "drop_index":
        result["name"] = _literal(node.args[1] if len(node.args) > 1 else _kw_node(node, "name"))
        result["destructive"] = bool(_literal(_kw_node(node, "destructive"), True))
    elif kind == "rename_table":
        result["new_name"] = _literal(node.args[1] if len(node.args) > 1 else _kw_node(node, "new_name"))
    elif kind == "sql":
        query_node = node.args[0] if node.args else _kw_node(node, "query")
        params_node = node.args[1] if len(node.args) > 1 else _kw_node(node, "params")
        result = {
            "operation": "sql", "query": _literal(query_node, ""),
            "params": list(_literal(params_node, []) or []),
            "destructive": bool(_literal(_kw_node(node, "destructive"), False)),
        }
    else:
        raise ValueError(f"Unsupported migration operation db.{kind}()")
    return result


def parse_model_command(transpiler, call):
    func = call.func
    if not (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in transpiler.data_models
        and func.attr in MODEL_METHODS
    ):
        return None
    transpiler._data_command_count += 1
    seq = transpiler._data_command_count
    method = func.attr
    command = {
        "type": "data_model", "seq": seq, "method": method,
        "model_var": func.value.id,
        "model": transpiler.data_models[func.value.id]["name"],
    }
    positional = list(call.args)
    if method in ("insert", "insert_many", "update"):
        command["values_node"] = positional[0] if positional else _kw_node(call, "values")
    if method == "get":
        command["id_node"] = positional[0] if positional else _kw_node(call, "item_id")
    if method in ("find", "update", "delete", "count"):
        command["filters_node"] = _kw_node(call, "filters")
    if method == "find":
        command["order_node"] = _kw_node(call, "order_by")
        command["limit_node"] = _kw_node(call, "limit")
        command["offset_node"] = _kw_node(call, "offset")
    if method in ("find", "get"):
        command["include_node"] = _resolve_assignment(
            transpiler, _kw_node(call, "include"),
        )
    command["on_result"] = _callback(transpiler, _kw_node(call, "on_result"), f"data_{method}_{seq}")
    command["on_error"] = _callback(transpiler, _kw_node(call, "on_error"), f"data_error_{seq}")
    for key in ("values_node", "filters_node", "order_node", "include_node"):
        if key in command:
            command[key] = _resolve_assignment(transpiler, command[key])
    if method in ("find", "get") and command["on_result"]:
        transpiler.json_item_callbacks.add(command["on_result"])
    return command


def is_command_call(transpiler, call):
    func = getattr(call, "func", None)
    return bool(
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and (
            (func.value.id in transpiler.data_models and func.attr in MODEL_METHODS)
            or (func.value.id in transpiler.data_observers and func.attr in OBSERVER_METHODS)
            or (func.value.id == "db" and func.attr == "transaction")
        )
    )


def parse_observer_command(transpiler, call):
    func = getattr(call, "func", None)
    if not (
        isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
        and func.value.id in transpiler.data_observers
        and func.attr in OBSERVER_METHODS
    ):
        return None
    transpiler._data_command_count += 1
    command = {
        "type": "data_observer", "seq": transpiler._data_command_count,
        "observer": func.value.id, "method": func.attr,
    }
    if func.attr == "update_query":
        for public, internal in (
            ("filters", "filters_node"), ("order_by", "order_node"),
            ("include", "include_node"), ("limit", "limit_node"),
            ("offset", "offset_node"),
        ):
            node = _kw_node(call, public)
            if node is not None:
                command[internal] = _resolve_assignment(transpiler, node)
    return command


def _callback(transpiler, node, tag):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Lambda):
        return transpiler._register_result_callback(node, False, tag)
    return None


def _resolve_assignment(transpiler, node):
    """Inline literal module assignments used by generated data commands."""
    if isinstance(node, ast.Name):
        if node.id in getattr(transpiler, "list_assignments", {}):
            return transpiler.list_assignments[node.id]
        if node.id in getattr(transpiler, "dict_assignments", {}):
            return transpiler.dict_assignments[node.id]
    return node


def parse_transaction_command(transpiler, call):
    if not _call_is(call, "db", "transaction"):
        return None
    run_node = _kw_node(call, "run")
    if run_node is None and call.args:
        run_node = call.args[0]
    transpiler._data_command_count += 1
    seq = transpiler._data_command_count
    run_name = run_node.id if isinstance(run_node, ast.Name) else None
    if run_name and run_name in transpiler.functions:
        transpiler.functions[run_name]["data_transaction"] = True
    return {
        "type": "data_transaction", "seq": seq,
        "run": run_name,
        "on_result": _callback(transpiler, _kw_node(call, "on_result"), f"data_tx_{seq}"),
        "on_error": _callback(transpiler, _kw_node(call, "on_error"), f"data_tx_error_{seq}"),
    }


def parse_tx_command(transpiler, call, assign_to=None):
    func = call.func
    if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)):
        return None
    if func.attr not in MODEL_METHODS:
        return None
    args = list(call.args)
    if not args or not isinstance(args[0], ast.Name) or args[0].id not in transpiler.data_models:
        return None
    method = func.attr
    model_var = args[0].id
    transpiler._data_command_count += 1
    command = {
        "type": "data_tx_assign" if assign_to else "data_tx",
        "seq": transpiler._data_command_count,
        "assign_to": assign_to, "tx_var": func.value.id,
        "method": method, "model": transpiler.data_models[model_var]["name"],
    }
    if method in ("insert", "insert_many", "update"):
        command["values_node"] = args[1] if len(args) > 1 else _kw_node(call, "values")
    if method == "get":
        command["id_node"] = args[1] if len(args) > 1 else _kw_node(call, "item_id")
    if method in ("find", "update", "delete", "count"):
        command["filters_node"] = _kw_node(call, "filters")
    if method == "find":
        command["order_node"] = _kw_node(call, "order_by")
        command["limit_node"] = _kw_node(call, "limit")
        command["offset_node"] = _kw_node(call, "offset")
    for key in ("values_node", "filters_node", "order_node"):
        if key in command:
            command[key] = _resolve_assignment(transpiler, command[key])
    return command


def repository_class(model_name):
    pieces = re.split(r"[^A-Za-z0-9]+", str(model_name))
    return "".join(piece[:1].upper() + piece[1:] for piece in pieces if piece) + "Repository"


def generate_files(schema, package, observers=None):
    if not schema or not schema.get("models"):
        return {}
    files = {
        "java/ApkpyDataExecutor.java": _generate_executor(package),
        "java/ApkpyDatabase.java": _generate_database(
            schema, package, reactive=bool(observers),
        ),
    }
    for model in schema["models"]:
        files[f"java/{repository_class(model['name'])}.java"] = _generate_repository(
            model, package, reactive=bool(observers),
        )
    if observers:
        files.update(data_reactive.generate_files(package))
    return files


def _j(value):
    return json.dumps(str(value), ensure_ascii=False)


def _java_string(value):
    return json.dumps(str(value), ensure_ascii=False).replace("</", "<\\/")


def _sql_literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _column_sql(name, spec, primary=True):
    sql_types = {
        "integer": "INTEGER", "real": "REAL", "text": "TEXT",
        "boolean": "INTEGER", "datetime": "INTEGER", "json": "TEXT", "blob": "BLOB",
    }
    result = f'"{name}" {sql_types[spec["kind"]]}'
    if primary and spec.get("primary_key"):
        result += " PRIMARY KEY"
        if spec.get("auto_increment"):
            result += " AUTOINCREMENT"
    if spec.get("required"):
        result += " NOT NULL"
    if spec.get("unique"):
        result += " UNIQUE"
    if "default" in spec:
        default = spec["default"]
        if isinstance(default, dict) and default.get("factory") == "now":
            default = 0
        if spec["kind"] == "boolean":
            default = 1 if default else 0
        if spec["kind"] == "json" and not isinstance(default, str):
            default = json.dumps(default, separators=(",", ":"))
        result += " DEFAULT " + _sql_literal(default)
    checks = []
    if spec.get("min_value") is not None:
        checks.append(f'"{name}" >= {spec["min_value"]}')
    if spec.get("max_value") is not None:
        checks.append(f'"{name}" <= {spec["max_value"]}')
    if spec.get("max_length") is not None:
        checks.append(f'length("{name}") <= {int(spec["max_length"])}')
    if spec.get("choices"):
        choices = ", ".join(_sql_literal(item) for item in spec["choices"])
        checks.append(f'"{name}" IN ({choices})')
    if checks:
        result += " CHECK (" + " AND ".join(checks) + ")"
    return result


def _create_table_sql(model, schema=None):
    parts = [_column_sql(name, spec) for name, spec in model["fields"].items()]
    for relation in (schema or {}).get("relations", []):
        if relation.get("child") != model["name"]:
            continue
        parent = next(
            item for item in schema["models"]
            if item["name"] == relation["parent"]
        )
        parent_key = next(
            name for name, spec in parent["fields"].items()
            if spec.get("primary_key")
        )
        action = {
            "restrict": "RESTRICT", "cascade": "CASCADE",
            "set_null": "SET NULL",
        }[relation.get("on_delete", "restrict")]
        parts.append(
            f'FOREIGN KEY ("{relation["foreign_key"]}") REFERENCES '
            f'"{relation["parent"]}" ("{parent_key}") ON DELETE {action}'
        )
    columns = ", ".join(parts)
    return f'CREATE TABLE IF NOT EXISTS "{model["name"]}" ({columns})'


def _create_index_sql(table, index):
    unique = "UNIQUE " if index.get("unique") else ""
    fields = ", ".join(f'"{item}"' for item in index["fields"])
    return f'CREATE {unique}INDEX IF NOT EXISTS "{index["name"]}" ON "{table}" ({fields})'


def _generate_executor(package):
    return f'''package {package};

import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class ApkpyDataExecutor {{
    public interface Task {{ String run() throws Exception; }}
    public interface Callback {{ void onResult(String result); void onError(String error); }}
    private static final ExecutorService EXECUTOR = Executors.newSingleThreadExecutor(r -> {{
        Thread thread = new Thread(r, "apkpy-data");
        thread.setDaemon(false);
        return thread;
    }});
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private ApkpyDataExecutor() {{}}

    public static void submit(Task task, Callback callback) {{
        EXECUTOR.execute(() -> {{
            try {{
                String value = task.run();
                if (callback != null) MAIN.post(() -> callback.onResult(value == null ? "" : value));
            }} catch (Exception error) {{
                String message = error.getMessage() == null ? error.toString() : error.getMessage();
                if (callback != null) MAIN.post(() -> callback.onError(message));
                else Log.e("ApkpyData", message, error);
            }}
        }});
    }}

    // A background job's Worker is already off the main thread, and its next
    // line must see the answer -- the order the Previewer keeps inside a job.
    // The callback runs outside the try, so an error in it is not reported as
    // a failed query.
    public static void runHere(Task task, Callback callback) {{
        String value;
        try {{
            value = task.run();
        }} catch (Exception error) {{
            String message = error.getMessage() == null ? error.toString() : error.getMessage();
            if (callback != null) callback.onError(message);
            else Log.e("ApkpyData", message, error);
            return;
        }}
        if (callback != null) callback.onResult(value == null ? "" : value);
    }}
}}
'''


def _field_config_java(name, spec):
    default_kind = "missing"
    default_value = "null"
    if "default" in spec:
        default = spec["default"]
        if isinstance(default, dict) and default.get("factory") == "now":
            default_kind = "now"
        else:
            default_kind = "value"
            if default is None:
                default_value = "JSONObject.NULL"
            elif isinstance(default, bool):
                default_value = "true" if default else "false"
            elif isinstance(default, (int, float)):
                default_value = str(default)
            elif isinstance(default, dict):
                default_value = f"parseObject({_java_string(json.dumps(default, ensure_ascii=False))})"
            elif isinstance(default, (list, tuple)):
                default_value = f"parseArray({_java_string(json.dumps(default, ensure_ascii=False))})"
            else:
                default_value = _java_string(default)
    choices = spec.get("choices")
    # parseArray, not new JSONArray: the JSONArray(String) constructor throws
    # the checked JSONException, which this initialiser neither catches nor
    # declares, so any field with choices= produced Java that did not compile.
    # The list/dict defaults above already go through the same helper.
    choices_java = (
        "null" if not choices
        else f"parseArray({_java_string(json.dumps(choices, ensure_ascii=False))})"
    )
    return (
        f'fields.put({_j(name)}, new Field({_j(name)}, {_j(spec["kind"])}, '
        f'{str(bool(spec.get("required"))).lower()}, {str(bool(spec.get("primary_key"))).lower()}, '
        f'{str(bool(spec.get("auto_increment"))).lower()}, {_j(default_kind)}, {default_value}, '
        f'{"null" if spec.get("min_value") is None else str(float(spec["min_value"]))}, '
        f'{"null" if spec.get("max_value") is None else str(float(spec["max_value"]))}, '
        f'{"null" if spec.get("max_length") is None else str(int(spec["max_length"]))}, {choices_java}));'
    )


def _generate_database(schema, package, reactive=False):
    has_relations = bool(schema.get("relations"))
    model_init = []
    create_lines = []
    for model in schema["models"]:
        model_init.append("        {")
        model_init.append("            LinkedHashMap<String, Field> fields = new LinkedHashMap<>();")
        for name, spec in model["fields"].items():
            model_init.append("            " + _field_config_java(name, spec))
        primary = next((name for name, spec in model["fields"].items() if spec.get("primary_key")), "")
        projection = ", ".join(_j(name) for name in model["fields"])
        model_init.append(
            f'            models.put({_j(model["name"])}, new Model({_j(model["name"])}, {_j(primary)}, fields, new String[]{{{projection}}}));'
        )
        model_init.append("        }")
        create_lines.append(f'        db.execSQL({_java_string(_create_table_sql(model, schema))});')
        for index in model.get("indexes", []):
            create_lines.append(f'        db.execSQL({_java_string(_create_index_sql(model["name"], index))});')

    relation_init = []
    for relation in schema.get("relations", []):
        relation_init.append(
            "        relations.add(new Relation("
            + ",".join(_j(relation[key]) for key in (
                "name", "parent", "child", "foreign_key",
                "parent_as", "children_as", "on_delete",
            ))
            + "));"
        )

    migration_switch = []
    destructive_versions = []
    migrations = {item["from"]: item for item in schema.get("migrations", [])}
    for version in range(1, int(schema["version"])):
        migration = migrations.get(version)
        if migration and migration.get("destructive"):
            destructive_versions.append(version)
        migration_switch.append(f"            case {version}:")
        if migration:
            for operation in migration.get("operations", []):
                migration_switch.extend(_migration_java(operation, schema))
        else:
            migration_switch.append(
                f'                throw new IllegalStateException("Missing migration {version} -> {version + 1}");'
            )
        migration_switch.append("                version++;")
        migration_switch.append("                break;")
    destructive_test = " || ".join(f"oldVersion == {item}" for item in destructive_versions) or "false"
    transaction_invalidation = (
        "if(success&&!changed.isEmpty())ApkpyDataInvalidationTracker.invalidate(expandInvalidations(changed));"
        if reactive else ""
    )
    reactive_imports = "import java.util.HashSet;\nimport java.util.Set;" if reactive else ""
    relation_field = "    private final List<Relation> relations = new ArrayList<>();" if has_relations else ""
    relation_class = '''
    static final class Relation {
        final String name,parent,child,foreignKey,parentAs,childrenAs,onDelete;
        Relation(String name,String parent,String child,String foreignKey,
                String parentAs,String childrenAs,String onDelete) {
            this.name=name;this.parent=parent;this.child=child;
            this.foreignKey=foreignKey;this.parentAs=parentAs;
            this.childrenAs=childrenAs;this.onDelete=onDelete;
        }
    }''' if has_relations else ""
    if reactive:
        transaction_fields = "        private final Set<String> changed = new HashSet<>();"
        transaction_methods = '''
        public long insert(String model, JSONObject values) throws Exception { long id=owner.insertSync(db, model, values);changed.add(model);return id; }
        public int insertMany(String model, JSONArray values) throws Exception { int count=owner.insertManySync(db, model, values);if(count>0)changed.add(model);return count; }
        public String get(String model, Object id) throws Exception { return owner.getSync(db, model, id); }
        public String find(String model, JSONArray filters, JSONArray order, Integer limit, int offset) throws Exception { return owner.findSync(db, model, filters, order, limit, offset); }
        public int update(String model, JSONObject values, JSONArray filters) throws Exception { int count=owner.updateSync(db, model, values, filters);if(count>0)changed.add(model);return count; }
        public int delete(String model, JSONArray filters) throws Exception { int count=owner.deleteSync(db, model, filters);if(count>0)changed.add(model);return count; }
        public int count(String model, JSONArray filters) throws Exception { return owner.countSync(db, model, filters); }'''
        transaction_task = f'''return()->{{SQLiteDatabase db=getWritableDatabase();db.beginTransaction();Transaction tx=new Transaction(this,db);boolean success=false;try{{String result=work.run(tx);db.setTransactionSuccessful();success=true;return result;}}finally{{Set<String>changed=new HashSet<>(tx.changed);db.endTransaction();{transaction_invalidation}}}}};'''
    else:
        transaction_fields = ""
        transaction_methods = '''
        public long insert(String model, JSONObject values) throws Exception { return owner.insertSync(db, model, values); }
        public int insertMany(String model, JSONArray values) throws Exception { return owner.insertManySync(db, model, values); }
        public String get(String model, Object id) throws Exception { return owner.getSync(db, model, id); }
        public String find(String model, JSONArray filters, JSONArray order, Integer limit, int offset) throws Exception { return owner.findSync(db, model, filters, order, limit, offset); }
        public int update(String model, JSONObject values, JSONArray filters) throws Exception { return owner.updateSync(db, model, values, filters); }
        public int delete(String model, JSONArray filters) throws Exception { return owner.deleteSync(db, model, filters); }
        public int count(String model, JSONArray filters) throws Exception { return owner.countSync(db, model, filters); }'''
        transaction_task = '''return()->{SQLiteDatabase db=getWritableDatabase();db.beginTransaction();try{String result=work.run(new Transaction(this,db));db.setTransactionSuccessful();return result;}finally{db.endTransaction();}};'''

    flat_read_methods = '''
    String getSync(SQLiteDatabase db,String modelName,Object id)throws Exception{Model m=model(modelName);if(m.primaryKey.isEmpty())throw new IllegalArgumentException("Model has no primary key");try(Cursor c=db.query(m.table,m.projection,"\\\""+m.primaryKey+"\\\" = ?",new String[]{String.valueOf(id)},null,null,null,"1")){return c.moveToFirst()?rowJson(c,m).toString():"";}}
    String getSync(String modelName,Object id)throws Exception{return getSync(getReadableDatabase(),modelName,id);}
    String getSync(SQLiteDatabase db,String modelName,Object id,JSONArray include)throws Exception{if(include!=null&&include.length()>0)throw new IllegalArgumentException("Model '"+modelName+"' has no declared relations");return getSync(db,modelName,id);}
    String getSync(String modelName,Object id,JSONArray include)throws Exception{return getSync(getReadableDatabase(),modelName,id,include);}
    String findSync(SQLiteDatabase db,String modelName,JSONArray filters,JSONArray order,Integer limit,int offset)throws Exception{Model m=model(modelName);Selection s=selection(m,filters);String orderSql=order(m,order);String lim=limit==null?null:String.valueOf(limit)+" OFFSET "+Math.max(0,offset);JSONArray rows=new JSONArray();try(Cursor c=db.query(m.table,m.projection,s.sql,s.args,null,null,orderSql,lim)){while(c.moveToNext())rows.put(rowJson(c,m));}return rows.toString();}
    String findSync(String modelName,JSONArray filters,JSONArray order,Integer limit,int offset)throws Exception{return findSync(getReadableDatabase(),modelName,filters,order,limit,offset);}
    String findSync(SQLiteDatabase db,String modelName,JSONArray filters,JSONArray order,Integer limit,int offset,JSONArray include)throws Exception{if(include!=null&&include.length()>0)throw new IllegalArgumentException("Model '"+modelName+"' has no declared relations");return findSync(db,modelName,filters,order,limit,offset);}
    String findSync(String modelName,JSONArray filters,JSONArray order,Integer limit,int offset,JSONArray include)throws Exception{return findSync(getReadableDatabase(),modelName,filters,order,limit,offset,include);}'''
    relation_read_methods = '''
    String getSync(SQLiteDatabase db,String modelName,Object id)throws Exception{return getSync(db,modelName,id,new JSONArray());}
    String getSync(SQLiteDatabase db,String modelName,Object id,JSONArray include)throws Exception{Model m=model(modelName);if(m.primaryKey.isEmpty())throw new IllegalArgumentException("Model has no primary key");try(Cursor c=db.query(m.table,m.projection,"\\\""+m.primaryKey+"\\\" = ?",new String[]{String.valueOf(id)},null,null,null,"1")){if(!c.moveToFirst())return "";JSONObject row=rowJson(c,m);JSONArray roots=new JSONArray();roots.put(row);hydrate(db,m,roots,include);return row.toString();}}
    String getSync(String modelName,Object id)throws Exception{return getSync(getReadableDatabase(),modelName,id,new JSONArray());}
    String getSync(String modelName,Object id,JSONArray include)throws Exception{return getSync(getReadableDatabase(),modelName,id,include);}
    String findSync(SQLiteDatabase db,String modelName,JSONArray filters,JSONArray order,Integer limit,int offset)throws Exception{return findSync(db,modelName,filters,order,limit,offset,new JSONArray());}
    String findSync(SQLiteDatabase db,String modelName,JSONArray filters,JSONArray order,Integer limit,int offset,JSONArray include)throws Exception{Model m=model(modelName);Selection s=selection(m,filters);String orderSql=order(m,order);String lim=limit==null?null:String.valueOf(limit)+" OFFSET "+Math.max(0,offset);JSONArray rows=new JSONArray();try(Cursor c=db.query(m.table,m.projection,s.sql,s.args,null,null,orderSql,lim)){while(c.moveToNext())rows.put(rowJson(c,m));}hydrate(db,m,rows,include);return rows.toString();}
    String findSync(String modelName,JSONArray filters,JSONArray order,Integer limit,int offset)throws Exception{return findSync(getReadableDatabase(),modelName,filters,order,limit,offset,new JSONArray());}
    String findSync(String modelName,JSONArray filters,JSONArray order,Integer limit,int offset,JSONArray include)throws Exception{return findSync(getReadableDatabase(),modelName,filters,order,limit,offset,include);}
    private Relation relation(String modelName,String alias){if(alias.contains("."))throw new IllegalArgumentException("Nested includes are not supported: "+alias);for(Relation relation:relations){if(relation.parent.equals(modelName)&&relation.childrenAs.equals(alias))return relation;if(relation.child.equals(modelName)&&relation.parentAs.equals(alias))return relation;}throw new IllegalArgumentException("Unknown include '"+alias+"' for model '"+modelName+"'");}
    private void hydrate(SQLiteDatabase db,Model rootModel,JSONArray roots,JSONArray include)throws Exception{
        if(include==null||include.length()==0||roots.length()==0)return;
        for(int includeIndex=0;includeIndex<include.length();includeIndex++){
            String alias=include.getString(includeIndex);Relation relation=relation(rootModel.table,alias);
            if(relation.parent.equals(rootModel.table))hydrateChildren(db,rootModel,roots,relation,alias);
            else hydrateParent(db,rootModel,roots,relation,alias);
        }
    }
    private void hydrateChildren(SQLiteDatabase db,Model parentModel,JSONArray roots,Relation relation,String alias)throws Exception{
        Model child=model(relation.child);LinkedHashMap<String,JSONArray> groups=new LinkedHashMap<>();List<String>values=new ArrayList<>();
        for(int i=0;i<roots.length();i++){JSONObject root=roots.getJSONObject(i);String key=jsonKey(root.opt(parentModel.primaryKey));JSONArray children=new JSONArray();root.put(alias,children);groups.put(key,children);if(!values.contains(key))values.add(key);}
        queryRelated(db,child,relation.foreignKey,values,child.primaryKey,row->{JSONArray group=groups.get(jsonKey(row.opt(relation.foreignKey)));if(group!=null)group.put(row);});
    }
    private void hydrateParent(SQLiteDatabase db,Model childModel,JSONArray roots,Relation relation,String alias)throws Exception{
        Model parent=model(relation.parent);LinkedHashMap<String,JSONObject>parents=new LinkedHashMap<>();List<String>values=new ArrayList<>();
        for(int i=0;i<roots.length();i++){Object value=roots.getJSONObject(i).opt(relation.foreignKey);if(value!=null&&value!=JSONObject.NULL){String key=jsonKey(value);if(!values.contains(key))values.add(key);}}
        queryRelated(db,parent,parent.primaryKey,values,parent.primaryKey,row->parents.put(jsonKey(row.opt(parent.primaryKey)),row));
        for(int i=0;i<roots.length();i++){JSONObject root=roots.getJSONObject(i);JSONObject value=parents.get(jsonKey(root.opt(relation.foreignKey)));root.put(alias,value==null?JSONObject.NULL:value);}
    }
    private interface RelatedRow{void accept(JSONObject row)throws Exception;}
    private void queryRelated(SQLiteDatabase db,Model target,String field,List<String>values,String orderField,RelatedRow receiver)throws Exception{
        for(int start=0;start<values.size();start+=900){int end=Math.min(values.size(),start+900);StringBuilder marks=new StringBuilder();String[]args=new String[end-start];for(int i=start;i<end;i++){if(marks.length()>0)marks.append(',');marks.append('?');args[i-start]=values.get(i);}try(Cursor cursor=db.query(target.table,target.projection,"\\\""+field+"\\\" IN ("+marks+")",args,null,null,"\\\""+orderField+"\\\" ASC")){while(cursor.moveToNext())receiver.accept(rowJson(cursor,target));}}
    }
    private String jsonKey(Object value){return value==null||value==JSONObject.NULL?"<null>":String.valueOf(value);}'''
    read_methods = relation_read_methods if has_relations else flat_read_methods
    if reactive:
        if has_relations:
            reactive_helpers = '''
    Set<String> queryDependencies(String modelName,JSONArray include){Model m=model(modelName);Set<String> result=new HashSet<>();result.add(m.table);if(include==null)return result;for(int i=0;i<include.length();i++){String alias=include.optString(i,"");Relation relation=relation(m.table,alias);result.add(relation.parent);result.add(relation.child);}return result;}
    Set<String> expandInvalidations(Set<String> changed){Set<String> result=new HashSet<>(changed);boolean added=true;while(added){added=false;for(Relation relation:relations)if(result.contains(relation.parent)&&!"restrict".equals(relation.onDelete)&&result.add(relation.child))added=true;}return result;}'''
        else:
            reactive_helpers = '''
    Set<String> queryDependencies(String modelName,JSONArray include){model(modelName);if(include!=null&&include.length()>0)throw new IllegalArgumentException("Model '"+modelName+"' has no declared relations");Set<String> result=new HashSet<>();result.add(modelName);return result;}
    Set<String> expandInvalidations(Set<String> changed){return new HashSet<>(changed);}'''
    else:
        reactive_helpers = ""

    return f'''package {package};

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import android.database.sqlite.SQLiteStatement;
import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONTokener;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.channels.FileChannel;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
{reactive_imports}

public final class ApkpyDatabase extends SQLiteOpenHelper {{
    private static final String DATABASE_NAME = {_j(schema.get("database_name", "apkpy_app.db"))};
    private static final int SCHEMA_VERSION = {int(schema["version"])};
    private static final String SCHEMA_NAME = {_j(schema["name"])};
    private static final String SCHEMA_HASH = {_j(schema["hash"])};
    private static volatile ApkpyDatabase instance;
    private final Context appContext;
    private final Map<String, Model> models = new LinkedHashMap<>();
{relation_field}

    static final class Field {{
        final String name, kind, defaultKind; final boolean required, primary, autoIncrement;
        final Object defaultValue; final Double min, max; final Integer maxLength; final JSONArray choices;
        Field(String name, String kind, boolean required, boolean primary, boolean autoIncrement,
              String defaultKind, Object defaultValue, Double min, Double max, Integer maxLength, JSONArray choices) {{
            this.name=name; this.kind=kind; this.required=required; this.primary=primary;
            this.autoIncrement=autoIncrement; this.defaultKind=defaultKind; this.defaultValue=defaultValue;
            this.min=min; this.max=max; this.maxLength=maxLength; this.choices=choices;
        }}
    }}
    static final class Model {{
        final String table, primaryKey; final LinkedHashMap<String, Field> fields; final String[] projection;
        Model(String table, String primaryKey, LinkedHashMap<String, Field> fields, String[] projection) {{
            this.table=table; this.primaryKey=primaryKey; this.fields=fields; this.projection=projection;
        }}
    }}
{relation_class}
    static final class Selection {{ final String sql; final String[] args; Selection(String sql, List<String> args) {{ this.sql=sql; this.args=args.toArray(new String[0]); }} }}
    public interface TransactionWork {{ String run(Transaction tx) throws Exception; }}
    public static final class Transaction {{
        private final ApkpyDatabase owner; private final SQLiteDatabase db;
{transaction_fields}
        Transaction(ApkpyDatabase owner, SQLiteDatabase db) {{ this.owner=owner; this.db=db; }}
{transaction_methods}
    }}

    private ApkpyDatabase(Context context) {{
        super(context.getApplicationContext(), DATABASE_NAME, null, SCHEMA_VERSION);
        appContext = context.getApplicationContext();
{chr(10).join(model_init)}
{chr(10).join(relation_init)}
    }}
    public static ApkpyDatabase getInstance(Context context) {{
        if (instance == null) synchronized (ApkpyDatabase.class) {{
            if (instance == null) instance = new ApkpyDatabase(context);
        }}
        return instance;
    }}

    @Override public void onConfigure(SQLiteDatabase db) {{ super.onConfigure(db); db.setForeignKeyConstraintsEnabled(true); }}
    @Override public void onCreate(SQLiteDatabase db) {{
{chr(10).join(create_lines)}
        db.execSQL("CREATE TABLE IF NOT EXISTS apkpy_schema_meta (id INTEGER PRIMARY KEY CHECK(id=1), schema_name TEXT NOT NULL, version INTEGER NOT NULL, schema_hash TEXT NOT NULL, history TEXT NOT NULL)");
        ContentValues meta = new ContentValues(); meta.put("id",1); meta.put("schema_name",SCHEMA_NAME);
        meta.put("version",SCHEMA_VERSION); meta.put("schema_hash",SCHEMA_HASH); meta.put("history","[]");
        db.insertOrThrow("apkpy_schema_meta", null, meta);
    }}
    @Override public void onOpen(SQLiteDatabase db) {{
        super.onOpen(db);
        try (Cursor cursor = db.rawQuery("SELECT version,schema_hash FROM apkpy_schema_meta WHERE id=1", null)) {{
            if (cursor.moveToFirst() && cursor.getInt(0) == SCHEMA_VERSION && !SCHEMA_HASH.equals(cursor.getString(1)))
                throw new IllegalStateException("ApkPy schema changed without increasing version " + SCHEMA_VERSION);
        }}
    }}
    @Override public void onDowngrade(SQLiteDatabase db, int oldVersion, int newVersion) {{
        throw new IllegalStateException("ApkPy refuses destructive database downgrade " + oldVersion + " -> " + newVersion);
    }}
    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {{
        File backup = null;
        if ({destructive_test}) backup = createPrivateBackup(db, oldVersion);
        int version = oldVersion;
        try {{
            while (version < newVersion) {{
                switch (version) {{
{chr(10).join(migration_switch)}
                    default: throw new IllegalStateException("No migration from version " + version);
                }}
            }}
            ContentValues meta = new ContentValues(); meta.put("version",newVersion); meta.put("schema_hash",SCHEMA_HASH);
            db.update("apkpy_schema_meta",meta,"id=1",null);
        }} catch (RuntimeException error) {{
            if (backup != null) markBackupForRecovery(backup);
            throw error;
        }}
    }}

    private Model model(String name) {{ Model model=models.get(name); if(model==null) throw new IllegalArgumentException("Unknown model '"+name+"'"); return model; }}
    private LinkedHashMap<String,Object> prepare(Model model, JSONObject values, boolean creating) throws Exception {{
        LinkedHashMap<String,Object> result = new LinkedHashMap<>();
        java.util.Iterator<String> keys=values.keys(); while(keys.hasNext()) {{ String key=keys.next(); if(!model.fields.containsKey(key)) throw new IllegalArgumentException("Unknown field '"+model.table+"."+key+"'"); }}
        for(Field field:model.fields.values()) {{
            Object value;
            if(values.has(field.name)) value=values.isNull(field.name)?null:values.get(field.name);
            else if(!creating) continue;
            else if("now".equals(field.defaultKind)) value=System.currentTimeMillis();
            else if("value".equals(field.defaultKind)) value=field.defaultValue==JSONObject.NULL?null:field.defaultValue;
            else if(field.autoIncrement) continue;
            else if(field.required) throw new IllegalArgumentException("Required field '"+model.table+"."+field.name+"' is missing");
            else value=null;
            result.put(field.name, normalize(model,field,value));
        }}
        return result;
    }}
    private Object normalize(Model model, Field field, Object value) throws Exception {{
        if(value==null) {{ if(field.required&&!field.autoIncrement) throw new IllegalArgumentException("Field '"+model.table+"."+field.name+"' cannot be null"); return null; }}
        if("integer".equals(field.kind)||"datetime".equals(field.kind)) {{
            if(value instanceof String) try{{value=Long.parseLong(((String)value).trim());}}catch(NumberFormatException error){{throw type(model,field,"integer");}}
            if(!(value instanceof Number)) throw type(model,field,"integer");
            if(!_apkpyIsWholeNumber((Number)value)) throw type(model,field,"a whole number");
            value=((Number)value).longValue();
        }}
        else if("real".equals(field.kind)) {{
            if(value instanceof String) try{{value=Double.parseDouble(((String)value).trim());}}catch(NumberFormatException error){{throw type(model,field,"real number");}}
            if(!(value instanceof Number)) throw type(model,field,"real number");
            value=((Number)value).doubleValue();
            if(Double.isNaN((Double)value)||Double.isInfinite((Double)value)) throw type(model,field,"a finite real number");
        }}
        else if("boolean".equals(field.kind)) {{
            if(value instanceof String) {{String text=((String)value).trim(); if("true".equalsIgnoreCase(text)||"1".equals(text))value=true;else if("false".equalsIgnoreCase(text)||"0".equals(text))value=false;}}
            if(value instanceof Number) {{long number=((Number)value).longValue();if(number==0L||number==1L)value=number==1L;}}
            if(!(value instanceof Boolean)) throw type(model,field,"boolean"); value=((Boolean)value)?1L:0L;
        }}
        else if("text".equals(field.kind)) {{ if(!(value instanceof String)) throw type(model,field,"text"); }}
        else if("json".equals(field.kind)) {{
            if(value instanceof JSONObject||value instanceof JSONArray) value=value.toString();
            else if(value instanceof String) _apkpyRequireJson(model,field,(String)value);
            else throw type(model,field,"JSON");
        }} else if("blob".equals(field.kind)) {{ if(value instanceof String) value=Base64.decode((String)value,Base64.DEFAULT); if(!(value instanceof byte[])) throw type(model,field,"base64 blob"); }}
        if(value instanceof Number) {{ double number=((Number)value).doubleValue(); if(field.min!=null&&number<field.min) throw new IllegalArgumentException(field.name+" is below min_value"); if(field.max!=null&&number>field.max) throw new IllegalArgumentException(field.name+" is above max_value"); }}
        if(field.maxLength!=null&&_apkpyTextLength(String.valueOf(value))>field.maxLength) throw new IllegalArgumentException(field.name+" exceeds max_length");
        if(field.choices!=null) {{ boolean found=false; for(int i=0;i<field.choices.length();i++) if(_apkpyChoiceText(field.choices.get(i)).equals(_apkpyChoiceText(value))) found=true; if(!found) throw new IllegalArgumentException(field.name+" is not an allowed choice"); }}
        return value;
    }}
    // ── As regras que os dois runtimes partilham ────────────────────
    // Escritas uma vez em apkpy_lib/data_rules.py; isto e a travessia delas
    // para o telemovel. Mexer aqui sem mexer la volta a abrir o fosso.
    private int _apkpyTextLength(String text) {{ return text.codePointCount(0,text.length()); }}
    private boolean _apkpyIsWholeNumber(Number number) {{ if(number instanceof Double||number instanceof Float) {{ double d=number.doubleValue(); return !Double.isNaN(d)&&!Double.isInfinite(d)&&d==Math.rint(d); }} return true; }}
    private String _apkpyBooleanArg(Object value) {{ return value instanceof Boolean?(((Boolean)value)?"1":"0"):String.valueOf(value); }}
    private String _apkpyChoiceText(Object item) {{ if(item instanceof Boolean) return ((Boolean)item)?"1":"0"; if(item instanceof Number) {{ double d=((Number)item).doubleValue(); if(!Double.isNaN(d)&&!Double.isInfinite(d)&&d==Math.rint(d)) return String.valueOf((long)d); }} return String.valueOf(item); }}
    private String _apkpyLikeEscape(String text) {{ StringBuilder out=new StringBuilder(); for(int i=0;i<text.length();i++) {{ char c=text.charAt(i); if(c=='\\\\'||c=='%'||c=='_') out.append('\\\\'); out.append(c); }} return out.toString(); }}
    private void _apkpyRefuseNullOrdering(String op,String name) {{ if("eq".equals(op)||"ne".equals(op)) return; throw new IllegalArgumentException("db."+op+"('"+name+"', None) cannot be compared with nothing. Use db.is_null('"+name+"') to ask for the empty rows, or leave this filter out."); }}
    private void _apkpyRequireJson(Model model,Field field,String text) throws Exception {{ JSONTokener reader=new JSONTokener(text); Object parsed; try {{ parsed=reader.nextValue(); }} catch(Exception error) {{ throw type(model,field,"JSON"); }} if(reader.nextClean()!=0) throw type(model,field,"JSON"); if(parsed instanceof String && !text.trim().startsWith("\\"")) throw type(model,field,"JSON"); }}
    private IllegalArgumentException type(Model model, Field field, String expected) {{ return new IllegalArgumentException("Field '"+model.table+"."+field.name+"' expects "+expected); }}
    private void bind(SQLiteStatement statement,int index,Object value) {{ if(value==null)statement.bindNull(index); else if(value instanceof byte[])statement.bindBlob(index,(byte[])value); else if(value instanceof Float||value instanceof Double)statement.bindDouble(index,((Number)value).doubleValue()); else if(value instanceof Number)statement.bindLong(index,((Number)value).longValue()); else statement.bindString(index,String.valueOf(value)); }}
    private long insertPrepared(SQLiteDatabase db,Model model,LinkedHashMap<String,Object> values) {{
        if(values.isEmpty()) {{ SQLiteStatement s=db.compileStatement("INSERT INTO \\\""+model.table+"\\\" DEFAULT VALUES"); try{{return s.executeInsert();}}finally{{s.close();}} }}
        StringBuilder columns=new StringBuilder(),marks=new StringBuilder(); for(String key:values.keySet()){{if(columns.length()>0){{columns.append(',');marks.append(',');}}columns.append('"').append(key).append('"');marks.append('?');}}
        SQLiteStatement statement=db.compileStatement("INSERT INTO \\\""+model.table+"\\\" ("+columns+") VALUES ("+marks+")"); int i=1; for(Object value:values.values())bind(statement,i++,value); try{{return statement.executeInsert();}}finally{{statement.close();}}
    }}
    long insertSync(SQLiteDatabase db,String modelName,JSONObject values)throws Exception{{Model m=model(modelName);return insertPrepared(db,m,prepare(m,values,true));}}
    long insertSync(String modelName,JSONObject values)throws Exception{{return insertSync(getWritableDatabase(),modelName,values);}}
    int insertManySync(SQLiteDatabase db,String modelName,JSONArray items)throws Exception{{boolean own=!db.inTransaction();if(own)db.beginTransaction();try{{for(int i=0;i<items.length();i++)insertSync(db,modelName,items.getJSONObject(i));if(own)db.setTransactionSuccessful();return items.length();}}finally{{if(own)db.endTransaction();}}}}
    int insertManySync(String modelName,JSONArray items)throws Exception{{return insertManySync(getWritableDatabase(),modelName,items);}}
{read_methods}
{reactive_helpers}
    int updateSync(SQLiteDatabase db,String modelName,JSONObject values,JSONArray filters)throws Exception{{Model m=model(modelName);LinkedHashMap<String,Object> prepared=prepare(m,values,false);ContentValues cv=contentValues(prepared);Selection s=selection(m,filters);return db.update(m.table,cv,s.sql,s.args);}}
    int updateSync(String modelName,JSONObject values,JSONArray filters)throws Exception{{return updateSync(getWritableDatabase(),modelName,values,filters);}}
    int deleteSync(SQLiteDatabase db,String modelName,JSONArray filters)throws Exception{{Model m=model(modelName);Selection s=selection(m,filters);return db.delete(m.table,s.sql,s.args);}}
    int deleteSync(String modelName,JSONArray filters)throws Exception{{return deleteSync(getWritableDatabase(),modelName,filters);}}
    int countSync(SQLiteDatabase db,String modelName,JSONArray filters)throws Exception{{Model m=model(modelName);Selection s=selection(m,filters);try(Cursor c=db.query(m.table,new String[]{{"COUNT(*)"}},s.sql,s.args,null,null,null)){{c.moveToFirst();return c.getInt(0);}}}}
    int countSync(String modelName,JSONArray filters)throws Exception{{return countSync(getReadableDatabase(),modelName,filters);}}
    private ContentValues contentValues(Map<String,Object> values){{ContentValues cv=new ContentValues();for(Map.Entry<String,Object> e:values.entrySet()){{Object v=e.getValue();if(v==null)cv.putNull(e.getKey());else if(v instanceof byte[])cv.put(e.getKey(),(byte[])v);else if(v instanceof Double||v instanceof Float)cv.put(e.getKey(),((Number)v).doubleValue());else if(v instanceof Number)cv.put(e.getKey(),((Number)v).longValue());else cv.put(e.getKey(),String.valueOf(v));}}return cv;}}
    private JSONObject rowJson(Cursor c,Model m)throws Exception{{JSONObject row=new JSONObject();for(Field f:m.fields.values()){{int i=c.getColumnIndex(f.name);if(i<0||c.isNull(i)){{row.put(f.name,JSONObject.NULL);continue;}}if("integer".equals(f.kind)||"datetime".equals(f.kind))row.put(f.name,c.getLong(i));else if("real".equals(f.kind))row.put(f.name,c.getDouble(i));else if("boolean".equals(f.kind))row.put(f.name,c.getInt(i)!=0);else if("json".equals(f.kind))row.put(f.name,new JSONTokener(c.getString(i)).nextValue());else if("blob".equals(f.kind))row.put(f.name,Base64.encodeToString(c.getBlob(i),Base64.NO_WRAP));else row.put(f.name,c.getString(i));}}return row;}}
    private Selection selection(Model m,JSONArray filters)throws Exception{{if(filters==null||filters.length()==0)return new Selection(null,new ArrayList<>());List<String>args=new ArrayList<>();List<String>parts=new ArrayList<>();for(int i=0;i<filters.length();i++)parts.add(filter(m,filters.getJSONObject(i),args));return new Selection(join(parts," AND "),args);}}
    private String filter(Model m,JSONObject f,List<String>args)throws Exception{{String op=f.getString("op");if("and".equals(op)||"or".equals(op)){{JSONArray children=f.getJSONArray("children");List<String>parts=new ArrayList<>();for(int i=0;i<children.length();i++)parts.add(filter(m,children.getJSONObject(i),args));return "("+join(parts,"and".equals(op)?" AND ":" OR ")+")";}}String name=f.getString("field");if(!m.fields.containsKey(name))throw new IllegalArgumentException("Unknown filter field "+name);String col="\\\""+name+"\\\"";if("is_null".equals(op))return col+(f.optBoolean("value",true)?" IS NULL":" IS NOT NULL");if("in".equals(op)){{JSONArray values=f.getJSONArray("value");if(values.length()==0)return "0";StringBuilder marks=new StringBuilder();for(int i=0;i<values.length();i++){{if(i>0)marks.append(',');marks.append('?');args.add(_apkpyBooleanArg(values.get(i)));}}return col+" IN ("+marks+")";}}String sign="eq".equals(op)?"=":"ne".equals(op)?"!=":"gt".equals(op)?">":"gte".equals(op)?">=":"lt".equals(op)?"<":"lte".equals(op)?"<=":null;Object value=f.opt("value");if(sign!=null){{if(value==null||value==JSONObject.NULL){{_apkpyRefuseNullOrdering(op,name);return col+("ne".equals(op)?" IS NOT NULL":" IS NULL");}}args.add(_apkpyBooleanArg(value));return col+" "+sign+" ?";}}String text=_apkpyLikeEscape(String.valueOf(value));if("contains".equals(op))text="%"+text+"%";else if("starts_with".equals(op))text=text+"%";else if("ends_with".equals(op))text="%"+text;else throw new IllegalArgumentException("Unknown filter "+op);args.add(text);return col+" LIKE ? ESCAPE '\\\\'";}}
    private String order(Model m,JSONArray orders)throws Exception{{if(orders==null)return null;List<String>parts=new ArrayList<>();for(int i=0;i<orders.length();i++){{JSONObject item=orders.getJSONObject(i);String field=item.getString("field");if(!m.fields.containsKey(field))throw new IllegalArgumentException("Unknown order field "+field);parts.add("\\\""+field+"\\\" "+("DESC".equals(item.optString("direction"))?"DESC":"ASC"));}}return join(parts,", ");}}
    private String join(List<String>values,String separator){{StringBuilder out=new StringBuilder();for(String value:values){{if(out.length()>0)out.append(separator);out.append(value);}}return out.toString();}}
    public ApkpyDataExecutor.Task transactionTask(TransactionWork work){{{transaction_task}}}
    public void transactionAsync(TransactionWork work,ApkpyDataExecutor.Callback callback){{ApkpyDataExecutor.submit(transactionTask(work),callback);}}
    private File createPrivateBackup(SQLiteDatabase db,int version){{try{{try(Cursor ignored=db.rawQuery("PRAGMA wal_checkpoint(FULL)",null)){{if(ignored.moveToFirst()){{}}}}File source=appContext.getDatabasePath(DATABASE_NAME);File target=new File(source.getParentFile(),DATABASE_NAME+".backup-v"+version);copy(source,target);return target;}}catch(Exception error){{throw new IllegalStateException("Could not create migration backup",error);}}}}
    private void markBackupForRecovery(File backup){{appContext.getSharedPreferences("apkpy_data",Context.MODE_PRIVATE).edit().putString("recovery_backup",backup.getAbsolutePath()).commit();}}
    private static void copy(File source,File target)throws Exception{{try(FileChannel input=new FileInputStream(source).getChannel();FileChannel output=new FileOutputStream(target).getChannel()){{output.transferFrom(input,0,input.size());output.force(true);}}}}
    private static void renameIndex(SQLiteDatabase db,String oldName,String newName){{try(Cursor c=db.rawQuery("SELECT sql FROM sqlite_master WHERE type='index' AND name=?",new String[]{{oldName}})){{if(!c.moveToFirst())throw new IllegalStateException("Missing index "+oldName);String sql=c.getString(0);db.execSQL("DROP INDEX \\\""+oldName+"\\\"");db.execSQL(sql.replaceFirst("(?i)(CREATE\\\\s+(?:UNIQUE\\\\s+)?INDEX\\\\s+)\\\\S+","$1"+newName));}}}}
    public static JSONObject parseObject(String value){{try{{return new JSONObject(value);}}catch(Exception error){{throw new IllegalArgumentException("Expected JSON object",error);}}}}
    public static JSONArray parseArray(String value){{try{{return new JSONArray(value);}}catch(Exception error){{throw new IllegalArgumentException("Expected JSON array",error);}}}}
    public static void put(JSONObject object,String key,Object value){{try{{object.put(key,value);}}catch(Exception error){{throw new IllegalArgumentException("Could not encode field "+key,error);}}}}
    public static void put(JSONArray array,Object value){{array.put(value);}}
}}
'''


def _migration_java(operation, schema):
    kind = operation["operation"]
    model_name = operation.get("model")
    indent = "                "
    if kind == "create_table":
        model = next(item for item in schema["models"] if item["name"] == model_name)
        return [f'{indent}db.execSQL({_java_string(_create_table_sql(model, schema))});']
    if kind == "add_column":
        sql = f'ALTER TABLE "{model_name}" ADD COLUMN {_column_sql(operation["name"], operation["field"], primary=False)}'
        return [f'{indent}db.execSQL({_java_string(sql)});']
    if kind == "rename_column":
        sql = f'ALTER TABLE "{model_name}" RENAME COLUMN "{operation["name"]}" TO "{operation["new_name"]}"'
        return [f'{indent}db.execSQL({_java_string(sql)});']
    if kind == "create_index":
        sql = _create_index_sql(model_name, operation)
        return [f'{indent}db.execSQL({_java_string(sql)});']
    if kind == "rename_index":
        return [f'{indent}renameIndex(db,{_j(operation["name"])},{_j(operation["new_name"])});']
    if kind == "drop_index":
        return [f'{indent}db.execSQL({_java_string("DROP INDEX \"" + operation["name"] + "\"")});']
    if kind == "rename_table":
        return [f'{indent}db.execSQL({_java_string("ALTER TABLE \"" + model_name + "\" RENAME TO \"" + operation["new_name"] + "\"")});']
    if kind == "sql":
        params = operation.get("params") or []
        if params:
            values = ", ".join(_java_object_literal(item) for item in params)
            return [f'{indent}db.execSQL({_java_string(operation["query"])},new Object[]{{{values}}});']
        return [f'{indent}db.execSQL({_java_string(operation["query"])});']
    return [f'{indent}throw new IllegalStateException("Unsupported migration {kind}");']


def _java_object_literal(value):
    if value is None: return "null"
    if isinstance(value, bool): return "true" if value else "false"
    if isinstance(value, (int, float)): return str(value)
    return _j(value)


def _generate_repository(model, package, reactive=False):
    cls = repository_class(model["name"])
    table = _j(model["name"])
    invalidation = (
        f'ApkpyDataInvalidationTracker.invalidate(db.expandInvalidations('
        f'java.util.Collections.singleton({table})));'
        if reactive else ""
    )
    return f'''package {package};

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;

public final class {cls} {{
    private {cls}() {{}}
    // Each operation is written once, as a Task. A screen submits it to the
    // data thread; a background job's Worker runs it where it is
    // (ApkpyDataExecutor.runHere).
    public static ApkpyDataExecutor.Task insertTask(Context context,JSONObject values){{return()->{{ApkpyDatabase db=ApkpyDatabase.getInstance(context);long result=db.insertSync({table},values);{invalidation}return String.valueOf(result);}};}}
    public static ApkpyDataExecutor.Task insertManyTask(Context context,JSONArray values){{return()->{{ApkpyDatabase db=ApkpyDatabase.getInstance(context);int result=db.insertManySync({table},values);if(result>0){{{invalidation}}}return String.valueOf(result);}};}}
    public static ApkpyDataExecutor.Task getTask(Context context,Object id,JSONArray include){{return()->ApkpyDatabase.getInstance(context).getSync({table},id,include);}}
    public static ApkpyDataExecutor.Task findTask(Context context,JSONArray filters,JSONArray order,Integer limit,int offset,JSONArray include){{return()->ApkpyDatabase.getInstance(context).findSync({table},filters,order,limit,offset,include);}}
    public static ApkpyDataExecutor.Task updateTask(Context context,JSONObject values,JSONArray filters){{return()->{{ApkpyDatabase db=ApkpyDatabase.getInstance(context);int result=db.updateSync({table},values,filters);if(result>0){{{invalidation}}}return String.valueOf(result);}};}}
    public static ApkpyDataExecutor.Task deleteTask(Context context,JSONArray filters){{return()->{{ApkpyDatabase db=ApkpyDatabase.getInstance(context);int result=db.deleteSync({table},filters);if(result>0){{{invalidation}}}return String.valueOf(result);}};}}
    public static ApkpyDataExecutor.Task countTask(Context context,JSONArray filters){{return()->String.valueOf(ApkpyDatabase.getInstance(context).countSync({table},filters));}}
    public static void insert(Context context,JSONObject values,ApkpyDataExecutor.Callback callback){{ApkpyDataExecutor.submit(insertTask(context,values),callback);}}
    public static void insertMany(Context context,JSONArray values,ApkpyDataExecutor.Callback callback){{ApkpyDataExecutor.submit(insertManyTask(context,values),callback);}}
    public static void get(Context context,Object id,JSONArray include,ApkpyDataExecutor.Callback callback){{ApkpyDataExecutor.submit(getTask(context,id,include),callback);}}
    public static void find(Context context,JSONArray filters,JSONArray order,Integer limit,int offset,JSONArray include,ApkpyDataExecutor.Callback callback){{ApkpyDataExecutor.submit(findTask(context,filters,order,limit,offset,include),callback);}}
    public static void update(Context context,JSONObject values,JSONArray filters,ApkpyDataExecutor.Callback callback){{ApkpyDataExecutor.submit(updateTask(context,values,filters),callback);}}
    public static void delete(Context context,JSONArray filters,ApkpyDataExecutor.Callback callback){{ApkpyDataExecutor.submit(deleteTask(context,filters),callback);}}
    public static void count(Context context,JSONArray filters,ApkpyDataExecutor.Callback callback){{ApkpyDataExecutor.submit(countTask(context,filters),callback);}}
}}
'''


def emit_command(lines, indent, command, value_to_java, emit_commands, functions_map, declared,
                 scope="activity", returns=None):
    """Emit one typed-data command.

    *scope* ``"activity"`` submits the operation to the data thread and
    answers on the main thread. ``"worker"`` -- the body of a background job --
    runs the same Task where it is, through ``ApkpyDataExecutor.runHere``, so
    the next line of the job sees the answer, as it does in the Previewer.

    *returns* is the compiler's "does this list of commands return on every
    path" check. A transaction body that ends in ``return total`` used to be
    followed by ``return "";``, which javac refuses as unreachable.
    """
    ctype = command["type"]
    seq = int(command.get("seq", 0))
    worker = scope != "activity"
    if ctype == "data_transaction":
        run = command.get("run")
        info = functions_map.get(run, {}) if run else {}
        body = info.get("cmds", [])
        if worker:
            lines.append(f"{indent}ApkpyDataExecutor.runHere(ApkpyDatabase.getInstance(getApplicationContext()).transactionTask(_apkpyTx -> {{")
        else:
            lines.append(f"{indent}ApkpyDatabase.getInstance(getApplicationContext()).transactionAsync(_apkpyTx -> {{")
        # The body is a lambda: what it declares does not exist after it.
        emit_commands(body, indent + "    ", set(declared))
        if not (returns and returns(body)):
            lines.append(f'{indent}    return "";')
        closer = "})" if worker else "}"
        lines.append(f"{indent}{closer}, {_callback_java(command)});")
        return
    if ctype in ("data_tx", "data_tx_assign"):
        expression = _tx_expression(lines, indent, command, value_to_java, seq)
        if ctype == "data_tx_assign":
            target = command.get("assign_to")
            prefix = "" if target in declared else "String "
            declared.add(target)
            lines.append(f"{indent}{prefix}{target} = String.valueOf({expression});")
        else:
            lines.append(f"{indent}{expression};")
        return
    if ctype == "data_observer":
        observer = command["observer"]
        method = command["method"]
        if method in ("refresh", "close"):
            lines.append(f"{indent}if ({observer} != null) {observer}.{method}();")
            return
        mask = 0
        if "filters_node" in command: mask |= 1
        if "order_node" in command: mask |= 2
        if "limit_node" in command: mask |= 4
        if "offset_node" in command: mask |= 8
        if "include_node" in command: mask |= 16
        filters = (_emit_filter_array(lines, indent, command.get("filters_node"), value_to_java,
                                      f"_apkpyObserverFilters{seq}")
                   if mask & 1 else "null")
        orders = (_emit_order_array(lines, indent, command.get("order_node"), value_to_java,
                                    f"_apkpyObserverOrder{seq}")
                  if mask & 2 else "null")
        includes = (_emit_string_array(lines, indent, command.get("include_node"), value_to_java,
                                       f"_apkpyObserverInclude{seq}")
                    if mask & 16 else "null")
        limit = (f"Integer.valueOf(String.valueOf({value_to_java(command['limit_node'])}))"
                 if mask & 4 else "null")
        offset = (f"Integer.valueOf(String.valueOf({value_to_java(command['offset_node'])}))"
                  if mask & 8 else "null")
        lines.append(
            f"{indent}if ({observer} != null) {observer}.updateQuery("
            f"{mask}, {filters}, {orders}, {limit}, {offset}, {includes});"
        )
        return
    if ctype != "data_model":
        return
    model_class = repository_class(command["model"])
    method = command["method"]
    callback = _callback_java(command)

    def operation(java_method, arguments):
        if worker:
            lines.append(
                f"{indent}ApkpyDataExecutor.runHere({model_class}.{java_method}Task("
                f"getApplicationContext(), {arguments}), {callback});")
        else:
            lines.append(
                f"{indent}{model_class}.{java_method}(getApplicationContext(), "
                f"{arguments}, {callback});")

    if method in ("insert", "update"):
        values = _emit_json_object(lines, indent, command.get("values_node"), value_to_java, f"_apkpyDataValues{seq}")
        if method == "insert":
            operation("insert", values)
        else:
            filters = _emit_filter_array(lines, indent, command.get("filters_node"), value_to_java, f"_apkpyDataFilters{seq}")
            operation("update", f"{values}, {filters}")
    elif method == "insert_many":
        values = _emit_json_array(lines, indent, command.get("values_node"), value_to_java, f"_apkpyDataItems{seq}")
        operation("insertMany", values)
    elif method == "get":
        item_id = value_to_java(command.get("id_node"))
        includes = _emit_string_array(lines, indent, command.get("include_node"), value_to_java, f"_apkpyDataInclude{seq}")
        operation("get", f"{item_id}, {includes}")
    elif method == "find":
        filters = _emit_filter_array(lines, indent, command.get("filters_node"), value_to_java, f"_apkpyDataFilters{seq}")
        orders = _emit_order_array(lines, indent, command.get("order_node"), value_to_java, f"_apkpyDataOrder{seq}")
        limit = "null" if command.get("limit_node") is None else f"Integer.valueOf(String.valueOf({value_to_java(command['limit_node'])}))"
        offset = "0" if command.get("offset_node") is None else f"Integer.parseInt(String.valueOf({value_to_java(command['offset_node'])}))"
        includes = _emit_string_array(lines, indent, command.get("include_node"), value_to_java, f"_apkpyDataInclude{seq}")
        operation("find", f"{filters}, {orders}, {limit}, {offset}, {includes}")
    elif method in ("delete", "count"):
        filters = _emit_filter_array(lines, indent, command.get("filters_node"), value_to_java, f"_apkpyDataFilters{seq}")
        operation(method, filters)


def _callback_java(command):
    result = command.get("on_result")
    error = command.get("on_error")
    if not result and not error:
        return "null"
    result_body = f"pythonCallback_{result}(value);" if result else ""
    error_body = f"pythonCallback_{error}(message);" if error else "android.util.Log.e(\"ApkpyData\", message);"
    return (
        "new ApkpyDataExecutor.Callback(){public void onResult(String value){" + result_body
        + "}public void onError(String message){" + error_body + "}}"
    )


def _tx_expression(lines, indent, command, value_to_java, seq):
    method = command["method"]
    table = _j(command["model"])
    if method in ("insert", "update"):
        values = _emit_json_object(lines, indent, command.get("values_node"), value_to_java, f"_apkpyTxValues{seq}")
        if method == "insert": return f"_apkpyTx.insert({table},{values})"
        filters = _emit_filter_array(lines, indent, command.get("filters_node"), value_to_java, f"_apkpyTxFilters{seq}")
        return f"_apkpyTx.update({table},{values},{filters})"
    if method == "insert_many":
        values = _emit_json_array(lines, indent, command.get("values_node"), value_to_java, f"_apkpyTxItems{seq}")
        return f"_apkpyTx.insertMany({table},{values})"
    if method == "get": return f"_apkpyTx.get({table},{value_to_java(command.get('id_node'))})"
    filters = _emit_filter_array(lines, indent, command.get("filters_node"), value_to_java, f"_apkpyTxFilters{seq}")
    if method == "delete": return f"_apkpyTx.delete({table},{filters})"
    if method == "count": return f"_apkpyTx.count({table},{filters})"
    if method == "find":
        orders = _emit_order_array(lines, indent, command.get("order_node"), value_to_java, f"_apkpyTxOrder{seq}")
        limit = "null" if command.get("limit_node") is None else f"Integer.valueOf(String.valueOf({value_to_java(command['limit_node'])}))"
        offset = "0" if command.get("offset_node") is None else f"Integer.parseInt(String.valueOf({value_to_java(command['offset_node'])}))"
        return f"_apkpyTx.find({table},{filters},{orders},{limit},{offset})"
    return '""'


def _emit_json_object(lines, indent, node, value_to_java, name):
    lines.append(f"{indent}org.json.JSONObject {name} = new org.json.JSONObject();")
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values):
            key_value = _literal(key)
            if isinstance(key_value, str):
                lines.append(f"{indent}ApkpyDatabase.put({name}, {_j(key_value)}, {_json_value(value, value_to_java)});")
    else:
        expression = value_to_java(node)
        lines.append(f"{indent}{name} = ApkpyDatabase.parseObject(String.valueOf({expression}));")
    return name


def _emit_json_array(lines, indent, node, value_to_java, name):
    lines.append(f"{indent}org.json.JSONArray {name} = new org.json.JSONArray();")
    if isinstance(node, (ast.List, ast.Tuple)):
        for index, item in enumerate(node.elts):
            if isinstance(item, ast.Dict):
                child = _emit_json_object(lines, indent, item, value_to_java, f"{name}Item{index}")
                lines.append(f"{indent}ApkpyDatabase.put({name}, {child});")
            else:
                lines.append(f"{indent}ApkpyDatabase.put({name}, {_json_value(item, value_to_java)});")
    elif node is not None:
        lines.append(f"{indent}{name} = ApkpyDatabase.parseArray(String.valueOf({value_to_java(node)}));")
    return name


def _json_value(node, value_to_java):
    if isinstance(node, ast.Constant):
        if node.value is None: return "org.json.JSONObject.NULL"
        if isinstance(node.value, bool): return "true" if node.value else "false"
        if isinstance(node.value, (int, float)): return str(node.value)
        return value_to_java(node)
    if isinstance(node, ast.Dict):
        try: return f"ApkpyDatabase.parseObject({_j(json.dumps(ast.literal_eval(node), ensure_ascii=False))})"
        except Exception: return "new org.json.JSONObject()"
    if isinstance(node, (ast.List, ast.Tuple)):
        try: return f"ApkpyDatabase.parseArray({_j(json.dumps(ast.literal_eval(node), ensure_ascii=False))})"
        except Exception: return "new org.json.JSONArray()"
    return f"String.valueOf({value_to_java(node)})"


def _emit_filter_array(lines, indent, node, value_to_java, name):
    lines.append(f"{indent}org.json.JSONArray {name} = new org.json.JSONArray();")
    nodes = []
    if isinstance(node, (ast.List, ast.Tuple)):
        nodes = list(node.elts)
    elif node is not None:
        nodes = [node]
    for index, item in enumerate(nodes):
        var = _emit_filter(lines, indent, item, value_to_java, f"{name}F{index}")
        lines.append(f"{indent}ApkpyDatabase.put({name}, {var});")
    return name


def _emit_filter(lines, indent, node, value_to_java, name):
    lines.append(f"{indent}org.json.JSONObject {name} = new org.json.JSONObject();")
    if not _call_is_any_db(node):
        return name
    op = node.func.attr
    lines.append(f"{indent}ApkpyDatabase.put({name}, \"op\", {_j(op.rstrip('_'))});")
    if op in ("and_", "or_"):
        lines[-1] = f"{indent}ApkpyDatabase.put({name}, \"op\", {_j(op[:-1])});"
        lines.append(f"{indent}org.json.JSONArray {name}Children = new org.json.JSONArray();")
        for index, child_node in enumerate(node.args):
            child = _emit_filter(lines, indent, child_node, value_to_java, f"{name}C{index}")
            lines.append(f"{indent}ApkpyDatabase.put({name}Children, {child});")
        lines.append(f"{indent}ApkpyDatabase.put({name}, \"children\", {name}Children);")
        return name
    field_node = node.args[0] if node.args else _kw_node(node, "name")
    lines.append(f"{indent}ApkpyDatabase.put({name}, \"field\", String.valueOf({value_to_java(field_node)}));")
    value_node = node.args[1] if len(node.args) > 1 else _kw_node(node, "value")
    if value_node is not None:
        lines.append(f"{indent}ApkpyDatabase.put({name}, \"value\", {_json_value(value_node, value_to_java)});")
    return name


def _emit_order_array(lines, indent, node, value_to_java, name):
    lines.append(f"{indent}org.json.JSONArray {name} = new org.json.JSONArray();")
    nodes = list(node.elts) if isinstance(node, (ast.List, ast.Tuple)) else ([] if node is None else [node])
    for index, item in enumerate(nodes):
        if _call_is_any_db(item) and item.func.attr in ("asc", "desc"):
            field_node = item.args[0] if item.args else _kw_node(item, "name")
            lines.append(f"{indent}org.json.JSONObject {name}O{index} = new org.json.JSONObject();")
            lines.append(f"{indent}ApkpyDatabase.put({name}O{index}, \"field\", String.valueOf({value_to_java(field_node)}));")
            lines.append(f"{indent}ApkpyDatabase.put({name}O{index}, \"direction\", {_j(item.func.attr.upper())});")
            lines.append(f"{indent}ApkpyDatabase.put({name}, {name}O{index});")
    return name


def _emit_string_array(lines, indent, node, value_to_java, name):
    lines.append(f"{indent}org.json.JSONArray {name} = new org.json.JSONArray();")
    nodes = list(node.elts) if isinstance(node, (ast.List, ast.Tuple)) else ([] if node is None else [node])
    for item in nodes:
        lines.append(
            f"{indent}ApkpyDatabase.put({name}, String.valueOf({value_to_java(item)}));"
        )
    return name


def emit_observer_initialization(lines, indent, observer, value_to_java):
    """Create one generated Activity subscription without starting it yet."""
    seq = re.sub(r"[^A-Za-z0-9_]", "_", observer["var"])
    filters = _emit_filter_array(
        lines, indent, observer.get("filters_node"), value_to_java,
        f"_apkpyObserveFilters_{seq}",
    )
    orders = _emit_order_array(
        lines, indent, observer.get("order_node"), value_to_java,
        f"_apkpyObserveOrder_{seq}",
    )
    includes = _emit_string_array(
        lines, indent, observer.get("include_node"), value_to_java,
        f"_apkpyObserveInclude_{seq}",
    )
    limit = ("null" if observer.get("limit_node") is None else
             f"Integer.valueOf(String.valueOf({value_to_java(observer['limit_node'])}))")
    offset = ("0" if observer.get("offset_node") is None else
              f"Integer.parseInt(String.valueOf({value_to_java(observer['offset_node'])}))")
    callback = _callback_java({
        "on_result": observer.get("on_change"),
        "on_error": observer.get("on_error"),
    })
    lines.append(
        f"{indent}{observer['var']} = new ApkpyQuerySubscription("
        f"getApplicationContext(), {_j(observer['model'])}, {filters}, {orders}, "
        f"{limit}, {offset}, {includes}, {callback});"
    )


def _call_is_any_db(node):
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "db"


__all__ = [
    "COMMAND_TYPES", "initialize", "parse_assignment", "parse_model_command",
    "parse_transaction_command", "parse_tx_command", "generate_files",
    "emit_command", "emit_observer_initialization", "repository_class",
    "is_command_call", "parse_observer_command",
]
