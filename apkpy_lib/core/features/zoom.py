"""The full-screen picture viewer, on the phone.

``image(src, zoom=True)`` puts a click listener on the ImageView that hands
its picture to ``ApkpyZoom``; ``view_image(src)`` hands it a file, a
packaged picture's name or an address. ApkpyZoom is a full-window dialog
that draws the picture itself: a pinch, a double tap and a drag go through
the same arithmetic the Previewer uses (``zoom_rules``), which the class
mirrors one for one -- fit, clampOffset, place, zoomAt, doubleTap,
thumbStart, backdropAlpha.

A picture opened from the screen grows out of its thumbnail and goes back
into it; one opened by name fades in. Back, the cross and a drag down on a
fitted picture close it.

``ApkpyZoom`` is a fixed class, written into the project only when an app
uses it, like ApkpyChoice and ApkpyField.
"""

import ast

from ... import zoom_rules as rules

CODE = rules.CODE
VIEW = 'view_image'


def java_string(value):
    text = str(value or '')
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def _line(node):
    return getattr(node, 'lineno', 0) or 0


def is_view_call(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == VIEW)


def _is_true(node):
    return isinstance(node, ast.Constant) and node.value is True


def uses(tree):
    """Whether the app opens a picture anywhere: the class ships only then."""
    for node in ast.walk(tree):
        if is_view_call(node):
            return True
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'image'
                and any(kw.arg == 'zoom' and _is_true(kw.value) for kw in node.keywords)):
            return True
    return False


def parse_image(transpiler, call, comp, api_type):
    """``zoom=`` on image(): written out as True or False."""
    node = transpiler._kw_node(call.keywords, 'zoom')
    if node is None:
        return
    line = _line(call)
    if not (isinstance(node, ast.Constant) and isinstance(node.value, bool)):
        rules.refuse('zoom= of image() is True or False, written out.',
                     'zoom=%s' % ast.dump(node)[:60], line)
    if not node.value:
        return
    rules.check_image(True, transpiler._kw_node(call.keywords, 'command'),
                      api_type == 'avatar', line)
    if getattr(transpiler, '_row_context', False):
        rules.refuse('zoom=True is for a picture on a screen; a row of a list is drawn '
                     'once for every item.',
                     'image(..., zoom=True) in a row= template', line,
                     ['Give the row\'s picture command=lambda item: view_image(item["photo"]).'])
    comp['zoom'] = True


def parse_call(transpiler, call):
    """``view_image(src, describe=...)`` written as a statement. None for
    anything else."""
    if not is_view_call(call):
        return None
    source = call.args[0] if call.args else transpiler._kw_node(call.keywords, 'src')
    if source is None:
        rules.refuse('view_image() takes the picture to open.', 'view_image()', _line(call))
    if isinstance(source, ast.Constant) and isinstance(source.value, str):
        value = source.value.strip()
        if value.startswith(('http://', 'https://')):
            _needs_internet(transpiler)
        elif value:
            # A picture named here and shown nowhere else still has to be
            # packaged with the app.
            getattr(transpiler, 'set_src_assets', set()).add(value)
    else:
        # Known when the app runs; it may be an address.
        _needs_internet(transpiler)
        if (isinstance(source, ast.Subscript) and isinstance(source.slice, ast.Constant)
                and isinstance(source.slice.value, str)):
            # view_image(item["photo"]): the pictures the app's lists name
            # under that key are packaged, once the whole file is read.
            keys = getattr(transpiler, 'zoom_item_keys', None)
            if keys is None:
                keys = transpiler.zoom_item_keys = set()
            keys.add(source.slice.value)
    describe = call.args[1] if len(call.args) > 1 else transpiler._kw_node(call.keywords, 'describe')
    return {'type': 'view_image', 'src_node': source, 'describe_node': describe}


_PICTURES = ('.png', '.jpg', '.jpeg', '.webp', '.gif')


def package_item_pictures(transpiler):
    """A picture named only inside a list -- {"photo": "harbour.jpg"} -- and
    opened with view_image(item["photo"]) was in nobody's layout, so nothing
    packaged it and the viewer opened on nothing."""
    keys = getattr(transpiler, 'zoom_item_keys', None)
    if not keys:
        return
    assets = getattr(transpiler, 'set_src_assets', None)
    if assets is None:
        return
    for node in (getattr(transpiler, 'list_assignments', {}) or {}).values():
        for row in getattr(node, 'elts', []) or []:
            if not isinstance(row, ast.Dict):
                continue
            for key, value in zip(row.keys, row.values):
                if (isinstance(key, ast.Constant) and key.value in keys
                        and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                    name = value.value.strip()
                    if (name and not name.startswith(('http://', 'https://'))
                            and name.lower().endswith(_PICTURES)):
                        assets.add(name)


def _needs_internet(transpiler):
    permissions = getattr(transpiler, 'declared_permissions', None)
    if permissions is not None and "INTERNET" not in permissions:
        permissions.append("INTERNET")


def click_java(indent, jv, describe):
    """The tap on image(..., zoom=True)."""
    return (f"{indent}{jv}.setOnClickListener(_zoomed -> "
            f"ApkpyZoom.show(this, _zoomed, {java_string(describe)}));")


def _text(java):
    """Words written in the source are already a String."""
    body = java[1:-1]
    literal = (len(java) >= 2 and java[0] == '"' and java[-1] == '"'
               and '"' not in body.replace('\\"', ''))
    return java if literal else 'String.valueOf(%s)' % java


def view_java(activity, source_java, describe_java):
    """view_image(src) inside any method or listener of ``activity``."""
    return (f"ApkpyZoom.show({activity}.this, {_text(source_java)}, "
            f"{_text(describe_java)});")


JAVA = r'''package __PACKAGE__;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.ValueAnimator;
import android.app.Activity;
import android.app.Dialog;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.drawable.BitmapDrawable;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.util.TypedValue;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.view.animation.DecelerateInterpolator;
import android.widget.FrameLayout;
import android.widget.ImageView;

/**
 * A picture over the whole window that can be pinched, double-tapped and
 * dragged. Mirrors apkpy_lib/zoom_rules.py.
 */
public final class ApkpyZoom extends FrameLayout {
    static final float MIN_ZOOM = __MIN_ZOOM__f;
    static final float MAX_ZOOM = __MAX_ZOOM__f;
    static final float DOUBLE_TAP = __DOUBLE_TAP__f;
    static final float DISMISS = __DISMISS__f;          // dp
    static final float CLOSE = __CLOSE__f;              // dp
    static final float CLOSE_ICON = __CLOSE_ICON__f;
    static final float CLOSE_INSET = __CLOSE_INSET__f;
    static final long OPEN_MS = __OPEN_MS__L;
    static final long CLOSE_MS = __CLOSE_MS__L;

    interface Ready { void use(Drawable picture); }

    private final Drawable picture;
    private final int imageW, imageH;
    private final View from;
    private final Dialog dialog;
    private final float density;
    private final Paint ink = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final View closeButton;
    private final ScaleGestureDetector pinch;
    private final GestureDetector taps;
    private float zoom = MIN_ZOOM, x, y;    // zoom 1 is fitted; (x, y) is the picture's top left
    private float dragY;                    // how far a fitted picture is pulled down
    private float progress;                 // 0 at the thumbnail, 1 open
    private RectF thumb;                    // the thumbnail, in this view's pixels
    private boolean opened, closing;
    private ValueAnimator animator;

    // ── opening ──────────────────────────────────────────────────────────

    /** A picture already on the screen: it grows from where it is. */
    public static void show(Activity activity, View from, String describe) {
        Drawable shown = from instanceof ImageView ? ((ImageView) from).getDrawable() : null;
        if (shown == null) return;                      // still loading: nothing to open
        Drawable.ConstantState state = shown.getConstantState();
        Drawable own = state != null ? state.newDrawable(activity.getResources()).mutate() : shown;
        open(activity, own, from, describe);
    }

    /** Any picture: an address, a file on the phone or one packaged with the app. */
    public static void show(final Activity activity, String source, final String describe) {
        load(activity, source, new Ready() {
            @Override public void use(Drawable picture) { open(activity, picture, null, describe); }
        });
    }

    private static void open(Activity activity, Drawable picture, View from, String describe) {
        if (picture == null || activity.isFinishing() || activity.isDestroyed()) return;
        // Back closes the viewer the way a tap does: the picture goes home
        // to where it came from. In the dialog's own onBackPressed(), not a
        // listener for the key -- an app that targets Android 16 is no
        // longer sent the key there, and the picture was cut off instead.
        final Runnable[] back = new Runnable[1];
        final Dialog dialog = new Dialog(activity, android.R.style.Theme_Translucent_NoTitleBar) {
            @Override public void onBackPressed() {
                if (back[0] != null) back[0].run();
                else super.onBackPressed();
            }
        };
        final ApkpyZoom viewer = new ApkpyZoom(activity, picture, from, describe, dialog);
        back[0] = new Runnable() {
            @Override public void run() { viewer.close(); }
        };
        dialog.setContentView(viewer, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        Window window = dialog.getWindow();
        if (window != null) {
            window.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
            window.clearFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
            // Under the status bar and the navigation bar: the whole glass.
            window.addFlags(WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                    | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS);
            window.setWindowAnimations(0);
            if (Build.VERSION.SDK_INT >= 28) {
                WindowManager.LayoutParams attrs = window.getAttributes();
                attrs.layoutInDisplayCutoutMode =
                        WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
                window.setAttributes(attrs);
            }
        }
        dialog.show();
    }

    private static void load(final Activity activity, String source, final Ready ready) {
        if (source == null) return;
        final String value = source.trim();
        if (value.isEmpty()) return;
        if (value.startsWith("http://") || value.startsWith("https://")) {
            new Thread(new Runnable() {
                @Override public void run() {
                    java.net.HttpURLConnection conn = null;
                    try {
                        conn = (java.net.HttpURLConnection) new java.net.URL(value).openConnection();
                        conn.setConnectTimeout(10000);
                        conn.setReadTimeout(15000);
                        conn.setInstanceFollowRedirects(true);
                        final Bitmap bitmap = BitmapFactory.decodeStream(conn.getInputStream());
                        if (bitmap == null) return;
                        activity.runOnUiThread(new Runnable() {
                            @Override public void run() {
                                ready.use(new BitmapDrawable(activity.getResources(), bitmap));
                            }
                        });
                    } catch (Exception ignored) {
                    } finally {
                        if (conn != null) conn.disconnect();
                    }
                }
            }).start();
            return;
        }
        java.io.File file = new java.io.File(value);
        if (file.isAbsolute() && file.exists()) {
            BitmapFactory.Options bounds = new BitmapFactory.Options();
            bounds.inJustDecodeBounds = true;
            BitmapFactory.decodeFile(value, bounds);
            int longest = Math.max(bounds.outWidth, bounds.outHeight), sample = 1;
            while (longest / (sample * 2) >= 2048) sample *= 2;
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inSampleSize = sample;
            Bitmap bitmap = BitmapFactory.decodeFile(value, options);
            if (bitmap != null) ready.use(new BitmapDrawable(activity.getResources(), bitmap));
            return;
        }
        // A picture packaged with the app, named as the build named it.
        String name = value.replaceAll(".*[/\\\\]", "").replaceAll("\\.[^.]*$", "")
                .toLowerCase().replaceAll("[^a-z0-9_]", "_");
        if (name.isEmpty()) return;
        if (!Character.isLetter(name.charAt(0))) name = "img_" + name;
        int res = activity.getResources().getIdentifier(name, "drawable", activity.getPackageName());
        if (res == 0) return;
        Drawable packaged = activity.getDrawable(res);
        if (packaged != null) ready.use(packaged);
    }

    private ApkpyZoom(Activity activity, Drawable picture, View from, String describe,
                      Dialog dialog) {
        super(activity);
        this.picture = picture;
        this.from = from;
        this.dialog = dialog;
        this.imageW = Math.max(1, picture.getIntrinsicWidth());
        this.imageH = Math.max(1, picture.getIntrinsicHeight());
        this.density = getResources().getDisplayMetrics().density;
        setWillNotDraw(false);
        setFocusable(true);
        setContentDescription(describe == null || describe.isEmpty() ? "Picture" : describe);
        ink.setColor(Color.WHITE);
        ink.setStyle(Paint.Style.STROKE);
        ink.setStrokeCap(Paint.Cap.ROUND);
        ink.setStrokeWidth(2f * density);

        // The cross is drawn here; this is what a finger and TalkBack reach.
        closeButton = new View(activity);
        closeButton.setContentDescription("Close");
        closeButton.setFocusable(true);
        closeButton.setClickable(true);
        TypedValue ripple = new TypedValue();
        if (activity.getTheme().resolveAttribute(
                android.R.attr.selectableItemBackgroundBorderless, ripple, true)) {
            closeButton.setBackgroundResource(ripple.resourceId);
        }
        closeButton.setOnClickListener(new OnClickListener() {
            @Override public void onClick(View v) { close(); }
        });
        int size = Math.round(CLOSE * density);
        LayoutParams params = new LayoutParams(size, size);
        params.leftMargin = Math.round(CLOSE_INSET * density);
        params.topMargin = topInset() + Math.round(CLOSE_INSET * density);
        addView(closeButton, params);

        pinch = new ScaleGestureDetector(activity, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScale(ScaleGestureDetector d) {
                set(zoomAt(zoom, x, y, d.getFocusX(), d.getFocusY(), d.getScaleFactor(),
                        imageW, imageH, getWidth(), getHeight()));
                dragY = 0f;
                return true;
            }
        });
        taps = new GestureDetector(activity, new GestureDetector.SimpleOnGestureListener() {
            @Override public boolean onDown(MotionEvent e) { return true; }
            @Override public boolean onDoubleTap(MotionEvent e) {
                zoomTo(doubleTap(zoom), e.getX(), e.getY());
                return true;
            }
            @Override public boolean onScroll(MotionEvent a, MotionEvent b, float dx, float dy) {
                if (pinch.isInProgress()) return false;
                if (zoom <= MIN_ZOOM + 0.01f) {
                    dragY = Math.max(0f, dragY - dy);       // a fitted picture is pulled down
                } else {
                    set(place(zoom, x - dx, y - dy, imageW, imageH, getWidth(), getHeight()));
                }
                invalidate();
                return true;
            }
        });
    }

    private int topInset() {
        int id = getResources().getIdentifier("status_bar_height", "dimen", "android");
        return id != 0 ? getResources().getDimensionPixelSize(id) : Math.round(24 * density);
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldW, int oldH) {
        super.onSizeChanged(w, h, oldW, oldH);
        set(place(zoom, x, y, imageW, imageH, w, h));
        if (opened || w == 0 || h == 0) return;
        opened = true;
        if (from != null && from.isShown() && from.getWidth() > 0) {
            int[] there = new int[2], here = new int[2];
            from.getLocationOnScreen(there);
            getLocationOnScreen(here);
            thumb = new RectF(there[0] - here[0], there[1] - here[1],
                    there[0] - here[0] + from.getWidth(), there[1] - here[1] + from.getHeight());
        }
        tween(0f, 1f, OPEN_MS, null);
    }

    // ── zoom_rules, one for one ─────────────────────────────────────────

    /** zoom_rules.fit */
    static float fit(float imageW, float imageH, float viewW, float viewH) {
        if (imageW <= 0 || imageH <= 0 || viewW <= 0 || viewH <= 0) return 0f;
        return Math.min(viewW / imageW, viewH / imageH);
    }

    /** zoom_rules.clamp_zoom */
    static float clampZoom(float zoom) {
        return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom));
    }

    /** zoom_rules.clamp_offset */
    static float clampOffset(float offset, float content, float view) {
        if (content <= view) return (view - content) / 2f;
        return Math.max(view - content, Math.min(0f, offset));
    }

    /** zoom_rules.place: {zoom, x, y} */
    static float[] place(float zoom, float x, float y, float imageW, float imageH,
                         float viewW, float viewH) {
        float legal = clampZoom(zoom);
        float scale = fit(imageW, imageH, viewW, viewH) * legal;
        return new float[]{legal, clampOffset(x, imageW * scale, viewW),
                clampOffset(y, imageH * scale, viewH)};
    }

    /** zoom_rules.zoom_at: {zoom, x, y} */
    static float[] zoomAt(float zoom, float x, float y, float focusX, float focusY, float factor,
                          float imageW, float imageH, float viewW, float viewH) {
        float target = clampZoom(zoom * factor);
        if (zoom <= 0) return place(target, x, y, imageW, imageH, viewW, viewH);
        float ratio = target / zoom;
        return place(target, focusX - (focusX - x) * ratio, focusY - (focusY - y) * ratio,
                imageW, imageH, viewW, viewH);
    }

    /** zoom_rules.double_tap */
    static float doubleTap(float zoom) {
        return zoom < (MIN_ZOOM + DOUBLE_TAP) / 2f ? DOUBLE_TAP : MIN_ZOOM;
    }

    /** zoom_rules.backdrop_alpha */
    static float backdropAlpha(float dragY, float viewH) {
        if (viewH <= 0) return 1f;
        return Math.max(0f, 1f - Math.max(0f, dragY) / (viewH * 0.75f));
    }

    /** zoom_rules.thumb_start: {scale, x, y}, the scale absolute */
    static float[] thumbStart(float thumbX, float thumbY, float thumbW, float thumbH,
                              float imageW, float imageH, float viewW, float viewH) {
        if (imageW <= 0 || imageH <= 0 || thumbW <= 0 || thumbH <= 0) {
            float scale = fit(imageW, imageH, viewW, viewH);
            return new float[]{scale, clampOffset(0, imageW * scale, viewW),
                    clampOffset(0, imageH * scale, viewH)};
        }
        float scale = Math.max(thumbW / imageW, thumbH / imageH);
        return new float[]{scale, thumbX + (thumbW - imageW * scale) / 2f,
                thumbY + (thumbH - imageH * scale) / 2f};
    }

    // ── the picture ─────────────────────────────────────────────────────

    private void set(float[] state) {
        zoom = state[0];
        x = state[1];
        y = state[2];
        invalidate();
    }

    private void zoomTo(final float target, final float focusX, final float focusY) {
        stop();
        animator = ValueAnimator.ofFloat(zoom, target);
        animator.setDuration(CLOSE_MS);
        animator.setInterpolator(new DecelerateInterpolator());
        animator.addUpdateListener(new ValueAnimator.AnimatorUpdateListener() {
            @Override public void onAnimationUpdate(ValueAnimator a) {
                float next = (Float) a.getAnimatedValue();
                set(zoomAt(zoom, x, y, focusX, focusY, next / zoom,
                        imageW, imageH, getWidth(), getHeight()));
            }
        });
        animator.start();
    }

    private void tween(float start, float end, long ms, final Runnable then) {
        stop();
        progress = start;
        animator = ValueAnimator.ofFloat(start, end);
        animator.setDuration(ms);
        animator.setInterpolator(new DecelerateInterpolator());
        animator.addUpdateListener(new ValueAnimator.AnimatorUpdateListener() {
            @Override public void onAnimationUpdate(ValueAnimator a) {
                progress = (Float) a.getAnimatedValue();
                invalidate();
            }
        });
        if (then != null) {
            animator.addListener(new AnimatorListenerAdapter() {
                @Override public void onAnimationEnd(Animator a) { then.run(); }
            });
        }
        animator.start();
    }

    private void stop() {
        if (animator != null) {
            animator.removeAllListeners();
            animator.cancel();
            animator = null;
        }
    }

    /** Back into the thumbnail when there is one; otherwise it fades. */
    public void close() {
        if (closing) return;
        closing = true;
        if (thumb != null && (from == null || !from.isShown())) thumb = null;
        tween(progress, 0f, CLOSE_MS, new Runnable() {
            @Override public void run() {
                try {
                    dialog.dismiss();
                } catch (IllegalArgumentException ignored) {
                    // The Activity went away under it.
                }
            }
        });
    }

    @Override
    protected void onDetachedFromWindow() {
        stop();
        super.onDetachedFromWindow();
    }

    private static float between(float a, float b, float t) {
        return a + (b - a) * t;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        float viewW = getWidth(), viewH = getHeight();
        float shown = progress * backdropAlpha(dragY, viewH);
        canvas.drawColor(Color.argb(Math.round(255 * shown), 0, 0, 0));
        float scale = fit(imageW, imageH, viewW, viewH) * zoom;
        if (scale <= 0) return;
        float left = x, top = y + dragY;
        canvas.save();
        if (progress < 1f && thumb != null) {
            float[] start = thumbStart(thumb.left, thumb.top, thumb.width(), thumb.height(),
                    imageW, imageH, viewW, viewH);
            scale = between(start[0], scale, progress);
            left = between(start[1], left, progress);
            top = between(start[2], top, progress);
            canvas.clipRect(between(thumb.left, 0, progress), between(thumb.top, 0, progress),
                    between(thumb.right, viewW, progress), between(thumb.bottom, viewH, progress));
            picture.setAlpha(255);
        } else {
            picture.setAlpha(Math.round(255 * Math.min(1f, progress)));
        }
        canvas.translate(left, top);
        canvas.scale(scale, scale);
        picture.setBounds(0, 0, imageW, imageH);
        picture.draw(canvas);
        canvas.restore();

        // The cross, over the close button's square.
        ink.setAlpha(Math.round(255 * shown));
        float size = CLOSE_ICON * density, inset = size * 0.25f;
        float cx = closeButton.getLeft() + (closeButton.getWidth() - size) / 2f;
        float cy = closeButton.getTop() + (closeButton.getHeight() - size) / 2f;
        canvas.drawLine(cx + inset, cy + inset, cx + size - inset, cy + size - inset, ink);
        canvas.drawLine(cx + inset, cy + size - inset, cx + size - inset, cy + inset, ink);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (closing || progress < 1f) return true;
        pinch.onTouchEvent(event);
        taps.onTouchEvent(event);
        int action = event.getActionMasked();
        if ((action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) && dragY > 0f) {
            if (dragY >= DISMISS * density) {
                close();
            } else {
                final float pulled = dragY;
                stop();
                animator = ValueAnimator.ofFloat(pulled, 0f);
                animator.setDuration(CLOSE_MS);
                animator.addUpdateListener(new ValueAnimator.AnimatorUpdateListener() {
                    @Override public void onAnimationUpdate(ValueAnimator a) {
                        dragY = (Float) a.getAnimatedValue();
                        invalidate();
                    }
                });
                animator.start();
            }
        }
        return true;
    }
}
'''


def java_source(package):
    text = JAVA.replace('__PACKAGE__', package)
    for name, value in (
            ('MIN_ZOOM', rules.MIN_ZOOM), ('MAX_ZOOM', rules.MAX_ZOOM),
            ('DOUBLE_TAP', rules.DOUBLE_TAP), ('DISMISS', float(rules.DISMISS)),
            ('CLOSE_ICON', float(rules.CLOSE_ICON)), ('CLOSE_INSET', float(rules.CLOSE_INSET)),
            ('CLOSE', float(rules.CLOSE)),
            ('OPEN_MS', rules.OPEN_MS), ('CLOSE_MS', rules.CLOSE_MS)):
        text = text.replace('__%s__' % name, str(value))
    return text
