package apkpygame.core.render;

import apkpygame.core.json.Json;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * A font's measures, read from the bundle (PATH.json, written by the build).
 * Line breaks and measured widths use only these numbers, never a platform's
 * rasteriser, so the game breaks its lines the same way on the PC and on the
 * phone. All sizes are per unit of text size.
 */
public final class FontData {
    /** One glyph of a bitmap font, in texels. */
    public static final class Glyph {
        public int x, y, w, h, offsetX, offsetY;
    }

    public final boolean bitmap;
    /** Baseline to the top of a line, and the distance between baselines. */
    public final double ascent, line;
    private final Map<Character, Double> advances = new HashMap<Character, Double>();
    private final double fallback;

    /** Bitmap fonts: the size it was drawn at, the image, and where the baseline is below a line's top (texels). */
    public final double nativeSize, base;
    public final String image;
    private final Map<Character, Glyph> glyphs = new HashMap<Character, Glyph>();

    /** What the platform's backend made of a TTF/OTF file (null: the system font, or a bitmap font). */
    public Object face;
    public boolean faceLoaded;
    public Texture texture;

    /** The measures used with the system font, which differs per platform: the same fixed widths everywhere. */
    public static final FontData SYSTEM = new FontData();

    private FontData() {
        bitmap = false;
        ascent = 0.93;
        line = 1.2;
        fallback = 0.56;
        nativeSize = base = 0;
        image = null;
        put(" .,:;'!|iljtfI", 0.3);
        put("mwMW@", 0.86);
        put("ABCDEFGHKNOPQRSTUVXYZ", 0.68);
        faceLoaded = true;
    }

    private void put(String chars, double value) {
        for (int i = 0; i < chars.length(); i++) advances.put(chars.charAt(i), value);
    }

    @SuppressWarnings("unchecked")
    public FontData(Map<String, Object> o) {
        bitmap = "bitmap".equals(Json.str(o, "kind", "ttf"));
        ascent = Json.num(o, "ascent", 1);
        line = Json.num(o, "line", 1.2);
        fallback = Json.num(o, "fallback", 0.5);
        nativeSize = Json.num(o, "size", 0);
        base = Json.num(o, "base", 0);
        image = Json.str(o, "image", null);
        for (Map.Entry<String, Object> e : Json.obj(o, "advances").entrySet()) {
            advances.put(e.getKey().charAt(0), ((Number) e.getValue()).doubleValue());
        }
        Map<String, Object> gs = Json.obj(o, "glyphs");
        if (gs != null) {
            for (Map.Entry<String, Object> e : gs.entrySet()) {
                List<Object> v = (List<Object>) e.getValue();
                Glyph g = new Glyph();
                g.x = ((Number) v.get(0)).intValue();
                g.y = ((Number) v.get(1)).intValue();
                g.w = ((Number) v.get(2)).intValue();
                g.h = ((Number) v.get(3)).intValue();
                g.offsetX = ((Number) v.get(4)).intValue();
                g.offsetY = ((Number) v.get(5)).intValue();
                glyphs.put(e.getKey().charAt(0), g);
            }
        }
    }

    /** The width of a character, per unit of text size. */
    public double advance(char c) {
        Double a = advances.get(c);
        return a != null ? a : fallback;
    }

    public Glyph glyph(char c) {
        return glyphs.get(c);
    }
}
