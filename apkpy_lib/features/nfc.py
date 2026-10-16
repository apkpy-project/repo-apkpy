"""Foreground NFC API. Desktop tags are explicitly simulated, never scanned."""
from __future__ import annotations

import json
import weakref

from ..core.features.nfc import REASONS, decode_tag, write_record

__all__ = ["NfcAPI", "nfc"]


def _window():
    from .. import ui
    proxy = getattr(ui, "_app", None)
    app = None if proxy is None else getattr(proxy, "_instance", None)
    return (ui, app) if app is not None else (None, None)


def _report(callback, ok, value):
    if callback is not None:
        try:
            callback(ok, value)
        except Exception as exc:
            from ..ui import report_exception
            report_exception(exc, context="NFC callback")


def _tags():
    text = [(1, b"T", b"\x05pt-PT" + "Olá, ApkPy!".encode("utf-8"))]
    url = [(1, b"U", b"\x04example.com/nfc")]
    return {
        "Text tag": dict(kind="NDEF", writable="yes", size="492", records=text, tech="NfcA,Ndef"),
        "URL tag": dict(kind="NDEF", writable="yes", size="492", records=url, tech="NfcA,Ndef"),
        "Empty tag": dict(kind="FORMATABLE", writable="yes", size="", records=[], tech="NfcA,NdefFormatable"),
        "Read-only": dict(kind="NDEF", writable="no", size="492", records=text, tech="NfcA,Ndef"),
        "Small (12 B)": dict(kind="NDEF", writable="yes", size="12", records=[], tech="NfcA,Ndef"),
        "Unknown tech": dict(kind="UNKNOWN", writable="no", size="", records=[], tech="NfcA"),
    }


def _message_size(records):
    # NDEF header + type-length + payload-length (SR or normal) + type/payload.
    return sum(2 + (1 if len(p) < 256 else 4) + len(t) + len(p) for _, t, p in records)


class _Session:
    def __init__(self, ui, app, screen):
        self.ui, self.app = ui, app
        self.screen = weakref.ref(screen)
        self.started = False
        # Que sessao e esta. Sobe a cada start/stop, e o tap() compara-a
        # depois de correr um callback: um callback pode reiniciar o leitor,
        # e o resultado da sessao anterior nao pertence a seguinte. O Android
        # faz o mesmo com a sua revision.
        self.revision = 0
        self.on_tag = self.on_error = None
        self.panel = self.caption = None
        self.pending = None
        self.tags = _tags()
        # Chain, do not replace, the application's lifecycle callbacks.
        info = ui._screen_lifecycles.setdefault(screen, {"mounted": True})
        for event, action in (("on_pause", self.pause), ("on_resume", self.resume), ("on_destroy", self.stop)):
            previous = info.get(event)
            def chained(previous=previous, action=action):
                action()
                if previous is not None:
                    previous()
            info[event] = chained

    def start(self, on_tag, on_error):
        self.pending = None
        self.revision += 1
        self.on_tag, self.on_error = on_tag, on_error
        self.started = True
        self.open_panel()
        self.update_caption("Tap a tag below to simulate contact.")

    def resume(self):
        if self.started:
            self.open_panel()

    def pause(self):
        self.pending = None
        if self.panel is not None:
            try:
                self.panel.destroy()
            except Exception:
                pass
        self.panel = self.caption = None

    def stop(self):
        self.revision += 1
        self.started = False
        self.pause()
        self.on_tag = self.on_error = None

    def write(self, kind, value, callback):
        if not self.started:
            _report(callback, False, "not_started")
            return
        self.pending = None
        try:
            record = write_record(kind, value)
        except (ValueError, UnicodeError) as exc:
            print("[NFC]", exc)
            _report(callback, False, "unknown")
            return
        self.pending = (record, callback)
        self.update_caption('Write next: ' + repr(value.replace("\n", " ")[:32]))

    def cancel_write(self):
        self.pending = None
        self.update_caption("Write cancelled. Tap a tag to read.")

    def update_caption(self, value):
        if self.caption is not None:
            self.caption.configure(text=value)

    def tap(self, name):
        if not self.started or self.app._active_screen is not self.screen():
            return
        revision = self.revision
        if name == "Tag lost":
            if self.pending:
                _, callback = self.pending
                self.pending = None
                self.update_caption("Tag lost. Arm the write again to retry.")
                _report(callback, False, "tag_lost")
            else:
                _report(self.on_error, False, "tag_lost")
            return
        tag = self.tags[name]
        formatted_now = False
        if self.pending:
            record, callback = self.pending
            self.pending = None  # One attempt, including failures.
            error = ("no_ndef" if tag["kind"] == "UNKNOWN" else
                     "read_only" if tag["writable"] == "no" else
                     "too_small" if tag["size"] and _message_size([record]) > int(tag["size"]) else None)
            if error:
                self.update_caption(error + ". Arm the write again to retry.")
                _report(callback, False, error)
                return
            formatted_now = tag["kind"] == "FORMATABLE"
            tag["records"] = [record]
            tag["kind"], tag["tech"] = "NDEF", "NfcA,Ndef"
            if not tag["size"]:
                tag["size"] = "492"  # Simulated formatted tag capacity.
            self.update_caption("Written. The app receives the updated tag below.")
            _report(callback, True, "ok")
            # O callback da escrita pode ter chamado nfc.start() outra vez: a
            # leitura que se segue e desta sessao, nao da que acabou de fechar.
            if (revision != self.revision or not self.started
                    or self.app._active_screen is not self.screen()):
                return
        used = "" if tag["kind"] == "UNKNOWN" else str(_message_size(tag["records"]))
        value = decode_tag(bytes.fromhex("04A224B2C15E%02X" % (128 + list(self.tags).index(name))),
                           tag["kind"], tag["writable"], "" if formatted_now else tag["size"], used,
                           "NfcA,NdefFormatable" if formatted_now else tag["tech"], tag["records"])
        _report(self.on_tag, True, json.dumps(value, ensure_ascii=False))

    def open_panel(self):
        if self.panel is not None:
            return
        import tkinter as tk
        ui, app = self.ui, self.app
        tokens = ui.global_styles.get("__theme__", {})
        surface = tokens.get("surface_high", "#25232A")
        text = tokens.get("text", "#E6E1E5")
        muted = tokens.get("text_secondary", "#CAC4D0")
        primary = tokens.get("primary", "#D0BCFF")
        border = tokens.get("border_subtle", "#49454F")
        font = ui.get_native_font("")
        panel = tk.Frame(app.body, bg=surface, highlightbackground=border, highlightthickness=1)
        panel.place(relx=0, rely=1.0, anchor="sw", relwidth=1, height=190)
        panel.lift()
        self.panel = panel
        header = tk.Frame(panel, bg=surface)
        header.pack(fill="x", padx=12, pady=(8, 2))
        tk.Label(header, text="NFC SIMULATOR · NO RADIO", bg=surface, fg=primary,
                 font=(font, -11, "bold")).pack(side="left")
        tk.Button(header, text="✕", command=self.stop, bg=surface, fg=text,
                  activebackground=surface, relief="flat", bd=0, cursor="hand2").pack(side="right")
        self.caption = tk.Label(panel, text="Tap a tag below to simulate contact.", anchor="w",
                                bg=surface, fg=muted, font=(font, -11))
        self.caption.pack(fill="x", padx=12, pady=(0, 6))
        choices = tk.Frame(panel, bg=surface)
        choices.pack(fill="x", padx=8)
        for col in range(3):
            choices.columnconfigure(col, weight=1, uniform="tag")
        for i, name in enumerate(self.tags):
            tk.Button(choices, text=name, command=lambda name=name: self.tap(name),
                      bg=ui._mix_hex(surface, text, .07), fg=text,
                      activebackground=ui._mix_hex(surface, primary, .15), activeforeground=text,
                      relief="flat", bd=0, font=(font, -11), cursor="hand2",
                      padx=3, pady=8).grid(row=i // 3, column=i % 3, sticky="ew", padx=3, pady=3)
        tk.Button(panel, text="Simulate tag lost", command=lambda: self.tap("Tag lost"),
                  bg=surface, fg=muted, activebackground=surface, relief="flat", bd=0,
                  font=(font, -11), cursor="hand2").pack(anchor="w", padx=10, pady=2)


class NfcAPI:
    """NDEF reading/writing. All callbacks receive (ok, value)."""
    reasons = REASONS

    def __init__(self):
        self._sessions = weakref.WeakKeyDictionary()

    def _session(self, create=False):
        ui, app = _window()
        if app is None or app._active_screen is None:
            return None
        screen = app._active_screen
        session = self._sessions.get(screen)
        if session is None and create:
            session = self._sessions[screen] = _Session(ui, app, screen)
        return session

    def status(self, on_result=None):
        _report(on_result, True, "ready")

    def start(self, on_tag=None, on_error=None):
        session = self._session(create=True)
        if session is None:
            _report(on_error, False, "unsupported")
        else:
            session.start(on_tag, on_error)

    def stop(self):
        import threading
        if threading.current_thread() is not threading.main_thread():
            # A background job can stop the foreground reader, never read tags.
            ui, app = _window()
            if app is not None:
                app.root.after(0, lambda: [s.stop() for s in list(self._sessions.values())])
            return
        session = self._session()
        if session:
            session.stop()

    def write(self, *, text=None, url=None, on_result=None):
        """Arm ONE write for the next tag. Nothing is written immediately."""
        if (text is None) == (url is None):
            raise ValueError("nfc.write() needs exactly one of text= or url=")
        session = self._session()
        if session is None:
            _report(on_result, False, "not_started")
        else:
            session.write("text" if text is not None else "url", text if text is not None else url, on_result)

    def cancel_write(self):
        import threading
        if threading.current_thread() is not threading.main_thread():
            ui, app = _window()
            if app is not None:
                app.root.after(0, lambda: [s.cancel_write() for s in list(self._sessions.values())])
            return
        session = self._session()
        if session:
            session.cancel_write()

    def settings(self):
        session = self._session()
        if session and session.caption is not None:
            session.caption.configure(text="Simulation only. Enable real NFC in Android Settings.")


nfc = NfcAPI()
