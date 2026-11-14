"""The keyboard of a text field, in the Previewer.

``inputs(..., type="email"|"phone"|"url", action=, on_submit=, autofill=)``,
``hide_keyboard()`` and ``field.focus()``. The rules -- the types, what each
action does, the autofill words -- are field_rules', which the compiler reads
too.

A desktop has no keyboard on the screen, so here:

* the Enter key is the keyboard's corner key: ``on_submit`` runs, "next"
  moves to the next field, and "done", "search" and "go" take the cursor out
  of the field, as the phone closes its keyboard;
* a field with no action does what Android does with one: Enter moves to the
  next field when there is one, and otherwise stays;
* a ``type="phone"`` field takes what a phone's dial pad types;
* ``autofill=`` has nothing to fill on a desktop and changes nothing.
"""

import inspect
import tkinter as tk

from .. import field_rules as rules


def options(type, action, on_submit, autofill, line=0):
    """The keyword arguments inputs() keeps for its field (checked here, once)."""
    has_submit = on_submit is not None
    ime = rules.action_of(type, action, has_submit, line)
    hint = rules.autofill_of(autofill, line)
    rules.check_autofill_type(type, hint, line)
    if has_submit:
        rules.check_submit_arity(_arity(on_submit), line)
    kept = {}
    if type in rules.KEYBOARD_TYPES:
        kept['keyboard'] = type
    if ime:
        kept['ime_action'] = ime
    if has_submit:
        kept['on_submit'] = on_submit
    if hint:
        kept['autofill'] = hint
    return kept


def _arity(fn):
    """How many parameters ``fn`` has, as the build counts them (each one,
    with a default or not), so both sides refuse the same functions."""
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return 1
    count = 0
    for param in params:
        if param.kind == param.VAR_POSITIONAL:
            return max(count, 1)
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
            count += 1
    return count


def _is_text_widget(widget):
    return isinstance(widget, (tk.Entry, tk.Text))


def _next_field(entry):
    """The next field you type in after ``entry``, in the screen's order, or None."""
    widget = entry
    for _ in range(400):
        try:
            widget = widget.tk_focusNext()
        except (tk.TclError, KeyError):
            return None
        if widget is None or widget is entry:
            return None
        if _is_text_widget(widget) and widget.winfo_viewable():
            return widget
    return None


def hide(app_instance):
    """Take the cursor out of every field: the phone closes its keyboard."""
    if app_instance is None:
        return
    try:
        app_instance.root.focus_set()
    except tk.TclError:
        pass


def _report(exc):
    from ..diagnostics import report_exception
    report_exception(exc, context="Previewer on_submit")


def wire(app_instance, comp, entry, placeholder):
    """Enter, the dial pad and a focus() asked before the field was drawn."""
    if comp is None:
        return
    kwargs = comp.kwargs
    if kwargs.get('keyboard') == 'phone':
        def _dial_pad(event):
            if event.char and event.char.isprintable() and event.char not in rules.PHONE_CHARS:
                return 'break'
            return None
        entry.bind('<KeyPress>', _dial_pad, add='+')

    action = kwargs.get('ime_action')
    on_submit = kwargs.get('on_submit')

    def _enter(event=None):
        if on_submit is not None:
            text = entry.get()
            if text == placeholder:
                text = ''
            try:
                on_submit(text) if _arity(on_submit) >= 1 else on_submit()
            except Exception as exc:     # noqa: BLE001 - shown like any callback error
                _report(exc)
        if action in rules.HIDES_KEYBOARD:
            hide(app_instance)
        elif action == 'next' or action is None:
            target = _next_field(entry)
            if target is not None:
                target.focus_set()
        return 'break'

    entry.bind('<Return>', _enter)
    entry.bind('<KP_Enter>', _enter)


def drawn(comp):
    """After a field is drawn: the focus() asked before there was a widget."""
    widget = getattr(comp, 'widget', None)
    if getattr(comp, '_want_focus', False) and widget is not None:
        comp._want_focus = False
        widget.after_idle(lambda: _focus_widget(widget))


def _focus_widget(widget):
    try:
        if widget.winfo_exists():
            widget.focus_set()
    except tk.TclError:
        pass


def focus(comp):
    """field.focus(): the cursor in the field (the phone opens its keyboard).
    Before the screen is drawn it waits for the field."""
    rules.check_focus(comp.kwargs.get('keyboard') or comp.kwargs.get('input_type', 'text'))
    widget = getattr(comp, 'widget', None)
    if widget is not None:
        try:
            if widget.winfo_exists():
                widget.focus_set()
                return
        except tk.TclError:
            pass
    comp._want_focus = True
