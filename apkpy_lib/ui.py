import tkinter as tk
from tkinter import ttk
import re
import os
import json
import random as _pyrandom
import datetime as _pydatetime
import __main__
from .theme import nav_colors as _nav_colors
from .theme import badge_at_end as _badge_at_end
from .theme import card_text_colors as _card_text_colors
from .theme import mini_player_colors as _mini_player_colors
from .theme import system_icon_color as _system_icon_color
from .theme import NAV_ACTIVE_LABEL_BOLD, NAV_BAR_DP, NAV_LABEL_GAP_DP
from .theme import (
    Theme,
    apply_text_transform,
    apply_theme,
    avatar_color,
    avatar_initials,
    avatar_text_color,
    collection_bubbles,
    component_style,
    default_text_size,
    input_accent_color,
    _length_px,
    _mix_color,
    _number,
    divider_spec,
    letter_spacing_px,
    line_spacing_extra,
    normalize_button_variant,
    normalize_card_variant,
    normalize_label_variant,
    normalize_skeleton_variant,
    normalize_text_align,
)
from . import fonts as _fonts
from . import icons as _icons
from . import job_rules as _job_rules
from . import motion as _motion
from .layout_engine import (
    box_shorthand as _box_shorthand,
    compute_layout_boxes, corner_radii, is_advanced_container, line_count,
)
from .maps import ContinuousLocationMixin
from .features import feeds as feeds_feature
from .features import field as _field_feature
from .features import sheet as _sheet_feature
from .features import zoom as _zoom_feature
from . import zoom_rules as _zoom_rules
from . import sheet_rules as _sheet_rules
from . import field_rules as _field_rules
from .features.data import DataCoreMixin
from .diagnostics import install_tk_exception_hook, report_exception

# Dicionário global para guardar os estilos processados
global_styles = {}
global_keyframes = {}
_active_theme = None
_style_viewport = (411, 914)

def _material_button_text(text, icon=None, variant=None):
    """Return only the label; Preview icons are drawn as vectors on the Canvas.

    Keeping glyphs out of the text avoids platform-font substitutions where a
    pencil, trash can, or save symbol can render as an unrelated character.
    """
    return "" if variant == "icon" and icon else str(text)


# --- Icons ------------------------------------------------------------------
# Geometry comes from apkpy_lib/icons.py, the same table the Android compiler
# reads.  This used to be ~250 lines of hand-drawn canvas lines and ovals that
# agreed with the phone on only 29 of 48 names, and that Tk drew without
# antialiasing however good the geometry was.  Rasterising the shared vector
# instead fixes both at once.

_ICON_CACHE = {}
_ICON_CACHE_ORDER = []
_ICON_CACHE_LIMIT = 512
_ICON_ERRORS_REPORTED = set()


def _app_script_dir():
    """Folder of the app being previewed; user icon paths are relative to it."""
    try:
        return os.path.dirname(os.path.abspath(__main__.__file__))
    except AttributeError:
        return os.getcwd()


def _icon_file_path(raw):
    return raw if os.path.isabs(raw) else os.path.join(_app_script_dir(), raw)


def _icon_token(raw):
    """Cheap cache token: the modification time for a user file, else nothing.

    This is a Hot Previewer, so editing logo.svg has to repaint it rather than
    serve the bitmap that was rasterised from the previous version.
    """
    if not _icons.is_file_reference(raw):
        return ''
    try:
        return str(os.path.getmtime(_icon_file_path(raw)))
    except OSError:
        return 'missing'


def _icon_subpaths(raw, style='filled'):
    """Flattened geometry for a catalogue name or a user .svg file."""
    if not _icons.is_file_reference(raw):
        return _icons.flatten(_icons.path_for(raw, style))
    try:
        return _icons.flatten(_icons.load_svg(_icon_file_path(raw)))
    except Exception as error:
        # A broken icon must never take the Previewer down. Report it once and
        # fall back to the same shape the phone would draw.
        if raw not in _ICON_ERRORS_REPORTED:
            _ICON_ERRORS_REPORTED.add(raw)
            report_exception(error, context='Loading icon %s' % raw)
        return _icons.flatten(_icons.path_for('circle'))


def _icon_photo(icon, color, size, style='filled'):
    """Tinted, antialiased icon bitmap. ``None`` when Pillow is unavailable."""
    size = max(1, int(round(size)))
    raw = str(icon or '').strip()
    # A PhotoImage belongs to one Tk interpreter: the same key from a root
    # created later named an image that no longer existed.
    key = (raw, str(color), size, style, id(getattr(tk, '_default_root', None)))
    token = _icon_token(raw)
    cached = _ICON_CACHE.get(key)
    if cached is not None and cached[0] == token:
        return cached[1]
    try:
        from PIL import Image, ImageTk
        coverage = _icons.rasterize(_icon_subpaths(raw, style), size, supersample=4)
        mask = Image.frombytes('L', (size, size), bytes(coverage))
        tinted = Image.new('RGBA', (size, size), _hex_to_rgb(str(color)) + (255,))
        tinted.putalpha(mask)
        photo = ImageTk.PhotoImage(tinted)
    except Exception:
        # No Pillow, or no Tk root yet: PhotoImage needs one. Fall back to
        # canvas polygons rather than letting an icon stop the Previewer.
        return None
    # The cache holds the only reference to the image. Without it Tk collects
    # the PhotoImage and the icon silently disappears from the canvas.
    if key not in _ICON_CACHE:
        # Only new keys join the eviction queue: a repaint after an edited
        # .svg replaces the value, and queuing it twice would later evict a
        # key that is still live.
        _ICON_CACHE_ORDER.append(key)
    _ICON_CACHE[key] = (token, photo)
    while len(_ICON_CACHE_ORDER) > _ICON_CACHE_LIMIT:
        _ICON_CACHE.pop(_ICON_CACHE_ORDER.pop(0), None)
    return photo


def _draw_icon_polygons(canvas, subpaths, cx, cy, color, size, tags):
    """Pillow-less fallback: identical geometry, without the antialiasing."""
    scale = float(size) / _icons.ICON_VIEWPORT
    half = _icons.ICON_VIEWPORT / 2.0
    for subpath in subpaths:
        coords = []
        for px, py in subpath:
            coords.extend((cx + (px - half) * scale, cy + (py - half) * scale))
        if len(coords) >= 6:
            canvas.create_polygon(
                *coords, fill=color, outline=color, tags=tags)


def _draw_material_icon(canvas, icon, cx, cy, color, size=18, tags="icon",
                        style="filled"):
    """Draw an icon from the catalogue shared with the Android compiler."""
    photo = _icon_photo(icon, color, size, style)
    if photo is not None:
        canvas.create_image(cx, cy, image=photo, tags=tags)
        return
    _draw_icon_polygons(
        canvas, _icon_subpaths(str(icon or '').strip(), style),
        cx, cy, color, size, tags)


# --- Status bar glyphs ------------------------------------------------------
# The signal, wifi and battery symbols in the Previewer's top strip.  They used
# to be the string "▮▮▮  ▲  ▮▮▮" -- whatever bars and triangle the system font
# happened to carry -- which read as a row of dashes and told nobody anything.
# These are vectors on the icon catalogue's 24x24 grid, rasterised by the same
# antialiasing pass, so they are drawn the way every other icon here is drawn.
#
# All three occupy one band -- y 8.6..18.8, x 3..21 -- so drawing them at a
# single size aligns them and spaces them evenly with no per-glyph nudging.

_STATUS_STRIP_HEIGHT = 24
_STATUS_GLYPH_SIZE = 24
STATUS_GLYPH_ORDER = ('signal', 'wifi', 'battery')


def _rounded_rect_path(x, y, w, h, r):
    """Path data for a rounded rectangle, wound clockwise."""
    r = min(r, w / 2.0, h / 2.0)
    return (
        'M%(xr)g %(y)g H%(xwr)g A%(r)g %(r)g 0 0 1 %(xw)g %(yr)g '
        'V%(yhr)g A%(r)g %(r)g 0 0 1 %(xwr)g %(yh)g '
        'H%(xr)g A%(r)g %(r)g 0 0 1 %(x)g %(yhr)g '
        'V%(yr)g A%(r)g %(r)g 0 0 1 %(xr)g %(y)g Z' % {
            'x': x, 'y': y, 'r': r,
            'xr': x + r, 'xw': x + w, 'xwr': x + w - r,
            'yr': y + r, 'yh': y + h, 'yhr': y + h - r,
        })


_STATUS_BATTERY_LEVEL = 0.8

# What ``battery.*`` answers in the Previewer. They live next to the drawn
# battery on purpose: the icon in the status strip reads the same number, so
# an app cannot say 14%% beside an icon showing 80%%.
_STATUS_CHARGING = False
_STATUS_POWER_SAVER = False

# Ordered layers of ``(path data, hollow)``. A hollow layer is wound backwards
# before it is rasterised, which is what makes the nonZero rule cut it out
# instead of filling it in -- and the order is there for the canvas fallback,
# which has no alpha mask and so paints the hollow rather than cutting it.
_STATUS_GLYPHS = {
    'signal': ((' '.join(
        _rounded_rect_path(x, y, 3.3, h, 1.1) for x, y, h in (
            (3.0, 14.6, 4.2), (7.9, 12.6, 6.2),
            (12.8, 10.6, 8.2), (17.7, 8.6, 10.2))), False),),
    'wifi': (('M12 18.8 L21 11.9 C20.14 10.4 16.71 8.6 12 8.6 '
              'S3.86 10.4 3 11.9 Z', False),),
    'battery': (
        (_rounded_rect_path(3.0, 9.0, 16.2, 9.4, 2.4), False),      # the shell
        (_rounded_rect_path(4.05, 10.05, 14.1, 7.3, 1.5), True),    # hollowed
        (' '.join((
            _rounded_rect_path(19.8, 11.4, 1.2, 4.6, 0.6),          # terminal
            _rounded_rect_path(4.8, 10.8, 12.6 * _STATUS_BATTERY_LEVEL,
                               5.8, 0.9),                           # charge
        )), False),
    ),
    # flashlight.on() -- a device thing, so it shows up in the device's own
    # strip rather than anywhere in the app. Nothing on a real phone draws a
    # torch here; this is the Previewer standing in for a light it cannot make.
    'torch': ((_icons.path_for('bolt'), False),),
    # recorder.start() -- Android itself lights a microphone in this strip
    # while an app is listening, in green; this is that.
    'mic': ((_icons.path_for('mic'), False),),
    # haptics.* -- a desk cannot shake. A phone between two pairs of waves,
    # for as long as the motor would run.
    'vibrate': ((' '.join((
        _rounded_rect_path(8.6, 8.6, 6.8, 10.2, 1.4),
        _rounded_rect_path(5.4, 10.6, 1.5, 6.2, 0.7),
        _rounded_rect_path(17.1, 10.6, 1.5, 6.2, 0.7),
        _rounded_rect_path(2.4, 12.2, 1.5, 3.0, 0.7),
        _rounded_rect_path(20.1, 12.2, 1.5, 3.0, 0.7),
    )), False),),
    # network.* -- a phone with no connection at all shows this in place of
    # its bars and its Wi-Fi fan. See _status_glyph_order().
    'airplane': ((_icons.path_for('airplanemode_active'), False),),
    # display.keep_on() and display.brightness() -- a desk has no screen to
    # keep awake and none to dim. Nothing on a real phone draws these; they
    # are lit while the screen on show asks for either.
    'awake': ((_icons.path_for('coffee'), False),),
    'brightness': ((_icons.path_for('light_mode'), False),),
}

# Amber, and always amber: the strip's palette follows the screen, but a lit
# torch reads as "something is on" and would disappear if it took the screen's
# ink on a screen whose ink is the same colour.
_STATUS_TORCH_COLOR = '#FFB020'
# What each lit glyph is drawn in, whatever the screen's own ink. The
# microphone is Android's privacy green.
_STATUS_LIT_COLORS = {'torch': _STATUS_TORCH_COLOR, 'mic': '#34C759'}

_STATUS_SUBPATHS = {}
_STATUS_PHOTOS = {}

# The band the three original glyphs were drawn on by hand. A glyph borrowed
# from the icon catalogue is drawn on the full 24x24 grid instead, so it comes
# out half again as tall as its neighbours and the row stops being a row.
_STATUS_BAND = (8.6, 18.8)
_STATUS_FITTED = frozenset({'torch', 'mic', 'airplane', 'awake', 'brightness'})


def _fit_to_band(parts):
    """Scale flattened subpaths into the strip's band, centred on x=12.

    One uniform scale, so the glyph keeps its proportions -- fitting the height
    and stretching the width would turn a bolt into a smear.
    """
    points = [point for part in parts for point in part]
    if not points:
        return parts
    top = min(y for _, y in points)
    bottom = max(y for _, y in points)
    if bottom <= top:
        return parts
    scale = (_STATUS_BAND[1] - _STATUS_BAND[0]) / (bottom - top)
    centre = (min(x for x, _ in points) + max(x for x, _ in points)) / 2.0
    return [[(12.0 + (x - centre) * scale, _STATUS_BAND[0] + (y - top) * scale)
             for x, y in part]
            for part in parts]


def _status_glyph_layers(name):
    """The glyph's layers as flattened point lists, flattened once per name."""
    cached = _STATUS_SUBPATHS.get(name)
    if cached is None:
        cached = []
        for data, hollow in _STATUS_GLYPHS[name]:
            parts = _icons.flatten(data)
            if name in _STATUS_FITTED:
                parts = _fit_to_band(parts)
            if hollow:
                parts = [list(reversed(part)) for part in parts]
            cached.append((parts, hollow))
        _STATUS_SUBPATHS[name] = cached
    return cached


def _status_glyph_photo(name, color):
    """Tinted, antialiased glyph. ``None`` without Pillow, or a named colour."""
    color = str(color)
    if not color.startswith('#'):
        # _hex_to_rgb would answer with its dark fallback and paint the strip
        # invisible; the canvas fallback below hands the name to Tk instead.
        return None
    # Per Tk interpreter, like _icon_photo: an image outlives no root.
    key = (name, color, id(getattr(tk, '_default_root', None)))
    if key in _STATUS_PHOTOS:
        return _STATUS_PHOTOS[key]
    size = _STATUS_GLYPH_SIZE
    try:
        from PIL import Image, ImageTk
        parts = []
        for subpaths, _hollow in _status_glyph_layers(name):
            parts.extend(subpaths)
        coverage = _icons.rasterize(parts, size, supersample=4)
        mask = Image.frombytes('L', (size, size), bytes(coverage))
        tinted = Image.new('RGBA', (size, size), _hex_to_rgb(color) + (255,))
        tinted.putalpha(mask)
        photo = ImageTk.PhotoImage(tinted)
    except Exception:
        # No Pillow, or no Tk root yet: PhotoImage needs one.
        return None
    if len(_STATUS_PHOTOS) > 24:
        # Only the palette in force is ever asked for. This is a leak guard,
        # not a working set, so clearing it costs one repaint.
        _STATUS_PHOTOS.clear()
    # The dict holds the only reference; without it Tk collects the image and
    # the strip silently empties.
    _STATUS_PHOTOS[key] = photo
    return photo


def _torch_is_lit():
    """Whether ``flashlight`` is on. Imported here rather than at the top so
    the feature module can reach back into ``ui`` without a cycle."""
    try:
        from .features.flashlight import flashlight as _flashlight
        return bool(_flashlight.is_on())
    except Exception:
        return False


def _lit_status_glyphs():
    """What leads the cluster right now: the torch while it is lit, the
    microphone while recorder is recording, the motor while it runs."""
    lit = ('torch',) if _torch_is_lit() else ()
    try:
        from .features import kit as _kit
        return lit + tuple(name for name in _kit.status_glyphs()
                           if name in _STATUS_GLYPHS)
    except Exception:
        return lit


_STATUS_CONNECTION = {
    'wifi': ('Wi-Fi', STATUS_GLYPH_ORDER),
    'mobile': ('Mobile data', ('signal', 'battery')),
    'none': ('No connection', ('airplane', 'battery')),
}
# The glyphs that are the connection: a click on one of them changes it.
_STATUS_CONNECTION_GLYPHS = frozenset({'signal', 'wifi', 'airplane'})


def _status_connection():
    """What ``network.kind()`` answers in the Previewer. Asked of the family
    itself, so the strip cannot draw a Wi-Fi fan over an app that is told
    there is no connection."""
    try:
        from .features import kit as _kit
        kind = _kit.network._kind
    except Exception:
        kind = 'wifi'
    return kind if kind in _STATUS_CONNECTION else 'wifi'


def _previewer_offline():
    """Whether the Previewer is standing in for a phone with no connection."""
    return _status_connection() == 'none'


def _status_glyph_order():
    """The strip's own glyphs, as the connection the Previewer stands in for
    would have them: bars and the fan on Wi-Fi, bars alone on mobile data,
    and an aeroplane where both were when there is no connection."""
    return _STATUS_CONNECTION[_status_connection()][1]


def _status_glyph_at(x):
    """The glyph drawn under ``x`` in the strip's canvas, or ``None``."""
    order = _lit_status_glyphs() + _status_glyph_order()
    index = int(x // _STATUS_GLYPH_SIZE)
    return order[index] if 0 <= index < len(order) else None


def _draw_status_glyphs(canvas, color, background):
    """Repaint the cluster in the palette the current screen resolved to."""
    canvas.delete('all')
    size = _STATUS_GLYPH_SIZE
    # The ink sits on 8.6..18.8, centred on 13.7 rather than on the box's 12.
    # Lifting by the difference centres what is drawn, not the empty box.
    cy = _STATUS_STRIP_HEIGHT / 2.0 - (13.7 - 12.0) * size / 24.0
    # The torch leads the cluster only while it is lit, and the canvas grows to
    # make room -- a fixed width would crop the leftmost glyph instead.
    order = _lit_status_glyphs() + _status_glyph_order()
    try:
        canvas.configure(width=size * len(order))
    except Exception:
        pass
    for index, name in enumerate(order):
        cx = index * size + size / 2.0
        ink = _STATUS_LIT_COLORS.get(name, color)
        photo = _status_glyph_photo(name, ink)
        if photo is not None:
            canvas.create_image(cx, cy, image=photo)
            continue
        # Canvas polygons have no alpha mask, so the battery's hollow is
        # painted in the strip's own colour rather than cut out -- and the
        # charge inside it has to come after, or the hollow buries it.
        for subpaths, hollow in _status_glyph_layers(name):
            _draw_icon_polygons(
                canvas, subpaths, cx, cy,
                background if hollow else ink, size, 'status')


def live_preview():
    """The Previewer window if one is ALREADY open, else ``None``.

    Asked through ``_instance`` on purpose. ``_app`` is a lazy proxy, so
    reading any other attribute of it -- ``root``, ``_active_screen`` -- runs
    ``__getattr__``, which BUILDS the window. A guard written as
    ``getattr(_app, 'root', None)`` therefore never answers ``None``: it opens
    a blank window and then reports that one exists.

    That is not hypothetical. ``language.set()`` asked that way, so running the
    test suite -- or any headless script that changes the language -- put an
    empty white Previewer on screen for as long as it ran.
    """
    return getattr(_app, '_instance', None)


def live_preview_root():
    """The live Previewer's Tk root, or ``None`` when no window is open.

    Safe to call from a background thread: it only reads an attribute, and
    never builds a Tk root off the main thread the way ``getattr(_app,
    'root', None)`` could.
    """
    return getattr(live_preview(), 'root', None)


def refresh_status_glyphs():
    """Repaint the device strip on its own.

    ``render_screen`` repaints it as part of drawing a screen, which covers
    everything that changes when a screen changes. The torch does not: it goes
    on and off inside a click handler, with no re-render behind it, so it needs
    a way to ask. The palette is the one the current screen resolved to, kept
    for exactly this.
    """
    instance = live_preview()
    canvas = getattr(instance, '_status_icons', None)
    if canvas is None:
        return
    try:
        if not canvas.winfo_exists():
            return
    except Exception:
        return
    color, background = getattr(
        instance, '_status_palette', ('#111111', '#ffffff'))
    _draw_status_glyphs(canvas, color, background)
    notifications._refresh()


# ── Tamanhos de dispositivo para o PREVIEW (em dp = resolução lógica) ─────────
# Só afeta a janela do previewer; no Android é ignorado (o ecrã real É o
# dispositivo). Vários modelos partilham o mesmo tamanho lógico — todos os nomes
# são aceites e apontam para as mesmas dimensões. Default = Pixel 9 (411x914).
_PREVIEW_DEVICES = {
    "Small Phone":    (360, 640),
    "Pixel 4":        (393, 830),
    "Pixel 4 XL":     (411, 869),
    "Pixel 4a":       (393, 851),
    "Pixel 5":        (393, 851),
    "Pixel 6":        (411, 914),
    "Pixel 6 Pro":    (411, 891),
    "Pixel 6a":       (411, 914),
    "Pixel 7":        (411, 914),
    "Pixel 7 Pro":    (411, 891),
    "Pixel 7a":       (411, 914),
    "Pixel 8":        (411, 914),
    "Pixel 8 Pro":    (448, 998),
    "Pixel 8a":       (411, 914),
    "Pixel 9":        (411, 914),   # default
    "Pixel 9 Pro":    (427, 952),
    "Pixel 9 Pro XL": (448, 997),
    "Pixel 9a":       (411, 914),
    "Pixel 10":       (411, 914),
    "Pixel 10 Pro":   (427, 952),
    "Pixel 9 Landscape": (914, 411),
    "Tablet":         (800, 1100),
    "Tablet Landscape": (1100, 800),
}
# Lookup tolerante (ignora maiúsculas/espaços): "pixel 8", "Pixel8", "PIXEL 8"...
_PREVIEW_DEVICES_NORM = {k.lower().replace(" ", ""): v for k, v in _PREVIEW_DEVICES.items()}

# Modos especiais (não são modelos): janela cheia.
#   "fullscreen" → ecrã cheio SEM barra de título (Esc para sair)
#   "maximized"  → janela maximizada COM a barra de título padrão (X para fechar)
_SPECIAL_MODES = ("fullscreen", "maximized", "maximizado", "responsive", "responsivo")

# Escolha atual do utilizador (None = default Pixel 9)
_preview_device = None


class JsonRows(str):
    """
    String JSON que também é iterável como lista de linhas.

    É o que `db.query` e as respostas de `https` devolvem: continua a ser
    uma `str` normal (funciona em `set_items`, f-strings, `storage.set`,
    `json_get`...) mas `for row in rows:` itera as linhas como dicts —
    exatamente o que o Android gerado faz com a JSONArray.

    Se o conteúdo não for um array JSON, o loop simplesmente não executa
    (mesmo comportamento do try/catch no Java gerado).
    """

    def _rows(self):
        try:
            data = json.loads(str(self))
            return data if isinstance(data, list) else []
        except ValueError:
            return []

    def __iter__(self):
        return iter(self._rows())

    def __len__(self):
        """Return the number of rows, matching ``len(JSONArray)`` on Android."""
        return len(self._rows())

    def __getitem__(self, key):
        """Index parsed rows instead of the backing JSON text.

        ``JsonRows`` remains a ``str`` for the older APIs that pass JSON between
        components, while integer and slice access now mirrors the row access
        exposed by the generated Android ``JSONArray`` adapter.
        """
        if isinstance(key, (int, slice)):
            return self._rows()[key]
        return super().__getitem__(key)


# ─── StorageAPI ───────────────────────────────────────────────────────────────

class StorageAPI:
    """
    Armazenamento persistente de chave-valor para o Hot Previewer.
    Os dados são guardados num ficheiro JSON ('apkpy_storage.json') na pasta
    do projecto, sobrevivendo a reaberturas da janela de preview.

    No Android (apkpy build), as chamadas são transpiladas para SharedPreferences.

    Exemplos::

        storage.set("nome", "Alice")
        nome = storage.get("nome", default="Visitante")
        storage.delete("nome")
        storage.clear()
    """

    def __init__(self):
        # Caminho do ficheiro JSON ao lado do script principal
        try:
            script_dir = os.path.dirname(os.path.abspath(__main__.__file__))
        except AttributeError:
            script_dir = os.getcwd()
        self._path = os.path.join(script_dir, 'apkpy_storage.json')
        self._data = {}
        self._load()

    def _load(self):
        """Carrega dados do ficheiro JSON (se existir)."""
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        """Persiste dados no ficheiro JSON."""
        try:
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def set(self, key, value):
        """Grava (ou actualiza) o valor associado à chave.

        O valor é sempre encriptado antes de tocar no disco (no Android,
        AES-256 com chave no Keystore) — o ficheiro fica ilegível para quem
        o roubar. Serializado em JSON para preservar o tipo no round-trip.
        """
        self._data[str(key)] = crypto.encrypt(json.dumps(value))
        self._save()

    def get(self, key, default=""):
        """Devolve o valor da chave, ou *default* se não existir.

        Desencripta automaticamente; valores antigos guardados em
        texto-limpo (antes da encriptação automática) são devolvidos tal
        como estão.

        Sem *default*, uma chave em falta dá "" -- o que o telemóvel sempre
        deu (`_apkpyStorageGet(key, "")`). Dava None aqui, e
        `"Olá " + storage.get("nome")` corria no telemóvel e rebentava no
        computador.
        """
        v = self._data.get(str(key), None)
        if v is None:
            return default
        if isinstance(v, str) and v.startswith('enc1$'):
            try:
                return json.loads(crypto.decrypt(v))
            except (ValueError, TypeError):
                return default
        return v

    def delete(self, key):
        """Remove a chave do armazenamento (não faz nada se não existir)."""
        if str(key) in self._data:
            del self._data[str(key)]
            self._save()

    def clear(self):
        """Remove **todas** as chaves guardadas."""
        self._data.clear()
        self._save()

    def keys(self):
        """Devolve todas as chaves guardadas."""
        return list(self._data.keys())


# Instância global partilhada por toda a app
storage = StorageAPI()


# ─── AppearanceAPI ────────────────────────────────────────────────────────────

APPEARANCE_MODES = ("dark", "light", "system")

# The Theme the app declared, and the two built from it. Kept apart from
# _active_theme, which is whichever of the pair is showing right now.
_declared_theme = [None]
_APPEARANCE_PAIR = {}


class AppearanceAPI:
    """Which of the two colour tables answers, chosen while the app runs.

    Android does this with resource qualifiers: the same
    ``@color/apkpy_background`` is read from ``values/`` or ``values-night/``,
    and ``AppCompatDelegate`` decides which. The Previewer has no resource
    system, so it swaps the ``Theme`` for its counterpart and re-renders --
    different machinery, the same two palettes, because both are built from
    the one ``Theme`` the app declared.
    """

    _KEY = "__apkpy_appearance"

    def set(self, mode):
        """Switch to ``"dark"``, ``"light"`` or ``"system"``.

        The choice is stored, so the app opens the way it was left -- which
        is what the generated Java does too, reading the same key before the
        first layout inflates.
        """
        chosen = str(mode).strip().lower()
        if chosen not in APPEARANCE_MODES:
            raise ValueError(
                'appearance.set(...) takes "dark", "light" or "system", '
                'not %r' % (mode,)
            )
        storage.set(self._KEY, chosen)
        _apply_appearance(chosen)
        return chosen

    def get(self):
        """What was chosen, or what the app declared if nobody chose."""
        stored = storage.get(self._KEY, "")
        if stored in APPEARANCE_MODES:
            return stored
        return _declared_appearance()


appearance = AppearanceAPI()


# ─── Languages ────────────────────────────────────────────────────────────────
# Text used to be written straight into each screen, so an app spoke exactly one
# language. The words now live in one table that both runtimes read; the rules
# for choosing between them are in core/i18n.py so the two cannot drift.

_ALL_SCREENS = []           # todos os Screen criados, por ordem
_TRANSLATIONS = {}          # tag -> {key: text}
_DEFAULT_LANGUAGE = ['']    # the tag Android keeps in res/values/


def translations(table, default=None):
    """Declare the app's words, one dictionary per language.

        translations({
            "en": {"save": "Save", "greeting": "Hello"},
            "pt": {"save": "Guardar", "greeting": "Ola"},
        }, default="en")

    The default language is the one the phone answers from when it has no
    translation for the device's own -- Android's ``res/values/`` -- so every
    key used anywhere has to exist in it. Left unset, the first language given
    is the default.
    """
    from .core import i18n as _i18n

    if not isinstance(table, dict) or not table:
        raise ValueError("translations() takes a dict of language -> words")

    cleaned = {}
    for tag, words in table.items():
        canonical = _i18n.canonical(tag)
        if canonical is None:
            raise ValueError(
                'translations(): %r is not a language ApkPy can put on a '
                'phone. Use "pt", "en" or "pt-BR".' % (tag,)
            )
        if not isinstance(words, dict):
            raise ValueError('translations(): %s must map keys to text' % canonical)
        for key in words:
            if not _i18n.KEY_PATTERN.match(str(key)):
                raise ValueError(
                    'translations(): %r is not a usable key. Use letters, '
                    'digits and underscore, starting with a letter.' % (key,)
                )
        cleaned[canonical] = {str(k): str(v) for k, v in words.items()}

    chosen = _i18n.canonical(default) if default else None
    if default and chosen not in cleaned:
        raise ValueError(
            'translations(default=%r): that language is not in the table.' % (default,)
        )
    _TRANSLATIONS.clear()
    _TRANSLATIONS.update(cleaned)
    _DEFAULT_LANGUAGE[0] = chosen or next(iter(cleaned))

    missing = _missing_keys()
    if missing:
        # Android answers a missing word from res/values/, so a key absent
        # there is a build error rather than a blank -- said here, where the
        # line that caused it is still on screen.
        raise ValueError(
            'translations(): %s must contain every key, because it is what '
            'the phone falls back to. Missing: %s'
            % (_DEFAULT_LANGUAGE[0], ', '.join(sorted(missing)))
        )
    return _DEFAULT_LANGUAGE[0]


def _missing_keys():
    """Keys some language has and the default language does not."""
    base = set(_TRANSLATIONS.get(_DEFAULT_LANGUAGE[0], {}))
    everything = set()
    for words in _TRANSLATIONS.values():
        everything |= set(words)
    return everything - base


def _system_language():
    """The desktop's language as a tag, the way the phone reads its own.

    ``locale.getlocale()`` answers ``Portuguese_Portugal`` on Windows, which
    is a name and not a tag: it matched nothing, so a Portuguese desktop
    quietly previewed the app in the fallback language while the phone showed
    Portuguese. Windows is asked for the real tag instead.
    """
    if os.name == "nt":
        try:
            import ctypes
            buffer = ctypes.create_unicode_buffer(85)
            if ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, 85):
                return buffer.value            # ex.: "pt-PT"
        except Exception:
            pass
    tag = ''
    try:
        import locale as _locale
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            tag = (_locale.getdefaultlocale()[0] or '')
    except Exception:
        tag = ''
    if not tag:
        tag = os.environ.get('LANG', '') or os.environ.get('LANGUAGE', '')
    tag = str(tag).split('.')[0].split(':')[0].replace('_', '-')
    # "C" and "POSIX" are what a bare Linux box (a CI runner, a container)
    # answers: no language was chosen, so none is reported.
    return '' if tag in ('C', 'POSIX') else tag


class _Translated(str):
    """A word that remembers which key it came from.

    It is a real string everywhere it is used, so nothing downstream has to
    know about it. The key is what lets ``language.set()`` resolve it again:
    a component reads its text once, when the module runs, and without this
    the Previewer would keep the first language on screen for ever while the
    phone -- whose layout holds a ``@string/`` reference, re-read every time
    the activity is recreated -- switched properly. Two runtimes, one visible
    difference, and no error anywhere.
    """

    __slots__ = ('key',)

    def __new__(cls, text, key):
        made = super().__new__(cls, text)
        made.key = key
        return made


def _retranslate(components):
    """Resolve every remembered word again, for a language that just changed."""
    for component in components or []:
        kwargs = getattr(component, 'kwargs', None)
        if isinstance(kwargs, dict):
            for name, value in list(kwargs.items()):
                if isinstance(value, _Translated):
                    kwargs[name] = t(value.key)
        _retranslate(getattr(component, 'children', None))


def t(key):
    """The word for *key* in the language in force.

    Falls back exactly as Android does: the device's full tag, then its
    language alone, then the default -- so a half-translated app reads the
    same in the Previewer as on a phone. A key nobody declared comes back as
    itself, which is visible on screen rather than blank.
    """
    from .core import i18n as _i18n

    if not _TRANSLATIONS:
        return _Translated(key, key)
    tag = _i18n.match_language(language.get(), list(_TRANSLATIONS),
                               _DEFAULT_LANGUAGE[0])
    words = _TRANSLATIONS.get(tag, {})
    if key in words:
        return _Translated(words[key], key)
    return _Translated(
        _TRANSLATIONS.get(_DEFAULT_LANGUAGE[0], {}).get(key, key), key)


class LanguageAPI:
    """Which language the app is speaking, and switching it while it runs."""

    _KEY = "__apkpy_language"

    def set(self, tag):
        """Switch language and redraw, remembering the choice.

        On the phone this is ``AppCompatDelegate.setApplicationLocales``,
        which recreates the activities the same way a theme change does.
        """
        from .core import i18n as _i18n

        canonical = _i18n.canonical(tag)
        if canonical is None:
            raise ValueError(
                'language.set(%r): use a tag like "pt", "en" or "pt-BR".' % (tag,)
            )
        storage.set(self._KEY, canonical)
        load_styles_now()
        # Os componentes leram o texto uma vez, quando o modulo correu. Redesenhar
        # sozinho voltaria a mostrar as mesmas palavras -- no telemovel o layout
        # guarda uma referencia @string/ e o Android re-resolve-a ao recriar a
        # Activity, e e' isso que isto faz aqui.
        for screen in _ALL_SCREENS:
            _retranslate(getattr(screen, 'components', None))
        # live_preview(), not _app: asking the proxy for _active_screen builds
        # the window, so this guard used to open a blank Previewer in every
        # headless caller -- a build, a test, a script.
        _live = live_preview()
        if _live is not None and _live._active_screen is not None:
            _live.render_screen(_live._active_screen, _from_back=True)
        return canonical

    def get(self):
        """The chosen language, or the desktop's own if nobody chose."""
        stored = storage.get(self._KEY, "")
        return stored or _system_language()

    def available(self):
        """Every language ``translations()`` declared, default first."""
        rest = sorted(tag for tag in _TRANSLATIONS if tag != _DEFAULT_LANGUAGE[0])
        return ([_DEFAULT_LANGUAGE[0]] if _DEFAULT_LANGUAGE[0] else []) + rest


language = LanguageAPI()


# ─── Crash reports ────────────────────────────────────────────────────────────

class CrashAPI:
    """What the app was doing when it last fell over.

        report = crash.last()
        if report:
            https.post(url, json={"trace": report}, on_result=sent)
            crash.clear()

    ApkPy keeps the report and nothing else: no vendor, no endpoint, no
    account. What to do with it is the app's decision, and everything needed
    to send it already exists.

    On the phone the report is written by an uncaught-exception handler that
    then passes the crash on to Android's own, so the app still stops the way
    the system expects. Here it is written from the Previewer's error hooks,
    which catch the same failures a screen callback can raise.
    """

    FILE_NAME = 'apkpy_crash.txt'

    def _path(self):
        return os.path.join(os.path.dirname(storage._path), self.FILE_NAME)

    def _record(self, text):
        try:
            with open(self._path(), 'w', encoding='utf-8') as handle:
                handle.write(text)
        except OSError:
            pass          # a report we cannot store is not worth a second crash

    def last(self):
        """The report from the previous run, or "" if it ended cleanly."""
        try:
            with open(self._path(), encoding='utf-8') as handle:
                return handle.read()
        except OSError:
            return ""

    def clear(self):
        """Forget it -- normally after sending it somewhere."""
        try:
            os.remove(self._path())
        except OSError:
            pass


crash = CrashAPI()


class AppAPI:
    """What version is running, and how to send someone to get a newer one.

        from apkpy_lib import app, https, json_get, modal

        blocker = modal("Update needed", content="...",
                        confirm_text="Update", dismissable=False,
                        on_confirm=lambda: app.open_store())

        def checked(ok, body):
            if ok and int(json_get(body, "minimum")) > int(app.version_code()):
                blocker.open()

        https.get("https://example.com/version", on_response=checked)

    **ApkPy does not invent the protocol.** What "too old" means, and where the
    answer comes from, belong to whoever runs the server -- an app distributed
    through a company's own device management is not asking Play anything.
    These are the three pieces that were missing: the running version, a way to
    open the listing, and a dialog that cannot be dismissed.
    """

    def _config(self):
        """[app] from apkpy.toml, read beside the running script."""
        import os as _os

        directory = _os.path.dirname(storage._path)
        path = _os.path.join(directory, "apkpy.toml")
        try:
            try:
                import tomllib
            except ImportError:      # before Python 3.11: the backport
                import tomli as tomllib
            with open(path, "rb") as handle:
                return tomllib.load(handle).get("app", {}) or {}
        except Exception:
            return {}

    def version_code(self):
        """The whole number that decides which build is newer, as text.

        On the phone this is read from the installed package, so it is the
        version actually running rather than the one the source hoped for.
        """
        return str(self._config().get("version_code", 1))

    def version_name(self):
        """The version people read, like "1.4.2"."""
        return str(self._config().get("version_name", "1.0.0"))

    def open_store(self, url=None):
        """Open the store listing for this app, or any address given.

        Android tries the Play app first and falls back to the web page, so
        this still does something on a device without the Play app -- which is
        exactly the sort of device an enterprise build lands on.
        """
        import webbrowser

        target = url
        if not target:
            package = self._config().get("application_id", "com.apkpy.app")
            target = "https://play.google.com/store/apps/details?id=" + package
        try:
            webbrowser.open(target)
        except Exception:
            pass
        return target


app = AppAPI()


def _record_preview_crash(error, traceback_object=None):
    """Write a report shaped like the one the phone writes."""
    import datetime as _datetime
    import platform as _platform
    import traceback as _traceback

    try:
        trace = ''.join(_traceback.format_exception(
            type(error), error, traceback_object or error.__traceback__))
    except Exception:
        trace = repr(error)
    crash._record(
        "when: %s\nthread: previewer\nandroid: -- (Previewer)\ndevice: %s\n\n%s"
        % (_datetime.datetime.now().isoformat(timespec="seconds"),
           _platform.platform(), trace)
    )


def _declared_appearance():
    """The mode ``run(theme=...)`` asked for, defaulting to light."""
    return "dark" if getattr(_declared_theme[0], "mode", "light") == "dark" else "light"


def _system_prefers_dark():
    """Whether the desktop is in dark mode, as far as we can tell.

    Windows answers through the registry. Anywhere else this is a guess, and
    a wrong guess would silently show the wrong palette, so it says light and
    the phone remains the place where "system" is authoritative.
    """
    if os.name != "nt":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        try:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        finally:
            winreg.CloseKey(key)
        return value == 0
    except Exception:
        return False


def _theme_for(mode):
    """One of the app's two themes, from the pair built when it started.

    Derived once and kept. Deriving on every switch loses the author's own
    colours on the way back: dark -> light -> dark would return the palette
    default rather than the background they wrote, because a counterpart only
    carries the accent.
    """
    pair = _APPEARANCE_PAIR
    if pair.get("source") is not _declared_theme[0]:
        declared = _declared_theme[0]
        if declared is None:
            return None
        pair.clear()
        pair["source"] = declared
        pair[declared.mode] = declared
        other = declared.counterpart()
        pair[other.mode] = other
    return pair.get(mode)


def _apply_appearance(mode):
    """Put the matching palette in force and redraw what is on screen."""
    global _active_theme
    if _declared_theme[0] is None:
        return
    wanted = mode
    if wanted == "system":
        wanted = "dark" if _system_prefers_dark() else "light"
    chosen = _theme_for(wanted)
    if chosen is not None:
        _active_theme = chosen
    load_styles_now()
    _live = live_preview()
    if _live is not None and _live._active_screen is not None:
        # Re-rendering is what Android's activity recreation does for the
        # same reason: the views on screen already hold the old colours.
        # live_preview() rather than _app: see language.set for what asking
        # the lazy proxy directly used to open.
        _live.render_screen(_live._active_screen, _from_back=True)


# ─── CryptoAPI ────────────────────────────────────────────────────────────────

class CryptoAPI:
    """
    Hashing seguro de passwords com salt aleatório — embutido na ApkPy, sem o
    utilizador precisar de importar hashlib.

    O resultado de `hash_password` tem o formato
    "pbkdf2-algo$iterações$salt_hex$hash_hex" e pode ser guardado diretamente
    no `storage` ou na `db`. Como o salt é aleatório, cada chamada produz uma
    string diferente — a verificação faz-se sempre com `verify_password`,
    nunca comparando hashes diretamente.

    No Android (apkpy build), transpila para um loop PBKDF2 sobre
    javax.crypto.Mac (HMAC-SHA256/512) — bit-a-bit idêntico ao
    hashlib.pbkdf2_hmac do Python, por isso um hash criado no Previewer é
    verificável no Android e vice-versa.

    Exemplos::

        storage.set("pw", crypto.hash_password(senha))
        ok = crypto.verify_password(tentativa, storage.get("pw"))
    """

    def hash_password(self, password, algo="sha256", iterations=200000):
        """Gera "pbkdf2-algo$iterações$salt$hash" com salt aleatório de 16 bytes.

        Usa PBKDF2 (key stretching): cada tentativa de brute-force custa
        *iterations* hashes em vez de 1, tornando ataques por GPU ~200.000×
        mais lentos com o default.
        """
        import hashlib
        algo = "sha512" if str(algo).lower() == "sha512" else "sha256"
        iterations = max(1, int(iterations))
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac(algo, str(password).encode("utf-8"), salt, iterations)
        return f"pbkdf2-{algo}${iterations}${salt.hex()}${dk.hex()}"

    def verify_password(self, password, stored):
        """Confirma se *password* corresponde a um hash criado por `hash_password`.

        Aceita o formato PBKDF2 atual e o formato legacy "algo$salt$hash"
        (1× SHA) de versões anteriores.
        """
        import hashlib
        import hmac
        parts = str(stored).split("$")
        try:
            if len(parts) == 4 and parts[0].startswith("pbkdf2-"):
                algo = "sha512" if parts[0] == "pbkdf2-sha512" else "sha256"
                iterations = int(parts[1])
                salt = bytes.fromhex(parts[2])
                dk = hashlib.pbkdf2_hmac(algo, str(password).encode("utf-8"), salt, iterations)
                return hmac.compare_digest(dk.hex(), parts[3])
            if len(parts) == 3:
                algo = "sha512" if parts[0].lower() == "sha512" else "sha256"
                salt = bytes.fromhex(parts[1])
                h = hashlib.new(algo)
                h.update(salt)
                h.update(str(password).encode("utf-8"))
                return hmac.compare_digest(h.hexdigest(), parts[2])
        except (ValueError, AttributeError):
            return False
        return False

    def _device_key(self):
        """Chave de dispositivo (32 bytes) gerada no primeiro uso.

        Simula o Android Keystore: no telemóvel a chave vive no hardware e
        nunca sai de lá; aqui fica num ficheiro local ao lado do script. Por
        isso os dados encriptados são por-dispositivo — o que se encripta no
        Previewer não se desencripta no Android (nem entre instalações).
        """
        try:
            script_dir = os.path.dirname(os.path.abspath(__main__.__file__))
        except AttributeError:
            script_dir = os.getcwd()
        path = os.path.join(script_dir, 'apkpy_device_key.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return bytes.fromhex(json.load(f)['key'])
        except Exception:
            key = os.urandom(32)
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump({'key': key.hex()}, f)
            except Exception:
                pass
            return key

    def _keystream(self, k_enc, nonce, length):
        """Keystream SHA-256 em modo contador (cifra de fluxo baseada em hash)."""
        import hashlib
        out = bytearray()
        counter = 0
        while len(out) < length:
            out.extend(hashlib.sha256(k_enc + nonce + counter.to_bytes(4, 'big')).digest())
            counter += 1
        return bytes(out[:length])

    def totp(self, secret, digits=6, period=30, at=None):
        """The six digits an authenticator app shows, for a shared secret.

            crypto.totp("JBSWY3DPEHPK3PXP")     # -> "492039"

        RFC 6238: HMAC-SHA1 over the number of periods since 1970, truncated
        to `digits`. It is entirely local -- no network, no account -- which
        is why an authenticator works on a plane.

        `secret` is the base32 string a QR code carries; spaces and case are
        ignored, and missing padding is added, because that is how people
        copy them.

        `at` fixes the moment, for tests and for showing what the code was a
        few seconds ago while someone finishes typing.
        """
        import base64
        import hashlib
        import hmac
        import struct
        import time

        cleaned = str(secret or "").replace(" ", "").replace("-", "").upper()
        if not cleaned:
            return ""
        cleaned += "=" * (-len(cleaned) % 8)
        try:
            key = base64.b32decode(cleaned, casefold=True)
        except Exception:
            # Android answers "" for a secret it cannot read; matching that
            # keeps an app's handling the same on both sides.
            return ""
        # 6 to 8 is what the RFC and every authenticator use; more would
        # also overflow the 31-bit truncation the algorithm defines.
        digits = max(6, min(8, int(digits)))
        period = max(1, int(period))
        moment = int(time.time() if at is None else at)
        mac = hmac.new(key, struct.pack(">Q", moment // period),
                       hashlib.sha1).digest()
        # Dynamic truncation: the last nibble picks where to read from.
        offset = mac[-1] & 0x0F
        code = ((mac[offset] & 0x7F) << 24 | mac[offset + 1] << 16
                | mac[offset + 2] << 8 | mac[offset + 3]) % (10 ** digits)
        return str(code).zfill(digits)

    def token(self, count=16):
        """`count` random bytes as hex -- an id nobody can guess.

        Use this for session ids, one-time links and nonces. `random` is
        seeded predictably and two of its outputs give away the rest, which
        is fine for shuffling a list and useless for a secret.
        """
        import secrets

        return secrets.token_hex(max(1, min(64, int(count))))

    def hash(self, text):
        """SHA-256 of some text, as hex.

        For integrity and comparison -- has this file changed, are these two
        the same. **Not for passwords**: it is fast by design, which is
        exactly what someone guessing them wants. Use `hash_password`.
        """
        import hashlib

        return hashlib.sha256(str(text).encode("utf-8")).hexdigest()

    def hash_file(self, path):
        """SHA-256 of a file's contents, read in chunks."""
        import hashlib

        digest = hashlib.sha256()
        try:
            with open(str(path), "rb") as handle:
                for chunk in iter(lambda: handle.read(8192), b""):
                    digest.update(chunk)
        except OSError:
            # Android returns "" for a path it cannot open; matching that
            # keeps an app's error handling the same on both sides.
            return ""
        return digest.hexdigest()

    # A password-derived key uses real AES-256-GCM on both sides, so the
    # result is a standard box that openssl or any language can open. The
    # device-key path below keeps its own format, because that data never
    # leaves the phone and has nothing to be compatible with.
    PBKDF2_ROUNDS = 200000

    def _password_key(self, password, salt, rounds):
        import hashlib

        return hashlib.pbkdf2_hmac(
            "sha256", str(password).encode("utf-8"), salt, rounds, dklen=32)

    def _aesgcm(self, key):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError:
            from .diagnostics import ApkpyError

            raise ApkpyError(
                code="U2032",
                title="Password encryption needs one more package",
                message="crypto.encrypt(..., password=...) uses AES-256-GCM so "
                        "the result can be opened anywhere, and the Previewer "
                        "has no AES of its own.",
                cause="The `cryptography` package is not installed.",
                expected="pip install cryptography",
                received="ImportError: cryptography",
                suggestions=[
                    "Run: pip install cryptography",
                    "The built Android app needs nothing extra -- this is only "
                    "for running the Previewer on the desktop.",
                ],
            )
        return AESGCM(key)

    def encrypt(self, text, password=None):
        """Encripta *text*.

        With ``password=``, the key is derived from that password and the
        result is portable: encrypt on the phone, decrypt on the desktop, or
        with any tool that speaks AES-256-GCM. Nothing but the password is
        needed to open it -- and nothing but the password can.

        Without one, the device's own key is used and the value never leaves
        the phone, which is the right default for stored settings.
        """
        if password is not None:
            import os as _os

            salt = _os.urandom(16)
            nonce = _os.urandom(12)
            key = self._password_key(password, salt, self.PBKDF2_ROUNDS)
            box = self._aesgcm(key).encrypt(
                nonce, str(text).encode("utf-8"), None)
            return "pw1$%d$%s$%s$%s" % (
                self.PBKDF2_ROUNDS, salt.hex(), nonce.hex(), box.hex())
        return self._encrypt_with_device_key(text)

    def _encrypt_with_device_key(self, text):
        """Encripta *text* (ida-e-volta) com a chave do dispositivo.

        Devolve "enc1$nonce$cifrado$tag". Encrypt-then-MAC: o `decrypt`
        rejeita dados adulterados. No Android transpila para AES-256-GCM
        com chave no Android Keystore.
        """
        import hashlib
        import hmac
        key = self._device_key()
        k_enc = hashlib.sha256(b'apkpy-enc' + key).digest()
        k_mac = hashlib.sha256(b'apkpy-mac' + key).digest()
        nonce = os.urandom(16)
        data = str(text).encode('utf-8')
        ct = bytes(a ^ b for a, b in zip(data, self._keystream(k_enc, nonce, len(data))))
        tag = hmac.new(k_mac, nonce + ct, hashlib.sha256).hexdigest()
        return f"enc1${nonce.hex()}${ct.hex()}${tag}"

    def decrypt(self, stored, password=None):
        """Desencripta um valor criado por `encrypt`.

        Returns "" for anything tampered with, malformed, made on another
        device, or opened with the wrong password -- the four cases an app
        should treat the same way: do not trust it.
        """
        text = str(stored or "")
        if text.startswith("pw1$"):
            if password is None:
                return ""
            parts = text.split("$")
            if len(parts) != 5:
                return ""
            try:
                rounds = int(parts[1])
                key = self._password_key(
                    password, bytes.fromhex(parts[2]), rounds)
                return self._aesgcm(key).decrypt(
                    bytes.fromhex(parts[3]), bytes.fromhex(parts[4]),
                    None).decode("utf-8")
            except Exception:
                # A wrong password fails the GCM tag, which is the point.
                return ""
        return self._decrypt_with_device_key(text)

    def _decrypt_with_device_key(self, stored):
        """Desencripta um valor criado por `encrypt`. Devolve "" se o valor
        estiver adulterado, malformado ou tiver sido criado noutro dispositivo."""
        import hashlib
        import hmac
        try:
            marker, nonce_hex, ct_hex, tag = str(stored).split("$")
            if marker != 'enc1':
                return ""
            nonce = bytes.fromhex(nonce_hex)
            ct = bytes.fromhex(ct_hex)
        except (ValueError, AttributeError):
            return ""
        key = self._device_key()
        k_enc = hashlib.sha256(b'apkpy-enc' + key).digest()
        k_mac = hashlib.sha256(b'apkpy-mac' + key).digest()
        expected = hmac.new(k_mac, nonce + ct, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, tag):
            return ""
        data = bytes(a ^ b for a, b in zip(ct, self._keystream(k_enc, nonce, len(ct))))
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return ""


# Instância global partilhada por toda a app
crypto = CryptoAPI()


class RandomAPI:
    """Aleatoriedade exposta pela própria apkpy_lib — `from apkpy_lib import random`,
    sem precisares de importar o módulo `random` do Python.

    No previewer usa o `random` real do Python; no Android o transpilador converte
    estas chamadas para `java.util.Random` / `Math.random()`. Só as features que
    suportamos: randint, choice e random.
    """
    def randint(self, a, b):
        """Inteiro aleatório em [a, b] (ambos incluídos)."""
        return _pyrandom.randint(int(a), int(b))

    def choice(self, seq):
        """Elemento aleatório de uma lista."""
        return _pyrandom.choice(seq)

    def random(self):
        """Float aleatório em [0.0, 1.0)."""
        return _pyrandom.random()


# Instância global: `from apkpy_lib import random`
random = RandomAPI()


class DatetimeAPI:
    """Data e hora expostas pela própria apkpy_lib — `from apkpy_lib import datetime`,
    sem precisares de importar o módulo `datetime` do Python.

    No previewer usa o `datetime` real do Python; no Android o transpilador
    converte estas chamadas para `java.text.SimpleDateFormat`. Tudo devolve uma
    String (modelo "tudo é String"). Os padrões batem certo nos dois lados.

    PARIDADE: tal como o `random`, os VALORES não coincidem ao milissegundo entre
    o previewer e o Android (são dois relógios lidos em instantes diferentes) —
    mas o formato é idêntico.
    """
    def now(self):
        """Data e hora: 'AAAA-MM-DD HH:MM:SS'."""
        return _pydatetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def date(self):
        """Data de hoje: 'AAAA-MM-DD'."""
        return _pydatetime.datetime.now().strftime("%Y-%m-%d")

    def time(self):
        """Hora atual: 'HH:MM:SS'."""
        return _pydatetime.datetime.now().strftime("%H:%M:%S")

    def year(self):
        """Ano (4 dígitos), como String."""
        return _pydatetime.datetime.now().strftime("%Y")

    def month(self):
        """Mês (01-12), como String."""
        return _pydatetime.datetime.now().strftime("%m")

    def day(self):
        """Dia do mês (01-31), como String."""
        return _pydatetime.datetime.now().strftime("%d")

    def hour(self):
        """Hora (00-23), como String."""
        return _pydatetime.datetime.now().strftime("%H")

    def minute(self):
        """Minuto (00-59), como String."""
        return _pydatetime.datetime.now().strftime("%M")

    def second(self):
        """Segundo (00-59), como String."""
        return _pydatetime.datetime.now().strftime("%S")


# Instância global: `from apkpy_lib import datetime`
datetime = DatetimeAPI()


class AudioAPI:
    """Reprodução de áudio exposta pela apkpy_lib — `from apkpy_lib import audio`.

    Toca música/sons a partir de um URL (http/https, com streaming) ou de um
    ficheiro local. É a fundação para apps tipo leitor de música.

    No Android, o transpilador converte estas chamadas para
    `android.media.MediaPlayer` (streaming de URLs + ficheiros locais).

    No Hot Previewer (Windows), usa o MCI do Windows (winmm, via ctypes) — SEM
    dependências extra; suporta MP3/WAV e pause/resume/stop/seek. URLs são
    descarregados para um ficheiro temporário antes de tocar. Noutros sistemas
    operativos (ou se o MCI falhar) degrada graciosamente: imprime o que tocaria,
    para a lógica da app continuar a correr no preview.

    PARIDADE: o Android tem audio focus, reprodução com o ecrã apagado, etc. — o
    preview serve só para ouvir/testar o fluxo. O comportamento é equivalente,
    não idêntico.
    """
    def __init__(self):
        self._alias = "apkpy_audio"
        self._is_open = False
        self._tmpfiles = []
        # Estado de playlist (audio.play_playlist / next / previous)
        self._playlist = []
        self._pl_titles = []
        self._pl_artists = []
        self._pl_arts = []
        self._index = -1
        self._order = []          # ordem de reprodução (shuffle)
        self._pos = 0             # posição em _order
        self._shuffle = False
        self._repeat = 0          # 0=off, 1=tudo, 2=uma
        self._polling = False
        self._seen_playing = False
        self._manual_stop = False
        # Barra "now playing" (audio.now_playing) — componentes a atualizar ao vivo
        self._np_progress = None
        self._np_time = None
        self._np_cover = None
        self._np_title = None
        self._np_artist = None
        self._np_enabled = False
        self._np_polling = False
        # Botões de estado (audio.controls) — refletem play/pause, shuffle, repeat
        self._ctrl = None
        self._ctrl_polling = False
        # Faixa atual (mini-player fixo lê isto)
        self._cur_title = ""
        self._cur_artist = ""
        self._cur_art = ""
        self._cur_src = ""
        # Like/guardar (audio.like_button / audio.liked_list) — persiste no storage
        self._like = None
        self._like_polling = False
        self._liked_list = None
        # Playlists do utilizador (audio.playlists_list) — list_view a refrescar
        self._playlists_list = None
        # Editor de playlist (audio.playlist_editor) — list_view com as faixas da
        # playlist em edição (audio.edit_playlist); tocar numa remove-a.
        self._playlist_editor = None
        self._editing_pl_name = ""

    # ─── Backend MCI (Windows, sem dependências) ─────────────────────────────
    def _has_mci(self):
        import sys
        return sys.platform.startswith("win")

    def _mci(self, command):
        """Envia um comando ao MCI (winmm). Devolve o código de erro (0 = ok),
        ou None se o MCI não existir neste SO."""
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(255)
            return ctypes.windll.winmm.mciSendStringW(ctypes.c_wchar_p(command), buf, 254, 0)
        except Exception:
            return None

    def _mci_query(self, command):
        """Como _mci mas devolve a resposta de texto do MCI (ex.: 'status ... mode'
        → 'playing'/'paused'/'stopped'). String vazia se indisponível."""
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(255)
            ctypes.windll.winmm.mciSendStringW(ctypes.c_wchar_p(command), buf, 254, 0)
            return buf.value
        except Exception:
            return ""

    def _close(self):
        if self._is_open:
            self._mci(f"close {self._alias}")
            self._is_open = False

    def _open_and_play(self, path):
        self._close()
        # mpegvideo é o device do MCI que toca MP3 (e a maioria dos formatos)
        err = self._mci(f'open "{path}" type mpegvideo alias {self._alias}')
        if err:  # falhou — tenta deixar o MCI inferir o device (ex.: .wav)
            err = self._mci(f'open "{path}" alias {self._alias}')
        if not err:
            self._is_open = True
            self._mci(f"play {self._alias}")
        else:
            print("[audio] não consegui abrir:", path)

    def play(self, src):
        """Toca `src` (URL http/https ou caminho de ficheiro). Substitui o que
        estiver a tocar. Sai do modo playlist (é uma faixa única)."""
        self._playlist = []
        self._index = -1
        self._play_src(src)

    def _play_src(self, src):
        """Reprodução real (download-se-URL + MCI). Partilhado por play(),
        play_background() e a navegação de playlist — NÃO mexe no estado da playlist."""
        src = str(src)
        self._manual_stop = False
        self._start_np_poll()  # começa a atualizar a barra "now playing", se houver
        if not self._has_mci():
            print("[audio] (preview sem áudio neste SO) tocaria:", src)
            return
        if src.startswith("http://") or src.startswith("https://"):
            import threading

            def _download_then_play():
                try:
                    import urllib.request, tempfile, ssl, os
                    ext = os.path.splitext(src.split("?")[0])[1] or ".mp3"
                    fd, tmp = tempfile.mkstemp(suffix=ext, prefix="apkpy_audio_")
                    os.close(fd)
                    ctx = ssl._create_unverified_context()
                    with urllib.request.urlopen(src, timeout=15, context=ctx) as r, open(tmp, "wb") as f:
                        f.write(r.read())
                    self._tmpfiles.append(tmp)
                    if _app and _app.root:
                        _app.root.after(0, lambda: self._open_and_play(tmp))
                    else:
                        self._open_and_play(tmp)
                except Exception as e:
                    print("[audio] falha ao descarregar:", e)

            threading.Thread(target=_download_then_play, daemon=True).start()
        else:
            self._open_and_play(src)

    def play_background(self, src, title=None, artist=None, art=None):
        """[Android] Toca em SEGUNDO PLANO: continua com o ecrã apagado e mostra
        controlos na notificação/lockscreen (foreground media service). `title`,
        `artist` e `art` (URL da capa) aparecem na notificação/lockscreen.

        No preview (Windows) não há lockscreen — toca igual ao `play()`, mostra o
        que estaria a tocar na consola e atualiza a capa do now_playing se houver.
        PARIDADE: o som é o mesmo; o background/lockscreen são exclusivos do Android."""
        _label = title or "(sem título)"
        _line = f"[audio] background: {_label}"
        if artist:
            _line += f" — {artist}"
        print(_line)
        # guarda a faixa atual (mini-player lê isto)
        self._cur_title = title or ""
        self._cur_artist = artist or ""
        self._cur_art = art or ""
        self._cur_src = str(src)
        self.play(src)
        self._set_cover(art)

    def _set_cover(self, url):
        """Atualiza a capa do now_playing (componente image), se houver."""
        if self._np_cover is not None and url:
            try:
                self._np_cover.set_src(url)
            except Exception:
                pass

    def pause(self):
        """Pausa a reprodução (mantém a posição)."""
        if self._has_mci() and self._is_open:
            self._mci(f"pause {self._alias}")

    def resume(self):
        """Retoma a reprodução depois de um pause()."""
        if self._has_mci() and self._is_open:
            self._mci(f"resume {self._alias}")
        elif self._playlist and 0 <= self._index < len(self._playlist):
            # The queue ended: play the track on screen again, as the phone's
            # media service does.
            self._play_current()

    def stop(self):
        """Pára a reprodução e liberta o leitor."""
        self._manual_stop = True
        self._cur_title = ""   # mini-player esconde-se
        self._cur_artist = ""
        self._cur_art = ""
        self._cur_src = ""
        if self._has_mci():
            self._close()

    def seek(self, seconds):
        """Salta para `seconds` segundos e continua a tocar."""
        if self._has_mci() and self._is_open:
            try:
                ms = int(float(seconds) * 1000)
            except Exception:
                ms = 0
            self._mci(f"play {self._alias} from {ms}")

    # ─── Playlist (audio.play_playlist / next / previous) ────────────────────
    def play_playlist(self, sources, titles=None, artists=None, arts=None, start=0):
        """Toca uma FILA de faixas. `sources` é a lista de URLs/ficheiros;
        `titles`/`artists`/`arts` (URLs de capa) são listas paralelas (opcionais).
        Avança sozinha quando uma faixa acaba; usa next()/previous() p/ saltar.

        No Android isto vira o foreground media service em modo playlist (com
        botões ⏮⏭ e capa na notificação/lockscreen). No preview toca pela mesma via
        do play(), avança por sondagem do MCI e atualiza a capa do now_playing."""
        self._playlist = [str(s) for s in (sources or [])]
        self._pl_titles = [str(t) for t in (titles or [])]
        self._pl_artists = [str(a) for a in (artists or [])]
        self._pl_arts = [str(a) for a in (arts or [])]
        # start aceita um índice (0,1,…) OU o src de uma faixa — neste caso
        # procura-o na fila (tap-to-play num carrossel arranca a fila nessa faixa).
        if isinstance(start, str) and start in self._playlist:
            self._index = self._playlist.index(start)
        else:
            try:
                self._index = int(start)
            except (ValueError, TypeError):
                self._index = 0
        if not (0 <= self._index < len(self._playlist)):
            self._index = 0 if self._playlist else -1
        self._build_order_keep_current()
        if self._index >= 0:
            self._play_current()
            self._start_poll()

    def _build_order_keep_current(self):
        """Constrói a ordem (sequencial ou baralhada) mantendo a faixa atual."""
        n = len(self._playlist)
        self._order = list(range(n))
        if self._shuffle and n > 1:
            _pyrandom.shuffle(self._order)
        self._pos = 0
        for k, idx in enumerate(self._order):
            if idx == self._index:
                self._pos = k
                break

    def shuffle(self):
        """Liga/desliga o modo aleatório (mantém a faixa atual a tocar)."""
        self._shuffle = not self._shuffle
        if self._playlist:
            self._build_order_keep_current()

    def repeat(self):
        """Cicla o modo de repetição: off → tudo → uma → off."""
        self._repeat = (self._repeat + 1) % 3

    def next(self):
        """Salta para a faixa seguinte na ordem (dá a volta no fim)."""
        if not self._playlist or not self._order:
            return
        self._pos = (self._pos + 1) % len(self._order)
        self._index = self._order[self._pos]
        self._play_current()

    def previous(self):
        """Volta à faixa anterior na ordem (dá a volta no início)."""
        if not self._playlist or not self._order:
            return
        self._pos = (self._pos - 1) % len(self._order)
        self._index = self._order[self._pos]
        self._play_current()

    def _advance(self):
        """Auto-advance no fim de uma faixa — respeita o repeat."""
        if not self._playlist or not self._order:
            return
        n = len(self._order)
        if self._pos + 1 >= n:
            if self._repeat == 1:   # repeat-tudo → volta ao início
                self._pos = 0
            else:                    # repeat-off → pára no fim da fila
                # The last track stays on screen (mini-player, now playing)
                # and play starts it again, as on the phone; stop() cleared
                # it and the mini-player vanished on the desktop only.
                self._manual_stop = True
                if self._has_mci():
                    self._close()
                return
        else:
            self._pos += 1
        self._index = self._order[self._pos]
        self._play_current()

    def _play_current(self):
        if not (0 <= self._index < len(self._playlist)):
            return
        title = self._pl_titles[self._index] if self._index < len(self._pl_titles) else ""
        artist = self._pl_artists[self._index] if self._index < len(self._pl_artists) else ""
        _line = f"[audio] playlist [{self._index + 1}/{len(self._playlist)}]: {title or '(sem título)'}"
        if artist:
            _line += f" — {artist}"
        print(_line)
        art = self._pl_arts[self._index] if self._index < len(self._pl_arts) else ""
        # guarda a faixa atual (mini-player lê isto)
        self._cur_title = title or ""
        self._cur_artist = artist or ""
        self._cur_art = art or ""
        self._cur_src = str(self._playlist[self._index])
        self._seen_playing = False
        self._play_src(self._playlist[self._index])
        self._set_cover(art)

    def _start_poll(self):
        if self._polling:
            return
        self._polling = True
        self._poll()

    def _poll(self):
        # Avança a playlist quando a faixa atual termina (MCI mode 'stopped' depois
        # de ter estado 'playing'). Só no preview; no Android é o onCompletion.
        if not self._playlist or self._index < 0:
            self._polling = False
            return
        mode = self._mci_query(f"status {self._alias} mode") if (self._has_mci() and self._is_open) else ""
        if mode == "playing":
            self._seen_playing = True
        elif mode == "stopped" and self._seen_playing and not self._manual_stop:
            self._seen_playing = False
            if self._repeat == 2:    # repeat-uma → repete a faixa
                self._play_current()
            else:                     # off/tudo → próxima (ou pára)
                self._advance()
        if _app and _app.root:
            _app.root.after(700, self._poll)
        else:
            self._polling = False

    # ─── Barra "now playing" (audio.now_playing) ─────────────────────────────
    def now_playing(self, progress=None, time=None, cover=None, title=None, artist=None):
        """Liga um slider (range), um label de tempo e/ou uma imagem de capa à
        reprodução: ficam a seguir a música ao vivo. Arrastar a bola e largar faz
        SEEK (salta a música para essa posição) — no Android via media service, no
        preview via MCI. A capa atualiza-se quando a faixa muda. `title`/`artist`
        são labels que passam a mostrar o nome/artista da faixa atual (ecrã
        "Now Playing" em grande)."""
        self._np_progress = progress
        self._np_time = time
        self._np_cover = cover
        self._np_title = title
        self._np_artist = artist
        self._np_enabled = True
        # Arrastar+largar a bola → seek. O slider chama _on_release(valor 0-100).
        if progress is not None:
            progress._on_release = self._np_seek

    def _np_seek(self, value_0_100):
        """Salta a reprodução para a posição (0-100%) escolhida no slider."""
        if not (self._has_mci() and self._is_open):
            return
        dur_s = self._mci_query(f"status {self._alias} length")
        dur = int(dur_s) if dur_s.isdigit() else 0
        if dur > 0:
            target_ms = max(0.0, min(100.0, float(value_0_100))) / 100.0 * dur
            self.seek(target_ms / 1000.0)

    @staticmethod
    def _fmt_ms(ms):
        s = max(0, int(ms)) // 1000
        return f"{s // 60}:{s % 60:02d}"

    def _start_np_poll(self):
        if not self._np_enabled or self._np_polling:
            return
        self._np_polling = True
        self._np_poll()

    def _np_poll(self):
        try:
            # título/artista da faixa atual (não depende do MCI estar aberto)
            if self._np_title is not None and self._cur_title:
                try:
                    self._np_title.set_value(self._cur_title)
                except Exception:
                    pass
            if self._np_artist is not None and self._cur_title:
                try:
                    self._np_artist.set_value(self._cur_artist)
                except Exception:
                    pass
            loaded = self._has_mci() and self._is_open
            if not loaded and getattr(self, '_np_last_dur', 0):
                # Nothing loaded (the queue ended, or stopped): back to the
                # start with the last track's length, as the phone shows it.
                if not getattr(self, '_np_rested', False):
                    self._np_rested = True
                    if self._np_time is not None:
                        try:
                            self._np_time.set_value(
                                f"{self._fmt_ms(0)} / {self._fmt_ms(self._np_last_dur)}")
                        except Exception:
                            pass
                    if self._np_progress is not None and not getattr(
                            self._np_progress, '_dragging', False):
                        try:
                            self._np_progress.set_value(0)
                        except Exception:
                            pass
            if loaded:
                pos_s = self._mci_query(f"status {self._alias} position")
                dur_s = self._mci_query(f"status {self._alias} length")
                pos = int(pos_s) if pos_s.isdigit() else 0
                dur = int(dur_s) if dur_s.isdigit() else 0
                if dur > 0:
                    self._np_last_dur = dur
                    self._np_rested = False
                    if self._np_time is not None:
                        try:
                            self._np_time.set_value(f"{self._fmt_ms(pos)} / {self._fmt_ms(dur)}")
                        except Exception:
                            pass
                    # NÃO mexer na bola enquanto o utilizador a arrasta (senão
                    # salta de volta); o seek acontece ao largar (_np_seek).
                    if self._np_progress is not None and not getattr(self._np_progress, '_dragging', False):
                        try:
                            # fração (não inteiro) → a bola desliza suave
                            self._np_progress.set_value(pos * 100.0 / dur)
                        except Exception:
                            pass
        except Exception:
            pass
        # sondagem frequente (~8x/s) p/ o movimento ser suave, não aos saltos
        if _app and _app.root:
            _app.root.after(120, self._np_poll)
        else:
            self._np_polling = False

    # ─── Botões de estado (audio.controls) ───────────────────────────────────
    def controls(self, play_pause=None, shuffle=None, repeat=None,
                 play_text="Play", pause_text="Pause",
                 shuffle_on="Shuffle: on", shuffle_off="Shuffle: off",
                 repeat_off="Repeat: off", repeat_all="Repeat: all",
                 repeat_one="Repeat: one"):
        """Faz botões REFLETIREM o estado do leitor: o play/pause mostra o
        estado e clicar alterna; o shuffle mostra on/off; o repeat off/all/one.

        A button with an icon and no text is an icon button, as every player
        draws them: play_arrow and pause swap, and shuffle and repeat light up
        in the button's ``active-color`` (repeat_one for one track). The texts
        used to default to Portuguese with emoji, which the Previewer drew as
        empty circles. No Android a Activity sonda o media service; no preview
        sondamos o MCI."""
        self._ctrl = {
            'play_pause': play_pause, 'shuffle': shuffle, 'repeat': repeat,
            'play_text': play_text, 'pause_text': pause_text,
            'shuffle_on': shuffle_on, 'shuffle_off': shuffle_off,
            'repeat_off': repeat_off, 'repeat_all': repeat_all, 'repeat_one': repeat_one,
        }
        # O play/pause passa a ALTERNAR (clicar pausa/retoma) — o comando é nosso.
        if play_pause is not None:
            play_pause._dynamic_command = self._toggle_play
        # Shuffle and repeat did nothing when tapped unless the app wrote
        # command=audio.shuffle itself -- the media guide's own example did
        # not. A button with a command of its own keeps it.
        if shuffle is not None and not shuffle.kwargs.get('command'):
            shuffle._dynamic_command = self.shuffle
        if repeat is not None and not repeat.kwargs.get('command'):
            repeat._dynamic_command = self.repeat

    def _toggle_play(self):
        mode = self._mci_query(f"status {self._alias} mode") if (self._has_mci() and self._is_open) else ""
        if mode == "playing":
            self.pause()
        else:
            self.resume()

    def _is_playing(self):
        if not (self._has_mci() and self._is_open):
            return False
        return self._mci_query(f"status {self._alias} mode") == "playing"

    def _start_ctrl_poll(self):
        if not self._ctrl or self._ctrl_polling:
            return
        self._ctrl_polling = True
        self._ctrl_poll()

    def _ctrl_poll(self):
        c = self._ctrl or {}
        try:
            def _set(comp, text, icon=None, lit=False):
                if comp is None:
                    return
                if _is_icon_button(comp):
                    comp._dynamic_icon = icon or comp.kwargs.get('icon')
                    comp._dynamic_icon_color = (
                        _merge_with_body(comp.kwargs.get('comp_id'), 'button')
                        .get('active-color') or global_styles.get('__theme__', {})
                        .get('primary', '#1DB954')) if lit else None
                else:
                    comp._dynamic_text = (lambda t=text: t)
                if getattr(comp, '_refresh_btn', None):
                    comp._refresh_btn()
            if c.get('play_pause') is not None:
                playing = self._is_playing()
                _set(c['play_pause'], c['pause_text'] if playing else c['play_text'],
                     'pause' if playing else 'play_arrow')
            if c.get('shuffle') is not None:
                _set(c['shuffle'], c['shuffle_on'] if self._shuffle else c['shuffle_off'],
                     'shuffle', lit=bool(self._shuffle))
            if c.get('repeat') is not None:
                # _repeat: 0=off, 1=tudo, 2=uma
                _set(c['repeat'], (c['repeat_off'], c['repeat_all'], c['repeat_one'])[self._repeat],
                     'repeat_one' if self._repeat == 2 else 'repeat', lit=self._repeat > 0)
        except Exception:
            pass
        if _app and _app.root:
            _app.root.after(300, self._ctrl_poll)
        else:
            self._ctrl_polling = False

    # ─── Like / Guardar (audio.like_button / audio.liked_list) ───────────────
    # As músicas guardadas persistem no `storage` (key "apkpy_liked") — uma lista
    # de {title, subtitle, image, src}. No Android é SharedPreferences "apkpy_fav".
    _LIKED_KEY = "apkpy_liked"

    def _liked_load(self):
        v = storage.get(self._LIKED_KEY, [])
        return [i for i in v if isinstance(i, dict)] if isinstance(v, list) else []

    @staticmethod
    def _track_key(title, artist):
        return f"{title}{artist}"

    def is_liked(self):
        """True se a faixa que está a tocar está guardada nos favoritos."""
        if not self._cur_title:
            return False
        k = self._track_key(self._cur_title, self._cur_artist)
        return any(self._track_key(i.get('title', ''), i.get('subtitle', '')) == k
                   for i in self._liked_load())

    def toggle_like(self):
        """Guarda/remove a faixa atual dos favoritos (persiste no storage)."""
        if not self._cur_title and not self._cur_src:
            return
        k = self._track_key(self._cur_title, self._cur_artist)
        items = self._liked_load()
        if any(self._track_key(i.get('title', ''), i.get('subtitle', '')) == k for i in items):
            items = [i for i in items
                     if self._track_key(i.get('title', ''), i.get('subtitle', '')) != k]
        else:
            items.append({'title': self._cur_title, 'subtitle': self._cur_artist,
                          'image': self._cur_art, 'src': self._cur_src})
        storage.set(self._LIKED_KEY, items)
        self._refresh_like_btn()
        self._refresh_liked_list()

    def like_button(self, button, liked="Liked", unliked="Like"):
        """Liga um botão ao like da faixa atual: clicar guarda/remove a faixa, e o
        botão reflete o estado. Persiste no storage. No Android a Activity sonda o
        media service e escreve em SharedPreferences, tal como audio.controls.

        An icon button (an icon, no text) swaps favorite_border for favorite in
        its ``active-color``. The defaults were emoji hearts, which the
        Previewer drew as empty circles."""
        self._like = {'btn': button, 'liked': liked, 'unliked': unliked}
        if button is not None:
            button._dynamic_command = self.toggle_like
        self._start_like_poll()

    def liked_list(self, list_view):
        """Liga um list_view à lista de músicas guardadas: enche-o a partir do
        storage e mantém-no atualizado quando dás like/unlike. Use rich=True +
        on_click=lambda item: audio.play_background(item["src"], ...) p/ tap-to-play."""
        self._liked_list = list_view
        self._refresh_liked_list()

    def _refresh_like_btn(self):
        c = self._like
        if not c or c.get('btn') is None:
            return
        try:
            is_liked = self.is_liked()
            if _is_icon_button(c['btn']):
                c['btn']._dynamic_icon = 'favorite' if is_liked else 'favorite_border'
                c['btn']._dynamic_icon_color = (
                    _merge_with_body(c['btn'].kwargs.get('comp_id'), 'button')
                    .get('active-color') or '#1DB954') if is_liked else None
            else:
                txt = c['liked'] if is_liked else c['unliked']
                c['btn']._dynamic_text = (lambda t=txt: t)
            if getattr(c['btn'], '_refresh_btn', None):
                c['btn']._refresh_btn()
        except Exception:
            # o botão pode ter sido destruído ao mudar de ecrã — ignora.
            pass

    def _refresh_liked_list(self):
        if self._liked_list is not None:
            try:
                self._liked_list.set_items(self._liked_load())
            except Exception:
                pass

    def _start_like_poll(self):
        if not self._like or self._like_polling:
            return
        self._like_polling = True
        self._like_poll()

    def _like_poll(self):
        self._refresh_like_btn()
        if _app and _app.root:
            _app.root.after(400, self._like_poll)
        else:
            self._like_polling = False

    # ─── Playlists do utilizador (criar/gerir) ───────────────────────────────
    # Guardadas no storage (key "apkpy_playlists") como { nome: [ {track}, ... ] }.
    # No Android é SharedPreferences "apkpy_pl".
    _PL_KEY = "apkpy_playlists"

    def _pl_load(self):
        v = storage.get(self._PL_KEY, {})
        return v if isinstance(v, dict) else {}

    def add_to_playlist(self, name, item=None):
        """Adiciona uma faixa à playlist `name` (cria-a se não existir). Sem `item`,
        adiciona a faixa A TOCAR; com `item` (dict de uma lista/carousel), adiciona
        essa. Persiste no storage; ignora duplicados e nomes vazios."""
        name = str(name or "").strip()
        if not name:
            print("[audio] playlist: escreve o nome da playlist")
            return
        if item is not None:
            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except ValueError:
                    item = {}
            track = {'title': str(item.get('title', '')), 'subtitle': str(item.get('subtitle', '')),
                     'image': str(item.get('image', '')), 'src': str(item.get('src', ''))}
        else:
            if not self._cur_title:
                print("[audio] toca uma música primeiro")
                return
            track = {'title': self._cur_title, 'subtitle': self._cur_artist,
                     'image': self._cur_art, 'src': self._cur_src}
        if not track['title']:
            return
        pls = self._pl_load()
        arr = list(pls.get(name, []))
        k = self._track_key(track['title'], track['subtitle'])
        if any(self._track_key(t.get('title', ''), t.get('subtitle', '')) == k
               for t in arr if isinstance(t, dict)):
            print(f"[audio] já está em {name}")
            return
        arr.append(track)
        pls[name] = arr
        storage.set(self._PL_KEY, pls)
        print(f"[audio] adicionada a {name}: {track['title']}")
        self._refresh_playlists_list()

    def play_saved_playlist(self, name):
        """Toca as faixas de uma playlist guardada como uma fila (com ⏮⏭)."""
        arr = [t for t in self._pl_load().get(str(name), []) if isinstance(t, dict)]
        if not arr:
            return
        self.play_playlist(
            sources=[t.get('src', '') for t in arr],
            titles=[t.get('title', '') for t in arr],
            artists=[t.get('subtitle', '') for t in arr],
            arts=[t.get('image', '') for t in arr])

    def playlists_list(self, list_view):
        """Liga um list_view à lista de PLAYLISTS do utilizador (nome + nº de faixas).
        Use on_click=lambda item: audio.play_saved_playlist(item["title"]) p/ tocar."""
        self._playlists_list = list_view
        self._refresh_playlists_list()

    def _refresh_playlists_list(self):
        if self._playlists_list is None:
            return
        items = []
        for name, tracks in self._pl_load().items():
            tracks = tracks if isinstance(tracks, list) else []
            n = len(tracks)
            cover = tracks[0].get('image', '') if (tracks and isinstance(tracks[0], dict)) else ''
            items.append({'title': name,
                          'subtitle': f"{n} música" + ("" if n == 1 else "s"),
                          'image': cover})
        try:
            self._playlists_list.set_items(items)
        except Exception:
            pass

    def edit_playlist(self, name):
        """Define qual a playlist em edição e enche o list_view ligado por
        audio.playlist_editor() com as suas faixas (tocar numa remove-a)."""
        self._editing_pl_name = str(name or "").strip()
        self._refresh_playlist_editor()

    def remove_from_playlist(self, name, item=None):
        """Remove uma faixa (por title+subtitle) da playlist `name`. `item` é o dict
        da faixa (de uma lista/carousel) ou o JSON dela. Persiste no storage."""
        name = str(name or "").strip()
        if not name:
            return
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except ValueError:
                item = {}
        item = item or {}
        k = self._track_key(str(item.get('title', '')), str(item.get('subtitle', '')))
        pls = self._pl_load()
        arr = [t for t in pls.get(name, []) if isinstance(t, dict)]
        new_arr = [t for t in arr
                   if self._track_key(t.get('title', ''), t.get('subtitle', '')) != k]
        if len(new_arr) == len(arr):
            return
        pls[name] = new_arr
        storage.set(self._PL_KEY, pls)
        print(f"[audio] removida de {name}: {item.get('title', '')}")
        self._refresh_playlist_editor()
        self._refresh_playlists_list()

    def delete_playlist(self, name):
        """Apaga a playlist `name` inteira. Persiste no storage."""
        name = str(name or "").strip()
        if not name:
            return
        pls = self._pl_load()
        if name not in pls:
            print(f"[audio] playlist não encontrada: {name}")
            return
        del pls[name]
        storage.set(self._PL_KEY, pls)
        print(f"[audio] playlist apagada: {name}")
        if name == self._editing_pl_name:
            self._editing_pl_name = ""
        self._refresh_playlist_editor()
        self._refresh_playlists_list()

    def playlist_editor(self, list_view):
        """Liga um list_view que mostra as faixas da playlist em edição
        (audio.edit_playlist). Use on_click=lambda item:
        audio.remove_from_playlist(<nome>, item) p/ remover ao tocar."""
        self._playlist_editor = list_view
        self._refresh_playlist_editor()

    def _refresh_playlist_editor(self):
        if self._playlist_editor is None:
            return
        name = self._editing_pl_name
        tracks = [t for t in self._pl_load().get(name, []) if isinstance(t, dict)] if name else []
        items = [{'title': t.get('title', ''), 'subtitle': t.get('subtitle', ''),
                  'image': t.get('image', ''), 'src': t.get('src', '')} for t in tracks]
        try:
            self._playlist_editor.set_items(items)
        except Exception:
            pass


# Instância global: `from apkpy_lib import audio`
audio = AudioAPI()


class FilesAPI:
    """Download de ficheiros para disco — `from apkpy_lib import files`.

    É o que torna a música (ou qualquer media) OFFLINE: descarrega um URL para um
    ficheiro local e depois toca-se com `audio.play(files.path(nome))`, sem rede.

    Fluxo típico (Spotify offline):

        if files.exists("song1.mp3"):
            audio.play(files.path("song1.mp3"))     # já está em disco
        else:
            files.download(URL, "song1.mp3", on_result=guardado)

        def guardado(ok, caminho):
            if ok:
                audio.play(caminho)

    No Android, `download` corre numa thread e escreve em `getFilesDir()` (a pasta
    privada da app); `path`/`exists`/`delete` operam sobre essa mesma pasta. No
    preview (Python) usa-se `~/.apkpy/files/` — os ficheiros PERSISTEM entre
    execuções, tal como no telemóvel.

    O callback de `download` recebe `(sucesso, caminho)` — o mesmo formato dos
    callbacks da câmara/galeria.
    """
    def _dir(self):
        import os
        d = os.path.join(os.path.expanduser("~"), ".apkpy", "files")
        os.makedirs(d, exist_ok=True)
        return d

    def path(self, name):
        """Caminho absoluto local para `name` (exista ou não ainda)."""
        import os
        return os.path.join(self._dir(), str(name))

    def exists(self, name):
        """True se `name` já foi descarregado para disco."""
        import os
        return os.path.exists(self.path(name))

    def read(self, name):
        """The text of one of the app's own files, or ``""`` when there is no
        such file.

        ``name`` is a file in the app's folder -- ``"notes.txt"``,
        ``"drafts/monday.txt"`` -- or the whole path ``files.path()`` and
        ``files.download()`` answer. The text is UTF-8, exactly as written.
        """
        from .features import kit as _kit
        return _kit.read(name)

    def write(self, name, text):
        """Keep ``text`` as the file ``name`` in the app's own folder, in
        place of what was there; folders in the name are made as needed.

        Answers ``"ok"``, ``"invalid"`` when ``name`` is not the name of a
        file in the app's folder, or ``"failed"``. The file is replaced whole
        or not at all.
        """
        from .features import kit as _kit
        return _kit.write(name, text)

    def append(self, name, text):
        """Add ``text`` to the end of the file ``name``, making the file if
        there is none. Answers as ``write()`` does."""
        from .features import kit as _kit
        return _kit.append(name, text)

    def save_as(self, name, text, mime="text/plain", on_result=None):
        """Ask the person where, and write this text there.

        An app's own folder is invisible to its owner. This opens the system's
        picker -- Downloads, a drive, a card -- and writes the file where the
        person chose; ``on_result(ok, name)`` hears the name it ended up with,
        or ``"cancelled"``. In the Previewer it is the desktop's Save dialog.
        """
        from .features import kit as _kit
        return _kit.save_as(name, text, mime, on_result)

    def save_copy(self, path, name="", on_result=None):
        """Ask the person where, and copy one of the app's files there --
        a recording, a download, anything ``files.path()`` names."""
        from .features import kit as _kit
        return _kit.save_copy(path, name, on_result)

    def delete(self, name):
        """Apaga o ficheiro local `name` (liberta espaço)."""
        import os
        try:
            os.remove(self.path(name))
        except OSError:
            pass

    def download(self, url, name, on_result=None):
        """Descarrega `url` para o ficheiro local `name`. Quando termina, chama
        `on_result(sucesso, caminho)`. Não bloqueia a interface (corre numa thread).

        Dentro de um background_job descarrega ali mesmo e responde antes da
        linha seguinte -- o Worker do telemóvel faz o mesmo
        (`_filesDownloadNow`), porque já corre fora da interface.
        """
        import threading

        if _job_rules.inside_job():
            ok, p = self._download_now(url, name)
            if on_result:
                on_result(ok, p)
            return

        def _run():
            ok, p = self._download_now(url, name)
            if on_result:
                if _app and _app.root:
                    _app.root.after(0, lambda: on_result(ok, p))
                else:
                    on_result(ok, p)

        threading.Thread(target=_run, daemon=True).start()

    def _download_now(self, url, name):
        """(sucesso, caminho) -- caminho "" quando falha, como no telemóvel."""
        try:
            import urllib.request, ssl
            p = self.path(name)
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request(str(url), headers={'User-Agent': 'ApkPyPreviewer'})
            with urllib.request.urlopen(req, timeout=20, context=ctx) as r, open(p, "wb") as f:
                f.write(r.read())
            return True, p
        except Exception as e:
            print("[files] download failed:", e)
            return False, ""

    def pick(self, on_result=None, types=None, title="Choose a file"):
        """Ask the user for a file of any type.

        ``on_result`` receives ``(success, path, name, size, mime)``.  Filter
        with ``types=["pdf", "docx"]`` or a MIME family such as
        ``types=["image/*"]``; the filter is advisory, because many Android
        document providers ignore it.

        ``path`` is an opaque handle: a real path here, a ``content://`` Uri on
        Android.  Pass it to ``uploads.*`` and read ``name``/``size``/``mime``
        instead of parsing it.  It is not managed by
        ``path()``/``exists()``/``delete()``, which address the app's own
        folder.
        """
        from .features.file_picker import pick as _pick

        return _pick(on_result=on_result, types=types, title=title)


# Instância global: `from apkpy_lib import files`
files = FilesAPI()


class UploadsAPI:
    """Uploads multipart em streaming — ``from apkpy_lib import uploads``.

    A mesma API envia ficheiros, imagens, áudio ou vídeo. O ``task_id`` é
    explícito para permitir cancelamento sem depender de valores de retorno que
    não existem no Java gerado.

    Exemplo::

        uploads.multipart(
            "avatar",
            "https://api.example.com/upload",
            caminho,
            field="photo",
            fields={"caption": "Night drive"},
            headers={"Authorization": "Bearer token"},
            on_progress=progresso,  # (percent, sent, total)
            on_result=terminou,     # (success, response)
        )
        uploads.cancel("avatar")
    """
    def __init__(self):
        import threading
        self._lock = threading.Lock()
        self._cancel_events = {}
        self._connections = {}

    @staticmethod
    def _deliver(callback, *args):
        if callback is None:
            return
        instance = getattr(_app, '_instance', None)
        root = getattr(instance, 'root', None) if instance is not None else None
        if root is not None:
            try:
                root.after(0, lambda: callback(*args))
                return
            except Exception:
                pass
        callback(*args)

    @staticmethod
    def _part(boundary, name, value):
        safe_name = str(name).replace('"', '').replace('\r', '').replace('\n', '')
        return (
            f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="{safe_name}"\r\n\r\n'
            f'{value}\r\n'
        ).encode('utf-8')

    def cancel(self, task_id):
        """Cancela imediatamente o upload com este ID."""
        key = str(task_id)
        with self._lock:
            event = self._cancel_events.get(key)
            connection = self._connections.get(key)
        if event is not None:
            event.set()
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def multipart(self, task_id, url, path, field="file", fields=None,
                  headers=None, content_type=None, on_progress=None,
                  on_result=None):
        """Envia um ficheiro multipart sem o carregar inteiro para a memória.

        ``on_progress`` recebe ``(percent, bytes_sent, total_bytes)``.
        ``on_result`` recebe ``(success, response)``; um cancelamento devolve
        ``False, "cancelled"``.
        """
        import http.client
        import mimetypes
        import os
        import ssl
        import threading
        import urllib.parse
        import uuid

        key = str(task_id or f"upload-{uuid.uuid4().hex}")
        self.cancel(key)
        cancelled = threading.Event()
        with self._lock:
            self._cancel_events[key] = cancelled

        def _run():
            connection = None
            try:
                source_path = os.path.abspath(os.path.expanduser(str(path)))
                if not os.path.isfile(source_path):
                    raise FileNotFoundError(source_path)
                file_size = os.path.getsize(source_path)
                filename = os.path.basename(source_path) or "upload.bin"
                mime = (
                    str(content_type).strip()
                    if content_type else
                    (mimetypes.guess_type(filename)[0] or "application/octet-stream")
                )
                boundary = f"----ApkPy{uuid.uuid4().hex}"
                prefix = bytearray()
                for name, value in (fields or {}).items():
                    prefix.extend(self._part(boundary, name, value))
                safe_field = (
                    str(field or "file").replace('"', '')
                    .replace('\r', '').replace('\n', '')
                )
                safe_filename = (
                    filename.replace('"', '').replace('\r', '').replace('\n', '')
                )
                prefix.extend((
                    f'--{boundary}\r\n'
                    f'Content-Disposition: form-data; name="{safe_field}"; '
                    f'filename="{safe_filename}"\r\n'
                    f'Content-Type: {mime}\r\n\r\n'
                ).encode('utf-8'))
                suffix = f'\r\n--{boundary}--\r\n'.encode('utf-8')

                parsed = urllib.parse.urlsplit(str(url))
                if parsed.scheme not in ("http", "https") or not parsed.hostname:
                    raise ValueError("upload URL must use http:// or https://")
                target = parsed.path or "/"
                if parsed.query:
                    target += "?" + parsed.query
                port = parsed.port
                if parsed.scheme == "https":
                    connection = http.client.HTTPSConnection(
                        parsed.hostname, port=port, timeout=30,
                        context=ssl.create_default_context(),
                    )
                else:
                    connection = http.client.HTTPConnection(
                        parsed.hostname, port=port, timeout=30,
                    )
                with self._lock:
                    self._connections[key] = connection
                request_headers = {
                    "User-Agent": "ApkPyPreviewer",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Content-Length": str(len(prefix) + file_size + len(suffix)),
                }
                if isinstance(headers, dict):
                    # A boundary e o tamanho pertencem ao encoder. Permitir que
                    # headers do utilizador os substituam cria corpos multipart
                    # inválidos e pode deixar o servidor à espera de mais bytes.
                    for name, value in headers.items():
                        header_name = str(name)
                        if header_name.lower() in (
                            "content-type", "content-length",
                        ):
                            continue
                        request_headers[header_name] = str(value)
                connection.putrequest("POST", target)
                for name, value in request_headers.items():
                    connection.putheader(name, value)
                connection.endheaders()
                connection.send(prefix)

                sent = 0
                last_percent = -1
                # Android hands the callback three Strings, so the Previewer
                # does too: an app written against one runtime must not break
                # on the other.  Use int(percent) to compare.
                self._deliver(on_progress, "0", "0", str(file_size))
                with open(source_path, "rb") as source:
                    while True:
                        if cancelled.is_set():
                            raise InterruptedError("cancelled")
                        chunk = source.read(65536)
                        if not chunk:
                            break
                        connection.send(chunk)
                        sent += len(chunk)
                        percent = (
                            min(100, int(sent * 100 / file_size))
                            if file_size > 0 else 100
                        )
                        if percent != last_percent:
                            last_percent = percent
                            self._deliver(
                                on_progress, str(percent), str(sent),
                                str(file_size),
                            )
                if cancelled.is_set():
                    raise InterruptedError("cancelled")
                if file_size == 0 or last_percent < 100:
                    self._deliver(
                        on_progress, "100", str(sent), str(file_size),
                    )
                connection.send(suffix)
                response = connection.getresponse()
                body = response.read().decode('utf-8', errors='replace')
                ok = 200 <= response.status < 300
                result_text = (
                    body if ok else
                    f"HTTP {response.status}" + (f": {body}" if body else "")
                )
                if not ok:
                    print(
                        f"[uploads] servidor rejeitou '{key}': "
                        f"{result_text[:500]}"
                    )
                self._deliver(on_result, ok, result_text)
            except Exception as exc:
                message = (
                    "cancelled"
                    if cancelled.is_set() or isinstance(exc, InterruptedError)
                    else str(exc)
                )
                if message != "cancelled":
                    print(f"[uploads] falha em '{key}': {message}")
                self._deliver(on_result, False, message)
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass
                with self._lock:
                    if self._cancel_events.get(key) is cancelled:
                        self._cancel_events.pop(key, None)
                    if self._connections.get(key) is connection:
                        self._connections.pop(key, None)

        threading.Thread(
            target=_run, name=f"apkpy-upload-{key}", daemon=True,
        ).start()
        return key

    def file(self, *args, **kwargs):
        """Alias semântico de :meth:`multipart` para ficheiros genéricos."""
        return self.multipart(*args, **kwargs)

    def image(self, *args, **kwargs):
        """Alias semântico de :meth:`multipart` para imagens."""
        return self.multipart(*args, **kwargs)

    def audio(self, *args, **kwargs):
        """Alias semântico de :meth:`multipart` para áudio."""
        return self.multipart(*args, **kwargs)

    def video(self, *args, **kwargs):
        """Alias semântico de :meth:`multipart` para vídeo."""
        return self.multipart(*args, **kwargs)


uploads = UploadsAPI()


# ─── AppsAPI (inspeção de apps instaladas) ────────────────────────────────────
# No Android usa o PackageManager. No desktop NÃO há esse conceito, por isso o
# preview devolve dados DEMO representativos (para a lógica da app — listas,
# extract, hash — funcionar e poder ser testada visualmente). Os callbacks
# recebem uma String JSON, igual ao Android (paridade).

_APPS_DEMO = [
    {"name": "Câmara",     "package": "com.android.camera2",        "version": "13.2", "system": True,  "perms": 7},
    {"name": "Chrome",     "package": "com.android.chrome",         "version": "126.0", "system": False, "perms": 12},
    {"name": "Definições", "package": "com.android.settings",       "version": "14",    "system": True,  "perms": 21},
    {"name": "Instagram",  "package": "com.instagram.android",      "version": "340.0", "system": False, "perms": 34},
    {"name": "Maps",       "package": "com.google.android.apps.maps","version": "11.132","system": False, "perms": 18},
    {"name": "Relógio",    "package": "com.android.deskclock",      "version": "8.1",   "system": True,  "perms": 5},
    {"name": "Spotify",    "package": "com.spotify.music",          "version": "8.9",   "version_alt": "", "system": False, "perms": 23},
    {"name": "WhatsApp",   "package": "com.whatsapp",               "version": "2.24",  "system": False, "perms": 41},
]

# Permissões DEMO por package (só algumas apps; as outras devolvem um conjunto base).
_APPS_DEMO_PERMS = {
    "com.whatsapp": ["android.permission.CAMERA", "android.permission.RECORD_AUDIO",
                     "android.permission.READ_CONTACTS", "android.permission.ACCESS_FINE_LOCATION",
                     "android.permission.READ_EXTERNAL_STORAGE", "android.permission.INTERNET"],
    "com.instagram.android": ["android.permission.CAMERA", "android.permission.ACCESS_FINE_LOCATION",
                              "android.permission.READ_MEDIA_IMAGES", "android.permission.INTERNET",
                              "android.permission.POST_NOTIFICATIONS"],
    "com.spotify.music": ["android.permission.INTERNET", "android.permission.BLUETOOTH",
                          "android.permission.FOREGROUND_SERVICE", "android.permission.POST_NOTIFICATIONS"],
}


class AppsAPI:
    """Inspeção de apps instaladas — `from apkpy_lib import apps`.

    - `apps.list(on_result=cb)` — cb recebe um JSON: [{name, package, version,
      system, apk, perms, subtitle}], ordenado por nome.
    - `apps.permissions(pkg, on_result=cb)` — cb recebe um JSON: lista de permissões.
    - `apps.extract(pkg, on_result=cb)` — copia o APK para Download/; cb(sucesso, caminho).
    - `apps.hash(pkg, on_result=cb)` — SHA-256 do APK; cb(sucesso, hash-hex).

    No Android usa o PackageManager (ver o compilador). No desktop devolve DEMO."""

    def list(self, on_result=None):
        rows = []
        for a in sorted(_APPS_DEMO, key=lambda x: x["name"].lower()):
            perms = a.get("perms", 0)
            sysf = a.get("system", False)
            rows.append({
                "name": a["name"], "package": a["package"], "version": a.get("version", ""),
                "system": sysf, "apk": "/data/app/%s/base.apk" % a["package"], "perms": perms,
                "subtitle": "%s  ·  %d perms%s" % (a["package"], perms, "  ·  sistema" if sysf else ""),
            })
        self._deliver(on_result, json.dumps(rows, ensure_ascii=False))

    def permissions(self, package, on_result=None):
        ps = _APPS_DEMO_PERMS.get(str(package),
                                  ["android.permission.INTERNET", "android.permission.ACCESS_NETWORK_STATE"])
        self._deliver(on_result, json.dumps(sorted(ps), ensure_ascii=False))

    def extract(self, package, on_result=None):
        try:
            import os as _os
            d = _os.path.join(_os.path.expanduser("~"), ".apkpy", "extracted")
            _os.makedirs(d, exist_ok=True)
            path = _os.path.join(d, str(package) + ".apk")
            with open(path, "wb") as f:
                f.write(b"PK\x03\x04apkpy-preview-demo-apk:" + str(package).encode("utf-8"))
            print("[apps] extract (preview): %s" % path)
            self._deliver(on_result, True, path, two=True)
        except Exception as e:
            print("[apps] extract failed:", e)
            self._deliver(on_result, False, "", two=True)

    def hash(self, package, on_result=None):
        import hashlib as _h
        # Hash estável por package (demo) — no Android é o SHA-256 do APK real.
        digest = _h.sha256(("apkpy-demo:" + str(package)).encode("utf-8")).hexdigest()
        print("[apps] hash (preview) %s -> %s" % (package, digest))
        self._deliver(on_result, True, digest, two=True)

    def _deliver(self, cb, a, b=None, two=False):
        if cb is None:
            return
        try:
            cb(a, b) if two else cb(a)
        except Exception as e:
            print("[apps] callback error:", e)


apps = AppsAPI()


# ─── AuthAPI (login OAuth) ────────────────────────────────────────────────────

# Endpoints OAuth2 por provider (espelha _OAUTH_PROVIDERS do compilador).
_OAUTH_PROVIDERS = {
    'google':  ('https://accounts.google.com/o/oauth2/v2/auth', 'https://oauth2.googleapis.com/token', 'openid email profile'),
    'spotify': ('https://accounts.spotify.com/authorize', 'https://accounts.spotify.com/api/token', 'user-read-email user-read-private'),
    'github':  ('https://github.com/login/oauth/authorize', 'https://github.com/login/oauth/access_token', 'read:user'),
}

# Perfil do utilizador (auth.user) por provider — espelha _OAUTH_USERINFO do compilador.
_OAUTH_USERINFO = {
    'google':  {'url': 'https://www.googleapis.com/oauth2/v3/userinfo', 'name': 'name', 'email': 'email', 'picture': 'picture'},
    'spotify': {'url': 'https://api.spotify.com/v1/me', 'name': 'display_name', 'email': 'email', 'picture': '__spotify_images__'},
    'github':  {'url': 'https://api.github.com/user', 'name': 'name', 'email': 'email', 'picture': 'avatar_url'},
}


class AuthAPI:
    """Login OAuth2 (authorization-code + PKCE) — `from apkpy_lib import auth`.

    No Android, auth.login() abre o browser no ecrã de consentimento; o redirect
    (deep-link) volta à ApkpyAuthActivity, que troca o code por um access token,
    guarda-o e navega para o ecrã `then`.

        auth.login(provider="google", client_id="...", scopes=["email"], then=home)
        auth.is_logged_in()   # há token?
        auth.token()          # o access token (p/ pôr nos pedidos https)
        auth.logout()         # apaga o token

    No PREVIEW (desktop) o scheme custom apkpy:// não é entregável a um browser, por
    isso fazemos o login REAL via loopback: redirect http://127.0.0.1:8888/callback
    + um mini-servidor local que apanha o `code` e troca por token (PKCE). Regista
    esse URL nas Redirect URIs do provider (além do apkpy://auth do Android)."""

    _main_queue = None      # fila de callables p/ correr na main thread do Tk
    _main_polling = False
    _last_provider = ""     # último provider usado (auth.user deriva o endpoint)

    def _token_file(self):
        d = os.path.join(os.path.expanduser("~"), ".apkpy")
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        return os.path.join(d, "auth_token.txt")

    def token(self):
        try:
            with open(self._token_file(), encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    def is_logged_in(self):
        return bool(self.token())

    def _set_token(self, t):
        try:
            with open(self._token_file(), "w", encoding="utf-8") as f:
                f.write(str(t or ""))
        except Exception:
            pass

    def logout(self):
        """Apaga o token guardado (volta ao estado deslogado)."""
        try:
            os.remove(self._token_file())
        except Exception:
            self._set_token("")

    def login(self, provider=None, client_id=None, scopes=None, then=None,
              redirect="apkpy://auth", auth_url=None, token_url=None, on_error=None,
              preview_port=8888):
        prov = (provider or "").lower()
        self._last_provider = prov
        self._start_main_pump()   # main thread aqui → seguro arrancar o pump
        d_auth, d_token, d_scopes = _OAUTH_PROVIDERS.get(prov, ("", "", ""))
        auth_url = auth_url or d_auth
        token_url = token_url or d_token
        if isinstance(scopes, (list, tuple)):
            scope_str = " ".join(str(s) for s in scopes)
        elif scopes:
            scope_str = str(scopes)
        else:
            scope_str = d_scopes
        if not auth_url or not client_id:
            print("[auth] login: missing provider/auth_url or client_id")
            if on_error:
                on_error("invalid config")
            return
        # Placeholder? (client_id de exemplo ainda não substituído) → não abrir um
        # separador partido no browser; só explica e simula, p/ testar o fluxo da UI.
        cid_low = str(client_id).lower()
        is_placeholder = any(m in cid_low for m in ("o-teu-client-id", "teu-client-id", "your-client-id", "your_client_id", "client-id-aqui"))
        if is_placeholder:
            print("[auth] WARNING: client_id is still a placeholder — browser NOT opened.")
            print("[auth]    Set your real client_id and register", redirect, "(Android) +")
            print("[auth]    http://127.0.0.1:%d/callback (preview) in the provider." % preview_port)
            print("[auth] (preview) simulating a successful login — preview token")
            self._set_token("preview-token")
            self._nav(then)
            return
        # client_id REAL → login a sério no desktop via loopback (o scheme custom
        # apkpy:// não é entregável a um browser de desktop; no Android é).
        self._preview_real_login(auth_url, token_url, client_id, scope_str, then, preview_port, on_error)

    # ─── Dispatch para a main thread do Tk (workers só enfileiram; o pump corre
    #     na main thread). Evita chamar Tk de outras threads (não é thread-safe). ──
    def _on_main(self, fn):
        if self._main_queue is None:
            self._main_queue = []
        self._main_queue.append(fn)

    def _start_main_pump(self):
        """Chamar a partir da MAIN thread (ex.: início de login/user)."""
        if _app and _app.root and not self._main_polling:
            self._main_polling = True
            self._pump_main()

    def _pump_main(self):
        q = self._main_queue
        if q:
            while q:
                try:
                    q.pop(0)()
                except Exception:
                    pass
        if _app and _app.root:
            _app.root.after(100, self._pump_main)
        else:
            self._main_polling = False

    def _nav(self, then):
        """Enfileira a navegação para `then` na main thread (o pump renderiza-o)."""
        if then is not None:
            self._on_main(lambda t=then: _app.render_screen(t) if (_app and _app.root) else None)

    def _preview_real_login(self, auth_url, token_url, client_id, scope_str, then, port, on_error):
        import urllib.parse, urllib.request, webbrowser, threading, secrets, hashlib, base64, json as _json
        import http.server, time
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
        redirect = f"http://127.0.0.1:{port}/callback"
        state = secrets.token_urlsafe(8)
        result = {}

        class _H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/callback":
                    self.send_response(404)
                    self.end_headers()
                    return
                q = urllib.parse.parse_qs(parsed.query)
                result["code"] = q.get("code", [""])[0]
                result["error"] = q.get("error", [""])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<h2 style='font-family:sans-serif'>apkpy: login complete &#10003;</h2>"
                                 "<p style='font-family:sans-serif'>You can close this tab and go back to the app.</p>".encode("utf-8"))

        try:
            server = http.server.HTTPServer(("127.0.0.1", port), _H)
        except OSError as e:
            print("[auth] could not open port", port, "->", e, "— simulating.")
            self._set_token("preview-token")
            self._nav(then)
            return
        server.timeout = 1
        params = urllib.parse.urlencode({
            "response_type": "code", "client_id": client_id, "redirect_uri": redirect,
            "scope": scope_str, "code_challenge_method": "S256", "code_challenge": challenge,
            "state": state,
        })
        full = f"{auth_url}?{params}"
        print("[auth] preview: redirect =", redirect)
        print("[auth] WARNING: register that URL in the provider's Redirect URIs (besides apkpy://auth for Android).")
        print("[auth] opening consent:", full)

        def _run():
            try:
                webbrowser.open(full)
            except Exception:
                pass
            deadline = time.time() + 180   # 3 min para autorizares
            while not result and time.time() < deadline:
                try:
                    server.handle_request()
                except Exception:
                    break
            try:
                server.server_close()
            except Exception:
                pass
            code = result.get("code", "")
            if not code:
                msg = result.get("error", "") or "no response (timeout)"
                print("[auth] login not completed:", msg)
                if on_error:
                    on_error(msg)
                return
            # trocar o code por um access token (PKCE, sem client secret)
            token = ""
            try:
                data = urllib.parse.urlencode({
                    "grant_type": "authorization_code", "code": code,
                    "redirect_uri": redirect, "client_id": client_id, "code_verifier": verifier,
                }).encode("utf-8")
                req = urllib.request.Request(token_url, data=data, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    token = _json.loads(r.read().decode("utf-8")).get("access_token", "")
            except Exception as e:
                print("[auth] token exchange failed:", e)
            if token:
                self._set_token(token)
                print("[auth] OK real login complete — token saved")
                self._nav(then)
            else:
                print("[auth] no access_token (check scopes/registered redirect)")
                if on_error:
                    on_error("no access_token")

        threading.Thread(target=_run, daemon=True).start()

    # ─── Perfil do utilizador (auth.user) ────────────────────────────────────
    def user(self, on_result=None, url=None):
        """Busca o perfil do utilizador logado (GET ao userinfo com o Bearer token)
        e chama `on_result` com um dict normalizado {name, email, picture}. Async.

            auth.user(on_result=lambda u: nome.set_value(u["name"]))"""
        if on_result is None:
            return
        self._start_main_pump()
        import threading
        threading.Thread(target=self._fetch_user, args=(on_result, url), daemon=True).start()

    def _fetch_user(self, cb, url):
        import urllib.request, urllib.error, json as _json
        tok = self.token()
        info = _OAUTH_USERINFO.get(self._last_provider, {})
        endpoint = url or info.get("url", "")
        if tok and tok != "preview-token" and endpoint:
            profile = {"name": "", "email": "", "picture": ""}
            try:
                req = urllib.request.Request(endpoint, headers={
                    "Authorization": "Bearer " + tok, "Accept": "application/json", "User-Agent": "apkpy"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    raw = _json.loads(r.read().decode("utf-8"))
                profile = self._normalize_profile(self._last_provider, raw)
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", "replace")
                except Exception:
                    pass
                print("[auth] user fetch failed: HTTP", e.code, "-", body[:300])
                if e.code == 403 and self._last_provider == "spotify":
                    print("[auth]    Spotify 403: a app está em Development Mode. Vai ao Dashboard")
                    print("[auth]    → a tua app → User Management → adiciona o teu nome + email Spotify.")
                profile["name"] = "(erro " + str(e.code) + ")"
            except Exception as e:
                print("[auth] user fetch failed:", e)
                profile["name"] = "(erro)"
        else:
            # token simulado (preview sem login real) → perfil de demonstração
            profile = {"name": "Preview User", "email": "preview@apkpy.local", "picture": ""}
        self._on_main(lambda: cb(profile))

    @staticmethod
    def _normalize_profile(provider, raw):
        if provider == "spotify":
            imgs = raw.get("images") or []
            pic = imgs[0].get("url", "") if imgs else ""
            return {"name": raw.get("display_name", ""), "email": raw.get("email", ""), "picture": pic}
        if provider == "github":
            return {"name": raw.get("name") or raw.get("login", ""), "email": raw.get("email", ""), "picture": raw.get("avatar_url", "")}
        return {"name": raw.get("name", ""), "email": raw.get("email", ""), "picture": raw.get("picture", "")}


# Instância global: `from apkpy_lib import auth`
auth = AuthAPI()


# ─── SQLiteAPI ────────────────────────────────────────────────────────────────

class SQLiteAPI(DataCoreMixin):
    """
    Base de dados relacional SQLite local.
    No Hot Previewer (Python), cria/usa um ficheiro .db local e usa o sqlite3 nativo.
    No Android (apkpy build), transpila para chamadas a SQLiteDatabase nativo.
    """

    def __init__(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__main__.__file__))
        except AttributeError:
            script_dir = os.getcwd()
        self._path = os.path.join(script_dir, 'apkpy_app.db')
        # Conexão partilhada activa durante uma transação (begin/commit/rollback).
        # Fora de uma transação é None e cada execute/query abre a sua própria.
        self._tx_conn = None
        # rowid da última linha inserida por execute() — lido por last_insert_id().
        self._last_insert_id = -1
        self._legacy_data_dirty = False
        self._data_core_init()

    def _open(self):
        """Devolve a conexão da transação activa, ou abre uma nova de uso único."""
        import sqlite3
        if self._tx_conn is not None:
            return self._tx_conn, False
        connection = sqlite3.connect(self._path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection, True

    def execute(self, query, params=None):
        """
        Executa uma query que não devolve resultados (INSERT, UPDATE, DELETE, CREATE TABLE).
        `params` (opcional) é uma lista de valores para os placeholders `?` —
        usa SEMPRE isto para dados do utilizador: evita SQL injection e
        queries partidas por apóstrofos (ex: O'Brien).

        Dentro de um bloco `db.begin()` … `db.commit()`, vários `execute`
        partilham a mesma conexão e só são gravados em conjunto (ou desfeitos
        com `db.rollback()`).
        """
        conn, own = self._open()
        cursor = conn.cursor()
        cursor.execute(query, tuple(params) if params else ())
        # rowid do último INSERT (igual ao SQLiteDatabase no Android)
        self._last_insert_id = cursor.lastrowid
        if own:
            conn.commit()
            conn.close()
            self._data_invalidate(None)
        else:
            self._legacy_data_dirty = True

    def query(self, query, params=None):
        """
        Executa um SELECT e devolve os resultados como uma String JSON (lista de objetos).
        `params` (opcional) é uma lista de valores para os placeholders `?`.

        O resultado também é iterável linha-a-linha::

            rows = db.query("SELECT * FROM notes")
            for row in rows:
                toast(row["content"])
        """
        import sqlite3
        import json
        conn, own = self._open()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, tuple(params) if params else ())
        rows = cursor.fetchall()
        if own:
            conn.close()
        # Converte para dicts
        result = [dict(row) for row in rows]
        return JsonRows(json.dumps(result, ensure_ascii=False))

    def last_insert_id(self):
        """
        Devolve o `rowid` (id auto-incrementado) da última linha inserida com
        `db.execute(...)` — sem precisares de um SELECT extra.

        Útil logo a seguir a um INSERT para saber o id da linha criada::

            db.execute("INSERT INTO users (name) VALUES (?)", [nome])
            novo_id = db.last_insert_id()

        No Android transpila para `SELECT last_insert_rowid()` na mesma
        conexão, devolvendo o mesmo valor.
        """
        return self._last_insert_id

    def begin(self):
        """
        Inicia uma transação: todos os `db.execute(...)` seguintes ficam
        pendentes até `db.commit()` (gravar tudo de uma vez) ou
        `db.rollback()` (desfazer tudo). Ou tudo ou nada — ideal para
        transferências, criação de registos relacionados, etc.

        No Android transpila para `SQLiteDatabase.beginTransaction()`.
        """
        import sqlite3
        if self._tx_conn is not None:
            return  # já há uma transação a decorrer
        self._tx_conn = sqlite3.connect(self._path)
        self._tx_conn.execute("PRAGMA foreign_keys = ON")

    def commit(self):
        """Confirma (grava no disco) tudo o que foi feito desde `db.begin()`."""
        if self._tx_conn is None:
            return
        try:
            self._tx_conn.commit()
        finally:
            self._tx_conn.close()
            self._tx_conn = None
        if self._legacy_data_dirty:
            self._legacy_data_dirty = False
            self._data_invalidate(None)

    def rollback(self):
        """Desfaz tudo o que foi feito desde `db.begin()` (nada é gravado)."""
        if self._tx_conn is None:
            return
        try:
            self._tx_conn.rollback()
        finally:
            self._tx_conn.close()
            self._tx_conn = None
            self._legacy_data_dirty = False

# Instância global partilhada por toda a app
db = SQLiteAPI()


def _parse_keyframes_internal(css_text):
    """Extrai blocos @keyframes do texto CSS e devolve um dict com as propriedades from/to."""
    keyframes = {}
    kf_blocks = re.findall(r'@keyframes\s+(\w+)\s*\{((?:[^{}]*\{[^{}]*\})*[^{}]*)\}', css_text)
    for name, content in kf_blocks:
        kf_dict = {}
        stages = re.findall(r'([a-zA-Z0-9%]+)\s*\{([^{}]*)\}', content)
        for stage, props_str in stages:
            props = {}
            lines = re.findall(r'([\w-]+)\s*:\s*(.*?);', props_str)
            for key, value in lines:
                props[key.strip()] = value.strip()
            kf_dict[stage.strip()] = props
        keyframes[name.strip()] = kf_dict
    return keyframes


def parse_css_internal(css_text):
    """Transforma o texto CSS num dicionário de estilos.

    Delega no parser CANÓNICO (apkpy_lib.core.style_parser.parse_css) — o mesmo
    que o transpilador usa para o Android. Antes havia DOIS parsers (este e o do
    core) com lógica copiada que divergiu: os seletores separados por vírgula
    funcionavam no Android mas não no preview. Com a delegação, preview e Android
    leem o CSS exatamente da mesma forma e nunca mais podem divergir."""
    from .core.style_parser import parse_css
    styles, _ = parse_css(css_text)
    return styles


def load_styles_now():
    """Procura a variável 'style' no ficheiro writehere.py e carrega-a (sempre recarrega)."""
    global global_styles, global_keyframes
    user_styles = {}
    if hasattr(__main__, 'style'):
        user_styles = parse_css_internal(__main__.style)
        global_keyframes = _parse_keyframes_internal(__main__.style)
        # Said once per name per run, so a Hot Previewer reload does not turn
        # one typo into a wall of repeats.
        from .core.style_parser import report_unknown_properties
        report_unknown_properties(user_styles, global_keyframes)
    else:
        global_keyframes = {}
    global_styles = apply_theme(user_styles, _active_theme)


def _get_body_style():
    """Devolve o dicionário de estilos do seletor global 'body', ou {} se não definido."""
    return global_styles.get('body', {})


def _merge_with_body(comp_id, comp_type=None, variant=None, row_variant=None):
    """
    Funde os estilos do 'body' (base global) com os do ID específico.
    As propriedades do ID específico sobrescrevem sempre as do body.
    Se comp_id for None ou não existir nos estilos, devolve apenas o body.
    """
    return component_style(
        global_styles, comp_type, comp_id, variant=variant,
        viewport=_style_viewport, row_variant=row_variant,
    )


def _preview_child_layout_style(comp):
    """Resolve one child's style for the Preview layout engine.

    An avatar's API size is explicit.  Letting flex shrink its slot clips the
    Tk canvas instead of resizing the bitmap, so avatars stay fixed-size while
    their flexible siblings continue to absorb the available space.
    """
    style = _merge_with_body(
        comp.kwargs.get('comp_id'), comp.comp_type,
        comp.kwargs.get('variant')
        if comp.comp_type in ('button', 'label', 'card') else None,
    )
    if comp.comp_type == 'image' and comp.kwargs.get('avatar'):
        size = max(16, int(comp.kwargs.get('avatar_size') or 48))
        style.update({
            'width': f'{size}px',
            'height': f'{size}px',
            'aspect-ratio': '1 / 1',
            'flex-shrink': '0',
        })
    return style


def _is_transparent(color):
    """True para uma cor CSS que não pinta nada.

    ``transparent`` e um hex de 8 dígitos com alfa ``00`` (a convenção
    ``#AARRGGBB`` que o Android usa) querem dizer o mesmo: o que está por trás
    aparece intacto.
    """
    raw = str(color or '').strip().lower()
    if raw in ('transparent', 'none'):
        return True
    if raw.startswith('#') and len(raw) == 9:
        return raw[1:3] == '00'
    if raw.startswith('#') and len(raw) == 5:
        return raw[1] == '0'
    if raw.startswith('rgba('):
        parts = raw[5:].rstrip(')').split(',')
        return len(parts) == 4 and _parse_anim_val(parts[3], 1.0) == 0
    return False


# What a {field} fills in a row built from components. The icon is left out:
# the phone draws every icon as a vector made at build time.
_ROW_FILLED = ('text', 'src', 'describe', 'placeholder')


def _row_flag(value, item, fill):
    """visible= / active=: a "{field}" read from the item, or a plain value."""
    if isinstance(value, str):
        value = fill(value, item) if '{' in value else value
    from .data_rules import field_is_on
    return field_is_on(value)


def _row_instance(template, item, fill):
    """A copy of a ``row=`` template for one item: ``{field}`` filled by
    ``fill(pattern, item)``, and a command that takes an argument given the
    item. The template itself is never rendered."""
    import inspect
    kwargs = {}
    for key, value in template.kwargs.items():
        if key in _ROW_FILLED and isinstance(value, str) and '{' in value:
            value = fill(value, item)
        elif key in ('command', 'on_click') and callable(value):
            try:
                wanted = [p for p in inspect.signature(value).parameters.values()
                          if p.default is inspect.Parameter.empty
                          and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
            except (TypeError, ValueError):
                wanted = []
            if wanted:
                value = (lambda f=value, it=item: f(it))
        kwargs[key] = value
    copy = ComponentDef(template.comp_type, **kwargs)
    # visible="{field}": a component the item turns off is not drawn at all,
    # as View.GONE takes no space on the phone.
    copy.children = [_row_instance(child, item, fill) for child in template.children
                     if child.kwargs.get('visible') is None
                     or _row_flag(child.kwargs['visible'], item, fill)]
    # active="{field}": the button shows active_icon in its active-color.
    if template.kwargs.get('active') is not None and \
            _row_flag(template.kwargs['active'], item, fill):
        copy._dynamic_icon = template.kwargs.get('active_icon') or template.kwargs.get('icon')
        copy._dynamic_icon_color = (
            _merge_with_body(template.kwargs.get('comp_id'), 'button').get('active-color')
            or global_styles.get('__theme__', {}).get('primary') or '#1DB954')
    return copy


class _PillBadge(tk.Canvas):
    """A row's badge with the round ends the phone gives it -- a
    GradientDrawable with a 10dp radius. A Label is square, and the unread
    count of a chat list is a circle (``min_side``).

    It answers ``configure(text=, bg=, fg=)`` as the Label it replaces did:
    ``bg`` is the badge's own colour; ``surface`` is the row behind it."""

    def __init__(self, master, surface, fill, fg, font, pad_x=6, pad_y=1, min_side=0):
        tk.Canvas.__init__(self, master, bg=surface, width=1, height=1,
                           highlightthickness=0, bd=0)
        self._pill = {'text': '', 'fill': fill, 'fg': fg, 'font': font}
        self._pad = (pad_x, pad_y)
        self._min_side = min_side

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        changed = False
        for key, name in (('text', 'text'), ('bg', 'fill'), ('background', 'fill'),
                          ('fg', 'fg'), ('foreground', 'fg'), ('font', 'font')):
            if key in kw:
                self._pill[name] = kw.pop(key)
                changed = True
        if 'surface' in kw:
            tk.Canvas.configure(self, bg=kw.pop('surface'))
            changed = True
        if kw:
            tk.Canvas.configure(self, **kw)
        if changed:
            self._paint()

    config = configure

    def cget(self, key):
        if key in ('text', 'font'):
            return self._pill[key]
        return tk.Canvas.cget(self, key)

    def _paint(self):
        text = str(self._pill['text'] or '')
        self.delete('all')
        if not text:
            tk.Canvas.configure(self, width=1, height=1)
            return
        try:
            import tkinter.font as _tkfont
            measure = _tkfont.Font(root=self, font=self._pill['font'])
            text_w, text_h = measure.measure(text), measure.metrics('linespace')
        except Exception:
            text_w, text_h = 7 * len(text), 14
        height = max(self._min_side, text_h + 2 * self._pad[1])
        width = max(height if self._min_side else 0, text_w + 2 * self._pad[0])
        tk.Canvas.configure(self, width=width, height=height)
        _create_rounded_rect(self, 0, 0, width, height, min(height / 2.0, 10),
                             fill=self._pill['fill'], outline='')
        self.create_text(width / 2.0, height / 2.0, text=text,
                         fill=self._pill['fg'], font=self._pill['font'])


def _is_icon_button(comp):
    """A button drawn as an icon alone: it has one and no words, or it is
    ``variant="icon"``, which draws the icon alone whatever its text says."""
    kwargs = getattr(comp, 'kwargs', {}) or {}
    if not kwargs.get('icon'):
        return False
    return (not str(kwargs.get('text') or '').strip()
            or kwargs.get('variant') == 'icon')


def _partial_alpha(color):
    """True for an ``#AARRGGBB``/``#ARGB`` colour that is neither clear nor opaque."""
    raw = str(color or '').strip().lower()
    if raw.startswith('#') and len(raw) == 9:
        return raw[1:3] not in ('00', 'ff')
    if raw.startswith('#') and len(raw) == 5:
        return raw[1] not in ('0', 'f')
    return False


# align-self for a child of a plain column (the screen itself): where it sits.
_ALIGN_SELF_ANCHOR = {
    'flex-end': 'e', 'end': 'e', 'right': 'e',
    'flex-start': 'w', 'start': 'w', 'left': 'w',
    'center': 'center',
}


def _shrinks_to_fit(style):
    """An absolute box with no width and not both sides set: in CSS it is as
    wide as its content."""
    if str(style.get('position', '')).strip().lower() != 'absolute':
        return False
    if str(style.get('width', '') or '').strip():
        return False
    return not (str(style.get('left', '') or '').strip()
                and str(style.get('right', '') or '').strip())


def _natural_width(slot, fallback):
    """The width an absolute container's content needs, instead of the full
    width its layout host is configured to -- which put a right-aligned
    column of buttons in the middle of the screen.

    A container records it on its layout host; the difference between the
    slot and that host is the container's own padding and inset."""
    pending = [slot]
    while pending:
        widget = pending.pop(0)
        natural = getattr(widget, '_apkpy_natural_width', None)
        if natural is not None:
            try:
                extra = max(0, slot.winfo_reqwidth() - widget.winfo_reqwidth())
            except Exception:
                extra = 0
            return max(1, min(fallback, natural + extra))
        try:
            pending.extend(widget.winfo_children())
        except Exception:
            pass
    return fallback


def _relayout_above(widget):
    """Ask the nearest container above to lay its children out again."""
    try:
        parent = widget.master
        while parent is not None:
            relayout = getattr(parent, '_apkpy_relayout', None)
            if relayout is not None:
                parent.after_idle(relayout)
                return
            parent = parent.master
    except Exception:
        pass


def _button_css_size(style):
    """A button's stylesheet width and height in Preview pixels, or None.

    Percentages keep the old behaviour (a column button already fills its
    width); absolute sizes are what the phone gives the view."""
    sizes = []
    for axis in ('width', 'height'):
        raw = str(style.get(axis, '') or '').strip().lower()
        if not raw or raw == 'auto' or raw.endswith('%'):
            sizes.append(None)
            continue
        sizes.append(_resolve_css_size_tk(raw, axis, _style_viewport) or None)
    return tuple(sizes)


def _tk_color(color, behind=None):
    """Uma cor CSS que o Tcl aceite mesmo.

    O Tk não tem alfa por widget. Uma superfície transparente *é* a superfície
    que está por trás, por isso resolve para ``behind``; um alfa parcial fica
    com a sua cor, que é mais perto do pretendido do que a alternativa — o Tcl
    rejeita ``#00000000`` e a rejeição sai como E1999 que mata a app inteira.
    """
    raw = str(color or '').strip()
    if not raw or _is_transparent(raw):
        return behind
    if raw.startswith('#') and len(raw) == 9:
        return '#' + raw[3:]          # #AARRGGBB -> #RRGGBB
    if raw.startswith('#') and len(raw) == 5:
        return '#' + raw[2:]          # #ARGB -> #RGB
    return raw


def _wrap_row_text(host, label, lines):
    """Let a collection row's text run to `lines` lines instead of one.

    Tk has no maxLines: a Label wraps once it is given a wraplength, and the
    row's fixed height does the cutting off. The width is only known once the
    row is laid out, so it is re-applied on every resize.
    """
    if lines <= 1:
        return
    label.configure(justify='left')

    def _apply(event=None):
        fixed = getattr(label, '_apkpy_fixed_wrap', None)
        if fixed:
            # A chat bubble hugs its text: tied to its own width, the wrap
            # would shrink it a little on every pass.
            label.configure(wraplength=fixed)
            return
        width = event.width if event is not None else host.winfo_width()
        if width > 1:
            label.configure(wraplength=max(60, width - 8))

    host.bind('<Configure>', _apply, add='+')
    host.after_idle(_apply)


def _get_style_bg(style_dict):
    """Lê a cor de fundo; suporta 'background-color' e 'backgroundcolor' (sem hífen)."""
    return style_dict.get('background-color') or style_dict.get('backgroundcolor')


def _get_style_fg(style_dict):
    """Lê a cor do texto."""
    return style_dict.get('color')

def _get_style_pressed_color(style_dict):
    """Lê a cor de fundo ao pressionar o botão."""
    return style_dict.get('pressed-color')

def _get_style_border_color(style_dict):
    """Lê a cor da borda, ou 'none'."""
    val = style_dict.get('border-color')
    if val and val.lower() == 'none':
        return ""
    return val

def _get_style_focus_border_color(style_dict):
    val = style_dict.get('focus-border-color') or style_dict.get('focus-color')
    if val and val.lower() == 'none':
        return ""
    return val

def _parse_radius(style_dict):
    """The largest corner of border-radius, for code that draws one radius.

    It stripped every non-digit, so ``24px 24px 0 0`` was a radius of
    242400."""
    return int(max(corner_radii(style_dict.get('border-radius', '0'))))


def _parse_radii(style_dict):
    """One radius, or (top-left, top-right, bottom-right, bottom-left) when
    the corners differ -- what _create_rounded_rect draws."""
    corners = tuple(int(round(c)) for c in corner_radii(style_dict.get('border-radius', '0')))
    return corners[0] if len(set(corners)) == 1 else corners

def _parse_border_width(style_dict):
    """Extrai a largura da borda (ex: '2px' -> 2)."""
    raw = style_dict.get('border-width', '0')
    cleaned = re.sub(r'[^0-9.]', '', str(raw))
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0

def _parse_margin(style_dict):
    """Devolve (top, right, bottom, left) em pixels a partir das propriedades de margin CSS."""
    def _px(val):
        cleaned = re.sub(r'[^0-9.]', '', str(val))
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return 0

    sides = _box_shorthand(style_dict.get('margin')) or (0, 0, 0, 0)
    top, right, bottom, left = (int(side) for side in sides)
    if 'margin-top'    in style_dict: top    = _px(style_dict['margin-top'])
    if 'margin-right'  in style_dict: right  = _px(style_dict['margin-right'])
    if 'margin-bottom' in style_dict: bottom = _px(style_dict['margin-bottom'])
    if 'margin-left'   in style_dict: left   = _px(style_dict['margin-left'])
    return top, right, bottom, left


def _watch_choice_change(comp):
    """``on_change`` for a switch, a checkbox or a slider.

    It was called for text fields only, here and on the phone, so a settings
    switch moved and nothing heard it. The callback gets what get_value()
    gives -- "true"/"false", or the slider's number as text -- whenever the
    value changes once the screen is showing: a tap, a drag or a set_value()
    from a callback. The value the screen opens with is not a change; the
    phone's listener skips it the same way (isShown() is false until the
    window is attached).
    """
    callback = comp.kwargs.get('on_change') if comp is not None else None
    kind = comp.kwargs.get('input_type', 'text') if comp is not None else ''
    if not callable(callback) or kind not in ('switch', 'checkbox', 'range'):
        return
    var = getattr(comp, '_toggle_var', None) or getattr(comp, '_tk_var', None)
    if var is None:
        return

    def current():
        value = comp.get_value()
        return str(value) if kind == 'range' else value

    def start():
        seen = {'value': current()}

        def changed(*_args):
            now = current()
            if now == seen['value']:
                return
            seen['value'] = now
            callback(now)

        try:
            var.trace_add('write', changed)
        except tk.TclError:
            pass

    # After the screen is built and any remembered state is back in place.
    _app.root.after_idle(start)


def _add_leading_gap(widget, gap, horizontal=False):
    """Widen the space before a packed widget by ``gap``.

    On the phone the gap is the child's own margin, so it goes when the child
    is hidden; kept in the widget's pady (or padx in a row) it does the same
    here, where a spacer frame would have stayed behind.
    """
    key = 'padx' if horizontal else 'pady'
    try:
        raw = widget.pack_info().get(key, 0)
    except tk.TclError:
        return
    parts = [int(float(p)) for p in re.findall(r'-?\d+(?:\.\d+)?', str(raw))]
    before, after = (parts + [0, 0])[:2] if len(parts) != 1 else (parts[0], parts[0])
    widget.pack_configure(**{key: (before + gap, after)})


def _parse_padding_tk(style_dict):
    """Return CSS padding as (top, right, bottom, left) for the Previewer."""
    raw = style_dict.get('padding')
    values = []
    for part in str(raw or '').split():
        cleaned = re.sub(r'[^0-9.]', '', part)
        if cleaned:
            values.append(int(float(cleaned)))
    if len(values) == 1:
        sides = (values[0], values[0], values[0], values[0])
    elif len(values) == 2:
        sides = (values[0], values[1], values[0], values[1])
    elif len(values) == 3:
        sides = (values[0], values[1], values[2], values[1])
    elif len(values) >= 4:
        sides = (values[0], values[1], values[2], values[3])
    else:
        sides = (0, 0, 0, 0)
    # The long names, read the same way the compiler reads them. Neither side
    # read them before, so a stylesheet saying padding-top was saying nothing.
    out = list(sides)
    for index, name in enumerate(('padding-top', 'padding-right',
                                  'padding-bottom', 'padding-left')):
        found = re.findall(r'(\d+(?:\.\d+)?)', str(style_dict.get(name) or ''))
        if found:
            out[index] = int(float(found[0]))
    return tuple(out)


# CSS on the left, Tk on the right.  Tk has no 'start'/'end', so a right-to-left
# locale does not mirror in the Previewer the way it does on the phone.
_TK_ANCHOR = {'left': 'w', 'center': 'center', 'right': 'e'}
_TK_JUSTIFY = {'left': 'left', 'center': 'center', 'right': 'right'}


def _text_measure(root, font):
    """A width-measuring function for one font, with a crude fallback."""
    try:
        import tkinter.font as _tkfont
        return _tkfont.Font(root=root, font=font).measure
    except Exception:
        return lambda value: len(str(value)) * 8


def _clip_to_width(root, font, text, limit):
    """Cut text to fit and end it in an ellipsis, like a TextView does."""
    value = str(text or '')
    if not value:
        return ''
    measure = _text_measure(root, font)
    if measure(value) <= limit:
        return value
    ellipsis = '…'
    kept = ''
    for index in range(1, len(value) + 1):
        if measure(value[:index] + ellipsis) > limit:
            break
        kept = value[:index]
    return (kept.rstrip() + ellipsis) if kept else ellipsis

def _tk_linespace(root, font, fallback=18):
    """The line box the font actually occupies, in px."""
    try:
        import tkinter.font as _tkfont
        return int(_tkfont.Font(root=root, font=font).metrics('linespace'))
    except Exception:
        return int(fallback)


def _tk_leading(root, font, style_dict, font_size, natural=None):
    """Half of the leading ``line-height`` asks for, as Tk padding in px.

    Tk has no line spacing on a Label, so the leading goes outside the text as
    padding instead of between the lines.  For one line -- a row label, a
    kicker, a heading, which is what line-height is for here -- that is exactly
    what CSS half-leading does and the box comes out the same height as the
    TextView.  A paragraph that wraps ends up shorter in the Previewer than on
    the phone, by the leading of each line after the first.
    """
    if natural is None:
        natural = _tk_linespace(root, font, int(font_size * 1.2))
    extra = line_spacing_extra(
        style_dict.get('line-height'), font_size, natural=natural,
    )
    return int(round(extra / 2.0))


def _material_button_height(
        line_height, padding=None, compact=False, flex=False, min_height=0):
    """Match Android button touch targets while respecting CSS padding."""
    if compact:
        # An icon alone is a 48px square unless the stylesheet sets its
        # min-height, which the phone then takes as the height.
        return int(min_height) if min_height else 48
    top, _right, bottom, _left = padding or (0, 0, 0, 0)
    content_height = max(1, int(line_height)) + top + bottom
    return max(40 if flex else 48, content_height, int(min_height or 0))


def _material_input_height(line_height, padding=None):
    """Match an Android EditText using the same CSS padding."""
    top, _right, bottom, _left = padding or (12, 12, 12, 12)
    return max(48, max(1, int(line_height)) + top + bottom)


def _material_button_text_width(text, measure, tracking=0.0):
    """Measure Material button text including Android-style letter spacing."""
    value = str(text or '')
    return float(measure(value)) + max(0, len(value) - 1) * max(0.0, tracking)


def _wrap_material_button_text(text, max_width, measure, tracking=0.0):
    """Wrap button text like Android TextView, including long single words."""
    value = str(text or '')
    if not value:
        return ['']
    limit = max(1.0, float(max_width))
    if _material_button_text_width(value, measure, tracking) <= limit:
        return [value]

    lines = []
    current = ''
    for word in value.split(' '):
        candidate = word if not current else f'{current} {word}'
        if _material_button_text_width(candidate, measure, tracking) <= limit:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ''
        while word:
            take = 1
            for index in range(1, len(word) + 1):
                if _material_button_text_width(
                    word[:index], measure, tracking,
                ) <= limit:
                    take = index
                else:
                    break
            lines.append(word[:take])
            word = word[take:]
    if current:
        lines.append(current)
    return lines or [value]


def _parse_image_size(style_dict):
    """Devolve (largura, altura) em píxeis a partir de width/height CSS. None = não definido."""
    def _dim(val):
        if not val:
            return None
        val_s = str(val).strip().lower()
        if val_s in ('match_parent', '100%', 'fill'):
            return 'match_parent'
        cleaned = re.sub(r'[^0-9.]', '', val_s)
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None
    return _dim(style_dict.get('width')), _dim(style_dict.get('height'))


def _get_style_placeholder_color(style_dict):
    """CSS ``placeholder-color``.

    The Android generator already honoured this; the Previewer had ``#9e9e9e``
    written into it, so a themed hint was one colour on the phone and grey on
    the desktop.
    """
    return style_dict.get('placeholder-color')


def _parse_object_fit(style_dict):
    """Lê object-fit CSS: 'cover'|'contain'|'fill'|'none'. Default: 'fill'."""
    return style_dict.get('object-fit', 'fill').strip().lower()


def _parse_opacity(style_dict):
    """Lê opacity CSS (0.0–1.0). Default: 1.0."""
    raw = style_dict.get('opacity', '1')
    try:
        return max(0.0, min(1.0, float(str(raw).strip())))
    except (ValueError, TypeError):
        return 1.0


def _parse_filter(style_dict):
    """Analisa a propriedade CSS filter e devolve um dict com os efeitos detectados."""
    raw = style_dict.get('filter', '')
    effects = {}
    if 'grayscale' in raw:
        m = re.search(r'grayscale\(\s*([0-9.]+)%?\)', raw)
        effects['grayscale'] = float(m.group(1)) / 100.0 if m else 1.0
    if 'blur' in raw:
        m = re.search(r'blur\(\s*([0-9.]+)px\)', raw)
        effects['blur'] = float(m.group(1)) if m else 0.0
    return effects


def _get_flex_orientation(style_dict):
    """
    Determina a orientação de flex a partir das propriedades CSS.

    - display:flex + flex-direction:column  → 'column'  (pack side=TOP)
    - display:flex + flex-direction:row     → 'row'     (pack side=LEFT)
    - display:flex sem flex-direction       → 'row'     (CSS default)
    - sem display:flex                      → 'column'  (stack vertical normal)
    """
    display  = style_dict.get('display', '').strip().lower()
    flex_dir = style_dict.get('flex-direction', '').strip().lower()
    if display == 'flex':
        return 'column' if flex_dir == 'column' else 'row'
    if display == 'grid':
        columns = str(style_dict.get('grid-template-columns', '1fr')).strip()
        return 'row' if len(columns.split()) > 1 else 'column'
    # Legado: apenas flex-direction
    return 'row' if flex_dir == 'row' else 'column'


def _percent_height_base():
    """What ``height: 100%`` fills: the screen below the status strip. The
    phone's screen root fits the system windows, so a full-height story or
    camera ends at the bottom of the display, not 24px past it."""
    return max(1, _style_viewport[1] - _STATUS_STRIP_HEIGHT)


def _resolve_css_size_tk(value, axis='width', viewport=None, percent_base=None):
    """Resolve px/dp, %, vw and vh into logical Preview pixels."""
    if value is None or str(value).strip() == '':
        return None
    width, height = viewport or _style_viewport
    text = str(value).strip().lower()
    if text in ('match_parent', 'fill'):
        return int(percent_base or (width if axis == 'width' else height))
    match = re.match(r'^(-?[\d.]+)\s*(px|dp|%|vw|vh)?$', text)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2) or 'px'
    if unit == '%':
        base = percent_base or (width if axis == 'width' else
                                (_percent_height_base() if viewport is None
                                 or tuple(viewport) == tuple(_style_viewport)
                                 else height))
        number = base * number / 100.0
    elif unit == 'vw':
        number = width * number / 100.0
    elif unit == 'vh':
        number = height * number / 100.0
    return max(0, int(round(number)))


# ── Typography helpers ────────────────────────────────────────────────────────

def get_native_font(css_family):
    """
    Mapeia uma CSS font-family genérica para a fonte nativa do sistema,
    garantindo fidelidade visual com o Android (Roboto ≈ Segoe UI no Windows).
    """
    is_win = os.name == 'nt'
    mapping = {
        'sans-serif': 'Segoe UI'    if is_win else 'Helvetica',
        'serif':      'Times New Roman',
        'monospace':  'Consolas'    if is_win else 'Courier',
    }
    if not css_family:
        return 'Segoe UI' if is_win else 'Helvetica'
    css_lower = css_family.strip().lower()
    for key, val in mapping.items():
        if key in css_lower:
            return val
    # Devolve o valor literal (ex: 'Roboto') como fallback
    return css_family.strip()


# Material's M2 bottom bar labels both states with textAppearanceCaption,
# 12sp; the name lives here where a test can hold it against the XML.
NAV_LABEL_SP = 12


def _nav_label_font(active=False):
    """The bottom-bar label font: 12px, bold for the active item.

    Negative size = exact pixels, the convention :func:`_build_tk_font`
    documents.  This used to be ``("Arial", 10, ...)``: ten *points* is
    13.3px at 96dpi.  The active item's bold is Material's
    (theme.NAV_ACTIVE_LABEL_BOLD); it was taken out once on the word of a
    phone that had lost every bold, and is back.
    """
    if active and NAV_ACTIVE_LABEL_BOLD:
        return (get_native_font(''), -NAV_LABEL_SP, 'bold')
    return (get_native_font(''), -NAV_LABEL_SP)


# ── Custom typefaces ──────────────────────────────────────────────────────────

_preview_fonts = _fonts.FontRegistry()
_FONT_LOAD_WARNED = set()

# FR_PRIVATE: the file is available to this process and never touches the
# fonts the person has installed.
_FR_PRIVATE = 0x10


def _install_font_file(path):
    """Ask the OS to make a font file available to Tk, for this process only.

    Windows is the platform this is verified on. Linux goes through fontconfig,
    which Tk's Xft backend reads from. macOS would need CoreText driven through
    ctypes, and writing that without a Mac to run it on is how you put a
    segfault in somebody else's Previewer -- so it declines instead, the app
    falls back to the nearest system family and says so once.
    """
    import sys
    if not os.path.exists(path):
        return False
    try:
        if sys.platform == 'win32':
            import ctypes
            add = ctypes.windll.gdi32.AddFontResourceExW
            add.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p)
            add.restype = ctypes.c_int
            return add(os.path.abspath(path), _FR_PRIVATE, None) > 0
        if sys.platform.startswith('linux'):
            import ctypes
            import ctypes.util
            library = ctypes.util.find_library('fontconfig')
            if not library:
                return False
            fc = ctypes.CDLL(library)
            fc.FcConfigGetCurrent.restype = ctypes.c_void_p
            fc.FcConfigAppFontAddFile.argtypes = (ctypes.c_void_p,
                                                  ctypes.c_char_p)
            fc.FcConfigAppFontAddFile.restype = ctypes.c_int
            return bool(fc.FcConfigAppFontAddFile(
                fc.FcConfigGetCurrent(),
                os.path.abspath(path).encode('utf-8'),
            ))
    except Exception:
        return False
    return False


_MARKDOWN_ROW_SIZE = 10


def _markdown_row_font():
    """A fonte de uma fatia de Markdown numa linha de coleccao."""
    return (('Segoe UI', _MARKDOWN_ROW_SIZE) if os.name == 'nt'
            else ('Helvetica', _MARKDOWN_ROW_SIZE))


def _markdown_row_tk_font():
    """A mesma fonte como objecto, que e' o que os estilos precisam para
    derivar negrito, italico e os tamanhos dos titulos."""
    import tkinter.font as _tkfont
    family, size = _markdown_row_font()
    return _tkfont.Font(family=family, size=size)


def _markdown_row_tags(text_widget, theme, accent, muted):
    """Aplica os estilos do Markdown a uma celula, com o mesmo codigo que o
    componente `markdown()` usa -- uma copia disto seria uma segunda maneira
    de desenhar um bloco de codigo."""
    from .features.rich_content import configure_markdown_tags
    configure_markdown_tags(
        text_widget, _markdown_row_tk_font(), theme, accent, muted)


def _fill_markdown_cell(text_widget, source, copy_code=False):
    """Escreve Markdown numa celula reciclada e da'-lhe a altura do conteudo.

    Uma celula e' reutilizada por linhas diferentes, por isso limpa-se sempre
    primeiro -- senao a resposta de uma mensagem aparecia colada a' seguinte.
    """
    text_widget.configure(state='normal')
    text_widget.delete('1.0', 'end')
    if not source:
        text_widget.configure(height=1, state='disabled')
        text_widget.pack_forget()
        return
    from .features.rich_content import render_markdown
    render_markdown(text_widget, source, copy_code=copy_code)
    # O renderizador termina cada linha com \n; o ultimo deixaria uma linha
    # vazia por baixo de cada mensagem.
    if text_widget.get('end-2c', 'end-1c') == '\n':
        text_widget.delete('end-2c', 'end-1c')
    text_widget.configure(state='disabled')
    if not text_widget.winfo_ismapped():
        text_widget.pack(fill='x', pady=(3, 0))
    _size_markdown_cell(text_widget)


def _grow_to_content(text_widget):
    """Add the rows a display-line count cannot see.

    ``displaylines`` counts lines of *text*. The Copy affordance under a fenced
    block is an embedded window, and a window is not a line -- so the cell was
    sized one button short and cut it in half. Measuring in pixels sees it, and
    the loop settles because each pass adds only the shortfall.
    """
    import math as _math

    for _ in range(3):
        text_widget.update_idletasks()
        try:
            needed = text_widget.count('1.0', 'end', 'ypixels')
        except Exception:
            return
        needed = int(needed[0]) if needed else 0
        available = text_widget.winfo_height()
        if needed <= 0 or available <= 0 or needed <= available:
            return
        try:
            rows = max(1, int(text_widget.cget('height')))
        except (TypeError, ValueError):
            return
        per_row = max(1.0, float(available) / rows)
        text_widget.configure(
            height=rows + max(1, int(_math.ceil(
                (needed - available) / per_row)))
        )


def _size_markdown_cell(text_widget):
    """Poe a altura do widget no numero de linhas que ele desenha mesmo.

    Tk nao sabe responder a isto antes de ter largura, por isso ha' um recuo
    por contagem de caracteres para a primeira passagem -- e uma segunda
    passagem em idle, quando a largura ja' existe, corrige.
    """
    try:
        text_widget.update_idletasks()
        width = text_widget.winfo_width()
        if width > 1:
            displayed = text_widget.count('1.0', 'end', 'displaylines')
            count = int(displayed[0]) if displayed else 1
            text_widget.configure(height=max(1, count))
            _grow_to_content(text_widget)
            return
    except Exception:
        pass
    import math as _math
    raw = text_widget.get('1.0', 'end-1c')
    estimate = sum(max(1, _math.ceil(len(line) / 44))
                   for line in raw.splitlines()) or 1
    text_widget.configure(height=max(1, estimate))
    text_widget.after_idle(lambda: _size_markdown_cell_again(text_widget))


def _size_markdown_cell_again(text_widget):
    try:
        if text_widget.winfo_exists() and text_widget.winfo_width() > 1:
            displayed = text_widget.count('1.0', 'end', 'displaylines')
            if displayed:
                text_widget.configure(height=max(1, int(displayed[0])))
    except Exception:
        pass


def _warn_font_once(key, message):
    if key in _FONT_LOAD_WARNED:
        return
    _FONT_LOAD_WARNED.add(key)
    print('[apkpy] ' + message)


def font(family, regular=None, bold=None, italic=None, bold_italic=None):
    """Register a typeface so ``font-family: "<family>"`` can reach it.

    The one thing that makes an app stop looking like every other app built
    with the same tool. Point the slots at ``.ttf`` or ``.otf`` files next to
    your code; the Android build copies them into the APK and the Previewer
    loads them for the length of the session, without installing anything.

    ~~~ python
    font("Tiempos",
         regular="assets/Tiempos-Regular.ttf",
         bold="assets/Tiempos-Bold.ttf")

    theme = Theme(font_family="Tiempos")
    ~~~

    Args:
        family:      The name CSS and ``Theme(font_family=...)`` will use.
        regular:     The upright face. Everything else falls back to it.
        bold:        Used for ``font-weight: bold``.
        italic:      Used for ``font-style: italic``.
        bold_italic: Used when both apply.

    Four slots, because four is what both sides can address. A weight you do
    not supply is synthesised -- faux bold, a sheared italic -- by Android and
    by Tk alike.

    On macOS the Previewer cannot load a font file and falls back to the
    nearest system family, with a note in the console. The APK is unaffected.
    """
    files = _fonts.normalise_files({
        'regular': regular, 'bold': bold,
        'italic': italic, 'bold_italic': bold_italic,
    })
    if not files:
        raise ValueError(
            'font("%s") needs at least one file, e.g. regular="Inter.ttf"'
            % family
        )

    tk_families = {}
    for slot, path in files.items():
        resolved = path if os.path.isabs(path) else os.path.abspath(path)
        if not os.path.exists(resolved):
            _warn_font_once(
                resolved,
                'font("%s", %s=...): no file at %s -- falling back to the '
                'system font. The Android build will report it too.'
                % (family, slot, path),
            )
            continue
        # Tk is asked for a family by name, so the file has to say what it is.
        # A file called Inter-Bold.ttf may introduce itself as "Inter" -- in
        # which case Tk picks the bold face on its own -- or as "Inter Bold",
        # which is a separate family and has to be named explicitly.
        name = _fonts.family_name_from_file(resolved)
        if not name:
            _warn_font_once(
                resolved,
                'font("%s", %s=...): %s is not a font file I can read.'
                % (family, slot, path),
            )
            continue
        if _install_font_file(resolved):
            tk_families[slot] = name
        else:
            _warn_font_once(
                'platform:' + family,
                'font("%s"): this platform will not load a font file into the '
                'Previewer, so the desktop shows the nearest system family. '
                'The font still ships in the APK.' % family,
            )

    return _preview_fonts.register(family, files, tk=tk_families)


def _body_text_size():
    """The ramp's body step -- the same figure the compiler writes as sp.

    This used to be 14 here and 16 there, which made every plain ``label()``
    a different size on the desktop than on the phone. Neither number was
    chosen over the other; they were picked independently years apart, because
    "body text" had no name for the two sides to share. Now it does, and the
    phone's figure is the one that wins.
    """
    return default_text_size(global_styles.get('__theme__'))


def _parse_font_size(style_dict, default=14):
    """Extrai font-size em px. Devolve 'default' se não definido."""
    raw = style_dict.get('font-size', '')
    cleaned = re.sub(r'[^0-9.]', '', str(raw))
    try:
        return int(float(cleaned))
    except (ValueError, TypeError):
        return default


def _parse_font_weight_tk(style_dict):
    """
    Devolve os modificadores de fonte Tkinter ('bold', 'italic', ou ambos).
    Retorna uma lista de strings para uso em font=(family, size, *modifiers).
    """
    weight = style_dict.get('font-weight', '').strip().lower()
    style  = style_dict.get('font-style',  '').strip().lower()
    mods = []
    if weight in ('bold', '700', '800', '900'):
        mods.append('bold')
    if style == 'italic':
        mods.append('italic')
    return mods


def _build_tk_font(style_dict, default_size=14):
    """
    Constrói uma tupla de fonte Tkinter a partir de um dicionário de estilos CSS.
    O tamanho é passado como NEGATIVO para que o Tkinter o interprete em píxeis
    (tamanho positivo = pontos; a 96 DPI 1pt = 1.333px, logo os textos ficam ~33%
    maiores do que o valor CSS indica). Com valor negativo ficamos 1 CSS-px = 1px
    no ecrã, igual ao dp no Android Studio.
    Ex: ('Segoe UI', -18, 'bold')  → 18 px exactos
    """
    size   = _parse_font_size(style_dict, default=default_size)
    mods   = _parse_font_weight_tk(style_dict)
    raw    = style_dict.get('font-family', '')
    entry  = _preview_fonts.lookup(raw)
    faces  = (entry or {}).get('tk') or {}
    if faces:
        # A registered typeface names its own faces. Whatever slot the
        # app did not supply stays in `mods`, so Tk fakes exactly what
        # Android fakes.
        slot, synth_bold, synth_italic = _fonts.resolve_slot(
            set(faces), 'bold' in mods, 'italic' in mods)
        if slot:
            mods = ((['bold'] if synth_bold else [])
                    + (['italic'] if synth_italic else []))
            return (faces[slot], -size, *mods)
    return (get_native_font(raw), -size, *mods)  # negativo = píxeis exactos


# --- Antialiased shapes -----------------------------------------------------
# Tk fills a polygon without antialiasing on Windows, so every rounded button,
# card, field and ring in the Previewer had stepped edges -- "ugly and
# pixelated" next to the same app on a phone, and a person trying ApkPy took
# the Previewer for what Android would show. Pillow is a dependency and the
# icons are already rasterised this way. A shape is now an image: the flat
# interior at its own size and the four corners drawn at 4x and scaled down,
# which costs 1-2 ms at any size (a whole 4x render of a tall card took 45).
# The canvas remembers each shape's parameters, so itemconfig(fill=...) -- the
# press tint, the theme fade -- redraws the image instead of failing on it.
# APKPY_PREVIEW_AA=0 draws the old polygons, to compare.

_AA_SCALE = 4
_AA_OPTIONS = frozenset({'fill', 'outline', 'width'})
_AA_KWARGS = frozenset({'fill', 'outline', 'width', 'tags', 'state'})
_AA_CACHE_LIMIT = 256
_AA_CORNERS = {}


def _aa_enabled():
    if os.environ.get('APKPY_PREVIEW_AA', '').strip() == '0':
        return False
    try:
        import PIL.Image  # noqa: F401
        import PIL.ImageTk  # noqa: F401
    except Exception:
        return False
    return True


def _aa_corner(r):
    """Coverage of a quarter disc of radius r, antialiased at 4x."""
    tile = _AA_CORNERS.get(r)
    if tile is None:
        from PIL import Image, ImageDraw
        s = _AA_SCALE
        big = Image.new('L', (r * s, r * s), 0)
        ImageDraw.Draw(big).ellipse((0, 0, 2 * r * s - 1, 2 * r * s - 1), fill=255)
        tile = big.resize((r, r), Image.BOX)
        _AA_CORNERS[r] = tile
    return tile


def _corner_tuple(r):
    """(top-left, top-right, bottom-right, bottom-left) from one radius or four."""
    if isinstance(r, (tuple, list)):
        return tuple(float(v) for v in r)
    return (float(r),) * 4


def _aa_mask(w, h, r):
    """Coverage of a w x h rounded rectangle: 255 inside, soft at the corners.
    ``r`` is one radius, or one per corner (a sheet rounded only on top)."""
    from PIL import Image
    mask = Image.new('L', (w, h), 255)
    tl, tr, br, bl = (int(min(round(v), w // 2, h // 2)) for v in _corner_tuple(r))
    if tl > 0:
        mask.paste(_aa_corner(tl), (0, 0))
    if tr > 0:
        mask.paste(_aa_corner(tr).transpose(Image.FLIP_LEFT_RIGHT), (w - tr, 0))
    if bl > 0:
        mask.paste(_aa_corner(bl).transpose(Image.FLIP_TOP_BOTTOM), (0, h - bl))
    if br > 0:
        mask.paste(_aa_corner(br).transpose(Image.ROTATE_180), (w - br, h - br))
    return mask


def _aa_rgba(canvas, color):
    """(r, g, b, a) for a colour Tk or ApkPy writes; None for no paint.

    ``#AARRGGBB`` keeps its alpha here -- the image composes over whatever
    the canvas has below it, which the polygon never could."""
    raw = str(color or '').strip()
    if not raw or _is_transparent(raw):
        return None
    alpha = 255
    if raw.startswith('#') and len(raw) == 9:
        alpha, raw = int(raw[1:3], 16), '#' + raw[3:]
    elif raw.startswith('#') and len(raw) == 5:
        alpha, raw = int(raw[1] * 2, 16), '#' + raw[2:]
    r, g, b = canvas.winfo_rgb(raw)
    return (r >> 8, g >> 8, b >> 8, alpha)


def _aa_shape_image(w, h, r, fill, outline, border):
    """RGBA image of the shape; the border lies inside the box, as Android's
    GradientDrawable strokes it."""
    from PIL import Image, ImageChops
    outer = _aa_mask(w, h, r)
    inner = outer
    ring = None
    if outline is not None and border > 0:
        if w > 2 * border and h > 2 * border:
            inner = Image.new('L', (w, h), 0)
            inner.paste(_aa_mask(w - 2 * border, h - 2 * border,
                                 tuple(max(c - border, 0) for c in _corner_tuple(r))),
                        (border, border))
            ring = ImageChops.subtract(outer, inner)
        else:
            inner, ring = Image.new('L', (w, h), 0), outer
    result = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    for colour, coverage in ((fill, inner), (outline, ring)):
        if colour is None or coverage is None:
            continue
        layer = Image.new('RGBA', (w, h), colour[:3] + (0,))
        a = colour[3]
        layer.putalpha(coverage if a == 255 else coverage.point(lambda v, a=a: v * a // 255))
        result = Image.alpha_composite(result, layer)
    return result


def _aa_photo(canvas, params):
    """A cached PhotoImage for these parameters, owned by the canvas's root
    (an image outlives neither the interpreter nor its window)."""
    from PIL import ImageTk
    fill = _aa_rgba(canvas, params['fill'])
    outline = _aa_rgba(canvas, params['outline'])
    try:
        border = int(round(float(params['width'] or 0)))
    except (TypeError, ValueError):
        border = 1
    key = (params['w'], params['h'], tuple(round(c, 2) for c in _corner_tuple(params['r'])),
           fill, outline, border)
    root = canvas._root()
    cache = root.__dict__.setdefault('_apkpy_aa_cache', {})
    photo = cache.pop(key, None)
    if photo is None:
        image = _aa_shape_image(params['w'], params['h'], params['r'],
                                fill, outline, border)
        photo = ImageTk.PhotoImage(image, master=canvas)
    cache[key] = photo                      # most recent last
    while len(cache) > _AA_CACHE_LIMIT:
        cache.pop(next(iter(cache)))        # shown images stay alive in the canvas
    return photo


# ── See-through widgets over pictures ────────────────────────────────────────
# Tk has no transparent widgets: a transparent button, label or row placed over
# an image was a square of whatever colour sat behind the image -- black boxes
# over a story, over a camera, where the phone shows the picture. An image
# canvas now remembers what it shows, and after layout every widget over it
# whose surface is its container's (which is what transparent resolves to)
# paints the part of the picture it covers under its own content. The shapes
# drawn on a canvas are RGBA, so their edges blend with it too.
_SEE_THROUGH_DELAY_MS = 60


def _set_backdrop(canvas, image, x=0, y=0):
    """Remember that ``canvas`` shows the PIL ``image`` with its top-left
    corner at canvas coordinates ``(x, y)``."""
    try:
        canvas._apkpy_backdrop = (image, int(round(x)), int(round(y)))
        _queue_see_through(canvas)
    except Exception:
        pass


def _queue_see_through(widget):
    """Run the see-through pass soon, once, whatever asked for it."""
    try:
        root = widget._root()
    except Exception:
        return
    if root.__dict__.get('_apkpy_see_queued'):
        return
    root._apkpy_see_queued = True

    def run():
        root._apkpy_see_queued = False
        try:
            _see_through_pass(root)
        except Exception:
            pass

    try:
        root.after(_SEE_THROUGH_DELAY_MS, run)
    except Exception:
        root._apkpy_see_queued = False


def _see_walk(widget):
    pending = [widget]
    while pending:
        current = pending.pop()
        yield current
        try:
            pending.extend(current.winfo_children())
        except Exception:
            pass


def _see_rgb(widget, colour):
    try:
        red, green, blue = widget.winfo_rgb(colour)
        return red >> 8, green >> 8, blue >> 8
    except Exception:
        return None


def _see_host(canvas):
    """The container whose other children may lie over this picture: the
    nearest one that lays its children out by coordinates."""
    widget = canvas.master
    while widget is not None:
        if widget.__dict__.get('_apkpy_relayout') is not None:
            return widget
        widget = widget.master
    return None


def _see_tile(canvas, backdrop_rgb, left, top, width, height):
    """The piece of the picture under a box at canvas coordinates."""
    from PIL import Image
    image, ox, oy = canvas._apkpy_backdrop
    if image.mode != 'RGB':
        base = Image.new('RGB', image.size, backdrop_rgb)
        if 'A' in image.getbands():
            base.paste(image.convert('RGBA'), (0, 0), image.convert('RGBA'))
        else:
            base.paste(image.convert('RGB'), (0, 0))
        image = base
    tile = Image.new('RGB', (width, height), backdrop_rgb)
    x1, y1 = max(left, ox), max(top, oy)
    x2 = min(left + width, ox + image.width)
    y2 = min(top + height, oy + image.height)
    if x2 > x1 and y2 > y1:
        tile.paste(image.crop((x1 - ox, y1 - oy, x2 - ox, y2 - oy)),
                   (x1 - left, y1 - top))
    return tile


def _see_install_canvas(widget):
    """Keep the borrowed picture at the bottom of a canvas that redraws."""
    if widget.__dict__.get('_apkpy_see_installed'):
        return
    widget._apkpy_see_installed = True
    original_delete = widget.delete
    original_lower = widget.tag_lower

    def restore():
        photo = widget.__dict__.get('_apkpy_see_photo')
        if photo is None:
            return
        try:
            if not widget.find_withtag('apkpy_see'):
                widget.create_image(0, 0, anchor='nw', image=photo, tags='apkpy_see')
            original_lower('apkpy_see')
        except Exception:
            pass

    def delete(*args):
        original_delete(*args)
        if 'all' in args:
            restore()

    def tag_lower(*args):
        original_lower(*args)
        if args and args[0] != 'apkpy_see':
            restore()

    widget.delete = delete
    widget.tag_lower = widget.lower_tag = tag_lower
    widget._apkpy_see_restore = restore


def _see_paint(widget, tile):
    from PIL import ImageTk
    photo = ImageTk.PhotoImage(tile, master=widget)
    widget._apkpy_see_photo = photo
    if isinstance(widget, tk.Canvas):
        _see_install_canvas(widget)
        try:
            tk.Canvas.delete(widget, 'apkpy_see')
        except Exception:
            pass
        widget._apkpy_see_restore()
    elif isinstance(widget, tk.Label):
        if '_apkpy_see_label' not in widget.__dict__:
            # A Label's 1px flat border is drawn in its background colour:
            # two dark lines either side of a caption over a picture.
            widget._apkpy_see_label = True
            widget.configure(padx=0, pady=0, bd=0)
        widget.configure(image=photo, compound='center')
    elif isinstance(widget, tk.Frame):
        under = widget.__dict__.get('_apkpy_see_under')
        if under is None:
            under = tk.Label(widget, bd=0, highlightthickness=0, padx=0, pady=0)
            under._apkpy_see_skip = True
            widget._apkpy_see_under = under
        under.configure(image=photo)
        under.place(x=0, y=0, relwidth=1, relheight=1)
        under.lower()
    else:
        return
    if not widget.__dict__.get('_apkpy_see_bound'):
        widget._apkpy_see_bound = True
        widget.bind('<Configure>', lambda _e, w=widget: _queue_see_through(w), add='+')


def _see_through_pass(root):
    canvases = [w for w in _see_walk(root)
                if isinstance(w, tk.Canvas) and w.__dict__.get('_apkpy_backdrop')]
    for canvas in canvases:
        if not canvas.winfo_ismapped():
            continue
        host = _see_host(canvas)
        if host is None:
            continue
        host_rgb = _see_rgb(host, host.cget('bg'))
        if host_rgb is None:
            continue
        cx, cy = canvas.winfo_rootx(), canvas.winfo_rooty()
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        chain = set()
        widget = canvas
        while widget is not None and widget is not host:
            chain.add(widget)
            widget = widget.master
        for widget in _see_walk(host):
            if widget is host or widget in chain:
                continue
            if widget.__dict__.get('_apkpy_see_skip'):
                continue
            if not isinstance(widget, (tk.Canvas, tk.Label, tk.Frame)):
                continue
            try:
                if not widget.winfo_ismapped():
                    continue
                wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
                ww, wh = widget.winfo_width(), widget.winfo_height()
            except Exception:
                continue
            if ww < 1 or wh < 1:
                continue
            if wx >= cx + cw or wy >= cy + ch or wx + ww <= cx or wy + wh <= cy:
                continue
            if _see_rgb(widget, widget.cget('bg')) != host_rgb:
                continue
            try:
                _see_paint(widget, _see_tile(canvas, host_rgb, wx - cx, wy - cy, ww, wh))
            except Exception:
                continue


def _aa_install(canvas):
    """Teach this canvas that some of its items are shapes drawn as images:
    fill, outline and width set on them redraw the image, and reading them
    returns what was set."""
    registry = canvas.__dict__.get('_apkpy_aa')
    if registry is not None:
        return registry
    registry = {}
    canvas._apkpy_aa = registry
    original_config = canvas.itemconfigure
    original_cget = canvas.itemcget
    original_delete = canvas.delete

    def itemconfigure(tag_or_id, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = dict(cnf, **kw)
            cnf = None
        if cnf is not None or not kw or not registry or not (_AA_OPTIONS & set(kw)):
            return original_config(tag_or_id, cnf, **kw)
        rest = {k: v for k, v in kw.items() if k not in _AA_OPTIONS}
        for item in canvas.find_withtag(tag_or_id):
            entry = registry.get(item)
            if entry is None:
                original_config(item, **kw)
                continue
            params = dict(entry[0])
            params.update({k: kw[k] for k in _AA_OPTIONS if k in kw})
            photo = _aa_photo(canvas, params)
            entry[0], entry[1] = params, photo
            original_config(item, image=photo, **rest)
        return None

    def itemcget(tag_or_id, option):
        if registry and option in _AA_OPTIONS:
            found = canvas.find_withtag(tag_or_id)
            if found and found[0] in registry:
                value = registry[found[0]][0].get(option)
                return '' if value is None else str(value)
        return original_cget(tag_or_id, option)

    def delete(*args):
        original_delete(*args)
        if registry:
            try:
                alive = set(canvas.find_all())
            except Exception:
                alive = set()
            for item in [i for i in registry if i not in alive]:
                del registry[item]

    canvas.itemconfigure = canvas.itemconfig = itemconfigure
    canvas.itemcget = itemcget
    canvas.delete = delete
    return registry


def _aa_shadow_photo(canvas, w, h, r, depth):
    """A soft shadow under a panel drawn at (1, 1, w - depth, h - depth).

    It replaces two near-black rounded layers offset down and to the right,
    which on a light screen read as a dark hard edge on two sides -- the
    "strange corner" under a bottom sheet -- where Android casts a blur.
    None without Pillow; the caller keeps the old layers."""
    if not _aa_enabled() or w < 8 or h < 8:
        return None
    try:
        from PIL import Image, ImageFilter, ImageTk
    except Exception:
        return None
    key = ('shadow', w, h, tuple(round(c, 2) for c in _corner_tuple(r)), depth)
    root = canvas._root()
    cache = root.__dict__.setdefault('_apkpy_aa_cache', {})
    photo = cache.pop(key, None)
    if photo is None:
        body_w, body_h = max(2, w - depth - 1), max(2, h - depth - 1)
        alpha = Image.new('L', (w, h), 0)
        # Light from above, as Material: the shadow falls a little down.
        alpha.paste(_aa_mask(body_w, body_h, r).point(lambda v: v * 70 // 255),
                    (1 + depth // 4, 1 + depth // 2))
        alpha = alpha.filter(ImageFilter.GaussianBlur(max(1.0, depth / 2.0)))
        image = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        image.putalpha(alpha)
        photo = ImageTk.PhotoImage(image, master=canvas)
    cache[key] = photo
    while len(cache) > _AA_CACHE_LIMIT:
        cache.pop(next(iter(cache)))
    return photo


def _aa_create(canvas, x1, y1, x2, y2, r, kwargs):
    """Draw the rounded rectangle as an antialiased image. None when it
    cannot be (no Pillow, an option only a polygon has, a colour Tk rejects),
    and the caller draws the polygon."""
    if set(kwargs) - _AA_KWARGS or not _aa_enabled():
        return None
    x, y = int(round(x1)), int(round(y1))
    w, h = int(round(x2)) - x, int(round(y2)) - y
    if w < 2 or h < 2:
        return None
    params = {'w': w, 'h': h, 'r': r,
              # A Tk polygon without -fill is black, and without -outline has none.
              'fill': kwargs.get('fill', 'black'),
              'outline': kwargs.get('outline', ''),
              'width': kwargs.get('width', 1)}
    try:
        photo = _aa_photo(canvas, params)
    except Exception:
        return None
    options = {'image': photo, 'anchor': 'nw'}
    for key in ('tags', 'state'):
        if key in kwargs:
            options[key] = kwargs[key]
    registry = _aa_install(canvas)
    item = canvas.create_image(x, y, **options)
    registry[item] = [params, photo]
    return item


def _create_circle(canvas, x1, y1, x2, y2, **kwargs):
    """A circle through the antialiased shape path: a rounded rectangle whose
    radius is half its side. Tk's create_oval has stepped edges on Windows --
    an avatar's initials, a switch, a slider's knob all looked cut out with
    scissors. Tk gives an oval a black outline unless told otherwise."""
    kwargs.setdefault('outline', 'black')
    side = min(x2 - x1, y2 - y1)
    return _create_rounded_rect(canvas, x1, y1, x2, y2, side / 2.0, **kwargs)


def _create_rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    """Draw a rounded rectangle with the same geometric radius as Android.

    Tk's smoothed control-point polygon visibly halved small radii, making an
    Android 18dp pill look almost square in the Previewer. Sampling the four
    quarter circles preserves the requested radius exactly.
    """
    import math
    # Tk keeps stroking a hairline when width is 0 as long as -outline is set.
    # CSS `border-width: 0` means no border, and that is what Android draws.
    try:
        if float(kwargs.get('width', 1) or 0) <= 0:
            kwargs.pop('outline', None)
            kwargs['width'] = 0
    except (TypeError, ValueError):
        pass
    corners = tuple(max(0.0, min(c, (x2 - x1) / 2, (y2 - y1) / 2))
                    for c in _corner_tuple(r))
    radius = max(corners)
    if radius <= 0:
        fill = kwargs.get('fill')
        if _is_transparent(fill) or _partial_alpha(fill):
            # Square, but clear or glass: only the image path has alpha, and
            # Tcl rejects "#00000000" outright.
            item = _aa_create(canvas, x1, y1, x2, y2, 0, kwargs)
            if item is not None:
                return item
            kwargs = dict(kwargs, fill=('' if _is_transparent(fill)
                                        else _tk_color(fill)))
        return canvas.create_rectangle(x1, y1, x2, y2, **kwargs)
    item = _aa_create(canvas, x1, y1, x2, y2,
                      corners if len(set(corners)) > 1 else radius, kwargs)
    if item is not None:
        return item
    segments = max(5, min(12, int(round(radius / 2)) + 2))
    points = []
    corners = (
        (x1 + radius, y1 + radius, math.pi, 1.5 * math.pi),
        (x2 - radius, y1 + radius, 1.5 * math.pi, 2 * math.pi),
        (x2 - radius, y2 - radius, 0, 0.5 * math.pi),
        (x1 + radius, y2 - radius, 0.5 * math.pi, math.pi),
    )
    for cx, cy, start, end in corners:
        for index in range(segments + 1):
            angle = start + (end - start) * index / segments
            points.extend((
                cx + math.cos(angle) * radius,
                cy + math.sin(angle) * radius,
            ))
    return canvas.create_polygon(points, smooth=False, **kwargs)


# ─── Animação Engine (Tkinter) ────────────────────────────────────────

def _hex_to_rgb(hex_color):
    """Converte cor hex (#RRGGBB) para tupla (r, g, b)."""
    hex_color = hex_color.strip('#')
    if len(hex_color) in (3, 4):
        hex_color = ''.join(c*2 for c in hex_color)
    if len(hex_color) == 8:                 # #AARRGGBB: the colour is the last six
        hex_color = hex_color[2:]
    try:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return (33, 33, 33)  # fallback


def _rgb_to_hex(r, g, b):
    """Converte (r, g, b) para string hex #RRGGBB."""
    return f'#{int(r):02x}{int(g):02x}{int(b):02x}'


def _lerp(a, b, t):
    """Interpola linearmente entre a e b com t em [0, 1]."""
    return a + (b - a) * t


def _parse_anim_val(raw, default=0.0):
    """Extrai valor numérico de uma string CSS (ex: '50px' -> 50.0)."""
    try:
        return float(re.sub(r'[^0-9.-]', '', str(raw)))
    except (ValueError, TypeError):
        return default


def _mix_hex(base, tint, amount):
    """Blend two hex colours. The pill is a tint of the bar, not a solid slab."""
    a, b = _hex_to_rgb(str(base)), _hex_to_rgb(str(tint))
    return _rgb_to_hex(*(_lerp(a[i], b[i], amount) for i in range(3)))


def _theme_background():
    """The real background behind an animating widget.

    A Tk widget has no alpha channel, so fading means interpolating its colour
    towards whatever is behind it.  This used to be the literal string
    ``#ffffff``: in a dark app -- and the bundled example is
    ``Theme(mode="dark")`` on ``#090B0D`` -- every fade flashed white.
    """
    tokens = global_styles.get('__theme__', {})
    return _hex_to_rgb(str(tokens.get('background', '#ffffff')))


def _motion_preset():
    return global_styles.get('__theme__', {}).get('motion', _motion.DEFAULT_PRESET)


_FADE_MAX_WIDGETS = 220
_FADE_STATE_ATTR = '_apkpy_fade_state'


def _collect_fade_targets(widget, targets, budget):
    """Every colour under ``widget`` that can stand in for an alpha channel.

    Tk has no per-widget alpha, so a fade means walking the subtree and
    interpolating each colour towards the theme background. Fading only the top
    widget would leave a card's text fully lit while its panel dimmed -- and
    would do nothing at all for a spinner or an empty state, which are canvases
    and frames rather than labels.
    """
    if budget[0] <= 0:
        return
    budget[0] -= 1
    for option in ('fg', 'bg'):
        try:
            value = widget.cget(option)
        except Exception:
            continue
        if value and str(value).startswith('#'):
            targets.append((widget, option, str(value), None))
    if isinstance(widget, tk.Canvas):
        try:
            items = widget.find_all()
        except Exception:
            items = ()
        for item in items:
            for option in ('fill', 'outline'):
                try:
                    value = widget.itemcget(item, option)
                except Exception:
                    continue
                if value and str(value).startswith('#'):
                    targets.append((widget, option, str(value), item))
    try:
        children = widget.winfo_children()
    except Exception:
        children = ()
    for child in children:
        _collect_fade_targets(child, targets, budget)


def _fade_component(widget, show, duration_ms, on_done=None):
    """Fade a widget and everything inside it.  True when it animated.

    What has to match the phone is the **duration and the presence** of the
    change, not the pixels: Android animates real alpha, and
    :func:`apkpy_lib.motion.duration` gives both sides the same number of
    milliseconds. When there is nothing colourable to interpolate this returns
    False and the caller applies the change at once -- a delay with nothing
    moving is worse than no animation.
    """
    # _app is lazy: touching an attribute builds the Tk window. Read the
    # instance directly, the way UploadsAPI._deliver does, so a hide() during
    # `apkpy build` cannot pop an empty Previewer.
    instance = getattr(_app, '_instance', None)
    root = getattr(instance, 'root', None)
    if widget is None or duration_ms <= 0 or root is None:
        return False
    try:
        if not widget.winfo_exists():
            return False
    except Exception:
        return False

    # True colours are remembered on the component and never re-read from a
    # widget that may be mid-fade. Without this a second fade starting over a
    # running one captured the interpolated value as the original and baked it
    # in: every show/hide cycle washed the component further towards the
    # background until cards and inputs were empty dark boxes.
    state = getattr(widget, _FADE_STATE_ATTR, None)
    if state is None:
        state = {'original': {}, 'token': 0}
        setattr(widget, _FADE_STATE_ATTR, state)
    remembered = state['original']

    found = []
    _collect_fade_targets(widget, found, [_FADE_MAX_WIDGETS])
    if not found:
        return False

    resolved = []
    for target, option, current, item in found:
        # The Tk path name, not id(): CPython reuses ids after a widget is
        # destroyed, which would map a rebuilt child onto a stale colour.
        key = (str(target), option, item)
        original = remembered.setdefault(key, current)
        resolved.append((target, option, _hex_to_rgb(original), original, item))

    state['token'] += 1
    token = state['token']
    background = _theme_background()
    frame_ms = 16
    total = max(1, int(duration_ms / frame_ms))

    def paint(amount, final=False):
        for target, option, rgb, original, item in resolved:
            value = original if final else _rgb_to_hex(
                _lerp(background[0], rgb[0], amount),
                _lerp(background[1], rgb[1], amount),
                _lerp(background[2], rgb[2], amount),
            )
            try:
                if item is None:
                    target.config(**{option: value})
                else:
                    target.itemconfig(item, **{option: value})
            except Exception:
                pass

    def _step(index):
        if state['token'] != token:
            return          # a newer fade took over; stop fighting it
        if index >= total:
            paint(1.0, final=True)
            if on_done:
                on_done()
            return
        progress = _motion.ease(index / float(total))
        paint(progress if show else 1.0 - progress)
        root.after(frame_ms, lambda: _step(index + 1))

    _step(0)
    return True


def _animate_widget(root, widget, style_dict, spacer=None, canvas=None,
                    fill_color=None, text_color=None):
    """Keyframe engine for the Tk Previewer.

    Reads ``animation-name``/``animation-duration``, finds the matching
    ``@keyframes`` and interpolates frame by frame with ``root.after``.

    Animated properties -- all four the Android generator supports, so a
    keyframe cannot work on the phone and do nothing here:

    * ``opacity``     -- interpolates the colour towards the theme background
    * ``margin-top``  -- the spacer frame above the widget
    * ``margin-left`` -- horizontal padding on the widget itself
    * ``scale``       -- canvas items where there is a canvas; elsewhere Tk
      cannot scale a widget, so it degrades to a fade of the same duration

    The curve is :func:`apkpy_lib.motion.ease`, the same cubic bezier the
    generated Android ``<set>`` names.
    """
    anim_name = style_dict.get('animation-name')
    if not anim_name:
        return
    frames = global_keyframes.get(anim_name)
    if not frames:
        return
    if _motion.is_disabled(_motion_preset()):
        return

    from_dict = frames.get('from', frames.get('0%', {}))
    to_dict   = frames.get('to',   frames.get('100%', {}))

    duration_ms = _motion.parse_duration(
        style_dict.get('animation-duration'), 600)
    frame_ms = 16  # ~60 fps
    total_frames = max(1, int(duration_ms / frame_ms))

    # ─ opacity ─────────────────────────────────────────
    do_opacity = 'opacity' in from_dict or 'opacity' in to_dict
    f_opacity  = _parse_anim_val(from_dict.get('opacity', 1.0), 1.0)
    t_opacity  = _parse_anim_val(to_dict.get('opacity',   1.0), 1.0)

    bg_rgb = _theme_background()
    if text_color:
        real_fg_rgb = _hex_to_rgb(text_color)
    else:
        try:
            actual_fg = (fill_color or '#e0e0e0') if canvas else widget.cget('fg')
            real_fg_rgb = _hex_to_rgb(actual_fg)
        except Exception:
            real_fg_rgb = (33, 33, 33)

    # ─ margin-top ──────────────────────────────────────
    do_margin = spacer is not None and (
        'margin-top' in from_dict or 'margin-top' in to_dict)
    f_margin  = _parse_anim_val(from_dict.get('margin-top', 0), 0)
    t_margin  = _parse_anim_val(to_dict.get('margin-top',   0), 0)

    # ─ margin-left ─────────────────────────────────────
    # Android translates the view on X; here the equivalent lever is the
    # widget's own horizontal padding inside its packer.
    target = widget if widget is not None else canvas
    do_margin_x = target is not None and (
        'margin-left' in from_dict or 'margin-left' in to_dict)
    f_margin_x = _parse_anim_val(from_dict.get('margin-left', 0), 0)
    t_margin_x = _parse_anim_val(to_dict.get('margin-left',   0), 0)
    if do_margin_x:
        try:
            do_margin_x = bool(target.pack_info())
        except Exception:
            do_margin_x = False

    # ─ scale ───────────────────────────────────────────
    has_scale = 'scale' in from_dict or 'scale' in to_dict
    f_scale = _parse_anim_val(from_dict.get('scale', 1.0), 1.0)
    t_scale = _parse_anim_val(to_dict.get('scale',   1.0), 1.0)
    do_scale = has_scale and canvas is not None
    if has_scale and not do_scale and not do_opacity:
        # Tk cannot scale a plain widget. Rather than silently doing nothing --
        # which is what happened before, and made `scale` look broken on the
        # desktop while it worked on the phone -- fade over the same duration.
        do_opacity = True
        f_opacity, t_opacity = (0.0, 1.0) if f_scale < t_scale else (1.0, 1.0)
    scale_state = [1.0]

    def _step(frame_idx):
        t_eased = _motion.ease(frame_idx / float(total_frames))

        if do_opacity:
            cur_opacity = _lerp(f_opacity, t_opacity, t_eased)
            if canvas is not None:
                fr = _hex_to_rgb(fill_color or '#e0e0e0')
                cur = _rgb_to_hex(
                    _lerp(bg_rgb[0], fr[0], cur_opacity),
                    _lerp(bg_rgb[1], fr[1], cur_opacity),
                    _lerp(bg_rgb[2], fr[2], cur_opacity),
                )
                try:
                    canvas.itemconfig('body', fill=cur)
                except Exception:
                    pass
            else:
                try:
                    widget.config(fg=_rgb_to_hex(
                        _lerp(bg_rgb[0], real_fg_rgb[0], cur_opacity),
                        _lerp(bg_rgb[1], real_fg_rgb[1], cur_opacity),
                        _lerp(bg_rgb[2], real_fg_rgb[2], cur_opacity),
                    ))
                except Exception:
                    pass

        if do_margin:
            try:
                spacer.config(height=max(0, int(_lerp(f_margin, t_margin, t_eased))))
            except Exception:
                pass

        if do_margin_x:
            try:
                offset = max(0, int(_lerp(f_margin_x, t_margin_x, t_eased)))
                target.pack_configure(padx=(offset, 0))
            except Exception:
                pass

        if do_scale:
            try:
                wanted = _lerp(f_scale, t_scale, t_eased) or 1.0
                factor = wanted / scale_state[0]
                width = canvas.winfo_width() or 1
                height = canvas.winfo_height() or 1
                canvas.scale('all', width / 2.0, height / 2.0, factor, factor)
                scale_state[0] = wanted
            except Exception:
                pass

        if frame_idx < total_frames:
            root.after(frame_ms, lambda: _step(frame_idx + 1))
            return

        # Exact final values: an eased curve must not leave a rounding residue.
        if do_opacity and canvas is None:
            try:
                widget.config(fg=text_color or _rgb_to_hex(*real_fg_rgb))
            except Exception:
                pass
        if do_margin:
            try:
                spacer.config(height=max(0, int(t_margin)))
            except Exception:
                pass
        if do_margin_x:
            try:
                target.pack_configure(padx=(max(0, int(t_margin_x)), 0))
            except Exception:
                pass

    _step(0)


# ─── ParamRef ─────────────────────────────────────────────────────────────────

class _ParamRef:
    """Referência lazy a um parâmetro de ecrã — re-avaliada no momento do render."""
    def __init__(self, screen, key, default):
        self.screen  = screen
        self.key     = key
        self.default = default
    def resolve(self):
        return str(self.screen._params.get(self.key, self.default))
    def __str__(self):
        return self.resolve()


# Reactive state + screen lifecycle

_reactive_state_counter = 0
_screen_lifecycles = {}


def _reactive_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _reactive_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


class ReactiveState:
    """Observable value shared by the Previewer and generated Android app."""

    def __init__(self, initial, id=None):
        global _reactive_state_counter
        _reactive_state_counter += 1
        self.id = str(id or f"state_{_reactive_state_counter}")
        self._value = initial
        self._bindings = []

    def get(self):
        return self._value

    def set(self, value):
        self._value = value
        self._publish()
        return value

    def increment(self, amount=1):
        try:
            value = self._value + amount
        except TypeError:
            value = float(self._value) + float(amount)
            if value.is_integer():
                value = int(value)
        return self.set(value)

    def decrement(self, amount=1):
        try:
            value = self._value - amount
        except TypeError:
            value = float(self._value) - float(amount)
            if value.is_integer():
                value = int(value)
        return self.set(value)

    def toggle(self):
        return self.set(not _reactive_bool(self._value))

    def bind(self, component, template="{value}"):
        if not hasattr(component, "set_value"):
            raise TypeError("ReactiveState.bind expects an ApkPy component")
        binding = {
            "kind": "value",
            "component": component,
            "template": str(template),
        }
        self._bindings.append(binding)
        self._apply_binding(binding)
        return component

    def bind_visibility(self, component, when=True):
        if not hasattr(component, "show") or not hasattr(component, "hide"):
            raise TypeError("ReactiveState.bind_visibility expects an ApkPy component")
        binding = {
            "kind": "visibility",
            "component": component,
            "when": bool(when),
        }
        self._bindings.append(binding)
        self._apply_binding(binding)
        return component

    def _apply_binding(self, binding):
        component = binding["component"]
        if binding["kind"] == "visibility":
            visible = _reactive_bool(self._value) is binding["when"]
            component._reactive_visible = visible
            component.show() if visible else component.hide()
            return
        text = binding["template"].replace("{value}", _reactive_text(self._value))
        component.set_value(text)

    def _publish(self):
        for binding in tuple(self._bindings):
            self._apply_binding(binding)


def state(initial, id=None):
    """Create an observable value that can drive one or more components."""
    return ReactiveState(initial, id=id)


def lifecycle(screen, on_mount=None, on_resume=None, on_pause=None, on_destroy=None):
    """Register callbacks matching the lifecycle of one screen."""
    callbacks = {
        "on_mount": on_mount,
        "on_resume": on_resume,
        "on_pause": on_pause,
        "on_destroy": on_destroy,
        "mounted": False,
    }
    for name, callback in callbacks.items():
        if name != "mounted" and callback is not None and not callable(callback):
            raise TypeError(f"lifecycle({name}=...) expects a callable")
    _screen_lifecycles[screen] = callbacks
    return callbacks


def _run_preview_lifecycle(screen, event):
    try:
        db._data_lifecycle(screen, event)
    except Exception as error:
        print("[data lifecycle]", error)
    info = _screen_lifecycles.get(screen)
    if not info:
        return
    callback = info.get(event)
    if callback is not None:
        callback()

# ─── ComponentDef ─────────────────────────────────────────────────────────────

def _queue_preview_relayout(widget):
    """Refresh rounded parent containers after a visibility change.

    Tk does not always emit ``<Configure>`` when a descendant is removed with
    ``pack_forget()``. Without an explicit refresh, the Canvas used by rounded
    ApkPy containers can keep its old height and leave an empty slot.
    """
    if widget is None:
        return
    try:
        root = widget.winfo_toplevel()
    except Exception:
        return

    def _refresh():
        try:
            root.update_idletasks()
            current = widget
            callbacks = []
            while current is not None:
                callback = getattr(current, '_apkpy_relayout', None)
                if callable(callback) and callback not in callbacks:
                    callbacks.append(callback)
                current = getattr(current, 'master', None)
            # Refresh from the closest container outwards so every parent
            # measures an already updated child.
            for callback in callbacks:
                callback()
                root.update_idletasks()
        except (tk.TclError, RuntimeError):
            pass

    try:
        root.after_idle(_refresh)
    except (tk.TclError, RuntimeError):
        pass


class ComponentDef:
    """
    Representa um componente de forma declarativa (antes de ser renderizado).
    Ao chamar button(..., screen=x) ou inputs(..., screen=x), é devolvido um
    ComponentDef que podes passar ao on_click_navigate().
    """
    def __init__(self, comp_type, **kwargs):
        self.comp_type = comp_type   # 'button' | 'inputs' | 'label' | 'container'
        self.kwargs = kwargs         # Inclui 'comp_id' para resolver estilos no render
        self.widget = None           # widget Tkinter (preenchido ao renderizar)
        self._tk_var = None          # StringVar / BooleanVar para radio/checkbox/range
        self.nav_target = None       # Screen de destino (definido por on_click_navigate)
        self.nav_data   = {}         # dados a passar ao navegar
        self.children = []           # Filhos se for um container
        self._initial_value = None   # Valor pendente se set_value for chamado antes do render
        self._param_ref = None       # _ParamRef guardado por set_value(screen.get_param(...))
        self._reactive_visible = None

    # ── Help, error and required, on a text field ───────────────────────────

    def set_error(self, text):
        """Show ``text`` under this field as an error, in the theme's error
        colour, with the field's line or outline in the same colour.
        ``set_error("")`` clears it and the help text comes back. Typing in
        the field clears it too."""
        _field_rules.check_type(self.kwargs.get('input_type', 'text')
                                if self.comp_type == 'inputs' else self.comp_type)
        _field_feature.set_error(self, text)

    def validate(self):
        """Check this field's ``required=`` rule: shows its error and
        returns False when the field is empty, clears it and returns True
        otherwise. A field with no rule is always valid."""
        _field_rules.check_type(self.kwargs.get('input_type', 'text')
                                if self.comp_type == 'inputs' else self.comp_type)
        return _field_feature.validate(self)

    # ── Leitura e Escrita de Valor ────────────────────────────────────────────

    def get_value(self):
        """
        Lê o valor actual do componente no Hot Previewer.

        - **inputs text/password/search**: devolve o texto digitado (string vazia
          se ainda mostrar o placeholder).
        - **inputs checkbox e switch**: devolve ``"true"`` ou ``"false"``, como no
          telemóvel.
        - **inputs range**: devolve o valor numérico do slider (int).
        - **inputs radio**: devolve a opção seleccionada (string).
        - **label**: devolve o texto visível.
        - Qualquer outro caso: devolve ``""``.
        """
        def _remembered():
            return self._initial_value if self._initial_value is not None else ""

        # A button answers its caption, as getText() does on the phone.
        if self.comp_type == 'button':
            return str(self.kwargs.get('text', ''))

        # Date / time picker
        if hasattr(self, '_date_var'):
            try:
                return self._date_var.get()  # "" se ainda não selecionado
            except tk.TclError:
                return _remembered()

        # Variável Tkinter (radio / checkbox / range)
        if self._tk_var is not None:
            try:
                val = self._tk_var.get()
                # o slider (range) usa DoubleVar p/ deslizar suave → devolve int
                if hasattr(self, '_range_redraw'):
                    return int(round(val))
                # A checkbox answers as the phone does, and as a switch
                # already did here: `agree.get_value() == "true"` was False
                # on the desktop, where it came back as the bool True.
                if isinstance(val, bool):
                    return "true" if val else "false"
                return val
            except Exception:
                return _remembered()

        if self.widget is None:
            return _remembered()

        try:
            # tk.Entry (text / password / search)
            if isinstance(self.widget, tk.Entry):
                val = self.widget.get()
                # Ignora o placeholder (texto cinzento que não é dados reais)
                if val == self.kwargs.get('placeholder', ''):
                    return ""
                return val
            # tk.Text (textarea)
            if isinstance(self.widget, tk.Text):
                val = self.widget.get("1.0", tk.END).rstrip("\n")
                if val == self.kwargs.get('placeholder', ''):
                    return ""
                return val
            # Canvas toggle (switch)
            if hasattr(self, '_toggle_var'):
                return "true" if self._toggle_var.get() else "false"
            # tk.Label
            if isinstance(self.widget, tk.Label):
                return self.widget.cget('text')
            # Fallback genérico com .get()
            if hasattr(self.widget, 'get'):
                return self.widget.get()
        except Exception:
            pass
        # Async callbacks are allowed to finish after their screen has been
        # replaced.  In that case the Tk widget is already destroyed, but the
        # value captured by ``_remember_screen_state`` remains authoritative.
        return _remembered()

    def set_items(self, items, title=None, subtitle=None, image=None,
                  has_more=True):
        """
        Atualiza dinamicamente os itens de uma lista ou coleção virtual.

        Aceita uma lista Python OU uma string JSON — por exemplo o resultado
        de db.query(...) ou o corpo de uma resposta https. Com `title=`,
        `subtitle=` e `image=` indicas que campo de cada objeto JSON mostrar
        (o `image=` é o URL da capa, para linhas ricas). Em
        ``virtual_collection`` o argumento ``has_more`` também conclui a
        tentativa de paginação ou refresh em curso:

            rows = db.query("SELECT name, artist, cover FROM tracks")
            my_list.set_items(rows, title="name", subtitle="artist", image="cover")
        """
        items = feeds_feature.normalize_items(items)
        if title is not None:
            mapped = []
            for row in items:
                if isinstance(row, dict):
                    # The whole row, so a tapped row's callback can read
                    # item["id"] -- the phone keeps every column too.
                    it = dict(row)
                    it['title'] = str(row.get(title, ''))
                    if subtitle is not None:
                        it['subtitle'] = str(row.get(subtitle, ''))
                    if image is not None:
                        it['image'] = str(row.get(image, ''))
                    mapped.append(it)
                else:
                    mapped.append(str(row))
            items = mapped
        # Guarda SEMPRE o valor: se o ecrã re-renderizar (ex.: voltar a um tab),
        # o _render_list relê o _initial_value — senão a lista voltava ao estado antigo.
        if self.comp_type == 'virtual_collection':
            return feeds_feature.replace_items(
                self, list(items), has_more=has_more
            )
        self._initial_value = list(items)
        if hasattr(self, '_tree_update_fn'):
            self._tree_update_fn(list(items))
        elif hasattr(self, '_list_update_fn'):
            self._list_update_fn(list(items))

    def append_items(self, items, has_more=True):
        """Append a page to ``virtual_collection`` without losing scroll."""
        return feeds_feature.append_items(self, items, has_more=has_more)

    def prepend_items(self, items):
        """Insert records before the current feed without losing scroll."""
        return feeds_feature.prepend_items(self, items)

    def update_item(self, item_id, changes, key="id", optimistic=False):
        """Patch one feed record selected by ``key``."""
        return feeds_feature.update_item(
            self, item_id, changes, key=key, optimistic=optimistic
        )

    def set_trailing(self, text):
        """Set the value a settings row shows on its right."""
        return self._set_row_field('trailing', text)

    def set_subtitle(self, text):
        """Set the second line of a settings row."""
        return self._set_row_field('subtitle', text)

    def _set_row_field(self, field, text):
        state = getattr(self, '_row_state', None)
        if state is None:
            self.kwargs[field] = text
            return
        state[field] = '' if text is None else str(text)
        try:
            self._row_redraw()
        except Exception:
            pass

    def stream(self, text, speed=None):
        """Type *text* into this label, a few characters at a time.

        What an answer arriving looks like. ``speed`` is ``slow``, ``normal``
        or ``fast``; ``instant`` -- and a theme with ``motion="none"`` -- puts
        the whole thing there at once, because somebody who turned animations
        off did not ask to watch text type itself.
        """
        full = str(text)
        chars, step = _motion.stream_step(speed, _motion_preset())
        if not chars or _app is None:
            self.set_value(full)
            return
        state = {'seen': 0}
        self.set_value('')

        def _tick():
            state['seen'] = min(len(full), state['seen'] + chars)
            self.set_value(full[:state['seen']])
            if state['seen'] < len(full):
                _app.root.after(step, _tick)

        _app.root.after(step, _tick)

    def stream_item(self, item_id, field, text, key="id", speed=None):
        """Type *text* into one field of one row, a few characters at a time.

        The chat case: add the row empty with ``merge_items`` and then stream
        the answer into it.
        """
        full = str(text)
        chars, step = _motion.stream_step(speed, _motion_preset())
        if not chars or _app is None:
            self.update_item(item_id, {field: full}, key=key)
            return
        state = {'seen': 0}
        self.update_item(item_id, {field: ''}, key=key)

        def _tick():
            state['seen'] = min(len(full), state['seen'] + chars)
            try:
                self.update_item(
                    item_id, {field: full[:state['seen']]}, key=key)
            except Exception:
                return
            if state['seen'] < len(full):
                _app.root.after(step, _tick)

        _app.root.after(step, _tick)

    def remove_item(self, item_id, key="id", optimistic=False):
        """Remove one feed record selected by ``key``."""
        return feeds_feature.remove_item(
            self, item_id, key=key, optimistic=optimistic
        )

    def merge_items(self, items, key="id"):
        """Upsert feed records while preserving the current order."""
        return feeds_feature.merge_items(self, items, key=key)

    def scroll_to_end(self):
        """Bring the newest row into view.

        The one thing a conversation needs and never had: you send a message,
        the answer lands under the fold, and you look at the message you just
        sent while the reply grows off-screen.
        """
        return feeds_feature.scroll_to_end(self)

    def scroll_to_top(self):
        """Bring the first row into view."""
        return feeds_feature.scroll_to_index(self, 0)

    def scroll_to_item(self, item_id, key="id"):
        """Bring one row into view, selected by the same key the mutations use."""
        return feeds_feature.scroll_to_item(self, item_id, key=key)

    def rollback(self, mutation_id=None):
        """Restore an optimistic mutation (the latest when omitted)."""
        return feeds_feature.rollback(self, mutation_id)

    def commit(self, mutation_id=None):
        """Accept an optimistic mutation and discard its snapshot."""
        return feeds_feature.commit(self, mutation_id)

    def finish_load(self, has_more=True):
        """Release a feed's loading latch after an empty page or an error."""
        return feeds_feature.finish_load(self, has_more=has_more)

    def refresh(self):
        """Trigger the callback configured with ``on_refresh``."""
        return feeds_feature.refresh(self)

    def _visibility_ms(self):
        """Duration for this component, from CSS ``transition:`` over the preset.

        The same call the Android generator makes, so the two cannot disagree
        about how long the change takes.
        """
        # ``transition`` is the one property that used to be read from the
        # id block alone, so ``body { transition: 400ms; }`` and
        # ``label { transition: 400ms; }`` were silently ignored while every
        # other property cascaded body -> type -> id.
        style = _merge_with_body(
            self.kwargs.get('comp_id'), self.comp_type)
        return _motion.duration(
            'visibility', _motion_preset(), style.get('transition'))

    def show(self):
        """Mostra o componente (ex: spinner) e, no caso do spinner, retoma a animação."""
        self._reactive_visible = True
        fn = getattr(self, '_component_show', None) or getattr(self, '_spin_show', None)
        if fn:
            try:
                fn()
            except tk.TclError:
                # Screens are rebuilt when navigating.  A callback can finish
                # while its component belongs to the previous (destroyed)
                # widget tree; visibility is still recorded above and will be
                # applied when the component is mounted again.
                pass
        elif self.widget is not None:
            try:
                self.widget.pack()
            except Exception:
                pass
        _fade_component(self.widget, True, self._visibility_ms())
        _queue_preview_relayout(self.widget)

    def hide(self):
        """Esconde o componente (ex: spinner) e pára a animação."""
        self._reactive_visible = False

        def _remove():
            fn = (getattr(self, '_component_hide', None)
                  or getattr(self, '_spin_hide', None))
            if fn:
                try:
                    fn()
                except tk.TclError:
                    # See ``show``: an async callback may complete while the
                    # original screen widget is no longer mounted.
                    pass
            elif self.widget is not None:
                try:
                    self.widget.pack_forget()
                except Exception:
                    pass
            _queue_preview_relayout(self.widget)

        # Fade first, then remove: taking the widget out immediately would
        # leave nothing to animate.
        if not _fade_component(self.widget, False, self._visibility_ms(), _remove):
            _remove()

    def set_value(self, value):
        """
        Escreve *value* no componente no Hot Previewer.

        - **inputs text/password/search**: substitui o conteúdo do campo.
        - **inputs checkbox**: define True/False (aceita também 0/1).
        - **inputs range**: define o valor do slider.
        - **inputs radio**: selecciona a opção que corresponda a *value*.
        - **label**: altera o texto visível.
        """
        if isinstance(value, _ParamRef):
            self._param_ref = value
            value = value.resolve()
        # A button's caption. The phone's setText() changed it and this
        # changed nothing: "Start" went on saying "Start" with the count
        # running. Kept in kwargs too, which is what the screen is drawn
        # from when it comes back.
        if self.comp_type == 'button':
            self.kwargs['text'] = str(value)
            retitle = getattr(self, '_retitle_btn', None)
            if retitle is not None:
                try:
                    retitle(_material_button_text(
                        value, self.kwargs.get('icon'), self.kwargs.get('variant')))
                except tk.TclError:
                    pass    # drawn on a screen that is gone; kwargs has it
            return
        # Date / time picker
        if hasattr(self, '_date_var'):
            try:
                self._date_var.set(str(value))
                if hasattr(self, '_date_lbl'):
                    tc = getattr(self, '_date_tc', '#212121')
                    self._date_lbl.config(text=str(value), fg=tc if value else '#9e9e9e')
            except Exception:
                pass
            return

        # Linha de definições desenhada em canvas — retitula e redesenha
        if hasattr(self, '_row_state'):
            self._row_state['text'] = str(value)
            try:
                self._row_redraw()
            except Exception:
                pass
            return

        # Canvas toggle (switch) — tratar antes do _tk_var genérico
        if hasattr(self, '_toggle_var'):
            try:
                self._toggle_var.set(str(value).lower() in ("true", "1", "yes", "on"))
                if hasattr(self, '_toggle_redraw'):
                    self._toggle_redraw()
            except Exception:
                pass
            return

        # Slider desenhado à mão (range) — define o valor E redesenha a bola
        if hasattr(self, '_range_redraw'):
            try:
                self._tk_var.set(float(value))
            except Exception:
                pass
            try:
                self._range_redraw()
            except Exception:
                pass
            return

        # Variável Tkinter (radio / checkbox / range)
        if self._tk_var is not None:
            try:
                self._tk_var.set(value)
            except Exception:
                pass
            return

        if self.widget is None:
            self._initial_value = value
            return

        try:
            # tk.Entry
            if isinstance(self.widget, tk.Entry):
                self.widget.delete(0, tk.END)
                placeholder = self.kwargs.get('placeholder', '')
                if not str(value) and placeholder:
                    # An empty field shows its hint again -- Android's
                    # android:hint does this on its own, and clearing the box
                    # after adding an item used to leave it blank and mute.
                    focused = False
                    try:
                        focused = self.widget.focus_get() is self.widget
                    except Exception:
                        focused = False
                    if not focused:
                        self.widget.config(show="")
                        self.widget.insert(0, placeholder)
                        self.widget.config(fg=getattr(
                            self, '_input_placeholder_color', '#9e9e9e'))
                        return
                if self.kwargs.get('input_type') == 'password':
                    self.widget.config(show="*")
                self.widget.insert(0, str(value))
                # Aplica a cor do texto correcto (não a cor de placeholder)
                try:
                    fg = getattr(self, '_input_text_color', None)
                    if not fg:
                        style = _merge_with_body(
                            self.kwargs.get('comp_id'), 'inputs'
                        )
                        fg = (
                            _get_style_fg(style)
                            or _get_style_fg(_get_body_style())
                            or '#212121'
                        )
                    self.widget.config(fg=fg)
                except Exception:
                    self.widget.config(fg='#212121')
                return
            # tk.Text (textarea)
            if isinstance(self.widget, tk.Text):
                self.widget.delete("1.0", tk.END)
                placeholder = self.kwargs.get('placeholder', '')
                if not str(value) and placeholder:
                    # Same rule as the single-line field above: an empty box
                    # shows its hint again, which is what android:hint does on
                    # its own.  Clearing a composer after sending used to leave
                    # the textarea blank and mute.
                    focused = False
                    try:
                        focused = self.widget.focus_get() is self.widget
                    except Exception:
                        focused = False
                    if not focused:
                        self.widget.insert("1.0", placeholder)
                        self.widget.config(fg=getattr(
                            self, '_input_placeholder_color', '#9e9e9e'))
                        return
                self.widget.insert("1.0", str(value))
                try:
                    fg = getattr(self, '_input_text_color', None)
                    if not fg:
                        style = _merge_with_body(
                            self.kwargs.get('comp_id'), 'inputs'
                        )
                        fg = (
                            _get_style_fg(style)
                            or _get_style_fg(_get_body_style())
                            or '#212121'
                        )
                    self.widget.config(fg=fg)
                except Exception:
                    self.widget.config(fg='#212121')
                return
            # tk.Label
            if isinstance(self.widget, tk.Label):
                before = (self.widget.winfo_reqwidth(), self.widget.winfo_reqheight())
                self.widget.config(text=str(value))
                # A container that places its children itself -- one with an
                # align-self, a position or a flex-grow among them -- measured
                # this label when it was drawn. Text that now takes more room,
                # or less, has to be measured again, as ApkpyLayout does on
                # the phone: a second line was drawn over whatever came next.
                if (self.widget.winfo_reqwidth(), self.widget.winfo_reqheight()) != before:
                    _queue_preview_relayout(self.widget)
                return
            # Fallback genérico com .set()
            if hasattr(self.widget, 'set'):
                self.widget.set(value)
        except Exception:
            pass

    def set_src(self, url):
        """Troca a imagem mostrada em runtime (ex.: capa do álbum no now_playing).
        Só faz efeito em componentes `image`. No Android compila para o
        carregamento remoto da capa pela barra now_playing."""
        self.kwargs['src'] = url
        fn = getattr(self, '_reload_image', None)
        if fn is not None:
            try:
                fn(str(url))
            except Exception:
                pass

    # Video controls live on the component so multiple players remain
    # independent and Android does not need a global playback singleton.
    def play(self):
        """Start or resume this ``video`` component."""
        fn = getattr(self, '_video_play', None)
        if fn is not None:
            fn()

    def pause(self):
        """Pause this ``video`` component without losing its position."""
        fn = getattr(self, '_video_pause', None)
        if fn is not None:
            fn()

    def stop(self):
        """Stop this ``video`` component and seek to the beginning."""
        fn = getattr(self, '_video_stop', None)
        if fn is not None:
            fn()

    def seek(self, seconds):
        """Seek this ``video`` component to ``seconds``."""
        fn = getattr(self, '_video_seek', None)
        if fn is not None:
            fn(seconds)

    def set_source(self, src, autoplay=False):
        """Replace the video source without recreating the component."""
        self.kwargs['src'] = src
        fn = getattr(self, '_video_set_source', None)
        if fn is not None:
            fn(src, autoplay)

    def set_speed(self, speed):
        """Change playback speed (for example ``0.75``, ``1`` or ``1.5``)."""
        fn = getattr(self, '_video_set_speed', None)
        if fn is not None:
            fn(speed)

    def set_muted(self, muted=True):
        """Mute or unmute this ``video`` component."""
        fn = getattr(self, '_video_set_muted', None)
        if fn is not None:
            fn(muted)

    # Map controls use the same component-scoped pattern as video controls.
    # Calling them before the map is rendered also updates the declarative
    # state, so navigation/re-rendering never resets the latest position.
    def set_center(self, latitude, longitude, zoom=None):
        """Move a ``map_view`` to a coordinate and optionally change zoom."""
        self.kwargs['latitude'] = latitude
        self.kwargs['longitude'] = longitude
        # An explicit recenter is a manual camera decision.  Live tracking can
        # opt back in with set_follow_user(True).
        self.kwargs['follow_user'] = False
        if zoom is not None:
            self.kwargs['zoom'] = zoom
        fn = getattr(self, '_map_set_center', None)
        if fn is not None:
            fn(latitude, longitude, zoom)

    def set_follow_user(self, enabled=True):
        """Enable or disable automatic camera follow for a ``map_view``.

        Enabling it recentres immediately when a live location is already
        known, and keeps following future GPS samples until the user pans or
        zooms the map.
        """
        enabled = bool(enabled)
        self.kwargs['follow_user'] = enabled
        fn = getattr(self, '_map_set_follow_user', None)
        if fn is not None:
            fn(enabled)

    def set_location(self, latitude, longitude, accuracy=0):
        """Update the live user marker on a ``map_view``."""
        self.kwargs['user_location'] = (latitude, longitude, accuracy)
        fn = getattr(self, '_map_set_location', None)
        if fn is not None:
            fn(latitude, longitude, accuracy)

    def set_markers(self, markers):
        """Replace all markers shown by a ``map_view``."""
        from .maps import _points
        markers = _points(markers)
        self.kwargs['markers'] = markers
        fn = getattr(self, '_map_set_markers', None)
        if fn is not None:
            fn(markers)

    def set_route(self, route):
        """Replace and persist the normalised route shown by a ``map_view``."""
        from .maps import _points
        route = _points(route)
        self.kwargs['route'] = route
        fn = getattr(self, '_map_set_route', None)
        if fn is not None:
            fn(route)

    def get_route(self):
        """Return a copy of the route currently shown by a ``map_view``."""
        from .maps import _points
        return [dict(point) for point in _points(self.kwargs.get('route'))]

    def set_zoom(self, zoom):
        """Change a ``map_view`` zoom level (2 to 19)."""
        self.kwargs['zoom'] = zoom
        fn = getattr(self, '_map_set_zoom', None)
        if fn is not None:
            fn(zoom)

    def clear_map_cache(self):
        """Clear tiles cached by this Preview map (Android clears its own cache)."""
        fn = getattr(self, '_map_clear_cache', None)
        if fn is not None:
            fn()


class _OverlayChildren(list):
    """What ``parent=<an overlay>`` appends to. Only a bottom sheet that
    names its screen holds components; anywhere else the component would
    show here and be dropped on the phone, so the line that asks is refused."""

    def __init__(self, overlay):
        super().__init__()
        self._overlay = overlay

    def append(self, comp):
        overlay = self._overlay
        if overlay.overlay_type != 'bottom_sheet':
            _sheet_rules.refuse(
                'Only a bottom sheet holds components; this is a %s.' % overlay.overlay_type,
                'parent=<a %s>' % overlay.overlay_type,
                suggestions=['Use bottom_sheet("...", screen=<its screen>) and parent=<the sheet>.'])
        if not overlay.kwargs.get('composed'):
            _sheet_rules.refuse(
                'This sheet has components in it but no screen.',
                'parent=<a bottom_sheet(%r) without screen=>' % overlay.kwargs.get('title', ''))
        super().append(comp)


class OverlayDef:
    """Declarative overlay shared by the Previewer and Android generator.

    Overlay definitions are intentionally detached from a ``Screen``. They do
    not occupy layout space and are only materialized when ``open()`` is
    called, which keeps both the Tk and Android trees lightweight.
    """

    def __init__(self, overlay_type, **kwargs):
        self.overlay_type = overlay_type
        self.kwargs = kwargs
        self.widget = None
        # A bottom sheet with screen= holds components: label(..., parent=sheet).
        self.children = _OverlayChildren(self)
        self._sheet = None

    def open(self):
        _show_overlay_preview(self)

    def close(self):
        global _active_preview_overlay
        widget = self.widget
        self.widget = None
        after_close = None
        if widget is not None:
            before_close = getattr(widget, '_apkpy_before_close', None)
            after_close = getattr(widget, '_apkpy_after_close', None)
            if before_close is not None:
                try:
                    before_close()
                except Exception:
                    pass
            for extra in getattr(widget, '_apkpy_overlay_extras', ()):
                try:
                    extra.destroy()
                except Exception:
                    pass
            try:
                widget.destroy()
            except Exception:
                pass
        if globals().get('_active_preview_overlay') is self:
            _active_preview_overlay = None
        if after_close is not None:
            after_close()


# ─── BottomNav ────────────────────────────────────────────────────────────────

def _remember_screen_state(screen):
    """Keep mutable Previewer values when a Screen is rebuilt after navigation."""
    def remember(comp):
        if comp.comp_type in ('inputs', 'input_field', 'label') and comp.widget is not None:
            try:
                if hasattr(comp.widget, 'winfo_exists') and not comp.widget.winfo_exists():
                    return
                comp._initial_value = comp.get_value()
            except Exception:
                pass
        for child in getattr(comp, 'children', []):
            remember(child)

    for component in getattr(screen, 'components', []):
        remember(component)


_active_bottom_nav = None  # singleton, set by bottom_nav()

class BottomNav:
    def __init__(self, screens, labels, icons, indicator="pill",
                 icons_active=None):
        self.indicator = indicator
        self.icons_active = list(icons_active or icons)
        self.screens = screens
        self.labels  = labels
        self.icons   = icons

def on_click_navigate(screen, data=None, transition="none"):
    """
    Navega para 'screen' passando dados opcionais.
    Usar dentro de command= lambdas ou funções.

    Exemplo:
        button("Ver detalhe", command=lambda: on_click_navigate(detail, data={"id": "42"}))
    """
    _job_rules.guard("navigation", "on_click_navigate(%s)" % getattr(screen, "id", ""))
    if data:
        screen._params = {k: str(v) for k, v in data.items()}
    if _app:
        _app.render_screen(screen, transition=transition)


def back():
    """Leave this screen for the one that opened it.

    The arrow in a header::

        button("", icon="arrow_back", describe="Back", command=back)

    On the phone it is ``finish()``: the screen closes and the one under it
    comes back as it was, with what was typed and how far it was scrolled --
    which is also what the system's Back gesture does. Opening the previous
    screen with ``on_click_navigate()`` instead puts a new copy of it on top,
    and Back then walks through the copies. On the first screen of the app,
    back() closes the app, as Back does; the Previewer, which has nowhere to
    go, stays where it is.
    """
    _job_rules.guard("navigation", "back()")
    if _app:
        _app.go_back()


_secure_screens = set()
_secure_everything = [False]


def secure_screen(screen=None):
    """Stop this screen being screenshotted, and blank it in the recents list.

        secure_screen(vault)     # just that one
        secure_screen()          # every screen

    On Android this is `FLAG_SECURE`: screenshots and screen recordings of the
    screen come out black, and the app's thumbnail in the recents carousel is
    hidden. Banking and messaging apps use it for exactly this.

    **The Previewer cannot honour it**, and does not pretend to -- Tk has no
    equivalent, and a desktop screenshot tool would capture the window anyway.
    It is recorded here so a test can see it was asked for. That is honest
    rather than lossy: on the phone the flag is invisible too, right up until
    someone tries to capture the screen.
    """
    if screen is None:
        _secure_everything[0] = True
    else:
        _secure_screens.add(getattr(screen, "id", str(screen)))


def secure_screen_asked(screen=None):
    """Whether ``secure_screen`` covers this screen. Used by tests."""
    if _secure_everything[0]:
        return True
    if screen is None:
        return bool(_secure_screens)
    return getattr(screen, "id", str(screen)) in _secure_screens


def bottom_nav(screens, labels=None, icons=None, indicator="pill",
               icons_active=None):
    """
    Adiciona uma barra de navegação inferior com tabs para cada screen.

    O item activo enche: uma pílula acende por trás do ícone e o ícone passa
    de contorno a preenchido. ``icons_active=`` substitui o preenchido por
    outro nome ou pelo teu ``.svg``; sem ele, a variante preenchida do mesmo
    nome é usada automaticamente.

    Exemplo:
        bottom_nav([home, profile, settings],
                   labels=["Home", "Profile", "Settings"],
                   icons=["home", "person", "settings"],
                   indicator="pill")
    """
    global _active_bottom_nav
    n = len(screens)
    _labels = list(labels) if labels else [s.id for s in screens]
    _icons  = list(icons)  if icons  else ['circle'] * n
    _active = list(icons_active) if icons_active else []
    while len(_labels) < n: _labels.append(screens[len(_labels)].id)
    while len(_icons)  < n: _icons.append('circle')
    while len(_active) < n: _active.append(_icons[len(_active)])
    _active_bottom_nav = BottomNav(
        screens, _labels, _icons,
        indicator=_motion.normalise_indicator(indicator),
        icons_active=_active,
    )
    return _active_bottom_nav


_active_mini_player = None  # singleton, set by mini_player()


def mini_player(open=None, id=None):
    """Mini-player FIXO — barra ancorada no fundo de TODOS os ecrãs que mostra a
    faixa atual (capa + título + artista + play/pause), lendo o leitor (audio).
    Esconde-se quando nada toca.

    Args:
        open: Screen a abrir ao tocar na barra (ex.: o leitor em grande).
        id:   CSS id. ``background-color``, ``color`` (title and play icon) and
              ``subtitle-color`` (artist); ``mini_player { }`` works too.

    No Android, a barra é gerada no XML de cada ecrã (acima do bottom_nav) e
    sondada a partir do media service. No preview, ancorada no fundo da janela.
    """
    global _active_mini_player
    _active_mini_player = {'open': open, 'id': id}
    return _active_mini_player


# ─── Screen ───────────────────────────────────────────────────────────────────

class Screen:
    """
    Container que agrupa componentes num ecrã.
    Cada Screen gera uma Activity separada no Android.

    Exemplo:
        login = Screen(id="login")
        label("Bem-vindo", screen=login)
        btn = button("Entrar", screen=login)
        login.on_click_navigate(button=btn, to=dashboard)
        run(start_screen=login)
    """

    def __init__(self, id, background_image=None, scroll=False, orientation=None):
        self.id = id
        self.background_image = background_image
        self.scroll = scroll
        # "portrait", "landscape" or "auto"; None for what run() says.
        self.orientation = _orientation_written(orientation, "Screen")
        self.components = []
        # Guardado para o language.set() poder reescrever as palavras de todos
        # os ecras, e nao so' do que esta' a' vista.
        _ALL_SCREENS.append(self)
        # App bars belong to the screen chrome, not to its scrolling component
        # list. Keeping this separate is what lets a normal toolbar stay fixed
        # and a sliver header collapse while the page scrolls underneath it.
        self.app_bar = None
        self._params = {}

    def _add(self, comp_def):
        self.components.append(comp_def)
        return comp_def

    def get_param(self, key, default=""):
        return _ParamRef(self, key, default)

    def on_click_navigate(self, button, to, data=None, transition="none"):
        button.nav_transition = _motion.normalise_transition(transition)
        button.nav_target = to
        button.nav_data   = data or {}


# ─── AppPreview ───────────────────────────────────────────────────────────────

def _prepare_preview_process_identity():
    """Give the Previewer its own Windows taskbar identity.

    Without an explicit AppUserModelID, Windows groups the Tk window under the
    Python interpreter and shows Python's icon even after the title-bar icon is
    changed. This must run before ``tk.Tk()`` creates the native window.
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ApkPy.Previewer"
        )
    except Exception:
        # Older Wine/Tk environments may not expose shell32. The Previewer
        # remains usable and still receives iconphoto below.
        pass


def _apply_windows_native_icon(root, ico_path):
    """Set both Win32 window icons instead of relying on Tk's fallback.

    ``iconphoto`` is enough on most desktops, but some Windows/Tk builds keep
    the Python executable icon for the taskbar or expose Tk's generic icon in
    the title bar.  WM_SETICON updates the real top-level HWND used by DWM and
    the taskbar.  The HICON objects remain alive until the Tk root is closed.
    """
    if os.name != "nt" or not os.path.isfile(ico_path):
        return

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        load_image = user32.LoadImageW
        load_image.argtypes = (
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        )
        load_image.restype = wintypes.HANDLE

        get_ancestor = user32.GetAncestor
        get_ancestor.argtypes = (wintypes.HWND, wintypes.UINT)
        get_ancestor.restype = wintypes.HWND

        hwnd = get_ancestor(wintypes.HWND(root.winfo_id()), 2)  # GA_ROOT
        if not hwnd:
            hwnd = wintypes.HWND(root.winfo_id())

        handles = getattr(root, "_apkpy_native_icon_handles", None)
        if not handles:
            image_icon = 1
            load_from_file = 0x0010
            icon_sizes = (
                (0, user32.GetSystemMetrics(49), user32.GetSystemMetrics(50)),
                (1, user32.GetSystemMetrics(11), user32.GetSystemMetrics(12)),
            )
            handles = []
            for icon_kind, width, height in icon_sizes:
                handle = load_image(
                    None,
                    ico_path,
                    image_icon,
                    max(1, width),
                    max(1, height),
                    load_from_file,
                )
                if handle:
                    handles.append((icon_kind, handle))
            root._apkpy_native_icon_handles = handles

        for icon_kind, handle in handles:
            user32.SendMessageW(hwnd, 0x0080, icon_kind, handle)  # WM_SETICON

        # Run once more after DWM has mapped the window. Reusing the same
        # handles is cheap and avoids a race seen in VS Code/terminal launches.
        if not getattr(root, "_apkpy_native_icon_recheck", False):
            root._apkpy_native_icon_recheck = True
            root.after(150, lambda: _apply_windows_native_icon(root, ico_path))
    except Exception:
        # An icon must never prevent the Previewer from starting.
        pass


def _apply_preview_window_icon(root):
    """Apply the packaged ApkPy mark to the title bar and taskbar."""
    assets = os.path.join(os.path.dirname(__file__), "assets")
    png_path = os.path.join(assets, "apkpy_preview.png")
    ico_path = os.path.join(assets, "apkpy_preview.ico")

    if os.name == "nt" and os.path.isfile(ico_path):
        try:
            # Apply the ICO first. iconphoto below is intentionally last so a
            # Tk fallback cannot replace the loaded PNG with a generic icon.
            root.iconbitmap(ico_path)
        except Exception:
            pass

    try:
        if os.path.isfile(png_path):
            photo = tk.PhotoImage(file=png_path)
            root.iconphoto(True, photo)
            # Tk only keeps a Tcl-side image reference reliably while Python
            # retains this object for the complete window lifetime.
            root._apkpy_preview_icon = photo
    except Exception:
        pass

    if os.name == "nt" and os.path.isfile(ico_path):
        # ``after_idle`` guarantees that Tk has created the native top-level
        # handle before WM_SETICON is sent.
        root.after_idle(lambda: _apply_windows_native_icon(root, ico_path))

class AppPreview:
    def __init__(self):
        _prepare_preview_process_identity()
        self.root = tk.Tk()
        install_tk_exception_hook(self.root)
        # The friendly printer stays; this only records the same failure where
        # crash.last() can find it, so the Previewer answers that call the way
        # the phone does instead of always saying "nothing happened".
        _printer = self.root.report_callback_exception

        def _record_then_print(error_type, error, tb):
            _record_preview_crash(error, tb)
            _printer(error_type, error, tb)

        self.root.report_callback_exception = _record_then_print
        self.root.title("APKPy Preview")
        _apply_preview_window_icon(self.root)
        # Pixel 9: 1080x2424 @ ~420dpi → 411x914 dp (resolução lógica)
        self.root.geometry("411x914")
        self.root.resizable(False, False)
        # The device standing up, and whether the person has turned it on its
        # side (Ctrl+Left / Ctrl+Right, the Android emulator's own keys). A
        # window that is the person's to resize has no upright size: None.
        self._upright = (411, 914)
        self._turned = False
        # The shape the window was last given. Never the one measured: a
        # desktop shorter than the phone hands back less than was asked, and
        # a shape that never matched would be asked for again on every draw.
        self._shape = (411, 914)
        self.root.configure(bg="#ffffff")

        # ── Barra de status ──────────────────────────────────────────────────
        self._status_frame = tk.Frame(
            self.root, bg="#ffffff", height=_STATUS_STRIP_HEIGHT)
        self._status_frame.pack_propagate(False)
        self._status_clock = tk.Label(
            self._status_frame, text="6:18", bg="#ffffff", fg="#111111",
            font=("Arial", 10, "bold"),
        )
        # Drawn, not typed. Signal, wifi and battery have no dependable glyphs
        # in a system font, and the ones this used to borrow read as dashes.
        self._status_icons = tk.Canvas(
            self._status_frame, bg="#ffffff", highlightthickness=0, bd=0,
            width=_STATUS_GLYPH_SIZE * len(STATUS_GLYPH_ORDER),
            height=_STATUS_STRIP_HEIGHT,
        )
        self._status_clock.pack(side="left", padx=8)
        self._status_icons.pack(side="right", padx=5)
        self._status_palette = ("#111111", "#ffffff")
        _draw_status_glyphs(self._status_icons, "#111111", "#ffffff")
        # The connection is the Previewer's to give and take away: a desk is
        # never offline, so nothing an app does without a connection would
        # ever be seen here. Bound before the notification shade binds the
        # strip, and it stops there: a click on the connection changes the
        # connection, and anywhere else on the strip still opens the shade.
        self._status_hint = None
        self._status_hint_after = None
        self._status_icons.bind('<ButtonRelease-1>', self._status_connection_click)
        self._status_icons.bind('<Motion>', self._status_connection_hover)
        self._status_icons.bind('<Leave>', self._status_connection_leave)



        # ── Bottom nav placeholder (packed last so it sits at bottom) ─────────
        self._bottom_nav_frame = None
        self._app_bar_frame = None
        self._app_bar_scroll_update = None

        # ── Corpo principal ──────────────────────────────────────────────────
        # Below the status strip, as on the phone: every screen root fits the
        # system windows (targetSdk 35 makes Android 15+ edge-to-edge), so
        # nothing the app draws sits under the clock. The strip keeps the
        # screen's or the app bar's colour, so it still reads as one surface.
        # The content started at y=0 here, and a 16px padding put the top
        # half of a row of chips behind the clock.
        self.body = tk.Frame(self.root, bg="#ffffff")
        self.body.pack(fill="both", expand=True, pady=(_STATUS_STRIP_HEIGHT, 0))
        self.layout = tk.Frame(self.body, bg="#ffffff")
        self.layout.pack(fill="both", expand=True)
        self.canvas = None
        self._scroll_canvas = None
        # Largura fixa da coluna de conteúdo (None = preenche a janela toda; com
        # valor = coluna de telemóvel centrada, usada no modo fullscreen).
        self._content_width = None

        # Initialize flex state
        self._is_flex = False
        self._flex_frame = None
        self._flex_side = tk.TOP
        self._flex_bg = "#ffffff"
        self._active_screen = None
        # The screens behind the current one, oldest first. Android keeps this
        # for free -- every Screen is an Activity and finish() returns to
        # whichever one started it. The Previewer swaps one widget tree for
        # another and used to remember nothing, so an app bar's back arrow was
        # drawn and did nothing: a settings screen you could open and not
        # leave.
        self._screen_stack = []
        # Alt+Left is the desktop's Back. Escape is deliberately left alone:
        # the overlays bind it themselves, and a modal that both closed and
        # navigated would be worse than no shortcut at all.
        self.root.bind_all('<Alt-Left>', self._system_back)
        self.root.bind_all('<Control-Left>', self._turn_device)
        self.root.bind_all('<Control-Right>', self._turn_device)
        self.root.protocol("WM_DELETE_WINDOW", self._close_preview)

    # ── which way up, and the bars ───────────────────────────────────────────

    def _way_up(self, screen):
        """``(way up, held)``: "portrait" or "landscape" for ``screen``, and
        whether the screen holds it or merely follows the device.

        What the screen asked while running wins over ``Screen(orientation=)``,
        which wins over ``run(orientation=)``. On a tablet nothing is held:
        Android 16 no longer lets an app choose there."""
        from .features import kit as _kit
        from . import kit_rules as _kit_rules
        kind = (_kit.display._for(screen).orientation
                or getattr(screen, 'orientation', None) or _app_orientation or 'auto')
        large = self._upright is not None and min(self._upright) >= _kit_rules.LARGE_SCREEN
        if kind == 'auto' or large:
            return ('landscape' if self._turned else 'portrait'), False
        return kind, True

    def _shape_for(self, screen):
        """Give the window the shape ``screen`` is shown in. Answers whether
        the shape changed."""
        if self._upright is None:
            return False
        narrow, tall = self._upright
        wanted = (tall, narrow) if self._way_up(screen)[0] == 'landscape' else (narrow, tall)
        if self._shape == wanted:
            return False
        self._shape = wanted
        self.root.geometry("%dx%d" % wanted)
        self.root.update_idletasks()
        return True

    def _show_bars(self, screen):
        """The status strip, or the whole window for a screen that asked for
        ``display.immersive()``."""
        from .features import kit as _kit
        hidden = bool(_kit.display._for(screen).immersive)
        try:
            if hidden:
                self._status_connection_leave()
                self._status_frame.place_forget()
            else:
                self._status_frame.place(x=0, y=0, relwidth=1, height=_STATUS_STRIP_HEIGHT)
                self._status_frame.lift()
            self.body.pack_configure(pady=(0 if hidden else _STATUS_STRIP_HEIGHT, 0))
        except Exception:
            pass

    def _display_asked(self):
        """What the screen on show asks of the display has changed."""
        screen = self._active_screen
        if screen is None:
            return
        self._show_bars(screen)
        if self._shape_for(screen):
            self._draw_again()

    def _draw_again(self):
        """Draw the screen on show again, in the shape the window now has --
        once the function that asked has returned, as the phone rebuilds a
        screen only after the call that turned it."""
        if getattr(self, '_draw_again_after', None) is not None:
            return

        def again():
            self._draw_again_after = None
            if self._active_screen is not None:
                self.render_screen(self._active_screen)

        self._draw_again_after = self._status_later(0, again)
        if self._draw_again_after is None:
            again()

    def _turn_device(self, _event=None):
        """Ctrl+Left / Ctrl+Right: the phone turned on its side, and back."""
        if self._upright is None or self._active_screen is None:
            return 'break'
        self._turned = not self._turned
        way, held = self._way_up(self._active_screen)
        if held:
            self._status_say("This screen stays in %s" % way)
        elif self._shape_for(self._active_screen):
            self._draw_again()
        return 'break'

    def _status_say(self, text, seconds=1.8):
        """A line under the strip that goes away by itself."""
        self._status_connection_leave()
        try:
            hint = tk.Label(
                self.root, text=text, bg='#2B2930', fg='#F5EFF7', padx=10, pady=6, bd=0,
                font=('Segoe UI', 9) if os.name == 'nt' else ('Helvetica', 9))
            hint.place(relx=1.0, x=-8, y=_STATUS_STRIP_HEIGHT + 4, anchor='ne')
            hint.lift()
        except Exception:
            return
        self._status_hint = hint
        self._status_hint_after = self._status_later(seconds, self._status_connection_leave)

    def _status_connection_click(self, event):
        if _status_glyph_at(event.x) not in _STATUS_CONNECTION_GLYPHS:
            return None
        from .features import kit as _kit
        _kit.network._switch()
        self._status_connection_hint(now=True)
        return "break"

    def _status_connection_hover(self, event):
        glyph = _status_glyph_at(event.x)
        over = glyph in _STATUS_CONNECTION_GLYPHS
        try:
            self._status_icons.configure(cursor="hand2" if over else "")
        except Exception:
            pass
        if not over:
            # The two glyphs display.* lights are nothing a phone draws, so
            # each says what it stands for.
            from .features import kit as _kit
            said = _kit.display._says(glyph)
            if not said:
                self._status_connection_leave()
            elif getattr(self._status_hint, '_apkpy_says', None) != said:
                self._status_say(said, seconds=4.0)
                if self._status_hint is not None:
                    self._status_hint._apkpy_says = said
        elif self._status_hint is None and self._status_hint_after is None:
            self._status_hint_after = self._status_later(0.45, self._status_connection_hint)

    def _status_later(self, seconds, work):
        # Not root.after(): that outlives the window, and Tk then prints
        # "invalid command name" at whoever closed the Previewer.
        from .features import kit_surfaces
        return kit_surfaces.later(self.root, seconds, work)

    def _status_connection_leave(self, _event=None):
        if self._status_hint_after is not None:
            try:
                self.root.after_cancel(self._status_hint_after)
            except Exception:
                pass
            self._status_hint_after = None
        if self._status_hint is not None:
            try:
                self._status_hint.destroy()
            except Exception:
                pass
            self._status_hint = None

    def _status_connection_hint(self, now=False):
        """Say what the connection is, under the strip. Nothing on the strip
        says it can be clicked, and three small glyphs do not say "you are
        offline" to somebody who was not looking at them."""
        self._status_connection_leave()
        said = _STATUS_CONNECTION[_status_connection()][0]
        try:
            hint = tk.Label(
                self.root, text=said if now else said + " · click to change",
                bg='#2B2930', fg='#F5EFF7', padx=10, pady=6, bd=0,
                font=('Segoe UI', 9) if os.name == 'nt' else ('Helvetica', 9))
            hint.place(relx=1.0, x=-8, y=_STATUS_STRIP_HEIGHT + 4, anchor='ne')
            hint.lift()
        except Exception:
            return
        self._status_hint = hint
        if now:
            self._status_hint_after = self._status_later(1.4, self._status_connection_leave)

    def _close_preview(self):
        try:
            location.stop_all()
        except Exception:
            pass
        try:
            from .routes import routes as _routes
            _routes.cancel_all()
        except Exception:
            pass
        if self._active_screen is not None:
            _run_preview_lifecycle(self._active_screen, "on_pause")
            _run_preview_lifecycle(self._active_screen, "on_destroy")
        self.root.destroy()

    # ── Multi-Screen ──────────────────────────────────────────────────────────

    def clear(self):
        """Remove todos os widgets do frame principal."""
        for widget in self.layout.winfo_children():
            widget.destroy()

    def _app_bar_palette(self, screen, fallback_bg):
        """Resolve one palette for both the status area and the toolbar."""
        bar = getattr(screen, 'app_bar', None)
        tokens = global_styles.get('__theme__', {})
        if bar is None:
            # The phone reads the colour behind the strip, not the mode.
            return fallback_bg, _system_icon_color(fallback_bg)
        kind = bar.comp_type
        comp_id = bar.kwargs.get('comp_id')
        style = _merge_with_body(comp_id, kind)
        return (
            _get_style_bg(style) or tokens.get('surface', fallback_bg),
            _get_style_fg(style) or tokens.get('text', '#FAFAFA'),
        )

    def _settle_layout(self):
        """Run the deferred container relayouts before the first paint.

        Rounded ApkPy containers re-measure themselves in ``after_idle``, so a
        freshly rendered screen was painted once with provisional heights --
        clipped cards, an input without its placeholder, a spinner overlapping
        the card -- and corrected a frame or two later. Doing that pass here
        means the screen is only ever shown settled.
        """
        root = self.root
        try:
            root.update_idletasks()
        except (tk.TclError, RuntimeError):
            return
        callbacks = []

        def walk(widget):
            try:
                children = widget.winfo_children()
            except (tk.TclError, RuntimeError):
                return
            for child in children:
                walk(child)
            callback = getattr(widget, '_apkpy_relayout', None)
            # Innermost first, so each parent measures a settled child.
            if callable(callback) and callback not in callbacks:
                callbacks.append(callback)

        target = self.layout
        if target is None:
            return
        walk(target)
        for callback in callbacks:
            try:
                callback()
                root.update_idletasks()
            except (tk.TclError, RuntimeError):
                return

    def _slide_screen(self, kind):
        """Slide the screen that was just rendered into place.

        Only the content moves: the bottom bar and the mini player are packed
        into the window, not into the layout, so they stay put -- which is also
        what happens on the phone, where the bar belongs to the Activity chrome.

        Returns False when it could not animate, so nothing pretends to.
        """
        kind = _motion.normalise_transition(kind)
        duration_ms = _motion.duration('screen', _motion_preset())
        if kind == 'none' or duration_ms <= 0:
            return False

        horizontal = kind == 'slide'
        self.root.update_idletasks()
        distance = (self.root.winfo_width() if horizontal
                    else self.root.winfo_height())
        if distance <= 1:
            return False

        canvas = self._scroll_canvas
        window_id = getattr(self, '_scroll_window_id', None)
        layout = self.layout
        if canvas is not None and window_id is not None:
            coords = list(canvas.coords(window_id)) + [0.0, 0.0]
            base_x, base_y = coords[0], coords[1]

            def apply(offset):
                canvas.coords(
                    window_id,
                    base_x + (offset if horizontal else 0),
                    base_y + (0 if horizontal else offset),
                )

            def restore():
                canvas.coords(window_id, base_x, base_y)
        else:
            try:
                packing = dict(layout.pack_info())
                siblings = layout.master.pack_slaves()
                index = siblings.index(layout)
                # pack_info() does not record the order among siblings, and
                # pack() appends. Without this the layout came back *after* the
                # app bar and covered it.
                follower = siblings[index + 1] if index + 1 < len(siblings) else None
            except Exception:
                # Managed by neither pack nor a canvas window: leave it alone.
                return False
            packing.pop('in', None)
            parent = layout.master
            self.root.update_idletasks()
            # The layout's own box, not the parent's: the app bar shares this
            # parent and must keep its strip while the content slides under it.
            base_x, base_y = layout.winfo_x(), layout.winfo_y()
            width = max(1, layout.winfo_width())
            height = max(1, layout.winfo_height())
            layout.pack_forget()

            def apply(offset):
                layout.place(
                    in_=parent,
                    x=base_x + (offset if horizontal else 0),
                    y=base_y + (0 if horizontal else offset),
                    width=width, height=height,
                )

            def restore():
                layout.place_forget()
                if follower is not None and follower.winfo_exists():
                    layout.pack(in_=parent, before=follower, **packing)
                else:
                    layout.pack(in_=parent, **packing)

        frame_ms = 16
        total = max(1, int(duration_ms / frame_ms))
        token = getattr(self, '_slide_token', 0) + 1
        self._slide_token = token

        def step(index):
            if getattr(self, '_slide_token', 0) != token:
                return          # another navigation started; abandon this one
            try:
                if index >= total:
                    restore()
                    return
                apply(distance * (1.0 - _motion.ease(index / float(total))))
                self.root.after(frame_ms, lambda: step(index + 1))
            except Exception:
                try:
                    restore()
                except Exception:
                    pass

        step(0)
        return True

    def _remember_for_back(self, target):
        """Record where a forward navigation came from.

        A screen already open behind us is brought forward rather than stacked
        a second time, which is what ``FLAG_ACTIVITY_REORDER_TO_FRONT`` does
        for the tabs of a ``bottom_nav`` -- without it, hopping between two
        tabs would grow the history for as long as you kept tapping.
        """
        previous = self._active_screen
        if previous is None or previous is target:
            return
        stack = self._screen_stack
        if target in stack:
            del stack[stack.index(target):]
            return
        stack.append(previous)

    def go_back(self):
        """Leave the current screen for the one that opened it.

        The Previewer's answer to ``finish()``. Returns False when there is
        nothing behind, which on a phone is where Back closes the app -- the
        Previewer stays put instead of shutting its own window.
        """
        if not self._screen_stack:
            return False
        from .features import kit as _kit
        _kit.display._closed(self._active_screen)
        self.render_screen(self._screen_stack.pop(), _from_back=True)
        return True

    def _system_back(self, _event=None):
        """Alt+Left: what the phone's Back gesture does, for a desktop window.

        A screen whose app bar has no back arrow -- or no app bar at all -- is
        still perfectly leaveable on Android, because the system provides the
        gesture. Without an equivalent, the Previewer would keep the trap for
        every screen that does not draw its own arrow.

        The order matters and is Android's: an open drawer closes first,
        before Back is allowed to leave the screen.
        """
        from .features import kit as _kit
        if _kit.app_lock._locked:
            # Locked, Back leaves the app as Home does: on the phone the task
            # goes behind, and here the window does.
            try:
                self.root.iconify()
            except Exception:
                pass
            return 'break'
        if getattr(self, '_drawer_panel', None) is not None:
            self.close_drawer()
            return 'break'
        self.go_back()
        return 'break'

    def render_screen(self, screen, transition=None, _from_back=False):
        global _style_viewport
        if not _from_back:
            self._remember_for_back(screen)
        # Which way up this screen is decides the size everything is laid
        # out in, so the window takes its shape before anything is measured.
        self._shape_for(screen)
        self.root.update_idletasks()
        viewport_width = self._content_width or max(1, self.root.winfo_width())
        viewport_height = max(1, self.root.winfo_height())
        _style_viewport = (viewport_width, viewport_height)
        """Limpa o ecrã e renderiza todos os componentes de um Screen."""
        if self._active_screen is not None:
            _run_preview_lifecycle(self._active_screen, "on_pause")
            _remember_screen_state(self._active_screen)
        # Remover bind_all de scroll anterior (evita acumulação entre renders)
        if getattr(self, '_root_scroll_bind_id', None):
            try:
                self.root.unbind_all('<MouseWheel>')
            except Exception:
                pass
            self._root_scroll_bind_id = None

        # Destruir layout anterior completamente para recriar estrutura scroll/no-scroll
        for overlay in getattr(self, '_screen_overlays', []) or []:
            try:
                overlay.destroy()
            except Exception:
                pass
        self._screen_overlays = []
        if self.layout:
            self.layout.destroy()
        if self._scroll_canvas:
            self._scroll_canvas.destroy()
            self._scroll_canvas = None
        if self._app_bar_frame:
            self._app_bar_frame.destroy()
            self._app_bar_frame = None
        self._app_bar_scroll_update = None
        self.canvas = None

        # Ler estilos do ecrã (identificado pelo screen.id)
        load_styles_now()
        screen_style = _merge_with_body(screen.id)

        # Cor de fundo do ecrã: ID específico > body > branco
        body_bg = _get_style_bg(_get_body_style())
        screen_bg_css = _get_style_bg(screen_style) or body_bg or '#ffffff'
        screen_bg_tk  = screen_bg_css if screen_bg_css.startswith('#') else '#ffffff'
        self.body.configure(bg=screen_bg_tk)

        # A real Android status bar occupies these pixels, but it is visually
        # part of the app bar. Keep the clock/icons and remove the detached
        # black strip by sharing the exact toolbar palette.
        status_bg, status_fg = self._app_bar_palette(screen, screen_bg_tk)
        self._status_frame.configure(bg=status_bg)
        self._status_clock.configure(bg=status_bg, fg=status_fg)
        self._status_icons.configure(bg=status_bg)
        self._status_palette = (status_fg, status_bg)
        _draw_status_glyphs(self._status_icons, status_fg, status_bg)
        # Overlay the system information inside the app's top surface instead
        # of reserving a second 24px row above it. A screen that asked for
        # display.immersive() has no strip at all.
        self._show_bars(screen)

        notifications._refresh()

        # The app bar is packed before the content canvas, therefore it remains
        # fixed without consuming screen padding or becoming part of the page.
        self._render_app_bar(screen, screen_bg_tk)

        if getattr(screen, 'scroll', False):
            # ── Layout com scroll vertical ───────────────────────────────────
            sc = tk.Canvas(self.body, bg=screen_bg_tk, highlightthickness=0)
            if self._content_width:
                # coluna de telemóvel centrada (fullscreen): largura fixa, fill='y'
                # + expand=True faz o Tk centrá-la horizontalmente no espaço livre.
                sc.configure(width=self._content_width)
                sc.pack(fill='y', expand=True)
            else:
                sc.pack(fill='both', expand=True)
            inner = tk.Frame(sc, bg=screen_bg_tk)
            win_id = sc.create_window((0, 0), window=inner, anchor='nw')

            # Atualizar scrollregion com as dimensões reais do inner frame
            def _on_frame_configure(e, _sc=sc):
                _sc.configure(scrollregion=(0, 0, e.width, e.height))
            # Ajustar largura do inner ao canvas para os widgets não ficarem estreitos
            def _on_canvas_configure(e, _sc=sc, _wid=win_id, _style=screen_style):
                max_width = _resolve_css_size_tk(
                    _style.get('max-width'), 'width', _style_viewport, e.width
                )
                target = min(e.width, max_width) if max_width else e.width
                _sc.coords(_wid, max(0, (e.width - target) // 2), 0)
                _sc.itemconfig(_wid, width=target)

            inner.bind('<Configure>', _on_frame_configure)
            sc.bind('<Configure>', _on_canvas_configure)

            self.layout = inner
            self._scroll_window_id = win_id
            self._scroll_canvas = sc
            self.canvas = sc

            # bind_all garante scroll mesmo com cursor sobre Entry/Text/Canvas filhos
            def _on_wheel(e, _sc=sc):
                # Deixar o scroll da list_view tratar os seus próprios eventos
                if isinstance(e.widget, tk.Canvas) and e.widget is not sc:
                    return
                _sc.yview_scroll(int(-1 * (e.delta / 120)), 'units')
                if self._app_bar_scroll_update:
                    self._app_bar_scroll_update(max(0, int(_sc.canvasy(0))))
            self.root.bind_all('<MouseWheel>', _on_wheel)
            self._root_scroll_bind_id = True
        else:
            # ── Layout simples sem scroll ────────────────────────────────────
            self.layout = tk.Frame(self.body, bg=screen_bg_tk)
            if self._content_width:
                self.layout.configure(width=self._content_width)
                self.layout.pack(fill='y', expand=True)
                self.layout.pack_propagate(False)  # respeita a largura fixa
            else:
                max_width = _resolve_css_size_tk(
                    screen_style.get('max-width'), 'width', _style_viewport,
                    viewport_width,
                )
                if max_width and max_width < viewport_width:
                    self.layout.configure(width=max_width)
                    self.layout.pack(fill='y', expand=True)
                    self.layout.pack_propagate(False)
                else:
                    self.layout.pack(fill='both', expand=True)

        # Determinar orientação flex
        flex_dir = _get_flex_orientation(screen_style)  # 'row' | 'column'
        is_flex  = screen_style.get('display', '').strip().lower() in ('flex', 'grid')
        # A screen that says nothing about padding has 5px above and below
        # and 10px at the sides, as the compiler writes it. The Previewer had
        # none, and made up for it with 12px on top only -- which it kept
        # adding under `padding: 0px`, where the phone starts at the edge.
        padding_style = screen_style
        if not str(screen_style.get('padding') or '').strip():
            padding_style = dict(screen_style, padding='5px 10px 5px 10px')
        pad_t, pad_r, pad_b, pad_l = _parse_padding_tk(padding_style)

        if is_flex:
            # Container flex: um Frame horizontal ou vertical
            pack_side = tk.LEFT if flex_dir == 'row' else tk.TOP
            flex_frame = tk.Frame(self.layout, bg=screen_bg_tk)
            flex_frame.pack(fill='both', expand=True,
                            padx=(pad_l, pad_r), pady=(pad_t, pad_b))
            # Guardar referencia para os _render_* usarem como parent
            self._flex_frame  = flex_frame
            self._flex_side   = pack_side
            self._flex_bg     = screen_bg_tk
            self._is_flex     = True
        else:
            # Layout normal: scroll vertical
            normal_frame = tk.Frame(self.layout, bg=screen_bg_tk)
            normal_frame.pack(fill='both', expand=True,
                              padx=(pad_l, pad_r), pady=(pad_t, pad_b))
            self._normal_content_frame = normal_frame
            self._flex_frame  = None
            self._flex_side   = None
            self._flex_bg     = screen_bg_tk
            self._is_flex     = False

        # Re-avaliar param bindings antes de renderizar (set_value(screen.get_param(...)))
        def _refresh_param_refs(comps):
            for comp in comps:
                if getattr(comp, '_param_ref', None) is not None:
                    comp.widget = None
                    comp._initial_value = comp._param_ref.resolve()
                _refresh_param_refs(getattr(comp, 'children', []))
        _refresh_param_refs(screen.components)

        # The screen's `gap` (a Theme's body gives 12px) goes between its own
        # children, as the compiler writes it: a margin on every child but
        # the first, in the flow's direction. The Previewer only spaced a
        # container's children, and a profile's grid began 32px higher here
        # than on the phone.
        gap_match = re.search(r'(\d+)', str(screen_style.get('gap', '0')))
        screen_gap = int(gap_match.group(1)) if gap_match else 0
        root_side = getattr(self, '_flex_side', None) or tk.TOP
        placed_one = False
        # The compiler's 6dp between stacked children is drawn here as a
        # label's own 2px above and below; a gap takes its place on both
        # sides, so a label on a spaced screen drops them.
        self._container._apkpy_stack_gap = screen_gap

        # Loop raiz
        overlay_comps = []
        for comp in screen.components:
            if str(_preview_child_layout_style(comp).get('position', '')).strip().lower() == 'absolute':
                overlay_comps.append(comp)
                continue
            target = self._container
            before = set(target.pack_slaves())
            self._render_comp(comp, target, getattr(self, '_is_flex', False), getattr(self, '_flex_side', tk.TOP), self._bg)
            added = [w for w in target.pack_slaves() if w not in before]
            if not added:
                continue
            if placed_one and screen_gap:
                _add_leading_gap(added[0], screen_gap, root_side == tk.LEFT)
            placed_one = True

        self._active_screen = screen
        # The panel belongs to the screen it was opened over; on the phone
        # a new Activity takes the whole window with it.
        self._drawer_panel = None
        self._drawer_scrim = None

        # Bottom navigation bar (rendered after content so it sits below)
        self._render_bottom_nav(screen)
        # Mini-player fixo (acima do bottom_nav, se houver)
        self._render_mini_player(screen)
        self._render_screen_overlays(overlay_comps, screen_bg_tk)

        # What a screen has that is not in its layout -- a banner ad's place --
        # is the screen's, and comes back with it.
        from .features import kit as _kit
        _kit.screen_shown(screen)

        lifecycle_info = _screen_lifecycles.get(screen)
        if lifecycle_info is not None and not lifecycle_info["mounted"]:
            lifecycle_info["mounted"] = True
            _run_preview_lifecycle(screen, "on_mount")
        _run_preview_lifecycle(screen, "on_resume")

        self._settle_layout()
        if transition:
            self._slide_screen(transition)

    def _render_screen_overlays(self, comps, bg):
        """A screen's own ``position: absolute`` children, over its content.

        They were laid out in the column with everything else: no floating
        button, no composer pinned to the bottom -- on the desktop and on the
        phone. Both now put them on a layer above the content, fixed like a
        floating button, placed by the same rules as an absolute child of a
        container (``layout_engine``). Tk cannot see through a widget: over
        anything but the screen's own colour a transparent one shows it."""
        area = self._scroll_canvas or self.layout
        if not comps or area is None:
            return
        entries = []
        for comp in comps:
            slot = tk.Frame(self.body, bg=bg, bd=0, highlightthickness=0)
            self._render_comp(comp, slot, False, tk.TOP, bg)
            self._screen_overlays.append(slot)
            entries.append((slot, _preview_child_layout_style(comp), comp))

        def place(event=None):
            try:
                # Let the containers inside finish their own layout pass (an
                # idle callback) so their requested height is the real one.
                area.update_idletasks()
                width, height = area.winfo_width(), area.winfo_height()
                if width <= 1 or height <= 1:
                    return
                live = [(slot, style) for slot, style, comp in entries
                        if getattr(comp, '_reactive_visible', True) is not False]
                items = []
                for slot, style in live:
                    req_w = max(1, slot.winfo_reqwidth())
                    if _shrinks_to_fit(style):
                        req_w = _natural_width(slot, req_w)
                    items.append({'style': style, 'width': req_w,
                                  'height': max(1, slot.winfo_reqheight())})
                boxes, _needed = compute_layout_boxes(
                    {'display': 'flex', 'flex-direction': 'column'}, items, width,
                    height=height, viewport=_style_viewport,
                )
                for slot, style, comp in entries:
                    slot.place_forget()
                for (slot, _style), box in zip(live, boxes):
                    if box is None:
                        continue
                    x, y, box_w, box_h, _z = box
                    slot.place(in_=area, x=round(x), y=round(y),
                               width=max(1, round(box_w)), height=max(1, round(box_h)))
                    slot.lift()
            except tk.TclError:
                pass

        pending = {'queued': False}

        def queue(event=None):
            if not pending['queued']:
                pending['queued'] = True

                def run():
                    pending['queued'] = False
                    place()
                area.after_idle(run)

        for slot, _style, _comp in entries:
            # show()/hide() walk up the widget tree looking for this.
            slot._apkpy_relayout = queue
            # A container learns its height from its own layout pass, after
            # this one: follow it, or a composer pinned to the bottom is 1px.
            for child in slot.winfo_children():
                child.bind('<Configure>', queue, add='+')
        area.bind('<Configure>', queue, add='+')
        queue()

    # ── Navigation drawer ────────────────────────────────────────────────────

    def open_drawer(self):
        """Slide the navigation panel in over the current screen."""
        definition = _app_drawer[0]
        if definition is None or getattr(self, '_drawer_panel', None) is not None:
            return
        style = _merge_with_body(definition.comp_id, 'drawer')
        theme = global_styles.get('__theme__', {})
        surface = _tk_color(_get_style_bg(style), theme.get('surface', '#FFFFFF'))
        fg = _tk_color(_get_style_fg(style), theme.get('text', '#111111'))
        muted = _tk_color(style.get('subtitle-color'),
                          theme.get('text_secondary', '#6B7280'))
        accent = _tk_color(style.get('active-color'),
                           theme.get('primary', '#6750A4'))
        pill = _tk_color(style.get('indicator-color'),
                         _mix_color(surface, accent, 0.22))
        line = _tk_color(style.get('divider-color'),
                         theme.get('border', '#E2E8F0'))
        radius = _parse_radius({'border-radius': style.get('border-radius', '0')})

        self.root.update_idletasks()
        host_w = max(1, self.body.winfo_width())
        host_h = max(1, self.body.winfo_height())
        # Material sizes a drawer at the screen minus 56dp, capped at 320dp.
        width = max(200, min(host_w - 56, 320))

        # Tk has no per-widget alpha, so the scrim dims to a flat colour
        # instead of showing the screen through it. What it does do is the
        # same job: darken everything and catch the tap that closes the panel.
        scrim = tk.Frame(
            self.body,
            bg=_mix_color(theme.get('background', '#000000'), '#000000', 0.55),
            cursor='arrow',
        )
        scrim.place(x=0, y=0, relwidth=1, relheight=1)
        scrim.bind('<Button-1>', lambda _e: self.close_drawer())

        panel = tk.Canvas(self.body, width=width, height=host_h, bg=surface,
                          highlightthickness=0, bd=0, cursor='hand2')
        panel.place(x=-width, y=0, width=width, height=host_h)

        title_font = _build_tk_font(
            {**style, 'font-size': style.get('font-size', '20px'),
             'font-weight': 'bold'}, default_size=20)
        sub_font = _build_tk_font(
            {**style, 'font-size': '13px', 'font-weight': 'normal'},
            default_size=13)
        item_font = _build_tk_font(
            {**style, 'font-size': style.get('item-size', '15px'),
             'font-weight': 'normal'}, default_size=15)

        hit = []
        y = 24
        if definition.header:
            panel.create_text(24, y + 12, text=str(definition.header),
                              anchor='w', fill=fg, font=title_font)
            y += 34
        if definition.subtitle:
            panel.create_text(24, y + 8, text=str(definition.subtitle),
                              anchor='w', fill=muted, font=sub_font)
            y += 26
        if definition.header or definition.subtitle:
            y += 10
            panel.create_line(24, y, width - 16, y, fill=line)
            y += 14

        active = getattr(self, '_active_screen', None)
        for index, target in enumerate(definition.screens):
            is_active = target is active
            top, bottom = y, y + 48
            if is_active:
                _create_rounded_rect(panel, 12, top + 2, width - 12, bottom - 2,
                                     radius or 24, fill=pill, outline=pill,
                                     width=0)
            tint = accent if is_active else fg
            icon = definition.icons[index] if index < len(definition.icons) else None
            if icon:
                _draw_material_icon(panel, icon, 40, (top + bottom) / 2.0,
                                    tint, size=22)
            label = (definition.labels[index]
                     if index < len(definition.labels) else '')
            panel.create_text(68, (top + bottom) / 2.0, text=str(label),
                              anchor='w', fill=tint, font=item_font)
            hit.append((top, bottom, target))
            y = bottom + 4

        def _clicked(event):
            for top, bottom, target in hit:
                if top <= event.y <= bottom:
                    self.close_drawer()
                    if target is not getattr(self, '_active_screen', None):
                        self.render_screen(target)
                    return

        panel.bind('<Button-1>', _clicked)
        self._drawer_panel = panel
        self._drawer_scrim = scrim
        self._slide_drawer(panel, -width, 0)

    def close_drawer(self):
        """Slide the navigation panel back out."""
        panel = getattr(self, '_drawer_panel', None)
        scrim = getattr(self, '_drawer_scrim', None)
        self._drawer_panel = None
        self._drawer_scrim = None
        if panel is None:
            return

        def _done():
            for widget in (panel, scrim):
                try:
                    if widget is not None:
                        widget.destroy()
                except tk.TclError:
                    pass

        width = max(1, panel.winfo_width())
        self._slide_drawer(panel, 0, -width, done=_done)

    def _slide_drawer(self, panel, start, end, done=None):
        """Move the panel between two x positions on the shared motion curve."""
        duration = _motion.duration('screen', _motion_preset())
        if duration <= 0:
            try:
                panel.place_configure(x=end)
            except tk.TclError:
                pass
            if done:
                done()
            return
        steps = max(2, int(duration / 16))
        state = {'step': 0}

        def _tick():
            state['step'] += 1
            progress = min(1.0, state['step'] / steps)
            try:
                panel.place_configure(
                    x=int(round(start + (end - start) * _motion.ease(progress)))
                )
            except tk.TclError:
                return
            if progress >= 1.0:
                if done:
                    done()
                return
            self.root.after(16, _tick)

        self.root.after(16, _tick)

    def _render_app_bar(self, screen, screen_bg):
        """Render a fixed Material-style toolbar or a collapsible sliver header."""
        bar = getattr(screen, 'app_bar', None)
        if bar is None:
            return

        kind = bar.comp_type
        surface, fg = self._app_bar_palette(screen, screen_bg)
        title = str(bar.kwargs.get('title', ''))
        # The bar has a stylesheet like everything else. It used to be read
        # only for its two colours, so a custom typeface reached the title on
        # the phone and not on the desktop.
        bar_style = _merge_with_body(bar.kwargs.get('comp_id'), kind)
        title_font = _build_tk_font(
            {'font-weight': 'bold', **bar_style, 'font-size':
             bar_style.get('font-size', '16px')},
            default_size=16,
        )
        title_align = normalize_text_align(bar_style.get('text-align'), 'left')
        is_sliver = kind == 'sliver_app_bar'
        collapsed_height = 72
        expanded = (
            max(collapsed_height, int(bar.kwargs.get('expanded_height', 240)))
            if is_sliver else collapsed_height
        )
        pinned = bool(bar.kwargs.get('pinned', True))

        outer = tk.Frame(self.body, bg=surface, height=expanded)
        outer.pack(fill='x', side='top')
        outer.pack_propagate(False)
        self._app_bar_frame = outer

        image_canvas = None
        raw_image = {'value': None}
        if is_sliver:
            image_canvas = tk.Canvas(
                outer, bg=surface, highlightthickness=0, height=expanded,
            )
            image_canvas.pack(fill='both', expand=True)

            def _draw_cover(event=None):
                raw = raw_image['value']
                if raw is None or not image_canvas.winfo_exists():
                    return
                from PIL import Image, ImageOps, ImageTk
                width = max(1, image_canvas.winfo_width())
                height = max(1, image_canvas.winfo_height())
                fitted = ImageOps.fit(raw.convert('RGB'), (width, height), Image.LANCZOS)
                photo = ImageTk.PhotoImage(fitted)
                image_canvas.image = photo
                image_canvas.delete('cover')
                image_canvas.create_image(0, 0, anchor='nw', image=photo, tags='cover')

            def _load_cover():
                src = str(bar.kwargs.get('image') or '')
                if not src:
                    return
                try:
                    from PIL import Image
                    if src.startswith(('http://', 'https://')):
                        import io, ssl, threading, urllib.request

                        def _remote():
                            try:
                                request = urllib.request.Request(
                                    src, headers={'User-Agent': 'ApkPyPreviewer'},
                                )
                                context = ssl._create_unverified_context()
                                with urllib.request.urlopen(request, timeout=10, context=context) as response:
                                    loaded = Image.open(io.BytesIO(response.read())).copy()
                                self.root.after(0, lambda: (raw_image.update(value=loaded), _draw_cover()))
                            except Exception as exc:
                                print(f"[ApkPy app bar] falha ao carregar {src} ({exc})")
                        threading.Thread(target=_remote, daemon=True).start()
                        return
                    path = src
                    if not os.path.isabs(path):
                        script_dir = os.path.dirname(os.path.abspath(getattr(__main__, '__file__', os.getcwd())))
                        path = os.path.join(script_dir, path)
                    raw_image['value'] = Image.open(path).copy()
                    outer.after_idle(_draw_cover)
                except Exception as exc:
                    print(f"[ApkPy app bar] falha ao carregar {src} ({exc})")

            image_canvas.bind('<Configure>', _draw_cover, add='+')
            _load_cover()

        # The complete top surface is 72px: the upper 24px belong to the
        # overlaid clock/system icons and the remaining 48px preserve Android's
        # minimum native toolbar/action touch target without adding another row.
        toolbar_height = 48
        toolbar = tk.Frame(outer, bg=surface, height=toolbar_height)
        toolbar.place(
            x=0, rely=1.0, anchor='sw', relwidth=1.0, height=toolbar_height,
        )
        toolbar.pack_propagate(False)

        def _icon_button(icon, command=None, description=None):
            canvas = tk.Canvas(
                toolbar, width=48, height=toolbar_height, bg=surface,
                highlightthickness=0, cursor='hand2' if command else '',
            )
            canvas.pack(side='left')
            _draw_material_icon(
                canvas, icon, 24, toolbar_height // 2, fg, size=22,
            )
            if description:
                # Tk has no accessibility tree equivalent to Android's content
                # description, but the tooltip text remains discoverable in tests.
                canvas.apkpy_description = description
            if command:
                def _run(_event=None):
                    try:
                        command()
                    except Exception as exc:
                        print(f"[ApkPy app bar] erro na acao: {exc}")
                canvas.bind('<Button-1>', _run)
            return canvas

        leading = bar.kwargs.get('leading')
        if leading:
            if isinstance(leading, ComponentDef):
                leading_icon = leading.kwargs.get('icon')
                leading_command = leading.kwargs.get('command')
                if leading_command is None and leading_icon == 'arrow_back':
                    # The same rule the generator applies: a back arrow with no
                    # command of its own means "leave this screen". Android
                    # writes finish() into the navigation listener; here it is
                    # the history stack. The condition is deliberately the icon
                    # name and nothing else, so both sides answer alike.
                    leading_command = self.go_back
                _icon_button(
                    leading_icon, leading_command,
                    leading.kwargs.get('label'),
                )
            else:
                _icon_button(str(leading))

        title_label = tk.Label(
            toolbar, text=title, bg=surface, fg=fg,
            anchor=_TK_ANCHOR.get(title_align, 'w'), font=title_font,
        )
        if title_align == 'center':
            # Android's app:titleCentered centres in the whole toolbar, not in
            # what the leading icon and the actions leave over. Packing would
            # centre in the gap and drift left as soon as an action appeared.
            title_label.place(relx=0.5, rely=0.5, anchor='center')
        else:
            title_label.pack(side='left', fill='both', expand=True,
                             padx=(8 if leading else 18, 4))

        for item in reversed(list(bar.kwargs.get('actions') or [])):
            if isinstance(item, ComponentDef):
                widget = _icon_button(
                    item.kwargs.get('icon'), item.kwargs.get('command'),
                    item.kwargs.get('label'),
                )
                widget.pack_forget()
                widget.pack(side='right')

        if is_sliver:
            minimum = collapsed_height if pinned else 0
            collapsible = max(1, expanded - minimum)

            def _update(offset):
                height = max(minimum, expanded - min(collapsible, max(0, int(offset))))
                outer.configure(height=height)
                if image_canvas is not None:
                    image_canvas.configure(height=max(1, height))
                toolbar.place_configure(rely=1.0)

            self._app_bar_scroll_update = _update


    def _render_bottom_nav(self, active_screen):
        """Renders (or refreshes) the bottom navigation bar if bottom_nav() was called."""
        bnav = _active_bottom_nav
        # Remove old bar first
        if self._bottom_nav_frame:
            self._bottom_nav_frame.destroy()
            self._bottom_nav_frame = None
        if not bnav:
            return
        # Ecrãs fora do bottom_nav (ex: detalhe) não mostram a barra —
        # paridade com o Android, onde só os ecrãs-tab têm BottomNavigationView.
        if active_screen not in bnav.screens:
            return

        # One rule for the bar and everything on it, shared with the
        # compiler (theme.nav_colors).
        bar_bg, active_color, inactive_color, pill_color = _nav_colors(
            global_styles.get('__theme__', {}))
        # The same height as the phone's bar (theme.NAV_BAR_DP).
        bar = tk.Frame(self.root, bg=bar_bg, height=NAV_BAR_DP)
        bar.pack(fill='x', side='bottom')
        bar.pack_propagate(False)
        self._bottom_nav_frame = bar

        n = len(bnav.screens)
        for i, (screen, label_text, icon_name) in enumerate(
                zip(bnav.screens, bnav.labels, bnav.icons)):
            is_active = (screen is active_screen)
            fg_active   = active_color
            fg_inactive = inactive_color
            fg = fg_active if is_active else fg_inactive

            col = tk.Frame(bar, bg=bar_bg)
            col.pack(side='left', fill='both', expand=True)

            style = getattr(bnav, 'indicator', 'pill')
            # A 2px rule on top was this Previewer's own invention; Android
            # draws a rounded indicator behind the icon. Same widget, two
            # different designs, and nobody had chosen either.
            if style == 'line':
                indicator = tk.Frame(
                    col, bg=fg_active if is_active else bar_bg, height=2)
                indicator.pack(fill='x', side='top')
            else:
                indicator = tk.Frame(col, bg=bar_bg, height=4)
                indicator.pack(fill='x', side='top')

            icon_canvas = tk.Canvas(
                col, width=64, height=32, bg=bar_bg,
                highlightthickness=0, borderwidth=0, cursor="hand2",
            )
            icon_canvas.pack(pady=(2, 0))
            if is_active and style == 'pill':
                _create_rounded_rect(
                    icon_canvas, 0, 0, 63, 31, 16,
                    fill=pill_color,
                    outline='',
                )
            active_name = (getattr(bnav, 'icons_active', None) or bnav.icons)[i]
            _draw_material_icon(
                icon_canvas,
                active_name if is_active else icon_name,
                32, 16, fg, size=22, tags='nav_icon',
                style='filled' if is_active else 'outlined',
            )

            lbl = tk.Label(col, text=label_text, bg=bar_bg, fg=fg,
                           font=_nav_label_font(is_active), cursor="hand2")
            # 4dp between pill and label, as activeIndicatorLabelPadding.
            lbl.pack(pady=(NAV_LABEL_GAP_DP, 0))

            # Click handler — e=None para funcionar tanto via bind como command=
            for w in (lbl, icon_canvas, col, indicator):
                w.bind('<Button-1>', lambda e=None, s=screen: self.render_screen(s))


    def _render_mini_player(self, active_screen):
        """Mini-player fixo: barra no fundo da janela (acima do bottom_nav) que
        mostra a faixa atual lida do `audio`. Esconde-se quando nada toca."""
        old = getattr(self, '_mini_player_frame', None)
        if old:
            try: old.destroy()
            except Exception: pass
            self._mini_player_frame = None
        if not _active_mini_player:
            return
        # No ecrã que o mini-player abre (o Now Playing em grande) a barra não
        # aparece — seria redundante; volta quando saíres desse ecrã.
        if _active_mini_player.get('open') is active_screen:
            return

        from . import audio as _audio  # singleton do leitor
        tokens = global_styles.get('__theme__', {})
        bar_bg, text_fg, muted_fg = (_tk_color(c, '#FFFFFF') for c in _mini_player_colors(
            tokens, component_style(global_styles, 'mini_player',
                                    _active_mini_player.get('id'), include_body=False,
                                    viewport=_style_viewport)))
        cover_bg = tokens.get('background', '#282828')
        bar = tk.Frame(self.root, bg=bar_bg, height=64)
        bar.pack(fill='x', side='bottom')
        bar.pack_propagate(False)
        self._mini_player_frame = bar

        cover = tk.Canvas(bar, width=48, height=48, bg=cover_bg, highlightthickness=0)
        cover.pack(side='left', padx=8, pady=8)
        txt = tk.Frame(bar, bg=bar_bg)
        txt.pack(side='left', fill='both', expand=True, padx=(2, 8))
        tfont = ('Segoe UI', 11, 'bold') if os.name == 'nt' else ('Helvetica', 11, 'bold')
        afont = ('Segoe UI', 9) if os.name == 'nt' else ('Helvetica', 9)
        title_lbl = tk.Label(txt, text="", bg=bar_bg, fg=text_fg, font=tfont, anchor='w')
        title_lbl.pack(fill='x', pady=(13, 0))
        artist_lbl = tk.Label(txt, text="", bg=bar_bg, fg=muted_fg, font=afont, anchor='w')
        artist_lbl.pack(fill='x')
        # A drawn icon: the ⏸ and ▶ characters came out as emoji on some
        # phones and as empty circles in the Previewer.
        pp = tk.Canvas(bar, width=40, height=40, bg=bar_bg, highlightthickness=0,
                       bd=0, cursor='hand2')
        pp.pack(side='right', padx=10)
        pp._apkpy_shown = None

        def _paint_pp(playing):
            glyph = 'pause' if playing else 'play_arrow'
            if pp._apkpy_shown == glyph:
                return
            pp._apkpy_shown = glyph
            pp.delete('all')
            _draw_material_icon(pp, glyph, 20, 20, text_fg, size=26, tags='icon')

        _paint_pp(True)

        def _toggle(e=None):
            if _audio._is_playing():
                _audio.pause()
            else:
                _audio.resume()
        pp.bind('<Button-1>', _toggle)

        open_screen = _active_mini_player.get('open')
        if open_screen is not None:
            for w in (cover, title_lbl, artist_lbl, txt):
                w.bind('<Button-1>', lambda e=None, s=open_screen: self.render_screen(s))

        state = {'art': None}

        def _poll():
            if not bar.winfo_exists():
                return
            t = getattr(_audio, '_cur_title', '')
            if not t:
                if bar.winfo_ismapped():
                    bar.pack_forget()
            else:
                if not bar.winfo_ismapped():
                    bar.pack(fill='x', side='bottom')
                title_lbl.config(text=t)
                artist_lbl.config(text=getattr(_audio, '_cur_artist', ''))
                _paint_pp(_audio._is_playing())
                art = getattr(_audio, '_cur_art', '')
                if art and art != state['art']:
                    state['art'] = art
                    self._load_thumb(cover, art, 48)
            self.root.after(400, _poll)

        if not getattr(_audio, '_cur_title', ''):
            bar.pack_forget()   # começa escondido se nada a tocar
        _poll()


    def _render_comp(self, comp, parent_widget, is_flex, pack_side, bg_color):
        if comp.comp_type == 'button':
            self._render_button(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'inputs':
            self._render_input(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'label':
            self._render_label(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'container':
            self._render_container(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'card':
            self._render_container(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'pager':
            self._render_pager(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'chart':
            self._render_chart(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type in ('chips', 'segmented'):
            from .features.choice import render_choice
            render_choice(self, comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'list_row':
            self._render_list_row(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'image':
            self._render_image(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'video':
            self._render_video(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'camera_view':
            from .features.camera_view import render_camera_view
            render_camera_view(self, comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'map':
            from .maps import render_map_preview
            render_map_preview(
                self, comp, parent_widget, is_flex, pack_side, bg_color
            )
        elif comp.comp_type in ('markdown', 'rich_text'):
            from .features.rich_content import render_rich_content_preview
            render_rich_content_preview(
                self, comp, parent_widget, is_flex, pack_side, bg_color
            )
        elif comp.comp_type == 'tree_view':
            from .features.rich_content import render_tree_preview
            render_tree_preview(
                self, comp, parent_widget, is_flex, pack_side, bg_color
            )
        elif comp.comp_type == 'list':
            self._render_list(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'virtual_collection':
            self._render_virtual_collection(
                comp, parent_widget, is_flex, pack_side, bg_color
            )
        elif comp.comp_type == 'carousel':
            self._render_carousel(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'grid':
            self._render_grid(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'spinner':
            self._render_spinner(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type == 'skeleton':
            self._render_skeleton(comp, parent_widget, is_flex, pack_side, bg_color)
        elif comp.comp_type in ('empty_state', 'error_state'):
            self._render_state(comp, parent_widget, is_flex, pack_side, bg_color)

        if comp._reactive_visible is False:
            comp.hide()
        elif comp._reactive_visible is True:
            comp.show()
        self._bind_component_overlays(comp)

    def _bind_component_overlays(self, comp):
        """Attach tooltip/popup/context behavior without wrapping the widget.

        Keeping the original widget is important for layout parity and mirrors
        Android, where the same View receives click/long-click listeners.
        """
        widget = getattr(comp, 'widget', None)
        if widget is None:
            return

        tip_text = comp.kwargs.get('tooltip')
        if tip_text:
            state = {'after': None, 'tip': None}

            def _hide_tip(_event=None):
                if state['after'] is not None:
                    try:
                        self.root.after_cancel(state['after'])
                    except Exception:
                        pass
                    state['after'] = None
                if state['tip'] is not None:
                    try:
                        state['tip'].destroy()
                    except Exception:
                        pass
                    state['tip'] = None

            def _show_tip():
                _hide_tip()
                try:
                    tip = tk.Label(
                        self.root, text=str(tip_text), bg='#2B2930', fg='#F5EFF7',
                        font=('Segoe UI', 9) if os.name == 'nt' else ('Helvetica', 9),
                        padx=10, pady=6, bd=0,
                    )
                    x = max(8, min(self.root.winfo_width() - tip.winfo_reqwidth() - 8,
                                   widget.winfo_rootx() - self.root.winfo_rootx()))
                    y = max(28, widget.winfo_rooty() - self.root.winfo_rooty() - 34)
                    tip.place(x=x, y=y)
                    tip.lift()
                    state['tip'] = tip
                except Exception:
                    pass

            def _queue_tip(_event=None):
                _hide_tip()
                state['after'] = self.root.after(450, _show_tip)

            widget.bind('<Enter>', _queue_tip, add='+')
            widget.bind('<Leave>', _hide_tip, add='+')
            widget.bind('<ButtonPress>', _hide_tip, add='+')

        popup = comp.kwargs.get('popup_menu')
        if isinstance(popup, OverlayDef):
            widget.bind(
                '<ButtonRelease-1>',
                lambda _event=None, overlay=popup: _show_overlay_preview(overlay, widget),
                add='+',
            )

        context = comp.kwargs.get('context_menu')
        if isinstance(context, OverlayDef):
            widget.bind(
                '<Button-3>',
                lambda _event=None, overlay=context: _show_overlay_preview(overlay, widget),
                add='+',
            )

    def _render_container(self, comp, parent_widget, parent_is_flex, parent_pack_side, parent_bg):
        comp_id = comp.kwargs.get('comp_id')
        semantic_type = 'card' if comp.comp_type == 'card' else 'container'
        style = _merge_with_body(
            comp_id, semantic_type,
            comp.kwargs.get('variant') if semantic_type == 'card' else None,
        )
        if comp.kwargs.get('card_actions'):
            style = {
                **style, 'display': 'flex', 'flex-direction': 'row',
                'gap': style.get('gap', '8px'),
                'background-color': 'transparent', 'border-width': '0px',
                'border-radius': '0px', 'padding': '0px',
            }

        # Tk Frames do not accept CSS transparency ("transparent" or an
        # 8-digit alpha color). Visually, a transparent nested surface is the
        # parent's surface, so resolve it here while keeping the Android/CSS
        # representation genuinely transparent.
        # ``background-color`` is the page's, not every box's. The cascade
        # merges the ``body`` block into every component, which was harmless
        # only while a container carried its own surface to override it: with
        # that default gone, every grouping started painting the screen colour
        # on top of whatever surface it sat on -- a flat dark band across a
        # composer. A container with nothing of its own is transparent, which
        # visually is its parent.
        own_fill = _get_style_bg(component_style(
            global_styles, semantic_type, comp_id, include_body=False,
            variant=(comp.kwargs.get('variant')
                     if semantic_type == 'card' else None),
            viewport=_style_viewport,
        ))
        bg = _tk_color(own_fill, parent_bg)
        flex_dir = _get_flex_orientation(style)
        responsive_config = comp.kwargs.get('responsive') or {}
        if responsive_config:
            width, height = _style_viewport
            if width > height and responsive_config.get('landscape'):
                flex_dir = responsive_config['landscape']
            elif width >= int(responsive_config.get('breakpoint', 600)):
                flex_dir = responsive_config.get('tablet', responsive_config.get('mobile', 'column'))
            else:
                flex_dir = responsive_config.get('mobile', 'column')
        is_flex = bool(responsive_config) or style.get('display', '').strip().lower() in ('flex', 'grid')
        pack_side = tk.LEFT if flex_dir == 'row' else tk.TOP
        child_styles = [
            _preview_child_layout_style(child) for child in comp.children
        ]
        advanced_layout = is_advanced_container(
            style, child_styles, responsive=bool(responsive_config)
        )
        mt, mr, mb, ml = _parse_margin(style)
        radius = _parse_radius(style)
        bc = _get_style_border_color(style)
        bw = _parse_border_width(style)
        shadow_raw = str(style.get('box-shadow', '')).strip().lower()
        has_shadow = bool(shadow_raw and shadow_raw != 'none')
        pad_t, pad_r, pad_b, pad_l = _parse_padding_tk(style)

        # ``flex-grow`` says "take what the siblings leave", and the phone
        # honours it either way: the generated child gets 0dp plus
        # layout_weight="1" whether or not the screen declared display:flex.
        # The Previewer used to drop it the moment the parent was a flex
        # container -- so writing the one declaration that makes a screen a
        # flex column silently disabled the property that fills it, and only
        # on the desktop. Somebody would have "fixed" their stylesheet to work
        # around a bug that does not exist on the device.
        parent_is_column = parent_pack_side in (tk.TOP, tk.BOTTOM)
        grows = (_number(style.get('flex-grow')) > 0
                 and (not parent_is_flex or parent_is_column))
        # In a row the layout engine gives a growing child its slot; the box
        # has to fill it. A rounded pill with flex-grow stayed as wide as its
        # content and left a hole before the send button.
        grows_in_row = (_number(style.get('flex-grow')) > 0
                        and parent_is_flex and not parent_is_column)
        outer = tk.Frame(parent_widget, bg=parent_bg)
        viewport_width = _style_viewport[0]
        requested_width = _resolve_css_size_tk(
            style.get('width'), 'width', _style_viewport, viewport_width
        )
        max_width = _resolve_css_size_tk(
            style.get('max-width'), 'width', _style_viewport, viewport_width
        )
        target_width = requested_width
        if max_width:
            target_width = min(target_width or viewport_width, max_width)
        min_height = _resolve_css_size_tk(
            style.get('min-height'), 'height', _style_viewport, _percent_height_base()
        )
        if not min_height and not comp.children:
            # An empty box of a fixed height -- a spacer, a colour bar, a tile
            # in a grid -- has nothing inside to measure, and was 1px here
            # while the phone's layout_height gave it its size (padding
            # included, as Android counts it).
            fixed_height = _resolve_css_size_tk(
                style.get('height'), 'height', _style_viewport, _percent_height_base()
            )
            if fixed_height:
                min_height = max(1, fixed_height - pad_t - pad_b)
        if target_width and target_width < viewport_width:
            outer.configure(width=target_width)
        if grows:
            # 0dp plus layout_weight on the phone: take what the siblings
            # leave, which is what pins whatever follows to the bottom.
            outer.pack(
                fill='both', expand=True,
                side=(parent_pack_side if parent_is_flex else tk.TOP),
                padx=(ml, mr), pady=(mt, mb),
            )
        elif parent_is_flex and parent_is_column:
            # match_parent is what the generated layout gives a container in a
            # vertical parent, so hugging the content here was a divergence.
            outer.pack(
                side=parent_pack_side, fill='x',
                padx=(ml, mr), pady=(mt, mb),
            )
        elif grows_in_row:
            outer.pack(side=parent_pack_side, fill='both', expand=True,
                       padx=(ml, mr), pady=(mt, mb))
        elif parent_is_flex:
            outer.pack(
                side=parent_pack_side,
                anchor='n' if parent_pack_side == tk.LEFT else 'w',
                padx=(ml, mr), pady=(mt, mb),
            )
        elif target_width and target_width < viewport_width:
            # align-self in a plain column: the phone gives it layout_gravity.
            outer.pack(padx=(ml, mr), pady=(mt, mb),
                       anchor=_ALIGN_SELF_ANCHOR.get(
                           str(style.get('align-self', '')).strip().lower(), 'center'))
        else:
            outer.pack(fill='x', padx=(ml, mr), pady=(mt, mb))

        panel = None
        panel_window = None
        inset = 0
        # The shadow is drawn inside the canvas, below and right of the shape;
        # the content has to leave that room too, or its corner leaves the curve.
        panel_shadow_depth = 5 if has_shadow else 0
        panel_radii = _parse_radii(style)
        if radius > 0:
            # Frames Tk não suportam cantos arredondados. Um Canvas desenha o
            # painel e aloja o frame de conteúdo, mantendo o layout declarativo.
            # The content is a rectangular Tk frame laid over the rounded
            # shape; its corner has to stay inside the curve. A corner at
            # (i, i) clears a radius-r arc from i = 1 + r(1 - 1/sqrt 2).
            # It used to be capped at 8 and the frame poked out of every
            # radius over ~24 -- hidden by the stepped polygon, plain next to
            # an antialiased one. padding already subtracts the inset, so this
            # moves content only where the padding is smaller than it.
            inset = max(2, min(16, int(1.999 + radius * 0.2929)), bw)
            panel = tk.Canvas(outer, bg=parent_bg, highlightthickness=0, bd=0)
            if grows or grows_in_row:
                panel.pack(fill='both', expand=True)
            elif parent_is_flex and parent_is_column:
                panel.pack(fill='x')
            elif parent_is_flex:
                panel.pack()
            elif target_width and target_width < viewport_width:
                # max-width: the shape is that wide, as the phone draws it. It
                # filled the column, so a chat bubble with max-width: 260px was
                # the width of the screen.
                panel.configure(width=target_width)
                panel.pack()
            else:
                panel.pack(fill='x')
            inner_frame = tk.Frame(panel, bg=bg)
            panel_window = panel.create_window(
                (inset, inset), window=inner_frame, anchor='nw', tags='content'
            )

            def _draw_panel(event=None, c=panel, win=panel_window):
                try:
                    w = event.width if event is not None else c.winfo_width()
                    h = c.winfo_height()
                    if w <= 1 or h <= 1:
                        return
                    c.delete('panel_shape')
                    c.delete('panel_shadow')
                    shadow_depth = panel_shadow_depth
                    shadow = (_aa_shadow_photo(c, w, h, panel_radii, shadow_depth)
                              if has_shadow else None)
                    if shadow is not None:
                        c._apkpy_shadow = shadow
                        c.create_image(0, 0, image=shadow, anchor='nw',
                                       tags='panel_shadow')
                    elif has_shadow:
                        # Tk has no native blurred box shadow. Two rounded,
                        # progressively offset layers give Material elevation
                        # without adding widgets or affecting layout geometry.
                        _create_rounded_rect(
                            c, 3, 4, w - 1, h - 1, radius,
                            fill='#030305', outline='#030305', width=1,
                            tags='panel_shadow',
                        )
                        _create_rounded_rect(
                            c, 2, 2, w - 2, h - 2, radius,
                            fill='#07070A', outline='#07070A', width=1,
                            tags='panel_shadow',
                        )
                    _create_rounded_rect(
                        c, 1, 1, w - max(1, shadow_depth),
                        h - max(1, shadow_depth), panel_radii,
                        fill=bg, outline=(bc if bw > 0 and bc else bg),
                        width=max(1, bw), tags='panel_shape',
                    )
                    c.tag_lower('panel_shape')
                    c.tag_lower('panel_shadow')
                    # In a flex *row* the panel hugs its content; in a
                    # column it is full width and the content is what has to
                    # be clamped. Without this a rounded container inside a
                    # ``display: flex`` screen let its children keep their
                    # natural width and the canvas cut off whatever fell past
                    # the edge -- the last control of a composer row.
                    if (not parent_is_flex or parent_is_column or target_width
                            or grows_in_row):
                        c.itemconfigure(win, width=max(1, w - inset * 2 - shadow_depth))
                    if grows:
                        # The content window is placed at a fixed corner, so a
                        # growing panel has to hand it the height as well --
                        # otherwise justify-content has nothing to centre in.
                        c.itemconfigure(win, height=max(1, h - inset * 2 - shadow_depth))
                except Exception:
                    pass

            def _fit_panel(event=None, c=panel, content=inner_frame):
                try:
                    changed = False
                    req_h = max(1, content.winfo_reqheight() + inset * 2
                                + panel_shadow_depth)
                    if int(float(c.cget('height'))) != req_h:
                        c.configure(height=req_h)
                        changed = True
                    if parent_is_flex and not parent_is_column:
                        req_w = max(
                            1,
                            target_width or (content.winfo_reqwidth() + inset * 2
                                             + panel_shadow_depth),
                        )
                        if int(float(c.cget('width'))) != req_w:
                            c.configure(width=req_w)
                            changed = True
                    c.after_idle(_draw_panel)
                    if changed:
                        # The rounded panel is a canvas: its new size reaches
                        # a flex parent only if that parent is told to look.
                        _relayout_above(c)
                except Exception:
                    pass

            panel.bind('<Configure>', _draw_panel)
            inner_frame.bind('<Configure>', _fit_panel, add='+')
            # ComponentDef.show()/hide() finds this callback while walking up
            # the Tk widget tree, including changes that emit no Configure.
            panel._apkpy_relayout = _fit_panel
        else:
            inner_frame = tk.Frame(
                outer, bg=bg,
                width=(target_width if advanced_layout and target_width else 0),
            )
            if bw > 0:
                inner_frame.configure(
                    highlightbackground=bc or bg,
                    highlightcolor=bc or bg,
                    highlightthickness=bw,
                )
            if is_flex and pack_side == tk.LEFT and not advanced_layout:
                inner_frame.pack(
                    anchor='e' if comp.kwargs.get('card_actions') else 'center'
                )
            else:
                inner_frame.pack(fill='both', expand=True)

        comp.widget = inner_frame

        # hide() and show() take the whole box away and bring it back, with
        # its margins and the gap before it, as GONE does on the phone.
        # comp.widget is the frame the children are in. For a rounded box
        # that is a window inside a canvas: pack_forget() did nothing to it,
        # so hide() hid nothing, and the pack() of show() then took it out of
        # the canvas for good -- half as wide, in the middle, over the shape.
        # A square box lost its content and kept its place, and came back
        # hugging its text.
        box_kept = {}

        def _hide_box():
            if outer.winfo_manager() != 'pack':
                return
            box_kept['pack'] = {key: value for key, value in outer.pack_info().items()
                                if key != 'in'}
            outer.pack_forget()

        def _show_box():
            if 'pack' not in box_kept or outer.winfo_manager() == 'pack':
                return
            # pack_info() does not say where among its siblings a widget was:
            # it goes before the first one made after it that is still there.
            siblings = parent_widget.winfo_children()
            follower = next((sibling for sibling in siblings[siblings.index(outer) + 1:]
                             if sibling.winfo_manager() == 'pack'), None)
            if follower is not None:
                outer.pack(before=follower, **box_kept['pack'])
            else:
                outer.pack(**box_kept['pack'])

        comp._component_show = _show_box
        comp._component_hide = _hide_box

        content_parent = inner_frame
        if any((pad_t, pad_r, pad_b, pad_l)):
            content_parent = tk.Frame(inner_frame, bg=bg)
            content_parent.pack(fill='both', expand=True,
                                padx=(max(0, pad_l - inset), max(0, pad_r - inset)),
                                pady=(max(0, pad_t - inset), max(0, pad_b - inset)))

        if advanced_layout and comp.children:
            # A geometria avançada é calculada uma única vez pelo motor
            # partilhado. Cada componente continua a usar o seu renderer normal,
            # alojado numa slot colocada por coordenadas. Assim não duplicamos
            # botões/inputs/listas nem os respetivos eventos.
            layout_host = tk.Frame(content_parent, bg=bg, bd=0,
                                   highlightthickness=0)
            layout_host.pack(fill='x', expand=True)
            # In a row, a child asks for the width of its own content -- the
            # same thing android:layout_width="wrap_content" gives ApkpyLayout.
            # Rendered as if it were stacked, a text button asked for the full
            # width instead, and the row only looked right because flex-shrink
            # squeezed it back; `flex-shrink: 0` then pushed the last controls
            # off the screen. Columns keep their existing semantics.
            row_slots = flex_dir == 'row' and \
                str(style.get('display', '')).strip().lower() != 'grid'
            slots = []
            for child in comp.children:
                slot = tk.Frame(layout_host, bg=bg, bd=0, highlightthickness=0)
                # The phone lays this child out inside an ApkpyLayout: a label
                # there is wrap_content with no indent, in a column as in a
                # row. Rendered as a stacked label it took the 16px indent of
                # a plain column -- a name beside an avatar sat 18px adrift.
                slot._apkpy_in_flex = True
                self._render_comp(
                    child, slot, row_slots,
                    tk.LEFT if row_slots else tk.TOP, bg,
                )
                slots.append(slot)

            effective_style = dict(style)
            if effective_style.get('display', '').lower() != 'grid':
                # ``advanced_layout`` may be enabled by a child property such
                # as flex-grow even when the container itself is a normal
                # vertical ApkPy container.  The shared layout engine follows
                # CSS and otherwise defaults flex layouts to ``row``.  Preserve
                # the Previewer's normal column semantics explicitly, matching
                # the direction encoded for Android, so siblings are not
                # squeezed into one clipped row.
                effective_style['display'] = 'flex'
                effective_style['flex-direction'] = flex_dir

            explicit_height = _resolve_css_size_tk(
                style.get('height'), 'height', _style_viewport, _percent_height_base()
            )
            relayout_state = {'width': -1, 'scheduled': False}
            hug_content = (parent_is_flex and not parent_is_column
                           and not grows and not grows_in_row and not target_width)

            def _apply_advanced_layout(host=layout_host, widgets=slots,
                                       styles_for_children=child_styles,
                                       layout_style=effective_style,
                                       children=list(comp.children)):
                relayout_state['scheduled'] = False
                try:
                    host.update_idletasks()
                    available = host.winfo_width()
                    if available <= 1:
                        parent_available = parent_widget.winfo_width()
                        if parent_available <= 1:
                            parent_available = _style_viewport[0] - pad_l - pad_r
                        available = (
                            min(target_width, parent_available)
                            if target_width else parent_available
                        )
                        available = max(1, available)
                    # A hidden child takes no space, the same way ApkpyLayout
                    # skips a GONE view. Leaving its slot in the flow reserved
                    # a gap the phone never has, and pushed the last control
                    # off the edge of a full row.
                    live = []
                    for index, widget in enumerate(widgets):
                        child = children[index] if index < len(children) else None
                        if child is not None and getattr(
                                child, '_reactive_visible', True) is False:
                            widget.place_forget()
                            continue
                        live.append(index)
                    items = []
                    for index in live:
                        child_style = styles_for_children[index]
                        req_w = max(1, widgets[index].winfo_reqwidth())
                        if _shrinks_to_fit(child_style):
                            req_w = _natural_width(widgets[index], req_w)
                        items.append({
                            'style': child_style,
                            'width': req_w,
                            'height': max(1, widgets[index].winfo_reqheight()),
                        })
                    if hug_content and items:
                        # A child of a flex row is as wide as its content
                        # (wrap_content on the phone). Laid out to the row's
                        # whole width, the first of five story cells took all
                        # of it and the other four vanished.
                        flowing = [item['width'] for item in items
                                   if str(item['style'].get('position', '')).lower() != 'absolute']
                        if layout_style.get('flex-direction') == 'row':
                            natural = sum(flowing) + _number(layout_style.get('gap')) * max(0, len(flowing) - 1)
                        else:
                            natural = max(flowing) if flowing else 1
                        available = max(1, min(available, int(round(natural))))
                    live_boxes, needed_height = compute_layout_boxes(
                        layout_style, items, available,
                        height=explicit_height or min_height,
                        viewport=_style_viewport,
                    )
                    boxes = [None] * len(widgets)
                    for slot_index, box in zip(live, live_boxes):
                        boxes[slot_index] = box
                    # Definir também a largura pedida quebra o ciclo de medição
                    # do Tk: um host que usa apenas `place()` reporta 1px ao pai,
                    # fazendo o contentor ser recortado em janelas largas.
                    host.configure(
                        width=max(1, available), height=max(1, needed_height)
                    )
                    host.pack_propagate(False)
                    flowing = [item['width'] for item in items
                               if str(item['style'].get('position', '')).lower() != 'absolute']
                    if layout_style.get('flex-direction') == 'row':
                        gap_px = _number(layout_style.get('gap'))
                        natural = sum(flowing) + gap_px * max(0, len(flowing) - 1)
                    else:
                        natural = max(flowing) if flowing else 1
                    natural = int(round(natural))
                    # Either change moves whatever holds this container: a
                    # composer measured its pill at 19px -- the pill's own
                    # text before its buttons were placed -- and, told only
                    # about widths, never learnt the pill was 50px tall.
                    measured = (natural, int(round(needed_height)))
                    if getattr(host, '_apkpy_measured', None) != measured:
                        host._apkpy_natural_width = natural
                        host._apkpy_measured = measured
                        _relayout_above(host)
                    for widget, box in zip(widgets, boxes):
                        if box is None:
                            continue
                        x, y, box_w, box_h, _z = box
                        widget.place(
                            x=round(x), y=round(y),
                            width=max(1, round(box_w)), height=max(1, round(box_h)),
                        )
                    for index in sorted(range(len(widgets)), key=lambda i: boxes[i][4] if boxes[i] else 0):
                        widgets[index].lift()
                    relayout_state['width'] = available
                    if any(str(item['style'].get('position', '')).lower() == 'absolute'
                           for item in items):
                        _queue_see_through(host)
                except (tk.TclError, RuntimeError):
                    pass

            def _queue_advanced_layout(event=None):
                width_now = event.width if event is not None else layout_host.winfo_width()
                if (width_now == relayout_state['width'] and
                        not relayout_state['scheduled']):
                    return
                if not relayout_state['scheduled']:
                    relayout_state['scheduled'] = True
                    layout_host.after_idle(_apply_advanced_layout)

            layout_host.bind('<Configure>', _queue_advanced_layout, add='+')
            # show()/hide() walk up looking for this: Tk emits no <Configure>
            # when a slot is added back, so without it a control that was
            # hidden and shown again never returned to the row.
            layout_host._apkpy_relayout = _apply_advanced_layout
            layout_host.after_idle(_apply_advanced_layout)
        else:
            gap_match = re.search(
                r'[\d.]+', str(style.get('gap', '0') if is_flex else '0')
            )
            gap = int(float(gap_match.group(0))) if gap_match else 0
            divider = divider_spec(style)
            # A frame packed with expand and no fill sits in the middle of what
            # is left, which is Tk's way of saying android:gravity="center".
            justify = str(style.get('justify-content', '')).strip().lower()
            if justify in ('center', 'flex-end', 'end') and pack_side != tk.LEFT:
                content_parent = tk.Frame(content_parent, bg=bg)
                content_parent.pack(
                    expand=(justify == 'center'), fill='x',
                    side=(tk.BOTTOM if justify != 'center' else tk.TOP),
                )
            for index, child in enumerate(comp.children):
                if index and gap:
                    spacer = tk.Frame(content_parent, bg=bg)
                    if pack_side == tk.LEFT:
                        spacer.configure(width=gap)
                        spacer.pack(side=tk.LEFT, fill='y')
                    else:
                        spacer.configure(height=gap)
                        spacer.pack(side=tk.TOP, fill='x')
                # Between children and never at the edges, which is what
                # android:showDividers="middle" does on the other side.
                if index and divider:
                    line = tk.Frame(
                        content_parent, bg=_tk_color(divider['color'], bg),
                    )
                    if pack_side == tk.LEFT:
                        line.configure(width=divider['width'])
                        line.pack(side=tk.LEFT, fill='y',
                                  pady=(divider['inset'], 0))
                    else:
                        line.configure(height=divider['width'])
                        line.pack(side=tk.TOP, fill='x',
                                  padx=(divider['inset'], 0))
                    line.pack_propagate(False)
                self._render_comp(child, content_parent, is_flex, pack_side, bg)

        if panel is not None:
            panel.after_idle(lambda: (
                panel.configure(height=max(1, inner_frame.winfo_reqheight() + inset * 2)),
                panel.event_generate('<Configure>'),
            ))
        if min_height:
            min_spacer = tk.Frame(content_parent, bg=bg, width=0, height=0)
            if pack_side == tk.LEFT:
                min_spacer.pack(side=tk.LEFT)

                def _apply_row_min(spacer=min_spacer, value=min_height):
                    spacer.configure(width=0, height=value)
            else:
                min_spacer.pack(side=tk.TOP)

                def _apply_row_min(spacer=min_spacer, content=content_parent,
                                   value=min_height):
                    current = max(0, content.winfo_reqheight() - spacer.winfo_reqheight())
                    spacer.configure(height=max(0, value - current))
            outer.after_idle(_apply_row_min)

    def _render_list_row(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """A settings row: icon, label, subtitle and something on the right.

        Drawn on one Canvas rather than assembled from widgets, for the same
        reason a button is: Tk cannot round the corners of a Frame, and the
        pieces of a row are fixed, so there is nothing for a layout manager to
        decide.
        """
        comp_id = comp.kwargs.get('comp_id')
        style = _merge_with_body(comp_id, 'list_row')
        bg_frame = bg_color if bg_color is not None else self._bg

        icon = comp.kwargs.get('icon')
        trailing_icon = comp.kwargs.get('trailing_icon')
        command = comp.kwargs.get('command')

        fill_color = _tk_color(_get_style_bg(style), bg_frame)
        pressed = _tk_color(_get_style_pressed_color(style), fill_color)
        fg = _tk_color(_get_style_fg(style), '#212121')
        sub_fg = _tk_color(style.get('subtitle-color'), fg)
        trail_fg = _tk_color(style.get('trailing-color'), sub_fg)
        icon_fg = _tk_color(style.get('icon-color') or style.get('tint'), fg)
        radius = _parse_radius(style)
        bc = _get_style_border_color(style)
        bw = _parse_border_width(style)
        mt, mr, mb, ml = _parse_margin(style)
        pad_t, pad_r, pad_b, pad_l = _parse_padding_tk(style)
        pad_l = pad_l or 16
        pad_r = pad_r or 16

        title_size = _parse_font_size(style, default=15)
        title_font = _build_tk_font(style, default_size=15)
        sub_font = _build_tk_font(
            {**style, 'font-size': style.get('subtitle-size', '13px'),
             'font-weight': 'normal'}, default_size=13,
        )
        trail_font = _build_tk_font(
            {**style, 'font-size': style.get('trailing-size', '13px'),
             'font-weight': 'normal'}, default_size=13,
        )
        icon_size = int(_length_px(style.get('icon-size'), 24))
        min_height = _resolve_css_size_tk(
            style.get('min-height'), 'height', _style_viewport,
        ) or 56

        title_space = _tk_linespace(self.root, title_font, 20)
        sub_space = _tk_linespace(self.root, sub_font, 17)
        leading = _tk_leading(self.root, title_font, style, title_size,
                              natural=title_space)
        content_h = title_space + leading * 2
        if comp.kwargs.get('subtitle') is not None:
            content_h += sub_space + 2
        height = max(int(min_height), content_h + pad_t + pad_b)

        fixed_width = _resolve_css_size_tk(
            style.get('width'), 'width', _style_viewport,
        )
        outer = tk.Frame(parent_widget, bg=bg_frame)
        canvas = tk.Canvas(outer, height=height, bg=bg_frame,
                           highlightthickness=0, bd=0,
                           cursor='hand2' if command else 'arrow')
        if is_flex and fixed_width:
            canvas.configure(width=fixed_width)
            outer.pack(side=pack_side, padx=(ml, mr), pady=(mt, mb))
            canvas.pack()
        elif is_flex:
            # No width of its own in a row: the siblings share what there is,
            # which is 0dp plus layout_weight on the phone.
            outer.pack(side=pack_side, fill='x', expand=True,
                       padx=(ml, mr), pady=(mt, mb))
            canvas.pack(fill='x', expand=True)
        else:
            outer.pack(fill='x', padx=(ml, mr), pady=(mt, mb))
            canvas.pack(fill='x', expand=True)
        comp.widget = canvas

        def _text_of(key, default=''):
            value = comp.kwargs.get(key)
            return default if value is None else str(value)

        state = {
            'text': _text_of('text'),
            'subtitle': _text_of('subtitle'),
            'trailing': _text_of('trailing'),
        }

        def _draw(_event=None, fill=None):
            try:
                if not canvas.winfo_exists():
                    return
            except tk.TclError:
                return
            canvas.delete('all')
            w = canvas.winfo_width()
            if w <= 1:
                w = max(80, _style_viewport[0] - ml - mr)
            h = max(height, canvas.winfo_height())
            body = fill if fill is not None else fill_color
            outline = bc if (bw > 0 and bc) else body
            if radius > 0:
                _create_rounded_rect(
                    canvas, 1, 1, w - 1, h - 1, radius, fill=body,
                    outline=outline, width=max(1, bw) if bw > 0 and bc else 0,
                    tags='body',
                )
            else:
                canvas.create_rectangle(
                    0, 0, w, h, fill=body, outline=outline,
                    width=bw if (bw > 0 and bc) else 0, tags='body',
                )

            x = pad_l
            if icon:
                _draw_material_icon(canvas, icon, x + icon_size / 2.0, h / 2.0,
                                    icon_fg, size=icon_size, tags='icon')
                x += icon_size + 16

            # The trailing pieces are measured first: what they take is room
            # the label no longer has, which is what layout_weight="1" on the
            # text block buys on the phone.
            right = w - pad_r
            if trailing_icon:
                _draw_material_icon(canvas, trailing_icon, right - 10, h / 2.0,
                                    trail_fg, size=20, tags='trailing_icon')
                right -= 28
            if state['trailing']:
                canvas.create_text(right, h / 2.0, text=state['trailing'],
                                   anchor='e', fill=trail_fg, font=trail_font,
                                   tags='trailing')
                right -= _text_measure(self.root, trail_font)(
                    state['trailing']) + 12

            limit = max(24, right - x - 8)
            if state['subtitle']:
                title_y = h / 2.0 - (sub_space + 2) / 2.0
                sub_y = title_y + title_space / 2.0 + 1 + sub_space / 2.0
            else:
                title_y, sub_y = h / 2.0, None
            canvas.create_text(
                x, title_y, anchor='w', fill=fg, font=title_font, tags='title',
                text=_clip_to_width(self.root, title_font, state['text'], limit),
            )
            if sub_y is not None:
                canvas.create_text(
                    x, sub_y, anchor='w', fill=sub_fg, font=sub_font,
                    tags='subtitle',
                    text=_clip_to_width(self.root, sub_font,
                                        state['subtitle'], limit),
                )

        canvas.bind('<Configure>', _draw)
        canvas.after_idle(_draw)
        # set_value(...) retitles the row; ComponentDef looks for this hook the
        # same way it looks for the one a switch or a slider leaves behind.
        comp._row_state = state
        comp._row_redraw = _draw

        if command or comp.nav_target is not None:
            press = _motion.normalise_press(style.get('press'))

            def _on_press(_event=None):
                if press != 'none':
                    _draw(fill=pressed)

            def _on_release(_event=None):
                _draw()
                if command:
                    command()
                if comp.nav_target is not None:
                    if comp.nav_data:
                        comp.nav_target._params = {
                            k: str(v) for k, v in comp.nav_data.items()
                        }
                    self.render_screen(
                        comp.nav_target,
                        transition=getattr(comp, 'nav_transition', None),
                    )

            canvas.bind('<ButtonPress-1>', _on_press)
            canvas.bind('<ButtonRelease-1>', _on_release)

        _animate_widget(_app.root, None, style, canvas=canvas,
                        fill_color=fill_color, text_color=fg)


    @property
    def _container(self):
        """Devolve o frame pai correto: flex_frame (modo flex) ou layout (modo normal)."""
        if getattr(self, '_is_flex', False) and self._flex_frame:
            return self._flex_frame
        return getattr(self, '_normal_content_frame', None) or self.layout

    @property
    def _pack_side(self):
        """Lado do pack para widgets em modo flex."""
        return getattr(self, '_flex_side', tk.TOP) or tk.TOP

    @property
    def _bg(self):
        """Cor de fundo activa do ecrã."""
        return getattr(self, '_flex_bg', '#ffffff') or '#ffffff'

    def _render_label(self, comp, parent_widget, is_flex, pack_side, bg_color):
        # A slot of the layout engine is the box ApkpyLayout gives the
        # TextView on the phone: the label fills it, text at the start unless
        # text-align says otherwise. It hugged its text in the middle of the
        # box instead -- a caption at left: 16px; right: 16px over a photo sat
        # centred on the desktop and at the left edge on the phone.
        in_slot = getattr(parent_widget, '_apkpy_in_flex', False)
        is_flex = is_flex or in_slot
        text    = comp.kwargs.get('text', '')
        comp_id = comp.kwargs.get('comp_id')
        variant = comp.kwargs.get('variant')
        # Fundir body + estilos específicos do componente
        style   = _merge_with_body(comp_id, 'label', variant)
        body_fg = _get_style_fg(_get_body_style())
        fg      = _get_style_fg(style) or body_fg or '#212121'
        mt, mr, mb, ml = _parse_margin(style)
        _body = _body_text_size()
        font    = _build_tk_font(style, default_size=_body)
        parent  = parent_widget
        bg      = bg_color
        align   = normalize_text_align(style.get('text-align'))
        leading = _tk_leading(
            self.root, font, style, _parse_font_size(style, default=_body),
        )

        # Se há animação de margin-top, começa do offset do @keyframes
        anim_name = style.get('animation-name')
        frames    = global_keyframes.get(anim_name, {}) if anim_name else {}
        from_mt   = _parse_anim_val(frames.get('from', {}).get('margin-top', mt), mt)
        spacer_h  = int(from_mt) if frames else mt

        if is_flex:
            # The phone's TextView here is wrap_content with no padding, and
            # its margins are the stylesheet's. The Previewer added 8px each
            # side and counted margin-top twice, so a caption written as two
            # labels in a row ("mara.vale" + the text) sat 16px apart and
            # indented, on the desktop only.
            lbl = tk.Label(
                parent, text=text, font=font,
                fg=fg, bg=bg,
                anchor=_TK_ANCHOR.get(align, 'w' if in_slot else 'center'),
                justify=_TK_JUSTIFY.get(align, 'left' if in_slot else 'center'),
                padx=0, pady=leading,
            )
            if in_slot:
                lbl.pack(side=pack_side, padx=(ml, mr), pady=(mt, mb), fill='x')
            else:
                lbl.pack(side=pack_side, padx=(ml, mr), pady=(mt, mb))
            comp.widget = lbl
            if getattr(comp, '_initial_value', None) is not None:
                comp.set_value(comp._initial_value)
            _animate_widget(_app.root, lbl, style, text_color=fg)
        else:
            # Modo normal: spacer animado acima do label. Only an animated
            # margin-top needs a frame of its own; a still one is the label's
            # pady, and a 0px frame was 1px tall in Tk.
            spacer = None
            if frames:
                spacer = tk.Frame(parent, bg=bg, height=spacer_h)
                spacer.pack(fill='x')
                spacer.pack_propagate(False)

            # The phone's rule (compiler, TextView in a column): a label with a
            # margin-left is measured from the edge; one without is indented
            # 16dp on both sides. Here it was 16 *plus* the margin, so
            # "1284 likes" with margin-left: 14px sat at 30px on the desktop
            # and at 14 on the phone.
            indent = 0 if ml > 0 else 16
            lbl = tk.Label(
                parent, text=text, font=font,
                fg=fg, bg=bg, anchor=_TK_ANCHOR.get(align, 'w'),
                justify=_TK_JUSTIFY.get(align, 'left'),
                padx=indent, pady=leading,
                wraplength=max(80, (self._content_width or 411) - 44
                               - 2 * indent - ml - mr),
            )
            breathing = 0 if getattr(parent, '_apkpy_stack_gap', 0) else 2
            lbl.pack(pady=(breathing + (0 if frames else spacer_h), breathing + mb),
                     fill='x', padx=(ml, mr))

            # TextView no Android quebra linhas automaticamente. Atualiza o
            # wraplength quando o pai recebe a largura real do layout/scroll.
            def _sync_label_wrap(event, widget=lbl):
                try:
                    widget.configure(wraplength=max(
                        80, event.width - 2 * indent - ml - mr))
                except Exception:
                    pass
            parent.bind('<Configure>', _sync_label_wrap, add='+')

            comp.widget = lbl
            if getattr(comp, '_initial_value', None) is not None:
                comp.set_value(comp._initial_value)

            _animate_widget(
                _app.root, lbl, style,
                spacer=spacer if frames else None,
                text_color=fg,
            )

    def _draw_material_button(self, text, bg, fg, radius, command, nav_target, comp=None,
                               border_color=None, border_width=0, pressed_color=None,
                               margin=(0, 0, 0, 0), font=None, parent=None, pack_side=None, bg_color=None,
                               nav_data=None, compact=False, icon=None, padding=None,
                               min_height=0, press=None, text_transform=None,
                               text_align=None, letter_spacing=None,
                               line_height=None, icon_color=None,
                               css_width=None, css_height=None, grow=False):
        """Botão Material Design: cinza claro, texto uppercase, flat.

        ``css_width``/``css_height`` are the stylesheet's size in Preview
        pixels. They were never passed here, so a 76x76 ring came out as a
        pill the width of its text -- while the phone drew the circle."""
        parent     = parent if parent is not None else self.layout
        bg_frame   = bg_color if bg_color is not None else self._bg

        fill_color = _tk_color(bg, bg_frame if compact or bg else "#e0e0e0")
        if _partial_alpha(bg) and _aa_enabled():
            # Glass: the antialiased shape composes it over what is behind.
            fill_color = str(bg).strip()
        elif bg and _is_transparent(bg) and _aa_enabled():
            # Clear: no body at all. Filled with the colour behind it, a
            # close button or a shutter ring over a picture was a dark disc
            # the phone never draws.
            fill_color = '#00000000'
        p_color    = _tk_color(pressed_color, "#bdbdbd")
        text_color = fg if fg else "#212121"
        outline_c  = border_color if border_color else ""
        outline_w  = border_width if border_width > 0 else (1 if outline_c else 0)
        display    = apply_text_transform(text, text_transform)
        mt, mr, mb, ml = margin
        btn_font   = font if font else ("Segoe UI" if os.name == 'nt' else "Helvetica", 11, "bold")
        is_flex    = pack_side is not None

        pad_t, pad_r, pad_b, pad_l = padding or (0, 0, 0, 0)
        try:
            import tkinter.font as _tkfont
            _font_measure = _tkfont.Font(root=self.root, font=btn_font)
            _line_height = _font_measure.metrics('linespace')
        except Exception:
            _font_measure = None
            _line_height = 18
        try:
            _font_px = abs(int(btn_font[1]))
        except (TypeError, ValueError, IndexError):
            _font_px = 11
        # Material tracks button labels at roughly 0.089em and ApkPy has always
        # measured them that way. CSS letter-spacing *replaces* that number
        # instead of adding to it, so `letter-spacing: 0` gives the tight chip
        # Android gives -- and leaving it unset changes nothing.
        _raw_spacing = str(letter_spacing or '').strip().lower()
        if _raw_spacing and _raw_spacing != 'normal':
            _tracking = letter_spacing_px(_raw_spacing, _font_px)
        else:
            _tracking = max(1.0, _line_height * 0.075)
        _line_box = _line_height + line_spacing_extra(
            line_height, _font_px, natural=_line_height,
        )
        _measure_text = (
            _font_measure.measure if _font_measure is not None
            else lambda value: len(str(value)) * 8
        )
        _bh_px = _material_button_height(
            _line_box, padding=padding, compact=compact, flex=is_flex,
            min_height=min_height,
        )
        # The 2px above and below stand in for MaterialButton's inset; a size
        # the stylesheet fixed is the whole box, and the gap cut a 76px ring.
        _v_gap = 2
        if css_height:
            _bh_px = css_height
            _v_gap = 0

        def _width_of(caption):
            """How wide a button the width of its text is, for this caption."""
            text_w = _material_button_text_width(
                caption, _measure_text, _tracking,
            )
            icon_w = 28 if icon and caption else (20 if icon else 0)
            horizontal_padding = pad_l + pad_r if (pad_l or pad_r) else 36
            # Rounded up, with a pixel to spare: _content_layout wraps at
            # the canvas width minus the same padding, and a label 0.4px
            # over it broke "Music" into "Musi" / "c".
            return max(48, int(-(-(text_w + icon_w + horizontal_padding) // 1)) + 1)

        if is_flex or compact:
            # Modo flex: botão dimensionado pelo TEXTO (como o wrap_content do
            # Android) — antes era fixo 120px e uma row de 5 botões transbordava.
            try:
                _bw_px = 48 if compact else _width_of(display)
            except Exception:
                _bw_px = 48 if compact else 120
            if css_width:
                _bw_px = css_width
            outer = tk.Frame(parent, bg=bg_frame)
            # flex-grow in a row: the phone's ApkpyLayout stretches the button
            # into what its siblings leave (grow=1 on its tag). Here it stayed
            # the width of its text -- two half-width buttons were two stubs.
            grow = grow and is_flex and pack_side in (tk.LEFT, tk.RIGHT)
            if is_flex:
                outer.pack(side=pack_side, padx=(ml, mr), pady=(mt, mb),
                           **({'fill': 'x', 'expand': True} if grow else {}))
            else:
                outer.pack(anchor='w', padx=(ml, mr), pady=(_v_gap + mt, _v_gap + mb))
            canvas = tk.Canvas(outer, width=_bw_px, height=_bh_px, bg=bg_frame,
                               highlightthickness=0, bd=0, cursor="hand2")
            if grow:
                canvas.pack(fill='x', expand=True)
            else:
                canvas.pack()
        elif css_width:
            # A fixed width in a column: centred, as the phone's screen
            # (gravity center_horizontal) places it.
            _bw_px = css_width
            outer = tk.Frame(parent, bg=bg_frame)
            outer.pack(padx=(ml, mr), pady=(_v_gap + mt, _v_gap + mb))
            canvas = tk.Canvas(outer, width=_bw_px, height=_bh_px, bg=bg_frame,
                               highlightthickness=0, bd=0, cursor="hand2")
            canvas.pack()
        else:
            outer = tk.Frame(parent, bg=bg_frame)
            outer.pack(padx=(ml, mr), pady=(_v_gap + mt, _v_gap + mb), fill="x")
            canvas = tk.Canvas(outer, height=_bh_px, bg=bg_frame,
                               highlightthickness=0, bd=0, cursor="hand2")
            canvas.pack(fill="x", expand=True)

        def _disp():
            # texto dinâmico (audio.controls): se o comp tiver um hook, usa-o
            if comp is not None and getattr(comp, '_dynamic_text', None) is not None:
                try:
                    return apply_text_transform(
                        comp._dynamic_text(), text_transform
                    )
                except Exception:
                    pass
            return display

        def _content_layout(w):
            label = "" if compact and icon else _disp()
            icon_w = 26 if icon and label else 0
            horizontal_padding = pad_l + pad_r if (pad_l or pad_r) else 36
            text_limit = max(1, w - horizontal_padding - icon_w)
            lines = (
                _wrap_material_button_text(
                    label, text_limit, _measure_text, _tracking,
                )
                if label else ['']
            )
            desired_height = css_height or _material_button_height(
                _line_box * max(1, len(lines)), padding=padding,
                compact=compact, flex=is_flex, min_height=min_height,
            )
            return label, lines, desired_height

        _align = normalize_text_align(text_align)
        _justify = _TK_JUSTIFY.get(_align, 'center')

        def _shown_icon():
            # audio.controls swaps play_arrow/pause and lights shuffle/repeat.
            return (getattr(comp, '_dynamic_icon', None) if comp is not None else None) or icon

        def _shown_colour():
            lit = getattr(comp, '_dynamic_icon_color', None) if comp is not None else None
            return lit or icon_color or text_color
        _edge_l = pad_l or 16
        _edge_r = pad_r or 16

        def _draw_content(w, h, lines=None):
            label = "" if compact and icon else _disp()
            if lines is None:
                _label, lines, _desired = _content_layout(w)
            wrapped_label = '\n'.join(lines)
            if not icon:
                if _align == 'left':
                    canvas.create_text(
                        _edge_l, h // 2, text=wrapped_label, anchor='w',
                        fill=text_color, font=btn_font, justify=_justify,
                        tags='label',
                    )
                elif _align == 'right':
                    canvas.create_text(
                        w - _edge_r, h // 2, text=wrapped_label, anchor='e',
                        fill=text_color, font=btn_font, justify=_justify,
                        tags='label',
                    )
                else:
                    canvas.create_text(
                        w // 2, h // 2, text=wrapped_label,
                        fill=text_color, font=btn_font, justify='center',
                        tags='label',
                    )
                return
            if not label:
                if _align == 'left':
                    icon_x = _edge_l + 10
                elif _align == 'right':
                    icon_x = w - _edge_r - 10
                else:
                    icon_x = w / 2
                _draw_material_icon(
                    canvas, _shown_icon(), icon_x, h / 2, _shown_colour(),
                    size=20, tags='icon',
                )
                return
            text_w = max(
                _material_button_text_width(line, _measure_text, _tracking)
                for line in lines
            )
            if _align in ('left', 'right'):
                # Icon pinned to the leading edge with the label beside it --
                # the shape app:iconGravity="start" gives on Android, and the
                # reason an aligned row reads as a list instead of a pill.
                _draw_material_icon(
                    canvas, _shown_icon(), _edge_l + 9, h / 2, _shown_colour(),
                    size=20, tags='icon',
                )
                if _align == 'left':
                    canvas.create_text(
                        _edge_l + 26, h // 2, text=wrapped_label, anchor='w',
                        fill=text_color, font=btn_font, justify=_justify,
                        tags='label',
                    )
                else:
                    canvas.create_text(
                        w - _edge_r, h // 2, text=wrapped_label, anchor='e',
                        fill=text_color, font=btn_font, justify=_justify,
                        tags='label',
                    )
                return
            total_w = 18 + 8 + text_w
            left = (w - total_w) / 2
            # icon-color counts here too, as Android bakes it into the icon.
            _draw_material_icon(
                canvas, _shown_icon(), left + 9, h / 2, _shown_colour(),
                size=20, tags='icon',
            )
            canvas.create_text(
                left + 26 + text_w / 2, h // 2, text=wrapped_label,
                fill=text_color, font=btn_font, justify='center', tags='label',
            )

        def _redraw(event=None, _fill=None):
            # O canvas pode já ter sido destruído (ex.: um poll de audio.controls/
            # like dispara depois de mudar de ecrã e o botão antigo já não existe).
            try:
                if not canvas.winfo_exists():
                    return
            except Exception:
                return
            canvas.delete("all")
            w = canvas.winfo_width()
            if w <= 1:
                w = event.width if event is not None and event.width > 1 else (
                    _bw_px if is_flex or compact or css_width else 320
                )
            _label, lines, desired_height = _content_layout(w)
            current_requested = int(float(canvas.cget('height')))
            if current_requested != desired_height:
                canvas.configure(height=desired_height)
            h = max(desired_height, canvas.winfo_height())
            cur_fill = _fill if _fill is not None else fill_color
            # A clear or glass body goes through the antialiased path even
            # square: Tk's rectangle has no alpha, and "#00000000" is not a
            # colour Tcl accepts -- a square transparent icon button took the
            # Previewer down.
            if radius > 0 or (_aa_enabled() and (
                    _is_transparent(cur_fill) or _partial_alpha(cur_fill))):
                _create_rounded_rect(canvas, 1, 1, w-1, h-1, radius, fill=cur_fill,
                                     outline=outline_c, width=outline_w, tags='body')
            else:
                canvas.create_rectangle(1, 1, w-1, h-1, fill=cur_fill,
                                        outline=outline_c, width=outline_w, tags='body')
            _draw_content(w, h, lines)
            canvas._current_fill = cur_fill

        _press_mode = _motion.normalise_press(press)
        _press_token = [0]

        def _tint_to(target, then=None):
            """Ease the button's fill towards a colour.

            Android's MaterialButton ripples; this used to swap the colour in
            one frame, so the same tap felt different on the two runtimes. Only
            the body item is reconfigured -- redrawing the whole canvas per
            frame would cost a text layout six times per press.
            """
            duration_ms = _motion.duration('press', _motion_preset())
            start = getattr(canvas, '_current_fill', None) or fill_color
            _press_token[0] += 1
            token = _press_token[0]

            def settle():
                try:
                    canvas.itemconfig('body', fill=target)
                except Exception:
                    pass
                canvas._current_fill = target
                if then:
                    then()

            if _press_mode == 'none' or duration_ms <= 0 or start == target:
                settle()
                return
            begin, end = _hex_to_rgb(str(start)), _hex_to_rgb(str(target))
            total = max(1, int(duration_ms / 16))

            def step(index):
                if _press_token[0] != token:
                    return
                if index >= total:
                    settle()
                    return
                amount = _motion.ease(index / float(total))
                try:
                    canvas.itemconfig('body', fill=_rgb_to_hex(
                        _lerp(begin[0], end[0], amount),
                        _lerp(begin[1], end[1], amount),
                        _lerp(begin[2], end[2], amount),
                    ))
                except Exception:
                    return
                canvas.after(16, lambda: step(index + 1))

            step(0)

        def _on_press(event):
            if _press_mode == 'none':
                return
            _tint_to(p_color)
            if _press_mode == 'scale':
                try:
                    w, h = canvas.winfo_width(), canvas.winfo_height()
                    canvas.scale('all', w / 2.0, h / 2.0, 0.97, 0.97)
                except Exception:
                    pass

        def _on_release(event):
            # Cancela a animacao do toque antes de redesenhar. Um clique mais
            # curto que ela (90 ms no preset standard; um toque no touchpad
            # chega a ~10 ms) deixava os passos que faltavam correr depois do
            # _redraw -- e o botao ficava na cor de premido ate ao proximo.
            _press_token[0] += 1
            _redraw()
            # comando dinâmico (audio.controls play/pause toggle) tem prioridade
            cmd = getattr(comp, '_dynamic_command', None) if comp is not None else None
            cmd = cmd or command
            if cmd: cmd()
            if nav_target:
                if nav_data:
                    nav_target._params = {k: str(v) for k, v in nav_data.items()}
                self.render_screen(
                    nav_target,
                    transition=getattr(comp, 'nav_transition', None)
                    if comp is not None else None,
                )

        def _retitle(caption):
            """``button.set_value()``: the new caption, and the width that
            goes with it where the button is as wide as its text -- what
            setText() and wrap_content do between them on the phone."""
            nonlocal display, _bw_px
            display = apply_text_transform(caption, text_transform)
            try:
                if not canvas.winfo_exists():
                    return
            except Exception:
                return
            if is_flex and not compact and not css_width and not grow:
                _bw_px = _width_of(display)
                canvas.configure(width=_bw_px)
            _redraw()
            _queue_preview_relayout(canvas)

        canvas.bind("<Configure>", lambda e: _redraw())
        canvas.bind("<ButtonPress-1>", _on_press)
        canvas.bind("<ButtonRelease-1>", _on_release)
        if comp is not None:
            comp.widget = canvas
            comp._refresh_btn = _redraw   # audio.controls usa-o p/ atualizar o rótulo
            comp._retitle_btn = _retitle
        return canvas

    def _render_button(self, comp, parent_widget, is_flex, pack_side, bg_color):
        variant    = comp.kwargs.get('variant')
        icon       = comp.kwargs.get('icon')
        text       = _material_button_text(comp.kwargs.get('text', ''), icon, variant)
        comp_id    = comp.kwargs.get('comp_id')
        # Fundir body + estilos específicos do componente
        style      = _merge_with_body(comp_id, 'button', variant)
        body_style = _get_body_style()
        bg         = _get_style_bg(style)
        fg         = _get_style_fg(style) or _get_style_fg(body_style)
        # ``icon-color`` and ``tint`` were the two names a person reaches for
        # and the only two that did nothing here: a button's icon took the
        # label colour and nothing else. list_row has read them from the
        # beginning, which made the silence look like a rule.
        icon_fg    = style.get('icon-color') or style.get('tint') or None
        pressed_bg = _get_style_pressed_color(style)
        radius     = _parse_radius(style)
        bc         = _get_style_border_color(style)
        bw         = _parse_border_width(style)
        margins    = _parse_margin(style)
        padding    = _parse_padding_tk(style)
        raw_min_height = str(style.get('min-height', '')).strip()
        min_height_match = re.search(r'\d+(?:\.\d+)?', raw_min_height)
        min_height = int(float(min_height_match.group(0))) if min_height_match else 0
        font       = _build_tk_font(style, default_size=11)
        css_width, css_height = _button_css_size(style)
        user_cmd   = comp.kwargs.get('command')
        nav_target = comp.nav_target
        nav_data   = comp.nav_data
        parent     = parent_widget

        if is_flex:
            # Modo flex: sem spacer, pack lateral
            canvas = self._draw_material_button(
                text, bg, fg, radius, user_cmd, nav_target,
                comp, bc, bw, pressed_bg,
                margin=(margins[0], margins[1], margins[2], margins[3]),
                font=font, parent=parent, pack_side=pack_side, bg_color=bg_color,
                nav_data=nav_data, compact=(variant == 'icon' or _is_icon_button(comp)), icon=icon,
                icon_color=icon_fg,
                press=style.get('press'),
                text_transform=style.get('text-transform'),
                text_align=style.get('text-align'),
                letter_spacing=style.get('letter-spacing'),
                line_height=style.get('line-height'),
                padding=padding, min_height=min_height,
                css_width=css_width, css_height=css_height,
                grow=_number(style.get('flex-grow')) > 0,
            )
            fill_color = bg if bg else '#e0e0e0'
            _animate_widget(_app.root, None, style, canvas=canvas,
                            fill_color=fill_color, text_color=fg)
        else:
            # Modo normal: spacer animado acima do botão
            anim_name = style.get('animation-name')
            frames    = global_keyframes.get(anim_name, {}) if anim_name else {}
            mt = margins[0]
            from_mt   = _parse_anim_val(frames.get('from', {}).get('margin-top', mt), mt)
            spacer_h  = int(from_mt) if frames else mt
            spacer = tk.Frame(parent, bg=bg_color, height=spacer_h)
            spacer.pack(fill='x')
            spacer.pack_propagate(False)

            canvas = self._draw_material_button(
                text, bg, fg, radius, user_cmd, nav_target,
                comp, bc, bw, pressed_bg,
                margin=(0, margins[1], margins[2], margins[3]),
                font=font, parent=parent, bg_color=bg_color,
                nav_data=nav_data, compact=(variant == 'icon'), icon=icon,
                icon_color=icon_fg,
                press=style.get('press'),
                text_transform=style.get('text-transform'),
                text_align=style.get('text-align'),
                letter_spacing=style.get('letter-spacing'),
                line_height=style.get('line-height'),
                padding=padding, min_height=min_height,
                css_width=css_width, css_height=css_height,
            )

            fill_color = bg if bg else '#e0e0e0'
            _animate_widget(
                _app.root, None, style,
                spacer=spacer if frames else None,
                canvas=canvas,
                fill_color=fill_color,
                text_color=fg,
            )

    def _render_input(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Resolve estilos no momento do render e delega ao add_input."""
        comp_id = comp.kwargs.get('comp_id')
        # Fundir body + estilos específicos do componente
        style   = _merge_with_body(comp_id, 'inputs')
        margin  = _parse_margin(style)

        # Se há animação de margin-top, criar spacer animado acima do input
        anim_name = style.get('animation-name')
        frames    = global_keyframes.get(anim_name, {}) if anim_name else {}
        mt        = margin[0]
        from_mt   = _parse_anim_val(frames.get('from', {}).get('margin-top', mt), mt)
        spacer_h  = int(from_mt) if frames else mt

        if not is_flex:
            spacer = tk.Frame(parent_widget, bg=bg_color, height=spacer_h)
            spacer.pack(fill='x')
            spacer.pack_propagate(False)
        else:
            spacer = None

        self.add_input(
            placeholder=comp.kwargs.get('placeholder', ''),
            placeholder_color=_get_style_placeholder_color(style),
            input_type=comp.kwargs.get('input_type', 'text'),
            bg=_get_style_bg(style),
            fg=_get_style_fg(style),
            radius=_parse_radius(style),
            border_color=_get_style_border_color(style),
            border_width=_parse_border_width(style),
            focus_border_color=_get_style_focus_border_color(style),
            margin=(
                margin[0] if is_flex else 0,
                margin[1], margin[2], margin[3],
            ),
            padding=_parse_padding_tk(style),
            font=_build_tk_font(style, default_size=13),
            accent_color=input_accent_color(global_styles, comp_id),
            parent=parent_widget,
            bg_color=bg_color,
            comp=comp,
        )
        if getattr(comp, '_initial_value', None) is not None:
            comp.set_value(comp._initial_value)
        _watch_choice_change(comp)

        # Animação de margem (o widget de input em si não tem fg, usa‑se um label “fantasma”)
        _animate_widget(
            _app.root, None, style,
            spacer=spacer if frames else None,
        )

    def _render_image_legacy(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Renderiza um componente de imagem no preview Tkinter."""
        src     = comp.kwargs.get('src', '')
        comp_id = comp.kwargs.get('comp_id')
        style   = _merge_with_body(comp_id, 'image')

        w_val, h_val = _parse_image_size(style)
        radius   = _parse_radius(style)
        opacity  = _parse_opacity(style)
        bc       = _get_style_border_color(style)
        bw       = _parse_border_width(style)
        mt, mr, mb, ml = _parse_margin(style)
        filters  = _parse_filter(style)
        obj_fit  = _parse_object_fit(style)

        # Dimensões finais em píxeis (1 CSS px = 1 dp = 1 Tkinter pixel)
        fluid_width = w_val == 'match_parent'
        if isinstance(w_val, int):
            w_px = w_val
        else:
            w_px = 200  # initial request; fluid images expand on Configure
        if isinstance(h_val, int):
            h_px = h_val
        else:
            h_px = 150  # fallback

        # Frame exterior (aplica margens)
        outer = tk.Frame(parent_widget, bg=bg_color)
        if is_flex:
            pack_options = {
                'side': pack_side, 'padx': (ml, mr), 'pady': (mt, mb),
            }
            if fluid_width and pack_side == tk.TOP:
                pack_options.update(fill='x')
            outer.pack(**pack_options)
        else:
            outer.pack(
                padx=(ml, mr), pady=(mt, mb),
                fill='x' if fluid_width else None,
            )

        # Canvas que contém a imagem
        hl_color = bc if bc else bg_color
        canvas = tk.Canvas(outer, width=w_px, height=h_px, bg=bg_color,
                           highlightthickness=bw if bw > 0 else 0,
                           highlightbackground=hl_color)
        canvas.pack(fill='x' if fluid_width else None)
        image_state = {
            'raw': None, 'last_width': None, 'resize_job': None,
            'placeholder': True,
        }

        def _target_size():
            width = canvas.winfo_width() if fluid_width else w_px
            return max(1, int(width)), h_px

        def _draw_placeholder(reason=''):
            # A carga remota resolve numa thread → pode chegar depois de mudares de
            # ecrã e o canvas já não existir. Não desenhes num widget destruído.
            try:
                if not canvas.winfo_exists():
                    return
            except Exception:
                return
            target_w, target_h = _target_size()
            image_state['placeholder'] = True
            canvas.delete('all')
            canvas.create_rectangle(
                0, 0, target_w, target_h,
                fill='#e0e0e0', outline='#bdbdbd',
            )
            canvas.create_text(
                target_w // 2, target_h // 2 - 12,
                text='\U0001f5bc\ufe0f',
                font=('Arial', max(14, min(target_w, target_h) // 6)),
            )
            short = os.path.basename(src) if src else 'image'
            canvas.create_text(target_w // 2, target_h // 2 + 14,
                               text=short, font=('Arial', 9), fill='#757575')

        def _process_and_draw(raw_img, remember=True):
            """Aplica object-fit/filtros/opacidade/raio e desenha no canvas."""
            try:
                if not canvas.winfo_exists():
                    return
            except Exception:
                return
            from PIL import Image, ImageOps, ImageTk, ImageFilter, ImageDraw
            if remember:
                image_state['raw'] = raw_img.copy()
            image_state['placeholder'] = False
            target_w, target_h = _target_size()
            canvas.delete('all')
            img = raw_img.convert('RGBA')

            # ── object-fit ─────────────────────────────────────────────────────
            if obj_fit == 'cover':
                img = ImageOps.fit(img, (target_w, target_h), Image.LANCZOS)
            elif obj_fit == 'contain':
                img.thumbnail((target_w, target_h), Image.LANCZOS)
                bg_img = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
                off = ((target_w - img.width) // 2, (target_h - img.height) // 2)
                bg_img.paste(img, off)
                img = bg_img
            elif obj_fit == 'none':
                bg_img = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
                off = ((target_w - img.width) // 2, (target_h - img.height) // 2)
                bg_img.paste(img, off)
                img = bg_img
            else:  # 'fill' e fallback
                img = img.resize((target_w, target_h), Image.LANCZOS)

            # ── filter: grayscale ───────────────────────────────────────────────
            if filters.get('grayscale', 0) > 0:
                gray = ImageOps.grayscale(img).convert('RGBA')
                if filters['grayscale'] >= 1.0:
                    img = gray
                else:
                    img = Image.blend(img, gray, filters['grayscale'])

            # ── filter: blur ────────────────────────────────────────────────────
            if filters.get('blur', 0) > 0:
                img = img.filter(ImageFilter.GaussianBlur(radius=filters['blur']))

            # ── opacity ─────────────────────────────────────────────────────────
            if opacity < 1.0:
                r_ch, g_ch, b_ch, a_ch = img.split()
                a_ch = a_ch.point(lambda x: int(x * opacity))
                img = Image.merge('RGBA', (r_ch, g_ch, b_ch, a_ch))

            # ── border-radius (máscara) ──────────────────────────────────────────
            if radius > 0:
                mask = _aa_mask(target_w, target_h,
                                min(radius, target_w // 2, target_h // 2))
                img.putalpha(mask)

            photo = ImageTk.PhotoImage(img)
            canvas.image = photo  # evitar garbage collection
            canvas.delete('all')  # remove o placeholder, se existir
            canvas.create_image(0, 0, anchor='nw', image=photo)

        def _on_canvas_resize(event):
            if not fluid_width or event.width <= 1:
                return
            if event.width == image_state['last_width']:
                return
            image_state['last_width'] = event.width
            if image_state['resize_job'] is not None:
                try:
                    canvas.after_cancel(image_state['resize_job'])
                except Exception:
                    pass

            def _redraw_at_new_width():
                image_state['resize_job'] = None
                if image_state['raw'] is not None:
                    _process_and_draw(image_state['raw'], remember=False)
                elif image_state['placeholder']:
                    _draw_placeholder()

            image_state['resize_job'] = canvas.after_idle(_redraw_at_new_width)

        if fluid_width:
            canvas.bind('<Configure>', _on_canvas_resize, add='+')

        def _load_src(s):
            """Carrega `s` (URL ou ficheiro local) no canvas. Reutilizável → permite
            trocar a imagem em runtime via comp.set_src() (ex.: capa do álbum)."""
            is_url = isinstance(s, str) and (s.startswith('http://') or s.startswith('https://'))
            if is_url:
                # Imagem remota: placeholder já, descarrega em background e desenha
                # quando chegar — sem bloquear a UI (igual ao `https`).
                _draw_placeholder('a carregar...')

                def _fetch_remote(_s=s):
                    try:
                        import urllib.request, ssl, io
                        from PIL import Image
                        req = urllib.request.Request(_s, headers={'User-Agent': 'ApkPyPreviewer'})
                        ctx = ssl._create_unverified_context()
                        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                            data = resp.read()
                        img = Image.open(io.BytesIO(data))
                        if live_preview() is not None:
                            live_preview().root.after(0, lambda im=img: _process_and_draw(im))
                        else:
                            _process_and_draw(img)
                    except Exception as e:
                        print(f"[ApkPy image] falha ao carregar {_s} ({e})")
                        if live_preview() is not None:
                            live_preview().root.after(0, lambda: _draw_placeholder('erro ao carregar'))

                import threading
                threading.Thread(target=_fetch_remote, daemon=True).start()
            else:
                try:
                    from PIL import Image
                    # Caminho da imagem (relativo ao script principal)
                    img_path = s
                    if not os.path.isabs(img_path):
                        try:
                            script_dir = os.path.dirname(os.path.abspath(__main__.__file__))
                        except AttributeError:
                            script_dir = os.getcwd()
                        img_path = os.path.join(script_dir, s)
                    _process_and_draw(Image.open(img_path))
                except ImportError:
                    _draw_placeholder('Pillow não instalado')
                except FileNotFoundError:
                    _draw_placeholder('Ficheiro não encontrado')
                except Exception:
                    _draw_placeholder('Erro ao carregar')

        _load_src(src)
        comp.widget = canvas
        comp._reload_image = _load_src

    def _render_image(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Render advanced images with cache, fallbacks and Android-like effects."""
        src = comp.kwargs.get('src', '')
        comp_id = comp.kwargs.get('comp_id')
        style = _merge_with_body(comp_id, 'image')
        is_avatar = bool(comp.kwargs.get('avatar'))
        avatar_size = int(comp.kwargs.get('avatar_size') or 48)
        ratio = comp.kwargs.get('aspect_ratio')
        if ratio is None:
            try:
                ratio = _normalize_image_ratio(style.get('aspect-ratio'))
            except ValueError:
                ratio = None
        placeholder = comp.kwargs.get('placeholder')
        fallback = comp.kwargs.get('fallback')
        use_cache = bool(comp.kwargs.get('cache', True))
        fade_in = bool(comp.kwargs.get('fade_in', False))
        tint = comp.kwargs.get('tint')

        w_val, h_val = _parse_image_size(style)
        radius = _parse_radius(style)
        opacity = _parse_opacity(style)
        bc = _get_style_border_color(style)
        bw = _parse_border_width(style)
        mt, mr, mb, ml = _parse_margin(style)
        filters = _parse_filter(style)
        filters['blur'] = max(
            float(filters.get('blur', 0) or 0),
            float(comp.kwargs.get('blur', 0) or 0),
        )
        obj_fit = _parse_object_fit(style)
        if is_avatar:
            w_val = h_val = avatar_size
            ratio = 1.0
            radius = avatar_size // 2
            obj_fit = 'cover'

        fluid_width = w_val == 'match_parent' or (
            ratio is not None and w_val is None and not is_avatar
        )
        w_px = w_val if isinstance(w_val, int) else 200
        h_px = (
            h_val if isinstance(h_val, int)
            else max(1, int(round(w_px / ratio))) if ratio else 150
        )
        # `height: 100%` is the height the parent gives it, as on the phone
        # (match_parent). It was 150px here: a full-bleed picture under a
        # TikTok-style column of buttons stopped a third of the way down.
        fluid_height = h_val == 'match_parent' and not is_avatar

        outer = tk.Frame(parent_widget, bg=bg_color)
        pack_options = {'padx': (ml, mr), 'pady': (mt, mb)}
        if is_flex:
            pack_options['side'] = pack_side
        if fluid_width and (not is_flex or pack_side == tk.TOP):
            pack_options['fill'] = 'x'
        if fluid_height:
            pack_options['fill'] = 'both' if fluid_width else 'y'
            pack_options['expand'] = True
        outer.pack(**pack_options)

        ring_px = int(bw) if (bw > 0 and bc and radius > 0) else 0
        canvas = tk.Canvas(
            outer, width=w_px, height=h_px, bg=bg_color,
            highlightthickness=bw if (bw > 0 and not ring_px) else 0,
            highlightbackground=bc or bg_color,
        )
        if fluid_height:
            canvas.pack(fill='both' if fluid_width else 'y', expand=True)
        else:
            canvas.pack(fill='x' if fluid_width else None)
        tap = comp.kwargs.get('command')
        if tap is not None:
            canvas.configure(cursor='hand2')
            canvas.bind('<Button-1>', lambda _event, run=tap: run())
        state = {
            'raw': None, 'placeholder': True, 'last_width': None,
            'resize_job': None, 'request': 0, 'fade': 0, 'src': src,
        }
        if comp.kwargs.get('zoom'):
            # A tap opens the picture over the whole screen, from here.
            canvas.configure(cursor='hand2')
            canvas.bind('<Button-1>', lambda _event: _zoom_feature.open_from(comp, canvas, state))
        comp._image_state = state
        if not hasattr(self, '_apkpy_image_cache'):
            self._apkpy_image_cache = {}
        status_colors = {
            'online': '#22C55E', 'away': '#F59E0B',
            'busy': '#EF4444', 'offline': '#71717A',
        }

        def _target_size():
            width = max(1, int(canvas.winfo_width() if fluid_width else w_px))
            if fluid_height:
                given = int(canvas.winfo_height())
                return width, (given if given > 1 else h_px)
            height = (
                max(1, int(round(width / ratio)))
                if ratio and not isinstance(h_val, int) else h_px
            )
            if int(float(canvas.cget('height'))) != height:
                canvas.configure(height=height)
            return width, height

        def _draw_status(width, height):
            color = status_colors.get(comp.kwargs.get('status'))
            if not (is_avatar and color):
                return
            dot = max(10, min(width, height) // 4)
            pad = max(1, dot // 7)
            _create_circle(
                canvas,
                width - dot - pad, height - dot - pad,
                width - pad, height - pad,
                fill=color, outline=bg_color, width=max(2, dot // 6),
            )

        def _placeholder(reason=''):
            try:
                if not canvas.winfo_exists():
                    return
            except Exception:
                return
            width, height = _target_size()
            state['raw'] = None
            state['placeholder'] = True
            state['fade'] += 1
            canvas.delete('all')
            canvas.create_rectangle(
                0, 0, width, height, fill='#27272A', outline='#3F3F46',
            )
            cx, cy = width // 2, height // 2
            # Platform-independent vector placeholder (no emoji-font surprises).
            canvas.create_oval(
                cx - 25, cy - 27, cx - 15, cy - 17,
                fill='#A1A1AA', outline='',
            )
            canvas.create_polygon(
                cx - 40, cy + 22, cx - 12, cy - 8,
                cx + 2, cy + 7, cx + 17, cy - 10, cx + 40, cy + 22,
                fill='#52525B', outline='',
            )
            canvas.create_text(
                cx, cy + 38,
                text=os.path.basename(str(state['src'])) or 'image',
                font=('Arial', 9), fill='#A1A1AA',
            )
            _draw_status(width, height)

        def _paint(img):
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(img)
            canvas.image = photo
            canvas.delete('all')
            canvas.create_image(0, 0, anchor='nw', image=photo)
            _draw_status(img.width, img.height)
            _set_backdrop(canvas, img)

        def _draw(raw, remember=True, placeholder_image=False, animate=False):
            try:
                if not canvas.winfo_exists():
                    return
            except Exception:
                return
            from PIL import (
                Image, ImageChops, ImageColor, ImageDraw,
                ImageFilter, ImageOps,
            )
            if remember:
                state['raw'] = raw.copy()
            state['placeholder'] = bool(placeholder_image)
            width, height = _target_size()
            img = raw.convert('RGBA')
            if obj_fit == 'cover':
                img = ImageOps.fit(img, (width, height), Image.LANCZOS)
            elif obj_fit in ('contain', 'none'):
                if obj_fit == 'contain':
                    img.thumbnail((width, height), Image.LANCZOS)
                fitted = Image.new('RGBA', (width, height), (0, 0, 0, 0))
                fitted.paste(img, ((width - img.width) // 2,
                                   (height - img.height) // 2))
                img = fitted
            else:
                img = img.resize((width, height), Image.LANCZOS)

            if filters.get('grayscale', 0) > 0:
                alpha = img.getchannel('A')
                gray = ImageOps.grayscale(img).convert('RGBA')
                gray.putalpha(alpha)
                amount = min(1.0, float(filters['grayscale']))
                img = gray if amount >= 1 else Image.blend(img, gray, amount)
            if filters.get('blur', 0) > 0:
                img = img.filter(ImageFilter.GaussianBlur(filters['blur']))
            if tint:
                try:
                    alpha = img.getchannel('A')
                    tinted = ImageOps.colorize(
                        ImageOps.grayscale(img), (0, 0, 0),
                        ImageColor.getrgb(str(tint)),
                    ).convert('RGBA')
                    tinted.putalpha(alpha)
                    img = tinted
                except (TypeError, ValueError):
                    pass
            if opacity < 1:
                img.putalpha(
                    img.getchannel('A').point(lambda value: int(value * opacity))
                )
            if radius > 0:
                corner = min(radius, width // 2, height // 2)
                # Antialiased, like every other rounded shape in the Previewer.
                mask = _aa_mask(width, height, corner)
                img.putalpha(ImageChops.multiply(img.getchannel('A'), mask))
                if ring_px:
                    try:
                        ring = _aa_shape_image(
                            width, height, corner, None,
                            _aa_rgba(canvas, bc), ring_px,
                        )
                        img = Image.alpha_composite(img, ring)
                    except Exception:
                        pass

            state['fade'] += 1
            fade_token = state['fade']
            if animate and fade_in and not placeholder_image:
                try:
                    bg_rgb = ImageColor.getrgb(bg_color)
                except (TypeError, ValueError):
                    bg_rgb = (0, 0, 0)
                background = Image.new('RGBA', img.size, (*bg_rgb, 255))

                def _step(index):
                    if fade_token != state['fade']:
                        return
                    _paint(Image.blend(background, img, index / 8.0))
                    if index < 8:
                        canvas.after(22, lambda: _step(index + 1))

                _step(1)
            else:
                _paint(img)

        def _asset_path(path):
            if not path:
                return None
            path = str(path)
            if os.path.isabs(path):
                return path
            try:
                base = os.path.dirname(os.path.abspath(__main__.__file__))
            except AttributeError:
                base = os.getcwd()
            return os.path.join(base, path)

        def _draw_asset(path, placeholder_image=False, animate=False):
            if not path:
                return False
            try:
                from PIL import Image
                with Image.open(_asset_path(path)) as opened:
                    raw = opened.copy()
                _draw(raw, placeholder_image=placeholder_image, animate=animate)
                return True
            except Exception:
                return False

        def _fallback():
            if not _draw_asset(fallback, animate=fade_in):
                _placeholder('erro ao carregar')

        def _resize(event):
            size = (event.width, event.height if fluid_height else 0)
            if (not (fluid_width or fluid_height) or event.width <= 1
                    or size == state['last_width']):
                return
            state['last_width'] = size
            if state['resize_job'] is not None:
                try:
                    canvas.after_cancel(state['resize_job'])
                except Exception:
                    pass

            def _redraw():
                state['resize_job'] = None
                if state['raw'] is None:
                    _placeholder()
                else:
                    _draw(
                        state['raw'], remember=False,
                        placeholder_image=state['placeholder'],
                    )

            state['resize_job'] = canvas.after_idle(_redraw)

        if fluid_width or fluid_height:
            canvas.bind('<Configure>', _resize, add='+')

        def _load_src(value):
            state['request'] += 1
            request = state['request']
            state['src'] = value
            is_url = isinstance(value, str) and value.startswith(('http://', 'https://'))
            if not is_url:
                if not _draw_asset(value, animate=fade_in):
                    _fallback()
                return

            if not _draw_asset(placeholder, placeholder_image=True):
                _placeholder('a carregar')
            cached = self._apkpy_image_cache.get(value) if use_cache else None
            if cached is not None:
                self._apkpy_image_cache.pop(value, None)
                self._apkpy_image_cache[value] = cached
                _draw(cached.copy(), animate=fade_in)
                return

            def _fetch(url=value, token=request):
                try:
                    import io
                    import ssl
                    import urllib.request
                    from PIL import Image
                    request_obj = urllib.request.Request(
                        url, headers={'User-Agent': 'ApkPyPreviewer'},
                    )
                    with urllib.request.urlopen(
                        request_obj, timeout=10,
                        context=ssl._create_unverified_context(),
                    ) as response:
                        payload = response.read()
                    with Image.open(io.BytesIO(payload)) as opened:
                        loaded = opened.copy()
                    if use_cache:
                        self._apkpy_image_cache[url] = loaded.copy()
                        while len(self._apkpy_image_cache) > 32:
                            oldest = next(iter(self._apkpy_image_cache))
                            self._apkpy_image_cache.pop(oldest, None)

                    def _finish():
                        if state['request'] == token:
                            _draw(loaded, animate=fade_in)

                    if live_preview() is not None:
                        live_preview().root.after(0, _finish)
                    else:
                        _finish()
                except Exception as exc:
                    print(f"[ApkPy image] falha ao carregar {url} ({exc})")
                    if live_preview() is not None:
                        live_preview().root.after(
                            0, lambda: _fallback()
                            if state['request'] == token else None,
                        )

            import threading
            threading.Thread(target=_fetch, daemon=True).start()

        _load_src(src)
        comp.widget = canvas
        comp._reload_image = _load_src

    def _render_video(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Render a responsive desktop video preview.

        OpenCV decodes real local/HTTP video frames on a single worker so Tk
        never blocks. FFmpeg and sounddevice stream the matching audio from the
        current playback position; pause, seek, speed and mute restart that
        stream without ever touching Tk from a background thread.
        """
        import concurrent.futures
        import queue
        import subprocess
        import threading
        import time

        try:
            import cv2
            from PIL import Image, ImageTk
            decoder_available = True
        except ImportError:
            cv2 = None
            Image = ImageTk = None
            decoder_available = False
        try:
            import imageio_ffmpeg
            import sounddevice
            audio_available = True
        except ImportError:
            imageio_ffmpeg = sounddevice = None
            audio_available = False
        comp_id = comp.kwargs.get('comp_id')
        style = _merge_with_body(comp_id, 'video')
        ratio = comp.kwargs.get('aspect_ratio') or (16.0 / 9.0)
        try:
            ratio = _normalize_image_ratio(style.get('aspect-ratio')) or ratio
        except ValueError:
            pass
        w_val, h_val = _parse_image_size(style)
        fluid_width = w_val == 'match_parent' or w_val is None
        w_px = w_val if isinstance(w_val, int) else 320
        h_px = h_val if isinstance(h_val, int) else max(1, int(round(w_px / ratio)))
        mt, mr, mb, ml = _parse_margin(style)
        surface = _get_style_bg(style) or '#111114'
        text_color = (
            _get_style_fg(style)
            or global_styles.get('__theme__', {}).get('text')
            or '#FAFAFA'
        )

        outer = tk.Frame(parent_widget, bg=bg_color)
        pack_options = {'padx': (ml, mr), 'pady': (mt, mb)}
        if is_flex:
            pack_options['side'] = pack_side
        if fluid_width and (not is_flex or pack_side == tk.TOP):
            pack_options['fill'] = 'x'
        outer.pack(**pack_options)
        show_controls = bool(comp.kwargs.get('controls', True))
        canvas = tk.Canvas(
            outer, width=w_px, height=h_px, bg=surface,
            highlightthickness=0, cursor='hand2',
        )
        canvas.pack(fill='x' if fluid_width else None)
        state = {
            'playing': bool(comp.kwargs.get('autoplay')),
            'controls_visible': show_controls,
            'controls_after': None,
            'position': 0.0,
            'duration': 60.0,
            'speed': 1.0,
            'muted': bool(comp.kwargs.get('muted')),
            'after': None,
            'poll_after': None,
            'poster': None,
            'frame': None,
            'photo': None,
            'source': str(comp.kwargs.get('src') or ''),
            'decoder_ready': False,
            'decoder_loading': False,
            'decoder_error': None,
            'decoder_generation': 0,
            'decode_pending': False,
            'seek_target': None,
            'fps': 24.0,
            'buffered': 0,
            'dragging': False,
            'drag_was_playing': False,
            'closed': False,
            'last_progress': 0.0,
            'audio_generation': 0,
            'audio_error': None,
        }
        decoder = {'capture': None}
        audio = {'process': None}
        audio_lock = threading.Lock()
        decoder_results = queue.Queue()
        decoder_executor = (
            concurrent.futures.ThreadPoolExecutor(
                max_workers=1, thread_name_prefix='apkpy-video',
            )
            if decoder_available else None
        )

        def _size():
            width = max(1, canvas.winfo_width() if fluid_width else w_px)
            video_height = (
                h_val if isinstance(h_val, int)
                else max(1, int(round(width / ratio)))
            )
            if int(float(canvas.cget('height'))) != video_height:
                canvas.configure(height=video_height)
            return width, video_height

        def _fit_preview_image(image_value, width, height):
            source = image_value.copy()
            fit = str(comp.kwargs.get('fit') or 'contain').lower()
            if fit == 'fill':
                return source.resize(
                    (max(1, width), max(1, height)), Image.Resampling.LANCZOS,
                )
            scale = (
                max(width / source.width, height / source.height)
                if fit == 'cover'
                else min(width / source.width, height / source.height)
            )
            target = (
                max(1, int(round(source.width * scale))),
                max(1, int(round(source.height * scale))),
            )
            source = source.resize(target, Image.Resampling.LANCZOS)
            if fit == 'cover':
                left = max(0, (source.width - width) // 2)
                top = max(0, (source.height - height) // 2)
                source = source.crop((left, top, left + width, top + height))
            return source

        def _draw():
            try:
                if not canvas.winfo_exists():
                    return
            except Exception:
                return
            width, video_height = _size()
            canvas.delete('all')
            canvas.create_rectangle(
                0, 0, width, video_height, fill=surface, outline='',
            )
            visual = state.get('frame') or state.get('poster')
            if visual is not None and Image is not None:
                try:
                    source = _fit_preview_image(visual, width, video_height)
                    if show_controls and state['controls_visible']:
                        # Tk has no alpha channel for Canvas rectangles. Blend
                        # the translucent scrim into the full frame so the
                        # controls never become an opaque black lower block.
                        source = Image.blend(
                            source.convert('RGB'),
                            Image.new('RGB', source.size, '#000000'), 0.28,
                        )
                    state['photo'] = ImageTk.PhotoImage(source)
                    canvas.create_image(
                        width // 2, video_height // 2, image=state['photo'],
                    )
                except Exception:
                    pass
            if state.get('decoder_loading') and state.get('frame') is None:
                canvas.create_text(
                    width // 2, video_height // 2, text='Opening video…',
                    fill=text_color,
                    font=('Segoe UI', 10) if os.name == 'nt'
                    else ('Helvetica', 10),
                )
            elif state.get('decoder_error') and state.get('frame') is None:
                canvas.create_text(
                    width // 2, video_height // 2,
                    text=state['decoder_error'], fill='#FCA5A5', width=width - 32,
                    justify='center',
                    font=('Segoe UI', 9) if os.name == 'nt'
                    else ('Helvetica', 9),
                )
            progress = (
                state['position'] / state['duration']
                if state['duration'] > 0 else 0.0
            )
            if show_controls and state['controls_visible']:
                center_x = width // 2
                control_y = max(
                    34, min(video_height - 78, int(video_height * 0.48)),
                )
                gap = max(38, min(56, width // 6))
                disabled = '#71717A'
                _draw_material_icon(
                    canvas, 'skip_previous', center_x - gap * 2,
                    control_y, disabled, size=27,
                )
                _draw_material_icon(
                    canvas, 'replay_5', center_x - gap,
                    control_y, text_color, size=27,
                )
                _create_circle(
                    canvas,
                    center_x - 21, control_y - 21,
                    center_x + 21, control_y + 21,
                    fill=text_color, outline='',
                )
                _draw_material_icon(
                    canvas, 'pause' if state['playing'] else 'play_arrow',
                    center_x, control_y, '#18181B', size=25,
                )
                _draw_material_icon(
                    canvas, 'forward_15', center_x + gap,
                    control_y, text_color, size=27,
                )
                _draw_material_icon(
                    canvas, 'skip_next', center_x + gap * 2,
                    control_y, disabled, size=27,
                )

                track_left = 14
                track_right = max(track_left + 1, width - 14)
                track_y = max(control_y + 32, video_height - 55)
                buffered = max(
                    0.0, min(1.0, state.get('buffered', 0) / 100.0),
                )
                progress = max(0.0, min(1.0, progress))
                canvas.create_line(
                    track_left, track_y, track_right, track_y,
                    fill='#52525B', width=3, capstyle='round',
                )
                if buffered > 0:
                    canvas.create_line(
                        track_left, track_y,
                        track_left + (track_right - track_left) * buffered,
                        track_y, fill='#A1A1AA', width=3, capstyle='round',
                    )
                progress_x = track_left + (track_right - track_left) * progress
                if progress > 0:
                    canvas.create_line(
                        track_left, track_y, progress_x, track_y,
                        fill=text_color, width=3, capstyle='round',
                    )
                _create_circle(
                    canvas,
                    progress_x - 5, track_y - 5,
                    progress_x + 5, track_y + 5,
                    fill=text_color, outline='',
                )
                current = max(0, int(state['position']))
                duration = max(0, int(state['duration']))
                time_y = video_height - 25
                canvas.create_text(
                    track_left, time_y,
                    text=(
                        f"{current // 60}:{current % 60:02d}  ·  "
                        f"{duration // 60}:{duration % 60:02d}"
                    ),
                    fill=text_color, anchor='w',
                    font=('Segoe UI', 10) if os.name == 'nt'
                    else ('Helvetica', 10),
                )
                _draw_material_icon(
                    canvas, 'settings', width - 22, time_y,
                    text_color, size=20,
                )

        def _progress_callback():
            callback = comp.kwargs.get('on_progress')
            if callable(callback):
                callback(
                    int(state['position']), int(state['duration']),
                    int(state.get('buffered', 0)),
                )

        def _resolve_source(source):
            value = str(source or '')
            if value.startswith(('http://', 'https://', 'rtsp://')):
                return value
            if os.path.isabs(value):
                return value
            main_file = getattr(__main__, '__file__', '')
            base = (
                os.path.dirname(os.path.abspath(main_file))
                if main_file else os.getcwd()
            )
            candidate = os.path.join(base, value)
            return candidate if os.path.exists(candidate) else value

        def _audio_speed_filter(speed):
            """Build an FFmpeg atempo chain for the supported 0.25x..4x."""
            remaining = max(0.25, min(4.0, float(speed)))
            factors = []
            while remaining < 0.5:
                factors.append(0.5)
                remaining /= 0.5
            while remaining > 2.0:
                factors.append(2.0)
                remaining /= 2.0
            factors.append(remaining)
            return ','.join(f'atempo={factor:.6g}' for factor in factors)

        def _stop_audio():
            # Invalidating the generation also handles the race where pause is
            # pressed while FFmpeg or the output device is still opening.
            state['audio_generation'] += 1
            with audio_lock:
                process = audio.get('process')
                audio['process'] = None
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

        def _audio_worker(token, source, position, speed):
            process = None
            stream = None
            try:
                command = [
                    imageio_ffmpeg.get_ffmpeg_exe(),
                    '-nostdin', '-loglevel', 'error',
                    '-ss', f'{max(0.0, position):.3f}',
                    '-i', _resolve_source(source),
                    '-vn', '-sn', '-dn',
                    '-filter:a', _audio_speed_filter(speed),
                    '-f', 's16le', '-acodec', 'pcm_s16le',
                    '-ac', '2', '-ar', '44100', 'pipe:1',
                ]
                popen_options = {
                    'stdin': subprocess.DEVNULL,
                    'stdout': subprocess.PIPE,
                    'stderr': subprocess.DEVNULL,
                    'bufsize': 65536,
                }
                if os.name == 'nt':
                    popen_options['creationflags'] = getattr(
                        subprocess, 'CREATE_NO_WINDOW', 0,
                    )
                process = subprocess.Popen(command, **popen_options)
                with audio_lock:
                    if token != state['audio_generation'] or state['closed']:
                        process.terminate()
                        return
                    audio['process'] = process
                stream = sounddevice.RawOutputStream(
                    samplerate=44100, channels=2, dtype='int16',
                    blocksize=4096,
                )
                stream.start()
                while (
                    token == state['audio_generation']
                    and not state['closed'] and state['playing']
                    and not state['muted']
                ):
                    chunk = process.stdout.read(16384)
                    if not chunk:
                        break
                    stream.write(chunk)
            except Exception as exc:
                decoder_results.put(('audio_error', (token, str(exc))))
            finally:
                if stream is not None:
                    try:
                        stream.abort()
                        stream.close()
                    except Exception:
                        pass
                if process is not None:
                    if process.poll() is None:
                        try:
                            process.terminate()
                        except Exception:
                            pass
                    try:
                        process.wait(timeout=1)
                    except Exception:
                        try:
                            process.kill()
                        except Exception:
                            pass
                    with audio_lock:
                        if audio.get('process') is process:
                            audio['process'] = None

        def _start_audio():
            _stop_audio()
            if (
                not audio_available or state['closed'] or not state['playing']
                or state['muted'] or not state['decoder_ready']
                or not state['source']
            ):
                return
            state['audio_error'] = None
            token = state['audio_generation']
            threading.Thread(
                target=_audio_worker,
                args=(
                    token, state['source'], state['position'], state['speed'],
                ),
                name='apkpy-video-audio', daemon=True,
            ).start()

        def _frame_to_image(frame):
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return Image.fromarray(rgb)

        def _release_capture():
            capture = decoder.get('capture')
            decoder['capture'] = None
            if capture is not None:
                capture.release()

        def _open_capture(token, source):
            _release_capture()
            capture = cv2.VideoCapture(_resolve_source(source))
            if not capture.isOpened():
                capture.release()
                return token, False, 'Could not open this video', None
            decoder['capture'] = capture
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            if not (fps > 0.0 and fps < 241.0):
                fps = 24.0
            frame_count = float(
                capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            )
            duration = frame_count / fps if frame_count > 0 else 60.0
            ok, frame = capture.read()
            if not ok or frame is None:
                capture.release()
                decoder['capture'] = None
                return token, False, 'The video has no readable frames', None
            position = max(
                0.0, float(capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0,
            )
            return token, True, '', {
                'image': _frame_to_image(frame),
                'fps': fps,
                'duration': max(0.1, duration),
                'position': position,
            }

        def _read_capture(token, seek_target):
            capture = decoder.get('capture')
            if capture is None or not capture.isOpened():
                return token, False, True, 'Video decoder is closed', None
            if seek_target is not None:
                capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, seek_target) * 1000.0)
            ok, frame = capture.read()
            if not ok or frame is None:
                return token, False, True, '', None
            position = max(
                0.0, float(capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0,
            )
            return token, True, False, '', {
                'image': _frame_to_image(frame), 'position': position,
            }

        def _report_decoder_error(message):
            _stop_audio()
            state['decoder_loading'] = False
            state['decoder_ready'] = False
            state['decoder_error'] = str(message or 'Video preview failed')
            state['playing'] = False
            _cancel_controls_hide()
            state['controls_visible'] = show_controls
            _draw()
            callback = comp.kwargs.get('on_error')
            if callable(callback):
                callback(state['decoder_error'])

        def _queue_decode(force=False, delay_ms=None):
            if (
                state['closed'] or not state['decoder_ready']
                or state['decode_pending']
                or (not force and not state['playing'])
            ):
                return

            def _submit():
                state['after'] = None
                if (
                    state['closed'] or not state['decoder_ready']
                    or state['decode_pending']
                    or (not force and not state['playing'])
                ):
                    return
                state['decode_pending'] = True
                target = state.get('seek_target')
                state['seek_target'] = None
                future = decoder_executor.submit(
                    _read_capture, state['decoder_generation'], target,
                )
                future.add_done_callback(
                    lambda completed: decoder_results.put(('frame', completed))
                )

            if delay_ms and delay_ms > 0:
                state['after'] = canvas.after(delay_ms, _submit)
            else:
                _submit()

        def _accept_open(future):
            try:
                token, success, message, payload = future.result()
            except Exception as exc:
                _report_decoder_error(str(exc))
                return
            if state['closed'] or token != state['decoder_generation']:
                return
            state['decoder_loading'] = False
            if not success:
                _report_decoder_error(message)
                return
            state['decoder_ready'] = True
            state['decoder_error'] = None
            state['fps'] = payload['fps']
            state['duration'] = payload['duration']
            state['position'] = payload['position']
            state['frame'] = payload['image']
            state['buffered'] = 100
            _draw()
            _progress_callback()
            ready = comp.kwargs.get('on_ready')
            if callable(ready):
                ready()
            if state['playing']:
                _start_audio()
                _queue_decode(delay_ms=0)
                _schedule_controls_hide()

        def _accept_frame(future):
            try:
                token, success, ended, message, payload = future.result()
            except Exception as exc:
                _report_decoder_error(str(exc))
                return
            if state['closed'] or token != state['decoder_generation']:
                return
            state['decode_pending'] = False
            if success:
                # A drag/seek may have arrived while this frame was decoding.
                # Do not flash the stale pre-seek frame; decode the requested
                # position immediately instead.
                if state.get('seek_target') is not None:
                    _queue_decode(force=True)
                    return
                state['frame'] = payload['image']
                state['position'] = min(
                    state['duration'], payload['position'],
                )
                now = time.monotonic()
                if now - state['last_progress'] >= 0.20:
                    state['last_progress'] = now
                    _progress_callback()
                _draw()
                if state['playing']:
                    delay = max(
                        1, int(round(1000.0 / (
                            state['fps'] * max(0.25, state['speed'])
                        ))),
                    )
                    _queue_decode(delay_ms=delay)
                return
            if message:
                _report_decoder_error(message)
                return
            if ended and comp.kwargs.get('loop'):
                state['position'] = 0.0
                state['seek_target'] = 0.0
                _start_audio()
                _queue_decode(force=True)
                return
            _stop_audio()
            state['playing'] = False
            state['position'] = state['duration']
            _cancel_controls_hide()
            state['controls_visible'] = show_controls
            _progress_callback()
            _draw()
            callback = comp.kwargs.get('on_end')
            if callable(callback):
                callback()

        def _poll_decoder():
            state['poll_after'] = None
            if state['closed']:
                return
            while True:
                try:
                    kind, future = decoder_results.get_nowait()
                except queue.Empty:
                    break
                if kind == 'poster':
                    if future is not None:
                        state['poster'] = future
                    _draw()
                elif kind == 'open':
                    _accept_open(future)
                elif kind == 'audio_error':
                    token, message = future
                    if token == state['audio_generation']:
                        state['audio_error'] = message
                        print(f"[video] audio preview: {message}")
                else:
                    _accept_frame(future)
            state['poll_after'] = canvas.after(15, _poll_decoder)

        def _begin_decoder():
            if not decoder_available:
                state['decoder_error'] = (
                    'Video Preview dependencies are unavailable; reinstall apkpy'
                )
                _draw()
                ready = comp.kwargs.get('on_ready')
                if callable(ready):
                    ready()
                if state['playing']:
                    _tick()
                return
            state['decoder_generation'] += 1
            token = state['decoder_generation']
            state['decoder_loading'] = True
            state['decoder_ready'] = False
            state['decoder_error'] = None
            state['decode_pending'] = False
            state['frame'] = None
            _draw()
            future = decoder_executor.submit(
                _open_capture, token, state['source'],
            )
            future.add_done_callback(
                lambda completed: decoder_results.put(('open', completed))
            )

        def _tick():
            """Lightweight fallback timeline when OpenCV is unavailable."""
            state['after'] = None
            if not state['playing'] or state['decoder_ready']:
                return
            state['position'] += 0.5 * state['speed']
            if state['position'] >= state['duration']:
                if comp.kwargs.get('loop'):
                    state['position'] = 0.0
                else:
                    state['position'] = state['duration']
                    state['playing'] = False
                    callback = comp.kwargs.get('on_end')
                    if callable(callback):
                        callback()
            _progress_callback()
            _draw()
            if state['playing'] and not state['decoder_ready']:
                state['after'] = canvas.after(500, _tick)

        def _cancel_controls_hide():
            callback_id = state.get('controls_after')
            if callback_id is not None:
                try:
                    canvas.after_cancel(callback_id)
                except Exception:
                    pass
                state['controls_after'] = None

        def _hide_controls():
            state['controls_after'] = None
            if (
                state['closed'] or not show_controls or not state['playing']
                or state['dragging']
            ):
                return
            state['controls_visible'] = False
            _draw()

        def _schedule_controls_hide(delay_ms=2800):
            _cancel_controls_hide()
            if (
                show_controls and state['controls_visible']
                and state['playing'] and not state['dragging']
                and not state['closed']
            ):
                state['controls_after'] = canvas.after(
                    max(1, int(delay_ms)), _hide_controls,
                )

        def _show_controls_temporarily():
            if not show_controls or state['closed']:
                return
            was_hidden = not state['controls_visible']
            state['controls_visible'] = True
            if was_hidden:
                _draw()
            _schedule_controls_hide()

        def _play():
            if state['position'] >= state['duration']:
                state['position'] = 0.0
                state['seek_target'] = 0.0
            state['playing'] = True
            if show_controls:
                state['controls_visible'] = True
            _draw()
            _schedule_controls_hide()
            if state['decoder_ready']:
                _start_audio()
                _queue_decode(force=True)
            elif decoder_available:
                if not state['decoder_loading']:
                    _begin_decoder()
            else:
                _tick()

        def _pause():
            state['playing'] = False
            _stop_audio()
            _cancel_controls_hide()
            if show_controls:
                state['controls_visible'] = True
            if state['after'] is not None:
                try:
                    canvas.after_cancel(state['after'])
                except Exception:
                    pass
                state['after'] = None
            _draw()

        def _stop():
            _pause()
            state['position'] = 0.0
            state['seek_target'] = 0.0
            if state['decoder_ready']:
                _queue_decode(force=True)
            _progress_callback()
            _draw()

        def _seek(seconds, decode=True):
            try:
                state['position'] = max(
                    0.0, min(state['duration'], float(seconds))
                )
            except (TypeError, ValueError):
                return
            state['seek_target'] = state['position']
            if decode:
                if state['decoder_ready']:
                    _queue_decode(force=True)
                    if state['playing']:
                        _start_audio()
                elif decoder_available and not state['decoder_loading']:
                    _begin_decoder()
            _progress_callback()
            _draw()
            if state['playing']:
                _show_controls_temporarily()

        def _set_source(src, autoplay=False):
            _pause()
            state['source'] = str(src or '')
            state['position'] = 0.0
            state['duration'] = 60.0
            state['buffered'] = 0
            state['frame'] = None
            state['playing'] = bool(autoplay)
            state['decoder_generation'] += 1
            state['decoder_ready'] = False
            state['decoder_loading'] = False
            state['decoder_error'] = None
            state['audio_error'] = None
            _draw()
            if comp.kwargs.get('preload', True) or state['playing']:
                _begin_decoder()
            if state['playing']:
                _schedule_controls_hide()

        def _set_speed(speed):
            try:
                state['speed'] = max(0.25, min(4.0, float(speed)))
                if state['playing']:
                    _start_audio()
                    _show_controls_temporarily()
            except (TypeError, ValueError):
                pass

        def _set_muted(muted=True):
            state['muted'] = bool(muted)
            if state['muted']:
                _stop_audio()
            elif state['playing']:
                _start_audio()
            _draw()
            if state['playing']:
                _show_controls_temporarily()

        def _load_poster():
            poster = comp.kwargs.get('poster')
            if not poster:
                decoder_results.put(('poster', None))
                return
            try:
                import io
                import ssl
                import urllib.request
                from PIL import Image
                if str(poster).startswith(('http://', 'https://')):
                    request = urllib.request.Request(
                        str(poster), headers={'User-Agent': 'ApkPyPreviewer'},
                    )
                    with urllib.request.urlopen(
                            request, timeout=10,
                            context=ssl._create_unverified_context()) as response:
                        image_value = Image.open(
                            io.BytesIO(response.read())
                        ).convert('RGB')
                else:
                    path = str(poster)
                    if not os.path.isabs(path):
                        path = os.path.join(
                            os.path.dirname(os.path.abspath(__main__.__file__)),
                            path,
                        )
                    image_value = Image.open(path).convert('RGB')
                decoder_results.put(('poster', image_value))
            except Exception:
                decoder_results.put(('poster', None))

        def _control_geometry():
            width, video_height = _size()
            center_x = width // 2
            control_y = max(
                34, min(video_height - 78, int(video_height * 0.48)),
            )
            gap = max(38, min(56, width // 6))
            track_left = 14
            track_right = max(track_left + 1, width - 14)
            track_y = max(control_y + 32, video_height - 55)
            return (
                width, video_height, center_x, control_y, gap,
                track_left, track_right, track_y,
            )

        def _timeline_seconds(event):
            (
                _width, _video_height, _center_x, _control_y, _gap,
                track_left, track_right, _track_y,
            ) = _control_geometry()
            fraction = max(0.0, min(
                1.0,
                (float(event.x) - track_left)
                / max(1, track_right - track_left),
            ))
            return state['duration'] * fraction

        def _pointer_down(event):
            (
                width, video_height, center_x, control_y, gap,
                _track_left, _track_right, track_y,
            ) = _control_geometry()
            if show_controls and not state['controls_visible']:
                _show_controls_temporarily()
                return
            if show_controls and abs(event.y - track_y) <= 12:
                state['dragging'] = True
                state['drag_was_playing'] = state['playing']
                _pause()
                _seek(_timeline_seconds(event), decode=False)
                return
            if show_controls and event.y >= video_height - 47 and event.x >= width - 48:
                speeds = (0.5, 1.0, 1.25, 1.5, 2.0)
                closest = min(
                    range(len(speeds)),
                    key=lambda index: abs(speeds[index] - state['speed']),
                )
                _set_speed(speeds[(closest + 1) % len(speeds)])
                _draw()
                _schedule_controls_hide()
                return
            if show_controls and abs(event.y - control_y) <= 31:
                if abs(event.x - center_x) <= 27:
                    _pause() if state['playing'] else _play()
                elif abs(event.x - (center_x - gap)) <= 25:
                    _seek(state['position'] - 5)
                elif abs(event.x - (center_x + gap)) <= 25:
                    _seek(state['position'] + 15)
                return
            if show_controls and event.y < video_height:
                _cancel_controls_hide()
                state['controls_visible'] = False
                _draw()

        def _pointer_activity(_event=None):
            if not state['dragging']:
                _show_controls_temporarily()

        def _pointer_move(event):
            if state['dragging']:
                _seek(_timeline_seconds(event), decode=False)

        def _pointer_up(event):
            if not state['dragging']:
                return
            resume = state['drag_was_playing']
            state['dragging'] = False
            state['drag_was_playing'] = False
            _seek(_timeline_seconds(event), decode=True)
            if resume:
                _play()

        def _show_video():
            if outer.winfo_manager() != 'pack':
                outer.pack(**pack_options)

        def _hide_video():
            _pause()
            outer.pack_forget()

        def _destroy_video(event):
            if event.widget is not outer or state['closed']:
                return
            state['closed'] = True
            state['playing'] = False
            state['decoder_generation'] += 1
            _stop_audio()
            for key in ('after', 'poll_after', 'controls_after'):
                callback_id = state.get(key)
                if callback_id is not None:
                    try:
                        canvas.after_cancel(callback_id)
                    except Exception:
                        pass
                    state[key] = None
            if decoder_executor is not None:
                try:
                    decoder_executor.submit(_release_capture)
                    decoder_executor.shutdown(wait=False)
                except Exception:
                    pass

        comp.widget = outer
        comp._component_show = _show_video
        comp._component_hide = _hide_video
        comp._video_play = _play
        comp._video_pause = _pause
        comp._video_stop = _stop
        comp._video_seek = _seek
        comp._video_set_source = _set_source
        comp._video_set_speed = _set_speed
        comp._video_set_muted = _set_muted
        canvas.bind('<Button-1>', _pointer_down)
        canvas.bind('<B1-Motion>', _pointer_move)
        canvas.bind('<ButtonRelease-1>', _pointer_up)
        canvas.bind('<Motion>', _pointer_activity, add='+')
        outer.bind('<Destroy>', _destroy_video, add='+')
        if fluid_width:
            canvas.bind('<Configure>', lambda _event=None: _draw(), add='+')

        threading.Thread(target=_load_poster, daemon=True).start()
        state['poll_after'] = canvas.after(15, _poll_decoder)
        _draw()
        if comp.kwargs.get('preload', True) or state['playing']:
            _begin_decoder()
        if state['playing']:
            _schedule_controls_hide()

    def _render_spinner(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Renderiza um spinner de loading (arco circular rotativo animado)."""
        comp_id = comp.kwargs.get('comp_id')
        style   = _merge_with_body(comp_id, 'spinner')
        color   = _get_style_fg(style) or '#4F46E5'
        mt, mr, mb, ml = _parse_margin(style)
        w_val, _h = _parse_image_size(style)
        size = w_val if isinstance(w_val, int) and w_val > 0 else 48

        outer = tk.Frame(parent_widget, bg=bg_color)
        pack_opts = {'padx': (ml, mr), 'pady': (mt + 4, mb + 4)}
        if is_flex:
            pack_opts['side'] = pack_side

        # A zero-size anchor preserves the declarative position. Hiding the
        # spinner can therefore remove its whole wrapper (and all its height)
        # while show() inserts it back at exactly the same point.
        anchor = tk.Frame(
            parent_widget, bg=bg_color, width=0, height=0,
            bd=0, highlightthickness=0,
        )
        anchor_opts = {'side': pack_side} if is_flex else {'side': tk.TOP}
        anchor.pack(**anchor_opts)

        canvas = tk.Canvas(outer, width=size, height=size, bg=bg_color, highlightthickness=0)
        comp.widget = canvas

        pad   = max(3, size // 8)
        state = {'angle': 0, 'running': False}

        def _tick():
            if not state['running']:
                return
            try:
                canvas.delete('all')
                canvas.create_arc(pad, pad, size - pad, size - pad,
                                  start=state['angle'], extent=270,
                                  style='arc', outline=color, width=pad)
                state['angle'] = (state['angle'] - 12) % 360
                canvas.after(40, _tick)
            except Exception:
                state['running'] = False

        def _start():
            if not state['running']:
                state['running'] = True
                _tick()

        def _show():
            if canvas.winfo_manager() != 'pack':
                canvas.pack()
            if outer.winfo_manager() != 'pack':
                outer.pack(before=anchor, **pack_opts)
            _start()

        def _hide():
            state['running'] = False
            try:
                canvas.delete('all')
            except Exception:
                pass
            outer.pack_forget()

        comp._spin_show = _show
        comp._spin_hide = _hide

        if comp.kwargs.get('visible', True):
            _show()

    def _render_skeleton(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Render a compact pulsing skeleton without one widget per row."""
        comp_id = comp.kwargs.get('comp_id')
        variant = comp.kwargs.get('variant', 'music_card')
        count = max(1, int(comp.kwargs.get('count', 1)))
        style = _merge_with_body(comp_id, 'skeleton')
        mt, mr, mb, ml = _parse_margin(style)
        radius = max(3, _parse_radius(style) or 8)
        base = _tk_color(_get_style_bg(style), '#343239')
        text_color = global_styles.get('__theme__', {}).get('text', '#E6E1E5')
        row_height = {'music_card': 72, 'list': 64, 'card': 194, 'text': 22}[variant]
        gap = 12 if variant != 'text' else 10
        total_height = count * row_height + max(0, count - 1) * gap

        outer = tk.Frame(parent_widget, bg=bg_color)
        # Keep a tiny anchor in the original pack order. The real component is
        # packed immediately before it and is removed completely by hide().
        # Keeping the (unmanaged) Canvas inside a permanently packed outer
        # frame made Tk preserve its old requested height, leaving a skeleton-
        # sized blank area that pushed empty/error states below the viewport.
        pack_opts = {'fill': 'x'}
        if is_flex:
            pack_opts['side'] = pack_side
        anchor = tk.Frame(
            parent_widget, bg=bg_color, width=0, height=0,
            bd=0, highlightthickness=0,
        )
        anchor_opts = {'side': pack_side} if is_flex else {
            'side': tk.TOP, 'fill': 'x'
        }
        anchor.pack(**anchor_opts)
        canvas_pack_opts = {
            'padx': (ml, mr), 'pady': (mt, mb),
            'fill': 'x', 'expand': True,
        }
        canvas = tk.Canvas(
            outer, height=total_height, bg=bg_color,
            highlightthickness=0, bd=0,
        )
        comp.widget = canvas
        state = {'running': False, 'phase': 0, 'after': None}
        base_rgb = _hex_to_rgb(base)
        text_rgb = _hex_to_rgb(text_color)

        def _pulse_color():
            step = state['phase'] % 24
            strength = (step if step <= 12 else 24 - step) / 12.0
            amount = 0.05 + strength * 0.11
            return _rgb_to_hex(*[
                _lerp(a, b, amount) for a, b in zip(base_rgb, text_rgb)
            ])

        def _rounded(x1, y1, x2, y2, r, fill):
            if x2 > x1 and y2 > y1:
                _create_rounded_rect(
                    canvas, x1, y1, x2, y2, r,
                    fill=fill, outline='', tags='skeleton_shape',
                )

        def _draw(_event=None):
            try:
                width = max(160, canvas.winfo_width())
                color = _pulse_color()
                canvas.delete('all')
                for index in range(count):
                    top = index * (row_height + gap)
                    if variant == 'music_card':
                        _rounded(0, top + 8, 56, top + 64, min(radius, 12), color)
                        _rounded(72, top + 14, width * .72, top + 28, radius, color)
                        _rounded(72, top + 40, width * .48, top + 51, radius, color)
                    elif variant == 'list':
                        _rounded(0, top + 8, 48, top + 56, 24, color)
                        _rounded(64, top + 12, width * .82, top + 25, radius, color)
                        _rounded(64, top + 37, width * .56, top + 48, radius, color)
                    elif variant == 'card':
                        _rounded(0, top, width, top + 124, min(radius, 14), color)
                        _rounded(0, top + 142, width * .72, top + 158, radius, color)
                        _rounded(0, top + 173, width * .48, top + 185, radius, color)
                    else:
                        line_width = (.92, .78, .62)[index % 3]
                        _rounded(0, top + 3, width * line_width, top + 17, radius, color)
            except Exception:
                state['running'] = False

        def _tick():
            if not state['running']:
                return
            state['phase'] += 1
            _draw()
            state['after'] = canvas.after(55, _tick)

        def _show():
            if canvas.winfo_manager() != 'pack':
                canvas.pack(**canvas_pack_opts)
            if outer.winfo_manager() != 'pack':
                outer.pack(before=anchor, **pack_opts)
            if not state['running']:
                state['running'] = True
                _tick()

        def _hide():
            state['running'] = False
            if state['after'] is not None:
                try:
                    canvas.after_cancel(state['after'])
                except Exception:
                    pass
                state['after'] = None
            outer.pack_forget()

        canvas.bind('<Configure>', _draw, add='+')
        comp._component_show = _show
        comp._component_hide = _hide
        if comp.kwargs.get('visible', True):
            _show()

    def _render_state(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Render an empty/error state as one centered semantic block."""
        kind = comp.comp_type
        comp_id = comp.kwargs.get('comp_id')
        style = _merge_with_body(comp_id, kind)
        mt, mr, mb, ml = _parse_margin(style)
        pad_t, pad_r, pad_b, pad_l = _parse_padding_tk(style)
        panel_bg = _tk_color(_get_style_bg(style), bg_color)
        tokens = global_styles.get('__theme__', {})
        fg = _get_style_fg(style) or tokens.get('text', '#E6E1E5')
        secondary = tokens.get('text_secondary', '#CAC4D0')
        icon_color = style.get('icon-color') or (
            tokens.get('error', '#F2B8B5') if kind == 'error_state'
            else tokens.get('primary', '#D0BCFF')
        )

        outer = tk.Frame(parent_widget, bg=bg_color)
        options = {'fill': 'x'}
        if is_flex:
            options['side'] = pack_side
        anchor = tk.Frame(
            parent_widget, bg=bg_color, width=0, height=0,
            bd=0, highlightthickness=0,
        )
        anchor_opts = {'side': pack_side} if is_flex else {
            'side': tk.TOP, 'fill': 'x'
        }
        anchor.pack(**anchor_opts)
        panel_pack_opts = {
            'padx': (ml, mr), 'pady': (mt, mb),
            'fill': 'x', 'expand': True,
        }
        panel = tk.Frame(outer, bg=panel_bg)
        icon_canvas = tk.Canvas(
            panel, width=72, height=72, bg=panel_bg,
            highlightthickness=0, bd=0,
        )
        icon_canvas.pack(pady=(pad_t, 12))
        _draw_material_icon(
            icon_canvas, comp.kwargs.get('icon'), 36, 36,
            icon_color, size=52, tags='state_icon',
        )
        wrap = max(180, (self._content_width or 411) - pad_l - pad_r - 52)
        tk.Label(
            panel, text=comp.kwargs.get('title', ''), bg=panel_bg, fg=fg,
            anchor='center', justify='center',
            font=('Segoe UI', 18, 'bold') if os.name == 'nt' else ('Helvetica', 18, 'bold'),
            wraplength=wrap,
        ).pack(fill='x', padx=(pad_l, pad_r), pady=(0, 8))
        message = str(comp.kwargs.get('message', '') or '')
        if message:
            tk.Label(
                panel, text=message, bg=panel_bg, fg=secondary,
                anchor='center', justify='center',
                font=('Segoe UI', 11) if os.name == 'nt' else ('Helvetica', 11),
                wraplength=wrap,
            ).pack(fill='x', padx=(pad_l, pad_r), pady=(0, 18))

        action = next(
            (child for child in comp.children if child.comp_type == 'button'), None
        )
        if action is not None:
            action_wrap = tk.Frame(panel, bg=panel_bg)
            action_wrap.pack(fill='x', padx=(pad_l, pad_r), pady=(0, pad_b))
            self._render_button(action, action_wrap, False, tk.TOP, panel_bg)
        else:
            tk.Frame(panel, bg=panel_bg, height=pad_b).pack(fill='x')
        comp.widget = panel

        def _show():
            if panel.winfo_manager() != 'pack':
                panel.pack(**panel_pack_opts)
            if outer.winfo_manager() != 'pack':
                outer.pack(before=anchor, **options)

        def _hide():
            outer.pack_forget()

        comp._component_show = _show
        comp._component_hide = _hide
        if comp.kwargs.get('visible', True):
            _show()

    def _load_thumb(self, canvas, src, size, height=None):
        """Carrega uma miniatura (URL ou ficheiro local) num pequeno canvas de
        uma linha rica de list_view. Placeholder + carga async; degrada se faltar
        Pillow ou a imagem falhar. ``size`` is the width; ``height`` defaults
        to it, and a wider box is filled and cropped in the middle, as
        centerCrop does on the phone."""
        height = height or size
        request = int(getattr(canvas, '_thumb_request', 0)) + 1
        canvas._thumb_request = request

        def _draw_ph():
            try:
                if getattr(canvas, '_thumb_request', None) != request:
                    return
                canvas.delete('all')
                canvas.create_rectangle(0, 0, size, height, fill='#1E293B', outline='')
                canvas.create_text(size // 2, height // 2, text='\U0001f3b5',
                                   font=('Arial', max(10, min(size, height) // 3)),
                                   fill='#475569')
            except Exception:
                pass

        def _draw_img(img):
            try:
                if getattr(canvas, '_thumb_request', None) != request:
                    return
                from PIL import Image, ImageTk, ImageOps
                img = ImageOps.fit(img.convert('RGB'), (size, height), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                canvas.delete('all')
                canvas.create_image(0, 0, anchor='nw', image=photo)
                canvas._thumb_photo = photo  # manter referência (senão o GC apaga)
            except Exception:
                _draw_ph()

        _draw_ph()
        is_url = isinstance(src, str) and (src.startswith('http://') or src.startswith('https://'))
        if is_url:
            def _fetch():
                try:
                    import urllib.request, ssl, io
                    from PIL import Image
                    req = urllib.request.Request(src, headers={'User-Agent': 'ApkPyPreviewer'})
                    ctx = ssl._create_unverified_context()
                    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                        data = r.read()
                    img = Image.open(io.BytesIO(data))
                    if live_preview() is not None:
                        live_preview().root.after(0, lambda: _draw_img(img))
                    else:
                        _draw_img(img)
                except Exception:
                    pass
            import threading
            threading.Thread(target=_fetch, daemon=True).start()
        else:
            try:
                from PIL import Image
                p = src
                if not os.path.isabs(p):
                    try:
                        sd = os.path.dirname(os.path.abspath(__main__.__file__))
                    except AttributeError:
                        sd = os.getcwd()
                    p = os.path.join(sd, src)
                _draw_img(Image.open(p))
            except Exception:
                pass

    def _render_list(self, comp, parent_widget, is_flex, pack_side, bg_color):
        comp_id  = comp.kwargs.get('comp_id')
        style    = _merge_with_body(comp_id, 'list')
        items    = comp.kwargs.get('items', [])
        on_click = comp.kwargs.get('on_click')

        item_bg  = _get_style_bg(style) or bg_color
        item_fg  = _get_style_fg(style) or '#212121'
        divider  = _get_style_border_color(style) or '#E2E8F0'
        mt, mr, mb, ml = _parse_margin(style)
        radius = _parse_radius(style)
        border_width = _parse_border_width(style)

        raw_h = style.get('height', '')
        cleaned_h = re.sub(r'[^0-9.]', '', str(raw_h))
        try:
            list_h = int(float(cleaned_h))
        except (ValueError, TypeError):
            list_h = 320

        outer = tk.Frame(parent_widget, bg=bg_color)
        outer.pack(padx=(ml, mr), pady=(mt, mb), fill='x')

        list_parent = outer
        if radius > 0:
            panel_inset = max(2, min(6, radius // 3), border_width)
            panel = tk.Canvas(
                outer, bg=bg_color, height=list_h,
                highlightthickness=0, bd=0,
            )
            panel.pack(fill='x')
            list_parent = tk.Frame(panel, bg=item_bg)
            list_parent_win = panel.create_window(
                (panel_inset, panel_inset), window=list_parent,
                anchor='nw', tags='list_content',
            )

            def _draw_list_panel(event, c=panel, win=list_parent_win):
                try:
                    w = event.width
                    c.delete('list_shape')
                    _create_rounded_rect(
                        c, 1, 1, w - 1, list_h - 1, radius,
                        fill=item_bg, outline=divider,
                        width=max(1, border_width), tags='list_shape',
                    )
                    c.tag_lower('list_shape')
                    c.itemconfigure(
                        win,
                        width=max(1, w - panel_inset * 2),
                        height=max(1, list_h - panel_inset * 2),
                    )
                except Exception:
                    pass

            panel.bind('<Configure>', _draw_list_panel)

        canvas = tk.Canvas(
            list_parent, bg=item_bg,
            height=max(1, list_h - (panel_inset * 2 if radius > 0 else 0)),
            highlightthickness=0, bd=0,
        )
        scrollbar = tk.Scrollbar(list_parent, orient='vertical', command=canvas.yview)
        inner = tk.Frame(canvas, bg=item_bg)
        inner_win = canvas.create_window((0, 0), window=inner, anchor='nw')

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(inner_win, width=e.width))

        def _on_scroll(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
            # "break" impede que o bind_all do ecrã (scroll da screen) também dispare:
            # com o rato sobre a lista, só a LISTA faz scroll, não o ecrã.
            return "break"

        canvas.bind('<MouseWheel>', _on_scroll)
        inner.bind('<MouseWheel>', _on_scroll)

        title_font = ('Segoe UI', 12) if os.name == 'nt' else ('Helvetica', 12)
        sub_font   = ('Segoe UI', 10) if os.name == 'nt' else ('Helvetica', 10)

        def _bind_scroll(widget):
            widget.bind('<MouseWheel>', _on_scroll)

        def _build(item_list):
            for w in inner.winfo_children():
                w.destroy()
            for i, item in enumerate(item_list):
                if isinstance(item, dict):
                    title    = item.get('title', str(item))
                    subtitle = item.get('subtitle', '')
                    image_url = item.get('image', '')
                else:
                    title, subtitle, image_url = str(item), '', ''

                row = tk.Frame(inner, bg=item_bg, cursor='hand2' if on_click else '')
                row.pack(fill='x')
                _bind_scroll(row)

                thumb = None
                if image_url:
                    # Linha rica: miniatura à esquerda + texto à direita
                    thumb = tk.Canvas(row, width=52, height=52, bg='#1E293B', highlightthickness=0)
                    thumb.pack(side='left', padx=(14, 0), pady=8)
                    _bind_scroll(thumb)
                    self._load_thumb(thumb, image_url, 52)
                    text_parent = tk.Frame(row, bg=item_bg)
                    text_parent.pack(side='left', fill='x', expand=True, padx=(12, 14))
                    _bind_scroll(text_parent)
                    _tpad = 0
                else:
                    text_parent = row
                    _tpad = 14

                t_lbl = tk.Label(text_parent, text=title, bg=item_bg, fg=item_fg,
                                 font=title_font, anchor='w', padx=_tpad,
                                 pady=(10 if not image_url else 8) if not subtitle else (5 if not image_url else 6))
                t_lbl.pack(fill='x')
                _bind_scroll(t_lbl)

                s_lbl = None
                if subtitle:
                    s_lbl = tk.Label(text_parent, text=subtitle, bg=item_bg, fg='#94A3B8',
                                     font=sub_font, anchor='w', padx=_tpad)
                    s_lbl.pack(fill='x', pady=(0, 8 if not image_url else 6))
                    _bind_scroll(s_lbl)

                if i < len(item_list) - 1:
                    tk.Frame(inner, bg=divider, height=1).pack(fill='x', padx=14)

                if on_click:
                    all_labels = [t_lbl] + ([s_lbl] if s_lbl else [])
                    if thumb is not None:
                        all_labels.append(thumb)
                    def _make(d=item, r=row, ib=item_bg, lbls=all_labels):
                        def _click(e):
                            r.config(bg='#E2E8F0')
                            for l in lbls:
                                try: l.config(bg='#E2E8F0')
                                except: pass
                            r.after(150, lambda: _restore(r, ib, lbls))
                            on_click(d)
                        def _restore(r, ib, lbls):
                            try: r.config(bg=ib)
                            except: pass
                            for l in lbls:
                                try: l.config(bg=ib)
                                except: pass
                        return _click
                    fn = _make()
                    row.bind('<Button-1>', fn)
                    for l in all_labels:
                        l.bind('<Button-1>', fn)

        _build(items)
        comp.widget = canvas
        comp._list_update_fn = _build

        if getattr(comp, '_initial_value', None) is not None:
            _build(comp._initial_value)

    # ── Legacy (sem Screen) ───────────────────────────────────────────────────

    def _render_chart(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Bars, a line, a donut or a ring, from chart_rules.

        Shapes are drawn by Pillow at 3x and scaled down -- Tk's canvas draws
        neither smooth arcs nor smooth diagonals on Windows -- and the text is
        Tk's, in the Previewer's own font. Every position comes from
        chart_rules, the numbers ApkpyChart draws from on the phone."""
        from PIL import Image, ImageDraw, ImageTk
        from . import chart_rules as rules
        comp_id = comp.kwargs.get('comp_id')
        own = component_style(global_styles, 'chart', comp_id, include_body=False)
        colors = rules.chart_colors(global_styles.get('__theme__', {}), own)
        kind = comp.kwargs.get('kind', 'bar')
        mt, mr, mb, ml = _parse_margin(_merge_with_body(comp_id, 'container'))
        height_match = re.search(r'([0-9.]+)', str(own.get('height', '')))
        draw_h = int(float(height_match.group(1))) if height_match else rules.DEFAULT_HEIGHT[kind]
        stroke_match = re.search(r'([0-9.]+)', str(own.get('stroke-width', '')))
        radius_match = re.search(r'([0-9.]+)', str(own.get('border-radius', '')))
        font_match = re.search(r'([0-9.]+)', str(own.get('font-size', '')))
        label_size = int(float(font_match.group(1))) if font_match else rules.LABEL_SIZE
        family = 'Segoe UI' if os.name == 'nt' else 'Helvetica'
        label_font = (family, -label_size)
        bg = _tk_color(bg_color, '#FFFFFF')

        outer = tk.Frame(parent_widget, bg=bg)
        if is_flex and pack_side in (tk.LEFT, tk.RIGHT):
            outer.pack(side=pack_side, fill='both', expand=True, padx=(ml, mr), pady=(mt, mb))
        else:
            outer.pack(fill='x', padx=(ml, mr), pady=(mt, mb),
                       **({'side': pack_side} if is_flex else {}))
        canvas = tk.Canvas(outer, height=draw_h, bg=bg, highlightthickness=0, bd=0)
        canvas.pack(fill='x')
        comp.widget = canvas
        hits = []          # (kind, geometry, item) for on_click

        def _rgba(colour, alpha=1.0):
            hex_value = _tk_color(colour, bg).lstrip('#')
            r, g, b = (int(hex_value[i:i + 2], 16) for i in (0, 2, 4))
            return (r, g, b, int(round(255 * alpha)))

        def _items():
            return rules.items_from(comp.kwargs.get('items') or [],
                                    comp.kwargs.get('x', 'label'), comp.kwargs.get('y', 'value'))

        def _draw(_event=None):
            try:
                width = canvas.winfo_width()
            except tk.TclError:
                return
            if width <= 2:
                return
            items = _items()
            legend_h = rules.legend_height(items) if kind == 'donut' else 0
            total_h = draw_h + legend_h
            if int(float(canvas.cget('height'))) != total_h:
                canvas.configure(height=total_h)
            S = 3
            image = Image.new('RGBA', (width * S, draw_h * S), _rgba(bg))
            pen = ImageDraw.Draw(image)
            canvas.delete('all')
            del hits[:]
            texts = []
            if kind in ('bar', 'line'):
                values = [value for _label, value, _c in items]
                scale_top, step = rules.nice_scale(max(values) if values else 0)
                left, top = rules.AXIS_WIDTH, 8
                plot_w = max(1, width - left - 8)
                plot_h = max(1, draw_h - top - rules.LABEL_HEIGHT)
                ticks = int(round(scale_top / step))
                for k in range(ticks + 1):
                    y = top + plot_h - (k * step / scale_top) * plot_h
                    pen.line([(left * S, y * S), ((left + plot_w) * S, y * S)],
                             fill=_rgba(colors['grid']), width=S)
                    texts.append((left - 6, y, rules.format_number(k * step), 'e', colors['label']))
                series = _rgba(colors['series'])
                if kind == 'bar':
                    corner = float(radius_match.group(1)) if radius_match else rules.BAR_RADIUS
                    for position, ((x0, y0, x1, y1), item) in enumerate(zip(
                            rules.bar_rects(values, left, top, plot_w, plot_h, scale_top), items)):
                        r = min(corner, (x1 - x0) / 2.0, max(0.0, y1 - y0) / 2.0)
                        if y1 - y0 >= 0.5:
                            pen.rounded_rectangle([x0 * S, y0 * S, x1 * S, y1 * S], radius=r * S,
                                                  fill=_rgba(item[2] or colors['series']),
                                                  corners=(True, True, False, False))
                        hits.append(('rect', (x0, top, x1, y1), position))
                else:
                    points = rules.line_points(values, left, top, plot_w, plot_h, scale_top)
                    line_w = float(stroke_match.group(1)) if stroke_match else rules.LINE_WIDTH
                    if comp.kwargs.get('fill') and len(points) > 1:
                        area = [(x * S, y * S) for x, y in points]
                        area += [(points[-1][0] * S, (top + plot_h) * S),
                                 (points[0][0] * S, (top + plot_h) * S)]
                        layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
                        ImageDraw.Draw(layer).polygon(area, fill=_rgba(colors['series'], rules.FILL_ALPHA))
                        image.alpha_composite(layer)
                        pen = ImageDraw.Draw(image)
                    if len(points) > 1:
                        pen.line([(x * S, y * S) for x, y in points], fill=series,
                                 width=int(round(line_w * S)), joint='curve')
                    for position, ((x, y), item) in enumerate(zip(points, items)):
                        rr = rules.POINT_RADIUS * S
                        pen.ellipse([x * S - rr, y * S - rr, x * S + rr, y * S + rr], fill=series)
                        hits.append(('rect', (x - plot_w / max(2, len(points)) / 2.0, top,
                                              x + plot_w / max(2, len(points)) / 2.0, top + plot_h), position))
                    # a line's labels sit under its points
                step_k = rules.label_step(len(items), plot_w)
                if kind == 'bar':
                    centers = [(x0 + x1) / 2.0 for x0, _y0, x1, _y1 in
                               rules.bar_rects(values, left, top, plot_w, plot_h, scale_top)]
                else:
                    centers = [x for x, _y in rules.line_points(values, left, top, plot_w, plot_h, scale_top)]
                for index, (cx, item) in enumerate(zip(centers, items)):
                    if index % step_k == 0 and item[0]:
                        texts.append((cx, top + plot_h + rules.LABEL_HEIGHT / 2.0, item[0], 'center',
                                      colors['label']))
            elif kind == 'donut':
                thickness = float(stroke_match.group(1)) if stroke_match else rules.DONUT_THICKNESS
                size = max(10, min(width, draw_h) - 8)
                cx, cy = width / 2.0, draw_h / 2.0
                box = [(cx - size / 2.0) * S, (cy - size / 2.0) * S,
                       (cx + size / 2.0) * S, (cy + size / 2.0) * S]
                arcs = rules.slices([value for _l, value, _c in items])
                if not any(sweep for _start, sweep in arcs):
                    pen.ellipse(box, outline=_rgba(colors['track']), width=int(thickness * S))
                for index, ((start, sweep), item) in enumerate(zip(arcs, items)):
                    if sweep <= 0:
                        continue
                    colour = rules.slice_color(index, item[2], colors['series'])
                    pen.arc(box, start, start + sweep, fill=_rgba(colour), width=int(thickness * S))
                    hits.append(('slice', (cx, cy, size / 2.0 - thickness, size / 2.0, start, sweep), index))
                if comp.kwargs.get('center') is not None:
                    texts.append((cx, cy, str(comp.kwargs.get('center')), 'center', colors['center'], True))
            else:   # ring
                thickness = float(stroke_match.group(1)) if stroke_match else rules.RING_THICKNESS
                size = max(10, draw_h - 8)
                cx, cy = width / 2.0, draw_h / 2.0
                box = [(cx - size / 2.0) * S, (cy - size / 2.0) * S,
                       (cx + size / 2.0) * S, (cy + size / 2.0) * S]
                pen.ellipse(box, outline=_rgba(colors['track']), width=int(thickness * S))
                fraction = rules.ring_fraction(comp.kwargs.get('value', 0), comp.kwargs.get('max', 100))
                if fraction > 0:
                    series = _rgba(colors['series'])
                    pen.arc(box, -90, -90 + fraction * 360.0, fill=series, width=int(thickness * S))
                    # Round ends, as Paint.Cap.ROUND draws them on the phone.
                    import math as _math
                    mid = size / 2.0 - thickness / 2.0
                    for angle in (-90.0, -90.0 + fraction * 360.0):
                        ex = cx + mid * _math.cos(_math.radians(angle))
                        ey = cy + mid * _math.sin(_math.radians(angle))
                        rr = thickness / 2.0 * S
                        pen.ellipse([ex * S - rr, ey * S - rr, ex * S + rr, ey * S + rr], fill=series)
                texts.append((cx, cy, rules.ring_center_text(
                    comp.kwargs.get('value', 0), comp.kwargs.get('max', 100),
                    comp.kwargs.get('center')), 'center', colors['center'], True))
            small = image.resize((width, draw_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(small, master=canvas)
            canvas._apkpy_chart_photo = photo
            canvas.create_image(0, 0, image=photo, anchor='nw')
            for entry in texts:
                x, y, text, anchor, colour = entry[:5]
                big = len(entry) > 5 and entry[5]
                canvas.create_text(x, y, text=text, anchor=anchor, fill=_tk_color(colour, bg),
                                   font=(family, -22, 'bold') if big else label_font)
            if kind == 'donut' and legend_h:
                row_y = draw_h + 8
                for index, (label, value, item_colour) in enumerate(items):
                    if not label:
                        continue
                    colour = _tk_color(rules.slice_color(index, item_colour, colors['series']), bg)
                    mid_y = row_y + rules.LEGEND_ROW / 2.0
                    d = rules.LEGEND_DOT
                    canvas.create_oval(16, mid_y - d / 2.0, 16 + d, mid_y + d / 2.0, fill=colour, outline='')
                    canvas.create_text(16 + d + 10, mid_y, text=label, anchor='w',
                                       fill=_tk_color(colors['center'], bg), font=label_font)
                    canvas.create_text(width - 16, mid_y, text=rules.format_number(value), anchor='e',
                                       fill=_tk_color(colors['label'], bg), font=label_font)
                    row_y += rules.LEGEND_ROW

        def _click(event):
            callback = comp.kwargs.get('on_click')
            if not callback:
                return
            import math as _math
            raw = comp.kwargs.get('items') or []
            for shape, geometry, position in hits:
                hit = False
                if shape == 'rect':
                    x0, y0, x1, y1 = geometry
                    hit = x0 <= event.x <= x1 and y0 <= event.y <= y1
                else:
                    cx, cy, inner, outer_r, start, sweep = geometry
                    dx, dy = event.x - cx, event.y - cy
                    distance = _math.hypot(dx, dy)
                    angle = (_math.degrees(_math.atan2(dy, dx)) - start) % 360.0
                    hit = inner <= distance <= outer_r and angle <= sweep
                if hit:
                    callback(raw[position] if position < len(raw) else {})
                    return

        canvas.bind('<Configure>', _draw)
        canvas.bind('<Button-1>', _click)
        if comp.kwargs.get('on_click'):
            canvas.configure(cursor='hand2')
        comp._chart_redraw = _draw


    def _render_pager(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Tabs over pages that slide: the page on screen sets the height.

        The tab strip, the indicator and the page offset are drawn from the
        same numbers the phone's ApkpyPager uses (theme.pager_colors,
        theme.tab_bar_height). Pages are placed side by side in a clipping
        frame and moved together; a drag of more than a fifth of the width
        goes to the next page, as a fling does on the phone."""
        from .theme import pager_colors, tab_bar_height, TAB_INDICATOR_HEIGHT
        comp_id = comp.kwargs.get('comp_id')
        own = component_style(global_styles, 'pager', comp_id, include_body=False)
        colors = pager_colors(global_styles.get('__theme__', {}), own)
        strip_bg = _tk_color(colors['background'], bg_color) if colors['background'] else bg_color
        active = _tk_color(colors['active'], '#6750A4')
        inactive = _tk_color(colors['inactive'], '#64748B')
        indicator_color = _tk_color(colors['indicator'], active)
        caps = own.get('text-transform')
        tabs = [child for child in comp.children if child.comp_type == 'tab']
        count = len(tabs)
        # Spaced as a container is -- the phone lays the pager out as one,
        # body gap included -- while its colours are its own.
        mt, mr, mb, ml = _parse_margin(_merge_with_body(comp_id, 'container'))

        outer = tk.Frame(parent_widget, bg=bg_color)
        if is_flex and pack_side in (tk.LEFT, tk.RIGHT):
            outer.pack(side=pack_side, fill='both', expand=True,
                       padx=(ml, mr), pady=(mt, mb))
        else:
            outer.pack(fill='x', padx=(ml, mr), pady=(mt, mb),
                       **({'side': pack_side} if is_flex else {}))
        comp.widget = outer

        has_text = any(str(t.kwargs.get('text') or '').strip() for t in tabs)
        has_icon = any(t.kwargs.get('icon') for t in tabs)
        bar_h = tab_bar_height(has_text, has_icon)
        strip = tk.Frame(outer, bg=strip_bg, height=bar_h)
        strip.pack(fill='x')
        strip.pack_propagate(False)
        strip.grid_propagate(False)
        cells = []
        font = _build_tk_font({'font-size': '14px', 'font-weight': 'bold'}, default_size=11)
        for index, tab_comp in enumerate(tabs):
            strip.grid_columnconfigure(index, weight=1, uniform='apkpy_tab')
            cell = tk.Canvas(strip, height=bar_h, bg=strip_bg, highlightthickness=0,
                             bd=0, cursor='hand2')
            cell.grid(row=0, column=index, sticky='nsew')
            cells.append(cell)
        strip.grid_rowconfigure(0, weight=1)
        indicator = tk.Frame(strip, bg=indicator_color, height=TAB_INDICATOR_HEIGHT)
        if colors['divider']:
            tk.Frame(outer, bg=_tk_color(colors['divider'], strip_bg), height=1).pack(fill='x')

        viewport = tk.Frame(outer, bg=bg_color, height=1)
        viewport.pack(fill='x')
        viewport.pack_propagate(False)
        pages = []
        for tab_comp in tabs:
            page = tk.Frame(viewport, bg=bg_color)
            page_def = ComponentDef('container', comp_id=tab_comp.kwargs.get('comp_id'))
            page_def.children = tab_comp.children
            page_def._reactive_visible = tab_comp._reactive_visible
            self._render_container(page_def, page, False, None, bg_color)
            tab_comp.widget = page
            pages.append(page)

        start = max(0, min(count - 1, int(getattr(comp, '_initial_page', 0) or 0))) if count else 0
        state = {'current': start, 'offset': float(start), 'anim': None}
        comp._current_page = start

        def _paint_tabs():
            nearest = int(round(state['offset']))
            for index, (cell, tab_comp) in enumerate(zip(cells, tabs)):
                cell.delete('all')
                width = max(1, cell.winfo_width())
                colour = active if index == nearest else inactive
                text = apply_text_transform(str(tab_comp.kwargs.get('text') or ''), caps,
                                            default='uppercase')
                icon = tab_comp.kwargs.get('icon')
                if icon and text:
                    _draw_material_icon(cell, icon, width / 2, bar_h / 2 - 11, colour, size=24)
                    cell.create_text(width / 2, bar_h / 2 + 16, text=text, fill=colour, font=font)
                elif icon:
                    _draw_material_icon(cell, icon, width / 2, bar_h / 2, colour, size=24)
                else:
                    cell.create_text(width / 2, bar_h / 2, text=text, fill=colour, font=font)

        def _place():
            width = max(1, viewport.winfo_width())
            for index, page in enumerate(pages):
                page.place(x=int(round((index - state['offset']) * width)), y=0, width=width)
            if count:
                tab_w = width / float(count)
                indicator.place(x=int(round(state['offset'] * tab_w)),
                                y=bar_h - TAB_INDICATOR_HEIGHT,
                                width=int(round(tab_w)), height=TAB_INDICATOR_HEIGHT)
                indicator.lift()

        def _fit_height(_event=None):
            if not pages:
                return
            try:
                wanted = max(1, pages[state['current']].winfo_reqheight())
                if int(float(viewport.cget('height'))) != wanted:
                    viewport.configure(height=wanted)
                    _relayout_above(viewport)
            except tk.TclError:
                pass

        def _settle(target):
            state['current'] = target
            state['offset'] = float(target)
            comp._current_page = target
            _place()
            _paint_tabs()
            _fit_height()

        def _slide_to(target):
            if not count:
                return
            target = max(0, min(count - 1, int(target)))
            if state['anim'] is not None:
                try:
                    viewport.after_cancel(state['anim'])
                except tk.TclError:
                    pass
                state['anim'] = None
            ms = _motion.duration('nav', _motion_preset())
            origin = state['offset']
            steps = max(1, int(round(ms / 16.0))) if ms > 0 else 0
            if steps == 0 or abs(origin - target) < 1e-3:
                _settle(target)
                return
            # The height follows the page it lands on from the start: the
            # phone requests a layout when the page changes, not at the end.
            state['current'] = target
            comp._current_page = target
            _fit_height()

            def _tick(step=1):
                progress = min(1.0, float(step) / steps)
                state['offset'] = origin + (target - origin) * _motion.ease(progress)
                _place()
                _paint_tabs()
                if progress < 1.0:
                    state['anim'] = viewport.after(16, lambda: _tick(step + 1))
                else:
                    state['anim'] = None
                    _settle(target)
            _tick()

        comp._select_page = _slide_to

        for index, cell in enumerate(cells):
            cell.bind('<Button-1>', lambda _e, i=index: _slide_to(i))
            cell.bind('<Configure>', lambda _e: _paint_tabs())
        viewport.bind('<Configure>', lambda _e: _place())
        for page in pages:
            page.bind('<Configure>', _fit_height, add='+')

        # A drag anywhere on a page: it moves with the pointer once it has
        # gone 12px sideways (and more sideways than down), and lands on the
        # next page past a fifth of the width -- or back on this one.
        drag = {'x': None, 'y': None, 'active': False, 'from': 0.0}
        tag = 'ApkpyPager%d' % id(outer)

        def _press(event):
            drag.update(x=event.x_root, y=event.y_root, active=False, **{'from': state['offset']})

        def _motion_drag(event):
            if drag['x'] is None or count < 2:
                return
            dx = event.x_root - drag['x']
            dy = event.y_root - drag['y']
            if not drag['active']:
                if abs(dx) <= 12 or abs(dx) <= abs(dy) * 1.2:
                    return
                drag['active'] = True
            width = max(1, viewport.winfo_width())
            state['offset'] = max(0.0, min(float(count - 1), drag['from'] - dx / float(width)))
            _place()
            _paint_tabs()

        def _release(_event):
            if drag['x'] is None:
                return
            was_active, drag['x'] = drag['active'], None
            if not was_active:
                return
            moved = state['offset'] - state['current']
            target = state['current']
            if moved > 0.2:
                target = state['current'] + 1
            elif moved < -0.2:
                target = state['current'] - 1
            _slide_to(target)

        viewport.bind_class(tag, '<ButtonPress-1>', _press, add='+')
        viewport.bind_class(tag, '<B1-Motion>', _motion_drag, add='+')
        viewport.bind_class(tag, '<ButtonRelease-1>', _release, add='+')

        def _tag_tree(widget=None):
            widget = widget or viewport
            try:
                tags = widget.bindtags()
                if tag not in tags:
                    widget.bindtags((tag,) + tuple(tags))
                for child in widget.winfo_children():
                    _tag_tree(child)
            except tk.TclError:
                pass

        _place()
        viewport.after_idle(lambda: (_tag_tree(), _settle(state['current'])))
        viewport.after(400, _tag_tree)


    def _render_virtual_collection(self, comp, parent_widget, is_flex,
                                   pack_side, bg_color):
        """Virtual list/grid backed by a bounded pool of reusable item views."""
        comp_id = comp.kwargs.get('comp_id')
        style = _merge_with_body(comp_id, 'virtual_collection')
        template = dict(comp.kwargs.get('template') or {})
        mode = comp.kwargs.get('layout', 'list')
        columns = 1 if mode == 'list' else max(
            1, int(comp.kwargs.get('columns', 2) or 2)
        )
        extent = max(56, int(comp.kwargs.get('item_height', 88) or 88))
        # Com altura automatica `extent` deixa de ser a lei e passa a ser a
        # estimativa por onde o scroll comeca, ate' cada linha ser medida.
        auto_height = bool(comp.kwargs.get('auto_height'))
        row_template = comp.kwargs.get('row_template')
        overscan = max(1, int(comp.kwargs.get('buffer', 2) or 2))
        prefetch = max(0, int(comp.kwargs.get('prefetch', 4) or 0))
        on_click = comp.kwargs.get('on_click')
        # Swipe and drag on the rows (gesture_rules). With either on, a tap is
        # taken when the button comes up, as Android takes it; taken on the
        # press, the start of every swipe opened the row it was swiping.
        swipe_right = comp.kwargs.get('swipe_right')
        swipe_left = comp.kwargs.get('swipe_left')
        can_reorder = bool(comp.kwargs.get('reorder'))
        gestures_on = bool(swipe_right or swipe_left or can_reorder) and mode == 'list'
        click_event = '<ButtonRelease-1>' if gestures_on else '<Button-1>'
        gesture_tag = 'ApkpyRowGesture%d' % id(comp)

        def _tag_gesture_tree(widget):
            """Put the gesture handlers first on a row and all it holds."""
            pending = [widget]
            while pending:
                current = pending.pop()
                try:
                    tags = current.bindtags()
                    if gesture_tag not in tags:
                        current.bindtags((gesture_tag,) + tuple(tags))
                    pending.extend(current.winfo_children())
                except tk.TclError:
                    pass
        has_image = bool(template.get('image'))
        has_markdown = bool(template.get('markdown'))
        has_avatar = bool(template.get('avatar'))
        # O mesmo `code-copy: button;` que o Android le', pelo mesmo parser.
        from .core.style_parser import wants_code_copy as _wants_code_copy
        row_copy_code = _wants_code_copy(style)

        height_match = re.search(r'([0-9.]+)', str(style.get('height', '520')))
        viewport_h = max(
            180, int(float(height_match.group(1))) if height_match else 520
        )
        # height: auto -- as tall as its items, scrolling with the screen (a
        # profile's photo grid under its header). The phone writes
        # wrap_content without nested scrolling; here the canvas takes the
        # content's height and every row is drawn.
        grows_with_items = str(style.get('height', '')).strip().lower() == 'auto'
        mt, mr, mb, ml = _parse_margin(style)
        theme = global_styles.get('__theme__', {})
        # Every one of these can be handed an 8-digit CSS colour, and Tk has no
        # per-widget alpha: a transparent surface is whatever sits behind it.
        # `item-background-color: #00000000` used to take the Previewer down
        # with an E1999 at startup -- which is exactly how a chat turn asks to
        # be text on the page rather than a card.
        collection_bg = _tk_color(_get_style_bg(style), bg_color)
        item_bg = _tk_color(
            style.get('item-background-color'), collection_bg)
        title_fg = _tk_color(
            style.get('title-color') or _get_style_fg(style), '#212121')
        subtitle_fg = _tk_color(
            style.get('subtitle-color'), theme.get('text_secondary', '#64748B'))
        meta_fg = _tk_color(style.get('meta-color'),
                            theme.get('primary', title_fg))
        badge_bg = _tk_color(style.get('badge-background-color'),
                             theme.get('primary', '#6750A4'))
        badge_fg = _tk_color(style.get('badge-color'),
                             theme.get('on_primary', '#FFFFFF'))
        badge_end = _badge_at_end(style)
        divider = _tk_color(
            style.get('item-border-color') or _get_style_border_color(style)
            or theme.get('border', '#E2E8F0'),
            item_bg,
        )
        # One line is the list-row default. A chat message needs more, and
        # reads as nonsense ellipsised to a single line -- Android's row
        # adapter takes the same two numbers.
        title_lines = line_count(style.get('title-lines'), 1)
        subtitle_lines = line_count(style.get('subtitle-lines'), 1)
        # Bubbles (a chat) or spaced, rounded rows: the rule Android reads too.
        bubble_table, item_shape = collection_bubbles(
            global_styles, comp_id, list(comp.kwargs.get('variants') or {}))
        shaped = mode == 'list' and bool(bubble_table or item_shape)
        item_radius = item_shape[0] if item_shape and item_shape[0] > 0 else 0
        item_gap = item_shape[1] if item_shape and item_shape[1] > 0 else 0

        outer = tk.Frame(parent_widget, bg=bg_color)
        pack_opts = {
            'padx': (ml, mr), 'pady': (mt, mb),
            'fill': 'both', 'expand': True,
        }
        if is_flex:
            pack_opts['side'] = pack_side
        outer.pack(**pack_opts)

        canvas = tk.Canvas(
            outer, bg=collection_bg, height=viewport_h,
            highlightthickness=0, bd=0,
        )
        scrollbar = tk.Scrollbar(outer, orient='vertical')
        canvas.pack(side='left', fill='both', expand=True)
        comp.widget = canvas

        state = {
            'items': list(
                comp._initial_value
                if comp._initial_value is not None
                else comp.kwargs.get('items', [])
            ),
            'first': -1,
            # Alturas ja' medidas, por indice de linha. O que ainda nao foi
            # visto vale a estimativa -- que e' como qualquer lista de alturas
            # variaveis funciona: nao se pode medir o que nao se desenhou.
            'heights': {},
            'estimate': float(extent),
            'offsets': None,
        }
        token_re = re.compile(r'\{([A-Za-z_][A-Za-z0-9_.-]*)\}')

        def _row_count():
            return (len(state['items']) + columns - 1) // columns

        def _row_height(index):
            return state['heights'].get(index, state['estimate'])

        def _offsets():
            """Onde cada linha comeca. Recalculado so' quando algo mudou."""
            if state['offsets'] is not None:
                return state['offsets']
            running = 0.0
            table = []
            for index in range(_row_count()):
                table.append(running)
                running += _row_height(index)
            table.append(running)          # o fim, para o scrollregion
            state['offsets'] = table
            return table

        def _invalidate_offsets():
            state['offsets'] = None

        def _first_visible(top):
            """A primeira linha visivel, por busca binaria nas posicoes."""
            table = _offsets()
            if len(table) <= 1:
                return 0
            import bisect
            return max(0, bisect.bisect_right(table, top) - 1)

        def _field(item, path):
            if not isinstance(item, dict):
                return str(item) if path in ('title', 'value') else ''
            value = item
            for part in path.split('.'):
                if not isinstance(value, dict):
                    return ''
                value = value.get(part, '')
            return '' if value is None else str(value)

        def _format(pattern, item):
            if pattern in (None, ''):
                return ''
            return token_re.sub(
                lambda match: _field(item, match.group(1)), str(pattern)
            )

        AVATAR_SIZE = 40

        def _paint_avatar(canvas, value):
            """Um circulo com as iniciais, na cor que o nome escolhe.

            As iniciais e a cor saem da mesma tabela que o Java recebe: se
            fossem calculadas aqui de outra maneira, o mesmo nome ficava de
            duas cores e ninguem percebia porque.
            """
            canvas.delete('all')
            text = avatar_initials(value)
            if not text:
                return False
            fill = avatar_color(value)
            ink = avatar_text_color(fill)
            _create_circle(
                canvas, 1, 1, AVATAR_SIZE - 1, AVATAR_SIZE - 1,
                fill=_tk_color(fill, item_bg), outline='',
            )
            canvas.create_text(
                AVATAR_SIZE / 2.0, AVATAR_SIZE / 2.0, text=text, fill=ink,
                font=('Segoe UI', 12, 'bold') if os.name == 'nt'
                else ('Helvetica', 12, 'bold'),
            )
            return True

        def _new_cell(row, column):
            if row_template is not None:
                # Built from components on every bind; nothing fixed to make.
                cell = tk.Frame(row, bg=item_bg, bd=0, highlightthickness=0,
                                cursor='hand2' if on_click else '')
                # No spacing of its own, in a grid too: the phone's
                # GridLayoutManager adds none, and the row's padding is what
                # spaces the cells (a photo grid is 1px apart, not 10).
                cell.grid(row=0, column=column, sticky='nsew')
                return {'frame': cell, 'row_mode': True, 'item': None,
                        'thumb': None, 'title': None, 'subtitle': None,
                        'badge': None, 'meta': None, 'body': None,
                        'avatar': None, 'text_box': None, 'stack': None,
                        'image_size': 0, 'backdrop': None, 'trail': None}
            body = None          # a fatia de Markdown, quando o template a pede
            text_box = None      # so' existe no modo lista
            stack = None         # a ordem de empilhamento, idem
            cell = tk.Frame(
                row, bg=item_bg, cursor='hand2' if on_click else '',
                bd=0, highlightthickness=0,
            )
            cell.grid(row=0, column=column, sticky='nsew',
                      padx=(0 if mode == 'list' else 5),
                      pady=((item_gap // 2, item_gap - item_gap // 2) if shaped
                            else (0 if mode == 'list' else 5)))
            backdrop = None
            if shaped:
                # Tk frames are rectangles. The row's shape is an antialiased
                # image behind its content -- the corners stay clear of it --
                # which is how the phone's rounded bubble looks.
                cell.configure(bg=collection_bg)
                backdrop = tk.Label(cell, bd=0, highlightthickness=0, bg=collection_bg)
                backdrop.place(x=0, y=0, relwidth=1, relheight=1)
                backdrop.lower()
                backdrop._apkpy_fill = item_bg

                def _paint_backdrop(_event=None, current=cell, holder=backdrop):
                    try:
                        width, height = current.winfo_width(), current.winfo_height()
                        if width <= 2 or height <= 2:
                            return
                        photo = _aa_photo(holder, {
                            'w': width, 'h': height, 'r': item_radius,
                            'fill': holder._apkpy_fill, 'outline': '', 'width': 0})
                        holder.configure(image=photo)
                        holder._apkpy_photo = photo
                    except Exception:
                        current.configure(bg=holder._apkpy_fill)

                cell.bind('<Configure>', _paint_backdrop, add='+')
                backdrop._apkpy_paint = _paint_backdrop
            trail = None
            if mode == 'list':
                image_size = max(44, min(64, extent - 24))
                leading = 0
                avatar = None
                if has_avatar:
                    avatar = tk.Canvas(
                        cell, width=AVATAR_SIZE, height=AVATAR_SIZE,
                        bg=item_bg, highlightthickness=0, bd=0,
                    )
                    # Encostado ao topo: numa linha alta um circulo a flutuar
                    # a meio nao aponta para o inicio da mensagem.
                    avatar.grid(row=0, column=leading, rowspan=2, sticky='n',
                                padx=(12, 10), pady=10)
                    leading += 1
                thumb = None
                if has_image:
                    thumb = tk.Canvas(
                        cell, width=image_size, height=image_size,
                        bg='#1E293B', highlightthickness=0, bd=0,
                    )
                    thumb.grid(row=0, column=leading, rowspan=2,
                               padx=(12 if leading == 0 else 0, 10), pady=10)
                    leading += 1
                content_column = leading
                cell.grid_columnconfigure(content_column, weight=1)
                text_box = tk.Frame(cell, bg=item_bg)
                text_box.grid(
                    row=0, column=content_column, rowspan=2, sticky='nsew',
                    padx=(12 if leading == 0 else 0, 0), pady=10,
                )
                title = tk.Label(
                    text_box, bg=item_bg, fg=title_fg, anchor='w',
                    font=('Segoe UI', 11, 'bold') if os.name == 'nt'
                    else ('Helvetica', 11, 'bold'),
                )
                title.pack(fill='x')
                subtitle = tk.Label(
                    text_box, bg=item_bg, fg=subtitle_fg, anchor='w',
                    font=('Segoe UI', 9) if os.name == 'nt'
                    else ('Helvetica', 9),
                )
                subtitle.pack(fill='x', pady=(3, 0))
                # An empty Label still occupies a line. A row that does not
                # use a slot has to stop reserving its space, or a turn with
                # only a message arrives as one line of text at the bottom of
                # an empty grey slab.
                stack = [(title, {'fill': 'x'}),
                         (subtitle, {'fill': 'x', 'pady': (3, 0)})]
                _wrap_row_text(text_box, title, title_lines)
                _wrap_row_text(text_box, subtitle, subtitle_lines)
                body = None
                if has_markdown:
                    # O mesmo renderizador do componente markdown() e os
                    # mesmos estilos: um bloco de codigo tem de ser o mesmo
                    # bloco de codigo nos dois sitios.
                    body = tk.Text(
                        text_box, wrap='word', width=1, height=1,
                        bg=item_bg, fg=title_fg, relief='flat', bd=0,
                        highlightthickness=0, padx=0, pady=0,
                        spacing1=1, spacing3=2, cursor='arrow',
                        font=_markdown_row_font(),
                    )
                    body.pack(fill='x', pady=(3, 0))
                    stack.append((body, {'fill': 'x', 'pady': (3, 0)}))
                    _markdown_row_tags(
                        body, theme,
                        _tk_color(
                            theme.get('secondary')
                            or theme.get('primary', '#6750A4'), item_bg),
                        subtitle_fg,
                    )
                _badge_font = (('Segoe UI', 8, 'bold') if os.name == 'nt'
                               else ('Helvetica', 8, 'bold'))
                if badge_end:
                    # A conversation row: the time level with the name and
                    # the unread count under it, both at the end.
                    trail = tk.Frame(cell, bg=item_bg)
                    trail.grid(row=0, column=content_column + 1, rowspan=2,
                               sticky='ne', padx=(8, 14), pady=(12, 10))
                    meta = tk.Label(
                        trail, bg=item_bg, fg=meta_fg, anchor='e',
                        font=('Segoe UI', 9) if os.name == 'nt'
                        else ('Helvetica', 9),
                    )
                    meta.pack(anchor='e')
                    badge = _PillBadge(trail, item_bg, badge_bg, badge_fg,
                                       _badge_font, pad_x=5, min_side=20)
                    badge.pack(anchor='e', pady=(6, 0))
                else:
                    badge = _PillBadge(text_box, item_bg, badge_bg, badge_fg,
                                       _badge_font)
                    badge.pack(anchor='w', pady=(4, 0))
                    stack.append((badge, {'anchor': 'w', 'pady': (4, 0)}))
                    meta = tk.Label(
                        cell, bg=item_bg, fg=meta_fg, anchor='e',
                        font=('Segoe UI', 9, 'bold') if os.name == 'nt'
                        else ('Helvetica', 9, 'bold'),
                    )
                    meta.grid(
                        row=0, column=content_column + 1, rowspan=2,
                        padx=(8, 14),
                    )
            else:
                image_size = max(96, extent - 88)
                thumb = None
                if has_image:
                    thumb = tk.Canvas(
                        cell, height=image_size, bg='#1E293B',
                        highlightthickness=0, bd=0,
                    )
                    thumb.pack(fill='x')
                avatar = None
                if has_avatar:
                    avatar = tk.Canvas(
                        cell, width=AVATAR_SIZE, height=AVATAR_SIZE,
                        bg=item_bg, highlightthickness=0, bd=0,
                    )
                    avatar.pack(anchor='w', padx=9, pady=(9, 0))
                title = tk.Label(
                    cell, bg=item_bg, fg=title_fg, anchor='w',
                    font=('Segoe UI', 10, 'bold') if os.name == 'nt'
                    else ('Helvetica', 10, 'bold'),
                )
                title.pack(fill='x', padx=9, pady=(7, 0))
                subtitle = tk.Label(
                    cell, bg=item_bg, fg=subtitle_fg, anchor='w',
                    font=('Segoe UI', 8) if os.name == 'nt'
                    else ('Helvetica', 8),
                )
                subtitle.pack(fill='x', padx=9, pady=(2, 0))
                _wrap_row_text(cell, title, title_lines)
                _wrap_row_text(cell, subtitle, subtitle_lines)
                if has_markdown:
                    body = tk.Text(
                        cell, wrap='word', width=1, height=1,
                        bg=item_bg, fg=title_fg, relief='flat', bd=0,
                        highlightthickness=0, padx=0, pady=0,
                        spacing1=1, spacing3=2, cursor='arrow',
                        font=_markdown_row_font(),
                    )
                    body.pack(fill='x', padx=9, pady=(3, 0))
                    _markdown_row_tags(
                        body, theme,
                        _tk_color(
                            theme.get('secondary')
                            or theme.get('primary', '#6750A4'), item_bg),
                        subtitle_fg,
                    )
                footer = tk.Frame(cell, bg=item_bg)
                footer.pack(fill='x', padx=9, pady=(5, 7))
                badge = _PillBadge(
                    footer, item_bg, badge_bg, badge_fg,
                    ('Segoe UI', 7, 'bold') if os.name == 'nt'
                    else ('Helvetica', 7, 'bold'), pad_x=5,
                )
                badge.pack(side='left')
                meta = tk.Label(
                    footer, bg=item_bg, fg=meta_fg, anchor='e',
                    font=('Segoe UI', 8, 'bold') if os.name == 'nt'
                    else ('Helvetica', 8, 'bold'),
                )
                meta.pack(side='right')

            slot = {
                'frame': cell, 'thumb': thumb, 'title': title,
                'subtitle': subtitle, 'badge': badge, 'meta': meta,
                'body': body, 'avatar': avatar, 'item': None,
                'text_box': text_box, 'stack': stack, 'trail': trail,
                'image_size': image_size, 'backdrop': backdrop,
            }

            def _activate(_event=None, current=slot):
                if on_click and current['item'] is not None:
                    on_click(current['item'])

            if on_click:
                for widget in filter(
                    None, (cell, thumb, title, subtitle, badge, meta, avatar)
                ):
                    widget.bind(click_event, _activate)
            return slot

        if auto_height:
            # Uma linha baixa cabe muitas vezes no ecra; o pool tem de dar
            # para o pior caso, nao para a estimativa. O tecto evita alocar
            # centenas de molduras num viewport alto.
            pool_size = min(28, max(4, viewport_h // 56 + overscan * 2))
        else:
            pool_size = max(
                3, (viewport_h + extent - 1) // extent + overscan * 2
            )
        pool = []

        def _make_pooled():
            row = tk.Frame(
                canvas, bg=collection_bg,
                highlightbackground=divider,
                # A row of components draws what it holds and nothing else,
                # as the phone's inflated row does.
                highlightthickness=0 if (shaped or row_template is not None) else 1, bd=0,
            )
            if not auto_height:
                row.configure(height=extent)
                row.grid_propagate(False)
            row.grid_rowconfigure(0, weight=1)
            for column in range(columns):
                row.grid_columnconfigure(column, weight=1, uniform='virtual_col')
            cells = [_new_cell(row, column) for column in range(columns)]
            window = canvas.create_window(
                0, 0, window=row, anchor='nw', state='hidden'
            )
            pool.append({'window': window, 'row': row, 'cells': cells})
            if auto_height and row_template is not None:
                # A row of components is measured when Tk has laid it out --
                # and again when a picture in it arrives. Measured at bind
                # time it was an empty frame (3px), and the next row was
                # drawn over it.
                row.bind('<Configure>', lambda _e: _queue_measure(), add='+')
            return pool[-1]

        for _index in range(pool_size):
            _make_pooled()

        # ── Row variants ────────────────────────────────────────────────────
        # One collection, more than one shape of row. A conversation is the
        # case that needs it: what you asked and what was answered are not the
        # same kind of thing, and drawing them identically is what made a chat
        # read as a list of paragraphs.
        row_variants = comp.kwargs.get('variants') or {}
        variant_format = comp.kwargs.get('variant')
        variant_colours = {}
        for _name in row_variants:
            _vstyle = _merge_with_body(
                comp_id, 'virtual_collection', row_variant=_name)
            variant_colours[_name] = {
                'bg': _tk_color(
                    _vstyle.get('item-background-color'), item_bg),
                'title': _tk_color(
                    _vstyle.get('title-color') or _get_style_fg(_vstyle),
                    title_fg),
                'subtitle': _tk_color(
                    _vstyle.get('subtitle-color'), subtitle_fg),
                'meta': _tk_color(_vstyle.get('meta-color'), meta_fg),
            }

        def _row_shape(item):
            """The template and the colours this one row is drawn with."""
            if not row_variants:
                return template, None
            name = _format(variant_format, item).strip()
            return (row_variants.get(name, template),
                    variant_colours.get(name))

        def _bind_row(slot, item):
            # Repositioning binds every visible row again. A row that already
            # shows this item is left alone: rebuilt, its containers laid out
            # again inside the measuring pass, which bound the rows again.
            if slot.get('item') is item and slot.get('_row_drawn'):
                return
            slot['item'] = item
            slot['_row_drawn'] = True
            cell = slot['frame']
            for child in cell.winfo_children():
                child.destroy()
            self._render_comp(_row_instance(row_template, item, _format),
                              cell, False, tk.TOP, item_bg)
            # Scrolling over a row, and a tap on it that no button of its own
            # took, reach the collection as they do for a slot row.
            pending = list(cell.winfo_children())
            while pending:
                widget = pending.pop()
                pending.extend(widget.winfo_children())
                try:
                    widget.bind('<MouseWheel>', _wheel, add='+')
                    if on_click and str(widget.cget('cursor')) != 'hand2':
                        widget.bind(click_event, lambda _e, current=slot: (
                            on_click(current['item']) if current['item'] is not None
                            else None), add='+')
                except Exception:
                    pass
            if gestures_on:
                _tag_gesture_tree(cell)

        def _bind(slot, item):
            if slot.get('row_mode'):
                _bind_row(slot, item)
                return
            slot['item'] = item
            template, colours = _row_shape(item)
            if colours is not None:
                slot['frame'].configure(bg=colours['bg'])
                # The Markdown cell paints its own surface, so leaving it out
                # left a darker strip behind the text of a tinted turn.
                for key in ('text_box', 'title', 'subtitle', 'meta', 'body', 'trail'):
                    widget = slot.get(key)
                    if widget is not None:
                        widget.configure(bg=colours['bg'])
                slot['title'].configure(fg=colours['title'])
                slot['subtitle'].configure(fg=colours['subtitle'])
                slot['meta'].configure(fg=colours['meta'])
                if slot.get('avatar') is not None:
                    slot['avatar'].configure(bg=colours['bg'])
            if slot.get('backdrop') is not None:
                slot['frame'].configure(bg=collection_bg)
                slot['backdrop']._apkpy_fill = colours['bg'] if colours else item_bg
                slot['backdrop'].configure(bg=collection_bg)
            slot['title'].configure(
                text=_format(template.get('title', '{title}'), item)
            )
            subtitle = _format(template.get('subtitle', ''), item)
            badge = _format(template.get('badge', ''), item)
            meta = _format(template.get('meta', ''), item)
            slot['subtitle'].configure(text=subtitle)
            _row_bg = colours['bg'] if colours else item_bg
            if isinstance(slot['badge'], _PillBadge):
                slot['badge'].configure(text=badge, bg=badge_bg, surface=_row_bg)
            else:
                slot['badge'].configure(text=badge, bg=badge_bg if badge else _row_bg)
            slot['meta'].configure(text=meta)
            if slot.get('trail') is not None:
                slot['meta'].pack_forget()
                slot['badge'].pack_forget()
                if meta:
                    slot['meta'].pack(anchor='e')
                if badge:
                    slot['badge'].pack(anchor='e', pady=(6 if meta else 0, 0))
            elif mode == 'list':
                slot['meta'].grid() if meta else slot['meta'].grid_remove()
            if shaped:
                name = _format(variant_format, item).strip() if variant_format else ''
                bubble = bubble_table.get(name)
                if bubble:
                    align, widest, percent = bubble
                    slot['frame'].grid_configure(
                        sticky={1: 'ne', 2: 'n'}.get(align, 'nw'))
                    total = max(160, canvas.winfo_width() or 360)
                    limit = (total * widest / 100.0 if percent and widest
                             else (widest or total))
                    meta_width = 0
                    if meta:
                        try:
                            import tkinter.font as _tkfont
                            meta_width = _tkfont.Font(
                                font=slot['meta'].cget('font')).measure(meta) + 22
                        except Exception:
                            meta_width = 8 * len(meta) + 22
                    wrap = max(60, int(limit - 26 - meta_width))
                    for key in ('title', 'subtitle'):
                        slot[key]._apkpy_fixed_wrap = wrap
                        slot[key].configure(wraplength=wrap, justify='left')
                else:
                    slot['frame'].grid_configure(sticky='nsew')
                    for key in ('title', 'subtitle'):
                        slot[key]._apkpy_fixed_wrap = None
                if slot.get('backdrop') is not None:
                    slot['frame'].after_idle(slot['backdrop']._apkpy_paint)
            markdown_source = ''
            if slot['body'] is not None:
                markdown_source = _format(template.get('markdown', ''), item)
                _fill_markdown_cell(
                    slot['body'], markdown_source, row_copy_code)
            # Re-stack from scratch: pack appends, so re-showing a slot that
            # was hidden would otherwise land it after the message instead of
            # above it.
            if slot.get('stack'):
                filled = {
                    id(slot['title']): bool(
                        _format(template.get('title', ''), item)),
                    id(slot['subtitle']): bool(subtitle),
                    id(slot['badge']): bool(badge),
                }
                if slot['body'] is not None:
                    filled[id(slot['body'])] = bool(markdown_source)
                for widget, _options in slot['stack']:
                    widget.pack_forget()
                for widget, options in slot['stack']:
                    if filled.get(id(widget), True):
                        widget.pack(**options)
            if slot['avatar'] is not None:
                drawn = _paint_avatar(
                    slot['avatar'], _format(template.get('avatar', ''), item)
                )
                if mode == 'list':
                    slot['avatar'].grid() if drawn else slot['avatar'].grid_remove()
                    # Removing the avatar collapses its column, so a turn
                    # without one had its text flush against the edge while
                    # the turn above it started 66px in. Nothing lined up.
                    if slot.get('text_box') is not None:
                        slot['text_box'].grid_configure(
                            padx=(0 if drawn else 14, 14))
                elif drawn:
                    if not slot['avatar'].winfo_ismapped():
                        slot['avatar'].pack(anchor='w', padx=9, pady=(9, 0))
                else:
                    slot['avatar'].pack_forget()
            image_src = _format(template.get('image', ''), item)
            if image_src and slot['thumb'] is not None:
                self._load_thumb(slot['thumb'], image_src, slot['image_size'])
            elif slot['thumb'] is not None:
                slot['thumb']._thumb_request = int(
                    getattr(slot['thumb'], '_thumb_request', 0)
                ) + 1
                slot['thumb'].delete('all')
                slot['thumb'].create_rectangle(
                    0, 0, slot['image_size'], slot['image_size'],
                    fill='#1E293B', outline='',
                )

        measure_state = {'queued': False}

        def _queue_measure():
            if measure_state['queued']:
                return
            measure_state['queued'] = True

            def run():
                measure_state['queued'] = False
                if measure_state.get('busy'):
                    return
                measure_state['busy'] = True
                try:
                    _measure_visible()
                except Exception:
                    pass
                finally:
                    measure_state['busy'] = False
            canvas.after_idle(run)

        def _measure_visible():
            """Guarda a altura real das linhas desenhadas.

            E' a diferenca entre estimar e saber: enquanto uma linha nao for
            desenhada a sua altura e' um palpite, e assim que for, deixa de
            ser. Se alguma mudou, as posicoes sao refeitas e o scroll com elas.
            """
            changed = False
            for pooled in pool:
                index = pooled.get('data_row')
                if index is None:
                    continue
                try:
                    height = float(pooled['row'].winfo_reqheight())
                except Exception:
                    continue
                if height <= 1:
                    continue
                if abs(state['heights'].get(index, -1) - height) > 0.5:
                    state['heights'][index] = height
                    changed = True
            if not changed:
                return
            measured = list(state['heights'].values())
            if measured:
                state['estimate'] = sum(measured) / len(measured)
            _invalidate_offsets()
            _reposition()
            _update_region(keep_first=True)

        def _reposition():
            """Volta a por cada linha visivel na sua posicao, sem religar."""
            table = _offsets()
            for pooled in pool:
                index = pooled.get('data_row')
                if index is None or index >= len(table) - 1:
                    continue
                canvas.coords(pooled['window'], 0, table[index])

        def _refresh(force=False):
            # Filling a Markdown cell calls update_idletasks to measure its
            # wrapped height. That flushes Tk's pending geometry work in the
            # middle of this loop, the canvas fires <Configure>, and this
            # function is entered again while the first call is still walking
            # the pool. The rows it had not reached yet kept the 1px width
            # they are born with, so a collection with a markdown slot drew
            # its first row and nothing else.
            if state.get('busy'):
                state['pending'] = True
                return
            rows = _row_count()
            if grows_with_items and len(pool) < rows:
                # Every row is on screen, so every row needs a frame.
                for _extra in range(rows - len(pool)):
                    grown = _make_pooled()
                    grown['row'].bind('<MouseWheel>', _wheel)
                    if gestures_on:
                        _tag_gesture_tree(grown['row'])
            if auto_height:
                first = max(0, _first_visible(canvas.canvasy(0)) - overscan)
            else:
                first = max(0, int(canvas.canvasy(0) // extent) - overscan)
            if not force and first == state['first']:
                return
            state['first'] = first
            width = max(1, canvas.winfo_width())
            table = _offsets() if auto_height else None
            state['busy'] = True
            try:
                for pool_index, pooled in enumerate(pool):
                    data_row = first + pool_index
                    if data_row >= rows:
                        pooled['data_row'] = None
                        canvas.itemconfigure(pooled['window'], state='hidden')
                        continue
                    pooled['data_row'] = data_row
                    canvas.itemconfigure(
                        pooled['window'], state='normal', width=width,
                    )
                    canvas.coords(
                        pooled['window'], 0,
                        table[data_row] if table else data_row * extent,
                    )
                    for column, slot in enumerate(pooled['cells']):
                        item_index = data_row * columns + column
                        if item_index < len(state['items']):
                            slot['frame'].grid()
                            _bind(slot, state['items'][item_index])
                        else:
                            slot['item'] = None
                            slot['frame'].grid_remove()
            finally:
                state['busy'] = False
            # Say the width once more now the nested layout has settled: the
            # canvas may have been remeasured while a cell was being filled.
            width = max(1, canvas.winfo_width())
            for pooled in pool:
                if pooled.get('data_row') is not None:
                    canvas.itemconfigure(pooled['window'], width=width)
            if state.pop('pending', False):
                canvas.after_idle(lambda: _refresh(force=True))
            if auto_height:
                canvas.after_idle(_measure_visible)
            canvas.after_idle(_maybe_request_end)

        def _update_region(keep_first=False):
            rows = _row_count()
            if auto_height:
                if not keep_first:
                    # Os itens mudaram ou a largura mudou; as alturas medidas
                    # eram de outro conteudo ou de outra quebra de linha.
                    state['heights'].clear()
                    _invalidate_offsets()
                content_h = int(_offsets()[-1]) if rows else 0
            else:
                content_h = rows * extent
            if grows_with_items:
                if abs(int(float(canvas.cget('height'))) - content_h) > 1:
                    canvas.configure(height=max(1, content_h))
                canvas.configure(scrollregion=(
                    0, 0, max(1, canvas.winfo_width()), max(1, content_h)))
                if scrollbar.winfo_ismapped():
                    scrollbar.pack_forget()
                if not keep_first:
                    state['first'] = -1
                _refresh(force=True)
                return
            canvas.configure(scrollregion=(
                0, 0, max(1, canvas.winfo_width()),
                max(viewport_h, content_h),
            ))
            # A RecyclerView draws no scrollbar until you drag it, so a thread
            # with one message had a rail down the Previewer that the phone
            # never showed.
            if content_h > max(1, canvas.winfo_height()):
                if not scrollbar.winfo_ismapped():
                    scrollbar.pack(side='right', fill='y')
            elif scrollbar.winfo_ismapped():
                scrollbar.pack_forget()
            if not keep_first:
                state['first'] = -1
            _refresh(force=True)

        def _content_height():
            rows = _row_count()
            if auto_height:
                return float(_offsets()[-1]) if rows else 0.0
            return float(rows * extent)

        def _row_top(row):
            if auto_height:
                table = _offsets()
                return float(table[max(0, min(len(table) - 1, row))])
            return float(row * extent)

        def _settle(row, passes):
            """Com alturas medidas, a posicao de uma linha e' um palpite ate'
            as linhas acima dela terem sido desenhadas. Depois de desenhar,
            a conta refaz-se com os numeros verdadeiros."""
            if passes > 0 and auto_height:
                canvas.after_idle(
                    lambda: _scroll_to_row(row, passes - 1, animate=False)
                )

        def _scroll_to_row(row, passes=2, animate=True):
            total = max(float(viewport_h), _content_height())
            if total <= 1:
                return
            target = min(1.0, max(0.0, _row_top(row) / total))
            ms = _motion.duration('nav', _motion_preset()) if animate else 0
            if ms <= 0 or _app is None:
                canvas.yview_moveto(target)
                _refresh(force=True)
                _settle(row, passes)
                return
            start = canvas.yview()[0]
            steps = max(1, int(round(ms / 16.0)))

            def _tick(step=1):
                progress = min(1.0, float(step) / steps)
                canvas.yview_moveto(
                    start + (target - start) * _motion.ease(progress)
                )
                _refresh()
                if progress < 1.0:
                    _app.root.after(16, lambda: _tick(step + 1))
                else:
                    _settle(row, passes)

            _tick()

        def _scroll(*args):
            canvas.yview(*args)
            canvas.after_idle(_refresh)

        def _wheel(event):
            delta = int(-1 * (event.delta / 120))
            top, bottom = canvas.yview()
            can_scroll_collection = (
                (delta < 0 and top > 0.0001)
                or (delta > 0 and bottom < 0.9999)
            )
            if can_scroll_collection:
                canvas.yview_scroll(delta, 'units')
                canvas.after_idle(_refresh)
            else:
                # Continue through a scrollable Screen when the virtual
                # collection reaches either edge. This avoids trapping the
                # wheel inside the RecyclerView preview and keeps controls
                # below the collection reachable.
                page = getattr(self, '_scroll_canvas', None)
                if page is not None and page is not canvas:
                    page.yview_scroll(delta, 'units')
                    if self._app_bar_scroll_update:
                        self._app_bar_scroll_update(
                            max(0, int(page.canvasy(0)))
                        )
            return 'break'

        scrollbar.configure(command=_scroll)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<MouseWheel>', _wheel)
        for pooled in pool:
            pooled['row'].bind('<MouseWheel>', _wheel)
            for slot in pooled['cells']:
                for widget in filter(None, (
                    slot['frame'], slot['thumb'], slot['title'],
                    slot['subtitle'], slot['badge'], slot['meta'],
                )):
                    widget.bind('<MouseWheel>', _wheel)
        canvas.bind('<Configure>', lambda _event: _update_region())

        status = tk.Label(
            outer, text='', bg=collection_bg, fg=meta_fg,
            font=('Segoe UI', 9, 'bold') if os.name == 'nt'
            else ('Helvetica', 9, 'bold'),
            padx=10, pady=5,
        )

        def _show_status(text, at_top=False):
            status.configure(text=text)
            status.place(
                relx=0.5, x=0, y=8 if at_top else -8,
                rely=0 if at_top else 1,
                anchor='n' if at_top else 's',
            )
            status.lift()

        def _hide_status():
            status.place_forget()

        def _feed_state_changed(feed_state):
            if feed_state.get('loading'):
                if feed_state.get('refreshing'):
                    _show_status('Refreshing...', at_top=True)
                else:
                    _show_status('Loading more...')
            else:
                _hide_status()

        def _feed_update(operation, values):
            if operation == 'append':
                top = max(0.0, canvas.canvasy(0))
                state['items'].extend(list(values or []))
                _update_region()
                total_height = max(
                    viewport_h,
                    ((len(state['items']) + columns - 1) // columns) * extent,
                )
                canvas.yview_moveto(
                    min(1.0, top / max(1.0, float(total_height)))
                )
                _refresh(force=True)
            elif operation == 'prepend':
                top = max(0.0, canvas.canvasy(0))
                inserted = list((values or {}).get('items', []))
                state['items'][0:0] = inserted
                inserted_rows = (
                    len(inserted) + columns - 1
                ) // columns
                _update_region()
                total_height = max(
                    viewport_h,
                    ((len(state['items']) + columns - 1) // columns) * extent,
                )
                canvas.yview_moveto(min(
                    1.0,
                    (top + inserted_rows * extent)
                    / max(1.0, float(total_height)),
                ))
                _refresh(force=True)
            elif operation == 'scroll':
                index = int((values or {}).get('index', 0))
                _scroll_to_row(max(0, index // columns))
            elif operation == 'update':
                payload = values or {}
                index = int(payload.get('index', -1))
                if 0 <= index < len(state['items']):
                    state['items'][index] = payload.get('item')
                    _refresh(force=True)
            elif operation == 'remove':
                top = max(0.0, canvas.canvasy(0))
                index = int((values or {}).get('index', -1))
                if 0 <= index < len(state['items']):
                    state['items'].pop(index)
                    _update_region()
                    total_height = max(
                        viewport_h,
                        ((len(state['items']) + columns - 1) // columns)
                        * extent,
                    )
                    canvas.yview_moveto(min(
                        1.0, top / max(1.0, float(total_height))
                    ))
                    _refresh(force=True)
            elif operation in ('merge', 'rollback'):
                top = max(0.0, canvas.canvasy(0))
                state['items'] = list((values or {}).get('items', []))
                _update_region()
                total_height = max(
                    viewport_h,
                    ((len(state['items']) + columns - 1) // columns) * extent,
                )
                canvas.yview_moveto(
                    min(1.0, top / max(1.0, float(total_height)))
                )
                _refresh(force=True)
            else:
                state['items'] = list(values or [])
                canvas.yview_moveto(0)
                _update_region()
                page = getattr(self, '_scroll_canvas', None)
                if (
                    page is not None
                    and page is not canvas
                    and feeds_feature.state_for(comp).get('refreshing')
                ):
                    page.yview_moveto(0)
                    if self._app_bar_scroll_update:
                        self._app_bar_scroll_update(0)
            canvas.after_idle(_maybe_request_end)

        def _maybe_request_end():
            if not comp.kwargs.get('on_end_reached'):
                return
            total = len(state['items'])
            if total == 0:
                feeds_feature.request_end(comp)
                return
            first_row = max(0, int(canvas.canvasy(0) // extent))
            visible_rows = max(1, (canvas.winfo_height() + extent - 1) // extent)
            last_item = min(
                total - 1,
                (first_row + visible_rows) * columns - 1,
            )
            if last_item >= total - 1 - prefetch:
                feeds_feature.request_end(comp)

        pull = {'start': None, 'distance': 0}

        def _pull_start(event):
            if (comp.kwargs.get('on_refresh')
                    and canvas.yview()[0] <= 0.0001):
                pull['start'] = event.y_root
                pull['distance'] = 0

        def _pull_move(event):
            if pull['start'] is None:
                return
            pull['distance'] = max(0, event.y_root - pull['start'])
            if pull['distance'] > 8:
                _show_status(
                    'Release to refresh'
                    if pull['distance'] >= 54 else 'Pull to refresh',
                    at_top=True,
                )

        def _pull_end(_event):
            should_refresh = pull['start'] is not None and pull['distance'] >= 54
            pull['start'] = None
            pull['distance'] = 0
            if should_refresh:
                if not feeds_feature.request_refresh(comp):
                    _feed_state_changed(feeds_feature.state_for(comp))
            else:
                _feed_state_changed(feeds_feature.state_for(comp))

        def _bind_pull(widget):
            widget.bind('<ButtonPress-1>', _pull_start, add='+')
            widget.bind('<B1-Motion>', _pull_move, add='+')
            widget.bind('<ButtonRelease-1>', _pull_end, add='+')

        _bind_pull(canvas)
        for pooled in pool:
            _bind_pull(pooled['row'])
            for slot in pooled['cells']:
                for widget in filter(None, (
                    slot['frame'], slot['thumb'], slot['title'],
                    slot['subtitle'], slot['badge'], slot['meta'],
                )):
                    _bind_pull(widget)

        if gestures_on:
            self._install_row_gestures(
                comp, canvas, pool, state, swipe_right, swipe_left, can_reorder,
                gesture_tag, collection_bg, theme)
            for pooled in pool:
                _tag_gesture_tree(pooled['row'])

        feeds_feature.bind_preview(
            comp, _feed_update, _feed_state_changed
        )
        comp._list_update_fn = lambda new_items: _feed_update(
            'replace', new_items
        )
        _update_region()
        canvas.after_idle(_maybe_request_end)

    def _install_row_gestures(self, comp, canvas, pool, state, swipe_right,
                              swipe_left, can_reorder, tag, collection_bg, theme):
        """Swipe a row away, lift it with a long press and drop it elsewhere.

        The phone does this with ItemTouchHelper, from the same numbers
        (``gesture_rules``). A right-click opens the actions a screen reader
        offers on the phone -- every swipe, and Move up / Move down -- so the
        desktop can reach them without the gesture too.
        """
        from . import gesture_rules as rules
        tokens = dict(theme or {})
        family = 'Segoe UI' if os.name == 'nt' else 'Helvetica'
        strip = tag + 'Strip'
        gesture = {'pooled': None, 'index': None, 'x': 0, 'y': 0,
                   'mode': None, 'dx': 0.0, 'timer': None, 'origin': 0.0,
                   'outline': None}

        def _pooled_for(widget):
            rows = {str(pooled['row']): pooled for pooled in pool}
            current = widget
            while current is not None:
                found = rows.get(str(current))
                if found is not None:
                    return found
                current = getattr(current, 'master', None)
            return None

        def _cancel_timer():
            if gesture['timer'] is not None:
                try:
                    canvas.after_cancel(gesture['timer'])
                except tk.TclError:
                    pass
                gesture['timer'] = None

        def _draw_strip(pooled, dx):
            canvas.delete(strip)
            action = swipe_right if dx > 0 else swipe_left
            if action is None or not dx:
                return
            top = canvas.coords(pooled['window'])[1]
            height = max(1, pooled['row'].winfo_height())
            width = max(1, canvas.winfo_width())
            color = _tk_color(
                rules.swipe_color(action['icon'], action.get('color'), tokens),
                rules.FALLBACK_COLOR)
            if dx > 0:
                canvas.create_rectangle(0, top, dx, top + height, fill=color,
                                        outline='', tags=strip)
                icon_x = rules.EDGE_PADDING + rules.ICON_SIZE / 2.0
                text_x, anchor = icon_x + rules.ICON_SIZE / 2.0 + rules.LABEL_GAP, 'w'
            else:
                canvas.create_rectangle(width + dx, top, width, top + height,
                                        fill=color, outline='', tags=strip)
                icon_x = width - rules.EDGE_PADDING - rules.ICON_SIZE / 2.0
                text_x, anchor = icon_x - rules.ICON_SIZE / 2.0 - rules.LABEL_GAP, 'e'
            middle = top + height / 2.0
            _draw_material_icon(canvas, action['icon'], icon_x, middle,
                                rules.FOREGROUND, size=rules.ICON_SIZE, tags=strip)
            if action.get('text'):
                canvas.create_text(text_x, middle, text=action['text'], anchor=anchor,
                                   fill=rules.FOREGROUND, tags=strip,
                                   font=(family, 11, 'bold'))

        def _slide(pooled, start, end, done):
            top = canvas.coords(pooled['window'])[1]
            steps = max(1, rules.SLIDE_MS // 16)

            def _tick(step=1):
                progress = min(1.0, step / float(steps))
                dx = start + (end - start) * _motion.ease(progress)
                canvas.coords(pooled['window'], dx, top)
                _draw_strip(pooled, dx)
                if progress < 1.0:
                    canvas.after(16, lambda: _tick(step + 1))
                else:
                    done()
            _tick()

        def _lift():
            gesture['timer'] = None
            pooled = gesture['pooled']
            if pooled is None or gesture['mode'] is not None:
                return
            gesture['mode'] = 'drag'
            gesture['origin'] = canvas.coords(pooled['window'])[1]
            row = pooled['row']
            gesture['outline'] = (row.cget('highlightthickness'),
                                  row.cget('highlightbackground'))
            row.configure(highlightthickness=2, highlightbackground=_tk_color(
                tokens.get('primary'), rules.FALLBACK_COLOR))
            row.lift()

        def _settle_row(pooled):
            if gesture['outline'] is not None:
                pooled['row'].configure(highlightthickness=gesture['outline'][0],
                                        highlightbackground=gesture['outline'][1])
                gesture['outline'] = None

        def _index_at(y, dragged):
            spans = []
            for pooled in pool:
                index = pooled.get('data_row')
                if index is None:
                    continue
                top = (gesture['origin'] if pooled is dragged
                       else canvas.coords(pooled['window'])[1])
                spans.append((top, top + max(1, pooled['row'].winfo_height()), index))
            if not spans:
                return gesture['index']
            spans.sort()
            for top, bottom, index in spans:
                if y < bottom:
                    return index
            return spans[-1][2]

        def _finish_swipe(index, direction):
            canvas.delete(strip)
            action = swipe_right if direction == 'right' else swipe_left
            if action is None or not 0 <= index < len(state['items']):
                return
            callback = action.get('on_swipe')
            if action.get('keep'):
                item = state['items'][index]
                for pooled in pool:
                    if pooled.get('data_row') == index:
                        canvas.coords(pooled['window'], 0,
                                      canvas.coords(pooled['window'])[1])
                if callback:
                    callback(item)
                return
            item = feeds_feature.remove_at(comp, index)
            if item is None:
                return
            if action.get('undo'):
                undone = {'done': False}

                def _undo():
                    undone['done'] = True
                    feeds_feature.insert_at(comp, index, item)

                def _commit():
                    if not undone['done'] and callback:
                        callback(item)

                _show_snackbar_preview(action['undo'], action=rules.UNDO,
                                       on_action=_undo, duration=rules.UNDO_MS)
                canvas.after(rules.UNDO_MS + 100, _commit)
            elif callback:
                callback(item)

        def _move(from_index, to_index):
            count = len(state['items'])
            if not (0 <= from_index < count and 0 <= to_index < count) \
                    or from_index == to_index:
                return False
            item = feeds_feature.move_row(comp, from_index, to_index)
            on_reorder = comp.kwargs.get('on_reorder')
            if item is not None and on_reorder:
                on_reorder(item, to_index)
            return True

        def _perform(kind, index):
            """One of the row's actions, the way TalkBack runs it: no gesture."""
            if kind in ('right', 'left'):
                _finish_swipe(index, kind)
            elif kind == 'up':
                _move(index, index - 1)
            elif kind == 'down':
                _move(index, index + 1)

        def _actions(index):
            return rules.accessibility_actions(
                right=swipe_right, left=swipe_left, reorder_enabled=can_reorder,
                index=index, count=len(state['items']))

        def _press(event):
            _cancel_timer()
            pooled = _pooled_for(event.widget)
            if pooled is None or pooled.get('data_row') is None:
                gesture['pooled'] = None
                return
            gesture.update(pooled=pooled, index=pooled['data_row'],
                           x=event.x_root, y=event.y_root, mode=None, dx=0.0)
            if can_reorder:
                gesture['timer'] = canvas.after(rules.LONG_PRESS_MS, _lift)

        def _drag(event):
            pooled = gesture['pooled']
            if pooled is None:
                return None
            dx = event.x_root - gesture['x']
            dy = event.y_root - gesture['y']
            if gesture['mode'] is None:
                if abs(dx) > rules.SLOP or abs(dy) > rules.SLOP:
                    _cancel_timer()     # it moved before it was held: no lift
                allowed = (dx > 0 and swipe_right) or (dx < 0 and swipe_left)
                if not (rules.is_sideways(dx, dy) and allowed):
                    return None
                gesture['mode'] = 'swipe'
            if gesture['mode'] == 'swipe':
                if (dx > 0 and not swipe_right) or (dx < 0 and not swipe_left):
                    dx = 0
                gesture['dx'] = dx
                canvas.coords(pooled['window'], dx, canvas.coords(pooled['window'])[1])
                _draw_strip(pooled, dx)
                return 'break'
            canvas.coords(pooled['window'], 0, gesture['origin'] + dy)
            return 'break'

        def _release(event):
            _cancel_timer()
            pooled, mode = gesture['pooled'], gesture['mode']
            gesture.update(pooled=None, mode=None)
            if pooled is None or mode is None:
                return None             # a tap: the row's own click runs
            if mode == 'swipe':
                dx, index = gesture['dx'], gesture['index']
                width = max(1, canvas.winfo_width())
                if dx and rules.commits(dx, width):
                    direction = 'right' if dx > 0 else 'left'
                    action = swipe_right if dx > 0 else swipe_left
                    # A row that stays slides back before its action runs,
                    # as ApkpyGestures does on the phone.
                    end = 0 if action.get('keep') else (width if dx > 0 else -width)
                    _slide(pooled, dx, end,
                           lambda: _finish_swipe(index, direction))
                else:
                    _slide(pooled, dx, 0, lambda: canvas.delete(strip))
                return 'break'
            y = canvas.canvasy(event.y_root - canvas.winfo_rooty())
            target = _index_at(y, pooled)
            _settle_row(pooled)
            if not _move(gesture['index'], target):
                canvas.coords(pooled['window'], 0, gesture['origin'])
            return 'break'

        def _menu(event):
            pooled = _pooled_for(event.widget)
            if pooled is None or pooled.get('data_row') is None:
                return None
            index = pooled['data_row']
            menu = tk.Menu(canvas, tearoff=0)
            for kind, text, enabled in _actions(index):
                menu.add_command(label=text,
                                 state='normal' if enabled else 'disabled',
                                 command=lambda k=kind, i=index: _perform(k, i))
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return 'break'

        canvas.bind_class(tag, '<ButtonPress-1>', _press)
        canvas.bind_class(tag, '<B1-Motion>', _drag)
        canvas.bind_class(tag, '<ButtonRelease-1>', _release)
        canvas.bind_class(tag, '<Button-3>', _menu)
        # What the tests (and anything else without a mouse) reach.
        comp._row_actions = _actions
        comp._row_perform = _perform

    def add_label(self, text, fg=None, font=None):
        lbl = tk.Label(
            self.layout, text=text,
            font=font if font else ("Segoe UI" if os.name == 'nt' else "Helvetica", 14),
            fg=fg if fg else "#212121", bg="#ffffff", anchor="w", padx=16
        )
        lbl.pack(pady=(4, 2), fill="x")

    def _render_carousel(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Carrossel HORIZONTAL: prateleira de cartões (capa + título + subtítulo)
        que desliza para o lado (roda do rato). Paridade com o HorizontalScrollView
        gerado no Android."""
        comp_id  = comp.kwargs.get('comp_id')
        style    = _merge_with_body(comp_id, 'carousel')
        on_click = comp.kwargs.get('on_click')
        items    = comp.kwargs.get('items', []) or []
        bg       = _get_style_bg(style) or bg_color
        fg, sub_fg = (_tk_color(c, '#FFFFFF') for c in _card_text_colors(component_style(
            global_styles, 'carousel', comp_id, include_body=False,
            viewport=_style_viewport)))
        CARD = 140
        title_font = ('Segoe UI', 11, 'bold') if os.name == 'nt' else ('Helvetica', 11, 'bold')
        sub_font   = ('Segoe UI', 9) if os.name == 'nt' else ('Helvetica', 9)

        outer = tk.Frame(parent_widget, bg=bg_color)
        outer.pack(fill='x', padx=8, pady=4)
        canvas = tk.Canvas(outer, bg=bg_color, highlightthickness=0, height=CARD + 56)
        canvas.pack(fill='x')
        inner = tk.Frame(canvas, bg=bg_color)
        canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        def _on_hscroll(e):
            canvas.xview_scroll(int(-1 * (e.delta / 120)), 'units')
            return "break"   # roda sobre o carrossel → desliza o carrossel, não o ecrã
        canvas.bind('<MouseWheel>', _on_hscroll)
        inner.bind('<MouseWheel>', _on_hscroll)

        for item in items:
            if isinstance(item, dict):
                title     = item.get('title', '')
                subtitle  = item.get('subtitle', '')
                image_url = item.get('image', '')
            else:
                title, subtitle, image_url = str(item), '', ''

            card = tk.Frame(inner, bg=bg_color, cursor='hand2' if on_click else '')
            card.pack(side='left', padx=8)
            cover = tk.Canvas(card, width=CARD, height=CARD, bg='#1E293B', highlightthickness=0)
            cover.pack()
            if image_url:
                self._load_thumb(cover, image_url, CARD)
            t = tk.Label(card, text=title, bg=bg_color, fg=fg, font=title_font,
                         anchor='w', wraplength=CARD, justify='left')
            t.pack(fill='x', pady=(6, 0))
            widgets = [card, cover, t]
            if subtitle:
                s = tk.Label(card, text=subtitle, bg=bg_color, fg=sub_fg, font=sub_font,
                             anchor='w', wraplength=CARD, justify='left')
                s.pack(fill='x')
                widgets.append(s)

            for w in widgets:
                w.bind('<MouseWheel>', _on_hscroll)
            if on_click:
                def _make(d=item):
                    return lambda e: on_click(d)
                fn = _make()
                for w in widgets:
                    w.bind('<Button-1>', fn)

        comp.widget = canvas

    def _render_grid(self, comp, parent_widget, is_flex, pack_side, bg_color):
        """Grelha de cartões (capa + título + subtítulo) em N colunas — paridade com
        o GridLayout gerado no Android (estilo página "Pesquisar" do Spotify)."""
        comp_id  = comp.kwargs.get('comp_id')
        style    = _merge_with_body(comp_id, 'grid')
        on_click = comp.kwargs.get('on_click')
        items    = comp.kwargs.get('items', []) or []
        try:
            cols = max(1, int(comp.kwargs.get('cols', 2) or 2))
        except (ValueError, TypeError):
            cols = 2
        bg = _get_style_bg(style) or bg_color
        fg, sub_fg = (_tk_color(c, '#FFFFFF') for c in _card_text_colors(component_style(
            global_styles, 'grid', comp_id, include_body=False,
            viewport=_style_viewport)))
        COVER = 150
        COVER_HEIGHT = 110
        title_font = ('Segoe UI', 11, 'bold') if os.name == 'nt' else ('Helvetica', 11, 'bold')
        sub_font   = ('Segoe UI', 9) if os.name == 'nt' else ('Helvetica', 9)

        outer = tk.Frame(parent_widget, bg=bg_color)
        outer.pack(fill='x', padx=10, pady=4)
        for c in range(cols):
            outer.grid_columnconfigure(c, weight=1, uniform='apkpy_gridcol')

        for idx, item in enumerate(items):
            if isinstance(item, dict):
                title     = item.get('title', '')
                subtitle  = item.get('subtitle', '')
                image_url = item.get('image', '')
            else:
                title, subtitle, image_url = str(item), '', ''

            r, c = idx // cols, idx % cols
            card = tk.Frame(outer, bg=bg_color, cursor='hand2' if on_click else '')
            card.grid(row=r, column=c, sticky='nsew', padx=6, pady=6)
            # The phone's cover is the card's width and 110dp tall, cropped
            # in the middle; a 150px square here left the covers narrower,
            # taller and indented beside the phone's.
            cover = tk.Canvas(card, width=COVER, height=COVER_HEIGHT, bg='#1E293B',
                              highlightthickness=0)
            cover.pack(fill='x')
            if image_url:
                def _fit_cover(event, canvas=cover, source=image_url):
                    if event.width > 1 and event.width != getattr(canvas, '_cover_width', None):
                        canvas._cover_width = event.width
                        self._load_thumb(canvas, source, event.width, COVER_HEIGHT)
                cover.bind('<Configure>', _fit_cover)
                self._load_thumb(cover, image_url, COVER, COVER_HEIGHT)
            t = tk.Label(card, text=title, bg=bg_color, fg=fg, font=title_font,
                         anchor='w', wraplength=COVER, justify='left')
            t.pack(fill='x', pady=(6, 0))
            widgets = [card, cover, t]
            if subtitle:
                s = tk.Label(card, text=subtitle, bg=bg_color, fg=sub_fg, font=sub_font,
                             anchor='w', wraplength=COVER, justify='left')
                s.pack(fill='x')
                widgets.append(s)
            if on_click:
                def _make(d=item):
                    return lambda e: on_click(d)
                fn = _make()
                for w in widgets:
                    w.bind('<Button-1>', fn)

        comp.widget = outer

    def add_button(self, text, command=None, bg=None, fg=None, radius=0,
                   border_color=None, border_width=0, pressed_color=None, font=None,
                   compact=False, icon=None):
        self._draw_material_button(text, bg, fg, radius, command, None,
                                   border_color=border_color,
                                   border_width=border_width,
                                   pressed_color=pressed_color,
                                   font=font, compact=compact, icon=icon)

    def add_input(self, placeholder="", input_type="text", bg=None, fg=None,
                  radius=0, border_color=None, border_width=0, focus_border_color=None,
                  margin=(0, 0, 0, 0), padding=None, font=None, accent_color=None,
                  parent=None, bg_color=None, comp=None,
                  placeholder_color=None):
        """Input com visual Material Design: linha cinza em baixo, verde ao focar."""
        ph_color = _tk_color(placeholder_color, "#9e9e9e")
        if comp is not None:
            # Resolved once here so set_value() can restore the hint later,
            # the same way _input_text_color already works.
            comp._input_placeholder_color = ph_color
        mt, mr, mb, ml = margin
        pad_t, pad_r, pad_b, pad_l = padding or (12, 12, 12, 12)
        parent = parent if parent is not None else self.layout
        # The phone gives a field a shape drawable once it has a background
        # or a border (see _assign_drawables), and a shape has no underline:
        # the Material line is the framework's default background, which the
        # drawable replaces. Only a field with neither keeps it.
        shaped = bool(str(bg or '').strip()) or bool(border_color and border_width)
        bg_frame = bg_color if bg_color is not None else (self._bg if hasattr(self, '_flex_bg') else "#ffffff")
        # A borderless field over a styled container is the idiom every chat
        # composer uses, and `background-color: #00000000` is how you write it.
        # Tk has no alpha, so a transparent field is the container behind it;
        # left raw it reached Tcl, which rejects it and took the app down.
        bg = _tk_color(bg, bg_frame) if _is_transparent(bg) else _tk_color(bg)
        # `border-width: 0px` is how you ask for a borderless field, and the
        # Android side already honours it -- _generate_drawable_xml emits no
        # <stroke>. The Previewer forced a 1px line back on, so a composer-style
        # input had a box around it on the desktop and none on the phone.
        border_width = max(0, int(border_width or 0))
        # Focus thickens the line; a borderless field has no line to thicken,
        # so it must not grow one -- Android's drawable has no <stroke> either.
        focus_width = max(2, border_width) if border_width else 0
        fg = _tk_color(fg)
        border_color = _tk_color(border_color)
        focus_border_color = _tk_color(focus_border_color)

        # ── TEXT / PASSWORD / SEARCH / NUMBER ────────────────────────────────
        if input_type in ("text", "password", "search", "number"):
            # Help and error text sit under the field, in the same frame.
            field = _field_feature.of(comp)
            if field is not None:
                outer = field.shell(parent, bg_frame, (ml, mr), (mt, mb))
            else:
                outer = tk.Frame(parent, bg=bg_frame)
                outer.pack(padx=(ml, mr), pady=(mt, mb), fill="x")

            show_char   = "*" if input_type == "password" else ""
            text_color  = fg if fg else "#212121"
            if comp is not None:
                # Preserve the fully resolved cascade for set_value().
                comp._input_text_color = text_color
            idle_line   = border_color if border_color else "#bdbdbd"
            focus_line  = focus_border_color if focus_border_color else idle_line
            input_font  = font if font else ("Segoe UI" if os.name == 'nt' else "Helvetica", 13)
            box_bg      = bg if bg else "#ffffff"
            try:
                import tkinter.font as _tkfont
                line_height = _tkfont.Font(
                    root=self.root, font=input_font,
                ).metrics('linespace')
            except Exception:
                line_height = 18
            input_height = _material_input_height(
                line_height, (pad_t, pad_r, pad_b, pad_l),
            )

            if radius > 0 or border_width > 0:
                canvas = tk.Canvas(
                    outer, height=input_height, bg=bg_frame,
                    highlightthickness=0,
                )
                canvas.pack(fill="x", expand=True)
                
                entry = tk.Entry(
                    canvas, font=input_font, show="",
                    bg=box_bg, fg=ph_color, relief="flat", bd=0,
                    highlightthickness=0, insertbackground=text_color
                )
                entry_x = max(8, pad_l)
                entry_y = input_height / 2
                entry_win = canvas.create_window(
                    entry_x, entry_y, window=entry, anchor="w",
                )
                
                outline_w = border_width
                
                def _redraw(event=None, outline_c=idle_line, lw=outline_w):
                    if field is not None:
                        outline_c, lw = field.line(outline_c), field.stroke(lw)
                    canvas.delete("bg_shape")
                    w = canvas.winfo_width() or (event.width if event else 320)
                    h = canvas.winfo_height() or input_height
                    if radius > 0:
                        _create_rounded_rect(canvas, 1, 1, w-1, h-1, radius, fill=box_bg, outline=outline_c, width=lw, tags="bg_shape")
                    else:
                        canvas.create_rectangle(1, 1, w-1, h-1, fill=box_bg, outline=outline_c, width=lw, tags="bg_shape")
                    canvas.tag_lower("bg_shape")
                    
                    canvas.itemconfig(
                        entry_win,
                        width=max(1, w - entry_x - pad_r),
                    )

                canvas.bind("<Configure>", lambda e: _redraw(e))
                
                def on_focus_in(e):
                    _redraw(outline_c=focus_line, lw=focus_width)
                    if entry.get() == placeholder:
                        entry.delete(0, tk.END)
                        entry.config(fg=text_color)
                    # A password hides what is typed, not its hint: the
                    # phone shows "Password", and this showed ********.
                    entry.config(show=show_char)
                
                def on_focus_out(e):
                    _redraw(outline_c=idle_line, lw=outline_w)
                    if entry.get() == "":
                        entry.config(show="")
                        entry.insert(0, placeholder)
                        entry.config(fg=ph_color)

                entry.bind("<FocusIn>",  on_focus_in)
                entry.bind("<FocusOut>", on_focus_out)
                
                entry.insert(0, placeholder)
                # Vincular ao ComponentDef para get_value/set_value
                if comp is not None:
                    comp.widget = entry

                def _field_repaint():
                    focused = _widget_has_focus(entry)
                    _redraw(outline_c=focus_line if focused else idle_line,
                            lw=focus_width if focused else outline_w)
                _field_pads = (entry_x, pad_r)
            else:
                entry = tk.Entry(
                    outer, font=input_font, show="",
                    bg=box_bg, fg=ph_color, relief="flat", bd=0,
                    highlightthickness=0, insertbackground=text_color
                )
                entry.pack(
                    fill="x", ipady=max(
                        5, (input_height - line_height) // 2,
                    ),
                    padx=(pad_l, pad_r),
                )

                line = tk.Frame(outer, bg=idle_line, height=1)
                if not shaped:
                    line.pack(fill="x")

                def _paint(focused, ln=line, box=outer):
                    """The underline, or the stroke all round that the
                    drawable draws; in the error colour while there is one."""
                    idle, focus = idle_line, focus_line
                    width = border_width if (border_width and border_color) else 0
                    if field is not None:
                        idle, focus = field.line(idle), field.line(focus)
                        width = field.stroke(width)
                    if not shaped:
                        ln.config(bg=focus if focused else idle,
                                  height=2 if focused else 1)
                    else:
                        box.configure(highlightthickness=width,
                                      highlightbackground=idle,
                                      highlightcolor=focus)
                _paint(False)

                entry.insert(0, placeholder)
                # Vincular ao ComponentDef para get_value/set_value
                if comp is not None:
                    comp.widget = entry

                def on_focus_in(e, ent=entry, ph=placeholder):
                    _paint(True)
                    if ent.get() == ph:
                        ent.delete(0, tk.END)
                        ent.config(fg=text_color)
                    ent.config(show=show_char)

                def on_focus_out(e, ent=entry, ph=placeholder):
                    _paint(False)
                    if ent.get() == "":
                        ent.config(show="")
                        ent.insert(0, ph)
                        ent.config(fg=ph_color)

                def _field_repaint():
                    _paint(_widget_has_focus(entry))
                _field_pads = (pad_l, pad_r)

                entry.bind("<FocusIn>",  on_focus_in)
                entry.bind("<FocusOut>", on_focus_out)

            if input_type == "number":
                def _validate_num(new_val):
                    if new_val in ("", "-"):
                        return True
                    try:
                        float(new_val)
                        return True
                    except ValueError:
                        return False
                vcmd = (entry.register(_validate_num), "%P")
                entry.config(validate="key", validatecommand=vcmd)

            # on_change: chama o callback a cada tecla (pesquisa em tempo real).
            on_change = comp.kwargs.get('on_change') if comp is not None else None
            if on_change:
                def _on_key(e, ent=entry, ph=placeholder, cb=on_change):
                    txt = ent.get()
                    if txt == ph:        # placeholder ≠ texto real
                        txt = ""
                    try:
                        cb(txt)
                    except Exception:
                        pass
                entry.bind("<KeyRelease>", _on_key)

            if field is not None:
                field.finish(entry, _field_pads, _field_repaint)

        # ── DATE / TIME picker ───────────────────────────────────────────────
        elif input_type in ("date", "time"):
            import datetime as _dt
            fmt_hint  = "DD/MM/AAAA" if input_type == "date" else "HH:MM"
            icon_char = "📅" if input_type == "date" else "🕐"

            outer = tk.Frame(parent, bg=bg_frame)
            outer.pack(padx=(16 + ml, 16 + mr), pady=(4 + mt, 4 + mb), fill="x")

            text_color = fg if fg else "#212121"
            if comp is not None:
                comp._input_text_color = text_color
            idle_line  = border_color if border_color else "#bdbdbd"
            focus_line = focus_border_color if focus_border_color else idle_line
            box_bg     = bg if bg else "#ffffff"
            input_font = font if font else ("Segoe UI" if os.name == 'nt' else "Helvetica", 13)
            outline_w  = border_width

            var = tk.StringVar(value="")  # empty = nada selecionado

            canvas = tk.Canvas(outer, height=44, bg=bg_frame, highlightthickness=0)
            canvas.pack(fill="x", expand=True)

            def _redraw_dt(outline_c=idle_line, lw=outline_w, c=canvas, r=radius, bbg=box_bg):
                c.delete("bg_shape")
                w = c.winfo_width() or 320
                h = c.winfo_height() or 44
                if r > 0:
                    _create_rounded_rect(c, 1, 1, w-1, h-1, r, fill=bbg, outline=outline_c, width=lw, tags="bg_shape")
                else:
                    c.create_rectangle(1, 1, w-1, h-1, fill=bbg, outline=outline_c, width=lw, tags="bg_shape")
                c.tag_lower("bg_shape")

            init_text  = placeholder if placeholder else fmt_hint
            init_color = ph_color

            lbl = tk.Label(canvas, text=init_text, font=input_font, bg=box_bg,
                           fg=init_color, anchor="w", cursor="hand2")
            lbl_win  = canvas.create_window(14, 22, window=lbl, anchor="w")
            icon_lbl = tk.Label(canvas, text=icon_char, font=("Segoe UI", 14), bg=box_bg,
                                fg=ph_color, cursor="hand2")
            icon_win = canvas.create_window(300, 22, window=icon_lbl, anchor="e")

            def _on_resize(e, _c=canvas, _lw=lbl_win, _iw=icon_win):
                _redraw_dt()
                _c.itemconfig(_lw, width=e.width - 52)
                _c.coords(_iw, e.width - 14, 22)

            canvas.bind("<Configure>", _on_resize)

            def open_picker(event=None, _var=var, _lbl=lbl, _tc=text_color, _ph=placeholder, _itype=input_type):
                current = _var.get()
                top = tk.Toplevel(canvas)
                top.title("Select Date" if _itype == "date" else "Select Time")
                top.resizable(False, False)
                top.grab_set()

                if _itype == "date":
                    today = _dt.date.today()
                    try:
                        p = current.split("/")
                        cur_d, cur_m, cur_y = int(p[0]), int(p[1]), int(p[2])
                    except Exception:
                        cur_d, cur_m, cur_y = today.day, today.month, today.year

                    tk.Label(top, text="Day").grid(row=0, column=0, padx=12, pady=(12, 2))
                    tk.Label(top, text="Month").grid(row=0, column=1, padx=12, pady=(12, 2))
                    tk.Label(top, text="Year").grid(row=0, column=2, padx=12, pady=(12, 2))
                    d_var  = tk.IntVar(value=cur_d)
                    m_var  = tk.IntVar(value=cur_m)
                    y_var  = tk.IntVar(value=cur_y)
                    tk.Spinbox(top, from_=1,    to=31,   textvariable=d_var, width=4).grid(row=1, column=0, padx=12, pady=(0, 4))
                    tk.Spinbox(top, from_=1,    to=12,   textvariable=m_var, width=4).grid(row=1, column=1, padx=12, pady=(0, 4))
                    tk.Spinbox(top, from_=1900, to=2100, textvariable=y_var, width=6).grid(row=1, column=2, padx=12, pady=(0, 4))
                    ncols = 3

                    def on_ok():
                        val = f"{d_var.get():02d}/{m_var.get():02d}/{y_var.get():04d}"
                        _var.set(val)
                        _lbl.config(text=val, fg=_tc)
                        top.destroy()
                else:
                    now = _dt.datetime.now()
                    try:
                        p = current.split(":")
                        cur_h, cur_mi = int(p[0]), int(p[1])
                    except Exception:
                        cur_h, cur_mi = now.hour, now.minute

                    tk.Label(top, text="Hour").grid(row=0, column=0, padx=12, pady=(12, 2))
                    tk.Label(top, text="Minute").grid(row=0, column=1, padx=12, pady=(12, 2))
                    h_var  = tk.IntVar(value=cur_h)
                    mi_var = tk.IntVar(value=cur_mi)
                    tk.Spinbox(top, from_=0, to=23, textvariable=h_var,  width=4).grid(row=1, column=0, padx=12, pady=(0, 4))
                    tk.Spinbox(top, from_=0, to=59, textvariable=mi_var, width=4).grid(row=1, column=1, padx=12, pady=(0, 4))
                    ncols = 2

                    def on_ok():
                        val = f"{h_var.get():02d}:{mi_var.get():02d}"
                        _var.set(val)
                        _lbl.config(text=val, fg=_tc)
                        top.destroy()

                btn_frame = tk.Frame(top)
                btn_frame.grid(row=2, column=0, columnspan=ncols, pady=(4, 12))
                tk.Button(btn_frame, text="Cancel", command=top.destroy).pack(side="left", padx=6)
                tk.Button(btn_frame, text="OK", command=on_ok, width=6).pack(side="right", padx=6)
                top.update_idletasks()
                top.geometry(f"+{canvas.winfo_rootx() + 10}+{canvas.winfo_rooty() + 50}")

            lbl.bind("<Button-1>",      open_picker)
            icon_lbl.bind("<Button-1>", open_picker)
            canvas.bind("<Button-1>",   open_picker, add="+")

            if comp is not None:
                comp._date_var       = var
                comp._date_lbl       = lbl
                comp._date_tc        = text_color
                comp._date_ph        = placeholder if placeholder else fmt_hint

        # ── TEXTAREA ──────────────────────────────────────────────────────────
        elif input_type == "textarea":
            # Textareas share the same outer box model as text, number and
            # search inputs.  The previous extra 16 px on both sides made only
            # this field visibly narrower in the desktop Previewer.
            field = _field_feature.of(comp)
            if field is not None:
                outer = field.shell(parent, bg_frame, (ml, mr), (mt, mb))
            else:
                outer = tk.Frame(parent, bg=bg_frame)
                outer.pack(padx=(ml, mr), pady=(mt, mb), fill="x")

            text_color = fg if fg else "#212121"
            idle_line  = border_color if border_color else "#bdbdbd"
            focus_line = focus_border_color if focus_border_color else idle_line
            input_font = font if font else ("Segoe UI" if os.name == 'nt' else "Helvetica", 13)
            box_bg     = bg if bg else "#ffffff"

            # Determine number of visible rows from CSS style (default 4)
            rows = 4
            if comp is not None:
                _ta_style = _merge_with_body(comp.kwargs.get('comp_id'), 'inputs')
                raw_rows = str(_ta_style.get('rows', '')).strip()
                if raw_rows.isdigit():
                    rows = int(raw_rows)

            # `rows` e' o minimo e `max-rows` o tecto, os mesmos numeros que
            # o EditText recebe. O Android ja' crescia com o texto e o
            # Previewer nao: escrevias seis linhas no telemovel e viam-se, e
            # no ambiente de trabalho ficavam quatro com uma barra de scroll.
            max_rows = max(rows * 2, 8)
            if comp is not None:
                raw_max_rows = str(_ta_style.get('max-rows', '')).strip()
                if raw_max_rows.isdigit():
                    max_rows = max(rows, int(raw_max_rows))

            def _grow_textarea(widget, after=None, low=rows, high=max_rows):
                """Da' ao campo a altura do que la' esta', entre os limites."""
                try:
                    shown = widget.count('1.0', 'end', 'displaylines')
                except Exception:
                    return
                used = shown[0] if isinstance(shown, (tuple, list)) else shown
                wanted = max(low, min(high, int(used or 1)))
                if int(widget.cget('height')) != wanted:
                    widget.configure(height=wanted)
                    if after is not None:
                        widget.after_idle(after)

            def _watch_textarea(widget, after=None):
                """Cresce a cada mudanca, venha ela do teclado ou de set_value."""
                def _changed(_event=None, w=widget):
                    if not w.edit_modified():
                        return
                    w.edit_modified(False)
                    _grow_textarea(w, after)

                widget.bind('<<Modified>>', _changed, add='+')
                widget.after_idle(lambda: _grow_textarea(widget, after))

            if radius > 0 or border_width > 0:
                canvas = tk.Canvas(outer, bg=bg_frame, highlightthickness=0)
                canvas.pack(fill="x", expand=True)

                txt = tk.Text(
                    canvas, font=input_font, height=rows,
                    bg=box_bg, fg=ph_color, relief="flat", bd=0,
                    highlightthickness=0, insertbackground=text_color,
                    wrap="word", padx=8, pady=6
                )
                txt_win = canvas.create_window(4, 4, window=txt, anchor="nw")
                outline_w = border_width

                def _redraw_ta(event=None, outline_c=idle_line, lw=outline_w, c=canvas, t=txt, tw=txt_win, r=radius, bx=box_bg):
                    if field is not None:
                        outline_c, lw = field.line(outline_c), field.stroke(lw)
                    c.delete("bg_shape")
                    w = c.winfo_width() or (event.width if event else 320)
                    line_h = t.winfo_reqheight()
                    h = line_h + 8
                    c.config(height=h)
                    if r > 0:
                        _create_rounded_rect(c, 1, 1, w-1, h-1, r, fill=bx, outline=outline_c, width=lw, tags="bg_shape")
                    else:
                        c.create_rectangle(1, 1, w-1, h-1, fill=bx, outline=outline_c, width=lw, tags="bg_shape")
                    c.tag_lower("bg_shape")
                    c.itemconfig(tw, width=w-8)

                canvas.bind("<Configure>", lambda e: _redraw_ta(e))

                def on_focus_in_ta(e, t=txt, ph=placeholder, c=canvas):
                    _redraw_ta(outline_c=focus_line, lw=focus_width, c=c, t=t, tw=txt_win, r=radius, bx=box_bg)
                    if t.get("1.0", tk.END).rstrip("\n") == ph:
                        t.delete("1.0", tk.END)
                        t.config(fg=text_color)

                def on_focus_out_ta(e, t=txt, ph=placeholder, c=canvas):
                    _redraw_ta(outline_c=idle_line, lw=outline_w, c=c, t=t, tw=txt_win, r=radius, bx=box_bg)
                    if t.get("1.0", tk.END).rstrip("\n") == "":
                        t.insert("1.0", ph)
                        t.config(fg=ph_color)

                txt.bind("<FocusIn>",  on_focus_in_ta)
                txt.bind("<FocusOut>", on_focus_out_ta)
                txt.insert("1.0", placeholder)

                if comp is not None:
                    comp.widget = txt

                _watch_textarea(txt, _redraw_ta)

                def _field_repaint():
                    focused = _widget_has_focus(txt)
                    _redraw_ta(outline_c=focus_line if focused else idle_line,
                               lw=focus_width if focused else outline_w)
                _field_pads = (12, 12)
            else:
                txt = tk.Text(
                    outer, font=input_font, height=rows,
                    bg=box_bg, fg=ph_color, relief="flat", bd=0,
                    highlightthickness=0, insertbackground=text_color,
                    wrap="word", padx=8, pady=6
                )
                txt.pack(fill="x")
                line = tk.Frame(outer, bg=idle_line, height=1)
                if not shaped:
                    line.pack(fill="x")

                def _paint_ta(focused, ln=line, box=outer):
                    idle, focus = idle_line, focus_line
                    width = border_width if (border_width and border_color) else 0
                    if field is not None:
                        idle, focus = field.line(idle), field.line(focus)
                        width = field.stroke(width)
                    if not shaped:
                        ln.config(bg=focus if focused else idle,
                                  height=2 if focused else 1)
                    else:
                        box.configure(highlightthickness=width,
                                      highlightbackground=idle,
                                      highlightcolor=focus)
                _paint_ta(False)

                txt.insert("1.0", placeholder)

                if comp is not None:
                    comp.widget = txt

                def on_focus_in_ta(e, t=txt, ph=placeholder):
                    _paint_ta(True)
                    if t.get("1.0", tk.END).rstrip("\n") == ph:
                        t.delete("1.0", tk.END)
                        t.config(fg=text_color)

                def on_focus_out_ta(e, t=txt, ph=placeholder):
                    _paint_ta(False)
                    if t.get("1.0", tk.END).rstrip("\n") == "":
                        t.insert("1.0", ph)
                        t.config(fg=ph_color)

                txt.bind("<FocusIn>",  on_focus_in_ta)
                txt.bind("<FocusOut>", on_focus_out_ta)

                _watch_textarea(txt)

                def _field_repaint():
                    _paint_ta(_widget_has_focus(txt))
                _field_pads = (8, 8)

            if field is not None:
                field.finish(txt, _field_pads, _field_repaint)

        # ── CHECKBOX ──────────────────────────────────────────────────────────
        elif input_type == "checkbox":
            var = tk.BooleanVar()
            chk_fg = fg if fg else "#212121"

            row = tk.Frame(parent, bg=bg_frame, cursor="hand2")
            row.pack(pady=(6 + mt, 6 + mb), padx=(ml, mr), fill="x", anchor="w")

            SZ = 20
            cv = tk.Canvas(row, width=SZ, height=SZ, bg=bg_frame, highlightthickness=0)
            cv.pack(side="left", padx=(0, 8))

            lbl = tk.Label(
                row, text=placeholder,
                font=font or (("Segoe UI", 11) if os.name == "nt" else ("Helvetica", 11)),
                bg=bg_frame, fg=chk_fg, cursor="hand2",
                anchor="w", justify="left",
            )
            lbl.pack(side="left")

            def _draw_chk(checked, _cv=cv, _bg=bg_frame):
                try:
                    _cv.delete("all")
                    fill   = "#4F46E5" if checked else _bg
                    border = "#4F46E5" if checked else "#94A3B8"
                    _cv.create_rectangle(2, 2, SZ-2, SZ-2,
                                         fill=fill, outline=border, width=2)
                    if checked:
                        _cv.create_line(5, SZ//2,     SZ//2-1, SZ-5, fill="white", width=2, capstyle="round")
                        _cv.create_line(SZ//2-1, SZ-5, SZ-4, 4,      fill="white", width=2, capstyle="round")
                except Exception:
                    pass

            _draw_chk(var.get())

            def _toggle(e=None, _v=var):
                _v.set(not _v.get())

            def _on_trace(*args, _v=var):
                _draw_chk(_v.get())

            var.trace_add("write", _on_trace)
            cv.bind("<Button-1>",  _toggle)
            lbl.bind("<Button-1>", _toggle)
            row.bind("<Button-1>", _toggle)

            if comp is not None:
                comp._tk_var = var

        # ── RANGE (slider) — desenhado à mão: track fino arredondado + bola ────
        elif input_type == "range":
            frame = tk.Frame(parent, bg=bg_frame)
            frame.pack(pady=(6 + mt, 6 + mb), padx=(16 + ml, 16 + mr), fill="x")
            if placeholder:
                tk.Label(
                    frame, text=placeholder, font=("Arial", 11),
                    bg=bg_frame, fg=fg if fg else "#212121"
                ).pack(anchor="w")

            scale_var = tk.DoubleVar(value=0)   # 0-100 (aceita fração → suave)
            accent    = accent_color or bg or "#38BDF8"  # progresso + bola
            track_col = "#3A3F4B" if bg else "#D0D0D0"  # resto do track
            _H, _R, _TH = 26, 8, 4                       # altura / raio da bola / espessura

            slider = tk.Canvas(frame, height=_H, bg=bg_frame, highlightthickness=0, cursor="hand2")
            slider.pack(fill="x")

            def _range_redraw(c=slider, v=scale_var, acc=accent, trk=track_col, H=_H, R=_R, TH=_TH):
                try:
                    c.delete("all")
                    w = c.winfo_width()
                    if w <= 1:
                        c.after(30, _range_redraw)   # ainda sem largura → tenta a seguir
                        return
                    cy = H // 2
                    x0, x1 = R, w - R
                    c.create_line(x0, cy, x1, cy, fill=trk, width=TH, capstyle="round")
                    frac = max(0.0, min(100.0, float(v.get()))) / 100.0
                    tx = x0 + frac * (x1 - x0)
                    if tx > x0:
                        c.create_line(x0, cy, tx, cy, fill=acc, width=TH, capstyle="round")
                    _create_circle(c, tx - R, cy - R, tx + R, cy + R, fill=acc, outline="#FFFFFF", width=1)
                except Exception:
                    pass

            def _range_set_from_x(px, c=slider, v=scale_var, redraw=_range_redraw, R=_R):
                w = c.winfo_width()
                x0, x1 = R, max(R + 1, w - R)
                frac = (px - x0) / float(x1 - x0)
                v.set(max(0.0, min(100.0, frac * 100.0)))
                redraw()

            def _range_press(e, c=comp):
                if c is not None:
                    c._dragging = True   # pausa o poll do now_playing (não salta de volta)
                _range_set_from_x(e.x)

            def _range_release(e, c=comp, v=scale_var):
                if c is not None:
                    c._dragging = False
                    cb = getattr(c, '_on_release', None)
                    if cb:                # now_playing: arrastar+largar → seek
                        try:
                            cb(float(v.get()))
                        except Exception:
                            pass

            slider.bind("<Button-1>", _range_press)
            slider.bind("<B1-Motion>", lambda e: _range_set_from_x(e.x))
            slider.bind("<ButtonRelease-1>", _range_release)
            slider.bind("<Configure>", lambda e: _range_redraw())

            # Vincular ao ComponentDef para get_value/set_value
            if comp is not None:
                comp.widget = slider
                comp._tk_var = scale_var
                comp._range_redraw = _range_redraw

        # ── RADIO ─────────────────────────────────────────────────────────────
        elif input_type == "radio":
            options = [o.strip() for o in placeholder.split("|")] if placeholder else ["Option 1", "Option 2"]
            var = tk.StringVar(value=options[0])
            frame = tk.Frame(parent, bg=bg_frame)
            frame.pack(pady=(6 + mt, 6 + mb), padx=(16 + ml, 16 + mr), fill="x")
            for opt in options:
                tk.Radiobutton(
                    frame, text=opt, variable=var, value=opt,
                    font=("Arial", 12), bg=bg_frame,
                    fg=fg if fg else "#212121", activebackground=bg_frame, anchor="w"
                ).pack(fill="x")
            if comp is not None:
                comp._tk_var = var

        # ── SELECT (dropdown) ─────────────────────────────────────────────────
        elif input_type == "switch":
            var = tk.BooleanVar(value=False)
            text_color = fg if fg else "#212121"
            # Keep the active track separate from the input/card surface.
            track_on  = accent_color or bg or "#4CAF50"
            track_off = "#9E9E9E"

            outer = tk.Frame(parent, bg=bg_frame)
            # The phone's SwitchCompat is match_parent with the stylesheet's
            # margins and 12dp above and below its text; 16px more at each side
            # here put "Private account" out of line with the section above it.
            outer.pack(padx=(ml, mr), pady=(mt, mb), fill="x")

            input_font = font if font else ("Segoe UI" if os.name == "nt" else "Helvetica", 13)

            # Toggle à direita primeiro (pack order determina posição)
            TW, TH = 46, 24
            canvas = tk.Canvas(outer, width=TW, height=TH, bg=bg_frame,
                               highlightthickness=0, cursor="hand2")
            canvas.pack(side="right", pady=12)

            lbl = tk.Label(outer, text=placeholder or "", bg=bg_frame, fg=text_color,
                           font=input_font, anchor="w")
            lbl.pack(side="left", fill="x", expand=True)

            def draw_toggle(v=var, c=canvas, tw=TW, th=TH, on_col=track_on, off_col=track_off):
                c.delete("all")
                col = on_col if v.get() else off_col
                r = th // 2
                # Track (rounded rectangle)
                _create_rounded_rect(c, 0, 0, tw, th, th / 2.0, fill=col, outline="")
                # Thumb (white circle)
                pad = 3
                if v.get():
                    _create_circle(c, tw - th + pad, pad, tw - pad, th - pad, fill="white", outline="")
                else:
                    _create_circle(c, pad, pad, th - pad, th - pad, fill="white", outline="")

            def on_toggle(event=None, v=var, redraw=draw_toggle):
                v.set(not v.get())
                redraw()

            canvas.bind("<Button-1>", on_toggle)
            draw_toggle()

            if comp is not None:
                comp.widget = canvas
                comp._toggle_var = var
                comp._toggle_redraw = draw_toggle

        elif input_type == "select":
            options = [o.strip() for o in placeholder.split("|")] if placeholder else ["Option 1"]
            var = tk.StringVar(value=options[0])
            outer = tk.Frame(parent, bg=bg_frame)
            outer.pack(padx=(16 + ml, 16 + mr), pady=(4 + mt, 4 + mb), fill="x")

            input_font = font if font else ("Segoe UI" if os.name == "nt" else "Helvetica", 13)
            text_color = fg if fg else "#212121"
            box_bg     = bg if bg else "#ffffff"
            outline_c = border_color or "#bdbdbd"
            outline_w = border_width
            select_h = max(46, radius * 2 + 10 if radius > 0 else 46)
            select_canvas = tk.Canvas(
                outer, height=select_h, bg=bg_frame,
                highlightthickness=0, bd=0, cursor="hand2",
            )
            select_canvas.pack(fill="x", expand=True)

            def _draw_select(event=None, c=select_canvas):
                try:
                    w = event.width if event is not None else c.winfo_width()
                    h = c.winfo_height() or select_h
                    if w <= 1:
                        return
                    c.delete("all")
                    if radius > 0:
                        _create_rounded_rect(
                            c, 1, 1, w - 1, h - 1, radius,
                            fill=box_bg, outline=outline_c, width=outline_w,
                        )
                    else:
                        c.create_rectangle(
                            1, 1, w - 1, h - 1,
                            fill=box_bg, outline=outline_c, width=outline_w,
                        )
                    c.create_text(
                        16, h // 2, text=var.get(), anchor="w",
                        fill=text_color, font=input_font,
                    )
                    ax, ay = w - 20, h // 2
                    c.create_polygon(
                        ax - 5, ay - 3, ax + 5, ay - 3, ax, ay + 3,
                        fill=text_color, outline="",
                    )
                except Exception:
                    pass

            menu = tk.Menu(
                select_canvas, tearoff=0,
                bg=box_bg, fg=text_color,
                activebackground=accent_color or outline_c,
                activeforeground="#FFFFFF",
                bd=1, relief="flat",
                font=input_font,
            )
            for option in options:
                menu.add_command(label=option, command=lambda value=option: var.set(value))

            def _open_select(event=None, c=select_canvas, popup=menu):
                try:
                    popup.tk_popup(c.winfo_rootx(), c.winfo_rooty() + c.winfo_height())
                finally:
                    try:
                        popup.grab_release()
                    except Exception:
                        pass

            select_canvas.bind("<Configure>", _draw_select)
            select_canvas.bind("<Button-1>", _open_select)
            var.trace_add("write", lambda *_: _draw_select())
            _draw_select()

            if comp is not None:
                comp.widget = select_canvas
                comp._tk_var = var

    def run(self):
        self.root.mainloop()


# Instância única da interface — criada apenas no primeiro uso real (lazy).
# Se criássemos a AppPreview() (tk.Tk()) aqui, qualquer simples `import apkpy_lib`
# (incluindo o que o `apkpy build` faz internamente) abriria uma janela vazia do
# Preview sem o utilizador alguma vez ter chamado run().
class _LazyAppPreview:
    def __init__(self):
        self._instance = None

    def _get(self):
        if self._instance is None:
            self._instance = AppPreview()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get(), name)

    def __bool__(self):
        return True

_app = _LazyAppPreview()


# ─── Public API ───────────────────────────────────────────────────────────────

def device(name):
    """[Só previewer] Define o tamanho da janela de preview por modelo de
    telemóvel (ex.: device("Pixel 8")) ou um modo de janela cheia:
      - "fullscreen" → ecrã cheio SEM barra de título (Esc para sair)
      - "maximized"  → maximizada COM a barra de título padrão (X para fechar)
    Em ambos, o conteúdo fica numa coluna de telemóvel centrada.

    É ignorada no Android — lá o ecrã real É o dispositivo. Chama-a a nível de
    módulo (antes do run()); o tamanho é aplicado quando o preview arranca.
    Default, se nunca chamada: Pixel 9 (411x914).
    """
    global _preview_device
    key = str(name).strip().lower().replace(" ", "")
    if key in _SPECIAL_MODES or key in _PREVIEW_DEVICES_NORM:
        _preview_device = key
    else:
        print(f'device(): modelo desconhecido: "{name}"')
        print("Disponíveis: " + ", ".join(_PREVIEW_DEVICES.keys()) + ", responsive, fullscreen, maximized")


_declared_permissions = []

def declare_permissions(perms):
    """
    Declara permissões (ex: "CAMERA", "INTERNET") que o compilador irá
    adicionar ao AndroidManifest.xml.
    """
    global _declared_permissions
    _declared_permissions.extend(perms)

def _permission_name(perm):
    """The bare Android name of a permission, as the compiler writes it."""
    name = str(perm).partition('|')[0].strip()
    return (name.rpartition('.')[2] or name).upper()


class PermissionsAPI:
    def __init__(self):
        self._granted = set()

    def has(self, perm):
        """No ambiente Tkinter, verifica se o utilizador já concedeu esta permissão localmente."""
        # "camera", "CAMERA" and "android.permission.CAMERA" are one
        # permission, as on the phone (the compiler's _permission_symbol).
        return _permission_name(perm) in self._granted
    
    def request(self, perm, on_response=None):
        """Simula o pedido de permissão com um popup de sistema de Tkinter."""
        import tkinter.messagebox as messagebox
        perm = _permission_name(perm)
        # Se houver root ativo, tenta centralizar, caso contrário, usa janela base
        res = messagebox.askyesno(
            "Emulated Permission Request", 
            f"The ApkPy application is requesting permission to use: {perm}\n\nGrant permission (Emulation)?"
        )
        if res:
            self._granted.add(perm)
            
        if on_response:
            on_response(res)

permissions = PermissionsAPI()

class ClipboardAPI:
    """
    API da área de transferência (clipboard) do sistema.
    - No Android: usa android.content.ClipboardManager / ClipData.
    - No Preview: usa a área de transferência nativa do SO via Tkinter,
      para que `Ctrl+V` fora da app cole mesmo o texto copiado.
    """
    def copy(self, text):
        """Copia `text` para a área de transferência do sistema."""
        try:
            _app.root.clipboard_clear()
            _app.root.clipboard_append(str(text))
            _app.root.update()
        except Exception as e:
            print(f"[ApkPy clipboard.copy] {text}  ({e})")

clipboard = ClipboardAPI()

from .features.camera import CameraAPI, camera

class GalleryAPI:
    """
    Galeria de imagens do dispositivo.
    - No Android: abre o seletor nativo de imagens do sistema
      (ActivityResultContracts.GetContent — não requer permissões de
      armazenamento em Android moderno) e devolve o caminho (content URI)
      da imagem escolhida ao callback `on_result(success, path)`.
    - No Preview: abre o explorador de ficheiros do SO filtrado para imagens —
      o callback recebe o caminho real do ficheiro escolhido.
    """
    def pick(self, on_result=None):
        """Abre a galeria (simulada no Preview) e devolve (sucesso, caminho) a `on_result`."""
        try:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="Escolher imagem da galeria",
                filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Todos os ficheiros", "*.*")],
                parent=live_preview_root(),
            )
            if on_result:
                on_result(bool(path), path or "")
        except Exception as e:
            print(f"[ApkPy gallery.pick] ({e})")
            if on_result:
                on_result(False, "")

gallery = GalleryAPI()

class LocationAPI(ContinuousLocationMixin):
    """
    Localização (GPS) do dispositivo.
    - No Android: lê a última localização conhecida via LocationManager
      (GPS / rede), pedindo a permissão ACCESS_FINE_LOCATION em runtime se
      necessário, e devolve (sucesso, latitude, longitude) ao callback
      `on_result(success, lat, lng)`. As coordenadas vêm como strings
      (tal como `get_value()`).
    - No Preview: como o computador não tem GPS, abre um diálogo onde podes
      escrever as coordenadas a simular (por omissão, Lisboa) — o callback
      recebe exatamente os valores que indicares.
    """
    def get_current(self, on_result=None):
        """Obtém a localização atual (simulada no Preview) e devolve (sucesso, lat, lng, city)."""
        try:
            from tkinter import simpledialog
            coords = simpledialog.askstring(
                "Simulate location (GPS)",
                "Enter the coordinates to simulate as 'latitude,longitude'\n(e.g. Lisbon: 38.7223,-9.1393):",
                initialvalue="38.7223,-9.1393",
                parent=live_preview_root(),
            )
        except Exception as e:
            print(f"[ApkPy location.get_current] ({e})")
            if on_result:
                on_result(False, "", "", "")
            return

        if not coords:
            if on_result:
                on_result(False, "", "", "")
            return

        parts = [p.strip() for p in coords.split(",")]
        lat = parts[0] if len(parts) > 0 else ""
        lng = parts[1] if len(parts) > 1 else ""

        def _lookup_city():
            # Reverse geocoding via OpenStreetMap (Nominatim) — o equivalente ao
            # android.location.Geocoder no build Android. Corre em background para
            # não bloquear a UI; se falhar (sem internet), devolve city="".
            city = ""
            try:
                import urllib.request, json, ssl
                url = (
                    "https://nominatim.openstreetmap.org/reverse"
                    f"?format=json&lat={lat}&lon={lng}&zoom=10"
                )
                req = urllib.request.Request(url, headers={"User-Agent": "ApkPyPreviewer"})
                ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    addr = data.get("address", {}) if isinstance(data, dict) else {}
                    city = (addr.get("city") or addr.get("town") or addr.get("village")
                            or addr.get("municipality") or addr.get("county") or "")
            except Exception as e:
                print(f"[ApkPy location.get_current] reverse geocode failed ({e})")

            if on_result:
                if live_preview() is not None:
                    live_preview().root.after(0, lambda c=city: on_result(True, lat, lng, c))
                else:
                    on_result(True, lat, lng, city)

        import threading
        threading.Thread(target=_lookup_city, daemon=True).start()

location = LocationAPI()

HTTPS_TIMEOUT = 60
"""Segundos à espera da resposta. Eram 10, e uma resposta de um modelo de
linguagem não cabe em 10: o pedido morria antes de chegar, sempre. O valor
espelha o `_HTTPS_READ_TIMEOUT_MS` do compilador — se um mudar, muda o outro."""

_HTTPS_TLS_WARNED = set()


def _https_encode_body(data):
    """O corpo, em bytes, e a decisão de lhe chamar JSON.

    Um dict vira JSON e não `a=1&b=2`: é o que as APIs querem, é o que o
    Android passou a enviar, e o form-encoding que aqui estava nunca teve par
    do outro lado (um dict compilava para string vazia, portanto não há uma
    única app publicada a depender dele).
    """
    import json as _json

    if data is None:
        return None
    if isinstance(data, (dict, list, tuple)):
        return _json.dumps(data, ensure_ascii=False).encode('utf-8')
    if isinstance(data, bytes):
        return data
    return str(data).encode('utf-8')


def _https_looks_json(body):
    """Mesma regra do `_apkpyJsonShape` do Android: o primeiro caractere."""
    if not body:
        return False
    peek = body.lstrip()[:1]
    return peek in (b'{', b'[')


# Hosts the app pinned: host -> {"pins", "expires", "subdomains"}. Read by the
# Previewer to check requests and by the compiler to write the Android config.
_PINNED_HOSTS = {}


def _live_pin(host, port=443, timeout=6):
    """The pin a real handshake with *host* produces, or None.

    This is the whole reason pinning is checkable at all before shipping: a
    mistyped pin is otherwise invisible until the app is on somebody's phone,
    refusing to reach its own server. Needs ``cryptography`` -- the same
    optional package ``crypto.encrypt(password=)`` uses -- because pulling the
    SubjectPublicKeyInfo out of a certificate by hand is ASN.1 parsing, and
    getting that subtly wrong would report the wrong pin, which is worse than
    reporting none.
    """
    try:
        import base64
        import hashlib
        import ssl

        from cryptography import x509
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat,
        )
    except ImportError:
        return None
    try:
        pem = ssl.get_server_certificate((host, port), timeout=timeout)
        certificate = x509.load_pem_x509_certificate(pem.encode("ascii"))
        spki = certificate.public_key().public_bytes(
            Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        return "sha256/" + base64.b64encode(hashlib.sha256(spki).digest()).decode()
    except Exception:
        return None       # offline, or a host that does not answer: not a verdict


def _pin_entry_for(host):
    """The pin set that applies to *host*, following includeSubdomains."""
    name = str(host or "").lower()
    entry = _PINNED_HOSTS.get(name)
    if entry is not None:
        return name, entry
    for pinned, entry in _PINNED_HOSTS.items():
        if entry.get("subdomains") and name.endswith("." + pinned):
            return pinned, entry
    return None, None


class HttpsAPI:
    """
    API HTTPS para o Hot Previewer (Tkinter).
    Executa os pedidos em background usando threads para não bloquear a interface.
    """

    # Checked once per host: a handshake per request would make the Previewer
    # crawl, and a certificate does not change while the window is open.
    _checked = {}

    def pin(self, host, pins, expires=None, subdomains=False):
        """Accept only these public keys for *host*.

            https.pin("api.example.com", [current_pin, backup_pin],
                      expires="2027-06-01")

        Two pins are required. An app pinned to the one certificate it can see
        today stops reaching its own server the day that certificate is
        replaced -- everyone at once, fixable only by a store update. The spare
        is what turns a renewal back into a routine.

        ``expires`` is the date Android stops enforcing this set. It is a
        safety valve rather than a schedule: past it the app keeps working with
        ordinary certificate checking instead of refusing to connect for ever.
        """
        from .core.features import pinning as _pinning

        for problem in (_pinning.check_host(host), _pinning.check_pins(pins),
                        _pinning.check_expires(expires)):
            if problem:
                raise ValueError("https.pin(): " + problem)
        name = _pinning.normalise(host)
        _PINNED_HOSTS[name] = {
            "pins": list(pins),
            "expires": expires,
            "subdomains": bool(subdomains),
        }
        return name

    def _refuse_unpinned(self, url):
        """The reason this request must not go out, or ''.

        Android would refuse it during the handshake; the Previewer refuses it
        here, so a wrong pin shows up on the desktop rather than on a phone.
        """
        import urllib.parse

        parsed = urllib.parse.urlparse(str(url))
        host = (parsed.hostname or "").lower()
        pinned, entry = _pin_entry_for(host)
        if entry is None:
            return ""
        if host in self._checked:
            return self._checked[host]
        live = _live_pin(host, parsed.port or 443)
        if live is None:
            # No cryptography installed, or the host did not answer. Saying
            # nothing beats inventing a verdict from a failed handshake.
            self._checked[host] = ""
            return ""
        verdict = "" if live in entry["pins"] else (
            "The certificate %s is using does not match any pin declared for "
            "%s. It is %s. On a phone this request would simply fail."
            % (host, pinned, live)
        )
        self._checked[host] = verdict
        return verdict
    def _request(self, method, url, data=None, headers=None, on_response=None,
                 timeout=None):
        import urllib.request
        import urllib.parse
        import urllib.error
        import threading
        import ssl

        wait = HTTPS_TIMEOUT if timeout is None else timeout
        try:
            wait = max(1.0, float(wait))
        except (TypeError, ValueError):
            wait = HTTPS_TIMEOUT

        def run_request():
            # A pinned host is checked before anything leaves: Android refuses
            # this during the handshake, and finding out here costs a message
            # instead of an app that cannot reach its own server.
            refusal = self._refuse_unpinned(url)
            if not refusal and _previewer_offline():
                # The Previewer is standing in for a phone with no connection
                # (a click on its status strip). Nothing leaves, and the
                # answer is the one Android gives there, word for word.
                refusal = ('Unable to resolve host "%s": No address associated '
                           'with hostname' % (urllib.parse.urlparse(url).hostname or url))
            if refusal:
                if on_response:
                    if _app and _app.root:
                        _app.root.after(0, lambda r=refusal: on_response(False, r))
                    else:
                        on_response(False, refusal)
                return
            try:
                encoded_data = _https_encode_body(data)

                merged_headers = {'User-Agent': 'ApkPyPreviewer'}
                if headers and isinstance(headers, dict):
                    merged_headers.update(headers)
                # O Android põe este header sozinho quando o corpo abre em
                # chaveta; sem ele aqui, o Previewer levava um 400 que o
                # telemóvel não levava — divergência à conta de um header.
                if _https_looks_json(encoded_data) and not any(
                        str(k).lower() == 'content-type' for k in merged_headers):
                    merged_headers['Content-Type'] = 'application/json; charset=utf-8'

                req = urllib.request.Request(url, data=encoded_data, headers=merged_headers, method=method)
                # Verificar o certificado é o comportamento normal. O contexto
                # sem verificação só entra se o sistema não tiver CAs (Windows
                # sem store) e avisa uma vez: uma chave de API não devia sair
                # por um túnel que ninguém validou, em silêncio.
                try:
                    ctx = ssl.create_default_context()
                    response_cm = urllib.request.urlopen(req, timeout=wait, context=ctx)
                except ssl.SSLCertVerificationError as tls_error:
                    host = urllib.parse.urlparse(url).hostname or url
                    if host not in _HTTPS_TLS_WARNED:
                        _HTTPS_TLS_WARNED.add(host)
                        print('[apkpy] Certificado de %s nao verificado (%s). O '
                              'Previewer continua sem verificar; o Android NAO '
                              'faz isto e vai recusar a ligacao.'
                              % (host, tls_error.reason if hasattr(tls_error, 'reason') else tls_error))
                    response_cm = urllib.request.urlopen(
                        req, timeout=wait, context=ssl._create_unverified_context())
                with response_cm as response:
                    # JsonRows: a resposta é str normal mas `for x in resp:`
                    # itera as linhas se for um array JSON (paridade c/ Android)
                    content = JsonRows(response.read().decode('utf-8'))
                    status = response.status
                    success = 200 <= status < 300
                    if on_response:
                        if _app and _app.root:
                            _app.root.after(0, lambda s=success, c=content: on_response(s, c))
                        else:
                            on_response(success, content)
            except Exception as e:
                # Erros HTTP (4xx/5xx) ainda têm um corpo de resposta útil
                if isinstance(e, urllib.error.HTTPError):
                    try:
                        err_msg = e.read().decode('utf-8')
                    except Exception:
                        err_msg = str(e)
                else:
                    err_msg = str(e)
                if on_response:
                    if _app and _app.root:
                        _app.root.after(0, lambda err=err_msg: on_response(False, err))
                    else:
                        on_response(False, err_msg)

        threading.Thread(target=run_request, daemon=True).start()

    def get(self, url, headers=None, on_response=None, timeout=None):
        self._request("GET", url, None, headers, on_response, timeout)

    def post(self, url, data=None, headers=None, on_response=None, timeout=None):
        """Envia um corpo. Um dict vira JSON — incluindo o escape, que é do
        serializador e não de uma concatenação à mão.

        ``timeout`` são segundos à espera da resposta (60 por omissão). Uma
        API de modelos de linguagem precisa de mais do que a conta habitual.
        """
        self._request("POST", url, data, headers, on_response, timeout)

    def put(self, url, data=None, headers=None, on_response=None, timeout=None):
        """Substitui um recurso existente (CRUD update completo)."""
        self._request("PUT", url, data, headers, on_response, timeout)

    def patch(self, url, data=None, headers=None, on_response=None, timeout=None):
        """Atualização parcial de um recurso (só os campos enviados)."""
        self._request("PATCH", url, data, headers, on_response, timeout)

    def delete(self, url, headers=None, on_response=None, timeout=None):
        """Apaga um recurso (CRUD delete)."""
        self._request("DELETE", url, None, headers, on_response, timeout)

https = HttpsAPI()

class ServiceAPI:
    """
    API de Background Services para o Hot Previewer (Tkinter).

    No previewer, tarefas periódicas correm em threads daemon que repetem
    num intervalo fixo. No build Android, `service.every(...)` é compilado
    para um `androidx.work.Worker` agendado via WorkManager — o mecanismo
    nativo recomendado para trabalho periódico em segundo plano.

    IMPORTANTE: a função passada em `run=` corre fora do ecrã principal
    (tal como um Worker no Android, que pode executar com a app fechada).
    Use apenas `storage`, `db`, `https` e `toast` lá dentro — não chame
    `.get_value()`/`.set_value()` em componentes de UI.
    """
    def __init__(self):
        self._timers = {}

    def every(self, run, minutes=15, id="bg_service", only_on_wifi=False, only_when_charging=False):
        """
        Agenda `run` para ser executado repetidamente a cada `minutes` minutos.

        `only_on_wifi` / `only_when_charging` são constraints exclusivas do Android
        (traduzidas para androidx.work.Constraints) — no Preview de desktop não há
        um conceito real de "WiFi vs. dados móveis" ou "a carregar", por isso são
        ignoradas aqui e a tarefa corre sempre no intervalo definido.
        """
        import threading

        if id in self._timers:
            return  # já agendado

        interval_seconds = max(1, int(minutes * 60))
        stop_event = threading.Event()
        self._timers[id] = stop_event
        run = _as_worker_body(run, id, stop_event.set)

        def _loop():
            while not stop_event.wait(interval_seconds):
                try:
                    if _app and _app.root:
                        _app.root.after(0, run)
                        continue
                except Exception:
                    pass  # mainloop ainda não arrancou (ex: intervalo de teste muito curto) — corre direto
                try:
                    run()
                except Exception as e:
                    print(f"[ApkPy Service:{id}] erro: {e}")

        threading.Thread(target=_loop, daemon=True).start()

    def once(self, run, after_minutes=0, id="once_service", only_on_wifi=False, only_when_charging=False):
        """
        Agenda `run` para correr UMA ÚNICA VEZ, passados `after_minutes` minutos
        (equivale a um `androidx.work.OneTimeWorkRequest` com `setInitialDelay`).

        Tal como `every`, a função corre fora do ecrã principal — usa apenas
        `storage`, `db`, `https` e `toast` lá dentro.

        `only_on_wifi`/`only_when_charging` são constraints exclusivas do Android
        (ver `every`) — ignoradas aqui no Preview de desktop.
        """
        import threading

        if id in self._timers:
            return  # já agendado

        delay_seconds = max(0, after_minutes * 60)
        run = _as_worker_body(run, id)

        def _run_once():
            self._timers.pop(id, None)
            try:
                if _app and _app.root:
                    _app.root.after(0, run)
                    return
            except Exception:
                pass
            try:
                run()
            except Exception as e:
                print(f"[ApkPy Service:{id}] erro: {e}")

        timer = threading.Timer(delay_seconds, _run_once)
        timer.daemon = True
        self._timers[id] = timer
        timer.start()

    def cancel(self, id="bg_service"):
        """Cancela uma tarefa periódica ou única previamente agendada (pelo `id`)."""
        task = self._timers.pop(id, None)
        if task is None:
            return
        if hasattr(task, 'set'):
            task.set()       # threading.Event (tarefa periódica de `every`)
        else:
            task.cancel()    # threading.Timer (tarefa única de `once`)

service = ServiceAPI()


def _as_worker_body(run, label, on_refused=None):
    """Run a service body under the same guard as a background_job.

    On the phone service.every() and service.once() are Workers too, so a call
    that needs a screen stops the build there. Here the body runs on the
    interface thread, where set_value() would simply work -- the guard is what
    keeps the desk from accepting what the phone refuses.
    """
    def body():
        try:
            with _job_rules.running_job():
                run()
        except Exception as error:
            if not _job_rules.is_refusal(error):
                raise
            report_exception(error, context=(
                "service '%s' - the body reached a call the phone refuses in "
                "the background, so it stops here" % label))
            if on_refused is not None:
                on_refused()
    body.__name__ = getattr(run, "__name__", "run")
    return body


def json_get(json_str, path):
    """
    Extrai um valor de uma string JSON usando notação de pontos.
    Exemplo: json_get(response, "main.temp") → "20.5"
    Suporta objetos aninhados: "a.b.c"
    Suporta acesso a listas por índice numérico: "0.name" → lista[0]["name"]
    Em caso de erro (chave não existe, JSON inválido), devolve "".
    """
    import json as _json
    try:
        obj = _json.loads(json_str)
        parts = path.split('.')
        for part in parts:
            if isinstance(obj, list):
                # acesso por índice numérico
                idx = int(part)
                obj = obj[idx]
            elif isinstance(obj, dict):
                obj = obj[part]
            else:
                return ""
        return str(obj)
    except Exception:
        return ""


def card_action(text, variant="text", command=None, icon=None, id=None):
    """Create a detached button intended for ``card(actions=[...])``."""
    return ComponentDef(
        'button', text=text, command=command, comp_id=id,
        variant=normalize_button_variant(variant), icon=icon,
    )


def action(icon, command=None, label=None, id=None):
    """Create an icon action for :func:`app_bar` or :func:`sliver_app_bar`.

    ``label`` is used as the Android accessibility description. The returned
    descriptor is detached: it only becomes visible when passed in ``actions``
    (or as ``leading``) to an app bar.
    """
    if not icon:
        raise ValueError("action(icon=...) requires a Material icon name")
    return ComponentDef(
        'app_bar_action', icon=str(icon), command=command,
        label=str(label or icon).replace('_', ' '), comp_id=id,
    )


def _attach_app_bar(kind, title, leading=None, actions=None, id=None,
                    image=None, expanded_height=240, pinned=True, screen=None):
    if screen is None or not isinstance(screen, Screen):
        raise TypeError(f"{kind}(screen=...) expects an ApkPy Screen")
    normalized_actions = []
    for item in actions or []:
        if not isinstance(item, ComponentDef) or item.comp_type != 'app_bar_action':
            raise TypeError("app bar actions must be created with action(...)")
        normalized_actions.append(item)
    if isinstance(leading, ComponentDef) and leading.comp_type != 'app_bar_action':
        raise TypeError("app bar leading must be an icon name or action(...)")
    bar = ComponentDef(
        kind, title=str(title), leading=leading, actions=normalized_actions,
        comp_id=id, image=image, expanded_height=int(expanded_height),
        pinned=bool(pinned),
    )
    screen.app_bar = bar
    return bar


def app_bar(title, leading=None, actions=None, id=None, screen=None):
    """Attach a fixed Material toolbar to a screen.

    Example::

        app_bar("Library", leading="menu", actions=[
            action("search", command=open_search),
        ], screen=home)
    """
    return _attach_app_bar(
        'app_bar', title, leading=leading, actions=actions, id=id, screen=screen,
    )


def sliver_app_bar(title, image, expanded_height=240, pinned=True,
                   leading=None, actions=None, id=None, screen=None):
    """Attach an image header that collapses as its scrollable screen moves."""
    return _attach_app_bar(
        'sliver_app_bar', title, leading=leading, actions=actions, id=id,
        image=image, expanded_height=expanded_height, pinned=pinned, screen=screen,
    )


def _card_action_component(action):
    if isinstance(action, ComponentDef):
        if action.comp_type != 'button':
            raise TypeError("card actions must be buttons")
        return action
    if isinstance(action, str):
        return card_action(action)
    if isinstance(action, dict):
        return card_action(
            action.get('text', ''), variant=action.get('variant', 'text'),
            command=action.get('command'), icon=action.get('icon'),
            id=action.get('id'),
        )
    if isinstance(action, (tuple, list)) and action:
        return card_action(
            action[0], variant=(action[1] if len(action) > 1 else 'text'),
            command=(action[2] if len(action) > 2 else None),
        )
    raise TypeError(
        "card actions must use card_action(), a string, dict or tuple"
    )


def card(title=None, subtitle=None, image=None, content=None, actions=None,
         id=None, variant="elevated", screen=None, parent=None):
    """Create a semantic Material card or an empty composable card surface.

    ``title``/``subtitle``/``image``/``actions`` provide the ready-made form.
    Omitting them returns an empty card that accepts normal ``parent=card``
    composition. Actions use :func:`card_action` to stay detached until the
    complete card is attached to a screen.
    """
    normalized = normalize_card_variant(variant)
    comp = ComponentDef('card', comp_id=id, variant=normalized)
    prefix = str(id or 'card')
    if image:
        comp.children.append(ComponentDef(
            'image', src=image, comp_id=f'{prefix}_media', card_media=True,
        ))
    if title is not None:
        comp.children.append(ComponentDef(
            'label', text=title, comp_id=f'{prefix}_title', variant='title',
        ))
    if subtitle is not None:
        comp.children.append(ComponentDef(
            'label', text=subtitle, comp_id=f'{prefix}_subtitle',
            variant='subtitle',
        ))
    if content is not None:
        contents = content if isinstance(content, (list, tuple)) else [content]
        for item in contents:
            if isinstance(item, ComponentDef):
                comp.children.append(item)
            else:
                comp.children.append(ComponentDef(
                    'label', text=str(item), comp_id=f'{prefix}_body',
                    variant='body',
                ))
    if actions:
        action_row = ComponentDef(
            'container', comp_id=f'{prefix}_actions', card_actions=True,
        )
        action_row.children.extend(_card_action_component(item) for item in actions)
        comp.children.append(action_row)
    if parent is not None:
        parent.children.append(comp)
    elif screen is not None:
        screen._add(comp)
    return comp


def container(id=None, screen=None, parent=None):
    """
    Cria um contentor (caixa) para agrupar outros componentes (ex: Note Card, Header).
    Pode ser adicionado à raiz do ecrã (screen) ou a outro contentor (parent).
    """
    comp = ComponentDef('container', comp_id=id)
    if parent is not None:
        parent.children.append(comp)
    elif screen is not None:
        screen._add(comp)
    return comp


class PagerDef(ComponentDef):
    """A pager: tabs over pages that swipe sideways."""

    def select(self, index):
        """Show page ``index`` (from 0), sliding to it as a tap on its tab does."""
        index = int(index)
        selector = getattr(self, '_select_page', None)
        if selector is not None:
            selector(index)
        else:
            self._initial_page = index


def pager(id=None, screen=None, parent=None):
    """Tabs over pages that swipe sideways -- a profile's Posts / Reels /
    Tagged, a chat app's Chats / Status / Calls.

    Each page is a ``tab()`` inside the pager, and what a page shows goes
    inside its tab with ``parent=``::

        tabs = pager(id="profile_tabs", screen=profile)
        posts = tab("Posts", icon="grid_on", parent=tabs)
        reels = tab("Reels", icon="slideshow", parent=tabs)
        virtual_collection(photos, row=tile, layout="grid", columns=3,
                           parent=posts)
        label("No reels yet", parent=reels)

    A tap on a tab slides to its page, and so does a swipe. ``tabs.select(1)``
    does it from code. Without a fixed height the pager is as tall as the
    page on screen, so a long grid and a short page can share it in a
    scrolling screen.

    CSS on the pager's id (or ``pager { }``): ``background-color`` (the strip;
    transparent by default), ``color`` (the other tabs), ``active-color`` (the
    tab on screen), ``indicator-color``, ``border-color`` (a line under the
    strip) and ``text-transform``. Each page is styled by its tab's id, like a
    container.
    """
    comp = PagerDef('pager', comp_id=id)
    if parent is not None:
        parent.children.append(comp)
    elif screen is not None:
        screen._add(comp)
    return comp


def tab(text="", icon=None, id=None, parent=None, describe=None):
    """One page of a ``pager()``: its tab shows ``text``, ``icon`` or both,
    and the components given ``parent=`` this tab are its page.

    An icon-only tab should have ``describe=`` -- what a screen reader says
    for it."""
    if parent is None or getattr(parent, 'comp_type', None) != 'pager':
        raise ValueError(
            'tab() goes inside a pager(): tabs = pager(id="tabs", screen=home), '
            'then tab("Posts", parent=tabs)')
    comp = ComponentDef('tab', text=text, icon=icon, comp_id=id, describe=describe)
    parent.children.append(comp)
    return comp


class ChartDef(ComponentDef):
    """A chart: bars, a line, a donut or a ring."""

    def set_items(self, items):
        """Draw these items instead: a list of dicts read by the chart's x and
        y names, or of numbers."""
        self.kwargs['items'] = list(items or [])
        redraw = getattr(self, '_chart_redraw', None)
        if redraw is not None:
            redraw()

    def set_value(self, value):
        """A ring's value (out of its ``max``)."""
        self.kwargs['value'] = value
        redraw = getattr(self, '_chart_redraw', None)
        if redraw is not None:
            redraw()


def chart(items=None, kind="bar", x="label", y="value", id=None, screen=None,
          parent=None, on_click=None, fill=False, value=0, max=100, center=None):
    """A chart drawn natively: ``kind="bar"``, ``"line"``, ``"donut"`` or
    ``"ring"``.

    Bars, a line and a donut take ``items`` -- dicts read by their ``x``
    (the label) and ``y`` (the number) keys, or plain numbers::

        spending = [{"label": "Jan", "value": 820}, {"label": "Feb", "value": 1140}]
        chart(spending, kind="bar", id="monthly", screen=home)
        chart(steps, kind="line", fill=True, screen=home)
        chart(categories, kind="donut", on_click=show_category, screen=home)
        budget = chart(kind="ring", value=72, max=100, screen=home)

    A ring shows one ``value`` out of ``max``, with ``center`` in the middle
    (the percentage when it is not given). ``set_items(items)`` redraws the
    others with new data, ``set_value(v)`` moves a ring. ``on_click`` gets the
    item of the bar or slice that was tapped. A donut lists its slices under
    it, and an item's ``color`` key colours its slice.

    CSS on its id (or ``chart { }``): ``color`` (the series), ``track-color``
    (under a ring or a donut), ``label-color``, ``grid-color``,
    ``title-color`` (a ring's centre), ``stroke-width`` (a line's or a ring's
    thickness), ``border-radius`` (the bars' corners) and ``height``.
    """
    from .chart_rules import normalize_kind
    comp = ChartDef('chart', items=list(items or []), kind=normalize_kind(kind), x=x, y=y,
                    comp_id=id, on_click=on_click, fill=bool(fill), value=value,
                    max=max, center=center)
    if parent is not None:
        parent.children.append(comp)
    elif screen is not None:
        screen._add(comp)
    return comp


class ChoiceDef(ComponentDef):
    """Chips or a segmented button: options that stay selected."""

    def _current(self):
        return list(self.kwargs.get('_selected') or [])

    def get_value(self):
        """The selected option, or "" when none is; a list of them when
        ``multiple=True``."""
        from .choice_rules import value_of
        return value_of(self._current(), bool(self.kwargs.get('multiple')))

    def set_value(self, value):
        """Select ``value`` (a list of options when ``multiple=True``).
        on_change is not called: it answers taps."""
        from .choice_rules import from_value
        if isinstance(value, _ParamRef):
            self._param_ref = value
            value = value.resolve()
        self.kwargs['_selected'] = from_value(
            self.comp_type, self.kwargs.get('options') or [], self._current(),
            value, bool(self.kwargs.get('multiple')), bool(self.kwargs.get('required')))
        redraw = getattr(self, '_choice_redraw', None)
        if redraw is not None:
            redraw()


def _choice(kind, options, selected, multiple, on_change, icons, check, required, id,
            screen, parent):
    from . import choice_rules as rules
    options = rules.options_from(kind, options)
    comp = ChoiceDef(kind, options=options,
                     icons=rules.icons_from(kind, icons, options), check=bool(check),
                     multiple=bool(multiple), required=bool(required),
                     on_change=on_change, comp_id=id,
                     _selected=rules.initial(kind, options, selected, bool(multiple),
                                             required=bool(required)))
    if parent is not None:
        parent.children.append(comp)
    elif screen is not None:
        screen._add(comp)
    return comp


def chips(options, selected=None, multiple=False, on_change=None, icons=None,
          check=True, required=False, id=None, screen=None, parent=None):
    """A row of chips that stay selected -- the filters over a mail inbox,
    the genres over a music app, the tags on a post.

    One chip at a time by default: a tap selects it, and a tap on the
    selected one clears it. ``multiple=True`` lets each chip turn on and off
    by itself. ``required=True`` always keeps one selected -- the filter bar
    with an "All" that a WhatsApp or a Spotify has: a tap on the selected
    chip does nothing, the last chip of a ``multiple`` set cannot be turned
    off, and with nothing named the first starts selected. Chips wrap onto
    another line when the screen runs out::

        filters = chips(["All", "Unread", "Starred"], selected="All",
                        on_change=show, screen=inbox)
        tags = chips(["Python", "Android", "Kotlin"], multiple=True,
                     selected=["Python"], on_change=retag, screen=post)

    ``on_change`` gets what ``get_value()`` gives -- the selected word, or ""
    when none is; with ``multiple=True`` a list of words -- after each tap.
    ``set_value()`` selects from code and does not call it. ``icons=`` puts
    an icon before each chip's words (one name per option, or None); a
    selected chip shows a check there, unless ``check=False``.

    Each chip is 32 tall to the eye and 48 to the finger, and a screen reader
    reads it as a checkbox (or a radio button when only one can be on).

    CSS on its id (or ``chips { }``): ``color``, ``background-color``,
    ``border-color``, ``active-color`` (a selected chip's words),
    ``indicator-color`` (its fill), ``border-radius`` and ``font-size``.
    """
    return _choice('chips', options, selected, multiple, on_change, icons, check,
                   required, id, screen, parent)


def segmented(options, selected=None, multiple=False, on_change=None, icons=None,
              check=True, required=False, id=None, screen=None, parent=None):
    """A segmented button: two to five options side by side in one outlined
    pill -- Day / Week / Month, List / Grid, Metric / Imperial.

    One segment is always selected unless ``multiple=True`` (and then, with
    ``required=True``, at least one); with nothing said, it is the first::

        period = segmented(["Day", "Week", "Month"], selected="Week",
                           on_change=show_period, screen=insights)

    The segments share the width equally. ``on_change``, ``get_value()``,
    ``set_value()``, ``icons=`` and ``check=`` work as they do on ``chips()``.

    CSS on its id (or ``segmented { }``): ``color``, ``background-color``,
    ``border-color``, ``active-color``, ``indicator-color``,
    ``border-radius`` and ``font-size``.
    """
    return _choice('segmented', options, selected, multiple, on_change, icons, check,
                   required, id, screen, parent)


def list_row(text, subtitle=None, icon=None, trailing=None, trailing_icon=None,
             command=None, id=None, screen=None, parent=None):
    """Add a settings-style row: icon, label, subtitle and a trailing element.

    This is the shape a settings screen is made of, and the one thing a
    ``button`` cannot be: its label sits at the leading edge, it carries a
    second line, and it has room on the right for a value, a badge or a
    chevron.  Everything is optional except the label.

    Args:
        text:          The label. The only required piece.
        subtitle:      A second, quieter line under it.
        icon:          A Material icon name, or a path to your own ``.svg``.
        trailing:      Text pinned to the right -- a value, a plan, a count.
        trailing_icon: An icon pinned to the right, after ``trailing``.
        command:       Called when the row is tapped.
        id:            ID for CSS. ``list_row { ... }`` styles every row.
        screen:        Screen the row belongs to.
        parent:        Container the row belongs to. Give the container a
                       ``divider-color`` and the rows are separated by
                       hairlines, drawn between them and never at the edges.

    Returns:
        A ComponentDef. To open a screen instead of running a command, use
        ``screen.on_click_navigate(button=the_row, to=other_screen)`` -- the
        method form, which is the one the Android build reads.
    """
    comp = ComponentDef(
        'list_row', text=text, subtitle=subtitle, icon=icon,
        trailing=trailing, trailing_icon=trailing_icon, command=command,
        comp_id=id,
    )
    if parent is not None:
        parent.children.append(comp)
        return comp
    if screen is not None:
        return screen._add(comp)
    raise ValueError(
        "list_row(...) needs screen= or parent= -- a row is part of a list, "
        "not a standalone legacy widget."
    )


# ── Navigation drawer ─────────────────────────────────────────────────────────

_app_drawer = [None]


class DrawerDef:
    """A navigation drawer: the panel that slides in from the leading edge.

    Declared once for the whole app, the way :func:`bottom_nav` is. Open it
    from an app bar's leading icon and the screens listed in it become the
    app's top-level navigation.
    """

    def __init__(self, screens, labels, icons, header, subtitle, comp_id):
        self.screens = list(screens)
        self.labels = list(labels)
        self.icons = list(icons)
        self.header = header
        self.subtitle = subtitle
        self.comp_id = comp_id

    def open(self):
        """Slide the panel in."""
        if _app is not None:
            _app.open_drawer()

    def close(self):
        """Slide it back out."""
        if _app is not None:
            _app.close_drawer()


def drawer(screens, labels=None, icons=None, header=None, subtitle=None,
           id=None):
    """Declare the app's navigation drawer.

    The panel that slides in from the leading edge and holds the app's
    top-level destinations -- the shape every assistant, mail client and
    reader uses, and the one thing a ``bottom_nav`` cannot be when there are
    more than five of them.

    ~~~ python
    menu = drawer(
        [chat, projects, artifacts],
        labels=["New chat", "Projects", "Artifacts"],
        icons=["add", "folder", "description"],
        header="Ora",
        subtitle="you@example.com",
    )

    app_bar("New chat", leading=action("menu", command=lambda: menu.open()),
            screen=chat)
    ~~~

    Args:
        screens:  The screens the drawer navigates to, in order.
        labels:   One label per screen. Defaults to the screen ids.
        icons:    One Material icon name per screen.
        header:   A line of text above the items -- an account name usually.
        subtitle: A quieter second line under it.
        id:       ID for CSS. ``drawer { ... }`` styles the panel.

    Returns:
        A DrawerDef with ``open()`` and ``close()``.
    """
    resolved_labels = list(labels or [])
    resolved_icons = list(icons or [])
    while len(resolved_labels) < len(screens):
        target = screens[len(resolved_labels)]
        resolved_labels.append(str(getattr(target, 'id', '') or ''))
    while len(resolved_icons) < len(screens):
        resolved_icons.append('circle')
    definition = DrawerDef(screens, resolved_labels, resolved_icons,
                           header, subtitle, id)
    _app_drawer[0] = definition
    return definition


class _LayoutSpec:
    """Internal value returned by row()/column() for responsive()."""
    def __init__(self, direction, children):
        self.direction = direction
        self.children = list(children)


def row(*children):
    """Describe a horizontal responsive arrangement."""
    return _LayoutSpec('row', children)


def column(*children):
    """Describe a vertical responsive arrangement."""
    return _LayoutSpec('column', children)


def responsive(mobile, tablet=None, landscape=None, breakpoint=600, id=None,
               screen=None, parent=None):
    """Create a container whose arrangement follows the active viewport."""
    if not isinstance(mobile, _LayoutSpec):
        raise TypeError("responsive(mobile=...) expects row(...) or column(...)")
    tablet = tablet or mobile
    if not isinstance(tablet, _LayoutSpec) or (
        landscape is not None and not isinstance(landscape, _LayoutSpec)
    ):
        raise TypeError("responsive layouts must use row(...) or column(...)")
    expected = list(mobile.children)
    for spec in (tablet, landscape):
        if spec is not None and (
            len(spec.children) != len(expected)
            or any(child not in spec.children for child in expected)
        ):
            raise ValueError("All responsive arrangements must contain the same components")
    config = {
        'mobile': mobile.direction,
        'tablet': tablet.direction,
        'breakpoint': int(breakpoint),
    }
    if landscape is not None:
        config['landscape'] = landscape.direction
    comp = ComponentDef('container', comp_id=id, responsive=config)
    comp.children.extend(expected)
    # A component declared with screen=/parent= is moved into the wrapper.
    if screen is not None:
        screen.components[:] = [child for child in screen.components if child not in expected]
    if parent is not None:
        parent.children[:] = [child for child in parent.children if child not in expected]
        parent.children.append(comp)
    elif screen is not None:
        screen._add(comp)
    return comp


def _normalize_image_ratio(value):
    """Normalize ``16:9``/``16/9``/numeric ratios for image components."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        ratio = float(value)
    else:
        text = str(value).strip().replace("/", ":")
        try:
            if ":" in text:
                left, right = text.split(":", 1)
                ratio = float(left.strip()) / float(right.strip())
            else:
                ratio = float(text)
        except (TypeError, ValueError, ZeroDivisionError):
            raise ValueError("aspect_ratio must be like '16:9', '1:1' or a positive number")
    if ratio <= 0:
        raise ValueError("aspect_ratio must be greater than zero")
    return ratio


def _new_image_component(src, id=None, *, placeholder=None, fallback=None,
                         cache=True, fade_in=False, blur=0, tint=None,
                         aspect_ratio=None, avatar_size=None, status=None):
    try:
        blur_value = max(0.0, float(blur or 0))
    except (TypeError, ValueError):
        raise ValueError("blur must be a non-negative number")
    ratio = _normalize_image_ratio(aspect_ratio)
    status_value = None if status in (None, "") else str(status).strip().lower()
    if status_value not in {None, "online", "away", "busy", "offline"}:
        raise ValueError("avatar status must be online, away, busy or offline")
    return ComponentDef(
        'image', src=src, comp_id=id,
        placeholder=placeholder, fallback=fallback,
        cache=bool(cache), fade_in=bool(fade_in), blur=blur_value,
        tint=tint, aspect_ratio=ratio,
        avatar=avatar_size is not None,
        avatar_size=avatar_size, status=status_value,
    )


def view_image(src, describe=None):
    """Open a picture over the whole screen, where it can be pinched,
    double-tapped and dragged::

        def open_photo(item):
            view_image(item["photo"])

    ``src`` is a file packaged with the app or an address. Back, the cross
    in the corner and a drag down close it. For a picture already on the
    screen, ``image(src, zoom=True)`` does this on a tap.
    """
    _job_rules.guard("navigation", "view_image()")
    return _zoom_feature.view(src, describe or '')


def image(src, id=None, screen=None, parent=None, *, placeholder=None,
          fallback=None, cache=True, fade_in=False, blur=0, tint=None,
          aspect_ratio=None, describe=None, command=None, zoom=False):
    """
    Adiciona uma imagem à interface.

    Args:
        src:    Caminho para o ficheiro de imagem (relativo à pasta do projeto).
                Exemplos: "logo.png", "assets/hero.jpg"
        id:     ID para aplicar estilos CSS.
                Propriedades suportadas:
                  width, height         → dimensões exatas em dp (1px CSS = 1dp Android)
                  object-fit            → cover | contain | fill | none
                  border-radius         → cantos arredondados
                  opacity               → transparência (0.0–1.0)
                  margin, margin-*      → espaçamento externo
                  border-color          → cor da borda
                  border-width          → espessura da borda
                  filter: grayscale()   → escala de cinzas
                  filter: blur()        → desfoque gaussiano
                  box-shadow            → sombra (elevation no Android)
        screen: Screen ao qual pertence (modo multi-ecrã).
        parent: Container pai ao qual pertence (para aninhamento).
        placeholder: Imagem local mostrada enquanto uma URL carrega.
        fallback: Imagem local usada quando a origem falha.
        cache: Reutiliza a imagem descarregada em memória.
        fade_in: Faz uma transição suave quando a imagem final chega.
        blur: Raio de desfoque em px/dp.
        tint: Cor aplicada sobre a imagem (ex.: ``"#7C3AED"``).
        aspect_ratio: Proporção como ``"16:9"``, ``"1:1"`` ou número.
        zoom: True makes a tap open the picture over the whole screen, where
              it can be pinched, double-tapped and dragged; Back, the cross
              and a drag down close it. It takes the place of ``command=``.
    """
    _zoom_rules.check_image(zoom, command)
    comp = _new_image_component(
        src, id,
        placeholder=placeholder, fallback=fallback, cache=cache,
        fade_in=fade_in, blur=blur, tint=tint,
        aspect_ratio=aspect_ratio,
    )
    # describe="" marca a imagem como decorativa: o leitor de ecra salta-a em
    # vez de anunciar o nome do ficheiro.
    if describe is not None:
        comp.kwargs['describe'] = str(describe)
    # command= runs when the picture is tapped, as a button's does.
    if command is not None:
        comp.kwargs['command'] = command
    if zoom:
        comp.kwargs['zoom'] = True
    if parent is not None:
        parent.children.append(comp)
        return comp
    elif screen is not None:
        return screen._add(comp)
    else:
        # Modo legado: renderiza imediatamente
        load_styles_now()
        # Cria um screen dummy para renderização imediata não é suportada em modo legado,
        # por isso mostra um placeholder de texto
        import tkinter as tk
        style = component_style(global_styles, 'image', id)
        w_val, h_val = _parse_image_size(style)
        w_px = w_val if isinstance(w_val, int) else 200
        h_px = h_val if isinstance(h_val, int) else 150
        canvas = tk.Canvas(_app.layout, width=w_px, height=h_px, bg='#e0e0e0',
                           highlightthickness=0)
        canvas.pack(pady=(4, 2))
        canvas.create_text(w_px // 2, h_px // 2, text=os.path.basename(src) or 'image',
                           font=('Arial', 10), fill='#757575')
        return None


def video(src, id=None, screen=None, parent=None, *, poster=None,
          autoplay=False, controls=True, loop=False, muted=False,
          preload=True, aspect_ratio="16:9", fit="contain",
          on_ready=None, on_progress=None, on_end=None, on_error=None):
    """Add a native video player.

    Android builds use Media3/ExoPlayer and support progressive files, HLS and
    DASH streams. The desktop Previewer decodes moving video and audio without
    blocking Tk, with synchronized play/pause, mute, speed and click/drag seek.
    All Preview dependencies are installed by the normal ``pip install apkpy``.

    ``on_progress`` receives ``(position_seconds, duration_seconds,
    buffered_percent)``. The returned component exposes ``play()``, ``pause()``,
    ``stop()``, ``seek(seconds)``, ``set_source(url, autoplay=False)``,
    ``set_speed(value)`` and ``set_muted(value)``.
    """
    ratio = _normalize_image_ratio(aspect_ratio) or (16.0 / 9.0)
    fit_value = str(fit or 'contain').strip().lower()
    if fit_value not in {'contain', 'cover', 'fill'}:
        raise ValueError("video fit must be contain, cover or fill")
    comp = ComponentDef(
        'video', src=str(src or ''), comp_id=id, poster=poster,
        autoplay=bool(autoplay), controls=bool(controls), loop=bool(loop),
        muted=bool(muted), preload=bool(preload), aspect_ratio=ratio,
        fit=fit_value, on_ready=on_ready, on_progress=on_progress,
        on_end=on_end, on_error=on_error,
    )
    if parent is not None:
        parent.children.append(comp)
        return comp
    if screen is not None:
        return screen._add(comp)
    raise ValueError("video() requires screen= or parent= in declarative apps")


def avatar(src, size=48, status=None, id=None, screen=None, parent=None, *,
           placeholder=None, fallback=None, cache=True, fade_in=True,
           blur=0, tint=None, describe=None, command=None):
    """Create a circular profile image with an optional presence badge.

    ``command`` runs when it is tapped (a story in a tray); ``describe`` is
    what a screen reader says, and ``""`` marks it as decoration."""
    try:
        size_value = max(16, int(size))
    except (TypeError, ValueError):
        raise ValueError("avatar size must be a positive integer")
    comp = _new_image_component(
        src, id,
        placeholder=placeholder, fallback=fallback, cache=cache,
        fade_in=fade_in, blur=blur, tint=tint, aspect_ratio=1.0,
        avatar_size=size_value, status=status,
    )
    if describe is not None:
        comp.kwargs['describe'] = str(describe)
    if command is not None:
        comp.kwargs['command'] = command
    if parent is not None:
        parent.children.append(comp)
        return comp
    if screen is not None:
        return screen._add(comp)
    return image(
        src, id=id, placeholder=placeholder, fallback=fallback, cache=cache,
        fade_in=fade_in, blur=blur, tint=tint, aspect_ratio="1:1",
    )

def label(text, id=None, screen=None, parent=None, variant=None):
    """
    Adiciona um texto/título à interface.

    Args:
        text:   O texto a mostrar.
        id:     ID para aplicar estilos CSS (ex: style = \"\"\"meu_label { color: red; }\"\"\").
        screen: Screen ao qual pertence (modo multi-ecrã).
        parent: Container pai ao qual pertence (para aninhamento).
    """
    variant = normalize_label_variant(variant)
    if parent is not None:
        comp = ComponentDef('label', text=text, comp_id=id, variant=variant)
        parent.children.append(comp)
        return comp
    elif screen is not None:
        # Estilos resolvidos no render (dentro de run()), não aqui
        comp = ComponentDef('label', text=text, comp_id=id, variant=variant)
        return screen._add(comp)
    else:
        # Modo legado: resolve estilos imediatamente
        load_styles_now()
        style = component_style(global_styles, 'label', id, variant=variant)
        fg    = _get_style_fg(style)
        font  = _build_tk_font(style, default_size=14)
        _app.add_label(text, fg=fg, font=font)
        return None


def button(text, id=None, command=None, screen=None, parent=None, variant=None, icon=None, describe=None):
    """
    Adiciona um botão à interface.

    Args:
        text:    O texto do botão.
        id:      ID para aplicar estilos CSS.
                 ex: style = \"\"\"meu_botao { background-color: blue; color: white; }\"\"\"
        command: Função a chamar ao clicar (modo legado sem Screen).
        screen:  Screen ao qual pertence (modo multi-ecrã).
        parent:  Container pai ao qual pertence (para aninhamento).
        variant: Variante Material 3: filled, outlined, tonal, text, danger ou icon.
        icon:    Nome de um ícone Material (ex.: "arrow_forward", "save", "delete").

    Returns:
        ComponentDef se screen ou parent for definido — usa-o em on_click_navigate().
    """
    variant = normalize_button_variant(variant)
    if parent is not None:
        comp = ComponentDef('button', text=text, command=command, comp_id=id,
                            variant=variant, icon=icon, describe=describe)
        parent.children.append(comp)
        return comp
    elif screen is not None:
        # Estilos resolvidos no render (dentro de run()), não aqui
        comp = ComponentDef('button', text=text, command=command, comp_id=id,
                            variant=variant, icon=icon, describe=describe)
        return screen._add(comp)
    else:
        # Modo legado: resolve estilos imediatamente
        load_styles_now()
        style      = component_style(global_styles, 'button', id, variant=variant)
        bg         = _get_style_bg(style)
        fg         = _get_style_fg(style)
        pressed_bg = _get_style_pressed_color(style)
        radius     = _parse_radius(style)
        bc         = _get_style_border_color(style)
        bw         = _parse_border_width(style)
        font       = _build_tk_font(style, default_size=11)
        display = _material_button_text(text, icon, variant)
        _app.add_button(display, command, bg, fg, radius=radius, border_color=bc,
                        border_width=bw, pressed_color=pressed_bg, font=font,
                        compact=(variant == 'icon'), icon=icon)
        return None


def _widget_has_focus(widget):
    try:
        return widget.focus_get() is widget
    except Exception:
        return False


def validate(*fields):
    """Check every field given and say whether they all passed::

        def send():
            if not validate(name, email):
                return

    Each field with ``required=`` that is empty shows its error -- all of
    them at once, not one a tap -- and the first one takes the cursor."""
    for field in fields:
        if not isinstance(field, ComponentDef):
            _field_rules.refuse('validate() takes the fields to check.',
                                'validate(%r)' % (field,))
        _field_rules.check_type(field.kwargs.get('input_type', 'text')
                                if field.comp_type == 'inputs' else field.comp_type)
    return _field_feature.validate_all(fields)


def inputs(placeholder="", id=None, type="text", screen=None, parent=None, on_change=None,
           help=None, error=None, required=False):
    """
    Adiciona um campo de input à interface.

    Tipos suportados:
      - "text"      → caixa de texto normal
      - "password"  → texto escondido com ●●●
      - "search"    → caixa de texto com botão ✕ para limpar
      - "checkbox"  → caixinha com visto (✓)
      - "switch"    → interruptor com o texto à esquerda (definições)
      - "range"     → slider/barra deslizante (0-100)
      - "radio"     → botões de escolha; separa opções com | no placeholder
                      ex: inputs("Sim|Não|Talvez", type="radio")

    Args:
        id:        ID para aplicar estilos CSS.
                   Suporta 'background-color' e 'backgroundcolor' (sem hífen).
        screen:    Screen ao qual pertence (modo multi-ecrã).
        parent:    Container pai ao qual pertence (para aninhamento).
        on_change: Callback chamado com o texto a cada tecla (pesquisa em tempo
                   real). Ex: inputs("Procurar", on_change=lambda q: filtrar(q)).
                   Num switch ou checkbox recebe "true"/"false", num range o
                   número como texto, sempre que o valor muda com o ecrã à
                   vista -- não pelo valor com que o ecrã abre.
        help:      Words under a text field, in the secondary text colour:
                   what to type, or why you ask.
        error:     Words under the field in the theme's error colour, in
                   place of the help; the field's line turns the same
                   colour. Usually set later with ``field.set_error(text)``
                   and cleared with ``field.set_error("")`` -- typing in the
                   field clears it too.
        required:  True, or the words to show when the field is empty
                   (``required="Enter your name"``). ``validate(a, b)`` and
                   ``field.validate()`` check it.
    """
    _field = {}
    _help = _field_rules.words(help, 'help')
    _error = _field_rules.words(error, 'error')
    _required = _field_rules.required_message(required)
    if _field_rules.wanted(_help, _error, _required):
        _field_rules.check_type(type)
        _field = {'help': _help, 'error': _error, 'required_message': _required}
    if parent is not None:
        comp = ComponentDef('inputs', placeholder=placeholder, input_type=type, comp_id=id, on_change=on_change, **_field)
        parent.children.append(comp)
        return comp
    elif screen is not None:
        # Estilos resolvidos no render (dentro de run()), não aqui
        comp = ComponentDef('inputs', placeholder=placeholder, input_type=type, comp_id=id, on_change=on_change, **_field)
        return screen._add(comp)
    else:
        # Modo legado: resolve estilos imediatamente
        load_styles_now()
        style  = component_style(global_styles, 'inputs', id)
        bg     = _get_style_bg(style)
        fg     = _get_style_fg(style)
        radius = _parse_radius(style)
        bc     = _get_style_border_color(style)
        bw     = _parse_border_width(style)
        fc     = _get_style_focus_border_color(style)
        font   = _build_tk_font(style, default_size=13)
        _app.add_input(placeholder=placeholder, input_type=type, bg=bg, fg=fg, radius=radius, border_color=bc, border_width=bw, focus_border_color=fc, font=font, accent_color=input_accent_color(global_styles, id))
        return None


# Alias para quem preferir este nome
input_field = inputs


def list_view(items=None, id=None, screen=None, parent=None, on_click=None, rich=False):
    """
    Cria uma lista scrollable de itens.

    Args:
        items:    Lista de strings ou dicts com 'title' e 'subtitle' opcionais.
                  Ex: ["Nota 1", "Nota 2"]
                  Ex: [{"title": "Nota 1", "subtitle": "Conteúdo..."}]
        id:       ID para aplicar estilos CSS.
                  Suporta: background-color, color, border-color, height (altura da lista em px).
        screen:   Screen ao qual pertence.
        parent:   Container ao qual pertence (alternativa a screen).
        on_click: Callback chamado com o item clicado (string ou dict).

    Métodos no objeto devolvido:
        .set_items(new_items) — atualiza a lista dinamicamente.

    Exemplo::

        tasks = list_view([], id="tasks", screen=home, on_click=lambda item: delete(item))
        tasks.set_items(["Compras", "Reunião", "Ginásio"])
    """
    if items is None:
        items = []
    if parent is not None:
        comp = ComponentDef('list', items=list(items), on_click=on_click,
                            comp_id=id, rich=bool(rich))
        parent.children.append(comp)
        return comp
    if screen is not None:
        comp = ComponentDef('list', items=list(items), on_click=on_click,
                            comp_id=id, rich=bool(rich))
        return screen._add(comp)
    return None


def _reject_unknown_slots(slots, known, variant_name=None):
    """A slot name the row does not draw is a silent no-op otherwise."""
    import difflib

    unknown = [key for key in slots if key not in known]
    if not unknown:
        return
    name = sorted(unknown)[0]
    close = difflib.get_close_matches(name, sorted(known), 1, 0.7)
    where = (' in variant %r' % variant_name) if variant_name else ''
    raise ValueError(
        'virtual_collection(template=...) has no slot %r%s. %sThe slots are: '
        '%s.' % (
            name, where,
            ('Did you mean %s? ' % close[0]) if close else '',
            ', '.join(sorted(known)),
        )
    )


def virtual_collection(items=None, template=None, id=None, screen=None, parent=None,
                       on_click=None, layout="list", columns=2,
                       item_height=None, buffer=2, on_end_reached=None,
                       on_refresh=None, prefetch=4, variant=None, row=None,
                       swipe_right=None, swipe_left=None, reorder=False,
                       on_reorder=None):
    """Virtualized list/grid with a reusable custom item template.

    Only the rows visible in the viewport are materialized in the Previewer.
    Android compiles this component to ``RecyclerView`` so ViewHolders are
    recycled instead of allocating one View tree per item.

    ``template`` maps visual slots to item fields using ``{field}`` tokens::

        tracks = virtual_collection(
            TRACKS,
            template={
                "image": "{cover}",
                "title": "{name}",
                "subtitle": "{artist} · {album}",
                "meta": "{duration}",
                "badge": "{quality}",
            },
            screen=home,
            on_click=lambda item: toast(item["name"]),
        )

    Supported slots are ``title``, ``subtitle``, ``image``, ``meta`` and
    ``badge``. ``layout`` can be ``"list"`` or ``"grid"``.

    ``row=`` builds each row from components instead of the fixed slots::

        def post_row(row):
            head = container(id="post_head", parent=row)
            avatar("{face}", size=34, parent=head, describe="{user}")
            label("{user}", id="post_user", parent=head)
            image("{picture}", id="post_pic", parent=row, aspect_ratio="1:1")
            button("", icon="favorite_border", describe="Like", parent=row,
                   command=lambda item: like(item))

        feed = virtual_collection(POSTS, row=post_row, id="feed", screen=home)

    The function is called once, with the row as its only argument; what it
    builds is the template. ``{field}`` in a text, a picture's source or a
    description is filled from each item, and a ``command`` that takes an
    argument receives the row's item. The row itself is styled as
    ``<id>_row``. Rows take the height of what they hold.

    ``on_end_reached`` runs once when the viewport enters the last ``prefetch``
    items. Complete it with ``append_items(...)`` or ``finish_load(...)``.
    ``on_refresh`` powers pull-to-refresh and can also be started with
    ``refresh()``. ``set_items(...)`` replaces the data and completes refresh.

    Rows can be swiped and dragged (a list, not a grid)::

        inbox = virtual_collection(
            MAIL, row=mail_row, id="inbox", screen=home,
            swipe_right=swipe("archive", "Archive", on_swipe=archive, undo="Archived"),
            swipe_left=swipe("delete", "Delete", on_swipe=delete),
            on_reorder=moved)

    ``swipe_right`` is the finger moving right, with the action shown at the
    left edge. The row leaves the list and ``on_swipe(item)`` runs; with
    ``undo=`` a snackbar offers to bring it back first, and ``on_swipe`` only
    runs once the chance has passed. ``keep=True`` slides the row back
    instead (mark as read). ``on_reorder(item, index)`` runs when a row
    lifted by a long press is dropped at a new place; ``reorder=True`` alone
    lets people reorder without telling you. Every swipe and every move is
    also an action TalkBack offers on the row -- nobody needs the gesture.
    """
    if items is None:
        items = []
    gestures = _collection_gestures(layout, swipe_right, swipe_left, reorder, on_reorder)
    row_template = None
    if row is not None:
        if not callable(row):
            raise TypeError(
                "virtual_collection(row=...) takes a function that builds one "
                "row, like def post_row(row): label('{title}', parent=row)")
        if template is not None:
            raise ValueError(
                "virtual_collection() takes template= or row=, not both: row= "
                "builds the whole row from components")
        row_template = ComponentDef('container', comp_id=('%s_row' % id) if id else None)
        row_template._apkpy_row_template = True
        row(row_template)
        if item_height is None:
            item_height = "auto"
    normalized_layout = str(layout or "list").strip().lower()
    if normalized_layout not in ("list", "grid"):
        raise ValueError('virtual_collection(layout=...) must be "list" or "grid"')
    try:
        column_count = max(1, int(columns))
    except (TypeError, ValueError):
        raise ValueError("virtual_collection(columns=...) must be a positive integer")
    if normalized_layout == "list":
        column_count = 1
    default_extent = 88 if normalized_layout == "list" else 224
    # `item_height="auto"` deixa cada linha tomar o que precisa. Um numero
    # continua a fixar todas, byte a byte como antes -- uma conversa nao pode
    # dar a mesma altura a "sim" e a uma funcao em Python, e uma grelha de
    # capas nao quer que uma legenda comprida entorte a grelha.
    auto_extent = isinstance(item_height, str) and item_height.strip().lower() == "auto"
    if auto_extent:
        extent = default_extent          # a estimativa por onde o scroll comeca
    else:
        try:
            extent = max(56, int(item_height or default_extent))
        except (TypeError, ValueError):
            raise ValueError(
                'virtual_collection(item_height=...) must be an integer '
                'or "auto"'
            )
    try:
        overscan = max(1, min(8, int(buffer)))
    except (TypeError, ValueError):
        raise ValueError("virtual_collection(buffer=...) must be an integer")
    try:
        prefetch_count = max(0, min(100, int(prefetch)))
    except (TypeError, ValueError):
        raise ValueError("virtual_collection(prefetch=...) must be an integer")

    default_template = {
        "title": "{title}",
        "subtitle": "{subtitle}",
        # A fatia que desenha Markdown a serio: titulos, listas, enfase e
        # blocos de codigo com fence. E' o que separa uma resposta de um
        # assistente de um paragrafo de texto cru com crases pelo meio.
        "markdown": "",
        # Um circulo com as iniciais de quem fala, com a cor tirada do nome.
        # A mesma tabela que o Java recebe, para que Ora seja a mesma cor no
        # telemovel e no ambiente de trabalho.
        "avatar": "",
        "image": "{image}",
        "meta": "{meta}",
        "badge": "{badge}",
    }
    row_variants = {}
    if variant is not None:
        # With ``variant=`` the template is keyed by the value that field
        # takes, so one collection can hold two shapes of row -- which is the
        # difference between a chat and a list of paragraphs.
        if not isinstance(template, dict) or not template:
            raise ValueError(
                'virtual_collection(variant=...) needs template={"name": '
                '{slot: ...}, ...}, one entry per value the field can take'
            )
        for name, slots in template.items():
            if not isinstance(slots, dict):
                raise ValueError(
                    'virtual_collection(template=...) with variant=%r must map '
                    'every name to a dict of slots; %r is not one'
                    % (variant, name)
                )
            _reject_unknown_slots(slots, default_template, name)
            row_variants[str(name)] = {
                key: str(slots.get(key, '')) for key in default_template
            }
        # The union decides which slots exist at all. A row that does not use
        # one hides it, exactly as an empty format string already did.
        item_template = {
            key: next(
                (shape[key] for shape in row_variants.values() if shape[key]),
                '',
            )
            for key in default_template
        }
    elif row_template is not None:
        # No slots at all: the components are the row.
        item_template = {key: "" for key in default_template}
    elif template is not None:
        if not isinstance(template, dict):
            raise TypeError("virtual_collection(template=...) must be a dict")
        _reject_unknown_slots(template, default_template)
        # A custom template is declarative: an omitted slot must not reserve
        # space in either the Previewer or the generated RecyclerView row.
        item_template = {key: "" for key in default_template}
        for key in default_template:
            if key in template:
                item_template[key] = str(template[key])
    else:
        item_template = dict(default_template)

    comp = ComponentDef(
        'virtual_collection',
        items=list(items),
        template=item_template,
        variant=(str(variant) if variant is not None else None),
        variants=row_variants,
        on_click=on_click,
        comp_id=id,
        layout=normalized_layout,
        columns=column_count,
        item_height=extent,
        auto_height=auto_extent,
        buffer=overscan,
        on_end_reached=on_end_reached,
        on_refresh=on_refresh,
        prefetch=prefetch_count,
        row_template=row_template,
        **gestures,
    )
    if parent is not None:
        parent.children.append(comp)
        return comp
    if screen is not None:
        return screen._add(comp)
    return None


class SwipeAction(dict):
    """What one swipe does to a row: made by ``swipe()``, given to a list."""


def swipe(icon, text, on_swipe=None, color=None, keep=False, undo=None):
    """An action a row of a ``virtual_collection`` reveals when it is swiped.

        swipe("archive", "Archive", on_swipe=archive, undo="Archived")
        swipe("delete", "Delete", on_swipe=delete)
        swipe("mark_email_read", "Read", on_swipe=mark_read, keep=True)

    Args:
        icon:     A Material icon, drawn in white on the strip.
        text:     The words next to it -- and what TalkBack offers on the row.
        on_swipe: Called with the row's item once the swipe is done.
        color:    The strip's colour. By default an icon that takes something
                  away (delete, block, close...) is red and the rest take the
                  theme's primary colour.
        keep:     True slides the row back instead of taking it away.
        undo:     A message; a snackbar shows it with Undo, the row comes back
                  if it is pressed, and ``on_swipe`` only runs if it is not.
    """
    if not str(icon or '').strip():
        raise ValueError('swipe() needs an icon, like swipe("archive", "Archive", ...)')
    if on_swipe is not None and not callable(on_swipe):
        raise TypeError('swipe(on_swipe=...) takes a function that receives the item')
    return SwipeAction(
        icon=str(icon).strip(), text=str(text or '').strip(), on_swipe=on_swipe,
        color=(str(color) if color else None), keep=bool(keep),
        undo=(str(undo) if undo not in (None, '', False) else None),
    )


def _collection_gestures(layout, swipe_right, swipe_left, reorder, on_reorder):
    """Check what a list was asked to do under a finger, and keep it."""
    for name, value in (('swipe_right', swipe_right), ('swipe_left', swipe_left)):
        if value is not None and not isinstance(value, SwipeAction):
            raise TypeError(
                'virtual_collection(%s=...) takes swipe(icon, text, on_swipe=...), '
                'not %r' % (name, type(value).__name__))
    if on_reorder is not None and not callable(on_reorder):
        raise TypeError(
            'virtual_collection(on_reorder=...) takes a function that receives '
            'the item and its new position')
    wants_reorder = bool(reorder) or on_reorder is not None
    wants_gesture = bool(swipe_right or swipe_left or wants_reorder)
    if wants_gesture and str(layout or 'list').strip().lower() != 'list':
        raise ValueError(
            'swiping and reordering are for a list: virtual_collection('
            'layout="grid") keeps its rows where they are')
    return {
        'swipe_right': swipe_right, 'swipe_left': swipe_left,
        'reorder': wants_reorder, 'on_reorder': on_reorder,
    }


def carousel(items=None, id=None, screen=None, parent=None, on_click=None):
    """
    Carrossel HORIZONTAL — prateleira de cartões (capa + título + subtítulo) que
    desliza para o lado, estilo "Tocados recentemente" do Spotify.

    Args:
        items:    Lista de dicts com 'title', 'subtitle', 'image' (capa) e, opcional,
                  'src' (áudio). Ex: [{"title": "Faixa", "subtitle": "Artista",
                  "image": "https://.../capa.jpg", "src": "https://.../faixa.mp3"}]
        id:       ID para estilos CSS (color, background-color).
        screen:   Screen ao qual pertence.
        on_click: Callback chamado com o item (dict) clicado.

    No Android gera um HorizontalScrollView com os cartões; a capa carrega async.
    """
    if items is None:
        items = []
    if parent is not None:
        comp = ComponentDef('carousel', items=list(items), on_click=on_click, comp_id=id)
        parent.children.append(comp)
        return comp
    if screen is not None:
        comp = ComponentDef('carousel', items=list(items), on_click=on_click, comp_id=id)
        return screen._add(comp)
    return None


def grid(items=None, id=None, screen=None, parent=None, on_click=None, cols=2):
    """
    Grelha de cartões (capa + título + subtítulo) em N colunas — estilo a página
    "Pesquisar" do Spotify (cartões de género/categoria numa grelha).

    Args:
        items:    Lista de dicts com 'title', 'subtitle', 'image' (capa) e, opcional,
                  'src'. Ex: [{"title": "Pop", "subtitle": "...", "image": "https://.../x.jpg"}]
        id:       ID para estilos CSS (color, background-color).
        screen:   Screen ao qual pertence.
        parent:   Container ao qual pertence (alternativa a screen).
        on_click: Callback chamado com o item (dict) clicado.
        cols:     Número de colunas (default 2).

    No Android gera um GridLayout; cada cartão ocupa uma célula e a capa carrega async.
    """
    if items is None:
        items = []
    if parent is not None:
        comp = ComponentDef('grid', items=list(items), on_click=on_click, comp_id=id, cols=cols)
        parent.children.append(comp)
        return comp
    if screen is not None:
        comp = ComponentDef('grid', items=list(items), on_click=on_click, comp_id=id, cols=cols)
        return screen._add(comp)
    return None


def skeleton(variant="music_card", count=1, id=None, screen=None, parent=None,
             visible=True):
    """Animated loading placeholder with no per-frame widget allocation.

    Variants: ``music_card``, ``list``, ``card`` and ``text``. Use ``show()``
    and ``hide()`` to switch it together with the final content/state.
    """
    normalized = normalize_skeleton_variant(variant)
    try:
        item_count = max(1, int(count))
    except (TypeError, ValueError):
        raise ValueError("skeleton(count=...) must be a positive integer")
    comp = ComponentDef(
        'skeleton', comp_id=id, variant=normalized,
        count=item_count, visible=bool(visible),
    )
    if parent is not None:
        parent.children.append(comp)
    elif screen is not None:
        screen._add(comp)
    return comp


def _state_action(action, command, default_text, default_icon):
    if isinstance(action, ComponentDef):
        if action.comp_type != 'button':
            raise TypeError("state actions must be buttons")
        return action
    if action is None and command is None:
        return None
    if isinstance(action, dict):
        return card_action(
            action.get('text', default_text),
            variant=action.get('variant', 'filled'),
            command=action.get('command', command),
            icon=action.get('icon', default_icon), id=action.get('id'),
        )
    if isinstance(action, (tuple, list)):
        text = action[0] if action else default_text
        callback = action[1] if len(action) > 1 else command
        return card_action(text, variant='filled', command=callback, icon=default_icon)
    return card_action(
        str(action or default_text), variant='filled',
        command=command, icon=default_icon,
    )


def empty_state(title, message="", icon="inbox", action=None, on_action=None,
                id=None, screen=None, parent=None, visible=True):
    """Centered empty-content state with an optional primary action."""
    comp = ComponentDef(
        'empty_state', title=str(title), message=str(message or ''),
        icon=str(icon or 'inbox'), comp_id=id, visible=bool(visible),
    )
    action_comp = _state_action(action, on_action, 'Explore', 'arrow_forward')
    if action_comp is not None:
        comp.children.append(action_comp)
    if parent is not None:
        parent.children.append(comp)
    elif screen is not None:
        screen._add(comp)
    return comp


def error_state(title, message="", retry=None, retry_text="Try again",
                icon="error_outline", id=None, screen=None, parent=None,
                visible=True):
    """Centered error state with an optional retry callback."""
    comp = ComponentDef(
        'error_state', title=str(title), message=str(message or ''),
        icon=str(icon or 'error_outline'), comp_id=id, visible=bool(visible),
    )
    if retry is not None:
        comp.children.append(card_action(
            str(retry_text), variant='filled', command=retry, icon='refresh',
            id=f'{id}_retry' if id else None,
        ))
    if parent is not None:
        parent.children.append(comp)
    elif screen is not None:
        screen._add(comp)
    return comp


def spinner(id=None, screen=None, parent=None, visible=True):
    """
    Indicador de loading circular (spinner) animado.

    Ideal para mostrar enquanto fazes `https.get()`, `db.query()` ou trabalho
    em segundo plano. Controla a visibilidade com `.show()` e `.hide()`.

    Args:
        id:      ID para estilos CSS. Suporta `color` (cor do arco) e
                 `width`/`height` (tamanho em px).
        screen:  Screen ao qual pertence.
        parent:  Container pai (para aninhamento).
        visible: Se começa visível (`True`, por omissão) ou escondido (`False`).

    Métodos no objeto devolvido:
        .show() — mostra o spinner e começa a rodar.
        .hide() — esconde o spinner e pára a animação.

    Exemplo::

        spin = spinner(id="loader", screen=home, visible=False)

        def fetch():
            spin.show()
            https.get(url, on_response=done)

        def done(ok, resp):
            spin.hide()
    """
    comp = ComponentDef('spinner', comp_id=id, visible=bool(visible))
    if parent is not None:
        parent.children.append(comp)
        return comp
    elif screen is not None:
        return screen._add(comp)
    return None


_sheet_ids = [0]


def bottom_sheet(title="", content="", items=None, on_select=None, close_text="Close",
                 id=None, screen=None, on_close=None):
    """A sheet that slides up over the current screen and can be dragged
    back down.

    Plain: a title, text and ``items`` -- selecting one calls
    ``on_select(value)`` and closes the sheet::

        sort = bottom_sheet("Sort by", items=["Newest", "Price"], on_select=apply)

    With components: give it the screen it opens over and put components
    in it with ``parent=``, as in a container::

        filters = bottom_sheet("Filters", screen=home)
        chips(["Newest", "Price"], selected="Newest", required=True, parent=filters)
        button("Apply", command=filters.close, parent=filters)

    ``open()`` shows it and ``close()`` hides it; dragging it down, a tap
    outside it and Back close it too, and ``on_close`` is called whichever
    way it went. The body is a column with 24 at the sides and 12 between
    components; CSS on the sheet's ``id`` changes that and its background.
    The definition occupies no layout space until ``open``.
    """
    composed = _sheet_rules.is_composed(screen)
    _sheet_rules.check_plain_arguments(composed, items)
    if composed and not id:
        _sheet_ids[0] += 1
        id = 'apkpy_sheet_%d' % _sheet_ids[0]
    return OverlayDef(
        'bottom_sheet', title=str(title or ''), content=str(content or ''),
        items=[str(item) for item in (items or [])], on_select=on_select,
        close_text=str(close_text), comp_id=id, composed=composed,
        screen=screen, on_close=on_close,
    )


def modal(title, content="", confirm_text="Confirm", cancel_text="Cancel",
          on_confirm=None, on_cancel=None, id=None, dismissable=True):
    """Create a modal Material dialog with optional confirm/cancel callbacks.

    ``dismissable=False`` makes it a wall rather than a dialog: the back
    button, a tap outside and the cancel button all stop working, so the
    person cannot get past it. That is what a forced update needs and what
    nothing else should use -- a dialog somebody cannot escape is a bug in
    every other situation.
    """
    return OverlayDef(
        'modal', title=str(title), content=str(content or ''),
        confirm_text=str(confirm_text), cancel_text=str(cancel_text),
        on_confirm=on_confirm, on_cancel=on_cancel, comp_id=id,
        dismissable=bool(dismissable),
    )


def menu(anchor=None, items=None, on_select=None, id=None):
    """Attach a compact popup menu to ``anchor`` and return its definition."""
    overlay = OverlayDef(
        'menu', anchor=anchor, items=[str(item) for item in (items or [])],
        on_select=on_select, comp_id=id,
    )
    if isinstance(anchor, ComponentDef):
        anchor.kwargs['popup_menu'] = overlay
    return overlay


def popup_menu(anchor=None, items=None, on_select=None, id=None):
    """Explicit alias for :func:`menu`."""
    return menu(anchor=anchor, items=items, on_select=on_select, id=id)


def context_menu(target, items=None, on_select=None, id=None):
    """Attach a right-click/long-press menu to a component."""
    overlay = OverlayDef(
        'context_menu', anchor=target,
        items=[str(item) for item in (items or [])],
        on_select=on_select, comp_id=id,
    )
    if not isinstance(target, ComponentDef):
        raise TypeError("context_menu(target=...) expects an ApkPy component")
    target.kwargs['context_menu'] = overlay
    return overlay


def tooltip(target, text):
    """Attach accessible hover/long-press help to an existing component."""
    if not isinstance(target, ComponentDef):
        raise TypeError("tooltip(target, text) expects an ApkPy component")
    target.kwargs['tooltip'] = str(text)
    return target


def date_picker(title="Select date", initial=None, on_select=None, id=None):
    """Create a date picker; ``on_select`` receives ``YYYY-MM-DD``."""
    return OverlayDef(
        'date_picker', title=str(title), initial=str(initial or ''),
        on_select=on_select, comp_id=id,
    )


def time_picker(title="Select time", initial=None, on_select=None, id=None):
    """Create a time picker; ``on_select`` receives ``HH:MM``."""
    return OverlayDef(
        'time_picker', title=str(title), initial=str(initial or ''),
        on_select=on_select, comp_id=id,
    )


def snackbar(message, action=None, on_action=None, duration=3000):
    """Show a transient message above the current screen chrome."""
    _job_rules.guard("dialog", "snackbar()")
    _show_snackbar_preview(
        str(message), action=str(action) if action is not None else None,
        on_action=on_action, duration=max(500, int(duration)),
    )


def _orientation_written(orientation, where):
    """``orientation=`` of a Screen or of run(): one of the three words, or
    None for nothing said. Refused in the build's own words otherwise."""
    if orientation is None:
        return None
    from . import kit_rules as _kit_rules
    label = "%s(orientation=)" % where
    kind = _kit_rules.display_orientation(orientation) if isinstance(orientation, str) else ""
    if not kind:
        _kit_rules.refuse(docs=_kit_rules.DOCS_OF["display"],
                          **_kit_rules.display_wrong_orientation(label, orientation))
    return kind


# run(orientation=): which way up the screens that say nothing are.
_app_orientation = None


def run(start_screen=None, theme=None, orientation=None):
    """
    Inicia a janela de preview.

    Args:
        start_screen: Screen inicial a mostrar (modo multi-ecrã).
                      Se None, mostra os componentes adicionados diretamente
                      (modo legado compatível).
        orientation: "portrait", "landscape" or "auto" for every screen that
                      does not say which way up it is itself.
    """
    global _active_theme, _app_orientation
    if theme is not None and not isinstance(theme, Theme):
        raise TypeError("run(theme=...) expects an apkpy_lib.Theme instance")
    _app_orientation = _orientation_written(orientation, "run")
    _active_theme = theme
    _declared_theme[0] = theme
    load_styles_now()
    # The app opens the way it was left, which is what the generated
    # onCreate does with the same stored key before the first inflate.
    if theme is not None:
        _stored = storage.get(AppearanceAPI._KEY, "")
        if _stored in APPEARANCE_MODES:
            _apply_appearance(_stored)
    _apply_preview_device()
    if start_screen is not None:
        _app.render_screen(start_screen)
    audio._start_ctrl_poll()   # botões de estado (audio.controls), se houver
    from .features.jobs import start_preview_pump
    start_preview_pump()       # entrega de observers de background_job na UI thread
    try:
        _app.run()
    except KeyboardInterrupt:
        pass
    finally:
        from .websocket import websocket
        websocket.close_all()


def _apply_preview_device():
    """Aplica a escolha de device() à janela do preview. Tem de correr ANTES do
    render_screen (a coluna centrada do fullscreen depende de _content_width).
    Usa a instância REAL (_app._get()) — escrever em _app (o wrapper lazy) não
    chegava à AppPreview, porque o wrapper não tem __setattr__ que delegue."""
    app = _app._get()
    if _preview_device in ("responsive", "responsivo"):
        app.root.resizable(True, True)
        app.root.geometry("900x700")
        app._content_width = None
        app._last_responsive_size = None
        app._upright = None                # the window is the person's to shape

        def _rerender_on_resize(event=None):
            if event is not None and event.widget is not app.root:
                return
            size = (app.root.winfo_width(), app.root.winfo_height())
            if size == app._last_responsive_size:
                return
            app._last_responsive_size = size
            pending = getattr(app, '_responsive_after', None)
            if pending:
                app.root.after_cancel(pending)
            if app._active_screen is not None:
                app._responsive_after = app.root.after(
                    140, lambda: app.render_screen(app._active_screen)
                )
        app.root.bind('<Configure>', _rerender_on_resize, add='+')
    elif _preview_device == "fullscreen":
        app.root.attributes("-fullscreen", True)
        # Esc sai do fullscreen (conveniência no desktop)
        app.root.bind("<Escape>", lambda e: app.root.attributes("-fullscreen", False))
        app._content_width = 411           # largura de telemóvel, centrada
        app._upright = None
    elif _preview_device in ("maximized", "maximizado"):
        # Maximiza MAS mantém a barra de título padrão (com o X para fechar).
        # resizable(True) é ESSENCIAL: com a janela fixa (resizable False, o
        # default do preview), o Windows desativa o botão restaurar/maximizar e
        # não dá para voltar ao tamanho normal nem arrastar para sair.
        app.root.resizable(True, True)
        try:
            app.root.state("zoomed")              # Windows (e macOS)
        except Exception:
            app.root.attributes("-zoomed", True)  # fallback em alguns Linux
        app._content_width = 411           # largura de telemóvel, centrada
        app._upright = None
    elif _preview_device:
        w, h = _PREVIEW_DEVICES_NORM[_preview_device]
        app.root.geometry(f"{w}x{h}")
        app._content_width = None
        # "Pixel 9 Landscape" is a Pixel 9 already turned on its side.
        app._upright = (min(w, h), max(w, h))
        app._turned = w > h
        app._shape = (w, h)
    # default (None): mantém os 411x914 definidos no AppPreview.__init__

_active_preview_overlay = None
_active_snackbar = None
_active_toast = None


def _overlay_palette(overlay_type, comp_id=None):
    tokens = global_styles.get('__theme__', {})
    style = component_style(global_styles, overlay_type, comp_id)
    return {
        'surface': _get_style_bg(style) or tokens.get('surface', '#1C1B1F'),
        'text': _get_style_fg(style) or tokens.get('text', '#F5EFF7'),
        'muted': tokens.get('text_secondary', '#CAC4D0'),
        'primary': tokens.get('primary', '#D0BCFF'),
        'on_primary': tokens.get('on_primary', '#381E72'),
        'border': tokens.get('border', '#49454F'),
        'scrim': '#101014',
    }


def _overlay_callback(callback, *args):
    if callback:
        try:
            callback(*args)
        except Exception as exc:
            report_exception(exc, context="Previewer overlay callback")


def _show_overlay_preview(overlay, anchor_widget=None):
    """Material-like overlay renderer used by every Previewer overlay API."""
    global _active_preview_overlay
    if not isinstance(overlay, OverlayDef):
        return
    if _active_preview_overlay is not None:
        _active_preview_overlay.close()
    _active_preview_overlay = overlay

    root = _app.root
    root.update_idletasks()
    kind = overlay.overlay_type
    data = overlay.kwargs
    palette = _overlay_palette(kind, data.get('comp_id'))

    if kind in ('menu', 'context_menu'):
        items = data.get('items') or []
        width = 190
        height = max(44, 12 + 42 * len(items))
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.configure(bg=palette['border'])
        win.attributes('-topmost', True)
        anchor_widget = anchor_widget or getattr(data.get('anchor'), 'widget', None)
        if anchor_widget is not None:
            x = anchor_widget.winfo_rootx()
            y = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4
        else:
            x = root.winfo_rootx() + root.winfo_width() - width - 16
            y = root.winfo_rooty() + 80
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = max(4, min(x, screen_w - width - 4))
        y = max(4, min(y, screen_h - height - 4))
        win.geometry(f'{width}x{height}+{x}+{y}')
        inner = tk.Frame(win, bg=palette['surface'], padx=6, pady=6)
        inner.pack(fill='both', expand=True, padx=1, pady=1)

        def _choose(value):
            overlay.close()
            _overlay_callback(data.get('on_select'), value)

        for item in items:
            tk.Button(
                inner, text=str(item), command=lambda value=item: _choose(value),
                bg=palette['surface'], fg=palette['text'], activebackground=palette['border'],
                activeforeground=palette['text'], relief='flat', bd=0, anchor='w',
                font=('Segoe UI', 10) if os.name == 'nt' else ('Helvetica', 10),
                padx=12, pady=8,
            ).pack(fill='x')
        win.bind('<Escape>', lambda _e: overlay.close())
        win.bind('<FocusOut>', lambda _e: root.after(120, overlay.close))
        win.after_idle(win.focus_force)
        overlay.widget = win
        return

    def _close(_event=None):
        overlay.close()

    if kind == 'bottom_sheet':
        # A normal Frame cannot be translucent in Tk, so the sheet is two
        # windows over the app: a translucent scrim and the sheet itself.
        # The current screen stays visible underneath, as under Android's
        # Material bottom sheet.
        _sheet_feature.show(overlay)
        return

    host = tk.Frame(root, bg=palette['scrim'])
    host.place(x=0, y=0, relwidth=1, relheight=1)
    host.lift()
    overlay.widget = host

    # dismissable=False e uma parede, nao um dialogo: sem Escape, sem Cancel.
    # O Android faz o mesmo com setCancelable(false), e uma actualizacao
    # obrigatoria que se fecha com Escape no desktop nao esta a ser ensaiada.
    _dismissable = data.get('dismissable', True) is not False
    if _dismissable:
        host.bind('<Escape>', _close)
    host.focus_set()

    panel = tk.Frame(
        host, bg=palette['surface'], highlightthickness=1,
        highlightbackground=palette['border'], padx=22, pady=20,
    )
    panel.place(relx=.5, rely=.5, anchor='center', relwidth=.86)
    tk.Label(
        panel, text=data.get('title', ''), bg=palette['surface'], fg=palette['text'],
        font=('Segoe UI', 16, 'bold') if os.name == 'nt' else ('Helvetica', 16, 'bold'),
        anchor='w',
    ).pack(fill='x')

    if kind == 'modal':
        tk.Label(
            panel, text=data.get('content', ''), bg=palette['surface'], fg=palette['muted'],
            wraplength=max(220, root.winfo_width() - 100), justify='left', anchor='w',
            font=('Segoe UI', 10) if os.name == 'nt' else ('Helvetica', 10),
        ).pack(fill='x', pady=(10, 18))
        actions = tk.Frame(panel, bg=palette['surface'])
        actions.pack(fill='x')

        def _modal_action(callback):
            overlay.close()
            _overlay_callback(callback)

        tk.Button(
            actions, text=data.get('confirm_text', 'Confirm'),
            command=lambda: _modal_action(data.get('on_confirm')),
            bg=palette['primary'], fg=palette['on_primary'], relief='flat', bd=0,
            padx=14, pady=8,
            font=('Segoe UI', 10, 'bold') if os.name == 'nt' else ('Helvetica', 10, 'bold'),
        ).pack(side='right', padx=(8, 0))
        if _dismissable:
            # Um Cancel num ecra de onde nao se pode sair e um botao que nao
            # faz nada, e ninguem acredita no botao seguinte.
            tk.Button(
                actions, text=data.get('cancel_text', 'Cancel'),
                command=lambda: _modal_action(data.get('on_cancel')),
                bg=palette['surface'], fg=palette['primary'], relief='flat', bd=0,
                padx=14, pady=8,
            ).pack(side='right')
        return

    now = _pydatetime.datetime.now()
    if kind == 'date_picker':
        try:
            initial = _pydatetime.datetime.strptime(data.get('initial', ''), '%Y-%m-%d')
        except Exception:
            initial = now
        values = [
            tk.StringVar(value=f'{initial.year:04d}'),
            tk.StringVar(value=f'{initial.month:02d}'),
            tk.StringVar(value=f'{initial.day:02d}'),
        ]
        ranges = [(2000, 2100), (1, 12), (1, 31)]
    else:
        try:
            initial = _pydatetime.datetime.strptime(data.get('initial', ''), '%H:%M')
        except Exception:
            initial = now
        values = [tk.StringVar(value=f'{initial.hour:02d}'), tk.StringVar(value=f'{initial.minute:02d}')]
        ranges = [(0, 23), (0, 59)]

    fields = tk.Frame(panel, bg=palette['surface'])
    fields.pack(pady=(18, 20))
    for index, ((start, end), var) in enumerate(zip(ranges, values)):
        tk.Spinbox(
            fields, from_=start, to=end, textvariable=var, width=5,
            wrap=True, justify='center', bg=palette['surface'], fg=palette['text'],
            buttonbackground=palette['border'], relief='flat', bd=0,
            font=('Segoe UI', 13) if os.name == 'nt' else ('Helvetica', 13),
            format='%02.0f' if index or kind == 'time_picker' else '%04.0f',
        ).pack(side='left', padx=5)

    def _picker_done():
        try:
            nums = [int(var.get()) for var in values]
            if kind == 'date_picker':
                result = f'{nums[0]:04d}-{nums[1]:02d}-{nums[2]:02d}'
            else:
                result = f'{nums[0]:02d}:{nums[1]:02d}'
        except Exception:
            return
        overlay.close()
        _overlay_callback(data.get('on_select'), result)

    actions = tk.Frame(panel, bg=palette['surface'])
    actions.pack(fill='x')
    tk.Button(
        actions, text='OK', command=_picker_done, bg=palette['primary'],
        fg=palette['on_primary'], relief='flat', bd=0, padx=16, pady=8,
    ).pack(side='right', padx=(8, 0))
    tk.Button(
        actions, text='Cancel', command=_close, bg=palette['surface'],
        fg=palette['primary'], relief='flat', bd=0, padx=16, pady=8,
    ).pack(side='right')


def _show_snackbar_preview(message, action=None, on_action=None, duration=3000):
    global _active_snackbar
    if _active_snackbar is not None:
        try:
            _active_snackbar.destroy()
        except Exception:
            pass
    root = _app.root
    palette = _overlay_palette('snackbar')
    bar = tk.Frame(
        root, bg='#322F35', highlightthickness=1,
        highlightbackground=palette['border'], padx=14, pady=10,
    )
    bar.place(relx=.5, rely=.91, anchor='s', relwidth=.92)
    bar.lift()
    tk.Label(
        bar, text=str(message), bg='#322F35', fg='#F5EFF7', anchor='w',
        justify='left', wraplength=max(170, root.winfo_width() - 150),
        font=('Segoe UI', 10) if os.name == 'nt' else ('Helvetica', 10),
    ).pack(side='left', fill='x', expand=True)

    def _dismiss(run_action=False):
        global _active_snackbar
        if run_action:
            _overlay_callback(on_action)
        try:
            bar.destroy()
        except Exception:
            pass
        if _active_snackbar is bar:
            _active_snackbar = None

    if action:
        tk.Button(
            bar, text=str(action).upper(), command=lambda: _dismiss(True),
            bg='#322F35', fg=palette['primary'], relief='flat', bd=0,
            font=('Segoe UI', 9, 'bold') if os.name == 'nt' else ('Helvetica', 9, 'bold'),
        ).pack(side='right', padx=(8, 0))
    root.after(max(500, int(duration)), _dismiss)
    _active_snackbar = bar


def _toast_layout(text_width, root_width):
    """Return Material toast width, pill height and text wrap width in pixels."""
    available = max(96, int(root_width) - 24)
    text_limit = max(60, available - 68)
    lines = max(1, min(2, (max(1, int(text_width)) + text_limit - 1) // text_limit))
    text_used = min(max(1, int(text_width)), text_limit)
    minimum = min(128, available)
    width = min(available, max(minimum, text_used + 68))
    return width, (48 if lines == 1 else 64), max(40, width - 68)


def _draw_toast_app_badge(canvas, cx, cy):
    """Small font-independent app badge, similar to Android's toast app icon."""
    _create_circle(canvas, cx - 10, cy - 10, cx + 10, cy + 10,
                   fill='#58688F', outline='#58688F', tags='toast_icon')
    # Tiny Android-style robot mark. Geometry is used instead of an emoji so
    # Windows, Linux and macOS all render the same icon.
    canvas.create_arc(cx - 6, cy - 6, cx + 6, cy + 5, start=0, extent=180,
                      style='pieslice', fill='#F7F7FC', outline='#F7F7FC',
                      tags='toast_icon')
    canvas.create_rectangle(cx - 6, cy - 1, cx + 6, cy + 5,
                            fill='#F7F7FC', outline='#F7F7FC', tags='toast_icon')
    canvas.create_line(cx - 4, cy - 5, cx - 6, cy - 8,
                       fill='#F7F7FC', width=1, tags='toast_icon')
    canvas.create_line(cx + 4, cy - 5, cx + 6, cy - 8,
                       fill='#F7F7FC', width=1, tags='toast_icon')
    canvas.create_oval(cx - 3.5, cy - 3, cx - 2.5, cy - 2,
                       fill='#58688F', outline='#58688F', tags='toast_icon')
    canvas.create_oval(cx + 2.5, cy - 3, cx + 3.5, cy - 2,
                       fill='#58688F', outline='#58688F', tags='toast_icon')


def toast(message):
    """Show a modern Android-like toast in the desktop Previewer."""
    global _active_toast
    root = live_preview_root()
    if root is None:
        # No Previewer open -- a build, a test, a plain script. Printing
        # beats dropping it: the app asked to say something to somebody.
        print('[ApkPy toast] %s' % (message,))
        return

    if _active_toast is not None:
        try:
            _active_toast.destroy()
        except Exception:
            pass
        _active_toast = None

    root.update_idletasks()
    text = str(message)
    font = ('Segoe UI', -13) if os.name == 'nt' else ('Helvetica', -13)
    try:
        import tkinter.font as _tkfont
        text_width = _tkfont.Font(root=root, font=font).measure(text)
    except Exception:
        text_width = len(text) * 7

    width, pill_height, wrap_width = _toast_layout(text_width, root.winfo_width())
    canvas_height = pill_height + 8
    transparent = '#FF00FF'
    toast_win = tk.Toplevel(root)
    toast_win.overrideredirect(True)
    toast_win.configure(bg=transparent)
    canvas_bg = transparent
    try:
        # Windows supports a colour key, which removes the rectangular Canvas
        # background and leaves only the rounded toast plus its shadow visible.
        toast_win.attributes('-transparentcolor', transparent)
        toast_win.attributes('-topmost', True)
    except tk.TclError:
        canvas_bg = getattr(_app, '_bg', None) or root.cget('bg')
        toast_win.configure(bg=canvas_bg)

    canvas = tk.Canvas(
        toast_win, width=width, height=canvas_height, bg=canvas_bg,
        highlightthickness=0, borderwidth=0,
    )
    canvas.pack(fill='both', expand=True)

    # Material-style low elevation followed by the light system toast pill.
    _create_rounded_rect(
        canvas, 3, 6, width - 3, pill_height + 5, pill_height // 2,
        fill='#050507', outline='#050507', tags='toast_shadow',
    )
    _create_rounded_rect(
        canvas, 2, 2, width - 2, pill_height + 2, pill_height // 2,
        fill='#F2F0F7', outline='#F2F0F7', tags='toast_surface',
    )
    _draw_toast_app_badge(canvas, 25, 2 + pill_height / 2)
    canvas.create_text(
        47, 2 + pill_height / 2, text=text, fill='#37343C', font=font,
        anchor='w', justify='left', width=wrap_width, tags='toast_text',
    )

    nav = getattr(_app, '_bottom_nav_frame', None)
    try:
        nav_height = nav.winfo_height() if nav is not None and nav.winfo_exists() else 0
    except Exception:
        nav_height = 0
    bottom_offset = max(24, nav_height + 12)
    root_x, root_y = root.winfo_rootx(), root.winfo_rooty()
    root_w, root_h = root.winfo_width(), root.winfo_height()
    toast_x = root_x + (root_w - width) // 2
    toast_y = root_y + root_h - bottom_offset - canvas_height
    toast_win.geometry(f'{width}x{canvas_height}+{toast_x}+{toast_y}')
    toast_win.lift(root)
    toast_win.apkpy_toast_style = 'android-pill'
    toast_win.apkpy_toast_canvas = canvas
    _active_toast = toast_win

    def _dismiss(target=toast_win):
        global _active_toast
        try:
            target.destroy()
        except Exception:
            pass
        if _active_toast is target:
            _active_toast = None

    root.after(2200, _dismiss)

_active_notifications = {}


def _notification_layout(root_width, title, message):
    """Return a phone-like heads-up notification size for the Previewer."""
    available = max(260, int(root_width or 411) - 24)
    width = min(380, available)
    title_lines = 2 if len(str(title or "")) > 34 else 1
    body_lines = 2 if len(str(message or "")) > 48 else 1
    height = 82 + (title_lines - 1) * 16 + (body_lines - 1) * 15
    return width, min(116, height)


from .features.notifications import notify, notifications



def _make_dialog(title, message, buttons):
    """Cria um diálogo modal com botões em inglês (evita tradução automática do SO)."""
    root = live_preview_root()
    result = [None]
    if root is None:
        # Nobody can press a button in a window that is not open, and a
        # modal nobody can answer would hang a build forever. Say what was
        # asked and answer None -- which confirm() reads as Cancel, the
        # safe half of a question nobody got to see.
        print('[ApkPy dialog] %s: %s  (sem Previewer aberto -- Cancel)'
              % (title, message))
        return None

    win = tk.Toplevel(root)
    win.title(str(title))
    win.resizable(False, False)
    win.grab_set()
    if root:
        win.transient(root)

    tk.Label(
        win, text=str(message), wraplength=300, justify='left',
        padx=20, pady=16, font=('Segoe UI', 10) if os.name == 'nt' else ('Helvetica', 10)
    ).pack()

    btn_frame = tk.Frame(win, pady=10)
    btn_frame.pack()

    for label_text, value in reversed(buttons):
        def _click(v=value):
            result[0] = v
            win.destroy()
        tk.Button(
            btn_frame, text=label_text, command=_click, width=10,
            relief='raised', bd=1, padx=8, pady=4
        ).pack(side='right', padx=6)

    win.wait_window()
    return result[0]


def alert(title, message):
    """
    Mostra um diálogo com título, mensagem e botão OK.
    - No Android: abre um AlertDialog nativo.
    - No Preview: diálogo Tkinter com botão OK em inglês.
    """
    _job_rules.guard("dialog", "alert()")
    _make_dialog(str(title), str(message), [("OK", True)])


def confirm(title, message, on_result=None):
    """
    Mostra um diálogo de confirmação com botões OK/Cancel.
    Chama on_result(True) se confirmar, on_result(False) se cancelar.
    - No Android: AlertDialog com botões positivo/negativo.
    - No Preview: diálogo Tkinter com botões OK/Cancel em inglês.
    """
    _job_rules.guard("dialog", "confirm()")
    result = _make_dialog(str(title), str(message), [("OK", True), ("Cancel", False)])
    if on_result:
        on_result(bool(result))


def share(text, title=None):
    """
    Abre o menu de partilha do sistema para enviar texto para outra app
    (WhatsApp, Email, SMS, Bluetooth, etc.).
    - No Android: gera um Intent.ACTION_SEND com Intent.createChooser(...).
    - No Preview: simula a folha de partilha do Android numa janela com uma
      lista de apps comuns — escolher uma só fecha o popup (não envia nada
      de verdade, serve para testares o fluxo visualmente).
    """
    try:
        win = tk.Toplevel(_app.root)
        win.title(title or "Partilhar via")
        win.configure(bg="#1E293B")
        win.geometry("300x280")
        win.resizable(False, False)
        win.transient(_app.root)

        tk.Label(
            win, text=title or "Partilhar via", bg="#1E293B", fg="#F8FAFC",
            font=("Arial", 12, "bold"), anchor="w"
        ).pack(pady=(14, 4), padx=14, fill="x")
        tk.Label(
            win, text=text, bg="#1E293B", fg="#94A3B8", font=("Arial", 9),
            wraplength=270, justify="left", anchor="w"
        ).pack(padx=14, pady=(0, 10), fill="x")

        for app_name in ["WhatsApp", "Gmail", "Mensagens", "Bluetooth", "Copiar para a área de transferência"]:
            tk.Button(
                win, text=app_name, bg="#334155", fg="#E2E8F0", relief="flat",
                font=("Arial", 10), anchor="w", padx=12, pady=8,
                activebackground="#475569", activeforeground="#F8FAFC",
                command=win.destroy
            ).pack(fill="x", padx=14, pady=2)
    except Exception as e:
        print(f"[ApkPy share] {title or ''}: {text}  ({e})")


# ── visible= and active= for the rows of a virtual_collection ─────────────────
def _row_state_arguments(factory, names):
    """Add keyword arguments that only mean something inside a row= template:
    ``visible="{field}"`` on a component, ``active="{field}"`` and
    ``active_icon=`` on a button. Stored on the component; _row_instance reads
    them for each item. The signature says so, as every component's does."""
    import functools
    import inspect

    @functools.wraps(factory)
    def wrapper(*args, **kwargs):
        extras = {name: kwargs.pop(name) for name in names
                  if name in kwargs and kwargs[name] is not None}
        for name in names:
            kwargs.pop(name, None)
        made = factory(*args, **kwargs)
        if extras and isinstance(made, ComponentDef):
            made.kwargs.update(extras)
        return made

    signature = inspect.signature(factory)
    extra = [inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=None)
             for name in names]
    wrapper.__signature__ = signature.replace(
        parameters=list(signature.parameters.values()) + extra)
    return wrapper


label = _row_state_arguments(label, ('visible',))
container = _row_state_arguments(container, ('visible',))
image = _row_state_arguments(image, ('visible',))
avatar = _row_state_arguments(avatar, ('visible',))
button = _row_state_arguments(button, ('visible', 'active', 'active_icon'))
