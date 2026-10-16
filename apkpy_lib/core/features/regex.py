"""Portable, build-time validated ``re`` subset for the native backend.

Patterns/flags are constants; input and replacement text may be dynamic.
Python's parser is used only by the compiler, never shipped in an APK. In
particular character classes/case folding are frozen from the build Python's
Unicode tables instead of inheriting a device's different Java/ICU tables.
"""
import ast
import functools
import json
import re
from pathlib import Path

try:
    from re import _parser, _compiler, _constants
except ImportError:  # Python 3.8--3.10
    import sre_parse as _parser
    import sre_compile as _compiler
    import sre_constants as _constants

from ...diagnostics import ApkpyError

METHODS = {"match", "search", "sub", "findall"}
MATCH_METHODS = {"group", "groups", "start", "end", "span"}
FLAGS = {name: int(getattr(re, name)) for name in (
    "I", "IGNORECASE", "M", "MULTILINE", "S", "DOTALL", "X", "VERBOSE",
    "A", "ASCII", "U", "UNICODE",
)}
FLAGS["NOFLAG"] = 0
ALLOWED_FLAGS = int(re.I | re.M | re.S | re.X | re.A | re.U)
PREFIX = "_apkpy_re_"


def error(message, node=None, suggestion=None):
    raise ApkpyError(message, code="C1701", line=getattr(node, "lineno", 0),
                     suggestions=[suggestion or "Use the documented portable re subset; keep patterns and flags constant."])


def _hex(cp):
    return "\\x{%x}" % cp


@functools.lru_cache(maxsize=128)
def _class(op, data, flags):
    """Exactly the characters Python accepts, compressed to Java ranges."""
    state = _parser.State()
    state.flags = flags
    token = list(data) if op == _constants.IN else data
    parsed = _parser.SubPattern(state, [(op, token)])
    test = _compiler.compile(parsed, flags).fullmatch
    ranges = []
    start = previous = None
    for cp in range(0x110000):
        # Only valid Unicode scalar input is part of the portable contract.
        found = not 0xD800 <= cp <= 0xDFFF and test(chr(cp)) is not None
        if found:
            if start is None:
                start = cp
            previous = cp
        elif start is not None:
            ranges.append(_hex(start) + ("-" + _hex(previous) if previous != start else ""))
            start = None
    if start is not None:
        ranges.append(_hex(start) + ("-" + _hex(previous) if previous != start else ""))
    return "[" + "".join(ranges) + "]" if ranges else "(?!)"


def compile_pattern(pattern, flags=0):
    if not isinstance(pattern, str):
        raise ValueError("Only Unicode string patterns are supported, not bytes or compiled patterns")
    if len(pattern) > 4096:
        raise ValueError("The portable pattern limit is 4096 characters")
    if flags & ~ALLOWED_FLAGS:
        raise ValueError("Supported flags: IGNORECASE, MULTILINE, DOTALL, VERBOSE, ASCII and UNICODE")
    compiled = re.compile(pattern, flags)
    parsed = _parser.parse(pattern, flags)

    def emit(tokens, mode):
        result = []
        for op, value in tokens:
            name = str(op)
            if name == "LITERAL":
                if 0xD800 <= value <= 0xDFFF:
                    raise ValueError("Surrogate code points are outside the portable Unicode subset")
                result.append(_class(op, value, mode) if mode & re.I else _hex(value))
            elif name == "NOT_LITERAL":
                result.append(_class(op, value, mode))
            elif name == "IN":
                result.append(_class(op, tuple(value), mode))
            elif name == "ANY":
                result.append("[\\s\\S]" if mode & re.S else "[^\\n]")
            elif name == "SUBPATTERN":
                group, add, remove, body = value
                inner_mode = (mode | add) & ~remove
                # a/u override one another for scoped flags.
                if add & re.A:
                    inner_mode &= ~re.U
                if add & re.U:
                    inner_mode &= ~re.A
                result.append(("(" if group else "(?:") + emit(body, inner_mode) + ")")
            elif name == "BRANCH":
                result.append("(?:" + "|".join(emit(branch, mode) for branch in value[1]) + ")")
            elif name in ("MAX_REPEAT", "MIN_REPEAT"):
                low, high, body = value
                high_text = "" if high == _constants.MAXREPEAT else str(high)
                result.append("(?:" + emit(body, mode) + "){%d,%s}%s" % (
                    low, high_text, "?" if name == "MIN_REPEAT" else ""))
            elif name in ("ASSERT", "ASSERT_NOT"):
                direction, body = value
                if direction < 0:
                    raise ValueError("Lookbehind is not in the portable subset yet; use a capturing group")
                result.append(("(?=" if name == "ASSERT" else "(?!") + emit(body, mode) + ")")
            elif name == "AT":
                anchor = str(value)
                if anchor == "AT_BEGINNING_STRING":
                    result.append("\\A")
                elif anchor == "AT_END_STRING":
                    result.append("\\z")  # Python's \\Z is strict, Java's is not.
                elif anchor in ("AT_BEGINNING", "AT_BEGINNING_LINE"):
                    result.append("(?:\\A|(?<=\\n))" if mode & re.M else "\\A")
                elif anchor in ("AT_END", "AT_END_LINE"):
                    result.append("(?=\\n|\\z)" if mode & re.M else "(?=\\n?\\z)")
                elif anchor in ("AT_BOUNDARY", "AT_NON_BOUNDARY"):
                    word = _class(_constants.IN, ((_constants.CATEGORY, _constants.CATEGORY_WORD),), mode & ~re.I)
                    boundary = "(?:(?<=%s)(?!%s)|(?<!%s)(?=%s))" % (word, word, word, word)
                    if anchor == "AT_NON_BOUNDARY":
                        boundary = "(?!" + boundary + ")"
                        if re.search(r"\B", "") is None:  # Python <= 3.13
                            boundary = "(?!\\A\\z)" + boundary
                    result.append(boundary)
                else:
                    raise ValueError("Unsupported anchor: " + anchor)
            else:
                raise ValueError("Unsupported regex construct: " + name +
                                 ". Pattern backreferences, conditionals, atomic groups and possessive repeats are not included yet")
        return "".join(result)

    return {"pattern": pattern, "flags": flags, "java": emit(parsed, parsed.state.flags),
            "groups": compiled.groups, "names": dict(compiled.groupindex)}


def internal(node, method=None):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id.startswith(PREFIX)
            and (method is None or node.func.id == PREFIX + method))


def java_value(node, val):
    if not internal(node):
        return None
    name = node.func.id[len(PREFIX):]
    args = ["null" if isinstance(arg, ast.Constant) and arg.value is None else val(arg)
            for arg in node.args]
    if name in ("match", "search", "findall"):
        return "ApkpyRegex.%s(%s, ApkpyRegex.text(%s))" % (name, args[0], args[1])
    if name == "sub":
        return "ApkpyRegex.sub(%s, ApkpyRegex.text(%s), ApkpyRegex.text(%s), String.valueOf(%s))" % tuple(args)
    if name in ("group", "start", "end", "span"):
        return "ApkpyRegex.%s(%s, String.valueOf(%s))" % (name, args[0], args[1])
    if name == "groups":
        return "ApkpyRegex.groups(%s, %s)" % tuple(args)
    if name == "is_none":
        return "String.valueOf(%s == null)" % args[0]
    if name == "present":
        return "String.valueOf(%s != null)" % args[0]
    if name == "nonempty":
        return "ApkpyRegex.nonempty(%s)" % args[0]
    if name == "bool_value":
        return "String.valueOf(Boolean.parseBoolean(%s))" % args[0]
    raise ValueError("Unknown regex lowering: " + name)


def condition(node, val):
    if any(internal(node, method) for method in ("is_none", "present", "nonempty", "bool_value")):
        return "Boolean.parseBoolean(%s)" % java_value(node, val)
    return None


def is_sequence(node):
    return any(internal(node, name) for name in ("findall", "groups", "span"))


class Plan(ast.NodeTransformer):
    def __init__(self, tree):
        self.patterns = []
        self.aliases = {"re": "re"}
        self.constants = {}
        self.kinds = {}
        self.seq = 0
        self.function_depth = 0
        assigned = {}
        for n in ast.walk(tree):
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for target in getattr(n, "targets", [getattr(n, "target", None)]):
                    if isinstance(target, ast.Name):
                        assigned[target.id] = assigned.get(target.id, 0) + 1
        self.immutable = {name for name, count in assigned.items() if count == 1}
        self.functions = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for n in tree.body:
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                if assigned.get(n.targets[0].id) == 1:
                    try:
                        self.constants[n.targets[0].id] = ast.literal_eval(n.value)
                    except (ValueError, TypeError):
                        pass

    def call(self, name, args, original):
        return ast.copy_location(ast.Call(func=ast.Name(id=PREFIX + name, ctx=ast.Load()),
                                          args=args, keywords=[]), original)

    def kind(self, node):
        if isinstance(node, ast.Name):
            return self.kinds.get(node.id)
        if internal(node, "match") or internal(node, "search"):
            return "match"
        if is_sequence(node):
            return "sequence"
        if internal(node, "group"):
            return "nullable"
        if any(internal(node, name) for name in ("present", "is_none", "nonempty", "bool_value")):
            return "predicate"
        return None

    def const(self, node):
        if isinstance(node, ast.Name) and node.id in self.constants:
            return self.constants[node.id]
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and self.aliases.get(node.value.id) == "re":
            if node.attr in FLAGS:
                return FLAGS[node.attr]
        if isinstance(node, ast.Name) and self.aliases.get(node.id, "").startswith("re."):
            name = self.aliases[node.id][3:]
            if name in FLAGS:
                return FLAGS[name]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return self.const(node.left) | self.const(node.right)
        return ast.literal_eval(node)

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == "re":
                self.aliases[alias.asname or "re"] = "re"
        return node

    def visit_ImportFrom(self, node):
        if node.module == "re":
            for alias in node.names:
                if alias.name not in METHODS | FLAGS.keys():
                    error("This re import is not supported: " + alias.name, node,
                          "Import match, search, sub, findall or the supported flags explicitly.")
                self.aliases[alias.asname or alias.name] = "re." + alias.name
        return node

    def visit_FunctionDef(self, node):
        old = self.kinds.copy(), self.aliases.copy(), self.constants.copy()
        local = {arg.arg for arg in node.args.args}
        for item in ast.walk(node):
            if isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                for target in getattr(item, "targets", [getattr(item, "target", None)]):
                    if isinstance(target, ast.Name):
                        local.add(target.id)
        for name in local:
            self.kinds.pop(name, None)
            self.constants.pop(name, None)
            self.aliases.pop(name, None)
        self.function_depth += 1
        node.body = [self.visit(item) for item in node.body]
        self.function_depth -= 1
        self.kinds, self.aliases, self.constants = old
        return node

    def visit_Assign(self, node):
        # Flags/constant aliases are compile-time values too, not unknown
        # Java objects such as `re.I` or a bitwise operation on Strings.
        try:
            constant = self.const(node.value)
            if isinstance(constant, (str, int)):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in self.immutable:
                        self.constants[target.id] = constant
                if not isinstance(node.value, ast.Constant):
                    node.value = ast.copy_location(ast.Constant(value=constant), node.value)
        except (ValueError, TypeError):
            pass
        node.value = self.visit(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.kinds[target.id] = self.kind(node.value)
                self.aliases.pop(target.id, None)
        return node

    def visit_Expr(self, node):
        node.value = self.visit(node.value)
        if internal(node.value):
            self.seq += 1
            return ast.copy_location(ast.Assign(targets=[ast.Name(
                id="_apkpy_regex_unused_%d" % self.seq, ctx=ast.Store())], value=node.value), node)
        return node

    def predicate(self, node):
        if self.kind(node) == "match":
            return self.call("present", [node], node)
        if self.kind(node) == "sequence":
            return self.call("nonempty", [node], node)
        if self.kind(node) == "predicate":
            return self.call("bool_value", [node], node) if isinstance(node, ast.Name) else node
        return node

    def visit_If(self, node):
        node.test = self.predicate(self.visit(node.test))
        node.body = [self.visit(n) for n in node.body]
        node.orelse = [self.visit(n) for n in node.orelse]
        return node

    visit_While = visit_If

    def visit_IfExp(self, node):
        node.test = self.predicate(self.visit(node.test))
        node.body, node.orelse = self.visit(node.body), self.visit(node.orelse)
        return node

    def visit_BoolOp(self, node):
        node.values = [self.predicate(self.visit(v)) for v in node.values]
        return node

    def visit_UnaryOp(self, node):
        node.operand = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            node.operand = self.predicate(node.operand)
        return node

    def visit_Compare(self, node):
        node = self.generic_visit(node)
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Is, ast.IsNot, ast.Eq, ast.NotEq)):
            a, b = node.left, node.comparators[0]
            if isinstance(a, ast.Constant) and a.value is None:
                a, b = b, a
            if self.kind(a) in ("match", "nullable") and isinstance(b, ast.Constant) and b.value is None:
                return self.call("is_none" if isinstance(node.ops[0], (ast.Is, ast.Eq)) else "present", [a], node)
        return node

    def visit_Call(self, node):
        dotted = ""
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if self.aliases.get(node.func.value.id) == "re":
                dotted = node.func.attr
        elif isinstance(node.func, ast.Name):
            alias = self.aliases.get(node.func.id, "")
            if alias.startswith("re."):
                dotted = alias[3:]
        if dotted:
            if not self.function_depth:
                error("Run regex operations inside a callback or helper function", node,
                      "Keep the pattern constant at module level, then call re inside a button, lifecycle or worker callback.")
            if dotted not in METHODS:
                error("re.%s() is not in the portable subset" % dotted, node,
                      "Use re.match, re.search, re.sub or re.findall with a constant string pattern.")
            params = ("pattern", "repl", "string", "count", "flags") if dotted == "sub" else ("pattern", "string", "flags")
            if len(node.args) > len(params):
                error("Too many arguments to re." + dotted, node)
            args = dict(zip(params, node.args))
            for kw in node.keywords:
                if kw.arg not in params or kw.arg in args:
                    error("Unknown or repeated regex argument: " + str(kw.arg), node)
                args[kw.arg] = kw.value
            required = params[:3] if dotted == "sub" else params[:2]
            if any(name not in args for name in required):
                error("Missing regex argument; expected " + ", ".join(required), node)
            try:
                pattern = self.const(args["pattern"])
                flags = self.const(args.get("flags", ast.Constant(value=0)))
                if not isinstance(flags, int):
                    raise ValueError("Regex flags must be constant integers or re flags")
                spec = compile_pattern(pattern, flags)
            except (ValueError, TypeError, re.error) as exc:
                error("Cannot compile re.%s: %s" % (dotted, exc), node)
            key = (pattern, flags)
            index = next((i for i, item in enumerate(self.patterns) if (item["pattern"], item["flags"]) == key), None)
            if index is None:
                index = len(self.patterns)
                self.patterns.append(spec)
            values = [ast.Constant(value=index)]
            if dotted == "sub":
                if isinstance(args["repl"], ast.Lambda) or (isinstance(args["repl"], ast.Name) and args["repl"].id in self.functions):
                    error("Callable re.sub replacements are not supported yet", node, "Pass a replacement string; numbered and named group references are supported.")
                try:
                    replacement = self.const(args["repl"])
                except (ValueError, TypeError):
                    replacement = None
                if replacement is not None:
                    try:
                        re.compile(pattern, flags).sub(replacement, "")
                    except (TypeError, ValueError, re.error, IndexError) as exc:
                        error("Invalid re.sub replacement: " + str(exc), node)
                values.append(self.visit(args["repl"]))
            if isinstance(args["string"], ast.Constant) and not isinstance(args["string"].value, str):
                error("Regex input must be a Unicode string", node)
            values.append(self.visit(args["string"]))
            if dotted == "sub":
                count = args.get("count", ast.Constant(value=0))
                if isinstance(count, ast.Constant) and isinstance(count.value, bool):
                    count = ast.Constant(value=int(count.value))
                if isinstance(count, ast.Constant) and not isinstance(count.value, int):
                    error("re.sub count must be an integer", node)
                values.append(self.visit(count))
            return self.call(dotted, values, node)

        node = self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "bool" and len(node.args) == 1:
            if self.kind(node.args[0]) in ("match", "sequence", "predicate"):
                return self.predicate(node.args[0])
        if isinstance(node.func, ast.Attribute) and self.kind(node.func.value) == "match":
            name = node.func.attr
            if name not in MATCH_METHODS or node.keywords or len(node.args) > 1:
                error("Unsupported Match method/arguments: " + name, node,
                      "Use group(index_or_name), groups(), start(), end() or span(); each accepts at most one positional argument.")
            default = ast.Constant(value=None if name == "groups" else 0)
            selector = node.args[0] if node.args else default
            try:
                key = self.const(selector)
            except (ValueError, TypeError):
                error("Match group selectors/defaults must be constant", node)
            if name == "groups":
                if key is not None and not isinstance(key, str):
                    error("groups(default) supports a constant string or None", node)
            elif isinstance(key, int):
                key = "i:" + str(int(key))
            elif isinstance(key, str):
                key = "n:" + key
            else:
                error("A group selector must be an integer index or a string name", node)
            return self.call(name, [node.func.value, ast.Constant(value=key)], node)
        return node

    def java(self, package):
        specs = [{"java": p["java"], "names": p["names"]} for p in self.patterns]
        encoded = json.dumps(specs, ensure_ascii=True, separators=(",", ":"))
        chunks = [json.dumps(encoded[i:i + 12000]) for i in range(0, len(encoded), 12000)]
        literal = "new StringBuilder()" + "".join(".append(%s)" % c for c in chunks) + ".toString()"
        source = Path(__file__).with_name("regex_android.java").read_text(encoding="utf-8")
        return source.replace("__PACKAGE__", package).replace("__SPECS__", literal)


def prepare(tree):
    plan = Plan(tree)
    modules, names = {"re"}, set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.asname or a.name for a in node.names if a.name == "re")
        elif isinstance(node, ast.ImportFrom) and node.module == "re":
            names.update(a.asname or a.name for a in node.names)
    if not any(isinstance(n, ast.Call) and (
        (isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id in modules)
        or (isinstance(n.func, ast.Name) and n.func.id in names)
    ) for n in ast.walk(tree)):
        return tree, plan
    return ast.fix_missing_locations(plan.visit(tree)), plan
