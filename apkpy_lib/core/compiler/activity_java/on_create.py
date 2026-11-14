"""onCreate, from its first line to its last."""
from ...features import web_page as web_page_feature
from ...features import sheet as sheet_feature
from ...features import data as data_feature
from ...features import jobs as jobs_feature
from ...features import font_weight as font_weight_feature
from ...features import pending_views as pending_views_feature
from ...features import keyboard as keyboard_feature
from ....theme import nav_look as _nav_look
from ....theme import component_style
from ..state import _I18N, _PENDING_TARGETS, _USES_CRASH, _USES_FLASHLIGHT, _WARM_WEB
from ..style import (
    _android_drawable_name, _color_java, _get_style_bg, _parse_font_size, _resolve_color,
)
from ..resources_xml import _drawer_item_id, _safe_android_id
from ..expressions import _callback_call_args, _escape_java_literal
from ..statements import _SearchUntranslatable, _report_untranslatable_search, _search_cond_java


class OnCreate:
    """onCreate, from its first line to its last."""

    def _open_on_create(self):
        """From the appearance check to the end of the screen's own setup: content view, system bars, bottom
        navigation, drawer, services, the notification permission."""
        styles = self.styles
        lines = self.lines
        screen_id = self.screen_id
        app_bar_info = self.app_bar_info
        start_screen_id = self.start_screen_id
        drawer_info = self.drawer_info
        self._declared_appearance = 'dark' if (
            (styles.get('__theme__', {}) or {}).get('mode') == 'dark'
        ) else 'light'
        lines.extend([
            "    // The appearance this Activity's views were inflated with. onResume",
            "    // compares it against what is stored: a screen that was stopped when",
            "    // the mode changed comes back wearing the old one.",
            "    private String _apkpyAppearanceShown = \"\";",
            "",
            "    // Which colour table answers: values/ or values-night/. Applied",
            "    // before the layout inflates, because after it the views already",
            "    // hold the colours of the mode that is on its way out.",
            "    private String _apkpyDeclaredAppearance() {",
            f'        return "{self._declared_appearance}";',
            "    }",
            "",
            "    private void _apkpyApplyAppearance(String mode) {",
            "        int night;",
            '        if ("light".equals(mode)) {',
            "            night = androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO;",
            '        } else if ("dark".equals(mode)) {',
            "            night = androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES;",
            "        } else {",
            "            night = androidx.appcompat.app.AppCompatDelegate"
            ".MODE_NIGHT_FOLLOW_SYSTEM;",
            "        }",
            "        if (androidx.appcompat.app.AppCompatDelegate.getDefaultNightMode()",
            "                != night) {",
            "            // AppCompat recreates the started activities itself; calling",
            "            // recreate() here as well would run onCreate twice.",
            "            androidx.appcompat.app.AppCompatDelegate"
            ".setDefaultNightMode(night);",
            "        }",
            "    }",
            "",
        ])

        lines.append("    @Override")
        lines.append("    protected void onCreate(Bundle savedInstanceState) {")
        if self.secure_screen:
            # Before setContentView, or the first frame can still be captured.
            lines.append("        // secure_screen(): no screenshots, and blank in recents.")
            lines.append("        getWindow().setFlags(")
            lines.append("                android.view.WindowManager.LayoutParams.FLAG_SECURE,")
            lines.append("                android.view.WindowManager.LayoutParams.FLAG_SECURE);")
        lines.append(
            '        _apkpyAppearanceShown = _apkpyStorageGet("__apkpy_appearance", '
            f'"{self._declared_appearance}");'
        )
        lines.append("        _apkpyApplyAppearance(_apkpyAppearanceShown);")
        if _USES_CRASH[0]:
            # Antes de tudo o que possa rebentar. Instalar em cada ecra e' de
            # proposito: a classe verifica se ja' esta' posto, e assim o handler
            # existe qualquer que seja o ecra por onde a app entrou.
            lines.append("        ApkpyCrashHandler.install(this);")
        if _I18N[0]['table']:
            # AppCompat so' guarda a lingua escolhida a partir do API 33; abaixo
            # disso a app tem de a repor sozinha, e e' isto que faz o "abre como
            # ficou" ser verdade em todos os telemoveis e nao so' nos novos.
            # Comparada antes de aplicada, como o modo de cor: chamar com o mesmo
            # valor pediria uma recriacao que ninguem quer.
            lines.append('        String _apkpyLanguage = _apkpyStorageGet("__apkpy_language", "");')
            lines.append('        if (!_apkpyLanguage.isEmpty() && !_apkpyLanguage.equals(')
            lines.append('                androidx.appcompat.app.AppCompatDelegate')
            lines.append('                        .getApplicationLocales().toLanguageTags())) {')
            lines.append('            androidx.appcompat.app.AppCompatDelegate.setApplicationLocales(')
            lines.append('                    androidx.core.os.LocaleListCompat'
                         '.forLanguageTags(_apkpyLanguage));')
            lines.append('        }')
        lines.append("        super.onCreate(savedInstanceState);")
        lines.append("")
        lines.append(f"        setContentView(R.layout.activity_screen_{screen_id});")
        # Bold on phones whose font theme forgets it; nothing elsewhere.
        lines.append(font_weight_feature.ACTIVITY_WATCH)
        lines.extend(sheet_feature.inflate_lines(self._screen_sheets, screen_id))
        if self.has_saved_text:
            lines.append("        _apkpyRestoreTextPolicy(savedInstanceState);")
        if self.has_flashlight or _USES_FLASHLIGHT[0]:
            # Registar entrega o estado actual de imediato. Sem isto, o
            # primeiro is_on() responderia "off" a uma luz que já estava
            # acesa — por exemplo acesa pelas definições rápidas.
            lines.append("        ApkpyTorch.watch(getApplicationContext());")
        lines.append("")

        if self.has_skeleton:
            for skeleton_comp in self.all_comps_flat:
                if skeleton_comp.get('comp_type') == 'skeleton' and skeleton_comp.get('visible', True):
                    lines.append(
                        f"        _apkpyStartSkeleton(findViewById(R.id.{skeleton_comp['_java_var']}));"
                    )
            lines.append("")

        # Theme system bars. Activities with an app bar draw edge-to-edge behind a
        # transparent status bar, so its inset is contained inside the toolbar's
        # 64dp instead of adding a second row above it.
        _theme = styles.get('__theme__', {})
        if _theme:
            _status = _resolve_color(_theme.get('background', '#000000'))
            if app_bar_info:
                _bar_style = component_style(
                    styles,
                    app_bar_info.get('type', 'app_bar'),
                    app_bar_info.get('id'),
                )
                _status = _resolve_color(
                    _get_style_bg(_bar_style)
                    or _theme.get('surface', _status)
                )
            _navigation = _resolve_color(_theme.get('surface', _status))
            lines.append("        // ApkPy Theme: native system bars")
            if app_bar_info:
                lines.append("        getWindow().setStatusBarColor(android.graphics.Color.TRANSPARENT);")
            else:
                lines.append(f'        getWindow().setStatusBarColor({_color_java(_status)});')
            lines.append(f'        getWindow().setNavigationBarColor({_color_java(_navigation)});')
            _system_flags = []
            if app_bar_info:
                _system_flags += [
                    "android.view.View.SYSTEM_UI_FLAG_LAYOUT_STABLE",
                    "android.view.View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN",
                ]
            # Estes dois nao podem ser decididos no build: a app troca de modo em
            # execucao. Ler a configuracao em vigor da' a mesma resposta que o
            # windowLightStatusBar do tema, e nas duas direccoes.
            lines.append(
                "        int _apkpySysUi = "
                + (" | ".join(_system_flags) if _system_flags else "0")
                + ";"
            )
            lines.append(
                "        if ((getResources().getConfiguration().uiMode"
            )
            lines.append(
                "                & android.content.res.Configuration.UI_MODE_NIGHT_MASK)"
            )
            lines.append(
                "                != android.content.res.Configuration.UI_MODE_NIGHT_YES) {"
            )
            lines.append(
                "            _apkpySysUi |= android.view.View"
                ".SYSTEM_UI_FLAG_LIGHT_STATUS_BAR"
            )
            lines.append(
                "                    | android.view.View"
                ".SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;"
            )
            lines.append("        }")
            lines.append(
                "        getWindow().getDecorView().setSystemUiVisibility(_apkpySysUi);"
            )
            lines.append("")
        # After the theme's flags, which decide by day/night alone.
        lines.append("        _apkpySystemIconsFollowBackground();")
        if _WARM_WEB[0] and screen_id == start_screen_id and not web_page_feature.uses(self.components):
            lines.append(web_page_feature.warm_java())
        lines.append("")

        # Bottom navigation setup
        if self.bottom_nav_info:
            lines.append("        BottomNavigationView bottomNav = findViewById(R.id.bottom_nav);")
            # A barra vai ate ao fundo do ecra. O pai dela (fitsSystemWindows)
            # guardava a zona do gesto como padding e mostrava la a cor da pagina:
            # uma faixa preta por baixo da barra, vista num telemovel. Agora o pai
            # faz o mesmo que fazia em cima e dos lados, e a zona de baixo passa
            # para dentro da barra -- a cor dela chega a borda e os itens ficam
            # acima do gesto.
            lines.append("        final android.view.View _apkpyNavHost = (android.view.View) bottomNav.getParent();")
            # A floating bar is a card above the gesture bar, not a band down to
            # the edge: the root's own padding keeps it clear, as it does the rest.
            _keep_inset = 'false && ' if _nav_look(styles)['floating'] else ''
            lines.append(f"        if ({_keep_inset}_apkpyNavHost.getFitsSystemWindows()) {{")
            lines.append("            androidx.core.view.ViewCompat.setOnApplyWindowInsetsListener(_apkpyNavHost, (_hv, _hi) -> {")
            lines.append("                androidx.core.graphics.Insets _bars = _hi.getInsets(")
            lines.append("                        androidx.core.view.WindowInsetsCompat.Type.systemBars()")
            lines.append("                        | androidx.core.view.WindowInsetsCompat.Type.displayCutout());")
            lines.append("                _hv.setPadding(_bars.left, _bars.top, _bars.right, 0);")
            lines.append("                bottomNav.setPadding(bottomNav.getPaddingLeft(), bottomNav.getPaddingTop(),")
            lines.append("                        bottomNav.getPaddingRight(), _bars.bottom);")
            lines.append("                return androidx.core.view.WindowInsetsCompat.CONSUMED;")
            lines.append("            });")
            lines.append("            androidx.core.view.ViewCompat.requestApplyInsets(_apkpyNavHost);")
            lines.append("        }")
            # Telemoveis antes do edge-to-edge desenham a barra do sistema a parte:
            # a mesma cor da barra de baixo, e icones que se vejam em cima dela.
            lines.append("        if (bottomNav.getBackground() instanceof android.graphics.drawable.ColorDrawable) {")
            lines.append("            int _apkpyNavBg = ((android.graphics.drawable.ColorDrawable) bottomNav.getBackground()).getColor();")
            lines.append("            getWindow().setNavigationBarColor(_apkpyNavBg);")
            lines.append("            new androidx.core.view.WindowInsetsControllerCompat(getWindow(), getWindow().getDecorView())")
            lines.append("                    .setAppearanceLightNavigationBars(")
            lines.append("                            androidx.core.graphics.ColorUtils.calculateLuminance(_apkpyNavBg) > 0.5);")
            lines.append("        }")
            lines.append("        _navReady = false;")
            lines.append(f"        bottomNav.setSelectedItemId(R.id.nav_{screen_id});")
            lines.append("        _navReady = true;")
            lines.append("        bottomNav.setOnItemSelectedListener(item -> {")
            lines.append("            if (!_navReady) return true;")
            lines.append("            int _navId = item.getItemId();")
            for tab_sid in self.bottom_nav_info['screen_ids']:
                tab_class = f"Screen_{tab_sid}Activity"
                lines.append(f"            if (_navId == R.id.nav_{tab_sid}) {{")
                if tab_sid == screen_id:
                    lines.append(f"                return true;")
                else:
                    lines.append(f"                Intent _i = new Intent({self.class_name}.this, {tab_class}.class);")
                    lines.append(f"                _i.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);")
                    lines.append(f"                startActivity(_i);")
                    lines.append(f"                overridePendingTransition(0, 0);")
                    lines.append(f"                return true;")
                lines.append(f"            }}")
            lines.append("            return false;")
            lines.append("        });")
            lines.append("")

        # Navigation drawer: the panel's items are the app's top-level
        # destinations, wired the same way the bottom bar's are.
        if drawer_info:
            lines.append("        com.google.android.material.navigation.NavigationView _apkpyDrawerView = findViewById(R.id.apkpy_drawer_view);")
            if screen_id in drawer_info['screen_ids']:
                lines.append(f"        _apkpyDrawerView.setCheckedItem(R.id.{_drawer_item_id(screen_id)});")
            # The header sits at the very top of the panel, which on an
            # edge-to-edge window is underneath the clock. The toolbar solves this
            # the same way, by asking for the inset rather than guessing at it.
            _drawer_status = _resolve_color((styles.get('__theme__', {}) or {}).get('background', '#000000'))
            lines.append("        androidx.drawerlayout.widget.DrawerLayout _apkpyDrawerRoot = findViewById(R.id.apkpy_drawer);")
            # Left alone a DrawerLayout paints the strip beside the panel from
            # colorPrimaryDark, which is a purple nobody asked for. The XML
            # attribute is accepted by AAPT and then ignored; the setter is not.
            lines.append(f'        _apkpyDrawerRoot.setStatusBarBackgroundColor({_color_java(_drawer_status)});')
            # Back belongs to the panel while any of it shows (see
            # _apkpyDrawerBack). A screen built again with its panel open -- the
            # phone was turned -- is told nothing by the listener, so the panel is
            # asked once, when the layout is there.
            lines.append("        getOnBackPressedDispatcher().addCallback(this, _apkpyDrawerBack);")
            lines.append("        _apkpyDrawerRoot.addDrawerListener(new androidx.drawerlayout.widget.DrawerLayout.SimpleDrawerListener() {")
            lines.append("            @Override public void onDrawerSlide(android.view.View _panel, float _shown) {")
            lines.append("                _apkpyDrawerBack.setEnabled(_shown > 0f);")
            lines.append("            }")
            lines.append("            @Override public void onDrawerClosed(android.view.View _panel) {")
            lines.append("                _apkpyDrawerBack.setEnabled(false);")
            lines.append("            }")
            lines.append("        });")
            lines.append("        _apkpyDrawerRoot.post(() -> _apkpyDrawerBack.setEnabled(")
            lines.append("                _apkpyDrawerRoot.isDrawerVisible(androidx.core.view.GravityCompat.START)));")
            lines.append("        androidx.core.view.ViewCompat.setOnApplyWindowInsetsListener(_apkpyDrawerView, (_dv, _di2) -> {")
            lines.append("            if (_apkpyDrawerView.getHeaderCount() > 0) {")
            lines.append("                android.view.View _dh = _apkpyDrawerView.getHeaderView(0);")
            lines.append("                int _dTop = _di2.getInsets(androidx.core.view.WindowInsetsCompat.Type.statusBars()).top;")
            lines.append("                int _dBase = Math.round(24 * getResources().getDisplayMetrics().density);")
            lines.append("                _dh.setPadding(_dh.getPaddingLeft(), _dTop + _dBase, _dh.getPaddingRight(), _dh.getPaddingBottom());")
            lines.append("            }")
            lines.append("            return _di2;")
            lines.append("        });")
            lines.append("        _apkpyDrawerView.setNavigationItemSelectedListener(_item -> {")
            lines.append("            _apkpyDrawer(false);")
            lines.append("            int _drawerId = _item.getItemId();")
            for target_sid in drawer_info['screen_ids']:
                if target_sid == screen_id:
                    continue
                target_class = f"Screen_{target_sid}Activity"
                lines.append(f"            if (_drawerId == R.id.{_drawer_item_id(target_sid)}) {{")
                lines.append(f"                Intent _di = new Intent({self.class_name}.this, {target_class}.class);")
                lines.append("                _di.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT);")
                lines.append("                startActivity(_di);")
                lines.append("            }")
            lines.append("            return true;")
            lines.append("        });")
            lines.append("")

        # Agendar background services (apenas no ecrã inicial — uma vez por ciclo de vida da app)
        if self.background_services and screen_id == start_screen_id:
            lines.append("        // ── Agendar background services (WorkManager) ──────────")
            for svc in self.background_services:
                worker_class = svc['worker_class']
                interval = max(15, int(svc.get('minutes', 15)))
                req_var = f"workRequest_{svc['id']}"

                wifi_only  = svc.get('only_on_wifi')
                charging   = svc.get('only_when_charging')
                constraints_var = None
                if wifi_only or charging:
                    constraints_var = f"constraints_{svc['id']}"
                    lines.append(f"        Constraints {constraints_var} = new Constraints.Builder()")
                    if wifi_only:
                        lines.append(f"                .setRequiredNetworkType(NetworkType.UNMETERED)")
                    if charging:
                        lines.append(f"                .setRequiresCharging(true)")
                    lines.append(f"            .build();")

                lines.append(f"        PeriodicWorkRequest {req_var} = new PeriodicWorkRequest.Builder(")
                lines.append(f"                {worker_class}.class, {interval}, java.util.concurrent.TimeUnit.MINUTES)")
                if constraints_var:
                    lines.append(f"            .setConstraints({constraints_var})")
                lines.append(f"            .build();")
                lines.append(f"        WorkManager.getInstance(getApplicationContext()).enqueueUniquePeriodicWork(")
                lines.append(f"            \"{svc['id']}\",")
                lines.append(f"            ExistingPeriodicWorkPolicy.KEEP,")
                lines.append(f"            {req_var}")
                lines.append(f"        );")
            lines.append("")

        # Pedir a permissão de notificações em runtime (Android 13+ / API 33+).
        # Sem isto, declarar POST_NOTIFICATIONS no manifesto não chega — o utilizador
        # tem de aprovar explicitamente, ou notify(...) fica silenciosamente sem efeito.
        if screen_id == start_screen_id and "POST_NOTIFICATIONS" in self.declared_permissions and not self.has_manual_notif_request:
            lines.append("        // ── Pedir permissão de notificações (Android 13+) ──────")
            lines.append("        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU &&")
            lines.append("                ActivityCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {")
            lines.append("            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.POST_NOTIFICATIONS}, PERMISSION_REQ_POST_NOTIFICATIONS);")
            lines.append("        }")
            lines.append("")

    def _write_components(self):
        """Every component, then what listens to them as the user types and changes them."""
        all_comps_flat = self.all_comps_flat
        lines = self.lines
        app_bar_info = self.app_bar_info
        # Contadores para nomes de variáveis Java (dict para ser mutável em closures)
        self.cnt = {
            'btn': 0, 'lbl': 0, 'inp': 0, 'container': 0, 'card': 0,
            'img': 0, 'lst': 0, 'vc': 0, 'car': 0, 'grid': 0, 'lrow': 0,
            'rich': 0,
        }
        self._gen_java_comps(self.components, "layout")
        if keyboard_feature.has_typed_field(all_comps_flat):
            lines.append("        " + keyboard_feature.KEEP_CALL)

        # ── Imagens remotas: carregar a URL para o ImageView em background ───────
        for _ri in all_comps_flat:
            if _ri['comp_type'] == 'image' and _ri.get('_is_remote'):
                _ri_url = (_ri.get('src') or '').replace('\\', '\\\\').replace('"', '\\"')
                _placeholder = _ri.get('placeholder')
                _fallback = _ri.get('fallback')
                _placeholder_ref = (
                    f'R.drawable.{_android_drawable_name(_placeholder)}'
                    if _placeholder and not str(_placeholder).startswith(('http://', 'https://'))
                    else '0'
                )
                _fallback_ref = (
                    f'R.drawable.{_android_drawable_name(_fallback)}'
                    if _fallback and not str(_fallback).startswith(('http://', 'https://'))
                    else '0'
                )
                lines.append(
                    f'        _loadRemoteImage(R.id.{_ri["_img_id"]}, "{_ri_url}", '
                    f'{_placeholder_ref}, {_fallback_ref}, '
                    f'{str(bool(_ri.get("cache", True))).lower()}, '
                    f'{str(bool(_ri.get("fade_in", False))).lower()});'
                )
        if app_bar_info and app_bar_info.get('_is_remote'):
            _bar_url = (app_bar_info.get('image') or '').replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'        _loadRemoteImage(R.id.apkpy_appbar_image, "{_bar_url}");')
        if self.has_remote_image:
            lines.append("")

        # ── Pesquisa em tempo real (inputs on_change) — TextWatcher por campo ─────
        #   A cada tecla, refiltra o dataset completo ({jv}_src) do list_view alvo
        #   com a condição traduzida e atualiza o adapter. Mesmo comportamento que
        #   o filtro do previewer (paridade Preview ↔ Android).
        for _si in self._search_inputs:
            _search = _si.get('search') or {}
            _inp_jv = _si.get('_java_var')
            _tgt_jv = self._get_jv_from_py_var(_search.get('target'))
            if not (_inp_jv and _tgt_jv):
                continue
            _qp = _search.get('query_param', 'q')
            _iv = _search.get('item_var', 'item')
            _cond_node = _search.get('cond')
            try:
                _cond_java = _search_cond_java(_cond_node, _qp, _iv) if _cond_node is not None else 'true'
            except _SearchUntranslatable as _ex:
                # The Previewer would filter but the APK would not: a silent
                # divergence is the worst outcome, so it is reported in full.
                _report_untranslatable_search(_ex, _search)
                continue
            _target_comp = next(
                (
                    c for c in all_comps_flat
                    if c.get('_py_var') == _search.get('target')
                ),
                None,
            )
            _target_is_virtual = bool(
                _target_comp
                and _target_comp.get('comp_type') == 'virtual_collection'
            )
            _refresh = (
                f"{_tgt_jv}Adapter.notifyDataSetChanged();"
                if _target_is_virtual or not self.scroll
                else f"update{_tgt_jv[0].upper()}{_tgt_jv[1:]}List();"
            )
            lines.append(f"        {_inp_jv}.addTextChangedListener(new android.text.TextWatcher() {{")
            lines.append("            public void beforeTextChanged(CharSequence _s, int _a, int _b, int _c) { }")
            lines.append("            public void onTextChanged(CharSequence _s, int _a, int _b, int _c) { }")
            lines.append("            public void afterTextChanged(android.text.Editable _ed) {")
            lines.append(f"                String _q = {_inp_jv}.getText().toString();")
            lines.append(f"                if ({_tgt_jv}_src == null) return;")
            lines.append(f"                {_tgt_jv}_items.clear();")
            lines.append(f"                for (int _i = 0; _i < {_tgt_jv}_src.size(); _i++) {{")
            lines.append(f"                    String _row = {_tgt_jv}_src.get(_i);")
            lines.append(f"                    if ({_cond_java}) {{ {_tgt_jv}_items.add(_row); }}")
            lines.append("                }")
            lines.append(f"                {_refresh}")
            lines.append("            }")
            lines.append("        });")
            lines.append("")

        # Generic named input callbacks (``on_change=search_changed``).  These
        # used to run only in the Previewer because the parser retained only the
        # specialised list-filter lambda handled above.
        for _ci in all_comps_flat:
            if _ci.get('comp_type') not in ('inputs', 'input_field'):
                continue
            if _ci.get('input_type', 'text') not in (
                    'text', 'password', 'search', 'textarea', 'number'):
                continue
            _change_callback = _ci.get('on_change')
            _change_jv = _ci.get('_java_var')
            if (not _change_callback or not _change_jv
                    or _change_callback not in self.functions_map):
                continue
            lines.append(
                f"        {_change_jv}.addTextChangedListener("
                "new android.text.TextWatcher() {"
            )
            lines.append("            public void beforeTextChanged(CharSequence _s, int _a, int _b, int _c) { }")
            lines.append("            public void onTextChanged(CharSequence _s, int _a, int _b, int _c) { }")
            lines.append("            public void afterTextChanged(android.text.Editable _ed) {")
            lines.append(
                f"                pythonCallback_{_change_callback}(_ed.toString());"
            )
            lines.append("            }")
            lines.append("        });")
            lines.append("")

        # A switch, a checkbox or a slider with ``on_change=fn`` got no listener:
        # the stored name was read for text fields only, so a settings switch
        # moved and nothing heard it, on the phone or in the Previewer. fn gets
        # what get_value() gives: "true"/"false", or the slider's number as text.
        # isShown() is false until the window is attached, after onResume: the
        # value the screen opens with (a set_value() at module level, a restored
        # state) is not a change, and the Previewer does not call fn for it.
        for _ci in all_comps_flat:
            if _ci.get('comp_type') not in ('inputs', 'input_field'):
                continue
            _kind = _ci.get('input_type', 'text')
            _change_callback = _ci.get('on_change')
            _change_jv = _ci.get('_java_var')
            if (_kind not in ('switch', 'checkbox', 'range') or not _change_callback
                    or not _change_jv or _change_callback not in self.functions_map):
                continue
            if _kind == 'range':
                lines += [
                    f"        {_change_jv}.setOnSeekBarChangeListener("
                    "new android.widget.SeekBar.OnSeekBarChangeListener() {",
                    "            public void onStartTrackingTouch(android.widget.SeekBar _s) { }",
                    "            public void onStopTrackingTouch(android.widget.SeekBar _s) { }",
                    "            public void onProgressChanged(android.widget.SeekBar _s, int _p, boolean _user) {",
                    f"                if (_s.isShown()) pythonCallback_{_change_callback}(String.valueOf(_p));",
                    "            }",
                    "        });",
                    "",
                ]
            else:
                lines += [
                    f"        {_change_jv}.setOnCheckedChangeListener("
                    "new android.widget.CompoundButton.OnCheckedChangeListener() {",
                    "            public void onCheckedChanged(android.widget.CompoundButton _b, boolean _on) {",
                    f"                if (_b.isShown()) pythonCallback_{_change_callback}(_on ? \"true\" : \"false\");",
                    "            }",
                    "        });",
                    "",
                ]

    def _write_first_commands(self):
        """The commands written at the top of the app's file that touch this screen, and the app bar's clicks."""
        lines = self.lines
        app_bar_info = self.app_bar_info
        # ── Carregar valores do storage e preencher campos (comandos de módulo) ──
        # Inclui apenas os que referenciam componentes neste ecrã
        if self.module_init_cmds:
            screen_py_vars = {c.get('_py_var') for c in self.all_comps_flat if c.get('_py_var')}

            def _cmd_touches_screen(cmd):
                if cmd['type'] == 'comp_set_value':
                    return cmd.get('py_var') in screen_py_vars
                if cmd['type'] == 'push_listen':
                    target = cmd.get('screen_id') or self.start_screen_id
                    return target == self.screen_id
                if cmd['type'] in ('if_compare', 'if_var'):
                    return any(_cmd_touches_screen(c) for c in cmd.get('true_body', []) + cmd.get('false_body', []))
                return True  # storage_get_assign – declaração de variável local (sempre inclui)

            def _cmd_sequence_relevant(cmds_seq):
                """Mantém storage_get_assign que sejam usados por comp_set_value relevante."""
                relevant = set()
                for cmd in cmds_seq:
                    if _cmd_touches_screen(cmd):
                        relevant.add(id(cmd))
                        if cmd['type'] == 'if_compare':
                            needed_var = cmd.get('left')
                            for c2 in cmds_seq:
                                if c2['type'] == 'storage_get_assign' and c2.get('var') == needed_var:
                                    relevant.add(id(c2))
                return [cmd for cmd in cmds_seq if id(cmd) in relevant]

            relevant_init = _cmd_sequence_relevant(self.module_init_cmds)
            if relevant_init:
                lines.append("        // ── Carregar preferências guardadas ────────────────")
                # Module code runs again on every screen; what it writes to other
                # screens is theirs to write (pending_views).
                if _PENDING_TARGETS[0]:
                    lines.append(pending_views_feature.mute_line("        ", True))
                self._gen_cmds(relevant_init, "        ")
                if _PENDING_TARGETS[0]:
                    lines.append(pending_views_feature.mute_line("        ", False))
                lines.append("")

        # OnClickListeners (navegação e custom functions combinados — inclui botões em containers)
        if app_bar_info:
            # Edge to edge on every Android, as 15 and later already are: the
            # root takes the sides and the bottom of the system bars (and the
            # keyboard), the toolbar below takes the top and grows under the
            # status bar in its own colour.
            lines.append("        androidx.core.view.WindowCompat.setDecorFitsSystemWindows(getWindow(), false);")
            lines.append("        android.view.View apkpyBarRoot = ((android.view.ViewGroup) findViewById(android.R.id.content)).getChildAt(0);")
            lines.append("        androidx.core.view.ViewCompat.setOnApplyWindowInsetsListener(apkpyBarRoot, (view, windowInsets) -> {")
            lines.append("            androidx.core.graphics.Insets apkpyEdges = windowInsets.getInsets(")
            lines.append("                    androidx.core.view.WindowInsetsCompat.Type.systemBars()")
            lines.append("                    | androidx.core.view.WindowInsetsCompat.Type.displayCutout()")
            lines.append("                    | androidx.core.view.WindowInsetsCompat.Type.ime());")
            lines.append("            view.setPadding(apkpyEdges.left, 0, apkpyEdges.right, apkpyEdges.bottom);")
            lines.append("            return windowInsets;")
            lines.append("        });")
            lines.append("        MaterialToolbar apkpyToolbar = findViewById(R.id.apkpy_toolbar);")
            lines.append("        final int apkpyToolbarContentHeight = Math.round(48 * getResources().getDisplayMetrics().density);")
            lines.append("        androidx.core.view.ViewCompat.setOnApplyWindowInsetsListener(apkpyToolbar, (view, windowInsets) -> {")
            lines.append("            int apkpyStatusInset = windowInsets.getInsets(androidx.core.view.WindowInsetsCompat.Type.statusBars()).top;")
            lines.append("            int apkpyToolbarTargetHeight = apkpyToolbarContentHeight + apkpyStatusInset;")
            lines.append("            android.view.ViewGroup.LayoutParams apkpyToolbarParams = view.getLayoutParams();")
            lines.append("            if (apkpyToolbarParams.height != apkpyToolbarTargetHeight) {")
            lines.append("                apkpyToolbarParams.height = apkpyToolbarTargetHeight;")
            lines.append("                view.setLayoutParams(apkpyToolbarParams);")
            lines.append("            }")
            lines.append("            view.setPadding(view.getPaddingLeft(), apkpyStatusInset, view.getPaddingRight(), view.getPaddingBottom());")
            lines.append("            if (view.getParent() instanceof com.google.android.material.appbar.CollapsingToolbarLayout) {")
            lines.append("                ((android.view.View)view.getParent()).setMinimumHeight(apkpyToolbarTargetHeight);")
            lines.append("            }")
            lines.append("            return windowInsets;")
            lines.append("        });")
            lines.append("        androidx.core.view.ViewCompat.requestApplyInsets(apkpyToolbar);")
            _bar_title_size = _parse_font_size(component_style(
                self.styles, app_bar_info.get('type', 'app_bar'), app_bar_info.get('id'),
                include_body=False))
            if _bar_title_size:
                # The title is a TextView the toolbar makes for itself, with
                # Material's 20sp; a size the bar's CSS names reached the
                # Previewer and never the phone.
                lines.append("        for (int _i = 0; _i < apkpyToolbar.getChildCount(); _i++) {")
                lines.append("            android.view.View _child = apkpyToolbar.getChildAt(_i);")
                lines.append("            if (_child instanceof android.widget.TextView && apkpyToolbar.getTitle() != null")
                lines.append("                    && apkpyToolbar.getTitle().toString().contentEquals(((android.widget.TextView) _child).getText())) {")
                lines.append(f"                ((android.widget.TextView) _child).setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, {_bar_title_size}f);")
                lines.append("            }")
                lines.append("        }")
            leading = app_bar_info.get('leading') or {}
            leading_cmd = leading.get('command')
            leading_info = self.functions_map.get(leading_cmd) if leading_cmd else None
            if leading_info or leading.get('icon') == 'arrow_back':
                lines.append("        apkpyToolbar.setNavigationOnClickListener(v -> {")
                if leading_info:
                    self._gen_cmds(leading_info.get('cmds', []), "            ")
                else:
                    lines.append("            finish();")
                lines.append("        });")
            actions = app_bar_info.get('actions') or []
            if actions:
                lines.append("        apkpyToolbar.setOnMenuItemClickListener(item -> {")
                lines.append("            int apkpyActionId = item.getItemId();")
                for index, item in enumerate(actions, 1):
                    item_id = item.get('_android_id') or _safe_android_id(
                        item.get('id'), f'appbar_{self.screen_id}_{index}',
                    )
                    lines.append(f"            if (apkpyActionId == R.id.{item_id}) {{")
                    command = item.get('command')
                    function = self.functions_map.get(command) if command else None
                    if function:
                        self._gen_cmds(function.get('cmds', []), "                ")
                    lines.append("                return true;")
                    lines.append("            }")
                lines.append("            return false;")
                lines.append("        });")
            lines.append("")

    def _write_listeners(self):
        """Clicks, long presses and tooltips of the components."""
        all_comps_flat = self.all_comps_flat
        lines = self.lines
        for comp in all_comps_flat:
            java_var = comp.get('_java_var')
            if not java_var:
                continue
            if comp.get('tooltip'):
                tip = _escape_java_literal(str(comp['tooltip']))
                lines.append(
                    f'        TooltipCompat.setTooltipText(findViewById(R.id.{java_var}), "{tip}");'
                )
            context_overlay = comp.get('context_overlay')
            if context_overlay in self.active_overlays:
                lines.append(f"        findViewById(R.id.{java_var}).setOnLongClickListener(v -> {{")
                lines.append(f"            {self._overlay_method_name(context_overlay)}();")
                lines.append("            return true;")
                lines.append("        });")
        if any(c.get('tooltip') or c.get('context_overlay') for c in all_comps_flat):
            lines.append("")

        for comp in all_comps_flat:
            # A row answers a tap exactly like a button does -- same
            # command, same navigation, same popup -- so it goes through the
            # same wiring rather than a second copy of it.
            if comp['comp_type'] not in ('button', 'list_row', 'image', 'container', 'card'):
                continue

            btn_py_var   = comp.get('_py_var')
            btn_java_var = comp.get('_java_var')
            cmd          = comp.get('command') or comp.get('on_click')

            nav_info = None
            for n in self.navigations:
                if n['from_screen_id'] == self.screen_id and n['button_py_var'] == btn_py_var:
                    nav_info = n
                    break

            func_info = self.functions_map.get(cmd) if cmd else None
            cmds = func_info['cmds'] if func_info else []
            popup_overlay = comp.get('popup_overlay')

            if (nav_info or cmds or popup_overlay in self.active_overlays) and btn_java_var:
                # A container or a card has no Java variable of its own.
                _tapped = (f"findViewById(R.id.{btn_java_var})"
                           if comp['comp_type'] in ('container', 'card') else btn_java_var)
                lines.append(f"        {_tapped}.setOnClickListener(new View.OnClickListener() {{")
                lines.append(f"            @Override")
                # The function's body is written in here, so the parameter takes a
                # name nobody writes: `v` clashed with `for k, v in d.items()`.
                lines.append(f"            public void onClick(View _apkpyTapped) {{")

                _click_args = (func_info or {}).get('args') or []
                _click_defaults = (func_info or {}).get('defaults') or {}
                if _click_args and all(a in _click_defaults for a in _click_args):
                    # command=refresh with def refresh(force=False): Python calls
                    # refresh() and force is False. Copying the body here left
                    # force undeclared, and javac stopped the build.
                    _call = _callback_call_args(
                        cmd, [_click_defaults[a] for a in _click_args], self._val_to_java,
                        self.functions_map, self.boolean_first_arg_callbacks)
                    lines.append(f"                pythonCallback_{cmd}({_call});")
                else:
                    self._gen_cmds(cmds, "                ")

                if popup_overlay in self.active_overlays:
                    lines.append(f"                {self._overlay_method_name(popup_overlay)}();")
                
                if nav_info:
                    to_class = f"Screen_{nav_info['to_screen_id']}Activity"
                    lines.append(f"                Intent intent = new Intent({self.class_name}.this, {to_class}.class);")
                    for k, v_node in (nav_info.get('data') or []):
                        lines.append(f"                intent.putExtra(\"{k}\", String.valueOf({self._val_to_java(v_node)}));")
                    lines.append(f"                startActivity(intent);")
                    self._emit_screen_transition(nav_info, "                ")
                
                lines.append(f"            }}")
                lines.append(f"        }});")
                lines.append("")

    def _write_player_controls(self):
        """now_playing, audio.controls, the mini player and the like button, kept up to date by a tick."""
        now_playing = self.now_playing
        lines = self.lines
        all_comps_flat = self.all_comps_flat
        class_name = self.class_name
        audio_like = self.audio_like
        _np_progress_jv = self._get_jv_from_py_var(now_playing['progress']) if self._np_active else None
        _np_time_jv = self._get_jv_from_py_var(now_playing.get('time')) if (self._np_active and now_playing.get('time')) else None
        _np_cover_jv = self._get_jv_from_py_var(now_playing.get('cover')) if (self._np_active and now_playing.get('cover')) else None
        _np_title_jv = self._get_jv_from_py_var(now_playing.get('title')) if (self._np_active and now_playing.get('title')) else None
        _np_artist_jv = self._get_jv_from_py_var(now_playing.get('artist')) if (self._np_active and now_playing.get('artist')) else None
        if self._np_active and _np_progress_jv:
            _np_time_decl = (f"final android.widget.TextView _npTime = findViewById(R.id.{_np_time_jv});"
                             if _np_time_jv else "final android.widget.TextView _npTime = null;")
            lines.append("        // ── Barra \"now playing\" (progresso ao vivo + arrastar p/ seek) ──")
            lines.append(f"        final android.widget.SeekBar _npBar = findViewById(R.id.{_np_progress_jv});")
            lines.append(f"        {_np_time_decl}")
            if _np_title_jv:
                lines.append(f"        final android.widget.TextView _npTitle = findViewById(R.id.{_np_title_jv});")
            if _np_artist_jv:
                lines.append(f"        final android.widget.TextView _npArtist = findViewById(R.id.{_np_artist_jv});")
            # The bar's accent-color, as the Previewer draws it; sky blue when the
            # stylesheet says nothing, as before. It was always sky blue here.
            _np_bar_comp = next((c for c in all_comps_flat
                                 if now_playing.get('progress')
                                 and c.get('_py_var') == now_playing.get('progress')), None)
            _np_accent = (component_style(self.styles, 'inputs', _np_bar_comp.get('id')).get('accent-color')
                          if _np_bar_comp is not None and _np_bar_comp.get('id') else None)
            _np_accent_java = _color_java(_np_accent) if _np_accent else '0xFF38BDF8'
            lines.append("        // Bola (thumb) redonda + track colorido (em vez do default quadradão).")
            lines.append("        int _npD = (int)(16 * getResources().getDisplayMetrics().density);")
            lines.append("        android.graphics.drawable.GradientDrawable _npThumb = new android.graphics.drawable.GradientDrawable();")
            lines.append("        _npThumb.setShape(android.graphics.drawable.GradientDrawable.OVAL);")
            lines.append(f"        _npThumb.setColor({_np_accent_java});")
            lines.append("        _npThumb.setSize(_npD, _npD);")
            lines.append("        _npBar.setThumb(_npThumb);")
            lines.append("        _npBar.setSplitTrack(false);")
            lines.append(f"        _npBar.setProgressTintList(android.content.res.ColorStateList.valueOf({_np_accent_java}));")
            lines.append("        _npBar.setProgressBackgroundTintList(android.content.res.ColorStateList.valueOf(0xFF3A3F4B));")
            lines.append("        _npBar.setOnSeekBarChangeListener(new android.widget.SeekBar.OnSeekBarChangeListener() {")
            lines.append("            public void onProgressChanged(android.widget.SeekBar sb, int p, boolean fromUser) {}")
            lines.append("            public void onStartTrackingTouch(android.widget.SeekBar sb) { _npSeeking = true; }")
            lines.append("            public void onStopTrackingTouch(android.widget.SeekBar sb) {")
            lines.append(f"                android.content.Intent _si = new android.content.Intent({class_name}.this, ApkpyMediaService.class);")
            lines.append("                _si.setAction(\"apkpy.SEEK\");")
            lines.append("                _si.putExtra(\"ms\", sb.getProgress());")
            lines.append(f"                {class_name}.this.startService(_si);")
            lines.append("                _npSeeking = false;")
            lines.append("            }")
            lines.append("        });")
            lines.append("        _npTick = new Runnable() {")
            lines.append("            public void run() {")
            lines.append("                int _dur = ApkpyMediaService.durationMs();")
            lines.append("                int _pos = ApkpyMediaService.currentPositionMs();")
            lines.append("                if (_dur > 0) {")
            lines.append("                    _npLastDur = _dur;")
            lines.append("                    _npBar.setMax(_dur);")
            lines.append("                    if (!_npSeeking) {")
            lines.append("                        // anima a bola de onde está até à nova posição → desliza suave")
            lines.append("                        if (_npAnim != null) _npAnim.cancel();")
            lines.append("                        _npAnim = android.animation.ObjectAnimator.ofInt(_npBar, \"progress\", _pos);")
            lines.append("                        _npAnim.setDuration(1000);")
            lines.append("                        _npAnim.setInterpolator(new android.view.animation.LinearInterpolator());")
            lines.append("                        _npAnim.start();")
            lines.append("                    }")
            # Nothing loaded (the queue ended, or stopped): back to the start with
            # the last track's length, as a player shows it. The bar stayed at the
            # end and the time read "0:00 / 0:00". The Previewer does the same.
            lines.append("                } else if (!_npSeeking && !ApkpyMediaService.isPlaying()) {")
            lines.append("                    if (_npAnim != null) _npAnim.cancel();")
            lines.append("                    _npBar.setProgress(0);")
            lines.append("                }")
            lines.append("                if (_npTime != null) _npTime.setText(_npFmt(_dur > 0 ? _pos : 0) + \" / \" + _npFmt(_dur > 0 ? _dur : _npLastDur));")
            if _np_title_jv or _np_artist_jv:
                lines.append("                // título/artista da faixa atual (labels do ecrã Now Playing)")
                lines.append("                String _npT = ApkpyMediaService.currentTitle();")
                lines.append("                if (_npT != null && !_npT.isEmpty()) {")
                if _np_title_jv:
                    lines.append("                    _npTitle.setText(_npT);")
                if _np_artist_jv:
                    lines.append("                    _npArtist.setText(ApkpyMediaService.currentArtist());")
                lines.append("                }")
            if _np_cover_jv:
                lines.append("                // capa do álbum: carrega quando a faixa muda")
                lines.append("                String _art = ApkpyMediaService.currentArt();")
                lines.append("                if (_art != null && !_art.isEmpty() && !_art.equals(_npLastArt)) {")
                lines.append("                    _npLastArt = _art;")
                lines.append("                    if (_art.startsWith(\"http://\") || _art.startsWith(\"https://\")) {")
                lines.append(f"                        _loadRemoteImage(R.id.{_np_cover_jv}, _art);")
                lines.append("                    } else {")
                lines.append("                        int _artRes = _apkpyBundled(_art, \"drawable\");")
                lines.append(f"                        if (_artRes != 0) ((android.widget.ImageView) findViewById(R.id.{_np_cover_jv})).setImageResource(_artRes);")
                lines.append("                    }")
                lines.append("                }")
            lines.append("                _npHandler.postDelayed(this, 1000);")
            lines.append("            }")
            lines.append("        };")
            lines.append("        _npHandler.post(_npTick);")

        if self._ac_active:
            _ac = self.audio_controls
            # Resolver os java vars dos botões AGORA (já atribuídos na geração do XML).
            _ac_play = self._get_jv_from_py_var(_ac['play_pause']) if _ac.get('play_pause') else None
            _ac_shuf = self._get_jv_from_py_var(_ac['shuffle']) if _ac.get('shuffle') else None
            _ac_rep  = self._get_jv_from_py_var(_ac['repeat']) if _ac.get('repeat') else None
            def _aclit(key):
                return '"' + _escape_java_literal(str(_ac.get(key, ''))) + '"'
            lines.append("")
            lines.append("        // ── Botões de estado do leitor (audio.controls) ─────────────────")
            if _ac_play:
                lines.append(f"        final android.widget.Button _acPlay = findViewById(R.id.{_ac_play});")
                lines.append("        _acPlay.setOnClickListener(new View.OnClickListener() {")
                lines.append("            public void onClick(View _v) {")
                lines.append(f"                android.content.Intent _ci = new android.content.Intent({class_name}.this, ApkpyMediaService.class);")
                lines.append("                _ci.setAction(ApkpyMediaService.isPlaying() ? \"apkpy.PAUSE\" : \"apkpy.RESUME\");")
                lines.append(f"                {class_name}.this.startService(_ci);")
                lines.append("            }")
                lines.append("        });")
            def _ac_owns_click(role):
                # A button with a command of its own keeps it (the Previewer too).
                var = _ac.get(role)
                found = next((c for c in all_comps_flat if var and c.get('_py_var') == var), None)
                return found is not None and not (found.get('command') or found.get('on_click'))

            def _ac_click(view, action):
                lines.append(f"        {view}.setOnClickListener(new View.OnClickListener() {{")
                lines.append("            public void onClick(View _v) {")
                lines.append(f"                android.content.Intent _ci = new android.content.Intent({class_name}.this, ApkpyMediaService.class);")
                lines.append(f"                _ci.setAction(\"{action}\");")
                lines.append(f"                {class_name}.this.startService(_ci);")
                lines.append("            }")
                lines.append("        });")

            if _ac_shuf:
                lines.append(f"        final android.widget.Button _acShuf = findViewById(R.id.{_ac_shuf});")
                if _ac_owns_click('shuffle'):
                    _ac_click("_acShuf", "apkpy.SHUFFLE")
            if _ac_rep:
                lines.append(f"        final android.widget.Button _acRep = findViewById(R.id.{_ac_rep});")
                if _ac_owns_click('repeat'):
                    _ac_click("_acRep", "apkpy.REPEAT")
            def _ac_icons(role):
                var = _ac.get(role)
                found = next((c for c in all_comps_flat if var and c.get('_py_var') == var), None)
                return (found or {}).get('_ac_icons')

            def _ac_icon_line(view, condition_icons):
                # condition_icons: [(java condition or None, state)] -- first match wins.
                expr = None
                for condition, state in reversed(condition_icons):
                    ref = f"R.drawable.{_ac_icons_now[state]}"
                    expr = ref if expr is None else f"({condition} ? {ref} : {expr})"
                return (f"                ((com.google.android.material.button.MaterialButton) {view}).setIcon("
                        f"androidx.core.content.ContextCompat.getDrawable({class_name}.this, {expr}));")

            lines.append("        _acTick = new Runnable() {")
            lines.append("            public void run() {")
            if _ac_play:
                _ac_icons_now = _ac_icons('play_pause')
                if _ac_icons_now:
                    lines.append(_ac_icon_line("_acPlay", [("ApkpyMediaService.isPlaying()", 'pause'), (None, 'play')]))
                else:
                    lines.append(f"                _acPlay.setText(ApkpyMediaService.isPlaying() ? {_aclit('pause_text')} : {_aclit('play_text')});")
            if _ac_shuf:
                _ac_icons_now = _ac_icons('shuffle')
                if _ac_icons_now:
                    lines.append(_ac_icon_line("_acShuf", [("ApkpyMediaService.shuffleOn()", 'on'), (None, 'off')]))
                else:
                    lines.append(f"                _acShuf.setText(ApkpyMediaService.shuffleOn() ? {_aclit('shuffle_on')} : {_aclit('shuffle_off')});")
            if _ac_rep:
                lines.append("                int _rm = ApkpyMediaService.repeatMode();")
                _ac_icons_now = _ac_icons('repeat')
                if _ac_icons_now:
                    lines.append(_ac_icon_line("_acRep", [("_rm == 2", 'one'), ("_rm == 1", 'all'), (None, 'off')]))
                else:
                    lines.append(f"                _acRep.setText(_rm == 2 ? {_aclit('repeat_one')} : (_rm == 1 ? {_aclit('repeat_all')} : {_aclit('repeat_off')}));")
            lines.append("                _acHandler.postDelayed(this, 400);")
            lines.append("            }")
            lines.append("        };")
            lines.append("        _acHandler.post(_acTick);")

        if self._mp_active:
            _mp_open = (self.mini_player or {}).get('open_sid')
            lines.append("")
            lines.append("        // ── Mini-player fixo (mini_player) ──────────────────────────────")
            lines.append("        final android.widget.LinearLayout _mpBar = findViewById(R.id.apkpy_miniplayer);")
            lines.append("        final android.widget.ImageView _mpCover = findViewById(R.id.apkpy_mp_cover);")
            lines.append("        final android.widget.TextView _mpTitle = findViewById(R.id.apkpy_mp_title);")
            lines.append("        final android.widget.TextView _mpArtist = findViewById(R.id.apkpy_mp_artist);")
            lines.append("        final android.widget.Button _mpPp = findViewById(R.id.apkpy_mp_pp);")
            lines.append("        _mpPp.setOnClickListener(new View.OnClickListener() {")
            lines.append("            public void onClick(View _v) {")
            lines.append(f"                android.content.Intent _mi = new android.content.Intent({class_name}.this, ApkpyMediaService.class);")
            lines.append("                _mi.setAction(ApkpyMediaService.isPlaying() ? \"apkpy.PAUSE\" : \"apkpy.RESUME\");")
            lines.append(f"                {class_name}.this.startService(_mi);")
            lines.append("            }")
            lines.append("        });")
            if _mp_open:
                lines.append("        _mpBar.setOnClickListener(new View.OnClickListener() {")
                lines.append("            public void onClick(View _v) {")
                lines.append(f"                startActivity(new android.content.Intent({class_name}.this, Screen_{_mp_open}Activity.class));")
                lines.append("            }")
                lines.append("        });")
            lines.append("        _mpTick = new Runnable() {")
            lines.append("            public void run() {")
            lines.append("                String _mt = ApkpyMediaService.currentTitle();")
            lines.append("                if (_mt == null || _mt.isEmpty()) {")
            lines.append("                    _mpBar.setVisibility(android.view.View.GONE);")
            lines.append("                } else {")
            lines.append("                    _mpBar.setVisibility(android.view.View.VISIBLE);")
            lines.append("                    _mpTitle.setText(_mt);")
            lines.append("                    _mpArtist.setText(ApkpyMediaService.currentArtist());")
            lines.append("                    ((com.google.android.material.button.MaterialButton) _mpPp).setIcon(androidx.core.content.ContextCompat.getDrawable(")
            lines.append(f"                            {class_name}.this, ApkpyMediaService.isPlaying() ? R.drawable.apkpy_mp_pause : R.drawable.apkpy_mp_play));")
            lines.append("                    String _ma = ApkpyMediaService.currentArt();")
            lines.append("                    if (_ma != null && !_ma.isEmpty() && !_ma.equals(_mpLastArt)) {")
            lines.append("                        _mpLastArt = _ma;")
            lines.append("                        _loadMpCover(_mpCover, _ma);")
            lines.append("                    }")
            lines.append("                }")
            lines.append("                _mpHandler.postDelayed(this, 400);")
            lines.append("            }")
            lines.append("        };")
            lines.append("        _mpHandler.post(_mpTick);")

        if self._like_active:
            _like_jv = self._get_jv_from_py_var(audio_like['button'])
            _liked_lit = '"' + _escape_java_literal(str(audio_like.get('liked', 'Liked'))) + '"'
            _unliked_lit = '"' + _escape_java_literal(str(audio_like.get('unliked', 'Like'))) + '"'
            lines.append("")
            lines.append("        // ── Botão de like/guardar (audio.like_button) ───────────────────")
            lines.append(f"        final android.widget.Button _likeBtn = findViewById(R.id.{_like_jv});")
            lines.append("        _likeBtn.setOnClickListener(new View.OnClickListener() {")
            lines.append("            public void onClick(View _v) { _apkpyToggleLike(); }")
            lines.append("        });")
            lines.append("        _likeTick = new Runnable() {")
            lines.append("            public void run() {")
            _like_comp = next((c for c in all_comps_flat
                               if audio_like.get('button')
                               and c.get('_py_var') == audio_like.get('button')), None)
            _like_icons = (_like_comp or {}).get('_like_icons')
            if _like_icons:
                lines.append("                ((com.google.android.material.button.MaterialButton) _likeBtn).setIcon(androidx.core.content.ContextCompat.getDrawable(")
                lines.append(f"                        {class_name}.this, _apkpyIsLiked() ? R.drawable.{_like_icons['liked']} : R.drawable.{_like_icons['unliked']}));")
            else:
                lines.append(f"                _likeBtn.setText(_apkpyIsLiked() ? {_liked_lit} : {_unliked_lit});")
            lines.append("                _likeHandler.postDelayed(this, 400);")
            lines.append("            }")
            lines.append("        };")
            lines.append("        _likeHandler.post(_likeTick);")

    def _close_on_create(self):
        """The first drawing of the state, on_mount, the observers, and the brace that ends onCreate."""
        reactive_states = self.reactive_states
        lines = self.lines
        if reactive_states:
            lines.append("")
            lines.append("        // Initial reactive render after every View is available.")
            for _state_var in reactive_states:
                lines.append(f"        {self._state_method_name(_state_var)}();")

        _mount_callback = self.lifecycle_info.get('on_mount')
        if _mount_callback and _mount_callback in self.functions_map:
            lines.append("")
            lines.append("        // ApkPy lifecycle: mounted once for this Activity instance.")
            lines.append(f"        pythonCallback_{_mount_callback}();")
            for _state_var in reactive_states:
                lines.append(f"        {self._state_method_name(_state_var)}();")

        if self.screen_data_observers:
            lines.append("")
            lines.append("        // Data Core 1.3.1: lifecycle-safe query observers.")
            for _observer in self.screen_data_observers:
                data_feature.emit_observer_initialization(
                    lines, "        ", _observer, self._val_to_java,
                )

        if self.screen_job_observers:
            lines.append("")
            jobs_feature.emit_observers(
                lines, "        ", self.screen_job_observers, self.class_name,
            )

        lines.append("    }")
