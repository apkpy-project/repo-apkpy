"""Reading a code -- ``from apkpy_lib import scan``.

On the phone this opens Google's own scanner: a camera surface drawn by Play
services, in Play services' process. The app never touches a frame and never
asks for the CAMERA permission.

There is nothing to imitate here, because there is nothing of ours on screen
to imitate. A desktop has no barcode in front of it either, so the Previewer
does the honest thing and asks: a small panel that says plainly it is standing
in for the scanner, takes a value by hand, and answers through the same
``(ok, value)`` callback the phone will use. Cancelling it answers
``cancelled``, exactly as backing out of the real scanner does -- which is the
part apps get wrong, so it is the part worth being able to rehearse.
"""

from __future__ import annotations

from ..core.features.scan import FORMATS, normalise_formats, unknown_formats

__all__ = ["ScanAPI", "scan", "FORMATS"]

_PANEL_WIDTH = 320


class ScanAPI:
    """Read a barcode or QR code."""

    def code(self, on_result=None, formats=None):
        """Ask for a code, answering ``on_result(ok, value)``.

        ``formats`` narrows what counts -- ``["qr"]``, ``["ean13", "code128"]``
        -- and left out, everything is read. A name that means nothing is
        refused here rather than quietly ignored, because a scanner reading
        more than you asked it to is how the wrong label gets into the wrong
        field.
        """
        unknown = unknown_formats(formats)
        if unknown:
            raise ValueError(
                'scan.code(formats=%r): %s is not a code ApkPy reads. '
                'Choose from: %s'
                % (formats, ', '.join(unknown), ', '.join(sorted(FORMATS)))
            )
        wanted = normalise_formats(formats)
        self._open_panel(on_result, wanted)
        return None

    # ── the stand-in ──────────────────────────────────────────────────────────

    def _open_panel(self, on_result, wanted):
        from .. import ui

        app = ui._app
        # Reading .root on the lazy proxy BUILDS the Previewer window, so an
        # `apkpy build` that merely imports the module would open one. Asking
        # whether it exists first is what stops that.
        if getattr(app, "_instance", None) is None:
            return self._answer(on_result, False, "unavailable")

        import tkinter as tk

        root = app.root
        panel = tk.Toplevel(root)
        panel.title("Scanner")
        panel.transient(root)
        panel.resizable(False, False)
        background = "#262624"
        panel.configure(bg=background)

        held = {"done": False}

        def finish(ok, value):
            if held["done"]:
                return
            held["done"] = True
            try:
                panel.destroy()
            except Exception:
                pass
            self._answer(on_result, ok, value)

        tk.Label(
            panel, text="PREVIEWER, NOT A REAL SCANNER",
            bg=background, fg="#9C9A93", font=("Segoe UI", 8, "bold"),
        ).pack(padx=16, pady=(14, 2), anchor="w")

        wording = ("Reading: " + ", ".join(sorted(
            name for name, constant in FORMATS.items() if constant in wanted))
        ) if wanted else "Reading: every format"
        tk.Label(
            panel, text=wording, bg=background, fg="#F5F4EF",
            font=("Segoe UI", 10), wraplength=_PANEL_WIDTH,
        ).pack(padx=16, pady=(0, 10), anchor="w")

        entry = tk.Entry(panel, width=34, bg="#1B1B19", fg="#F5F4EF",
                         insertbackground="#F5F4EF", relief="flat")
        entry.pack(padx=16, pady=(0, 12), ipady=6)
        entry.focus_set()

        buttons = tk.Frame(panel, bg=background)
        buttons.pack(padx=16, pady=(0, 14), fill="x")

        def scanned():
            value = entry.get()
            # An empty read is not a read. The phone answers "unreadable" for a
            # code it saw but could not decode, so this does the same rather
            # than handing the app a blank it would store as a real value.
            finish(bool(value), value or "unreadable")

        tk.Button(buttons, text="Cancel", relief="flat", bg="#3A3A37",
                  fg="#F5F4EF", command=lambda: finish(False, "cancelled"),
                  ).pack(side="right", padx=(8, 0))
        tk.Button(buttons, text="Scan", relief="flat", bg="#C96442",
                  fg="#FFFFFF", command=scanned).pack(side="right")

        entry.bind("<Return>", lambda _event: scanned())
        panel.bind("<Escape>", lambda _event: finish(False, "cancelled"))
        panel.protocol("WM_DELETE_WINDOW", lambda: finish(False, "cancelled"))

        panel.update_idletasks()
        panel.geometry("+%d+%d" % (root.winfo_rootx() + 40,
                                   root.winfo_rooty() + 120))

    @staticmethod
    def _answer(on_result, ok, value):
        if on_result is None:
            return
        try:
            on_result(ok, value)
        except TypeError:
            on_result(ok)


scan = ScanAPI()
