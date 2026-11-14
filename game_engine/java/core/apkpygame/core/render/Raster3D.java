package apkpygame.core.render;

/**
 * A software rasterizer for QUAD3D commands, in plain Java: what the desktop
 * (the Previewer, `apkpygame play`, screenshots) uses for 2.5D scenes, where
 * the phone uses OpenGL ES. Same rules as the GLES backend: a depth buffer,
 * perspective-correct texture coordinates, nearest or linear sampling,
 * cutout (texels under half alpha are skipped), see-through quads blended
 * without writing depth, per-vertex fog. Triangles are clipped against the
 * near plane, so ground quads under the camera are not lost.
 *
 * <p>It draws into its own ARGB buffer the size of the surface; the backend
 * then lays that image under the 2D commands that come after (UI). Measured
 * (measured): ~280 frames per second for 1 000 quads at
 * 411x914 on the development PC.
 */
public final class Raster3D {
    private int width, height;
    private int[] color = new int[0];
    private float[] depth = new float[0];
    private boolean used;
    private final double[] clip = new double[4 * 7];          // 4 corners: x, y, z, w, u, v, fog
    private final double[] poly = new double[8 * 7], next = new double[8 * 7];
    private final double[] screen = new double[8 * 7];        // sx, sy, z, 1/w, u/w, v/w, fog/w

    /** A new frame on a surface of this size. Nothing is cleared until a quad comes. */
    public void begin(int surfaceWidth, int surfaceHeight) {
        if (surfaceWidth != width || surfaceHeight != height) {
            width = Math.max(1, surfaceWidth);
            height = Math.max(1, surfaceHeight);
            color = new int[width * height];
            depth = new float[width * height];
        }
        used = false;
    }

    /** Whether any quad was drawn this frame (else there is nothing to lay on the surface). */
    public boolean used() {
        return used;
    }

    /** ARGB, premultiplied by nothing: transparent where no quad was drawn. */
    public int[] pixels() {
        return color;
    }

    public int width() {
        return width;
    }

    public int height() {
        return height;
    }

    /**
     * Draws one QUAD3D. {@code texels} is the texture as ARGB (null for a plain colour), {@code tw} x {@code th}.
     */
    public void quad(DrawCommand c, int[] texels, int tw, int th) {
        if (!used) {
            java.util.Arrays.fill(color, 0);
            java.util.Arrays.fill(depth, Float.POSITIVE_INFINITY);
            used = true;
        }
        View3D v = c.view3d;
        double[] m = v.viewProjection.m;
        boolean fog = v.fogEnd > v.fogStart;
        for (int i = 0; i < 4; i++) {
            double x = c.xyz[i * 3], y = c.xyz[i * 3 + 1], z = c.xyz[i * 3 + 2];
            int o = i * 7;
            clip[o] = m[0] * x + m[4] * y + m[8] * z + m[12];
            clip[o + 1] = m[1] * x + m[5] * y + m[9] * z + m[13];
            clip[o + 2] = m[2] * x + m[6] * y + m[10] * z + m[14];
            clip[o + 3] = m[3] * x + m[7] * y + m[11] * z + m[15];
            clip[o + 4] = c.uv[i * 2];
            clip[o + 5] = c.uv[i * 2 + 1];
            double f = 0;
            if (fog) {
                double dx = x - v.eyeX, dy = y - v.eyeY, dz = z - v.eyeZ;
                f = (Math.sqrt(dx * dx + dy * dy + dz * dz) - v.fogStart) / (v.fogEnd - v.fogStart);
                f = f < 0 ? 0 : f > 1 ? 1 : f;
            }
            clip[o + 6] = f;
        }
        int n = clipNear();
        if (n < 3) return;
        for (int i = 0; i < n; i++) {
            int o = i * 7;
            double iw = 1 / poly[o + 3];
            screen[o] = v.x + (poly[o] * iw * 0.5 + 0.5) * v.width;
            screen[o + 1] = v.y + (0.5 - poly[o + 1] * iw * 0.5) * v.height;
            screen[o + 2] = poly[o + 2] * iw;
            screen[o + 3] = iw;
            screen[o + 4] = poly[o + 4] * iw;
            screen[o + 5] = poly[o + 5] * iw;
            screen[o + 6] = poly[o + 6] * iw;
        }
        int x0 = Math.max(0, (int) Math.floor(v.x)), y0 = Math.max(0, (int) Math.floor(v.y));
        int x1 = Math.min(width - 1, (int) Math.ceil(v.x + v.width) - 1);
        int y1 = Math.min(height - 1, (int) Math.ceil(v.y + v.height) - 1);
        for (int i = 1; i + 1 < n; i++) {
            triangle(0, i, i + 1, c, texels, tw, th, x0, y0, x1, y1, fog ? v.fogColor : 0, fog);
        }
    }

    /** Sutherland-Hodgman against the near plane (z + w >= 0): the quad in poly[], answers its vertex count. */
    private int clipNear() {
        System.arraycopy(clip, 0, poly, 0, 4 * 7);
        int n = 4, out = 0;
        for (int i = 0; i < n; i++) {
            int a = i * 7, b = ((i + 1) % n) * 7;
            double da = poly[a + 2] + poly[a + 3], db = poly[b + 2] + poly[b + 3];
            if (da >= 0) {
                System.arraycopy(poly, a, next, out * 7, 7);
                out++;
            }
            if ((da >= 0) != (db >= 0)) {
                double t = da / (da - db);
                for (int k = 0; k < 7; k++) next[out * 7 + k] = poly[a + k] + (poly[b + k] - poly[a + k]) * t;
                out++;
            }
        }
        System.arraycopy(next, 0, poly, 0, out * 7);
        return out;
    }

    private void triangle(int ia, int ib, int ic, DrawCommand c, int[] texels, int tw, int th,
                          int clipX0, int clipY0, int clipX1, int clipY1, int fogColor, boolean fog) {
        int a = ia * 7, b = ib * 7, d = ic * 7;
        double ax = screen[a], ay = screen[a + 1], bx = screen[b], by = screen[b + 1], cx = screen[d], cy = screen[d + 1];
        double area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay);
        if (Math.abs(area) < 1e-9) return;
        int minX = Math.max(clipX0, (int) Math.floor(Math.min(ax, Math.min(bx, cx))));
        int maxX = Math.min(clipX1, (int) Math.ceil(Math.max(ax, Math.max(bx, cx))));
        int minY = Math.max(clipY0, (int) Math.floor(Math.min(ay, Math.min(by, cy))));
        int maxY = Math.min(clipY1, (int) Math.ceil(Math.max(ay, Math.max(by, cy))));
        if (minX > maxX || minY > maxY) return;
        double inv = 1 / area;
        double A0 = (by - cy) * inv, B0 = (cx - bx) * inv, C0 = (bx * cy - cx * by) * inv;
        double A1 = (cy - ay) * inv, B1 = (ax - cx) * inv, C1 = (cx * ay - ax * cy) * inv;
        double A2 = (ay - by) * inv, B2 = (bx - ax) * inv, C2 = (ax * by - bx * ay) * inv;
        int tint = c.color;
        double alpha = Math.max(0, Math.min(1, c.alpha));
        int ta = (int) Math.round(((tint >>> 24) & 255) * alpha), tr = (tint >> 16) & 255, tg = (tint >> 8) & 255,
                tb = tint & 255;
        boolean opaque = c.cutout;
        boolean smooth = c.smooth && texels != null;
        int fr = (fogColor >> 16) & 255, fgc = (fogColor >> 8) & 255, fb = fogColor & 255;
        for (int py = minY; py <= maxY; py++) {
            double sy = py + 0.5, sx = minX + 0.5;
            double w0 = A0 * sx + B0 * sy + C0, w1 = A1 * sx + B1 * sy + C1, w2 = A2 * sx + B2 * sy + C2;
            int row = py * width;
            for (int px = minX; px <= maxX; px++, w0 += A0, w1 += A1, w2 += A2) {
                if (w0 < 0 || w1 < 0 || w2 < 0) continue;
                double z = w0 * screen[a + 2] + w1 * screen[b + 2] + w2 * screen[d + 2];
                int at = row + px;
                if (z >= depth[at]) continue;
                int sa, sr, sg, sb;
                if (texels != null) {
                    double iw = w0 * screen[a + 3] + w1 * screen[b + 3] + w2 * screen[d + 3];
                    double u = (w0 * screen[a + 4] + w1 * screen[b + 4] + w2 * screen[d + 4]) / iw;
                    double t = (w0 * screen[a + 5] + w1 * screen[b + 5] + w2 * screen[d + 5]) / iw;
                    int texel = smooth ? bilinear(texels, tw, th, u, t) : nearest(texels, tw, th, u, t);
                    sa = texel >>> 24;
                    if (opaque && sa < 128) continue;
                    sr = ((texel >> 16) & 255) * tr / 255;
                    sg = ((texel >> 8) & 255) * tg / 255;
                    sb = (texel & 255) * tb / 255;
                    sa = sa * ta / 255;
                } else {
                    sa = ta;
                    sr = tr;
                    sg = tg;
                    sb = tb;
                }
                if (fog) {
                    double iw = w0 * screen[a + 3] + w1 * screen[b + 3] + w2 * screen[d + 3];
                    double f = (w0 * screen[a + 6] + w1 * screen[b + 6] + w2 * screen[d + 6]) / iw;
                    sr += (int) ((fr - sr) * f);
                    sg += (int) ((fgc - sg) * f);
                    sb += (int) ((fb - sb) * f);
                }
                if (opaque || sa >= 255) {
                    color[at] = 0xFF000000 | (sr << 16) | (sg << 8) | sb;
                    if (opaque) depth[at] = (float) z;
                } else if (sa > 0) {                        // see-through: blended, depth kept
                    int dst = color[at];
                    int da = dst >>> 24, k = 255 - sa;
                    int or = (sr * sa + ((dst >> 16) & 255) * k) / 255;
                    int og = (sg * sa + ((dst >> 8) & 255) * k) / 255;
                    int ob = (sb * sa + (dst & 255) * k) / 255;
                    int oa = sa + da * k / 255;
                    color[at] = (oa << 24) | (or << 16) | (og << 8) | ob;
                }
            }
        }
    }

    private static int nearest(int[] texels, int tw, int th, double u, double v) {
        int x = (int) (u * tw), y = (int) (v * th);
        x = x < 0 ? 0 : x >= tw ? tw - 1 : x;
        y = y < 0 ? 0 : y >= th ? th - 1 : y;
        return texels[y * tw + x];
    }

    private static int bilinear(int[] texels, int tw, int th, double u, double v) {
        double fx = u * tw - 0.5, fy = v * th - 0.5;
        int x0 = (int) Math.floor(fx), y0 = (int) Math.floor(fy);
        double ax = fx - x0, ay = fy - y0;
        int c00 = at(texels, tw, th, x0, y0), c10 = at(texels, tw, th, x0 + 1, y0);
        int c01 = at(texels, tw, th, x0, y0 + 1), c11 = at(texels, tw, th, x0 + 1, y0 + 1);
        int out = 0;
        for (int shift = 0; shift <= 24; shift += 8) {
            double top = ((c00 >>> shift) & 255) * (1 - ax) + ((c10 >>> shift) & 255) * ax;
            double bottom = ((c01 >>> shift) & 255) * (1 - ax) + ((c11 >>> shift) & 255) * ax;
            out |= ((int) Math.round(top * (1 - ay) + bottom * ay) & 255) << shift;
        }
        return out;
    }

    private static int at(int[] texels, int tw, int th, int x, int y) {
        x = x < 0 ? 0 : x >= tw ? tw - 1 : x;
        y = y < 0 ? 0 : y >= th ? th - 1 : y;
        return texels[y * tw + x];
    }
}
