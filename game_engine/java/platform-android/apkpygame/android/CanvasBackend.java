package apkpygame.android;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.PorterDuff;
import android.graphics.PorterDuffColorFilter;
import android.graphics.Rect;
import android.graphics.RectF;

import apkpygame.core.GameException;
import apkpygame.core.math.Color;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderBackend;
import apkpygame.core.render.Texture;

/** Draws the render queue on a hardware-accelerated android.graphics.Canvas. */
final class CanvasBackend implements RenderBackend {
    private Canvas canvas;
    private final Matrix matrix = new Matrix();
    private final float[] values = new float[9];
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Rect src = new Rect();
    private final RectF dst = new RectF();
    private int lastTint = Color.WHITE;
    private final java.util.HashMap<Integer, PorterDuffColorFilter> filters =
            new java.util.HashMap<Integer, PorterDuffColorFilter>();

    void setCanvas(Canvas canvas) {
        this.canvas = canvas;
    }

    @Override public Texture loadTexture(String path, byte[] data) {
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inScaled = false;
        Bitmap bitmap = BitmapFactory.decodeByteArray(data, 0, data.length, options);
        if (bitmap == null) {
            throw new GameException("G3022", "'" + path + "' is not an image Android can read",
                    "Use PNG, JPEG or WebP.");
        }
        return new Texture(path, bitmap.getWidth(), bitmap.getHeight(), bitmap);
    }

    @Override public Object loadFont(String path, byte[] data) {
        return Fonts.typeface(data);
    }

    @Override public void begin(int surfaceWidth, int surfaceHeight, int clearColor) {
        canvas.drawColor(clearColor);
    }

    @Override public void draw(DrawCommand c) {
        if (c.kind == DrawCommand.Kind.QUAD3D) {
            throw new GameException("G3041", "a 2.5D scene needs OpenGL ES, and this game is drawn with the Canvas",
                    "Use Game(renderer=\"auto\") or Game(renderer=\"gles\").");
        }
        values[0] = (float) c.matrix.a;
        values[1] = (float) c.matrix.c;
        values[2] = (float) c.matrix.tx;
        values[3] = (float) c.matrix.b;
        values[4] = (float) c.matrix.d;
        values[5] = (float) c.matrix.ty;
        values[6] = 0;
        values[7] = 0;
        values[8] = 1;
        matrix.setValues(values);
        canvas.save();
        if (c.clipping) canvas.clipRect(c.clipX, c.clipY, c.clipX + c.clipW, c.clipY + c.clipH);
        canvas.concat(matrix);
        dst.set((float) c.x, (float) c.y, (float) (c.x + c.w), (float) (c.y + c.h));
        switch (c.kind) {
            case SPRITE:
                paint.setStyle(Paint.Style.FILL);
                paint.setColor(0xFFFFFFFF);
                paint.setAlpha((int) Math.round(255 * Math.max(0, Math.min(1, c.alpha))));
                paint.setFilterBitmap(c.smooth);
                if (c.color != lastTint) {
                    lastTint = c.color;
                    paint.setColorFilter(c.color == Color.WHITE ? null : filter(c.color));
                }
                src.set(c.srcX, c.srcY, c.srcX + c.srcW, c.srcY + c.srcH);
                canvas.drawBitmap(c.texture.pixels != null ? painted(c.texture) : (Bitmap) c.texture.handle,
                        src, dst, paint);
                break;
            case RECT:
            case CIRCLE:
                plain(c);
                if (c.kind == DrawCommand.Kind.RECT) canvas.drawRect(dst, paint);
                else canvas.drawOval(dst, paint);
                break;
            case TEXT:
                plain(c);
                paint.setStyle(Paint.Style.FILL);
                paint.setTypeface((android.graphics.Typeface) c.face);
                paint.setTextSize((float) c.size);
                paint.setTextAlign(c.align < 0 ? Paint.Align.LEFT : c.align == 0 ? Paint.Align.CENTER
                        : Paint.Align.RIGHT);
                canvas.drawText(c.text, (float) c.x, (float) c.y, paint);
                break;
            default:
                break;
        }
        canvas.restore();
    }

    /** A Canvas's pixels as a Bitmap of its own, copied again only when the game painted since. */
    static Bitmap painted(Texture t) {
        Bitmap b = (Bitmap) t.live;
        if (b == null) {
            b = Bitmap.createBitmap(t.width, t.height, Bitmap.Config.ARGB_8888);
            t.live = b;
            t.liveVersion = -1;
        }
        if (t.liveVersion != t.version) {
            b.setPixels(t.pixels, 0, t.width, 0, 0, t.width, t.height);
            t.liveVersion = t.version;
        }
        return b;
    }

    /** One filter per tint colour, made once (a new one per sprite cost ~20% at 2000 sprites). */
    private PorterDuffColorFilter filter(int color) {
        PorterDuffColorFilter f = filters.get(color);
        if (f == null) {
            f = new PorterDuffColorFilter(color, PorterDuff.Mode.MULTIPLY);
            filters.put(color, f);
        }
        return f;
    }

    private void plain(DrawCommand c) {
        if (lastTint != Color.WHITE) {
            lastTint = Color.WHITE;
            paint.setColorFilter(null);
        }
        paint.setColor(c.color);
        paint.setStyle(c.filled ? Paint.Style.FILL : Paint.Style.STROKE);
        paint.setStrokeWidth((float) c.stroke);
    }

    @Override public void end() {
        canvas = null;
    }
}
