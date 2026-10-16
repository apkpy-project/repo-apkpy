"""The line of words under a text field, in the Previewer.

``inputs(..., help=, error=, required=)`` and ``field.set_error()`` put
supporting text under a field and turn its line or outline to the error
colour. What the line says and when a field counts as empty come from
``field_rules`` -- the module ApkpyField mirrors on the phone.

A text field is built inside a frame of its own (``shell``), so the words
can sit under it wherever the field is: in a column, in a row, in a card.
The label itself is only made when there is something to say.
"""

import tkinter as tk

from .. import field_rules as rules


class Field:
    """One text field's help, error and required rule."""

    def __init__(self, ui, comp):
        self.ui = ui
        self.comp = comp
        kwargs = comp.kwargs if comp is not None else {}
        self.help = kwargs.get('help') or ''
        self.required = kwargs.get('required_message') or ''
        self.error = kwargs.get('error') or ''
        tokens = ui.global_styles.get('__theme__', {}) or {}
        colours = rules.colors(tokens)
        self.help_colour = ui._tk_color(colours['help'], '#49454F')
        self.error_colour = ui._tk_color(colours['error'], '#B3261E')
        self.font = ui._build_tk_font({'font-size': '%dpx' % rules.SUPPORT_SIZE,
                                       'font-family': tokens.get('font-family', '')},
                                      default_size=rules.SUPPORT_SIZE)
        self.wrap = None
        self.label = None
        self.pads = (12, 12)
        self.bg = '#FFFFFF'
        self.repaint = None

    # What add_input asks while it draws the field.

    def line(self, colour):
        """The field's line or outline: the error colour while it shows one."""
        return self.error_colour if self.error else colour

    def stroke(self, width):
        return rules.stroke(width) if self.error else width

    def shell(self, parent, bg, padx, pady):
        """The frame the field is built in. The supporting text goes under
        it, inside the same outer frame, so the pair moves as one."""
        self.bg = bg
        self.wrap = tk.Frame(parent, bg=bg)
        self.wrap.pack(padx=padx, pady=pady, fill='x')
        outer = tk.Frame(self.wrap, bg=bg)
        outer.pack(fill='x')
        return outer

    def finish(self, widget, pads, repaint):
        """The field is drawn: remember how to redraw it and show what there
        is to say."""
        self.pads = pads
        self.repaint = repaint
        if widget is not None:
            # Typing answers the complaint. The phone clears the error on
            # the first change too.
            widget.bind('<KeyRelease>', self._typed, add='+')
        self._show()

    # What the app asks.

    def set_error(self, text):
        self.error = rules.words(text, 'error')
        self._show()

    def validate(self):
        """Check the field's own rule, show or clear its error, and say
        whether it passed."""
        problem = rules.check(self.comp.get_value(), self.required)
        self.set_error(problem)
        return not problem

    def supporting(self):
        return rules.supporting(self.help, self.error)

    def _typed(self, event=None):
        if self.error and getattr(event, 'keysym', '') not in ('Tab', 'ISO_Left_Tab',
                                                             'Shift_L', 'Shift_R'):
            self.set_error('')

    def _show(self):
        words, is_error = self.supporting()
        try:
            if words:
                if self.label is None:
                    self.label = tk.Label(self.wrap, bg=self.bg, font=self.font,
                                          anchor='w', justify='left',
                                          bd=0, padx=0, pady=0, highlightthickness=0)
                    self.wrap.bind('<Configure>', self._fit, add='+')
                self.label.config(text=words,
                                  fg=self.error_colour if is_error else self.help_colour)
                self.label.pack(fill='x', padx=self.pads, pady=(rules.SUPPORT_GAP, 0))
                self._fit()
            elif self.label is not None:
                self.label.pack_forget()
            if self.repaint is not None:
                self.repaint()
        except tk.TclError:
            # The screen was rebuilt under a callback that finished late.
            pass

    def _fit(self, event=None):
        if self.label is None:
            return
        width = (event.width if event is not None else self.wrap.winfo_width())
        room = width - self.pads[0] - self.pads[1]
        if room > 40:
            self.label.config(wraplength=room)


def of(comp):
    """The Field of a text field being drawn, made once per render."""
    if comp is None:
        return None
    from .. import ui
    field = Field(ui, comp)
    comp._field = field
    return field


def set_error(comp, text):
    field = getattr(comp, '_field', None)
    if field is not None and field.wrap is not None:
        field.set_error(text)
    else:
        # Before the screen is drawn: it starts with this error.
        comp.kwargs['error'] = rules.words(text, 'error')


def validate(comp):
    field = getattr(comp, '_field', None)
    if field is not None and field.wrap is not None:
        return field.validate()
    problem = rules.check(comp.get_value(), comp.kwargs.get('required_message') or '')
    comp.kwargs['error'] = problem
    return not problem


def validate_all(comps):
    """Every field is checked -- all the errors show at once -- and the
    first one that failed takes the cursor."""
    first = None
    for comp in comps:
        if not validate(comp) and first is None:
            first = comp
    if first is not None:
        try:
            first.widget.focus_set()
        except Exception:
            pass
    return first is None
