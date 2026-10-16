"""Explicit Android foreground-service location tracking."""

from __future__ import annotations

import ast

from . import maps as maps_feature


COMMAND_TYPES = frozenset({"location_background_start", "location_background_stop"})


def _kw_node(transpiler, call, name):
    return transpiler._kw_node(call.keywords, name)


def _pos_or_kw(transpiler, call, position, name):
    return call.args[position] if len(call.args) > position else _kw_node(transpiler, call, name)


def is_call(call):
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "location"
        and func.attr in {"start_background_tracking", "stop_background_tracking"}
    )


def parse_call(transpiler, call):
    if not is_call(call):
        return None
    # Activity generation may normalise callback command trees later.  Keep an
    # explicit project-level marker so the service and Manifest entry cannot be
    # lost while the same parsed commands are reused across multiple screens.
    transpiler.needs_location_service = True
    for permission in (
        "ACCESS_COARSE_LOCATION", "ACCESS_FINE_LOCATION", "POST_NOTIFICATIONS",
        "FOREGROUND_SERVICE", "FOREGROUND_SERVICE_LOCATION",
    ):
        if permission not in transpiler.declared_permissions:
            transpiler.declared_permissions.append(permission)
    watch_id = _pos_or_kw(transpiler, call, 0, "watch_id") or ast.Constant(value="default")
    if call.func.attr == "stop_background_tracking":
        return {"type": "location_background_stop", "watch_id_node": watch_id}
    return {
        "type": "location_background_start",
        "watch_id_node": watch_id,
        "callback": maps_feature._callback(
            transpiler, _kw_node(transpiler, call, "on_update"), 5,
            "background_location", boolean_first=True,
        ),
        "sample_callback": maps_feature._callback(
            transpiler, _kw_node(transpiler, call, "on_sample"), 9,
            "background_location_sample", boolean_first=True,
        ),
        "status_callback": maps_feature._callback(
            transpiler, _kw_node(transpiler, call, "on_status"), 2,
            "background_location_status",
        ),
        "title_node": _kw_node(transpiler, call, "title") or ast.Constant(value="Location active"),
        "text_node": _kw_node(transpiler, call, "text") or ast.Constant(value="Tracking your trip"),
        "interval": max(1000, int(transpiler._kw(call.keywords, "interval", 5000) or 5000)),
        "min_distance": max(0.0, float(transpiler._kw(call.keywords, "min_distance", 5.0) or 0.0)),
        "high_accuracy": str(transpiler._kw(call.keywords, "accuracy", "high")).lower() == "high",
    }


def commands_use_background(functions_map, module_init_cmds=None):
    def walk(commands):
        for command in commands or []:
            if not isinstance(command, dict):
                continue
            if command.get("type") in COMMAND_TYPES:
                return True
            for key in ("true_body", "false_body", "body"):
                if walk(command.get(key, [])):
                    return True
        return False
    return walk(module_init_cmds) or any(
        walk(info.get("cmds", [])) for info in functions_map.values() if info
    )


def emit_command(lines, indent, command, val_to_java):
    watch_id = val_to_java(command.get("watch_id_node"))
    if command.get("type") == "location_background_stop":
        lines.append("%s_locationStopBackground(String.valueOf(%s));" % (indent, watch_id))
        return
    callback = command.get("callback")
    update_arg = (
        "(success, latitude, longitude, accuracy, speed) -> "
        "pythonCallback_%s(success, latitude, longitude, accuracy, speed)" % callback
        if callback else "null"
    )
    sample_callback = command.get("sample_callback")
    sample_arg = (
        "(success, latitude, longitude, accuracy, speed, bearing, timestamp, provider, isMock) -> "
        "pythonCallback_%s(success, latitude, longitude, accuracy, speed, bearing, timestamp, provider, isMock)"
        % sample_callback if sample_callback else "null"
    )
    status_callback = command.get("status_callback")
    status_arg = (
        "(status, message) -> pythonCallback_%s(status, message)" % status_callback
        if status_callback else "null"
    )
    lines.append(
        "%s_locationStartBackground(String.valueOf(%s), String.valueOf(%s), "
        "String.valueOf(%s), %dL, %sf, %s, %s, %s, %s);" % (
            indent, watch_id, val_to_java(command.get("title_node")),
            val_to_java(command.get("text_node")), int(command.get("interval", 5000)),
            float(command.get("min_distance", 5.0)),
            str(bool(command.get("high_accuracy", True))).lower(),
            update_arg, sample_arg, status_arg,
        )
    )


def activity_runtime_java(package):
    return r'''
    // -- explicit background location: Android foreground service ----------
    private interface ApkpyBackgroundLocationCallback {
        void onLocation(boolean success, String latitude, String longitude,
                        String accuracy, String speed);
    }
    private interface ApkpyBackgroundSampleCallback {
        void onSample(boolean success, String latitude, String longitude,
                      String accuracy, String speed, String bearing,
                      String timestamp, String provider, String isMock);
    }
    private interface ApkpyBackgroundStatusCallback {
        void onStatus(String status, String message);
    }
    private final java.util.Map<String, ApkpyBackgroundLocationCallback>
            _apkpyBackgroundCallbacks = new java.util.concurrent.ConcurrentHashMap<>();
    private final java.util.Map<String, ApkpyBackgroundSampleCallback>
            _apkpyBackgroundSampleCallbacks = new java.util.concurrent.ConcurrentHashMap<>();
    private final java.util.Map<String, ApkpyBackgroundStatusCallback>
            _apkpyBackgroundStatusCallbacks = new java.util.concurrent.ConcurrentHashMap<>();
    private android.content.Intent _apkpyPendingBackgroundIntent;
    private boolean _apkpyBackgroundReceiverRegistered;

    private final android.content.BroadcastReceiver _apkpyBackgroundReceiver =
            new android.content.BroadcastReceiver() {
        @Override public void onReceive(android.content.Context context, android.content.Intent intent) {
            if (intent == null || !ApkpyLocationService.ACTION_UPDATE.equals(intent.getAction())) return;
            String id = intent.getStringExtra("id");
            String status = intent.getStringExtra("status");
            String message = intent.getStringExtra("message");
            ApkpyBackgroundStatusCallback statusCallback = _apkpyBackgroundStatusCallbacks.get(id);
            if (statusCallback != null && status != null)
                statusCallback.onStatus(status, message == null ? "" : message);
            if (!intent.getBooleanExtra("has_location", false)) return;
            String latitude = intent.getStringExtra("latitude");
            String longitude = intent.getStringExtra("longitude");
            String accuracy = intent.getStringExtra("accuracy");
            String speed = intent.getStringExtra("speed");
            String bearing = intent.getStringExtra("bearing");
            String timestamp = intent.getStringExtra("timestamp");
            String provider = intent.getStringExtra("provider");
            String isMock = intent.getStringExtra("is_mock");
            ApkpyBackgroundLocationCallback callback = _apkpyBackgroundCallbacks.get(id);
            if (callback != null) callback.onLocation(true, latitude, longitude, accuracy, speed);
            ApkpyBackgroundSampleCallback sample = _apkpyBackgroundSampleCallbacks.get(id);
            if (sample != null) sample.onSample(true, latitude, longitude, accuracy, speed,
                    bearing, timestamp, provider, isMock);
        }
    };

    private final androidx.activity.result.ActivityResultLauncher<String[]>
            _apkpyBackgroundPermissionLauncher = registerForActivityResult(
            new androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions(),
            result -> {
                boolean granted = Boolean.TRUE.equals(result.get(
                        android.Manifest.permission.ACCESS_FINE_LOCATION))
                        || Boolean.TRUE.equals(result.get(
                        android.Manifest.permission.ACCESS_COARSE_LOCATION));
                if (granted && _apkpyPendingBackgroundIntent != null) {
                    androidx.core.content.ContextCompat.startForegroundService(
                            this, _apkpyPendingBackgroundIntent);
                    _apkpyPendingBackgroundIntent = null;
                } else if (!granted) {
                    for (ApkpyBackgroundStatusCallback callback
                            : _apkpyBackgroundStatusCallbacks.values()) {
                        callback.onStatus("permission_denied", "Location permission was denied");
                    }
                }
            });

    private void _apkpyRegisterBackgroundReceiver() {
        if (_apkpyBackgroundReceiverRegistered) return;
        android.content.IntentFilter filter = new android.content.IntentFilter(
                ApkpyLocationService.ACTION_UPDATE);
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            registerReceiver(_apkpyBackgroundReceiver, filter,
                    android.content.Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(_apkpyBackgroundReceiver, filter);
        }
        _apkpyBackgroundReceiverRegistered = true;
    }

    private boolean _apkpyHasBackgroundLocationPermission() {
        return androidx.core.content.ContextCompat.checkSelfPermission(
                this, android.Manifest.permission.ACCESS_FINE_LOCATION)
                == android.content.pm.PackageManager.PERMISSION_GRANTED
                || androidx.core.content.ContextCompat.checkSelfPermission(
                this, android.Manifest.permission.ACCESS_COARSE_LOCATION)
                == android.content.pm.PackageManager.PERMISSION_GRANTED;
    }

    private void _locationStartBackground(
            String id, String title, String text, long intervalMs, float minDistance,
            boolean highAccuracy, ApkpyBackgroundLocationCallback callback,
            ApkpyBackgroundSampleCallback sampleCallback,
            ApkpyBackgroundStatusCallback statusCallback) {
        _apkpyRegisterBackgroundReceiver();
        if (callback != null) _apkpyBackgroundCallbacks.put(id, callback);
        if (sampleCallback != null) _apkpyBackgroundSampleCallbacks.put(id, sampleCallback);
        if (statusCallback != null) {
            _apkpyBackgroundStatusCallbacks.put(id, statusCallback);
            statusCallback.onStatus("starting", "Starting visible background tracking");
        }
        android.content.Intent intent = new android.content.Intent(this, ApkpyLocationService.class);
        intent.setAction(ApkpyLocationService.ACTION_START);
        intent.putExtra("id", id); intent.putExtra("title", title); intent.putExtra("text", text);
        intent.putExtra("interval", Math.max(1000L, intervalMs));
        intent.putExtra("min_distance", Math.max(0f, minDistance));
        intent.putExtra("high_accuracy", highAccuracy);
        if (_apkpyHasBackgroundLocationPermission()) {
            androidx.core.content.ContextCompat.startForegroundService(this, intent);
        } else {
            _apkpyPendingBackgroundIntent = intent;
            java.util.ArrayList<String> permissions = new java.util.ArrayList<>();
            permissions.add(android.Manifest.permission.ACCESS_FINE_LOCATION);
            permissions.add(android.Manifest.permission.ACCESS_COARSE_LOCATION);
            if (android.os.Build.VERSION.SDK_INT >= 33)
                permissions.add(android.Manifest.permission.POST_NOTIFICATIONS);
            _apkpyBackgroundPermissionLauncher.launch(permissions.toArray(new String[0]));
        }
    }

    private void _locationStopBackground(String id) {
        android.content.Intent intent = new android.content.Intent(this, ApkpyLocationService.class);
        intent.setAction(ApkpyLocationService.ACTION_STOP); intent.putExtra("id", id);
        startService(intent);
        ApkpyBackgroundStatusCallback callback = _apkpyBackgroundStatusCallbacks.remove(id);
        _apkpyBackgroundCallbacks.remove(id); _apkpyBackgroundSampleCallbacks.remove(id);
        if (callback != null) callback.onStatus("stopped", "Background tracking stopped");
    }

    private void _locationBackgroundDispose() {
        if (_apkpyBackgroundReceiverRegistered) {
            try { unregisterReceiver(_apkpyBackgroundReceiver); } catch (Exception ignored) {}
            _apkpyBackgroundReceiverRegistered = false;
        }
        _apkpyBackgroundCallbacks.clear(); _apkpyBackgroundSampleCallbacks.clear();
        _apkpyBackgroundStatusCallbacks.clear();
    }
'''.replace("__PACKAGE__", package)


def generate_service_java(package):
    return r'''package __PACKAGE__;

public final class ApkpyLocationService extends android.app.Service
        implements android.location.LocationListener {
    public static final String ACTION_START = "__PACKAGE__.location.START";
    public static final String ACTION_STOP = "__PACKAGE__.location.STOP";
    public static final String ACTION_UPDATE = "__PACKAGE__.location.UPDATE";
    private static final String CHANNEL = "apkpy_location";
    private static final int NOTIFICATION_ID = 4207;

    private android.location.LocationManager manager;
    private com.google.android.gms.location.FusedLocationProviderClient fusedClient;
    private com.google.android.gms.location.LocationCallback fusedCallback;
    private String trackingId = "default";
    private String notificationTitle = "Location active";
    private String notificationText = "Tracking your trip";
    private android.location.Location previous;

    @Override public void onCreate() {
        super.onCreate();
        manager = (android.location.LocationManager)getSystemService(LOCATION_SERVICE);
        try {
            fusedClient = com.google.android.gms.location.LocationServices
                    .getFusedLocationProviderClient(this);
        } catch (Exception ignored) {}
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            android.app.NotificationChannel channel = new android.app.NotificationChannel(
                    CHANNEL, "Location tracking", android.app.NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Visible status for active trip tracking");
            ((android.app.NotificationManager)getSystemService(NOTIFICATION_SERVICE))
                    .createNotificationChannel(channel);
        }
    }

    @Override public int onStartCommand(android.content.Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            getSharedPreferences("apkpy_location", MODE_PRIVATE).edit()
                    .putBoolean("active", false).apply();
            stopTracking();
            if (android.os.Build.VERSION.SDK_INT >= 24)
                stopForeground(STOP_FOREGROUND_REMOVE);
            else stopForeground(true);
            stopSelf(); return START_NOT_STICKY;
        }
        android.content.SharedPreferences state = getSharedPreferences(
                "apkpy_location", MODE_PRIVATE);
        long interval;
        float distance;
        boolean highAccuracy;
        if (intent != null && ACTION_START.equals(intent.getAction())) {
            trackingId = intent.getStringExtra("id") == null ? "default" : intent.getStringExtra("id");
            notificationTitle = intent.getStringExtra("title") == null
                    ? "Location active" : intent.getStringExtra("title");
            notificationText = intent.getStringExtra("text") == null
                    ? "Tracking your trip" : intent.getStringExtra("text");
            interval = intent.getLongExtra("interval", 5000L);
            distance = intent.getFloatExtra("min_distance", 5f);
            highAccuracy = intent.getBooleanExtra("high_accuracy", true);
            state.edit().putBoolean("active", true)
                    .putString("id", trackingId)
                    .putString("title", notificationTitle)
                    .putString("text", notificationText)
                    .putLong("interval", interval)
                    .putFloat("distance", distance)
                    .putBoolean("high_accuracy", highAccuracy).apply();
        } else if (intent == null && state.getBoolean("active", false)) {
            trackingId = state.getString("id", "default");
            notificationTitle = state.getString("title", "Location active");
            notificationText = state.getString("text", "Tracking your trip");
            interval = state.getLong("interval", 5000L);
            distance = state.getFloat("distance", 5f);
            highAccuracy = state.getBoolean("high_accuracy", true);
        } else {
            return START_NOT_STICKY;
        }
        android.app.Notification foregroundNotification = notification();
        if (android.os.Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFICATION_ID, foregroundNotification,
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION);
        } else {
            startForeground(NOTIFICATION_ID, foregroundNotification);
        }
        startTracking(interval, distance, highAccuracy);
        sendStatus("active", "Foreground location service is active");
        return START_STICKY;
    }

    private android.app.Notification notification() {
        android.content.Intent stopIntent = new android.content.Intent(this, ApkpyLocationService.class);
        stopIntent.setAction(ACTION_STOP); stopIntent.putExtra("id", trackingId);
        android.app.PendingIntent stop = android.app.PendingIntent.getService(
                this, 73, stopIntent,
                android.app.PendingIntent.FLAG_UPDATE_CURRENT | android.app.PendingIntent.FLAG_IMMUTABLE);
        android.content.Intent openIntent = getPackageManager().getLaunchIntentForPackage(getPackageName());
        android.app.PendingIntent open = openIntent == null ? null : android.app.PendingIntent.getActivity(
                this, 74, openIntent,
                android.app.PendingIntent.FLAG_UPDATE_CURRENT | android.app.PendingIntent.FLAG_IMMUTABLE);
        androidx.core.app.NotificationCompat.Builder builder =
                new androidx.core.app.NotificationCompat.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.ic_menu_mylocation)
                .setContentTitle(notificationTitle).setContentText(notificationText)
                .setOngoing(true).setOnlyAlertOnce(true)
                .setCategory(androidx.core.app.NotificationCompat.CATEGORY_SERVICE)
                .addAction(0, "Stop", stop);
        if (open != null) builder.setContentIntent(open);
        return builder.build();
    }

    @android.annotation.SuppressLint("MissingPermission")
    private void startTracking(long interval, float distance, boolean highAccuracy) {
        stopTracking();
        if (androidx.core.content.ContextCompat.checkSelfPermission(
                this, android.Manifest.permission.ACCESS_FINE_LOCATION)
                != android.content.pm.PackageManager.PERMISSION_GRANTED
                && androidx.core.content.ContextCompat.checkSelfPermission(
                this, android.Manifest.permission.ACCESS_COARSE_LOCATION)
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            sendStatus("permission_denied", "Location permission is unavailable");
            stopSelf(); return;
        }
        if (fusedClient != null) {
            try {
                int priority = highAccuracy
                        ? com.google.android.gms.location.Priority.PRIORITY_HIGH_ACCURACY
                        : com.google.android.gms.location.Priority.PRIORITY_BALANCED_POWER_ACCURACY;
                com.google.android.gms.location.LocationRequest request =
                        new com.google.android.gms.location.LocationRequest.Builder(
                                priority, Math.max(1000L, interval))
                                .setMinUpdateIntervalMillis(Math.max(500L, interval / 2L))
                                .setMinUpdateDistanceMeters(Math.max(0f, distance))
                                .build();
                fusedCallback = new com.google.android.gms.location.LocationCallback() {
                    @Override public void onLocationResult(
                            com.google.android.gms.location.LocationResult result) {
                        if (result == null) return;
                        for (android.location.Location location : result.getLocations())
                            onLocationChanged(location);
                    }
                };
                fusedClient.requestLocationUpdates(
                        request, fusedCallback, android.os.Looper.getMainLooper());
                fusedClient.getLastLocation().addOnSuccessListener(location -> {
                    if (location != null) onLocationChanged(location);
                });
                return;
            } catch (Exception fusedError) {
                fusedCallback = null;
                sendStatus("fallback", "Fused provider unavailable; using Android location");
            }
        }
        if (manager == null) { sendStatus("unavailable", "Location service unavailable"); return; }
        String preferred = highAccuracy ? android.location.LocationManager.GPS_PROVIDER
                : android.location.LocationManager.NETWORK_PROVIDER;
        String fallback = highAccuracy ? android.location.LocationManager.NETWORK_PROVIDER
                : android.location.LocationManager.GPS_PROVIDER;
        try {
            String provider = manager.isProviderEnabled(preferred) ? preferred
                    : manager.isProviderEnabled(fallback) ? fallback : null;
            if (provider == null) { sendStatus("provider_disabled", "Enable device location"); return; }
            manager.requestLocationUpdates(provider, Math.max(1000L, interval),
                    Math.max(0f, distance), this, android.os.Looper.getMainLooper());
        } catch (Exception error) {
            sendStatus("error", error.getMessage() == null
                    ? error.getClass().getSimpleName() : error.getMessage());
        }
    }

    @Override public void onLocationChanged(android.location.Location location) {
        if (location == null) return;
        float speed = location.hasSpeed() ? location.getSpeed() : 0f;
        if (!location.hasSpeed() && previous != null) {
            long elapsed = Math.max(1L, location.getTime() - previous.getTime());
            speed = previous.distanceTo(location) / (elapsed / 1000f);
        }
        previous = new android.location.Location(location);
        android.content.Intent update = new android.content.Intent(ACTION_UPDATE);
        update.setPackage(getPackageName()); update.putExtra("id", trackingId);
        update.putExtra("status", "active"); update.putExtra("message", "Location received");
        update.putExtra("has_location", true);
        update.putExtra("latitude", format(location.getLatitude()));
        update.putExtra("longitude", format(location.getLongitude()));
        update.putExtra("accuracy", one(location.getAccuracy()));
        update.putExtra("speed", one(speed));
        update.putExtra("bearing", one(location.hasBearing() ? location.getBearing() : 0f));
        update.putExtra("timestamp", String.valueOf(location.getTime()));
        update.putExtra("provider", location.getProvider() == null ? "unknown" : location.getProvider());
        update.putExtra("is_mock", String.valueOf(
                android.os.Build.VERSION.SDK_INT >= 18 && location.isFromMockProvider()));
        sendBroadcast(update);
    }

    @Override public void onProviderDisabled(String provider) {
        sendStatus("provider_disabled", provider + " provider is disabled");
    }
    private void sendStatus(String status, String message) {
        android.content.Intent update = new android.content.Intent(ACTION_UPDATE);
        update.setPackage(getPackageName()); update.putExtra("id", trackingId);
        update.putExtra("status", status); update.putExtra("message", message);
        update.putExtra("has_location", false); sendBroadcast(update);
    }
    private static String format(double value) {
        return String.format(java.util.Locale.US, "%.6f", value);
    }
    private static String one(double value) {
        return String.format(java.util.Locale.US, "%.1f", value);
    }
    private void stopTracking() {
        try { if (manager != null) manager.removeUpdates(this); } catch (Exception ignored) {}
        try {
            if (fusedClient != null && fusedCallback != null)
                fusedClient.removeLocationUpdates(fusedCallback);
        } catch (Exception ignored) {}
        fusedCallback = null;
    }
    @Override public void onDestroy() { stopTracking(); super.onDestroy(); }
    @Override public android.os.IBinder onBind(android.content.Intent intent) { return null; }
}
'''.replace("__PACKAGE__", package)


__all__ = [
    "COMMAND_TYPES", "activity_runtime_java", "commands_use_background",
    "emit_command", "generate_service_java", "is_call", "parse_call",
]
