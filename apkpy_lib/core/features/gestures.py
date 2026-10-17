"""Swipe and drag on the rows of a virtual_collection, on the phone.

``virtual_collection(..., swipe_right=swipe(...), swipe_left=swipe(...),
reorder=True, on_reorder=fn)`` becomes an ``ItemTouchHelper`` on the
RecyclerView. The numbers and words come from ``gesture_rules`` -- the same
module the Previewer reads -- and every gesture is also registered as an
accessibility action on the row, so TalkBack offers Archive, Delete, Move up
and Move down without anybody performing the gesture.

``ApkpyGestures`` is a fixed class, written into the project only when a list
uses it, like ApkpyPager and ApkpyChart.
"""

import ast

from ... import gesture_rules as rules
from .. import unsupported

CODE = rules.CODE
DOCS = "https://repo-apkpy.pages.dev/ui-components/#rows-that-swipe-and-move"


def refuse(message, received, line=0, suggestions=None):
    from ...diagnostics import ApkpyError
    raise ApkpyError(
        message,
        code=CODE,
        title="A list gesture ApkPy cannot build",
        cause=("Swiping and reordering are for the rows of a list, and each "
               "swipe is written with swipe(icon, text, on_swipe=...)."),
        expected=('virtual_collection(items, row=..., swipe_right=swipe("archive", '
                  '"Archive", on_swipe=archive), on_reorder=moved)'),
        received=received,
        suggestions=suggestions or [
            'swipe_left=swipe("delete", "Delete", on_swipe=delete)',
            'swipe_right=swipe("archive", "Archive", on_swipe=archive, undo="Archived")',
        ],
        docs=DOCS,
        line=line or 0,
    )


def uses_gestures(comp):
    return bool(comp.get('_gestures'))


def _constant(node, default=None):
    if node is None:
        return default
    if isinstance(node, ast.Constant):
        return node.value
    return ast  # a marker: not a constant


def _callback(transpiler, node, tag, arity):
    """A named function or a lambda, as the name of a function Java calls.

    The first parameter is the row's item (JSON); a reorder callback's second
    one is the new position, a number.
    """
    if node is None:
        return None
    if isinstance(node, ast.Name):
        transpiler.json_item_callbacks.add(node.id)
        return node.id
    if isinstance(node, ast.Lambda):
        params = [a.arg for a in node.args.args]
        defaults = ['item', 'index'][:arity]
        params = (params + defaults[len(params):])[:arity]
        name = transpiler._unique_function_name(tag)
        body = ast.Expr(value=node.body)
        ast.fix_missing_locations(body)
        transpiler.functions[name] = {
            'args': params,
            'cmds': transpiler._parse_statements([body]),
            'string_args': set(params),
            'returns_value': False,
        }
        transpiler.json_item_callbacks.add(name)
        return name
    return False


def _parse_swipe(transpiler, node, side, collection_id, line):
    if node is None or (isinstance(node, ast.Constant) and node.value is None):
        return None
    if isinstance(node, ast.Name) and node.id in getattr(transpiler, 'swipe_defs', {}):
        node = transpiler.swipe_defs[node.id]
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'swipe'):
        refuse('virtual_collection(%s=...) takes swipe(icon, text, on_swipe=...).' % side,
               'swipe_%s=%s' % (side.split('_')[1], unsupported.describe(node)[:80]), line)
    keywords = {k.arg: k.value for k in node.keywords if k.arg}
    args = list(node.args)
    icon = _constant(args[0] if args else keywords.get('icon'))
    text = _constant(args[1] if len(args) > 1 else keywords.get('text'), '')
    color = _constant(keywords.get('color'))
    keep = _constant(keywords.get('keep'), False)
    undo = _constant(keywords.get('undo'))
    for name, value in (('icon', icon), ('text', text), ('color', color),
                        ('keep', keep), ('undo', undo)):
        if value is ast:
            refuse('swipe(%s=...) has to be written out in the source: the phone '
                   'draws the strip before any of your code runs.' % name,
                   unsupported.describe(node)[:100], line,
                   ['swipe("archive", "Archive", on_swipe=archive)'])
    if not str(icon or '').strip():
        refuse('swipe() needs an icon.', unsupported.describe(node)[:100], line)
    on_swipe_node = args[2] if len(args) > 2 else keywords.get('on_swipe')
    callback = _callback(transpiler, on_swipe_node,
                         '%s_%s' % (collection_id or 'list', side), 1)
    if callback is False:
        refuse('swipe(on_swipe=...) takes a function or a lambda that receives the item.',
               unsupported.describe(on_swipe_node)[:100], line)
    return {
        'icon': str(icon).strip(), 'text': str(text or '').strip(),
        'color': str(color) if color else None, 'keep': bool(keep),
        'undo': str(undo) if undo not in (None, '', False) else None,
        'callback': callback,
    }


def parse(transpiler, call, comp):
    """Read the gesture keywords of a virtual_collection(...) call."""
    keywords = {k.arg: k.value for k in call.keywords if k.arg}
    wanted = [k for k in ('swipe_right', 'swipe_left', 'reorder', 'on_reorder')
              if k in keywords]
    if not wanted:
        return
    line = getattr(call, 'lineno', 0)
    collection_id = comp.get('id')
    right = _parse_swipe(transpiler, keywords.get('swipe_right'), 'swipe_right',
                         collection_id, line)
    left = _parse_swipe(transpiler, keywords.get('swipe_left'), 'swipe_left',
                        collection_id, line)
    reorder = _constant(keywords.get('reorder'), False)
    if reorder is ast:
        refuse('virtual_collection(reorder=...) is True or False, written out.',
               unsupported.describe(keywords['reorder'])[:80], line)
    on_reorder = None
    if keywords.get('on_reorder') is not None:
        on_reorder = _callback(transpiler, keywords['on_reorder'],
                               '%s_reorder' % (collection_id or 'list'), 2)
        if on_reorder is False:
            refuse('virtual_collection(on_reorder=...) takes a function or a '
                   'lambda that receives the item and its new position.',
                   unsupported.describe(keywords['on_reorder'])[:100], line)
        # The position is a number on both sides: an int in the Previewer,
        # a number inside the Java method.
        transpiler.reorder_callbacks = getattr(transpiler, 'reorder_callbacks', set())
        transpiler.reorder_callbacks.add(on_reorder)
    wants_reorder = bool(reorder) or bool(on_reorder)
    if not (right or left or wants_reorder):
        return
    if comp.get('layout', 'list') != 'list':
        refuse('Swiping and reordering are for a list; this collection is a grid.',
               'virtual_collection(layout="grid", ...)', line,
               ['virtual_collection(items, row=..., swipe_left=swipe(...))'])
    comp['_gestures'] = {'right': right, 'left': left, 'reorder': wants_reorder,
                         'on_reorder': on_reorder}


def mark_reorder_positions(transpiler):
    """After the visit: a named on_reorder's second parameter is a number."""
    for name in getattr(transpiler, 'reorder_callbacks', ()) or ():
        info = transpiler.functions.get(name)
        if not info or len(info.get('args') or []) < 2:
            continue
        numeric = dict(info.get('numeric_args') or {})
        numeric[info['args'][1]] = False       # an int
        info['numeric_args'] = numeric
        info.setdefault('string_args', set()).add(info['args'][1])


def java_string(value):
    text = str(value or '')
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def _side_java(side, tokens):
    if not side:
        return 'null'
    color = rules.swipe_color(side['icon'], side.get('color'), tokens)
    return ('new ApkpyGestures.Side(android.graphics.Color.parseColor("%s"), '
            'R.drawable.%s, %s, %s)' % (color, side['_drawable'],
                                        java_string(side['text'] or side['icon']),
                                        'true' if side.get('keep') else 'false'))


def emit_setup(lines, indent, comp, tokens):
    """Attach the gestures right after the adapter, in onCreate."""
    spec = comp.get('_gestures')
    if not spec:
        return
    jv = comp['_java_var']
    on_reorder = spec.get('on_reorder')
    lines.append(f"{indent}ApkpyGestures.attach({jv}, {jv}_items, "
                 f"{_side_java(spec.get('right'), tokens)}, "
                 f"{_side_java(spec.get('left'), tokens)}, "
                 f"{'true' if spec.get('reorder') else 'false'}, "
                 "new ApkpyGestures.Listener() {")
    lines.append(f"{indent}    @Override public void onSwiped(int position, boolean right) "
                 f"{{ _apkpySwiped{jv.title()}(position, right); }}")
    if on_reorder:
        lines.append(f"{indent}    @Override public void onDropped(int from, int to) {{")
        lines.append(f"{indent}        if (to >= 0 && to < {jv}_items.size()) "
                     f"pythonCallback_{on_reorder}({jv}_items.get(to), String.valueOf(to));")
        lines.append(f"{indent}    }}")
    else:
        lines.append(f"{indent}    @Override public void onDropped(int from, int to) {{ }}")
    lines.append(f"{indent}}});")


def _branch(lines, jv, side, indent):
    callback = side.get('callback')
    call = f"pythonCallback_{callback}(item);" if callback else ""
    if side.get('keep'):
        lines.append(f"{indent}{jv}Adapter.notifyItemChanged(position);")
        if call:
            lines.append(f"{indent}{call}")
        return
    lines.append(f"{indent}{jv}_items.remove(position);")
    lines.append(f"{indent}{jv}Adapter.notifyItemRemoved(position);")
    if not side.get('undo'):
        if call:
            lines.append(f"{indent}{call}")
        return
    bar = "com.google.android.material.snackbar.Snackbar"
    lines.extend([
        f"{indent}final boolean[] undone = {{false}};",
        # The list itself is a local of onCreate; the snackbar finds its
        # place from the content view, as snackbar() does.
        f"{indent}{bar} bar = {bar}.make(findViewById(android.R.id.content), "
        f"{java_string(side['undo'])}, {bar}.LENGTH_INDEFINITE);",
        f"{indent}bar.setDuration({rules.UNDO_MS});",
        f"{indent}bar.setAction({java_string(rules.UNDO)}, v -> {{",
        f"{indent}    undone[0] = true;",
        f"{indent}    int at = Math.min(position, {jv}_items.size());",
        f"{indent}    {jv}_items.add(at, item);",
        f"{indent}    {jv}Adapter.notifyItemInserted(at);",
        f"{indent}}});",
        f"{indent}bar.addCallback(new com.google.android.material.snackbar."
        f"BaseTransientBottomBar.BaseCallback<{bar}>() {{",
        f"{indent}    @Override public void onDismissed({bar} shown, int event) {{",
        f"{indent}        if (!undone[0]) {{ {call} }}",
        f"{indent}    }}",
        f"{indent}}});",
        f"{indent}bar.show();",
    ])


def emit_methods(lines, comp):
    """The method a swipe calls: take the row away (or not) and tell the app."""
    spec = comp.get('_gestures')
    if not spec:
        return
    jv = comp['_java_var']
    lines.append("")
    lines.append(f"    private void _apkpySwiped{jv.title()}(final int position, boolean right) {{")
    lines.append(f"        if (position < 0 || position >= {jv}_items.size()) {{")
    lines.append(f"            {jv}Adapter.notifyDataSetChanged();")
    lines.append("            return;")
    lines.append("        }")
    lines.append(f"        final String item = {jv}_items.get(position);")
    for flag, key in (('right', 'right'), ('!right', 'left')):
        side = spec.get(key)
        if not side:
            continue
        lines.append(f"        if ({flag}) {{")
        _branch(lines, jv, side, "            ")
        lines.append("            return;")
        lines.append("        }")
    lines.append(f"        {jv}Adapter.notifyItemChanged(position);")
    lines.append("    }")


JAVA = r'''package __PACKAGE__;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.view.View;
import androidx.core.content.ContextCompat;
import androidx.core.view.ViewCompat;
import androidx.recyclerview.widget.ItemTouchHelper;
import androidx.recyclerview.widget.RecyclerView;

/**
 * Swipe and drag on the rows of a list (virtual_collection). The threshold,
 * colours, sizes and words are gesture_rules.py's, the module the Previewer
 * reads; every gesture is also an accessibility action on the row.
 */
public final class ApkpyGestures extends ItemTouchHelper.Callback {

    public interface Listener {
        void onSwiped(int position, boolean right);
        void onDropped(int from, int to);
    }

    /** What one direction reveals: a colour, a white icon and its words. */
    public static final class Side {
        final int color;
        final int icon;
        final String text;
        final boolean keep;

        public Side(int color, int icon, String text, boolean keep) {
            this.color = color;
            this.icon = icon;
            this.text = text;
            this.keep = keep;
        }
    }

    static final float THRESHOLD = __THRESHOLD__f;
    static final float ICON = __ICON__f;
    static final float EDGE = __EDGE__f;
    static final float GAP = __GAP__f;
    static final float LABEL = __LABEL__f;
    static final long SLIDE_MS = __SLIDE__L;
    static final String MOVE_UP = "__MOVE_UP__";
    static final String MOVE_DOWN = "__MOVE_DOWN__";

    private final RecyclerView list;
    private final java.util.List<String> items;
    private final Side right;
    private final Side left;
    private final boolean reorder;
    private final Listener listener;
    private final Drawable rightIcon;
    private final Drawable leftIcon;
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint words = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final float density;
    private final java.util.WeakHashMap<View, Boolean> offered = new java.util.WeakHashMap<>();
    private int dragFrom = -1;
    private int dragTo = -1;

    private ApkpyGestures(RecyclerView list, java.util.List<String> items, Side right,
                          Side left, boolean reorder, Listener listener) {
        this.list = list;
        this.items = items;
        this.right = right;
        this.left = left;
        this.reorder = reorder;
        this.listener = listener;
        this.density = list.getResources().getDisplayMetrics().density;
        this.rightIcon = right == null ? null : ContextCompat.getDrawable(list.getContext(), right.icon);
        this.leftIcon = left == null ? null : ContextCompat.getDrawable(list.getContext(), left.icon);
        words.setColor(0xFFFFFFFF);
        words.setTextSize(LABEL * list.getResources().getDisplayMetrics().scaledDensity);
        words.setTypeface(Typeface.DEFAULT_BOLD);
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            // A phone with its own font draws every weight from one variable
            // file; only the weight axis makes it bold (see ApkpyChart).
            try { words.setFontVariationSettings("'wght' 700"); } catch (Exception ignored) { }
        }
    }

    public static ApkpyGestures attach(RecyclerView list, java.util.List<String> items,
                                       Side right, Side left, boolean reorder,
                                       Listener listener) {
        ApkpyGestures gestures = new ApkpyGestures(list, items, right, left, reorder, listener);
        new ItemTouchHelper(gestures).attachToRecyclerView(list);
        gestures.offerActions();
        return gestures;
    }

    @Override public int getMovementFlags(RecyclerView view, RecyclerView.ViewHolder holder) {
        int drag = reorder ? (ItemTouchHelper.UP | ItemTouchHelper.DOWN) : 0;
        int swipe = (right != null ? ItemTouchHelper.RIGHT : 0) | (left != null ? ItemTouchHelper.LEFT : 0);
        return makeMovementFlags(drag, swipe);
    }

    @Override public boolean isLongPressDragEnabled() { return reorder; }

    @Override public boolean isItemViewSwipeEnabled() { return right != null || left != null; }

    @Override public float getSwipeThreshold(RecyclerView.ViewHolder holder) { return THRESHOLD; }

    @Override public boolean onMove(RecyclerView view, RecyclerView.ViewHolder from,
                                    RecyclerView.ViewHolder to) {
        int a = from.getBindingAdapterPosition();
        int b = to.getBindingAdapterPosition();
        if (a < 0 || b < 0) return false;
        if (dragFrom < 0) dragFrom = a;
        dragTo = b;
        move(a, b);
        return true;
    }

    private void move(int a, int b) {
        String row = items.remove(a);
        items.add(b, row);
        RecyclerView.Adapter<?> adapter = list.getAdapter();
        if (adapter != null) adapter.notifyItemMoved(a, b);
    }

    @Override public void onSwiped(RecyclerView.ViewHolder holder, int direction) {
        int position = holder.getBindingAdapterPosition();
        Side side = direction == ItemTouchHelper.RIGHT ? right : left;
        if (side != null && side.keep) comeBack(holder.itemView);
        if (position >= 0) listener.onSwiped(position, direction == ItemTouchHelper.RIGHT);
    }

    /**
     * A row that stays (keep=True) slides back into place. ItemTouchHelper
     * leaves a swiped row off the edge until an item animator brings it back,
     * and these lists have none: "Renew the gym card" stayed off-screen over
     * its purple strip, on a phone, the first time it was tried.
     */
    private void comeBack(final View row) {
        row.animate().translationX(0f).setDuration(SLIDE_MS)
                .withEndAction(() -> getDefaultUIUtil().clearView(row)).start();
    }

    @Override public void onSelectedChanged(RecyclerView.ViewHolder holder, int state) {
        super.onSelectedChanged(holder, state);
        if (state == ItemTouchHelper.ACTION_STATE_DRAG && holder != null) {
            ViewCompat.setElevation(holder.itemView, 8f * density);
        }
    }

    @Override public void clearView(RecyclerView view, RecyclerView.ViewHolder holder) {
        super.clearView(view, holder);
        ViewCompat.setElevation(holder.itemView, 0f);
        if (dragFrom >= 0 && dragTo >= 0 && dragFrom != dragTo) listener.onDropped(dragFrom, dragTo);
        dragFrom = -1;
        dragTo = -1;
    }

    @Override public void onChildDraw(Canvas canvas, RecyclerView view, RecyclerView.ViewHolder holder,
                                      float dX, float dY, int state, boolean active) {
        if (state == ItemTouchHelper.ACTION_STATE_SWIPE && dX != 0f) {
            Side side = dX > 0 ? right : left;
            Drawable icon = dX > 0 ? rightIcon : leftIcon;
            if (side != null) strip(canvas, holder.itemView, dX, side, icon);
        }
        super.onChildDraw(canvas, view, holder, dX, dY, state, active);
    }

    private void strip(Canvas canvas, View row, float dX, Side side, Drawable icon) {
        float top = row.getTop();
        float bottom = row.getBottom();
        float middle = (top + bottom) / 2f;
        float size = ICON * density;
        float pad = EDGE * density;
        float gap = GAP * density;
        float baseline = middle - (words.descent() + words.ascent()) / 2f;
        fill.setColor(side.color);
        canvas.save();
        if (dX > 0) {
            float edge = row.getLeft();
            canvas.clipRect(edge, top, edge + dX, bottom);
            canvas.drawRect(edge, top, edge + dX, bottom, fill);
            float x = edge + pad;
            drawIcon(canvas, icon, x, middle, size);
            words.setTextAlign(Paint.Align.LEFT);
            canvas.drawText(side.text, x + size + gap, baseline, words);
        } else {
            float edge = row.getRight();
            canvas.clipRect(edge + dX, top, edge, bottom);
            canvas.drawRect(edge + dX, top, edge, bottom, fill);
            float x = edge - pad - size;
            drawIcon(canvas, icon, x, middle, size);
            words.setTextAlign(Paint.Align.RIGHT);
            canvas.drawText(side.text, x - gap, baseline, words);
        }
        canvas.restore();
    }

    private static void drawIcon(Canvas canvas, Drawable icon, float x, float middle, float size) {
        if (icon == null) return;
        icon.setBounds(Math.round(x), Math.round(middle - size / 2f),
                Math.round(x + size), Math.round(middle + size / 2f));
        icon.draw(canvas);
    }

    /** Every gesture as an action TalkBack lists on the row. */
    private void offerActions() {
        list.addOnChildAttachStateChangeListener(new RecyclerView.OnChildAttachStateChangeListener() {
            @Override public void onChildViewAttachedToWindow(View row) {
                if (offered.containsKey(row)) return;
                offered.put(row, Boolean.TRUE);
                if (right != null) ViewCompat.addAccessibilityAction(row, right.text, (v, args) -> act(v, 0));
                if (left != null) ViewCompat.addAccessibilityAction(row, left.text, (v, args) -> act(v, 1));
                if (reorder) {
                    ViewCompat.addAccessibilityAction(row, MOVE_UP, (v, args) -> act(v, 2));
                    ViewCompat.addAccessibilityAction(row, MOVE_DOWN, (v, args) -> act(v, 3));
                }
            }

            @Override public void onChildViewDetachedFromWindow(View row) { }
        });
    }

    private boolean act(View row, int kind) {
        int position = list.getChildAdapterPosition(row);
        if (position == RecyclerView.NO_POSITION) return false;
        if (kind == 0 || kind == 1) {
            listener.onSwiped(position, kind == 0);
            return true;
        }
        int to = kind == 2 ? position - 1 : position + 1;
        if (to < 0 || to >= items.size()) return false;
        move(position, to);
        listener.onDropped(position, to);
        return true;
    }
}
'''


def java_source(package):
    return (JAVA.replace('__PACKAGE__', package)
            .replace('__THRESHOLD__', repr(float(rules.SWIPE_THRESHOLD)))
            .replace('__ICON__', repr(float(rules.ICON_SIZE)))
            .replace('__EDGE__', repr(float(rules.EDGE_PADDING)))
            .replace('__GAP__', repr(float(rules.LABEL_GAP)))
            .replace('__LABEL__', repr(float(rules.LABEL_SIZE)))
            .replace('__SLIDE__', str(int(rules.SLIDE_MS)))
            .replace('__MOVE_UP__', rules.MOVE_UP)
            .replace('__MOVE_DOWN__', rules.MOVE_DOWN))


__all__ = ['CODE', 'refuse', 'uses_gestures', 'parse', 'mark_reorder_positions',
           'emit_setup', 'emit_methods', 'java_source']
