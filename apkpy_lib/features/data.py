"""Typed, declarative SQLite data layer used by ApkPy's desktop preview.

This module deliberately has no dependency on ``ui.py``.  ``SQLiteAPI`` mixes
in :class:`DataCoreMixin`, while callbacks import the preview lazily only when
they need to return to Tk's main thread.  The same descriptors are consumed by
the Android compiler, so schema declarations remain ordinary Python objects in
the Previewer and compile-time metadata in generated apps.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
import re
import shutil
import sqlite3
import threading
from typing import Any, Callable, Iterable, Optional

from .. import data_rules, job_rules
from .data_reactive import QuerySubscription, RelationDef
from ..diagnostics import format_exception


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MISSING = object()


class DataCoreError(ValueError):
    """A declaration, validation, query, or migration error."""


@dataclass(frozen=True)
class NowValue:
    pass


@dataclass(frozen=True)
class FieldDef:
    kind: str
    required: bool = False
    optional: bool = False
    default: Any = _MISSING
    primary_key: bool = False
    auto_increment: bool = False
    unique: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_length: Optional[int] = None
    choices: Optional[tuple] = None

    def describe(self) -> dict:
        default = self.default
        if isinstance(default, NowValue):
            default = {"factory": "now"}
        elif default is _MISSING:
            default = {"missing": True}
        elif isinstance(default, bytes):
            default = {"blob": default.hex()}
        return {
            "kind": self.kind,
            "required": self.required,
            "optional": self.optional,
            "default": default,
            "primary_key": self.primary_key,
            "auto_increment": self.auto_increment,
            "unique": self.unique,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "max_length": self.max_length,
            "choices": list(self.choices) if self.choices is not None else None,
        }


@dataclass(frozen=True)
class IndexDef:
    name: str
    fields: tuple[str, ...]
    unique: bool = False

    def describe(self) -> dict:
        return {"name": self.name, "fields": list(self.fields), "unique": self.unique}


@dataclass(frozen=True)
class FilterDef:
    operation: str
    field_name: Optional[str] = None
    value: Any = None
    children: tuple["FilterDef", ...] = ()


@dataclass(frozen=True)
class OrderDef:
    field_name: str
    direction: str


@dataclass(frozen=True)
class MigrationOperation:
    operation: str
    model: Any = None
    name: Optional[str] = None
    new_name: Optional[str] = None
    fields: tuple[str, ...] = ()
    field_def: Optional[FieldDef] = None
    unique: bool = False
    query: Optional[str] = None
    params: tuple[Any, ...] = ()
    destructive: bool = False


@dataclass(frozen=True)
class MigrationDef:
    from_version: int
    to_version: int
    operations: tuple[MigrationOperation, ...]
    destructive: bool = False


@dataclass
class SchemaDef:
    owner: Any
    name: str
    version: int
    models: tuple["ModelDef", ...]
    relations: tuple[RelationDef, ...]
    migrations: tuple[MigrationDef, ...]
    schema_hash: str
    source_file: str
    source_line: int

    def info(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "hash": self.schema_hash,
            "models": [model.name for model in self.models],
            "relations": [relation.name for relation in self.relations],
            "source": f"{self.source_file}:{self.source_line}",
        }


@dataclass
class ModelDef:
    owner: Any
    name: str
    fields: dict[str, FieldDef]
    indexes: tuple[IndexDef, ...] = ()
    source_file: str = ""
    source_line: int = 0

    def insert(self, values, on_result=None, on_error=None):
        return self.owner._data_insert(self, values, on_result, on_error)

    def insert_many(self, items, on_result=None, on_error=None):
        return self.owner._data_insert_many(self, items, on_result, on_error)

    def get(self, item_id, on_result=None, on_error=None, include=None):
        return self.owner._data_get(
            self, item_id, on_result, on_error, include or [],
        )

    def find(self, filters=None, order_by=None, limit=None, offset=0,
             on_result=None, on_error=None, include=None):
        return self.owner._data_find(
            self, filters or [], order_by or [], limit, offset,
            on_result, on_error, include or [],
        )

    def observe(self, filters=None, order_by=None, limit=None, offset=0,
                include=None, screen=None, on_change=None, on_error=None):
        return self.owner._data_observe(
            self, filters or [], order_by or [], limit, offset,
            include or [], screen, on_change, on_error,
        )

    def update(self, values, filters=None, on_result=None, on_error=None):
        return self.owner._data_update(
            self, values, filters or [], on_result, on_error,
        )

    def delete(self, filters=None, on_result=None, on_error=None):
        return self.owner._data_delete(self, filters or [], on_result, on_error)

    def count(self, filters=None, on_result=None, on_error=None):
        return self.owner._data_count(self, filters or [], on_result, on_error)

    @property
    def primary_key(self) -> Optional[str]:
        for name, definition in self.fields.items():
            if definition.primary_key:
                return name
        return None

    def describe(self) -> dict:
        return {
            "name": self.name,
            "fields": {name: definition.describe() for name, definition in self.fields.items()},
            "indexes": [index.describe() for index in self.indexes],
        }


class TransactionContext:
    """Synchronous operations allowed inside a queued atomic transaction."""

    def __init__(self, owner, connection):
        self._owner = owner
        self._connection = connection
        self._dirty_models = set()

    def insert(self, model, values):
        result = self._owner._insert_sync(self._connection, model, values)
        self._dirty_models.add(model.name)
        return result

    def insert_many(self, model, items):
        result = self._owner._insert_many_sync(self._connection, model, items)
        if result:
            self._dirty_models.add(model.name)
        return result

    def get(self, model, item_id):
        return self._owner._get_sync(self._connection, model, item_id)

    def find(self, model, filters=None, order_by=None, limit=None, offset=0):
        return self._owner._find_sync(
            self._connection, model, filters or [], order_by or [], limit, offset,
        )

    def update(self, model, values, filters=None):
        result = self._owner._update_sync(
            self._connection, model, values, filters or [],
        )
        if result:
            self._dirty_models.add(model.name)
        return result

    def delete(self, model, filters=None):
        result = self._owner._delete_sync(self._connection, model, filters or [])
        if result:
            self._dirty_models.add(model.name)
        return result

    def count(self, model, filters=None):
        return self._owner._count_sync(self._connection, model, filters or [])


class DataCoreMixin:
    """Implementation mixed into the public ``SQLiteAPI`` object."""

    _SQL_TYPES = {
        "integer": "INTEGER",
        "real": "REAL",
        "text": "TEXT",
        "boolean": "INTEGER",
        "datetime": "INTEGER",
        "json": "TEXT",
        "blob": "BLOB",
    }

    def _data_core_init(self):
        self._data_models: dict[str, ModelDef] = {}
        self._data_relations: dict[str, RelationDef] = {}
        self._data_schema: Optional[SchemaDef] = None
        self._data_executor: Optional[ThreadPoolExecutor] = None
        self._data_executor_lock = threading.Lock()
        self._data_observer_lock = threading.RLock()
        self._data_observers: list[QuerySubscription] = []

    # -- declaration factories -------------------------------------------------

    def _field(self, kind, **options):
        if kind not in self._SQL_TYPES:
            raise DataCoreError(f"Unsupported data type '{kind}'.")
        choices = options.get("choices")
        if choices is not None:
            options["choices"] = tuple(choices)
        definition = FieldDef(kind=kind, **options)
        if definition.required and definition.optional:
            raise DataCoreError("A field cannot be both required and optional.")
        if definition.auto_increment and not (
                definition.primary_key and definition.kind == "integer"):
            raise DataCoreError(
                "auto_increment=True requires an integer primary key."
            )
        if definition.min_value is not None and definition.max_value is not None \
                and definition.min_value > definition.max_value:
            raise DataCoreError("min_value cannot be greater than max_value.")
        if definition.max_length is not None and definition.max_length < 0:
            raise DataCoreError("max_length cannot be negative.")
        return definition

    def integer(self, **options): return self._field("integer", **options)
    def real(self, **options): return self._field("real", **options)
    def text(self, **options): return self._field("text", **options)
    def boolean(self, **options): return self._field("boolean", **options)
    def datetime(self, **options): return self._field("datetime", **options)
    def json(self, **options): return self._field("json", **options)
    def blob(self, **options): return self._field("blob", **options)
    def now(self): return NowValue()

    def index(self, name, fields, unique=False):
        self._validate_identifier(name, "index")
        if not fields:
            raise DataCoreError(f"Index '{name}' must contain at least one field.")
        return IndexDef(str(name), tuple(str(item) for item in fields), bool(unique))

    def model(self, name, fields, indexes=None):
        source_file, source_line = self._source_location(2)
        self._validate_identifier(name, "model")
        if name in self._data_models:
            raise DataCoreError(
                f"Duplicate model '{name}' at {source_file}:{source_line}."
            )
        if not isinstance(fields, dict) or not fields:
            raise DataCoreError(f"Model '{name}' must declare at least one field.")
        normalized = {}
        primary_keys = []
        for field_name, definition in fields.items():
            self._validate_identifier(field_name, f"field in model '{name}'")
            if not isinstance(definition, FieldDef):
                raise DataCoreError(
                    f"Field '{name}.{field_name}' is not a db field declaration."
                )
            normalized[str(field_name)] = definition
            if definition.primary_key:
                primary_keys.append(field_name)
        if len(primary_keys) > 1:
            raise DataCoreError(
                f"Model '{name}' declares more than one primary key."
            )
        normalized_indexes = tuple(indexes or ())
        index_names = set()
        for index in normalized_indexes:
            if not isinstance(index, IndexDef):
                raise DataCoreError(f"Model '{name}' received an invalid index.")
            if index.name in index_names:
                raise DataCoreError(f"Duplicate index '{index.name}' in model '{name}'.")
            index_names.add(index.name)
            missing = [field for field in index.fields if field not in normalized]
            if missing:
                raise DataCoreError(
                    f"Index '{index.name}' references unknown field(s): "
                    + ", ".join(missing)
                )
        model = ModelDef(
            owner=self, name=str(name), fields=normalized,
            indexes=normalized_indexes, source_file=source_file,
            source_line=source_line,
        )
        self._data_models[model.name] = model
        return model

    def relation(self, name, parent, child, foreign_key, parent_as,
                 children_as, on_delete="restrict"):
        """Declare a validated one-to-many relation between two models."""
        self._validate_identifier(name, "relation")
        self._validate_identifier(parent_as, "parent relation alias")
        self._validate_identifier(children_as, "children relation alias")
        self._validate_identifier(foreign_key, "foreign key")
        if name in self._data_relations:
            raise DataCoreError(f"Duplicate relation '{name}'.")
        if parent_as == children_as:
            raise DataCoreError(
                f"Relation '{name}' requires distinct parent_as and children_as aliases."
            )
        requested_aliases = {str(parent_as), str(children_as)}
        for existing in self._data_relations.values():
            existing_aliases = {existing.parent_as, existing.children_as}
            duplicate_aliases = sorted(requested_aliases & existing_aliases)
            if duplicate_aliases:
                raise DataCoreError(
                    "Relation aliases must be unique; already declared: "
                    + ", ".join(duplicate_aliases)
                    + "."
                )
        if not isinstance(parent, ModelDef) or parent.owner is not self:
            raise DataCoreError(f"Relation '{name}' has an invalid parent model.")
        if not isinstance(child, ModelDef) or child.owner is not self:
            raise DataCoreError(f"Relation '{name}' has an invalid child model.")
        if parent is child:
            raise DataCoreError(
                f"Relation '{name}' cannot relate a model to itself in ApkPy 1.3.1."
            )
        parent_key = parent.primary_key
        if parent_key is None:
            raise DataCoreError(
                f"Relation '{name}' parent '{parent.name}' requires a primary key."
            )
        if foreign_key not in child.fields:
            raise DataCoreError(
                f"Relation '{name}' references unknown field "
                f"'{child.name}.{foreign_key}'."
            )
        parent_field = parent.fields[parent_key]
        child_field = child.fields[foreign_key]
        if parent_field.kind != child_field.kind:
            raise DataCoreError(
                f"Relation '{name}' type mismatch: '{parent.name}.{parent_key}' "
                f"is {parent_field.kind}, but '{child.name}.{foreign_key}' "
                f"is {child_field.kind}."
            )
        action = str(on_delete or "restrict").strip().lower()
        if action not in {"restrict", "cascade", "set_null"}:
            raise DataCoreError(
                "on_delete must be 'restrict', 'cascade', or 'set_null'."
            )
        if action == "set_null" and (child_field.required or not child_field.optional):
            raise DataCoreError(
                f"Relation '{name}' uses set_null, so "
                f"'{child.name}.{foreign_key}' must be optional=True."
            )
        relation = RelationDef(
            str(name), parent, child, str(foreign_key), str(parent_as),
            str(children_as), action,
        )
        self._data_relations[relation.name] = relation
        return relation

    # -- filters and ordering --------------------------------------------------

    def _filter(self, operation, field_name, value=None):
        self._validate_identifier(field_name, "filter field")
        return FilterDef(operation, str(field_name), value)

    def eq(self, name, value): return self._filter("eq", name, value)
    def ne(self, name, value): return self._filter("ne", name, value)
    def gt(self, name, value): return self._filter("gt", name, value)
    def gte(self, name, value): return self._filter("gte", name, value)
    def lt(self, name, value): return self._filter("lt", name, value)
    def lte(self, name, value): return self._filter("lte", name, value)
    def contains(self, name, value): return self._filter("contains", name, value)
    def starts_with(self, name, value): return self._filter("starts_with", name, value)
    def ends_with(self, name, value): return self._filter("ends_with", name, value)
    def in_(self, name, values): return self._filter("in", name, list(values))
    def is_null(self, name, value=True): return self._filter("is_null", name, bool(value))

    def and_(self, *filters):
        return FilterDef("and", children=tuple(filters))

    def or_(self, *filters):
        return FilterDef("or", children=tuple(filters))

    def asc(self, name):
        self._validate_identifier(name, "order field")
        return OrderDef(str(name), "ASC")

    def desc(self, name):
        self._validate_identifier(name, "order field")
        return OrderDef(str(name), "DESC")

    # -- migration declarations ----------------------------------------------

    def migration(self, from_version, to_version, operations, destructive=False):
        if int(to_version) != int(from_version) + 1:
            raise DataCoreError(
                "Each migration must advance exactly one version "
                f"({from_version} -> {to_version} is not consecutive)."
            )
        normalized = tuple(operations or ())
        for operation in normalized:
            if not isinstance(operation, MigrationOperation):
                raise DataCoreError("Migration operations must be created with db.* helpers.")
        is_destructive = bool(destructive or any(op.destructive for op in normalized))
        if any(op.destructive for op in normalized) and not destructive:
            raise DataCoreError(
                "This migration contains destructive operations; pass destructive=True."
            )
        return MigrationDef(
            int(from_version), int(to_version), normalized, is_destructive,
        )

    def create_table(self, model):
        return MigrationOperation("create_table", model=model)

    def add_column(self, model, name, definition):
        self._validate_identifier(name, "column")
        if not isinstance(definition, FieldDef):
            raise DataCoreError("add_column() requires a db field declaration.")
        return MigrationOperation("add_column", model=model, name=name, field_def=definition)

    def rename_column(self, model, name, new_name):
        self._validate_identifier(name, "column")
        self._validate_identifier(new_name, "column")
        return MigrationOperation("rename_column", model=model, name=name, new_name=new_name)

    def create_index(self, model, name, fields, unique=False):
        self._validate_identifier(name, "index")
        return MigrationOperation(
            "create_index", model=model, name=name,
            fields=tuple(fields), unique=bool(unique),
        )

    def rename_index(self, model, name, new_name):
        self._validate_identifier(name, "index")
        self._validate_identifier(new_name, "index")
        return MigrationOperation(
            "rename_index", model=model, name=name, new_name=new_name,
        )

    def drop_index(self, model, name, destructive=True):
        self._validate_identifier(name, "index")
        return MigrationOperation(
            "drop_index", model=model, name=name, destructive=bool(destructive),
        )

    def rename_table(self, model, new_name):
        self._validate_identifier(new_name, "table")
        return MigrationOperation("rename_table", model=model, new_name=new_name)

    def sql(self, query, params=None, destructive=False):
        if not isinstance(query, str) or not query.strip():
            raise DataCoreError("db.sql() requires a non-empty SQL statement.")
        return MigrationOperation(
            "sql", query=query, params=tuple(params or ()),
            destructive=bool(destructive),
        )

    def schema(self, name, version, models, migrations=None, relations=None,
               database_name=None):
        source_file, source_line = self._source_location(2)
        self._validate_identifier(name, "schema")
        if self._data_schema is not None:
            raise DataCoreError(
                f"Only one typed schema is allowed; '{self._data_schema.name}' already exists."
            )
        version = int(version)
        if version < 1:
            raise DataCoreError("Schema version must be at least 1.")
        if database_name is not None:
            database_name = str(database_name).strip()
            if not database_name or any(part in database_name for part in ("/", "\\", "..")):
                raise DataCoreError("database_name must be a plain local filename.")
            if not database_name.endswith(".db"):
                database_name += ".db"
            self._path = os.path.join(os.path.dirname(self._path), database_name)
        normalized_models = tuple(models or ())
        if not normalized_models:
            raise DataCoreError("A schema must contain at least one model.")
        if len({model.name for model in normalized_models}) != len(normalized_models):
            raise DataCoreError("A schema cannot contain duplicate models.")
        model_set = set(id(model) for model in normalized_models)
        normalized_relations = tuple(relations or ())
        relation_names = set()
        relation_aliases = set()
        for relation in normalized_relations:
            if not isinstance(relation, RelationDef):
                raise DataCoreError("Invalid relation declaration.")
            if id(relation.parent) not in model_set or id(relation.child) not in model_set:
                raise DataCoreError(
                    f"Relation '{relation.name}' uses a model outside schema '{name}'."
                )
            if relation.name in relation_names:
                raise DataCoreError(f"Duplicate relation '{relation.name}' in schema '{name}'.")
            relation_names.add(relation.name)
            for alias in (relation.parent_as, relation.children_as):
                if alias in relation_aliases:
                    raise DataCoreError(
                        f"Duplicate relation alias '{alias}' in schema '{name}'."
                    )
                relation_aliases.add(alias)
        normalized_migrations = tuple(migrations or ())
        by_from = {}
        for migration in normalized_migrations:
            if not isinstance(migration, MigrationDef):
                raise DataCoreError("Invalid migration declaration.")
            if migration.from_version in by_from:
                raise DataCoreError(
                    f"Two migrations start at version {migration.from_version}."
                )
            by_from[migration.from_version] = migration
        if normalized_migrations:
            first = min(item.from_version for item in normalized_migrations)
            cursor = first
            while cursor < version:
                migration = by_from.get(cursor)
                if migration is None:
                    raise DataCoreError(
                        f"Missing migration path {cursor} -> {cursor + 1} for schema '{name}'."
                    )
                cursor = migration.to_version
        payload = {
            "name": name,
            "models": [model.describe() for model in normalized_models],
            "relations": [relation.describe() for relation in normalized_relations],
        }
        schema_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        schema = SchemaDef(
            owner=self, name=str(name), version=version,
            models=normalized_models, relations=normalized_relations,
            migrations=normalized_migrations,
            schema_hash=schema_hash, source_file=source_file,
            source_line=source_line,
        )
        self._data_schema = schema
        try:
            self._ensure_schema(schema)
        except Exception as error:
            self._data_schema = None
            raise DataCoreError(
                f"{source_file}:{source_line}: schema '{name}' could not be opened: {error}. "
                "Check the version, migration path, and field declarations."
            ) from error
        return schema

    # -- public transaction ---------------------------------------------------

    def transaction(self, run, on_result=None, on_error=None):
        if not callable(run):
            raise DataCoreError("db.transaction(run=...) requires a function.")

        def work():
            connection = self._connect()
            tx = TransactionContext(self, connection)
            try:
                connection.execute("BEGIN IMMEDIATE")
                result = run(tx)
                connection.commit()
                return result, set(tx._dirty_models)
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        def completed(payload):
            result, dirty = payload
            if dirty:
                self._data_invalidate(dirty)
            if on_result:
                on_result(result)

        return self._submit(work, completed, on_error)

    # -- asynchronous model entrypoints --------------------------------------

    def _data_insert(self, model, values, on_result, on_error):
        return self._submit_connection(
            lambda connection: self._insert_sync(connection, model, values),
            on_result, on_error, invalidates={model.name},
        )

    def _data_insert_many(self, model, items, on_result, on_error):
        return self._submit_connection(
            lambda connection: self._insert_many_sync(connection, model, items),
            on_result, on_error, invalidates={model.name},
        )

    def _data_get(self, model, item_id, on_result, on_error, include=None):
        return self._submit_connection(
            lambda connection: self._get_sync(
                connection, model, item_id, include or [],
            ),
            on_result, on_error, result_kind="json_object",
        )

    def _data_find(self, model, filters, order_by, limit, offset, on_result,
                   on_error, include=None):
        return self._submit_connection(
            lambda connection: self._find_sync(
                connection, model, filters, order_by, limit, offset,
                include or [],
            ),
            on_result, on_error, result_kind="rows",
        )

    def _data_update(self, model, values, filters, on_result, on_error):
        return self._submit_connection(
            lambda connection: self._update_sync(connection, model, values, filters),
            on_result, on_error, invalidates={model.name},
        )

    def _data_delete(self, model, filters, on_result, on_error):
        return self._submit_connection(
            lambda connection: self._delete_sync(connection, model, filters),
            on_result, on_error, invalidates={model.name},
        )

    def _data_count(self, model, filters, on_result, on_error):
        return self._submit_connection(
            lambda connection: self._count_sync(connection, model, filters),
            on_result, on_error,
        )

    # -- synchronous data operations -----------------------------------------

    def _insert_sync(self, connection, model, values):
        prepared = self._prepare_values(model, values, creating=True)
        if not prepared:
            cursor = connection.execute(f'INSERT INTO "{model.name}" DEFAULT VALUES')
        else:
            names = list(prepared)
            placeholders = ", ".join("?" for _ in names)
            columns = ", ".join(f'"{name}"' for name in names)
            cursor = connection.execute(
                f'INSERT INTO "{model.name}" ({columns}) VALUES ({placeholders})',
                [prepared[name] for name in names],
            )
        return int(cursor.lastrowid)

    def _insert_many_sync(self, connection, model, items):
        materialized = list(items or ())
        if not materialized:
            return 0
        connection.execute("SAVEPOINT apkpy_insert_many")
        try:
            for values in materialized:
                self._insert_sync(connection, model, values)
            connection.execute("RELEASE SAVEPOINT apkpy_insert_many")
            return len(materialized)
        except Exception:
            connection.execute("ROLLBACK TO SAVEPOINT apkpy_insert_many")
            connection.execute("RELEASE SAVEPOINT apkpy_insert_many")
            raise

    def _get_sync(self, connection, model, item_id, include=None):
        primary_key = model.primary_key
        if primary_key is None:
            raise DataCoreError(f"Model '{model.name}' has no primary key for get().")
        row = connection.execute(
            f'SELECT * FROM "{model.name}" WHERE "{primary_key}" = ? LIMIT 1',
            (self._coerce_value(model, primary_key, item_id),),
        ).fetchone()
        result = self._decode_row(model, row) if row is not None else None
        if result is not None and include:
            self._hydrate_includes(connection, model, [result], include)
        return result

    def _find_sync(self, connection, model, filters, order_by, limit, offset,
                   include=None):
        where_sql, params = self._compile_filters(model, filters)
        order_sql = self._compile_orders(model, order_by)
        sql = f'SELECT * FROM "{model.name}"{where_sql}{order_sql}'
        if limit is not None:
            limit = int(limit)
            offset = int(offset or 0)
            if limit < 0 or offset < 0:
                raise DataCoreError("limit and offset cannot be negative.")
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset:
            raise DataCoreError("offset requires limit.")
        rows = connection.execute(sql, params).fetchall()
        result = [self._decode_row(model, row) for row in rows]
        if include:
            self._hydrate_includes(connection, model, result, include)
        return result

    def _hydrate_includes(self, connection, model, rows, include):
        relations = self._resolve_includes(model, include)
        if not rows:
            return rows
        for relation, direction, alias in relations:
            if direction == "children":
                parent_key = relation.parent.primary_key
                keys = [row.get(parent_key) for row in rows if row.get(parent_key) is not None]
                related = self._fetch_related_rows(
                    connection, relation.child, relation.foreign_key, keys,
                )
                grouped = {}
                for child_row in related:
                    grouped.setdefault(child_row.get(relation.foreign_key), []).append(child_row)
                for row in rows:
                    row[alias] = grouped.get(row.get(parent_key), [])
            else:
                foreign_values = [
                    row.get(relation.foreign_key) for row in rows
                    if row.get(relation.foreign_key) is not None
                ]
                parent_key = relation.parent.primary_key
                related = self._fetch_related_rows(
                    connection, relation.parent, parent_key, foreign_values,
                )
                mapped = {row.get(parent_key): row for row in related}
                for row in rows:
                    row[alias] = mapped.get(row.get(relation.foreign_key))
        return rows

    def _fetch_related_rows(self, connection, model, field_name, values):
        unique = list(dict.fromkeys(values))
        if not unique:
            return []
        result = []
        # Keep below SQLite's common 999-variable limit.
        for start in range(0, len(unique), 900):
            chunk = unique[start:start + 900]
            placeholders = ", ".join("?" for _ in chunk)
            sql = (
                f'SELECT * FROM "{model.name}" WHERE "{field_name}" '
                f'IN ({placeholders})'
            )
            primary_key = model.primary_key
            if primary_key:
                sql += f' ORDER BY "{primary_key}" ASC'
            fetched = connection.execute(sql, chunk).fetchall()
            result.extend(self._decode_row(model, row) for row in fetched)
        return result

    def _update_sync(self, connection, model, values, filters):
        prepared = self._prepare_values(model, values, creating=False)
        if not prepared:
            return 0
        where_sql, params = self._compile_filters(model, filters)
        assignments = ", ".join(f'"{name}" = ?' for name in prepared)
        cursor = connection.execute(
            f'UPDATE "{model.name}" SET {assignments}{where_sql}',
            list(prepared.values()) + params,
        )
        return int(cursor.rowcount)

    def _delete_sync(self, connection, model, filters):
        where_sql, params = self._compile_filters(model, filters)
        cursor = connection.execute(
            f'DELETE FROM "{model.name}"{where_sql}', params,
        )
        return int(cursor.rowcount)

    def _count_sync(self, connection, model, filters):
        where_sql, params = self._compile_filters(model, filters)
        row = connection.execute(
            f'SELECT COUNT(*) AS apkpy_count FROM "{model.name}"{where_sql}', params,
        ).fetchone()
        return int(row["apkpy_count"])

    # -- relations and observation ------------------------------------------

    def _resolve_includes(self, model, include):
        aliases = list(include or ())
        resolved = []
        seen = set()
        for alias in aliases:
            if not isinstance(alias, str) or not alias or "." in alias:
                raise DataCoreError(
                    "include accepts one-level relation aliases such as "
                    "include=['notes']; nested includes are not supported."
                )
            if alias in seen:
                continue
            seen.add(alias)
            match = None
            for relation in getattr(self._data_schema, "relations", ()):
                if relation.parent is model and relation.children_as == alias:
                    match = (relation, "children", alias)
                    break
                if relation.child is model and relation.parent_as == alias:
                    match = (relation, "parent", alias)
                    break
            if match is None:
                raise DataCoreError(
                    f"Model '{model.name}' has no relation alias '{alias}'."
                )
            resolved.append(match)
        return resolved

    def _data_query_dependencies(self, model, include):
        dependencies = {model.name}
        for relation, direction, _alias in self._resolve_includes(model, include):
            dependencies.add(
                relation.child.name if direction == "children" else relation.parent.name
            )
        return dependencies

    def _data_observe(self, model, filters, order_by, limit, offset, include,
                      screen, on_change, on_error):
        if screen is None:
            raise DataCoreError("observe(screen=...) requires an ApkPy screen.")
        if not callable(on_change):
            raise DataCoreError("observe(on_change=...) requires a callback.")
        if on_error is not None and not callable(on_error):
            raise DataCoreError("observe(on_error=...) expects a callback.")
        subscription = QuerySubscription(
            self, model, filters=filters, order_by=order_by, limit=limit,
            offset=offset, include=include, screen=screen,
            on_change=on_change, on_error=on_error,
        )
        with self._data_observer_lock:
            self._data_observers.append(subscription)
        return subscription

    def _data_remove_observer(self, subscription):
        with self._data_observer_lock:
            try:
                self._data_observers.remove(subscription)
            except ValueError:
                pass

    def _data_lifecycle(self, screen, event):
        with self._data_observer_lock:
            observers = [item for item in self._data_observers if item.screen is screen]
        for observer in observers:
            if event == "on_resume":
                observer.resume()
            elif event == "on_pause":
                observer.pause()
            elif event == "on_destroy":
                observer.close()

    def _data_expand_invalidations(self, models):
        """Which observers a change has to wake, cascades included.

        Read the relations once and a chain of two only resolved when they
        happened to be declared parent first; the rule is in data_rules now
        and repeats until nothing new appears, like the generated Java always
        did.
        """
        if models is None:
            return None
        relations = [(relation.parent.name, relation.child.name,
                      relation.on_delete)
                     for relation in getattr(self._data_schema, "relations", ())]
        return data_rules.invalidated_by(models, relations)

    def _data_invalidate(self, models=None):
        # Observers belong to screens. A write made inside a job invalidates
        # them from the job's own thread, and their re-query must not count as
        # part of the body: it would run inline, and an on_change that sets a
        # label would be refused as if the job had done it.
        with job_rules.outside_job():
            expanded = self._data_expand_invalidations(models)
            with self._data_observer_lock:
                observers = list(self._data_observers)
            for observer in observers:
                observer.invalidate(expanded)

    # -- validation and SQL compilation --------------------------------------

    def _prepare_values(self, model, values, creating):
        if not isinstance(values, dict):
            raise DataCoreError(f"Values for '{model.name}' must be a dictionary.")
        unknown = sorted(set(values) - set(model.fields))
        if unknown:
            raise DataCoreError(
                f"Model '{model.name}' has no field(s): {', '.join(unknown)}."
            )
        prepared = {}
        for name, definition in model.fields.items():
            if name in values:
                value = values[name]
            elif not creating:
                continue
            elif definition.default is not _MISSING:
                value = self._resolve_default(definition.default)
            elif definition.auto_increment:
                continue
            elif definition.required:
                raise DataCoreError(f"Required field '{model.name}.{name}' is missing.")
            else:
                value = None
            prepared[name] = self._coerce_value(model, name, value)
        return prepared

    def _coerce_value(self, model, name, value):
        definition = model.fields[name]
        if value is None:
            if definition.required and not definition.auto_increment:
                raise DataCoreError(f"Field '{model.name}.{name}' cannot be null.")
            return None
        if definition.kind == "integer":
            if isinstance(value, bool):
                value = int(value)
            elif isinstance(value, str):
                try:
                    value = int(value.strip())
                except ValueError as error:
                    raise DataCoreError(
                        f"Field '{model.name}.{name}' expects an integer."
                    ) from error
            elif not data_rules.is_whole_number(value):
                raise DataCoreError(
                    f"Field '{model.name}.{name}' expects an integer, "
                    f"and {value!r} is not a whole number."
                )
            value = int(value)
        elif definition.kind == "real":
            if isinstance(value, str):
                try:
                    value = float(value.strip())
                except ValueError as error:
                    raise DataCoreError(
                        f"Field '{model.name}.{name}' expects a real number."
                    ) from error
            elif isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DataCoreError(f"Field '{model.name}.{name}' expects a real number.")
            if not data_rules.is_real_number(value):
                raise DataCoreError(
                    f"Field '{model.name}.{name}' expects a real number, "
                    f"and {value!r} is not a finite one."
                )
            value = float(value)
        elif definition.kind == "text":
            if not isinstance(value, str):
                raise DataCoreError(f"Field '{model.name}.{name}' expects text.")
        elif definition.kind == "boolean":
            if isinstance(value, str) and value.strip().lower() in ("true", "false", "1", "0"):
                value = value.strip().lower() in ("true", "1")
            elif isinstance(value, int) and value in (0, 1):
                value = bool(value)
            if not isinstance(value, bool):
                raise DataCoreError(f"Field '{model.name}.{name}' expects a boolean.")
            value = 1 if value else 0
        elif definition.kind == "datetime":
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                value = int(value.timestamp() * 1000)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                value = int(value)
            elif isinstance(value, str):
                try:
                    value = int(value.strip())
                except ValueError as error:
                    raise DataCoreError(
                        f"Field '{model.name}.{name}' expects datetime or epoch milliseconds."
                    ) from error
            else:
                raise DataCoreError(
                    f"Field '{model.name}.{name}' expects datetime or epoch milliseconds."
                )
        elif definition.kind == "json":
            if isinstance(value, str):
                try:
                    json.loads(value)
                except Exception as error:
                    raise DataCoreError(
                        f"Field '{model.name}.{name}' contains invalid JSON: {error}."
                    ) from error
            else:
                try:
                    value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                except Exception as error:
                    raise DataCoreError(
                        f"Field '{model.name}.{name}' is not JSON serializable: {error}."
                    ) from error
        elif definition.kind == "blob":
            if isinstance(value, str):
                try:
                    value = data_rules.blob_from_text(value)
                except Exception as error:
                    raise DataCoreError(
                        f"Field '{model.name}.{name}' expects bytes or Base64 text."
                    ) from error
            if not isinstance(value, (bytes, bytearray, memoryview)):
                raise DataCoreError(f"Field '{model.name}.{name}' expects bytes.")
            value = bytes(value)
        if definition.min_value is not None and value < definition.min_value:
            raise DataCoreError(
                f"Field '{model.name}.{name}' must be at least {definition.min_value}."
            )
        if definition.max_value is not None and value > definition.max_value:
            raise DataCoreError(
                f"Field '{model.name}.{name}' must be at most {definition.max_value}."
            )
        if definition.max_length is not None and (
                data_rules.text_length(value) if isinstance(value, str)
                else len(value)) > definition.max_length:
            raise DataCoreError(
                f"Field '{model.name}.{name}' exceeds max_length={definition.max_length}."
            )
        comparable = bool(value) if definition.kind == "boolean" else value
        if not data_rules.matches_choice(comparable, definition.choices):
            raise DataCoreError(
                f"Field '{model.name}.{name}' must be one of {list(definition.choices)}."
            )
        return value

    def _compile_filters(self, model, filters):
        if filters is None:
            filters = []
        if isinstance(filters, FilterDef):
            filters = [filters]
        parts = []
        params = []
        for definition in filters:
            sql, values = self._compile_filter(model, definition)
            parts.append(sql)
            params.extend(values)
        return ((" WHERE " + " AND ".join(parts)) if parts else ""), params

    def _compile_filter(self, model, definition):
        if not isinstance(definition, FilterDef):
            raise DataCoreError("Filters must be created with db.eq(), db.and_(), etc.")
        operation = definition.operation
        if operation in ("and", "or"):
            if not definition.children:
                raise DataCoreError(f"db.{operation}_() requires at least one filter.")
            compiled = [self._compile_filter(model, child) for child in definition.children]
            joiner = " AND " if operation == "and" else " OR "
            return "(" + joiner.join(item[0] for item in compiled) + ")", [
                value for item in compiled for value in item[1]
            ]
        name = definition.field_name
        if name not in model.fields:
            raise DataCoreError(f"Unknown filter field '{model.name}.{name}'.")
        column = f'"{name}"'
        if operation == "is_null":
            return f"{column} IS {'NULL' if definition.value else 'NOT NULL'}", []
        if operation == "in":
            values = list(definition.value or ())
            if not values:
                return "0", []
            coerced = [self._coerce_value(model, name, value) for value in values]
            return f"{column} IN ({', '.join('?' for _ in coerced)})", coerced
        operators = {
            "eq": "=", "ne": "!=", "gt": ">", "gte": ">=",
            "lt": "<", "lte": "<=",
        }
        if operation in operators:
            if definition.value is None and operation in ("eq", "ne"):
                return f"{column} IS {'NOT ' if operation == 'ne' else ''}NULL", []
            if definition.value is None:
                raise DataCoreError(
                    f"db.{operation}('{name}', None) cannot be compared with "
                    f"nothing. Use db.is_null('{name}') to ask for the empty "
                    f"rows, or leave this filter out."
                )
            return (
                f"{column} {operators[operation]} ?",
                [self._coerce_value(model, name, definition.value)],
            )
        if operation in ("contains", "starts_with", "ends_with"):
            if model.fields[name].kind != "text":
                raise DataCoreError(f"db.{operation}() requires a text field.")
            value = data_rules.like_pattern(operation, definition.value)
            return (f"{column} LIKE ? ESCAPE '{data_rules.LIKE_ESCAPE}'",
                    [value])
        raise DataCoreError(f"Unknown filter operation '{operation}'.")

    def _compile_orders(self, model, orders):
        if isinstance(orders, OrderDef):
            orders = [orders]
        parts = []
        for order in orders or ():
            if not isinstance(order, OrderDef):
                raise DataCoreError("order_by entries must use db.asc() or db.desc().")
            if order.field_name not in model.fields:
                raise DataCoreError(
                    f"Unknown order field '{model.name}.{order.field_name}'."
                )
            parts.append(f'"{order.field_name}" {order.direction}')
        return (" ORDER BY " + ", ".join(parts)) if parts else ""

    # -- schema runtime -------------------------------------------------------

    def _connect(self):
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self, schema):
        connection = self._connect()
        backup_path = None
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS apkpy_schema_meta ("
                "id INTEGER PRIMARY KEY CHECK(id = 1), "
                "schema_name TEXT NOT NULL, version INTEGER NOT NULL, "
                "schema_hash TEXT NOT NULL, history TEXT NOT NULL)"
            )
            meta = connection.execute(
                "SELECT schema_name, version, schema_hash, history "
                "FROM apkpy_schema_meta WHERE id = 1"
            ).fetchone()
            if meta is None:
                for model in schema.models:
                    self._create_model(connection, model)
                connection.execute(
                    "INSERT INTO apkpy_schema_meta "
                    "(id, schema_name, version, schema_hash, history) VALUES (1, ?, ?, ?, ?)",
                    (schema.name, schema.version, schema.schema_hash, "[]"),
                )
                connection.execute(f"PRAGMA user_version = {schema.version}")
                connection.commit()
                return
            current_version = int(meta["version"])
            if meta["schema_name"] != schema.name:
                raise DataCoreError(
                    f"Database belongs to schema '{meta['schema_name']}', not '{schema.name}'."
                )
            if current_version > schema.version:
                raise DataCoreError(
                    f"Downgrade {current_version} -> {schema.version} is refused to protect data."
                )
            if current_version == schema.version:
                if meta["schema_hash"] != schema.schema_hash:
                    raise DataCoreError(
                        "The schema changed without increasing its version. "
                        f"Increase version above {schema.version} and add a migration."
                    )
                connection.commit()
                return
            migration_map = {item.from_version: item for item in schema.migrations}
            path = []
            cursor = current_version
            while cursor < schema.version:
                migration = migration_map.get(cursor)
                if migration is None:
                    raise DataCoreError(
                        f"Missing migration {cursor} -> {cursor + 1}."
                    )
                path.append(migration)
                cursor = migration.to_version
            if any(item.destructive for item in path):
                connection.execute("PRAGMA wal_checkpoint(FULL)")
                connection.commit()
                connection.close()
                backup_path = self._backup_database(current_version)
                connection = self._connect()
            history = json.loads(meta["history"] or "[]")
            connection.execute("BEGIN IMMEDIATE")
            for migration in path:
                self._apply_migration(connection, migration)
                history.append({
                    "from": migration.from_version,
                    "to": migration.to_version,
                    "applied_at": int(datetime.now(timezone.utc).timestamp() * 1000),
                })
            connection.execute(
                "UPDATE apkpy_schema_meta SET version = ?, schema_hash = ?, history = ? "
                "WHERE id = 1",
                (schema.version, schema.schema_hash, json.dumps(history)),
            )
            connection.execute(f"PRAGMA user_version = {schema.version}")
            connection.commit()
        except Exception:
            try:
                connection.rollback()
            except Exception:
                pass
            try:
                connection.close()
            except Exception:
                pass
            if backup_path:
                shutil.copy2(backup_path, self._path)
            raise
        finally:
            try:
                connection.close()
            except Exception:
                pass

    def _create_model(self, connection, model):
        fields = []
        for name, definition in model.fields.items():
            fields.append(self._column_sql(name, definition, allow_primary_key=True))
        for relation in getattr(self._data_schema, "relations", ()):
            if relation.child is not model:
                continue
            parent_key = relation.parent.primary_key
            action = {
                "restrict": "RESTRICT",
                "cascade": "CASCADE",
                "set_null": "SET NULL",
            }[relation.on_delete]
            fields.append(
                f'FOREIGN KEY ("{relation.foreign_key}") REFERENCES '
                f'"{relation.parent.name}" ("{parent_key}") ON DELETE {action}'
            )
        connection.execute(
            f'CREATE TABLE IF NOT EXISTS "{model.name}" ({", ".join(fields)})'
        )
        for index in model.indexes:
            self._execute_create_index(connection, model.name, index)

    def _column_sql(self, name, definition, allow_primary_key=False):
        sql = f'"{name}" {self._SQL_TYPES[definition.kind]}'
        if allow_primary_key and definition.primary_key:
            sql += " PRIMARY KEY"
            if definition.auto_increment:
                sql += " AUTOINCREMENT"
        if definition.required:
            sql += " NOT NULL"
        if definition.unique:
            sql += " UNIQUE"
        if definition.default is not _MISSING:
            default = self._resolve_default(definition.default)
            coerced = self._coerce_default(definition, default)
            sql += " DEFAULT " + self._sql_literal(coerced)
        checks = []
        if definition.min_value is not None:
            checks.append(f'"{name}" >= {definition.min_value}')
        if definition.max_value is not None:
            checks.append(f'"{name}" <= {definition.max_value}')
        if definition.max_length is not None:
            checks.append(f'length("{name}") <= {int(definition.max_length)}')
        if definition.choices:
            choices = ", ".join(self._sql_literal(item) for item in definition.choices)
            checks.append(f'"{name}" IN ({choices})')
        if checks:
            sql += " CHECK (" + " AND ".join(checks) + ")"
        return sql

    def _apply_migration(self, connection, migration):
        for operation in migration.operations:
            model_name = getattr(operation.model, "name", operation.model)
            if operation.operation == "create_table":
                self._create_model(connection, operation.model)
            elif operation.operation == "add_column":
                connection.execute(
                    f'ALTER TABLE "{model_name}" ADD COLUMN '
                    + self._column_sql(operation.name, operation.field_def)
                )
            elif operation.operation == "rename_column":
                connection.execute(
                    f'ALTER TABLE "{model_name}" RENAME COLUMN '
                    f'"{operation.name}" TO "{operation.new_name}"'
                )
            elif operation.operation == "create_index":
                self._execute_create_index(
                    connection, model_name,
                    IndexDef(operation.name, operation.fields, operation.unique),
                )
            elif operation.operation == "rename_index":
                row = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='index' AND name=?",
                    (operation.name,),
                ).fetchone()
                if row is None or not row["sql"]:
                    raise DataCoreError(f"Index '{operation.name}' does not exist.")
                connection.execute(f'DROP INDEX "{operation.name}"')
                create_sql = re.sub(
                    r"(?i)(CREATE\s+(?:UNIQUE\s+)?INDEX\s+)\S+",
                    lambda match: match.group(1) + f'"{operation.new_name}"',
                    row["sql"], count=1,
                )
                connection.execute(create_sql)
            elif operation.operation == "drop_index":
                connection.execute(f'DROP INDEX "{operation.name}"')
            elif operation.operation == "rename_table":
                connection.execute(
                    f'ALTER TABLE "{model_name}" RENAME TO "{operation.new_name}"'
                )
            elif operation.operation == "sql":
                connection.execute(operation.query, operation.params)
            else:
                raise DataCoreError(f"Unsupported migration operation '{operation.operation}'.")

    def _execute_create_index(self, connection, model_name, index):
        columns = ", ".join(f'"{name}"' for name in index.fields)
        unique = "UNIQUE " if index.unique else ""
        connection.execute(
            f'CREATE {unique}INDEX IF NOT EXISTS "{index.name}" '
            f'ON "{model_name}" ({columns})'
        )

    def _backup_database(self, version):
        backup = f"{self._path}.backup-v{version}"
        if os.path.exists(self._path):
            shutil.copy2(self._path, backup)
        else:
            open(backup, "ab").close()
        return backup

    # -- async/callback plumbing ---------------------------------------------

    def _submit_connection(self, operation, on_result, on_error,
                           result_kind=None, invalidates=None):
        def work():
            connection = self._connect()
            try:
                result = operation(connection)
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        def completed(result):
            if invalidates:
                self._data_invalidate(invalidates)
            if on_result:
                on_result(result)

        return self._submit(
            work, completed if (invalidates or on_result) else None,
            on_error, result_kind,
        )

    def _shape_result(self, result, result_kind):
        if result_kind == "rows":
            return self._json_rows(result)
        if result_kind == "json_object":
            # A typed ``get()`` is a Python object in the Previewer,
            # matching the field access supported by the generated
            # Android callback (``row["field"]``).  Returning a JSON
            # string here made the first character accessible instead
            # of the requested field and broke Preview/Android parity.
            return "" if result is None else result
        return result

    def _run_here(self, operation, on_result, on_error, result_kind=None):
        """Run now, on this thread, and answer before returning.

        Inside a background job the body is already off the interface thread,
        and on the phone its Worker answers before the next line
        (``ApkpyDataExecutor.runHere``).  Handing the operation to the data
        thread here would let the job run on -- or finish -- before its own
        insert had happened.  The callback runs on the job's thread, as part of
        the body, so what it may call is what the body may call; an error it
        raises is the body's error, exactly as in the Worker.
        """
        future = Future()
        try:
            result = self._shape_result(operation(), result_kind)
        except Exception as error:
            future.set_exception(error)
            message = format_exception(error, context="Data Core operation").strip()
            if on_error:
                on_error(message)
            else:
                print(message)
            return future
        future.set_result(result)
        if on_result:
            on_result(result)
        return future

    def _submit(self, operation, on_result, on_error, result_kind=None):
        if job_rules.inside_job():
            return self._run_here(operation, on_result, on_error, result_kind)
        executor = self._executor()
        future = executor.submit(operation)

        def completed(done):
            try:
                result = self._shape_result(done.result(), result_kind)
                if on_result:
                    self._dispatch(lambda: on_result(result))
            except Exception as error:
                # Callbacks still receive text, but now it contains the model,
                # source line, likely correction and a stable diagnostic code.
                message = format_exception(error, context="Data Core operation").strip()
                if on_error:
                    self._dispatch(lambda message=message: on_error(message))
                else:
                    print(message)

        future.add_done_callback(completed)
        return future

    def _executor(self):
        with self._data_executor_lock:
            if self._data_executor is None:
                self._data_executor = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="apkpy-data"
                )
            return self._data_executor

    @staticmethod
    def _dispatch(callback):
        try:
            from apkpy_lib import ui as ui_module
            app = getattr(ui_module, "_app", None)
            # Do not instantiate Tk merely because a headless test completed.
            # The lazy wrapper exposes its already-created instance directly.
            instance = getattr(app, "_instance", app)
            root = getattr(instance, "root", None) if instance is not None else None
            if root is not None:
                root.after(0, callback)
                return
        except Exception:
            pass
        callback()

    @staticmethod
    def _json_rows(rows):
        payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
        try:
            from apkpy_lib.ui import JsonRows
            return JsonRows(payload)
        except Exception:
            return rows

    # -- small helpers --------------------------------------------------------

    @staticmethod
    def _validate_identifier(name, label):
        if not isinstance(name, str) or not _IDENTIFIER.match(name):
            raise DataCoreError(
                f"Invalid {label} name {name!r}; use letters, digits and underscores."
            )

    @staticmethod
    def _source_location(depth):
        frame = inspect.stack()[depth]
        return os.path.abspath(frame.filename), int(frame.lineno)

    @staticmethod
    def _resolve_default(value):
        if isinstance(value, NowValue):
            return int(datetime.now(timezone.utc).timestamp() * 1000)
        return value

    @staticmethod
    def _coerce_default(definition, value):
        if definition.kind == "boolean": return 1 if value else 0
        if definition.kind == "json" and not isinstance(value, str):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if definition.kind == "datetime" and isinstance(value, datetime):
            if value.tzinfo is None: value = value.replace(tzinfo=timezone.utc)
            return int(value.timestamp() * 1000)
        if isinstance(value, bytes): return value
        return value

    @staticmethod
    def _sql_literal(value):
        if value is None: return "NULL"
        if isinstance(value, bool): return "1" if value else "0"
        if isinstance(value, (int, float)): return str(value)
        if isinstance(value, bytes): return "X'" + value.hex() + "'"
        return "'" + str(value).replace("'", "''") + "'"

    @staticmethod
    def _decode_row(model, row):
        result = dict(row)
        for name, definition in model.fields.items():
            value = result.get(name)
            if value is None:
                continue
            if definition.kind == "boolean":
                result[name] = bool(value)
            elif definition.kind == "json":
                try:
                    result[name] = json.loads(value)
                except Exception:
                    result[name] = value
            elif definition.kind == "blob":
                # JSON callbacks cannot carry raw bytes.  Base64 is what the
                # phone writes and what normalize() reads back, so both sides
                # spell the same bytes the same way -- this used to be hex here
                # and Base64 there, with a comment claiming they matched.
                result[name] = data_rules.blob_to_text(value)
        return result


__all__ = [
    "DataCoreError", "DataCoreMixin", "FieldDef", "IndexDef",
    "FilterDef", "OrderDef", "ModelDef", "SchemaDef", "MigrationDef",
    "MigrationOperation", "TransactionContext", "NowValue",
    "RelationDef", "QuerySubscription",
]
