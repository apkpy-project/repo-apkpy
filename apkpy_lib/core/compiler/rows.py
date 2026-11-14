"""virtual_collection(row=...): a row drawn with the app's own components."""
import os
import re

from ...theme import collection_bubbles, component_style

from .style import _parse_aspect_ratio
from .expressions import _escape_java_literal


# ── virtual_collection(row=...) ──────────────────────────────────────────────
# The view ids a row's components get in its own layout. They are handed out
# before either generator runs -- the Activity's Java is written before the
# XML -- in the order the XML generator counts them, from zero, and the
# generator is checked against them (_row_layout_xml).
_ROW_ID_PREFIX = {
    'label': 'lbl', 'button': 'btn', 'inputs': 'inp', 'input_field': 'inp',
    'card': 'card', 'container': 'cnt', 'image': 'img',
}
_ROW_TOKEN = re.compile(r'\{([A-Za-z_][A-Za-z0-9_.-]*)\}')
_PICTURE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')


def _row_components(root):
    """The row's components, depth first, the root included."""
    found = []
    pending = [root]
    while pending:
        comp = pending.pop(0)
        found.append(comp)
        pending[0:0] = list(comp.get('children') or [])
    return found


def _assign_row_ids(root):
    counts = {}
    for comp in _row_components(root):
        prefix = _ROW_ID_PREFIX.get(comp.get('comp_type'))
        if prefix:
            counts[prefix] = counts.get(prefix, 0) + 1
            comp['_xml_id'] = '%s%d' % (prefix, counts[prefix])


def _row_fill(pattern, item):
    return _ROW_TOKEN.sub(lambda m: str((item or {}).get(m.group(1), '')), str(pattern))


def _package_row_pictures(transpiler, comp):
    """A row's pictures ship with the app: a fixed source as it is, and a
    ``{field}`` source for every item written in the file that names a local
    picture. Web addresses need the network."""
    for part in _row_components(comp['row']):
        if part.get('comp_type') != 'image':
            continue
        src = str(part.get('src') or '')
        if not src:
            continue
        if '{' not in src:
            if not src.startswith(('http://', 'https://')):
                transpiler.set_src_assets.add(src)
            continue
        if 'INTERNET' not in transpiler.declared_permissions:
            transpiler.declared_permissions.append('INTERNET')
        for item in comp.get('items', []) or []:
            value = _row_fill(src, item)
            if value and not value.startswith(('http://', 'https://')) \
                    and os.path.splitext(value)[1].lower() in _PICTURE_EXTENSIONS:
                transpiler.set_src_assets.add(value)


def _emit_row_adapter_setup(lines, indent, jv, comp, styles, screen_id, click_java,
                            item_callbacks):
    """``{jv}Adapter = new ApkpyRowAdapter(...)`` for a row= collection."""
    bindings, actions = _row_bindings(comp)
    lit = _row_active_buttons(comp)
    ratio_ids, ratio_values = [], []
    for part in _row_components(comp['row']):
        if part.get('comp_type') != 'image' or part.get('avatar') or not part.get('_xml_id'):
            continue
        part_style = component_style(styles, 'image', part.get('id'))
        ratio = _parse_aspect_ratio(part.get('aspect_ratio') or part_style.get('aspect-ratio'))
        if ratio and not part_style.get('height'):
            ratio_ids.append(part['_xml_id'])
            ratio_values.append(ratio)

    prefix = _row_layout_name(screen_id, jv) + '_'

    def _ids(names):
        return ", ".join("R.id.%s%s" % (prefix, name) for name in names)

    def _texts(values):
        return ", ".join('"%s"' % _escape_java_literal(str(value)) for value in values)

    calls = []
    for _view, callback in actions:
        if callback in item_callbacks:
            calls.append("_item -> pythonCallback_%s(_item)" % callback)
        else:
            calls.append("_item -> pythonCallback_%s()" % callback)
    lines.append(
        f"{indent}{jv}Adapter = new ApkpyRowAdapter({jv}_items, "
        f"R.layout.{_row_layout_name(screen_id, jv)}, "
        f"new int[]{{{_ids(view for view, _k, _p in bindings)}}}, "
        f"new String[]{{{_texts(kind for _v, kind, _p in bindings)}}}, "
        f"new String[]{{{_texts(pattern for _v, _k, pattern in bindings)}}}, "
        f"new int[]{{{_ids(view for view, _c in actions)}}}, "
        f"new ApkpyVirtualClick[]{{{', '.join(calls)}}}, "
        f"new int[]{{{_ids(ratio_ids)}}}, "
        f"new float[]{{{', '.join('%.6ff' % value for value in ratio_values)}}}, "
        f"new int[]{{{_ids(view for view, _p, _on, _off in lit)}}}, "
        f"new String[]{{{_texts(pattern for _v, pattern, _on, _off in lit)}}}, "
        f"new int[]{{{', '.join('R.drawable.' + on for _v, _p, on, _off in lit)}}}, "
        f"new int[]{{{', '.join('R.drawable.' + off for _v, _p, _on, off in lit)}}}, "
        f"{click_java});"
    )
    # gap: on the collection spaces its rows, as it does a template's.
    _bubbles, shape = collection_bubbles(styles, comp.get('id'), [])
    if shape and shape[1] > 0:
        lines.append(f"{indent}{jv}Adapter.setGap({shape[1]});")


def _row_layout_name(screen_id, collection_var):
    """res/layout/<this>.xml -- the same name from the Java and the XML side."""
    return 'apkpy_row_%s_%s' % (re.sub(r'[^a-z0-9_]', '_', str(screen_id).lower()),
                                collection_var)


def _every_comp(comp_list):
    for comp in comp_list or ():
        yield comp
        yield from _every_comp(comp.get('children'))


def _row_bindings(comp):
    """What the row adapter fills on every bind: (view id, what, pattern),
    and the views whose tap runs a command: (view id, callback, takes item)."""
    bindings, actions = [], []
    for part in _row_components(comp['row']):
        view = part.get('_xml_id')
        if not view:
            continue
        kind = part.get('comp_type')
        if kind in ('label', 'button') and '{' in str(part.get('text') or ''):
            bindings.append((view, 'text', str(part['text'])))
        if kind == 'image' and '{' in str(part.get('src') or ''):
            bindings.append((view, 'src', str(part['src'])))
        if '{' in str(part.get('describe') or ''):
            bindings.append((view, 'describe', str(part['describe'])))
        visible = part.get('visible')
        if isinstance(visible, str) and '{' in visible:
            # An avatar's id is on the picture; its frame is what takes space.
            bindings.append((view, 'visible_parent' if part.get('avatar') else 'visible',
                             visible))
        command = part.get('command')
        if command and kind in ('button', 'image', 'container', 'card'):
            actions.append((view, command))
    return bindings, actions


def _row_active_buttons(comp):
    """(view id, pattern, lit drawable, plain drawable) for the buttons of a
    row whose active="{field}" lights them."""
    found = []
    for part in _row_components(comp['row']):
        active = part.get('active')
        if part.get('comp_type') == 'button' and part.get('_xml_id') \
                and isinstance(active, str) and '{' in active \
                and part.get('_active_icon_drawable') and part.get('_icon_drawable'):
            found.append((part['_xml_id'], active, part['_active_icon_drawable'],
                          part['_icon_drawable']))
    return found
