"""What a piece of the source holds, as far as it says: text, a number, a list."""
import ast
import json

from ..features import regex as regex_feature
from ..features import shared_containers as shared_containers_feature
from ..features import unpacking as unpacking_feature
from ..features import item_assignment as item_feature
from ..features import sets as sets_feature
from ..features import counters as counters_feature

from .state import (
    _BOUND_NAMES, _FIXED_NUMBER_LISTS, _GLOBALS, _IMPORTED_NAMES, _KIND_RETURNS, _MODULE_KINDS,
    _MUTATED_LISTS, _PARAM_KINDS, _STATE_NAMES,
)


def _json_call(node):
    """'loads' or 'dumps' for json.loads(...) / json.dumps(...), else None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'json' \
            and node.func.attr in ('loads', 'dumps'):
        return node.func.attr
    return None


def _dict_receiver(node):
    """True when node.get()/keys()/... is a dict's method, not the app's call."""
    if isinstance(node, ast.Name):
        return (node.id in _BOUND_NAMES[0] and node.id not in _IMPORTED_NAMES[0]
                and node.id not in _STATE_NAMES[0])
    return isinstance(node, (ast.Subscript, ast.Call, ast.Dict))


_DICT_VALUE_METHODS = ('keys', 'values', 'items')

# String methods whose answer is text, whatever they are called on.
_TEXT_METHODS = frozenset({
    'upper', 'lower', 'strip', 'lstrip', 'rstrip', 'replace', 'title',
    'capitalize', 'join', 'zfill', 'ljust', 'rjust', 'center', 'swapcase',
    'casefold',
})


def _static_kind(node, local_kinds=None):
    """'list', 'dict' or 'text' when the source says what *node* holds; else None.

    On the phone every value is text, and a list or a dict is the JSON text of
    one. Python knows which is which from the object; the generated Java can
    only know it from the source, and that is where this reads it -- never
    from the running value. Where it answers None the caller keeps the
    behaviour that does not depend on knowing.

    *local_kinds* maps the names assigned in the function being written; a name
    reassigned to something else is recorded as 'other', so a module-level
    name of the same spelling is not consulted by mistake.
    """
    if isinstance(node, (ast.List, ast.Tuple, ast.ListComp)):
        return 'list'
    if isinstance(node, (ast.Dict, ast.DictComp)):
        return 'dict'
    if isinstance(node, ast.JoinedStr):
        return 'text'
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) \
            and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
        return 'text'
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'format':
        return 'text'
    if _json_call(node) == 'dumps':
        return 'text'
    if isinstance(node, ast.Constant):
        return 'text' if isinstance(node.value, str) else None
    if _is_split_call(node):
        return 'list'
    if regex_feature.internal(node, 'findall'):
        # str(re.findall(...)) showed the JSON, ["1","22"], not ['1', '22'].
        return 'list'
    if sets_feature.makes_set(node):
        return 'list'                   # a set is kept as the list of its items
    if sets_feature.op_of(node) == 'show':
        return 'text'
    counted = counters_feature.op_of(node)
    if counted in counters_feature.DICT_RESULTS:
        return 'dict'
    if counted in counters_feature.LIST_RESULTS:
        return 'list'
    if counted in counters_feature.TEXT_RESULTS:
        return 'text'
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'auth' \
            and node.func.attr == 'claims':
        return 'dict'
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id in ('str', 'chr'):
            return 'text'
        if node.func.id in ('list', 'sorted', 'reversed', unpacking_feature.UNPACK):
            return 'list'
        if node.func.id == 'dict' and len(node.args) == 1 and not node.keywords \
                and _static_kind(node.args[0], local_kinds) == 'dict':
            return 'dict'
        if node.func.id in (item_feature.SETITEM, item_feature.DELITEM) and node.args:
            return _static_kind(node.args[0], local_kinds)
        if node.func.id == item_feature.LISTOP and len(node.args) >= 2:
            op = node.args[0].value
            if op == 'popvalue':
                return None                  # the item: anything
            if op == 'update':
                return 'dict'
            if op in ('pop', 'clear'):
                return _static_kind(node.args[1], local_kinds)    # a dict too
            return 'list'
        if node.func.id == 'dict':
            return 'dict'
        return _KIND_RETURNS[0].get(node.func.id)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in _DICT_VALUE_METHODS and not node.args \
            and _dict_receiver(node.func.value):
        return 'list'
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == 'copy' and not node.args \
            and _dict_receiver(node.func.value):
        return _static_kind(node.func.value, local_kinds)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in _TEXT_METHODS \
            and not (isinstance(node.func.value, ast.Name)
                     and node.func.value.id in ('re', 'os', 'path')):
        return 'text'
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mult)):
        left = _static_kind(node.left, local_kinds)
        right = _static_kind(node.right, local_kinds)
        if 'text' in (left, right):
            return 'text'
        if left == 'list' or right == 'list':
            return 'list'
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr == 'splitlines':
        return 'list'
    if isinstance(node, ast.Name):
        if local_kinds is not None and node.id in local_kinds:
            kind = local_kinds[node.id]
            return kind if kind in ('list', 'dict', 'text') else None
        return _MODULE_KINDS[0].get(node.id)
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        kind = _static_kind(node.value, local_kinds)
        return kind if kind in ('list', 'text') else None
    return None


def _always_returns(body):
    """Whether these statements end in a return (or a raise) on every path."""
    if not body:
        return False
    last = body[-1]
    if isinstance(last, (ast.Return, ast.Raise)):
        return True
    if isinstance(last, ast.If):
        return _always_returns(last.body) and _always_returns(last.orelse)
    if isinstance(last, ast.Try):
        return (_always_returns(last.body) or _always_returns(last.orelse)) \
            and all(_always_returns(h.body) for h in last.handlers)
    return False


def _list_params(fn):
    """Parameters the body appends to or inserts into: cart.append(x). On the
    phone that only works on a list, so the parameter is one. (sort(),
    reverse() and the other changers stop the build on a parameter, in
    features/item_assignment.py, and never get here.)"""
    params = {a.arg for a in list(getattr(fn.args, 'posonlyargs', [])) + list(fn.args.args)}
    found = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in ('append', 'insert') \
                and isinstance(node.func.value, ast.Name) and node.func.value.id in params:
            found.add(node.func.value.id)
        elif isinstance(node.func, ast.Name) and node.func.id == item_feature.LISTOP \
                and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant) \
                and node.args[0].value in ('append', 'insert') \
                and isinstance(node.args[1], ast.Name) and node.args[1].id in params:
            found.add(node.args[1].id)
    return found


def _function_return_kind(fn):
    """'list', 'dict' or 'text' when every return of *fn* gives that, else None.

    The names of the body are read first, the way _static_kind reads the
    names of a function being written: a name given two kinds, or anything
    else than an assignment (a for, a with, an unpacking), is not known. A
    parameter is what the caller gave, unless its default is None and the
    body gives it a value (if tags is None: tags = []).
    """
    local, returns = _body_kinds(fn)
    if not returns or not _always_returns(fn.body):
        return None
    kinds = {(_static_kind(v, local) if v is not None else None) for v in returns}
    kind = kinds.pop() if len(kinds) == 1 else None
    return kind if kind in ('list', 'dict', 'text') else None


def _body_kinds(fn):
    """(name -> kind, the values returned) for the body of *fn*.

    The kind is 'list', 'dict', 'text' or 'other', read as _function_return_kind
    says. A parameter is what the calls give it (_PARAM_KINDS), or a list when
    the body appends to it.
    """
    args = fn.args
    positional = list(getattr(args, 'posonlyargs', [])) + list(args.args)
    params = [a.arg for a in positional + list(args.kwonlyargs)]
    none_default = {a.arg for a, d in zip(positional[len(positional) - len(args.defaults):],
                                          args.defaults)
                    if isinstance(d, ast.Constant) and d.value is None}
    appended = _list_params(fn)
    given = _PARAM_KINDS[0].get(fn.name) or {}
    values, returns, stores = {}, [], {}
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return):
            returns.append(node.value)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values.setdefault(target.id, []).append(node.value)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            values.setdefault(node.target.id, []).append(ast.BinOp(
                left=ast.Name(id=node.target.id, ctx=ast.Load()), op=node.op, right=node.value))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            values.setdefault(node.target.id, []).append(node.value)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                values.setdefault(name, []).append(None)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            values.setdefault(node.name, []).append(None)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            stores[node.id] = stores.get(node.id, 0) + 1
        stack.extend(ast.iter_child_nodes(node))
    for name, count in stores.items():
        if count != len(values.get(name, ())):
            values.setdefault(name, []).append(None)     # a for, a with, a, b = ...
    local = {name: 'other' for name in set(values) | set(params)}
    for _ in range(len(local) + 1):
        known = {}
        for name in local:
            kinds = {(_static_kind(v, local) if v is not None else None)
                     for v in values.get(name, ())}
            if name in params and name not in none_default:
                kinds.add('list' if name in appended else given.get(name))
            kind = kinds.pop() if len(kinds) == 1 else None
            known[name] = kind if kind in ('list', 'dict', 'text') else 'other'
        if known == local:
            break
        local = known
    return local, returns


def _param_kinds(tree):
    """function -> {parameter: 'list' or 'dict'} for the parameters that every
    call of the module fills with that kind.

    A list travels as its JSON text, and inside the function nothing said the
    parameter was one: `if xs:` read "[]" as text that is not empty, so an
    empty list was true and `first([])` went down the branch for a full one.
    The calls say what it is, as they say which parameters are numbers
    (prescan_numeric_args), and only when every call is one this can read. A
    function handed on as a value (on_click=f, key=f) is called by something
    else with something else; a parameter the body gives a value of its own
    is left as it was.
    """
    defs = {n.name: n for n in getattr(tree, 'body', []) if isinstance(n, ast.FunctionDef)}
    if not defs:
        return {}
    callee = {id(n.func) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    as_value = {n.id for n in ast.walk(tree)
                if isinstance(n, ast.Name) and n.id in defs and id(n) not in callee}
    calls = {name: [] for name in defs}       # (call, owner FunctionDef or None, readable)

    def collect(root, owner, readable=True):
        if isinstance(root, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef,
                             ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            # Its own names: what a name there holds is not what the
            # function around it says.
            readable = False
        if isinstance(root, ast.Call) and isinstance(root.func, ast.Name) and root.func.id in calls:
            calls[root.func.id].append((root, owner, readable))
        for child in ast.iter_child_nodes(root):
            collect(child, owner, readable)

    for statement in tree.body:
        if isinstance(statement, ast.FunctionDef):
            for inner in statement.body:
                collect(inner, statement)
        else:
            collect(statement, None)

    def given(call, fn):
        """parameter -> the node that fills it, or None for the whole call."""
        params = [a.arg for a in fn.args.args]
        out = dict(zip(params[len(params) - len(fn.args.defaults):], fn.args.defaults))
        for i, arg in enumerate(call.args):
            if isinstance(arg, ast.Starred) or i >= len(params):
                return None
            out[params[i]] = arg
        for keyword in call.keywords:
            if keyword.arg is None or keyword.arg not in params:
                return None
            out[keyword.arg] = keyword.value
        return out

    def agree(records, fn, scopes):
        params = [a.arg for a in fn.args.args]
        seen = {p: set() for p in params}
        for call, owner, readable in records:
            filled = given(call, fn) if readable else None
            if filled is None:
                return {}
            if owner is not None and owner.name not in scopes:
                scopes[owner.name] = _body_kinds(owner)[0]
            scope = scopes[owner.name] if owner is not None else None
            for p in params:
                node = filled.get(p)
                seen[p].add(_static_kind(node, scope) if node is not None else None)
        return {p: kinds.pop() for p, kinds in seen.items()
                if len(kinds) == 1 and next(iter(kinds)) in ('list', 'dict')}

    found = _PARAM_KINDS[0] = {}
    for _ in range(4):
        scopes = {}
        fresh = {}
        for name, fn in defs.items():
            records = calls[name]
            if name in as_value or not records:
                continue
            stored = {n.id for n in ast.walk(fn)
                      if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del))}
            outside = agree([r for r in records if r[1] is not fn], fn, scopes)
            outside = {p: k for p, k in outside.items() if p not in stored}
            inside = [r for r in records if r[1] is fn]
            if outside and inside:
                # first(xs[1:]) inside first: a list there if xs is one.
                saved = found.get(name)
                found[name] = outside
                again = agree(inside, fn, {})
                if saved is None:
                    found.pop(name)
                else:
                    found[name] = saved
                outside = {p: k for p, k in outside.items() if again.get(p) == k}
            if outside:
                fresh[name] = outside
        if fresh == found:
            break
        found.clear()
        found.update(fresh)
    return dict(found)


def _return_kinds(tree):
    """name -> 'list'/'dict'/'text' for the module's functions that always
    answer that kind (_function_return_kind). One that returns what another
    returns is known once the other is."""
    functions = [n for n in getattr(tree, 'body', []) if isinstance(n, ast.FunctionDef)]
    found = {}
    _KIND_RETURNS[0] = found             # _static_kind reads it while this works
    for _ in range(len(functions) + 1):
        grew = False
        for fn in functions:
            if fn.name not in found:
                kind = _function_return_kind(fn)
                if kind is not None:
                    found[fn.name] = kind
                    grew = True
        if not grew:
            break
    return found


def _literal_number_kind(node):
    """'int', 'float' or 'mixed' for a list or tuple written out with numbers
    only (a sign allowed), else None."""
    if not isinstance(node, (ast.List, ast.Tuple)) or not node.elts:
        return None
    kinds = set()
    for item in node.elts:
        value = item.operand if isinstance(item, ast.UnaryOp) \
            and isinstance(item.op, (ast.USub, ast.UAdd)) else item
        if not isinstance(value, ast.Constant) or isinstance(value.value, bool):
            return None
        if isinstance(value.value, int) and abs(value.value) < 2 ** 63:
            kinds.add('int')
        elif isinstance(value.value, float):
            kinds.add('float')
        else:
            return None
    return kinds.pop() if len(kinds) == 1 else 'mixed'


def _number_list_kind(node):
    """The same for a list written out here, or the name of a module list of
    numbers that nothing changes or hands on (_FIXED_NUMBER_LISTS)."""
    if isinstance(node, ast.Name):
        return _FIXED_NUMBER_LISTS[0].get(node.id)
    return _literal_number_kind(node)


def _fixed_number_lists(tree):
    """NUMS = [9, 12, 10] at the top of the file, only read anywhere: its
    items are numbers wherever they are read (features/shared_containers.py
    says what reading is)."""
    found = {}
    body = list(getattr(tree, 'body', []))
    readers = shared_containers_feature.function_readers(tree)
    for stmt in body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)):
            continue
        name = stmt.targets[0].id
        kind = _literal_number_kind(stmt.value)
        if kind is None or name in _MUTATED_LISTS[0] or name in _GLOBALS[0]:
            continue
        if shared_containers_feature.only_read(name, body, skip={stmt.targets[0]},
                                               readers=readers):
            found[name] = kind
    return found


def _number_item_java(node, val_to_java):
    """(Java, is_float) for an item, the max/min or the sum of a list of
    numbers of one kind: [4, 15, 7][0], NUMS[i], max(NUMS), sum(FLOATS).
    They answered text: i = NUMS[0] and then xs.append(i) put '9' in xs."""
    if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) \
            and not isinstance(node.slice, (ast.Slice, getattr(ast, 'ExtSlice', ast.Slice))):
        kind = _number_list_kind(node.value)
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ('max', 'min', 'sum') and len(node.args) == 1 \
            and not node.keywords and not isinstance(node.args[0], ast.Starred):
        kind = _number_list_kind(node.args[0])
        if kind == 'mixed' and node.func.id == 'sum':
            kind = 'float'
    else:
        return None
    if kind == 'int':
        return ("Long.parseLong(String.valueOf(%s))" % val_to_java(node), False)
    if kind == 'float':
        return ("Double.parseDouble(String.valueOf(%s))" % val_to_java(node), True)
    return None


def _module_kinds(transpiler, tree):
    """What the module-level names hold, as far as the source says.

    A name bound at module level to two different kinds is left out: guessing
    between them is the mistake worth refusing.
    """
    seen = {}

    def note(name, kind):
        if name in seen and seen[name] != kind:
            seen[name] = None
        else:
            seen[name] = kind

    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        name = node.targets[0].id
        kind = _static_kind(node.value)
        note(name, kind)
    for name in getattr(transpiler, 'mutated_lists', ()) or ():
        note(name, 'list')
    return {name: kind for name, kind in seen.items() if kind}


def _module_struct_text(tree, skip=()):
    """Module-level lists, tuples and dicts written out, as their JSON text.

    Only literals: a value with a name or a call inside is built when the app
    runs, and has no text to put in a field. A tuple is a JSON array, as it is
    everywhere else on the phone. The last binding of a name wins, as in
    Python.
    """
    found = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        name = node.targets[0].id
        if name in skip:
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple, ast.Dict)):
            found.pop(name, None)
            continue
        try:
            value = ast.literal_eval(node.value)
            text = json.dumps(value, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':'))
        except (ValueError, TypeError, SyntaxError):
            found.pop(name, None)
            continue
        found[name] = text
    return found


def _kind_from(val_to_java, node):
    """_static_kind through the generator that knows the local names."""
    kind_of = getattr(val_to_java, 'kind_of', None)
    return kind_of(node) if kind_of is not None else _static_kind(node)


def _is_split_call(node):
    """text.split(...) -- a list by construction, whatever the text holds."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'split'
            and not (isinstance(node.func.value, ast.Name)
                     and node.func.value.id == 're'))


def _int_literal(node):
    """The value of an int written out (``3``, ``-2``), or None."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _int_literal(node.operand)
        if inner is None:
            return None
        return -inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.Constant) and isinstance(node.value, int) \
            and not isinstance(node.value, bool):
        return node.value
    return None
