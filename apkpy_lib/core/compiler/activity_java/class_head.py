"""The top of the Java file: imports, the class line, its fields, and the methods every screen has."""
from ...features import push as push_feature
from ...features import sheet as sheet_feature
from ...features import gestures as gestures_feature
from ...features import maps as maps_feature
from ...features import routes as routes_feature
from ...features import location_background as location_background_feature
from ...features import feeds as feeds_feature
from ...features import file_picker as file_picker_feature
from ...features import biometrics as biometrics_feature
from ...features import bluetooth as bluetooth_feature
from ...features import native as native_feature
from ...features import nfc as nfc_feature
from ...features import ble as ble_feature
from ...features import billing as billing_feature
from ...features import wallpaper as wallpaper_feature
from ...features import sensors as sensors_feature
from ...features import row_adapter as row_adapter_feature
from ....theme import LIGHT_SURFACE_LUMINANCE as _theme_light_surface
from ....theme import component_style
from ..state import _NUMERIC_CONST_TEXT
from ..style import _get_style_bg, _get_style_border_color, _get_style_fg, _resolve_color
from ..expressions import _java_string_field, _module_struct_fields
from ..prescan import _singleton_fields
from ..manifest import _permission_symbol


class ClassHead:
    """The top of the Java file: imports, the class line, its fields, and the methods every screen has."""

    def _collect_imports(self):
        """The import lines, for what the screen uses."""
        background_services = self.background_services
        self.imports = [
            f"import {self.package}.R;",
            "import android.os.Bundle;",
            "import android.view.View;",
            "import android.widget.LinearLayout;",
            "import androidx.appcompat.app.AppCompatActivity;",
            "import android.Manifest;",
            "import android.content.pm.PackageManager;",
            "import androidx.core.app.ActivityCompat;",
            "import androidx.core.content.ContextCompat;",
            "import androidx.annotation.NonNull;",
        ]
        # imports= de cada bloco native: o Java do autor usa nomes curtos.
        self.imports.extend(native_feature.imports_java())
        if self.has_button:    self.imports.append("import android.widget.Button;")
        if self.has_edittext:  self.imports.append("import android.widget.EditText;")
        if self.has_textview:  self.imports.append("import android.widget.TextView;")
        if self.has_checkbox:  self.imports.append("import android.widget.CheckBox;")
        if self.has_seekbar:   self.imports.append("import android.widget.SeekBar;")
        if self.has_radio:
            self.imports += ["import android.widget.RadioGroup;", "import android.widget.RadioButton;"]
        if self.has_spinner:
            self.imports += ["import android.widget.Spinner;", "import android.widget.ArrayAdapter;"]
        if self.has_skeleton:
            self.imports += ["import android.view.animation.AlphaAnimation;", "import android.view.animation.Animation;"]
        if self.has_list:
            if self.scroll:
                self.imports += ["import android.widget.LinearLayout;"]
            else:
                self.imports += ["import android.widget.ListView;", "import android.widget.ArrayAdapter;"]
        if self.has_virtual_collection:
            self.imports += [
                "import androidx.recyclerview.widget.RecyclerView;",
                "import androidx.recyclerview.widget.LinearLayoutManager;",
                "import androidx.recyclerview.widget.GridLayoutManager;",
            ]
            if self.has_feed_mutations:
                self.imports.append("import androidx.recyclerview.widget.DiffUtil;")
        if self.has_video:
            self.imports += [
                "import androidx.media3.common.MediaItem;",
                "import androidx.media3.common.Player;",
                "import androidx.media3.common.PlaybackException;",
                "import androidx.media3.exoplayer.ExoPlayer;",
                "import androidx.media3.ui.PlayerView;",
            ]
        if self.has_switch:    self.imports.append("import androidx.appcompat.widget.SwitchCompat;")
        if self.has_nav or self.bottom_nav_info or self.drawer_info or self.has_nav_cmd: self.imports.append("import android.content.Intent;")
        if self.bottom_nav_info: self.imports.append("import com.google.android.material.bottomnavigation.BottomNavigationView;")
        if self.app_bar_info: self.imports.append("import com.google.android.material.appbar.MaterialToolbar;")
        if self.has_snackbar: self.imports.append("import com.google.android.material.snackbar.Snackbar;")
        if self.has_bottom_sheet: self.imports.append("import com.google.android.material.bottomsheet.BottomSheetDialog;")
        if self.has_modal: self.imports.append("import com.google.android.material.dialog.MaterialAlertDialogBuilder;")
        if self.has_popup_menu: self.imports.append("import android.widget.PopupMenu;")
        if any(c.get('tooltip') for c in self.all_comps_flat):
            self.imports.append("import androidx.appcompat.widget.TooltipCompat;")
        if self.has_toast or self.functions_map: self.imports.append("import android.widget.Toast;")
        self.imports.append("import android.content.SharedPreferences;")
        self.imports.append("import android.content.Context;")
        self.onetime_services = self.onetime_services or {}
        has_any_services = bool(background_services) or bool(self.onetime_services)
        all_constrained_services = list(background_services or []) + list(self.onetime_services.values())
        needs_constraints  = any(svc.get('only_on_wifi') or svc.get('only_when_charging') for svc in all_constrained_services)
        needs_network_type = any(svc.get('only_on_wifi') for svc in all_constrained_services)

        if has_any_services and (self.screen_id == self.start_screen_id or self.has_service_cancel or self.has_service_once):
            self.imports.append("import androidx.work.WorkManager;")
            if needs_constraints:
                self.imports.append("import androidx.work.Constraints;")
            if needs_network_type:
                self.imports.append("import androidx.work.NetworkType;")
            if background_services and self.screen_id == self.start_screen_id:
                self.imports.append("import androidx.work.PeriodicWorkRequest;")
                self.imports.append("import androidx.work.ExistingPeriodicWorkPolicy;")
            if self.has_service_once:
                self.imports.append("import androidx.work.OneTimeWorkRequest;")
                self.imports.append("import androidx.work.ExistingWorkPolicy;")

        if self.has_alert or self.has_confirm:
            self.imports.append("import androidx.appcompat.app.AlertDialog;")
        if (self.has_camera_capture or self.has_gallery_pick or self.has_file_pick
                or self.has_bluetooth or self.has_ble):
            self.imports.append("import androidx.activity.result.ActivityResultLauncher;")
            self.imports.append("import androidx.activity.result.contract.ActivityResultContracts;")
        if self.has_camera_capture:
            self.imports.append("import android.net.Uri;")
            self.imports.append("import androidx.core.content.FileProvider;")

        # Verificar se algum componente tem animação para importar classes
        has_animation = any(self.styles.get(c.get('id'), {}).get('animation-name') for c in self.all_comps_flat if c.get('id'))
        if has_animation:
            self.imports.append("import android.view.animation.Animation;")
            self.imports.append("import android.view.animation.AnimationUtils;")

    def _write_fields(self):
        """package, imports, the class line and its fields."""
        lines = self.lines
        string_constants = self.string_constants
        all_comps_flat = self.all_comps_flat
        lines.append(f"package {self.package};")
        lines.append("")
        lines.extend(sorted(set(self.imports)))
        lines.append("")
        lines.append(f"public class {self.class_name} extends AppCompatActivity {{")
        lines.append("")
        if self.has_remote_image:
            lines.append("    private static final java.util.concurrent.ExecutorService _apkpyImageExecutor =")
            lines.append("            java.util.concurrent.Executors.newFixedThreadPool(3);")
            lines.append("    private final java.util.concurrent.ConcurrentHashMap<Integer, String> _apkpyImageRequests =")
            lines.append("            new java.util.concurrent.ConcurrentHashMap<>();")
            if self.has_image_cache:
                lines.append("    private static final android.util.LruCache<String, android.graphics.Bitmap> _apkpyImageCache =")
                lines.append("            new android.util.LruCache<>(24);")
            lines.append("")
        for i, perm in enumerate(self.declared_permissions):
            symbol = _permission_symbol(perm)
            lines.append(f"    private static final int PERMISSION_REQ_{symbol} = {100 + i};")
        # Emitir constantes de string a nível de módulo como campos Java
        if string_constants:
            for const_name, const_val in string_constants.items():
                lines.append(_java_string_field(const_name, const_val))
        # Um numero escrito no modulo (VAT = 23) e um campo como os outros: viaja
        # como String e a aritmetica le-o de la.
        for _num_name, _num_val in _NUMERIC_CONST_TEXT[0].items():
            if _num_name in (string_constants or {}):
                continue
            lines.append(f'    private static final String {_num_name} = "{_num_val}";')
        # Uma lista, um tuplo ou um dict escrito no modulo e' um campo tambem,
        # com o seu texto JSON: sem ele, len(ITEMS) ou PRICES["tea"] numa funcao
        # nomeavam um simbolo que nenhuma classe declarava.
        lines.extend(_module_struct_fields(string_constants))
        lines.extend(_singleton_fields())
        if self.declared_permissions or string_constants:
            lines.append("")

        # Callback functions are currently emitted in every Activity because a
        # callback can be shared by controls on more than one screen.  Declare all
        # observer handles as nullable fields too, while only constructing/resuming
        # the observers owned by this screen below.  Cross-screen commands then
        # remain harmless no-ops instead of producing uncompilable Java.
        for _observer in self.all_data_observers:
            lines.append(
                f"    private ApkpyQuerySubscription {_observer['var']};"
            )
        if self.all_data_observers:
            lines.append("")

        if self.bottom_nav_info:
            lines.append("    private boolean _navReady = false;")
            lines.append("")

        if self.has_overlays:
            lines.append("    private android.app.Dialog _apkpyActiveOverlay;")
            if self.has_popup_menu:
                lines.append("    private PopupMenu _apkpyActiveMenu;")
            lines.append("")
        lines.extend(sheet_feature.field_lines(self._screen_sheets))

        if self._np_active:
            lines.append("    // Barra \"now playing\": sondagem da posição + seek por arrasto.")
            lines.append("    private boolean _npSeeking = false;")
            lines.append("    private final android.os.Handler _npHandler = new android.os.Handler(android.os.Looper.getMainLooper());")
            lines.append("    private Runnable _npTick;")
            lines.append("    private android.animation.ObjectAnimator _npAnim;")
            lines.append("    private String _npLastArt = \"\";")
            lines.append("    private int _npLastDur = 0;")
            lines.append("")

        if self._ac_active:
            lines.append("    // Botões de estado (audio.controls): poll que reflete o estado do leitor.")
            lines.append("    private final android.os.Handler _acHandler = new android.os.Handler(android.os.Looper.getMainLooper());")
            lines.append("    private Runnable _acTick;")
            lines.append("")

        if self._mp_active:
            lines.append("    // Mini-player fixo: poll que mostra a faixa atual + play/pause.")
            lines.append("    private final android.os.Handler _mpHandler = new android.os.Handler(android.os.Looper.getMainLooper());")
            lines.append("    private Runnable _mpTick;")
            lines.append("    private String _mpLastArt = \"\";")
            lines.append("")

        if self._like_active:
            lines.append("    // Botão de like/guardar (audio.like_button): poll que reflete se a faixa atual está guardada.")
            lines.append("    private final android.os.Handler _likeHandler = new android.os.Handler(android.os.Looper.getMainLooper());")
            lines.append("    private Runnable _likeTick;")
            lines.append("")

        # Campos de instância para list_view (ArrayList + Adapter precisam ser acessíveis nos callbacks)
        # Pesquisa em tempo real (inputs com on_change): py_var dos list_views alvo,
        # que guardam uma cópia integral dos itens ({jv}_src) p/ filtrar a cada tecla.
        self._search_inputs = [c for c in all_comps_flat
                               if c['comp_type'] in ('inputs', 'input_field') and c.get('search')]
        self._search_target_pyvars = {c['search']['target'] for c in self._search_inputs}

        self._list_comps = [c for c in all_comps_flat if c['comp_type'] == 'list_view']
        if self._list_comps:
            for _lc in self._list_comps:
                _ljv = _lc['_java_var']
                lines.append(f"    private java.util.ArrayList<String> {_ljv}_items;")
                if _lc.get('_py_var') in self._search_target_pyvars:
                    lines.append(f"    private java.util.ArrayList<String> {_ljv}_src;")
                if not self.scroll:
                    lines.append(f"    private android.widget.ArrayAdapter<String> {_ljv}Adapter;")
            lines.append("")

        self._virtual_comps = [
            c for c in all_comps_flat if c['comp_type'] == 'virtual_collection'
        ]
        if self._virtual_comps:
            for _vc in self._virtual_comps:
                _vjv = _vc['_java_var']
                lines.append(f"    private java.util.ArrayList<String> {_vjv}_items;")
                if _vc.get('_py_var') in self._search_target_pyvars:
                    lines.append(f"    private java.util.ArrayList<String> {_vjv}_src;")
                lines.append(f"    private {'ApkpyRowAdapter' if _vc.get('row') else 'ApkpyVirtualAdapter'} {_vjv}Adapter;")
                if (
                    _vc.get('_py_var') in self._recycler_field_pyvars
                    and not feeds_feature.is_paginated(_vc)
                ):
                    lines.append(f"    private RecyclerView {_vjv};")
                feeds_feature.emit_fields(lines, _vc)
                if _vc.get('_py_var') in self._mutated_feed_pyvars:
                    feeds_feature.emit_mutation_fields(lines, _vc)
            lines.append("")

        self._video_comps = [
            c for c in all_comps_flat if c['comp_type'] == 'video'
        ]
        for _camera_comp in all_comps_flat:
            if _camera_comp['comp_type'] == 'camera_view':
                lines.append(f"    private ApkpyCameraView {_camera_comp['_java_var']};")
        if self._video_comps:
            for _video in self._video_comps:
                _vv = _video['_java_var']
                lines.append(f"    private PlayerView {_vv};")
                lines.append(f"    private ExoPlayer {_vv}Player;")
                lines.append(
                    f"    private final android.os.Handler {_vv}Handler = "
                    "new android.os.Handler(android.os.Looper.getMainLooper());"
                )
                lines.append(f"    private Runnable {_vv}ProgressTick;")
                lines.append(f"    private boolean {_vv}ResumeAfterPause = false;")
                lines.append(f"    private boolean {_vv}ReadySent = false;")
                lines.append(f"    private boolean {_vv}Prepared = false;")
            lines.append("")

        _map_comps = [c for c in all_comps_flat if c['comp_type'] == 'map']
        if _map_comps:
            for _map in _map_comps:
                lines.append(f"    private ApkpyMapView {_map['_java_var']};")
            lines.append("")

    def _write_launchers(self):
        """What has to be a field because Android wants it registered before the Activity starts: the launchers of
        the camera and of the pickers, the WebSocket, the upload callbacks."""
        lines = self.lines
        package = self.package
        # ── Câmara / Galeria — ActivityResultLaunchers (têm de ser registados como
        # campos de instância, antes de a Activity chegar a STARTED) ───────────────
        self.has_wallpaper = wallpaper_feature.commands_use_wallpaper(
            self.functions_map, self.module_init_cmds)
        self._wallpaper_callbacks = wallpaper_feature.callbacks_used(
            self.functions_map, self.module_init_cmds)
        if self.has_wallpaper:
            lines.append("    private void _apkpyWallpaperSet(String source, String target, String tag, ApkpyWallpaper.Result result) {")
            lines.append("        ApkpyWallpaper.preview(this, source, target, tag, result);")
            lines.append("    }")
        if self.has_camera_capture or self.has_gallery_pick or self.has_files or self.has_apps:
            lines.append("    private interface PhotoResultCallback { void onResult(boolean success, String path); }")
            lines.append("")
        if self.has_file_pick:
            lines.append(file_picker_feature.callback_interface_java())
            lines.append("")
        if self.has_biometrics:
            lines.append(biometrics_feature.callback_interface_java())
            lines.append("")
        if self.has_bluetooth:
            lines.append(bluetooth_feature.callback_interface_java(package))
            lines.append("")
        if self.has_nfc:
            lines.append(nfc_feature.activity_runtime_java(package))
        if self.has_ble:
            lines.append(ble_feature.callback_interface_java(package))
            lines.append("")
        if self.has_billing:
            lines.append(billing_feature.callback_interface_java(package))
            lines.append("")
        if self.has_push:
            lines.extend(push_feature.activity_runtime_java().splitlines())
        if self.has_continuous_location:
            lines.extend(maps_feature.activity_runtime_java().splitlines())
        if self.has_sensors:
            lines.extend(sensors_feature.activity_runtime_java(
                self._sensors_watched).splitlines())
            if 'steps' in self._sensors_watched:
                lines.extend(sensors_feature.step_permission_java().splitlines())
        if self.has_routes:
            lines.extend(routes_feature.activity_runtime_java().splitlines())
        if self.has_background_location:
            lines.extend(location_background_feature.activity_runtime_java(package).splitlines())
        if self.has_websocket:
            lines.extend("""
    // ── websocket.* : mensagens bidirecionais, fila e reconexão ────────────
    private void _websocketUi(final Runnable callback) {
        if (callback == null || isFinishing() || isDestroyed()) return;
        runOnUiThread(callback);
    }

    private void _websocketConnect(
            final String id,
            final String url,
            final java.util.Map<String, String> headers,
            final java.util.List<String> protocols,
            final boolean reconnect,
            final long reconnectDelayMs,
            final long maxReconnectDelayMs,
            final long pingSeconds,
            final WebSocketOpenCallback onOpen,
            final WebSocketMessageCallback onMessage,
            final WebSocketCloseCallback onClose,
            final WebSocketErrorCallback onError) {
        _websocketClose(id, 1000, "replaced");
        java.util.Map<String, String> safeHeaders = headers == null
                ? new java.util.HashMap<>()
                : new java.util.HashMap<>(headers);
        java.util.List<String> safeProtocols = protocols == null
                ? new java.util.ArrayList<>()
                : new java.util.ArrayList<>(protocols);
        ApkpyWebSocketRecord record = new ApkpyWebSocketRecord(
                id, url, safeHeaders, safeProtocols, reconnect,
                Math.max(100L, reconnectDelayMs),
                Math.max(Math.max(100L, reconnectDelayMs), maxReconnectDelayMs),
                Math.max(0L, pingSeconds),
                onOpen, onMessage, onClose, onError);
        _apkpyWebSockets.put(id, record);
        _websocketOpen(record);
    }

    private void _websocketOpen(final ApkpyWebSocketRecord record) {
        if (record.intentional || _apkpyWebSockets.get(record.id) != record) {
            return;
        }
        final int generation;
        synchronized (record) {
            record.reconnectScheduled = false;
            generation = ++record.generation;
            if (record.client == null) {
                okhttp3.OkHttpClient.Builder builder =
                        new okhttp3.OkHttpClient.Builder()
                                .retryOnConnectionFailure(true);
                if (record.pingSeconds > 0L) {
                    builder.pingInterval(
                            record.pingSeconds,
                            java.util.concurrent.TimeUnit.SECONDS);
                }
                record.client = builder.build();
            }
        }
        okhttp3.Request.Builder request = new okhttp3.Request.Builder()
                .url(record.url);
        for (java.util.Map.Entry<String, String> header
                : record.headers.entrySet()) {
            request.header(header.getKey(), header.getValue());
        }
        if (!record.protocols.isEmpty()) {
            request.header(
                    "Sec-WebSocket-Protocol",
                    android.text.TextUtils.join(", ", record.protocols));
        }
        record.socket = record.client.newWebSocket(
                request.build(),
                new okhttp3.WebSocketListener() {
                    private boolean isCurrent() {
                        return !record.intentional
                                && record.generation == generation
                                && _apkpyWebSockets.get(record.id) == record;
                    }

                    @Override
                    public void onOpen(
                            okhttp3.WebSocket webSocket,
                            okhttp3.Response response) {
                        if (!isCurrent()) {
                            webSocket.close(1000, "stale");
                            return;
                        }
                        record.socket = webSocket;
                        record.connected = true;
                        record.attempt = 0;
                        synchronized (record.pending) {
                            while (!record.pending.isEmpty()) {
                                if (!webSocket.send(record.pending.removeFirst())) {
                                    break;
                                }
                            }
                        }
                        if (record.onOpen != null) {
                            _websocketUi(() -> record.onOpen.onOpen());
                        }
                    }

                    @Override
                    public void onMessage(
                            okhttp3.WebSocket webSocket, String message) {
                        if (isCurrent() && record.onMessage != null) {
                            _websocketUi(
                                    () -> record.onMessage.onMessage(message));
                        }
                    }

                    @Override
                    public void onClosing(
                            okhttp3.WebSocket webSocket,
                            int code,
                            String reason) {
                        webSocket.close(code, reason);
                    }

                    @Override
                    public void onClosed(
                            okhttp3.WebSocket webSocket,
                            int code,
                            String reason) {
                        if (!isCurrent()) return;
                        record.connected = false;
                        if (record.onClose != null) {
                            _websocketUi(() -> record.onClose.onClose(
                                    String.valueOf(code), reason));
                        }
                        _websocketScheduleReconnect(record);
                    }

                    @Override
                    public void onFailure(
                            okhttp3.WebSocket webSocket,
                            Throwable error,
                            okhttp3.Response response) {
                        if (!isCurrent()) return;
                        record.connected = false;
                        String message = error.getMessage() == null
                                ? error.getClass().getSimpleName()
                                : error.getMessage();
                        if (record.onError != null) {
                            _websocketUi(
                                    () -> record.onError.onError(message));
                        }
                        if (record.onClose != null) {
                            _websocketUi(() -> record.onClose.onClose(
                                    "1006", message));
                        }
                        _websocketScheduleReconnect(record);
                    }
                });
    }

    private void _websocketScheduleReconnect(
            final ApkpyWebSocketRecord record) {
        if (!record.reconnect || record.intentional
                || _apkpyWebSockets.get(record.id) != record) {
            return;
        }
        final long delay;
        synchronized (record) {
            if (record.reconnectScheduled) return;
            int exponent = Math.min(record.attempt++, 8);
            long scaled = record.baseDelayMs * (1L << exponent);
            long bounded = Math.min(record.maxDelayMs, scaled);
            long jitterLimit = Math.max(
                    1L, Math.min(500L, bounded / 5L + 1L));
            long jitter = java.util.concurrent.ThreadLocalRandom.current()
                    .nextLong(jitterLimit);
            delay = bounded + jitter;
            record.reconnectScheduled = true;
            record.reconnectRunnable = () -> {
                synchronized (record) {
                    record.reconnectScheduled = false;
                }
                _websocketOpen(record);
            };
        }
        _apkpyWebSocketHandler.postDelayed(record.reconnectRunnable, delay);
    }

    private boolean _websocketSend(
            final String id, final String message) {
        ApkpyWebSocketRecord record = _apkpyWebSockets.get(id);
        if (record == null || record.intentional) return false;
        okhttp3.WebSocket socket = record.socket;
        if (record.connected && socket != null && socket.send(message)) {
            return true;
        }
        synchronized (record.pending) {
            while (record.pending.size() >= APKPY_WEBSOCKET_MAX_PENDING) {
                record.pending.removeFirst();
            }
            record.pending.addLast(message);
        }
        return true;
    }

    private boolean _websocketClose(
            final String id, final int code, final String reason) {
        ApkpyWebSocketRecord record = _apkpyWebSockets.remove(id);
        if (record == null) return false;
        record.intentional = true;
        record.connected = false;
        Runnable pendingReconnect = record.reconnectRunnable;
        if (pendingReconnect != null) {
            _apkpyWebSocketHandler.removeCallbacks(pendingReconnect);
        }
        okhttp3.WebSocket socket = record.socket;
        if (socket != null) {
            socket.close(
                    Math.max(1000, Math.min(4999, code)),
                    reason == null ? "closed" : reason);
        }
        if (record.onClose != null) {
            String safeReason = reason == null ? "closed" : reason;
            _websocketUi(() -> record.onClose.onClose(
                    String.valueOf(code), safeReason));
        }
        _websocketShutdownClient(record.client);
        return true;
    }

    private void _websocketShutdownClient(
            okhttp3.OkHttpClient client) {
        if (client == null) return;
        client.dispatcher().cancelAll();
        client.dispatcher().executorService().shutdown();
        client.connectionPool().evictAll();
    }

    private void _websocketCloseAll() {
        for (String id : new java.util.ArrayList<>(
                _apkpyWebSockets.keySet())) {
            _websocketClose(id, 1000, "activity destroyed");
        }
        _apkpyWebSockets.clear();
    }
""".splitlines())

        if self.has_uploads:
            lines.append("    private interface UploadProgressCallback { void onProgress(int percent, long sent, long total); }")
            lines.append("    private interface UploadResultCallback { void onResult(boolean success, String response); }")
            lines.append("    private final java.util.concurrent.ExecutorService _apkpyUploadExecutor = java.util.concurrent.Executors.newFixedThreadPool(2);")
            lines.append("    private final java.util.concurrent.ConcurrentHashMap<String, java.util.concurrent.atomic.AtomicBoolean> _apkpyUploadCancels = new java.util.concurrent.ConcurrentHashMap<>();")
            lines.append("    private final java.util.concurrent.ConcurrentHashMap<String, java.net.HttpURLConnection> _apkpyUploadConnections = new java.util.concurrent.ConcurrentHashMap<>();")
            lines.append("")
        if self.has_websocket:
            lines.append("    private interface WebSocketOpenCallback { void onOpen(); }")
            lines.append("    private interface WebSocketMessageCallback { void onMessage(String message); }")
            lines.append("    private interface WebSocketCloseCallback { void onClose(String code, String reason); }")
            lines.append("    private interface WebSocketErrorCallback { void onError(String message); }")
            lines.append("    private final android.os.Handler _apkpyWebSocketHandler = new android.os.Handler(android.os.Looper.getMainLooper());")
            lines.append("    private final java.util.concurrent.ConcurrentHashMap<String, ApkpyWebSocketRecord> _apkpyWebSockets = new java.util.concurrent.ConcurrentHashMap<>();")
            lines.append("    private static final int APKPY_WEBSOCKET_MAX_PENDING = 64;")
            lines.append("    private static class ApkpyWebSocketRecord {")
            lines.append("        final String id, url;")
            lines.append("        final java.util.Map<String, String> headers;")
            lines.append("        final java.util.List<String> protocols;")
            lines.append("        final boolean reconnect;")
            lines.append("        final long baseDelayMs, maxDelayMs, pingSeconds;")
            lines.append("        final WebSocketOpenCallback onOpen;")
            lines.append("        final WebSocketMessageCallback onMessage;")
            lines.append("        final WebSocketCloseCallback onClose;")
            lines.append("        final WebSocketErrorCallback onError;")
            lines.append("        final java.util.ArrayDeque<String> pending = new java.util.ArrayDeque<>();")
            lines.append("        volatile okhttp3.OkHttpClient client;")
            lines.append("        volatile okhttp3.WebSocket socket;")
            lines.append("        volatile boolean intentional = false, connected = false, reconnectScheduled = false;")
            lines.append("        volatile int attempt = 0, generation = 0;")
            lines.append("        volatile Runnable reconnectRunnable;")
            lines.append("        ApkpyWebSocketRecord(String id, String url, java.util.Map<String, String> headers, java.util.List<String> protocols, boolean reconnect, long baseDelayMs, long maxDelayMs, long pingSeconds, WebSocketOpenCallback onOpen, WebSocketMessageCallback onMessage, WebSocketCloseCallback onClose, WebSocketErrorCallback onError) {")
            lines.append("            this.id = id; this.url = url; this.headers = headers; this.protocols = protocols;")
            lines.append("            this.reconnect = reconnect; this.baseDelayMs = baseDelayMs; this.maxDelayMs = maxDelayMs; this.pingSeconds = pingSeconds;")
            lines.append("            this.onOpen = onOpen; this.onMessage = onMessage; this.onClose = onClose; this.onError = onError;")
            lines.append("        }")
            lines.append("    }")
            lines.append("")
        if self.has_camera_capture:
            lines.append("    private Uri _cameraPhotoUri;")
            lines.append("    private PhotoResultCallback _pendingCameraCallback;")
            lines.append("    private final ActivityResultLauncher<Uri> _cameraLauncher = registerForActivityResult(")
            lines.append("            new ActivityResultContracts.TakePicture(),")
            lines.append("            success -> {")
            lines.append("                PhotoResultCallback cb = _pendingCameraCallback;")
            lines.append("                _pendingCameraCallback = null;")
            lines.append("                if (cb != null) cb.onResult(success, (success && _cameraPhotoUri != null) ? _cameraPhotoUri.toString() : \"\");")
            lines.append("            });")
            lines.append("")
        if self.has_file_pick:
            lines.extend(file_picker_feature.launcher_java().splitlines())
            lines.append("")
        if self.has_gallery_pick:
            lines.append("    private PhotoResultCallback _pendingGalleryCallback;")
            lines.append("    private final ActivityResultLauncher<String> _galleryLauncher = registerForActivityResult(")
            lines.append("            new ActivityResultContracts.GetContent(),")
            lines.append("            uri -> {")
            lines.append("                PhotoResultCallback cb = _pendingGalleryCallback;")
            lines.append("                _pendingGalleryCallback = null;")
            lines.append("                if (cb != null) cb.onResult(uri != null, uri != null ? uri.toString() : \"\");")
            lines.append("            });")
            lines.append("")

    def _write_shared_methods(self):
        """Methods written before onCreate: the lists' updaters, the visibility animations, the skeleton,
        text and rows that arrive a little at a time."""
        lines = self.lines
        # ── Localização (GPS) — interface de callback (success, latitude, longitude) ──
        if self.has_location:
            lines.append("    private interface LocationResultCallback { void onResult(boolean success, String lat, String lng, String city); }")
            lines.append("")

        # Gerar métodos updateXxxList() para list_view em scroll screens
        if self.scroll and self._list_comps:
            for _lc in self._list_comps:
                _ljv = _lc['_java_var']
                _lc_id = _lc.get('id') or _ljv
                _lc_style = component_style(self.styles, 'list', _lc_id)
                _fg  = _resolve_color(_get_style_fg(_lc_style) or '#212121')
                _bg  = _resolve_color(_get_style_bg(_lc_style)) if _get_style_bg(_lc_style) else '#ffffff'
                _div = _resolve_color(_get_style_border_color(_lc_style) or '#E2E8F0')
                _sub = _resolve_color(
                    self.styles.get('__theme__', {}).get('text_secondary', _fg)
                )
                if _div == '#d9d9d9':
                    _div = '#E2E8F0'
                _on_click = _lc.get('on_click')
                _is_rich = bool(_lc.get('rich'))
                method_name = f"update{_ljv[0].upper()}{_ljv[1:]}List"
                lines.append(f"    private void {method_name}() {{")
                lines.append(f"        LinearLayout container = findViewById(R.id.{_ljv}_container);")
                lines.append(f"        container.removeAllViews();")
                lines.append(f"        float den = getResources().getDisplayMetrics().density;")
                lines.append(f'        int textColor = android.graphics.Color.parseColor("{_fg}");')
                lines.append(f'        int subtitleColor = android.graphics.Color.parseColor("{_sub}");')
                lines.append(f'        int bgColor = android.graphics.Color.parseColor("{_bg}");')
                lines.append(f'        int dividerColor = android.graphics.Color.parseColor("{_div}");')
                lines.append(f"        for (int i = 0; i < {_ljv}_items.size(); i++) {{")
                lines.append(f"            final String item = {_ljv}_items.get(i);")
                if _is_rich:
                    lines.append(f'            String title = item, subtitle = "";')
                    lines.append(f"            try {{")
                    lines.append(f"                org.json.JSONObject rowJson = new org.json.JSONObject(item);")
                    lines.append(f'                title = rowJson.optString("title", "");')
                    lines.append(f'                subtitle = rowJson.optString("subtitle", "");')
                    lines.append(f"            }} catch (Exception ignored) {{ }}")
                    lines.append(f"            LinearLayout row = new LinearLayout(this);")
                    lines.append(f"            row.setOrientation(LinearLayout.VERTICAL);")
                    lines.append(f"            row.setBackgroundColor(bgColor);")
                    lines.append(f"            int padH = (int)(16 * den), padV = (int)(11 * den);")
                    lines.append(f"            row.setPadding(padH, padV, padH, padV);")
                    lines.append(f"            android.widget.TextView titleView = new android.widget.TextView(this);")
                    lines.append(f"            titleView.setText(title);")
                    lines.append(f"            titleView.setTextColor(textColor);")
                    lines.append(f"            titleView.setTextSize(15);")
                    lines.append(f"            titleView.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);")
                    lines.append(f"            row.addView(titleView);")
                    lines.append(f"            if (!subtitle.isEmpty()) {{")
                    lines.append(f"                android.widget.TextView subtitleView = new android.widget.TextView(this);")
                    lines.append(f"                subtitleView.setText(subtitle);")
                    lines.append(f"                subtitleView.setTextColor(subtitleColor);")
                    lines.append(f"                subtitleView.setTextSize(13);")
                    lines.append(f"                subtitleView.setPadding(0, (int)(4 * den), 0, 0);")
                    lines.append(f"                row.addView(subtitleView);")
                    lines.append(f"            }}")
                    if _on_click:
                        lines.append(f"            row.setOnClickListener(v -> pythonCallback_{_on_click}(item));")
                    lines.append(f"            container.addView(row);")
                else:
                    lines.append(f"            android.widget.TextView tv = new android.widget.TextView(this);")
                    lines.append(f"            tv.setText(_apkpyRowText(item));")
                    lines.append(f"            tv.setTextColor(textColor);")
                    lines.append(f"            tv.setBackgroundColor(bgColor);")
                    lines.append(f"            int pad = (int)(16 * den);")
                    lines.append(f"            tv.setPadding(pad, pad, pad, pad);")
                    lines.append(f"            tv.setTextSize(14);")
                    if _on_click:
                        lines.append(f"            tv.setOnClickListener(v -> pythonCallback_{_on_click}(item));")
                    lines.append(f"            container.addView(tv);")
                lines.append(f"            if (i < {_ljv}_items.size() - 1) {{")
                lines.append(f"                android.view.View divider = new android.view.View(this);")
                lines.append(f"                divider.setLayoutParams(new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, (int)(1 * den)));")
                lines.append(f"                divider.setBackgroundColor(dividerColor);")
                lines.append(f"                container.addView(divider);")
                lines.append(f"            }}")
                lines.append(f"        }}")
                lines.append(f"    }}")
                lines.append("")

        if self._has_visibility_motion:
            lines.append("    private void _apkpySetVisible(int viewId, boolean show, long ms) {")
            lines.append("        final View target = findViewById(viewId);")
            lines.append("        if (target == null) return;")
            lines.append("        if (ms <= 0L || _apkpyMotionScale() <= 0f) {")
            lines.append("            target.setAlpha(1f);")
            lines.append("            target.setVisibility(show ? View.VISIBLE : View.GONE);")
            lines.append("            return;")
            lines.append("        }")
            lines.append("        target.animate().cancel();")
            lines.append("        android.view.animation.Interpolator curve =")
            lines.append("                new android.view.animation.PathInterpolator(0.4f, 0f, 0.2f, 1f);")
            lines.append("        if (show) {")
            lines.append("            if (target.getVisibility() == View.VISIBLE && target.getAlpha() == 1f) return;")
            lines.append("            target.setAlpha(0f);")
            lines.append("            target.setVisibility(View.VISIBLE);")
            lines.append("            target.animate().alpha(1f).setDuration(ms).setInterpolator(curve).start();")
            lines.append("        } else {")
            lines.append("            if (target.getVisibility() != View.VISIBLE) return;")
            lines.append("            target.animate().alpha(0f).setDuration(ms).setInterpolator(curve)")
            lines.append("                  .withEndAction(new Runnable() {")
            lines.append("                      @Override public void run() {")
            lines.append("                          target.setVisibility(View.GONE);")
            lines.append("                          target.setAlpha(1f);")
            lines.append("                      }")
            lines.append("                  }).start();")
            lines.append("        }")
            lines.append("    }")
            lines.append("")
            # Someone who turned animations off in Accessibility meant it.
            lines.append("    private float _apkpyMotionScale() {")
            lines.append("        try {")
            lines.append("            return android.provider.Settings.Global.getFloat(")
            lines.append("                    getContentResolver(),")
            lines.append("                    android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f);")
            lines.append("        } catch (Throwable ignored) {")
            lines.append("            return 1f;")
            lines.append("        }")
            lines.append("    }")
            lines.append("")

        if not self.app_bar_info:
            # The screen root fits the system windows, so its colour is what the
            # clock sits on. Read at run time: a token or night mode changes it.
            # The threshold is theme.LIGHT_SURFACE_LUMINANCE.
            lines.append("    private void _apkpySystemIconsFollowBackground() {")
            lines.append("        android.view.ViewGroup _content = findViewById(android.R.id.content);")
            lines.append("        View _root = _content == null ? null : _content.getChildAt(0);")
            lines.append("        if (_root == null || !(_root.getBackground() instanceof android.graphics.drawable.ColorDrawable)) return;")
            lines.append("        int _c = ((android.graphics.drawable.ColorDrawable) _root.getBackground()).getColor();")
            lines.append("        if (android.graphics.Color.alpha(_c) < 255) return;")
            lines.append("        boolean _light = (0.299 * android.graphics.Color.red(_c) + 0.587 * android.graphics.Color.green(_c)")
            lines.append(f"                + 0.114 * android.graphics.Color.blue(_c)) / 255.0 > {_theme_light_surface};")
            lines.append("        androidx.core.view.WindowInsetsControllerCompat _bars =")
            lines.append("                new androidx.core.view.WindowInsetsControllerCompat(getWindow(), getWindow().getDecorView());")
            lines.append("        _bars.setAppearanceLightStatusBars(_light);")
            if not self.bottom_nav_info:
                lines.append("        _bars.setAppearanceLightNavigationBars(_light);")
            lines.append("    }")
            lines.append("")
        else:
            # The top bar runs under the status bar, so the clock sits on the
            # bar's colour; the navigation bar still sits on the screen's.
            # Without this a light app's dark icons were on #18181B.
            lines.append("    private void _apkpySystemIconsFollowBackground() {")
            lines.append("        androidx.core.view.WindowInsetsControllerCompat _bars =")
            lines.append("                new androidx.core.view.WindowInsetsControllerCompat(getWindow(), getWindow().getDecorView());")
            lines.append("        Boolean _top = _apkpyLightBehind(findViewById(R.id.apkpy_toolbar));")
            lines.append("        if (_top != null) _bars.setAppearanceLightStatusBars(_top);")
            if not self.bottom_nav_info:
                lines.append("        android.view.ViewGroup _content = findViewById(android.R.id.content);")
                lines.append("        Boolean _bottom = _apkpyLightBehind(_content == null ? null : _content.getChildAt(0));")
                lines.append("        if (_bottom != null) _bars.setAppearanceLightNavigationBars(_bottom);")
            lines.append("    }")
            lines.append("")
            lines.append("    private Boolean _apkpyLightBehind(View _v) {")
            lines.append("        if (_v == null || !(_v.getBackground() instanceof android.graphics.drawable.ColorDrawable)) return null;")
            lines.append("        int _c = ((android.graphics.drawable.ColorDrawable) _v.getBackground()).getColor();")
            lines.append("        if (android.graphics.Color.alpha(_c) < 255) return null;")
            lines.append("        return (0.299 * android.graphics.Color.red(_c) + 0.587 * android.graphics.Color.green(_c)")
            lines.append(f"                + 0.114 * android.graphics.Color.blue(_c)) / 255.0 > {_theme_light_surface};")
            lines.append("    }")
            lines.append("")

        if self.has_skeleton:
            lines.append("    private void _apkpyStartSkeleton(View target) {")
            lines.append("        if (target == null || target.getAnimation() != null) return;")
            lines.append("        AlphaAnimation pulse = new AlphaAnimation(0.48f, 1.0f);")
            lines.append("        pulse.setDuration(780L);")
            lines.append("        pulse.setRepeatMode(Animation.REVERSE);")
            lines.append("        pulse.setRepeatCount(Animation.INFINITE);")
            lines.append("        target.startAnimation(pulse);")
            lines.append("    }")
            lines.append("")

        if self.has_virtual_collection:
            self._emit_virtual_collection_adapter()
            if any(c.get('row') for c in self.all_comps_flat
                   if c['comp_type'] == 'virtual_collection'):
                row_adapter_feature.emit(lines)
            if self.has_feed_mutations or self._scroll_lookup_pyvars:
                feeds_feature.emit_lookup_helpers(lines)
            if self.has_feed_mutations:
                feeds_feature.emit_mutation_helpers(lines)
            if self.has_feed_scroll:
                feeds_feature.emit_scroll_helper(lines)
            for _vc in self._virtual_comps:
                feeds_feature.emit_helpers(lines, _vc)
                gestures_feature.emit_methods(lines, _vc)

        # Text arriving a few characters at a time. Emitted only for apps that ask
        # for it, and driven by a Handler on the main looper -- the same clock the
        # Previewer's `after` runs on.
        # Both helpers live on the Activity, so they are gated on this screen
        # actually having the widget they touch -- the commands come from the
        # whole module, and a screen with no collection has no adapter class.
        if self.has_textview and self._cmds_contain_any('comp_stream'):
            lines += [
                "",
                "    private void _apkpyStreamText(final android.widget.TextView view,",
                "            final String full, final int chunk, final int stepMs) {",
                "        if (view == null) return;",
                "        if (chunk <= 0 || stepMs <= 0) { view.setText(full); return; }",
                "        view.setText(\"\");",
                "        final android.os.Handler _h = new android.os.Handler(android.os.Looper.getMainLooper());",
                "        final int[] _seen = {0};",
                "        _h.postDelayed(new Runnable() {",
                "            @Override public void run() {",
                "                _seen[0] = Math.min(full.length(), _seen[0] + chunk);",
                "                view.setText(full.substring(0, _seen[0]));",
                "                if (_seen[0] < full.length()) _h.postDelayed(this, stepMs);",
                "            }",
                "        }, stepMs);",
                "    }",
            ]
        if self.has_virtual_collection and self._cmds_contain_any('comp_stream_item'):
            lines += [
                "",
                "    private void _apkpyStreamPatch(java.util.ArrayList<String> items,",
                "            ApkpyVirtualAdapter adapter, int index, String field, String text) {",
                "        try {",
                "            org.json.JSONObject _patch = new org.json.JSONObject();",
                "            _patch.put(field, text);",
                "            items.set(index, _apkpyVcMergeJson(items.get(index), _patch.toString()));",
                "            if (adapter != null) adapter.notifyItemChanged(index);",
                "        } catch (Exception ignored) { }",
                "    }",
                "",
                "    private void _apkpyStreamItem(final java.util.ArrayList<String> items,",
                "            final ApkpyVirtualAdapter adapter, final String key,",
                "            final String itemId, final String field, final String full,",
                "            final int chunk, final int stepMs) {",
                "        final int _index = _apkpyVcFind(items, key, itemId);",
                "        if (_index < 0) return;",
                "        if (chunk <= 0 || stepMs <= 0) {",
                "            _apkpyStreamPatch(items, adapter, _index, field, full);",
                "            return;",
                "        }",
                "        _apkpyStreamPatch(items, adapter, _index, field, \"\");",
                "        final android.os.Handler _h = new android.os.Handler(android.os.Looper.getMainLooper());",
                "        final int[] _seen = {0};",
                "        _h.postDelayed(new Runnable() {",
                "            @Override public void run() {",
                "                _seen[0] = Math.min(full.length(), _seen[0] + chunk);",
                "                _apkpyStreamPatch(items, adapter, _index, field,",
                "                        full.substring(0, _seen[0]));",
                "                if (_seen[0] < full.length()) _h.postDelayed(this, stepMs);",
                "            }",
                "        }, stepMs);",
                "    }",
            ]
