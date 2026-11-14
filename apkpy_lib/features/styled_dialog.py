"""alert() and confirm() in the app's own style, in the Previewer.

Two windows over the app, as the bottom sheet: a black one at 60% for the
scrim, and the card, whose rounded corners are see-through. The parts and
their fallbacks are dialog_rules.look(); the phone draws the same card from
the same answer (core/features/styled_dialog.py).
"""

import tkinter as tk
import tkinter.font as tkfont

from .. import dialog_rules as rules
from ..core import css_colors

_SEE_THROUGH = '#010203'


def _plain(colour, behind):
    """A colour Tk can paint: alpha mixed over what is behind it."""
    seen = css_colors.over(css_colors.named(str(colour or '').strip()), behind)
    seen = str(seen or behind)
    return seen if seen.startswith('#') and len(seen) in (4, 7) else behind


def _font(ui, size, bold):
    return ui._build_tk_font({'font-size': '%dpx' % size,
                              'font-weight': 'bold' if bold else 'normal'},
                             default_size=size)


def _button_picture(ui, look, width, height, behind):
    """A gradient button as an image with rounded corners, or None."""
    if not look.get('gradient'):
        return None
    try:
        from PIL import Image, ImageDraw, ImageTk
        from ..core.gradients import gradient_of
        from . import gradient_image
        picture = gradient_image.render(gradient_of({'background': look['gradient']}),
                                        width, height)
        if picture is None:
            return None
        under = Image.new('RGBA', (width, height), behind)
        mask = Image.new('L', (width, height), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1),
                                               radius=int(look['radius']), fill=255)
        under.paste(picture, (0, 0), mask)
        return ImageTk.PhotoImage(under)
    except Exception:
        return None


def ask(ui, title, message, buttons):
    """Show the card and wait; the value of the button pressed, else None
    (the scrim or Escape, which the phone reads as cancel too)."""
    root = ui.live_preview_root()
    look = rules.look(ui.global_styles)
    root.update_idletasks()
    rx, ry = root.winfo_rootx(), root.winfo_rooty()
    rw, rh = max(1, root.winfo_width()), max(1, root.winfo_height())
    result = [None]

    scrim = tk.Toplevel(root)
    scrim.overrideredirect(True)
    scrim.configure(bg='#000000')
    scrim.geometry('%dx%d+%d+%d' % (rw, rh, rx, ry))
    try:
        scrim.attributes('-alpha', rules.SCRIM)
        scrim.attributes('-topmost', True)
    except tk.TclError:
        pass

    card_w = rules.width(rw)
    win = tk.Toplevel(root)
    win.overrideredirect(True)
    corners = _SEE_THROUGH
    try:
        win.attributes('-transparentcolor', _SEE_THROUGH)
        win.attributes('-topmost', True)
    except tk.TclError:
        corners = '#000000'
    canvas = tk.Canvas(win, width=card_w, height=10, bg=corners, highlightthickness=0)
    canvas.pack()

    card = look['card']
    dim = '#000000'
    surface = _plain(card['background'], dim)
    pad = card['padding']
    inner = card_w - 2 * pad
    y = pad
    title_id = canvas.create_text(pad, y, text=str(title), anchor='nw', width=inner,
                                  fill=_plain(look['title']['color'], surface),
                                  font=_font(ui, look['title']['size'], look['title']['bold']))
    y = canvas.bbox(title_id)[3] + 8
    message_id = canvas.create_text(pad, y, text=str(message), anchor='nw', width=inner,
                                    fill=_plain(look['message']['color'], surface),
                                    font=_font(ui, look['message']['size'],
                                               look['message']['bold']))
    y = canvas.bbox(message_id)[3] + 24

    # The confirming button on the right, as in the app this copies.
    pressed = [(text, value, look['ok'] if index == 0 else look['cancel'])
               for index, (text, value) in enumerate(buttons)]
    row = list(reversed(pressed))
    count = len(row)
    button_w = (inner - rules.BUTTON_GAP * (count - 1)) / float(count)
    pictures = []

    def _close(value):
        result[0] = value
        for window in (win, scrim):
            try:
                window.destroy()
            except tk.TclError:
                pass

    button_h = 0
    for index, (text, value, part) in enumerate(row):
        font = _font(ui, part['size'], part['bold'])
        line = tkfont.Font(root=root, font=font).metrics('linespace')
        height = int(line + 2 * part['padding'])
        button_h = max(button_h, height)
        x0 = pad + index * (button_w + rules.BUTTON_GAP)
        tag = 'button%d' % index
        picture = _button_picture(ui, part, int(button_w), height, surface)
        if picture is not None:
            pictures.append(picture)
            canvas.create_image(x0, y, image=picture, anchor='nw', tags=tag)
        else:
            fill = _plain(part['background'], surface)
            outline = _plain(part['border'], surface) if part['border'] else ''
            ui._create_rounded_rect(canvas, x0, y, x0 + button_w, y + height, part['radius'],
                                    fill=fill, outline=outline or fill,
                                    width=max(1, int(part['border_width'])) if outline else 1,
                                    tags=tag)
        canvas.create_text(x0 + button_w / 2, y + height / 2, text=str(text),
                           fill=_plain(part['color'], surface), font=font, tags=tag)
        canvas.tag_bind(tag, '<Button-1>', lambda _e, v=value: _close(v))
        canvas.tag_bind(tag, '<Enter>', lambda _e: canvas.configure(cursor='hand2'))
        canvas.tag_bind(tag, '<Leave>', lambda _e: canvas.configure(cursor=''))
    canvas._apkpy_pictures = pictures

    card_h = int(y + button_h + pad)
    canvas.configure(height=card_h)
    outline = _plain(card['border'], surface) if card['border'] and card['border_width'] else ''
    shape = ui._create_rounded_rect(canvas, 1, 1, card_w - 1, card_h - 1, card['radius'],
                                    fill=surface, outline=outline or surface,
                                    width=max(1, int(card['border_width'])) if outline else 1)
    canvas.tag_lower(shape)
    win.geometry('%dx%d+%d+%d' % (card_w, card_h, rx + (rw - card_w) // 2,
                                  ry + (rh - card_h) // 2))
    win.lift(scrim)
    scrim.bind('<Button-1>', lambda _e: _close(None))
    for window in (scrim, win):
        window.bind('<Escape>', lambda _e: _close(None))
    win.after_idle(win.focus_force)
    win.wait_window()
    return result[0]
