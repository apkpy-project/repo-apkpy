"""Maps and continuous location for ApkPy.

The desktop implementation intentionally mirrors the generated Android API:
``map_view`` renders OpenStreetMap raster tiles and ``location.watch`` exposes
both the legacy five-value callback and a richer location sample callback.
Android generation lives in
``apkpy_lib.core.features.maps`` so this module stays lightweight at import
time and does not create a hard dependency on a vendor SDK or API key.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import io
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time
import urllib.request


DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_ATTRIBUTION = "© OpenStreetMap contributors"
DEFAULT_USER_AGENT = "ApkPyPreviewer/1.2 (+https://repo-apkpy.pages.dev/)"


@dataclass(frozen=True)
class LocationSample:
    """One immutable location reading used by the desktop runtime.

    Generated Android callbacks expose the same fields as callback arguments,
    keeping the generated project free from a Python runtime.
    """

    success: bool
    latitude: str = ""
    longitude: str = ""
    accuracy: str = ""
    speed: str = ""
    bearing: str = ""
    timestamp: str = ""
    provider: str = ""
    is_mock: str = "false"
    status: str = "active"


def _coordinate(value, name, minimum, maximum):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return result


def _point(value):
    if isinstance(value, dict):
        lat = value.get("lat", value.get("latitude"))
        lng = value.get("lng", value.get("longitude", value.get("lon")))
        result = dict(value)
    elif isinstance(value, (list, tuple)) and len(value) >= 2:
        lat, lng = value[0], value[1]
        result = {"lat": lat, "lng": lng}
    else:
        raise ValueError("map points must be {'lat': ..., 'lng': ...} or [lat, lng]")
    result["lat"] = _coordinate(lat, "latitude", -90.0, 90.0)
    result["lng"] = _coordinate(lng, "longitude", -180.0, 180.0)
    return result


def _points(values):
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if isinstance(values, dict) and values.get("type") == "Feature":
        values = values.get("geometry", {}).get("coordinates", [])
        values = [[item[1], item[0]] for item in values if len(item) >= 2]
    return [_point(item) for item in (values or [])]


def _preview_route_points(source):
    """Resolve a fixed route or a live map component into immutable points."""
    try:
        if hasattr(source, "get_route") and callable(source.get_route):
            source = source.get_route()
        elif callable(source):
            source = source()
        return tuple((point["lat"], point["lng"]) for point in _points(source))
    except (TypeError, ValueError):
        return ()


def _auto_view(latitude, longitude, zoom, markers, route):
    points = list(markers or []) + list(route or [])
    explicit = latitude is not None and longitude is not None
    if explicit:
        return latitude, longitude, 14 if zoom is None else zoom
    if points:
        latitudes = [point["lat"] for point in points]
        longitudes = [point["lng"] for point in points]
        latitude = sum(latitudes) / len(latitudes)
        longitude = sum(longitudes) / len(longitudes)
        if zoom is None:
            span = max(max(latitudes) - min(latitudes),
                       max(longitudes) - min(longitudes), 0.00001)
            zoom = max(2, min(17, int(math.log2(180.0 / span)) - 1))
        return latitude, longitude, zoom
    return 0.0, 0.0, 2 if zoom is None else zoom


def map_view(latitude=None, longitude=None, zoom=None, *, markers=None,
             route=None, show_user=True, follow_user=False, on_tap=None,
             tile_url=DEFAULT_TILE_URL, attribution=DEFAULT_ATTRIBUTION,
             tile_user_agent=DEFAULT_USER_AGENT, cache_days=7,
             disk_cache=True, preview_label="PREVIEW · NO DEVICE GPS",
             id=None, screen=None, parent=None):
    """Create an interactive, key-free map component.

    ``markers`` accepts dictionaries with ``lat``, ``lng``, optional ``title``
    and ``color``. ``route`` accepts the same dictionaries or ``[lat, lng]``
    pairs.  The returned component supports ``set_center()``,
    ``set_follow_user()``, ``set_location()``, ``set_markers()``,
    ``set_route()``, ``get_route()`` and ``set_zoom()``.
    """
    from .ui import ComponentDef

    marker_points = _points(markers)
    route_points = _points(route)
    latitude, longitude, zoom = _auto_view(
        latitude, longitude, zoom, marker_points, route_points,
    )
    lat = _coordinate(latitude, "latitude", -90.0, 90.0)
    lng = _coordinate(longitude, "longitude", -180.0, 180.0)
    try:
        zoom_value = max(2, min(19, int(zoom)))
    except (TypeError, ValueError) as exc:
        raise ValueError("zoom must be an integer between 2 and 19") from exc
    comp = ComponentDef(
        "map", latitude=lat, longitude=lng, zoom=zoom_value,
        markers=marker_points, route=route_points,
        show_user=bool(show_user), follow_user=bool(follow_user),
        on_tap=on_tap, tile_url=str(tile_url or DEFAULT_TILE_URL),
        attribution=str(attribution or ""),
        tile_user_agent=str(tile_user_agent or DEFAULT_USER_AGENT),
        cache_days=max(0, int(cache_days or 0)),
        disk_cache=bool(disk_cache), preview_label=str(preview_label or ""),
        comp_id=id,
    )
    if parent is not None:
        parent.children.append(comp)
        return comp
    if screen is not None:
        return screen._add(comp)
    raise ValueError("map_view() requires screen= or parent= in declarative apps")


class ContinuousLocationMixin:
    """Preview implementation shared by ``LocationAPI``.

    Desktop computers do not expose Android's LocationManager, so a supplied
    ``preview_route`` is replayed deterministically.  This keeps courier,
    delivery and tracking screens testable before opening Android Studio.
    """

    def watch(self, watch_id, on_update=None, *, on_sample=None, on_status=None,
              interval=1500, min_distance=0.0, accuracy="high",
              provider="auto", preview_route=None, loop=True, screen=None,
              max_age=15000, max_accuracy=None, timeout=15000):
        watch_key = str(watch_id or "default")
        self.stop(watch_key)
        try:
            interval_ms = max(250, int(interval))
        except (TypeError, ValueError):
            interval_ms = 1500
        route = _preview_route_points(preview_route)
        record = {
            "route": route, "index": 0, "after": None,
            "route_source": preview_route,
            "callback": on_update, "sample_callback": on_sample,
            "status_callback": on_status, "interval": interval_ms,
            "loop": bool(loop), "screen": screen,
            "accuracy": 4.0 if str(accuracy).lower() == "high" else 24.0,
            "min_distance": max(0.0, float(min_distance or 0.0)),
            "provider": "preview-simulation", "last": None,
            "max_age": max(0, int(max_age or 0)),
            "max_accuracy": None if max_accuracy is None else max(0.0, float(max_accuracy)),
            "timeout": max(0, int(timeout or 0)),
        }
        if not hasattr(self, "_continuous_watches"):
            self._continuous_watches = {}
        self._continuous_watches[watch_key] = record

        if not route:
            if callable(on_status):
                on_status("unavailable", "Desktop Preview has no device GPS; pass preview_route explicitly to simulate movement")
            if callable(on_update):
                on_update(False, "", "", "", "")
            if callable(on_sample):
                on_sample(False, "", "", "", "", "", str(int(time.time() * 1000)),
                          "preview", "false")
            self._continuous_watches.pop(watch_key, None)
            return watch_key

        if callable(on_status):
            on_status("simulated", "Preview is replaying the explicit preview_route; Android uses device location")

        def tick():
            current = getattr(self, "_continuous_watches", {}).get(watch_key)
            if current is not record:
                return
            active_route = _preview_route_points(record["route_source"])
            if active_route != record["route"]:
                record["route"] = active_route
                record["index"] = 0
                record["last"] = None
            if not active_route:
                self.stop(watch_key)
                return
            from . import ui as _ui
            app = getattr(_ui, "_app", None)
            if screen is None or app is None or app._active_screen is screen:
                lat, lng = active_route[record["index"]]
                previous = record["last"]
                speed = 0.0
                if previous is not None:
                    metres = _haversine(previous[0], previous[1], lat, lng)
                    speed = metres / max(0.25, interval_ms / 1000.0)
                record["last"] = (lat, lng)
                callback = record["callback"]
                if callback:
                    callback(True, f"{lat:.6f}", f"{lng:.6f}",
                             f"{record['accuracy']:.1f}", f"{speed:.1f}")
                sample_callback = record["sample_callback"]
                if sample_callback:
                    bearing = 0.0
                    if previous is not None:
                        bearing = _bearing(previous[0], previous[1], lat, lng)
                    sample_callback(
                        True, f"{lat:.6f}", f"{lng:.6f}",
                        f"{record['accuracy']:.1f}", f"{speed:.1f}",
                        f"{bearing:.1f}", str(int(time.time() * 1000)),
                        record["provider"], "true",
                    )
                next_index = record["index"] + 1
                if next_index >= len(active_route):
                    if not record["loop"]:
                        self.stop(watch_key)
                        return
                    next_index = 0
                record["index"] = next_index
            if app is not None and getattr(app, "root", None):
                try:
                    record["after"] = app.root.after(interval_ms, tick)
                except Exception:
                    self.stop(watch_key)

        from . import ui as _ui
        app = getattr(_ui, "_app", None)
        if app is not None and getattr(app, "root", None):
            record["after"] = app.root.after(0, tick)
        else:
            tick()
        return watch_key

    def stop(self, watch_id="default"):
        record = getattr(self, "_continuous_watches", {}).pop(
            str(watch_id or "default"), None
        )
        if not record:
            return
        status_callback = record.get("status_callback")
        if callable(status_callback):
            status_callback("stopped", "Location tracking stopped")
        if record.get("after") is None:
            return
        try:
            from . import ui as _ui
            app = getattr(_ui, "_app", None)
            if app is not None and getattr(app, "root", None):
                app.root.after_cancel(record["after"])
        except Exception:
            pass

    def stop_all(self):
        for watch_id in list(getattr(self, "_continuous_watches", {})):
            self.stop(watch_id)

    def start_background_tracking(self, watch_id, on_update=None, *,
                                  on_sample=None, on_status=None,
                                  title="Location active", text="Tracking your trip",
                                  interval=5000, min_distance=5.0,
                                  accuracy="high", preview_route=None,
                                  screen=None):
        """Start explicit foreground-service tracking on Android.

        The desktop Preview cannot run an Android service, so it reuses the
        opt-in route simulator and reports ``preview_only`` via ``on_status``.
        """
        if callable(on_status):
            on_status("preview_only", "Background tracking is simulated only while the Preview window is open")
        return self.watch(
            watch_id, on_update=on_update, on_sample=on_sample,
            interval=interval, min_distance=min_distance, accuracy=accuracy,
            preview_route=preview_route, screen=screen,
        )

    def stop_background_tracking(self, watch_id="default"):
        self.stop(watch_id)


def _haversine(lat1, lng1, lat2, lng2):
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def _bearing(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


_TILE_CACHE = OrderedDict()
_TILE_PENDING = set()
_TILE_LOCK = threading.Lock()
_MAX_TILES = 128


def _tile_cache_root():
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "ApkPy" / "map_tiles"
    return Path.home() / ".cache" / "apkpy" / "map_tiles"


def _tile_namespace(tile_url):
    return hashlib.sha256(str(tile_url).encode("utf-8")).hexdigest()[:12]


def _tile_cache_path(key):
    namespace, zoom, tile_x, tile_y = key
    return (
        _tile_cache_root() / namespace / str(zoom) / str(tile_x)
        / (str(tile_y) + ".png")
    )


def _world_xy(lat, lng, zoom):
    size = 256.0 * (2 ** zoom)
    safe_lat = max(-85.05112878, min(85.05112878, float(lat)))
    x = (float(lng) + 180.0) / 360.0 * size
    sin_lat = math.sin(math.radians(safe_lat))
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * size
    return x, y


def _latlng(world_x, world_y, zoom):
    size = 256.0 * (2 ** zoom)
    lng = world_x / size * 360.0 - 180.0
    n = math.pi - 2.0 * math.pi * world_y / size
    lat = math.degrees(math.atan(math.sinh(n)))
    return lat, lng


def _download_tile(key, canvas, redraw, config):
    _namespace, zoom, tile_x, tile_y = key
    try:
        from PIL import Image
        cache_path = _tile_cache_path(key)
        cache_seconds = max(0, int(config.get("cache_days", 7))) * 86400
        if config.get("disk_cache", True) and cache_path.is_file() and (
                cache_seconds <= 0 or time.time() - cache_path.stat().st_mtime <= cache_seconds):
            image = Image.open(cache_path).convert("RGB")
            with _TILE_LOCK:
                _TILE_CACHE[key] = image
                _TILE_CACHE.move_to_end(key)
            return
        url = str(config.get("tile_url") or DEFAULT_TILE_URL)
        url = url.replace("{z}", str(zoom)).replace("{x}", str(tile_x)).replace("{y}", str(tile_y))
        request = urllib.request.Request(
            url,
            headers={"User-Agent": str(config.get("user_agent") or DEFAULT_USER_AGENT)},
        )
        with urllib.request.urlopen(request, timeout=7) as response:
            payload = response.read()
            image = Image.open(io.BytesIO(payload)).convert("RGB")
        if config.get("disk_cache", True):
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(payload)
            except OSError:
                pass
        with _TILE_LOCK:
            _TILE_CACHE[key] = image
            _TILE_CACHE.move_to_end(key)
            while len(_TILE_CACHE) > _MAX_TILES:
                _TILE_CACHE.popitem(last=False)
    except Exception:
        pass
    finally:
        with _TILE_LOCK:
            _TILE_PENDING.discard(key)
        try:
            canvas.after(0, redraw)
        except Exception:
            pass


def render_map_preview(app, comp, parent_widget, is_flex, pack_side, bg_color):
    """Render ``map_view`` inside the Hot Previewer."""
    import tkinter as tk
    from . import ui as _ui

    style = _ui._merge_with_body(comp.kwargs.get("comp_id"), "map")
    mt, mr, mb, ml = _ui._parse_margin(style)

    def dimension(name, fallback):
        raw = style.get(name)
        if raw is None:
            return fallback
        match = __import__("re").search(r"[0-9.]+", str(raw))
        return max(80, int(float(match.group(0)))) if match else fallback

    width = dimension("width", 360)
    # `height: 100%` is the parent's height, as match_parent on the phone.
    # It used to be read as 100 pixels: a full-screen map under a ride sheet
    # was a strip at the top of the Previewer.
    fluid_height = str(style.get("height", "")).strip().lower() in {"100%", "match_parent", "fill"}
    height = 290 if fluid_height else dimension("height", 290)
    fluid = str(style.get("width", "")).lower() in {"100%", "match_parent", "auto"} or "width" not in style
    fill = ("both" if fluid else "y") if fluid_height else ("x" if fluid else None)
    outer = tk.Frame(parent_widget, bg=bg_color)
    options = {"padx": (ml, mr), "pady": (mt, mb)}
    if is_flex:
        options["side"] = pack_side
    outer.pack(fill=fill, expand=fluid_height, **options)
    canvas = tk.Canvas(
        outer, width=width, height=height, bg="#171A20", bd=0,
        highlightthickness=0, cursor="hand2",
    )
    canvas.pack(fill=fill, expand=fluid or fluid_height)
    initial_user_location = comp.kwargs.get("user_location")
    state = {
        "lat": float(comp.kwargs.get("latitude", 0.0)),
        "lng": float(comp.kwargs.get("longitude", 0.0)),
        "zoom": int(comp.kwargs.get("zoom", 14)),
        "markers": _points(comp.kwargs.get("markers")),
        "route": _points(comp.kwargs.get("route")),
        "location": (
            (float(initial_user_location[0]), float(initial_user_location[1]))
            if initial_user_location else None
        ),
        "accuracy": (
            float(initial_user_location[2])
            if initial_user_location and len(initial_user_location) > 2 else 0.0
        ),
        "drag": None, "location_animation": None,
        "images": [], "dragged": False,
        "follow_user": bool(comp.kwargs.get("follow_user", False)),
    }
    tile_config = {
        "tile_url": comp.kwargs.get("tile_url", DEFAULT_TILE_URL),
        "user_agent": comp.kwargs.get("tile_user_agent", DEFAULT_USER_AGENT),
        "cache_days": comp.kwargs.get("cache_days", 7),
        "disk_cache": comp.kwargs.get("disk_cache", True),
    }
    tile_namespace = _tile_namespace(tile_config["tile_url"])

    def redraw(_event=None):
        if not canvas.winfo_exists():
            return
        canvas.delete("all")
        state["images"] = []
        cw = max(1, canvas.winfo_width())
        ch = max(1, canvas.winfo_height())
        centre_x, centre_y = _world_xy(state["lat"], state["lng"], state["zoom"])
        left, top = centre_x - cw / 2, centre_y - ch / 2
        first_x, last_x = math.floor(left / 256), math.floor((left + cw) / 256)
        first_y, last_y = math.floor(top / 256), math.floor((top + ch) / 256)
        tile_count = 2 ** state["zoom"]
        for tile_x in range(first_x, last_x + 1):
            for tile_y in range(first_y, last_y + 1):
                x, y = tile_x * 256 - left, tile_y * 256 - top
                canvas.create_rectangle(x, y, x + 256, y + 256, fill="#20242B", outline="#2C323B")
                if tile_y < 0 or tile_y >= tile_count:
                    continue
                wrapped_x = tile_x % tile_count
                key = (tile_namespace, state["zoom"], wrapped_x, tile_y)
                with _TILE_LOCK:
                    cached = _TILE_CACHE.get(key)
                    if cached is not None:
                        _TILE_CACHE.move_to_end(key)
                    should_fetch = cached is None and key not in _TILE_PENDING
                    if should_fetch:
                        _TILE_PENDING.add(key)
                if cached is not None:
                    try:
                        from PIL import ImageTk
                        photo = ImageTk.PhotoImage(cached)
                        state["images"].append(photo)
                        canvas.create_image(x, y, image=photo, anchor="nw")
                    except Exception:
                        pass
                elif should_fetch:
                    threading.Thread(
                        target=_download_tile,
                        args=(key, canvas, redraw, tile_config), daemon=True,
                    ).start()

        def screen_xy(lat, lng):
            wx, wy = _world_xy(lat, lng, state["zoom"])
            return wx - left, wy - top

        route = state["route"]
        if len(route) >= 2:
            coords = []
            for point in route:
                coords.extend(screen_xy(point["lat"], point["lng"]))
            canvas.create_line(*coords, fill="#22D3EE", width=7, smooth=True)
            canvas.create_line(*coords, fill="#F4F7FB", width=2, smooth=True)

        for marker in state["markers"]:
            x, y = screen_xy(marker["lat"], marker["lng"])
            color = str(marker.get("color") or "#8B5CF6")
            canvas.create_oval(x - 9, y - 9, x + 9, y + 9, fill=color, outline="#FFFFFF", width=3)
            title = str(marker.get("title") or "")
            if title:
                canvas.create_text(x, y - 17, text=title, fill="#FFFFFF",
                                   font=("Segoe UI", 9, "bold"))

        if comp.kwargs.get("show_user", True) and state["location"]:
            lat, lng = state["location"]
            x, y = screen_xy(lat, lng)
            accuracy = max(0.0, float(state["accuracy"]))
            if accuracy:
                metres_per_pixel = 156543.03392 * math.cos(math.radians(lat)) / (2 ** state["zoom"])
                radius = min(90, max(8, accuracy / max(0.1, metres_per_pixel)))
                canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                                   fill="#193A52", outline="#22D3EE", width=1)
            canvas.create_oval(x - 10, y - 10, x + 10, y + 10,
                               fill="#22D3EE", outline="#FFFFFF", width=4)
        attribution = str(comp.kwargs.get("attribution") or "")
        if attribution:
            label_width = max(130, len(attribution) * 5)
            canvas.create_rectangle(
                cw - label_width - 8, ch - 20, cw, ch,
                fill="#111827", outline="",
            )
            canvas.create_text(cw - 8, ch - 7, anchor="se", text=attribution,
                               fill="#E5E7EB", font=("Segoe UI", 7))
        preview_label = str(comp.kwargs.get("preview_label") or "")
        if preview_label:
            label_width = max(180, len(preview_label) * 6)
            canvas.create_rectangle(
                8, 8, 8 + label_width, 32,
                fill="#111827", outline="#22D3EE", width=1,
            )
            canvas.create_text(18, 20, anchor="w", text=preview_label,
                               fill="#22D3EE", font=("Segoe UI", 8, "bold"))

    def set_center(lat, lng, zoom=None):
        state["lat"] = _coordinate(lat, "latitude", -90.0, 90.0)
        state["lng"] = _coordinate(lng, "longitude", -180.0, 180.0)
        state["follow_user"] = False
        comp.kwargs["follow_user"] = False
        if zoom is not None:
            state["zoom"] = max(2, min(19, int(float(zoom))))
        redraw()

    def set_follow_user(enabled=True):
        enabled = bool(enabled)
        state["follow_user"] = enabled
        comp.kwargs["follow_user"] = enabled
        if enabled and state.get("location") is not None:
            state["lat"], state["lng"] = state["location"]
        redraw()

    def set_location(lat, lng, accuracy=0.0):
        lat_value = _coordinate(lat, "latitude", -90.0, 90.0)
        lng_value = _coordinate(lng, "longitude", -180.0, 180.0)
        try:
            state["accuracy"] = max(0.0, float(accuracy or 0.0))
        except (TypeError, ValueError):
            state["accuracy"] = 0.0
        animation = state.get("location_animation")
        if animation is not None:
            try:
                canvas.after_cancel(animation)
            except Exception:
                pass
        start = state.get("location")
        if start is None:
            state["location"] = (lat_value, lng_value)
            if state["follow_user"]:
                state["lat"], state["lng"] = lat_value, lng_value
            redraw()
            return

        steps = 10
        index = 0

        def animate():
            nonlocal index
            index += 1
            fraction = min(1.0, index / steps)
            eased = 1.0 - (1.0 - fraction) ** 3
            current_lat = start[0] + (lat_value - start[0]) * eased
            lng_delta = (lng_value - start[1] + 180.0) % 360.0 - 180.0
            current_lng = (start[1] + lng_delta * eased + 180.0) % 360.0 - 180.0
            state["location"] = (current_lat, current_lng)
            if state["follow_user"]:
                state["lat"], state["lng"] = current_lat, current_lng
            redraw()
            if fraction < 1.0:
                state["location_animation"] = canvas.after(24, animate)
            else:
                state["location_animation"] = None

        animate()

    def set_markers(markers):
        state["markers"] = _points(markers)
        redraw()

    def set_route(route):
        state["route"] = _points(route)
        redraw()

    def set_zoom(zoom):
        state["zoom"] = max(2, min(19, int(float(zoom))))
        redraw()

    def clear_cache():
        with _TILE_LOCK:
            for key in list(_TILE_CACHE):
                if key[0] == tile_namespace:
                    _TILE_CACHE.pop(key, None)
        try:
            import shutil
            shutil.rmtree(_tile_cache_root() / tile_namespace, ignore_errors=True)
        except OSError:
            pass
        redraw()

    def press(event):
        state["drag"] = (event.x, event.y, *_world_xy(state["lat"], state["lng"], state["zoom"]))
        state["dragged"] = False

    def drag(event):
        if not state["drag"]:
            return
        sx, sy, wx, wy = state["drag"]
        if abs(event.x - sx) + abs(event.y - sy) > 3:
            state["dragged"] = True
            state["follow_user"] = False
            comp.kwargs["follow_user"] = False
        state["lat"], state["lng"] = _latlng(wx - (event.x - sx), wy - (event.y - sy), state["zoom"])
        redraw()

    def release(event):
        if not state["dragged"] and callable(comp.kwargs.get("on_tap")):
            centre_x, centre_y = _world_xy(state["lat"], state["lng"], state["zoom"])
            lat, lng = _latlng(
                centre_x + event.x - canvas.winfo_width() / 2,
                centre_y + event.y - canvas.winfo_height() / 2,
                state["zoom"],
            )
            comp.kwargs["on_tap"](f"{lat:.6f}", f"{lng:.6f}")
        state["drag"] = None

    def wheel(event):
        delta = 1 if event.delta > 0 else -1
        state["follow_user"] = False
        comp.kwargs["follow_user"] = False
        set_zoom(state["zoom"] + delta)

    canvas.bind("<Configure>", redraw)
    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", release)
    canvas.bind("<MouseWheel>", wheel)
    comp.widget = canvas
    comp._map_set_center = set_center
    comp._map_set_follow_user = set_follow_user
    comp._map_set_location = set_location
    comp._map_set_markers = set_markers
    comp._map_set_route = set_route
    comp._map_set_zoom = set_zoom
    comp._map_clear_cache = clear_cache
    redraw()
