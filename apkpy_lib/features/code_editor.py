"""Colours in a textarea while you type, in the Previewer.

``codigo { syntax: html; }`` on an ``inputs(type="textarea")`` colours its
words as an editor does: the same table ``markdown()`` uses for a fenced
block (core/code_highlight.py), so a keyword is the same colour in the
editor, in a code block and on the phone (core/features/code_editor.py).
"""

from ..core import code_highlight as _code


def language(style):
    """The table the stylesheet names with ``syntax:``, or None."""
    return _code.language((style or {}).get("syntax"))


def watch(text_widget, style, text_colour, placeholder=""):
    """Recolour the widget after every change, typed or set_value()."""
    lang = language(style)
    if not lang:
        return False
    palette = _code.palette(text_colour)
    for kind in _code.KINDS:
        text_widget.tag_configure("syntax_" + kind, foreground=palette[kind])
    pending = [False]

    def paint():
        pending[0] = False
        try:
            for kind in _code.KINDS:
                text_widget.tag_remove("syntax_" + kind, "1.0", "end")
            content = text_widget.get("1.0", "end-1c")
            if placeholder and content == placeholder:
                return
            for number, line in enumerate(content.split("\n"), start=1):
                for start, end, kind in _code.tokens(line, lang):
                    text_widget.tag_add("syntax_" + kind, "%d.%d" % (number, start),
                                        "%d.%d" % (number, end))
        except Exception:
            pass

    def queue(_event=None):
        if not pending[0]:
            pending[0] = True
            try:
                text_widget.after_idle(paint)
            except Exception:
                pending[0] = False

    text_widget.bind("<<Modified>>", queue, add="+")
    text_widget.bind("<KeyRelease>", queue, add="+")
    queue()
    return True
