"""Contacts API; desktop address book is synthetic, never the host's contacts."""
from __future__ import annotations
import json
import re
from copy import deepcopy
from ..core.features.contacts import REASONS

__all__ = ["ContactsAPI", "contacts"]

def _window():
    from .. import ui
    app = getattr(getattr(ui, "_app", None), "_instance", None)
    return ui, app

def _report(callback, ok, value):
    if callback:
        try: callback(ok, value)
        except Exception as exc:
            from ..ui import report_exception
            report_exception(exc, context="Contacts callback")

def _row(id, name, phone="", email=""):
    return {"id": str(id), "uri": "content://com.android.contacts/contacts/lookup/preview-" + str(id) + "/" + str(id),
            "name": name, "phone": phone, "email": email,
            "phones": [phone] if phone else [], "emails": [email] if email else []}

class _AddressBook:
    def __init__(self):
        self.rows = [_row(1, "Alex Morgan", "+1 202-555-0101", "alex@example.com"),
                     _row(2, "Jamie Lee", "+1 202-555-0102", "jamie@example.com"),
                     _row(3, "Sam Rivera", "+1 202-555-0103"),
                     _row(4, "Taylor Chen", email="taylor@example.com")]
        self.next_id = 5

    def get(self, id):
        id = str(id)
        if not re.fullmatch(r"[0-9]+", id):
            found = next((r for r in self.rows if r["uri"] == id), None)
        else: found = next((r for r in self.rows if r["id"] == id), None)
        return deepcopy(found)

    def list(self, query, limit, offset):
        # SQL NOCASE is ASCII case folding, not locale-aware casefold().
        fold = lambda s: s.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
        rows = sorted(self.rows, key=lambda r: (fold(r["name"]), int(r["id"])))
        return deepcopy([r for r in rows if fold(query) in fold(r["name"])][offset:offset + limit])

    def save(self, name, phone, email, id=None):
        if id is not None:
            original = self.get(id)
            if not original: return None
            self.rows = [r for r in self.rows if r["id"] != original["id"]]
            id = original["id"]
        else:
            id = self.next_id; self.next_id += 1
        result = _row(id, name, phone, email)
        self.rows.append(result)
        return deepcopy(result)

class ContactsAPI:
    """Two-argument callbacks; JSON for rows/editor returns, reason for errors."""
    reasons = REASONS

    def __init__(self):
        self._book = _AddressBook()
        self._permission = "ask"
        self._pending = None
        self._panel = None
        self._hooks = set()

    def pick(self, kind="phone", on_result=None):
        if kind not in ("phone", "email"): raise ValueError("Choose kind='phone' or 'email'")
        self._start("pick", {"kind": kind}, on_result)

    def list(self, query="", limit=50, offset=0, on_result=None):
        if not isinstance(query, str) or type(limit) is not int or type(offset) is not int or not 1 <= limit <= 100 or not 0 <= offset <= 100000:
            raise ValueError("Use query text, limit 1..100 and offset 0..100000")
        self._start("list", {"query": query, "limit": limit, "offset": offset}, on_result)

    def get(self, id, on_result=None):
        self._start("get", {"id": str(id)}, on_result)

    def create(self, name="", phone="", email="", on_result=None):
        if not all(isinstance(v, str) for v in (name, phone, email)): raise ValueError("Contact fields must be strings")
        self._start("create", {"name": name, "phone": phone, "email": email}, on_result)

    def edit(self, id, on_result=None):
        self._start("edit", {"id": str(id)}, on_result)

    def settings(self, on_result=None):
        self._start("settings", {}, on_result)

    def _start(self, verb, options, callback):
        import threading
        if threading.current_thread() is not threading.main_thread():
            _report(callback, False, "unavailable"); return
        ui, app = _window()
        if app is None or app._active_screen is None:
            _report(callback, False, "unavailable"); return
        if self._pending:
            _report(callback, False, "busy"); return
        screen = app._active_screen
        self._pending = (verb, options, callback, screen)
        if screen not in self._hooks:
            info = ui._screen_lifecycles.setdefault(screen, {"mounted": True})
            for event in ("on_pause", "on_destroy"):
                previous = info.get(event)
                def cleanup(previous=previous, screen=screen):
                    if self._pending and self._pending[3] is screen: self._finish(False, "cancelled")
                    if previous: previous()
                info[event] = cleanup
            self._hooks.add(screen)
        self._run()

    def _finish(self, ok, value):
        if not self._pending: return
        callback = self._pending[2]
        self._pending = None
        if self._panel is not None:
            self._panel.destroy(); self._panel = None
        _report(callback, ok, value)

    def _run(self):
        verb, options, callback, screen = self._pending
        if verb in ("list", "get"):
            # Uma recusa simples nao fecha a porta: o Android so deixa de
            # perguntar depois de "don't ask again", e e isso que o Java
            # gerado verifica com shouldShowRequestPermissionRationale.
            if self._permission in ("ask", "denied"): self._show("permission"); return
            if self._permission != "granted":
                self._finish(False, "permission_blocked"); return
            value = self._book.list(**options) if verb == "list" else self._book.get(options["id"])
            self._finish(value is not None, json.dumps(value, ensure_ascii=False) if value is not None else "not_found")
            return
        if verb == "edit" and not self._book.get(options["id"]): self._finish(False, "not_found"); return
        self._show(verb)

    def _grant(self, state):
        """A resposta ao painel de permissao.

        Uma recusa termina ESTA operacao; e a proxima que volta a perguntar.
        Reentrar no _run() aqui daria um painel a seguir ao outro para sempre,
        e no telemovel o que acontece e o pedido falhar e a app poder tentar
        outra vez mais tarde.
        """
        self._permission = state
        if self._pending[0] == "settings": self._finish(True, "opened")
        elif state == "granted": self._run()
        else: self._finish(False, "permission_blocked" if state == "blocked"
                           else "permission_denied")

    def _select(self, id):
        item = self._book.get(id)
        if item is None: self._finish(False, "not_found"); return
        kind = self._pending[1]["kind"]
        other = "email" if kind == "phone" else "phone"
        item[other] = ""; item[other + "s"] = []
        self._finish(True, json.dumps(item, ensure_ascii=False))

    def _editor_done(self, saved, fields=None):
        verb, options, _, _ = self._pending
        uri = ""
        if saved:
            item = self._book.save(*fields, id=options.get("id") if verb == "edit" else None)
            if item is None: self._finish(False, "not_found"); return
            uri = item["uri"]
        self._finish(True, json.dumps({"status": "editor_returned", "result_code": "ok" if saved else "cancelled", "uri": uri}))

    def _cancel(self):
        if self._pending and self._pending[0] in ("create", "edit"): self._editor_done(False)
        else: self._finish(False, "cancelled")

    def _show(self, mode):
        import tkinter as tk
        ui, app = _window()
        if self._panel is not None: self._panel.destroy()
        tokens = ui.global_styles.get("__theme__", {})
        surface = tokens.get("surface_high", "#25232A"); text = tokens.get("text", "#E6E1E5")
        muted = tokens.get("text_secondary", "#CAC4D0"); primary = tokens.get("primary", "#D0BCFF")
        font = ui.get_native_font("")
        panel = self._panel = tk.Frame(app.body, bg=surface, highlightbackground=muted, highlightthickness=1)
        panel.place(relx=0.025, rely=0.025, relwidth=.95, relheight=.95); panel.lift()
        header = tk.Frame(panel, bg=surface); header.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(header, text="CONTACTS · SIMULATED", bg=surface, fg=primary, font=(font, -11, "bold")).pack(side="left")
        def button(parent, title, command):
            b = tk.Button(parent, text=title, command=command, bg=surface, fg=primary,
                activebackground=ui._mix_hex(surface, primary, .12), activeforeground=text,
                font=(font, -13), relief="flat", bd=0, padx=10, pady=10, cursor="hand2")
            return b
        button(header, "Close", self._cancel).pack(side="right")
        title = {"permission": "Read your address book?", "settings": "Contacts access", "pick": "Choose a " + self._pending[1].get("kind", "phone"), "create": "New contact", "edit": "Edit contact"}[mode]
        tk.Label(panel, text=title, bg=surface, fg=text, font=(font, -22, "bold"), anchor="w").pack(fill="x", padx=16, pady=(8, 6))
        note = "Only fictional contacts. Your computer's address book is never read or changed."
        description = tk.Label(panel, text=note, bg=surface, fg=muted, font=(font, -12), justify="left", anchor="w")
        description.pack(fill="x", padx=16, pady=(0, 14))
        description.bind("<Configure>", lambda e: description.configure(wraplength=max(80, e.width - 2)))
        if mode in ("permission", "settings"):
            for title, value in (("Allow reading", "granted"), ("Deny", "denied"), ("Deny · don't ask again", "blocked")):
                button(panel, title, lambda value=value: self._grant(value)).pack(fill="x", padx=16, pady=4)
        elif mode == "pick":
            search = tk.StringVar()
            entry = tk.Entry(panel, textvariable=search, bg=surface, fg=text, insertbackground=text, font=(font, -14))
            entry.pack(fill="x", padx=16, pady=(0, 10))
            area = tk.Frame(panel, bg=surface); area.pack(fill="both", expand=True, padx=12, pady=4)
            scroll = tk.Scrollbar(area); scroll.pack(side="right", fill="y")
            canvas = tk.Canvas(area, bg=surface, highlightthickness=0, yscrollcommand=scroll.set)
            canvas.pack(side="left", fill="both", expand=True); scroll.configure(command=canvas.yview)
            choices = tk.Frame(canvas, bg=surface)
            window = canvas.create_window((0, 0), window=choices, anchor="nw")
            canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
            choices.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            def populate(*_):
                rows = [r for r in self._book.list(search.get(), 100, 0) if r[self._pending[1]["kind"]]]
                for child in choices.winfo_children(): child.destroy()
                if not rows:
                    tk.Label(choices, text="No matching contacts", bg=surface, fg=muted, font=(font, -13)).pack(pady=20)
                for r in rows:
                    tile = tk.Frame(choices, bg=ui._mix_hex(surface, text, .045), padx=12, pady=12)
                    tile.pack(fill="x", pady=(0, 8))
                    for title, color, weight in ((r["name"], text, "bold"), (r[self._pending[1]["kind"]], muted, "normal")):
                        line = tk.Label(tile, text=title, bg=tile.cget("bg"), fg=color, anchor="w", font=(font, -14, weight), cursor="hand2")
                        line.pack(fill="x")
                        line.bind("<Button-1>", lambda e, id=r["id"]: self._select(id))
                        line.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
                    tile.bind("<Button-1>", lambda e, id=r["id"]: self._select(id))
                canvas.yview_moveto(0)
            search.trace_add("write", populate); populate()
            canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
            tk.Label(panel, text="Tap one contact to return its selected detail.", bg=surface, fg=muted,
                     font=(font, -11)).pack(fill="x", padx=16, pady=12)
        else:
            options = self._pending[1]
            values = self._book.get(options["id"]) if mode == "edit" else options
            entries = []
            for key in ("name", "phone", "email"):
                tk.Label(panel, text=key.title(), bg=surface, fg=muted, anchor="w", font=(font, -12)).pack(fill="x", padx=16, pady=(8, 3))
                entry = tk.Entry(panel, bg=surface, fg=text, insertbackground=text, font=(font, -15))
                entry.insert(0, values.get(key, "")); entry.pack(fill="x", padx=16, ipady=6); entries.append(entry)
            button(panel, "Save simulated contact", lambda: self._editor_done(True, [e.get() for e in entries])).pack(fill="x", padx=16, pady=18)

contacts = ContactsAPI()
