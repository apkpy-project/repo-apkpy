"""Chips and segmented buttons in the Previewer.

Drawn on one canvas from choice_rules -- the module ApkpyChoice reads on the
phone -- so a tap selects the same thing, a chip wraps at the same place and
a selected segment takes the same colour on both. The shapes go through the
antialiased rounded-rectangle path every other shape here uses, the icons
through the shared Material catalogue.
"""

import tkinter as tk

from .. import choice_rules as rules


def render_choice(app, comp, parent_widget, is_flex, pack_side, bg_color):
    from .. import ui

    kind = comp.comp_type
    comp_id = comp.kwargs.get('comp_id')
    own = ui.component_style(ui.global_styles, kind, comp_id, include_body=False)
    tokens = ui.global_styles.get('__theme__', {}) or {}
    colors = rules.colors(kind, tokens, own)
    corner = rules.radius(kind, own)
    size = rules.text_size(own)
    font = ui._build_tk_font({'font-size': '%dpx' % int(round(size)),
                              'font-family': tokens.get('font-family', '')},
                             default_size=int(round(size)))
    mt, mr, mb, ml = ui._parse_margin(ui._merge_with_body(comp_id, 'container'))
    bg = ui._tk_color(bg_color, '#FFFFFF')

    outer = tk.Frame(parent_widget, bg=bg)
    if is_flex and pack_side in (tk.LEFT, tk.RIGHT):
        outer.pack(side=pack_side, fill='x', expand=True, padx=(ml, mr), pady=(mt, mb))
    else:
        outer.pack(fill='x', padx=(ml, mr), pady=(mt, mb),
                   **({'side': pack_side} if is_flex else {}))
    canvas = tk.Canvas(outer, height=rules.TOUCH, bg=bg, highlightthickness=0, bd=0,
                       cursor='hand2')
    canvas.pack(fill='x')
    comp.widget = canvas
    measure = ui._text_measure(canvas, font)
    options = list(comp.kwargs.get('options') or [])
    icons = list(comp.kwargs.get('icons') or [None] * len(options))
    multiple = bool(comp.kwargs.get('multiple'))
    check = comp.kwargs.get('check', True)
    required = bool(comp.kwargs.get('required'))
    inset = rules.vertical_inset(kind)
    hits = []          # (x0, y0, x1, y1, option)

    def _clip(text, room):
        return ui._clip_to_width(canvas, font, text, max(0, int(room)))

    def _chips(width, selected):
        widths = []
        for option, icon in zip(options, icons):
            lead = rules.leading_icon(icon, option in selected, check)
            widths.append(min(width, rules.chip_width(measure(option), bool(lead))))
        places = rules.flow(widths, width)
        total = max(1, rules.lines_of(places)) * rules.TOUCH
        if int(float(canvas.cget('height'))) != total:
            canvas.configure(height=total)
        for option, icon, chip_w, (x, line) in zip(options, icons, widths, places):
            on = option in selected
            top = line * rules.TOUCH + inset
            ui._create_rounded_rect(
                canvas, x, top, x + chip_w, top + rules.CHIP_HEIGHT, corner,
                fill=(colors['active_fill'] if on else (colors['fill'] or '')),
                outline=('' if (on or not colors['border']) else colors['border']),
                width=(0 if (on or not colors['border']) else rules.BORDER))
            lead = rules.leading_icon(icon, on, check)
            ink = colors['active_text'] if on else colors['text']
            text_x = x + rules.CHIP_PAD
            if lead:
                ui._draw_material_icon(
                    canvas, lead, x + rules.CHIP_PAD_ICON + rules.ICON / 2.0,
                    top + rules.CHIP_HEIGHT / 2.0,
                    colors['active_text'] if on else colors['icon'], size=rules.ICON)
                text_x = x + rules.CHIP_PAD_ICON + rules.ICON + rules.ICON_GAP
            canvas.create_text(text_x, top + rules.CHIP_HEIGHT / 2.0, anchor='w',
                               text=_clip(option, x + chip_w - rules.CHIP_PAD - text_x),
                               fill=ui._tk_color(ink, '#000000'), font=font)
            hits.append((x, line * rules.TOUCH, x + chip_w,
                         (line + 1) * rules.TOUCH, option))

    def _segments(width, selected):
        if int(float(canvas.cget('height'))) != rules.TOUCH:
            canvas.configure(height=rules.TOUCH)
        edges = rules.segment_edges(len(options), width)
        top, bottom = inset, inset + rules.SEGMENT_HEIGHT
        r = min(corner, rules.SEGMENT_HEIGHT / 2.0)
        last = len(options) - 1
        for index, option in enumerate(options):
            on = option in selected
            fill = colors['active_fill'] if on else colors['fill']
            if fill:
                corners = (r if index == 0 else 0, r if index == last else 0,
                           r if index == last else 0, r if index == 0 else 0)
                ui._create_rounded_rect(canvas, edges[index], top, edges[index + 1], bottom,
                                        corners, fill=fill, width=0)
        if colors['border']:
            ui._create_rounded_rect(canvas, 0, top, width, bottom, r, fill='',
                                    outline=colors['border'], width=rules.BORDER)
            border = ui._tk_color(colors['border'], '#79747E')
            for index in range(1, len(options)):
                canvas.create_line(edges[index], top, edges[index], bottom, fill=border)
        for index, (option, icon) in enumerate(zip(options, icons)):
            on = option in selected
            x0, x1 = edges[index], edges[index + 1]
            lead = rules.leading_icon(icon, on, check)
            room = (x1 - x0) - 2 * rules.SEGMENT_PAD - ((rules.ICON + rules.ICON_GAP) if lead else 0)
            text = _clip(option, room)
            content = measure(text) + ((rules.ICON + rules.ICON_GAP) if lead else 0)
            start = x0 + ((x1 - x0) - content) / 2.0
            mid = (top + bottom) / 2.0
            ink = colors['active_text'] if on else colors['text']
            if lead:
                ui._draw_material_icon(canvas, lead, start + rules.ICON / 2.0, mid,
                                       colors['active_text'] if on else colors['icon'],
                                       size=rules.ICON)
                start += rules.ICON + rules.ICON_GAP
            canvas.create_text(start, mid, anchor='w', text=text,
                               fill=ui._tk_color(ink, '#000000'), font=font)
            hits.append((x0, 0, x1, rules.TOUCH, option))

    def draw(_event=None):
        try:
            width = canvas.winfo_width()
        except tk.TclError:
            return
        if width <= 2:
            return
        canvas.delete('all')
        del hits[:]
        selected = comp.kwargs.get('_selected') or []
        if kind == 'chips':
            _chips(width, selected)
        else:
            _segments(width, selected)

    def click(event):
        for x0, y0, x1, y1, option in hits:
            if x0 <= event.x < x1 and y0 <= event.y < y1:
                before = list(comp.kwargs.get('_selected') or [])
                after = rules.tap(kind, options, before, option, multiple, required)
                if after == before:
                    return
                comp.kwargs['_selected'] = after
                draw()
                callback = comp.kwargs.get('on_change')
                if callable(callback):
                    callback(rules.value_of(after, multiple))
                return

    comp._choice_redraw = draw
    canvas.bind('<Configure>', draw)
    canvas.bind('<Button-1>', click)
