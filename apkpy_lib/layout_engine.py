"""Shared normalization and Preview geometry for advanced ApkPy layouts.

The Android backend consumes the same compact metadata through ApkpyLayout,
while the desktop Preview uses :func:`compute_layout_boxes` directly. Keeping
CSS parsing here prevents the two renderers from inventing different rules.
"""

import math
import re


ADVANCED_CHILD_PROPERTIES = frozenset({
    "flex-grow", "flex-shrink", "flex-basis", "align-self",
    "grid-column", "grid-row", "aspect-ratio", "position",
    "z-index", "top", "right", "bottom", "left",
})


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
        return float(match.group(0)) if match else float(default)


def box_shorthand(value):
    """CSS box shorthand as (top, right, bottom, left), or None if empty.

    ``margin: 24px 16px`` is four sides written short. Both renderers used to
    strip the non-digits out of the whole string and read what was left as one
    number, so ``24px 16px 0px 16px`` became a margin of 2,416,016 -- the
    screen went blank and nothing said why.
    """
    parts = []
    for piece in str(value or "").split():
        found = re.findall(r"-?\d+(?:\.\d+)?", piece)
        if found:
            parts.append(float(found[0]))
    if not parts:
        return None
    if len(parts) == 1:
        return (parts[0],) * 4
    if len(parts) == 2:
        return (parts[0], parts[1], parts[0], parts[1])
    if len(parts) == 3:
        return (parts[0], parts[1], parts[2], parts[1])
    return (parts[0], parts[1], parts[2], parts[3])


def corner_radii(value):
    """CSS ``border-radius`` as (top-left, top-right, bottom-right,
    bottom-left) in px.

    Both runtimes used to strip every non-digit from the value, so
    ``24px 24px 0 0`` -- a sheet rounded only at the top -- became a radius
    of 242400. The shorthand expands the way CSS expands it; an elliptical
    ``a / b`` keeps its horizontal radii."""
    text = str(value or '').split('/')[0].strip()
    parts = [max(0.0, _number(part, 0.0)) for part in text.split() if part]
    if not parts:
        return (0.0, 0.0, 0.0, 0.0)
    if len(parts) == 1:
        return (parts[0],) * 4
    if len(parts) == 2:
        return (parts[0], parts[1], parts[0], parts[1])
    if len(parts) == 3:
        return (parts[0], parts[1], parts[2], parts[1])
    return tuple(parts[:4])


def css_dimension(value, base, default=None, viewport=None, axis="width"):
    """Resolve a compact CSS dimension to logical pixels."""
    if value is None or str(value).strip().lower() in ("", "auto", "none"):
        return default
    text = str(value).strip().lower()
    if text in ("match_parent", "fill"):
        return float(base)
    match = re.match(r"^(-?[\d.]+)\s*(px|dp|%|vw|vh)?$", text)
    if not match:
        return default
    number = float(match.group(1))
    unit = match.group(2) or "px"
    if unit == "%":
        return float(base) * number / 100.0
    if unit in ("vw", "vh"):
        vw, vh = viewport or (base, base)
        return float(vw if unit == "vw" else vh) * number / 100.0
    return number


def parse_aspect_ratio(value):
    """Return width/height for ``16/9``, ``16:9`` or a decimal ratio."""
    text = str(value or "").strip()
    if not text:
        return None
    for separator in ("/", ":"):
        if separator in text:
            left, right = text.split(separator, 1)
            denominator = _number(right, 0)
            return (_number(left, 0) / denominator) if denominator else None
    ratio = _number(text, 0)
    return ratio if ratio > 0 else None


def _split_css_values(text):
    values, current, depth = [], [], 0
    for char in str(text or ""):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char.isspace() and depth == 0:
            if current:
                values.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        values.append("".join(current))
    return values


def parse_grid_tracks(value):
    """Normalize grid-template-columns, including simple repeat()."""
    text = str(value or "1fr").strip().lower()
    repeat = re.fullmatch(r"repeat\(\s*(\d+)\s*,\s*([^()]+)\s*\)", text)
    if repeat:
        return [repeat.group(2).strip()] * max(1, int(repeat.group(1)))
    tracks = _split_css_values(text)
    return tracks or ["1fr"]


def grid_line(value):
    """Return ``(zero_based_start|None, span)`` for grid-column/grid-row."""
    text = str(value or "auto").strip().lower()
    if not text or text == "auto":
        return None, 1
    if text.startswith("span "):
        return None, max(1, int(_number(text, 1)))
    parts = [part.strip() for part in text.split("/", 1)]
    start = max(0, int(_number(parts[0], 1)) - 1)
    if len(parts) == 1:
        return start, 1
    if parts[1].startswith("span "):
        return start, max(1, int(_number(parts[1], 1)))
    end = max(start + 1, int(_number(parts[1], start + 2)) - 1)
    return start, max(1, end - start)


def line_count(value, default=1):
    """How many lines a row's text may occupy before it is cut off.

    One line is the list-row default on both sides. A chat message is the case
    that needs more: read as a single ellipsised line it is unreadable, and
    both runtimes were hard-coded to one.
    """
    if value is None or str(value).strip() == "":
        return max(1, int(default))
    text = str(value).strip().lower()
    if text in ("none", "auto"):
        return 99
    return max(1, min(99, int(round(_number(text, default)))))


def _align(value, default="start"):
    value = str(value or default).strip().lower()
    return {
        "flex-start": "start", "flex-end": "end",
        "space_between": "space-between", "space_around": "space-around",
        "space_evenly": "space-evenly",
    }.get(value, value)


def is_advanced_container(style, child_styles=(), responsive=False):
    display = str(style.get("display", "")).strip().lower()
    if display == "grid":
        return True
    if display == "flex" and any(
        key in style for key in ("flex-wrap", "justify-content", "align-items")
    ):
        return True
    if responsive and display == "grid":
        return True
    return any(
        any(key in child for key in ADVANCED_CHILD_PROPERTIES)
        for child in child_styles
    )


def encode_container_tag(style, fallback_direction="column"):
    mode = "grid" if str(style.get("display", "")).lower() == "grid" else "flex"
    parts = ["apkpy", f"mode={mode}"]
    gap = max(0, int(round(_number(style.get("gap"), 0))))
    parts.append(f"gap={gap}")
    parts.append(f"justify={_align(style.get('justify-content'), 'start')}")
    parts.append(f"align={_align(style.get('align-items'), 'stretch')}")
    if mode == "grid":
        tracks = parse_grid_tracks(style.get("grid-template-columns", "1fr"))
        parts.append("tracks=" + ",".join(track.replace(" ", "") for track in tracks))
    else:
        direction = str(style.get("flex-direction", fallback_direction)).strip().lower()
        parts.append(f"direction={'row' if direction == 'row' else 'column'}")
        wrap = str(style.get("flex-wrap", "nowrap")).strip().lower()
        parts.append(f"wrap={1 if wrap in ('wrap', 'wrap-reverse') else 0}")
        parts.append(f"reverse={1 if wrap == 'wrap-reverse' else 0}")
    return ";".join(parts)


def encode_child_tag(style, parent_direction=None):
    parts = ["apkpy-child"]
    mapping = {
        "flex-grow": "grow", "flex-shrink": "shrink",
        "flex-basis": "basis", "align-self": "alignSelf",
        "aspect-ratio": "ratio", "position": "position",
        "z-index": "z", "top": "top", "right": "right",
        "bottom": "bottom", "left": "left", "width": "width",
        "height": "height",
    }
    for css_key, tag_key in mapping.items():
        if css_key not in style:
            continue
        value = style[css_key]
        if css_key == "aspect-ratio":
            value = parse_aspect_ratio(value)
            if value is None:
                continue
            value = f"{value:.6g}"
        elif css_key in ("align-self", "position"):
            value = _align(value, "auto")
        parts.append(f"{tag_key}={str(value).replace(';', '')}")
    # In the Previewer a growing child without an explicit main-axis size
    # starts from a zero basis.  Encode the same rule for Android so sibling
    # actions with ``flex-grow: 1`` receive equal widths instead of inheriting
    # different bases from their label lengths.
    direction = str(parent_direction or "").strip().lower()
    main_property = (
        "width" if direction in ("row", "horizontal") else
        "height" if direction in ("column", "vertical") else None
    )
    if (
        main_property
        and "flex-grow" in style
        and _number(style.get("flex-grow"), 0) > 0
        and "flex-basis" not in style
        and main_property not in style
    ):
        parts.append("basis=0")
    for css_key, prefix in (("grid-column", "col"), ("grid-row", "row")):
        if css_key in style:
            start, span = grid_line(style[css_key])
            if start is not None:
                parts.append(f"{prefix}={start}")
            parts.append(f"{prefix}Span={span}")
    return ";".join(parts) if len(parts) > 1 else ""


def _track_widths(tracks, available, gap, viewport):
    usable = max(0.0, available - gap * max(0, len(tracks) - 1))
    widths = [0.0] * len(tracks)
    fr_total = 0.0
    for index, track in enumerate(tracks):
        text = str(track).strip().lower()
        if text.endswith("fr"):
            fr_total += max(0.0, _number(text, 1))
        else:
            widths[index] = max(0.0, css_dimension(
                text, usable, 0, viewport=viewport, axis="width"
            ))
    remaining = max(0.0, usable - sum(widths))
    if fr_total:
        for index, track in enumerate(tracks):
            if str(track).strip().lower().endswith("fr"):
                widths[index] = remaining * max(0.0, _number(track, 1)) / fr_total
    return widths


def _justify_positions(used, available, count, gap, justify):
    extra = max(0.0, available - used)
    offset, actual_gap = 0.0, gap
    if justify == "center":
        offset = extra / 2
    elif justify == "end":
        offset = extra
    elif justify == "space-between" and count > 1:
        actual_gap += extra / (count - 1)
    elif justify == "space-around" and count:
        actual_gap += extra / count
        offset = (actual_gap - gap) / 2
    elif justify == "space-evenly" and count:
        actual_gap += extra / (count + 1)
        offset = actual_gap - gap
    return offset, actual_gap


def compute_layout_boxes(container_style, items, width, height=None, viewport=None):
    """Compute Preview boxes for flex/grid/absolute children.

    Each item is ``{"style": dict, "width": req_w, "height": req_h}``.
    Returns ``(boxes, required_height)`` where boxes contain x/y/width/height/z.
    """
    width = max(1.0, float(width))
    viewport = viewport or (width, height or width)
    gap = max(0.0, _number(container_style.get("gap"), 0))
    mode = "grid" if str(container_style.get("display", "")).lower() == "grid" else "flex"
    boxes = [None] * len(items)
    flow = []
    absolute = []
    for index, item in enumerate(items):
        if str(item.get("style", {}).get("position", "")).lower() == "absolute":
            absolute.append((index, item))
        else:
            flow.append((index, item))

    required_height = 0.0
    if mode == "grid":
        tracks = parse_grid_tracks(container_style.get("grid-template-columns", "1fr"))
        columns = max(1, len(tracks))
        col_widths = _track_widths(tracks, width, gap, viewport)
        occupied, placements, cursor = set(), [], 0
        for index, item in flow:
            style = item.get("style", {})
            explicit_col, col_span = grid_line(style.get("grid-column"))
            explicit_row, row_span = grid_line(style.get("grid-row"))
            col_span = min(columns, col_span)
            if explicit_col is not None or explicit_row is not None:
                row = explicit_row or 0
                col = min(columns - col_span, explicit_col or 0)
            else:
                while True:
                    row, col = divmod(cursor, columns)
                    if col + col_span <= columns and all(
                        (row + rr, col + cc) not in occupied
                        for rr in range(row_span) for cc in range(col_span)
                    ):
                        break
                    cursor += 1
                cursor = row * columns + col + col_span
            for rr in range(row_span):
                for cc in range(col_span):
                    occupied.add((row + rr, col + cc))
            placements.append((index, item, row, col, row_span, col_span))
        row_count = max((row + span for _, _, row, _, span, _ in placements), default=0)
        row_heights = [0.0] * row_count
        measured = []
        for index, item, row, col, row_span, col_span in placements:
            cell_width = sum(col_widths[col:col + col_span]) + gap * (col_span - 1)
            style = item.get("style", {})
            item_width = css_dimension(style.get("width"), cell_width, cell_width, viewport)
            ratio = parse_aspect_ratio(style.get("aspect-ratio"))
            item_height = css_dimension(
                style.get("height"), height or viewport[1], item.get("height", 1),
                viewport, "height",
            )
            if ratio:
                item_height = item_width / ratio
            measured.append((index, row, col, row_span, col_span, item_width, item_height, style))
            share = item_height / row_span
            for rr in range(row, row + row_span):
                row_heights[rr] = max(row_heights[rr], share)
        col_x = [0.0]
        for value in col_widths[:-1]:
            col_x.append(col_x[-1] + value + gap)
        row_y = [0.0]
        for value in row_heights[:-1]:
            row_y.append(row_y[-1] + value + gap)
        for index, row, col, row_span, col_span, item_width, item_height, style in measured:
            cell_width = sum(col_widths[col:col + col_span]) + gap * (col_span - 1)
            cell_height = sum(row_heights[row:row + row_span]) + gap * (row_span - 1)
            align = _align(style.get("align-self"), _align(container_style.get("align-items"), "stretch"))
            x = col_x[col]
            y = row_y[row]
            if align == "center":
                y += max(0, (cell_height - item_height) / 2)
            elif align == "end":
                y += max(0, cell_height - item_height)
            elif align == "stretch" and not style.get("aspect-ratio"):
                item_height = cell_height
            boxes[index] = (x, y, min(cell_width, item_width), item_height, int(_number(style.get("z-index"), 0)))
        required_height = sum(row_heights) + gap * max(0, row_count - 1)
    else:
        direction = str(container_style.get("flex-direction", "row")).lower()
        horizontal = direction != "column"
        wrap = str(container_style.get("flex-wrap", "nowrap")).lower() in ("wrap", "wrap-reverse")
        main_limit = width if horizontal else float(height or sum(max(1, i.get("height", 1)) for _, i in flow) + gap * len(flow))
        lines, line, used = [], [], 0.0
        for index, item in flow:
            style = item.get("style", {})
            req_main = item.get("width" if horizontal else "height", 1)
            main_property = "width" if horizontal else "height"
            basis = css_dimension(style.get("flex-basis"), main_limit, None, viewport,
                                  main_property)
            if basis is None:
                if (
                    _number(style.get("flex-grow"), 0) > 0
                    and main_property not in style
                ):
                    basis = 0.0
                else:
                    basis = css_dimension(
                        style.get(main_property), main_limit, req_main,
                        viewport, main_property,
                    )
            cross_property = "height" if horizontal else "width"
            cross_limit = float(height or viewport[1]) if horizontal else width
            cross = css_dimension(
                style.get(cross_property), cross_limit,
                item.get(cross_property, 1), viewport, cross_property,
            )
            ratio = parse_aspect_ratio(style.get("aspect-ratio"))
            if ratio:
                cross = basis / ratio if horizontal else basis * ratio
            addition = basis + (gap if line else 0)
            if wrap and line and used + addition > main_limit:
                lines.append(line)
                line, used = [], 0.0
            line.append([index, item, max(1.0, basis), max(1.0, cross)])
            used += max(1.0, basis) + (gap if len(line) > 1 else 0)
        if line:
            lines.append(line)
        cross_cursor = 0.0
        line_data = []
        for current in lines:
            total = sum(entry[2] for entry in current) + gap * max(0, len(current) - 1)
            remaining = main_limit - total
            if remaining > 0:
                grow_total = sum(max(0.0, _number(e[1].get("style", {}).get("flex-grow"), 0)) for e in current)
                if grow_total:
                    for entry in current:
                        grow = max(0.0, _number(entry[1].get("style", {}).get("flex-grow"), 0))
                        entry[2] += remaining * grow / grow_total
            elif remaining < 0:
                shrink_total = sum(max(0.0, _number(e[1].get("style", {}).get("flex-shrink"), 1)) * e[2] for e in current)
                if shrink_total:
                    for entry in current:
                        weight = max(0.0, _number(entry[1].get("style", {}).get("flex-shrink"), 1)) * entry[2]
                        entry[2] = max(1.0, entry[2] + remaining * weight / shrink_total)
            used = sum(e[2] for e in current) + gap * max(0, len(current) - 1)
            line_cross = max((e[3] for e in current), default=0)
            if not horizontal and not wrap:
                # A normal ApkPy container is a single vertical flex column.
                # Its cross axis is the full available width, not the largest
                # requested child width.  Using the latter let wide Tk widgets
                # extend beyond the host and clipped their right-hand border.
                line_cross = width
            justify = _align(container_style.get("justify-content"), "start")
            main_cursor, actual_gap = _justify_positions(used, main_limit, len(current), gap, justify)
            for index, item, main_size, cross_size in current:
                style = item.get("style", {})
                align = _align(style.get("align-self"), _align(container_style.get("align-items"), "stretch"))
                cross_offset = 0.0
                cross_property = "height" if horizontal else "width"
                if align == "center":
                    cross_offset = (line_cross - cross_size) / 2
                elif align == "end":
                    cross_offset = line_cross - cross_size
                elif (align == "stretch" and
                      not style.get("aspect-ratio") and
                      not style.get(cross_property)):
                    cross_size = line_cross
                if horizontal:
                    box = (main_cursor, cross_cursor + cross_offset, main_size, cross_size)
                else:
                    box = (cross_cursor + cross_offset, main_cursor, cross_size, main_size)
                boxes[index] = (*box, int(_number(style.get("z-index"), 0)))
                main_cursor += main_size + actual_gap
            line_data.append(line_cross)
            cross_cursor += line_cross + gap
        required_height = (cross_cursor - gap if lines else 0) if horizontal else main_limit

    base_height = max(required_height, float(height or 0), 1.0)
    for index, item in absolute:
        style = item.get("style", {})
        left = css_dimension(style.get("left"), width, None, viewport)
        right = css_dimension(style.get("right"), width, None, viewport)
        top = css_dimension(style.get("top"), base_height, None, viewport, "height")
        bottom = css_dimension(style.get("bottom"), base_height, None, viewport, "height")
        item_width = css_dimension(style.get("width"), width, item.get("width", 1), viewport)
        item_height = css_dimension(style.get("height"), base_height, item.get("height", 1), viewport, "height")
        if left is not None and right is not None:
            item_width = max(1, width - left - right)
        ratio = parse_aspect_ratio(style.get("aspect-ratio"))
        if ratio:
            item_height = item_width / ratio
        x = left if left is not None else max(0, width - (right or 0) - item_width)
        y = top if top is not None else max(0, base_height - (bottom or 0) - item_height)
        boxes[index] = (x, y, item_width, item_height, int(_number(style.get("z-index"), 0)))
    return boxes, int(math.ceil(base_height))
