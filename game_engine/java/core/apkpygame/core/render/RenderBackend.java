package apkpygame.core.render;

/**
 * Draws a RenderQueue on one platform: Android Canvas, Java2D, and later GLES.
 * The core computes every matrix; a backend only executes commands.
 */
public interface RenderBackend {
    /** Decodes an image (PNG/JPEG/WebP) the assets returned. */
    Texture loadTexture(String path, byte[] data);

    /** Prepares a TTF/OTF file; answers what DrawCommand.face will carry. */
    Object loadFont(String path, byte[] data);

    void begin(int surfaceWidth, int surfaceHeight, int clearColor);

    void draw(DrawCommand command);

    void end();
}
