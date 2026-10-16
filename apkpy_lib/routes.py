"""Opt-in route calculation shared by the Preview and Android generator.

No coordinate is sent anywhere until ``routes.calculate`` is called.  The
default endpoint is the public OSRM demo server and can be replaced by a
self-hosted or compatible endpoint for production/privacy-sensitive apps.
"""

from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request

from .maps import _point


DEFAULT_ROUTE_ENDPOINT = "https://router.project-osrm.org"


def route_points(value):
    """Decode the compact route JSON returned to ``on_result`` callbacks."""
    if isinstance(value, list):
        return value
    try:
        decoded = json.loads(str(value or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return decoded if isinstance(decoded, list) else []


def _dispatch(callback, *args):
    if not callable(callback):
        return
    try:
        from . import ui as _ui
        app = getattr(_ui, "_app", None)
        root = getattr(app, "root", None)
        if root is not None:
            root.after(0, lambda: callback(*args))
            return
    except Exception:
        pass
    callback(*args)


class RouteAPI:
    """Calculate and cancel street-aware routes without a bundled vendor SDK."""

    def __init__(self):
        self._requests = {}
        self._lock = threading.Lock()

    def calculate(self, request_id, origin, destination, on_result=None, *,
                  profile="driving", endpoint=DEFAULT_ROUTE_ENDPOINT,
                  alternatives=False, timeout=15):
        request_key = str(request_id or "default")
        start = _point(origin)
        end = _point(destination)
        selected_profile = str(profile or "driving").lower()
        if selected_profile not in {"driving", "walking", "cycling"}:
            raise ValueError("profile must be driving, walking or cycling")
        cancel_event = threading.Event()
        with self._lock:
            previous = self._requests.pop(request_key, None)
            if previous is not None:
                previous.set()
            self._requests[request_key] = cancel_event

        def worker():
            try:
                base = str(endpoint or DEFAULT_ROUTE_ENDPOINT).rstrip("/")
                coordinates = (
                    f"{start['lng']:.7f},{start['lat']:.7f};"
                    f"{end['lng']:.7f},{end['lat']:.7f}"
                )
                query = urllib.parse.urlencode({
                    "overview": "full",
                    "geometries": "geojson",
                    "alternatives": "true" if alternatives else "false",
                })
                url = f"{base}/route/v1/{selected_profile}/{coordinates}?{query}"
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "ApkPyRoutes/1.2 (+https://repo-apkpy.pages.dev/)",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(request, timeout=max(1, int(timeout))) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if cancel_event.is_set():
                    return
                available = payload.get("routes") or []
                if not available:
                    raise ValueError(str(payload.get("message") or "No route found"))
                route = available[0]
                coordinates = route.get("geometry", {}).get("coordinates", [])
                points = [
                    {"lat": float(item[1]), "lng": float(item[0])}
                    for item in coordinates if isinstance(item, (list, tuple)) and len(item) >= 2
                ]
                route_json = json.dumps(points, separators=(",", ":"))
                _dispatch(
                    on_result, True, route_json,
                    f"{float(route.get('distance', 0.0)):.1f}",
                    f"{float(route.get('duration', 0.0)):.1f}", "",
                )
            except Exception as exc:
                if not cancel_event.is_set():
                    _dispatch(on_result, False, "[]", "0", "0", str(exc))
            finally:
                with self._lock:
                    if self._requests.get(request_key) is cancel_event:
                        self._requests.pop(request_key, None)

        threading.Thread(
            target=worker, name="apkpy-route-" + request_key, daemon=True,
        ).start()
        return request_key

    def cancel(self, request_id="default"):
        with self._lock:
            request = self._requests.pop(str(request_id or "default"), None)
        if request is not None:
            request.set()

    def cancel_all(self):
        with self._lock:
            requests = list(self._requests.values())
            self._requests.clear()
        for request in requests:
            request.set()


routes = RouteAPI()


__all__ = ["RouteAPI", "routes", "route_points", "DEFAULT_ROUTE_ENDPOINT"]
