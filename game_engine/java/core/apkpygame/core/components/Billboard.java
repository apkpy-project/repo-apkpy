package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Scene;
import apkpygame.core.math.Color;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.Camera3D;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.Quads;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;

/**
 * 2.5D: a sprite standing up on the ground and turned to the camera (around
 * the vertical axis only, as on the DS). The image is a sheet: one row per
 * direction (1, 4 or 8; rows: down, left, up, right; with 8, the diagonals in
 * between: down, down-left, left, up-left, up, up-right, right, down-right)
 * and one column per walking frame (column 0 when standing still).
 *
 * <p>{@code facing} (degrees on the ground: 0 down, 90 right, 180 up, 270
 * left) follows the walk by itself unless a script sets {@code autoFacing}
 * false. With {@code stand}, the entity's elevation follows the heights of
 * the scene's Tilemap (stairs and ledges).
 */
public final class Billboard extends Component {
    public Texture texture;
    public int frameW, frameH;
    public int directions = 1;
    public double fps = 8;
    public double facing;
    public boolean autoFacing = true;
    public boolean stand = true;
    public int tint = Color.WHITE;
    public double alpha = 1;
    public boolean smooth;
    public boolean visible = true;
    /** A frame of the sheet chosen by a script (a monster in a sheet of monsters); -1: by direction and walking. */
    private int fixedFrame = -1;

    /** Another image of the bundle, cut in cells of the same size. */
    public void setImage(String path) {
        texture = game().assets.texture(path);
    }

    public void setFrame(int frame) {
        fixedFrame = frame;
    }
    /** The point of the picture at the entity's position: (0.5, 1) is the middle of the feet. */
    public double pivotX = 0.5, pivotY = 1;

    private Tilemap map;
    private boolean looked, moving;
    private double lastX = Double.NaN, lastY;

    /** Whether it moved since its last step (it shows its walking frames). */
    public boolean moving() {
        return moving;
    }

    @Override protected void update(double dt) {
        Transform2D t = entity().transform;
        if (!Double.isNaN(lastX)) {        // facing is game logic (scripts read it): from the steps, StrictMath
            double dx = t.x - lastX, dy = t.y - lastY;
            moving = dx * dx + dy * dy > 1e-9;
            if (moving && autoFacing) facing = StrictMath.toDegrees(StrictMath.atan2(dx, dy));
        }
        lastX = t.x;
        lastY = t.y;
        if (!stand) return;
        if (!looked) {
            looked = true;
            for (apkpygame.core.Entity e : scene().entities()) {
                Tilemap found = e.get(Tilemap.class);
                if (found != null) map = found;
            }
        }
        if (map == null) return;
        double target = map.heightAt(entity().worldX(), entity().worldY());
        Transform2D tr = entity().transform;
        double k = Math.min(1, dt * 14);
        tr.elevation = Math.abs(target - tr.elevation) < 0.05 ? target : tr.elevation + (target - tr.elevation) * k;
    }

    @Override protected void render3d(RenderQueue queue, Mat3 world, double elevation) {
        Scene s = scene();
        if (!visible || texture == null || s.camera3d == null) return;
        int fw = frameW > 0 ? frameW : texture.width, fh = frameH > 0 ? frameH : texture.height;
        Camera3D cam = s.camera3d;
        int row = 0;
        if (directions == 4 || directions == 8) {
            double rel = ((facing - cam.yaw) % 360 + 360) % 360;
            int k = (int) Math.round(rel / (360.0 / directions)) % directions;
            row = (directions - k) % directions;
        }
        int columns = Math.max(1, texture.width / fw);
        int col = moving ? (int) (game().steps() * game().stepSeconds * fps) % columns : 0;
        if (fixedFrame >= 0) {
            col = fixedFrame % columns;
            row = fixedFrame / columns;
        }
        double scaleX = Math.sqrt(world.a * world.a + world.b * world.b);
        double scaleY = Math.sqrt(world.c * world.c + world.d * world.d);
        double w = fw * scaleX, h = fh * scaleY;
        double rx = cam.rightX(), ry = cam.rightY();
        double gx = world.tx, gy = world.ty;
        double left = -pivotX * w, right = (1 - pivotX) * w, bottom = elevation - (1 - pivotY) * h;
        DrawCommand c = Quads.add(queue, s.view3d, texture, tint, alpha, smooth);
        Quads.corner(c, 0, gx + rx * left, gy + ry * left, bottom);
        Quads.corner(c, 1, gx + rx * right, gy + ry * right, bottom);
        Quads.corner(c, 2, gx + rx * right, gy + ry * right, bottom + h);
        Quads.corner(c, 3, gx + rx * left, gy + ry * left, bottom + h);
        Quads.region(c, col * fw, row * fh, fw, fh, false);
        Quads.sortSeeThrough(c);
    }
}
