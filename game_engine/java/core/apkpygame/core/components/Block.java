package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Scene;
import apkpygame.core.math.Color;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.Quads;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;

/**
 * 2.5D: a box on the ground (houses, walls, crates, ledges): {@code width} x
 * {@code depth} units around the entity, {@code height} units up from its
 * elevation. The top and the sides each take an image (stretched over the
 * face) or a plain colour; each side gets its own shade, as on the DS, where
 * the light is painted in. The entity's rotation turns the box.
 */
public final class Block extends Component {
    public double width = 16, depth = 16, height = 16;
    public Texture top, side;
    public int topColor = Color.WHITE, sideColor = Color.WHITE;
    public boolean smooth;
    public boolean visible = true;

    @Override protected void render3d(RenderQueue queue, Mat3 world, double elevation) {
        Scene s = scene();
        if (!visible || s.camera3d == null) return;
        double hw = width / 2, hd = depth / 2;
        // the four ground corners through the entity's matrix (position, rotation, scale)
        double[] gx = new double[4], gy = new double[4];
        double[][] local = {{-hw, hd}, {hw, hd}, {hw, -hd}, {-hw, -hd}};
        for (int i = 0; i < 4; i++) {
            gx[i] = world.mapX(local[i][0], local[i][1]);
            gy[i] = world.mapY(local[i][0], local[i][1]);
        }
        double low = elevation, high = elevation + height;
        DrawCommand t = Quads.add(queue, s.view3d, top, topColor, 1, smooth);
        Quads.corner(t, 0, gx[0], gy[0], high);
        Quads.corner(t, 1, gx[1], gy[1], high);
        Quads.corner(t, 2, gx[2], gy[2], high);
        Quads.corner(t, 3, gx[3], gy[3], high);
        whole(t);
        double[] shades = {0.86, 0.7, 0.78, 0.7};          // front (+y), right, back, left
        for (int i = 0; i < 4; i++) {
            int a = i, b = (i + 1) % 4;                     // corners: front-left, front-right, back-right, back-left
            DrawCommand c = Quads.add(queue, s.view3d, side, Quads.shade(sideColor, shades[i]), 1, smooth);
            Quads.corner(c, 0, gx[a], gy[a], low);
            Quads.corner(c, 1, gx[b], gy[b], low);
            Quads.corner(c, 2, gx[b], gy[b], high);
            Quads.corner(c, 3, gx[a], gy[a], high);
            whole(c);
        }
    }

    private static void whole(DrawCommand c) {
        if (c.texture == null) return;
        Quads.region(c, 0, 0, c.texture.width, c.texture.height, false);
    }
}
