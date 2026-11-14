"""The top of the app's file: functions, assignments, ifs, and the calls that make screens."""
import ast

from ...features import push as push_feature
from ...features import maps as maps_feature
from ...features import routes as routes_feature
from ...features import location_background as location_background_feature
from ...features import data as data_feature
from ...features import jobs as jobs_feature
from ...features import native as native_feature
from ...features import kit as kit_feature
from ...features import nfc as nfc_feature
from ...features import contacts as contacts_feature
from ...features import ui_functions as ui_functions_feature
from ...features import notifications as notifications_feature
from ...features import camera as camera_feature
from ...features import keyboard as keyboard_feature
from .... import motion
from ....diagnostics import ApkpyError
from ... import unsupported
from ..kinds import _list_params
from ..expressions import _CMP_OPS, _cond_shape_supported, _written_comparand
from ..statements import _mark_item_names


class ModuleReader:
    """The top of the app's file: functions, assignments, ifs, and the calls that make screens."""

    def visit_FunctionDef(self, node):
        arg_names = [arg.arg for arg in node.args.args]
        # A função devolve um valor? (algum `return <expr>` em qualquer ramo)
        returns_value = any(
            isinstance(n, ast.Return) and n.value is not None for n in ast.walk(node)
        ) or node.name in getattr(self, 'value_called', ())
        self.functions[node.name] = {
            'args': arg_names,
            # Funções do utilizador chamadas com argumentos: por omissão cada
            # parâmetro é uma String (modelo "tudo é String"). Os argumentos
            # booleanos de callbacks nativos (success/granted/...) continuam a
            # ser detetados na emissão, onde a verificação boolean tem prioridade.
            'string_args': set(arg_names),
            # O parâmetro continua a viajar como String -- é assim que os
            # valores atravessam a fronteira -- mas se todas as chamadas lhe
            # passam um número, dentro do corpo ele conta como número e
            # `cents / 100` volta a ser uma conta em vez de um refúgio.
            'numeric_args': self.numeric_args_for(node.name, arg_names),
            'returns_value': returns_value,
            # cart.append(x) on a parameter: a list, as str(cart) shows it.
            'list_params': _list_params(node),
            # The defaults, for a button whose command= calls it with none.
            'defaults': dict(zip(arg_names[len(arg_names) - len(node.args.defaults):],
                                 node.args.defaults)),
            'cmds': (_mark_item_names(node), self._parse_statements(node.body))[1]
        }

        # Do not call generic_visit(node), otherwise we would incorrectly process
        # function internals as global module commands (like visit_Assign and visit_If)

    def visit_For(self, node):
        # `for` a nível de módulo → corre no onCreate do ecrã inicial.
        # Um `for a, b in ...` (ou com else) era deitado fora aqui sem uma
        # palavra -- quatro apps de montra perderam assim as linhas que o seu
        # for construia. Os que constroem UI ja foram desenrolados antes
        # (ui_functions.expand); o que sobra e recusado com a razao.
        if not isinstance(node.target, ast.Name) or node.orelse:
            unsupported.raise_untranslated_loop(node)
        if isinstance(node.target, ast.Name):
            self.module_init_cmds.append({
                'type': 'for_loop',
                'var': node.target.id,
                'iter_node': node.iter,
                'body': self._parse_statements(node.body),
                'body_ast': node.body,
            })

        # Sem generic_visit: o corpo já foi processado por _parse_statements

    def visit_While(self, node):
        # `while` a nível de módulo → corre no onCreate do ecrã inicial
        if _cond_shape_supported(node.test):
            self.module_init_cmds.append({
                'type': 'while_loop',
                'test': node.test,
                'body': self._parse_statements(node.body),
            })

        # Sem generic_visit: o corpo já foi processado por _parse_statements

    def _fold_string_concat(self, node):
        """`A = "x" + B + "y"` no topo do módulo, colado num literal só.

        Só participam literais e constantes já recolhidas -- e recolhidas
        quer dizer escritas ACIMA desta linha, porque isto lê o módulo de
        cima para baixo tal como o Python o executaria. Devolve None se
        alguma peça não for conhecível antes de a app correr.
        """
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return self.string_constants.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = self._fold_string_concat(node.left)
            if left is None:
                return None
            right = self._fold_string_concat(node.right)
            if right is None:
                return None
            return left + right
        return None

    def _unknown_concat_names(self, node, found):
        """Os nomes que impedem a colagem, e se havia texto na expressão."""
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            self._unknown_concat_names(node.left, found)
            self._unknown_concat_names(node.right, found)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found['had_text'] = True
        elif isinstance(node, ast.Name):
            if node.id not in self.string_constants:
                found['names'].append(node.id)
        else:
            found['other'] = True
        return found

    def _report_unfoldable_concat(self, var_name, value):
        """Uma constante de texto meio-conhecida é um erro, não um silêncio."""
        found = self._unknown_concat_names(value, {'names': [], 'had_text': False,
                                                   'other': False})
        # Só reclama de uma expressão que é claramente texto: `A + B` entre
        # duas listas continua a ser assunto de outra pessoa.
        if not found['had_text'] or found['other'] or not found['names']:
            return
        missing = found['names'][0]
        # Fatal, e não um aviso: o nome ficaria por declarar, e o build do
        # Android morreria com um cannot-find-symbol que não explica nada.
        # Mais vale parar aqui, onde ainda se sabe o porquê.
        raise ApkpyError(
            '%s is written by joining text to %s, and %s is not a text '
            'constant declared above it.' % (var_name, missing, missing),
            code='U2027',
            title='This constant is built from a name ApkPy does not know',
            cause=(
                'Constants at the top of a module are read in order and '
                'written into the app as fixed text, because ApkPy reads your '
                'module rather than running it. A piece it cannot resolve '
                'leaves the whole constant undefined.'
            ),
            expected='every piece to be a string, or a string constant declared earlier',
            received='%s = ... + %s + ...' % (var_name, missing),
            suggestions=(
                'Move the declaration of %s above %s.' % (missing, var_name),
                'Write the whole value as one string literal.',
                'Build it inside a function instead, where names are resolved '
                'as the app runs.',
            ),
            docs='https://repo-apkpy.pages.dev/reference/essential/',
            line=getattr(value, 'lineno', 0),
        )

    def visit_Assign(self, node):
        if not node.targets or not isinstance(node.targets[0], ast.Name):
            self.generic_visit(node)
            return

        var_name = node.targets[0].id
        value    = node.value

        # Captura constantes de string a nível de módulo (ex: API_KEY = "...")
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            self.string_constants[var_name] = value.value
            self.generic_visit(node)
            return

        # ... e as que sao escritas por pedacos, que e' como se escreve um URL:
        #     API_URL = BASE + "/models/" + API_MODEL
        # Sem isto o nome era usado no Java sem nunca ter sido declarado, e o
        # build morria com um cannot-find-symbol longe daqui.
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
            folded = self._fold_string_concat(value)
            if folded is not None:
                self.string_constants[var_name] = folded
                self.generic_visit(node)
                return
            self._report_unfoldable_concat(var_name, value)

        # A comprehension here used to fall through to generic_visit and vanish:
        # the name stayed an empty list on the phone.
        if isinstance(value, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            unsupported.raise_module_comprehension(value)

        # Captura listas literais a nível de módulo (ex: _history_items = [...])
        if isinstance(value, ast.List):
            self.list_assignments[var_name] = value
            self.generic_visit(node)
            return

        if isinstance(value, ast.Dict):
            self.dict_assignments[var_name] = value
            self.generic_visit(node)
            return

        if not isinstance(value, ast.Call):
            self.generic_visit(node)
            return

        func = value.func

        if data_feature.parse_assignment(self, var_name, value):
            return

        # sync = background_job("sync_notes", run=fn, ...)
        if jobs_feature.parse_assignment(self, var_name, value):
            return

        # count = state(0, id="cart_count")
        if isinstance(func, ast.Name) and func.id == 'state':
            initial_node = (
                value.args[0] if value.args
                else self._kw_node(value.keywords, 'initial')
            )
            if initial_node is None:
                initial_node = ast.Constant(value="")
            state_id = self._kw(value.keywords, 'id', var_name)
            self.reactive_states[var_name] = {
                'id': str(state_id or var_name),
                'initial_node': initial_node,
                'bindings': [],
            }

        # login_screen = Screen(id="login")
        elif isinstance(func, ast.Name) and func.id == 'Screen':
            screen_id = self._kw(value.keywords, 'id', var_name)
            bg_image = self._kw(value.keywords, 'background_image')
            scroll_kw = self._kw(value.keywords, 'scroll', False)
            self.screens[var_name] = screen_id
            if bg_image:
                self.screen_bg_images[screen_id] = bg_image
            if scroll_kw:
                self.screen_scroll[screen_id] = True
            turned = kit_feature.orientation_of(value, 'Screen')
            if turned is not None:
                self.screen_orientation[screen_id] = turned
            self.screen_components.setdefault(screen_id, [])

        # virtual_collection(row=post_row): ui_functions expands the row
        # function into a template container that belongs to no screen.
        elif isinstance(func, ast.Name) and func.id == ui_functions_feature.ROW_FACTORY:
            template = self._parse_component_call('container', value, py_var=var_name)
            if template is not None:
                template['_row_template'] = True

        # btn = button("Entrar", screen=login_screen)
        elif isinstance(func, ast.Name) and func.id in ('button', 'inputs', 'input_field', 'label', 'container', 'card', 'image', 'video', 'camera_view', 'map_view', 'avatar', 'list_row', 'list_view', 'virtual_collection', 'markdown', 'rich_text', 'tree_view', 'carousel', 'grid', 'spinner', 'skeleton', 'empty_state', 'error_state', 'upload_button', 'pager', 'tab', 'chart', 'chips', 'segmented', 'web_page', 'draw_pad'):
            self._parse_component_call(func.id, value, py_var=var_name)

        elif isinstance(func, ast.Name) and func.id in (
                'bottom_sheet', 'modal', 'menu', 'popup_menu',
                'context_menu', 'date_picker', 'time_picker'):
            self._parse_overlay_call(func.id, value, var_name)

        elif isinstance(func, ast.Name) and func.id == 'drawer':
            self._parse_drawer_call(value, var_name)

        elif isinstance(func, ast.Name) and func.id == 'responsive':
            self._parse_responsive_call(value, py_var=var_name)

        # saved_val = storage.get("key", "")  — nível de módulo → vai para onCreate
        elif isinstance(func, ast.Attribute) and func.attr == 'get' and \
                isinstance(func.value, ast.Name) and func.value.id == 'storage':
            key = value.args[0].value if value.args and hasattr(value.args[0], 'value') else ''
            default_node = value.args[1] if len(value.args) > 1 else None
            default_kw   = self._kw(value.keywords, 'default')
            if default_node is not None and hasattr(default_node, 'value'):
                v = default_node.value
                default_val = ('"true"' if v else '"false"') if isinstance(v, bool) else str(v)
            elif default_kw is not None:
                default_val = str(default_kw)
            else:
                default_val = '""'
            if not default_val.startswith('"'):
                default_val = f'"{default_val}"'
            self.module_init_cmds.append({
                'type': 'storage_get_assign',
                'var': var_name,
                'key': key,
                'default': default_val,
                'key_node': value.args[0] if value.args else None,
                'default_node': default_node if default_node is not None
                else self._kw_node(value.keywords, 'default'),
            })

        # saved_val = db.query(sql) — nível de módulo → vai para onCreate
        elif isinstance(func, ast.Attribute) and func.attr == 'query' and \
                isinstance(func.value, ast.Name) and func.value.id == 'db':
            if value.args:
                sql_node = value.args[0]
                params_node = value.args[1] if len(value.args) > 1 else self._kw_node(value.keywords, 'params')
                self.module_init_cmds.append({
                    'type': 'db_query_assign',
                    'var': var_name,
                    'sql_node': sql_node,
                    'params_node': params_node
                })

        self.generic_visit(node)

    def visit_If(self, node):
        """Captura blocos if de nível de módulo (ex: if saved_x != "": comp.set_value(saved_x))."""
        test = node.test
        before = len(self.module_init_cmds)
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and test.comparators:
            left = test.left.id if isinstance(test.left, ast.Name) else None
            op_node = test.ops[0]
            comp_node = test.comparators[0]
            # See _parse_statements: the shortcut is for a right side that is
            # written out.
            written = _written_comparand(comp_node)
            right = comp_node.value if written else ''
            if left == '__name__' and right == '__main__':
                return  # Ignorar este bloco na compilação para Android
            op = _CMP_OPS.get(type(op_node))  # ==, !=, <, >, <=, >=
            if written and left and op is not None:
                self.module_init_cmds.append({
                    'type':       'if_compare',
                    'left':       left,
                    'op':         op,
                    'right':      right,
                    'true_body':  self._parse_statements(node.body),
                    'false_body': self._parse_statements(node.orelse),
                })
            elif op is not None or isinstance(op_node, (ast.In, ast.NotIn)):
                self.module_init_cmds.append({
                    'type':       'if_cond',
                    'test':       test,
                    'true_body':  self._parse_statements(node.body),
                    'false_body': self._parse_statements(node.orelse),
                })
        elif isinstance(test, (ast.BoolOp, ast.UnaryOp, ast.Call, ast.Constant, ast.Name)) \
                and _cond_shape_supported(test):
            # if a and b:  |  if not x:  |  if valor.isdigit():  (and/or/not + predicados)
            self.module_init_cmds.append({
                'type':       'if_cond',
                'test':       test,
                'true_body':  self._parse_statements(node.body),
                'false_body': self._parse_statements(node.orelse),
            })
        if len(self.module_init_cmds) == before:
            # A module-level if nothing above understood used to vanish, body
            # and all, without a word.
            unsupported.raise_untranslated_condition(test)

        # Não chamar generic_visit para evitar duplicar visit_Assign/visit_Expr nos filhos

    def visit_Expr(self, node):
        if not isinstance(node.value, ast.Call):
            self.generic_visit(node)
            return

        call = node.value
        func = call.func

        if notifications_feature.is_call(call):
            command = notifications_feature.parse_call(self, call)
            if command:
                self.module_init_cmds.append(command)
            return
        if camera_feature.is_call(call):
            self.module_init_cmds.append(camera_feature.parse_call(self, call))
            return
        if nfc_feature.is_call(call):
            self.module_init_cmds.append(nfc_feature.parse_call(self, call))
            return
        if contacts_feature.is_call(call):
            self.module_init_cmds.append(contacts_feature.parse_call(self, call))
            return

        # state.bind(component, "{value} items") and visibility bindings are
        # declarative: they generate one compact render method per state.
        if isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Name) and \
                func.value.id in self.reactive_states and \
                func.attr in ('bind', 'bind_visibility'):
            state_info = self.reactive_states[func.value.id]
            component_node = (
                call.args[0] if call.args
                else self._kw_node(call.keywords, 'component')
            )
            component_var = (
                component_node.id if isinstance(component_node, ast.Name) else None
            )
            if component_var:
                if func.attr == 'bind':
                    template_node = (
                        call.args[1] if len(call.args) > 1
                        else self._kw_node(call.keywords, 'template')
                    )
                    template = (
                        str(template_node.value)
                        if isinstance(template_node, ast.Constant)
                        else '{value}'
                    )
                    state_info['bindings'].append({
                        'kind': 'value',
                        'component_var': component_var,
                        'template': template,
                    })
                else:
                    when_node = (
                        call.args[1] if len(call.args) > 1
                        else self._kw_node(call.keywords, 'when')
                    )
                    when = (
                        bool(when_node.value)
                        if isinstance(when_node, ast.Constant)
                        else True
                    )
                    state_info['bindings'].append({
                        'kind': 'visibility',
                        'component_var': component_var,
                        'when': when,
                    })

        # lifecycle(screen=..., on_mount=..., on_resume=..., ...)
        elif isinstance(func, ast.Name) and func.id == 'lifecycle':
            screen_node = (
                call.args[0] if call.args
                else self._kw_node(call.keywords, 'screen')
            )
            screen_var = screen_node.id if isinstance(screen_node, ast.Name) else None
            screen_id = self.screens.get(screen_var) if screen_var else None
            if screen_id:
                callbacks = {}
                for event in ('on_mount', 'on_resume', 'on_pause', 'on_destroy'):
                    event_node = self._kw_node(call.keywords, event)
                    callbacks[event] = self._register_overlay_callback(
                        event_node, f'lifecycle_{screen_id}_{event}',
                    )
                self.screen_lifecycles[screen_id] = callbacks

        elif isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Name) and \
                func.value.id in self.reactive_states and \
                func.attr in ('set', 'increment', 'decrement', 'toggle'):
            self.module_init_cmds.extend(self._parse_statements([node]))

        elif data_feature.is_command_call(self, call):
            self.module_init_cmds.extend(self._parse_statements([node]))

        # job.observe(...) is a module-level binding (like lifecycle/now_playing),
        # not a command — it wires a screen to WorkManager's LiveData.
        elif jobs_feature.is_observe_call(self, call):
            jobs_feature.parse_observe(self, call)

        elif jobs_feature.is_command_call(self, call):
            self.module_init_cmds.extend(self._parse_statements([node]))

        elif push_feature.is_push_call(call) or routes_feature.is_call(call) or \
                location_background_feature.is_call(call) or \
                maps_feature.is_location_call(call) or \
                maps_feature.is_map_component_call(self, call):
            self.module_init_cmds.extend(self._parse_statements([node]))

        # Chamadas standalone: label("...", screen=x), inputs("...", screen=x)
        elif isinstance(func, ast.Name) and func.id in ('button', 'inputs', 'input_field', 'label', 'container', 'card', 'image', 'video', 'camera_view', 'map_view', 'avatar', 'list_row', 'list_view', 'virtual_collection', 'markdown', 'rich_text', 'tree_view', 'carousel', 'grid', 'spinner', 'skeleton', 'empty_state', 'error_state', 'upload_button', 'pager', 'tab', 'chart', 'chips', 'segmented', 'web_page', 'draw_pad'):
            self._parse_component_call(func.id, call)

        elif isinstance(func, ast.Name) and func.id in (
                'bottom_sheet', 'modal', 'menu', 'popup_menu',
                'context_menu', 'date_picker', 'time_picker'):
            self._parse_overlay_call(
                func.id, call, self._overlay_var_name(func.id, call),
            )

        elif isinstance(func, ast.Name) and func.id == 'responsive':
            self._parse_responsive_call(call)

        elif isinstance(func, ast.Name) and func.id in ('app_bar', 'sliver_app_bar'):
            self._parse_app_bar_call(func.id, call)

        elif isinstance(func, ast.Name) and func.id == 'tooltip':
            target_node = call.args[0] if call.args else self._kw_node(call.keywords, 'target')
            text_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'text')
            target_var = target_node.id if isinstance(target_node, ast.Name) else None
            text = str(text_node.value) if isinstance(text_node, ast.Constant) else ''
            target = self.component_vars.get(target_var)
            if target is not None and text:
                target['tooltip'] = text

        # email.focus() at the top: the screen opens with the cursor in the
        # field and the keyboard up, as the Previewer opens with the cursor there.
        elif isinstance(func, ast.Attribute) and func.attr == keyboard_feature.FOCUS and \
                isinstance(func.value, ast.Name) and \
                func.value.id in self.component_vars:
            self.module_init_cmds.extend(self._parse_statements([node]))

        # stop_button.hide() — a componente arranca escondida. O Previewer
        # sempre o respeitou; sem isto o Android mostrava os dois botões ao
        # abrir e a troca só ficava certa depois do primeiro toque.
        elif isinstance(func, ast.Attribute) and func.attr in ('show', 'hide', 'set_state') and \
                isinstance(func.value, ast.Name) and \
                func.value.id in self.component_vars:
            for cmd in self._parse_statements([node]):
                # This is the starting state, not a change of state: animating
                # it would flash the component on screen and fade it out while
                # the user is still looking at the first frame.
                if cmd.get('type') == 'comp_visibility':
                    cmd['instant'] = True
                self.module_init_cmds.append(cmd)

        # db.execute(sql) — nível de módulo → vai para onCreate
        elif isinstance(func, ast.Attribute) and func.attr == 'execute' and \
                isinstance(func.value, ast.Name) and func.value.id == 'db':
            if call.args:
                sql_node = call.args[0]
                params_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'params')
                self.module_init_cmds.append({
                    'type': 'db_execute',
                    'sql_node': sql_node,
                    'params_node': params_node
                })

        # audio.now_playing(progress_slider, time_label) — liga um range input e um
        # label à reprodução do media service (barra de progresso ao vivo + seek).
        elif isinstance(func, ast.Attribute) and func.attr == 'now_playing' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            prog_node = call.args[0] if call.args else self._kw_node(call.keywords, 'progress')
            time_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'time')
            cover_node = call.args[2] if len(call.args) > 2 else self._kw_node(call.keywords, 'cover')
            title_node = call.args[3] if len(call.args) > 3 else self._kw_node(call.keywords, 'title')
            artist_node = call.args[4] if len(call.args) > 4 else self._kw_node(call.keywords, 'artist')
            prog_var = prog_node.id if isinstance(prog_node, ast.Name) else None
            time_var = time_node.id if isinstance(time_node, ast.Name) else None
            cover_var = cover_node.id if isinstance(cover_node, ast.Name) else None
            title_var = title_node.id if isinstance(title_node, ast.Name) else None
            artist_var = artist_node.id if isinstance(artist_node, ast.Name) else None
            if prog_var:
                self.now_playing = {'progress': prog_var, 'time': time_var, 'cover': cover_var,
                                    'title': title_var, 'artist': artist_var}

        # audio.controls(play_pause=btn, shuffle=btn, repeat=btn, ...textos) — faz os
        # botões REFLETIREM o estado do leitor: ▶/⏸ a tocar/pausado (clicar alterna),
        # 🔀 ligado/desligado, 🔁 off/tudo/uma. A Activity sonda o serviço (poll) e
        # atualiza os rótulos; o botão play/pause manda PAUSE/RESUME conforme o estado.
        elif isinstance(func, ast.Attribute) and func.attr == 'controls' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            def _ctrl_var(name):
                n = self._kw_node(call.keywords, name)
                return n.id if isinstance(n, ast.Name) else None
            self.audio_controls = {
                'play_pause':  _ctrl_var('play_pause'),
                'shuffle':     _ctrl_var('shuffle'),
                'repeat':      _ctrl_var('repeat'),
                'play_text':   self._kw(call.keywords, 'play_text', 'Play'),
                'pause_text':  self._kw(call.keywords, 'pause_text', 'Pause'),
                'shuffle_on':  self._kw(call.keywords, 'shuffle_on', 'Shuffle: on'),
                'shuffle_off': self._kw(call.keywords, 'shuffle_off', 'Shuffle: off'),
                'repeat_off':  self._kw(call.keywords, 'repeat_off', 'Repeat: off'),
                'repeat_all':  self._kw(call.keywords, 'repeat_all', 'Repeat: all'),
                'repeat_one':  self._kw(call.keywords, 'repeat_one', 'Repeat: one'),
            }
            for _p in ('FOREGROUND_SERVICE', 'FOREGROUND_SERVICE_MEDIA_PLAYBACK'):
                if _p not in self.declared_permissions:
                    self.declared_permissions.append(_p)

        # audio.like_button(btn, liked="❤️", unliked="🤍") — clicar guarda/remove a
        # faixa atual dos favoritos (SharedPreferences) e o ícone reflete o estado.
        elif isinstance(func, ast.Attribute) and func.attr == 'like_button' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            btn_node = call.args[0] if call.args else self._kw_node(call.keywords, 'button')
            btn_var = btn_node.id if isinstance(btn_node, ast.Name) else None
            if btn_var:
                self.audio_like = {
                    'button':  btn_var,
                    'liked':   self._kw(call.keywords, 'liked', 'Liked'),
                    'unliked': self._kw(call.keywords, 'unliked', 'Like'),
                }

        # audio.liked_list(list_view) — enche um list_view com as músicas guardadas.
        elif isinstance(func, ast.Attribute) and func.attr == 'liked_list' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            lst_node = call.args[0] if call.args else self._kw_node(call.keywords, 'list')
            lst_var = lst_node.id if isinstance(lst_node, ast.Name) else None
            if lst_var:
                self.audio_liked_list = lst_var

        # audio.playlists_list(list_view) — enche um list_view com as PLAYLISTS do
        # utilizador (nome + nº de faixas). Tocar numa toca-a (play_saved_playlist).
        elif isinstance(func, ast.Attribute) and func.attr == 'playlists_list' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            lst_node = call.args[0] if call.args else self._kw_node(call.keywords, 'list')
            lst_var = lst_node.id if isinstance(lst_node, ast.Name) else None
            if lst_var:
                self.audio_playlists_list = lst_var

        # audio.playlist_editor(list_view) — list_view que mostra as faixas da playlist
        # em edição (audio.edit_playlist). Tocar numa faixa remove-a (remove_from_playlist).
        elif isinstance(func, ast.Attribute) and func.attr == 'playlist_editor' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            lst_node = call.args[0] if call.args else self._kw_node(call.keywords, 'list')
            lst_var = lst_node.id if isinstance(lst_node, ast.Name) else None
            if lst_var:
                self.audio_playlist_editor = lst_var

        # font("Tiempos", regular=..., bold=...)
        elif isinstance(func, ast.Name) and func.id == 'font':
            self._parse_font_call(call)

        # apkpy.declare_permissions(...)
        # secure_screen() / secure_screen(vault) -- FLAG_SECURE, which stops
        # screenshots and blanks the app in the recents carousel.
        elif (isinstance(func, ast.Name) and func.id == 'secure_screen') or \
             (isinstance(func, ast.Attribute) and func.attr == 'secure_screen'):
            self.has_secure_screen = True
            target = call.args[0] if call.args else self._kw_node(call.keywords, 'screen')
            if isinstance(target, ast.Name):
                if self.secure_screens is None:
                    self.secure_screens = set()
                self.secure_screens.add(target.id)
            else:
                # No screen named: every one of them.
                self.secure_screens = None
            return
        elif (isinstance(func, ast.Name) and func.id == 'declare_permissions') or \
             (isinstance(func, ast.Attribute) and func.attr == 'declare_permissions'):
            if call.args and isinstance(call.args[0], ast.List):
                for elt in call.args[0].elts:
                    if hasattr(elt, 'value'):
                        self.declared_permissions.append(elt.value)

        # service.every(run=fn, minutes=N, id="...") — tarefa periódica em segundo plano
        elif isinstance(func, ast.Attribute) and func.attr == 'every' and \
                isinstance(func.value, ast.Name) and func.value.id == 'service':
            keywords = self._service_keywords(call, 'every')
            run_node = self._kw_node(keywords, 'run')
            run_name = run_node.id if isinstance(run_node, ast.Name) else None
            minutes  = self._kw(keywords, 'minutes', 15)
            svc_id   = self._kw(keywords, 'id', f"bg_service_{len(self.background_services)}")
            only_on_wifi       = self._kw(keywords, 'only_on_wifi', False)
            only_when_charging = self._kw(keywords, 'only_when_charging', False)
            if run_name:
                self.background_services.append({
                    'id': svc_id,
                    'function_name': run_name,
                    'minutes': minutes,
                    'only_on_wifi': bool(only_on_wifi),
                    'only_when_charging': bool(only_when_charging),
                    'line': getattr(call, 'lineno', 0),
                })

        # login_screen.on_click_navigate(button=btn_entrar, to=dashboard_screen, data={"key": val})
        elif isinstance(func, ast.Attribute) and func.attr == 'on_click_navigate':
            from_screen_var = func.value.id if isinstance(func.value, ast.Name) else None
            button_py_var   = self._kw(call.keywords, 'button')
            to_screen_var   = self._kw(call.keywords, 'to')
            data_node       = self._kw_node(call.keywords, 'data')
            data_pairs = []
            if isinstance(data_node, ast.Dict):
                for k_node, v_node in zip(data_node.keys, data_node.values):
                    if isinstance(k_node, ast.Constant):
                        data_pairs.append((k_node.value, v_node))

            if from_screen_var and button_py_var and to_screen_var:
                from_screen_id = self.screens.get(from_screen_var)
                to_screen_id   = self.screens.get(to_screen_var)
                if from_screen_id and to_screen_id:
                    self.navigations.append({
                        'from_screen_id': from_screen_id,
                        'button_py_var':  button_py_var,
                        'to_screen_id':   to_screen_id,
                        'data':           data_pairs,
                        # The statement form inside a def already carried this.
                        # This is the form the published examples use, and it
                        # dropped the argument on the floor -- so the docs
                        # showed a transition that only the Previewer played.
                        'transition': motion.normalise_transition(
                            self._kw(call.keywords, 'transition', 'none')),
                    })

        # bottom_nav([home, profile], labels=["Home", "Profile"], icons=["home", "person"])
        elif isinstance(func, ast.Name) and func.id == 'drawer':
            self._parse_drawer_call(call)

        elif isinstance(func, ast.Name) and func.id == 'bottom_nav':
            screens_arg = call.args[0] if call.args else None
            screen_ids = []
            if isinstance(screens_arg, ast.List):
                for elt in screens_arg.elts:
                    if isinstance(elt, ast.Name):
                        sid = self.screens.get(elt.id)
                        if sid:
                            screen_ids.append(sid)
            labels_node = self._kw_node(call.keywords, 'labels')
            labels = []
            if isinstance(labels_node, ast.List):
                labels = [e.value for e in labels_node.elts if isinstance(e, ast.Constant)]
            icons_node = self._kw_node(call.keywords, 'icons')
            icons = []
            if isinstance(icons_node, ast.List):
                icons = [e.value for e in icons_node.elts if isinstance(e, ast.Constant)]
            if screen_ids:
                # Pad labels/icons to match screen count
                while len(labels) < len(screen_ids):
                    labels.append(screen_ids[len(labels)])
                while len(icons) < len(screen_ids):
                    icons.append('circle')
                active_node = self._kw_node(call.keywords, 'icons_active')
                icons_active = []
                if isinstance(active_node, ast.List):
                    icons_active = [
                        e.value for e in active_node.elts
                        if isinstance(e, ast.Constant)
                    ]
                while len(icons_active) < len(screen_ids):
                    icons_active.append(icons[len(icons_active)])
                self.bottom_nav = {
                    'screen_ids': screen_ids, 'labels': labels, 'icons': icons,
                    'icons_active': icons_active,
                    'indicator': motion.normalise_indicator(
                        self._kw(call.keywords, 'indicator', 'pill')),
                }

        # mini_player(open=ecra) — barra de leitor fixa no fundo de TODOS os ecrãs.
        elif isinstance(func, ast.Name) and func.id == 'mini_player':
            open_node = self._kw_node(call.keywords, 'open')
            open_sid = self.screens.get(open_node.id) if isinstance(open_node, ast.Name) else None
            self.mini_player = {'open_sid': open_sid, 'id': self._kw(call.keywords, 'id', None)}

        # comp.set_value(val) — nível de módulo, para popular labels/inputs no onCreate
        elif isinstance(func, ast.Attribute) and func.attr == 'set_value':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var and call.args:
                self.module_init_cmds.append({'type': 'comp_set_value', 'py_var': py_var, 'val_node': call.args[0]})

        # run(start_screen=login_screen)
        elif isinstance(func, ast.Name) and func.id == 'run':
            start_var = self._kw(call.keywords, 'start_screen')
            if start_var:
                self.start_screen_id = self.screens.get(start_var)
            turned = kit_feature.orientation_of(call, 'run')
            if turned is not None:
                self.app_orientation = turned

        # refresh() — chamada de módulo a uma função do utilizador (definida
        # acima no ficheiro) → corre no onCreate (ex: carga inicial de listas).
        # Argumentos são preservados (ex: carregar("inicial")).
        elif isinstance(func, ast.Name) and func.id in self.functions:
            self.module_init_cmds.append(
                {'type': 'function_call', 'name': func.id,
                 'args_nodes': list(call.args),
                 'keywords_nodes': {k.arg: k.value for k in call.keywords if k.arg},
                 'lineno': getattr(call, 'lineno', 0)})

        # Um bloco native chamado no topo do modulo: corre no onCreate, como
        # qualquer outra chamada daqui, e o on_result= tem de sobreviver.
        elif isinstance(func, ast.Name) and native_feature.function_for(func.id) is not None:
            native_feature.register_callback(self, call)
            self.module_init_cmds.append({
                'type': 'function_call', 'name': func.id,
                'args_nodes': list(call.args),
                'keywords_nodes': {k.arg: k.value for k in call.keywords if k.arg},
                'lineno': getattr(call, 'lineno', 0)})

        self.generic_visit(node)
