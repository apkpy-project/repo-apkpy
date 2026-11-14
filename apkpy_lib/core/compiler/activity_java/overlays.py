"""The drawer, the sheets and dialogs, and the last lines of the class."""
from ...features import styled_dialog as styled_dialog_feature
from .... import dialog_rules as _dialog_rules
from ...features import sheet as sheet_feature
from ...features import font_weight as font_weight_feature
from ..style import _resolve_color
from ..expressions import _drop_unused_struct_fields, _escape_java_literal
from ..statements import _cmds_contain, _fn_cmds


class Overlays:
    """The drawer, the sheets and dialogs, and the last lines of the class."""

    def _write_drawer_and_overlays(self):
        """The mini player's bar, the drawer's Back, and each sheet and dialog the screen opens."""
        lines = self.lines
        if self._mp_active:
            lines.append("")
            lines.append("    // Capa do mini-player — carga async para a ImageView dada.")
            lines.append("    private void _loadMpCover(final android.widget.ImageView iv, final String url) {")
            lines.append("        if (url == null || url.isEmpty()) return;")
            lines.append("        if (!(url.startsWith(\"http://\") || url.startsWith(\"https://\"))) {")
            lines.append("            int _res = _apkpyBundled(url, \"drawable\");")
            lines.append("            if (_res != 0) iv.setImageResource(_res);")
            lines.append("            return;")
            lines.append("        }")
            lines.append("        new Thread(() -> {")
            lines.append("            try {")
            lines.append("                java.net.HttpURLConnection conn = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();")
            lines.append("                conn.setConnectTimeout(10000);")
            lines.append("                conn.setReadTimeout(10000);")
            lines.append("                conn.setInstanceFollowRedirects(true);")
            lines.append("                conn.connect();")
            lines.append("                final android.graphics.Bitmap fbmp = android.graphics.BitmapFactory.decodeStream(conn.getInputStream());")
            lines.append("                conn.disconnect();")
            lines.append("                if (fbmp != null) runOnUiThread(() -> iv.setImageBitmap(fbmp));")
            lines.append("            } catch (Exception e) { }")
            lines.append("        }).start();")
            lines.append("    }")

        if self.drawer_info:
            lines.append("")
            lines.append("    private void _apkpyDrawer(boolean open) {")
            lines.append("        androidx.drawerlayout.widget.DrawerLayout _d = findViewById(R.id.apkpy_drawer);")
            lines.append("        if (_d == null) return;")
            lines.append("        if (open) _d.openDrawer(androidx.core.view.GravityCompat.START);")
            lines.append("        else _d.closeDrawer(androidx.core.view.GravityCompat.START);")
            lines.append("    }")
            lines.append("")
            # Back closes the panel before it leaves the screen, which is what
            # every Android user expects and what DrawerLayout does not do alone.
            # A callback of the dispatcher, not an onBackPressed(): on Android 16
            # an app that targets it is no longer handed onBackPressed(). (Seen
            # on a phone with the old override left in: the panel closed all the
            # same, because DrawerLayout 1.2 takes Back itself there -- so this
            # was code that no longer ran, not yet a fault. Below Android 13
            # nothing but this closes it.) It is on only while the panel shows,
            # so at every other moment Back -- and the system's own animation of
            # it -- is not ours to touch.
            lines.append("    private final androidx.activity.OnBackPressedCallback _apkpyDrawerBack =")
            lines.append("            new androidx.activity.OnBackPressedCallback(false) {")
            lines.append("        @Override public void handleOnBackPressed() { _apkpyDrawer(false); }")
            lines.append("    };")

        lines.extend(sheet_feature.find_override(self._screen_sheets))

        if self.has_overlays:
            lines.append("")
            lines.append("    private void _apkpyCloseOverlay() {")
            lines.append("        if (_apkpyActiveOverlay != null) {")
            lines.append("            _apkpyActiveOverlay.dismiss();")
            lines.append("            _apkpyActiveOverlay = null;")
            lines.append("        }")
            if self.has_popup_menu:
                lines.append("        if (_apkpyActiveMenu != null) {")
                lines.append("            _apkpyActiveMenu.dismiss();")
                lines.append("            _apkpyActiveMenu = null;")
                lines.append("        }")
            lines.append("    }")

        if self.has_bottom_sheet:
            lines.append("")
            lines.append("    private int _apkpyOverlayDp(int value) {")
            lines.append("        return Math.round(value * getResources().getDisplayMetrics().density);")
            lines.append("    }")
            lines.append("")
            lines.append("    private android.widget.TextView _apkpyOverlayText(String text, float size, boolean bold) {")
            lines.append("        android.widget.TextView view = new android.widget.TextView(this);")
            lines.append("        view.setText(text);")
            lines.append("        view.setTextSize(size);")
            lines.append("        view.setTextColor(ContextCompat.getColor(this, R.color.apkpy_text));")
            lines.append("        if (bold) view.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);")
            lines.append("        return view;")
            lines.append("    }")

        for overlay_name, overlay in self.active_overlays.items():
            method = self._overlay_method_name(overlay_name)
            overlay_type = overlay.get('type')
            title = _escape_java_literal(str(overlay.get('title', '')))

            if overlay_type == 'bottom_sheet' and overlay.get('composed'):
                if overlay_name in self._screen_sheets:
                    lines.extend(sheet_feature.open_method(
                        method, overlay_name, overlay,
                        font_weight_feature.dialog_watch(sheet_feature._dialog(overlay_name))))
                else:
                    lines.extend(sheet_feature.absent_method(method))

            elif overlay_type == 'bottom_sheet':
                content = _escape_java_literal(str(overlay.get('content', '')))
                close_text = _escape_java_literal(str(overlay.get('close_text', 'Close')))
                callback = overlay.get('on_select')
                lines.append("")
                lines.append(f"    private void {method}() {{")
                lines.append("        final BottomSheetDialog dialog = new BottomSheetDialog(this);")
                lines.append("        android.widget.LinearLayout body = new android.widget.LinearLayout(this);")
                lines.append("        body.setOrientation(android.widget.LinearLayout.VERTICAL);")
                lines.append("        int pad = _apkpyOverlayDp(20);")
                lines.append("        body.setPadding(pad, _apkpyOverlayDp(12), pad, _apkpyOverlayDp(16));")
                lines.append("        body.setBackgroundColor(ContextCompat.getColor(this, R.color.apkpy_surface));")
                lines.append("        android.view.View handle = new android.view.View(this);")
                lines.append("        android.graphics.drawable.GradientDrawable handleBg = new android.graphics.drawable.GradientDrawable();")
                lines.append("        handleBg.setColor(ContextCompat.getColor(this, R.color.apkpy_text_secondary));")
                lines.append("        handleBg.setCornerRadius(_apkpyOverlayDp(2));")
                lines.append("        handle.setBackground(handleBg);")
                lines.append("        android.widget.LinearLayout.LayoutParams handleLp = new android.widget.LinearLayout.LayoutParams(_apkpyOverlayDp(36), _apkpyOverlayDp(4));")
                lines.append("        handleLp.gravity = android.view.Gravity.CENTER_HORIZONTAL;")
                lines.append("        handleLp.bottomMargin = _apkpyOverlayDp(16);")
                lines.append("        body.addView(handle, handleLp);")
                lines.append(f"        android.widget.TextView heading = _apkpyOverlayText(\"{title}\", 20, true);")
                lines.append("        body.addView(heading);")
                if content:
                    lines.append(f"        android.widget.TextView copy = _apkpyOverlayText(\"{content}\", 14, false);")
                    lines.append("        copy.setTextColor(ContextCompat.getColor(this, R.color.apkpy_text_secondary));")
                    lines.append("        copy.setPadding(0, _apkpyOverlayDp(6), 0, _apkpyOverlayDp(10));")
                    lines.append("        body.addView(copy);")
                for index, item in enumerate(overlay.get('items') or []):
                    escaped_item = _escape_java_literal(str(item))
                    lines.append(f"        android.widget.TextView item{index} = _apkpyOverlayText(\"{escaped_item}\", 16, false);")
                    lines.append(f"        item{index}.setGravity(android.view.Gravity.CENTER_VERTICAL);")
                    lines.append(f"        item{index}.setMinHeight(_apkpyOverlayDp(48));")
                    lines.append(f"        item{index}.setClickable(true);")
                    lines.append(f"        item{index}.setFocusable(true);")
                    if callback:
                        lines.append(f"        item{index}.setOnClickListener(v -> {{ dialog.dismiss(); pythonCallback_{callback}(\"{escaped_item}\"); }});")
                    else:
                        lines.append(f"        item{index}.setOnClickListener(v -> dialog.dismiss());")
                    lines.append(f"        body.addView(item{index});")
                lines.append("        com.google.android.material.button.MaterialButton close = new com.google.android.material.button.MaterialButton(this);")
                lines.append(f"        close.setText(\"{close_text}\");")
                lines.append("        close.setOnClickListener(v -> dialog.dismiss());")
                lines.append("        body.addView(close);")
                lines.append("        dialog.setContentView(body);")
                if overlay.get('on_close'):
                    lines.append("        dialog.setOnDismissListener(d -> { if (_apkpyActiveOverlay == dialog) "
                                 f"_apkpyActiveOverlay = null; pythonCallback_{overlay['on_close']}(); }});")
                else:
                    lines.append("        dialog.setOnDismissListener(d -> { if (_apkpyActiveOverlay == dialog) _apkpyActiveOverlay = null; });")
                lines.append("        _apkpyActiveOverlay = dialog;")
                lines.append("        dialog.show();")
                lines.append(font_weight_feature.dialog_watch("dialog"))
                lines.append("    }")

            elif overlay_type == 'modal':
                content = _escape_java_literal(str(overlay.get('content', '')))
                confirm_text = _escape_java_literal(str(overlay.get('confirm_text', 'Confirm')))
                cancel_text = _escape_java_literal(str(overlay.get('cancel_text', 'Cancel')))
                on_confirm = overlay.get('on_confirm')
                on_cancel = overlay.get('on_cancel')
                lines.append("")
                lines.append(f"    private void {method}() {{")
                lines.append("        MaterialAlertDialogBuilder builder = new MaterialAlertDialogBuilder(this)")
                lines.append(f"                .setTitle(\"{title}\")")
                lines.append(f"                .setMessage(\"{content}\");")
                if on_confirm:
                    lines.append(f"        builder.setPositiveButton(\"{confirm_text}\", (d, w) -> pythonCallback_{on_confirm}());")
                else:
                    lines.append(f"        builder.setPositiveButton(\"{confirm_text}\", null);")
                _dismissable = overlay.get('dismissable', True)
                if not _dismissable:
                    # Sem botao de sair: um Cancel num ecra que nao se pode deixar
                    # e' um botao que nao faz nada, e ninguem acredita no proximo.
                    pass
                elif on_cancel:
                    lines.append(f"        builder.setNegativeButton(\"{cancel_text}\", (d, w) -> pythonCallback_{on_cancel}());")
                else:
                    lines.append(f"        builder.setNegativeButton(\"{cancel_text}\", null);")
                if not _dismissable:
                    # Trava o botao de voltar e o toque fora do dialogo.
                    lines.append("        builder.setCancelable(false);")
                lines.append("        androidx.appcompat.app.AlertDialog dialog = builder.create();")
                lines.append("        dialog.setOnDismissListener(d -> { if (_apkpyActiveOverlay == dialog) _apkpyActiveOverlay = null; });")
                lines.append("        _apkpyActiveOverlay = dialog;")
                lines.append("        dialog.show();")
                lines.append(font_weight_feature.dialog_watch("dialog"))
                lines.append("    }")

            elif overlay_type in ('menu', 'context_menu'):
                anchor_java = self._get_jv_from_py_var(overlay.get('anchor'))
                callback = overlay.get('on_select')
                lines.append("")
                lines.append(f"    private void {method}() {{")
                if anchor_java:
                    lines.append(f"        View anchor = findViewById(R.id.{anchor_java});")
                else:
                    lines.append("        View anchor = findViewById(android.R.id.content);")
                lines.append("        if (anchor == null) return;")
                lines.append("        final PopupMenu popup = new PopupMenu(this, anchor);")
                for index, item in enumerate(overlay.get('items') or []):
                    escaped_item = _escape_java_literal(str(item))
                    lines.append(f"        popup.getMenu().add(0, {index + 1}, {index}, \"{escaped_item}\");")
                if callback:
                    lines.append("        popup.setOnMenuItemClickListener(item -> {")
                    lines.append(f"            pythonCallback_{callback}(String.valueOf(item.getTitle()));")
                    lines.append("            return true;")
                    lines.append("        });")
                lines.append("        popup.setOnDismissListener(menu -> { if (_apkpyActiveMenu == popup) _apkpyActiveMenu = null; });")
                lines.append("        _apkpyActiveMenu = popup;")
                lines.append("        popup.show();")
                lines.append("    }")

            elif overlay_type == 'date_picker':
                callback = overlay.get('on_select')
                initial = _escape_java_literal(str(overlay.get('initial', '')))
                lines.append("")
                lines.append(f"    private void {method}() {{")
                lines.append("        final java.util.Calendar calendar = java.util.Calendar.getInstance();")
                if initial:
                    lines.append(f"        try {{ calendar.setTime(new java.text.SimpleDateFormat(\"yyyy-MM-dd\", java.util.Locale.US).parse(\"{initial}\")); }} catch (Exception ignored) {{}}")
                lines.append("        android.app.DatePickerDialog dialog = new android.app.DatePickerDialog(this, (view, year, month, day) -> {")
                if callback:
                    lines.append(f"            pythonCallback_{callback}(String.format(java.util.Locale.US, \"%04d-%02d-%02d\", year, month + 1, day));")
                lines.append("        }, calendar.get(java.util.Calendar.YEAR), calendar.get(java.util.Calendar.MONTH), calendar.get(java.util.Calendar.DAY_OF_MONTH));")
                lines.append("        dialog.setTitle(\"" + title + "\");")
                lines.append("        dialog.setOnDismissListener(d -> { if (_apkpyActiveOverlay == dialog) _apkpyActiveOverlay = null; });")
                lines.append("        _apkpyActiveOverlay = dialog;")
                lines.append("        dialog.show();")
                lines.append("    }")

            elif overlay_type == 'time_picker':
                callback = overlay.get('on_select')
                initial = str(overlay.get('initial', ''))
                hour, minute = -1, -1
                try:
                    hour, minute = [int(part) for part in initial.split(':', 1)]
                except Exception:
                    pass
                lines.append("")
                lines.append(f"    private void {method}() {{")
                lines.append("        final java.util.Calendar calendar = java.util.Calendar.getInstance();")
                hour_expr = str(hour) if 0 <= hour <= 23 else 'calendar.get(java.util.Calendar.HOUR_OF_DAY)'
                minute_expr = str(minute) if 0 <= minute <= 59 else 'calendar.get(java.util.Calendar.MINUTE)'
                lines.append("        android.app.TimePickerDialog dialog = new android.app.TimePickerDialog(this, (view, hour, minute) -> {")
                if callback:
                    lines.append(f"            pythonCallback_{callback}(String.format(java.util.Locale.US, \"%02d:%02d\", hour, minute));")
                lines.append(f"        }}, {hour_expr}, {minute_expr}, true);")
                lines.append("        dialog.setTitle(\"" + title + "\");")
                lines.append("        dialog.setOnDismissListener(d -> { if (_apkpyActiveOverlay == dialog) _apkpyActiveOverlay = null; });")
                lines.append("        _apkpyActiveOverlay = dialog;")
                lines.append("        dialog.show();")
                lines.append("    }")

    def _write_dialogs_and_close(self):
        """alert and confirm, the state drawables, bundled files, and the brace that ends the class."""
        lines = self.lines
        _styled_dialogs = (self.has_alert or self.has_confirm) and _dialog_rules.wanted(self.styles)
        if _styled_dialogs:
            lines.extend(styled_dialog_feature.java_helper(
                self.styles, lambda c: str(_resolve_color(c))))
        if self.has_alert and _styled_dialogs:
            lines.append("")
            lines.append("    private void _alertDialog(String title, String message, String ok) {")
            lines.append("        _apkpyStyledDialog(title, message, ok != null ? ok : getString(android.R.string.ok), null, null, null);")
            lines.append("    }")
        elif self.has_alert:
            lines.append("")
            # ok=None is the system's own OK, in the phone's language.
            lines.append("    private void _alertDialog(String title, String message, String ok) {")
            lines.append("        ApkpyWeight.watch(new AlertDialog.Builder(this)")
            lines.append("                .setTitle(title)")
            lines.append("                .setMessage(message)")
            lines.append("                .setPositiveButton(ok != null ? ok : getString(android.R.string.ok), null)")
            lines.append("                .show().getWindow());")
            lines.append("    }")

        _stateful = [cc for cc in self.all_comps_flat
                     if (cc.get('_state_drawables') or cc.get('_state_text'))
                     and cc.get('_java_var')]
        if _stateful or _cmds_contain(self.module_init_cmds, 'comp_state') or any(
                _cmds_contain(_fn_cmds(body), 'comp_state')
                for body in (self.functions_map or {}).values()):
            # set_state(): the drawable and the text colour compiled for each
            # `id:state` block; None puts back what the view was inflated with.
            lines.append("")
            lines.append("    private final java.util.HashMap<Integer, Object[]> _apkpyStateBase = new java.util.HashMap<>();")
            lines.append("")
            lines.append("    private void _apkpySetState(int id, String state) {")
            lines.append("        View v = findViewById(id);")
            lines.append("        if (v == null) return;")
            lines.append("        if (!_apkpyStateBase.containsKey(id)) _apkpyStateBase.put(id, new Object[]{")
            lines.append("                v.getBackground(), v instanceof TextView ? ((TextView) v).getTextColors() : null});")
            lines.append("        Object[] base = _apkpyStateBase.get(id);")
            lines.append("        String s = state == null ? \"\" : state;")
            lines.append("        int bg = 0, fg = 0; boolean hasFg = false;")
            for cc in _stateful:
                _jv = cc['_java_var']
                for _st, _res in sorted((cc.get('_state_drawables') or {}).items()):
                    lines.append(f"        if (id == R.id.{_jv} && s.equals(\"{_st}\")) bg = R.drawable.{_res};")
                for _st, _hex in sorted((cc.get('_state_text') or {}).items()):
                    lines.append(f"        if (id == R.id.{_jv} && s.equals(\"{_st}\")) {{ fg = android.graphics.Color.parseColor(\"{_hex}\"); hasFg = true; }}")
            lines.append("        int l = v.getPaddingLeft(), t = v.getPaddingTop(), r = v.getPaddingRight(), b = v.getPaddingBottom();")
            lines.append("        if (bg != 0) v.setBackgroundResource(bg); else v.setBackground((android.graphics.drawable.Drawable) base[0]);")
            lines.append("        v.setPadding(l, t, r, b);")
            lines.append("        if (v instanceof TextView) {")
            lines.append("            if (hasFg) ((TextView) v).setTextColor(fg);")
            lines.append("            else if (base[1] != null) ((TextView) v).setTextColor((android.content.res.ColorStateList) base[1]);")
            lines.append("        }")
            lines.append("    }")

        if self.has_confirm:
            lines.append("")
            lines.append("    private interface ConfirmCallback { void onResult(boolean confirmed); }")
            lines.append("")
            # "OK" and "Cancel" were written in English into every app; with no
            # ok=/cancel= the buttons are the system's, in the phone's language.
            lines.append("    private void _confirmDialog(String title, String message, String ok, String cancel, final ConfirmCallback cb) {")
            if _styled_dialogs:
                lines.append("        _apkpyStyledDialog(title, message, ok != null ? ok : getString(android.R.string.ok),")
                lines.append("                cancel != null ? cancel : getString(android.R.string.cancel),")
                lines.append("                () -> { if (cb != null) cb.onResult(true); },")
                lines.append("                () -> { if (cb != null) cb.onResult(false); });")
                lines.append("    }")
        if self.has_confirm and not _styled_dialogs:
            lines.append("        ApkpyWeight.watch(new AlertDialog.Builder(this)")
            lines.append("                .setTitle(title)")
            lines.append("                .setMessage(message)")
            lines.append("                .setPositiveButton(ok != null ? ok : getString(android.R.string.ok), (d, w) -> { if (cb != null) cb.onResult(true); })")
            lines.append("                .setNegativeButton(cancel != null ? cancel : getString(android.R.string.cancel), (d, w) -> { if (cb != null) cb.onResult(false); })")
            lines.append("                .show().getWindow());")
            lines.append("    }")

        if any('_apkpyBundled(' in line for line in lines):
            # A file packaged with the app, found by the name the compiler gave
            # it (_android_drawable_name): basename, no extension, lower case,
            # [a-z0-9_], "img_" before a leading digit.
            lines.append("")
            lines.append("    private int _apkpyBundled(String source, String type) {")
            lines.append("        if (source == null) return 0;")
            lines.append("        String name = source.trim();")
            lines.append("        name = name.substring(Math.max(name.lastIndexOf('/'), name.lastIndexOf(92)) + 1);")
            lines.append("        int dot = name.lastIndexOf('.');")
            lines.append("        if (dot > 0) name = name.substring(0, dot);")
            lines.append("        name = name.toLowerCase(java.util.Locale.ROOT).replaceAll(\"[^a-z0-9_]\", \"_\");")
            lines.append("        if (name.isEmpty()) return 0;")
            lines.append("        if (!Character.isLetter(name.charAt(0))) name = \"img_\" + name;")
            lines.append("        return getResources().getIdentifier(name, type, getPackageName());")
            lines.append("    }")

        lines.append("}")
        return "\n".join(_drop_unused_struct_fields(lines))
