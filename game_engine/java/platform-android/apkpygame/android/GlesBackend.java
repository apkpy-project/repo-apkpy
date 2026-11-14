package apkpygame.android;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.opengl.GLES20;
import android.opengl.GLUtils;

import apkpygame.core.GameException;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderBackend;
import apkpygame.core.render.Texture;
import apkpygame.core.render.View3D;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.util.IdentityHashMap;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Draws the render queue with OpenGL ES 2.0, on the GL thread of a
 * GlGameView. The commands arrive sorted; consecutive ones that use the same
 * texture (and filter) go to the GPU as one batch of triangles. Vertices are
 * transformed on the CPU with each command's matrix, so the result is the
 * same as the Canvas backend's: sprites (tint, alpha, regions), rectangles
 * and circles (filled or outlined), and text (drawn once with Paint into a
 * texture, kept in a small cache).
 *
 * Textures stay android.graphics.Bitmap (Texture.handle), as for the Canvas;
 * they are uploaded when first drawn, and again after the GL context is lost
 * (contextCreated()).
 */
final class GlesBackend implements RenderBackend {
    private static final int FLOATS = 8;                 // x, y, u, v, r, g, b, a (colour premultiplied)
    private static final int MAX_VERTICES = 6 * 4096;
    private static final int CIRCLE_SEGMENTS = 40;
    private static final int TEXT_CACHE = 192;

    private static final String VERTEX = "attribute vec2 aPos; attribute vec2 aUv; attribute vec4 aColor;\n"
            + "uniform vec2 uScale; varying vec2 vUv; varying vec4 vColor;\n"
            + "void main() { vUv = aUv; vColor = aColor;\n"
            + "  gl_Position = vec4(aPos.x * uScale.x - 1.0, 1.0 - aPos.y * uScale.y, 0.0, 1.0); }\n";
    private static final String FRAGMENT = "precision mediump float; uniform sampler2D uTex;\n"
            + "varying vec2 vUv; varying vec4 vColor;\n"
            + "void main() { gl_FragColor = texture2D(uTex, vUv) * vColor; }\n";

    // 2.5D (QUAD3D): world positions through the camera, depth test, cutout by discard, fog per vertex
    private static final int FLOATS_3D = 10;             // x, y, z, u, v, r, g, b, a, fog
    private static final String VERTEX_3D = "attribute vec3 aPos; attribute vec2 aUv; attribute vec4 aColor;\n"
            + "attribute float aFog; uniform mat4 uMvp; varying vec2 vUv; varying vec4 vColor; varying float vFog;\n"
            + "void main() { vUv = aUv; vColor = aColor; vFog = aFog; gl_Position = uMvp * vec4(aPos, 1.0); }\n";
    private static final String FRAGMENT_3D = "precision mediump float; uniform sampler2D uTex;\n"
            + "uniform float uCutout; uniform vec4 uFog; varying vec2 vUv; varying vec4 vColor; varying float vFog;\n"
            + "void main() { vec4 t = texture2D(uTex, vUv);\n"
            + "  if (uCutout > 0.5 && t.a < 0.5) discard;\n"
            + "  vec4 c = t * vColor; c.rgb = mix(c.rgb, uFog.rgb * c.a, vFog); gl_FragColor = c; }\n";

    private final CanvasBackend decoder;
    private final float[] vertices = new float[MAX_VERTICES * FLOATS];
    private final FloatBuffer buffer = ByteBuffer.allocateDirect(vertices.length * 4)
            .order(ByteOrder.nativeOrder()).asFloatBuffer();
    private int count;
    private int program, aPos, aUv, aColor, uScale, uTex;
    private int program3d, aPos3, aUv3, aColor3, aFog3, uMvp3, uTex3, uCutout3, uFog3;
    private final float[] vertices3d = new float[MAX_VERTICES * FLOATS_3D];
    private final FloatBuffer buffer3d = ByteBuffer.allocateDirect(vertices3d.length * 4)
            .order(ByteOrder.nativeOrder()).asFloatBuffer();
    private final float[] mvp = new float[16];
    private boolean mode3d, cutout3d;
    private apkpygame.core.render.View3D view3d;
    private int white;
    private int boundTexture = -1;
    private boolean boundSmooth;
    private int width, height;

    /** GL texture ids of bitmaps, and their current filter (true = linear); empty after a context loss. */
    private final Map<Bitmap, int[]> textures = new IdentityHashMap<Bitmap, int[]>();
    private final LinkedHashMap<String, TextTexture> texts = new LinkedHashMap<String, TextTexture>(64, 0.75f, true);
    private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);

    private static final class TextTexture {
        int id;
        float width, height, ascent;       // in texture pixels; ascent < 0
    }

    GlesBackend(CanvasBackend decoder) {
        this.decoder = decoder;
        textPaint.setColor(0xFFFFFFFF);
    }

    /** A new GL context (the first one, or after the old one was lost): everything is made again. */
    void contextCreated() {
        textures.clear();
        texts.clear();
        program = link(compile(GLES20.GL_VERTEX_SHADER, VERTEX), compile(GLES20.GL_FRAGMENT_SHADER, FRAGMENT));
        aPos = GLES20.glGetAttribLocation(program, "aPos");
        aUv = GLES20.glGetAttribLocation(program, "aUv");
        aColor = GLES20.glGetAttribLocation(program, "aColor");
        uScale = GLES20.glGetUniformLocation(program, "uScale");
        uTex = GLES20.glGetUniformLocation(program, "uTex");
        program3d = link(compile(GLES20.GL_VERTEX_SHADER, VERTEX_3D), compile(GLES20.GL_FRAGMENT_SHADER, FRAGMENT_3D));
        aPos3 = GLES20.glGetAttribLocation(program3d, "aPos");
        aUv3 = GLES20.glGetAttribLocation(program3d, "aUv");
        aColor3 = GLES20.glGetAttribLocation(program3d, "aColor");
        aFog3 = GLES20.glGetAttribLocation(program3d, "aFog");
        uMvp3 = GLES20.glGetUniformLocation(program3d, "uMvp");
        uTex3 = GLES20.glGetUniformLocation(program3d, "uTex");
        uCutout3 = GLES20.glGetUniformLocation(program3d, "uCutout");
        uFog3 = GLES20.glGetUniformLocation(program3d, "uFog");
        Bitmap one = Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888);
        one.eraseColor(0xFFFFFFFF);
        white = upload(one, false);
        one.recycle();
        boundTexture = -1;
    }

    @Override public Texture loadTexture(String path, byte[] data) {
        return decoder.loadTexture(path, data);         // a Bitmap, uploaded when first drawn
    }

    @Override public Object loadFont(String path, byte[] data) {
        return Fonts.typeface(data);
    }

    @Override public void begin(int surfaceWidth, int surfaceHeight, int clearColor) {
        width = surfaceWidth;
        height = surfaceHeight;
        GLES20.glViewport(0, 0, surfaceWidth, surfaceHeight);
        GLES20.glClearColor(((clearColor >> 16) & 255) / 255f, ((clearColor >> 8) & 255) / 255f,
                (clearColor & 255) / 255f, 1f);
        GLES20.glDepthMask(true);
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT | GLES20.GL_DEPTH_BUFFER_BIT);
        GLES20.glDisable(GLES20.GL_DEPTH_TEST);
        GLES20.glDisable(GLES20.GL_CULL_FACE);
        mode3d = false;
        view3d = null;
        GLES20.glEnable(GLES20.GL_BLEND);
        GLES20.glBlendFunc(GLES20.GL_ONE, GLES20.GL_ONE_MINUS_SRC_ALPHA);     // premultiplied alpha
        GLES20.glUseProgram(program);
        GLES20.glUniform2f(uScale, 2f / surfaceWidth, 2f / surfaceHeight);
        GLES20.glUniform1i(uTex, 0);
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
        boundTexture = -1;
        count = 0;
    }

    @Override public void draw(DrawCommand c) {
        if (c.kind == DrawCommand.Kind.QUAD3D) {
            quad3d(c);
            return;
        }
        if (mode3d) leave3d();
        scissor(c);
        switch (c.kind) {
            case SPRITE: {
                Bitmap bitmap = c.texture.pixels != null ? painted(c.texture) : (Bitmap) c.texture.handle;
                use(texture(bitmap), c.smooth);
                float tw = bitmap.getWidth(), th = bitmap.getHeight();
                float a = (float) Math.max(0, Math.min(1, c.alpha));
                quad(c.matrix, c.x, c.y, c.w, c.h, c.srcX / tw, c.srcY / th, (c.srcX + c.srcW) / tw,
                        (c.srcY + c.srcH) / th, c.color, a);
                break;
            }
            case RECT:
                use(white, false);
                if (c.filled) {
                    quad(c.matrix, c.x, c.y, c.w, c.h, 0, 0, 1, 1, c.color, 1);
                } else {
                    double s = c.stroke, h = s / 2;
                    quad(c.matrix, c.x - h, c.y - h, c.w + s, s, 0, 0, 1, 1, c.color, 1);
                    quad(c.matrix, c.x - h, c.y + c.h - h, c.w + s, s, 0, 0, 1, 1, c.color, 1);
                    quad(c.matrix, c.x - h, c.y + h, s, c.h - s, 0, 0, 1, 1, c.color, 1);
                    quad(c.matrix, c.x + c.w - h, c.y + h, s, c.h - s, 0, 0, 1, 1, c.color, 1);
                }
                break;
            case CIRCLE:
                use(white, false);
                circle(c);
                break;
            case TEXT:
                text(c);
                break;
            default:
                break;
        }
    }

    private boolean scissorOn;
    private int scissorX, scissorY, scissorW, scissorH;

    /** The batch ends where the clipping changes. GL counts from the bottom of the surface. */
    private void scissor(DrawCommand c) {
        if (c.clipping == scissorOn && (!c.clipping || (c.clipX == scissorX && c.clipY == scissorY
                && c.clipW == scissorW && c.clipH == scissorH))) return;
        flush();
        scissorOn = c.clipping;
        scissorX = c.clipX;
        scissorY = c.clipY;
        scissorW = c.clipW;
        scissorH = c.clipH;
        if (scissorOn) {
            GLES20.glEnable(GLES20.GL_SCISSOR_TEST);
            GLES20.glScissor(scissorX, height - scissorY - scissorH, scissorW, scissorH);
        } else {
            GLES20.glDisable(GLES20.GL_SCISSOR_TEST);
        }
    }

    @Override public void end() {
        flush();
        if (scissorOn) {
            scissorOn = false;
            GLES20.glDisable(GLES20.GL_SCISSOR_TEST);
        }
        if (mode3d) leave3d();
    }

    // ── 2.5D ─────────────────────────────────────────────────────────────

    private void quad3d(DrawCommand c) {
        if (!mode3d || c.view3d != view3d) enter3d(c.view3d);
        if (c.cutout != cutout3d) {
            flush();
            cutout3d = c.cutout;
            GLES20.glUniform1f(uCutout3, cutout3d ? 1f : 0f);
            GLES20.glDepthMask(cutout3d);                   // see-through quads do not hide what is behind
        }
        int id = c.texture == null ? white : texture((Bitmap) c.texture.handle);
        use(id, c.smooth && c.texture != null);
        if (count + 6 > MAX_VERTICES) flush();
        int argb = c.color;
        float a = ((argb >>> 24) / 255f) * (float) Math.max(0, Math.min(1, c.alpha));
        float r = ((argb >> 16) & 255) / 255f * a, g = ((argb >> 8) & 255) / 255f * a, b = (argb & 255) / 255f * a;
        View3D v = c.view3d;
        boolean fog = v.fogEnd > v.fogStart;
        int[] order = {0, 1, 2, 0, 2, 3};
        for (int k : order) {
            double x = c.xyz[k * 3], y = c.xyz[k * 3 + 1], z = c.xyz[k * 3 + 2];
            float f = 0;
            if (fog) {
                double dx = x - v.eyeX, dy = y - v.eyeY, dz = z - v.eyeZ;
                double t = (Math.sqrt(dx * dx + dy * dy + dz * dz) - v.fogStart) / (v.fogEnd - v.fogStart);
                f = (float) (t < 0 ? 0 : t > 1 ? 1 : t);
            }
            int i = count * FLOATS_3D;
            vertices3d[i] = (float) x;
            vertices3d[i + 1] = (float) y;
            vertices3d[i + 2] = (float) z;
            vertices3d[i + 3] = (float) c.uv[k * 2];
            vertices3d[i + 4] = (float) c.uv[k * 2 + 1];
            vertices3d[i + 5] = r;
            vertices3d[i + 6] = g;
            vertices3d[i + 7] = b;
            vertices3d[i + 8] = a;
            vertices3d[i + 9] = f;
            count++;
        }
    }

    private void enter3d(View3D v) {
        flush();
        mode3d = true;
        view3d = v;
        GLES20.glUseProgram(program3d);
        for (int i = 0; i < 16; i++) mvp[i] = (float) v.viewProjection.m[i];
        GLES20.glUniformMatrix4fv(uMvp3, 1, false, mvp, 0);
        GLES20.glUniform1i(uTex3, 0);
        int fc = v.fogColor;
        GLES20.glUniform4f(uFog3, ((fc >> 16) & 255) / 255f, ((fc >> 8) & 255) / 255f, (fc & 255) / 255f, 1f);
        cutout3d = true;
        GLES20.glUniform1f(uCutout3, 1f);
        GLES20.glDepthMask(true);
        GLES20.glEnable(GLES20.GL_DEPTH_TEST);
        GLES20.glDepthFunc(GLES20.GL_LESS);
        // the game area of the surface (GL counts y from the bottom)
        GLES20.glViewport((int) Math.round(v.x), (int) Math.round(height - v.y - v.height),
                (int) Math.round(v.width), (int) Math.round(v.height));
        boundTexture = -1;
    }

    private void leave3d() {
        flush();
        mode3d = false;
        view3d = null;
        GLES20.glDisable(GLES20.GL_DEPTH_TEST);
        GLES20.glDepthMask(true);
        GLES20.glUseProgram(program);
        GLES20.glViewport(0, 0, width, height);
        boundTexture = -1;
    }

    // ── geometry ─────────────────────────────────────────────────────────

    private void quad(Mat3 m, double x, double y, double w, double h, float u0, float v0, float u1, float v1,
                      int argb, float alpha) {
        reserve(6);
        float a = ((argb >>> 24) / 255f) * alpha;
        float r = ((argb >> 16) & 255) / 255f * a, g = ((argb >> 8) & 255) / 255f * a, b = (argb & 255) / 255f * a;
        double x1 = x + w, y1 = y + h;
        float ax = (float) m.mapX(x, y), ay = (float) m.mapY(x, y);
        float bx = (float) m.mapX(x1, y), by = (float) m.mapY(x1, y);
        float cx = (float) m.mapX(x1, y1), cy = (float) m.mapY(x1, y1);
        float dx = (float) m.mapX(x, y1), dy = (float) m.mapY(x, y1);
        vertex(ax, ay, u0, v0, r, g, b, a);
        vertex(bx, by, u1, v0, r, g, b, a);
        vertex(cx, cy, u1, v1, r, g, b, a);
        vertex(ax, ay, u0, v0, r, g, b, a);
        vertex(cx, cy, u1, v1, r, g, b, a);
        vertex(dx, dy, u0, v1, r, g, b, a);
    }

    private void circle(DrawCommand c) {
        int argb = c.color;
        float a = (argb >>> 24) / 255f;
        float r = ((argb >> 16) & 255) / 255f * a, g = ((argb >> 8) & 255) / 255f * a, b = (argb & 255) / 255f * a;
        double cx = c.x + c.w / 2, cy = c.y + c.h / 2, rx = c.w / 2, ry = c.h / 2;
        double inner = c.filled ? 0 : 1 - c.stroke / Math.max(1e-9, Math.min(rx, ry)) / 2;
        double outer = c.filled ? 1 : 1 + c.stroke / Math.max(1e-9, Math.min(rx, ry)) / 2;
        Mat3 m = c.matrix;
        for (int i = 0; i < CIRCLE_SEGMENTS; i++) {
            double t0 = 2 * Math.PI * i / CIRCLE_SEGMENTS, t1 = 2 * Math.PI * (i + 1) / CIRCLE_SEGMENTS;
            double ox0 = cx + Math.cos(t0) * rx * outer, oy0 = cy + Math.sin(t0) * ry * outer;
            double ox1 = cx + Math.cos(t1) * rx * outer, oy1 = cy + Math.sin(t1) * ry * outer;
            double ix0 = cx + Math.cos(t0) * rx * inner, iy0 = cy + Math.sin(t0) * ry * inner;
            double ix1 = cx + Math.cos(t1) * rx * inner, iy1 = cy + Math.sin(t1) * ry * inner;
            reserve(6);
            vertex((float) m.mapX(ix0, iy0), (float) m.mapY(ix0, iy0), 0, 0, r, g, b, a);
            vertex((float) m.mapX(ox0, oy0), (float) m.mapY(ox0, oy0), 0, 0, r, g, b, a);
            vertex((float) m.mapX(ox1, oy1), (float) m.mapY(ox1, oy1), 0, 0, r, g, b, a);
            vertex((float) m.mapX(ix0, iy0), (float) m.mapY(ix0, iy0), 0, 0, r, g, b, a);
            vertex((float) m.mapX(ox1, oy1), (float) m.mapY(ox1, oy1), 0, 0, r, g, b, a);
            vertex((float) m.mapX(ix1, iy1), (float) m.mapY(ix1, iy1), 0, 0, r, g, b, a);
        }
    }

    /** Text: rasterised once per (text, size on screen) into a texture, white; the colour comes from the vertices. */
    private void text(DrawCommand c) {
        if (c.text == null || c.text.isEmpty()) return;
        Mat3 m = c.matrix;
        double scale = Math.max(0.05, Math.sqrt(m.a * m.a + m.b * m.b));
        float px = Math.max(1, Math.round(c.size * scale * 2) / 2f);            // pixels on screen, half steps
        String key = (c.face == null ? "" : System.identityHashCode(c.face) + "/") + px + "|" + c.text;
        TextTexture t = texts.get(key);
        if (t == null) {
            t = makeText(c.text, px, c.face);
            texts.put(key, t);
            evictTexts();
        }
        use(t.id, true);
        double unit = c.size / px;                       // local units per texture pixel
        double w = t.width * unit, h = t.height * unit;
        double left = c.align < 0 ? c.x : c.align == 0 ? c.x - w / 2 : c.x - w;
        quad(m, left, c.y + t.ascent * unit, w, h, 0, 0, 1, 1, c.color, 1);
    }

    private TextTexture makeText(String text, float px, Object face) {
        textPaint.setTypeface((android.graphics.Typeface) face);
        textPaint.setTextSize(px);
        Paint.FontMetrics fm = textPaint.getFontMetrics();
        int w = Math.max(1, (int) Math.ceil(textPaint.measureText(text)) + 2);
        int h = Math.max(1, (int) Math.ceil(fm.descent - fm.ascent) + 2);
        Bitmap bitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        new Canvas(bitmap).drawText(text, 1, 1 - fm.ascent, textPaint);
        TextTexture t = new TextTexture();
        t.id = upload(bitmap, true);
        bitmap.recycle();
        t.width = w;
        t.height = h;
        t.ascent = fm.ascent - 1;                       // the baseline is this far below the top (negative)
        return t;
    }

    private void evictTexts() {
        if (texts.size() <= TEXT_CACHE) return;
        flush();
        Iterator<Map.Entry<String, TextTexture>> it = texts.entrySet().iterator();
        while (texts.size() > TEXT_CACHE * 3 / 4 && it.hasNext()) {
            int id = it.next().getValue().id;
            GLES20.glDeleteTextures(1, new int[]{id}, 0);
            if (boundTexture == id) boundTexture = -1;
            it.remove();
        }
    }

    // ── batching ─────────────────────────────────────────────────────────

    private void vertex(float x, float y, float u, float v, float r, float g, float b, float a) {
        int i = count * FLOATS;
        vertices[i] = x;
        vertices[i + 1] = y;
        vertices[i + 2] = u;
        vertices[i + 3] = v;
        vertices[i + 4] = r;
        vertices[i + 5] = g;
        vertices[i + 6] = b;
        vertices[i + 7] = a;
        count++;
    }

    private void reserve(int n) {
        if (count + n > MAX_VERTICES) flush();
    }

    /** Draw with this texture: a change of texture or filter ends the batch. */
    private void use(int id, boolean smooth) {
        if (id == boundTexture && smooth == boundSmooth) return;
        flush();
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, id);
        int filter = smooth ? GLES20.GL_LINEAR : GLES20.GL_NEAREST;
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MIN_FILTER, filter);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MAG_FILTER, filter);
        boundTexture = id;
        boundSmooth = smooth;
    }

    private void flush() {
        if (count == 0) return;
        if (mode3d) {
            buffer3d.clear();
            buffer3d.put(vertices3d, 0, count * FLOATS_3D);
            int stride3 = FLOATS_3D * 4;
            buffer3d.position(0);
            GLES20.glVertexAttribPointer(aPos3, 3, GLES20.GL_FLOAT, false, stride3, buffer3d);
            GLES20.glEnableVertexAttribArray(aPos3);
            buffer3d.position(3);
            GLES20.glVertexAttribPointer(aUv3, 2, GLES20.GL_FLOAT, false, stride3, buffer3d);
            GLES20.glEnableVertexAttribArray(aUv3);
            buffer3d.position(5);
            GLES20.glVertexAttribPointer(aColor3, 4, GLES20.GL_FLOAT, false, stride3, buffer3d);
            GLES20.glEnableVertexAttribArray(aColor3);
            buffer3d.position(9);
            GLES20.glVertexAttribPointer(aFog3, 1, GLES20.GL_FLOAT, false, stride3, buffer3d);
            GLES20.glEnableVertexAttribArray(aFog3);
            GLES20.glDrawArrays(GLES20.GL_TRIANGLES, 0, count);
            count = 0;
            return;
        }
        buffer.clear();
        buffer.put(vertices, 0, count * FLOATS);
        int stride = FLOATS * 4;
        buffer.position(0);
        GLES20.glVertexAttribPointer(aPos, 2, GLES20.GL_FLOAT, false, stride, buffer);
        GLES20.glEnableVertexAttribArray(aPos);
        buffer.position(2);
        GLES20.glVertexAttribPointer(aUv, 2, GLES20.GL_FLOAT, false, stride, buffer);
        GLES20.glEnableVertexAttribArray(aUv);
        buffer.position(4);
        GLES20.glVertexAttribPointer(aColor, 4, GLES20.GL_FLOAT, false, stride, buffer);
        GLES20.glEnableVertexAttribArray(aColor);
        GLES20.glDrawArrays(GLES20.GL_TRIANGLES, 0, count);
        count = 0;
    }

    // ── GL objects ───────────────────────────────────────────────────────

    /**
     * A Canvas: its Bitmap (CanvasBackend.painted), and when the game painted since the last upload, the GL
     * texture made from it gets the new pixels (one texSubImage2D; the pending batch is drawn first).
     */
    private Bitmap painted(Texture t) {
        int before = t.liveVersion;
        Bitmap bitmap = CanvasBackend.painted(t);
        int[] id = textures.get(bitmap);
        if (id != null && before != t.liveVersion) {
            flush();
            GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, id[0]);
            GLUtils.texSubImage2D(GLES20.GL_TEXTURE_2D, 0, 0, 0, bitmap);
            boundTexture = -1;
        }
        return bitmap;
    }

    private int texture(Bitmap bitmap) {
        int[] t = textures.get(bitmap);
        if (t == null) {
            t = new int[]{upload(bitmap, true)};
            textures.put(bitmap, t);
        }
        return t[0];
    }

    /** A new GL texture. It binds it, so the pending batch is drawn first (with the texture it was meant for). */
    private int upload(Bitmap bitmap, boolean smooth) {
        flush();
        boundTexture = -1;
        int[] id = new int[1];
        GLES20.glGenTextures(1, id, 0);
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D, id[0]);
        int filter = smooth ? GLES20.GL_LINEAR : GLES20.GL_NEAREST;
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MIN_FILTER, filter);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_MAG_FILTER, filter);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
        GLUtils.texImage2D(GLES20.GL_TEXTURE_2D, 0, bitmap, 0);           // premultiplied, as the blend expects
        return id[0];
    }

    private static int compile(int type, String source) {
        int shader = GLES20.glCreateShader(type);
        GLES20.glShaderSource(shader, source);
        GLES20.glCompileShader(shader);
        int[] ok = new int[1];
        GLES20.glGetShaderiv(shader, GLES20.GL_COMPILE_STATUS, ok, 0);
        if (ok[0] == 0) {
            throw new GameException("G3040", "OpenGL ES shader: " + GLES20.glGetShaderInfoLog(shader),
                    "Use Game(renderer=\"canvas\") on this device.");
        }
        return shader;
    }

    private static int link(int vertex, int fragment) {
        int p = GLES20.glCreateProgram();
        GLES20.glAttachShader(p, vertex);
        GLES20.glAttachShader(p, fragment);
        GLES20.glLinkProgram(p);
        int[] ok = new int[1];
        GLES20.glGetProgramiv(p, GLES20.GL_LINK_STATUS, ok, 0);
        if (ok[0] == 0) {
            throw new GameException("G3040", "OpenGL ES program: " + GLES20.glGetProgramInfoLog(p),
                    "Use Game(renderer=\"canvas\") on this device.");
        }
        return p;
    }
}
