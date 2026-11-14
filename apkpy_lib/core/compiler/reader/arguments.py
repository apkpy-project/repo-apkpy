"""What a call was given, and the app's functions it names as callbacks."""
import ast
import re

from ... import unsupported
from ..expressions import _translation_mark
from ..statements import _SERVICE_PARAMS


class ArgumentReader:
    """What a call was given, and the app's functions it names as callbacks."""

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _kw(self, keywords, name, default=None):
        """Extrai o valor de um keyword argument por nome."""
        for kw in keywords:
            if kw.arg == name:
                marked = _translation_mark(kw.value)
                if marked is not None:
                    return marked
                if isinstance(kw.value, ast.Constant):
                    return kw.value.value
                elif isinstance(kw.value, ast.Name):
                    return kw.value.id  # devolve o nome da variável
                if name == 'id':
                    # Anything else was dropped: the component lost its
                    # styles on the phone only -- id="day_done" if done else
                    # "day_open" drew Onda's week as plain 16sp letters.
                    unsupported.raise_unsupported(
                        kw.value,
                        cause=(
                            'An id names the component in the layout and in '
                            'the stylesheet, so it is written while the app is '
                            'built and has to be a piece of text. Anything else '
                            'left the component without an id -- styled in the '
                            'Previewer, plain on the phone.'
                        ),
                        suggestions=[
                            'Write the id as one piece of text: id="day_done".',
                            'Inside a for loop over a list written in the file, '
                            'an id joined from text ("day_" + kind) or chosen '
                            'by a True/False from that list is read too.',
                        ],
                    )
        return default

    def _first_arg(self, call, name, default=''):
        """The first parameter of a component call, positional or by name.

        Every public component takes its main value first -- button(text),
        label(text), inputs(placeholder) -- so it is almost always positional.
        Passing it by name is equally valid Python and the Previewer has always
        honoured it; reading only ``args[0]`` here emitted an empty attribute,
        so the label or hint showed on the desktop and vanished on the phone.
        """
        if call.args:
            marked = _translation_mark(call.args[0])
            if marked is not None:
                return marked
        if call.args and isinstance(call.args[0], ast.Constant):
            return call.args[0].value
        if call.args:
            # Um nome que o modulo declarou como texto resolve-se aqui; era
            # `label(TITULO)` e saia `android:text=""` -- o Previewer mostrava
            # a palavra e o telemovel nao mostrava nada, sem um aviso.
            first = call.args[0]
            if isinstance(first, ast.Name) and first.id in self.string_constants:
                return self.string_constants[first.id]
            if not isinstance(first, ast.Name):
                unsupported.raise_unsupported(
                    first,
                    cause=(
                        'The text of a component is written into the layout '
                        'while the app is built, so it has to be something '
                        'ApkPy can read off the page: a piece of text, a '
                        'constant declared above, or t("key"). Anything else '
                        'left the attribute empty -- visible in the Previewer, '
                        'blank on the phone.'
                    ),
                    suggestions=[
                        'Write it as one piece of text.',
                        'Set it while the app runs instead: give the component '
                        'an id and call set_value() in a function.',
                    ],
                )
        value = self._kw(call.keywords, name)
        return default if value is None else value

    def _kw_node(self, keywords, name):
        """Extrai o nó AST completo de um keyword argument por nome."""
        for kw in keywords:
            if kw.arg == name:
                return kw.value
        return None

    def _service_keywords(self, call, verb):
        """service.every/once as the Previewer reads them: by position or by name.

        Only ``run=`` by name was read, so ``service.every(sync, minutes=15)``
        -- the order the Previewer's own signature gives -- produced no Worker
        and no word: the service ran at the desk and never on the phone.
        """
        params = _SERVICE_PARAMS[verb]
        if len(call.args) > len(params):
            unsupported.raise_unsupported(
                call,
                cause='service.%s() takes %d arguments: %s.'
                      % (verb, len(params), ', '.join(params)),
                suggestions=['Name them: service.%s(run=sync, %s=15).'
                             % (verb, params[1])])
        named = {kw.arg for kw in call.keywords if kw.arg}
        keywords = list(call.keywords)
        for name, node in zip(params, call.args):
            if name not in named:
                keywords.append(ast.keyword(arg=name, value=node))
        run_node = self._kw_node(keywords, 'run')
        if not isinstance(run_node, ast.Name):
            unsupported.raise_unsupported(
                call,
                cause=('service.%s() becomes a Worker built from a function in '
                       'this file, so it needs that function by name.' % verb),
                suggestions=['Define def sync(): at module level and pass '
                             'service.%s(run=sync, ...).' % verb])
        return keywords

    def _unique_function_name(self, base):
        """Return a deterministic callback name without overwriting a sibling.

        Anonymous components used to share ``btn_cmd``. Every later lambda then
        replaced the previous entry in ``self.functions``, so all Android click
        listeners executed the final button's command.
        """
        clean = re.sub(r'[^A-Za-z0-9_]', '_', str(base or 'callback'))
        if clean and clean[0].isdigit():
            clean = '_' + clean
        candidate = clean or 'callback'
        suffix = 2
        while candidate in self.functions:
            candidate = f"{clean}_{suffix}"
            suffix += 1
        return candidate

    def _register_result_callback(self, cb_node, two_arg, tag):
        """Regista um callback `on_result` de uma API assíncrona e devolve o seu
        nome (ou None). Aceita função NOMEADA ou LAMBDA. `two_arg` distingue a
        aridade: (success, resultado) para extract/hash, ou (json) único para
        list/permissions — este último marcado como json_item_callback (o param
        é uma String JSON; `x["k"]` resolve via _jsonGet). Reaproveita a mesma
        síntese de lambda do `auth.user`, generalizada."""
        if isinstance(cb_node, ast.Name):
            name = cb_node.id
            if two_arg:
                self.boolean_first_arg_callbacks.add(name)
            else:
                self.json_item_callbacks.add(name)
            return name
        if isinstance(cb_node, ast.Lambda):
            params = [a.arg for a in cb_node.args.args]
            name = 'apps_%s_cb' % tag
            body_stmt = ast.Expr(value=cb_node.body)
            ast.fix_missing_locations(body_stmt)
            cb_cmds = self._parse_statements([body_stmt])
            if two_arg:
                p = (params + ['success', 'result'])[:2]
                self.functions[name] = {'args': p, 'cmds': cb_cmds, 'string_args': {p[1]}}
                self.boolean_first_arg_callbacks.add(name)
            else:
                p = params[0] if params else 'data'
                self.functions[name] = {'args': [p], 'cmds': cb_cmds, 'string_args': {p}}
                self.json_item_callbacks.add(name)
            return name
        return None

    def _register_upload_progress_callback(self, cb_node):
        """Register ``on_progress(percent, sent, total)`` including lambdas."""
        if isinstance(cb_node, ast.Name):
            return cb_node.id
        if isinstance(cb_node, ast.Lambda):
            params = [arg.arg for arg in cb_node.args.args]
            params = (params + ['percent', 'sent', 'total'])[:3]
            name = self._unique_function_name('upload_progress_cb')
            body_stmt = ast.Expr(value=cb_node.body)
            ast.fix_missing_locations(body_stmt)
            self.functions[name] = {
                'args': params,
                'cmds': self._parse_statements([body_stmt]),
                'string_args': set(params),
            }
            return name
        return None

    def _register_websocket_callback(self, cb_node, arity, tag):
        """Register a named callback or lambda used by ``websocket.connect``."""
        if isinstance(cb_node, ast.Name):
            return cb_node.id
        if not isinstance(cb_node, ast.Lambda):
            return None
        defaults = {
            0: [],
            1: ['message'],
            2: ['code', 'reason'],
        }
        params = [arg.arg for arg in cb_node.args.args]
        params = (params + defaults.get(arity, []))[:arity]
        while len(params) < arity:
            params.append(f'arg{len(params) + 1}')
        name = self._unique_function_name(f'websocket_{tag}_cb')
        body_stmt = ast.Expr(value=cb_node.body)
        ast.fix_missing_locations(body_stmt)
        self.functions[name] = {
            'args': params,
            'cmds': self._parse_statements([body_stmt]),
            'string_args': set(params),
        }
        return name

    def _register_overlay_callback(self, node, tag, with_value=False):
        """Register named/lambda overlay callbacks without duplicating emitters."""
        if isinstance(node, ast.Name):
            return node.id
        if not isinstance(node, ast.Lambda):
            return None
        name = self._unique_function_name(tag)
        params = [arg.arg for arg in node.args.args]
        if with_value:
            param = params[0] if params else 'value'
            args = [param]
            string_args = {param}
        else:
            args = []
            string_args = set()
        body_stmt = ast.Expr(value=node.body)
        ast.fix_missing_locations(body_stmt)
        self.functions[name] = {
            'args': args,
            'cmds': self._parse_statements([body_stmt]),
            'string_args': string_args,
            'returns_value': False,
        }
        return name

    def _literal_string_list(self, node):
        if isinstance(node, ast.Name):
            node = self.list_assignments.get(node.id, node)
        if not isinstance(node, (ast.List, ast.Tuple)):
            return []
        return [
            str(item.value) for item in node.elts
            if isinstance(item, ast.Constant)
        ]

    def _parse_callback_kw(self, call, key, hint):
        """Resolve ``command=`` into the name of a function Android can call.

        Three spellings reach the same place: a plain name, a lambda, and a
        bound method such as ``command=feed.refresh``.  The last two are given
        a generated wrapper so the regular command parser emits the same Java
        it would for a function written out by hand.
        """
        node = self._kw_node(call.keywords, key)
        if getattr(self, '_row_context', False):
            # Inside a row: a command that takes an argument gets the row's
            # item, as the Previewer calls it -- the same JSON string an
            # on_click receives, so item["user"] reads a field.
            if isinstance(node, ast.Lambda) and node.args.args:
                param = node.args.args[0].arg
                cb_name = self._unique_function_name(str(hint) + '_cmd')
                body_stmt = ast.Expr(value=node.body)
                ast.fix_missing_locations(body_stmt)
                self.functions[cb_name] = {
                    'args': [param],
                    'cmds': self._parse_statements([body_stmt]),
                    'string_args': {param},
                }
                self.json_item_callbacks.add(cb_name)
                self._row_item_callbacks.add(cb_name)
                return cb_name
            if isinstance(node, ast.Name) and \
                    getattr(self, 'function_arity', {}).get(node.id, 0) >= 1:
                self.json_item_callbacks.add(node.id)
                self._row_item_callbacks.add(node.id)
                return node.id
        if isinstance(node, ast.Lambda):
            body_stmt = ast.Expr(value=node.body)
        elif isinstance(node, ast.Attribute):
            body_stmt = ast.Expr(
                value=ast.Call(func=node, args=[], keywords=[])
            )
        else:
            return self._kw(call.keywords, key)
        cb_name = self._unique_function_name(str(hint) + '_cmd')
        ast.fix_missing_locations(body_stmt)
        self.functions[cb_name] = {
            'args': [],
            'cmds': self._parse_statements([body_stmt]),
            'string_args': set(),
        }
        return cb_name
