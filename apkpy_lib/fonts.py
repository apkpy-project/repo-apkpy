"""Custom typefaces, shared by the Previewer and the Android compiler.

No Tkinter and no Android build in here.  Both backends read the same table, so
``font-family: "Tiempos"`` resolves to the same four files on the desktop and on
the phone, and the parsing of a font file happens once instead of twice.

Four slots and no more: ``regular``, ``bold``, ``italic`` and ``bold_italic``.
That is exactly what Tk can address -- a family plus the ``bold`` and ``italic``
modifiers -- and Android expresses the same four as ``fontWeight``/``fontStyle``
pairs.  ``light``, ``medium`` and ``semibold`` are missing on purpose: Android
would honour them and the Previewer could not, which is a difference you would
only meet once the APK was on a phone.
"""

import os
import re
import struct


# slot -> (android fontWeight, android fontStyle is italic)
SLOTS = {
    "regular": (400, False),
    "bold": (700, False),
    "italic": (400, True),
    "bold_italic": (700, True),
}

# The order slots are written in, so a generated family XML is stable.
SLOT_ORDER = ("regular", "bold", "italic", "bold_italic")

# What to fall back to when the app did not supply the slot being asked for.
# The last resort is always `regular`, and whatever is missing is synthesised
# by the renderer -- faux bold and a shear -- on both sides alike.
_FALLBACK = {
    "regular": ("regular", "bold", "italic", "bold_italic"),
    "bold": ("bold", "regular", "bold_italic", "italic"),
    "italic": ("italic", "regular", "bold_italic", "bold"),
    "bold_italic": ("bold_italic", "bold", "italic", "regular"),
}

FONT_SUFFIXES = (".ttf", ".otf")


def resource_name(family):
    """An Android resource name for a family: lowercase, digits, underscores.

    Resource names cannot carry capitals, spaces or dashes, and cannot start
    with a digit, so "Tiempos Text" becomes "tiempos_text".
    """
    slug = re.sub(r"[^a-z0-9_]", "_", str(family or "").strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        return "apkpy_font"
    return slug if slug[0].isalpha() else "f_" + slug


def slot_resource_name(family, slot):
    """The resource name of one file inside a family."""
    return "%s_%s" % (resource_name(family), slot)


def normalise_files(files):
    """Keep the slots that are real and drop the rest, in a stable order.

    Raises on a slot nobody can render, rather than accepting it and quietly
    doing nothing -- an unknown keyword here is a typo every time.
    """
    unknown = [key for key in files if key not in SLOTS]
    if unknown:
        raise ValueError(
            "font(...) knows these slots: %s. Got: %s"
            % (", ".join(SLOT_ORDER), ", ".join(sorted(unknown)))
        )
    return {
        slot: str(files[slot])
        for slot in SLOT_ORDER
        if files.get(slot)
    }


def resolve_slot(available, bold=False, italic=False):
    """Pick the file for a request, and say what still has to be faked.

    Returns ``(slot, synthesise_bold, synthesise_italic)``.  ``slot`` is
    ``None`` when the family has no files at all.
    """
    wanted = (
        "bold_italic" if (bold and italic)
        else "bold" if bold
        else "italic" if italic
        else "regular"
    )
    for slot in _FALLBACK[wanted]:
        if slot in available:
            have_bold, have_italic = slot in ("bold", "bold_italic"), \
                slot in ("italic", "bold_italic")
            return slot, (bold and not have_bold), (italic and not have_italic)
    return None, bold, italic


def family_name_from_file(path):
    """The family a font file calls itself, from its own ``name`` table.

    Needed because Tk is asked for a family by name, not by path, and a file
    called ``Inter-Bold.ttf`` may well introduce itself as "Inter" -- or as
    "Inter Bold", which is a different family as far as Tk is concerned.
    Returns ``None`` for anything that is not a readable sfnt font.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        return None
    return _family_from_bytes(data)


def _family_from_bytes(data):
    if len(data) < 12:
        return None
    # A TrueType collection points at its first face; a plain font starts at 0.
    offset = struct.unpack(">I", data[12:16])[0] if data[:4] == b"ttcf" else 0
    try:
        table_count = struct.unpack(">H", data[offset + 4:offset + 6])[0]
    except struct.error:
        return None
    name_offset = None
    for index in range(table_count):
        record = offset + 12 + index * 16
        if data[record:record + 4] == b"name":
            name_offset = struct.unpack(">I", data[record + 8:record + 12])[0]
            break
    if name_offset is None or name_offset + 6 > len(data):
        return None
    count, strings = struct.unpack(">HH", data[name_offset + 2:name_offset + 6])
    best = None
    for index in range(count):
        record = name_offset + 6 + index * 12
        if record + 12 > len(data):
            break
        platform, _encoding, _lang, name_id, length, start = struct.unpack(
            ">HHHHHH", data[record:record + 12])
        if name_id != 1:
            continue
        begin = name_offset + strings + start
        raw = data[begin:begin + length]
        try:
            if platform == 3:
                value = raw.decode("utf-16-be")
            elif platform == 1:
                value = raw.decode("mac-roman")
            else:
                value = raw.decode("latin-1")
        except (UnicodeDecodeError, LookupError):
            continue
        value = value.replace("\x00", "").strip()
        # Windows records (platform 3) win: they are the ones Tk and GDI read.
        if value and (best is None or platform == 3):
            best = value
            if platform == 3:
                break
    return best


# ── The registry both backends fill ──────────────────────────────────────────
#
# One shape, two instances: the Previewer fills its own by running `font(...)`,
# the compiler fills its own from the same call read out of the source. Separate
# instances because a transpile inside a Previewer session -- which is exactly
# what the test suite does -- must not inherit the other one's families.

class FontRegistry:
    """The typefaces one app declared."""

    def __init__(self):
        self._by_name = {}

    def register(self, family, files, base_dir=None, **extra):
        """Record a family. Returns the stored entry."""
        name = str(family or "").strip()
        if not name:
            raise ValueError("font(...) needs a family name")
        resolved = {}
        for slot, path in normalise_files(files).items():
            resolved[slot] = (
                os.path.join(base_dir, path)
                if base_dir and not os.path.isabs(path) else path
            )
        entry = {"name": name, "resource": resource_name(name),
                 "files": resolved}
        entry.update(extra)
        self._by_name[name.lower()] = entry
        return entry

    def lookup(self, family):
        """The entry for a CSS ``font-family`` value, or ``None``."""
        return self._by_name.get(str(family or "").strip().strip("\"'").lower())

    def all(self):
        """Every family, in the order it was declared."""
        return dict(self._by_name)

    def drop(self, key):
        """Forget one family, by the key `all()` lists it under."""
        self._by_name.pop(key, None)

    def clear(self):
        """Forget every family."""
        self._by_name.clear()

    def __bool__(self):
        return bool(self._by_name)

    def __len__(self):
        return len(self._by_name)
