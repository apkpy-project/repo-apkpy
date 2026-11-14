"""The look shared by the Studio and the editors: sharp on a scaled screen, and one set of colours.

By Ruben Rego (the monster-rpg template's Studio), shared by every game's Studio."""
import tkinter as tk
from tkinter import ttk

BG = "#f4f5f7"
PANEL = "#ffffff"
LINE = "#d5d8de"
TEXT = "#22252b"
MUTED = "#667080"
ACCENT = "#2f6fdb"
SIDE = "#23262f"
SIDE_TEXT = "#c8ccd6"
GOOD = "#208040"
BAD = "#c02020"


def make_root(title="Studio"):
    """A window that the system draws at its real resolution. Without this, Windows stretches it and it looks blurred."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass
    root = tk.Tk()
    root.title(title)
    apply_theme(root)
    return root


def px(widget, n):
    """n pixels of a screen at 100%, on this screen."""
    return int(n * widget.winfo_fpixels("1i") / 96)


def apply_theme(root):
    root.configure(bg=BG)
    for key, value in (("*Background", BG), ("*Foreground", TEXT), ("*activeBackground", "#e4e7ec"), ("*Button.relief", "flat"), ("*Button.borderWidth", 1),
                       ("*Button.highlightThickness", 0), ("*Button.background", "#e9ebef"), ("*Listbox.background", PANEL), ("*Listbox.relief", "flat"),
                       ("*Listbox.selectBackground", ACCENT), ("*Listbox.selectForeground", "#ffffff"), ("*Listbox.highlightThickness", 1),
                       ("*Listbox.highlightColor", LINE), ("*Listbox.highlightBackground", LINE), ("*Entry.background", PANEL), ("*Entry.relief", "flat"),
                       ("*Entry.highlightThickness", 1), ("*Entry.highlightBackground", LINE), ("*Entry.highlightColor", ACCENT), ("*Spinbox.background", PANEL),
                       ("*Spinbox.relief", "flat"), ("*Spinbox.highlightThickness", 1), ("*Spinbox.highlightBackground", LINE), ("*Spinbox.highlightColor", ACCENT),
                       ("*Text.background", PANEL), ("*Text.relief", "flat"), ("*Text.highlightThickness", 1), ("*Text.highlightBackground", LINE),
                       ("*Checkbutton.highlightThickness", 0), ("*Radiobutton.highlightThickness", 0), ("*TCombobox*Listbox.background", PANEL),
                       ("*TCombobox*Listbox.selectBackground", ACCENT), ("*TCombobox*Listbox.selectForeground", "#ffffff")):
        root.option_add(key, value)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=TEXT, bordercolor=LINE, lightcolor=BG, darkcolor=BG, troughcolor=BG)
    style.configure("TEntry", fieldbackground=PANEL, bordercolor=LINE)
    style.configure("TCombobox", fieldbackground=PANEL, background="#e9ebef", arrowcolor=TEXT, bordercolor=LINE)
    style.map("TCombobox", fieldbackground=[("readonly", PANEL)], selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", TEXT)])
    style.configure("TNotebook", background=BG, bordercolor=LINE, tabmargins=(2, 2, 2, 0))
    style.configure("TNotebook.Tab", background="#e4e7ec", padding=(10, 4), bordercolor=LINE)
    style.map("TNotebook.Tab", background=[("selected", PANEL)])
    row = int(root.winfo_fpixels("1i") / 96 * 26)
    style.configure("Treeview", background=PANEL, fieldbackground=PANEL, rowheight=row, bordercolor=LINE, borderwidth=1)
    style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#ffffff")])
    style.configure("Vertical.TScrollbar", background="#dfe2e7", arrowcolor=MUTED)


class Scrolling(tk.Frame):
    """A column of widgets that scrolls: self.inner is where they go."""

    def __init__(self, parent, **options):
        tk.Frame.__init__(self, parent, **options)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas)
        self.window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.bind_all_wheel(self.canvas)

    def bind_all_wheel(self, widget):
        widget.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self.wheel))
        widget.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def wheel(self, event):
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def to_top(self):
        self.canvas.yview_moveto(0)
