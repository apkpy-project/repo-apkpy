package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.GameException;
import apkpygame.core.json.Json;
import apkpygame.core.math.Mat3;
import apkpygame.core.physics2d.TileGrid;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.Quads;
import apkpygame.core.Scene;
import apkpygame.core.math.Color;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * A tile map made in Tiled (converted by apkpygame build to
 * tilemaps/NAME.json): its tile layers are drawn (only the tiles on screen),
 * and its solid cells are given to the physics. Keep the tilemap entity
 * unrotated and unscaled: the physics reads tiles in world units.
 */
public final class Tilemap extends Component {
    public String path;
    public int layer = -10;
    public boolean smooth;

    private Texture texture;
    private int tileW, tileH, cols, rows, columns, margin, spacing, firstGid;
    private final List<int[]> layers = new ArrayList<int[]>();
    private final List<int[]> allLayers = new ArrayList<int[]>();
    /** 2.5D: the height of each cell (tiles; a tile is tileW world units up), and the tile drawn on walls. */
    private double[] heights;
    /** Local tile id -> its Tiled properties other than height/side ("zone": "grass"...), if any. */
    private final Map<Integer, Map<String, Object>> tileTags = new java.util.HashMap<Integer, Map<String, Object>>();
    private final Map<Integer, Integer> sides = new java.util.HashMap<Integer, Integer>();
    private final Mat3 inverse = new Mat3();

    @Override protected void start() {
        Map<String, Object> o;
        try {
            o = Json.parseObject(game().assets.text(path));
        } catch (IllegalArgumentException e) {
            throw new GameException("G3023", path + " is not a tilemap the engine can read", "Rebuild the game.", e);
        }
        tileW = (int) Json.num(o, "tile_w", 16);
        tileH = (int) Json.num(o, "tile_h", 16);
        cols = (int) Json.num(o, "cols", 0);
        rows = (int) Json.num(o, "rows", 0);
        columns = (int) Json.num(o, "columns", 1);
        margin = (int) Json.num(o, "margin", 0);
        spacing = (int) Json.num(o, "spacing", 0);
        firstGid = (int) Json.num(o, "firstgid", 1);
        texture = game().assets.texture(Json.str(o, "image", ""));
        for (Object item : Json.list(o, "layers")) {
            @SuppressWarnings("unchecked")
            Map<String, Object> l = (Map<String, Object>) item;
            int[] data = ints(Json.list(l, "data"));
            allLayers.add(data);                               // hidden layers too: tile tags often live there
            if (!Json.bool(l, "visible", true)) continue;
            layers.add(data);
        }
        List<Object> hs = Json.list(o, "heights");
        if (!hs.isEmpty()) {
            heights = new double[cols * rows];
            for (int i = 0; i < heights.length && i < hs.size(); i++) heights[i] = ((Number) hs.get(i)).doubleValue();
        }
        Map<String, Object> sd = Json.obj(o, "sides");
        if (sd != null) {
            for (Map.Entry<String, Object> e : sd.entrySet()) {
                sides.put(Integer.parseInt(e.getKey()), ((Number) e.getValue()).intValue());
            }
        }
        Map<String, Object> tags = Json.obj(o, "tile_tags");
        if (tags != null) {
            for (Map.Entry<String, Object> e : tags.entrySet()) {
                @SuppressWarnings("unchecked")
                Map<String, Object> p = (Map<String, Object>) e.getValue();
                tileTags.put(Integer.parseInt(e.getKey()), p);
            }
        }
        List<Object> solid = Json.list(o, "solid");
        if (!solid.isEmpty()) {
            boolean[] cells = new boolean[cols * rows];
            for (int i = 0; i < cells.length && i < solid.size(); i++) cells[i] = ((Number) solid.get(i)).intValue() != 0;
            scene().physics.setTiles(new TileGrid(entity().worldX(), entity().worldY(), tileW, tileH, cols, rows, cells));
        }
    }

    private static int[] ints(List<Object> data) {
        int[] out = new int[data.size()];
        for (int i = 0; i < out.length; i++) out[i] = ((Number) data.get(i)).intValue();
        return out;
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        if (texture == null) return;
        // the tiles under the surface: its corners, back in map space
        inverse.set(world).invert();
        double sw = game().viewport.surfaceWidth, sh = game().viewport.surfaceHeight;
        double minX = Double.MAX_VALUE, minY = Double.MAX_VALUE, maxX = -Double.MAX_VALUE, maxY = -Double.MAX_VALUE;
        double[][] corners = {{0, 0}, {sw, 0}, {0, sh}, {sw, sh}};
        for (double[] p : corners) {
            double x = inverse.mapX(p[0], p[1]), y = inverse.mapY(p[0], p[1]);
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x);
            maxY = Math.max(maxY, y);
        }
        int c0 = Math.max(0, (int) Math.floor(minX / tileW)), c1 = Math.min(cols - 1, (int) Math.floor(maxX / tileW));
        int r0 = Math.max(0, (int) Math.floor(minY / tileH)), r1 = Math.min(rows - 1, (int) Math.floor(maxY / tileH));
        for (int li = 0; li < layers.size(); li++) {
            int[] data = layers.get(li);
            for (int r = r0; r <= r1; r++) {
                for (int c = c0; c <= c1; c++) {
                    int gid = data[r * cols + c] & 0x1FFFFFFF;
                    if (gid < firstGid) continue;
                    int local = gid - firstGid;
                    DrawCommand d = queue.add(DrawCommand.Kind.SPRITE);
                    d.layer = layer + li;
                    d.matrix.set(world);
                    d.texture = texture;
                    d.srcX = margin + (local % columns) * (tileW + spacing);
                    d.srcY = margin + (local / columns) * (tileH + spacing);
                    d.srcW = tileW;
                    d.srcH = tileH;
                    d.x = c * tileW;
                    d.y = r * tileH;
                    d.w = tileW + 0.02;         // a hair of overlap: no seams between tiles when scaled
                    d.h = tileH + 0.02;
                    d.smooth = smooth;
                }
            }
        }
    }

    /** 2.5D: the ground's height (world units) at a world point; 0 outside the map or without heights. */
    public double heightAt(double worldX, double worldY) {
        if (heights == null) return 0;
        int c = (int) Math.floor((worldX - entity().worldX()) / tileW), r = (int) Math.floor((worldY - entity().worldY()) / tileH);
        if (c < 0 || r < 0 || c >= cols || r >= rows) return 0;
        return heights[r * cols + c] * tileW;
    }

    /**
     * A property of the tile at a world point (scene.tile_tag(x, y, "zone")): the
     * top-most layer whose tile there has it; "" when none has (or outside the map).
     */
    public String tileTag(double worldX, double worldY, String key) {
        if (tileTags.isEmpty()) return "";
        int c = (int) Math.floor((worldX - entity().worldX()) / tileW), r = (int) Math.floor((worldY - entity().worldY()) / tileH);
        if (c < 0 || r < 0 || c >= cols || r >= rows) return "";
        for (int i = allLayers.size() - 1; i >= 0; i--) {
            int gid = allLayers.get(i)[r * cols + c];
            if (gid == 0) continue;
            Map<String, Object> p = tileTags.get(gid - firstGid);
            if (p != null && p.containsKey(key)) {
                Object v = p.get(key);
                return v instanceof Double ? apkpygame.core.Py.str((Double) v) : String.valueOf(v);
            }
        }
        return "";
    }

    private double cellHeight(int c, int r) {
        if (heights == null || c < 0 || r < 0 || c >= cols || r >= rows) return 0;
        return heights[r * cols + c] * tileW;
    }

    /** 2.5D: every tile as a quad at its cell's height, and walls where a cell is higher than its neighbour. */
    @Override protected void render3d(RenderQueue queue, Mat3 world, double elevation) {
        Scene s = scene();
        if (texture == null || s.camera3d == null) return;
        double ox = world.tx, oy = world.ty;
        for (int li = 0; li < layers.size(); li++) {
            int[] data = layers.get(li);
            for (int r = 0; r < rows; r++) {
                for (int c = 0; c < cols; c++) {
                    int gid = data[r * cols + c] & 0x1FFFFFFF;
                    if (gid < firstGid) continue;
                    int local = gid - firstGid;
                    double h = elevation + cellHeight(c, r) + li * 0.04;     // upper layers a hair above
                    double x0 = ox + c * tileW, y0 = oy + r * tileH, x1 = x0 + tileW, y1 = y0 + tileH;
                    DrawCommand d = Quads.add(queue, s.view3d, texture, Color.WHITE, 1, smooth);
                    Quads.corner(d, 0, x0, y1, h);
                    Quads.corner(d, 1, x1, y1, h);
                    Quads.corner(d, 2, x1, y0, h);
                    Quads.corner(d, 3, x0, y0, h);
                    tileRegion(d, local);
                    if (li == 0) walls(queue, s, c, r, local, x0, y0, x1, y1, elevation);
                }
            }
        }
    }

    /** The walls of cell (c, r) down to each lower neighbour (or to 0 at the map's edge), one tile high each. */
    private void walls(RenderQueue queue, Scene s, int c, int r, int local, double x0, double y0, double x1, double y1,
                       double base) {
        double h = cellHeight(c, r);
        if (h <= 0) return;
        Integer side = sides.get(local);
        int tile = side != null ? side : local;
        // (neighbour dc, dr), the edge's two ground corners (left to right as seen from outside), shade
        double[][] edges = {{0, 1, x0, y1, x1, y1, 0.86}, {1, 0, x1, y1, x1, y0, 0.7}, {0, -1, x1, y0, x0, y0, 0.78},
                {-1, 0, x0, y0, x0, y1, 0.7}};
        for (double[] e : edges) {
            double low = cellHeight(c + (int) e[0], r + (int) e[1]);
            for (double z = low; z < h - 1e-9; z += tileW) {
                double top = Math.min(h, z + tileW);
                DrawCommand d = Quads.add(queue, s.view3d, texture, Quads.shade(Color.WHITE, e[6]), 1, smooth);
                Quads.corner(d, 0, e[2], e[3], base + z);
                Quads.corner(d, 1, e[4], e[5], base + z);
                Quads.corner(d, 2, e[4], e[5], base + top);
                Quads.corner(d, 3, e[2], e[3], base + top);
                tileRegion(d, tile);
                double part = (top - z) / tileW;                    // a partial last piece shows the tile's top part
                d.uv[1] = d.uv[7] + (d.uv[1] - d.uv[7]) * part;
                d.uv[3] = d.uv[5] + (d.uv[3] - d.uv[5]) * part;
            }
        }
    }

    private void tileRegion(DrawCommand d, int local) {
        Quads.region(d, margin + (local % columns) * (tileW + spacing), margin + (local / columns) * (tileH + spacing),
                tileW, tileH, false);
    }

    public int cols() {
        return cols;
    }

    public int rows() {
        return rows;
    }
}
