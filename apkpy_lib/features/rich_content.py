"""Rich documents and virtualized trees for ApkPy.

The public components in this module deliberately keep their data model small:

``markdown``
    Renders Markdown without a WebView.

``rich_text``
    Renders an ordered list of styled inline spans.

``tree_view``
    Flattens only expanded nodes.  Closed branches create no Preview rows and
    compile to a RecyclerView on Android.
"""

from __future__ import annotations

import copy
import json
import math
import re
import tkinter as tk
import tkinter.font as tkfont
from typing import Any, Iterable


_INLINE_RE = re.compile(
    r"(\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|~~([^~]+)~~|"
    r"`([^`]+)`|\*([^*]+)\*)"
)

# Android's sp glyphs are rasterized and then scaled by the emulator/device
# viewport. A small correction keeps explicit rich-span sizes visually aligned
# with that result in the desktop Previewer.
_RICH_SPAN_PREVIEW_SCALE = 0.90


def _attach(component, screen=None, parent=None):
    if parent is not None:
        parent.children.append(component)
        return component
    if screen is not None:
        return screen._add(component)
    return None


def _normalise_spans(spans: Any) -> list[dict[str, Any]]:
    if isinstance(spans, str):
        spans = [{"text": spans}]
    if not isinstance(spans, (list, tuple)):
        raise TypeError("rich_text(spans=...) must be a string or a list")

    result: list[dict[str, Any]] = []
    for item in spans:
        if isinstance(item, str):
            result.append({"text": item})
            continue
        if not isinstance(item, dict):
            raise TypeError("each rich_text span must be a string or dict")
        span = {
            "text": str(item.get("text", "")),
            "bold": bool(item.get("bold", False)),
            "italic": bool(item.get("italic", False)),
            "underline": bool(item.get("underline", False)),
            "strike": bool(item.get("strike", False)),
            "code": bool(item.get("code", False)),
        }
        if item.get("color"):
            span["color"] = str(item["color"])
        if item.get("link"):
            span["link"] = str(item["link"])
        if item.get("size") is not None:
            try:
                span["size"] = max(8, min(72, int(item["size"])))
            except (TypeError, ValueError):
                raise ValueError("rich_text span size must be an integer")
        result.append(span)
    return result


def _normalise_nodes(nodes: Any, *, expand_depth: int, _depth: int = 0,
                     _path: str = "") -> list[dict[str, Any]]:
    if not isinstance(nodes, (list, tuple)):
        raise TypeError("tree_view(nodes=...) must be a list")
    if _depth > 24:
        raise ValueError("tree_view supports at most 24 nested levels")

    result: list[dict[str, Any]] = []
    for index, item in enumerate(nodes):
        if isinstance(item, str):
            item = {"title": item}
        if not isinstance(item, dict):
            raise TypeError("each tree node must be a string or dict")
        path = f"{_path}.{index}" if _path else str(index)
        children = _normalise_nodes(
            item.get("children", []),
            expand_depth=expand_depth,
            _depth=_depth + 1,
            _path=path,
        )
        explicit_expanded = item.get("expanded")
        expanded = (
            bool(explicit_expanded)
            if explicit_expanded is not None
            else bool(children and _depth < expand_depth)
        )
        result.append({
            "key": str(item.get("key", path)),
            "title": str(item.get("title", "")),
            "subtitle": str(item.get("subtitle", "")),
            "expanded": expanded,
            "children": children,
        })
    return result


def markdown(source: str, id=None, screen=None, parent=None, *,
             selectable: bool = True):
    """Render Markdown natively in the Previewer and generated Android app.

    Supported syntax includes headings, emphasis, links, inline/fenced code,
    quotes, ordered and unordered lists, checkboxes and dividers.  No WebView
    or JavaScript runtime is added to the APK.
    """
    if not isinstance(source, str):
        raise TypeError("markdown(source=...) must be a string")
    from ..ui import ComponentDef

    return _attach(
        ComponentDef(
            "markdown",
            source=source,
            selectable=bool(selectable),
            comp_id=id,
        ),
        screen=screen,
        parent=parent,
    )


def rich_text(spans, id=None, screen=None, parent=None, *,
              selectable: bool = True):
    """Render inline rich text from a compact span list.

    Each span accepts ``text`` plus ``bold``, ``italic``, ``underline``,
    ``strike``, ``code``, ``color``, ``size`` and ``link``.
    """
    from ..ui import ComponentDef

    return _attach(
        ComponentDef(
            "rich_text",
            spans=_normalise_spans(spans),
            selectable=bool(selectable),
            comp_id=id,
        ),
        screen=screen,
        parent=parent,
    )


def tree_view(nodes, id=None, screen=None, parent=None, *,
              expand_depth: int = 1, row_height: int = 58):
    """Render an expandable hierarchy with only visible nodes materialized.

    Nodes are dictionaries with ``title``, optional ``subtitle``, optional
    ``key``, optional ``expanded`` and recursive ``children``.
    """
    try:
        depth = max(0, min(12, int(expand_depth)))
        extent = max(48, min(96, int(row_height)))
    except (TypeError, ValueError):
        raise ValueError("tree_view expand_depth and row_height must be integers")

    from ..ui import ComponentDef

    return _attach(
        ComponentDef(
            "tree_view",
            nodes=_normalise_nodes(nodes, expand_depth=depth),
            expand_depth=depth,
            row_height=extent,
            comp_id=id,
        ),
        screen=screen,
        parent=parent,
    )


def _font(base, *, size=None, bold=False, italic=False, family=None):
    resolved_size = (
        abs(int(size))
        if size is not None
        else abs(int(base.actual("size")))
    )
    return tkfont.Font(
        family=family or base.actual("family"),
        size=-resolved_size,
        weight="bold" if bold else "normal",
        slant="italic" if italic else "roman",
    )


def _pack_outer(widget, *, is_flex, pack_side, margin):
    mt, mr, mb, ml = margin
    if is_flex:
        widget.pack(
            side=pack_side,
            anchor="n" if pack_side == tk.LEFT else "w",
            padx=(ml, mr),
            pady=(mt, mb),
        )
    else:
        widget.pack(fill="x", padx=(ml, mr), pady=(mt, mb))


def _surface(app, comp, parent_widget, is_flex, pack_side, parent_bg,
             semantic, *, fixed_height=None):
    from ..ui import (
        _create_rounded_rect,
        _get_style_bg,
        _get_style_border_color,
        _merge_with_body,
        _parse_border_width,
        _parse_margin,
        _parse_padding_tk,
        _parse_radius,
    )

    style = _merge_with_body(comp.kwargs.get("comp_id"), semantic)
    bg = _get_style_bg(style) or parent_bg
    if str(bg).lower() in ("transparent", "#00000000"):
        bg = parent_bg
    border = _get_style_border_color(style) or bg
    width = max(0, _parse_border_width(style))
    radius = max(0, _parse_radius(style))
    padding = _parse_padding_tk(style)
    margin = _parse_margin(style)

    holder = tk.Frame(parent_widget, bg=parent_bg, bd=0, highlightthickness=0)
    _pack_outer(
        holder,
        is_flex=is_flex,
        pack_side=pack_side,
        margin=margin,
    )

    canvas = tk.Canvas(
        holder,
        bg=parent_bg,
        bd=0,
        highlightthickness=0,
        height=fixed_height or 1,
    )
    canvas.pack(fill="x")
    # A rectangular child stretched over the entire canvas hides the rounded
    # corners underneath it. Keep the child inset only around the curved edge,
    # then compensate that inset in the content padding below.
    corner_inset = max(
        width + 1,
        min(24, int(math.ceil(radius))) if radius > 0 else 0,
    )
    vertical_inset = max(1, width + 1)
    inner = tk.Frame(canvas, bg=bg, bd=0, highlightthickness=0)
    win = canvas.create_window(
        (corner_inset, vertical_inset),
        anchor="nw",
        window=inner,
    )

    def draw(event=None):
        try:
            w = event.width if event is not None else canvas.winfo_width()
            h = fixed_height or max(
                1,
                inner.winfo_reqheight() + (vertical_inset * 2),
            )
            canvas.configure(height=h)
            window_options = {
                "width": max(1, w - (corner_inset * 2)),
            }
            # Dynamic rich-content surfaces must follow the child's natural
            # requested height. Forcing the old canvas height back onto the
            # child creates a circular layout that can never shrink after text
            # reflow. Only deliberately fixed components (the tree viewport)
            # receive an explicit window height.
            if fixed_height is not None:
                window_options["height"] = max(
                    1,
                    h - (vertical_inset * 2),
                )
            canvas.itemconfigure(win, **window_options)
            canvas.delete("surface")
            _create_rounded_rect(
                canvas, 1, 1, max(2, w - 2), max(2, h - 2), radius,
                fill=bg,
                outline=border if width else bg,
                width=max(1, width),
                tags="surface",
            )
            canvas.tag_lower("surface")
        except tk.TclError:
            return

    canvas.bind("<Configure>", draw)
    inner.bind("<Configure>", lambda _event: canvas.after_idle(draw), add="+")

    pt, pr, pb, pl = padding
    content = tk.Frame(inner, bg=bg, bd=0, highlightthickness=0)
    content.pack(
        fill="both",
        expand=fixed_height is not None,
        padx=(
            max(0, pl - corner_inset),
            max(0, pr - corner_inset),
        ),
        pady=(
            max(0, pt - vertical_inset),
            max(0, pb - vertical_inset),
        ),
    )

    comp.widget = holder
    comp._component_show = lambda: _pack_outer(
        holder,
        is_flex=is_flex,
        pack_side=pack_side,
        margin=margin,
    )
    comp._component_hide = holder.pack_forget
    return content, style, bg, holder


def _insert_inline(text_widget, text, base_tags=()):
    cursor = 0
    for match in _INLINE_RE.finditer(text):
        if match.start() > cursor:
            text_widget.insert("end", text[cursor:match.start()], base_tags)
        token = match.group(0)
        tags = list(base_tags)
        value = token
        if match.group(2) is not None:
            value = match.group(2)
            tags.append("link")
        elif match.group(4) is not None:
            value = match.group(4)
            tags.append("bold")
        elif match.group(5) is not None:
            value = match.group(5)
            tags.append("strike")
        elif match.group(6) is not None:
            value = match.group(6)
            tags.append("code")
        elif match.group(7) is not None:
            value = match.group(7)
            tags.append("italic")
        text_widget.insert("end", value, tuple(tags))
        cursor = match.end()
    if cursor < len(text):
        text_widget.insert("end", text[cursor:], base_tags)


def configure_markdown_tags(text_widget, base_font, tokens, accent, muted):
    """Dá a um widget Text os estilos que o Markdown usa.

    Extraído porque passou a ter dois clientes: o componente `markdown()` e
    uma linha de `virtual_collection` com uma fatia `markdown`. Duas cópias
    disto seriam duas cópias do aspecto, que é como um bloco de código acaba
    cinzento num sítio e transparente no outro.
    """
    text_widget.tag_configure("bold", font=_font(base_font, bold=True))
    text_widget.tag_configure("italic", font=_font(base_font, italic=True))
    text_widget.tag_configure("underline", underline=True)
    text_widget.tag_configure("strike", overstrike=True)
    text_widget.tag_configure(
        "code",
        font=_font(base_font, family="Consolas"),
        background=tokens.get("surface_variant", "#27272A"),
    )
    text_widget.tag_configure(
        "code_block",
        font=_font(base_font, family="Consolas"),
        background=tokens.get("surface_variant", "#27272A"),
        lmargin1=10,
        lmargin2=10,
        spacing1=5,
        spacing3=5,
    )
    text_widget.tag_configure(
        # O mesmo tamanho relativo do RelativeSizeSpan(0.85f) no Android.
        "copy_action",
        foreground=accent,
        font=_font(base_font, size=max(8, round(base_font.actual("size") * 0.85))),
    )
    text_widget.tag_configure("link", foreground=accent, underline=True)
    text_widget.tag_configure("quote", foreground=muted, lmargin1=8, lmargin2=8)
    text_widget.tag_configure("bullet", foreground=accent)
    text_widget.tag_configure("check", foreground=accent)
    text_widget.tag_configure("divider", foreground=muted)
    for level, factor in ((1, 1.75), (2, 1.5), (3, 1.3), (4, 1.15), (5, 1.05), (6, 1.0)):
        text_widget.tag_configure(
            f"h{level}",
            font=_font(
                base_font,
                size=max(9, round(base_font.actual("size") * factor)),
                bold=True,
            ),
            # Android's RelativeSizeSpan changes typography but does not add a
            # hidden paragraph margin. Markdown blank lines already provide the
            # intended section spacing.
            spacing1=2,
            spacing3=3,
        )


def _copy_snippet(text_widget, snippet):
    try:
        text_widget.clipboard_clear()
        text_widget.clipboard_append(snippet)
    except Exception:
        return
    from ..ui import toast
    toast("Copied")


def _insert_copy_label(text_widget, snippet, ordinal):
    """Põe um "Copy" tocável por baixo de um bloco, com o texto desse bloco."""
    tag = "copy_%d" % ordinal
    resting = text_widget.cget("cursor")
    text_widget.insert("end", "⧉ Copy", ("copy_action", tag))
    text_widget.insert("end", "\n")
    text_widget.tag_bind(
        tag, "<Button-1>",
        lambda _event, s=snippet: _copy_snippet(text_widget, s),
    )
    text_widget.tag_bind(
        tag, "<Enter>", lambda _event: text_widget.configure(cursor="hand2")
    )
    text_widget.tag_bind(
        tag, "<Leave>", lambda _event: text_widget.configure(cursor=resting)
    )


def render_markdown(text_widget, source, copy_code=False):
    """Escreve Markdown num widget Text já estilizado por
    :func:`configure_markdown_tags`. O nome público de `_render_markdown`."""
    _render_markdown(text_widget, source, copy_code=copy_code)


def _render_markdown(text_widget, source, copy_code=False):
    in_code = False
    block = []
    copies = 0
    for raw_line in str(source).splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            if in_code and copy_code and block:
                copies += 1
                # O mesmo texto que o Android copia: as linhas do bloco, cada
                # uma com a sua quebra, sem as crases.
                _insert_copy_label(
                    text_widget, "".join(line + "\n" for line in block), copies
                )
            in_code = not in_code
            block = []
            continue
        if in_code:
            block.append(raw_line)
            text_widget.insert("end", raw_line + "\n", ("code_block",))
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", raw_line)
        if heading:
            level = min(6, len(heading.group(1)))
            _insert_inline(text_widget, heading.group(2), (f"h{level}",))
            text_widget.insert("end", "\n")
            continue
        if stripped in ("---", "***", "___"):
            # Keep the divider short enough for narrow mobile previews. A long
            # run of glyphs wraps as text and looks like two separate rules.
            text_widget.insert("end", "────────────────\n", ("divider",))
            continue
        quote = re.match(r"^\s*>\s?(.*)$", raw_line)
        if quote:
            text_widget.insert("end", "▌ ", ("quote",))
            _insert_inline(text_widget, quote.group(1), ("quote",))
            text_widget.insert("end", "\n")
            continue
        check = re.match(r"^\s*[-*]\s+\[([ xX])\]\s+(.*)$", raw_line)
        if check:
            text_widget.insert(
                "end", ("[x] " if check.group(1).lower() == "x" else "[ ] "),
                ("check",),
            )
            _insert_inline(text_widget, check.group(2))
            text_widget.insert("end", "\n")
            continue
        ordered = re.match(r"^\s*(\d+)[.)]\s+(.*)$", raw_line)
        if ordered:
            text_widget.insert("end", f"{ordered.group(1)}. ", ("bullet",))
            _insert_inline(text_widget, ordered.group(2))
            text_widget.insert("end", "\n")
            continue
        bullet = re.match(r"^\s*[-*+]\s+(.*)$", raw_line)
        if bullet:
            text_widget.insert("end", "• ", ("bullet",))
            _insert_inline(text_widget, bullet.group(1))
            text_widget.insert("end", "\n")
            continue
        _insert_inline(text_widget, raw_line)
        text_widget.insert("end", "\n")


def render_rich_content_preview(app, comp, parent_widget, is_flex, pack_side,
                                bg_color):
    from ..ui import (
        _build_tk_font,
        _get_style_fg,
        _get_body_style,
        _merge_with_body,
    )

    semantic = comp.comp_type
    content, style, surface_bg, _holder = _surface(
        app, comp, parent_widget, is_flex, pack_side, bg_color, semantic
    )
    body_fg = _get_style_fg(_get_body_style())
    fg = _get_style_fg(style) or body_fg or "#212121"
    tokens = __import__("apkpy_lib.ui", fromlist=["global_styles"]).global_styles.get(
        "__theme__", {}
    )
    muted = tokens.get("text_secondary", "#6B7280")
    accent = tokens.get("secondary", tokens.get("primary", "#6750A4"))
    base_font_spec = _build_tk_font(style, default_size=14)
    base_modifiers = {str(value).lower() for value in base_font_spec[2:]}
    base_font = tkfont.Font(
        family=base_font_spec[0],
        size=base_font_spec[1],
        weight="bold" if "bold" in base_modifiers else "normal",
        slant="italic" if "italic" in base_modifiers else "roman",
    )
    source = (
        comp.kwargs.get("source", "")
        if semantic == "markdown"
        else "".join(str(span.get("text", "")) for span in comp.kwargs.get("spans", []))
    )
    approximate_lines = max(
        2,
        sum(max(1, math.ceil(len(line) / 46)) for line in str(source).splitlines()),
    )
    text_widget = tk.Text(
        content,
        wrap="word",
        # Do not let Tk's 80-character default request enlarge the hidden
        # canvas before the Previewer has assigned its responsive width.
        width=1,
        height=min(30, approximate_lines + 1),
        bg=surface_bg,
        fg=fg,
        insertbackground=fg,
        relief="flat",
        bd=0,
        highlightthickness=0,
        padx=0,
        pady=0,
        spacing1=2,
        spacing3=3,
        cursor="arrow",
        font=base_font,
    )
    # This surface already follows the Text widget's requested height. Asking
    # pack() to expand gives the widget an oversized vertical parcel and centers
    # it inside that parcel, which looks like a large blank top margin.
    text_widget.pack(fill="x")
    configure_markdown_tags(text_widget, base_font, tokens, accent, muted)

    if semantic == "markdown":
        from ..core.style_parser import wants_code_copy
        _render_markdown(
            text_widget, comp.kwargs.get("source", ""),
            copy_code=wants_code_copy(style),
        )
    else:
        for index, span in enumerate(comp.kwargs.get("spans", [])):
            tags = []
            for flag in ("bold", "italic", "underline", "strike", "code"):
                if span.get(flag):
                    tags.append(flag)
            if span.get("link"):
                tags.append("link")
            if span.get("color"):
                name = f"span_color_{index}"
                text_widget.tag_configure(name, foreground=span["color"])
                tags.append(name)
            if span.get("size"):
                name = f"span_size_{index}"
                preview_size = max(
                    8,
                    round(
                        int(span["size"]) * _RICH_SPAN_PREVIEW_SCALE
                    ),
                )
                text_widget.tag_configure(
                    name,
                    font=_font(
                        base_font,
                        size=preview_size,
                        bold=bool(span.get("bold")),
                        italic=bool(span.get("italic")),
                    ),
                )
                tags.append(name)
            text_widget.insert("end", span.get("text", ""), tuple(tags))

    # A disabled Tk Text remains selectable/copyable, but cannot be changed by
    # paste, IME or accessibility input. This matches Android TextView.
    text_widget.configure(state="disabled")

    resize_job = [None]
    resize_attempts = [0]
    measured_width = [None]
    resize_bound = [False]
    settle_passes = [0]

    def apply_height():
        resize_job[0] = None
        try:
            # During the first idle pass an embedded Text can still report one
            # pixel of width. Measuring then treats almost every glyph as a
            # separate display line. Wait for the canvas to assign the real
            # responsive width before changing the requested height.
            if text_widget.winfo_width() < 80:
                resize_attempts[0] += 1
                if resize_attempts[0] <= 40:
                    resize_job[0] = text_widget.after(25, apply_height)
                return
            resize_attempts[0] = 0
            current_width = int(text_widget.winfo_width())
            measured = text_widget.count(
                "1.0",
                "end-1c",
                "update",
                "displaylines",
            )
            measured_pixels = text_widget.count(
                "1.0",
                "end-1c",
                "update",
                "ypixels",
            )
            # Tk reports transitions between display lines, so a non-empty
            # document needs one additional row for its first line.
            measured_count = (
                measured[0]
                if isinstance(measured, (tuple, list))
                else measured
            )
            rendered_lines = (
                int(measured_count) + 1
                if measured_count is not None
                else 1
            )
            measured_pixel_count = (
                measured_pixels[0]
                if isinstance(measured_pixels, (tuple, list))
                else measured_pixels
            )
            line_unit = max(
                1,
                int(base_font.metrics("linespace")) + 5,
            )
            pixel_lines = (
                int(
                    math.ceil(
                        (int(measured_pixel_count) + line_unit) / line_unit
                    )
                )
                if measured_pixel_count is not None
                else 1
            )
            target = max(
                1,
                min(40, max(rendered_lines, pixel_lines)),
            )
            if int(text_widget.cget("height")) != target:
                text_widget.configure(height=target)
            measured_width[0] = current_width
            if not resize_bound[0]:
                # Bind only after the initial geometry pass. Binding before the
                # canvas is mapped observes alternating 1px/transient sizes.
                text_widget.bind(
                    "<Configure>",
                    fit_to_rendered_lines,
                    add="+",
                )
                resize_bound[0] = True
            if settle_passes[0] < 3:
                # The outer canvas can gain its final width immediately after
                # the first height change without delivering that transient
                # resize to a newly-bound child. A few bounded rechecks make
                # the result deterministic without leaving a polling loop.
                settle_passes[0] += 1
                resize_job[0] = text_widget.after(150, apply_height)
        except (tk.TclError, TypeError, ValueError):
            return

    def fit_to_rendered_lines(event=None):
        candidate_width = (
            int(event.width)
            if event is not None and getattr(event, "width", None) is not None
            else int(text_widget.winfo_width())
        )
        if candidate_width < 80 or measured_width[0] == candidate_width:
            return

        if resize_job[0] is not None:
            try:
                text_widget.after_cancel(resize_job[0])
            except tk.TclError:
                pass

        # Debounce instead of measuring on the first idle pass: the rounded
        # canvas emits a short Configure burst while assigning its real width.
        resize_job[0] = text_widget.after(120, apply_height)

    # Line wrapping is only final once Tk knows the component width. Refit on
    # resize so responsive previews stay compact instead of reserving guessed
    # blank lines.
    resize_job[0] = text_widget.after(250, apply_height)
    if not comp.kwargs.get("selectable", True):
        text_widget.bind("<Button-1>", lambda _event: "break")
    comp._rich_text_widget = text_widget


def _visible_nodes(nodes, depth=0):
    result = []
    for node in nodes:
        result.append((node, depth))
        if node.get("expanded") and node.get("children"):
            result.extend(_visible_nodes(node["children"], depth + 1))
    return result


def render_tree_preview(app, comp, parent_widget, is_flex, pack_side, bg_color):
    from ..ui import (
        _get_style_bg,
        _get_style_fg,
        _get_body_style,
        _merge_with_body,
        _resolve_css_size_tk,
    )

    style = _merge_with_body(comp.kwargs.get("comp_id"), "tree_view")
    raw_height = _resolve_css_size_tk(
        style.get("height", "360px"),
        "height",
        getattr(app, "_style_viewport", None),
        360,
    )
    height = max(180, int(raw_height or 360))
    content, style, surface_bg, _holder = _surface(
        app,
        comp,
        parent_widget,
        is_flex,
        pack_side,
        bg_color,
        "tree_view",
        fixed_height=height,
    )
    fg = _get_style_fg(style) or _get_style_fg(_get_body_style()) or "#212121"
    item_bg = style.get("item-background-color") or surface_bg
    divider = style.get("item-border-color") or style.get("border-color") or "#3F3F46"
    tokens = __import__("apkpy_lib.ui", fromlist=["global_styles"]).global_styles.get(
        "__theme__", {}
    )
    muted = style.get("subtitle-color") or tokens.get("text_secondary", "#6B7280")
    accent = style.get("accent-color") or tokens.get("secondary", "#6750A4")
    row_height = int(comp.kwargs.get("row_height", 58))

    viewport = tk.Canvas(
        content,
        bg=surface_bg,
        bd=0,
        highlightthickness=0,
        height=max(1, height - 8),
    )
    viewport.pack(side="left", fill="both", expand=True)
    scrollbar = tk.Scrollbar(content, orient="vertical", command=viewport.yview)
    scrollbar.pack(side="right", fill="y")
    viewport.configure(yscrollcommand=scrollbar.set)
    rows = tk.Frame(viewport, bg=surface_bg, bd=0, highlightthickness=0)
    row_window = viewport.create_window((0, 0), window=rows, anchor="nw")

    def update_scroll(_event=None):
        viewport.configure(scrollregion=viewport.bbox("all"))

    rows.bind("<Configure>", update_scroll)
    viewport.bind(
        "<Configure>",
        lambda event: viewport.itemconfigure(row_window, width=event.width),
    )

    def redraw():
        for child in rows.winfo_children():
            child.destroy()
        visible = _visible_nodes(comp.kwargs.get("nodes", []))
        for node, depth in visible:
            row = tk.Frame(
                rows,
                bg=item_bg,
                height=row_height,
                highlightbackground=divider,
                highlightthickness=0,
            )
            row.pack(fill="x")
            row.pack_propagate(False)
            indent = 12 + min(12, depth) * 20
            has_children = bool(node.get("children"))
            disclosure = "▼" if has_children and node.get("expanded") else (
                "▶" if has_children else "•"
            )
            marker = tk.Label(
                row,
                text=disclosure,
                bg=item_bg,
                fg=accent if has_children else muted,
                font=("Segoe UI Symbol", 10),
                width=2,
                anchor="center",
            )
            marker.pack(side="left", padx=(indent, 3))
            texts = tk.Frame(row, bg=item_bg)
            texts.pack(side="left", fill="both", expand=True, pady=(7, 5))
            title = tk.Label(
                texts,
                text=node.get("title", ""),
                bg=item_bg,
                fg=fg,
                font=("Segoe UI", 11, "bold"),
                anchor="w",
            )
            title.pack(fill="x")
            subtitle = node.get("subtitle", "")
            subtitle_widget = None
            if subtitle:
                subtitle_widget = tk.Label(
                    texts,
                    text=subtitle,
                    bg=item_bg,
                    fg=muted,
                    font=("Segoe UI", 9),
                    anchor="w",
                )
                subtitle_widget.pack(fill="x")
            separator = tk.Frame(rows, bg=divider, height=1)
            separator.pack(fill="x", padx=(indent + 25, 0))

            if has_children:
                def toggle(_event=None, current=node):
                    current["expanded"] = not current.get("expanded", False)
                    redraw()

                for widget in (row, marker, texts, title, subtitle_widget):
                    if widget is not None:
                        widget.configure(cursor="hand2")
                        widget.bind("<Button-1>", toggle)
        update_scroll()

    def on_wheel(event):
        viewport.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    viewport.bind("<MouseWheel>", on_wheel)
    rows.bind("<MouseWheel>", on_wheel)
    comp._tree_update_fn = lambda nodes: (
        comp.kwargs.__setitem__(
            "nodes",
            _normalise_nodes(
                nodes,
                expand_depth=int(comp.kwargs.get("expand_depth", 1)),
            ),
        ),
        redraw(),
    )
    redraw()


__all__ = [
    "markdown",
    "rich_text",
    "tree_view",
    "render_rich_content_preview",
    "render_tree_preview",
    "configure_markdown_tags",
    "render_markdown",
]
