"""The app bar, the drawer, sheets and dialogs, fonts."""
import ast

from ...features import sheet as sheet_feature
from .... import fonts as _fonts
from ....diagnostics import Diagnostic, report_diagnostic
from ..expressions import _translation_mark


class BarReader:
    """The app bar, the drawer, sheets and dialogs, fonts."""

    def _parse_app_bar_action(self, node, tag):
        """Parse action("icon", command=...) used by app-bar declarations."""
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'action'):
            return None
        icon = (node.args[0].value if node.args and isinstance(node.args[0], ast.Constant)
                else self._kw(node.keywords, 'icon', 'circle'))
        item_id = self._kw(node.keywords, 'id')
        label = self._kw(node.keywords, 'label', str(icon).replace('_', ' '))
        cmd_node = self._kw_node(node.keywords, 'command')
        command = None
        if isinstance(cmd_node, ast.Name):
            command = cmd_node.id
        elif isinstance(cmd_node, ast.Lambda):
            command = self._unique_function_name(f'{tag}_cmd')
            body_stmt = ast.Expr(value=cmd_node.body)
            ast.fix_missing_locations(body_stmt)
            self.functions[command] = {
                'args': [], 'cmds': self._parse_statements([body_stmt]),
                'string_args': set(), 'returns_value': False,
            }
        return {
            'icon': str(icon), 'id': item_id, 'label': str(label),
            'command': command,
        }

    def _parse_app_bar_call(self, kind, call):
        screen_node = self._kw_node(call.keywords, 'screen')
        if not isinstance(screen_node, ast.Name):
            return None
        screen_id = self.screens.get(screen_node.id)
        if not screen_id:
            return None
        title = (call.args[0].value if call.args and isinstance(call.args[0], ast.Constant)
                 else self._kw(call.keywords, 'title', ''))
        bar_id = self._kw(call.keywords, 'id')
        leading_node = self._kw_node(call.keywords, 'leading')
        if isinstance(leading_node, ast.Constant):
            leading = {'icon': str(leading_node.value), 'id': None,
                       'label': str(leading_node.value).replace('_', ' '),
                       'command': None}
        else:
            leading = self._parse_app_bar_action(leading_node, f'{screen_id}_leading')

        actions_node = self._kw_node(call.keywords, 'actions')
        actions = []
        if isinstance(actions_node, (ast.List, ast.Tuple)):
            for index, action_node in enumerate(actions_node.elts, 1):
                parsed = self._parse_app_bar_action(
                    action_node, f'{screen_id}_appbar_action_{index}',
                )
                if parsed:
                    actions.append(parsed)

        meta = {
            'type': kind, 'id': bar_id, 'title': str(title),
            'leading': leading, 'actions': actions,
            'image': self._kw(call.keywords, 'image'),
            'expanded_height': int(self._kw(call.keywords, 'expanded_height', 240)),
            'pinned': bool(self._kw(call.keywords, 'pinned', True)),
        }
        image = meta.get('image')
        if isinstance(image, str) and image.startswith(('http://', 'https://')):
            meta['_is_remote'] = True
            if 'INTERNET' not in self.declared_permissions:
                self.declared_permissions.append('INTERNET')
        self.screen_app_bars[screen_id] = meta
        return meta

    def _overlay_var_name(self, kind, call):
        """A stable name for an overlay nobody assigned to a variable.

        ``popup_menu(anchor=chip, ...)`` and ``context_menu(row, ...)`` attach
        themselves to another component, so they are normally written as bare
        statements -- nothing needs the return value. Only the assigned form
        used to be parsed, so the menu opened in the Previewer and the button
        did nothing at all on the phone.
        """
        anchor_node = (
            call.args[0] if call.args else
            self._kw_node(call.keywords,
                          'target' if kind == 'context_menu' else 'anchor')
        )
        base = anchor_node.id if isinstance(anchor_node, ast.Name) else 'apkpy'
        suffix = 'context' if kind == 'context_menu' else kind
        name = '%s_%s' % (base, suffix)
        index = 2
        while name in self.overlays:
            name = '%s_%s%d' % (base, suffix, index)
            index += 1
        return name

    def _parse_overlay_call(self, kind, call, py_var):
        normalized = 'menu' if kind == 'popup_menu' else kind
        overlay = {
            'type': normalized,
            'id': self._kw(call.keywords, 'id', py_var),
        }
        title_node = call.args[0] if call.args else self._kw_node(call.keywords, 'title')
        if normalized in ('bottom_sheet', 'modal', 'date_picker', 'time_picker'):
            overlay['title'] = (
                str(title_node.value) if isinstance(title_node, ast.Constant) else ''
            )

        if normalized in ('menu', 'context_menu'):
            anchor_node = (
                call.args[0] if call.args else
                self._kw_node(call.keywords, 'anchor' if normalized == 'menu' else 'target')
            )
            overlay['anchor'] = anchor_node.id if isinstance(anchor_node, ast.Name) else None
            items_node = self._kw_node(call.keywords, 'items')
            if items_node is None and len(call.args) > 1:
                items_node = call.args[1]
            overlay['items'] = self._literal_string_list(items_node)
            cb_node = self._kw_node(call.keywords, 'on_select')
            overlay['on_select'] = self._register_overlay_callback(
                cb_node, f'{py_var}_select', with_value=True,
            )
            anchor = self.component_vars.get(overlay['anchor'])
            if anchor is not None:
                anchor['context_overlay' if normalized == 'context_menu' else 'popup_overlay'] = py_var

        elif normalized == 'bottom_sheet':
            content_node = (
                call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'content')
            )
            overlay['content'] = (
                str(content_node.value) if isinstance(content_node, ast.Constant) else ''
            )
            overlay['items'] = self._literal_string_list(self._kw_node(call.keywords, 'items'))
            overlay['close_text'] = str(self._kw(call.keywords, 'close_text', 'Close'))
            overlay['on_select'] = self._register_overlay_callback(
                self._kw_node(call.keywords, 'on_select'),
                f'{py_var}_select', with_value=True,
            )
            overlay['on_close'] = self._register_overlay_callback(
                self._kw_node(call.keywords, 'on_close'), f'{py_var}_close',
            )
            if self._kw_node(call.keywords, 'screen') is not None:
                # With a screen it holds components: label(..., parent=sheet).
                _sheet_text = (_translation_mark(content_node)
                               if content_node is not None else None)
                sheet_feature.parse(
                    self, call, overlay, py_var,
                    self._first_arg(call, 'title'),
                    _sheet_text if _sheet_text is not None else overlay['content'],
                    overlay['on_close'])

        elif normalized == 'modal':
            content_node = (
                call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'content')
            )
            overlay['content'] = (
                str(content_node.value) if isinstance(content_node, ast.Constant) else ''
            )
            overlay['confirm_text'] = str(self._kw(call.keywords, 'confirm_text', 'Confirm'))
            # dismissable=False faz dele uma parede: o botao de voltar,
            # o toque fora e o Cancel deixam de funcionar. E o que uma
            # actualizacao obrigatoria precisa, e nada mais deve usar.
            overlay['dismissable'] = self._kw(
                call.keywords, 'dismissable', True) is not False
            overlay['cancel_text'] = str(self._kw(call.keywords, 'cancel_text', 'Cancel'))
            overlay['on_confirm'] = self._register_overlay_callback(
                self._kw_node(call.keywords, 'on_confirm'), f'{py_var}_confirm',
            )
            overlay['on_cancel'] = self._register_overlay_callback(
                self._kw_node(call.keywords, 'on_cancel'), f'{py_var}_cancel',
            )

        elif normalized in ('date_picker', 'time_picker'):
            overlay['initial'] = str(self._kw(call.keywords, 'initial', '') or '')
            overlay['on_select'] = self._register_overlay_callback(
                self._kw_node(call.keywords, 'on_select'),
                f'{py_var}_select', with_value=True,
            )

        self.overlays[py_var] = overlay
        return overlay

    def _parse_font_call(self, call):
        """font("Tiempos", regular="...", bold="...") at module level."""
        family = self._first_arg(call, 'family')
        if not family:
            return
        slots = {}
        for slot in _fonts.SLOT_ORDER:
            value = self._kw(call.keywords, slot)
            if value:
                slots[slot] = str(value)
        if not slots:
            report_diagnostic(Diagnostic(
                code='U2023',
                title='This typeface has no files',
                message='font("%s") was given no font file.' % family,
                cause=(
                    'A family is the four files it is made of. Without at '
                    'least a regular face there is nothing to put in the APK.'
                ),
                expected='font("%s", regular="assets/Regular.ttf")' % family,
                received='font("%s")' % family,
                suggestions=(
                    'Point regular= at a .ttf or .otf file next to your code.',
                ),
                docs='https://repo-apkpy.pages.dev/themes-styling/',
            ))
            return
        try:
            self.fonts.register(family, slots)
        except ValueError as exc:
            report_diagnostic(Diagnostic(
                code='U2024',
                title='ApkPy cannot do this font slot',
                message=str(exc),
                cause=(
                    'Four slots, because four is what both sides can address: '
                    'Tk has a family plus bold and italic, and Android '
                    'expresses the same four as fontWeight/fontStyle pairs. '
                    'A "medium" would render on the phone and not on the '
                    'desktop, which is the difference this project exists to '
                    'avoid.'
                ),
                expected='regular, bold, italic or bold_italic',
                received=repr(family),
                suggestions=(
                    'Register the extra weight as its own family and name it '
                    'in font-family where you want it.',
                ),
                docs='https://repo-apkpy.pages.dev/themes-styling/',
            ))

    def _parse_drawer_call(self, call, var_name=None):
        """drawer([chat, projects], labels=..., icons=..., header=...)."""
        screens_arg = call.args[0] if call.args else self._kw_node(
            call.keywords, 'screens')
        screen_ids = []
        if isinstance(screens_arg, ast.List):
            for elt in screens_arg.elts:
                if isinstance(elt, ast.Name):
                    sid = self.screens.get(elt.id)
                    if sid:
                        screen_ids.append(sid)
        if not screen_ids:
            return

        def _strings(key):
            node = self._kw_node(call.keywords, key)
            return ([e.value for e in node.elts if isinstance(e, ast.Constant)]
                    if isinstance(node, ast.List) else [])

        labels = _strings('labels')
        icons = _strings('icons')
        while len(labels) < len(screen_ids):
            labels.append(screen_ids[len(labels)])
        while len(icons) < len(screen_ids):
            icons.append('circle')
        self.drawer = {
            'screen_ids': screen_ids,
            'labels': labels,
            'icons': icons,
            'header': self._kw(call.keywords, 'header'),
            'subtitle': self._kw(call.keywords, 'subtitle'),
            'id': self._kw(call.keywords, 'id'),
        }
        self.drawer_var = var_name or self.drawer_var
