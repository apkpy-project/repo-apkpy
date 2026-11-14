"""Read from the whole file before any screen: drawer, overlays, pins, translations, numbers."""
import ast
import json

from ...features import function_values as function_values_feature
from ... import unsupported
from ... import i18n as i18n_feature
from ...features import pinning as pinning_feature
from ..state import _FN_TARGETS, _I18N, _MUTATED_LISTS
from ..numeric import _local_numeric_names, _numeric_arg_kind, _numeric_body_names, _numeric_params


class FirstPass:
    """Read from the whole file before any screen: drawer, overlays, pins, translations, numbers."""

    def prescan_drawer(self, tree):
        """Learn the drawer's variable name before any function body is read.

        An app bar is usually written above the drawer it opens -- the drawer
        needs every screen to exist first, and the app bars come with the
        screens. Parsing strictly top to bottom would meet `menu.open()`
        before `menu` was anything, and drop it in silence, which is this
        project's most expensive class of bug.
        """
        for node in getattr(tree, 'body', []):
            if not isinstance(node, ast.Assign) or not node.targets:
                continue
            target = node.targets[0]
            value = node.value
            if (isinstance(target, ast.Name) and isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == 'drawer'):
                self.drawer_var = target.id
                return

    def prescan_overlays(self, tree):
        """Learn the names of the sheets and dialogs before any function
        body is read.

        A sheet with components is written after the functions its buttons
        call -- Python needs ``command=apply`` to exist -- and one of those
        functions closes the sheet. Read strictly top to bottom, that
        ``filters.close()`` came before ``filters`` was anything.
        """
        self.overlay_names = set()
        for node in getattr(tree, 'body', []):
            if not isinstance(node, ast.Assign) or not node.targets:
                continue
            target, value = node.targets[0], node.value
            if (isinstance(target, ast.Name) and isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id in ('bottom_sheet', 'modal', 'menu', 'popup_menu',
                                          'context_menu', 'date_picker', 'time_picker')):
                self.overlay_names.add(target.id)

    def prescan_pins(self, tree):
        """Read ``https.pin(...)`` before anything else.

        The pins become a res/ file and a manifest attribute rather than code,
        so they have to be known before either is written -- and reading them
        from the whole tree means a pin declared below the screen that uses the
        host still counts, which is the only order anybody would expect.
        """
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'pin'
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'https'):
                continue
            try:
                host = ast.literal_eval(node.args[0]) if node.args else ''
                pins = ast.literal_eval(node.args[1]) if len(node.args) > 1 else []
            except (ValueError, SyntaxError, TypeError, IndexError):
                host, pins = '', []
            expires = subdomains = None
            for keyword in node.keywords:
                if not isinstance(keyword.value, ast.Constant):
                    continue
                if keyword.arg == 'expires':
                    expires = keyword.value.value
                elif keyword.arg == 'subdomains':
                    subdomains = keyword.value.value
                elif keyword.arg == 'pins':
                    pins = pins or []

            for problem in (pinning_feature.check_host(host),
                            pinning_feature.check_pins(pins),
                            pinning_feature.check_expires(expires)):
                if problem:
                    unsupported.raise_unsupported(
                        node,
                        cause=(
                            'Pinning decides which certificate the app will '
                            'accept for a host, and it is written into the app '
                            'rather than checked while it runs -- so a mistake '
                            'here is a mistake nobody can fix without a new '
                            'release. ' + problem[0].upper() + problem[1:] + '.'
                        ),
                        suggestions=[
                            'The pin is the base64 of a SHA-256 over the '
                            'certificate public key; the Previewer prints the '
                            'live one when it does not match.',
                        ],
                        received='https.pin(%r, ...)' % (host,),
                    )
            self.pinned_hosts[pinning_feature.normalise(host)] = {
                'pins': list(pins),
                'expires': expires,
                'subdomains': bool(subdomains),
            }

    def prescan_translations(self, tree):
        """Read ``translations({...})`` before any screen is parsed.

        Whole-tree rather than top to bottom: a component that calls ``t()``
        is usually written above the table it reads from, and meeting the
        call first would drop the word in silence -- this project's most
        expensive class of bug, and the reason the drawer has a prescan too.
        """
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'translations' and node.args):
                continue
            try:
                table = ast.literal_eval(node.args[0])
            except (ValueError, SyntaxError, TypeError):
                unsupported.raise_unsupported(
                    node,
                    cause=('The words are written into the app as fixed text, '
                           'because ApkPy reads your module instead of running '
                           'it. This table is built from something it cannot '
                           'read off the page.'),
                    suggestions=['Write the dictionary out literally.'],
                    received='translations(...)',
                )
            default = None
            for keyword in node.keywords:
                if keyword.arg == 'default' and isinstance(keyword.value, ast.Constant):
                    default = keyword.value.value

            cleaned = {}
            for tag, words in (table or {}).items():
                canonical = i18n_feature.canonical(tag)
                if canonical is None or not isinstance(words, dict):
                    unsupported.raise_unsupported(
                        node,
                        cause=('A language becomes a res/ folder on the phone, '
                               'and Android only matches folders named after a '
                               'language and an optional region.'),
                        suggestions=['Use a tag like "pt", "en" or "pt-BR".'],
                        received='translations({%r: ...})' % (tag,),
                    )
                cleaned[canonical] = {str(k): str(v) for k, v in words.items()}
            if not cleaned:
                continue
            chosen = i18n_feature.canonical(default) if default else None
            _I18N[0] = {'table': cleaned,
                        'default': chosen or next(iter(cleaned))}
            self.translations = cleaned
            self.default_language = _I18N[0]['default']
            return

    def prescan_mutated_lists(self, tree):
        """Learn which module-level lists the app changes, before reading a body.

        A list written at module level is normally inlined wherever it is used,
        which is right up to the moment somebody appends to it. From then on
        Python sees the list grow and the inlined copy keeps answering with the
        original -- the Previewer and the phone would disagree for the rest of
        the session, and neither would say so.

        Those names move to the process-wide store instead, which is one list
        per app exactly as a module-level list is one list per program. Lists
        nobody appends to keep the old inlining, so no app that works today
        gains a field it never asked for.

        Read from the whole tree rather than top to bottom: the function that
        appends is usually written above the list it appends to.
        """
        module_lists = {}
        for node in getattr(tree, 'body', []):
            if (isinstance(node, ast.Assign) and node.targets
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, (ast.List, ast.Tuple))):
                module_lists[node.targets[0].id] = node.value

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'append'
                    and isinstance(node.func.value, ast.Name)):
                continue
            name = node.func.value.id
            if name not in module_lists:
                continue
            try:
                seed = json.dumps(ast.literal_eval(module_lists[name]))
            except (ValueError, SyntaxError, TypeError):
                # Uma lista construída a partir de nomes não tem valor fixo por
                # onde começar, e semear com [] apagaria o que lá estava.
                unsupported.raise_unsupported(
                    node,
                    cause=(
                        'A module-level list that the app appends to has to '
                        'start from a value ApkPy can write down, because the '
                        'phone starts from that text rather than by running '
                        'your module. This one is built from other names.'
                    ),
                    suggestions=[
                        'Write %s as a plain list of literals.' % name,
                        'Build it inside a function instead.',
                    ],
                    received='%s.append(...)' % name,
                )
            self.mutated_lists.add(name)
            _MUTATED_LISTS[0][name] = seed

    def prescan_own_names(self, tree):
        """Names the app defines itself, before any body is read.

        ``back()`` is ApkPy's, unless the module has its own ``def back():``
        -- an app written before 1.12.0 may, and its function must keep being
        the one called, whichever comes first in the file.
        """
        self.own_function_names = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        # ``archive = swipe("archive", "Archive", ...)`` written once and
        # given to a list later: the list reads the call it names.
        self.swipe_defs = {
            node.targets[0].id: node.value
            for node in getattr(tree, 'body', [])
            if isinstance(node, ast.Assign) and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == 'swipe'
        }

    def prescan_numeric_args(self, tree):
        """Decide which function parameters always arrive as numbers.

        Every parameter used to be text, because "everything is String" is how
        values cross the boundary. That is right at the boundary and wrong
        inside the function: ``def total(cents): return cents / 100`` stopped
        the build, even when every call passed a number.

        So the call sites decide. A parameter counts as a number when the
        function is called at least once and *every* call passes something
        this pass can prove is one -- a numeric literal, ``int()``/``float()``/
        ``len()``, arithmetic between those, or a name that its own body only
        ever assigns from them. Anything less and the parameter stays text,
        because a wrong guess here would silently turn a sum into glued text.
        """
        numeric_names = _numeric_body_names(tree)
        # f(x) of a value is a call of each function handed on as one.
        fn_targets = set(_FN_TARGETS[0]) | function_values_feature.targets(tree)

        defs = {node.name: node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)}
        params, returns = {}, {}

        # Parameters and return values decide each other -- one helper feeding
        # another, euros(with_vat(cents)), only works once both are known --
        # so this settles instead of reading the source once. It converges
        # because nothing stops being a number once a round has found it.
        #
        # n = f(n), f a function handed on as a value: whether f(n) is a
        # number depends on what the functions that can reach that call
        # answer, which depends on n. Each group of them (one name per group,
        # features/function_values.py) is first supposed to answer a whole
        # number; a group where one of them then does not is read again
        # without it, until what is supposed holds.
        _groups = {}
        for _node in ast.walk(tree):
            if isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name) \
                    and function_values_feature.is_call_name(_node.func.id):
                _groups[_node.func.id] = set(function_values_feature.reach(_node, fn_targets))
        _assumed = set(_groups)
        _rounds = 0
        while True:
            _rounds += 1
            returns = dict(returns)
            for _group in _assumed:
                returns[_group] = False
            calls = {}
            # fact(n - 1) inside fact: whether n is a number there depends on
            # whether n is a number -- read once the other calls have said.
            recursive = {}

            def _record(root, scope, owner=None):
                """Every call under *root*, read with that scope's numbers."""
                for node in ast.walk(root):
                    if not (isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Name)):
                        continue
                    if owner is not None and node.func.id == owner and not node.keywords:
                        recursive.setdefault(owner, []).append(node)
                        continue
                    if function_values_feature.is_call_name(node.func.id):
                        # A call of each function it can reach with that many
                        # arguments (the rest, TypeError, pass nothing), its
                        # defaults filling the end.
                        kinds = [_numeric_arg_kind(arg, scope, returns) for arg in node.args[1:]]
                        for target in function_values_feature.reach(node, fn_targets):
                            target_fn = defs.get(target)
                            if target_fn is None:
                                continue
                            total = len(target_fn.args.args)
                            required = total - len(target_fn.args.defaults)
                            if not required <= len(kinds) <= total:
                                continue
                            filled = list(kinds) + [
                                _numeric_arg_kind(d, scope, returns)
                                for d in target_fn.args.defaults[len(kinds) - required:]]
                            calls.setdefault(target, []).append(filled)
                        continue
                    seen = calls.setdefault(node.func.id, [])
                    if node.keywords:
                        # A keyword argument does not say which position it
                        # fills until the definition is read; leave the whole
                        # call out rather than lining the arguments up by
                        # guessing.
                        seen.append(None)
                        continue
                    seen.append([_numeric_arg_kind(arg, scope, returns)
                                 for arg in node.args])

            # A parameter handed straight to another function -- line(name,
            # cents) calling euros(cents) -- only counts inside the body that
            # already knows it is a number.
            local_numbers = {name: _local_numeric_names(node, numeric_names, returns)
                             for name, node in defs.items()}
            for name, node in defs.items():
                scope = dict(numeric_names)
                scope.update(local_numbers[name])
                scope.update(params.get(name) or {})
                for statement in node.body:
                    _record(statement, scope, owner=name)

            for node in tree.body:
                if not isinstance(node, ast.FunctionDef):
                    _record(node, numeric_names)

            fresh = {}
            for name, node in defs.items():
                arg_names = [arg.arg for arg in node.args.args]
                outside = _numeric_params(calls.get(name), arg_names)
                if recursive.get(name) and outside:
                    # The calls from outside say which parameters are numbers;
                    # the function's calls to itself keep them so only if they
                    # pass numbers too, read with that same assumption.
                    scope = dict(numeric_names)
                    scope.update(outside)
                    inner = [[_numeric_arg_kind(arg, scope, returns) for arg in call.args]
                             for call in recursive[name]]
                    outside = _numeric_params((calls.get(name) or []) + inner, arg_names)
                fresh[name] = outside

            grown = {}
            for name, node in defs.items():
                local = dict(numeric_names)
                local.update(local_numbers[name])
                local.update(fresh.get(name) or {})
                values = [sub.value for sub in ast.walk(node)
                          if isinstance(sub, ast.Return) and sub.value is not None]
                if not values:
                    continue
                kinds = [_numeric_arg_kind(value, local, returns)
                         for value in values]
                calls_itself = any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                                   and c.func.id == name for v in values for c in ast.walk(v))
                if any(kind is None for kind in kinds) and name not in returns and calls_itself:
                    # return n * fact(n - 1), n if n < 2 else fib(n - 1) + ...:
                    # if every return is a number once the calls to itself
                    # are, each call that ends returns one -- the deepest
                    # took a return that does not call it. Whole numbers
                    # first, then decimals; the guess has to come back.
                    for guess in (False, True):
                        assumed = dict(returns)
                        assumed[name] = guess
                        trial = [_numeric_arg_kind(value, local, assumed) for value in values]
                        if all(kind is not None for kind in trial) and any(trial) == guess:
                            kinds = trial
                            break
                if any(kind is None for kind in kinds):
                    continue
                grown[name] = any(kinds)

            for _group, _members in _groups.items():
                if _group in _assumed:
                    grown[_group] = False
                else:
                    # Known from its functions: every one answers the same.
                    _kinds = {grown.get(m) for m in _members}
                    if len(_kinds) == 1 and None not in _kinds:
                        grown[_group] = _kinds.pop()
            settled = (fresh, grown) == (params, returns) or _rounds >= 6
            params, returns = fresh, grown
            if not settled:
                continue
            _failed = {g for g in _assumed
                       if not all(returns.get(m) is False for m in _groups[g])}
            if not _failed:
                break
            _assumed -= _failed
            _rounds = 0
            params, returns = {}, {}

        self.numeric_params = params
        self.numeric_returns = returns
        self.numeric_constant_text = {
            target.id: repr(node.value.value)
            for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name) and target.id in numeric_names
            and isinstance(node.value, ast.Constant)
        }
        self.numeric_constants = {
            target.id: numeric_names[target.id]
            for node in tree.body if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name) and target.id in numeric_names
        }

    def numeric_args_for(self, name, arg_names):
        """The parameters of *name* that every call site fills with a number."""
        found = getattr(self, 'numeric_params', {}).get(name)
        if not found:
            return {}
        return {arg: kind for arg, kind in found.items() if arg in arg_names}
