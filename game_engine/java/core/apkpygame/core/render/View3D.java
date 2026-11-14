package apkpygame.core.render;

import apkpygame.core.math.Mat4;

/**
 * What every QUAD3D command of a frame shares: the camera's view-projection,
 * where the game is on the surface (the viewport's rectangle, in pixels; the
 * 3D image fills it), and the fog. A backend draws QUAD3D commands with a
 * depth buffer inside that rectangle.
 */
public final class View3D {
    public final Mat4 viewProjection = new Mat4();
    /** The game area on the surface, in pixels (top-left origin). */
    public double x, y, width, height;
    /** Fog: none when fogEnd <= fogStart. Distances from the eye, world units; the colour is ARGB. */
    public double fogStart, fogEnd;
    public int fogColor;
    /** The eye (OpenGL coordinates), for the fog and for sorting what is see-through. */
    public double eyeX, eyeY, eyeZ;
}
