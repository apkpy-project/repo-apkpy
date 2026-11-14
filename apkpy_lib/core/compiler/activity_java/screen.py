"""What is on the screen and what the app does with it: the questions every other part asks."""
from ...features import push as push_feature
from ...features import sheet as sheet_feature
from ...features import maps as maps_feature
from ...features import routes as routes_feature
from ...features import location_background as location_background_feature
from ...features import file_picker as file_picker_feature
from ...features import biometrics as biometrics_feature
from ...features import bluetooth as bluetooth_feature
from ...features import nfc as nfc_feature
from ...features import ble as ble_feature
from ...features import billing as billing_feature
from ...features import flashlight as flashlight_feature
from ...features import sensors as sensors_feature
from .... import motion
from ....theme import badge_at_end, component_style
from ..state import _BODY_KEYS, _USES_SENSORS
from ..style import _image_component_style
from ..resources_xml import _safe_android_id
from ..statements import _cmds_contain, _fn_cmds
from ..layout_xml import _vc_bubble_layout


class ScreenFacts:
    """What is on the screen and what the app does with it: the questions every other part asks."""

    # Helper: walk entire comp tree recursively
    def _all_comps(self, comp_list):
        for c in comp_list:
            yield c
            for ch in self._all_comps(c.get('children', [])):
                yield ch

    def _number_the_components(self):
        """Give each component the name its view has in the Java, in the order the layout numbers them."""
        all_comps_flat = self.all_comps_flat
        app_bar_info = self.app_bar_info
        now_playing = self.now_playing
        # Pre-atribuir _java_var a list_view components antes de gerar campos de instância
        _lst_pre = 0
        _vc_pre = 0
        _video_pre = 0
        _camera_view_pre = 0
        _map_pre = 0
        for _c in all_comps_flat:
            if _c['comp_type'] == 'list_view':
                _lst_pre += 1
                _c['_java_var'] = f"lst{_lst_pre}"
            elif _c['comp_type'] == 'virtual_collection':
                _vc_pre += 1
                _c['_java_var'] = f"vc{_vc_pre}"
            elif _c['comp_type'] == 'video':
                _video_pre += 1
                _c['_java_var'] = f"video{_video_pre}"
            elif _c['comp_type'] == 'camera_view':
                _camera_view_pre += 1
                _c['_java_var'] = f"cameraView{_camera_view_pre}"
            elif _c['comp_type'] == 'map':
                _map_pre += 1
                _c['_java_var'] = f"map{_map_pre}"

        # Pre-atribuir o id do ImageView (img1, img2, ...) na mesma ordem que o XML,
        # para que o carregamento de imagens remotas use o R.id correto.
        _img_pre = 0
        for _c in all_comps_flat:
            if _c['comp_type'] == 'image':
                _img_pre += 1
                _c['_img_id'] = f"img{_img_pre}"
        self.has_remote_image = (any(c['comp_type'] == 'image' and c.get('_is_remote') for c in all_comps_flat)
                                 or bool(app_bar_info and app_bar_info.get('_is_remote')))
        self.has_set_src = self._uses_command('comp_set_src')
        if self.has_set_src:
            self.has_remote_image = True
        # A capa do now_playing carrega-se em runtime via _loadRemoteImage → garante o helper.
        if now_playing and now_playing.get('cover') and any(
                c.get('_py_var') == now_playing.get('cover') for c in all_comps_flat):
            self.has_remote_image = True
        self.has_image_cache = self.has_remote_image and (
            bool(app_bar_info and app_bar_info.get('_is_remote'))
            or any(c['comp_type'] == 'image' and c.get('_is_remote')
                   and c.get('cache', True) for c in all_comps_flat)
        )
        self.has_image_tint = any(
            c['comp_type'] == 'image'
            and bool(c.get('tint') or _image_component_style(self.styles, c).get('tint'))
            for c in all_comps_flat
        )

        # Pre-atribuir o id do spinner (spin1, spin2, ...) na mesma ordem que o XML,
        # para que show()/hide() resolvam o R.id correto.
        _spin_pre = 0
        for _c in all_comps_flat:
            if _c['comp_type'] == 'spinner':
                _spin_pre += 1
                _c['_java_var'] = f"spin{_spin_pre}"

        _skeleton_pre = 0
        _state_pre = 0
        for _c in all_comps_flat:
            if _c['comp_type'] == 'skeleton':
                _skeleton_pre += 1
                _c['_java_var'] = f"skeleton{_skeleton_pre}"
            elif _c['comp_type'] in ('empty_state', 'error_state'):
                _state_pre += 1
                _c['_java_var'] = f"state{_state_pre}"
        # Variáveis de `for row in rows:` (JSON): row["k"] compila p/ _jsonGet
        self._json_iter_vars = set()

        # Nomes locais que o gerador viu receber um dict ou uma lista literal. Em
        # Java guardam texto JSON, por isso aninhá-los noutro literal tem de os
        # repor como estrutura — senão `{"messages": msgs}` sai com o array inteiro
        # entre aspas, que é uma coisa que nenhuma API aceita.
        self._json_struct_vars = set()

        # O que cada nome local guarda, quando o codigo o diz: 'list', 'dict',
        # 'text', ou 'other' depois de ser reatribuido a outra coisa.
        self._struct_kinds = {}

        # Variáveis locais que guardam um número (assign de int()/float()/aritmética).
        # Mapeia nome -> is_float, para que `valor = float(x)` continue numérico em
        # `valor * 2` (senão seria tratado como String e a conta evaporava). Reset no
        # início de cada corpo de função/handler (ver _gen_cmds / _gen_cmds_local).
        self._numeric_vars = {}
        # A comparison between two values that are not written out asks this
        # whether either is a number (_compare_node_to_java).
        self._val_to_java.numeric = self._numeric_java_expr
        self._val_to_java.bool_names = lambda: self._cur_bool_args[0]
        self._val_to_java.kind_of = self._kind_of

    def _uses_command(self, kind):
        def walk(value):
            if isinstance(value, dict):
                return value.get('type') == kind or any(walk(v) for v in value.values())
            return isinstance(value, (list, tuple)) and any(walk(v) for v in value)
        return walk(self.module_init_cmds) or any(
            walk((info or {}).get('cmds', [])) for info in (self.functions_map or {}).values())

    def _see_what_is_used(self):
        """Look once at the components and at the commands: what this screen needs written."""
        all_comps_flat = self.all_comps_flat
        styles = self.styles
        module_init_cmds = self.module_init_cmds
        functions_map = self.functions_map
        audio_playlists_list = self.audio_playlists_list
        audio_playlist_editor = self.audio_playlist_editor
        overlays = self.overlays
        # Descobrir quais imports são necessários (recursivo — inclui filhos de containers)
        types = {c.get('input_type', '') for c in all_comps_flat if c['comp_type'] in ('inputs', 'input_field')}
        self.has_button    = any(c['comp_type'] == 'button' for c in all_comps_flat)
        self.has_edittext  = bool(types & {'text', 'password', 'search', 'textarea', 'number'})
        self.has_textview  = any(c['comp_type'] == 'label' for c in all_comps_flat)
        self.has_checkbox  = 'checkbox' in types
        self.has_seekbar   = 'range' in types
        self.has_radio     = 'radio' in types
        self.has_spinner   = 'select' in types
        self.has_switch    = 'switch' in types
        self.has_list      = any(c['comp_type'] == 'list_view' for c in all_comps_flat)
        self.has_virtual_collection = any(
            c['comp_type'] == 'virtual_collection' for c in all_comps_flat
        )
        # A chamada ao renderizador de Markdown so' e' escrita se alguma coleccao
        # pedir a fatia. Escreve-la sempre obrigaria a embarcar o ApkpyRichContentView
        # em todas as apps com uma lista, e mudava o APK de quem nunca pediu nada.
        self.has_vc_markdown = any(
            c['comp_type'] == 'virtual_collection'
            and (c.get('template') or {}).get('markdown')
            for c in all_comps_flat
        )
        self.has_vc_avatar = any(
            c['comp_type'] == 'virtual_collection'
            and (c.get('template') or {}).get('avatar')
            for c in all_comps_flat
        )
        # Rows that are not all the same shape. Gated so a collection that never
        # asks for variants generates the adapter it always generated.
        self.has_vc_variants = any(
            c['comp_type'] == 'virtual_collection' and c.get('variants')
            for c in all_comps_flat
        )
        # Rows drawn as bubbles or cards with space between them: a variant with
        # align-self/max-width (a chat), or item-border-radius/gap on the
        # collection. Gated like the rest, so an existing adapter stays as it was.
        self.has_vc_bubbles = any(
            c['comp_type'] == 'virtual_collection'
            and _vc_bubble_layout(c, styles)[0]
            for c in all_comps_flat
        ) or any(
            c['comp_type'] == 'virtual_collection'
            and _vc_bubble_layout(c, styles)[1]
            for c in all_comps_flat
        )
        # badge-position: end -- gated the same way.
        self.has_vc_badge_end = any(
            c['comp_type'] == 'virtual_collection'
            and badge_at_end(component_style(styles, 'virtual_collection', c.get('id')))
            for c in all_comps_flat
        )
        self.has_video     = any(c['comp_type'] == 'video' for c in all_comps_flat)
        has_map       = any(c['comp_type'] == 'map' for c in all_comps_flat)
        self.has_carousel  = any(c['comp_type'] == 'carousel' for c in all_comps_flat)
        self.has_grid      = any(c['comp_type'] == 'grid' for c in all_comps_flat)
        self.has_skeleton  = any(c['comp_type'] == 'skeleton' for c in all_comps_flat)
        self.has_nav       = any(n['from_screen_id'] == self.screen_id for n in self.navigations)

        # Motion. A screen that never changes a component's visibility does not
        # get the helper, the same way it does not get icons it never uses.
        self._theme_motion = (styles or {}).get('__theme__', {}).get('motion')
        self._has_visibility_motion = (
            not motion.is_disabled(self._theme_motion)
            and (_cmds_contain(module_init_cmds, 'comp_visibility')
                 or any(_cmds_contain(_fn_cmds(body), 'comp_visibility')
                        for body in (functions_map or {}).values()))
        )

        self._screen_transitions_used = set()
        self.has_toast = False
        for comp in all_comps_flat:
            if comp['comp_type'] == 'button':
                cmd = comp.get('command') or comp.get('on_click')
                if cmd and cmd in functions_map and functions_map[cmd]:
                    self.has_toast = True
                    break
        self._feed_mutation_types = (
            'comp_prepend_items',
            'comp_stream_item',
            'comp_update_item',
            'comp_remove_item',
            'comp_merge_items',
            'comp_feed_rollback',
            'comp_feed_commit',
        )
        self._screen_virtual_pyvars = {
            comp.get('_py_var')
            for comp in all_comps_flat
            if comp.get('comp_type') == 'virtual_collection'
            and comp.get('_py_var')
        }

        self._mutated_feed_pyvars = set()
        # Saltar para uma linha nao muda dados nenhuns, mas precisa da mesma coisa
        # que uma mutacao: a RecyclerView tem de ser um campo, senao a chamada de
        # dentro de uma funcao nao tem nada para tocar.
        self._scrolled_feed_pyvars = set()
        self._scroll_lookup_pyvars = set()
        for _feed_function in functions_map.values():
            if _feed_function:
                self._collect_mutated_feeds(_feed_function.get('cmds', []))
        self.has_feed_mutations = bool(self._mutated_feed_pyvars)
        self.has_feed_scroll = bool(self._scrolled_feed_pyvars)
        self._recycler_field_pyvars = self._mutated_feed_pyvars | self._scrolled_feed_pyvars
        self.has_service_cancel = any(
            self._cmds_use_type(f_info.get('cmds', []), 'service_cancel')
            for f_info in functions_map.values() if f_info
        )
        self.has_service_once = any(
            self._cmds_use_type(f_info.get('cmds', []), 'service_once')
            for f_info in functions_map.values() if f_info
        )
        has_notify = any(
            self._cmds_use_type(f_info.get('cmds', []), 'notify')
            for f_info in functions_map.values() if f_info
        )
        self.has_share = any(
            self._cmds_use_type(f_info.get('cmds', []), 'share')
            for f_info in functions_map.values() if f_info
        )
        # Uma app que nunca troca de aparencia nao ganha o onResume que
        # verifica se ela mudou -- e' codigo que so' faz sentido para quem pede.
        self.has_appearance_switch = self._cmds_contain_any('appearance_set')
        self.has_clipboard_copy = any(
            self._cmds_use_type(f_info.get('cmds', []), 'clipboard_copy')
            for f_info in functions_map.values() if f_info
        )
        self.has_audio = any(
            any(self._cmds_use_type(f_info.get('cmds', []), t)
                for t in ('audio_play', 'audio_pause', 'audio_resume', 'audio_stop', 'audio_seek'))
            for f_info in functions_map.values() if f_info
        )
        self.has_audio_bg = any(
            any(self._cmds_use_type(f_info.get('cmds', []), t)
                for t in ('audio_play_bg', 'audio_playlist', 'audio_next', 'audio_prev', 'audio_shuffle', 'audio_repeat', 'audio_play_saved_playlist'))
            for f_info in functions_map.values() if f_info
        )
        # Criar/gerir playlists (audio.add_to_playlist / play_saved_playlist / playlists_list /
        # edit_playlist / remove_from_playlist / delete_playlist): gera os helpers _apkpyPl*
        # + o refresh no onResume.
        self._uses_playlists = bool(audio_playlists_list) or bool(audio_playlist_editor) or any(
            any(self._cmds_use_type(f_info.get('cmds', []), t)
                for t in ('audio_add_to_playlist', 'audio_play_saved_playlist',
                          'audio_edit_playlist', 'audio_remove_from_playlist', 'audio_delete_playlist'))
            for f_info in functions_map.values() if f_info
        )
        self._playlists_list_active = bool(audio_playlists_list) and any(
            c.get('_py_var') == audio_playlists_list for c in all_comps_flat)
        self._playlist_editor_active = bool(audio_playlist_editor) and any(
            c.get('_py_var') == audio_playlist_editor for c in all_comps_flat)
        # Os helpers de playlist (_apkpyAddToPlaylist lê o serviço; _apkpyPlaySavedPlaylist
        # chama _audioPlayPlaylist) são SEMPRE gerados sob _uses_playlists → garante que a
        # máquina de áudio-bg (incl. _audioPlayPlaylist) também existe.
        if self._uses_playlists:
            self.has_audio_bg = True
        # Esta Activity inicia o login OAuth? (→ emite _authStartLogin + helpers PKCE)
        self.has_auth_login = bool(self.auth) and any(
            self._cmds_use_type(f_info.get('cmds', []), 'auth_login')
            for f_info in functions_map.values() if f_info
        )
        # Esta Activity busca o perfil do utilizador? (→ emite _authFetchUser)
        self.has_auth_user = bool(self.auth) and any(
            self._cmds_use_type(f_info.get('cmds', []), 'auth_user')
            for f_info in functions_map.values() if f_info
        )
        # Navegação DENTRO de funções (on_click_navigate(ecra) como statement) gera um
        # cmd 'navigate' → também precisa do import android.content.Intent. As funções
        # são emitidas em todas as activities, por isso basta detetar globalmente.
        self.has_nav_cmd = any(
            self._cmds_use_type(f_info.get('cmds', []), 'navigate')
            for f_info in functions_map.values() if f_info
        )
        # Barra "now playing": só se aplica se o range/label estiver NESTE ecrã.
        # (Os _java_var só são atribuídos mais à frente, por isso aqui testamos o _py_var;
        #  os java vars são resolvidos no momento de emitir o wiring, no fim do onCreate.)
        self._np_active = bool(self.now_playing) and any(
            c.get('_py_var') == self.now_playing['progress'] for c in all_comps_flat
        )
        self._ac_active = bool(self.audio_controls) and (self._ac_has('play_pause') or self._ac_has('shuffle') or self._ac_has('repeat'))
        # Mini-player fixo: barra em TODOS os ecrãs (lê o media service). Sempre ativo
        # quando mini_player() foi chamado — a barra está no XML de cada ecrã.
        self._mp_active = bool(self.mini_player)
        # Like/guardar: o botão e/ou a lista de favoritos têm de estar NESTE ecrã.
        self._like_active = bool(self.audio_like) and any(
            c.get('_py_var') == self.audio_like['button'] for c in all_comps_flat)
        self._liked_list_active = bool(self.audio_liked_list) and any(
            c.get('_py_var') == self.audio_liked_list for c in all_comps_flat)
        self.has_files = any(
            any(self._cmds_use_type(f_info.get('cmds', []), t)
                for t in ('files_download', 'files_delete'))
            for f_info in functions_map.values() if f_info
        )
        self.has_uploads = any(
            any(self._cmds_use_type(f_info.get('cmds', []), t)
                for t in ('upload_multipart', 'upload_cancel'))
            for f_info in functions_map.values() if f_info
        )
        self.has_websocket = any(
            any(self._cmds_use_type(f_info.get('cmds', []), t)
                for t in (
                    'websocket_connect', 'websocket_send', 'websocket_close',
                ))
            for f_info in functions_map.values() if f_info
        )
        self.has_push = push_feature.commands_use_push(functions_map, module_init_cmds)
        self.has_continuous_location = maps_feature.commands_use_location(
            functions_map, module_init_cmds
        )
        self.has_routes = routes_feature.commands_use_routes(functions_map, module_init_cmds)
        self.has_background_location = location_background_feature.commands_use_background(
            functions_map, module_init_cmds
        )
        # apps.* (inspeção de apps instaladas) — usa o PhotoResultCallback partilhado
        # (extract/hash) e o padrão Consumer<String> (list/permissions).
        self.has_apps = any(
            any(self._cmds_use_type(f_info.get('cmds', []), t)
                for t in ('apps_list', 'apps_permissions', 'apps_extract', 'apps_hash'))
            for f_info in functions_map.values() if f_info
        )
        self.has_camera_capture = any(
            self._cmds_use_type(f_info.get('cmds', []), 'camera_capture')
            for f_info in functions_map.values() if f_info
        )
        self.has_gallery_pick = any(
            self._cmds_use_type(f_info.get('cmds', []), 'gallery_pick')
            for f_info in functions_map.values() if f_info
        )
        self.has_file_pick = file_picker_feature.commands_use_picker(
            functions_map, module_init_cmds,
        )
        self.has_biometrics = biometrics_feature.commands_use_biometrics(
            functions_map, module_init_cmds,
        )
        self.has_bluetooth = bluetooth_feature.commands_use_bluetooth(
            functions_map, module_init_cmds,
        )
        self.has_nfc = nfc_feature.commands_use_nfc(functions_map, module_init_cmds)
        self.has_ble = ble_feature.commands_use_ble(
            functions_map, module_init_cmds,
        )
        self.has_billing = billing_feature.commands_use_billing(
            functions_map, module_init_cmds,
        )
        self.has_flashlight = flashlight_feature.commands_use_flashlight(
            functions_map, module_init_cmds,
        )
        self.has_sensors = sensors_feature.commands_use_sensors(
            functions_map, module_init_cmds,
        ) or _USES_SENSORS[0]
        self._sensors_watched = sensors_feature.sensors_used(
            functions_map, module_init_cmds,
        )
        self.has_location = any(
            self._cmds_use_type(f_info.get('cmds', []), 'location_get')
            for f_info in functions_map.values() if f_info
        )
        self.has_alert = any(
            self._cmds_use_type(f_info.get('cmds', []), 'alert')
            for f_info in functions_map.values() if f_info
        )
        self.has_confirm = any(
            self._cmds_use_type(f_info.get('cmds', []), 'confirm')
            for f_info in functions_map.values() if f_info
        )
        self.has_snackbar = any(
            self._cmds_use_type(f_info.get('cmds', []), 'snackbar')
            for f_info in functions_map.values() if f_info
        )
        _overlay_names = set()
        for _function in functions_map.values():
            if _function:
                self._used_overlay_names(_function.get('cmds', []), _overlay_names)
        for _component in all_comps_flat:
            for _key in ('popup_overlay', 'context_overlay'):
                if _component.get(_key):
                    _overlay_names.add(_component[_key])
        self.active_overlays = {
            name: overlays[name] for name in _overlay_names if name in overlays
        }
        self.has_bottom_sheet = any(o.get('type') == 'bottom_sheet' for o in self.active_overlays.values())
        self.has_modal = any(o.get('type') == 'modal' for o in self.active_overlays.values())
        self.has_popup_menu = any(o.get('type') in ('menu', 'context_menu') for o in self.active_overlays.values())
        has_date_picker = any(o.get('type') == 'date_picker' for o in self.active_overlays.values())
        has_time_picker = any(o.get('type') == 'time_picker' for o in self.active_overlays.values())
        self.has_overlays = bool(self.active_overlays)
        # The sheets with components that live in this screen. Inflated whether
        # or not anything opens them: their components are set up in onCreate.
        self._screen_sheets = sheet_feature.of_screen(overlays, self.screen_id)
        self.has_manual_notif_request = any(
            self._cmds_request_perm(f_info.get('cmds', []), 'POST_NOTIFICATIONS')
            for f_info in functions_map.values() if f_info
        )

    # service.cancel(...)/service.once(...) podem ser chamados a partir de qualquer
    # ecrã (não só o inicial), por isso é preciso procurar nas cmds de TODAS as funções
    def _cmds_use_type(self, cmds_list, type_name):
        for c in cmds_list:
            if isinstance(c, dict):
                if c.get('type') == type_name:
                    return True
                for body_key in ('true_body', 'false_body'):
                    if c.get(body_key) and self._cmds_use_type(c[body_key], type_name):
                        return True
        return False

    def _collect_mutated_feeds(self, cmds_list):
        for command in cmds_list:
            if not isinstance(command, dict):
                continue
            if command.get('py_var') in self._screen_virtual_pyvars:
                if command.get('type') in self._feed_mutation_types:
                    self._mutated_feed_pyvars.add(command.get('py_var'))
                elif command.get('type') == 'comp_scroll_to':
                    self._scrolled_feed_pyvars.add(command.get('py_var'))
                    if command.get('mode') == 'item':
                        self._scroll_lookup_pyvars.add(command.get('py_var'))
            for body_key in ('true_body', 'false_body'):
                if command.get(body_key):
                    self._collect_mutated_feeds(command[body_key])

    def _cmds_contain_any(self, kind):
        return _cmds_contain(self.module_init_cmds, kind) or any(
            self._cmds_use_type(f_info.get('cmds', []), kind)
            for f_info in self.functions_map.values() if f_info
        )

    # Botões de estado (audio.controls). O _java_var dos botões só é atribuído na
    # geração do XML, por isso aqui (cedo, p/ declarar os campos) testamos só a
    # PRESENÇA do py_var; os java vars resolvem-se mais tarde, no onCreate.
    def _ac_has(self, role):
        pv = self.audio_controls.get(role) if self.audio_controls else None
        return bool(pv) and any(c.get('_py_var') == pv for c in self.all_comps_flat)

    def _used_overlay_names(self, cmds_list, result):
        for cmd in cmds_list or []:
            if not isinstance(cmd, dict):
                continue
            if cmd.get('type') in ('overlay_open', 'overlay_close') and cmd.get('overlay'):
                result.add(cmd['overlay'])
            for body_key in _BODY_KEYS:
                self._used_overlay_names(cmd.get(body_key, []), result)

    def _overlay_method_name(self, name):
        return '_apkpyOpen_' + _safe_android_id(name, 'overlay')

    # O utilizador já pede a permissão manualmente com request("POST_NOTIFICATIONS", ...)?
    # Se sim, não geramos um pedido automático duplicado no arranque.
    def _cmds_request_perm(self, cmds_list, perm_name):
        for c in cmds_list:
            if isinstance(c, dict):
                if c.get('type') == 'request_permission' and c.get('perm') == perm_name:
                    return True
                for body_key in ('true_body', 'false_body'):
                    if c.get(body_key) and self._cmds_request_perm(c[body_key], perm_name):
                        return True
        return False
