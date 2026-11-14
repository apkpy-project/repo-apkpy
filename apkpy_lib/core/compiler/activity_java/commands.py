"""What a function of the app does, command by command, written as Java statements."""
import ast
import json

from ...features import push as push_feature
from ...features import chart as chart_feature
from ...features import choice as choice_feature
from ...features import field as field_feature
from ...features import web_page as web_page_feature
from ...features import zoom as zoom_feature
from ...features import draw_pad as draw_pad_feature
from ...features import keyboard as keyboard_feature
from ...features import maps as maps_feature
from ...features import routes as routes_feature
from ...features import location_background as location_background_feature
from ...features import rich_content as rich_content_feature
from ...features import feeds as feeds_feature
from ...features import data as data_feature
from ...features import jobs as jobs_feature
from ...features import file_picker as file_picker_feature
from ...features import biometrics as biometrics_feature
from ...features import bluetooth as bluetooth_feature
from ...features import native as native_feature
from ...features import nfc as nfc_feature
from ...features import contacts as contacts_feature
from ...features import ble as ble_feature
from ...features import billing as billing_feature
from ...features import flashlight as flashlight_feature
from ...features import pending_views as pending_views_feature
from ...features import wallpaper as wallpaper_feature
from ...features import sensors as sensors_feature
from ...features import view_state as view_state_feature
from ...features import function_values as function_values_feature
from ...features import notifications as notifications_feature
from ...features import camera as camera_feature
from ...features import camera_view as camera_view_feature
from .... import motion
from ....theme import component_style
from ... import unsupported
from ..state import _NUMBERISH_NAMES, _NUMERIC_CONSTS, _RAW_LOOP_VARS, _RETURNS_VALUE
from ..expressions import (
    _callback_call_args, _cmds_definitely_return, _cond_to_java, _escape_java_literal,
    _forget_numberish, _https_body_java, _https_timeout_java, _if_compare_cond, _note_numberish,
    _parenthesized, _raw_item_java, _rich_set_value_java, _sql_params_java, _storage_default_java,
    _storage_key_java, _text_value_java, _track_json_struct,
)
from ..statements import (
    _ITEM_COUNT, _ITEM_ONCE, _ITEM_SHARED, _ITEM_SHARED_JAVA, _ITEM_STACK, _assign_rhs_java,
    _emit_apps_cmd, _emit_for_loop, _emit_language_set, _emit_list_append, _emit_print, _emit_raise,
    _emit_try_block, _emit_while_loop, _hoist_branch_assignments, _item_names_hide,
    _item_names_leave, _item_names_show, _line_mark, _raw_loop_enter, _shared_item_names,
)
from ..prescan import _global_sync_java


class Commands:
    """What a function of the app does, command by command, written as Java statements."""

    def _emit_upload_cmd(self, target_lines, indent, command):
        """Emit one optimized multipart call for both top-level and callbacks."""
        seq = int(command.get('seq', 0))
        task = self._val_to_java(command.get('task_node'))
        url = self._val_to_java(command.get('url_node'))
        path = self._val_to_java(command.get('path_node'))
        field = (
            self._val_to_java(command.get('field_node'))
            if command.get('field_node') is not None else '"file"'
        )
        content_type = (
            self._val_to_java(command.get('content_type_node'))
            if command.get('content_type_node') is not None else '""'
        )
        fields_arg = "null"
        fields_node = command.get('fields_node')
        if fields_node is not None:
            fields_arg = f"_upload_fields_{seq}"
            target_lines.extend(
                self._dict_node_to_java(fields_node, fields_arg, indent)
            )
        headers_arg = "null"
        headers_node = command.get('headers_node')
        if headers_node is not None:
            headers_arg = f"_upload_headers_{seq}"
            target_lines.extend(
                self._dict_node_to_java(headers_node, headers_arg, indent)
            )
        # Java rejects a lambda parameter that shadows a parameter or local of
        # the enclosing method, so these names are mangled rather than the
        # obvious success/response/percent/sent/total.
        progress_cb = command.get('progress_callback')
        progress_arg = (
            "(_upPercent, _upSent, _upTotal) -> "
            f"pythonCallback_{progress_cb}("
            "String.valueOf(_upPercent), String.valueOf(_upSent), "
            "String.valueOf(_upTotal))"
            if progress_cb else "null"
        )
        result_cb = command.get('result_callback')
        result_arg = (
            f"(_upOk, _upResponse) -> pythonCallback_{result_cb}("
            "_upOk, _upResponse)"
            if result_cb else "null"
        )
        target_lines.append(
            f"{indent}_uploadMultipart("
            f"String.valueOf({task}), String.valueOf({url}), "
            f"String.valueOf({path}), String.valueOf({field}), "
            f"{fields_arg}, {headers_arg}, String.valueOf({content_type}), "
            f"{progress_arg}, {result_arg});"
        )

    def _emit_websocket_cmd(self, target_lines, indent, command):
        """Emit one WebSocket command for onCreate and callback bodies."""
        command_type = command.get('type')
        connection = self._val_to_java(command.get('connection_node'))
        if command_type == 'websocket_send':
            message = self._val_to_java(command.get('message_node'))
            target_lines.append(
                f"{indent}_websocketSend(String.valueOf({connection}), "
                f"String.valueOf({message}));"
            )
            return
        if command_type == 'websocket_close':
            reason = (
                self._val_to_java(command.get('reason_node'))
                if command.get('reason_node') is not None else '"closed"'
            )
            target_lines.append(
                f"{indent}_websocketClose(String.valueOf({connection}), "
                f"{int(command.get('code', 1000))}, "
                f"String.valueOf({reason}));"
            )
            return

        seq = int(command.get('seq', 0))
        url = self._val_to_java(command.get('url_node'))
        headers_arg = 'null'
        if command.get('headers_node') is not None:
            headers_arg = f"_websocket_headers_{seq}"
            target_lines.extend(self._dict_node_to_java(
                command.get('headers_node'), headers_arg, indent
            ))
        protocols_arg = 'null'
        protocols = command.get('protocols') or []
        if protocols:
            protocols_arg = f"_websocket_protocols_{seq}"
            target_lines.append(
                f"{indent}java.util.List<String> {protocols_arg} = "
                "new java.util.ArrayList<>();"
            )
            for protocol in protocols:
                target_lines.append(
                    f"{indent}{protocols_arg}.add("
                    f"{json.dumps(str(protocol))});"
                )
        open_callback = command.get('open_callback')
        message_callback = command.get('message_callback')
        close_callback = command.get('close_callback')
        error_callback = command.get('error_callback')
        open_arg = (
            f"() -> pythonCallback_{open_callback}()"
            if open_callback else 'null'
        )
        message_arg = (
            f"message -> pythonCallback_{message_callback}(message)"
            if message_callback else 'null'
        )
        close_arg = (
            f"(code, reason) -> pythonCallback_{close_callback}(code, reason)"
            if close_callback else 'null'
        )
        error_arg = (
            f"message -> pythonCallback_{error_callback}(message)"
            if error_callback else 'null'
        )
        target_lines.append(
            f"{indent}_websocketConnect("
            f"String.valueOf({connection}), String.valueOf({url}), "
            f"{headers_arg}, {protocols_arg}, "
            f"{str(bool(command.get('reconnect', True))).lower()}, "
            f"{int(command.get('reconnect_delay_ms', 1000))}L, "
            f"{int(command.get('max_reconnect_delay_ms', 15000))}L, "
            f"{int(command.get('ping_interval_seconds', 25))}L, "
            f"{open_arg}, {message_arg}, {close_arg}, {error_arg});"
        )

    def _emit_screen_transition(self, command, indent):
        """Slide the next screen in, when the app asked for it.

        overridePendingTransition is deprecated at the targetSdk this project
        generates, so API 34+ gets overrideActivityTransition and older devices
        keep the old call. Without the guard the animation is simply dropped on
        new Android versions, silently.
        """
        lines = self.lines
        kind = (command or {}).get('transition') or 'none'
        if kind == 'none' or motion.is_disabled(self._theme_motion):
            return
        self._screen_transitions_used.add(kind)
        enter = f"R.anim.apkpy_{kind}_enter"
        exit_ = f"R.anim.apkpy_{kind}_exit"
        lines.append(
            f"{indent}if (android.os.Build.VERSION.SDK_INT >= 34) {{")
        lines.append(
            f"{indent}    overrideActivityTransition("
            f"OVERRIDE_TRANSITION_OPEN, {enter}, {exit_});")
        lines.append(f"{indent}}} else {{")
        lines.append(f"{indent}    overridePendingTransition({enter}, {exit_});")
        lines.append(f"{indent}}}")

    def _visibility_ms(self, comp_dict):
        """Duration for one component: CSS ``transition:`` over the preset."""
        if not self._has_visibility_motion:
            return 0
        # Cascade like every other property: body -> type -> id. Reading the
        # id block alone made ``transition`` the single exception, and an
        # app that set it once on body got nothing on either runtime.
        comp_style = component_style(
            self.styles, (comp_dict or {}).get('comp_type'),
            (comp_dict or {}).get('id'),
        )
        return motion.duration(
            'visibility', self._theme_motion, comp_style.get('transition'))

    # ── _gen_cmds: converte lista de comandos Python em linhas Java ──────────
    def _emit_reactive_state_cmd(self, command, indent):
        lines = self.lines
        state_var = command['state_var']
        state_info = self.reactive_states[state_var]
        key = self._state_key_literal(state_var)
        default_expr = self._val_to_java(state_info.get('initial_node'))
        default_java = f"String.valueOf({default_expr})"
        if command['type'] == 'state_set':
            value_java = self._val_to_java(command.get('value_node'))
            lines.append(
                f'{indent}ApkpyReactiveState.set("{key}", '
                f'String.valueOf({value_java}));'
            )
        elif command['type'] == 'state_increment':
            amount_java = self._val_to_java(command.get('amount_node'))
            sign = '-1.0d * ' if command.get('direction', 1) < 0 else ''
            lines.append(
                f'{indent}ApkpyReactiveState.increment("{key}", '
                f'{sign}Double.parseDouble(String.valueOf({amount_java})), '
                f'{default_java});'
            )
        else:
            lines.append(
                f'{indent}ApkpyReactiveState.toggle("{key}", {default_java});'
            )
        lines.append(f"{indent}{self._state_method_name(state_var)}();")

    def _emit_video_control(self, target_lines, indent, command):
        jv = self._get_jv_from_py_var(command.get('py_var'))
        if not jv:
            return
        component = next(
            (
                item for item in self.all_comps_flat
                if item.get('_py_var') == command.get('py_var')
            ),
            None,
        )
        action_name = command.get('action')
        args_nodes = command.get('args_nodes') or []
        target_lines.append(f"{indent}if ({jv}Player != null) {{")
        body_indent = indent + "    "
        if action_name == 'play':
            target_lines.append(
                f"{body_indent}if (!{jv}Prepared) {{ "
                f"{jv}Player.prepare(); {jv}Prepared = true; }}"
            )
            target_lines.append(f"{body_indent}{jv}Player.play();")
        elif action_name == 'pause':
            target_lines.append(f"{body_indent}{jv}Player.pause();")
        elif action_name == 'stop':
            target_lines.append(f"{body_indent}{jv}Player.stop();")
            target_lines.append(f"{body_indent}{jv}Player.seekTo(0L);")
            target_lines.append(f"{body_indent}{jv}Prepared = false;")
        elif action_name == 'seek' and args_nodes:
            value = self._val_to_java(args_nodes[0])
            target_lines.append(f"{body_indent}try {{")
            target_lines.append(
                f"{body_indent}    long _videoSeekMs = Math.max(0L, "
                f"Math.round(Double.parseDouble(String.valueOf({value})) "
                "* 1000.0d));"
            )
            target_lines.append(
                f"{body_indent}    {jv}Player.seekTo(_videoSeekMs);"
            )
            target_lines.append(
                f"{body_indent}}} catch (Exception _videoSeekError) {{ }}"
            )
        elif action_name == 'set_source' and args_nodes:
            source = self._val_to_java(args_nodes[0])
            autoplay_node = command.get('autoplay_node')
            autoplay = (
                self._val_to_java(autoplay_node)
                if autoplay_node is not None else 'false'
            )
            preload = bool(component and component.get('preload', True))
            target_lines.append(
                f"{body_indent}{jv}ReadySent = false;"
            )
            target_lines.append(
                f"{body_indent}{jv}Player.setMediaItem("
                f"MediaItem.fromUri(String.valueOf({source})));"
            )
            if preload:
                target_lines.append(f"{body_indent}{jv}Player.prepare();")
                target_lines.append(f"{body_indent}{jv}Prepared = true;")
            else:
                target_lines.append(f"{body_indent}{jv}Prepared = false;")
            target_lines.append(
                f"{body_indent}if (Boolean.parseBoolean(String.valueOf("
                f"{autoplay}))) {{"
            )
            target_lines.append(
                f"{body_indent}    if (!{jv}Prepared) {{ "
                f"{jv}Player.prepare(); {jv}Prepared = true; }}"
            )
            target_lines.append(f"{body_indent}    {jv}Player.play();")
            target_lines.append(f"{body_indent}}} else {{")
            target_lines.append(f"{body_indent}    {jv}Player.pause();")
            target_lines.append(f"{body_indent}}}")
        elif action_name == 'set_speed' and args_nodes:
            value = self._val_to_java(args_nodes[0])
            target_lines.append(f"{body_indent}try {{")
            target_lines.append(
                f"{body_indent}    float _videoSpeed = Math.max(0.25f, "
                f"Math.min(4.0f, Float.parseFloat(String.valueOf({value}))));"
            )
            target_lines.append(
                f"{body_indent}    {jv}Player.setPlaybackSpeed(_videoSpeed);"
            )
            target_lines.append(
                f"{body_indent}}} catch (Exception _videoSpeedError) {{ }}"
            )
        elif action_name == 'set_muted':
            value = self._val_to_java(args_nodes[0]) if args_nodes else 'true'
            target_lines.append(
                f"{body_indent}{jv}Player.setVolume("
                f"Boolean.parseBoolean(String.valueOf({value})) ? 0f : 1f);"
            )
        target_lines.append(f"{indent}}}")

    def _gen_cmds_body(self, cmds_list, indent, declared=None):
        lines = self.lines
        functions_map = self.functions_map
        _cur_bool_args = self._cur_bool_args
        class_name = self.class_name
        all_comps_flat = self.all_comps_flat
        # *declared* = nomes já declarados neste método Java. Uma segunda
        # atribuição à mesma variável (ex.: acumular texto dentro de um for)
        # tem de gerar `x = ...` e não `String x = ...` (redeclaração não
        # compila). O set flui pelas recursões (if/for) e começa vazio em
        # cada ponto de emissão top-level (onCreate, cada onClick, ...).
        if declared is None:
            declared = set()
            self._numeric_vars.clear()  # novo corpo top-level → esquece numéricos anteriores
            _NUMBERISH_NAMES[0] = set()
            self._struct_kinds.clear()
            self._numeric_vars.update(_NUMERIC_CONSTS[0])
        for c in cmds_list:
            _line_mark(lines, c, indent)
            _hoist_branch_assignments(c, lines, indent, declared)
            _forget_numberish(c)
            if isinstance(c, str):
                lines.append(f"{indent}Toast.makeText(getApplicationContext(), \"{c}\", Toast.LENGTH_SHORT).show();")
            elif c['type'] == 'toast':
                msg_expr = self._val_to_java(c['msg_node']) if c.get('msg_node') else '""'
                lines.append(f"{indent}Toast.makeText(getApplicationContext(), String.valueOf({msg_expr}), Toast.LENGTH_SHORT).show();")
            elif c['type'] == 'snackbar':
                msg_expr = self._val_to_java(c['msg_node']) if c.get('msg_node') else '""'
                duration = max(500, int(c.get('duration', 3000)))
                lines.append(f"{indent}{{")
                lines.append(f"{indent}    Snackbar _apkpyBar = Snackbar.make(findViewById(android.R.id.content), String.valueOf({msg_expr}), Snackbar.LENGTH_INDEFINITE);")
                lines.append(f"{indent}    _apkpyBar.setDuration({duration});")
                if c.get('action_node'):
                    action_expr = self._val_to_java(c['action_node'])
                    callback = c.get('callback')
                    if callback:
                        lines.append(f"{indent}    _apkpyBar.setAction(String.valueOf({action_expr}), _apkpyActionView -> pythonCallback_{callback}());")
                    else:
                        lines.append(f"{indent}    _apkpyBar.setAction(String.valueOf({action_expr}), v -> {{}});")
                lines.append(f"{indent}    _apkpyBar.show();")
                lines.append(f"{indent}}}")
            elif c['type'] == 'comp_stream':
                jv = self._get_jv_from_py_var(c['py_var'])
                if jv:
                    chars, step = motion.stream_step(c.get('speed'), self._theme_motion)
                    lines.append(
                        # findViewById e nao o nome local: a variavel `jv` so'
                        # existe dentro do onCreate, e um stream() escrito numa
                        # funcao com nome caia num cannot-find-symbol.
                        f"{indent}_apkpyStreamText("
                        f"(android.widget.TextView) findViewById(R.id.{jv}), "
                        f"String.valueOf({self._val_to_java(c['val_node'])}), "
                        f"{chars}, {step});"
                    )
            elif c['type'] == 'comp_stream_item':
                jv = self._get_jv_from_py_var(c['py_var'])
                if jv:
                    chars, step = motion.stream_step(c.get('speed'), self._theme_motion)
                    lines.append(
                        f"{indent}_apkpyStreamItem({jv}_items, {jv}Adapter, "
                        f'"{_escape_java_literal(str(c.get("key") or "id"))}", '
                        f"String.valueOf({self._val_to_java(c['item_id_node'])}), "
                        f"String.valueOf({self._val_to_java(c['field_node'])}), "
                        f"String.valueOf({self._val_to_java(c['val_node'])}), "
                        f"{chars}, {step});"
                    )
            elif c['type'] == 'drawer_open':
                lines.append(f"{indent}_apkpyDrawer(true);")
            elif c['type'] == 'drawer_close':
                lines.append(f"{indent}_apkpyDrawer(false);")
            elif c['type'] == 'overlay_open':
                lines.append(f"{indent}{self._overlay_method_name(c['overlay'])}();")
            elif c['type'] == 'overlay_close':
                lines.append(f"{indent}_apkpyCloseOverlay();")
            elif c['type'] in ('state_set', 'state_increment', 'state_toggle'):
                self._emit_reactive_state_cmd(c, indent)
            elif c['type'] in (
                    'comp_append_items', 'comp_prepend_items',
                    'comp_update_item', 'comp_remove_item',
                    'comp_merge_items', 'comp_feed_rollback',
                    'comp_feed_commit', 'comp_finish_load', 'comp_refresh', 'comp_scroll_to'):
                self._emit_feed_command(c, indent)
            elif c['type'] in data_feature.COMMAND_TYPES:
                data_feature.emit_command(
                    lines, indent, c, self._val_to_java, self._gen_cmds,
                    functions_map, declared, returns=_cmds_definitely_return,
                )
            elif c['type'] in jobs_feature.COMMAND_TYPES:
                jobs_feature.emit_command(lines, indent, c, self._val_to_java, "activity")
            elif c['type'] == 'function_call' and native_feature.function_for(c['name']) is not None:
                native_feature.emit_command(
                    lines, indent,
                    native_feature.statement_command(c, functions_map),
                    self._val_to_java, functions_map)
            elif c['type'] == 'function_call' and function_values_feature.is_call_name(c['name']):
                # f(x) on a line of its own, f a function kept in a value.
                lines.append(f"{indent}_apkpyCall(" + ", ".join(
                    "String.valueOf(%s)" % self._val_to_java(a) for a in c.get('args_nodes', [])) + ");")
            elif c['type'] == 'function_call':
                if c['name'] not in functions_map:
                    unsupported.raise_unknown_function(
                        c['name'], c.get('lineno', 0), functions_map)
                _fc_args = _callback_call_args(c['name'], c.get('args_nodes', []), self._val_to_java, functions_map, self.boolean_first_arg_callbacks, _cur_bool_args[0])
                lines.append(f"{indent}pythonCallback_{c['name']}({_fc_args});")
            elif c['type'] == 'service_cancel':
                id_val = self._val_to_java(c['id_node']) if c.get('id_node') else '"bg_service"'
                lines.append(f"{indent}WorkManager.getInstance(getApplicationContext()).cancelUniqueWork(String.valueOf({id_val}));")
            elif c['type'] == 'service_once':
                svc_id = c['id']
                worker_class = (self.onetime_services or {}).get(svc_id, {}).get('worker_class')
                if worker_class:
                    delay = max(0, int(c.get('after_minutes', 0)))
                    req_var = f"onceRequest_{svc_id}"
                    constraints_var = None
                    if c.get('only_on_wifi') or c.get('only_when_charging'):
                        constraints_var = f"constraints_{svc_id}"
                        lines.append(f"{indent}Constraints {constraints_var} = new Constraints.Builder()")
                        if c.get('only_on_wifi'):
                            lines.append(f"{indent}        .setRequiredNetworkType(NetworkType.UNMETERED)")
                        if c.get('only_when_charging'):
                            lines.append(f"{indent}        .setRequiresCharging(true)")
                        lines.append(f"{indent}    .build();")
                    lines.append(f"{indent}OneTimeWorkRequest {req_var} = new OneTimeWorkRequest.Builder({worker_class}.class)")
                    lines.append(f"{indent}        .setInitialDelay({delay}, java.util.concurrent.TimeUnit.MINUTES)")
                    if constraints_var:
                        lines.append(f"{indent}        .setConstraints({constraints_var})")
                    lines.append(f"{indent}    .build();")
                    lines.append(f"{indent}WorkManager.getInstance(getApplicationContext()).enqueueUniqueWork(")
                    lines.append(f"{indent}    \"{svc_id}\",")
                    lines.append(f"{indent}    ExistingWorkPolicy.REPLACE,")
                    lines.append(f"{indent}    {req_var}")
                    lines.append(f"{indent});")
            elif c['type'] == 'alert':
                title_expr = self._val_to_java(c['title_node']) if c.get('title_node') else '"Aviso"'
                msg_expr   = self._val_to_java(c['msg_node']) if c.get('msg_node') else '""'
                ok_expr = f"String.valueOf({self._val_to_java(c['ok_node'])})" if c.get('ok_node') else 'null'
                lines.append(f"{indent}_alertDialog(String.valueOf({title_expr}), String.valueOf({msg_expr}), {ok_expr});")
            elif c['type'] == 'confirm':
                title_expr = self._val_to_java(c['title_node']) if c.get('title_node') else '"Confirmar"'
                msg_expr   = self._val_to_java(c['msg_node']) if c.get('msg_node') else '""'
                cb = c.get('callback')
                ok_expr = f"String.valueOf({self._val_to_java(c['ok_node'])})" if c.get('ok_node') else 'null'
                cancel_expr = (f"String.valueOf({self._val_to_java(c['cancel_node'])})"
                               if c.get('cancel_node') else 'null')
                if cb:
                    lines.append(f"{indent}_confirmDialog(String.valueOf({title_expr}), String.valueOf({msg_expr}), {ok_expr}, {cancel_expr}, confirmed -> pythonCallback_{cb}(confirmed));")
                else:
                    lines.append(f"{indent}_confirmDialog(String.valueOf({title_expr}), String.valueOf({msg_expr}), {ok_expr}, {cancel_expr}, null);")
            elif c['type'] == 'notify' or c['type'].startswith('notification_'):
                notifications_feature.emit_command(lines, c, self._val_to_java, indent)
            elif c['type'] == 'share':
                text_expr  = self._val_to_java(c['text_node']) if c.get('text_node') else '""'
                title_expr = f"String.valueOf({self._val_to_java(c['title_node'])})" if c.get('title_node') else 'null'
                lines.append(f"{indent}_share(String.valueOf({text_expr}), {title_expr});")
            elif c['type'] == 'clipboard_copy':
                text_expr = self._val_to_java(c['text_node']) if c.get('text_node') else '""'
                lines.append(f"{indent}_clipboardCopy(String.valueOf({text_expr}));")
            elif c['type'] == 'audio_play':
                src_expr = self._val_to_java(c['src_node']) if c.get('src_node') else '""'
                lines.append(f"{indent}_audioPlay(String.valueOf({src_expr}));")
            elif c['type'] == 'audio_pause':
                lines.append(f"{indent}_audioPause();")
            elif c['type'] == 'audio_resume':
                lines.append(f"{indent}_audioResume();")
            elif c['type'] == 'audio_stop':
                lines.append(f"{indent}_audioStop();")
            elif c['type'] == 'audio_seek':
                sec_expr = self._val_to_java(c['sec_node']) if c.get('sec_node') else '"0"'
                lines.append(f"{indent}_audioSeek(String.valueOf({sec_expr}));")
            elif c['type'] == 'audio_play_bg':
                src_expr = self._val_to_java(c['src_node']) if c.get('src_node') else '""'
                title_expr = self._val_to_java(c['title_node']) if c.get('title_node') else '""'
                artist_expr = self._val_to_java(c['artist_node']) if c.get('artist_node') else '""'
                art_expr = self._val_to_java(c['art_node']) if c.get('art_node') else '""'
                lines.append(f"{indent}_audioPlayBackground(String.valueOf({src_expr}), String.valueOf({title_expr}), String.valueOf({artist_expr}), String.valueOf({art_expr}));")
            elif c['type'] == 'audio_playlist':
                srcs_expr = self._val_to_java(c['sources_node']) if c.get('sources_node') else '"[]"'
                titles_expr = self._val_to_java(c['titles_node']) if c.get('titles_node') else '"[]"'
                artists_expr = self._val_to_java(c['artists_node']) if c.get('artists_node') else '"[]"'
                arts_expr = self._val_to_java(c['arts_node']) if c.get('arts_node') else '"[]"'
                # start pode ser um índice (0, 1, …) OU o src de uma faixa — o
                # serviço resolve (parseInt, senão procura o src na fila). Assim o
                # tap-to-play num carrossel/lista pode arrancar a fila nessa faixa.
                start_expr = f"String.valueOf({self._val_to_java(c['start_node'])})" if c.get('start_node') else '"0"'
                lines.append(f"{indent}_audioPlayPlaylist(String.valueOf({srcs_expr}), String.valueOf({titles_expr}), String.valueOf({artists_expr}), String.valueOf({arts_expr}), {start_expr});")
            elif c['type'] == 'audio_add_to_playlist':
                _pl_name = self._val_to_java(c['name_node']) if c.get('name_node') else '""'
                if c.get('item_node') is not None:
                    _pl_item = self._val_to_java(c['item_node'])
                    lines.append(f"{indent}_apkpyAddTrackToPlaylist(String.valueOf({_pl_name}), String.valueOf({_pl_item}));")
                else:
                    lines.append(f"{indent}_apkpyAddToPlaylist(String.valueOf({_pl_name}));")
            elif c['type'] == 'audio_play_saved_playlist':
                _pl_name = self._val_to_java(c['name_node']) if c.get('name_node') else '""'
                lines.append(f"{indent}_apkpyPlaySavedPlaylist(String.valueOf({_pl_name}));")
            elif c['type'] == 'audio_edit_playlist':
                _pl_name = self._val_to_java(c['name_node']) if c.get('name_node') else '""'
                lines.append(f"{indent}_apkpyEditPlaylist(String.valueOf({_pl_name}));")
            elif c['type'] == 'audio_remove_from_playlist':
                _pl_name = self._val_to_java(c['name_node']) if c.get('name_node') else '""'
                _pl_item = self._val_to_java(c['item_node']) if c.get('item_node') is not None else '""'
                lines.append(f"{indent}_apkpyRemoveTrackFromPlaylist(String.valueOf({_pl_name}), String.valueOf({_pl_item}));")
            elif c['type'] == 'audio_delete_playlist':
                _pl_name = self._val_to_java(c['name_node']) if c.get('name_node') else '""'
                lines.append(f"{indent}_apkpyDeletePlaylist(String.valueOf({_pl_name}));")
            elif c['type'] == 'audio_next':
                lines.append(f"{indent}_audioServiceCmd(\"apkpy.NEXT\");")
            elif c['type'] == 'audio_prev':
                lines.append(f"{indent}_audioServiceCmd(\"apkpy.PREV\");")
            elif c['type'] == 'audio_shuffle':
                lines.append(f"{indent}_audioServiceCmd(\"apkpy.SHUFFLE\");")
            elif c['type'] == 'audio_repeat':
                lines.append(f"{indent}_audioServiceCmd(\"apkpy.REPEAT\");")
            elif c['type'] == 'files_download':
                url_expr = self._val_to_java(c['url_node']) if c.get('url_node') else '""'
                name_expr = self._val_to_java(c['name_node']) if c.get('name_node') else '""'
                cb = c.get('callback')
                if cb:
                    lines.append(f"{indent}_filesDownload(String.valueOf({url_expr}), String.valueOf({name_expr}), (success, path) -> pythonCallback_{cb}(success, path));")
                else:
                    lines.append(f"{indent}_filesDownload(String.valueOf({url_expr}), String.valueOf({name_expr}), null);")
            elif c['type'] == 'files_delete':
                name_expr = self._val_to_java(c['name_node']) if c.get('name_node') else '""'
                lines.append(f"{indent}_filesDelete(String.valueOf({name_expr}));")
            elif c['type'] == 'upload_multipart':
                self._emit_upload_cmd(lines, indent, c)
            elif c['type'] == 'upload_cancel':
                task_expr = (
                    self._val_to_java(c['task_node'])
                    if c.get('task_node') is not None else '""'
                )
                lines.append(
                    f"{indent}_uploadCancel(String.valueOf({task_expr}));"
                )
            elif c['type'] in (
                    'websocket_connect', 'websocket_send',
                    'websocket_close'):
                self._emit_websocket_cmd(lines, indent, c)
            elif c['type'] in push_feature.COMMAND_TYPES:
                push_feature.emit_command(lines, indent, c, self._val_to_java)
            elif c['type'] in maps_feature.COMMAND_TYPES:
                maps_feature.emit_command(
                    lines, indent, c, self._val_to_java, self._get_comp_from_py_var
                )
            elif c['type'] in routes_feature.COMMAND_TYPES:
                routes_feature.emit_command(lines, indent, c, self._val_to_java)
            elif c['type'] in location_background_feature.COMMAND_TYPES:
                location_background_feature.emit_command(lines, indent, c, self._val_to_java)
            elif c['type'] == 'auth_login':
                lines.append(f"{indent}_authStartLogin();")
            elif c['type'] == 'auth_logout':
                lines.append(f'{indent}ApkpyAuth.clear(getApplicationContext());')
            elif c['type'] == 'auth_user':
                cb = c.get('callback')
                if cb:
                    lines.append(f"{indent}_authFetchUser(_u -> pythonCallback_{cb}(_u));")
                else:
                    lines.append(f"{indent}_authFetchUser(_u -> {{}});")
            elif c['type'] in ('apps_list', 'apps_permissions', 'apps_extract', 'apps_hash'):
                _emit_apps_cmd(lines, indent, c, self._val_to_java)
            elif c['type'] == 'camera_capture':
                cb = c.get('callback')
                if cb:
                    lines.append(f"{indent}_cameraCapture((success, path) -> pythonCallback_{cb}(success, path));")
                else:
                    lines.append(f"{indent}_cameraCapture(null);")
            elif c['type'] in file_picker_feature.COMMAND_TYPES:
                file_picker_feature.emit_command(
                    lines, indent, c, self._val_to_java, functions_map,
                )
            elif c['type'] in biometrics_feature.COMMAND_TYPES:
                biometrics_feature.emit_command(
                    lines, indent, c, self._val_to_java, functions_map,
                )
            elif c['type'] in flashlight_feature.COMMAND_TYPES:
                flashlight_feature.emit_command(
                    lines, indent, c, self._val_to_java, functions_map,
                )
            elif c['type'] in wallpaper_feature.COMMAND_TYPES:
                wallpaper_feature.emit_command(
                    lines, indent, c, self._val_to_java, functions_map,
                )
            elif c['type'] in camera_feature.COMMAND_TYPES:
                camera_feature.emit_command(lines, indent, c, self._val_to_java, functions_map)
            elif c['type'] == 'camera_view_control':
                camera_view_feature.emit_control(lines, indent, c, self._get_jv_from_py_var, self._val_to_java)
            elif c['type'] in sensors_feature.COMMAND_TYPES:
                sensors_feature.emit_command(
                    lines, indent, c, self._val_to_java, functions_map,
                )
            elif c['type'] in bluetooth_feature.COMMAND_TYPES:
                bluetooth_feature.emit_command(
                    lines, indent, c, self._val_to_java, functions_map,
                )
            elif c['type'] in nfc_feature.COMMAND_TYPES:
                nfc_feature.emit_command(lines, indent, c, self._val_to_java, functions_map)
            elif c['type'] in contacts_feature.COMMAND_TYPES:
                contacts_feature.emit_command(lines, indent, c, self._val_to_java)
            elif c['type'] in ble_feature.COMMAND_TYPES:
                ble_feature.emit_command(
                    lines, indent, c, self._val_to_java, functions_map,
                )
            elif c['type'] in billing_feature.COMMAND_TYPES:
                billing_feature.emit_command(
                    lines, indent, c, self._val_to_java, functions_map,
                )
            elif c['type'] == 'gallery_pick':
                cb = c.get('callback')
                if cb:
                    lines.append(f"{indent}_galleryPick((success, path) -> pythonCallback_{cb}(success, path));")
                else:
                    lines.append(f"{indent}_galleryPick(null);")
            elif c['type'] == 'location_get':
                cb = c.get('callback')
                if cb:
                    lines.append(f"{indent}_getLocation((success, lat, lng, city) -> pythonCallback_{cb}(success, lat, lng, city));")
                else:
                    lines.append(f"{indent}_getLocation(null);")
            elif c['type'] == 'navigate':
                to_class = f"Screen_{c['to_screen_id']}Activity"
                lines.append(f"{indent}Intent _navIntent = new Intent({class_name}.this, {to_class}.class);")
                for k, v_node in (c.get('data') or []):
                    lines.append(f"{indent}_navIntent.putExtra(\"{_escape_java_literal(str(k))}\", String.valueOf({self._val_to_java(v_node)}));")
                lines.append(f"{indent}startActivity(_navIntent);")
                self._emit_screen_transition(c, indent)
            elif c['type'] == 'navigate_back':
                lines.append(f"{indent}{class_name}.this.finish();")
            elif c['type'] == 'request_permission':
                lines.append(f"{indent}ActivityCompat.requestPermissions({class_name}.this, new String[]{{Manifest.permission.{c['perm']}}}, PERMISSION_REQ_{c['perm']});")
            elif c['type'] == 'if_has_permission':
                lines.append(f"{indent}if (ContextCompat.checkSelfPermission({class_name}.this, Manifest.permission.{c['perm']}) == PackageManager.PERMISSION_GRANTED) {{")
                self._gen_cmds(c['true_body'], indent + "    ", declared)
                lines.append(f"{indent}}} else {{")
                self._gen_cmds(c['false_body'], indent + "    ", declared)
                lines.append(f"{indent}}}")
            elif c['type'] == 'if_var':
                lines.append(f"{indent}if {_parenthesized(_cond_to_java(ast.Name(id=c['var'], ctx=ast.Load()), self._val_to_java, _cur_bool_args[0]))} {{")
                self._gen_cmds(c['true_body'], indent + "    ", declared)
                lines.append(f"{indent}}} else {{")
                self._gen_cmds(c['false_body'], indent + "    ", declared)
                lines.append(f"{indent}}}")
            elif c['type'] == 'list_append':
                _emit_list_append(lines, indent, c, self._val_to_java, self._json_iter_vars)
            elif c['type'] == 'raise':
                _emit_raise(lines, indent, c, self._val_to_java, self._numeric_java_expr)
            elif c['type'] == 'print':
                _emit_print(lines, indent, c, self._val_to_java)
            elif c['type'] == 'try_block':
                _emit_try_block(lines, indent, c,
                                lambda b, ind: self._gen_cmds(b, ind, declared),
                                declared)
            elif c['type'] == 'for_loop':
                # A variável do loop é declarada pelo próprio for em Java.
                declared.add(c['var'])
                _emit_for_loop(lines, indent, c, self._val_to_java,
                               lambda b, ind: self._gen_cmds(b, ind, declared),
                               self._json_iter_vars, self._numeric_vars)
            elif c['type'] == 'while_loop':
                _emit_while_loop(lines, indent, c, self._val_to_java,
                                 lambda b, ind: self._gen_cmds(b, ind, declared),
                                 _cur_bool_args[0])
            elif c['type'] == 'break':
                lines.append(f"{indent}break;")
            elif c['type'] == 'continue':
                lines.append(f"{indent}continue;")
            elif c['type'] == 'return':
                if c.get('value_node') is not None:
                    lines.append(f"{indent}return {_text_value_java(c['value_node'], self._val_to_java)};")
                else:
                    lines.append(f"{indent}return ApkpyValues.NONE;" if _RETURNS_VALUE[0] else f"{indent}return;")
            elif c['type'] == 'if_compare':
                cond = _if_compare_cond(c, self._val_to_java)
                lines.append(f"{indent}if ({cond}) {{")
                self._gen_cmds(c['true_body'], indent + "    ", declared)
                lines.append(f"{indent}}} else {{")
                self._gen_cmds(c['false_body'], indent + "    ", declared)
                lines.append(f"{indent}}}")
            elif c['type'] == 'if_cond':
                cond = _cond_to_java(c['test'], self._val_to_java, _cur_bool_args[0]) or unsupported.raise_untranslated_condition(c['test'])
                lines.append(f"{indent}if ({cond}) {{")
                self._gen_cmds(c['true_body'], indent + "    ", declared)
                lines.append(f"{indent}}} else {{")
                self._gen_cmds(c['false_body'], indent + "    ", declared)
                lines.append(f"{indent}}}")
            elif c['type'] == 'storage_set':
                # Encriptação automática at-rest (AES + Keystore) via helper
                lines.append(f"{indent}_apkpyStorageSet({_storage_key_java(c, self._val_to_java)}, String.valueOf({self._val_to_java(c['val_node'])}));")
            elif c['type'] == 'scan_code':
                _sc = c.get('callback')
                lines.append('%s_apkpyScanCode(%s);' % (
                    indent,
                    ('(ok, value) -> pythonCallback_%s(ok, value)' % _sc)
                    if _sc else '(ok, value) -> { }'))
            elif c['type'] == 'app_open_store':
                _u = (self._val_to_java(c['url_node']) if c.get('url_node')
                      else 'null')
                lines.append(f"{indent}_apkpyOpenStore({_u});")
            elif c['type'] == 'crash_clear':
                lines.append(f"{indent}ApkpyCrashHandler.clear(getApplicationContext());")
            elif c['type'] == 'language_set':
                _emit_language_set(lines, indent, self._val_to_java(c['val_node']))
            elif c['type'] == 'appearance_set':
                # Guardado antes de aplicado: o setDefaultNightMode recria a
                # Activity, e o onCreate seguinte le' esta chave para saber
                # que tabela de cores pedir.
                _mode_java = self._val_to_java(c['val_node'])
                lines.append(
                    f"{indent}_apkpyStorageSet(\"__apkpy_appearance\", "
                    f"String.valueOf({_mode_java}));"
                )
                lines.append(
                    f"{indent}_apkpyApplyAppearance("
                    f"String.valueOf({_mode_java}));"
                )
            elif c['type'] == 'storage_delete':
                lines.append(f"{indent}getSharedPreferences(\"apkpy_storage\", Context.MODE_PRIVATE).edit().remove({_storage_key_java(c, self._val_to_java)}).apply();")
            elif c['type'] == 'storage_clear':
                lines.append(f"{indent}SharedPreferences prefs_clr = getSharedPreferences(\"apkpy_storage\", Context.MODE_PRIVATE);")
                lines.append(f"{indent}prefs_clr.edit().clear().apply();")
            elif c['type'] == 'https_get':
                _method = c.get('method', 'GET')
                url_val = self._val_to_java(c['url_node'])
                callback_name = c['callback'] if c['callback'] else "null"
                _timeout = _https_timeout_java(c.get('timeout_node'), self._val_to_java)
                headers_node = c.get('headers_node')
                if headers_node is not None:
                    h_var = f"_headers_{id(c) & 0xFFFF}"
                    lines.extend(self._dict_node_to_java(headers_node, h_var, indent))
                    lines.append(f"{indent}executeHttpsRequest(\"{_method}\", String.valueOf({url_val}), null, {h_var}, {_timeout}, new HttpsCallback() {{")
                else:
                    lines.append(f"{indent}executeHttpsRequest(\"{_method}\", String.valueOf({url_val}), null, null, {_timeout}, new HttpsCallback() {{")
                lines.append(f"{indent}    @Override")
                lines.append(f"{indent}    public void onResponse(boolean success, String response) {{")
                if callback_name != "null":
                    lines.append(f"{indent}        pythonCallback_{callback_name}(success, response);")
                lines.append(f"{indent}    }}")
                lines.append(f"{indent}}});")
            elif c['type'] == 'https_post':
                _method = c.get('method', 'POST')
                url_val = self._val_to_java(c['url_node'])
                _data_arg = _https_body_java(c['data_node'], self._val_to_java)
                callback_name = c['callback'] if c['callback'] else "null"
                _timeout = _https_timeout_java(c.get('timeout_node'), self._val_to_java)
                headers_node = c.get('headers_node')
                if headers_node is not None:
                    h_var = f"_headers_{id(c) & 0xFFFF}"
                    lines.extend(self._dict_node_to_java(headers_node, h_var, indent))
                    lines.append(f"{indent}executeHttpsRequest(\"{_method}\", String.valueOf({url_val}), {_data_arg}, {h_var}, {_timeout}, new HttpsCallback() {{")
                else:
                    lines.append(f"{indent}executeHttpsRequest(\"{_method}\", String.valueOf({url_val}), {_data_arg}, null, {_timeout}, new HttpsCallback() {{")
                lines.append(f"{indent}    @Override")
                lines.append(f"{indent}    public void onResponse(boolean success, String response) {{")
                if callback_name != "null":
                    lines.append(f"{indent}        pythonCallback_{callback_name}(success, response);")
                lines.append(f"{indent}    }}")
                lines.append(f"{indent}}});")
            elif c['type'] == 'storage_get_assign':
                _decl = "" if c['var'] in declared else "String "
                declared.add(c['var'])
                lines.append(f"{indent}{_decl}{c['var']} = _apkpyStorageGet({_storage_key_java(c, self._val_to_java)}, {_storage_default_java(c, self._val_to_java)});")
            elif c['type'] == 'db_execute':
                _p = _sql_params_java(c.get('params_node'), self._val_to_java)
                _args = f", {_p}" if _p else ""
                lines.append(f"{indent}_sqliteExecute(String.valueOf({self._val_to_java(c['sql_node'])}){_args});")
            elif c['type'] == 'db_begin':
                lines.append(f"{indent}_dbBegin();")
            elif c['type'] == 'db_commit':
                lines.append(f"{indent}_dbCommit();")
            elif c['type'] == 'db_rollback':
                lines.append(f"{indent}_dbRollback();")
            elif c['type'] == 'db_query_assign':
                _p = _sql_params_java(c.get('params_node'), self._val_to_java)
                _args = f", {_p}" if _p else ""
                _decl = "" if c['var'] in declared else "String "
                declared.add(c['var'])
                lines.append(f"{indent}{_decl}{c['var']} = _sqliteQuery(String.valueOf({self._val_to_java(c['sql_node'])}){_args});")
            elif c['type'] == 'global_sync':
                lines.append(f"{indent}{_global_sync_java(c['name'])}")
            elif c['type'] == 'local_string_assign':
                val_java = _assign_rhs_java(c['val_node'], self._val_to_java)
                _decl = "" if c['var'] in declared else "String "
                declared.add(c['var'])
                lines.append(f"{indent}{_decl}{c['var']} = {val_java};")
                _track_json_struct(c['var'], c['val_node'], self._json_struct_vars, self._struct_kinds, self._kind_of)
                _ne_t = self._numeric_java_expr(c['val_node'])
                if _ne_t is not None:
                    self._numeric_vars[c['var']] = _ne_t[1]
                else:
                    self._numeric_vars.pop(c['var'], None)
                _note_numberish(c['var'], c['val_node'], self._numeric_java_expr, _ne_t)
                # k = data["n"]: the item beside its text, so a list, a dict,
                # dumps() or a comparison gets 5 and not "5" (_mark_item_names).
                if getattr(c['val_node'], _ITEM_SHARED, None) == c['var'] \
                        and c['var'] in _ITEM_SHARED_JAVA[0]:
                    if _ne_t is not None:
                        _raw_now = "_apkpyNumberOf(String.valueOf(%s))" % c['var']
                    else:
                        _raw_now = _raw_item_java(c['val_node'], self._val_to_java) or "null"
                    lines.append(f"{indent}{_ITEM_SHARED_JAVA[0][c['var']]} = {_raw_now};")
                elif getattr(c['val_node'], _ITEM_ONCE, None) == c['var'] \
                        and c['var'] not in _RAW_LOOP_VARS[0] and _ne_t is None:
                    # Declared once, so a lambda may still read it.
                    _raw_now = _raw_item_java(c['val_node'], self._val_to_java)
                    if _raw_now is not None:
                        _ITEM_COUNT[0] += 1
                        _item_java = '_ir%d_%s' % (_ITEM_COUNT[0], c['var'])
                        lines.append(f"{indent}Object {_item_java} = {_raw_now};")
                        _ITEM_STACK[0].append((c['var'], _raw_loop_enter(c['var'], _item_java)))
            elif c['type'] == 'crypto_verify_assign':
                pw_java     = self._val_to_java(c['pw_node'])
                stored_java = self._val_to_java(c['stored_node'])
                _decl = "" if c['var'] in declared else "boolean "
                declared.add(c['var'])
                lines.append(f"{indent}{_decl}{c['var']} = _apkpyVerifyPassword(String.valueOf({pw_java}), String.valueOf({stored_java}));")
                # Regista como boolean para `if var:` gerar `if (var)` e não
                # `var != null && !var.isEmpty()` (que não compila p/ primitivo).
                _cur_bool_args[0].add(c['var'])
            elif c['type'] == 'video_control':
                self._emit_video_control(lines, indent, c)
            elif c['type'] == 'draw_pad_call':
                _pad = self._get_comp_from_py_var(c['py_var'])
                _pad_line = draw_pad_feature.command_java(
                    c, _pad.get('_java_var') if _pad and _pad.get('comp_type') == draw_pad_feature.COMPONENT
                    else None, self._val_to_java)
                if _pad_line:
                    lines.append(indent + _pad_line)
            elif c['type'] == 'keyboard_call':
                _kb_line = keyboard_feature.command_java(c, self._get_comp_from_py_var(c['py_var']))
                if _kb_line:
                    lines.append(indent + _kb_line)
            elif c['type'] == 'view_image':
                _describe = c.get('describe_node')
                lines.append(indent + zoom_feature.view_java(
                    class_name, self._val_to_java(c['src_node']),
                    self._val_to_java(_describe) if _describe is not None else '""'))
            elif c['type'] == 'field_error':
                _box = self._field_box_of(c['py_var'])
                if _box:
                    lines.append(indent + field_feature.error_java(_box, self._val_to_java(c['val_node'])))
            elif c['type'] == 'field_check':
                _check = field_feature.check_java(c['node'], self._field_box_of)
                if _check != 'true':
                    lines.append(indent + _check + ';')
            elif c['type'] == 'comp_set_value':
                jv = self._get_jv_from_py_var(c['py_var'])
                comp_dict = next((cc for cc in all_comps_flat if cc.get('_py_var') == c['py_var']), None)
                if jv and comp_dict:
                    ctype = comp_dict.get('comp_type', '')
                    itype = comp_dict.get('input_type', 'text') if ctype in ('inputs', 'input_field') else ''
                    val_java = self._val_to_java(c['val_node'])
                    # A ring moves to a value out of its max.
                    if ctype in choice_feature.COMPONENTS:
                        lines.append(indent + choice_feature.set_java(jv, val_java))
                    elif ctype == web_page_feature.COMPONENT:
                        lines.append(indent + web_page_feature.set_java(jv, val_java))
                    elif ctype in rich_content_feature.COMPONENT_NAMES:
                        lines.append(_rich_set_value_java(indent, ctype, jv, val_java,
                                                          c['val_node']))
                    elif ctype == 'chart':
                        lines.append(
                            f'{indent}((ApkpyChart) findViewById(R.id.{jv}))'
                            f'.setValue(Float.parseFloat(String.valueOf({val_java})));')
                    # A row is a LinearLayout holding three TextViews. Its label
                    # is the one set_value means; setText on the row itself is a
                    # cannot-find-symbol, which is what this used to emit.
                    elif ctype == 'list_row':
                        lines.append(
                            f'{indent}((android.widget.TextView)findViewById('
                            f'R.id.{jv}_title)).setText(String.valueOf({val_java}));'
                        )
                    elif itype == 'radio':
                        placeholder = comp_dict.get('placeholder', '')
                        options = [o.strip() for o in placeholder.split('|')] if placeholder else []
                        for i, opt in enumerate(options):
                            rb_id = f"{jv}_rb{i}"
                            kw = 'if' if i == 0 else 'else if'
                            lines.append(f"{indent}{kw} ({val_java}.equals(\"{opt}\")) {jv}Group.check(R.id.{rb_id});")
                    elif itype == 'switch':
                        lines.append(f"{indent}{jv}.setChecked(String.valueOf({val_java}).equals(\"true\"));")
                    elif itype == 'checkbox':
                        lines.append(f"{indent}if (String.valueOf({val_java}).equals(\"true\")) {jv}.setChecked(true);")
                        lines.append(f"{indent}else {jv}.setChecked(false);")
                    elif itype == 'select':
                        placeholder_local = comp_dict.get('placeholder', '')
                        options = [o.strip() for o in placeholder_local.split('|')] if placeholder_local else []
                        for i, opt in enumerate(options):
                            kw = 'if' if i == 0 else 'else if'
                            lines.append(f"{indent}{kw} ({val_java}.equals(\"{opt}\")) {jv}.setSelection({i});")
                    elif itype == 'range':
                        lines.append(f"{indent}try {{ {jv}.setProgress(Integer.parseInt(String.valueOf({val_java}))); }} catch (Exception _e_{jv}) {{}}")
                    elif itype in ('text', 'password', 'search', 'textarea', 'number'):
                        lines.append(f"{indent}{jv}.setText(String.valueOf({val_java}));")
                    else:
                        lines.append(f"{indent}{jv}.setText(String.valueOf({val_java}));")
                    view_state_feature.remember(lines, indent, comp_dict, jv)
                else:
                    self._pending_put(indent, c, pending_views_feature.VALUE,
                                      self._val_to_java(c['val_node']))
            elif c['type'] == 'comp_set_row_field':
                jv = self._get_jv_from_py_var(c['py_var'])
                if jv:
                    # The slot only exists if the row declared it, so the
                    # lookup is guarded rather than assumed.
                    lines.append(
                        f'{indent}{{ android.view.View _slot = findViewById('
                        f'R.id.{jv}_{c["field"]}); if (_slot != null) '
                        f'((android.widget.TextView) _slot).setText('
                        f'String.valueOf({self._val_to_java(c["val_node"])})); }}'
                    )
                    view_state_feature.remember(lines, indent, {}, jv, c['field'])

            elif c['type'] == 'comp_set_src':
                jv = self._get_jv_from_py_var(c['py_var'])
                if jv:
                    lines.append(f'{indent}_apkpySetImage(R.id.{jv}, '
                                 f'String.valueOf({self._val_to_java(c["val_node"])}));')

            elif c['type'] == 'comp_get_value_assign':
                jv = self._get_jv_from_py_var(c['py_var'])
                comp_dict = next((cc for cc in all_comps_flat if cc.get('_py_var') == c['py_var']), None)
                _decl = "" if c['var'] in declared else "String "
                declared.add(c['var'])
                # o nome passa a guardar texto (ou a lista do chips(multiple=True)):
                # nome[0], len(nome) e for ch in nome contam-no como o Python.
                self._struct_kinds[c['var']] = ('list' if comp_dict and comp_dict.get('comp_type') in choice_feature.COMPONENTS
                                                and comp_dict.get('multiple') else 'text')
                if jv and comp_dict:
                    ctype = comp_dict.get('comp_type', '')
                    itype = comp_dict.get('input_type', 'text') if ctype in ('inputs', 'input_field') else ''
                    if ctype in choice_feature.COMPONENTS:
                        lines.append(f"{indent}{_decl}{c['var']} = {choice_feature.get_java(jv)};")
                    elif itype == 'radio':
                        lines.append(f"{indent}{_decl}{c['var']} = \"\";")
                        lines.append(f"{indent}int _chk_{jv} = {jv}Group.getCheckedRadioButtonId();")
                        lines.append(f"{indent}if (_chk_{jv} != -1) {{ RadioButton _rb_{jv} = findViewById(_chk_{jv}); {c['var']} = _rb_{jv}.getText().toString(); }}")
                    elif itype == 'switch':
                        lines.append(f"{indent}{_decl}{c['var']} = {jv}.isChecked() ? \"true\" : \"false\";")
                    elif itype == 'checkbox':
                        lines.append(f"{indent}{_decl}{c['var']} = {jv}.isChecked() ? \"true\" : \"false\";")
                    elif itype == 'select':
                        lines.append(f"{indent}{_decl}{c['var']} = {jv}.getSelectedItem() != null ? {jv}.getSelectedItem().toString() : \"\";")
                    elif itype == 'range':
                        lines.append(f"{indent}{_decl}{c['var']} = String.valueOf({jv}.getProgress());")
                    elif itype in ('text', 'password', 'search', 'textarea', 'number'):
                        lines.append(f"{indent}{_decl}{c['var']} = {jv}.getText().toString();")
                    else:
                        lines.append(f"{indent}{_decl}{c['var']} = {jv}.getText().toString();")
                else:
                    # O componente pertence a outro ecrã: esta Activity também
                    # recebe o callback (nunca chamado aqui), por isso declara
                    # a variável vazia para o Java compilar.
                    lines.append(f"{indent}{_decl}{c['var']} = \"\";")
            elif c['type'] == 'comp_set_items':
                jv = self._get_jv_from_py_var(c['py_var'])
                if jv:
                    comp_dict = next(
                        (cc for cc in all_comps_flat
                         if cc.get('_py_var') == c['py_var']),
                        None,
                    )
                    if comp_dict and comp_dict.get('comp_type') == 'chart':
                        _items_node = c['items_node']
                        _items_json = chart_feature.literal_items(_items_node)
                        _items_java = (chart_feature.java_string(_items_json) if _items_json is not None
                                       else 'String.valueOf(%s)' % self._val_to_java(_items_node))
                        lines.append(f"{indent}((ApkpyChart) findViewById(R.id.{jv})).setItems({_items_java});")
                        continue
                    _is_virtual = bool(
                        comp_dict
                        and comp_dict.get('comp_type') == 'virtual_collection'
                    )
                    _rich = any(
                        cc.get('rich') for cc in all_comps_flat
                        if cc.get('_py_var') == c['py_var']
                    )
                    lines.append(f"{indent}{jv}_items.clear();")
                    if (
                        _is_virtual
                        and c.get('py_var') in self._mutated_feed_pyvars
                    ):
                        lines.append(f"{indent}{jv}Optimistic.clear();")
                        lines.append(f"{indent}{jv}OptimisticKeys.clear();")
                    self._emit_fill_items(indent, jv, c, _is_virtual, _rich)
                    if _is_virtual:
                        lines.append(f"{indent}{jv}Adapter.notifyDataSetChanged();")
                        if feeds_feature.is_paginated(comp_dict):
                            _has_more = c.get('has_more_node')
                            _has_more_java = (
                                self._val_to_java(_has_more)
                                if _has_more is not None else 'true'
                            )
                            lines.append(
                                f"{indent}_apkpyFinish{jv.title()}Load("
                                f"Boolean.parseBoolean(String.valueOf("
                                f"{_has_more_java})));"
                            )
                            lines.append(f"{indent}{jv}.scrollToPosition(0);")
                            if comp_dict.get('on_end_reached'):
                                lines.append(
                                    f"{indent}{jv}.post("
                                    f"() -> _apkpyMaybeLoad{jv.title()}Page());"
                                )
                    elif self.scroll:
                        method_name = f"update{jv[0].upper()}{jv[1:]}List"
                        lines.append(f"{indent}{method_name}();")
                    else:
                        lines.append(f"{indent}{jv}Adapter.notifyDataSetChanged();")
                else:
                    self._pending_put_items(indent, c)
            elif c['type'] == 'pager_select':
                _pager_jv = self._get_jv_from_py_var(c['py_var']) or ''
                if _pager_jv.endswith('_host'):
                    _index_node = c['index_node']
                    if isinstance(_index_node, ast.Constant) and isinstance(_index_node.value, int):
                        _index_java = str(_index_node.value)
                    else:
                        _index_java = 'Integer.parseInt(String.valueOf(%s))' % self._val_to_java(_index_node)
                    lines.append(f"{indent}((ApkpyPager) findViewById(R.id.{_pager_jv[:-5]})).select({_index_java}, true);")
            elif c['type'] == 'comp_state':
                jv = self._get_jv_from_py_var(c['py_var'])
                _node = c.get('state_node')
                if _node is None or (isinstance(_node, ast.Constant) and _node.value is None):
                    _state_java = 'null'
                else:
                    _state_java = f"String.valueOf({self._val_to_java(_node)})"
                if jv:
                    lines.append(f"{indent}_apkpySetState(R.id.{jv}, {_state_java});")
            elif c['type'] == 'comp_visibility':
                jv = self._visible_view_of(c['py_var'])
                if jv:
                    vis = 'android.view.View.VISIBLE' if c['visible'] else 'android.view.View.GONE'
                    comp_dict = next(
                        (cc for cc in all_comps_flat if cc.get('_py_var') == c['py_var']), None
                    )
                    if comp_dict and comp_dict.get('comp_type') == 'skeleton':
                        lines.append(f"{indent}{{")
                        lines.append(f"{indent}    View _skeletonView = findViewById(R.id.{jv});")
                        lines.append(f"{indent}    _skeletonView.setVisibility({vis});")
                        if c['visible']:
                            lines.append(f"{indent}    _apkpyStartSkeleton(_skeletonView);")
                        else:
                            lines.append(f"{indent}    _skeletonView.clearAnimation();")
                        lines.append(f"{indent}}}")
                    else:
                        _vis_ms = 0 if c.get('instant') else self._visibility_ms(comp_dict)
                        if _vis_ms > 0:
                            lines.append(
                                f"{indent}_apkpySetVisible(R.id.{jv}, "
                                f"{str(bool(c['visible'])).lower()}, {_vis_ms}L);")
                        else:
                            lines.append(f"{indent}findViewById(R.id.{jv}).setVisibility({vis});")
                else:
                    self._pending_put(indent, c, pending_views_feature.VISIBLE,
                                      '"1"' if c['visible'] else '"0"')

    # The item a `k = d[k]` declares (_ITEM_ONCE) is seen to the end of the
    # Java block it is declared in, and never in another method.
    def _gen_cmds(self, cmds_list, indent, declared=None):
        hidden = _item_names_hide() if declared is None else None
        mark = len(_ITEM_STACK[0])
        try:
            if declared is None:
                # One Object per _ITEM_SHARED name, for the whole method; it
                # is null until the name is given its first item.
                for name in _shared_item_names(cmds_list):
                    _ITEM_COUNT[0] += 1
                    java = '_ir%d_%s' % (_ITEM_COUNT[0], name)
                    self.lines.append(f"{indent}Object {java} = null;")
                    _ITEM_SHARED_JAVA[0][name] = java
                    _ITEM_STACK[0].append((name, _raw_loop_enter(
                        name, "(%s != null ? %s : _apkpyStored(%s))" % (java, java, name))))
            return self._gen_cmds_body(cmds_list, indent, declared)
        finally:
            _item_names_leave(mark)
            if hidden is not None:
                _item_names_show(hidden)
