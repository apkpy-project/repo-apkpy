package apkpygame.core.render;

import apkpygame.core.math.Mat3;

/**
 * What a scene is seen through. Camera2D today; a Camera3D (perspective)
 * implements the 3D counterpart later, which is why this is an interface.
 */
public interface Camera {
    /** Writes the world-to-virtual-screen transform into {@code out}. */
    void viewMatrix(double viewWidth, double viewHeight, Mat3 out);
}
