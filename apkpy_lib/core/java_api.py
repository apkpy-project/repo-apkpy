# -*- coding: utf-8 -*-
"""What a Java class looks like from outside, read from the class files of a jar.

A ``@native`` function written in Python calls Android classes, and the build
has to know -- for ``vibrator.vibrate(ms)`` -- that ``Vibrator`` has a
``vibrate(long)``, what it answers and what it can throw. ``android.jar``, the
file every app is compiled against, holds each public class with exactly that;
this module reads it. Nothing in the jar is executed: the classes in it are
stubs, and all that is used is their shape.

The same folder of the SDK has ``data/api-versions.xml``, which says in which
Android version each class and member arrived. :class:`ApiLevels` reads it, so
a call to something newer than the oldest phone the app runs on can be caught
while the app is built instead of on that phone.
"""
from __future__ import annotations

import os
import struct
import zipfile
from dataclasses import dataclass

__all__ = [
    "Prim", "Cls", "Arr", "TVar", "Wild", "NULL", "OBJECT", "STRING",
    "JavaClass", "JavaField", "JavaMethod", "Library", "ApiLevels",
    "PRIMITIVES", "BOXES", "UNBOXES", "source", "erase", "substitute",
    "find_android_jar", "android_version",
]

PRIMITIVES = ("boolean", "byte", "char", "short", "int", "long", "float",
              "double", "void")
_DESCRIPTOR_PRIMITIVES = {"Z": "boolean", "B": "byte", "C": "char",
                          "S": "short", "I": "int", "J": "long",
                          "F": "float", "D": "double", "V": "void"}
BOXES = {"boolean": "java.lang.Boolean", "byte": "java.lang.Byte",
         "char": "java.lang.Character", "short": "java.lang.Short",
         "int": "java.lang.Integer", "long": "java.lang.Long",
         "float": "java.lang.Float", "double": "java.lang.Double"}
UNBOXES = {box: prim for prim, box in BOXES.items()}

ACC_PUBLIC = 0x0001
ACC_PROTECTED = 0x0004
ACC_STATIC = 0x0008
ACC_FINAL = 0x0010
ACC_BRIDGE = 0x0040
ACC_VARARGS = 0x0080
ACC_INTERFACE = 0x0200
ACC_ABSTRACT = 0x0400
ACC_SYNTHETIC = 0x1000
ACC_ENUM = 0x4000


# --- types -------------------------------------------------------------------

@dataclass(frozen=True)
class Prim:
    name: str


@dataclass(frozen=True)
class Cls:
    """A class or interface by its binary name: dots for packages, ``$`` for a
    class written inside another (``android.os.Build$VERSION``)."""
    name: str
    args: tuple = ()


@dataclass(frozen=True)
class Arr:
    elem: object


@dataclass(frozen=True)
class TVar:
    name: str


@dataclass(frozen=True)
class Wild:
    """``? extends X`` (kind ``+``), ``? super X`` (``-``) or ``?`` (``*``)."""
    kind: str
    bound: object = None


class _Null:
    def __repr__(self):                                    # pragma: no cover
        return "NULL"


NULL = _Null()
OBJECT = Cls("java.lang.Object")
STRING = Cls("java.lang.String")


def source(kind):
    """The type as it is written in Java source."""
    if isinstance(kind, Prim):
        return kind.name
    if isinstance(kind, Arr):
        return source(kind.elem) + "[]"
    if isinstance(kind, Cls):
        name = kind.name.replace("$", ".")
        if name.startswith("java.lang.") and name.count(".") == 2:
            name = name[10:]            # String, Object: imported by Java itself
        if kind.args and not any(_has_variable(arg) for arg in kind.args):
            return "%s<%s>" % (name, ", ".join(source(arg) for arg in kind.args))
        return name
    if isinstance(kind, Wild):
        if kind.kind == "+":
            return "? extends " + source(kind.bound)
        if kind.kind == "-":
            return "? super " + source(kind.bound)
        return "?"
    return "java.lang.Object"


def _has_variable(kind):
    if isinstance(kind, TVar):
        return True
    if isinstance(kind, Arr):
        return _has_variable(kind.elem)
    if isinstance(kind, Cls):
        return any(_has_variable(arg) for arg in kind.args)
    if isinstance(kind, Wild):
        return kind.bound is not None and _has_variable(kind.bound)
    return False


def substitute(kind, bindings):
    """The type with every variable in ``bindings`` replaced."""
    if not bindings:
        return kind
    if isinstance(kind, TVar):
        return bindings.get(kind.name, kind)
    if isinstance(kind, Arr):
        return Arr(substitute(kind.elem, bindings))
    if isinstance(kind, Cls) and kind.args:
        return Cls(kind.name, tuple(substitute(arg, bindings) for arg in kind.args))
    if isinstance(kind, Wild) and kind.bound is not None:
        return Wild(kind.kind, substitute(kind.bound, bindings))
    return kind


def erase(kind, bounds=None):
    """What is left of a type once nothing is known about its variables: a
    variable becomes its bound, and a class that still names one goes raw."""
    bounds = bounds or {}
    if isinstance(kind, TVar):
        bound = bounds.get(kind.name, OBJECT)
        return erase(bound, {k: v for k, v in bounds.items() if k != kind.name})
    if isinstance(kind, Arr):
        return Arr(erase(kind.elem, bounds))
    if isinstance(kind, Wild):
        if kind.kind == "+" and kind.bound is not None:
            return erase(kind.bound, bounds)
        return OBJECT
    if isinstance(kind, Cls) and kind.args:
        if any(_has_variable(arg) for arg in kind.args):
            return Cls(kind.name)
        return kind
    return kind


# --- signatures --------------------------------------------------------------

class _Reader:
    """A descriptor or a generic signature, read left to right."""

    def __init__(self, text):
        self.text = text
        self.at = 0

    def peek(self):
        return self.text[self.at] if self.at < len(self.text) else ""

    def take(self):
        char = self.text[self.at]
        self.at += 1
        return char

    def until(self, stops):
        start = self.at
        while self.at < len(self.text) and self.text[self.at] not in stops:
            self.at += 1
        return self.text[start:self.at]

    def type(self):
        char = self.take()
        if char in _DESCRIPTOR_PRIMITIVES:
            return Prim(_DESCRIPTOR_PRIMITIVES[char])
        if char == "[":
            return Arr(self.type())
        if char == "T":
            name = self.until(";")
            self.take()
            return TVar(name)
        if char == "L":
            name = self.until("<;.")
            args = self.arguments()
            while self.peek() == ".":           # Outer<K>.Inner<V>
                self.take()
                name += "$" + self.until("<;.")
                args = self.arguments()
            self.take()                         # ;
            return Cls(name.replace("/", "."), args)
        raise ValueError("unreadable type in %r at %d" % (self.text, self.at - 1))

    def arguments(self):
        if self.peek() != "<":
            return ()
        self.take()
        out = []
        while self.peek() != ">":
            char = self.peek()
            if char == "*":
                self.take()
                out.append(Wild("*"))
            elif char in "+-":
                self.take()
                out.append(Wild(char, self.type()))
            else:
                out.append(self.type())
        self.take()
        return tuple(out)

    def parameters(self):
        """``<T:Ljava/lang/Object;U::Ljava/lang/Comparable<TU;>;>``"""
        if self.peek() != "<":
            return []
        self.take()
        out = []
        while self.peek() != ">":
            name = self.until(":")
            bound = None
            while self.peek() == ":":
                self.take()
                if self.peek() == ":":          # no class bound, interfaces follow
                    continue
                if self.peek() in ">" or self.peek() == "":
                    break
                found = self.type()
                if bound is None:
                    bound = found
            out.append((name, bound or OBJECT))
        self.take()
        return out


def _method_signature(text):
    reader = _Reader(text)
    parameters = reader.parameters()
    assert reader.take() == "("
    arguments = []
    while reader.peek() != ")":
        arguments.append(reader.type())
    reader.take()
    answer = reader.type()
    return parameters, arguments, answer


def _class_signature(text):
    reader = _Reader(text)
    parameters = reader.parameters()
    parents = []
    while reader.peek():
        parents.append(reader.type())
    return parameters, parents


# --- class files -------------------------------------------------------------

@dataclass
class JavaField:
    name: str
    type: object
    static: bool
    final: bool
    public: bool
    owner: str
    constant: object = None
    deprecated: bool = False


@dataclass
class JavaMethod:
    name: str
    params: list
    ret: object
    static: bool
    varargs: bool
    public: bool
    abstract: bool
    owner: str
    descriptor: str
    type_params: list
    throws: list
    deprecated: bool = False

    @property
    def is_constructor(self):
        return self.name == "<init>"

    def shown(self):
        """``vibrate(long, int)`` -- for the list an error prints."""
        parts = [source(erase(kind, dict(self.type_params))) for kind in self.params]
        if self.varargs and parts and parts[-1].endswith("[]"):
            parts[-1] = parts[-1][:-2] + "..."
        name = self.owner.rsplit(".", 1)[-1].replace("$", ".") if self.is_constructor \
            else self.name
        return "%s(%s)" % (name, ", ".join(parts))


@dataclass
class JavaClass:
    name: str
    flags: int
    super_name: object
    interfaces: list
    type_params: list
    parents: list                       # with their type arguments
    fields: dict
    methods: dict
    deprecated: bool = False

    @property
    def is_interface(self):
        return bool(self.flags & ACC_INTERFACE)

    @property
    def is_abstract(self):
        return bool(self.flags & ACC_ABSTRACT)

    @property
    def simple(self):
        return self.name.rsplit(".", 1)[-1].replace("$", ".")


def _parse_class(data):
    if data[:4] != b"\xca\xfe\xba\xbe":
        raise ValueError("not a class file")
    at = 8
    (count,) = struct.unpack_from(">H", data, at)
    at += 2
    pool = [None] * count
    index = 1
    while index < count:
        tag = data[at]
        at += 1
        if tag == 1:
            (length,) = struct.unpack_from(">H", data, at)
            at += 2
            pool[index] = data[at:at + length].decode("utf-8", "replace")
            at += length
        elif tag in (3, 4):
            pool[index] = (tag, struct.unpack_from(">i" if tag == 3 else ">f", data, at)[0])
            at += 4
        elif tag in (5, 6):
            pool[index] = (tag, struct.unpack_from(">q" if tag == 5 else ">d", data, at)[0])
            at += 8
            index += 1
        elif tag in (7, 8, 16, 19, 20):
            pool[index] = (tag, struct.unpack_from(">H", data, at)[0])
            at += 2
        elif tag in (9, 10, 11, 12, 17, 18):
            at += 4
        elif tag == 15:
            at += 3
        else:
            raise ValueError("unknown constant tag %d" % tag)
        index += 1

    def utf(number):
        return pool[number]

    def class_name(number):
        if not number:
            return None
        return pool[pool[number][1]].replace("/", ".")

    def attributes(position):
        (how_many,) = struct.unpack_from(">H", data, position)
        position += 2
        found = {}
        for _ in range(how_many):
            name_index, length = struct.unpack_from(">HI", data, position)
            position += 6
            found[utf(name_index)] = data[position:position + length]
            position += length
        return found, position

    flags, this_index, super_index, interface_count = struct.unpack_from(">HHHH", data, at)
    at += 8
    interfaces = [class_name(number) for number in
                  struct.unpack_from(">%dH" % interface_count, data, at)]
    at += 2 * interface_count
    name = class_name(this_index)
    super_name = class_name(super_index)

    fields = {}
    (field_count,) = struct.unpack_from(">H", data, at)
    at += 2
    for _ in range(field_count):
        access, name_index, descriptor_index = struct.unpack_from(">HHH", data, at)
        found, at = attributes(at + 6)
        if access & ACC_SYNTHETIC or not access & (ACC_PUBLIC | ACC_PROTECTED):
            continue
        signature = found.get("Signature")
        text = utf(struct.unpack(">H", signature)[0]) if signature else utf(descriptor_index)
        constant = None
        if "ConstantValue" in found:
            entry = pool[struct.unpack(">H", found["ConstantValue"])[0]]
            if entry[0] == 8:
                constant = pool[entry[1]]
            else:
                constant = entry[1]
        fields[utf(name_index)] = JavaField(
            utf(name_index), _Reader(text).type(), bool(access & ACC_STATIC),
            bool(access & ACC_FINAL), bool(access & ACC_PUBLIC), name, constant,
            "Deprecated" in found)

    methods = {}
    (method_count,) = struct.unpack_from(">H", data, at)
    at += 2
    for _ in range(method_count):
        access, name_index, descriptor_index = struct.unpack_from(">HHH", data, at)
        found, at = attributes(at + 6)
        if access & (ACC_SYNTHETIC | ACC_BRIDGE):
            continue
        if not access & (ACC_PUBLIC | ACC_PROTECTED):
            continue
        method_name = utf(name_index)
        if method_name == "<clinit>":
            continue
        descriptor = utf(descriptor_index)
        signature = found.get("Signature")
        text = utf(struct.unpack(">H", signature)[0]) if signature else descriptor
        type_params, params, ret = _method_signature(text)
        throws = []
        if "Exceptions" in found:
            block = found["Exceptions"]
            (how_many,) = struct.unpack_from(">H", block, 0)
            throws = [class_name(number) for number in
                      struct.unpack_from(">%dH" % how_many, block, 2)]
        methods.setdefault(method_name, []).append(JavaMethod(
            method_name, params, ret, bool(access & ACC_STATIC),
            bool(access & ACC_VARARGS), bool(access & ACC_PUBLIC),
            bool(access & ACC_ABSTRACT), name, descriptor, type_params, throws,
            "Deprecated" in found))

    found, at = attributes(at)
    type_params, parents = [], []
    if "Signature" in found:
        type_params, parents = _class_signature(
            utf(struct.unpack(">H", found["Signature"])[0]))
    else:
        if super_name:
            parents.append(Cls(super_name))
        parents.extend(Cls(interface) for interface in interfaces)
    return JavaClass(name, flags, super_name, interfaces, type_params, parents,
                     fields, methods, "Deprecated" in found)


# --- the library -------------------------------------------------------------

class Library:
    """The classes of one or more jars, read as they are asked for."""

    def __init__(self, jars):
        self.jars = [os.path.abspath(path) for path in jars]
        self._zips = [zipfile.ZipFile(path) for path in self.jars]
        self._names = [set(archive.namelist()) for archive in self._zips]
        self._classes = {}
        self._ancestors = {}

    def close(self):
        for archive in self._zips:
            archive.close()

    def find(self, name):
        """The class with this binary name, or ``None``."""
        if name in self._classes:
            return self._classes[name]
        entry = name.replace(".", "/") + ".class"
        found = None
        for archive, names in zip(self._zips, self._names):
            if entry in names:
                found = _parse_class(archive.read(entry))
                break
        self._classes[name] = found
        return found

    def resolve(self, dotted):
        """``android.os.Build.VERSION`` as people write it: the last dots may
        be a class inside a class."""
        dotted = dotted.strip().replace("$", ".")
        parts = dotted.split(".")
        for inner in range(len(parts)):
            outer = len(parts) - inner
            if outer < 1:
                break
            name = ".".join(parts[:outer])
            if inner:
                name += "$" + "$".join(parts[outer:])
            found = self.find(name)
            if found is not None:
                return found
        return None

    def nested(self, owner, simple):
        return self.find(owner.name + "$" + simple)

    def packages_with(self, simple):
        """Every class in the jars with this simple name: for "did you mean"."""
        suffix = "/" + simple + ".class"
        out = []
        for names in self._names:
            for entry in names:
                if entry.endswith(suffix) or entry.endswith("$" + simple + ".class"):
                    out.append(entry[:-6].replace("/", ".").replace("$", "."))
        return sorted(set(out))

    def close_to(self, simple, count=4):
        """Full names of classes whose simple name is near this one: what
        somebody who misspelt a class probably meant."""
        import difflib
        if not hasattr(self, "_simple_names"):
            names = {}
            for entries in self._names:
                for entry in entries:
                    if not entry.endswith(".class") or "$" in entry:
                        continue
                    full = entry[:-6].replace("/", ".")
                    names.setdefault(full.rsplit(".", 1)[-1], []).append(full)
            self._simple_names = names
        out = []
        for near in difflib.get_close_matches(simple, list(self._simple_names),
                                              n=count, cutoff=0.75):
            out.extend(sorted(self._simple_names[near], key=lambda name: (
                not name.startswith("android."), name)))
        return out[:count]

    # -- the hierarchy --

    def parents(self, kind):
        """The classes a type extends and implements, with what its own type
        arguments make of theirs."""
        found = self.find(kind.name)
        if found is None:
            return []
        bindings = {}
        if kind.args and len(kind.args) == len(found.type_params):
            bindings = {name: arg for (name, _), arg in zip(found.type_params, kind.args)}
        out = []
        for parent in found.parents:
            if bindings:
                out.append(substitute(parent, bindings))
            elif found.type_params:
                out.append(Cls(parent.name))        # a raw type has raw parents
            else:
                out.append(parent)
        if found.is_interface and not out:
            out.append(OBJECT)
        return out

    def lineage(self, kind):
        """The type and everything above it, nearest first."""
        out, seen, queue = [], set(), [kind]
        while queue:
            current = queue.pop(0)
            if current.name in seen:
                continue
            seen.add(current.name)
            out.append(current)
            queue.extend(self.parents(current))
        if OBJECT.name not in seen:
            out.append(OBJECT)
        return out

    def ancestors(self, name):
        """The names of everything a class is."""
        if name not in self._ancestors:
            self._ancestors[name] = {kind.name for kind in self.lineage(Cls(name))}
        return self._ancestors[name]

    def is_a(self, name, ancestor):
        return ancestor in self.ancestors(name)

    # -- members --

    def field(self, kind, name):
        """The field and its type as seen from ``kind``, or ``(None, None)``."""
        for owner in self.lineage(kind):
            found = self.find(owner.name)
            if found is None or name not in found.fields:
                continue
            field = found.fields[name]
            return field, substitute(field.type, self._bindings(found, owner))
        return None, None

    def methods(self, kind, name):
        """Every method called ``name`` reachable from ``kind``, nearest first,
        as ``(method, bindings of the class's own type variables)``."""
        out, seen = [], set()
        lineage = [kind] if name == "<init>" else self.lineage(kind)
        for owner in lineage:
            found = self.find(owner.name)
            if found is None:
                continue
            for method in found.methods.get(name, ()):
                key = method.descriptor.split(")")[0]
                if key in seen:
                    continue
                seen.add(key)
                out.append((method, self._bindings(found, owner)))
        return out

    def member_names(self, kind, static=None):
        """Names somebody may have meant: for the suggestions of an error."""
        names = set()
        for owner in self.lineage(kind):
            found = self.find(owner.name)
            if found is None:
                continue
            for field in found.fields.values():
                if field.public and (static is None or field.static == static):
                    names.add(field.name)
            for overloads in found.methods.values():
                for method in overloads:
                    if method.public and not method.is_constructor and (
                            static is None or method.static == static):
                        names.add(method.name)
        return sorted(names)

    @staticmethod
    def _bindings(found, owner):
        if owner.args and len(owner.args) == len(found.type_params):
            return {name: arg for (name, _), arg in zip(found.type_params, owner.args)}
        return {}

    def bounds(self, kind):
        found = self.find(kind.name)
        return dict(found.type_params) if found else {}


# --- which Android has what --------------------------------------------------

_ANDROID_NAMES = {
    21: "5.0", 22: "5.1", 23: "6.0", 24: "7.0", 25: "7.1", 26: "8.0",
    27: "8.1", 28: "9", 29: "10", 30: "11", 31: "12", 32: "12L", 33: "13",
    34: "14", 35: "15", 36: "16",
}


def android_version(level):
    """``Android 8.0 (API 26)``"""
    name = _ANDROID_NAMES.get(int(level))
    return "Android %s (API %d)" % (name, level) if name else "API %d" % level


class ApiLevels:
    """``data/api-versions.xml``: the API level each class and member is from."""

    def __init__(self, path):
        self.path = path
        self._classes = None

    def _load(self):
        import xml.etree.ElementTree as ElementTree
        classes = {}
        for _event, node in ElementTree.iterparse(self.path, events=("end",)):
            if node.tag != "class":
                continue
            since = _level(node.get("since"), 1)
            members = {}
            for child in node:
                if child.tag in ("method", "field"):
                    name = child.get("name")
                    if child.tag == "method":
                        name = name.split(")")[0] + ")"
                    members[(child.tag, name)] = _level(child.get("since"), since)
            classes[node.get("name").replace("/", ".")] = (since, members)
            node.clear()
        self._classes = classes

    def of_class(self, name):
        if self._classes is None:
            self._load()
        found = self._classes.get(name)
        return found[0] if found else None

    def of_method(self, owner, name, descriptor):
        """The level of ``owner.name(descriptor)``; a method the table does
        not list is as old as its class."""
        return self._member(owner, ("method", name + descriptor.split(")")[0] + ")"))

    def of_field(self, owner, name):
        return self._member(owner, ("field", name))

    def _member(self, owner, key):
        if self._classes is None:
            self._load()
        found = self._classes.get(owner)
        if not found:
            return None
        return found[1].get(key, found[0])


def _level(text, default):
    try:
        return int(str(text).split(".")[0])
    except (TypeError, ValueError):
        return default


def find_android_jar(compile_sdk=35):
    """``(android.jar, api-versions.xml or None)`` of the platform apps are
    compiled against, or ``(None, None)`` when no SDK is installed.

    ``APKPY_ANDROID_JAR`` names the jar directly, for a machine that keeps it
    somewhere of its own.
    """
    named = os.environ.get("APKPY_ANDROID_JAR", "").strip()
    if named and os.path.isfile(named):
        table = os.path.join(os.path.dirname(named), "data", "api-versions.xml")
        return named, (table if os.path.isfile(table) else None)
    from ..native_build import find_android_sdk
    sdk = find_android_sdk()
    if not sdk:
        return None, None
    platforms = os.path.join(sdk, "platforms")
    wanted = os.path.join(platforms, "android-%d" % compile_sdk)
    candidates = [wanted]
    if os.path.isdir(platforms):
        others = []
        for entry in os.listdir(platforms):
            if entry.startswith("android-"):
                others.append((_level(entry[8:], 0), os.path.join(platforms, entry)))
        candidates.extend(path for _level_, path in sorted(others, reverse=True))
    for folder in candidates:
        jar = os.path.join(folder, "android.jar")
        if os.path.isfile(jar):
            table = os.path.join(folder, "data", "api-versions.xml")
            return jar, (table if os.path.isfile(table) else None)
    return None, None
