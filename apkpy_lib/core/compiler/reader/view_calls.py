"""A call that changes the screen: a component's method, a list's items, a dialog, a screen."""
import ast

from ...features import native as native_feature
from ...features import camera_view as camera_view_feature
from .... import motion
from ..expressions import _navigate_data_pairs


class ViewCallReader:
    """A call that changes the screen: a component's method, a list's items, a dialog, a screen."""

    def _component_call(self, cmds, call, func):
        """A component's own method: the camera view, a video, set_value, set_src, a row's text, a stream."""
        if isinstance(func, ast.Attribute) and func.attr not in ('hide', 'show') and isinstance(func.value, ast.Name) and self.component_vars.get(func.value.id, {}).get('comp_type') == 'camera_view':
            cmds.append(camera_view_feature.parse_control(self, call))

        # video.play()/pause()/seek()/... — direct Media3 control.
        elif isinstance(func, ast.Attribute) and \
                func.attr in (
                    'play', 'pause', 'stop', 'seek', 'set_source',
                    'set_speed', 'set_muted',
                ) and isinstance(func.value, ast.Name) and \
                self.component_vars.get(
                    func.value.id, {}
                ).get('comp_type') == 'video':
            cmds.append({
                'type': 'video_control',
                'py_var': func.value.id,
                'action': func.attr,
                'args_nodes': list(call.args),
                'autoplay_node': self._kw_node(
                    call.keywords, 'autoplay'
                ),
            })

        # comp.set_value(valor)
        elif isinstance(func, ast.Attribute) and func.attr == 'set_value':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var and call.args:
                val_node = call.args[0]
                cmds.append({'type': 'comp_set_value', 'py_var': py_var, 'val_node': val_node})

        # image.set_src(src): documented, and refused by the compiler
        # (U2033) -- a story viewer, a profile photo, the cover of the
        # track now playing could not change on a phone.
        elif isinstance(func, ast.Attribute) and func.attr == 'set_src':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var and call.args:
                first = call.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    self.set_src_assets.add(first.value)
                cmds.append({'type': 'comp_set_src', 'py_var': py_var, 'val_node': first})

        # row.set_trailing(x) / row.set_subtitle(x) -- the two slots a
        # settings row has beyond its label.
        elif isinstance(func, ast.Attribute) and func.attr in (
                'set_trailing', 'set_subtitle') and call.args:
            py_var = (func.value.id
                      if isinstance(func.value, ast.Name) else None)
            if py_var:
                cmds.append({
                    'type': 'comp_set_row_field', 'py_var': py_var,
                    'field': func.attr.split('_', 1)[1],
                    'val_node': call.args[0],
                })

        # comp.stream(text) / comp.stream_item(id, field, text)
        elif isinstance(func, ast.Attribute) and                         func.attr in ('stream', 'stream_item'):
            py_var = (func.value.id
                      if isinstance(func.value, ast.Name) else None)
            speed_node = self._kw_node(call.keywords, 'speed')
            speed = (speed_node.value
                     if isinstance(speed_node, ast.Constant) else None)
            if py_var and func.attr == 'stream' and call.args:
                cmds.append({
                    'type': 'comp_stream', 'py_var': py_var,
                    'val_node': call.args[0], 'speed': speed,
                })
            elif py_var and len(call.args) >= 3:
                cmds.append({
                    'type': 'comp_stream_item', 'py_var': py_var,
                    'item_id_node': call.args[0],
                    'field_node': call.args[1],
                    'val_node': call.args[2],
                    'key': self._kw(call.keywords, 'key', 'id'),
                    'speed': speed,
                })
        else:
            return False
        return True

    def _collection_call(self, cmds, call, func):
        """The items of a list or a collection: set, append, prepend, scroll, update, remove, merge, refresh."""
        # comp.set_items(items) — lista literal OU string JSON
        # (ex: resultado de db.query / https) com title=/subtitle=
        if isinstance(func, ast.Attribute) and func.attr == 'set_items':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var and call.args:
                items_node = call.args[0]
                # Uma lista que a app muda NAO pode ser trocada pelo
                # seu literal aqui: o ecra ficaria a mostrar a lista de
                # origem por muito que ela tivesse crescido. Fica o
                # nome, e o _val_to_java le o estado partilhado.
                if (isinstance(items_node, ast.Name)
                        and items_node.id in self.list_assignments
                        and items_node.id not in self.mutated_lists):
                    items_node = self.list_assignments[items_node.id]
                cmds.append({'type': 'comp_set_items', 'py_var': py_var, 'items_node': items_node,
                              'title_key': self._kw(call.keywords, 'title'),
                              'subtitle_key': self._kw(call.keywords, 'subtitle'),
                              'image_key': self._kw(call.keywords, 'image'),
                              'has_more_node': self._kw_node(
                                  call.keywords, 'has_more'
                              )})

        elif isinstance(func, ast.Attribute) and func.attr == 'append_items':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var and call.args:
                items_node = call.args[0]
                # Uma lista que a app muda NAO pode ser trocada pelo
                # seu literal aqui: o ecra ficaria a mostrar a lista de
                # origem por muito que ela tivesse crescido. Fica o
                # nome, e o _val_to_java le o estado partilhado.
                if (isinstance(items_node, ast.Name)
                        and items_node.id in self.list_assignments
                        and items_node.id not in self.mutated_lists):
                    items_node = self.list_assignments[items_node.id]
                cmds.append({
                    'type': 'comp_append_items',
                    'py_var': py_var,
                    'items_node': items_node,
                    'has_more_node': self._kw_node(
                        call.keywords, 'has_more'
                    ),
                })

        elif isinstance(func, ast.Attribute) and func.attr == 'prepend_items':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var and call.args:
                items_node = call.args[0]
                # Uma lista que a app muda NAO pode ser trocada pelo
                # seu literal aqui: o ecra ficaria a mostrar a lista de
                # origem por muito que ela tivesse crescido. Fica o
                # nome, e o _val_to_java le o estado partilhado.
                if (isinstance(items_node, ast.Name)
                        and items_node.id in self.list_assignments
                        and items_node.id not in self.mutated_lists):
                    items_node = self.list_assignments[items_node.id]
                cmds.append({
                    'type': 'comp_prepend_items',
                    'py_var': py_var,
                    'items_node': items_node,
                })

        elif isinstance(func, ast.Attribute) and func.attr in (
                'scroll_to_end', 'scroll_to_top', 'scroll_to_item'):
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var:
                cmds.append({
                    'type': 'comp_scroll_to',
                    'py_var': py_var,
                    'mode': func.attr[len('scroll_to_'):],
                    'item_id_node': call.args[0] if call.args else None,
                    'key_node': self._kw_node(call.keywords, 'key'),
                })

        elif isinstance(func, ast.Attribute) and func.attr == 'update_item':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var and len(call.args) >= 2:
                changes_node = call.args[1]
                if (isinstance(changes_node, ast.Name)
                        and changes_node.id in self.dict_assignments):
                    changes_node = self.dict_assignments[changes_node.id]
                cmds.append({
                    'type': 'comp_update_item',
                    'py_var': py_var,
                    'item_id_node': call.args[0],
                    'changes_node': changes_node,
                    'key_node': self._kw_node(call.keywords, 'key'),
                    'optimistic_node': self._kw_node(
                        call.keywords, 'optimistic'
                    ),
                })

        elif isinstance(func, ast.Attribute) and func.attr == 'remove_item':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var and call.args:
                cmds.append({
                    'type': 'comp_remove_item',
                    'py_var': py_var,
                    'item_id_node': call.args[0],
                    'key_node': self._kw_node(call.keywords, 'key'),
                    'optimistic_node': self._kw_node(
                        call.keywords, 'optimistic'
                    ),
                })

        elif isinstance(func, ast.Attribute) and func.attr == 'merge_items':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var and call.args:
                items_node = call.args[0]
                # Uma lista que a app muda NAO pode ser trocada pelo
                # seu literal aqui: o ecra ficaria a mostrar a lista de
                # origem por muito que ela tivesse crescido. Fica o
                # nome, e o _val_to_java le o estado partilhado.
                if (isinstance(items_node, ast.Name)
                        and items_node.id in self.list_assignments
                        and items_node.id not in self.mutated_lists):
                    items_node = self.list_assignments[items_node.id]
                cmds.append({
                    'type': 'comp_merge_items',
                    'py_var': py_var,
                    'items_node': items_node,
                    'key_node': self._kw_node(call.keywords, 'key'),
                })

        elif isinstance(func, ast.Attribute) and func.attr in (
                'rollback', 'commit'):
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var:
                mutation_node = (
                    call.args[0] if call.args
                    else self._kw_node(call.keywords, 'mutation_id')
                )
                cmds.append({
                    'type': (
                        'comp_feed_rollback'
                        if func.attr == 'rollback'
                        else 'comp_feed_commit'
                    ),
                    'py_var': py_var,
                    'mutation_node': mutation_node,
                })

        elif isinstance(func, ast.Attribute) and func.attr == 'finish_load':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var:
                has_more_node = (
                    call.args[0] if call.args
                    else self._kw_node(call.keywords, 'has_more')
                )
                cmds.append({
                    'type': 'comp_finish_load',
                    'py_var': py_var,
                    'has_more_node': has_more_node,
                })

        elif isinstance(func, ast.Attribute) and func.attr == 'refresh':
            py_var = func.value.id if isinstance(func.value, ast.Name) else None
            if py_var:
                cmds.append({
                    'type': 'comp_refresh',
                    'py_var': py_var,
                })
        else:
            return False
        return True

    def _screen_call(self, cmds, call, func, func_id):
        """The drawer, sheets and dialogs, a pager's tab, set_state, show and hide, going to another screen,
        back, a list's append, and a call of one of the app's own functions."""
        # menu.open() -- a gaveta e' parte do layout, nao um dialogo,
        # por isso tem o seu proprio comando em vez de um overlay.
        if isinstance(func, ast.Attribute) and func.attr in ('open', 'close') and \
                self.drawer_var and isinstance(func.value, ast.Name) and \
                func.value.id == self.drawer_var:
            cmds.append({'type': 'drawer_' + func.attr})

        elif isinstance(func, ast.Attribute) and func.attr in ('open', 'close') and \
                isinstance(func.value, ast.Name) and (
                    func.value.id in self.overlays
                    or func.value.id in getattr(self, 'overlay_names', ())):
            cmds.append({
                'type': 'overlay_open' if func.attr == 'open' else 'overlay_close',
                'overlay': func.value.id,
            })

        # tabs.select(1) -- a pager slides to a page, as a tap on its tab
        elif (isinstance(func, ast.Attribute) and func.attr == 'select'
                and isinstance(func.value, ast.Name)
                and (self.component_vars.get(func.value.id) or {}).get('_pager')):
            cmds.append({
                'type': 'pager_select', 'py_var': func.value.id,
                'index_node': call.args[0] if call.args else ast.Constant(value=0),
            })

        # comp.show() / comp.hide() — visibilidade (ex: spinner de loading)
        elif isinstance(func, ast.Attribute) and func.attr == 'set_state' and \
                isinstance(func.value, ast.Name):
            state_node = (call.args[0] if call.args
                          else self._kw_node(call.keywords, 'state'))
            cmds.append({'type': 'comp_state', 'py_var': func.value.id,
                         'state_node': state_node})

        elif isinstance(func, ast.Attribute) and func.attr in ('show', 'hide') and \
                isinstance(func.value, ast.Name):
            cmds.append({'type': 'comp_visibility', 'py_var': func.value.id, 'visible': func.attr == 'show'})

        # on_click_navigate(screen, {"key": val}) or data={...} -- navegar
        # passando dados. Positional, as the signature allows and the
        # API reference shows, the data was dropped: the next screen
        # opened with every get_param() at its default.
        elif func_id == 'on_click_navigate' and call.args:
            to_var = call.args[0].id if isinstance(call.args[0], ast.Name) else None
            to_sid = self.screens.get(to_var) if to_var else None
            data_node = call.args[1] if len(call.args) > 1 \
                else self._kw_node(call.keywords, 'data')
            data_pairs = _navigate_data_pairs(data_node)
            transition_node = call.args[2] if len(call.args) > 2 \
                else self._kw_node(call.keywords, 'transition')
            transition = transition_node.value \
                if isinstance(transition_node, ast.Constant) else 'none'
            if to_sid:
                cmds.append({
                    'type': 'navigate', 'to_screen_id': to_sid,
                    'data': data_pairs,
                    'transition': motion.normalise_transition(transition or 'none'),
                })

        # back() -- leave this screen for the one that opened it:
        # finish() on the phone, the history's pop in the Previewer.
        # An app's own def back() still wins.
        elif (func_id == 'back' and not call.args and not call.keywords
                and 'back' not in getattr(self, 'own_function_names', ())):
            cmds.append({'type': 'navigate_back'})

        # lista.append(x) — desaparecia inteiro. Era o mais caro dos
        # silêncios: é assim que se constrói uma lista, e o exemplo do
        # chat que vem na biblioteca nunca funcionou no telemóvel.
        elif isinstance(func, ast.Attribute) and func.attr == 'append' \
                and isinstance(func.value, ast.Name) and call.args:
            cmds.append({'type': 'list_append', 'var': func.value.id,
                         'val_node': call.args[0],
                         'lineno': getattr(call, 'lineno', 0)})

        # Chamadas locais a outras funções Python (ex: atualizar_ui()
        # ou remover(item["title"]) — os argumentos são preservados).
        elif isinstance(func, ast.Name):
            # keywords_nodes: um bloco native.java_async() responde pelo
            # on_result=, e deitar fora as keywords perdia o callback.
            native_feature.register_callback(self, call)
            cmds.append({'type': 'function_call', 'name': func.id,
                         'args_nodes': list(call.args),
                         'keywords_nodes': {k.arg: k.value
                                            for k in call.keywords if k.arg},
                         'lineno': getattr(call, 'lineno', 0)})
        else:
            return False
        return True
