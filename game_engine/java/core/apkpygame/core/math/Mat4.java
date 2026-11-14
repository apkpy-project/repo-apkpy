package apkpygame.core.math;

/**
 * A 4x4 matrix for the 2.5D (and later 3D) camera, column-major as OpenGL
 * reads it: m[col * 4 + row]. OpenGL conventions: Y up, right-handed, the
 * camera looks down -Z, clip space -1..1. Trigonometry uses StrictMath: the
 * camera turns taps into world points, which is game logic.
 */
public final class Mat4 {
    public final double[] m = new double[16];

    public Mat4() {
        identity();
    }

    public Mat4 identity() {
        java.util.Arrays.fill(m, 0);
        m[0] = m[5] = m[10] = m[15] = 1;
        return this;
    }

    public Mat4 set(Mat4 o) {
        System.arraycopy(o.m, 0, m, 0, 16);
        return this;
    }

    /** this = a * b (b applied first). {@code a} or {@code b} may be this. */
    public Mat4 multiply(Mat4 a, Mat4 b) {
        double[] r = new double[16];
        for (int c = 0; c < 4; c++) {
            for (int row = 0; row < 4; row++) {
                r[c * 4 + row] = a.m[row] * b.m[c * 4] + a.m[4 + row] * b.m[c * 4 + 1]
                        + a.m[8 + row] * b.m[c * 4 + 2] + a.m[12 + row] * b.m[c * 4 + 3];
            }
        }
        System.arraycopy(r, 0, m, 0, 16);
        return this;
    }

    /** A perspective projection: vertical field of view in degrees. */
    public Mat4 perspective(double fovDegrees, double aspect, double near, double far) {
        double f = 1 / StrictMath.tan(StrictMath.toRadians(fovDegrees) / 2);
        java.util.Arrays.fill(m, 0);
        m[0] = f / aspect;
        m[5] = f;
        m[10] = (far + near) / (near - far);
        m[11] = -1;
        m[14] = 2 * far * near / (near - far);
        return this;
    }

    /** A view matrix: the eye at (ex, ey, ez) looking at (tx, ty, tz), Y up. */
    public Mat4 lookAt(double ex, double ey, double ez, double tx, double ty, double tz) {
        double fx = tx - ex, fy = ty - ey, fz = tz - ez;
        double fl = StrictMath.sqrt(fx * fx + fy * fy + fz * fz);
        fx /= fl;
        fy /= fl;
        fz /= fl;
        double sx = -fz, sz = fx;                           // forward x up(0, 1, 0)
        double sl = StrictMath.sqrt(sx * sx + sz * sz);
        if (sl < 1e-12) {                                   // looking straight down: any right will do
            sx = 1;
            sz = 0;
            sl = 1;
        }
        sx /= sl;
        sz /= sl;
        double ux = -sz * fy, uy = sz * fx - sx * fz, uz = sx * fy;   // right x forward
        m[0] = sx; m[1] = ux; m[2] = -fx; m[3] = 0;
        m[4] = 0;  m[5] = uy; m[6] = -fy; m[7] = 0;
        m[8] = sz; m[9] = uz; m[10] = -fz; m[11] = 0;
        m[12] = -(sx * ex + sz * ez);
        m[13] = -(ux * ex + uy * ey + uz * ez);
        m[14] = fx * ex + fy * ey + fz * ez;
        m[15] = 1;
        return this;
    }

    /** The inverse (cofactors); a singular matrix becomes the identity. */
    public Mat4 invert() {
        double[] a = m, inv = new double[16];
        inv[0] = a[5] * a[10] * a[15] - a[5] * a[11] * a[14] - a[9] * a[6] * a[15] + a[9] * a[7] * a[14] + a[13] * a[6] * a[11] - a[13] * a[7] * a[10];
        inv[4] = -a[4] * a[10] * a[15] + a[4] * a[11] * a[14] + a[8] * a[6] * a[15] - a[8] * a[7] * a[14] - a[12] * a[6] * a[11] + a[12] * a[7] * a[10];
        inv[8] = a[4] * a[9] * a[15] - a[4] * a[11] * a[13] - a[8] * a[5] * a[15] + a[8] * a[7] * a[13] + a[12] * a[5] * a[11] - a[12] * a[7] * a[9];
        inv[12] = -a[4] * a[9] * a[14] + a[4] * a[10] * a[13] + a[8] * a[5] * a[14] - a[8] * a[6] * a[13] - a[12] * a[5] * a[10] + a[12] * a[6] * a[9];
        inv[1] = -a[1] * a[10] * a[15] + a[1] * a[11] * a[14] + a[9] * a[2] * a[15] - a[9] * a[3] * a[14] - a[13] * a[2] * a[11] + a[13] * a[3] * a[10];
        inv[5] = a[0] * a[10] * a[15] - a[0] * a[11] * a[14] - a[8] * a[2] * a[15] + a[8] * a[3] * a[14] + a[12] * a[2] * a[11] - a[12] * a[3] * a[10];
        inv[9] = -a[0] * a[9] * a[15] + a[0] * a[11] * a[13] + a[8] * a[1] * a[15] - a[8] * a[3] * a[13] - a[12] * a[1] * a[11] + a[12] * a[3] * a[9];
        inv[13] = a[0] * a[9] * a[14] - a[0] * a[10] * a[13] - a[8] * a[1] * a[14] + a[8] * a[2] * a[13] + a[12] * a[1] * a[10] - a[12] * a[2] * a[9];
        inv[2] = a[1] * a[6] * a[15] - a[1] * a[7] * a[14] - a[5] * a[2] * a[15] + a[5] * a[3] * a[14] + a[13] * a[2] * a[7] - a[13] * a[3] * a[6];
        inv[6] = -a[0] * a[6] * a[15] + a[0] * a[7] * a[14] + a[4] * a[2] * a[15] - a[4] * a[3] * a[14] - a[12] * a[2] * a[7] + a[12] * a[3] * a[6];
        inv[10] = a[0] * a[5] * a[15] - a[0] * a[7] * a[13] - a[4] * a[1] * a[15] + a[4] * a[3] * a[13] + a[12] * a[1] * a[7] - a[12] * a[3] * a[5];
        inv[14] = -a[0] * a[5] * a[14] + a[0] * a[6] * a[13] + a[4] * a[1] * a[14] - a[4] * a[2] * a[13] - a[12] * a[1] * a[6] + a[12] * a[2] * a[5];
        inv[3] = -a[1] * a[6] * a[11] + a[1] * a[7] * a[10] + a[5] * a[2] * a[11] - a[5] * a[3] * a[10] - a[9] * a[2] * a[7] + a[9] * a[3] * a[6];
        inv[7] = a[0] * a[6] * a[11] - a[0] * a[7] * a[10] - a[4] * a[2] * a[11] + a[4] * a[3] * a[10] + a[8] * a[2] * a[7] - a[8] * a[3] * a[6];
        inv[11] = -a[0] * a[5] * a[11] + a[0] * a[7] * a[9] + a[4] * a[1] * a[11] - a[4] * a[3] * a[9] - a[8] * a[1] * a[7] + a[8] * a[3] * a[5];
        inv[15] = a[0] * a[5] * a[10] - a[0] * a[6] * a[9] - a[4] * a[1] * a[10] + a[4] * a[2] * a[9] + a[8] * a[1] * a[6] - a[8] * a[2] * a[5];
        double det = a[0] * inv[0] + a[1] * inv[4] + a[2] * inv[8] + a[3] * inv[12];
        if (det == 0) return identity();
        for (int i = 0; i < 16; i++) m[i] = inv[i] / det;
        return this;
    }

    /** (x, y, z, 1) through the matrix, into out[0..3] (clip space for a projection: not divided by w). */
    public void transform(double x, double y, double z, double[] out, int at) {
        out[at] = m[0] * x + m[4] * y + m[8] * z + m[12];
        out[at + 1] = m[1] * x + m[5] * y + m[9] * z + m[13];
        out[at + 2] = m[2] * x + m[6] * y + m[10] * z + m[14];
        out[at + 3] = m[3] * x + m[7] * y + m[11] * z + m[15];
    }
}
