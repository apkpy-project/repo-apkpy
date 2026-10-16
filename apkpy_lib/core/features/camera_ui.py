"""Serializable camera UI contract shared by Python and generated Android."""
import re

CONTROLS = ("close", "pro", "flash", "timer", "grid", "quality", "ratio",
            "torch", "zoom", "exposure", "flip", "shutter", "pause", "mode", "audio")
LABELS = {
    "close": "Close", "pro": "Pro", "capture": "Take photo", "record": "Record",
    "stop": "Stop", "pause": "Pause", "resume": "Resume", "flip": "Flip",
    "flash": "Flash", "timer": "Timer", "grid": "Grid", "quality": "Quality",
    "ratio": "Ratio", "torch": "Torch", "zoom": "Zoom", "exposure": "EV",
    "mode": "Mode", "audio": "Mic", "retake": "Retake",
    "use_photo": "Use photo", "use_video": "Use video",
}
COLORS = {"background": "#0e1216", "surface": "#1a2026", "accent": "#95edc7",
          "on_accent": "#0e1216", "text": "#ffffff", "muted": "#9caebd"}
UI_OPTIONS = {"controls": None, "labels": None, "colors": None,
              "title": "CAMERA", "button_radius": 18,
              "controls_position": "auto"}
JSON_OPTIONS = ("controls", "labels", "colors")


def validate_ui(options):
    selected = options["controls"]
    if selected is not None:
        if not isinstance(selected, (list, tuple)) or any(not isinstance(k, str) or k not in CONTROLS for k in selected):
            raise ValueError("camera.controls must be a list of: " + ", ".join(CONTROLS))
        if len(set(selected)) != len(selected):
            raise ValueError("camera.controls cannot repeat a control")
        if not {"close", "shutter"}.issubset(selected):
            raise ValueError("camera.controls must include close and shutter")
    for name, allowed in (("labels", LABELS), ("colors", COLORS)):
        values = options[name]
        if values is None:
            continue
        if not isinstance(values, dict):
            raise ValueError("camera.%s must be a dictionary" % name)
        for key, value in values.items():
            if key not in allowed:
                raise ValueError("Unknown camera.%s key: %s" % (name, key))
            if not isinstance(value, str):
                raise ValueError("camera.%s values must be strings" % name)
            if name == "colors" and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise ValueError("camera.colors values must use #RRGGBB")
            if name == "labels" and (not value.strip() or len(value) > 48 or any(ord(c) < 32 for c in value)):
                raise ValueError("Camera labels must contain 1-48 characters, without line breaks")
    title = options["title"]
    if not isinstance(title, str) or not title.strip() or len(title) > 48 or any(ord(c) < 32 for c in title):
        raise ValueError("camera.title must contain 1-48 characters, without line breaks")
    radius = options["button_radius"]
    if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not 0 <= radius <= 32:
        raise ValueError("camera.button_radius must be between 0 and 32")
    if options["controls_position"] not in ("auto", "top", "bottom"):
        raise ValueError("camera.controls_position must be auto, top or bottom")


def control_rows(selected, mode):
    """Header actions stay anchored; sliders get a full row; other actions wrap."""
    rows, current = [], []
    for key in (CONTROLS if selected is None else selected):
        if key in ("close", "pro") or key == "pause" and mode != "video":
            continue
        if key in ("zoom", "exposure"):
            if current:
                rows.append(current)
                current = []
            rows.append([key])
        else:
            current.append(key)
            if len(current) == 3:
                rows.append(current)
                current = []
    if current:
        rows.append(current)
    return rows
