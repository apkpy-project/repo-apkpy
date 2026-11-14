"""A component of a screen, with its arguments: button(), card(), list_view() and the rest."""
import ast

from ...features import pager as pager_feature
from ...features import chart as chart_feature
from ...features import choice as choice_feature
from ...features import field as field_feature
from ...features import web_page as web_page_feature
from ...features import draw_pad as draw_pad_feature
from ...features import keyboard as keyboard_feature
from .... import field_rules as _field_rules
from ...features import sheet as sheet_feature
from ...features import zoom as zoom_feature
from ...features import gestures as gestures_feature
from .... import chart_rules as _chart_rules
from ...features import maps as maps_feature
from ...features import rich_content as rich_content_feature
from ...features import feeds as feeds_feature
from ...features import file_picker as file_picker_feature
from ...features import camera_view as camera_view_feature
from ....theme import (
    normalize_button_variant, normalize_card_variant, normalize_label_variant,
    normalize_skeleton_variant,
)
from ..style import _parse_aspect_ratio
from ..statements import _change_lambda, _parse_search_onchange
from ..rows import _assign_row_ids, _package_row_pictures


class ComponentReader:
    """A component of a screen, with its arguments: button(), card(), list_view() and the rest."""

    def _parse_component_call(self, comp_type, call, py_var=None):
        """A component; inside a virtual_collection(row=...) template it is
        marked, and its commands receive the row's item."""
        parent_var = self._kw(call.keywords, 'parent')
        parent = self.component_vars.get(parent_var) if parent_var else None
        in_row = bool(parent and (parent.get('_row_template') or parent.get('_in_row')))
        previous = getattr(self, '_row_context', False)
        self._row_context = in_row
        try:
            comp = self._parse_component_call_inner(comp_type, call, py_var)
        finally:
            self._row_context = previous
        if comp is not None and in_row:
            comp['_in_row'] = True
        return comp

    def _parse_component_call_inner(self, comp_type, call, py_var=None):
        """
        Extrai info de uma chamada de componente e associa ao Screen ou Parent correto.
        Devolve o dict do componente ou None se não tiver screen/parent.
        """
        screen_var = self._kw(call.keywords, 'screen')
        parent_var = self._kw(call.keywords, 'parent')
        
        if screen_var is None and parent_var is None and py_var is None:
            return None  # modo legado, sem Screen nem parent
        if parent_var in self.overlays and parent_var not in self.component_vars:
            # It showed in the Previewer and was dropped on the phone.
            sheet_feature.refuse_child_of_plain_sheet(parent_var, getattr(call, 'lineno', 0))

        screen_id = self.screens.get(screen_var) if screen_var else None

        api_comp_type = comp_type
        normalized_type = (
            'image' if comp_type == 'avatar'
            else 'map' if comp_type == 'map_view'
            # upload_button is sugar: it renders and styles as a real button.
            else 'button' if comp_type == 'upload_button'
            # A pager and each of its tabs are containers, marked: everything
            # done for a container (ids, shapes, callbacks inside) still holds.
            else 'container' if comp_type in ('pager', 'tab')
            else comp_type
        )
        comp = {'comp_type': normalized_type, 'screen_id': screen_id, '_py_var': py_var, 'children': []}

        # describe= vale para qualquer componente, por isso e' lido aqui e nao
        # em cada um dos que o usam. A ausencia e a string vazia dizem coisas
        # diferentes: "ninguem escreveu" e "isto e' decoracao, salta".
        _described = self._kw_node(call.keywords, 'describe')
        if isinstance(_described, ast.Constant):
            comp['describe'] = str(_described.value or '')
        # Inside a row= template: visible="{field}" shows or hides this
        # component per item; a button's active="{field}" lights active_icon.
        for _flag in ('visible', 'active', 'active_icon'):
            _flag_node = self._kw_node(call.keywords, _flag)
            if isinstance(_flag_node, ast.Constant) and _flag_node.value is not None:
                comp[_flag] = _flag_node.value

        if comp_type in rich_content_feature.COMPONENT_NAMES:
            rich_content_feature.parse_component(self, comp_type, call, comp)
        elif comp_type == 'map_view':
            maps_feature.parse_component(self, call, comp, py_var)
        elif comp_type == 'camera_view':
            camera_view_feature.parse_component(self, call, comp)
        elif comp_type == 'upload_button':
            file_picker_feature.parse_upload_button(self, call, comp, py_var)
        elif comp_type == 'button':
            comp['text']       = self._first_arg(call, 'text')
            comp['id']         = self._kw(call.keywords, 'id')
            comp['variant']    = normalize_button_variant(self._kw(call.keywords, 'variant'))
            comp['icon']       = self._kw(call.keywords, 'icon')
            comp['command'] = self._parse_callback_kw(
                call, 'command', py_var or comp.get('id') or 'btn',
            )
            comp['on_click']   = self._kw(call.keywords, 'on_click')
        elif comp_type in ('inputs', 'input_field'):
            self._inputs_component(call, py_var, comp)
        elif comp_type == 'label':
            comp['text'] = self._first_arg(call, 'text')
            comp['id']   = self._kw(call.keywords, 'id')
            comp['variant'] = normalize_label_variant(
                self._kw(call.keywords, 'variant')
            )

        elif comp_type in choice_feature.COMPONENTS:
            choice_feature.parse(self, comp_type, call, comp, py_var)

        elif comp_type == web_page_feature.COMPONENT:
            web_page_feature.parse(self, call, comp)

        elif comp_type == draw_pad_feature.COMPONENT:
            draw_pad_feature.parse(self, call, comp, py_var)

        elif comp_type == 'chart':
            self._chart_component(call, py_var, comp)

        elif comp_type == 'pager':
            comp['id'] = self._kw(call.keywords, 'id')
            comp['_pager'] = True

        elif comp_type == 'tab':
            comp['id'] = self._kw(call.keywords, 'id')
            comp['_tab'] = True
            comp['_tab_text'] = self._first_arg(call, 'text') or ''
            comp['_tab_icon'] = self._kw(call.keywords, 'icon')
            _tab_parent = self.component_vars.get(parent_var) if parent_var else None
            if not (_tab_parent and _tab_parent.get('_pager')):
                pager_feature.refuse_orphan_tab(getattr(call, 'lineno', 0))

        elif comp_type == 'container':
            comp['id'] = self._kw(call.keywords, 'id')
            # on_click=fn: the whole box is tapped, as a button is.
            comp['command'] = self._parse_callback_kw(
                call, 'on_click', py_var or comp.get('id') or 'box',
            )

        elif comp_type == 'list_row':
            comp['text'] = self._first_arg(call, 'text')
            comp['id'] = self._kw(call.keywords, 'id')
            for key in ('subtitle', 'icon', 'trailing', 'trailing_icon'):
                comp[key] = self._kw(call.keywords, key)
            # A row is tapped like a button, so it reuses the button's command
            # parsing wholesale -- lambda, bound method or plain name.
            comp['command'] = self._parse_callback_kw(
                call, 'command', py_var or comp.get('id') or 'row',
            )
            comp['on_click'] = self._kw(call.keywords, 'on_click')


        elif comp_type == 'card':
            self._card_component(call, py_var, comp)

        elif comp_type in ('image', 'avatar'):
            self._image_component(call, py_var, api_comp_type, comp)

        elif comp_type == 'video':
            self._video_component(call, py_var, comp)

        elif comp_type == 'spinner':
            comp['id'] = self._kw(call.keywords, 'id')
            vis = self._kw(call.keywords, 'visible', True)
            comp['visible'] = False if vis in (False, 'False', 'false') else True

        elif comp_type == 'skeleton':
            comp['id'] = self._kw(call.keywords, 'id')
            comp['variant'] = normalize_skeleton_variant(
                self._kw(call.keywords, 'variant',
                         call.args[0].value if call.args and isinstance(call.args[0], ast.Constant)
                         else 'music_card')
            )
            try:
                comp['count'] = max(1, int(self._kw(call.keywords, 'count', 1)))
            except (TypeError, ValueError):
                comp['count'] = 1
            vis = self._kw(call.keywords, 'visible', True)
            comp['visible'] = False if vis in (False, 'False', 'false') else True

        elif comp_type in ('empty_state', 'error_state'):
            self._state_component(comp_type, call, comp)

        elif comp_type == 'list_view':
            self._list_view_component(call, py_var, comp)

        elif comp_type == 'virtual_collection':
            self._virtual_collection_component(call, py_var, comp)

        elif comp_type == 'carousel':
            self._carousel_component(call, py_var, comp)

        elif comp_type == 'grid':
            self._grid_component(call, py_var, comp)

        if py_var:
            self.component_vars[py_var] = comp

        if parent_var and parent_var in self.component_vars:
            self.component_vars[parent_var]['children'].append(comp)
        elif screen_id:
            self.screen_components.setdefault(screen_id, []).append(comp)

        return comp

    def _inputs_component(self, call, py_var, comp):
        """inputs()."""
        # placeholder is the first parameter, so it is usually positional --
        # but inputs(placeholder="...") is equally valid and the Previewer
        # honours it. Reading only args[0] left android:hint="" and the
        # field came out blank on the phone after showing its hint on the
        # desktop.
        comp['placeholder'] = self._first_arg(call, 'placeholder')
        comp['id']          = self._kw(call.keywords, 'id')
        comp['input_type']  = self._kw(call.keywords, 'type', 'text')
        _field_rules.check_known(comp['input_type'], line=getattr(call, 'lineno', 0))
        # Suporte a password=True (sintaxe alternativa)
        for kw in call.keywords:
            if kw.arg == 'password' and isinstance(kw.value, ast.Constant) and kw.value.value:
                comp['input_type'] = 'password'
        # Pesquisa em tempo real: on_change=lambda q: alvo.set_items([...])
        # — guarda o alvo, o nome da query e a condição p/ gerar um
        #   TextWatcher no Android (paridade com o filtro do previewer).
        on_change_node = self._kw_node(call.keywords, 'on_change')
        search = _parse_search_onchange(on_change_node)
        if search:
            comp['search'] = search
        elif isinstance(on_change_node, ast.Name):
            # A regular named callback is different from the specialised
            # ``lambda q: list.set_items(...)`` fast path above.  Keep it
            # so Android can call the same Python function on every text
            # change, just like the desktop Previewer already does.
            comp['on_change'] = on_change_node.id
        elif isinstance(on_change_node, ast.Lambda):
            # Any other lambda: a function of its own, so the same
            # listener calls it. It used to be dropped here.
            comp['on_change'] = _change_lambda(
                self, on_change_node, comp.get('id') or py_var or 'input')
        # type="email" and the rest of the keyboard; email/phone/url become "text" here.
        keyboard_feature.parse(self, call, comp, py_var)
        field_feature.parse(self, call, comp, py_var)

    def _chart_component(self, call, py_var, comp):
        """chart()."""
        comp['id'] = self._kw(call.keywords, 'id')
        _chart_kind = self._kw(call.keywords, 'kind') or 'bar'
        try:
            comp['kind'] = _chart_rules.normalize_kind(_chart_kind)
        except ValueError:
            chart_feature.refuse_kind(_chart_kind, getattr(call, 'lineno', 0))
        comp['x'] = self._kw(call.keywords, 'x') or 'label'
        comp['y'] = self._kw(call.keywords, 'y') or 'value'
        _chart_items = call.args[0] if call.args else self._kw_node(call.keywords, 'items')
        comp['items_json'] = chart_feature.literal_items(
            _chart_items, getattr(self, 'list_assignments', {}))
        comp['items_node'] = _chart_items if comp['items_json'] is None else None
        comp['fill'] = bool(self._kw(call.keywords, 'fill'))
        comp['value_node'] = self._kw_node(call.keywords, 'value')
        comp['max'] = self._kw(call.keywords, 'max')
        comp['center'] = self._kw(call.keywords, 'center')
        # on_click gets the tapped item, as a list's does: a function
        # that takes it, or a lambda with one parameter.
        _chart_click = self._kw_node(call.keywords, 'on_click')
        if isinstance(_chart_click, ast.Lambda) and _chart_click.args.args:
            _param = _chart_click.args.args[0].arg
            _cb = self._unique_function_name(str(py_var or comp.get('id') or 'chart') + '_click')
            _body = ast.Expr(value=_chart_click.body)
            ast.fix_missing_locations(_body)
            self.functions[_cb] = {'args': [_param],
                                   'cmds': self._parse_statements([_body]),
                                   'string_args': {_param}}
            comp['on_click'] = _cb
        elif isinstance(_chart_click, ast.Name):
            comp['on_click'] = _chart_click.id
        else:
            comp['on_click'] = None
        if comp['on_click']:
            self.json_item_callbacks.add(comp['on_click'])

    def _card_component(self, call, py_var, comp):
        """card()."""
        self._implicit_card_count += 1
        comp['id'] = self._kw(call.keywords, 'id')
        comp['command'] = self._parse_callback_kw(
            call, 'on_click', py_var or comp.get('id') or 'card',
        )
        comp['variant'] = normalize_card_variant(
            self._kw(call.keywords, 'variant', 'elevated')
        )
        prefix = str(comp['id'] or f'card_{self._implicit_card_count}')

        media = self._kw(call.keywords, 'image')
        if media:
            image_comp = {
                'comp_type': 'image', 'screen_id': None, '_py_var': None,
                'id': f'{prefix}_media', 'src': media,
                'card_media': True, 'children': [],
            }
            if isinstance(media, str) and media.startswith(('http://', 'https://')):
                image_comp['_is_remote'] = True
                if 'INTERNET' not in self.declared_permissions:
                    self.declared_permissions.append('INTERNET')
            comp['children'].append(image_comp)

        for key, label_variant, suffix in (
            ('title', 'title', 'title'),
            ('subtitle', 'subtitle', 'subtitle'),
            ('content', 'body', 'body'),
        ):
            value = self._kw(call.keywords, key)
            if value is not None:
                comp['children'].append({
                    'comp_type': 'label', 'screen_id': None,
                    '_py_var': None, 'id': f'{prefix}_{suffix}',
                    'text': str(value), 'variant': label_variant,
                    'children': [],
                })

        actions_node = self._kw_node(call.keywords, 'actions')
        action_nodes = (
            actions_node.elts
            if isinstance(actions_node, (ast.List, ast.Tuple)) else []
        )
        if action_nodes:
            action_row = {
                'comp_type': 'container', 'screen_id': None,
                '_py_var': None, 'id': f'{prefix}_actions',
                'card_actions': True, 'children': [],
            }
            for index, action_node in enumerate(action_nodes):
                action_comp = None
                if isinstance(action_node, ast.Call) and isinstance(action_node.func, ast.Name) and action_node.func.id in ('button', 'card_action'):
                    action_comp = self._parse_component_call(
                        'button', action_node,
                        py_var=f'__{prefix}_action_{index + 1}',
                    )
                elif isinstance(action_node, ast.Constant):
                    action_comp = {
                        'comp_type': 'button', 'screen_id': None,
                        '_py_var': None, 'children': [], 'id': None,
                        'text': str(action_node.value), 'variant': 'text',
                        'icon': None, 'command': None, 'on_click': None,
                    }
                if action_comp:
                    action_row['children'].append(action_comp)
            if action_row['children']:
                comp['children'].append(action_row)

    def _image_component(self, call, py_var, api_comp_type, comp):
        """image() and avatar()."""
        # A picture answers a tap like a button: a story in a tray, a
        # cover on a shelf, a photo that opens.
        comp['command'] = self._parse_callback_kw(
            call, 'command', py_var or self._kw(call.keywords, 'id') or 'image',
        )
        # zoom=True: a tap opens the picture over the whole screen.
        zoom_feature.parse_image(self, call, comp, api_comp_type)
        src_node = call.args[0] if call.args else self._kw_node(call.keywords, 'src')
        comp['src'] = src_node.value if isinstance(src_node, ast.Constant) else ''
        comp['id']  = self._kw(call.keywords, 'id')
        comp['placeholder'] = self._kw(call.keywords, 'placeholder')
        comp['fallback'] = self._kw(call.keywords, 'fallback')
        comp['cache'] = bool(self._kw(call.keywords, 'cache', True))
        comp['fade_in'] = bool(self._kw(
            call.keywords, 'fade_in', True if api_comp_type == 'avatar' else False,
        ))
        try:
            comp['blur'] = max(0.0, float(self._kw(call.keywords, 'blur', 0) or 0))
        except (TypeError, ValueError):
            comp['blur'] = 0.0
        comp['tint'] = self._kw(call.keywords, 'tint')
        comp['aspect_ratio'] = _parse_aspect_ratio(
            self._kw(call.keywords, 'aspect_ratio')
        )
        if api_comp_type == 'avatar':
            comp['avatar'] = True
            try:
                comp['size'] = max(16, int(self._kw(call.keywords, 'size', 48)))
            except (TypeError, ValueError):
                comp['size'] = 48
            status = self._kw(call.keywords, 'status')
            comp['status'] = str(status).lower() if status else None
            comp['aspect_ratio'] = 1.0
        # Imagem remota (URL) — carregada em runtime, não copiada para drawable
        _img_src = comp['src']
        if isinstance(_img_src, str) and (_img_src.startswith('http://') or _img_src.startswith('https://')):
            comp['_is_remote'] = True
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")

    def _video_component(self, call, py_var, comp):
        """video()."""
        src_node = call.args[0] if call.args else self._kw_node(
            call.keywords, 'src'
        )
        comp['src'] = (
            str(src_node.value) if isinstance(src_node, ast.Constant) else ''
        )
        comp['id'] = self._kw(call.keywords, 'id')
        comp['poster'] = self._kw(call.keywords, 'poster')
        comp['autoplay'] = bool(self._kw(call.keywords, 'autoplay', False))
        comp['controls'] = bool(self._kw(call.keywords, 'controls', True))
        comp['loop'] = bool(self._kw(call.keywords, 'loop', False))
        comp['muted'] = bool(self._kw(call.keywords, 'muted', False))
        comp['preload'] = bool(self._kw(call.keywords, 'preload', True))
        comp['aspect_ratio'] = (
            _parse_aspect_ratio(
                self._kw(call.keywords, 'aspect_ratio', '16:9')
            ) or (16.0 / 9.0)
        )
        fit = str(self._kw(call.keywords, 'fit', 'contain')).lower()
        comp['fit'] = fit if fit in ('contain', 'cover', 'fill') else 'contain'
        comp['on_ready'] = self._register_websocket_callback(
            self._kw_node(call.keywords, 'on_ready'), 0,
            f'{py_var or "video"}_ready',
        )
        comp['on_progress'] = self._register_websocket_callback(
            self._kw_node(call.keywords, 'on_progress'), 3,
            f'{py_var or "video"}_progress',
        )
        comp['on_end'] = self._register_websocket_callback(
            self._kw_node(call.keywords, 'on_end'), 0,
            f'{py_var or "video"}_end',
        )
        comp['on_error'] = self._register_websocket_callback(
            self._kw_node(call.keywords, 'on_error'), 1,
            f'{py_var or "video"}_error',
        )
        if any(
                isinstance(value, str)
                and value.startswith(('http://', 'https://'))
                for value in (comp.get('src'), comp.get('poster'))):
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")

    def _state_component(self, comp_type, call, comp):
        """empty_state() and error_state()."""
        self._implicit_state_count += 1
        comp['id'] = self._kw(call.keywords, 'id')
        title_node = call.args[0] if call.args else self._kw_node(call.keywords, 'title')
        message_node = (
            call.args[1] if len(call.args) > 1
            else self._kw_node(call.keywords, 'message')
        )
        comp['title'] = str(title_node.value) if isinstance(title_node, ast.Constant) else ''
        comp['message'] = str(message_node.value) if isinstance(message_node, ast.Constant) else ''
        comp['icon'] = str(self._kw(
            call.keywords, 'icon',
            'error_outline' if comp_type == 'error_state' else 'inbox',
        ))
        vis = self._kw(call.keywords, 'visible', True)
        comp['visible'] = False if vis in (False, 'False', 'false') else True
        prefix = str(comp['id'] or f'state_{self._implicit_state_count}')

        if comp_type == 'empty_state':
            action_node = self._kw_node(call.keywords, 'action')
            command_node = self._kw_node(call.keywords, 'on_action')
            action_comp = None
            if (isinstance(action_node, ast.Call)
                    and isinstance(action_node.func, ast.Name)
                    and action_node.func.id in ('button', 'card_action')):
                action_comp = self._parse_component_call(
                    'button', action_node, py_var=f'__{prefix}_action',
                )
            else:
                action_text = (
                    str(action_node.value) if isinstance(action_node, ast.Constant)
                    else ('Explore' if command_node is not None else '')
                )
                if action_text:
                    action_comp = {
                        'comp_type': 'button', 'screen_id': None,
                        '_py_var': f'__{prefix}_action', 'children': [],
                        'id': f'{prefix}_action', 'text': action_text,
                        'variant': 'filled', 'icon': 'arrow_forward',
                        'command': self._register_overlay_callback(
                            command_node, f'{prefix}_action',
                        ),
                        'on_click': None,
                    }
                    self.component_vars[action_comp['_py_var']] = action_comp
            if action_comp:
                comp['children'].append(action_comp)
        else:
            retry_node = self._kw_node(call.keywords, 'retry')
            if retry_node is not None:
                retry_text = str(self._kw(call.keywords, 'retry_text', 'Try again'))
                action_comp = {
                    'comp_type': 'button', 'screen_id': None,
                    '_py_var': f'__{prefix}_retry', 'children': [],
                    'id': f'{prefix}_retry', 'text': retry_text,
                    'variant': 'filled', 'icon': 'refresh',
                    'command': self._register_overlay_callback(
                        retry_node, f'{prefix}_retry',
                    ),
                    'on_click': None,
                }
                self.component_vars[action_comp['_py_var']] = action_comp
                comp['children'].append(action_comp)

    def _list_view_component(self, call, py_var, comp):
        """list_view()."""
        comp['id'] = self._kw(call.keywords, 'id')
        on_click_node = self._kw_node(call.keywords, 'on_click')
        if isinstance(on_click_node, ast.Lambda):
            lam = on_click_node
            param = lam.args.args[0].arg if lam.args.args else 'item'
            cb_name = (py_var or 'list') + '_onclick'
            body_stmt = ast.Expr(value=lam.body)
            ast.fix_missing_locations(body_stmt)
            cb_cmds = self._parse_statements([body_stmt])
            self.functions[cb_name] = {'args': [param], 'cmds': cb_cmds, 'string_args': {param}}
            comp['on_click'] = cb_name
        elif isinstance(on_click_node, ast.Name):
            comp['on_click'] = on_click_node.id
        else:
            comp['on_click'] = self._kw(call.keywords, 'on_click')
        comp['items']    = []
        items_arg = call.args[0] if call.args else self._kw_node(call.keywords, 'items')
        # Resolver referências de variável (ex: list_view(_history_items, ...))
        if items_arg and isinstance(items_arg, ast.Name):
            # Uma lista de modulo que a app MUDA nao pode ser cravada no
            # onCreate: ao voltar ao ecra, a Activity e' recriada e repunha
            # a lista de ORIGEM por cima da que tinha crescido. Guarda-se o
            # nome, e a construcao le o estado partilhado em runtime.
            if items_arg.id in self.mutated_lists:
                comp['_items_var'] = items_arg.id
            items_arg = self.list_assignments.get(items_arg.id, items_arg)
        if items_arg and isinstance(items_arg, ast.List):
            for elt in items_arg.elts:
                if isinstance(elt, ast.Constant):
                    comp['items'].append(str(elt.value))
                elif isinstance(elt, ast.Dict):
                    # Every key the row was written with, not only the
                    # four the adapters draw: the row is what a tap hands
                    # to on_click, and item["id"] has to be there.
                    row = {'title': '', 'subtitle': ''}
                    for k, v in zip(elt.keys, elt.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                            row[str(k.value)] = (str(v.value) if k.value in (
                                'title', 'subtitle', 'image', 'src') else v.value)
                    comp['items'].append(row)
        # "Linha rica": miniatura + título + subtítulo. Ativo se algum item
        # trouxer "image" OU se rich=True (p/ listas preenchidas dinamicamente).
        _rich_kw = self._kw(call.keywords, 'rich', False)
        comp['rich'] = bool(_rich_kw) or any(
            isinstance(it, dict) and it.get('image') for it in comp['items']
        )
        if comp['rich']:
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")
            # numa lista rica o item passado ao on_click é JSON → item["k"] = _jsonGet
            if comp.get('on_click'):
                self.json_item_callbacks.add(comp['on_click'])

    def _virtual_collection_component(self, call, py_var, comp):
        """virtual_collection()."""
        comp['id'] = self._kw(call.keywords, 'id')
        layout = str(self._kw(call.keywords, 'layout', 'list')).lower()
        comp['layout'] = layout if layout in ('list', 'grid') else 'list'
        try:
            comp['columns'] = max(
                1, int(self._kw(call.keywords, 'columns', 2) or 2)
            )
        except (TypeError, ValueError):
            comp['columns'] = 2
        if comp['layout'] == 'list':
            comp['columns'] = 1
        default_height = 88 if comp['layout'] == 'list' else 224
        _raw_height = self._kw(call.keywords, 'item_height', default_height)
        # item_height="auto": cada linha toma a altura do que leva. Um
        # numero continua a fixar todas, e o XML sai igual ao de antes.
        comp['auto_height'] = (
            isinstance(_raw_height, str)
            and _raw_height.strip().lower() == 'auto'
        )
        if comp['auto_height']:
            comp['item_height'] = default_height
        else:
            try:
                comp['item_height'] = max(
                    56, int(_raw_height or default_height)
                )
            except (TypeError, ValueError):
                comp['item_height'] = default_height
        try:
            comp['buffer'] = max(
                1, min(8, int(self._kw(call.keywords, 'buffer', 2) or 2))
            )
        except (TypeError, ValueError):
            comp['buffer'] = 2
        feeds_feature.parse_pagination(self, call, comp, py_var)
        gestures_feature.parse(self, call, comp)

        row_node = self._kw_node(call.keywords, 'row')
        row_template = (self.component_vars.get(row_node.id)
                        if isinstance(row_node, ast.Name) else None)
        if row_template is not None and row_template.get('_row_template'):
            comp['row'] = row_template
            _assign_row_ids(row_template)
            if self._kw_node(call.keywords, 'item_height') is None:
                # A row of components takes the height of what it holds.
                comp['auto_height'] = True

        default_template = {
            'title': '{title}', 'subtitle': '{subtitle}',
            # Markdown a serio numa linha: enfase, listas, e blocos de
            # codigo com fence. Vazia por omissao, para que nenhuma
            # coleccao ja' escrita ganhe uma TextView nova.
            'markdown': '',
            # Um circulo com as iniciais de quem fala. Vazia por omissao,
            # pela mesma razao: uma lista ja' escrita nao ganha uma vista
            # nova nem uma cor que ninguem pediu.
            'avatar': '',
            'image': '{image}', 'meta': '{meta}', 'badge': '{badge}',
        }
        template_node = self._kw_node(call.keywords, 'template')
        if isinstance(template_node, ast.Name):
            template_node = self.dict_assignments.get(
                template_node.id, template_node
            )
        # ``variant="{role}"`` makes the template a mapping of that
        # field's value to a shape, so one collection holds more than one
        # kind of row. Read here rather than in the generator because the
        # union of the shapes decides which slots the row builds at all.
        comp['variant'] = self._kw(call.keywords, 'variant', None)
        comp['variants'] = {}
        if isinstance(template_node, ast.Dict):
            try:
                literal_template = ast.literal_eval(template_node)
                if comp['variant']:
                    for name, slots in literal_template.items():
                        if not isinstance(slots, dict):
                            continue
                        comp['variants'][str(name)] = {
                            key: str(slots.get(key, ''))
                            for key in default_template
                        }
                    default_template = {
                        key: next(
                            (shape[key]
                             for shape in comp['variants'].values()
                             if shape[key]),
                            '',
                        )
                        for key in default_template
                    }
                else:
                    # Match the Python runtime: once a custom template is
                    # supplied, omitted slots are absent instead of
                    # silently falling back to image/subtitle/meta.
                    default_template = {
                        key: '' for key in default_template
                    }
                    for key in default_template:
                        if key in literal_template:
                            default_template[key] = str(
                                literal_template[key])
            except (ValueError, TypeError, SyntaxError):
                pass
        comp['template'] = default_template

        comp['items'] = []
        items_arg = (
            call.args[0] if call.args
            else self._kw_node(call.keywords, 'items')
        )
        if isinstance(items_arg, ast.Name):
            # Uma lista de modulo que a app MUDA nao pode ser cravada no
            # onCreate: ao voltar ao ecra, a Activity e' recriada e repunha
            # a lista de ORIGEM por cima da que tinha crescido. Guarda-se o
            # nome, e a construcao le o estado partilhado em runtime.
            if items_arg.id in self.mutated_lists:
                comp['_items_var'] = items_arg.id
            items_arg = self.list_assignments.get(items_arg.id, items_arg)
        if isinstance(items_arg, ast.List):
            for element in items_arg.elts:
                try:
                    value = ast.literal_eval(element)
                except (ValueError, TypeError, SyntaxError):
                    continue
                comp['items'].append(
                    value if isinstance(value, dict)
                    else {'title': str(value)}
                )

        on_click_node = self._kw_node(call.keywords, 'on_click')
        if isinstance(on_click_node, ast.Lambda):
            param = (
                on_click_node.args.args[0].arg
                if on_click_node.args.args else 'item'
            )
            cb_name = self._unique_function_name(
                (py_var or comp.get('id') or 'collection') + '_onclick'
            )
            body_stmt = ast.Expr(value=on_click_node.body)
            ast.fix_missing_locations(body_stmt)
            self.functions[cb_name] = {
                'args': [param],
                'cmds': self._parse_statements([body_stmt]),
                'string_args': {param},
            }
            comp['on_click'] = cb_name
        elif isinstance(on_click_node, ast.Name):
            comp['on_click'] = on_click_node.id
        else:
            comp['on_click'] = self._kw(call.keywords, 'on_click')
        if comp.get('on_click'):
            self.json_item_callbacks.add(comp['on_click'])
        if comp['template'].get('image'):
            if 'INTERNET' not in self.declared_permissions:
                self.declared_permissions.append('INTERNET')
        if comp.get('row'):
            comp['template'] = {key: '' for key in comp['template']}
            _package_row_pictures(self, comp)

    def _carousel_component(self, call, py_var, comp):
        """carousel()."""
        # Carrossel HORIZONTAL: prateleira de cartões (capa + título + subtítulo)
        # que desliza para o lado (estilo "Tocados recentemente" do Spotify).
        comp['id'] = self._kw(call.keywords, 'id')
        on_click_node = self._kw_node(call.keywords, 'on_click')
        if isinstance(on_click_node, ast.Lambda):
            lam = on_click_node
            param = lam.args.args[0].arg if lam.args.args else 'item'
            # usa py_var OU o id (único) p/ o nome do callback — 2 carrosséis sem
            # variável davam o mesmo nome e colidiam em self.functions.
            cb_name = (py_var or comp.get('id') or 'car') + '_onclick'
            body_stmt = ast.Expr(value=lam.body)
            ast.fix_missing_locations(body_stmt)
            cb_cmds = self._parse_statements([body_stmt])
            self.functions[cb_name] = {'args': [param], 'cmds': cb_cmds, 'string_args': {param}}
            comp['on_click'] = cb_name
        elif isinstance(on_click_node, ast.Name):
            comp['on_click'] = on_click_node.id
        else:
            comp['on_click'] = self._kw(call.keywords, 'on_click')
        comp['items'] = []
        items_arg = call.args[0] if call.args else self._kw_node(call.keywords, 'items')
        if items_arg and isinstance(items_arg, ast.Name):
            # Uma lista de modulo que a app MUDA nao pode ser cravada no
            # onCreate: ao voltar ao ecra, a Activity e' recriada e repunha
            # a lista de ORIGEM por cima da que tinha crescido. Guarda-se o
            # nome, e a construcao le o estado partilhado em runtime.
            if items_arg.id in self.mutated_lists:
                comp['_items_var'] = items_arg.id
            items_arg = self.list_assignments.get(items_arg.id, items_arg)
        if items_arg and isinstance(items_arg, ast.List):
            for elt in items_arg.elts:
                if isinstance(elt, ast.Dict):
                    title, subtitle, img, src = '', '', '', ''
                    for k, v in zip(elt.keys, elt.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                            if k.value == 'title':      title    = str(v.value)
                            elif k.value == 'subtitle': subtitle = str(v.value)
                            elif k.value == 'image':    img      = str(v.value)
                            elif k.value == 'src':      src      = str(v.value)
                    comp['items'].append({'title': title, 'subtitle': subtitle, 'image': img, 'src': src})
                elif isinstance(elt, ast.Constant):
                    comp['items'].append({'title': str(elt.value), 'subtitle': '', 'image': '', 'src': ''})
        if "INTERNET" not in self.declared_permissions:
            self.declared_permissions.append("INTERNET")
        if comp.get('on_click'):
            self.json_item_callbacks.add(comp['on_click'])

    def _grid_component(self, call, py_var, comp):
        """grid()."""
        # Grelha de cartões (capa + título + subtítulo) em N colunas (estilo a
        # página "Pesquisar" do Spotify). Igual ao carousel mas em grelha vertical.
        comp['id'] = self._kw(call.keywords, 'id')
        try:
            comp['cols'] = max(1, int(self._kw(call.keywords, 'cols', 2) or 2))
        except (ValueError, TypeError):
            comp['cols'] = 2
        on_click_node = self._kw_node(call.keywords, 'on_click')
        if isinstance(on_click_node, ast.Lambda):
            lam = on_click_node
            param = lam.args.args[0].arg if lam.args.args else 'item'
            cb_name = (py_var or comp.get('id') or 'grid') + '_onclick'
            body_stmt = ast.Expr(value=lam.body)
            ast.fix_missing_locations(body_stmt)
            cb_cmds = self._parse_statements([body_stmt])
            self.functions[cb_name] = {'args': [param], 'cmds': cb_cmds, 'string_args': {param}}
            comp['on_click'] = cb_name
        elif isinstance(on_click_node, ast.Name):
            comp['on_click'] = on_click_node.id
        else:
            comp['on_click'] = self._kw(call.keywords, 'on_click')
        comp['items'] = []
        items_arg = call.args[0] if call.args else self._kw_node(call.keywords, 'items')
        if items_arg and isinstance(items_arg, ast.Name):
            # Uma lista de modulo que a app MUDA nao pode ser cravada no
            # onCreate: ao voltar ao ecra, a Activity e' recriada e repunha
            # a lista de ORIGEM por cima da que tinha crescido. Guarda-se o
            # nome, e a construcao le o estado partilhado em runtime.
            if items_arg.id in self.mutated_lists:
                comp['_items_var'] = items_arg.id
            items_arg = self.list_assignments.get(items_arg.id, items_arg)
        if items_arg and isinstance(items_arg, ast.List):
            for elt in items_arg.elts:
                if isinstance(elt, ast.Dict):
                    title, subtitle, img, src = '', '', '', ''
                    for k, v in zip(elt.keys, elt.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                            if k.value == 'title':      title    = str(v.value)
                            elif k.value == 'subtitle': subtitle = str(v.value)
                            elif k.value == 'image':    img      = str(v.value)
                            elif k.value == 'src':      src      = str(v.value)
                    comp['items'].append({'title': title, 'subtitle': subtitle, 'image': img, 'src': src})
                elif isinstance(elt, ast.Constant):
                    comp['items'].append({'title': str(elt.value), 'subtitle': '', 'image': '', 'src': ''})
        if "INTERNET" not in self.declared_permissions:
            self.declared_permissions.append("INTERNET")
        if comp.get('on_click'):
            self.json_item_callbacks.add(comp['on_click'])

    def _parse_responsive_call(self, call, py_var=None):
        """Parse responsive(mobile=column(...), tablet=row(...), ...)."""
        def _layout(name):
            node = self._kw_node(call.keywords, name)
            if node is None:
                return None
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                return None
            if node.func.id not in ('row', 'column'):
                return None
            children = []
            for arg in node.args:
                if not isinstance(arg, ast.Name) or arg.id not in self.component_vars:
                    return None
                children.append(self.component_vars[arg.id])
            return {'direction': node.func.id, 'children': children}

        mobile = _layout('mobile')
        if mobile is None:
            return None
        tablet = _layout('tablet') or mobile
        landscape = _layout('landscape')
        expected = mobile['children']
        for spec in (tablet, landscape):
            if spec is not None and (
                len(spec['children']) != len(expected)
                or any(child not in spec['children'] for child in expected)
            ):
                return None

        screen_var = self._kw(call.keywords, 'screen')
        parent_var = self._kw(call.keywords, 'parent')
        screen_id = self.screens.get(screen_var) if screen_var else None
        if screen_id is None and parent_var is None and py_var is None:
            return None
        try:
            breakpoint = int(self._kw(call.keywords, 'breakpoint', 600) or 600)
        except (TypeError, ValueError):
            breakpoint = 600
        config = {
            'mobile': mobile['direction'],
            'tablet': tablet['direction'],
            'breakpoint': breakpoint,
        }
        if landscape is not None:
            config['landscape'] = landscape['direction']
        comp = {
            'comp_type': 'container',
            'screen_id': screen_id,
            '_py_var': py_var,
            'id': self._kw(call.keywords, 'id'),
            'responsive': config,
            'children': list(expected),
        }

        # Move already attached children into this wrapper, avoiding duplicates.
        for sid, roots in self.screen_components.items():
            self.screen_components[sid] = [item for item in roots if item not in expected]
        if parent_var and parent_var in self.component_vars:
            parent = self.component_vars[parent_var]
            parent['children'] = [item for item in parent['children'] if item not in expected]
            parent['children'].append(comp)
        elif screen_id:
            self.screen_components.setdefault(screen_id, []).append(comp)
        if py_var:
            self.component_vars[py_var] = comp
        return comp
