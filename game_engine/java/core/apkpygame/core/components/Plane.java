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
 * 2.5D: one picture as a quad: lying on the ground ("flat": rugs, shadows,
 * paths) or standing ("upright": signs, fences, roofs seen from the front),
 * turned by the entity's rotation. {@code cross} adds a second upright quad
 * at right angles, the classic cheap tree. Image or plain colour.
 */
public final class Plane extends Component {
    public Texture texture;
    public int color = Color.WHITE;
    public double alpha = 1;
    public double width = 16, height = 16;
    public boolean flat;
    public boolean cross;
    public boolean smooth;
    public boolean visible = true;

    @Override protected void render3d(RenderQueue queue, Mat3 world, double elevation) {
        Scene s = scene();
        if (!visible || s.camera3d == null) return;
        double hw = width / 2, hh = height / 2;
        if (flat) {
            DrawCommand c = Quads.add(queue, s.view3d, texture, color, alpha, smooth);
            double[][] p = {{-hw, hh}, {hw, hh}, {hw, -hh}, {-hw, -hh}};
            for (int i = 0; i < 4; i++) {
                Quads.corner(c, i, world.mapX(p[i][0], p[i][1]), world.mapY(p[i][0], p[i][1]), elevation + 0.05);
            }
            region(c);
            Quads.sortSeeThrough(c);
            return;
        }
        upright(queue, s, world, elevation, 1, 0);
        if (cross) upright(queue, s, world, elevation, 0, 1);
    }

    /** A standing quad along the local direction (dx, dy), its bottom at the entity's elevation. */
    private void upright(RenderQueue queue, Scene s, Mat3 world, double elevation, double dx, double dy) {
        double hw = width / 2;
        double ax = world.mapX(-dx * hw, -dy * hw), ay = world.mapY(-dx * hw, -dy * hw);
        double bx = world.mapX(dx * hw, dy * hw), by = world.mapY(dx * hw, dy * hw);
        DrawCommand c = Quads.add(queue, s.view3d, texture, color, alpha, smooth);
        Quads.corner(c, 0, ax, ay, elevation);
        Quads.corner(c, 1, bx, by, elevation);
        Quads.corner(c, 2, bx, by, elevation + height);
        Quads.corner(c, 3, ax, ay, elevation + height);
        region(c);
        Quads.sortSeeThrough(c);
    }

    private static void region(DrawCommand c) {
        if (c.texture != null) Quads.region(c, 0, 0, c.texture.width, c.texture.height, false);
    }
}
