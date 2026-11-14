package apkpygame.tests;

import apkpygame.core.Entity;
import apkpygame.core.Game;
import apkpygame.core.GameException;
import apkpygame.core.Py;
import apkpygame.core.components.Canvas;
import apkpygame.core.render.Png;
import apkpygame.core.render.Texture;
import apkpygame.testkit.HeadlessPlatform;

import java.awt.image.BufferedImage;
import java.awt.image.IndexColorModel;
import java.io.ByteArrayOutputStream;
import java.util.zip.CRC32;
import java.util.zip.Deflater;
import javax.imageio.ImageIO;

/**
 * Canvas: pixels a game paints while it runs. The drawing calls, the PNG reader it starts from (checked against
 * the JDK's own reader, and against PNG files written here byte by byte for what ImageIO never writes), the
 * brush a finger paints with, and the state hash the parity check compares.
 */
public final class CanvasTests {
    private static int passed, failed;

    public static void main(String[] args) {
        run("set, get, fill, clear and what is outside", new Check() { public void run() throws Exception { pixels(); } });
        run("rect, line and circle land on the pixels they name", new Check() { public void run() throws Exception { shapes(); } });
        run("flood fills the area joined by sides, and only it", new Check() { public void run() throws Exception { flood(); } });
        run("a colour that is not one is a ValueError", new Check() { public void run() throws Exception { badColour(); } });
        run("png: what the JDK reads, for the files ImageIO writes", new Check() { public void run() throws Exception { pngLikeJdk(); } });
        run("png: grey, grey with alpha, 16 bits, tRNS and every filter", new Check() { public void run() throws Exception { pngByHand(); } });
        run("png: interlaced and broken files say G3025", new Check() { public void run() throws Exception { pngRefused(); } });
        run("a canvas starts from an image, or a frame of it", new Check() { public void run() throws Exception { startsFromImage(); } });
        run("stamp lays an image over, mixing what is see-through", new Check() { public void run() throws Exception { stamp(); } });
        run("the brush paints a stroke with no gaps, only from the canvas", new Check() { public void run() throws Exception { brush(); } });
        run("the pixels are in the state hash, and only when there is a canvas", new Check() { public void run() throws Exception { hash(); } });
        run("drawn as a sprite of its own pixels, counted when they change", new Check() { public void run() throws Exception { drawn(); } });
        System.out.println();
        System.out.println(passed + " passed, " + failed + " failed");
        System.exit(failed == 0 ? 0 : 1);
    }

    interface Check {
        void run() throws Exception;
    }

    private static void run(String name, Check check) {
        try {
            check.run();
            passed++;
            System.out.println("  ok    " + name);
        } catch (Throwable t) {
            failed++;
            System.out.println("  FAIL  " + name + ": " + t);
        }
    }

    private static void ok(boolean condition, String what) {
        if (!condition) throw new AssertionError(what);
    }

    private static void same(Object a, Object b, String what) {
        if (a == null ? b != null : !a.equals(b)) throw new AssertionError(what + ": " + a + " != " + b);
    }

    // ── a game with one canvas ───────────────────────────────────────────

    static final String GAME = "{\"format\":1,\"name\":\"t\",\"size\":[360,640],\"start_scene\":\"main\",\"seed\":7}";

    /** A scene with one entity at (x, y) holding a canvas declared by {@code canvas} (its JSON, without the type). */
    static Game game(String canvas, double x, double y, HeadlessPlatform.MemoryAssets files) {
        String scene = "{\"format\":1,\"kind\":\"2d\",\"entities\":[{\"name\":\"pad\",\"transform\":{\"x\":" + x
                + ",\"y\":" + y + "},\"components\":[{\"type\":\"Canvas\"" + (canvas.isEmpty() ? "" : "," + canvas)
                + "}]}]}";
        Game g = Game.load(new HeadlessPlatform(files.put("game.json", GAME).put("scenes/main.json", scene)));
        g.viewport.update(360, 640);                      // a surface pixel is a world unit
        g.start("main", "");
        g.step();
        return g;
    }

    static Game game(String canvas) {
        return game(canvas, 180, 320, new HeadlessPlatform.MemoryAssets());
    }

    static Canvas canvas(Game g) {
        Entity pad = g.scene().find("pad");
        return pad.get(Canvas.class);
    }

    // ── drawing ──────────────────────────────────────────────────────────

    static void pixels() {
        Canvas c = canvas(game("\"width\":8,\"height\":4"));
        ok(c.width == 8 && c.height == 4, "the size declared");
        same(c.get(0, 0), "#00000000", "see-through to start with");
        c.set(2, 1, "#ff8800");
        same(c.get(2, 1), "#ff8800", "what was set");
        c.set(3, 1, "#80ff0000");
        same(c.get(3, 1), "#80ff0000", "a see-through colour is kept, not mixed");
        c.set(-1, 0, "#ffffff");
        c.set(8, 0, "#ffffff");
        same(c.get(-1, 0), "", "outside");
        same(c.get(0, 4), "", "outside, below");
        c.fill("#123");
        same(c.get(7, 3), "#112233", "#rgb is #rrggbb");
        ok(c.count("#112233") == 32, "count");
        c.clear();
        ok(c.count("#00000000") == 32, "clear");
    }

    static void shapes() {
        Canvas c = canvas(game("\"width\":10,\"height\":10,\"color\":\"#000000\""));
        c.rect(-2, -2, 4, 3, "#ff0000");                   // clipped: x 0..1, y 0
        ok(c.count("#ff0000") == 2, "rect, clipped at the edges: " + c.count("#ff0000"));
        c.rect(5, 5, 0, 3, "#ff0000");
        ok(c.count("#ff0000") == 2, "an empty rect paints nothing");
        c.fill("#000000");
        c.line(0, 9, 9, 0, "#00ff00");
        ok(c.count("#00ff00") == 10, "a diagonal is one pixel per column");
        same(c.get(0, 9), "#00ff00", "first end");
        same(c.get(9, 0), "#00ff00", "last end");
        c.fill("#000000");
        c.line(1, 1, 7, 3, "#00ff00");
        ok(c.count("#00ff00") == 7, "a shallow line: one pixel per column: " + c.count("#00ff00"));
        c.fill("#000000");
        c.circle(5, 5, 0, "#0000ff");
        ok(c.count("#0000ff") == 1, "radius 0: the pixel");
        c.circle(5, 5, 1, "#0000ff");
        ok(c.count("#0000ff") == 9, "radius 1: 3 x 3");
        c.fill("#000000");
        c.circle(5, 5, 3, "#0000ff");
        ok(c.count("#0000ff") == 37, "radius 3: " + c.count("#0000ff"));
        same(c.get(5, 2), "#0000ff", "top");
        same(c.get(2, 2), "#000000", "not the corner");
    }

    static void flood() {
        Canvas c = canvas(game("\"width\":9,\"height\":9,\"color\":\"#ffffff\""));
        c.rect(2, 2, 5, 5, "#000000");
        c.rect(3, 3, 3, 3, "#ffffff");                     // a white room inside a black ring
        c.set(4, 4, "#000000");                            // with a pillar
        c.flood(3, 3, "#ff0000");
        ok(c.count("#ff0000") == 8, "the room, around the pillar: " + c.count("#ff0000"));
        same(c.get(0, 0), "#ffffff", "outside the ring is untouched");
        c.flood(0, 0, "#00ff00");
        ok(c.count("#00ff00") == 81 - 25, "around the ring: " + c.count("#00ff00"));
        c.set(1, 0, "#000000");
        c.set(0, 1, "#000000");
        c.flood(0, 0, "#0000ff");
        ok(c.count("#0000ff") == 1, "corners do not join: " + c.count("#0000ff"));
        c.flood(-1, 0, "#0000ff");
        c.flood(0, 0, "#0000ff");
        ok(c.count("#0000ff") == 1, "outside, and the same colour, change nothing");
    }

    static void badColour() {
        Canvas c = canvas(game("\"width\":2,\"height\":2"));
        try {
            c.set(0, 0, "red");
            throw new AssertionError("no error");
        } catch (Py.PyError e) {
            ok(e.getMessage().startsWith("ValueError: 'red' is not a colour"), e.getMessage());
        }
        c.set(0, 0, "#00000001");
        same(c.get(0, 0), "#00000001", "the one colour that looks like the error (alpha 00, blue 01) is kept");
    }

    // ── PNG ──────────────────────────────────────────────────────────────

    static byte[] write(BufferedImage image) throws Exception {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        ImageIO.write(image, "png", out);
        return out.toByteArray();
    }

    static void pngLikeJdk() throws Exception {
        java.util.Random r = new java.util.Random(5);
        BufferedImage argb = new BufferedImage(37, 23, BufferedImage.TYPE_INT_ARGB);
        BufferedImage rgb = new BufferedImage(37, 23, BufferedImage.TYPE_INT_RGB);
        byte[] reds = new byte[5], greens = new byte[5], blues = new byte[5], alphas = new byte[5];
        for (int i = 0; i < 5; i++) {
            reds[i] = (byte) (i * 60);
            greens[i] = (byte) (255 - i * 40);
            blues[i] = (byte) (i * 13);
            alphas[i] = (byte) (i == 0 ? 0 : i == 1 ? 128 : 255);
        }
        BufferedImage indexed = new BufferedImage(37, 23, BufferedImage.TYPE_BYTE_INDEXED,
                new IndexColorModel(8, 5, reds, greens, blues, alphas));
        BufferedImage binary = new BufferedImage(37, 23, BufferedImage.TYPE_BYTE_BINARY);
        for (int y = 0; y < 23; y++) {
            for (int x = 0; x < 37; x++) {
                // smooth runs and noise, so the writer picks every filter
                int smooth = ((x * 7) & 255) << 16 | ((y * 11) & 255) << 8 | ((x + y) * 5 & 255);
                int noise = r.nextInt();
                argb.setRGB(x, y, (y % 3 == 0 ? noise : smooth | 0xFF000000) & (x % 5 == 0 ? 0x80FFFFFF : 0xFFFFFFFF));
                rgb.setRGB(x, y, y % 2 == 0 ? noise : smooth);
                indexed.getRaster().setSample(x, y, 0, (x * y + x) % 5);
                binary.getRaster().setSample(x, y, 0, (x ^ y) & 1);
            }
        }
        BufferedImage[] all = {argb, rgb, indexed, binary};
        String[] names = {"RGBA", "RGB", "palette with alpha", "1 bit"};
        for (int k = 0; k < all.length; k++) {
            byte[] file = write(all[k]);
            BufferedImage jdk = ImageIO.read(new java.io.ByteArrayInputStream(file));
            Png png = Png.decode("x.png", file);
            ok(png.width == 37 && png.height == 23, names[k] + ": size");
            for (int y = 0; y < 23; y++) {
                for (int x = 0; x < 37; x++) {
                    int want = jdk.getRGB(x, y), got = png.argb[y * 37 + x];
                    if ((want >>> 24) == 0 && (got >>> 24) == 0) continue;          // see-through: its colour is moot
                    if (want != got) {
                        throw new AssertionError(names[k] + " at " + x + "," + y + ": " + Integer.toHexString(got)
                                + " != " + Integer.toHexString(want));
                    }
                }
            }
        }
    }

    /** A PNG written here: each row with the filter asked for, as the specification says. */
    static byte[] png(int w, int h, int depth, int type, byte[][] rows, int[] filters, byte[] plte, byte[] trns,
                      boolean interlaced) throws Exception {
        int channels = type == 0 || type == 3 ? 1 : type == 2 ? 3 : type == 4 ? 2 : 4;
        int step = Math.max(1, channels * depth / 8);
        ByteArrayOutputStream raw = new ByteArrayOutputStream();
        byte[] above = new byte[rows[0].length];
        for (int y = 0; y < h; y++) {
            byte[] row = rows[y];
            int f = filters[y % filters.length];
            raw.write(f);
            for (int i = 0; i < row.length; i++) {
                int x = row[i] & 255, a = i >= step ? row[i - step] & 255 : 0, b = above[i] & 255,
                        c = i >= step ? above[i - step] & 255 : 0;
                int p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
                int predict = f == 0 ? 0 : f == 1 ? a : f == 2 ? b : f == 3 ? (a + b) >> 1
                        : pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
                raw.write((x - predict) & 255);
            }
            above = row;
        }
        Deflater deflater = new Deflater();
        deflater.setInput(raw.toByteArray());
        deflater.finish();
        ByteArrayOutputStream z = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        while (!deflater.finished()) z.write(buf, 0, deflater.deflate(buf));
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.write(new byte[]{(byte) 137, 80, 78, 71, 13, 10, 26, 10});
        ByteArrayOutputStream ihdr = new ByteArrayOutputStream();
        int32(ihdr, w);
        int32(ihdr, h);
        ihdr.write(depth);
        ihdr.write(type);
        ihdr.write(0);
        ihdr.write(0);
        ihdr.write(interlaced ? 1 : 0);
        chunk(out, "IHDR", ihdr.toByteArray());
        if (plte != null) chunk(out, "PLTE", plte);
        if (trns != null) chunk(out, "tRNS", trns);
        chunk(out, "IDAT", z.toByteArray());
        chunk(out, "IEND", new byte[0]);
        return out.toByteArray();
    }

    static void int32(ByteArrayOutputStream out, int v) {
        out.write(v >>> 24);
        out.write(v >>> 16);
        out.write(v >>> 8);
        out.write(v);
    }

    static void chunk(ByteArrayOutputStream out, String type, byte[] data) throws Exception {
        int32(out, data.length);
        byte[] name = type.getBytes("US-ASCII");
        out.write(name);
        out.write(data);
        CRC32 crc = new CRC32();
        crc.update(name);
        crc.update(data);
        int32(out, (int) crc.getValue());
    }

    static void pngByHand() throws Exception {
        int[] every = {0, 1, 2, 3, 4};
        // grey 8 bits, with a tRNS key: 5 rows, one per filter
        byte[][] grey = new byte[5][6];
        for (int y = 0; y < 5; y++) for (int x = 0; x < 6; x++) grey[y][x] = (byte) (x * 40 + y * 9);
        Png p = Png.decode("g.png", png(6, 5, 8, 0, grey, every, null, new byte[]{0, 49}, false));
        same(Integer.toHexString(p.argb[2 * 6 + 1]), "ff3a3a3a", "grey 58 (row 2, Up filter)");
        same(Integer.toHexString(p.argb[1 * 6 + 1]), "313131", "the tRNS grey is see-through (49)");
        same(Integer.toHexString(p.argb[4 * 6 + 5]), "ffececec", "Paeth row (grey 5*40 + 4*9 = 236)");
        // grey 2 bits: 0..3 is 0, 85, 170, 255
        byte[][] two = {{(byte) 0b00011011, (byte) 0b11000000}};
        p = Png.decode("g2.png", png(5, 1, 2, 0, two, new int[]{1}, null, null, false));
        same(Integer.toHexString(p.argb[1]), "ff555555", "2 bits: 1 is 85");
        same(Integer.toHexString(p.argb[4]), "ffffffff", "2 bits: the fifth pixel, from the second byte");
        // grey and alpha, 16 bits: the high byte
        byte[][] ga16 = {{0x12, 0x34, (byte) 0x80, 0x00, (byte) 0xff, (byte) 0xff, 0x00, 0x01}};
        p = Png.decode("ga.png", png(2, 1, 16, 4, ga16, new int[]{4}, null, null, false));
        same(Integer.toHexString(p.argb[0]), "80121212", "16 bits keep the high byte");
        same(Integer.toHexString(p.argb[1]), "ffffff", "alpha 1 of 65535 is 0");
        // RGB 16 bits with a tRNS key, compared at 16 bits
        byte[][] rgb16 = {{0, 1, 0, 2, 0, 3, 0, 1, 0, 2, 0, 4}};
        p = Png.decode("rgb.png", png(2, 1, 16, 2, rgb16, new int[]{3}, null, new byte[]{0, 1, 0, 2, 0, 3}, false));
        ok((p.argb[0] >>> 24) == 0 && (p.argb[1] >>> 24) == 255, "the key matches all 16 bits, not the high byte");
        // palette, 4 bits, shorter tRNS: the rest is opaque
        byte[] plte = {(byte) 255, 0, 0, 0, (byte) 255, 0, 0, 0, (byte) 255};
        byte[][] pal = {{0x01, 0x20}};
        p = Png.decode("p.png", png(3, 1, 4, 3, pal, new int[]{0}, plte, new byte[]{0x40}, false));
        same(Integer.toHexString(p.argb[0]), "40ff0000", "index 0, alpha from tRNS");
        same(Integer.toHexString(p.argb[1]), "ff00ff00", "index 1, past tRNS: opaque");
        same(Integer.toHexString(p.argb[2]), "ff0000ff", "index 2");
    }

    static void pngRefused() throws Exception {
        byte[][] one = {{0}};
        String[] cases = {"interlaced", "not a PNG", "cut short"};
        byte[] good = png(1, 1, 8, 0, one, new int[]{0}, null, null, false);
        byte[][] files = {png(1, 1, 8, 0, one, new int[]{0}, null, null, true), "GIF89a".getBytes("US-ASCII"),
                java.util.Arrays.copyOf(good, good.length - 20)};
        for (int i = 0; i < files.length; i++) {
            try {
                Png.decode("bad.png", files[i]);
                throw new AssertionError(cases[i] + ": no error");
            } catch (GameException e) {
                ok("G3025".equals(e.code) && e.getMessage().contains("bad.png"), cases[i] + ": " + e.getMessage());
            }
        }
    }

    // ── images ───────────────────────────────────────────────────────────

    /** A 4 x 2 image: a row of red, green, blue, white; a row of half-see-through black. */
    static byte[] fourByTwo() throws Exception {
        BufferedImage image = new BufferedImage(4, 2, BufferedImage.TYPE_INT_ARGB);
        int[] top = {0xFFFF0000, 0xFF00FF00, 0xFF0000FF, 0xFFFFFFFF};
        for (int x = 0; x < 4; x++) {
            image.setRGB(x, 0, top[x]);
            image.setRGB(x, 1, 0x80000000);
        }
        return write(image);
    }

    static void startsFromImage() throws Exception {
        HeadlessPlatform.MemoryAssets files = new HeadlessPlatform.MemoryAssets().put("a.png", fourByTwo());
        Canvas c = canvas(game("\"image\":\"a.png\"", 180, 320, files));
        ok(c.width == 4 && c.height == 2, "the image's size: " + c.width + "x" + c.height);
        same(c.get(1, 0), "#00ff00", "its pixels");
        same(c.get(0, 1), "#80000000", "see-through kept");
        c = canvas(game("\"image\":\"a.png\",\"region\":[2,0,2,1],\"width\":3,\"height\":2,\"color\":\"#ffffff\"",
                180, 320, new HeadlessPlatform.MemoryAssets().put("a.png", fourByTwo())));
        same(c.get(0, 0), "#0000ff", "a frame: from its corner");
        same(c.get(1, 0), "#ffffff", "the frame's pixels");
        same(c.get(2, 0), "#ffffff", "past the frame: the colour");
        same(c.get(0, 1), "#ffffff", "below the frame: the colour");
    }

    static void stamp() throws Exception {
        HeadlessPlatform.MemoryAssets files = new HeadlessPlatform.MemoryAssets().put("a.png", fourByTwo());
        Canvas c = canvas(game("\"width\":5,\"height\":3,\"color\":\"#ffffff\"", 180, 320, files));
        c.stamp("a.png", 2, 1);
        same(c.get(2, 1), "#ff0000", "opaque pixels replace");
        same(c.get(4, 1), "#0000ff", "clipped at the right edge");
        same(c.get(2, 2), "#7f7f7f", "half black over white: grey");
        same(c.get(1, 1), "#ffffff", "left of it");
        c.fill("#00000000");
        c.stamp("a.png", 0, 0);
        same(c.get(0, 1), "#80000000", "over nothing: the image's own pixel");
    }

    // ── the brush ────────────────────────────────────────────────────────

    static void brush() {
        // 20 x 10 pixels, centred at (180, 320): its pixel (0, 0) is the world point (170, 315)
        Game g = game("\"width\":20,\"height\":10,\"brush\":\"#000000\"");
        Canvas c = canvas(g);
        g.input.pointerDown(1, 171.5, 316.5);              // pixel (1, 1)
        g.step();
        same(c.get(1, 1), "#000000", "the pixel under the finger");
        ok(c.changed, "changed in that step");
        g.input.pointerMove(1, 185.5, 322.5);              // pixel (15, 7): far, in one step
        g.step();
        ok(c.count("#000000") == 15, "a stroke with no gaps: " + c.count("#000000"));
        same(c.get(15, 7), "#000000", "to where the finger is");
        g.step();
        ok(!c.changed, "nothing new while the finger stands still");
        g.input.pointerMove(1, 260, 400);                  // off the canvas: the stroke goes on to the edge
        g.step();
        g.input.pointerUp(1, 260, 400);
        g.step();
        int painted = c.count("#000000");
        g.input.pointerDown(2, 100, 100);                  // a finger that goes down off the canvas
        g.step();
        g.input.pointerMove(2, 175.5, 320.5);
        g.step();
        ok(c.count("#000000") == painted, "does not paint when it comes over it");
        g.input.pointerUp(2, 175.5, 320.5);
        g.step();
        c.setBrush("#ff0000");
        c.brushSize = 3;
        g.input.pointerDown(3, 172.5, 322.5);              // pixel (2, 7)
        g.step();
        ok(c.count("#ff0000") == 9, "size 3: a 3 x 3 spot: " + c.count("#ff0000"));
        same(c.brushText(), "#ff0000", "the brush, as a script reads it");
        ok(c.pointerX() == 2 && c.pointerY() == 7, "the pixel under the finger: " + c.pointerX() + "," + c.pointerY());
        g.input.pointerUp(3, 172.5, 322.5);
        g.step();
        c.setBrush("");
        same(c.brushText(), "", "no brush");
        g.input.pointerDown(4, 175.5, 320.5);
        g.step();
        ok(!c.changed, "with no brush the finger paints nothing");
        ok(c.pointerX() == 5 && c.pointerY() == 5, "but where it is still says");
        g.input.pointerMove(4, 100, 100);
        g.step();
        ok(c.pointerX() == -1 && c.pointerY() == -1, "off the canvas: -1");
    }

    // ── checks ───────────────────────────────────────────────────────────

    static void hash() {
        Game a = game("\"width\":8,\"height\":8"), b = game("\"width\":8,\"height\":8");
        same(a.stateHash(), b.stateHash(), "the same game");
        canvas(a).set(3, 3, "#ff0000");
        ok(!a.stateHash().equals(b.stateHash()), "a painted pixel is a different state");
        canvas(b).set(3, 3, "#ff0000");
        same(a.stateHash(), b.stateHash(), "the same pixel again");
        Game plain = Game.load(new HeadlessPlatform(new HeadlessPlatform.MemoryAssets().put("game.json", GAME)
                .put("scenes/main.json", "{\"format\":1,\"kind\":\"2d\",\"entities\":[{\"name\":\"pad\",\"transform\":"
                        + "{\"x\":180,\"y\":320},\"components\":[]}]}")));
        plain.viewport.update(360, 640);
        plain.start("main", "");
        plain.step();
        Game withCanvas = game("\"width\":8,\"height\":8");
        ok(!plain.stateHash().equals(withCanvas.stateHash()), "the canvas's pixels count");
    }

    static void drawn() {
        Game g = game("\"width\":6,\"height\":4,\"color\":\"#ffffff\"");
        Canvas c = canvas(g);
        HeadlessPlatform p = (HeadlessPlatform) g.platform;
        g.render(360, 640);
        ok(p.drawn == 1, "one command drawn: " + p.drawn);
        Texture t = c.texture();
        ok(t.pixels != null && t.width == 6 && t.height == 4 && t.handle == null, "a texture of the canvas's own pixels");
        same(Integer.toHexString(t.pixels[0]), "ffffffff", "what it holds");
        int before = t.version;
        g.step();
        g.render(360, 640);
        ok(t.version == before, "nothing painted: the same version (a backend copies nothing)");
        c.set(0, 0, "#000000");
        ok(t.version != before, "painted: a new version");
        same(Integer.toHexString(t.pixels[0]), "ff000000", "the texture is the canvas's pixels, not a copy");
    }
}
