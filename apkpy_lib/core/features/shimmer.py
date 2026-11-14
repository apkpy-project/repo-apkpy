"""shimmer, on the phone: ApkpyShimmer, a Drawable on the view's overlay.

A ValueAnimator turns the period; the drawable asks shimmer_rules' question
(where is the band?) in Java, and paints a LinearGradient clipped to the
box's rounded corners.
"""

from ... import shimmer_rules as rules
from .. import gradients

JAVA_FILE = "java/ApkpyShimmer.java"


def setup_java(indent, java_var, value, radius_dp, resolve):
    spec = rules.parse(value)
    if spec is None:
        return []
    period, colour = spec
    argb = gradients.argb(resolve(colour)) or (0x59, 255, 255, 255)
    return ["%sApkpyShimmer.on(findViewById(R.id.%s), 0x%02X%02X%02X%02X, %d, %.1ff);"
            % ((indent, java_var) + tuple(argb) + (period, float(radius_dp)))]


_JAVA = '''package __PACKAGE__;

import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.drawable.Drawable;
import android.os.SystemClock;
import android.view.View;

/** shimmer: a band of light across a box, again and again (shimmer_rules.py).
 *  It asks for the next frame from draw(), so it runs only while the box is
 *  on screen, and sleeps through the rest of each period: an animator ran
 *  120 frames a second for every bar, on screens nobody was looking at. */
final class ApkpyShimmer extends Drawable implements Runnable {
    private static final float SWEEP = __SWEEP__f;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path clip = new Path();
    private final Matrix move = new Matrix();
    private final int colour;
    private final float radius;
    private final long period;
    private final long start = SystemClock.uptimeMillis();

    private ApkpyShimmer(int colour, float radius, long period) {
        this.colour = colour;
        this.radius = radius;
        this.period = Math.max(200, period);
    }

    static void on(final View view, int colour, long period, float radiusDp) {
        if (view == null) return;
        final ApkpyShimmer band = new ApkpyShimmer(colour,
                radiusDp * view.getResources().getDisplayMetrics().density, period);
        view.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, or, ob) -> band.setBounds(0, 0, r - l, b - t));
        band.setBounds(0, 0, view.getWidth(), view.getHeight());
        view.getOverlay().add(band);
    }

    @Override
    protected void onBoundsChange(Rect bounds) {
        int clear = colour & 0x00FFFFFF;
        paint.setShader(new LinearGradient(0, 0, Math.max(1, bounds.width()), 0,
                new int[]{clear, colour, clear}, null, Shader.TileMode.CLAMP));
        clip.reset();
        clip.addRoundRect(new RectF(bounds), radius, radius, Path.Direction.CW);
    }

    @Override public void run() { invalidateSelf(); }

    @Override
    public void draw(Canvas canvas) {
        if (paint.getShader() == null || getBounds().isEmpty()) return;
        long now = SystemClock.uptimeMillis();
        float phase = ((now - start) % period) / (float) period;
        if (phase >= SWEEP) {
            // Resting: one wake-up at the start of the next sweep.
            scheduleSelf(this, now + (long) ((1f - phase) * period));
            return;
        }
        float p = phase / SWEEP;
        p = p * p * (3f - 2f * p);
        float width = getBounds().width();
        move.setTranslate((-1f + 2f * p) * width, 0);
        paint.getShader().setLocalMatrix(move);
        canvas.save();
        canvas.clipPath(clip);
        canvas.drawRect(getBounds(), paint);
        canvas.restore();
        // 60 frames a second is smooth for a band of light; a 120 Hz screen
        // would otherwise draw the box twice as often for nothing.
        scheduleSelf(this, now + 16);
    }

    @Override public void setAlpha(int alpha) {}
    @Override public void setColorFilter(ColorFilter filter) {}
    @Override public int getOpacity() { return PixelFormat.TRANSLUCENT; }
}
'''


def java_source(package):
    return _JAVA.replace("__PACKAGE__", package).replace("__SWEEP__", repr(rules.SWEEP))
