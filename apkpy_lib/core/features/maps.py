"""Compiler support for key-free maps and continuous Android location."""

from __future__ import annotations

import ast
import json


COMMAND_TYPES = frozenset({
    "location_watch", "location_stop", "map_set_center", "map_set_follow_user", "map_set_location",
    "map_set_markers", "map_set_route", "map_set_zoom", "map_clear_map_cache",
})


def _kw_node(transpiler, call, name):
    return transpiler._kw_node(call.keywords, name)


def _pos_or_kw(transpiler, call, position, name):
    return call.args[position] if len(call.args) > position else _kw_node(transpiler, call, name)


def _callback(transpiler, node, arity, tag, boolean_first=False):
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.Lambda):
        defaults = {
            2: ["latitude", "longitude"],
            5: ["success", "latitude", "longitude", "accuracy", "speed"],
            9: [
                "success", "latitude", "longitude", "accuracy", "speed",
                "bearing", "timestamp", "provider", "is_mock",
            ],
        }
        params = [arg.arg for arg in node.args.args]
        params = (params + defaults.get(arity, []))[:arity]
        while len(params) < arity:
            params.append("arg%d" % (len(params) + 1))
        name = transpiler._unique_function_name("maps_%s_cb" % tag)
        body = ast.Expr(value=node.body)
        ast.fix_missing_locations(body)
        transpiler.functions[name] = {
            "args": params,
            "cmds": transpiler._parse_statements([body]),
            "string_args": set(params[1:] if boolean_first else params),
        }
    else:
        return None
    if boolean_first:
        transpiler.boolean_first_arg_callbacks.add(name)
    return name


def _literal(node, fallback):
    if node is None:
        return fallback
    try:
        return ast.literal_eval(node)
    except (TypeError, ValueError, SyntaxError):
        return fallback


def _literal_from_transpiler(transpiler, node, fallback):
    if isinstance(node, ast.Name):
        node = (
            transpiler.list_assignments.get(node.id)
            or transpiler.dict_assignments.get(node.id)
            or node
        )
    return _literal(node, fallback)


def _normalise_points(values, markers=False):
    result = []
    for item in values or []:
        if isinstance(item, dict):
            lat = item.get("lat", item.get("latitude"))
            lng = item.get("lng", item.get("longitude", item.get("lon")))
            point = dict(item)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            lat, lng = item[:2]
            point = {}
        else:
            continue
        try:
            point["lat"] = max(-90.0, min(90.0, float(lat)))
            point["lng"] = max(-180.0, min(180.0, float(lng)))
        except (TypeError, ValueError):
            continue
        if markers:
            point["title"] = str(point.get("title", ""))
            point["color"] = str(point.get("color", "#8B5CF6"))
        result.append(point)
    return result


def parse_component(transpiler, call, comp, py_var):
    """Fill a compiler component created for ``map_view``."""
    marker_values = _normalise_points(
        _literal_from_transpiler(
            transpiler, _kw_node(transpiler, call, "markers"), []
        ), markers=True
    )
    route_values = _normalise_points(
        _literal_from_transpiler(
            transpiler, _kw_node(transpiler, call, "route"), []
        ), markers=False
    )
    latitude = _literal(_pos_or_kw(transpiler, call, 0, "latitude"), None)
    longitude = _literal(_pos_or_kw(transpiler, call, 1, "longitude"), None)
    zoom = _literal(_pos_or_kw(transpiler, call, 2, "zoom"), None)
    points = marker_values + route_values
    if latitude is None or longitude is None:
        if points:
            latitude = sum(point["lat"] for point in points) / len(points)
            longitude = sum(point["lng"] for point in points) / len(points)
            if zoom is None:
                span = max(
                    max(point["lat"] for point in points) - min(point["lat"] for point in points),
                    max(point["lng"] for point in points) - min(point["lng"] for point in points),
                    0.00001,
                )
                import math
                zoom = max(2, min(17, int(math.log(180.0 / span, 2)) - 1))
        else:
            latitude, longitude = 0.0, 0.0
    if zoom is None:
        zoom = 2 if not points else 14
    try:
        latitude = max(-90.0, min(90.0, float(latitude)))
        longitude = max(-180.0, min(180.0, float(longitude)))
        zoom = max(2, min(19, int(zoom)))
    except (TypeError, ValueError):
        latitude, longitude, zoom = 0.0, 0.0, 2
    comp.update({
        "id": transpiler._kw(call.keywords, "id"),
        "latitude": latitude,
        "longitude": longitude,
        "zoom": zoom,
        "markers": marker_values,
        "route": route_values,
        "show_user": bool(transpiler._kw(call.keywords, "show_user", True)),
        "follow_user": bool(transpiler._kw(call.keywords, "follow_user", False)),
        "tile_url": str(transpiler._kw(
            call.keywords, "tile_url", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        )),
        "attribution": str(transpiler._kw(
            call.keywords, "attribution", "© OpenStreetMap contributors"
        )),
        "tile_user_agent": str(transpiler._kw(
            call.keywords, "tile_user_agent",
            "ApkPy Android/1.2 (+https://repo-apkpy.pages.dev/)",
        )),
        "cache_days": max(0, int(transpiler._kw(call.keywords, "cache_days", 7) or 0)),
        "disk_cache": bool(transpiler._kw(call.keywords, "disk_cache", True)),
        "on_tap": _callback(
            transpiler, _kw_node(transpiler, call, "on_tap"), 2,
            "%s_tap" % (py_var or "map"),
        ),
    })
    for permission in ("INTERNET",):
        if permission not in transpiler.declared_permissions:
            transpiler.declared_permissions.append(permission)
    return comp


def is_location_call(call):
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "location"
        and func.attr in {"watch", "stop"}
    )


def is_map_component_call(transpiler, call):
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and transpiler.component_vars.get(func.value.id, {}).get("comp_type") == "map"
        and func.attr in {
            "set_center", "set_follow_user", "set_location", "set_markers", "set_route",
            "set_zoom", "clear_map_cache",
        }
    )


def parse_call(transpiler, call):
    func = call.func
    if is_location_call(call):
        for permission in ("ACCESS_COARSE_LOCATION", "ACCESS_FINE_LOCATION"):
            if permission not in transpiler.declared_permissions:
                transpiler.declared_permissions.append(permission)
        watch_id = _pos_or_kw(transpiler, call, 0, "watch_id") or ast.Constant(value="default")
        if func.attr == "stop":
            return {"type": "location_stop", "watch_id_node": watch_id}
        callback = _callback(
            transpiler, _kw_node(transpiler, call, "on_update"), 5,
            "location", boolean_first=True,
        )
        sample_callback = _callback(
            transpiler, _kw_node(transpiler, call, "on_sample"), 9,
            "location_sample", boolean_first=True,
        )
        status_callback = _callback(
            transpiler, _kw_node(transpiler, call, "on_status"), 2,
            "location_status",
        )
        max_accuracy = transpiler._kw(call.keywords, "max_accuracy", -1)
        if max_accuracy is None:
            max_accuracy = -1
        return {
            "type": "location_watch",
            "watch_id_node": watch_id,
            "callback": callback,
            "sample_callback": sample_callback,
            "status_callback": status_callback,
            "interval": max(250, int(transpiler._kw(call.keywords, "interval", 1500) or 1500)),
            "min_distance": max(0.0, float(transpiler._kw(call.keywords, "min_distance", 0.0) or 0.0)),
            "high_accuracy": str(transpiler._kw(call.keywords, "accuracy", "high")).lower() == "high",
            "provider": str(transpiler._kw(call.keywords, "provider", "auto") or "auto").lower(),
            "max_age": max(0, int(transpiler._kw(call.keywords, "max_age", 15000) or 0)),
            "max_accuracy": float(max_accuracy),
            "timeout": max(0, int(transpiler._kw(call.keywords, "timeout", 15000) or 0)),
        }

    if not is_map_component_call(transpiler, call):
        return None
    action = func.attr
    command = {"type": "map_" + action, "py_var": func.value.id}
    if action == "set_center":
        command.update({
            "lat_node": _pos_or_kw(transpiler, call, 0, "latitude"),
            "lng_node": _pos_or_kw(transpiler, call, 1, "longitude"),
            "zoom_node": _pos_or_kw(transpiler, call, 2, "zoom"),
        })
    elif action == "set_follow_user":
        command["enabled_node"] = (
            _pos_or_kw(transpiler, call, 0, "enabled")
            or ast.Constant(value=True)
        )
    elif action == "set_location":
        command.update({
            "lat_node": _pos_or_kw(transpiler, call, 0, "latitude"),
            "lng_node": _pos_or_kw(transpiler, call, 1, "longitude"),
            "accuracy_node": _pos_or_kw(transpiler, call, 2, "accuracy") or ast.Constant(value=0),
        })
    elif action in {"set_markers", "set_route"}:
        node = _pos_or_kw(transpiler, call, 0, action[4:])
        if isinstance(node, ast.Name):
            node = (
                transpiler.list_assignments.get(node.id)
                or transpiler.dict_assignments.get(node.id)
                or node
            )
        try:
            literal = ast.literal_eval(node)
            node = ast.Constant(value=json.dumps(literal, ensure_ascii=False, separators=(",", ":")))
        except (TypeError, ValueError, SyntaxError):
            pass
        command["value_node"] = node
    elif action == "set_zoom":
        command["zoom_node"] = _pos_or_kw(transpiler, call, 0, "zoom")
    return command


def commands_use_location(functions_map, module_init_cmds=None):
    def walk(commands):
        for command in commands or []:
            if not isinstance(command, dict):
                continue
            if command.get("type") in {"location_watch", "location_stop"}:
                return True
            for key in ("true_body", "false_body", "body"):
                if walk(command.get(key, [])):
                    return True
        return False
    return walk(module_init_cmds) or any(
        walk(info.get("cmds", [])) for info in functions_map.values() if info
    )


def emit_command(lines, indent, command, val_to_java, component_lookup):
    kind = command.get("type")
    if kind == "location_watch":
        watch_id = val_to_java(command.get("watch_id_node"))
        callback = command.get("callback")
        callback_arg = (
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
            "%s_locationWatch(String.valueOf(%s), %dL, %sf, %s, \"%s\", "
            "%dL, %sf, %dL, %s, %s, %s);" % (
                indent, watch_id, int(command.get("interval", 1500)),
                float(command.get("min_distance", 0.0)),
                str(bool(command.get("high_accuracy", True))).lower(),
                str(command.get("provider", "auto")).replace('"', '\\"'),
                int(command.get("max_age", 15000)),
                float(command.get("max_accuracy", -1.0)),
                int(command.get("timeout", 15000)),
                callback_arg, sample_arg, status_arg,
            )
        )
        return
    if kind == "location_stop":
        lines.append("%s_locationStop(String.valueOf(%s));" % (
            indent, val_to_java(command.get("watch_id_node"))
        ))
        return

    component = component_lookup(command.get("py_var"))
    if not component:
        return
    java_var = component.get("_java_var")
    if not java_var:
        return
    def number(node, fallback="0"):
        return "_apkpyMapDouble(String.valueOf(%s), %s)" % (
            val_to_java(node) if node is not None else '""', fallback
        )
    if kind == "map_set_center":
        zoom_node = command.get("zoom_node")
        zoom = number(zoom_node, "-1") if zoom_node is not None else "-1"
        lines.append("%s%s.setCenter(%s, %s, (int)%s);" % (
            indent, java_var, number(command.get("lat_node")),
            number(command.get("lng_node")), zoom,
        ))
    elif kind == "map_set_follow_user":
        lines.append("%s%s.setFollowUser(Boolean.parseBoolean(String.valueOf(%s)));" % (
            indent, java_var, val_to_java(command.get("enabled_node")),
        ))
    elif kind == "map_set_location":
        lines.append("%s%s.setLocation(%s, %s, (float)%s);" % (
            indent, java_var, number(command.get("lat_node")),
            number(command.get("lng_node")), number(command.get("accuracy_node")),
        ))
    elif kind == "map_set_markers":
        lines.append("%s%s.setMarkersJson(String.valueOf(%s));" % (
            indent, java_var, val_to_java(command.get("value_node"))
        ))
    elif kind == "map_set_route":
        lines.append("%s%s.setRouteJson(String.valueOf(%s));" % (
            indent, java_var, val_to_java(command.get("value_node"))
        ))
    elif kind == "map_set_zoom":
        lines.append("%s%s.setZoom((int)%s);" % (
            indent, java_var, number(command.get("zoom_node"), "14")
        ))
    elif kind == "map_clear_map_cache":
        lines.append("%s%s.clearTileCache();" % (indent, java_var))


def activity_runtime_java():
    return r'''
    // -- location.watch : filtered, lifecycle-safe device tracking ----------
    private interface ApkpyLocationCallback {
        void onLocation(boolean success, String latitude, String longitude,
                        String accuracy, String speed);
    }
    private interface ApkpyLocationSampleCallback {
        void onSample(boolean success, String latitude, String longitude,
                      String accuracy, String speed, String bearing,
                      String timestamp, String provider, String isMock);
    }
    private interface ApkpyLocationStatusCallback {
        void onStatus(String status, String message);
    }

    private final class ApkpyLocationWatch implements android.location.LocationListener {
        final String id;
        final long intervalMs;
        final float minDistance;
        final boolean highAccuracy;
        final String providerMode;
        final long maxAgeMs;
        final float maxAccuracy;
        final long timeoutMs;
        final ApkpyLocationCallback callback;
        final ApkpyLocationSampleCallback sampleCallback;
        final ApkpyLocationStatusCallback statusCallback;
        boolean active;
        boolean delivered;
        android.location.Location previous;
        Runnable timeoutRunnable;
        com.google.android.gms.location.LocationCallback fusedCallback;

        ApkpyLocationWatch(String id, long intervalMs, float minDistance,
                           boolean highAccuracy, String providerMode,
                           long maxAgeMs, float maxAccuracy, long timeoutMs,
                           ApkpyLocationCallback callback,
                           ApkpyLocationSampleCallback sampleCallback,
                           ApkpyLocationStatusCallback statusCallback) {
            this.id = id;
            this.intervalMs = Math.max(250L, intervalMs);
            this.minDistance = Math.max(0f, minDistance);
            this.highAccuracy = highAccuracy;
            this.providerMode = providerMode == null ? "auto" : providerMode;
            this.maxAgeMs = Math.max(0L, maxAgeMs);
            this.maxAccuracy = maxAccuracy;
            this.timeoutMs = Math.max(0L, timeoutMs);
            this.callback = callback;
            this.sampleCallback = sampleCallback;
            this.statusCallback = statusCallback;
        }

        void status(String value, String message) {
            if (statusCallback != null) runOnUiThread(() ->
                    statusCallback.onStatus(value, message));
        }

        boolean acceptable(android.location.Location location) {
            if (location == null) return false;
            if (maxAccuracy > 0f && location.hasAccuracy()
                    && location.getAccuracy() > maxAccuracy) {
                status("low_accuracy", String.format(java.util.Locale.US,
                        "Ignored location with %.1f m accuracy", location.getAccuracy()));
                return false;
            }
            if (maxAgeMs > 0L && android.os.Build.VERSION.SDK_INT >= 17) {
                long ageMs = Math.max(0L,
                        (android.os.SystemClock.elapsedRealtimeNanos()
                                - location.getElapsedRealtimeNanos()) / 1000000L);
                if (ageMs > maxAgeMs) {
                    status("stale", "Ignored stale location sample");
                    return false;
                }
            }
            return true;
        }

        void armTimeout(final String provider) {
            if (delivered || timeoutMs <= 0L) return;
            timeoutRunnable = () -> {
                if (active && !delivered) {
                    if (callback != null) callback.onLocation(false, "", "", "", "");
                    if (sampleCallback != null) sampleCallback.onSample(
                            false, "", "", "", "", "", "", provider, "false");
                    status("timeout", "No acceptable location arrived before timeout");
                }
            };
            _apkpyLocationHandler.postDelayed(timeoutRunnable, timeoutMs);
        }

        @Override public void onLocationChanged(android.location.Location location) {
            if (!acceptable(location)) return;
            float speed = location.hasSpeed() ? location.getSpeed() : 0f;
            if (!location.hasSpeed() && previous != null) {
                long delta = Math.max(1L, location.getTime() - previous.getTime());
                speed = previous.distanceTo(location) / (delta / 1000f);
            }
            previous = new android.location.Location(location);
            delivered = true;
            if (timeoutRunnable != null) _apkpyLocationHandler.removeCallbacks(timeoutRunnable);
            final float finalSpeed = speed;
            final String latitude = String.format(java.util.Locale.US, "%.6f", location.getLatitude());
            final String longitude = String.format(java.util.Locale.US, "%.6f", location.getLongitude());
            final String accuracy = String.format(java.util.Locale.US, "%.1f", location.getAccuracy());
            final String speedValue = String.format(java.util.Locale.US, "%.1f", finalSpeed);
            final String bearing = String.format(java.util.Locale.US, "%.1f",
                    location.hasBearing() ? location.getBearing() : 0f);
            final String timestamp = String.valueOf(location.getTime());
            final String provider = location.getProvider() == null ? "unknown" : location.getProvider();
            final String isMock = String.valueOf(
                    android.os.Build.VERSION.SDK_INT >= 18 && location.isFromMockProvider());
            runOnUiThread(() -> {
                if (callback != null) callback.onLocation(
                        true, latitude, longitude, accuracy, speedValue);
                if (sampleCallback != null) sampleCallback.onSample(
                        true, latitude, longitude, accuracy, speedValue,
                        bearing, timestamp, provider, isMock);
                if (statusCallback != null) statusCallback.onStatus(
                        "active", "Location received from " + provider);
            });
        }

        @Override public void onProviderDisabled(String provider) {
            runOnUiThread(() -> {
                if (callback != null) callback.onLocation(false, "", "", "", "");
                if (sampleCallback != null) sampleCallback.onSample(
                        false, "", "", "", "", "", "", provider, "false");
                if (statusCallback != null) statusCallback.onStatus(
                        "provider_disabled", provider + " provider is disabled");
            });
        }
    }

    private final android.os.Handler _apkpyLocationHandler =
            new android.os.Handler(android.os.Looper.getMainLooper());
    private final java.util.Map<String, ApkpyLocationWatch> _apkpyLocationWatches =
            new java.util.LinkedHashMap<>();
    private com.google.android.gms.location.FusedLocationProviderClient _apkpyFusedClient;

    private final androidx.activity.result.ActivityResultLauncher<String[]>
            _apkpyLocationPermissionLauncher = registerForActivityResult(
            new androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions(),
            result -> {
                boolean granted = Boolean.TRUE.equals(result.get(
                        android.Manifest.permission.ACCESS_FINE_LOCATION))
                        || Boolean.TRUE.equals(result.get(
                        android.Manifest.permission.ACCESS_COARSE_LOCATION));
                if (granted) {
                    _locationResumeAll();
                } else {
                    for (ApkpyLocationWatch watch : _apkpyLocationWatches.values()) {
                        if (watch.callback != null)
                            watch.callback.onLocation(false, "", "", "", "");
                        if (watch.sampleCallback != null)
                            watch.sampleCallback.onSample(false, "", "", "", "",
                                    "", "", "permission", "false");
                        watch.status("permission_denied", "Location permission was denied");
                    }
                }
            });

    private boolean _locationHasPermission() {
        return androidx.core.content.ContextCompat.checkSelfPermission(
                this, android.Manifest.permission.ACCESS_FINE_LOCATION)
                == android.content.pm.PackageManager.PERMISSION_GRANTED
                || androidx.core.content.ContextCompat.checkSelfPermission(
                this, android.Manifest.permission.ACCESS_COARSE_LOCATION)
                == android.content.pm.PackageManager.PERMISSION_GRANTED;
    }

    @android.annotation.SuppressLint("MissingPermission")
    private void _locationStart(ApkpyLocationWatch watch) {
        if (watch == null || watch.active || !_locationHasPermission()) return;
        if ("auto".equals(watch.providerMode) || "fused".equals(watch.providerMode)) {
            try {
                if (_apkpyFusedClient == null) {
                    _apkpyFusedClient = com.google.android.gms.location.LocationServices
                            .getFusedLocationProviderClient(this);
                }
                int priority = watch.highAccuracy
                        ? com.google.android.gms.location.Priority.PRIORITY_HIGH_ACCURACY
                        : com.google.android.gms.location.Priority.PRIORITY_BALANCED_POWER_ACCURACY;
                com.google.android.gms.location.LocationRequest request =
                        new com.google.android.gms.location.LocationRequest.Builder(
                                priority, watch.intervalMs)
                                .setMinUpdateIntervalMillis(Math.max(250L, watch.intervalMs / 2L))
                                .setMinUpdateDistanceMeters(watch.minDistance)
                                .build();
                watch.fusedCallback = new com.google.android.gms.location.LocationCallback() {
                    @Override public void onLocationResult(
                            com.google.android.gms.location.LocationResult result) {
                        if (result == null) return;
                        for (android.location.Location location : result.getLocations())
                            watch.onLocationChanged(location);
                    }
                };
                _apkpyFusedClient.requestLocationUpdates(
                        request, watch.fusedCallback, android.os.Looper.getMainLooper());
                _apkpyFusedClient.getLastLocation().addOnSuccessListener(location -> {
                    if (location != null && watch.acceptable(location)) watch.onLocationChanged(location);
                });
                watch.active = true;
                watch.status("searching", "Waiting for fused location");
                watch.armTimeout("fused");
                return;
            } catch (Exception fusedError) {
                watch.fusedCallback = null;
                if ("fused".equals(watch.providerMode)) {
                    watch.status("error", "Fused provider unavailable: "
                            + fusedError.getClass().getSimpleName());
                    return;
                }
                watch.status("fallback", "Fused provider unavailable; using Android system provider");
            }
        }
        android.location.LocationManager manager = (android.location.LocationManager)
                getSystemService(android.content.Context.LOCATION_SERVICE);
        if (manager == null) {
            watch.status("unavailable", "Location service is unavailable");
            return;
        }
        String primary;
        if ("gps".equals(watch.providerMode)) {
            primary = android.location.LocationManager.GPS_PROVIDER;
        } else if ("network".equals(watch.providerMode)) {
            primary = android.location.LocationManager.NETWORK_PROVIDER;
        } else {
            primary = watch.highAccuracy
                    ? android.location.LocationManager.GPS_PROVIDER
                    : android.location.LocationManager.NETWORK_PROVIDER;
        }
        String fallback = watch.highAccuracy
                ? android.location.LocationManager.NETWORK_PROVIDER
                : android.location.LocationManager.GPS_PROVIDER;
        try {
            String provider = manager.isProviderEnabled(primary) ? primary
                    : manager.isProviderEnabled(fallback) ? fallback : null;
            if (provider == null) {
                watch.status("provider_disabled", "Enable device location services");
                return;
            }
            manager.requestLocationUpdates(provider, watch.intervalMs,
                    watch.minDistance, watch, android.os.Looper.getMainLooper());
            android.location.Location last = manager.getLastKnownLocation(provider);
            watch.active = true;
            watch.status("searching", "Waiting for a fresh " + provider + " location");
            if (last != null && watch.acceptable(last)) watch.onLocationChanged(last);
            watch.armTimeout(provider);
        } catch (Exception error) {
            watch.active = false;
            if (watch.callback != null)
                watch.callback.onLocation(false, "", "", "", "");
            if (watch.sampleCallback != null)
                watch.sampleCallback.onSample(false, "", "", "", "",
                        "", "", primary, "false");
            watch.status("error", error.getMessage() == null
                    ? error.getClass().getSimpleName() : error.getMessage());
        }
    }

    private void _locationWatch(String id, long intervalMs, float minDistance,
                                boolean highAccuracy, String providerMode,
                                long maxAgeMs, float maxAccuracy, long timeoutMs,
                                ApkpyLocationCallback callback,
                                ApkpyLocationSampleCallback sampleCallback,
                                ApkpyLocationStatusCallback statusCallback) {
        _locationStop(id);
        ApkpyLocationWatch watch = new ApkpyLocationWatch(
                id, intervalMs, minDistance, highAccuracy, providerMode,
                maxAgeMs, maxAccuracy, timeoutMs,
                callback, sampleCallback, statusCallback);
        _apkpyLocationWatches.put(id, watch);
        if (_locationHasPermission()) {
            _locationStart(watch);
        } else {
            watch.status("permission_required", "Location permission is required");
            _apkpyLocationPermissionLauncher.launch(new String[] {
                    android.Manifest.permission.ACCESS_FINE_LOCATION,
                    android.Manifest.permission.ACCESS_COARSE_LOCATION
            });
        }
    }

    private void _locationStop(String id) {
        ApkpyLocationWatch watch = _apkpyLocationWatches.remove(id);
        if (watch == null) return;
        try {
            if (_apkpyFusedClient != null && watch.fusedCallback != null)
                _apkpyFusedClient.removeLocationUpdates(watch.fusedCallback);
            android.location.LocationManager manager = (android.location.LocationManager)
                    getSystemService(android.content.Context.LOCATION_SERVICE);
            if (manager != null) manager.removeUpdates(watch);
        } catch (Exception ignored) {}
        if (watch.timeoutRunnable != null)
            _apkpyLocationHandler.removeCallbacks(watch.timeoutRunnable);
        watch.active = false;
        watch.status("stopped", "Location tracking stopped");
    }

    private void _locationPauseAll() {
        android.location.LocationManager manager = (android.location.LocationManager)
                getSystemService(android.content.Context.LOCATION_SERVICE);
        for (ApkpyLocationWatch watch : _apkpyLocationWatches.values()) {
            try {
                if (_apkpyFusedClient != null && watch.fusedCallback != null)
                    _apkpyFusedClient.removeLocationUpdates(watch.fusedCallback);
                if (manager != null) manager.removeUpdates(watch);
            }
            catch (Exception ignored) {}
            watch.active = false;
            if (watch.timeoutRunnable != null)
                _apkpyLocationHandler.removeCallbacks(watch.timeoutRunnable);
        }
    }

    private void _locationResumeAll() {
        if (!_locationHasPermission()) return;
        for (ApkpyLocationWatch watch : _apkpyLocationWatches.values()) {
            _locationStart(watch);
        }
    }

    private void _locationStopAll() {
        for (String id : new java.util.ArrayList<>(_apkpyLocationWatches.keySet())) {
            _locationStop(id);
        }
        _apkpyLocationHandler.removeCallbacksAndMessages(null);
    }

    private static double _apkpyMapDouble(String value, double fallback) {
        try { return Double.parseDouble(value); }
        catch (Exception ignored) { return fallback; }
    }
'''


def generate_map_view_java(package):
    """A compact native Android map with OSM tiles, markers and route drawing."""
    return r'''package %s;

public final class ApkpyMapView extends android.view.View {
    public interface OnMapTapListener { void onTap(double latitude, double longitude); }

    private static final int TILE = 256;
    private final android.graphics.Paint paint = new android.graphics.Paint(3);
    private final android.util.LruCache<String, android.graphics.Bitmap> tiles =
            new android.util.LruCache<String, android.graphics.Bitmap>(128) {
                @Override protected int sizeOf(String key, android.graphics.Bitmap value) { return 1; }
            };
    private final java.util.Set<String> pending =
            java.util.Collections.synchronizedSet(new java.util.HashSet<>());
    private final java.util.concurrent.ExecutorService loader =
            java.util.concurrent.Executors.newFixedThreadPool(4);
    private final java.util.List<Marker> markers = new java.util.ArrayList<>();
    private final java.util.List<Point> route = new java.util.ArrayList<>();
    private final android.view.ScaleGestureDetector scaleDetector;

    private double latitude = 0.0, longitude = 0.0;
    private int zoom = 2;
    private boolean showUser = true, followUser = false;
    private boolean hasLocation = false;
    private double userLatitude, userLongitude;
    private float userAccuracy;
    private float downX, downY;
    private double downWorldX, downWorldY;
    private boolean dragged;
    private OnMapTapListener tapListener;
    private android.animation.ValueAnimator locationAnimator;
    private String tileTemplate = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    private String attribution = "© OpenStreetMap contributors";
    private String tileUserAgent = "ApkPy Android/1.2 (+https://repo-apkpy.pages.dev/)";
    private long tileCacheMillis = 7L * 24L * 60L * 60L * 1000L;
    private boolean diskCache = true;

    private static class Point {
        final double lat, lng;
        Point(double lat, double lng) { this.lat = lat; this.lng = lng; }
    }
    private static final class Marker extends Point {
        final String title;
        final int color;
        Marker(double lat, double lng, String title, int color) {
            super(lat, lng); this.title = title; this.color = color;
        }
    }

    public ApkpyMapView(android.content.Context context) { this(context, null); }
    public ApkpyMapView(android.content.Context context, android.util.AttributeSet attrs) {
        super(context, attrs);
        setLayerType(android.view.View.LAYER_TYPE_SOFTWARE, null);
        scaleDetector = new android.view.ScaleGestureDetector(context,
                new android.view.ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScale(android.view.ScaleGestureDetector detector) {
                if (Math.abs(detector.getScaleFactor() - 1.0f) > 0.01f)
                    followUser = false;
                if (detector.getScaleFactor() > 1.08f) setZoom(zoom + 1);
                else if (detector.getScaleFactor() < 0.92f) setZoom(zoom - 1);
                return true;
            }
        });
    }

    public void setCenter(double lat, double lng, int newZoom) {
        latitude = clamp(lat, -85.05112878, 85.05112878);
        longitude = wrapLng(lng);
        if (newZoom >= 2) zoom = Math.max(2, Math.min(19, newZoom));
        followUser = false;
        invalidate();
    }
    public void setZoom(int value) { zoom = Math.max(2, Math.min(19, value)); invalidate(); }
    public void setShowUser(boolean value) { showUser = value; invalidate(); }
    public void setFollowUser(boolean value) {
        followUser = value;
        if (value && hasLocation) {
            latitude = userLatitude;
            longitude = userLongitude;
        }
        invalidate();
    }
    public void setOnMapTapListener(OnMapTapListener value) { tapListener = value; }
    public void setTileConfig(String template, String credit, String userAgent,
                              int cacheDays, boolean persistTiles) {
        String previousTemplate = tileTemplate;
        if (template != null && !template.trim().isEmpty()) tileTemplate = template;
        if (!tileTemplate.equals(previousTemplate)) {
            tiles.evictAll(); pending.clear();
        }
        attribution = credit == null ? "" : credit;
        if (userAgent != null && !userAgent.trim().isEmpty()) tileUserAgent = userAgent;
        tileCacheMillis = Math.max(0, cacheDays) * 24L * 60L * 60L * 1000L;
        diskCache = persistTiles;
        invalidate();
    }
    public void setLocation(double lat, double lng, float accuracy) {
        final double targetLat = clamp(lat, -85.05112878, 85.05112878);
        final double rawTargetLng = wrapLng(lng);
        userAccuracy = Math.max(0f, accuracy);
        if (!hasLocation) {
            userLatitude = targetLat; userLongitude = rawTargetLng; hasLocation = true;
            if (followUser) { latitude = targetLat; longitude = rawTargetLng; }
            invalidate(); return;
        }
        if (locationAnimator != null) locationAnimator.cancel();
        final double startLat = userLatitude, startLng = userLongitude;
        double longitudeDelta = rawTargetLng - startLng;
        if (longitudeDelta > 180.0) longitudeDelta -= 360.0;
        else if (longitudeDelta < -180.0) longitudeDelta += 360.0;
        final double targetLng = startLng + longitudeDelta;
        locationAnimator = android.animation.ValueAnimator.ofFloat(0f, 1f);
        locationAnimator.setDuration(260L);
        locationAnimator.setInterpolator(new android.view.animation.DecelerateInterpolator());
        locationAnimator.addUpdateListener(animation -> {
            float fraction = (float)animation.getAnimatedValue();
            userLatitude = startLat + (targetLat - startLat) * fraction;
            userLongitude = wrapLng(startLng + (targetLng - startLng) * fraction);
            if (followUser) { latitude = userLatitude; longitude = userLongitude; }
            invalidate();
        });
        locationAnimator.start();
    }

    public void clearTileCache() {
        tiles.evictAll();
        deleteTree(tileCacheDirectory());
        invalidate();
    }

    public void setMarkersJson(String json) {
        markers.clear();
        try {
            org.json.JSONArray array = new org.json.JSONArray(json == null ? "[]" : json);
            for (int i = 0; i < array.length(); i++) {
                org.json.JSONObject item = array.optJSONObject(i);
                if (item == null) continue;
                int color;
                try { color = android.graphics.Color.parseColor(item.optString("color", "#8B5CF6")); }
                catch (Exception ignored) { color = 0xFF8B5CF6; }
                markers.add(new Marker(item.optDouble("lat"), item.optDouble("lng"),
                        item.optString("title", ""), color));
            }
        } catch (Exception ignored) {}
        invalidate();
    }

    public void setRouteJson(String json) {
        route.clear();
        try {
            org.json.JSONArray array = new org.json.JSONArray(json == null ? "[]" : json);
            for (int i = 0; i < array.length(); i++) {
                org.json.JSONObject object = array.optJSONObject(i);
                if (object != null) {
                    route.add(new Point(object.optDouble("lat"), object.optDouble("lng")));
                } else {
                    org.json.JSONArray pair = array.optJSONArray(i);
                    if (pair != null && pair.length() >= 2)
                        route.add(new Point(pair.optDouble(0), pair.optDouble(1)));
                }
            }
        } catch (Exception ignored) {}
        invalidate();
    }

    @Override protected void onDraw(android.graphics.Canvas canvas) {
        super.onDraw(canvas);
        canvas.drawColor(0xFF20242B);
        double[] centre = world(latitude, longitude, zoom);
        double left = centre[0] - getWidth() / 2.0;
        double top = centre[1] - getHeight() / 2.0;
        int firstX = (int)Math.floor(left / TILE), lastX = (int)Math.floor((left + getWidth()) / TILE);
        int firstY = (int)Math.floor(top / TILE), lastY = (int)Math.floor((top + getHeight()) / TILE);
        int count = 1 << zoom;
        paint.setStyle(android.graphics.Paint.Style.FILL);
        for (int x = firstX; x <= lastX; x++) for (int y = firstY; y <= lastY; y++) {
            float px = (float)(x * TILE - left), py = (float)(y * TILE - top);
            paint.setColor(0xFF252A32); canvas.drawRect(px, py, px + TILE, py + TILE, paint);
            if (y < 0 || y >= count) continue;
            int wrapped = ((x %% count) + count) %% count;
            String key = zoom + "/" + wrapped + "/" + y;
            android.graphics.Bitmap bitmap = tiles.get(key);
            if (bitmap != null) canvas.drawBitmap(bitmap, px, py, paint);
            else requestTile(key, zoom, wrapped, y);
        }
        drawRoute(canvas, left, top);
        drawMarkers(canvas, left, top);
        drawUser(canvas, left, top);
        if (attribution != null && !attribution.isEmpty()) {
            paint.setColor(0xFFE5E7EB); paint.setTextSize(dp(9));
            paint.setTextAlign(android.graphics.Paint.Align.RIGHT);
            canvas.drawText(attribution, getWidth() - dp(7), getHeight() - dp(7), paint);
        }
    }

    private void drawRoute(android.graphics.Canvas canvas, double left, double top) {
        if (route.size() < 2) return;
        android.graphics.Path path = new android.graphics.Path();
        for (int i = 0; i < route.size(); i++) {
            double[] p = world(route.get(i).lat, route.get(i).lng, zoom);
            if (i == 0) path.moveTo((float)(p[0] - left), (float)(p[1] - top));
            else path.lineTo((float)(p[0] - left), (float)(p[1] - top));
        }
        paint.setStyle(android.graphics.Paint.Style.STROKE); paint.setStrokeCap(android.graphics.Paint.Cap.ROUND);
        paint.setStrokeJoin(android.graphics.Paint.Join.ROUND); paint.setColor(0xFF22D3EE); paint.setStrokeWidth(dp(7));
        canvas.drawPath(path, paint); paint.setColor(0xFFF4F7FB); paint.setStrokeWidth(dp(2)); canvas.drawPath(path, paint);
    }

    private void drawMarkers(android.graphics.Canvas canvas, double left, double top) {
        paint.setTextAlign(android.graphics.Paint.Align.CENTER); paint.setTextSize(dp(11));
        for (Marker marker : markers) {
            double[] p = world(marker.lat, marker.lng, zoom); float x = (float)(p[0] - left), y = (float)(p[1] - top);
            paint.setStyle(android.graphics.Paint.Style.FILL); paint.setColor(marker.color); canvas.drawCircle(x, y, dp(9), paint);
            paint.setStyle(android.graphics.Paint.Style.STROKE); paint.setStrokeWidth(dp(3)); paint.setColor(android.graphics.Color.WHITE);
            canvas.drawCircle(x, y, dp(9), paint);
            if (!marker.title.isEmpty()) { paint.setStyle(android.graphics.Paint.Style.FILL); paint.setColor(android.graphics.Color.WHITE); canvas.drawText(marker.title, x, y - dp(16), paint); }
        }
    }

    private void drawUser(android.graphics.Canvas canvas, double left, double top) {
        if (!showUser || !hasLocation) return;
        double[] p = world(userLatitude, userLongitude, zoom); float x = (float)(p[0] - left), y = (float)(p[1] - top);
        double metresPerPixel = 156543.03392 * Math.cos(Math.toRadians(userLatitude)) / (1 << zoom);
        float radius = (float)Math.max(dp(8), Math.min(dp(90), userAccuracy / Math.max(.1, metresPerPixel)));
        paint.setStyle(android.graphics.Paint.Style.FILL); paint.setColor(0x4438BDF8); canvas.drawCircle(x, y, radius, paint);
        paint.setStyle(android.graphics.Paint.Style.STROKE); paint.setStrokeWidth(dp(1)); paint.setColor(0xFF22D3EE); canvas.drawCircle(x, y, radius, paint);
        paint.setStyle(android.graphics.Paint.Style.FILL); canvas.drawCircle(x, y, dp(10), paint);
        paint.setStyle(android.graphics.Paint.Style.STROKE); paint.setStrokeWidth(dp(4)); paint.setColor(android.graphics.Color.WHITE); canvas.drawCircle(x, y, dp(10), paint);
    }

    private void requestTile(String key, int z, int x, int y) {
        if (!pending.add(key)) return;
        loader.execute(() -> {
            java.net.HttpURLConnection connection = null;
            try {
                java.io.File cachedFile = tileCacheFile(key);
                if (diskCache && cachedFile.isFile()
                        && (tileCacheMillis <= 0L
                        || System.currentTimeMillis() - cachedFile.lastModified() <= tileCacheMillis)) {
                    android.graphics.Bitmap cached = android.graphics.BitmapFactory.decodeFile(
                            cachedFile.getAbsolutePath());
                    if (cached != null) { tiles.put(key, cached); return; }
                }
                String address = tileTemplate.replace("{z}", String.valueOf(z))
                        .replace("{x}", String.valueOf(x)).replace("{y}", String.valueOf(y));
                java.net.URL url = new java.net.URL(address);
                connection = (java.net.HttpURLConnection)url.openConnection();
                connection.setConnectTimeout(6000); connection.setReadTimeout(6000);
                connection.setRequestProperty("User-Agent", tileUserAgent);
                byte[] payload;
                try (java.io.InputStream input = connection.getInputStream();
                     java.io.ByteArrayOutputStream output = new java.io.ByteArrayOutputStream()) {
                    byte[] buffer = new byte[8192]; int read;
                    while ((read = input.read(buffer)) != -1) output.write(buffer, 0, read);
                    payload = output.toByteArray();
                }
                android.graphics.Bitmap bitmap = android.graphics.BitmapFactory.decodeByteArray(
                        payload, 0, payload.length);
                if (bitmap != null) {
                    tiles.put(key, bitmap);
                    if (diskCache) {
                        java.io.File parent = cachedFile.getParentFile();
                        if (parent != null) parent.mkdirs();
                        try (java.io.FileOutputStream output = new java.io.FileOutputStream(cachedFile)) {
                            output.write(payload);
                        } catch (Exception ignored) {}
                    }
                }
            } catch (Exception ignored) {
            } finally {
                if (connection != null) connection.disconnect(); pending.remove(key); postInvalidate();
            }
        });
    }

    private java.io.File tileCacheDirectory() {
        java.io.File root = new java.io.File(getContext().getCacheDir(), "apkpy_map_tiles");
        return new java.io.File(root, Integer.toHexString(tileTemplate.hashCode()));
    }
    private java.io.File tileCacheFile(String key) {
        return new java.io.File(tileCacheDirectory(), key.replace('/', '_') + ".png");
    }
    private static void deleteTree(java.io.File file) {
        if (file == null || !file.exists()) return;
        java.io.File[] children = file.listFiles();
        if (children != null) for (java.io.File child : children) deleteTree(child);
        try { file.delete(); } catch (Exception ignored) {}
    }

    @Override public boolean onTouchEvent(android.view.MotionEvent event) {
        scaleDetector.onTouchEvent(event);
        switch (event.getActionMasked()) {
            case android.view.MotionEvent.ACTION_DOWN:
                downX = event.getX(); downY = event.getY(); dragged = false;
                double[] c = world(latitude, longitude, zoom); downWorldX = c[0]; downWorldY = c[1]; return true;
            case android.view.MotionEvent.ACTION_MOVE:
                if (Math.abs(event.getX() - downX) + Math.abs(event.getY() - downY) > dp(3)) {
                    dragged = true;
                    followUser = false;
                }
                double[] ll = latLng(downWorldX - (event.getX() - downX), downWorldY - (event.getY() - downY), zoom);
                latitude = ll[0]; longitude = ll[1]; invalidate(); return true;
            case android.view.MotionEvent.ACTION_UP:
                if (!dragged && tapListener != null) {
                    double[] centre = world(latitude, longitude, zoom);
                    double[] tapped = latLng(centre[0] + event.getX() - getWidth()/2.0,
                            centre[1] + event.getY() - getHeight()/2.0, zoom);
                    tapListener.onTap(tapped[0], tapped[1]); performClick();
                }
                return true;
            default: return true;
        }
    }
    @Override public boolean performClick() { super.performClick(); return true; }

    private float dp(float value) { return value * getResources().getDisplayMetrics().density; }
    private static double clamp(double value, double min, double max) { return Math.max(min, Math.min(max, value)); }
    private static double wrapLng(double value) { return ((value + 180.0) %% 360.0 + 360.0) %% 360.0 - 180.0; }
    private static double[] world(double lat, double lng, int z) {
        double size = TILE * (double)(1 << z); double safe = clamp(lat, -85.05112878, 85.05112878);
        double x = (lng + 180.0) / 360.0 * size; double sin = Math.sin(Math.toRadians(safe));
        double y = (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * size;
        return new double[] {x, y};
    }
    private static double[] latLng(double x, double y, int z) {
        double size = TILE * (double)(1 << z); double lng = x / size * 360.0 - 180.0;
        double n = Math.PI - 2.0 * Math.PI * y / size; double lat = Math.toDegrees(Math.atan(Math.sinh(n)));
        return new double[] {lat, wrapLng(lng)};
    }
}
''' % package
