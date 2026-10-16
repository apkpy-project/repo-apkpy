"""Compiler support for explicit, cancellable street-route calculation."""

from __future__ import annotations

import ast


COMMAND_TYPES = frozenset({"route_calculate", "route_cancel"})


def _kw_node(transpiler, call, name):
    return transpiler._kw_node(call.keywords, name)


def _pos_or_kw(transpiler, call, position, name):
    return call.args[position] if len(call.args) > position else _kw_node(transpiler, call, name)


def _resolve(transpiler, node):
    if isinstance(node, ast.Name):
        return (
            transpiler.list_assignments.get(node.id)
            or transpiler.dict_assignments.get(node.id)
            or node
        )
    return node


def _point_nodes(transpiler, node):
    def coordinate(value):
        # Negative literals arrive as UnaryOp nodes (for example ``-73.9``).
        # Normalising literal numbers here keeps the generic expression
        # compiler out of route parsing while runtime variables still pass
        # through unchanged.
        try:
            number = ast.literal_eval(value)
            if isinstance(number, (int, float)) and not isinstance(number, bool):
                return ast.Constant(value=number)
        except (TypeError, ValueError, SyntaxError):
            pass
        return value

    node = _resolve(transpiler, node)
    if isinstance(node, (ast.List, ast.Tuple)) and len(node.elts) >= 2:
        return coordinate(node.elts[0]), coordinate(node.elts[1])
    if isinstance(node, ast.Dict):
        values = {}
        for key, value in zip(node.keys, node.values):
            try:
                values[str(ast.literal_eval(key))] = value
            except Exception:
                continue
        lat = values.get("lat", values.get("latitude"))
        lng = values.get("lng", values.get("longitude", values.get("lon")))
        if lat is not None and lng is not None:
            return coordinate(lat), coordinate(lng)
    return ast.Constant(value=0), ast.Constant(value=0)


def _callback(transpiler, node):
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.Lambda):
        defaults = ["success", "route_json", "distance", "duration", "error"]
        params = [arg.arg for arg in node.args.args]
        params = (params + defaults)[:5]
        name = transpiler._unique_function_name("route_result_cb")
        body = ast.Expr(value=node.body)
        ast.fix_missing_locations(body)
        transpiler.functions[name] = {
            "args": params,
            "cmds": transpiler._parse_statements([body]),
            "string_args": set(params[1:]),
        }
    else:
        return None
    transpiler.boolean_first_arg_callbacks.add(name)
    return name


def is_call(call):
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "routes"
        and func.attr in {"calculate", "cancel"}
    )


def parse_call(transpiler, call):
    if not is_call(call):
        return None
    if "INTERNET" not in transpiler.declared_permissions:
        transpiler.declared_permissions.append("INTERNET")
    request_id = _pos_or_kw(transpiler, call, 0, "request_id") or ast.Constant(value="default")
    if call.func.attr == "cancel":
        return {"type": "route_cancel", "request_id_node": request_id}
    origin = _pos_or_kw(transpiler, call, 1, "origin")
    destination = _pos_or_kw(transpiler, call, 2, "destination")
    origin_lat, origin_lng = _point_nodes(transpiler, origin)
    destination_lat, destination_lng = _point_nodes(transpiler, destination)
    return {
        "type": "route_calculate",
        "request_id_node": request_id,
        "origin_lat_node": origin_lat,
        "origin_lng_node": origin_lng,
        "destination_lat_node": destination_lat,
        "destination_lng_node": destination_lng,
        "callback": _callback(transpiler, _kw_node(transpiler, call, "on_result")),
        "profile_node": _kw_node(transpiler, call, "profile") or ast.Constant(value="driving"),
        "endpoint_node": _kw_node(transpiler, call, "endpoint") or ast.Constant(
            value="https://router.project-osrm.org"
        ),
        "alternatives": bool(transpiler._kw(call.keywords, "alternatives", False)),
        "timeout": max(1, int(transpiler._kw(call.keywords, "timeout", 15) or 15)),
    }


def commands_use_routes(functions_map, module_init_cmds=None):
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
    if command.get("type") == "route_cancel":
        lines.append("%s_routeCancel(String.valueOf(%s));" % (
            indent, val_to_java(command.get("request_id_node")),
        ))
        return

    def number(node):
        return "_apkpyRouteDouble(String.valueOf(%s))" % val_to_java(node)

    callback = command.get("callback")
    callback_arg = (
        "(success, routeJson, distance, duration, error) -> "
        "pythonCallback_%s(success, routeJson, distance, duration, error)" % callback
        if callback else "null"
    )
    lines.append(
        "%s_routeCalculate(String.valueOf(%s), %s, %s, %s, %s, "
        "String.valueOf(%s), String.valueOf(%s), %s, %d, %s);" % (
            indent,
            val_to_java(command.get("request_id_node")),
            number(command.get("origin_lat_node")),
            number(command.get("origin_lng_node")),
            number(command.get("destination_lat_node")),
            number(command.get("destination_lng_node")),
            val_to_java(command.get("profile_node")),
            val_to_java(command.get("endpoint_node")),
            str(bool(command.get("alternatives", False))).lower(),
            int(command.get("timeout", 15)), callback_arg,
        )
    )


def activity_runtime_java():
    return r'''
    // -- routes.calculate : explicit, cancellable OSRM-compatible requests --
    private interface ApkpyRouteCallback {
        void onRoute(boolean success, String routeJson, String distance,
                     String duration, String error);
    }

    private final java.util.concurrent.ExecutorService _apkpyRouteExecutor =
            java.util.concurrent.Executors.newFixedThreadPool(3);
    private final java.util.concurrent.ConcurrentHashMap<String, java.net.HttpURLConnection>
            _apkpyRouteConnections = new java.util.concurrent.ConcurrentHashMap<>();

    private static double _apkpyRouteDouble(String value) {
        try { return Double.parseDouble(value); }
        catch (Exception ignored) { return 0.0; }
    }

    private void _routeCancel(String id) {
        java.net.HttpURLConnection connection = _apkpyRouteConnections.remove(id);
        if (connection != null) connection.disconnect();
    }

    private void _routeCalculate(
            final String id, final double originLat, final double originLng,
            final double destinationLat, final double destinationLng,
            final String profile, final String endpoint,
            final boolean alternatives, final int timeoutSeconds,
            final ApkpyRouteCallback callback) {
        _routeCancel(id);
        _apkpyRouteExecutor.execute(() -> {
            java.net.HttpURLConnection connection = null;
            try {
                String cleanEndpoint = endpoint == null || endpoint.trim().isEmpty()
                        ? "https://router.project-osrm.org" : endpoint.replaceAll("/+$", "");
                String selectedProfile = ("walking".equals(profile) || "cycling".equals(profile))
                        ? profile : "driving";
                String coordinates = String.format(java.util.Locale.US,
                        "%.7f,%.7f;%.7f,%.7f", originLng, originLat,
                        destinationLng, destinationLat);
                String address = cleanEndpoint + "/route/v1/" + selectedProfile + "/"
                        + coordinates + "?overview=full&geometries=geojson&alternatives="
                        + (alternatives ? "true" : "false");
                connection = (java.net.HttpURLConnection) new java.net.URL(address).openConnection();
                connection.setConnectTimeout(Math.max(1000, timeoutSeconds * 1000));
                connection.setReadTimeout(Math.max(1000, timeoutSeconds * 1000));
                connection.setRequestProperty("Accept", "application/json");
                connection.setRequestProperty("User-Agent",
                        "ApkPyRoutes/1.2 (+https://repo-apkpy.pages.dev/)");
                _apkpyRouteConnections.put(id, connection);
                int status = connection.getResponseCode();
                java.io.InputStream input = status >= 200 && status < 300
                        ? connection.getInputStream() : connection.getErrorStream();
                java.io.BufferedReader reader = new java.io.BufferedReader(
                        new java.io.InputStreamReader(input, java.nio.charset.StandardCharsets.UTF_8));
                StringBuilder body = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) body.append(line);
                reader.close();
                if (status < 200 || status >= 300) {
                    throw new java.io.IOException("Route HTTP " + status);
                }
                org.json.JSONObject root = new org.json.JSONObject(body.toString());
                org.json.JSONArray available = root.optJSONArray("routes");
                if (available == null || available.length() == 0) {
                    throw new java.io.IOException(root.optString("message", "No route found"));
                }
                org.json.JSONObject route = available.getJSONObject(0);
                org.json.JSONArray coordinatesJson = route.getJSONObject("geometry")
                        .getJSONArray("coordinates");
                org.json.JSONArray points = new org.json.JSONArray();
                for (int index = 0; index < coordinatesJson.length(); index++) {
                    org.json.JSONArray coordinate = coordinatesJson.getJSONArray(index);
                    org.json.JSONObject point = new org.json.JSONObject();
                    point.put("lat", coordinate.getDouble(1));
                    point.put("lng", coordinate.getDouble(0));
                    points.put(point);
                }
                String distance = String.format(java.util.Locale.US, "%.1f",
                        route.optDouble("distance", 0.0));
                String duration = String.format(java.util.Locale.US, "%.1f",
                        route.optDouble("duration", 0.0));
                if (callback != null && _apkpyRouteConnections.get(id) == connection) {
                    final String routeJson = points.toString();
                    runOnUiThread(() -> callback.onRoute(
                            true, routeJson, distance, duration, ""));
                }
            } catch (Exception error) {
                if (callback != null && _apkpyRouteConnections.get(id) == connection) {
                    final String message = error.getMessage() == null
                            ? error.getClass().getSimpleName() : error.getMessage();
                    runOnUiThread(() -> callback.onRoute(false, "[]", "0", "0", message));
                }
            } finally {
                if (connection != null) {
                    _apkpyRouteConnections.remove(id, connection);
                    connection.disconnect();
                }
            }
        });
    }

    private void _routeCancelAll() {
        for (String id : new java.util.ArrayList<>(_apkpyRouteConnections.keySet())) {
            _routeCancel(id);
        }
        _apkpyRouteExecutor.shutdownNow();
    }
'''


__all__ = [
    "COMMAND_TYPES", "activity_runtime_java", "commands_use_routes",
    "emit_command", "is_call", "parse_call",
]
