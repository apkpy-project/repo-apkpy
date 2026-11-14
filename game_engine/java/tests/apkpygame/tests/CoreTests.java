package apkpygame.tests;

import apkpygame.core.Component;
import apkpygame.core.Entity;
import apkpygame.core.Game;
import apkpygame.core.GameException;
import apkpygame.core.GameHost;
import apkpygame.core.Input;
import apkpygame.core.Scene;
import apkpygame.core.Viewport;
import apkpygame.core.components.Spin;
import apkpygame.core.json.Json;
import apkpygame.core.math.Color;
import apkpygame.core.math.Mat3;
import apkpygame.core.math.Rng;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderBackend;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;
import apkpygame.testkit.HeadlessPlatform;
import apkpygame.testkit.Snapshot;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Tests of the core, with no framework (plain Java 8, runs anywhere):
 *     python src/tools/test_engine.py
 */
public final class CoreTests {
    private static int passed, failed;

    public static void main(String[] args) {
        run("json round trip", new Check() { public void run() { json(); } });
        run("json errors say the line", new Check() { public void run() { jsonErrors(); } });
        run("mat3 transform and inverse", new Check() { public void run() { mat3(); } });
        run("viewport fit / fill / expand", new Check() { public void run() { viewport(); } });
        run("viewport: pixel art in the Previewer frames as on a 1080p phone", new Check() { public void run() { viewportPhone(); } });
        run("fixed steps", new Check() { public void run() { fixedSteps(); } });
        run("same steps, same state (determinism)", new Check() { public void run() { determinism(); } });
        run("rng sequence is pinned", new Check() { public void run() { rng(); } });
        run("spawn, destroy later, children go too", new Check() { public void run() { lifecycle(); } });
        run("input: surface to virtual to world", new Check() { public void run() { input(); } });
        run("render queue order", new Check() { public void run() { queueOrder(); } });
        run("render: scene to commands", new Check() { public void run() { rendering(); } });
        run("bundle errors have codes", new Check() { public void run() { bundleErrors(); } });
        run("unknown component is skipped", new Check() { public void run() { unknownComponent(); } });
        run("exit / openApp protocol", new Check() { public void run() { protocol(); } });
        run("OnTap: hit area and actions", new Check() { public void run() { onTap(); } });
        run("on_back runs the scene's actions", new Check() { public void run() { onBack(); } });
        run("only_if: the actions run when the condition holds", new Check() { public void run() { onlyIf(); } });
        run("a body stopped by a solid collider touches it: a ball breaks a brick", new Check() { public void run() { bricks(); } });
        run("deflect: a ball leaves a paddle turned by where it touched it", new Check() { public void run() { deflect(); } });
        run("texts: device language, default, fallback", new Check() { public void run() { texts(); } });
        System.out.println();
        System.out.println(passed + " passed, " + failed + " failed");
        System.exit(failed == 0 ? 0 : 1);
    }

    interface Check {
        void run();
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

    private static void near(double a, double b, String what) {
        if (Math.abs(a - b) > 1e-9) throw new AssertionError(what + ": " + a + " != " + b);
    }

    // ── fixtures ─────────────────────────────────────────────────────────

    static final String GAME = "{\"format\":1,\"name\":\"t\",\"size\":[360,640],\"start_scene\":\"main\",\"seed\":7}";

    static String scene(int boxes) {
        StringBuilder s = new StringBuilder("{\"format\":1,\"kind\":\"2d\",\"entities\":[");
        Rng rng = new Rng(3);
        for (int i = 0; i < boxes; i++) {
            if (i > 0) s.append(',');
            s.append("{\"name\":\"b").append(i).append("\",\"tags\":[\"box\"],\"transform\":{\"x\":")
                    .append(rng.range(0, 360)).append(",\"y\":").append(rng.range(0, 640))
                    .append(",\"scale\":0.5},\"components\":[{\"type\":\"Shape\",\"size\":[10,10]},")
                    .append("{\"type\":\"Spin\",\"speed\":").append(rng.range(-180, 180))
                    .append("},{\"type\":\"Mover\",\"velocity\":[").append(rng.range(-200, 200)).append(',')
                    .append(rng.range(-200, 200)).append("],\"bounce\":true}]}");
        }
        return s.append("]}").toString();
    }

    static HeadlessPlatform.MemoryAssets assets(int boxes) {
        return new HeadlessPlatform.MemoryAssets().put("game.json", GAME).put("scenes/main.json", scene(boxes));
    }

    static Game game(int boxes) {
        Game g = Game.load(new HeadlessPlatform(assets(boxes)));
        g.start("main", "");
        return g;
    }

    // ── tests ────────────────────────────────────────────────────────────

    static void json() {
        String text = "{\"a\":1.5,\"b\":[true,null,\"x\\\"y\\n\"],\"c\":{\"d\":-2e3},\"e\":\"\\u00e9\"}";
        Map<String, Object> o = Json.parseObject(text);
        near(Json.num(o, "a", 0), 1.5, "a");
        ok(Json.list(o, "b").get(0) == Boolean.TRUE, "b[0]");
        ok("x\"y\n".equals(Json.list(o, "b").get(2)), "escapes");
        near(Json.num(Json.obj(o, "c"), "d", 0), -2000, "exponent");
        ok("\u00e9".equals(o.get("e")), "unicode");
        ok(Json.stringify(Json.parse(Json.stringify(o))).equals(Json.stringify(o)), "stable");
        ok(Json.stringify(Json.parse("{\"n\":3}")).equals("{\"n\":3}"), "whole numbers without .0");
    }

    static void jsonErrors() {
        try {
            Json.parse("{\n\"a\": 1,\n\"b\": }");
            ok(false, "should fail");
        } catch (IllegalArgumentException e) {
            ok(e.getMessage().contains("line 3"), e.getMessage());
        }
    }

    static void mat3() {
        Mat3 m = new Mat3().setTransform(10, 20, 90, 2, 3);
        near(m.mapX(1, 0), 10, "x of (1,0) after 90 degrees");
        near(m.mapY(1, 0), 22, "y of (1,0): scale 2 rotated onto +y");
        Mat3 inv = new Mat3().set(m).invert();
        near(inv.mapX(m.mapX(5, 7), m.mapY(5, 7)), 5, "inverse x");
        near(inv.mapY(m.mapX(5, 7), m.mapY(5, 7)), 7, "inverse y");
        Mat3 parent = new Mat3().setTransform(100, 0, 0, 1, 1);
        Mat3 child = new Mat3().setTransform(5, 0, 0, 1, 1);
        near(new Mat3().set(parent).multiply(child).mapX(0, 0), 105, "parent * child");
    }

    static void viewport() {
        Viewport fit = new Viewport(360, 640, "fit");
        fit.update(1440, 3088);
        near(fit.scale, 4, "fit scale");
        near(fit.offsetY, (3088 - 2560) / 2.0, "fit bars");
        near(fit.toVirtualX(720), 180, "fit to virtual");
        Viewport fill = new Viewport(360, 640, "fill");
        fill.update(1440, 3088);
        near(fill.scale, 3088 / 640.0, "fill scale");
        Viewport expand = new Viewport(360, 640, "expand");
        expand.update(1440, 3088);
        near(expand.height, 772, "expand grows the visible height");
        near(expand.offsetY, 0, "expand has no bars");
    }

    static void viewportPhone() {
        // the phone (2400x1080, landscape), a 480x270 pixel-art game: 4x, 600x270 of world
        Viewport phone = new Viewport(480, 270, "expand", true);
        phone.update(2400, 1080);
        near(phone.scale, 4, "phone: whole scale");
        near(phone.width, 600, "phone: visible width");
        // the Previewer: the same phone in 914x411 window pixels; counted in window pixels it was 1x and 914 wide
        Viewport window = new Viewport(480, 270, "expand", true);
        window.update(914, 411);
        near(window.width, 914, "window pixels: 1x, the world the phone never shows");
        Viewport preview = new Viewport(480, 270, "expand", true, 1080);
        preview.update(914, 411);
        near(preview.scale * 1080 / 411.0, 4, "Previewer: 4 phone pixels per virtual pixel");
        near(preview.height, 270, "Previewer: the phone's height");
        near(preview.width, 914 / (411 / 270.0), "Previewer: the phone's width for that shape");
        Viewport fit = new Viewport(480, 270, "fit", true, 1080);
        fit.update(914, 411);
        near(fit.offsetY, 0, "fit: no bars top and bottom (1080 / 270 is whole)");
        Viewport fill = new Viewport(480, 270, "fill", true, 1080);
        fill.update(1000, 450);
        near(fill.scale * 1080 / 450.0, 5, "fill: the phone's 5x (2400 / 480), not 1000 / 480 rounded up to 3x");
        Viewport smooth = new Viewport(480, 270, "expand", false, 1080);
        smooth.update(914, 411);
        near(smooth.scale, 411 / 270.0, "no pixel art: the phone does not change anything");
    }

    static void fixedSteps() {
        Game g = game(1);
        ok(g.advance(0.1) == 5, "0.1 s at 60 Hz is 6 steps, capped at 5 per frame");
        Game h = game(1);
        int total = 0;
        for (int i = 0; i < 120; i++) total += h.advance(1.0 / 120);
        ok(total == 60, "120 frames at 120 Hz = 60 steps, got " + total);
        ok(h.steps() == 60, "steps()");
    }

    static void determinism() {
        String a = Snapshot.run(assets(300), "main", "", 600);
        String b = Snapshot.run(assets(300), "main", "", 600);
        String c = Snapshot.run(assets(300), "main", "", 601);
        ok(a.equals(b), "same steps: " + a + " vs " + b);
        ok(!a.equals(c), "one more step changes the state");
        System.out.println("        hash(300 boxes, 600 steps) = " + a);
    }

    static void rng() {
        Rng r = new Rng(42);
        long first = r.nextLong();
        ok(first == 0xbdd732262feb6e95L, "SplitMix64(42) first value changed: " + Long.toHexString(first));
        double d = new Rng(1).next();
        ok(d >= 0 && d < 1, "next in [0,1)");
    }

    static void lifecycle() {
        Game g = game(0);
        Scene s = g.scene();
        final List<String> log = new ArrayList<String>();
        Entity parent = new Entity("parent").addTag("p");
        Entity child = new Entity("child");
        parent.addChild(child);
        parent.add(new Component() {
            @Override protected void start() { log.add("start"); }
            @Override protected void update(double dt) { log.add("update"); }
            @Override protected void destroyed() { log.add("destroyed"); }
        });
        s.spawn(parent);
        ok(s.entityCount() == 2, "parent and child");
        g.step();
        ok(log.equals(java.util.Arrays.asList("start", "update")), "start before update: " + log);
        parent.destroy();
        ok(s.find("parent") == parent, "destroy waits for the end of the step");
        g.step();
        ok(s.find("parent") == null && s.find("child") == null, "both gone");
        ok(child.isDestroyed() && log.contains("destroyed"), "destroyed() called");
        ok(s.withTag("p").isEmpty(), "no tag left");
    }

    static void input() {
        Game g = game(0);
        g.viewport.update(1440, 3088);
        g.scene().camera.x = 180 + 100;        // camera moved 100 units right
        g.input.pointerDown(3, 720, 1544);     // the centre of the surface
        g.step();
        Input.Pointer p = g.input.pointer();
        ok(p != null && p.id == 3 && p.down && p.pressed, "pointer down");
        near(p.x, 180, "virtual x");
        near(p.y, 320, "virtual y");
        near(p.worldX, 280, "world x through the camera");
        g.input.pointerUp(3, 720, 1544);
        g.step();
        ok(p.released && !p.down, "released");
        g.step();
        ok(g.input.pointer() == null, "gone after the released step");
        g.input.keyDown("left");
        g.step();
        ok(g.input.wasKeyPressed("left") && g.input.axisX() == -1, "keys");
        g.step();
        ok(!g.input.wasKeyPressed("left") && g.input.isKeyDown("left"), "pressed only once");
    }

    static void queueOrder() {
        RenderQueue q = new RenderQueue();
        q.add(DrawCommand.Kind.RECT).layer = 2;
        DrawCommand b = q.add(DrawCommand.Kind.RECT);
        b.layer = 1;
        b.order = 5;
        DrawCommand c = q.add(DrawCommand.Kind.RECT);
        c.layer = 1;
        c.order = 5;
        q.add(DrawCommand.Kind.RECT).layer = 0;
        final List<DrawCommand> seen = new ArrayList<DrawCommand>();
        q.flush(new Recorder(seen));
        ok(seen.get(0).layer == 0 && seen.get(1) == b && seen.get(2) == c && seen.get(3).layer == 2,
                "layer, then order, then submission");
    }

    static void rendering() {
        Game g = game(0);
        Entity e = new Entity("e");
        e.transform.set(100, 50);
        e.add(apkpygame.core.components.Shape.rect(20, 10, Color.WHITE));
        g.scene().spawn(e);
        g.step();
        final List<DrawCommand> seen = new ArrayList<DrawCommand>();
        final List<double[]> where = new ArrayList<double[]>();
        HeadlessPlatform p = (HeadlessPlatform) g.platform;
        g.render(720, 1280);       // scale 2, no bars
        ok(p.drawn == 1, "one command drawn, got " + p.drawn);
        Recorder r = new Recorder(seen) {
            @Override public void draw(DrawCommand c) {
                super.draw(c);
                where.add(new double[]{c.matrix.mapX(c.x, c.y), c.matrix.mapY(c.x, c.y)});
            }
        };
        RenderQueue q = new RenderQueue();
        DrawCommand c = q.add(DrawCommand.Kind.RECT);
        c.matrix.setTransform(200, 100, 0, 2, 2);
        c.x = -10;
        c.y = -5;
        q.flush(r);
        near(where.get(0)[0], 180, "top-left x in pixels");
        near(where.get(0)[1], 90, "top-left y in pixels");
    }

    static void bundleErrors() {
        try {
            Game.load(new HeadlessPlatform(new HeadlessPlatform.MemoryAssets().put("game.json", GAME)))
                    .start("nope", "");
            ok(false, "should fail");
        } catch (GameException e) {
            ok(e.code.equals("G3002"), e.code);
            // what the phone shows ("error: " + e): ApkPy's prefix, as the build's errors
            ok(e.toString().startsWith("APKPY G3002: there is no scene 'nope'"), e.toString());
        }
        try {
            Game.load(new HeadlessPlatform(new HeadlessPlatform.MemoryAssets().put("game.json", "{\"format\":9}")));
            ok(false, "should fail");
        } catch (GameException e) {
            ok(e.code.equals("G3001"), e.code);
        }
    }

    static void unknownComponent() {
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets().put("game.json", GAME)
                .put("scenes/main.json", "{\"format\":1,\"entities\":[{\"name\":\"x\",\"components\":"
                        + "[{\"type\":\"FromTheFuture\"},{\"type\":\"Spin\",\"speed\":60}]}]}");
        Game g = Game.load(new HeadlessPlatform(a));
        g.start("main", "");
        Entity x = g.scene().find("x");
        ok(x != null && x.get(Spin.class) != null, "the known component stays");
        for (int i = 0; i < 60; i++) g.step();
        near(x.transform.rotation, 60, "spun 60 degrees in 1 s");
    }

    static void protocol() {
        Game g = game(0);
        final String[] got = new String[1];
        g.setHost(new GameHost() {
            @Override public void ended(String json) { got[0] = json; }
        });
        Map<String, Object> data = new java.util.LinkedHashMap<String, Object>();
        data.put("coins", 3.0);
        g.openApp("shop", data);
        ok(got[0].equals("{\"v\":1,\"action\":\"open\",\"screen\":\"shop\",\"data\":{\"coins\":3},\"suspended\":true}"),
                got[0]);
        ok(g.advance(1) == 0, "an ended game does not step");
        g.resumeAfterOpen();
        ok(g.advance(1.0 / 60) == 1, "resumed");
        g.exit(null);
        ok(got[0].equals("{\"v\":1,\"action\":\"exit\",\"result\":{},\"suspended\":false}"), got[0]);
    }

    static void onTap() {
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets().put("game.json", GAME)
                .put("pop.wav", new byte[]{1})
                .put("scenes/main.json", "{\"format\":1,\"entities\":[{\"name\":\"coin\",\"transform\":"
                        + "{\"x\":100,\"y\":100,\"rotation\":45},\"components\":[{\"type\":\"Shape\",\"size\":[40,20]},"
                        + "{\"type\":\"OnTap\",\"actions\":[{\"do\":\"sound\",\"sound\":\"pop.wav\"},"
                        + "{\"do\":\"store_add\",\"key\":\"coins\",\"amount\":2},{\"do\":\"destroy\"}]}]}]}");
        Game g = Game.load(new HeadlessPlatform(a));
        g.start("main", "");
        g.viewport.update(360, 640);
        g.step();
        g.input.pointerDown(0, 100 + 18, 100);     // outside: the 40x20 box is turned 45 degrees
        g.step();
        ok(g.scene().find("coin") != null, "a miss does nothing");
        g.input.pointerUp(0, 0, 0);
        g.step();
        g.input.pointerDown(0, 100 + 6, 100 + 6);   // inside, along the rotated long side
        g.step();
        ok(g.scene().find("coin") == null, "tapped: destroyed");
        ok(g.platform.store().get("coins").equals("2"), "store_add: " + g.platform.store().get("coins"));
    }

    static void onBack() {
        final String[] got = new String[1];
        GameHost host = new GameHost() {
            @Override public void ended(String json) { got[0] = json; }
        };
        Game plain = game(0);
        plain.setHost(host);
        plain.back();
        ok(got[0].contains("\"action\":\"exit\"") && got[0].contains("\"reason\":\"back\""), got[0]);
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets().put("game.json", GAME)
                .put("scenes/main.json", "{\"format\":1,\"on_back\":[{\"do\":\"store_set\",\"key\":\"k\","
                        + "\"value\":\"v\"},{\"do\":\"open\",\"screen\":\"pause_menu\"}],\"entities\":[]}");
        Game g = Game.load(new HeadlessPlatform(a));
        g.start("main", "");
        g.setHost(host);
        g.back();
        ok(got[0].contains("\"screen\":\"pause_menu\"") && got[0].contains("\"suspended\":true"), got[0]);
        ok(g.platform.store().get("k").equals("v"), "actions run in order");
    }

    static void onlyIf() {
        String door = "{\"name\":\"door\",\"tags\":[\"door\"],\"transform\":{\"x\":100,\"y\":100},\"components\":["
                + "{\"type\":\"Shape\",\"size\":[40,40]},{\"type\":\"OnTap\",\"actions\":["
                + "{\"do\":\"if\",\"condition\":{\"var\":\"keys\",\"op\":\">=\",\"value\":1},\"actions\":["
                + "{\"do\":\"var_add\",\"var\":\"keys\",\"amount\":-1},{\"do\":\"destroy\"}]},"
                + "{\"do\":\"if\",\"condition\":{\"count\":\"door\",\"op\":\"==\",\"value\":1},\"actions\":["
                + "{\"do\":\"var_add\",\"var\":\"tries\"}]}]}]}";
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets()
                .put("game.json", "{\"format\":1,\"name\":\"t\",\"size\":[360,640],\"start_scene\":\"main\","
                        + "\"vars\":{\"keys\":0,\"tries\":0}}")
                .put("scenes/main.json", "{\"format\":1,\"entities\":[" + door + "]}");
        Game g = Game.load(new HeadlessPlatform(a));
        g.start("main", "");
        g.viewport.update(360, 640);
        g.step();
        g.input.pointerDown(0, 100, 100);
        g.step();
        g.input.pointerUp(0, 100, 100);
        g.step();
        ok(g.scene().find("door") != null, "no key: the door stays");
        near(g.var("tries"), 1, "the other only_if ran: one door");
        g.setVar("keys", 1);
        g.input.pointerDown(0, 100, 100);
        g.step();
        ok(g.scene().find("door") == null, "a key: the door opens");
        near(g.var("keys"), 0, "and the key is used");
        near(g.var("tries"), 1, "count(door) leaves out the door destroyed a moment ago");
    }

    static void bricks() {
        String ball = "{\"name\":\"ball\",\"tags\":[\"ball\"],\"transform\":{\"x\":100,\"y\":200},\"components\":["
                + "{\"type\":\"Collider\",\"shape\":\"box\",\"size\":[8,8]},"
                + "{\"type\":\"Body\",\"velocity\":[0,-300],\"bounce\":1}]}";
        String brick = "{\"name\":\"brick\",\"tags\":[\"brick\"],\"transform\":{\"x\":100,\"y\":100},\"components\":["
                + "{\"type\":\"Collider\",\"size\":[32,12],\"solid\":true},"
                + "{\"type\":\"OnCollide\",\"tag\":\"ball\",\"side\":\"bottom\",\"actions\":["
                + "{\"do\":\"destroy\"},{\"do\":\"var_add\",\"var\":\"score\"}]}]}";
        String floor = "{\"name\":\"floor\",\"transform\":{\"x\":180,\"y\":400},\"components\":["
                + "{\"type\":\"Collider\",\"size\":[360,20],\"solid\":true}]}";
        String runner = "{\"name\":\"runner\",\"tags\":[\"runner\"],\"transform\":{\"x\":40,\"y\":300},\"components\":["
                + "{\"type\":\"Collider\",\"size\":[10,10]},{\"type\":\"Body\",\"gravity\":900},"
                + "{\"type\":\"OnCollide\",\"tag\":\"\",\"actions\":[{\"do\":\"var_add\",\"var\":\"landed\"}]}]}";
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets()
                .put("game.json", "{\"format\":1,\"name\":\"t\",\"size\":[360,640],\"start_scene\":\"main\","
                        + "\"vars\":{\"score\":0,\"landed\":0}}")
                .put("scenes/main.json", "{\"format\":1,\"entities\":[" + ball + "," + brick + "," + floor + "," + runner + "]}");
        Game g = Game.load(new HeadlessPlatform(a));
        g.start("main", "");
        for (int i = 0; i < 60; i++) g.step();
        ok(g.scene().find("brick") == null, "the ball broke the brick");
        near(g.var("score"), 1, "once");
        apkpygame.core.physics2d.Body b = g.scene().find("ball").get(apkpygame.core.physics2d.Body.class);
        ok(b.vy > 0, "and bounced back down: " + b.vy);
        near(g.var("landed"), 1, "resting on the floor touches it once, not every step");
    }

    /** The ball's velocity after it fell on a paddle 80 wide at x = 180, from this x. */
    static double[] offPaddle(double x) {
        String ball = "{\"name\":\"ball\",\"tags\":[\"ball\"],\"transform\":{\"x\":" + x + ",\"y\":300},\"components\":["
                + "{\"type\":\"Collider\",\"size\":[8,8]},{\"type\":\"Body\",\"velocity\":[0,300],\"bounce\":1},"
                + "{\"type\":\"OnCollide\",\"tag\":\"paddle\",\"actions\":[{\"do\":\"deflect\",\"angle\":60}]}]}";
        String paddle = "{\"name\":\"paddle\",\"tags\":[\"paddle\"],\"transform\":{\"x\":180,\"y\":400},\"components\":["
                + "{\"type\":\"Collider\",\"size\":[80,12],\"solid\":true}]}";
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets()
                .put("game.json", "{\"format\":1,\"name\":\"t\",\"size\":[360,640],\"start_scene\":\"main\"}")
                .put("scenes/main.json", "{\"format\":1,\"entities\":[" + ball + "," + paddle + "]}");
        Game g = Game.load(new HeadlessPlatform(a));
        g.start("main", "");
        for (int i = 0; i < 30; i++) g.step();
        apkpygame.core.physics2d.Body b = g.scene().find("ball").get(apkpygame.core.physics2d.Body.class);
        return new double[]{b.vx, b.vy};
    }

    static void deflect() {
        double[] middle = offPaddle(180), left = offPaddle(160), end = offPaddle(220), past = offPaddle(222);
        near(middle[0], 0, "from the middle, straight back");
        near(middle[1], -300, "at its own speed");
        near(left[0], -300 * StrictMath.sin(StrictMath.toRadians(30)), "half way to the left end: 30 degrees to the left");
        near(left[1], -300 * StrictMath.cos(StrictMath.toRadians(30)), "and up");
        near(end[0], 300 * StrictMath.sin(StrictMath.toRadians(60)), "at the end: the whole angle");
        near(StrictMath.sqrt(end[0] * end[0] + end[1] * end[1]), 300, "the speed stays");
        near(past[0], end[0], "past the end (its edge on the paddle's): no more than the angle");
    }

    static void texts() {
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets().put("game.json", GAME)
                .put("texts.json", "{\"default\":\"en\",\"languages\":{\"en\":{\"hi\":\"Hello\",\"only\":\"EN\"},"
                        + "\"pt\":{\"hi\":\"Ola\"}}}")
                .put("scenes/main.json", "{\"format\":1,\"entities\":[{\"name\":\"t\",\"components\":"
                        + "[{\"type\":\"Text\",\"key\":\"hi\",\"text\":\"Hello\"}]}]}");
        HeadlessPlatform pt = new HeadlessPlatform(a);
        pt.language = "pt";
        Game g = Game.load(pt);
        g.start("main", "");
        ok(g.scene().find("t").get(apkpygame.core.components.Text.class).text.equals("Ola"), "device language");
        ok(g.text("only", "x").equals("EN"), "falls back to the default language");
        ok(g.text("missing", "x").equals("x"), "then to the fallback");
    }

    static class Recorder implements RenderBackend {
        final List<DrawCommand> seen;

        Recorder(List<DrawCommand> seen) {
            this.seen = seen;
        }

        @Override public Texture loadTexture(String path, byte[] data) { return null; }
        @Override public Object loadFont(String path, byte[] data) { return null; }
        @Override public void begin(int w, int h, int clear) { }
        @Override public void draw(DrawCommand c) { seen.add(c); }
        @Override public void end() { }
    }
}
