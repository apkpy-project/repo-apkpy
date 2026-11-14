package apkpygame.core;

import apkpygame.core.json.Json;
import apkpygame.core.math.Color;

import java.util.Map;

/** game.json of the bundle (format 1). */
public final class GameConfig {
    public static final int FORMAT = 1;

    public String name = "game";
    public double width = 360, height = 640;
    /** fit | fill | expand */
    public String scale = "fit";
    /** portrait | landscape | any */
    public String orientation = "portrait";
    /** Android: "auto" (OpenGL ES, else Canvas), "gles" or "canvas". */
    public String renderer = "auto";
    /** The font of every Text without one (its path in the bundle); null: the system's. */
    public String font;
    /** Screen pixels per virtual pixel are a whole number (pixel art). */
    public boolean pixelScale;
    public int background = Color.BLACK;
    public String startScene = "main";
    public int fixedHz = 60;
    public boolean debug;
    public long seed = 1;
    /** Starting values of the game's variables (score, lives...). */
    public final java.util.Map<String, Double> vars = new java.util.LinkedHashMap<String, Double>();

    public static GameConfig read(String json) {
        Map<String, Object> o = Json.parseObject(json);
        int format = (int) Json.num(o, "format", FORMAT);
        if (format > FORMAT) {
            throw new GameException("G3001", "game.json is format " + format + ", this engine reads up to "
                    + FORMAT, "Update the ApkPyGame engine, or rebuild the game with the same version.");
        }
        GameConfig c = new GameConfig();
        c.name = Json.str(o, "name", c.name);
        double[] size = Json.pair(o, "size", c.width, c.height);
        c.width = size[0];
        c.height = size[1];
        c.scale = Json.str(o, "scale", c.scale);
        c.orientation = Json.str(o, "orientation", c.orientation);
        c.renderer = Json.str(o, "renderer", c.renderer);
        c.background = Color.parse(Json.str(o, "background", null), c.background);
        c.font = Json.str(o, "font", null);
        c.pixelScale = Json.bool(o, "pixel_scale", false);
        c.startScene = Json.str(o, "start_scene", c.startScene);
        c.fixedHz = (int) Json.num(o, "fixed_hz", c.fixedHz);
        c.debug = Json.bool(o, "debug", false);
        c.seed = (long) Json.num(o, "seed", 1);
        Map<String, Object> vars = Json.obj(o, "vars");
        if (vars != null) {
            for (Map.Entry<String, Object> v : vars.entrySet()) {
                if (v.getValue() instanceof Number) c.vars.put(v.getKey(), ((Number) v.getValue()).doubleValue());
            }
        }
        return c;
    }
}
