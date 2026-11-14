package apkpygame.core.render;

import apkpygame.core.math.Mat3;

/**
 * A 2D camera: (x, y) is the world point at the centre of the view.
 * The default, centred on the virtual screen, makes world units equal
 * virtual-screen units (Y down, origin at the top left).
 */
public final class Camera2D implements Camera {
    public double x, y, zoom = 1, rotation;

    public Camera2D(double x, double y) {
        this.x = x;
        this.y = y;
    }

    @Override public void viewMatrix(double viewWidth, double viewHeight, Mat3 out) {
        out.identity()
                .translate(viewWidth / 2, viewHeight / 2)
                .rotate(-rotation)
                .scale(zoom, zoom)
                .translate(-x, -y);
    }
}
