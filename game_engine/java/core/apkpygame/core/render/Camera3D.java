package apkpygame.core.render;

import apkpygame.core.math.Mat4;

/**
 * The camera of a "2.5d" scene: a perspective camera that looks down at a
 * point of the ground from a distance, like the DS-era RPGs.
 *
 * <p>The world stays the 2D one: ground (x, y) with y towards the viewer, and
 * an elevation up. In OpenGL terms ground (x, y) at elevation e is the point
 * (x, e, y): Y up, right-handed. With yaw 0 the camera stands on the +y side
 * of its target (the bottom of a 2D map) and looks "up" the map.
 *
 * <p>Its numbers turn taps into ground points (game logic), so they come only
 * from the scene (target, pitch, yaw, distance, fov) and use StrictMath.
 */
public final class Camera3D {
    /** Degrees down from the horizon (90 = straight down). */
    public double pitch = 40;
    /** Degrees around the vertical axis; 0 = looking along -y (up the map). */
    public double yaw;
    /** World units from the target to the eye. */
    public double distance = 220;
    /** Vertical field of view, degrees. */
    public double fov = 40;
    public double near = 4, far = 4000;

    private final Mat4 view = new Mat4(), projection = new Mat4();
    public final Mat4 viewProjection = new Mat4(), inverse = new Mat4();
    /** The eye, in OpenGL coordinates (x, elevation, y), after update(). */
    public double eyeX, eyeY, eyeZ;

    /** Builds the matrices for a target on the ground (x, y) at elevation e, for a view of this aspect (w / h). */
    public void update(double targetX, double targetY, double elevation, double aspect) {
        double p = StrictMath.toRadians(pitch), a = StrictMath.toRadians(yaw);
        double horizontal = StrictMath.cos(p) * distance;
        eyeX = targetX + StrictMath.sin(a) * horizontal;
        eyeY = elevation + StrictMath.sin(p) * distance;
        eyeZ = targetY + StrictMath.cos(a) * horizontal;
        view.lookAt(eyeX, eyeY, eyeZ, targetX, elevation, targetY);
        projection.perspective(fov, aspect, near, far);
        viewProjection.multiply(projection, view);
        inverse.set(viewProjection).invert();
    }

    /** The camera's right on the ground: billboards face the camera by turning to it. */
    public double rightX() {
        return StrictMath.cos(StrictMath.toRadians(yaw));
    }

    public double rightY() {
        return -StrictMath.sin(StrictMath.toRadians(yaw));
    }

    /**
     * The ground point (x, y) under a point of the view (ndcX, ndcY in -1..1, Y up), on the plane at
     * {@code elevation}; false when the ray does not meet it (pointing at the sky).
     */
    public boolean pick(double ndcX, double ndcY, double elevation, double[] out) {
        double[] a = new double[4], b = new double[4];
        unproject(ndcX, ndcY, -1, a);
        unproject(ndcX, ndcY, 1, b);
        double dy = b[1] - a[1];
        if (dy > -1e-12 && dy < 1e-12) return false;
        double t = (elevation - a[1]) / dy;
        if (t < 0) return false;
        out[0] = a[0] + (b[0] - a[0]) * t;
        out[1] = a[2] + (b[2] - a[2]) * t;
        return true;
    }

    private void unproject(double x, double y, double z, double[] out) {
        inverse.transform(x, y, z, out, 0);
        double w = out[3];
        out[0] /= w;
        out[1] /= w;
        out[2] /= w;
    }
}
