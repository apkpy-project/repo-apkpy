package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.math.Color;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;

/**
 * An image (or a region of one). One texel is one world unit; the pivot
 * (0..1 on each axis, centre by default) is the point placed at the
 * entity's position and the one it rotates around.
 */
public final class Sprite extends Component {
    public Texture texture;
    public int srcX, srcY, srcW, srcH;
    public double pivotX = 0.5, pivotY = 0.5;
    public int tint = Color.WHITE;
    public double alpha = 1;
    public int layer, order;
    /** false for pixel art (nearest-neighbour). */
    public boolean smooth = true;
    public boolean flipX, flipY;
    public boolean visible = true;

    public Sprite(Texture texture) {
        setTexture(texture);
    }

    public void setTexture(Texture texture) {
        this.texture = texture;
        srcX = srcY = 0;
        srcW = texture == null ? 0 : texture.width;
        srcH = texture == null ? 0 : texture.height;
    }

    public void setTint(String hex) {
        tint = Color.parse(hex, tint);
    }

    /** Another image of the bundle, cut in cells of the same size (a monster in a screen that shows any monster). */
    public void setImage(String path) {
        Texture t = game().assets.texture(path);
        if (t != texture) texture = t;
    }

    /** A frame of a sheet (cells of this sprite's size, left to right, top to bottom). */
    public void setFrame(int frame) {
        int columns = Math.max(1, texture.width / Math.max(1, srcW));
        setRegion(frame % columns * srcW, frame / columns * srcH, srcW, srcH);
    }

    public void setRegion(int x, int y, int w, int h) {
        srcX = x;
        srcY = y;
        srcW = w;
        srcH = h;
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        if (!visible || texture == null || alpha <= 0) return;
        DrawCommand c = queue.add(DrawCommand.Kind.SPRITE);
        c.layer = layer;
        c.order = order;
        c.matrix.set(world);
        if (flipX || flipY) c.matrix.scale(flipX ? -1 : 1, flipY ? -1 : 1);
        c.texture = texture;
        c.srcX = srcX;
        c.srcY = srcY;
        c.srcW = srcW;
        c.srcH = srcH;
        c.x = -pivotX * srcW;
        c.y = -pivotY * srcH;
        c.w = srcW;
        c.h = srcH;
        c.color = tint;
        c.alpha = alpha;
        c.smooth = smooth;
    }
}
