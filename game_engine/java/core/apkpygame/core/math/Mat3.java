package apkpygame.core.math;

/**
 * A 2D affine transform, mutable so the render path allocates nothing:
 *
 * <pre>
 *  | a  c  tx |
 *  | b  d  ty |
 *  | 0  0  1  |
 * </pre>
 *
 * Maps (x, y) to (a*x + c*y + tx, b*x + d*y + ty). Angles are in degrees,
 * as everywhere in the API; trigonometry uses StrictMath so every platform
 * computes the same bits.
 */
public final class Mat3 {
    public double a = 1, b, c, d = 1, tx, ty;

    public Mat3 identity() {
        a = 1; b = 0; c = 0; d = 1; tx = 0; ty = 0;
        return this;
    }

    public Mat3 set(Mat3 m) {
        a = m.a; b = m.b; c = m.c; d = m.d; tx = m.tx; ty = m.ty;
        return this;
    }

    public Mat3 set(double a, double b, double c, double d, double tx, double ty) {
        this.a = a; this.b = b; this.c = c; this.d = d; this.tx = tx; this.ty = ty;
        return this;
    }

    /** translate(x, y) * rotate(degrees) * scale(sx, sy) */
    public Mat3 setTransform(double x, double y, double degrees, double sx, double sy) {
        double r = StrictMath.toRadians(degrees);
        double cos = degrees == 0 ? 1 : StrictMath.cos(r);
        double sin = degrees == 0 ? 0 : StrictMath.sin(r);
        a = cos * sx; b = sin * sx;
        c = -sin * sy; d = cos * sy;
        tx = x; ty = y;
        return this;
    }

    /** this = this * m (m is applied first) */
    public Mat3 multiply(Mat3 m) {
        double na = a * m.a + c * m.b, nb = b * m.a + d * m.b;
        double nc = a * m.c + c * m.d, nd = b * m.c + d * m.d;
        double ntx = a * m.tx + c * m.ty + tx, nty = b * m.tx + d * m.ty + ty;
        a = na; b = nb; c = nc; d = nd; tx = ntx; ty = nty;
        return this;
    }

    public Mat3 translate(double x, double y) {
        tx += a * x + c * y;
        ty += b * x + d * y;
        return this;
    }

    public Mat3 scale(double sx, double sy) {
        a *= sx; b *= sx; c *= sy; d *= sy;
        return this;
    }

    public Mat3 rotate(double degrees) {
        if (degrees == 0) return this;
        double r = StrictMath.toRadians(degrees), cos = StrictMath.cos(r), sin = StrictMath.sin(r);
        double na = a * cos + c * sin, nb = b * cos + d * sin;
        double nc = -a * sin + c * cos, nd = -b * sin + d * cos;
        a = na; b = nb; c = nc; d = nd;
        return this;
    }

    public Mat3 invert() {
        double det = a * d - b * c;
        if (det == 0) return identity();
        double ia = d / det, ib = -b / det, ic = -c / det, id = a / det;
        double itx = -(ia * tx + ic * ty), ity = -(ib * tx + id * ty);
        a = ia; b = ib; c = ic; d = id; tx = itx; ty = ity;
        return this;
    }

    public double mapX(double x, double y) {
        return a * x + c * y + tx;
    }

    public double mapY(double x, double y) {
        return b * x + d * y + ty;
    }

    @Override public String toString() {
        return "Mat3[" + a + ", " + b + ", " + c + ", " + d + ", " + tx + ", " + ty + "]";
    }
}
