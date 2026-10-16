# -*- coding: utf-8 -*-
"""The calls that reach the rest of the phone, on the desk.

    from apkpy_lib import haptics, speech, browser, downloads, calendar, \\
        phone, recorder, printing, incoming, files

A desktop has no vibration motor, no dialler and no share sheet, so none of
these can be the real thing here. What each one can be is *honest about what
the phone would do* and *answerable*, so every branch of an app can be walked
through at the desk:

* a call that hands over to another app -- the dialler, the calendar, the
  messages app -- draws that moment: a sheet rises over the app with what the
  other app was given, and "Back to the app" is the person coming back;
* a call that asks the person something asks, with the nearest thing a
  desktop has -- a real Save dialog, a field to type what would have been
  said;
* a call the desktop *can* do for real, it does: ``browser.open`` opens the
  browser, ``downloads.start`` downloads and shows it in the notification
  shade, ``recorder`` records from the microphone when there is one.

Which calls exist and what they answer is ``apkpy_lib/kit_rules.py``, the
table the compiler reads too. The words a phone can answer and a desk never
will (``no_vibrator``, ``permission_blocked``...) are in that table, and an
app that wants to see one has to see it on a phone.
"""
from __future__ import annotations

import inspect
import os
import sys
import threading
import time

from .. import job_rules
from .. import kit_rules as rules
from ..diagnostics import ApkpyError

__all__ = [
    "HapticsAPI", "haptics", "SpeechAPI", "speech", "BrowserAPI", "browser",
    "DownloadsAPI", "downloads", "CalendarAPI", "calendar", "PhoneAPI",
    "phone", "RecorderAPI", "recorder", "PrintingAPI", "printing",
    "IncomingAPI", "incoming", "save_as", "save_copy", "status_glyphs",
    "HomeWidgetAPI", "home_widget", "QuickTileAPI", "quick_tile", "AdsAPI", "ads",
    "UpdatesAPI", "updates", "HealthAPI", "health", "TimerAPI", "timer",
    "NetworkAPI", "network", "DisplayAPI", "display", "AppLockAPI", "app_lock",
]


# ── the Previewer window, if there is one ────────────────────────────────────

def _root():
    """The live Previewer's Tk root, or ``None``. Never builds a window."""
    from .. import ui
    return ui.live_preview_root()


def _later(seconds, work):
    """``work()`` after ``seconds`` on the Tk thread, unless the Previewer
    closes first. With no Previewer it runs now."""
    root = _root()
    if root is None:
        work()
        return
    from . import kit_surfaces
    if kit_surfaces.later(root, seconds, work) is None:
        work()


def _on_main(work):
    """Run on the Tk thread when there is one, else here."""
    import threading as _threading
    root = _root()
    if root is None:
        work()
    elif _threading.current_thread() is _threading.main_thread():
        _later(0, work)
    else:
        # From a worker thread only after() is safe to call; the bookkeeping
        # that cancels timers belongs to the Tk thread, so it is done there.
        try:
            root.after(0, lambda: _later(0, work))
        except Exception:
            pass


def _answer(on_result, ok, value):
    """``on_result(ok, value)``, on the thread the screens live on."""
    if on_result is None:
        return
    _on_main(lambda: on_result(bool(ok), "" if value is None else str(value)))


def _refresh_strip():
    from .. import ui
    if ui.live_preview() is None:
        return
    try:
        ui.refresh_status_glyphs()
    except Exception:
        pass


# What is lit in the device's strip right now: name -> the moment it goes out
# (None for "until told"). The strip is the Previewer's own, like the torch.
_LIT = {}


def status_glyphs():
    """The glyphs these calls have lit, for ``ui._draw_status_glyphs``."""
    now = time.monotonic()
    return tuple(name for name, until in _LIT.items() if until is None or until > now)


def _light(name, seconds=None):
    _LIT[name] = None if seconds is None else time.monotonic() + seconds
    _refresh_strip()
    if seconds is not None and _root() is not None:
        _later(seconds + 0.03, _refresh_strip)


def _unlight(name):
    _LIT.pop(name, None)
    _refresh_strip()


def _hand_over(kind, icon, app_name, title, rows=(), quote="", note="", on_close=None):
    """Another app comes to the front. With a Previewer open that is a sheet
    over the app; with none it is a line printed -- which beats dropping it,
    since the app asked for something to happen -- and nobody to wait for."""
    if _root() is None:
        said = [text for _icon, text in rows if str(text).strip()]
        if quote:
            said.append(quote)
        print("[ApkPy %s] %s%s" % (app_name.lower(), title,
                                   (": " + " | ".join(said)) if said else ""))
        if on_close:
            on_close()
        return None
    from . import kit_surfaces
    return kit_surfaces.Handover(kind, icon, app_name, title, rows=rows, quote=quote,
                                 note=note, on_close=on_close).open()


class _NoSuchCall(ApkpyError, AttributeError):
    """A call the family does not have, said the way the build says it.

    Still an ``AttributeError``: ``hasattr(haptics, "widget")`` -- which code
    that walks an app's names is free to ask -- has to answer False, not stop
    the Previewer.
    """


class _Api:
    """What the families share: their words, and the refusal inside a job."""

    namespace = ""

    @property
    def reasons(self):
        return rules.reasons(self.namespace)

    def __getattr__(self, name):
        # Reached only for a name the family does not have.
        if name.startswith("_") or not self.namespace:
            raise AttributeError(name)
        rules.refuse(error=_NoSuchCall, **rules.unknown(self.namespace, name))

    def _guard(self, verb):
        # A job body has no screen to hand over from; the build refuses the
        # same call with the same words.
        job_rules.guard("screen_api", rules.label(self.namespace, verb))


# ── haptics ──────────────────────────────────────────────────────────────────

class HapticsAPI(_Api):
    """A touch you can feel, and the vibration motor.

    A desk cannot shake. For as long as the motor would run, the Previewer
    lights a small vibrating phone in the device's strip, beside the signal.
    """

    namespace = "haptics"

    def __init__(self):
        self.last = None        # ("tap",) or ("vibrate", 200): what was felt last

    def _feel(self, kind, seconds):
        self.last = kind
        _light("vibrate", seconds)
        return "ok"

    def tap(self):
        """The light click of pressing something."""
        self._guard("tap")
        return self._feel(("tap",), 0.35)

    def tick(self):
        """Lighter still: a value changing under the finger."""
        self._guard("tick")
        return self._feel(("tick",), 0.25)

    def heavy(self):
        """The firm bump of a long press."""
        self._guard("heavy")
        return self._feel(("heavy",), 0.45)

    def success(self):
        """It worked."""
        self._guard("success")
        return self._feel(("success",), 0.45)

    def error(self):
        """It did not."""
        self._guard("error")
        return self._feel(("error",), 0.55)

    def vibrate(self, ms=200):
        """Run the motor for this many milliseconds."""
        self._guard("vibrate")
        default = rules.verb("haptics", "vibrate").params[0][2]
        length = int(rules.clamp(rules.whole(ms, default), *rules.LIMITS["vibrate_ms"]))
        return self._feel(("vibrate", length), max(0.35, length / 1000.0))

    def available(self):
        """Whether there is a motor at all. The stand-in always has one."""
        self._guard("available")
        return True


haptics = HapticsAPI()


# ── speech ───────────────────────────────────────────────────────────────────

class SpeechAPI(_Api):
    """The phone reading text aloud, and writing down what it hears."""

    namespace = "speech"

    def __init__(self):
        self._saying = 0        # which sentence is current; 0 when silent
        self._count = 0
        self._waiting = None    # the on_result of the one being said
        self.last = None        # (text, language, rate, pitch) of the last say()

    def say(self, text, language="", rate=1.0, pitch=1.0, on_result=None):
        """Read this aloud; ``on_result(ok, reason)`` when it has been said.

        A new sentence replaces the one being read, whose ``on_result`` hears
        ``"stopped"``. The desk has no voice: the words are shown as a caption
        for as long as a voice would take over them.
        """
        self._guard("say")
        words = "" if text is None else str(text)
        self.last = (words, str(language or ""),
                     rules.clamp(rules.number(rate, 1.0), *rules.LIMITS["rate"]),
                     rules.clamp(rules.number(pitch, 1.0), *rules.LIMITS["pitch"]))
        if not words.strip():
            _answer(on_result, True, "ok")
            return
        self._interrupt()
        self._count += 1
        self._saying = token = self._count
        self._waiting = on_result
        seconds = rules.speaking_seconds(words, rate)

        def finished():
            if self._saying != token:
                return
            self._saying = 0
            waiting, self._waiting = self._waiting, None
            _answer(waiting, True, "ok")

        root = _root()
        if root is None:
            # Nothing to wait in: it is said, as far as a script can tell.
            print("[ApkPy speech] %s" % words)
            finished()
            return
        from . import kit_surfaces
        kit_surfaces.caption(words if len(words) <= 220 else words[:217] + "...", seconds)
        _later(seconds, finished)

    def _interrupt(self):
        if not self._saying:
            return
        self._saying = 0
        waiting, self._waiting = self._waiting, None
        _answer(waiting, False, "stopped")

    def stop(self):
        """Stop reading."""
        self._guard("stop")
        self._interrupt()
        if _root() is not None:
            from . import kit_surfaces
            for shown in list(kit_surfaces._captions):
                kit_surfaces._drop_caption(shown)
        return "ok"

    def is_speaking(self):
        """Whether something is being read right now."""
        self._guard("is_speaking")
        return bool(self._saying)

    def listen(self, prompt="", language="", on_result=None):
        """Open the microphone; ``on_result(ok, words)``.

        On the desk the words are typed, into a sheet that stands where the
        phone's microphone sheet would: what matters at the desk is what the
        app does with them.
        """
        self._guard("listen")
        asked = str(prompt) if str(prompt or "").strip() else "Speak now"
        if _root() is None:
            print("[ApkPy speech] %s  (no Previewer open -- cancelled)" % asked)
            _answer(on_result, False, "cancelled")
            return

        def heard(typed):
            _unlight("mic")
            typed = (typed or "").strip()
            if typed:
                _answer(on_result, True, typed)
            else:
                _answer(on_result, False, "nothing_heard")

        def closed():
            _unlight("mic")
            _answer(on_result, False, "cancelled")

        from . import kit_surfaces
        _light("mic")
        kit_surfaces.Handover(
            "listen", "mic", "Voice input", asked, field="Type what would be said",
            note="On the phone this is the system's microphone sheet, and the "
                 "words are spoken.",
            done="Done", on_done=heard, on_close=closed).open()

    def can_listen(self):
        """Whether this phone can turn speech into text. The stand-in can."""
        self._guard("can_listen")
        return True


speech = SpeechAPI()


# ── browser ──────────────────────────────────────────────────────────────────

def _open_in_browser(target):
    """The desktop browser, unless the session asked for none (tests do)."""
    if os.environ.get("APKPY_PREVIEW_NO_BROWSER", "").strip() == "1":
        return False
    try:
        import webbrowser
        return bool(webbrowser.open(target))
    except Exception:
        return False


def _host(address):
    import urllib.parse
    return urllib.parse.urlparse(address).netloc or address


class BrowserAPI(_Api):
    """A web page: over the app in the phone's browser, or inside the app."""

    namespace = "browser"

    def __init__(self):
        self.last = None        # ("open", url) or ("show", url, html, title)

    def open(self, url):
        """The page in a browser tab drawn over the app."""
        self._guard("open")
        address = rules.web_address(url)
        if not address:
            return "invalid"
        self.last = ("open", address)
        if _root() is not None:
            _open_in_browser(address)
        _hand_over("open", "public", "Browser", _host(address), rows=[("link", address)],
                   note="Opened in this computer's browser. On the phone it is a "
                        "browser tab drawn over the app, one Back away.")
        return "ok"

    def show(self, url="", html="", title="", on_result=None):
        """The page, or your own HTML, inside the app.

        Tk draws no web pages, so the desk opens it in the browser to look at
        -- an address as it is, HTML from a file written for the purpose --
        and stands a sheet where the page would be. Closing the sheet is the
        person closing the page: ``on_result(True, address)``.
        """
        self._guard("show")
        address = rules.web_address(url)
        markup = "" if html is None else str(html)
        if not address and not markup.strip():
            _answer(on_result, False, "invalid")
            return
        self.last = ("show", address, markup, str(title or ""))
        if _root() is not None:
            _open_in_browser(address or "file:///" + _write_page(
                markup, title or "page", _page_css()).replace(os.sep, "/"))
        heading = str(title).strip() or (_host(address) if address else "Your page")
        _hand_over("show", "web", "A page inside the app", heading,
                   rows=[("link", address)] if address else [("code", "HTML written by the app")],
                   note="Opened in this computer's browser to look at. On the phone "
                        "it is drawn inside the app, under a bar with a close button.",
                   on_close=lambda: _answer(on_result, True, address))


def _page_css():
    """The rules a page inside the app is given, in the app's colours -- the
    ones ApkpyBrowser reads from the Activity's theme on the phone."""
    surface, primary, dark = "#FFFFFF", "#3D5AFE", False
    try:
        from .. import ui
        tokens = ui.global_styles.get("__theme__", {}) or {}
        surface = str(tokens.get("background") or surface)
        primary = str(tokens.get("primary") or primary)
        red, green, blue = (int(surface[i:i + 2], 16) for i in (1, 3, 5))
        dark = (0.299 * red + 0.587 * green + 0.114 * blue) / 255.0 < 0.5
    except Exception:
        surface, primary, dark = "#FFFFFF", "#3D5AFE", False
    return rules.page_css(surface, "#F2F2F2" if dark else "#1B1B1F", primary)


def _write_page(markup, name, css):
    """HTML the app wrote, as a file a browser can open."""
    import re
    import tempfile
    folder = os.path.join(tempfile.gettempdir(), "apkpy-preview")
    os.makedirs(folder, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", str(name)).strip("-.") or "page"
    path = os.path.join(folder, safe[:60] + ".html")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(rules.document(markup, css))
    return path


browser = BrowserAPI()


# ── files.read / files.write / files.append ──────────────────────────────────

def _own_file(name):
    """The file a name means in the app's folder, or ``""`` when it is not
    the name of one."""
    from .. import ui
    folder = ui.files._dir()
    given = rules.trim(name)
    # files.path("notes.txt") and the callback of files.download() answer the
    # whole path; it means the same file as the bare name.
    root = folder + os.sep
    if given.startswith(root):
        given = given[len(root):].replace(os.sep, "/")
    clean = rules.file_name(given)
    return os.path.join(folder, *clean.split("/")) if clean else ""


def read(name):
    """The text of one of the app's files; ``""`` when there is none."""
    job_rules.guard("screen_api", "files.read()")
    path = _own_file(name)
    if not path:
        return ""
    try:
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8", "replace")
    except OSError:
        return ""
    # A file saved by a desktop editor may open with a byte-order mark, which
    # is not part of what it says.
    return text[1:] if text[:1] == "\ufeff" else text


def _put(verb, name, text, add):
    job_rules.guard("screen_api", "files.%s()" % verb)
    path = _own_file(name)
    if not path:
        return "invalid"
    # Bytes, so no line ending is changed: the phone keeps the text as given.
    data = ("" if text is None else str(text)).encode("utf-8", "replace")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if add:
            with open(path, "ab") as handle:
                handle.write(data)
        else:
            # Replaced whole or not at all, as on the phone.
            spare = os.path.join(os.path.dirname(path),
                                 ".apkpy-" + os.path.basename(path) + ".tmp")
            try:
                with open(spare, "wb") as handle:
                    handle.write(data)
                os.replace(spare, path)
            except OSError:
                if os.path.exists(spare):
                    os.remove(spare)
                raise
    except OSError:
        return "failed"
    return "ok"


def write(name, text):
    """Keep this text as one of the app's files, in place of what was there."""
    return _put("write", name, text, False)


def append(name, text):
    """Add this text to the end of one of the app's files."""
    return _put("append", name, text, True)


# ── files.save_as / files.save_copy ──────────────────────────────────────────

def _ask_where(name):
    """The desktop's own Save dialog. ``""`` when it is closed -- and with no
    Previewer open, when there is nobody to ask."""
    root = _root()
    if root is None:
        print("[ApkPy files] save %s  (no Previewer open -- cancelled)" % name)
        return ""
    try:
        from tkinter import filedialog
        return filedialog.asksaveasfilename(parent=root, initialfile=str(name),
                                            title="Save to...") or ""
    except Exception:
        return ""


def save_as(name, text, mime="text/plain", on_result=None):
    """Ask where, and write this text there. ``on_result(ok, name)``."""
    job_rules.guard("screen_api", "files.save_as()")
    where = _ask_where(name)
    if not where:
        _answer(on_result, False, "cancelled")
        return
    try:
        with open(where, "w", encoding="utf-8", newline="") as handle:
            handle.write("" if text is None else str(text))
    except OSError:
        _answer(on_result, False, "failed")
        return
    _answer(on_result, True, os.path.basename(where))


def save_copy(path, name="", on_result=None):
    """Ask where, and copy one of the app's files there. ``on_result(ok, name)``."""
    job_rules.guard("screen_api", "files.save_copy()")
    from .. import ui
    given = str(path or "").strip()
    source = given if os.path.isabs(given) else ui.files.path(given)
    if not given or not os.path.isfile(source):
        _answer(on_result, False, "not_found")
        return
    where = _ask_where(str(name).strip() or os.path.basename(source))
    if not where:
        _answer(on_result, False, "cancelled")
        return
    try:
        import shutil
        shutil.copyfile(source, where)
    except OSError:
        _answer(on_result, False, "failed")
        return
    _answer(on_result, True, os.path.basename(where))


# ── downloads ────────────────────────────────────────────────────────────────

def _download_notice(key, title, message, progress, ongoing):
    """The download, in the Previewer's notification shade -- which is where
    Android shows one. It is the system's notification, not the app's, so it
    does not wait on the app's permission to notify."""
    try:
        from .notifications import notifications as shade
        drawer = shade._ensure()
        if drawer is None:
            return
        shade.channel("apkpy_downloads", "Downloads", "high")
        previous = shade.items.pop(key, {})
        shade.items[key] = {
            "id": key, "title": str(title), "message": str(message),
            "channel": "apkpy_downloads", "icon": "download", "style": "none",
            "picture": None, "lines": [], "actions": [], "on_tap": None,
            "on_dismiss": None, "ongoing": bool(ongoing), "progress": progress,
            "group": None, "when": None,
            "expanded": previous.get("expanded", False),
            "timestamp": int(time.time() * 1000),
        }
        shade._refresh()
        drawer.heads_up(key)
    except Exception:
        # The shade is a courtesy; the download is what was asked for.
        pass


class DownloadsAPI(_Api):
    """A download the phone does itself, into the Downloads folder."""

    namespace = "downloads"

    def __init__(self):
        self._count = 0

    def folder(self):
        """Where the Previewer puts them: ``~/.apkpy/downloads``. Not the
        desktop's own Downloads folder -- a rehearsal should not leave files
        among a person's own."""
        path = os.path.join(os.path.expanduser("~"), ".apkpy", "downloads")
        os.makedirs(path, exist_ok=True)
        return path

    def start(self, url, name="", title="", on_result=None):
        """Download in the background; ``on_result(ok, name)`` when it lands."""
        self._guard("start")
        address = rules.web_address(url)
        if not address:
            _answer(on_result, False, "invalid")
            return
        file = str(name or "").strip()
        if not file:
            import urllib.parse
            file = os.path.basename(urllib.parse.urlparse(address).path) or "download"
        file = file.replace("\\", "/").rsplit("/", 1)[-1]
        if file in ("", ".", ".."):
            file = "download"
        target = os.path.join(self.folder(), file)
        shown = str(title).strip() or file
        self._count += 1
        key = "apkpy_download_%d" % self._count
        if _root() is None:
            print("[ApkPy downloads] %s -> %s" % (address, target))
        else:
            _download_notice(key, shown, "Downloading…", "indeterminate", True)

        def work():
            import urllib.request
            word = ""
            try:
                request = urllib.request.Request(address, headers={"User-Agent": "ApkPy-Previewer"})
                with urllib.request.urlopen(request, timeout=60) as response, \
                        open(target, "wb") as handle:
                    while True:
                        chunk = response.read(64 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
            except OSError as problem:
                word = "no_space" if getattr(problem, "errno", None) == 28 else "failed"
            except Exception:
                word = "failed"
            if word:
                try:
                    os.remove(target)
                except OSError:
                    pass
                _on_main(lambda: _download_notice(key, shown, "Download unsuccessful", None, False))
                _answer(on_result, False, word)
                return
            _on_main(lambda: _download_notice(key, shown, "Download complete", None, False))
            _answer(on_result, True, file)

        threading.Thread(target=work, name="apkpy-download", daemon=True).start()


downloads = DownloadsAPI()


# ── calendar and phone ───────────────────────────────────────────────────────

class CalendarAPI(_Api):
    """An event, written into the phone's calendar app for the person to save."""

    namespace = "calendar"

    def __init__(self):
        self.last = None

    def add_event(self, title, start, end="", location="", notes="", all_day=False):
        """Open the calendar's new-event screen, filled in."""
        self._guard("add_event")
        times = rules.event_times(start, end, all_day)
        if times is None:
            return "invalid"
        begin, finish, whole_day = times
        self.last = {"title": str(title), "begin": begin, "finish": finish,
                     "all_day": whole_day, "location": str(location or ""),
                     "notes": str(notes or "")}
        if whole_day:
            import datetime
            last_day = finish - datetime.timedelta(days=1)
            when = begin.strftime("%A, %d %B %Y")
            if last_day.date() != begin.date():
                when = begin.strftime("%d %B") + " – " + last_day.strftime("%d %B %Y")
            when += "\nAll day"
        else:
            when = begin.strftime("%A, %d %B %Y") + "\n" + begin.strftime("%H:%M") \
                + " – " + (finish.strftime("%H:%M") if finish.date() == begin.date()
                                else finish.strftime("%d %B, %H:%M"))
        _hand_over("event", "event", "Calendar", str(title).strip() or "New event",
                   rows=[("schedule", when), ("place", location), ("notes", notes)],
                   note="On the phone the calendar opens on a new event with this "
                        "filled in, and the person saves it.")
        return "ok"


calendar = CalendarAPI()


def _spaced(digits):
    """A number in threes, the way a dialler shows one being typed."""
    lead = "+" if digits.startswith("+") else ""
    body = digits[len(lead):]
    if not body.isdigit() or len(body) < 7:
        return digits
    groups = []
    while len(body) > 4:
        groups.insert(0, body[-3:])
        body = body[:-3]
    return lead + " ".join([body] + groups)


class PhoneAPI(_Api):
    """The dialler and the messages app, with the number already typed."""

    namespace = "phone"

    def __init__(self):
        self.last = None

    def dial(self, number):
        """Open the dialler on this number; the person presses call."""
        self._guard("dial")
        digits = rules.phone_number(number)
        if not digits:
            return "invalid"
        self.last = ("dial", digits)
        _hand_over("dial", "call", "Phone", _spaced(digits),
                   note="On the phone the dialler opens with this number typed, "
                        "and the person presses call.")
        return "ok"

    def sms(self, number, text=""):
        """Open a message to this number; the person presses send."""
        self._guard("sms")
        digits = rules.phone_number(number)
        if not digits:
            return "invalid"
        words = "" if text is None else str(text)
        self.last = ("sms", digits, words)
        _hand_over("sms", "sms", "Messages", "To " + _spaced(digits), quote=words,
                   note="On the phone the messages app opens with this written, "
                        "and the person presses send.")
        return "ok"


phone = PhoneAPI()


# ── recorder ─────────────────────────────────────────────────────────────────

def _named(sentence):
    """A sentence with the app's name in it. With no name it says "this app",
    with a capital only where a sentence starts."""
    name = _app_name()
    text = sentence % name
    return text[:1].upper() + text[1:] if sentence.startswith("%s") else text


def screen_shown(screen):
    """The Previewer has just drawn ``screen``: put back what the screen has
    that is not in its layout."""
    try:
        ads._show(screen)
    except Exception:
        pass
    try:
        timer._screen_shown(screen)
    except Exception:
        pass
    try:
        network._screen_shown(screen)
    except Exception:
        pass
    try:
        display._screen_shown(screen)
    except Exception:
        pass
    try:
        app_lock._screen_shown(screen)
    except Exception:
        pass


def _app_name():
    """The app's name from apkpy.toml, as Android writes it in the dialog."""
    try:
        from .. import ui
        name = str(ui.app._config().get("name") or "").strip()
        return name or "this app"
    except Exception:
        return "this app"


class RecorderAPI(_Api):
    """The microphone, recorded into a file of the app.

    The desk records for real when it can -- the ``sounddevice`` package the
    Previewer already uses for video sound -- into a ``.wav`` under
    ``~/.apkpy/files/recordings``. With no microphone, or none it is allowed
    to open, the file holds silence of the right length: ``stop()`` still
    answers a file that plays, which is what the rest of the app is waiting
    for. The phone writes ``.m4a``.

    While it records, the device's strip shows a green microphone -- the
    one Android itself lights whenever an app is listening.
    """

    namespace = "recorder"
    RATE = 44100

    def __init__(self):
        self._since = None
        self._path = ""
        self._stream = None
        self._wave = None
        self._frames = 0
        self._lock = threading.Lock()

    def folder(self):
        from .. import ui
        path = os.path.join(ui.files._dir(), "recordings")
        os.makedirs(path, exist_ok=True)
        return path

    def start(self, on_result=None):
        """Ask for the microphone if needed, and start recording."""
        self._guard("start")
        if self._since is not None:
            _answer(on_result, False, "busy")
            return
        from .. import ui
        if ui.permissions.has("RECORD_AUDIO"):
            self._go(on_result)
            return
        if _root() is None:
            # Nobody to ask: a script records as a granted app would.
            ui.permissions._granted.add("RECORD_AUDIO")
            self._go(on_result)
            return

        def answered(choice):
            if choice == "deny":
                _answer(on_result, False, "permission_denied")
                return
            if choice == "always":
                ui.permissions._granted.add("RECORD_AUDIO")
            self._go(on_result)

        from . import kit_surfaces
        kit_surfaces.Handover(
            "permission", "mic", "Permission", "Allow %s to record audio?" % _app_name(),
            choices=[("While using the app", "always"), ("Only this time", "once"),
                     ("Don\u2019t allow", "deny")],
            note="Android asks this the first time, in a dialog of its own.",
            on_choice=answered, on_close=lambda: answered("deny")).open()

    def _go(self, on_result):
        if self._since is not None:
            _answer(on_result, False, "busy")
            return
        try:
            self._begin()
        except Exception:
            self._close()
            _answer(on_result, False, "failed")
            return
        _light("mic")
        _answer(on_result, True, "ok")

    def _begin(self):
        import wave
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = os.path.join(self.folder(), "recording-%s.wav" % stamp)
        copy = 2
        while os.path.exists(path):
            path = os.path.join(self.folder(), "recording-%s-%d.wav" % (stamp, copy))
            copy += 1
        handle = wave.open(path, "wb")
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(self.RATE)
        self._wave, self._path, self._since = handle, path, time.monotonic()
        self._frames = 0
        if _root() is None:
            return              # a script: silence, no device opened
        try:
            import sounddevice

            def heard(data, _frames, _time, _status):
                with self._lock:
                    if self._wave is not None:
                        self._wave.writeframes(bytes(data))
                        self._frames += len(data) // 2

            self._stream = sounddevice.RawInputStream(
                samplerate=self.RATE, channels=1, dtype="int16", callback=heard)
            self._stream.start()
        except Exception:
            # No microphone, or none the desk may open: silence it is.
            self._stream = None

    def _close(self):
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        with self._lock:
            handle, self._wave = self._wave, None
            if handle is not None:
                try:
                    # Whatever the microphone did not fill is silence, so the
                    # file is as long as the recording was.
                    wanted = int((time.monotonic() - (self._since or time.monotonic())) * self.RATE)
                    missing = max(0, wanted - self._frames)
                    if stream is None and missing:
                        handle.writeframes(b"\x00\x00" * min(missing, self.RATE * 600))
                    handle.close()
                except Exception:
                    pass
        self._since = None

    def stop(self):
        """Stop, and answer the path of the file (``""`` when nothing was recorded)."""
        self._guard("stop")
        if self._since is None:
            return ""
        path = self._path
        self._close()
        self._path = ""
        _unlight("mic")
        try:
            if os.path.getsize(path) <= 44:      # a header and no sound
                os.remove(path)
                return ""
        except OSError:
            return ""
        return path

    def is_recording(self):
        """Whether it is recording right now."""
        self._guard("is_recording")
        return self._since is not None

    def seconds(self):
        """How long it has been recording, in whole seconds -- as text, like
        every value that comes back from the phone."""
        self._guard("seconds")
        if self._since is None:
            return "0"
        return str(int(time.monotonic() - self._since))


recorder = RecorderAPI()


# ── printing ─────────────────────────────────────────────────────────────────

class PrintingAPI(_Api):
    """Android's print screen: any printer, or Save as PDF."""

    namespace = "printing"

    def __init__(self):
        self.last = None        # (name, html) of the last document

    def html(self, html, name="Document", on_result=None):
        """Print a document written in HTML.

        The desk opens the document in the browser, which is where a desktop
        prints from and the quickest way to see the pages as they will be.
        """
        self._guard("html")
        job = str(name).strip() or "Document"
        markup = "" if html is None else str(html)
        self.last = (job, markup)
        if _root() is not None:
            _open_in_browser("file:///" + _write_page(
                markup, job, rules.PRINT_CSS).replace(os.sep, "/"))
        _hand_over("print", "print", "Print", job,
                   rows=[("picture_as_pdf", "Save as PDF, or any printer the phone knows")],
                   note="Opened in this computer's browser to look at the pages. On "
                        "the phone this is Android's print screen.")
        _answer(on_result, True, "ok")

    def text(self, text, name="Document", on_result=None):
        """Print plain text as it is."""
        self._guard("text")
        import html as _html
        self.html('<pre class="apkpy-text">%s</pre>'
                  % _html.escape("" if text is None else str(text), quote=False),
                  name, on_result)


printing = PrintingAPI()


# ── incoming ─────────────────────────────────────────────────────────────────

class IncomingAPI(_Api):
    """What opened the app from outside: a link, or something shared into it.

    Nobody taps a link on the desk, so a declaration can say what the
    Previewer pretends arrived::

        incoming.links("notes", preview="notes://open/42")
        incoming.shares("text", preview="Buy milk")

    The phone ignores ``preview=``. Without it the desk answers ``""``, which
    is what an app opened from its icon gets on the phone too.
    """

    namespace = "incoming"

    def __init__(self):
        self._link = ""
        self._text = ""
        self._file = ""
        self.declared_links = []
        self.declared_shares = []

    def links(self, scheme, host="", preview=""):
        """Addresses that open this app. Written once, at the top of the file."""
        problem = rules.link_scheme(scheme, host)
        if problem:
            rules.refuse("incoming.links(): " + problem,
                         received="incoming.links(%r%s)" % (scheme, ", %r" % host if host else ""))
        self.declared_links.append((str(scheme), str(host or "")))
        if preview:
            self._link = str(preview)

    def shares(self, kind="text", preview=""):
        """What other apps can share into this one: "text", "image" or "file"."""
        if kind not in rules.SHARE_KINDS:
            rules.refuse("incoming.shares(): there is no kind %r" % (kind,),
                         received="incoming.shares(%r)" % (kind,),
                         suggestions=["One of: %s." % ", ".join(
                             '"%s"' % known for known in rules.SHARE_KINDS)])
        self.declared_shares.append(str(kind))
        if preview:
            if kind == "text":
                self._text = str(preview)
            else:
                self._file = str(preview)

    def link(self):
        """The address that opened the app, or ``""``."""
        self._guard("link")
        return self._link

    def text(self):
        """The text another app shared, or ``""``."""
        self._guard("text")
        return self._text

    def file(self):
        """The path of a copy of the file another app shared, or ``""``."""
        self._guard("file")
        return self._file

    def clear(self):
        """Forget what arrived, once the app has dealt with it."""
        self._guard("clear")
        self._link = self._text = self._file = ""
        return "ok"


incoming = IncomingAPI()


# ── what an app has outside its own screens ──────────────────────────────────

def _yes(value):
    """True for ``True`` and for the text ``"true"``, as the phone reads it."""
    return value if isinstance(value, bool) else rules.truth(value)


class _Declared(_Api):
    """A family that means nothing until one line at the top of the file has
    said what the app is built with. The build stops at a call that comes
    without it; the desk says the same thing in the same words."""

    def __init__(self):
        self.declared = None

    def _need(self, verb):
        if self.declared is None:
            _declaration, why, example = rules.DECLARED_BY[self.namespace]
            rules.refuse("%s: %s" % (rules.label(self.namespace, verb), why),
                         received="%s.%s(...)" % (self.namespace, verb),
                         cause="What the app has outside its own screens is written "
                               "into it when it is built, from one line at the top of "
                               "the file.",
                         suggestions=["Add this at the top of the file: " + example])


class HomeWidgetAPI(_Declared):
    """The app's widget on the home screen.

    One line says the app has one, and what it shows before the app has said
    anything::

        home_widget.define("Steps today", "0", caption="steps", icon="directions_walk")

    From then on ``home_widget.set()`` changes what it shows. A desk has no
    home screen, so the Previewer shows the widget itself for a moment at the
    top of the window each time it changes -- the launcher's drawing of it,
    in the app's colours.
    """

    namespace = "home_widget"

    def __init__(self):
        super().__init__()
        self.title = self.text = self.caption = self.icon = ""
        self._count = 0

    def define(self, title, text="", caption="", icon="", name=""):
        """That the app has a widget. Written once, at the top of the file."""
        if not rules.trim(title):
            rules.refuse("home_widget.define(): a widget has at least a title",
                         received="home_widget.define(%r)" % (title,),
                         suggestions=[rules.DECLARED_BY["home_widget"][2]])
        self.declared = {"title": str(title), "text": str(text or ""),
                         "caption": str(caption or ""), "icon": str(icon or ""),
                         "name": str(name or "")}
        self.title, self.text = self.declared["title"], self.declared["text"]
        self.caption, self.icon = self.declared["caption"], self.declared["icon"]

    def _draw(self, card=False):
        from .. import ui
        from . import kit_surfaces
        root = _root()

        def draw(canvas, x, y, width):
            return kit_surfaces.draw_widget(
                ui, root, canvas, x, y, width, kit_surfaces.widget_palette(ui, root),
                self.title, self.text, self.caption, self.icon, card=card)
        return draw

    def set(self, text, caption="", title=""):
        """What the widget shows from now on. An empty title keeps the one it has."""
        self._guard("set")
        self._need("set")
        self.text = "" if text is None else str(text)
        self.caption = "" if caption is None else str(caption)
        if rules.trim(title):
            self.title = str(title)
        if _root() is not None:
            from . import kit_surfaces
            kit_surfaces.peek("Home screen", "home", self._draw())
        return "ok"

    def count(self):
        """How many of them are on the home screen -- as text, like every
        value that comes back from the phone."""
        self._guard("count")
        self._need("count")
        return str(self._count)

    def pin(self):
        """Ask the launcher to put one on the home screen; the person places it."""
        self._guard("pin")
        self._need("pin")
        if _root() is None:
            self._count += 1
            return "ok"
        from .. import ui
        from . import kit_surfaces
        root = _root()

        def picture(canvas, x, y, width):
            return kit_surfaces.outside(ui, root, canvas, x, y, width, self._draw(card=True))

        def chosen(choice):
            if choice == "add":
                self._count += 1
                kit_surfaces.peek("Home screen", "home", self._draw())

        kit_surfaces.Handover(
            "pin", "widgets", "Home screen", "Add to Home screen?", picture=picture,
            choices=[("Add to Home screen", "add"), ("Cancel", "cancel")],
            note="The launcher asks this and the person drops the widget where they "
                 "want it. Dragged taller, it becomes this card; one cell high, it is "
                 "a single row.",
            on_choice=chosen).open()
        return "ok"


home_widget = HomeWidgetAPI()


class QuickTileAPI(_Declared):
    """The app's tile in quick settings.

    One line says the app has one::

        quick_tile.define("Walk", icon="directions_walk")

    ``quick_tile.set(True, subtitle="On a walk")`` lights it. A tap on the
    tile opens the app, and its first screen asks ``quick_tile.opened()``.
    Nobody pulls a shade down on the desk, so ``define(..., preview=True)``
    has the Previewer pretend the tile is how the person arrived.
    """

    namespace = "quick_tile"

    def __init__(self):
        super().__init__()
        self.label = self.icon = self.subtitle = ""
        self._active = False
        self._opened = False
        self._added = False

    def define(self, label, icon="", preview=False):
        """That the app has a tile. Written once, at the top of the file."""
        if not rules.trim(label):
            rules.refuse("quick_tile.define(): a tile has a name",
                         received="quick_tile.define(%r)" % (label,),
                         suggestions=[rules.DECLARED_BY["quick_tile"][2]])
        self.declared = {"label": str(label), "icon": str(icon or ""),
                         "preview": bool(preview)}
        self.label, self.icon = self.declared["label"], self.declared["icon"]
        self._opened = bool(preview)

    def _draw(self, wide=False, lit=None):
        from .. import ui
        from . import kit_surfaces
        root = _root()

        def draw(canvas, x, y, width):
            # A tile is half the shade wide; on its own it is drawn at that width.
            span = width if wide else min(width, 190)
            return kit_surfaces.draw_tile(
                ui, root, canvas, x, y, span, kit_surfaces.widget_palette(ui, root),
                self.label, self.subtitle, self.icon,
                self._active if lit is None else lit)
        return draw

    def set(self, active=True, subtitle=""):
        """Whether the tile is lit, and the line under its name."""
        self._guard("set")
        self._need("set")
        self._active = _yes(active)
        self.subtitle = "" if subtitle is None else str(subtitle)
        if _root() is not None:
            from . import kit_surfaces
            kit_surfaces.peek("Quick settings", "tune", self._draw())
        return "ok"

    def is_active(self):
        """Whether the tile is lit."""
        self._guard("is_active")
        self._need("is_active")
        return self._active

    def opened(self):
        """Whether a tap on the tile is what opened the app."""
        self._guard("opened")
        self._need("opened")
        return self._opened

    def clear(self):
        """Forget that the tile opened the app, once it is dealt with."""
        self._guard("clear")
        self._need("clear")
        self._opened = False
        return "ok"

    def offer(self, on_result=None):
        """Ask the person to add the tile to quick settings."""
        self._guard("offer")
        self._need("offer")
        if self._added:
            _answer(on_result, True, "already")
            return
        if _root() is None:
            self._added = True
            _answer(on_result, True, "added")
            return
        from .. import ui
        from . import kit_surfaces
        root = _root()

        def picture(canvas, x, y, width):
            # Android shows the tile it is asking about lit, whatever the
            # app last set.
            return kit_surfaces.outside(ui, root, canvas, x, y, width, self._draw(lit=True))

        def chosen(choice):
            if choice == "add":
                self._added = True
                _answer(on_result, True, "added")
            else:
                _answer(on_result, False, "dismissed")

        kit_surfaces.Handover(
            "tile", "tune", "Quick settings",
            "Add %s to Quick Settings?" % (self.label.strip() or "this tile"),
            picture=picture, choices=[("Add tile", "add"), ("Do not add tile", "no")],
            note="On the phone this is Android's own dialog, in the phone's colours and "
                 "language: the app gives the tile its name and its icon, nothing else. "
                 "Before Android 13 nobody is asked, and this call answers \"unsupported\".",
            on_choice=chosen, on_close=lambda: chosen("no")).open()


quick_tile = QuickTileAPI()


class AdsAPI(_Declared):
    """Google AdMob: a banner, an ad between two screens, an ad for a reward.

    ::

        ads.setup("test")                       # your AdMob app id, before release
        ads.banner("test")                      # along the bottom of this screen
        ads.interstitial("test", on_result=carry_on)
        ads.rewarded("test", on_result=paid)    # paid(ok, amount)

    ``"test"`` is Google's own sample, on the phone as well: a real ad that
    costs nobody anything. The desk shows where each ad goes and answers as
    the phone would, so the app around them can be finished before there is
    an AdMob account at all.

    On the phone the person is asked for consent before the first ad, where
    the law requires it and without the app doing anything. The desk only
    shows that question when ``ads.consent()`` is called.
    """

    namespace = "ads"

    def __init__(self):
        super().__init__()
        self._banner = None
        # A banner is asked for by a screen and is that screen's: going to
        # another screen and coming back finds it where it was.
        self._banners = {}          # screen -> whether it is along the top
        self._asked = False
        self.last = None            # ("banner", unit, position), ("interstitial", unit)...

    def _screen(self):
        from .. import ui
        return getattr(ui.live_preview(), "_active_screen", None)

    def _show(self, screen):
        if self._banner is not None:
            self._banner.close()
            self._banner = None
        if screen in self._banners and _root() is not None:
            from . import kit_surfaces
            self._banner = kit_surfaces.Banner(top=self._banners[screen]).open()

    def setup(self, app_id):
        """Which AdMob app this is. Written once, at the top of the file."""
        found = rules.ad_app_id(app_id)
        if not found:
            rules.refuse('ads.setup(): app_id= is the id AdMob gives the app -- '
                         '"ca-app-pub-1234567890123456~1234567890" -- or "test"',
                         received="ads.setup(%r)" % (app_id,),
                         suggestions=[rules.DECLARED_BY["ads"][2]])
        self.declared = {"app_id": found}

    @property
    def banner_shown(self):
        return self._banner is not None and self._banner.shown

    def banner(self, unit, position="bottom"):
        """A banner along the bottom of this screen, or the top."""
        self._guard("banner")
        self._need("banner")
        if not rules.ad_unit(unit, "banner"):
            return "invalid"
        top = rules.trim(position) == "top"
        self.last = ("banner", rules.trim(unit), "top" if top else "bottom")
        screen = self._screen()
        self._banners[screen] = top
        self._show(screen)
        return "ok"

    def hide_banner(self):
        """Take the banner away; the screen gets its room back."""
        self._guard("hide_banner")
        self._need("hide_banner")
        screen = self._screen()
        self._banners.pop(screen, None)
        self._show(screen)
        return "ok"

    def prepare(self, interstitial="", rewarded=""):
        """Fetch these ahead, so they open the moment they are asked for."""
        self._guard("prepare")
        self._need("prepare")
        for unit, kind in ((interstitial, "interstitial"), (rewarded, "rewarded")):
            if rules.trim(unit) and not rules.ad_unit(unit, kind):
                return "invalid"
        return "ok"

    def _full(self, kind, unit, on_result):
        self._guard(kind)
        self._need(kind)
        if not rules.ad_unit(unit, kind):
            _answer(on_result, False, "invalid")
            return
        self.last = (kind, rules.trim(unit))
        paid = kind == "rewarded"
        if _root() is None:
            _answer(on_result, True, rules.AD_REWARD if paid else "closed")
            return

        def closed(earned):
            if paid:
                _answer(on_result, bool(earned), rules.AD_REWARD if earned else "skipped")
            else:
                _answer(on_result, True, "closed")

        from . import kit_surfaces
        kit_surfaces.ad_cover(paid, closed)

    def interstitial(self, unit, on_result=None):
        """A full-screen ad, at a pause in the app."""
        self._full("interstitial", unit, on_result)

    def rewarded(self, unit, on_result=None):
        """An ad the person chooses to watch. Answers the reward's amount."""
        self._full("rewarded", unit, on_result)

    def _form(self, on_result, closing_is_ok):
        if _root() is None:
            self._asked = True
            _answer(on_result, True, "ok")
            return

        def chosen(_choice):
            self._asked = True
            _answer(on_result, True, "ok")

        def left():
            if closing_is_ok:
                _answer(on_result, True, "ok")
            else:
                _answer(on_result, False, "failed")

        from . import kit_surfaces
        kit_surfaces.Handover(
            "consent", "verified_user", "Google",
            _named("%s asks for your consent to use your personal data"),
            rows=[("ads_click", "Personalised advertising and content, advertising and "
                                "content measurement"),
                  ("devices", "Store and access information on this device")],
            choices=[("Consent", "yes"), ("Do not consent", "no"),
                     ("Manage options", "manage")],
            note="Google's own form. It is shown where the law requires it -- the EEA, "
                 "the UK, Switzerland -- and nowhere else. Any answer lets ads be "
                 "requested; it decides which.",
            on_choice=chosen, on_close=left).open()

    def consent(self, on_result=None):
        """Ask what the law where the person lives says to ask."""
        self._guard("consent")
        self._need("consent")
        if self._asked:
            _answer(on_result, True, "ok")
            return
        self._form(on_result, closing_is_ok=False)

    def needs_privacy_options(self):
        """Whether the app has to offer a way back to that question."""
        self._guard("needs_privacy_options")
        self._need("needs_privacy_options")
        return self._asked

    def privacy_options(self, on_result=None):
        """Open the question again, for the person to change their answer."""
        self._guard("privacy_options")
        self._need("privacy_options")
        self._form(on_result, closing_is_ok=True)


ads = AdsAPI()


class UpdatesAPI(_Api):
    """A newer version of the app, taken from Google Play without leaving it.

    ::

        updates.check(on_result=found)          # found(ok, "available")
        updates.start("flexible", on_result=ready)
        updates.install()                       # restarts into it

    Only a copy of the app that came from Play can be compared with Play: on
    a phone, a build installed over a cable answers ``"not_from_play"``. So
    that the screens an app builds around an update can be seen at all, the
    desk always has one waiting.
    """

    namespace = "updates"

    def __init__(self):
        self._downloaded = False
        self._installed = False

    def _state(self):
        if self._installed:
            return False, "none"
        if self._downloaded:
            return True, "downloaded"
        return True, "available"

    def check(self, on_result=None):
        """Ask Play whether there is a newer version."""
        self._guard("check")
        ok, word = self._state()
        _later(0.35, lambda: _answer(on_result, ok, word))

    def start(self, mode="flexible", on_result=None):
        """Download it: behind the app, or over the whole screen."""
        self._guard("start")
        ok, word = self._state()
        if word != "available":
            _answer(on_result, ok, word)
            return
        immediate = rules.trim(mode) == "immediate"

        def installed():
            self._installed = True
            _answer(on_result, True, "ok")

        def downloaded():
            self._downloaded = True
            _answer(on_result, True, "downloaded")

        if _root() is None:
            installed() if immediate else downloaded()
            return
        from . import kit_surfaces
        if immediate:
            def left(done):
                if done:
                    kit_surfaces.caption("On the phone the app restarts here, into "
                                         "the new version", 2.6, icon="restart_alt")
                    installed()
                else:
                    _answer(on_result, False, "cancelled")
            kit_surfaces.update_cover(_named("%s"), left)
            return

        def chosen(choice):
            if choice != "yes":
                _answer(on_result, False, "cancelled")
                return
            kit_surfaces.caption("Downloading the update\u2026", 1.8, icon="download")
            _later(1.9, downloaded)

        kit_surfaces.Handover(
            "update", "shop", "Google Play", "Update available",
            rows=[("system_update", _named("%s has a newer version")),
                  ("download", "It downloads while you carry on")],
            choices=[("Update", "yes"), ("No thanks", "no")],
            note="On the phone this is Google Play's own sheet, and only a copy of the "
                 "app that came from Play is shown it.",
            on_choice=chosen, on_close=lambda: chosen("no")).open()

    def install(self):
        """Restart into the version that was downloaded."""
        self._guard("install")
        if not self._downloaded:
            return "nothing"
        self._downloaded = False
        self._installed = True
        if _root() is not None:
            from . import kit_surfaces
            kit_surfaces.caption("On the phone the app restarts here, into the new version",
                                 2.6, icon="restart_alt")
        return "ok"


updates = UpdatesAPI()


# What Health Connect calls each kind, on the screen where the person decides.
_HEALTH_NAMES = {
    "steps": "Steps", "distance": "Distance",
    "active_calories": "Active calories burned", "calories": "Total calories burned",
    "heart_rate": "Heart rate", "resting_heart_rate": "Resting heart rate",
    "sleep": "Sleep", "weight": "Weight", "floors": "Floors climbed",
    "exercise": "Exercise", "hydration": "Hydration",
}


class HealthAPI(_Declared):
    """What the phone's health records say: steps, heart rate, sleep.

    ::

        health.policy("https://example.com/privacy")
        health.ask("steps, heart_rate", on_result=asked)
        health.read("steps", on_result=got)                 # today so far
        health.read("sleep", start="2026-10-04 20:00", on_result=got)

    The records are Health Connect's, which is part of Android from 14 on.
    A desk has no body, so the Previewer answers a plausible reading: the
    same day always gives the same number and no two days quite the same,
    which is what a chart needs to look like a chart.
    """

    namespace = "health"

    def __init__(self):
        super().__init__()
        self._granted = set()

    def policy(self, url):
        """Where the app's privacy policy is. Written once, at the top of the file."""
        if not rules.web_address(url):
            rules.refuse("health.policy(): url= is the address of the privacy policy, "
                         "starting with https://",
                         received="health.policy(%r)" % (url,),
                         suggestions=[rules.DECLARED_BY["health"][2]])
        self.declared = {"url": rules.trim(url)}

    def _kinds(self, verb, text, one):
        kinds, wrong = rules.health_kinds(text)
        label = rules.label("health", verb)
        if kinds is None:
            rules.refuse("%s: there is no kind %r" % (label, wrong),
                         received="health.%s(%r)" % (verb, text),
                         suggestions=["One of: %s." % ", ".join(rules.HEALTH_KINDS)])
        if not kinds or (one and len(kinds) != 1):
            rules.refuse("%s takes %s" % (label, "one kind" if one else "at least one kind"),
                         received="health.%s(%r)" % (verb, text))
        return kinds

    def available(self):
        """Whether this phone keeps health records an app can ask for."""
        self._guard("available")
        self._need("available")
        return True

    def allowed(self, kind):
        """Whether the app may read this."""
        self._guard("allowed")
        self._need("allowed")
        return self._kinds("allowed", kind, True)[0] in self._granted

    def ask(self, kinds, on_result=None):
        """Ask the person to let the app read these."""
        self._guard("ask")
        self._need("ask")
        wanted = self._kinds("ask", kinds, False)
        if all(kind in self._granted for kind in wanted) or _root() is None:
            self._granted.update(wanted)
            _answer(on_result, True, "ok")
            return

        def chosen(choice):
            if choice == "allow":
                self._granted.update(wanted)
                _answer(on_result, True, "ok")
            else:
                _answer(on_result, False, "denied")

        from . import kit_surfaces
        kit_surfaces.Handover(
            "health", "health_and_safety", "Health Connect",
            _named("Allow %s to read your health data?"),
            rows=[(rules.HEALTH_KINDS[kind][2], _HEALTH_NAMES[kind]) for kind in wanted],
            choices=[("Allow", "allow"), ("Don\u2019t allow", "deny")],
            note="On the phone this is Health Connect's own screen, with a switch for "
                 "each kind and a link to the app's privacy policy.",
            on_choice=chosen, on_close=lambda: chosen("deny")).open()

    def read(self, kind, start="", end="", on_result=None):
        """The total, or the average, between two moments -- today when none
        is given."""
        self._guard("read")
        self._need("read")
        what = self._kinds("read", kind, True)[0]
        import datetime
        period = rules.health_period(start, end, datetime.datetime.now())
        if period is None:
            _answer(on_result, False, "invalid")
        elif what not in self._granted:
            _answer(on_result, False, "no_permission")
        else:
            _answer(on_result, True, rules.health_sample(what, period[0], period[1]))


health = HealthAPI()


# ── timer ────────────────────────────────────────────────────────────────────

def _function_name(label, run):
    """The name a function of the app is called by, or the build's own
    refusal: a function with a name, written at the top of the file, that
    takes nothing."""
    name = getattr(run, "__name__", "")
    plain = inspect.isfunction(run) and name != "<lambda>" \
        and getattr(run, "__qualname__", name) == name
    if not plain:
        rules.refuse(**rules.timer_not_a_function(
            label, "%s%s)" % (label[:-1], name or type(run).__name__)))
    taken = []
    for parameter in inspect.signature(run).parameters.values():
        star = {parameter.VAR_POSITIONAL: "*", parameter.VAR_KEYWORD: "**"}
        taken.append(star.get(parameter.kind, "") + parameter.name)
    if taken:
        rules.refuse(**rules.timer_takes_nothing(label, name, taken))
    return name


class _Waiting:
    """One timer: the function, how far apart, and the moment it waits for."""

    __slots__ = ("name", "run", "period", "due", "handle")

    def __init__(self, name, run, period, due):
        self.name, self.run, self.period, self.due = name, run, period, due
        self.handle = None


class _Clockwork:
    """Which function waits on which screen, and what a moment going by does.

    ApkpyTimers again, with whatever wakes it in place of the phone's Handler.
    It is handed its clock and its way of being woken, so a test can be both
    and no test has to wait for time to pass.

    One thing is the desk's own. On the phone a screen left with Back is
    closed and its timers end; the Previewer keeps every screen it has drawn
    (a screen's ``on_mount`` runs once here), so a timer waits for its screen
    to be on show again. Opened a second time, the screen's clock is ticking
    on both -- started again on the phone, carried on here.
    """

    def __init__(self, now, wake, unwake):
        self.now, self.wake, self.unwake = now, wake, unwake
        self._waiting = {}      # screen -> {name: _Waiting}
        self._shown = None      # the screen on show; None before there is one

    def start(self, screen, seconds, name, run, repeating):
        millis = rules.timer_millis(seconds, repeating)
        if millis < 0:
            return "invalid"
        mine = self._waiting.setdefault(screen, {})
        before = mine.pop(name, None)
        if before is not None:
            self._unpost(before)
        timer = mine[name] = _Waiting(name, run, millis if repeating else 0,
                                      self.now() + millis)
        if screen == self._shown:
            self._post(screen, timer)
        return "ok"

    def cancel(self, screen, name):
        timer = self._waiting.get(screen, {}).pop(name, None)
        if timer is None:
            return "not_running"
        self._unpost(timer)
        return "ok"

    def running(self, screen, name):
        return name in self._waiting.get(screen, {})

    def shown(self, screen):
        """``screen`` is the one on show now: its timers run, the others wait.
        What fell due while it was away runs once, at once."""
        early = self._waiting.pop(None, None) if screen is not None else None
        if early:
            # Started before any screen was on show; the first one has them.
            mine = self._waiting.setdefault(screen, {})
            for name, timer in early.items():
                mine.setdefault(name, timer)
        self._shown = screen
        for owner, mine in list(self._waiting.items()):
            for timer in list(mine.values()):
                if owner == screen:
                    self._post(owner, timer)
                else:
                    self._unpost(timer)

    def forget(self):
        for mine in self._waiting.values():
            for timer in mine.values():
                self._unpost(timer)
        self._waiting = {}
        self._shown = None

    def _post(self, screen, timer):
        self._unpost(timer)
        timer.handle = self.wake(max(0, timer.due - self.now()),
                                 lambda: self._fire(screen, timer))

    def _unpost(self, timer):
        if timer.handle is not None:
            self.unwake(timer.handle)
        timer.handle = None

    def _fire(self, screen, timer):
        timer.handle = None
        mine = self._waiting.get(screen)
        if mine is None or mine.get(timer.name) is not timer or screen != self._shown:
            return
        # Settled before the function runs, as on the phone: running() is
        # false inside an after(), and either kind can stop itself or start
        # itself over.
        if timer.period > 0:
            timer.due = rules.timer_next(timer.due, timer.period, self.now())
            self._post(screen, timer)
        else:
            del mine[timer.name]
        timer.run()


class TimerAPI(_Api):
    """A function of the app run later, or again and again.

        timer.after(2, hide_banner)      # once, two seconds from now
        timer.every(1, tick)             # every second
        timer.cancel(tick)               # stop that one
        if timer.running(tick): ...

    A timer is known by the function it calls and belongs to the screen that
    is on show when it is started. Starting one for a function that already
    has one starts it over, so ``timer.after(0.4, search)`` on every keystroke
    searches once, when the typing stops.

    Time keeps going by while the screen is not on show and nothing is run
    meanwhile; when it comes back, what fell due runs once. The Previewer
    follows the same rule for the screen in its window.
    """

    namespace = "timer"

    def __init__(self):
        self._clockwork = _Clockwork(self._now, self._wake, self._unwake)
        self._window = None

    @staticmethod
    def _now():
        return int(time.monotonic() * 1000)

    @staticmethod
    def _wake(millis, work):
        root = _root()
        if root is None:
            return None             # no window: nothing is on show to run for
        from . import kit_surfaces
        ident = kit_surfaces.later(root, millis / 1000.0, work)
        return None if ident is None else (root, ident)

    @staticmethod
    def _unwake(handle):
        root, ident = handle
        try:
            root.after_cancel(ident)
        except Exception:
            pass

    @staticmethod
    def _screen():
        """The screen on show, which is the one a call made now belongs to."""
        from .. import ui
        live = ui.live_preview()
        return getattr(live, "_active_screen", None) if live is not None else None

    def _named(self, verb, run, seconds=None):
        """The name of the function ``run``, or the build's own refusal."""
        label = rules.label(self.namespace, verb)
        if seconds is not None and callable(seconds):
            rules.refuse(**rules.timer_swapped(label, getattr(seconds, "__name__", "tick")))
        return _function_name(label, run)

    def _start(self, verb, seconds, run, repeating, written_in):
        self._guard(verb)
        name = self._named(verb, run, seconds)
        if written_in == "<module>":
            rules.refuse(**rules.timer_at_the_top(rules.label(self.namespace, verb)))
        return self._clockwork.start(self._screen(), seconds, name, run, repeating)

    def after(self, seconds, run):
        """Run the function once, this many seconds from now. Answers
        ``"ok"``, or ``"invalid"`` when ``seconds`` is not a time."""
        return self._start("after", seconds, run, False, sys._getframe(1).f_code.co_name)

    def every(self, seconds, run):
        """Run the function again and again, this many seconds apart -- never
        more often than twenty times a second. Answers as ``after()`` does."""
        return self._start("every", seconds, run, True, sys._getframe(1).f_code.co_name)

    def cancel(self, run):
        """Stop the timer of that function. Answers ``"ok"``, or
        ``"not_running"`` when it had none waiting on this screen."""
        self._guard("cancel")
        return self._clockwork.cancel(self._screen(), self._named("cancel", run))

    def running(self, run):
        """Whether that function has a timer waiting on this screen."""
        self._guard("running")
        return self._clockwork.running(self._screen(), self._named("running", run))

    def _screen_shown(self, screen):
        # A second Previewer in one process -- a test run -- starts clean.
        root = _root()
        if self._window is not None and root is not self._window:
            self._clockwork.forget()
        self._window = root
        self._clockwork.shown(screen)


timer = TimerAPI()


# ── network ──────────────────────────────────────────────────────────────────

class _Watchers:
    """Which functions are told of a change on which screen, and what each
    screen last heard.

    ApkpyNetwork again, without Android. It is handed the way to read the
    connection, so a test can be the connection. A screen's functions are
    called when the three answers, as one text, are not what the screen last
    heard, and only while it is the one on show: a change that comes and goes
    while it is away is not told, one that is still there when it comes back
    is told once.
    """

    def __init__(self, state):
        self.state = state
        self._watching = {}     # screen -> [what it last heard, {name: function}]
        self._shown = None

    def add(self, screen, name, run):
        mine = self._watching.get(screen)
        if mine is None:
            # From here: what the connection is now is not a change.
            mine = self._watching[screen] = [self.state(), {}]
        mine[1][name] = run
        return "ok"

    def shown(self, screen):
        early = self._watching.pop(None, None) if screen is not None else None
        if early:
            # Asked before any screen was on show; the first one has them.
            mine = self._watching.setdefault(screen, [early[0], {}])
            for name, run in early[1].items():
                mine[1].setdefault(name, run)
        self._shown = screen

    def changed(self):
        mine = self._watching.get(self._shown)
        if not mine or not mine[1]:
            return
        now = self.state()
        if now == mine[0]:
            return
        mine[0] = now
        for run in list(mine[1].values()):
            run()

    def forget(self):
        self._watching = {}
        self._shown = None


class NetworkAPI(_Api):
    """Whether the phone reaches the internet, over what, and being told when
    that changes.

        if network.online(): ...
        network.kind()                  # "wifi", "mobile", "ethernet", "other", "none"
        network.metered()               # mobile data, a hotspot
        network.on_change(changed)      # changed() is called when one of them changes

    A desk has no connection of its own to stand for the phone's: a computer
    is always on its cable or its Wi-Fi, and the screens an app has for being
    offline would never be seen. So the connection is the one drawn in the
    Previewer's status strip, and a click on it takes it from Wi-Fi to mobile
    data to none and round again. With none, ``https`` fails and a
    ``background_job`` that needs the network waits, as on a phone in a lift.
    """

    namespace = "network"
    # What the strip is switched between. A desk has no use for the other two.
    _SWITCH = ("wifi", "mobile", "none")

    def __init__(self):
        self._kind = "wifi"
        self._watchers = _Watchers(self._state)
        self._window = None

    def _state(self):
        return rules.network_state(
            rules.network_online(self._kind != "none", True, True), self._kind,
            rules.network_metered(self._kind != "none", self._kind != "mobile"))

    def online(self):
        """Whether the phone reaches the internet right now."""
        self._guard("online")
        return self._kind != "none"

    def kind(self):
        """What the connection is: ``"wifi"``, ``"mobile"``, ``"ethernet"``,
        ``"other"``, or ``"none"`` when there is not one."""
        self._guard("kind")
        return self._kind

    def metered(self):
        """Whether the person pays for what goes over the connection."""
        self._guard("metered")
        return self._kind == "mobile"

    def on_change(self, run):
        """Call the function whenever one of the three answers changes, while
        the screen that asked is on show. Answers ``"ok"``."""
        self._guard("on_change")
        label = rules.label(self.namespace, "on_change")
        name = _function_name(label, run)
        if sys._getframe(1).f_code.co_name == "<module>":
            rules.refuse(**rules.timer_at_the_top(label))
        return self._watchers.add(TimerAPI._screen(), name, run)

    # -- the Previewer's own ----------------------------------------------

    def _switch(self, kind=None):
        """Change the connection the Previewer stands in for; with nothing,
        to the next of Wi-Fi, mobile data and none. Answers what it is now."""
        if kind is None:
            at = self._SWITCH.index(self._kind) if self._kind in self._SWITCH else -1
            kind = self._SWITCH[(at + 1) % len(self._SWITCH)]
        if kind not in rules.NETWORK_KINDS:
            raise ValueError("the connection is one of %s, got %r"
                             % (", ".join(rules.NETWORK_KINDS), kind))
        if kind != self._kind:
            self._kind = kind
            _refresh_strip()
            _later(0, self._watchers.changed)
        return kind

    def _screen_shown(self, screen):
        # A second Previewer in one process -- a test run -- starts clean.
        root = _root()
        if self._window is not None and root is not self._window:
            self._watchers.forget()
            self._kind = "wifi"
        self._window = root
        self._watchers.shown(screen)
        _later(0, self._watchers.changed)


network = NetworkAPI()


def offline():
    """Whether the Previewer is standing in for a phone with no connection.
    What ``https`` and the job queue ask before they reach for the real one."""
    return network._kind == "none"


# ── display ──────────────────────────────────────────────────────────────────

class _Asked:
    """What one screen has asked of the display."""

    __slots__ = ("keep_on", "brightness", "immersive", "orientation")

    def __init__(self):
        self.keep_on = False
        self.brightness = rules.BRIGHTNESS_OWN
        self.immersive = False
        self.orientation = ""       # "" until the screen says which way up


_NOTHING_ASKED = _Asked()


class DisplayAPI(_Api):
    """What the phone's screen does while one of the app's screens is on show.

        display.keep_on(True)               # no dimming, no locking
        display.brightness(1.0)             # 0 to 1; "auto" gives it back
        display.immersive(True)             # the bars go; a swipe shows them
        display.orientation("landscape")    # "portrait", "landscape", "auto"

    Each belongs to the screen that asked and holds while that screen is the
    one on show: another screen opened over it has none of it, and coming
    back finds it as it was. Closing the screen ends it.

    A desk has no screen to keep awake and none to dim. The Previewer lights
    a cup in the device's strip while the screen on show keeps the phone on
    and a sun while it sets the brightness, takes the strip away for
    ``immersive``, and turns its own window for ``orientation``.
    """

    namespace = "display"

    def __init__(self):
        self._asked = {}        # screen -> _Asked
        self._window = None

    # -- what a screen has asked for ----------------------------------------

    def _for(self, screen):
        """What ``screen`` has asked for; nothing, when it never asked."""
        return self._asked.get(screen, _NOTHING_ASKED)

    def _mine(self, verb, written_in):
        self._guard(verb)
        if written_in == "<module>":
            rules.refuse(**rules.display_at_the_top(rules.label(self.namespace, verb)))
        return self._asked.setdefault(TimerAPI._screen(), _Asked())

    def keep_on(self, on=True):
        """Keep the phone from dimming and locking while this screen is on
        show. Answers ``"ok"``."""
        self._mine("keep_on", sys._getframe(1).f_code.co_name).keep_on = rules.truth(on)
        return self._changed()

    def brightness(self, level):
        """How bright the phone is while this screen is on show: from 0 to 1,
        or ``"auto"`` to give the level back to the phone. Answers ``"ok"``,
        or ``"invalid"`` when ``level`` is neither."""
        mine = self._mine("brightness", sys._getframe(1).f_code.co_name)
        read = rules.display_brightness(level)
        if read == rules.BRIGHTNESS_INVALID:
            return "invalid"
        mine.brightness = read
        return self._changed()

    def immersive(self, on=True):
        """Hide the status bar and the navigation bar. Answers ``"ok"``."""
        self._mine("immersive", sys._getframe(1).f_code.co_name).immersive = rules.truth(on)
        return self._changed()

    def orientation(self, kind):
        """Which way up this screen is: ``"portrait"``, ``"landscape"``, or
        ``"auto"`` to turn with the phone. Answers ``"ok"``, or ``"invalid"``
        when ``kind`` is none of the three."""
        mine = self._mine("orientation", sys._getframe(1).f_code.co_name)
        known = rules.display_orientation(kind)
        if not known:
            return "invalid"
        mine.orientation = known
        return self._changed()

    # -- the Previewer's own ------------------------------------------------

    def _changed(self):
        self._draw()
        return "ok"

    def _draw(self):
        """Show what the screen on show has asked for: the strip's two
        glyphs, the strip itself, and which way up the window is."""
        asked = self._for(TimerAPI._screen())
        wanted = [name for name, lit in (("awake", asked.keep_on),
                                         ("brightness", asked.brightness >= 0)) if lit]
        if [name for name in _LIT if name in ("awake", "brightness")] != wanted:
            # Both out and back in, so the cup is always before the sun
            # whichever was asked for first.
            _LIT.pop("awake", None)
            _LIT.pop("brightness", None)
            for name in wanted:
                _LIT[name] = None
            _refresh_strip()
        from .. import ui
        live = ui.live_preview()
        if live is not None:
            live._display_asked()

    def _says(self, glyph):
        """What one of the two glyphs stands for, in words."""
        asked = self._for(TimerAPI._screen())
        if glyph == "awake" and asked.keep_on:
            return "This screen keeps the phone on"
        if glyph == "brightness" and asked.brightness >= 0:
            return "Brightness %d%% on this screen" % int(round(asked.brightness * 100))
        return ""

    def _closed(self, screen):
        """``screen`` was left with Back: on the phone it is gone, and what it
        asked for went with it."""
        self._asked.pop(screen, None)

    def _screen_shown(self, screen):
        # A second Previewer in one process -- a test run -- starts clean.
        root = _root()
        if self._window is not None and root is not self._window:
            self._asked = {}
            _LIT.pop("awake", None)
            _LIT.pop("brightness", None)
        self._window = root
        self._draw()


display = DisplayAPI()


# ── the app's own lock ───────────────────────────────────────────────────────

def _padlock_photo(size, tonal, ink, background):
    """The cover's padlock on its tonal circle, drawn the way ApkpyAppLock's
    Padlock view draws it -- the same shackle, body and keyhole on the same
    grid of r/40 -- so the two do not differ by a keyhole. None without
    Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageTk
        from .. import ui
        grain = 4
        side = size * grain
        rgb = lambda colour: ui._hex_to_rgb(str(colour)) + (255,)
        # On the screen's own colour: a transparent black corner bled a dark
        # ring round the circle as the picture was made smaller.
        image = Image.new("RGBA", (side, side), rgb(background))
        draw = ImageDraw.Draw(image)
        c = side / 2.0
        unit = c / 40.0
        draw.ellipse((0, 0, side - 1, side - 1), fill=rgb(tonal))
        # The shackle: an arch over the body, its stroke centred on the line.
        width = 4.5 * unit
        half = width / 2.0
        draw.arc((c - 9 * unit - half, c - 20 * unit - half, c + 9 * unit + half, c - 2 * unit + half),
                 180, 360, fill=rgb(ink), width=int(round(width)))
        for x in (c - 9 * unit, c + 9 * unit):
            draw.line((x, c - 11 * unit, x, c - 3 * unit), fill=rgb(ink), width=int(round(width)))
        # The body, and its keyhole in the circle's colour.
        draw.rounded_rectangle((c - 15 * unit, c - 4 * unit, c + 15 * unit, c + 20 * unit),
                               radius=4 * unit, fill=rgb(ink))
        draw.ellipse((c - 3.5 * unit, c + 2.5 * unit, c + 3.5 * unit, c + 9.5 * unit), fill=rgb(tonal))
        draw.rounded_rectangle((c - 1.6 * unit, c + 7 * unit, c + 1.6 * unit, c + 13 * unit),
                               radius=1.6 * unit, fill=rgb(tonal))
        return ImageTk.PhotoImage(image.resize((size, size), Image.LANCZOS))
    except Exception:
        return None


class AppLockAPI(_Api):
    """The app locks itself, and the phone's own lock opens it again.

        app_lock.after(5)        # five minutes away, or untouched
        app_lock.now()           # a "Lock" button
        app_lock.off()           # no more locking
        if app_lock.locked(): ...

    The rule is the app's, not a screen's: once said it is kept, beside the
    app's storage, and every screen follows it -- after the app is closed
    too. The app is locked as it comes back after the minutes away, or once
    nobody has touched it for that long while it is in front; 0 locks it
    every time it comes back.

    Locked, the app is covered and the phone's own prompt asks for a
    fingerprint, a face or the screen lock. In the Previewer, minimising the
    window is the app going to the background and closing it is the app
    closed; a click or a key is a touch. The prompt is the one
    ``biometrics.unlock()`` draws: click the sensor, or Use PIN.
    """

    namespace = "app_lock"

    def __init__(self):
        # The desk stands in for a phone with a screen lock. A test sets
        # this to False for the phone that has none.
        self.secure = True
        self._forget_window()
        self._window = None

    def _forget_window(self):
        self._locked = False
        self._asking = False
        self._just_said = False
        self._in_front = False
        self._touched_at = time.monotonic()
        self._cover = None
        self._idle_after = None

    # -- the rule, kept beside the app's own storage ------------------------

    @staticmethod
    def _path():
        from .. import ui
        folder = os.path.dirname(os.path.abspath(ui.storage._path))
        return os.path.join(folder, rules.APP_LOCK_FILE)

    def _rule(self):
        import json
        try:
            with open(self._path(), encoding="utf-8") as handle:
                kept = json.load(handle)
        except (OSError, ValueError):
            return {}
        return kept if isinstance(kept, dict) else {}

    def _keep(self, **changes):
        import json
        kept = self._rule()
        kept.update(changes)
        try:
            with open(self._path(), "w", encoding="utf-8") as handle:
                json.dump(kept, handle, indent=2)
        except OSError:
            pass

    def _ruled(self):
        return "minutes" in self._rule()

    # -- the calls ----------------------------------------------------------

    def _mine(self, verb, written_in):
        self._guard(verb)
        if written_in == "<module>":
            rules.refuse(**rules.app_lock_at_the_top(rules.label(self.namespace, verb)))

    def after(self, minutes, title=""):
        """Lock the app once it has been away, or untouched, for this many
        minutes -- 0 locks it every time it comes back. Answers ``"ok"``,
        ``"invalid"`` when ``minutes`` is not a number from 0, or
        ``"no_lock"`` on a phone with no screen lock, where the rule is kept
        and holds once one is set."""
        self._mine("after", sys._getframe(1).f_code.co_name)
        read = rules.app_lock_minutes(minutes)
        if read == rules.APP_LOCK_INVALID:
            return "invalid"
        if not self._ruled() and not self._in_front:
            # Said as the app opens, for the first time: what it did before
            # it had a rule is no reason to lock it now.
            self._just_said = True
        self._keep(minutes=read, title=rules.trim(title))
        self._touched()
        self._idle()
        return "ok" if self.secure else "no_lock"

    def now(self):
        """Lock the app now. Answers ``"ok"``, or ``"no_lock"`` on a phone
        with no screen lock, which nothing could open again."""
        self._mine("now", sys._getframe(1).f_code.co_name)
        if not self.secure:
            return "no_lock"
        self._lock()
        return "ok"

    def off(self):
        """No more locking: the rule is taken away, and a locked app opened.
        Answers ``"ok"``."""
        self._mine("off", sys._getframe(1).f_code.co_name)
        try:
            os.remove(self._path())
        except OSError:
            pass
        if self._locked:
            self._open()
        self._cancel_idle()
        return "ok"

    def locked(self):
        """Whether the app is locked right now."""
        self._mine("locked", sys._getframe(1).f_code.co_name)
        return self._locked

    # -- in front, and away ---------------------------------------------------

    def _screen_shown(self, screen):
        root = _root()
        if root is None:
            return
        if root is not self._window:
            # A new Previewer is the app's process starting: what is kept on
            # disk decides, as on the phone.
            self._forget_window()
            self._window = root
            self._watch(root)
            self._came_back()
        elif self._locked:
            self._draw_cover()

    def _watch(self, root):
        def mapped(event):
            if event.widget is root:
                self._came_back()

        def unmapped(event):
            if event.widget is root:
                self._went_away()

        def touched(_event):
            self._touched()

        try:
            root.bind("<Map>", mapped, add="+")
            root.bind("<Unmap>", unmapped, add="+")
            root.bind("<Destroy>", unmapped, add="+")
            for sequence in ("<ButtonPress>", "<KeyPress>", "<MouseWheel>"):
                root.bind_all(sequence, touched, add="+")
        except Exception:
            pass

    def _came_back(self):
        if self._in_front:
            return
        self._in_front = True
        if self._just_said:
            self._just_said = False
            return
        self._touched()
        if self._asking:
            return
        kept = self._rule()
        if self._locked or (kept.get("locked") and self.secure):
            self._locked = False            # drawn again, and asked again
            self._lock()
            return
        if "minutes" not in kept:
            return
        left_at = kept.get("left_at", 0)
        self._keep(left_at=0)
        minutes = rules.app_lock_minutes(kept.get("minutes"))
        if self.secure and rules.app_lock_due(left_at, time.time() * 1000.0, minutes):
            self._lock()
        else:
            self._idle()

    def _went_away(self):
        if not self._in_front:
            return
        self._in_front = False
        self._cancel_idle()
        if self._ruled() and not self._asking:
            self._keep(left_at=time.time() * 1000.0)

    # -- untouched ------------------------------------------------------------

    def _touched(self):
        self._touched_at = time.monotonic()

    def _cancel_idle(self):
        if self._idle_after is not None and self._window is not None:
            try:
                self._window.after_cancel(self._idle_after)
            except Exception:
                pass
        self._idle_after = None

    def _idle(self):
        """Lock once nobody has touched the app for the minutes, or look
        again then."""
        self._cancel_idle()
        root = _root()
        kept = self._rule()
        if root is None or self._locked or not self._in_front or "minutes" not in kept:
            return
        minutes = rules.app_lock_minutes(kept.get("minutes"))
        if minutes <= 0:
            return
        wait = minutes * 60.0 - (time.monotonic() - self._touched_at)
        if wait <= 0:
            if self.secure:
                self._lock()
            return
        from . import kit_surfaces
        self._idle_after = kit_surfaces.later(root, wait, self._idle)

    # -- locked ---------------------------------------------------------------

    def _lock(self):
        if self._locked or not self.secure:
            return
        self._locked = True
        self._keep(locked=True)
        self._cancel_idle()
        self._draw_cover()
        self._ask()

    def _open(self):
        self._locked = False
        if os.path.exists(self._path()):
            self._keep(locked=False, left_at=0)
        if self._cover is not None:
            try:
                self._cover.destroy()
            except Exception:
                pass
        self._cover = None
        self._touched()
        self._idle()

    def _ask(self):
        if self._asking or not self._locked or _root() is None:
            return
        self._asking = True
        from ..core.features.biometrics import normalise_prompt
        from . import biometrics as _biometrics
        title = rules.app_lock_title(self._rule().get("title", ""), self._name())

        def answered(success, _reason):
            self._asking = False
            if success:
                self._open()

        _biometrics._show_prompt(normalise_prompt(title, None, None, True), answered)

    @staticmethod
    def _name():
        """The app's name from apkpy.toml, as the phone has it; "" for none."""
        try:
            from .. import ui
            return str(ui.app._config().get("name") or "").strip()
        except Exception:
            return ""

    def _draw_cover(self):
        """The app's name, a padlock and one button, over the screen."""
        from .. import ui
        live = ui.live_preview()
        body = getattr(live, "body", None) if live is not None else None
        if body is None:
            return
        if self._cover is not None:
            try:
                if self._cover.winfo_exists():
                    self._cover.lift()
                    return
            except Exception:
                pass
        import tkinter as tk
        tokens = ui.global_styles.get("__theme__", {})
        background = tokens.get("background", "#FFFBFE")
        text = tokens.get("text", "#1D1B20")
        muted = tokens.get("text_secondary", "#49454F")
        primary = tokens.get("primary", "#6750A4")
        on_primary = tokens.get("on_primary", "#FFFFFF")
        # The colour the phone takes too: apkpy_nav_indicator.
        tonal = tokens.get("nav_indicator") or ui._mix_hex(background, primary, 0.16)
        font = ui.get_native_font("")

        cover = tk.Frame(body, bg=background, cursor="arrow")
        cover.place(x=0, y=0, relwidth=1, relheight=1)
        cover.lift()
        self._cover = cover
        body.update_idletasks()
        width = max(1, body.winfo_width())

        column = tk.Frame(cover, bg=background)
        column.place(relx=0.5, rely=0.5, anchor="center")
        size = 80
        badge = tk.Canvas(column, width=size, height=size, bg=background,
                          highlightthickness=0, bd=0)
        photo = _padlock_photo(size, tonal, primary, background)
        if photo is not None:
            badge.create_image(size // 2, size // 2, image=photo)
            badge.image = photo
        else:
            ui._create_circle(badge, 0, 0, size - 1, size - 1, fill=tonal, outline="")
            ui._draw_material_icon(badge, "lock", size // 2, size // 2, primary, size=40)
        badge.pack()
        tk.Label(column, text=rules.app_lock_heading(self._name()), bg=background,
                 fg=text, font=(font, -22, "bold"), wraplength=max(200, width - 64),
                 justify="center").pack(pady=(24, 0))
        tk.Label(column, text=rules.APP_LOCK_WORDS["line"], bg=background, fg=muted,
                 font=(font, -14), wraplength=min(280, max(200, width - 64)),
                 justify="center").pack(pady=(8, 0))
        label = rules.APP_LOCK_WORDS["button"]
        pill_w, pill_h = 120, 48
        pill = tk.Canvas(column, width=pill_w, height=pill_h, bg=background,
                         highlightthickness=0, bd=0, cursor="hand2")
        ui._create_rounded_rect(pill, 0, 0, pill_w - 1, pill_h - 1, pill_h // 2,
                                fill=primary, outline="")
        pill.create_text(pill_w // 2, pill_h // 2, text=label, fill=on_primary,
                         font=(font, -14, "bold"))
        pill.bind("<Button-1>", lambda _event: self._ask())
        pill.pack(pady=(32, 0))


app_lock = AppLockAPI()
