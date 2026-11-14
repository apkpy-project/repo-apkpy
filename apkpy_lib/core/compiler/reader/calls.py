"""A call on a line of its own: a message, the map, storage, the phone, the network, audio."""
import ast

from ...features import push as push_feature
from ...features import field as field_feature
from ...features import zoom as zoom_feature
from ...features import draw_pad as draw_pad_feature
from ...features import keyboard as keyboard_feature
from ...features import maps as maps_feature
from ...features import routes as routes_feature
from ...features import location_background as location_background_feature
from ...features import data as data_feature
from ...features import jobs as jobs_feature
from ...features import file_picker as file_picker_feature
from ...features import biometrics as biometrics_feature
from ...features import bluetooth as bluetooth_feature
from ...features import nfc as nfc_feature
from ...features import contacts as contacts_feature
from ...features import ble as ble_feature
from ...features import billing as billing_feature
from ...features import flashlight as flashlight_feature
from ...features import wallpaper as wallpaper_feature
from ...features import sensors as sensors_feature
from ...features import auth_oidc as auth_oidc_feature
from ...features import notifications as notifications_feature
from ...features import camera as camera_feature
from ... import unsupported
from ...features import scan as scan_feature
from ..state import _SCAN_FORMATS
from ..expressions import _OAUTH_PROVIDERS, _OAUTH_USERINFO
from ..statements import _print_command
from ..manifest import _permission_symbol


class CallReader:
    """A call on a line of its own: a message, the map, storage, the phone, the network, audio."""

    def _call_statement(self, cmds, stmt):
        """A call on a line of its own: what it asks the phone to do, as a command."""
        call = stmt.value
        func = call.func
        func_id = getattr(func, 'id', getattr(func, 'attr', ''))

        data_command = data_feature.parse_model_command(self, call)
        if data_command is None:
            data_command = data_feature.parse_transaction_command(self, call)
        if data_command is None:
            data_command = data_feature.parse_tx_command(self, call)
        if data_command is None:
            data_command = data_feature.parse_observer_command(self, call)
        if data_command is None:
            # job.enqueue/cancel/progress/retry/fail — same dispatch slot,
            # a feature module returning a command dict or None.
            data_command = jobs_feature.parse_command(self, call)
        if data_command is None:
            data_command = notifications_feature.parse_call(self, call)
        if data_command is None:
            # field.set_error(...), field.validate(), validate(a, b)
            data_command = field_feature.parse_call(self, call)
        if data_command is None:
            data_command = zoom_feature.parse_call(self, call)
        if data_command is None:
            # pad.clear() / pad.save(name): before the list's clear() below.
            data_command = draw_pad_feature.parse_call(self, call)
        if data_command is None:
            # hide_keyboard() / field.focus()
            data_command = keyboard_feature.parse_call(self, call)

        if data_command is not None:
            cmds.append(data_command)

        # Uma chamada com ponto que ninguém acima reconheceu — antes
        # desaparecia inteira, sem linha nenhuma no Java.
        elif not (self._message_call(cmds, call, func, func_id)
                  or self._map_call(cmds, call)
                  or self._state_call(cmds, call, func)
                  or self._device_call(cmds, call, func)
                  or self._data_and_https_call(cmds, call, func)
                  or self._socket_and_upload_call(cmds, call, func)
                  or self._audio_call(cmds, call, func)
                  or self._files_apps_auth_call(cmds, call, func)
                  or self._component_call(cmds, call, func)
                  or self._collection_call(cmds, call, func)
                  or self._screen_call(cmds, call, func, func_id)):
            unsupported.raise_unsupported(call)

    def _message_call(self, cmds, call, func, func_id):
        """print, toast, snackbar, alert, confirm, share, and asking for a permission."""
        # print() to Logcat -- unless the app has its own print.
        if func_id == 'print' and isinstance(func, ast.Name) \
                and 'print' not in getattr(self, 'own_function_names', ()):
            cmds.append(_print_command(call))

        elif func_id == 'toast':
            msg_node = call.args[0] if call.args else self._kw_node(call.keywords, 'message')
            cmds.append({'type': 'toast', 'msg_node': msg_node})

        elif func_id == 'snackbar':
            msg_node = call.args[0] if call.args else self._kw_node(call.keywords, 'message')
            action_node = self._kw_node(call.keywords, 'action')
            callback = self._register_overlay_callback(
                self._kw_node(call.keywords, 'on_action'), 'snackbar_action',
            )
            duration = self._kw(call.keywords, 'duration', 3000)
            cmds.append({
                'type': 'snackbar', 'msg_node': msg_node,
                'action_node': action_node, 'callback': callback,
                'duration': int(duration) if isinstance(duration, (int, float)) else 3000,
            })

        # alert(title, message) — diálogo simples com botão OK
        elif func_id == 'alert':
            title_node = call.args[0] if len(call.args) > 0 else self._kw_node(call.keywords, 'title')
            msg_node   = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'message')
            cmds.append({'type': 'alert', 'title_node': title_node, 'msg_node': msg_node,
                         'ok_node': self._kw_node(call.keywords, 'ok')})

        # confirm(title, message, on_result=cb) — diálogo OK/Cancelar com callback boolean
        elif func_id == 'confirm':
            title_node = call.args[0] if len(call.args) > 0 else self._kw_node(call.keywords, 'title')
            msg_node   = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'message')
            callback   = self._kw(call.keywords, 'on_result')
            cmds.append({'type': 'confirm', 'title_node': title_node, 'msg_node': msg_node, 'callback': callback,
                         'ok_node': self._kw_node(call.keywords, 'ok'),
                         'cancel_node': self._kw_node(call.keywords, 'cancel')})
            if callback:
                self.boolean_first_arg_callbacks.add(callback)

        # share(text, title="...") — abre o menu de partilha do sistema
        # (Intent.ACTION_SEND / Intent.createChooser) para enviar texto
        # para outra app (WhatsApp, Email, SMS, etc.)
        elif func_id == 'share':
            text_node  = call.args[0] if len(call.args) > 0 else self._kw_node(call.keywords, 'text')
            title_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'title')
            cmds.append({'type': 'share', 'text_node': text_node, 'title_node': title_node})

        elif func_id == 'request':
            perm = call.args[0].value if call.args and hasattr(call.args[0], 'value') else ""
            # "camera", "CAMERA" and "android.permission.CAMERA" are one
            # permission; Java wants Manifest.permission.CAMERA. The
            # first and last wrote names javac refused.
            perm = _permission_symbol(str(perm).strip())
            # Asking for a permission means the manifest has to list it,
            # and the request code is declared from that list.
            if perm and all(_permission_symbol(p) != perm
                            for p in self.declared_permissions):
                self.declared_permissions.append(perm)
            callback = self._kw(call.keywords, 'on_response')
            cmds.append({'type': 'request_permission', 'perm': perm, 'callback': callback})
            if callback and perm:
                self.permission_callbacks[perm] = callback
            if callback:
                self.boolean_first_arg_callbacks.add(callback)
        else:
            return False
        return True

    def _map_call(self, cmds, call):
        """Routes, location in the background, maps."""
        # ReactiveState mutations. Every mutation is followed by one
        # render pass for that state in the current Activity.
        if routes_feature.is_call(call):
            route_command = routes_feature.parse_call(self, call)
            if route_command:
                cmds.append(route_command)

        elif location_background_feature.is_call(call):
            background_location_command = location_background_feature.parse_call(self, call)
            if background_location_command:
                cmds.append(background_location_command)

        elif maps_feature.is_location_call(call) or \
                maps_feature.is_map_component_call(self, call):
            map_command = maps_feature.parse_call(self, call)
            if map_command:
                cmds.append(map_command)
        else:
            return False
        return True

    def _state_call(self, cmds, call, func):
        """The app's state and what it keeps: state, storage, scan, the store page, crash reports, language,
        appearance, the clipboard."""
        if isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Name) and \
                func.value.id in self.reactive_states and \
                func.attr in ('set', 'increment', 'decrement', 'toggle'):
            state_var = func.value.id
            if func.attr == 'set':
                value_node = call.args[0] if call.args else self._kw_node(call.keywords, 'value')
                if value_node is not None:
                    cmds.append({
                        'type': 'state_set',
                        'state_var': state_var,
                        'value_node': value_node,
                    })
            elif func.attr in ('increment', 'decrement'):
                amount_node = call.args[0] if call.args else self._kw_node(call.keywords, 'amount')
                if amount_node is None:
                    amount_node = ast.Constant(value=1)
                cmds.append({
                    'type': 'state_increment',
                    'state_var': state_var,
                    'amount_node': amount_node,
                    'direction': 1 if func.attr == 'increment' else -1,
                })
            else:
                cmds.append({'type': 'state_toggle', 'state_var': state_var})

        # storage.set("chave", valor)
        elif isinstance(func, ast.Attribute) and func.attr == 'set' and \
                isinstance(func.value, ast.Name) and func.value.id == 'storage':
            if len(call.args) >= 2:
                key = call.args[0].value if hasattr(call.args[0], 'value') else ''
                val_node = call.args[1]
                cmds.append({'type': 'storage_set', 'key': key, 'val_node': val_node,
                             'key_node': call.args[0]})

        # scan.code(on_result=..., formats=[...]) — leitor de
        # codigos do Google, noutro processo e sem CAMERA.
        elif (isinstance(func, ast.Attribute) and func.attr == 'code'
              and isinstance(func.value, ast.Name)
              and func.value.id == 'scan'):
            _cb = self._kw(call.keywords, 'on_result')
            if _cb:
                self.boolean_first_arg_callbacks.add(_cb)
            _fmt_node = self._kw_node(call.keywords, 'formats')
            _names = (self._literal_string_list(_fmt_node)
                      if _fmt_node is not None else [])
            _bad = scan_feature.unknown_formats(_names)
            if _bad:
                unsupported.raise_unsupported(
                    call,
                    cause=('A scanner told to read a symbology it does '
                           'not know would read every one instead, and '
                           'the wrong label off the same box is how a '
                           'wrong value gets into the right field.'),
                    suggestions=['Choose from: %s.'
                                 % ', '.join(sorted(scan_feature.FORMATS))],
                    received='formats=%r' % (_names,),
                )
            _SCAN_FORMATS[0] = scan_feature.normalise_formats(_names)
            cmds.append({'type': 'scan_code', 'callback': _cb})

        # app.open_store() — a ficha da app na loja, ou um
        # endereco proprio (uma distribuicao gerida nao esta
        # na Play).
        elif (isinstance(func, ast.Attribute)
              and func.attr == 'open_store'
              and isinstance(func.value, ast.Name)
              and func.value.id == 'app'):
            cmds.append({'type': 'app_open_store',
                         'url_node': call.args[0] if call.args else None})

        # crash.clear() — esquecer o relatorio, tipicamente
        # depois de o enviar para algum lado.
        elif (isinstance(func, ast.Attribute) and func.attr == 'clear'
              and isinstance(func.value, ast.Name)
              and func.value.id == 'crash'):
            cmds.append({'type': 'crash_clear'})

        # language.set("pt") — troca de idioma com a app a correr
        elif isinstance(func, ast.Attribute) and func.attr == 'set' and                         isinstance(func.value, ast.Name) and                         func.value.id == 'language':
            if call.args:
                cmds.append({
                    'type': 'language_set',
                    'val_node': call.args[0],
                })

        # appearance.set("dark" | "light" | "system")
        elif isinstance(func, ast.Attribute) and func.attr == 'set' and \
                isinstance(func.value, ast.Name) and \
                func.value.id == 'appearance':
            if call.args:
                cmds.append({
                    'type': 'appearance_set',
                    'val_node': call.args[0],
                })

        # storage.delete("chave")
        elif isinstance(func, ast.Attribute) and func.attr == 'delete' and \
                isinstance(func.value, ast.Name) and func.value.id == 'storage':
            if call.args:
                key = call.args[0].value if hasattr(call.args[0], 'value') else ''
                cmds.append({'type': 'storage_delete', 'key': key,
                             'key_node': call.args[0]})

        # storage.clear()
        elif isinstance(func, ast.Attribute) and func.attr == 'clear' and \
                isinstance(func.value, ast.Name) and func.value.id == 'storage':
            cmds.append({'type': 'storage_clear'})

        # clipboard.copy(text) — copia texto para a área de transferência do sistema
        elif isinstance(func, ast.Attribute) and func.attr == 'copy' and \
                isinstance(func.value, ast.Name) and func.value.id == 'clipboard':
            text_node = call.args[0] if call.args else self._kw_node(call.keywords, 'text')
            cmds.append({'type': 'clipboard_copy', 'text_node': text_node})
        else:
            return False
        return True

    def _device_call(self, cmds, call, func):
        """What the phone has: camera, pickers, biometrics, flashlight, wallpaper, sensors, Bluetooth, NFC,
        contacts, billing, the gallery, location, services."""
        # camera.capture(on_result=callback) — abre a câmara nativa e devolve
        # (sucesso, caminho_da_foto) ao callback. Requer permissão CAMERA em runtime.
        if camera_feature.is_call(call):
            cmds.append(camera_feature.parse_call(self, call))

        # gallery.pick(on_result=callback) — abre o seletor nativo de imagens
        # e devolve (sucesso, caminho_da_imagem) ao callback.
        elif file_picker_feature.is_call(call):
            cmds.append(file_picker_feature.parse_call(self, call))

        # biometrics.unlock(...) — the system fingerprint prompt.
        elif biometrics_feature.is_call(call):
            cmds.append(biometrics_feature.parse_call(self, call))

        # flashlight.on/off/toggle() — the torch on the back.
        elif flashlight_feature.is_call(call):
            cmds.append(flashlight_feature.parse_call(self, call))

        elif wallpaper_feature.is_call(call):
            cmds.append(wallpaper_feature.parse_call(self, call))

        # sensors.shake/compass/steps/light/proximity/stop()
        elif sensors_feature.is_call(call):
            cmds.append(sensors_feature.parse_call(self, call))

        # bluetooth.devices/connect/send/disconnect — classic SPP.
        elif bluetooth_feature.is_call(call):
            cmds.append(bluetooth_feature.parse_call(self, call))
        elif nfc_feature.is_call(call):
            cmds.append(nfc_feature.parse_call(self, call))
        elif contacts_feature.is_call(call):
            cmds.append(contacts_feature.parse_call(self, call))

        # ble.scan/connect/send/disconnect — Low Energy.
        elif ble_feature.is_call(call):
            cmds.append(ble_feature.parse_call(self, call))

        # billing.prices/buy/subscribe/owned/consume — Play billing.
        elif billing_feature.is_call(call):
            cmds.append(billing_feature.parse_call(self, call))

        elif isinstance(func, ast.Attribute) and func.attr == 'pick' and \
                isinstance(func.value, ast.Name) and func.value.id == 'gallery':
            callback = self._kw(call.keywords, 'on_result')
            cmds.append({'type': 'gallery_pick', 'callback': callback})
            if callback:
                self.boolean_first_arg_callbacks.add(callback)

        # location.get_current(on_result=callback) — lê a localização (GPS)
        # e devolve (sucesso, latitude, longitude) ao callback.
        # Requer permissão ACCESS_FINE_LOCATION em runtime.
        elif isinstance(func, ast.Attribute) and func.attr == 'get_current' and \
                isinstance(func.value, ast.Name) and func.value.id == 'location':
            callback = self._kw(call.keywords, 'on_result')
            cmds.append({'type': 'location_get', 'callback': callback})
            if callback:
                self.boolean_first_arg_callbacks.add(callback)
            if "ACCESS_FINE_LOCATION" not in self.declared_permissions:
                self.declared_permissions.append("ACCESS_FINE_LOCATION")
            # Geocoder (coordenadas → cidade) precisa de acesso à rede
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")

        # service.cancel(id="...") — cancela uma tarefa periódica em segundo plano
        elif isinstance(func, ast.Attribute) and func.attr == 'cancel' and \
                isinstance(func.value, ast.Name) and func.value.id == 'service':
            id_node = self._kw_node(call.keywords, 'id')
            if id_node is None and call.args:
                id_node = call.args[0]
            cmds.append({'type': 'service_cancel', 'id_node': id_node})

        # service.once(run=fn, after_minutes=N, id="...") — tarefa única atrasada
        elif isinstance(func, ast.Attribute) and func.attr == 'once' and \
                isinstance(func.value, ast.Name) and func.value.id == 'service':
            keywords = self._service_keywords(call, 'once')
            run_node = self._kw_node(keywords, 'run')
            run_name = run_node.id if isinstance(run_node, ast.Name) else None
            after_minutes = self._kw(keywords, 'after_minutes', 0)
            svc_id = self._kw(keywords, 'id', f"once_service_{len(self.onetime_services)}")
            only_on_wifi       = bool(self._kw(keywords, 'only_on_wifi', False))
            only_when_charging = bool(self._kw(keywords, 'only_when_charging', False))
            if run_name:
                self.onetime_services.append({
                    'id': svc_id,
                    'function_name': run_name,
                    'only_on_wifi': only_on_wifi,
                    'only_when_charging': only_when_charging,
                    'line': getattr(call, 'lineno', 0),
                })
                cmds.append({
                    'type': 'service_once',
                    'id': svc_id,
                    'after_minutes': after_minutes,
                    'only_on_wifi': only_on_wifi,
                    'only_when_charging': only_when_charging,
                })
        else:
            return False
        return True

    def _data_and_https_call(self, cmds, call, func):
        """The database, https, push."""
        # db.execute(sql) / db.execute(sql, [a, b]) / db.execute(sql, params=[a, b])
        if isinstance(func, ast.Attribute) and func.attr == 'execute' and \
                isinstance(func.value, ast.Name) and func.value.id == 'db':
            if call.args:
                sql_node = call.args[0]
                params_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'params')
                cmds.append({'type': 'db_execute', 'sql_node': sql_node, 'params_node': params_node})

        # db.begin() / db.commit() / db.rollback() — transações (ou tudo ou nada)
        elif isinstance(func, ast.Attribute) and func.attr in ('begin', 'commit', 'rollback') and \
                isinstance(func.value, ast.Name) and func.value.id == 'db':
            cmds.append({'type': 'db_' + func.attr})

        # https.get/delete(url, headers=..., on_response=...) — sem corpo
        elif isinstance(func, ast.Attribute) and func.attr in ('get', 'delete') and \
                isinstance(func.value, ast.Name) and func.value.id == 'https':
            url_node = call.args[0] if call.args else None
            callback = self._kw(call.keywords, 'on_response')
            headers_node = self._kw_node(call.keywords, 'headers')
            cmds.append({'type': 'https_get', 'method': func.attr.upper(), 'url_node': url_node, 'headers_node': headers_node, 'callback': callback, 'timeout_node': self._kw_node(call.keywords, 'timeout')})
            if callback:
                self.boolean_first_arg_callbacks.add(callback)
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")

        # https.post/put/patch(url, data, headers=..., on_response=...) — com corpo
        elif isinstance(func, ast.Attribute) and func.attr in ('post', 'put', 'patch') and \
                isinstance(func.value, ast.Name) and func.value.id == 'https':
            url_node = call.args[0] if call.args else None
            data_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'data')
            callback = self._kw(call.keywords, 'on_response')
            headers_node = self._kw_node(call.keywords, 'headers')
            cmds.append({'type': 'https_post', 'method': func.attr.upper(), 'url_node': url_node, 'data_node': data_node, 'headers_node': headers_node, 'callback': callback, 'timeout_node': self._kw_node(call.keywords, 'timeout')})
            if callback:
                self.boolean_first_arg_callbacks.add(callback)
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")

        # uploads.multipart(id, url, path, ...) — multipart em streaming
        # com progresso, cancelamento e callbacks na UI. Os aliases
        # file/image/audio/video partilham o mesmo runtime otimizado.
        elif push_feature.is_push_call(call):
            push_command = push_feature.parse_call(self, call)
            if push_command:
                cmds.append(push_command)
        else:
            return False
        return True

    def _socket_and_upload_call(self, cmds, call, func):
        """WebSockets and uploads."""
        if isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Name) and \
                func.value.id == 'websocket' and \
                func.attr == 'connect':
            connection_node = (
                call.args[0] if call.args
                else self._kw_node(call.keywords, 'connection_id')
            )
            url_node = (
                call.args[1] if len(call.args) > 1
                else self._kw_node(call.keywords, 'url')
            )
            headers_node = self._kw_node(call.keywords, 'headers')
            if isinstance(headers_node, ast.Name):
                headers_node = self.dict_assignments.get(
                    headers_node.id, headers_node
                )
            protocols_node = self._kw_node(call.keywords, 'protocols')
            if isinstance(protocols_node, ast.Name):
                protocols_node = self.list_assignments.get(
                    protocols_node.id, protocols_node
                )
            self._websocket_command_count += 1
            websocket_seq = self._websocket_command_count
            callbacks = {
                'open_callback': self._register_websocket_callback(
                    self._kw_node(call.keywords, 'on_open'),
                    0, f'open_{websocket_seq}',
                ),
                'message_callback': self._register_websocket_callback(
                    self._kw_node(call.keywords, 'on_message'),
                    1, f'message_{websocket_seq}',
                ),
                'close_callback': self._register_websocket_callback(
                    self._kw_node(call.keywords, 'on_close'),
                    2, f'close_{websocket_seq}',
                ),
                'error_callback': self._register_websocket_callback(
                    self._kw_node(call.keywords, 'on_error'),
                    1, f'error_{websocket_seq}',
                ),
            }
            reconnect = self._kw(
                call.keywords, 'reconnect', True
            )
            reconnect_delay = self._kw(
                call.keywords, 'reconnect_delay', 1.0
            )
            max_reconnect_delay = self._kw(
                call.keywords, 'max_reconnect_delay', 15.0
            )
            ping_interval = self._kw(
                call.keywords, 'ping_interval', 25.0
            )
            cmds.append({
                'type': 'websocket_connect',
                'seq': websocket_seq,
                'connection_node': connection_node,
                'url_node': url_node,
                'headers_node': headers_node,
                'protocols': self._literal_string_list(
                    protocols_node
                ),
                'reconnect': bool(reconnect),
                'reconnect_delay_ms': max(
                    100, int(float(reconnect_delay) * 1000)
                ),
                'max_reconnect_delay_ms': max(
                    100, int(float(max_reconnect_delay) * 1000)
                ),
                'ping_interval_seconds': max(
                    0, int(float(ping_interval))
                ),
                **callbacks,
            })
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")

        elif isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Name) and \
                func.value.id == 'websocket' and \
                func.attr == 'send':
            connection_node = (
                call.args[0] if call.args
                else self._kw_node(call.keywords, 'connection_id')
            )
            message_node = (
                call.args[1] if len(call.args) > 1
                else self._kw_node(call.keywords, 'message')
            )
            cmds.append({
                'type': 'websocket_send',
                'connection_node': connection_node,
                'message_node': message_node,
            })

        elif isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Name) and \
                func.value.id == 'websocket' and \
                func.attr == 'close':
            connection_node = (
                call.args[0] if call.args
                else self._kw_node(call.keywords, 'connection_id')
            )
            code = (
                call.args[1].value
                if len(call.args) > 1 and
                isinstance(call.args[1], ast.Constant)
                else self._kw(call.keywords, 'code', 1000)
            )
            reason_node = (
                call.args[2] if len(call.args) > 2
                else self._kw_node(call.keywords, 'reason')
            )
            cmds.append({
                'type': 'websocket_close',
                'connection_node': connection_node,
                'code': max(1000, min(4999, int(code))),
                'reason_node': reason_node,
            })

        elif isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Name) and \
                func.value.id == 'uploads' and \
                func.attr in ('multipart', 'file', 'image', 'audio', 'video'):
            task_node = (
                call.args[0] if call.args
                else self._kw_node(call.keywords, 'task_id')
            )
            url_node = (
                call.args[1] if len(call.args) > 1
                else self._kw_node(call.keywords, 'url')
            )
            path_node = (
                call.args[2] if len(call.args) > 2
                else self._kw_node(call.keywords, 'path')
            )
            field_node = self._kw_node(call.keywords, 'field')
            fields_node = self._kw_node(call.keywords, 'fields')
            headers_node = self._kw_node(call.keywords, 'headers')
            content_type_node = self._kw_node(
                call.keywords, 'content_type'
            )
            if isinstance(fields_node, ast.Name):
                fields_node = self.dict_assignments.get(
                    fields_node.id, fields_node
                )
            if isinstance(headers_node, ast.Name):
                headers_node = self.dict_assignments.get(
                    headers_node.id, headers_node
                )
            self._upload_command_count += 1
            upload_seq = self._upload_command_count
            progress_cb = self._register_upload_progress_callback(
                self._kw_node(call.keywords, 'on_progress')
            )
            result_cb = self._register_result_callback(
                self._kw_node(call.keywords, 'on_result'),
                True, f'upload_result_{upload_seq}',
            )
            cmds.append({
                'type': 'upload_multipart',
                'seq': upload_seq,
                'task_node': task_node,
                'url_node': url_node,
                'path_node': path_node,
                'field_node': field_node,
                'fields_node': fields_node,
                'headers_node': headers_node,
                'content_type_node': content_type_node,
                'progress_callback': progress_cb,
                'result_callback': result_cb,
            })
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")

        elif isinstance(func, ast.Attribute) and func.attr == 'cancel' and \
                isinstance(func.value, ast.Name) and \
                func.value.id == 'uploads':
            task_node = (
                call.args[0] if call.args
                else self._kw_node(call.keywords, 'task_id')
            )
            cmds.append({
                'type': 'upload_cancel', 'task_node': task_node,
            })
        else:
            return False
        return True

    def _audio_call(self, cmds, call, func):
        """audio: playing, playlists, the saved ones."""
        # audio.play_background(src, title=, artist=) — toca em SEGUNDO PLANO
        # (foreground media service): continua com o ecrã apagado e mostra
        # controlos na notificação/lockscreen.
        if isinstance(func, ast.Attribute) and func.attr == 'play_background' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            src_node = call.args[0] if call.args else self._kw_node(call.keywords, 'src')
            title_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'title')
            artist_node = call.args[2] if len(call.args) > 2 else self._kw_node(call.keywords, 'artist')
            art_node = call.args[3] if len(call.args) > 3 else self._kw_node(call.keywords, 'art')
            cmds.append({'type': 'audio_play_bg', 'src_node': src_node, 'title_node': title_node, 'artist_node': artist_node, 'art_node': art_node})
            for _p in ('INTERNET', 'POST_NOTIFICATIONS', 'FOREGROUND_SERVICE', 'FOREGROUND_SERVICE_MEDIA_PLAYBACK'):
                if _p not in self.declared_permissions:
                    self.declared_permissions.append(_p)

        # audio.play_playlist(sources=[...], titles=[...], artists=[...], start=0)
        # — fila de faixas em segundo plano, com ⏮⏭ na notificação/lockscreen.
        elif isinstance(func, ast.Attribute) and func.attr == 'play_playlist' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            sources_node = call.args[0] if call.args else self._kw_node(call.keywords, 'sources')
            titles_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'titles')
            artists_node = call.args[2] if len(call.args) > 2 else self._kw_node(call.keywords, 'artists')
            arts_node = self._kw_node(call.keywords, 'arts')
            start_node = self._kw_node(call.keywords, 'start')
            # Resolver listas guardadas em variáveis de módulo (SOURCES = [...])
            # para o literal — senão o Java referencia um símbolo inexistente.
            # (mesmo padrão do list_view(items=<variável>).)
            if isinstance(sources_node, ast.Name):
                sources_node = self.list_assignments.get(sources_node.id, sources_node)
            if isinstance(titles_node, ast.Name):
                titles_node = self.list_assignments.get(titles_node.id, titles_node)
            if isinstance(artists_node, ast.Name):
                artists_node = self.list_assignments.get(artists_node.id, artists_node)
            if isinstance(arts_node, ast.Name):
                arts_node = self.list_assignments.get(arts_node.id, arts_node)
            for _node, _bucket in ((sources_node, self.audio_assets),
                                   (arts_node, self.set_src_assets)):
                if isinstance(_node, (ast.List, ast.Tuple)):
                    for _elt in _node.elts:
                        if isinstance(_elt, ast.Constant) and isinstance(_elt.value, str):
                            _bucket.add(_elt.value)
            cmds.append({'type': 'audio_playlist', 'sources_node': sources_node, 'titles_node': titles_node, 'artists_node': artists_node, 'arts_node': arts_node, 'start_node': start_node})
            for _p in ('INTERNET', 'POST_NOTIFICATIONS', 'FOREGROUND_SERVICE', 'FOREGROUND_SERVICE_MEDIA_PLAYBACK'):
                if _p not in self.declared_permissions:
                    self.declared_permissions.append(_p)

        # audio.next() / audio.previous() — saltar faixa na playlist
        elif isinstance(func, ast.Attribute) and func.attr in ('next', 'previous') and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            cmds.append({'type': 'audio_next' if func.attr == 'next' else 'audio_prev'})

        # audio.shuffle() (liga/desliga) / audio.repeat() (cicla off/all/one)
        elif isinstance(func, ast.Attribute) and func.attr in ('shuffle', 'repeat') and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            cmds.append({'type': 'audio_shuffle' if func.attr == 'shuffle' else 'audio_repeat'})

        # audio.add_to_playlist(name)        — adiciona a faixa ATUAL
        # audio.add_to_playlist(name, item)  — adiciona uma faixa específica
        #   (ex.: o item de um on_click de lista). Cria a playlist se não existir.
        #   Persiste em SharedPreferences "apkpy_pl".
        elif isinstance(func, ast.Attribute) and func.attr == 'add_to_playlist' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            name_node = call.args[0] if call.args else self._kw_node(call.keywords, 'name')
            item_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'item')
            cmds.append({'type': 'audio_add_to_playlist', 'name_node': name_node, 'item_node': item_node})
            for _p in ('FOREGROUND_SERVICE', 'FOREGROUND_SERVICE_MEDIA_PLAYBACK'):
                if _p not in self.declared_permissions:
                    self.declared_permissions.append(_p)

        # audio.play_saved_playlist(name) — toca as faixas de uma playlist guardada (fila)
        elif isinstance(func, ast.Attribute) and func.attr == 'play_saved_playlist' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            name_node = call.args[0] if call.args else self._kw_node(call.keywords, 'name')
            cmds.append({'type': 'audio_play_saved_playlist', 'name_node': name_node})
            for _p in ('INTERNET', 'POST_NOTIFICATIONS', 'FOREGROUND_SERVICE', 'FOREGROUND_SERVICE_MEDIA_PLAYBACK'):
                if _p not in self.declared_permissions:
                    self.declared_permissions.append(_p)

        # audio.edit_playlist(name) — define qual a playlist em edição e enche
        #   o list_view ligado por audio.playlist_editor() com as suas faixas.
        elif isinstance(func, ast.Attribute) and func.attr == 'edit_playlist' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            name_node = call.args[0] if call.args else self._kw_node(call.keywords, 'name')
            cmds.append({'type': 'audio_edit_playlist', 'name_node': name_node})

        # audio.remove_from_playlist(name, item) — remove uma faixa (por title+
        #   subtitle) da playlist. Persiste em SharedPreferences "apkpy_pl".
        elif isinstance(func, ast.Attribute) and func.attr == 'remove_from_playlist' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            name_node = call.args[0] if call.args else self._kw_node(call.keywords, 'name')
            item_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'item')
            cmds.append({'type': 'audio_remove_from_playlist', 'name_node': name_node, 'item_node': item_node})

        # audio.delete_playlist(name) — apaga a playlist inteira.
        elif isinstance(func, ast.Attribute) and func.attr == 'delete_playlist' and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio':
            name_node = call.args[0] if call.args else self._kw_node(call.keywords, 'name')
            cmds.append({'type': 'audio_delete_playlist', 'name_node': name_node})

        # audio.play(src) / pause() / resume() / stop() / seek(seconds)
        # — leitor de áudio nativo (android.media.MediaPlayer). play() faz
        # streaming de URLs http/https e toca ficheiros locais.
        elif isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Name) and func.value.id == 'audio' and \
                func.attr in ('play', 'pause', 'resume', 'stop', 'seek'):
            if func.attr == 'play':
                src_node = call.args[0] if call.args else self._kw_node(call.keywords, 'src')
                if isinstance(src_node, ast.Constant) and isinstance(src_node.value, str):
                    self.audio_assets.add(src_node.value)
                cmds.append({'type': 'audio_play', 'src_node': src_node})
                if "INTERNET" not in self.declared_permissions:
                    self.declared_permissions.append("INTERNET")
            elif func.attr == 'seek':
                sec_node = call.args[0] if call.args else self._kw_node(call.keywords, 'seconds')
                cmds.append({'type': 'audio_seek', 'sec_node': sec_node})
            else:
                cmds.append({'type': 'audio_' + func.attr})
        else:
            return False
        return True

    def _files_apps_auth_call(self, cmds, call, func):
        """files, the installed apps, sign-in."""
        # files.download(url, name, on_result=cb) — descarrega um URL para um
        # ficheiro local (offline). cb recebe (sucesso, caminho). Async.
        if isinstance(func, ast.Attribute) and func.attr == 'download' and \
                isinstance(func.value, ast.Name) and func.value.id == 'files':
            url_node = call.args[0] if call.args else self._kw_node(call.keywords, 'url')
            name_node = call.args[1] if len(call.args) > 1 else self._kw_node(call.keywords, 'name')
            callback = self._kw(call.keywords, 'on_result')
            cmds.append({'type': 'files_download', 'url_node': url_node, 'name_node': name_node, 'callback': callback})
            if callback:
                self.boolean_first_arg_callbacks.add(callback)
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")

        # files.delete(name) — apaga um ficheiro local descarregado
        elif isinstance(func, ast.Attribute) and func.attr == 'delete' and \
                isinstance(func.value, ast.Name) and func.value.id == 'files':
            name_node = call.args[0] if call.args else self._kw_node(call.keywords, 'name')
            cmds.append({'type': 'files_delete', 'name_node': name_node})

        # apps.* — inspeção de apps instaladas (PackageManager). Base de
        # "App Inspector"/APK Extractor/scanner de segurança.
        #   apps.list(on_result=cb)          → cb(json) : [{name,package,version,system,apk,perms}]
        #   apps.permissions(pkg, on_result) → cb(json) : ["android.permission.X", ...]
        #   apps.extract(pkg, on_result)     → cb(success, path) : copia o APK p/ Download/
        #   apps.hash(pkg, on_result)        → cb(success, sha256hex) : impressão digital do APK
        elif isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Name) and func.value.id == 'apps' and \
                func.attr in ('list', 'permissions', 'extract', 'hash'):
            # Resolve o callback (função nomeada OU lambda), com a aridade
            # certa: JSON-único (list/permissions) ou (success, resultado).
            two_arg = func.attr in ('extract', 'hash')
            cb_node = self._kw_node(call.keywords, 'on_result')
            cb_name = self._register_result_callback(cb_node, two_arg, func.attr)
            if func.attr == 'list':
                cmds.append({'type': 'apps_list', 'callback': cb_name})
            elif func.attr == 'permissions':
                pkg_node = call.args[0] if call.args else self._kw_node(call.keywords, 'package')
                cmds.append({'type': 'apps_permissions', 'pkg_node': pkg_node, 'callback': cb_name})
            else:
                pkg_node = call.args[0] if call.args else self._kw_node(call.keywords, 'package')
                cmds.append({'type': 'apps_' + func.attr, 'pkg_node': pkg_node, 'callback': cb_name})
            # QUERY_ALL_PACKAGES: ver TODAS as apps no Android 11+ (senão só
            # as que declaram <queries> ou interagem com a nossa).
            if "QUERY_ALL_PACKAGES" not in self.declared_permissions:
                self.declared_permissions.append("QUERY_ALL_PACKAGES")

        # auth.login(provider=, client_id=, scopes=[...], then=ecra, redirect=)
        # — login OAuth2 (authorization-code + PKCE). Abre o browser no ecrã de
        # consentimento; o redirect volta à ApkpyAuthActivity (deep-link), que
        # troca o code por token e navega para `then`. Config GLOBAL (self.auth).
        elif isinstance(func, ast.Attribute) and func.attr == 'login' and \
                isinstance(func.value, ast.Name) and func.value.id == 'auth':
            # Resolve um kwarg p/ o seu VALOR (constante OU variável de módulo
            # CONST = "..."), porque _kw devolveria só o nome da variável.
            def _auth_str(name, default=''):
                node = self._kw_node(call.keywords, name)
                if isinstance(node, ast.Constant):
                    return node.value
                if isinstance(node, ast.Name) and node.id in self.string_constants:
                    return self.string_constants[node.id]
                return default
            def _auth_arg(index):
                # auth.login("microsoft", "client-id"): the first two
                # by position too, as the Previewer takes them.
                if len(call.args) <= index:
                    return ''
                node = call.args[index]
                if isinstance(node, ast.Constant):
                    return str(node.value)
                if isinstance(node, ast.Name) and node.id in self.string_constants:
                    return self.string_constants[node.id]
                return ''
            provider = (_auth_str('provider', '') or _auth_arg(0) or '').lower()
            issuer = _auth_str('issuer', '')
            if provider == 'microsoft':
                # Entra ID: the tenant picks who may sign in -- common,
                # organizations, consumers, or the company's own.
                auth_url, token_url = auth_oidc_feature.microsoft_endpoints(
                    _auth_str('tenant', 'common'))
                def_scopes = auth_oidc_feature.MICROSOFT_SCOPES
            elif issuer:
                # Okta, Auth0, Keycloak...: the endpoints come from the
                # issuer's discovery document, read when the sign-in starts.
                auth_url, token_url, def_scopes = '', '', auth_oidc_feature.OIDC_SCOPES
            else:
                auth_url, token_url, def_scopes = _OAUTH_PROVIDERS.get(provider, ('', '', ''))
            auth_url = _auth_str('auth_url', auth_url)
            token_url = _auth_str('token_url', token_url)
            client_id = _auth_str('client_id', '') or _auth_arg(1)
            redirect = _auth_str('redirect', 'apkpy://auth')
            # scopes: lista de literais OU string única
            scopes_node = self._kw_node(call.keywords, 'scopes')
            if isinstance(scopes_node, ast.List):
                scopes = ' '.join(str(e.value) for e in scopes_node.elts if isinstance(e, ast.Constant))
            elif isinstance(scopes_node, ast.Constant):
                scopes = str(scopes_node.value)
            else:
                scopes = def_scopes
            then_node = self._kw_node(call.keywords, 'then')
            then_sid = self.screens.get(then_node.id) if isinstance(then_node, ast.Name) else None
            # scheme/host do redirect (apkpy://auth → apkpy / auth) p/ o intent-filter
            _scheme, _host = 'apkpy', 'auth'
            if '://' in redirect:
                _scheme, _rest = redirect.split('://', 1)
                _host = _rest.split('/', 1)[0].split('?', 1)[0] or 'auth'
            _ui = _OAUTH_USERINFO.get(provider, {})
            if provider == 'microsoft':
                # Graph's picture needs the token to load: no picture.
                _ui = {'url': auth_oidc_feature.MICROSOFT_USERINFO,
                       'name': 'name', 'email': 'email', 'picture': ''}
            elif issuer:
                _ui = {'url': '', 'name': 'name', 'email': 'email', 'picture': 'picture'}
            self.auth = {
                'provider': provider, 'auth_url': auth_url, 'token_url': token_url,
                'client_id': client_id, 'redirect': redirect, 'scopes': scopes,
                'issuer': issuer,
                'then_sid': then_sid, 'scheme': _scheme, 'host': _host,
                'userinfo_url': _auth_str('userinfo_url', _ui.get('url', '')),
                'ui_name': _ui.get('name', 'name'),
                'ui_email': _ui.get('email', 'email'),
                'ui_picture': _ui.get('picture', 'picture'),
            }
            cmds.append({'type': 'auth_login'})
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")

        # auth.logout() — apaga o token guardado (volta ao estado deslogado)
        elif isinstance(func, ast.Attribute) and func.attr == 'logout' and \
                isinstance(func.value, ast.Name) and func.value.id == 'auth':
            cmds.append({'type': 'auth_logout'})

        # auth.user(on_result=lambda profile: ...) — busca o perfil do
        # utilizador logado (GET ao userinfo com o Bearer token) e chama o
        # callback com um JSON normalizado {name, email, picture}. Async.
        elif isinstance(func, ast.Attribute) and func.attr == 'user' and \
                isinstance(func.value, ast.Name) and func.value.id == 'auth':
            cb_node = self._kw_node(call.keywords, 'on_result')
            cb_name = None
            if isinstance(cb_node, ast.Lambda):
                param = cb_node.args.args[0].arg if cb_node.args.args else 'user'
                cb_name = 'auth_user_cb'
                body_stmt = ast.Expr(value=cb_node.body)
                ast.fix_missing_locations(body_stmt)
                cb_cmds = self._parse_statements([body_stmt])
                self.functions[cb_name] = {'args': [param], 'cmds': cb_cmds, 'string_args': {param}}
                self.json_item_callbacks.add(cb_name)
            elif isinstance(cb_node, ast.Name):
                cb_name = cb_node.id
                self.json_item_callbacks.add(cb_name)
            cmds.append({'type': 'auth_user', 'callback': cb_name})
            if "INTERNET" not in self.declared_permissions:
                self.declared_permissions.append("INTERNET")
        else:
            return False
        return True
