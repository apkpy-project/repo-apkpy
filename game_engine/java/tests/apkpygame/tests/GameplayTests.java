package apkpygame.tests;

import apkpygame.core.Entity;
import apkpygame.core.Game;
import apkpygame.core.GameHost;
import apkpygame.core.components.Animator;
import apkpygame.core.components.Emitter;
import apkpygame.core.components.Sprite;
import apkpygame.core.components.Text;
import apkpygame.core.components.Tween;
import apkpygame.core.physics2d.Body;
import apkpygame.testkit.HeadlessPlatform;
import apkpygame.testkit.Snapshot;

/**
 * Games without code: physics, collisions, rules, spawning, controllers, animation, UI.
 *     python src/tools/test_engine.py
 */
public final class GameplayTests {
    private static int passed, failed;

    public static void main(String[] args) {
        run("body falls and lands on solid tiles", new Check() { public void run() { landsOnTiles(); } });
        run("walls stop a body; no tunnelling at speed", new Check() { public void run() { walls(); } });
        run("platformer: jump from the floor, not in the air", new Check() { public void run() { jumps(); } });
        run("collisions: tags, sides (stomp), actions on other", new Check() { public void run() { collide(); } });
        run("rules fire once when they become true", new Check() { public void run() { rules(); } });
        run("spawner: every, limit, total, seeded", new Check() { public void run() { spawner(); } });
        run("lifetime, timer, tween", new Check() { public void run() { timeThings(); } });
        run("text shows variables; exit substitutes them", new Check() { public void run() { varsInText(); } });
        run("goto scene keeps variables", new Check() { public void run() { gotoScene(); } });
        run("touch button holds a virtual key (ui coordinates)", new Check() { public void run() { touchButton(); } });
        run("animator follows the controller state", new Check() { public void run() { animator(); } });
        run("emitter burst lives and dies", new Check() { public void run() { emitter(); } });
        run("camera follows within bounds", new Check() { public void run() { camera(); } });
        run("a physics game is deterministic", new Check() { public void run() { deterministic(); } });
        run("a busy physics step allocates (almost) nothing", new Check() { public void run() { noGarbage(); } });
        run("culling: what is off the surface is not drawn", new Check() { public void run() { culling(); } });
        run("2.5D: a tap in the middle of the view is the point the camera looks at", new Check() { public void run() { pick25d(); } });
        run("2.5D: GridController walks cell by cell, turns on a short press, stops at solid", new Check() { public void run() { grid(); } });
        run("2.5D: a solid Block stops the walk at every cell it is on", new Check() { public void run() { gridBlock(); } });
        run("2.5D: a game with taps comes back from its journal", new Check() { public void run() { journal25d(); } });
        run("2.5D: Raster3D draws a quad and keeps the ground under the camera", new Check() { public void run() { raster(); } });
        run("a suspended game comes back from its journal (process death)", new Check() { public void run() { journal(); } });
        run("a journal that does not reach the saved world is refused (G3030)", new Check() { public void run() { journalMismatch(); } });
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

    private static void ok(boolean c, String what) {
        if (!c) throw new AssertionError(what);
    }

    private static void near(double a, double b, double eps, String what) {
        if (Math.abs(a - b) > eps) throw new AssertionError(what + ": " + a + " != " + b);
    }

    static final String GAME = "{\"format\":1,\"size\":[320,240],\"vars\":{\"lives\":3}}";
    /** 20x8 tiles of 16: floor on row 6, a wall at column 12 (rows 3..5). */
    static String map() {
        StringBuilder solid = new StringBuilder(), data = new StringBuilder();
        for (int r = 0; r < 8; r++) {
            for (int c = 0; c < 20; c++) {
                boolean s = r == 6 || (c == 12 && r >= 3 && r <= 5);
                if (r + c > 0) {
                    solid.append(',');
                    data.append(',');
                }
                solid.append(s ? 1 : 0);
                data.append(s ? 1 : 0);
            }
        }
        return "{\"format\":1,\"tile_w\":16,\"tile_h\":16,\"cols\":20,\"rows\":8,\"image\":\"t.png\",\"columns\":1,"
                + "\"firstgid\":1,\"layers\":[{\"name\":\"g\",\"data\":[" + data + "]}],\"solid\":[" + solid + "]}";
    }

    static final String MAP_ENTITY = "{\"name\":\"map\",\"components\":[{\"type\":\"Tilemap\",\"map\":\"tilemaps/m.json\"}]}";

    static Game game(String sceneJson) {
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets().put("game.json", GAME)
                .put("tilemaps/m.json", map()).put("t.png", png(16, 16)).put("s.png", png(64, 16))
                .put("scenes/main.json", sceneJson).put("scenes/two.json", "{\"format\":1,\"entities\":[]}");
        Game g = Game.load(new HeadlessPlatform(a));
        g.start("main", "");
        g.viewport.update(320, 240);
        return g;
    }

    static String scene(String entities) {
        return "{\"format\":1,\"entities\":[" + entities + "]}";
    }

    static byte[] png(int w, int h) {
        byte[] d = new byte[33];
        d[0] = (byte) 0x89; d[1] = 'P'; d[2] = 'N'; d[3] = 'G';
        d[16] = (byte) (w >> 24); d[17] = (byte) (w >> 16); d[18] = (byte) (w >> 8); d[19] = (byte) w;
        d[20] = (byte) (h >> 24); d[21] = (byte) (h >> 16); d[22] = (byte) (h >> 8); d[23] = (byte) h;
        return d;
    }

    static void steps(Game g, int n) {
        for (int i = 0; i < n; i++) g.step();
    }

    static final String PLAYER = "{\"name\":\"p\",\"tags\":[\"player\"],\"transform\":{\"x\":40,\"y\":20},\"components\":["
            + "{\"type\":\"Collider\",\"size\":[12,14]},{\"type\":\"Body\",\"gravity\":900},"
            + "{\"type\":\"PlatformerController\",\"speed\":100,\"jump\":300}]}";

    // ── tests ────────────────────────────────────────────────────────────

    static void landsOnTiles() {
        Game g = game(scene(MAP_ENTITY + "," + PLAYER));
        steps(g, 120);
        Entity p = g.scene().find("p");
        Body b = p.get(Body.class);
        ok(b.onFloor, "on the floor");
        near(p.transform.y + 7, 96, 1e-6, "feet exactly on the top of row 6");
        near(b.vy, 0, 1e-9, "stopped");
    }

    static void walls() {
        Game g = game(scene(MAP_ENTITY + ",{\"name\":\"b\",\"transform\":{\"x\":150,\"y\":88},\"components\":["
                + "{\"type\":\"Collider\",\"size\":[8,8]},{\"type\":\"Body\",\"velocity\":[3000,0]}]}"));
        steps(g, 1);
        Entity b = g.scene().find("b");
        ok(b.get(Body.class).onWallRight, "onWallRight in the step it hits");
        steps(g, 9);
        near(b.transform.x + 4, 192, 1e-6, "stopped at the wall's left side (column 12) even at 3000 u/s");
    }

    static void jumps() {
        Game g = game(scene(MAP_ENTITY + "," + PLAYER));
        steps(g, 120);
        Entity p = g.scene().find("p");
        double floorY = p.transform.y;
        g.input.keyDown("space");
        steps(g, 10);
        ok(p.transform.y < floorY - 20, "jumped: " + (floorY - p.transform.y));
        g.input.keyUp("space");
        steps(g, 2);
        g.input.keyDown("space");             // in the air: no double jump
        steps(g, 2);
        Body b = p.get(Body.class);
        ok(b.vy > -300 + 1, "no jump in the air");
        g.input.keyUp("space");
        steps(g, 120);
        ok(b.onFloor, "back down");
        g.input.keyDown("right");
        steps(g, 30);
        ok(p.transform.x > 40 + 40, "ran right: " + p.transform.x);
    }

    static void collide() {
        String enemy = "{\"name\":\"e\",\"tags\":[\"enemy\"],\"transform\":{\"x\":100,\"y\":88},\"components\":["
                + "{\"type\":\"Collider\",\"size\":[16,16]},"
                + "{\"type\":\"OnCollide\",\"tag\":\"player\",\"side\":\"top\",\"actions\":[{\"do\":\"destroy\"},"
                + "{\"do\":\"var_add\",\"var\":\"score\",\"amount\":10},{\"do\":\"impulse\",\"target\":\"other\",\"velocity\":[0,-200]}]},"
                + "{\"type\":\"OnCollide\",\"tag\":\"player\",\"side\":\"sides\",\"actions\":[{\"do\":\"var_add\",\"var\":\"lives\",\"amount\":-1},"
                + "{\"do\":\"respawn\",\"target\":\"other\"}]}]}";
        String faller = "{\"name\":\"p\",\"tags\":[\"player\"],\"transform\":{\"x\":100,\"y\":40},\"components\":["
                + "{\"type\":\"Collider\",\"size\":[12,14]},{\"type\":\"Body\",\"gravity\":900}]}";
        Game g = game(scene(MAP_ENTITY + "," + enemy + "," + faller));
        steps(g, 60);
        ok(g.scene().find("e") == null, "stomped from the top: destroyed");
        near(g.var("score"), 10, 0, "score");
        near(g.var("lives"), 3, 0, "no life lost");
        String walker = "{\"name\":\"p\",\"tags\":[\"player\"],\"transform\":{\"x\":60,\"y\":88},\"components\":["
                + "{\"type\":\"Collider\",\"size\":[12,14]},{\"type\":\"Body\",\"gravity\":900,\"velocity\":[120,0]}]}";
        Game h = game(scene(MAP_ENTITY + "," + enemy + "," + walker));
        steps(h, 30);
        ok(h.scene().find("e") != null, "side hit: the enemy stays");
        near(h.var("lives"), 2, 0, "a life lost");
        near(h.scene().find("p").transform.x, 60, 2.5, "respawned");
    }

    static void rules() {
        Game g = game("{\"format\":1,\"rules\":[{\"var\":\"lives\",\"op\":\"<=\",\"value\":0,\"actions\":"
                + "[{\"do\":\"var_add\",\"var\":\"fired\",\"amount\":1}]},{\"count\":\"coin\",\"op\":\"==\",\"value\":0,"
                + "\"actions\":[{\"do\":\"exit\",\"result\":{\"score\":\"{score}\",\"text\":\"got {score}\"}}]}],"
                + "\"entities\":[{\"name\":\"c\",\"tags\":[\"coin\"]}]}");
        final String[] got = new String[1];
        g.setHost(new GameHost() { public void ended(String json) { got[0] = json; } });
        g.setVar("lives", 0);
        steps(g, 5);
        near(g.var("fired"), 1, 0, "fired once, not every step");
        g.setVar("score", 7);
        g.scene().find("c").destroy();
        steps(g, 2);
        ok(got[0] != null && got[0].contains("\"score\":7,\"text\":\"got 7\""), String.valueOf(got[0]));
    }

    static void spawner() {
        String tpl = "{\"name\":\"rock\",\"tags\":[\"rock\"],\"components\":[]}";
        Game g = game(scene("{\"name\":\"s\",\"transform\":{\"x\":10,\"y\":10},\"components\":[{\"type\":\"Spawner\","
                + "\"entity\":" + tpl + ",\"every\":0.5,\"area\":[0,0,100,0],\"limit\":3,\"total\":5}]}"));
        steps(g, 100);
        ok(g.scene().count("rock") == 3, "limit 3 alive: " + g.scene().count("rock"));
        for (Entity e : g.scene().withTag("rock")) {
            ok(e.transform.x >= 10 && e.transform.x <= 110 && e.transform.y == 10, "inside the area");
            e.destroy();
        }
        steps(g, 600);
        ok(g.scene().count("rock") == 2, "total 5: 3 + 2: " + g.scene().count("rock"));
    }

    static void timeThings() {
        Game g = game(scene("{\"name\":\"a\",\"components\":[{\"type\":\"Lifetime\",\"seconds\":0.5,"
                + "\"actions\":[{\"do\":\"var_add\",\"var\":\"gone\"}]}]},"
                + "{\"name\":\"t\",\"components\":[{\"type\":\"Timer\",\"every\":0.25,\"actions\":[{\"do\":\"var_add\",\"var\":\"ticks\"}]}]},"
                + "{\"name\":\"w\",\"components\":[{\"type\":\"Shape\"},{\"type\":\"Tween\",\"property\":\"x\",\"to\":100,"
                + "\"duration\":1,\"ease\":\"linear\",\"mode\":\"once\"}]}"));
        steps(g, 61);
        ok(g.scene().find("a") == null && g.var("gone") == 1, "lifetime");
        near(g.var("ticks"), 4, 0, "timer 4 times in 1 s");
        near(g.scene().find("w").transform.x, 100, 1e-9, "tween reached its end");
        ok(g.scene().find("w").get(Tween.class) != null, "tween stays");
    }

    static void varsInText() {
        Game g = game(scene("{\"name\":\"hud\",\"ui\":true,\"components\":[{\"type\":\"Text\",\"text\":\"Lives {lives} / {nope} {x\"}]}"));
        steps(g, 1);
        Text t = g.scene().find("hud").get(Text.class);
        ok(t.shown().equals("Lives 3 / 0 {x"), t.shown());
        g.setVar("lives", 2.5);
        ok(t.shown().equals("Lives 2.5 / 0 {x"), t.shown());
    }

    static void gotoScene() {
        Game g = game(scene("{\"name\":\"t\",\"components\":[{\"type\":\"Timer\",\"every\":0.1,\"repeat\":false,"
                + "\"actions\":[{\"do\":\"var_add\",\"var\":\"score\",\"amount\":5},{\"do\":\"goto\",\"scene\":\"two\"}]}]}"));
        steps(g, 10);
        ok(g.scene().name.equals("two"), "in scene two");
        near(g.var("score"), 5, 0, "score kept");
        near(g.var("lives"), 3, 0, "lives kept");
    }

    static void touchButton() {
        Game g = game(scene(MAP_ENTITY + "," + PLAYER + ",{\"name\":\"jump\",\"ui\":true,\"transform\":{\"x\":290,\"y\":210},"
                + "\"components\":[{\"type\":\"Shape\",\"shape\":\"circle\",\"radius\":20},{\"type\":\"TouchButton\",\"key\":\"jump\"}]}"));
        g.scene().camera.x = 500;          // a moved camera must not change where the ui button is
        steps(g, 120);
        Entity p = g.scene().find("p");
        double floorY = p.transform.y;
        g.input.pointerDown(0, 290, 210);
        steps(g, 12);
        ok(p.transform.y < floorY - 15, "the button made it jump: " + (floorY - p.transform.y));
    }

    static void animator() {
        String anims = "\"animations\":{\"idle\":{\"frames\":[[0,0,16,16]],\"fps\":4},"
                + "\"run\":{\"frames\":[[16,0,16,16],[32,0,16,16]],\"fps\":10}}";
        Game g = game(scene(MAP_ENTITY + ",{\"name\":\"p\",\"transform\":{\"x\":40,\"y\":80},\"components\":["
                + "{\"type\":\"Sprite\",\"image\":\"s.png\",\"region\":[0,0,16,16]},{\"type\":\"Collider\",\"size\":[12,14]},"
                + "{\"type\":\"Body\",\"gravity\":900},{\"type\":\"PlatformerController\"},{\"type\":\"Animator\"," + anims + "}]}"));
        steps(g, 60);
        Sprite s = g.scene().find("p").get(Sprite.class);
        ok(s.srcX == 0, "idle frame");
        g.input.keyDown("right");
        steps(g, 3);
        ok(g.scene().find("p").get(Animator.class).current.equals("run") && s.srcX >= 16, "run frames: " + s.srcX);
        g.input.keyUp("right");
        g.input.keyDown("left");
        steps(g, 2);
        ok(s.flipX, "faces left");
    }

    static void emitter() {
        Game g = game(scene("{\"name\":\"boom\",\"components\":[{\"type\":\"Emitter\",\"burst\":30,\"lifetime\":[0.2,0.4]}]}"));
        steps(g, 1);
        ok(g.scene().find("boom").get(Emitter.class).alive() == 30, "burst 30");
        steps(g, 30);
        ok(g.scene().find("boom").get(Emitter.class).alive() == 0, "all gone");
    }

    static void camera() {
        Game g = game("{\"format\":1,\"camera\":{\"follow\":\"p\",\"bounds\":[0,0,320,128]},\"entities\":["
                + MAP_ENTITY + "," + PLAYER + "]}");
        steps(g, 60);
        near(g.scene().camera.x, 160, 1e-9, "x clamped to the bounds (player at 40, view 320 wide)");
        near(g.scene().camera.y, 64, 1e-9, "y: bounds smaller than the view: centred");
    }

    static void deterministic() {
        String sceneJson = "{\"format\":1,\"entities\":[" + MAP_ENTITY + ",{\"name\":\"s\",\"transform\":{\"x\":0,\"y\":0},"
                + "\"components\":[{\"type\":\"Spawner\",\"every\":0.2,\"area\":[0,0,300,40],\"entity\":"
                + "{\"name\":\"ball\",\"components\":[{\"type\":\"Collider\",\"shape\":\"circle\",\"radius\":4},"
                + "{\"type\":\"Body\",\"gravity\":500,\"bounce\":0.6,\"velocity\":[60,0]}]}}]}]}";
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets().put("game.json", GAME)
                .put("tilemaps/m.json", map()).put("t.png", png(16, 16)).put("scenes/main.json", sceneJson);
        String h1 = Snapshot.run(a, "main", "", 900), h2 = Snapshot.run(a, "main", "", 900);
        ok(h1.equals(h2), h1 + " vs " + h2);
        System.out.println("        hash(spawner + bouncing bodies + tiles, 900 steps) = " + h1);
    }

    static HeadlessPlatform.MemoryAssets suspendable() {
        String coin = "{\"name\":\"coin\",\"transform\":{\"x\":200,\"y\":60},\"components\":[{\"type\":\"Shape\","
                + "\"size\":[30,30]},{\"type\":\"OnTap\",\"actions\":[{\"do\":\"store_add\",\"key\":\"coins\",\"amount\":2},"
                + "{\"do\":\"var_add\",\"var\":\"lives\",\"amount\":1},{\"do\":\"destroy\"}]}]}";
        String spawner = "{\"name\":\"s\",\"components\":[{\"type\":\"Spawner\",\"every\":0.3,\"area\":[0,0,300,40],"
                + "\"entity\":{\"name\":\"ball\",\"components\":[{\"type\":\"Collider\",\"shape\":\"circle\",\"radius\":4},"
                + "{\"type\":\"Body\",\"gravity\":500,\"bounce\":0.6}]}}]}";
        String sceneJson = "{\"format\":1,\"on_back\":[{\"do\":\"open\",\"screen\":\"pause_menu\"}],\"entities\":["
                + MAP_ENTITY + "," + PLAYER + "," + coin + "," + spawner + "]}";
        return new HeadlessPlatform.MemoryAssets().put("game.json", GAME).put("tilemaps/m.json", map())
                .put("t.png", png(16, 16)).put("scenes/main.json", sceneJson);
    }

    /** A run with keys, a tap, a store_add, the random spawner and two pauses (Back -> open_app). */
    static Game playedAndSuspended(HeadlessPlatform.MemoryAssets a) {
        Game g = Game.load(new HeadlessPlatform(a));
        g.start("main", "");
        g.viewport.update(640, 480);                  // surface pixels: twice the virtual size
        steps(g, 30);
        g.input.keyDown("right");
        steps(g, 40);
        g.input.keyUp("right");
        g.back();                                     // first pause...
        ok(g.isEnded(), "paused");
        g.resumeAfterOpen();                          // ...and back to the game
        g.input.keyDown("space");
        steps(g, 3);
        g.input.keyUp("space");
        g.input.pointerDown(0, 400, 120);             // the coin, at (200, 60) virtual
        g.step();
        g.input.pointerUp(0, 400, 120);
        steps(g, 50);
        g.back();                                     // the pause the app process dies in
        ok(g.endJson().contains("pause_menu"), "suspended: " + g.endJson());
        return g;
    }

    static void journal() {
        HeadlessPlatform.MemoryAssets a = suspendable();
        Game live = playedAndSuspended(a);
        ok(live.platform.store().get("coins").equals("2") && live.var("lives") == 4, "the coin was taken");
        String saved = live.journalJson();
        HeadlessPlatform fresh = new HeadlessPlatform(a);
        fresh.store().set("coins", "100");                         // the app changed the store meanwhile
        Game back = Game.restore(fresh, saved);
        ok(back.stateHash().equals(live.stateHash()), back.stateHash() + " vs " + live.stateHash());
        ok(back.isEnded() && back.endJson().equals(live.endJson()), "restored suspended: " + back.endJson());
        ok(fresh.store().get("coins").equals("100"), "playing the journal again writes nothing to the store");
        ok(back.var("lives") == 4, "vars too");
        for (Game g : new Game[]{live, back}) {
            g.resumeAfterOpen();
            g.input.keyDown("left");
            steps(g, 60);
        }
        ok(back.stateHash().equals(live.stateHash()), "they go on the same: " + back.stateHash() + " vs " + live.stateHash());
        Game again = Game.restore(new HeadlessPlatform(a), playedAndSuspended(a).journalJson());
        ok(again.stateHash().equals(playedAndSuspended(a).stateHash()), "the same every time");
        System.out.println("        journal: " + saved.length() + " bytes for " + live.steps() + " steps, state " + back.stateHash());
    }

    static void journalMismatch() {
        HeadlessPlatform.MemoryAssets a = suspendable();
        String saved = playedAndSuspended(a).journalJson();
        String other = saved.replace("\"hash\":\"", "\"hash\":\"x");
        try {
            Game.restore(new HeadlessPlatform(a), other);
            ok(false, "accepted");
        } catch (apkpygame.core.GameException e) {
            ok(e.code.equals("G3030"), e.code);
        }
    }

    /** 60 balls resting on the floor and on each other: contacts every step, no spawning. */
    static void noGarbage() {
        StringBuilder balls = new StringBuilder();
        for (int i = 0; i < 60; i++) {
            balls.append(",{\"name\":\"b").append(i).append("\",\"transform\":{\"x\":").append(20 + (i % 20) * 9)
                    .append(",\"y\":").append(20 + (i / 20) * 9).append("},\"components\":[{\"type\":\"Collider\","
                    + "\"shape\":\"circle\",\"radius\":5},{\"type\":\"Body\",\"gravity\":500}]}");
        }
        Game g = game(scene(MAP_ENTITY + balls));
        steps(g, 600);                                  // settle, and let every list reach its size
        com.sun.management.ThreadMXBean bean =
                (com.sun.management.ThreadMXBean) java.lang.management.ManagementFactory.getThreadMXBean();
        long id = Thread.currentThread().getId();
        long before = bean.getThreadAllocatedBytes(id);
        steps(g, 600);
        long perStep = (bean.getThreadAllocatedBytes(id) - before) / 600;
        System.out.println("        " + perStep + " bytes allocated per step (60 bodies in contact)");
        ok(perStep < 256, perStep + " bytes per step");
    }

    static void culling() {
        StringBuilder shapes = new StringBuilder();
        for (int i = 0; i < 100; i++) {
            if (i > 0) shapes.append(',');
            shapes.append("{\"name\":\"s").append(i).append("\",\"transform\":{\"x\":").append(i * 40)
                    .append(",\"y\":100},\"components\":[{\"type\":\"Shape\",\"size\":[20,20]}]}");
        }
        Game g = game(scene(shapes.toString()));
        apkpygame.core.render.RenderQueue q = new apkpygame.core.render.RenderQueue();
        final int[] drawn = new int[1];
        apkpygame.core.render.RenderBackend count = (apkpygame.core.render.RenderBackend) java.lang.reflect.Proxy
                .newProxyInstance(GameplayTests.class.getClassLoader(),
                        new Class<?>[]{apkpygame.core.render.RenderBackend.class}, new java.lang.reflect.InvocationHandler() {
                            @Override public Object invoke(Object p, java.lang.reflect.Method m, Object[] a) {
                                if (m.getName().equals("draw")) drawn[0]++;
                                return null;
                            }
                        });
        for (apkpygame.core.Entity e : g.scene().entities()) {
            for (apkpygame.core.Component c : e.components()) {
                if (c instanceof apkpygame.core.components.Shape) {
                    apkpygame.core.math.Mat3 m = new apkpygame.core.math.Mat3().set(1, 0, 0, 1, e.transform.x, e.transform.y);
                    q.add(apkpygame.core.render.DrawCommand.Kind.RECT).matrix.set(m);
                    q.add(apkpygame.core.render.DrawCommand.Kind.TEXT).matrix.set(m);
                }
            }
        }
        q.clip(320, 240);
        q.flush(count);
        // x = 0, 40, ..., 320 touch the 320-wide surface (9 boxes), plus every text (100)
        ok(drawn[0] == 9 + 100 && q.culled() == 91, drawn[0] + " drawn, " + q.culled() + " culled");
    }

    static Game game25d(String entities) {
        String sceneJson = "{\"format\":1,\"kind\":\"2.5d\",\"camera\":{\"x\":100,\"y\":100,\"pitch\":40,\"distance\":200,"
                + "\"follow\":\"hero\"},\"entities\":[" + entities + "]}";
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets()
                .put("game.json", "{\"format\":1,\"size\":[360,640]}").put("hero.png", png(48, 96))
                .put("scenes/main.json", sceneJson);
        Game g = Game.load(new HeadlessPlatform(a));
        g.start("main", "");
        g.viewport.update(360, 640);
        return g;
    }

    static final String HERO = "{\"name\":\"hero\",\"transform\":{\"x\":104,\"y\":104},\"components\":["
            + "{\"type\":\"Billboard\",\"image\":\"hero.png\",\"frame_size\":[16,24],\"directions\":4},"
            + "{\"type\":\"GridController\",\"tap\":true}]}";

    static void pick25d() {
        Game g = game25d(HERO);
        g.step();
        g.input.pointerDown(0, 180, 320);                     // the middle of the view
        g.step();
        apkpygame.core.Input.Pointer p = g.input.pointer();
        near(p.worldX, g.scene().camera.x, 1e-6, "x");
        near(p.worldY, g.scene().camera.y, 1e-6, "y");
        g.input.pointerUp(0, 180, 320);
        g.step();
        g.input.pointerDown(0, 180, 600);                     // lower on the screen: nearer the camera, larger y
        g.step();
        ok(g.input.pointer().worldY > g.scene().camera.y + 10, "below the middle is nearer: " + g.input.pointer().worldY);
    }

    static void grid() {
        Game g = game25d(HERO + ",{\"name\":\"rock\",\"tags\":[\"solid\"],\"transform\":{\"x\":152,\"y\":104}}");
        apkpygame.core.Entity hero = g.scene().find("hero");
        apkpygame.core.components.Billboard b = hero.get(apkpygame.core.components.Billboard.class);
        g.step();
        near(hero.transform.x, 104, 1e-9, "starts on a cell centre");
        g.input.keyDown("up");                                // a short press: only turns
        g.step();
        g.input.keyUp("up");
        steps(g, 10);
        near(hero.transform.y, 104, 1e-9, "a short press does not walk");
        near(b.facing, 180, 1e-9, "it turned up");
        g.input.keyDown("right");                             // held: walks right, one cell at a time
        steps(g, 60);
        g.input.keyUp("right");
        steps(g, 30);
        near(hero.transform.x, 136, 1e-9, "two cells, then the rock at 152 stops it");
        near(b.facing, 90, 1e-9, "facing right");
        near(hero.transform.y, 104, 1e-9, "same row");
    }

    /** Where a hero that starts in this row is after walking right for a while, a house 48 x 32 in the cell at 168, 104. */
    static double walkedTo(int row) {
        Game g = game25d(HERO.replace("\"y\":104", "\"y\":" + row)
                + ",{\"name\":\"house\",\"tags\":[\"solid\"],\"transform\":{\"x\":168,\"y\":104},"
                + "\"components\":[{\"type\":\"Block\",\"size\":[48,32],\"height\":30}]}");
        apkpygame.core.Entity hero = g.scene().find("hero");
        g.step();
        g.input.keyDown("right");
        steps(g, 120);
        g.input.keyUp("right");
        steps(g, 30);
        return hero.transform.x;
    }

    static void gridBlock() {
        near(walkedTo(104), 136, 1e-9, "the house's row: its first cell (152) stops the walk");
        near(walkedTo(88), 136, 1e-9, "the row above, which the house is half on, stops it too");
        ok(walkedTo(72) > 200, "two rows above, the way is free: " + walkedTo(72));
    }

    static void journal25d() {
        HeadlessPlatform.MemoryAssets a = new HeadlessPlatform.MemoryAssets()
                .put("game.json", "{\"format\":1,\"size\":[360,640]}").put("hero.png", png(48, 96))
                .put("scenes/main.json", "{\"format\":1,\"kind\":\"2.5d\",\"camera\":{\"pitch\":40,\"distance\":200,"
                        + "\"follow\":\"hero\"},\"on_back\":[{\"do\":\"open\",\"screen\":\"pause\"}],\"entities\":[" + HERO + "]}");
        Game g = Game.load(new HeadlessPlatform(a));
        g.start("main", "");
        g.viewport.update(720, 1280);
        steps(g, 5);
        g.input.pointerDown(0, 600, 300);
        g.step();
        g.input.pointerUp(0, 600, 300);
        steps(g, 120);
        g.back();
        ok(g.isEnded(), "paused");
        Game back = Game.restore(new HeadlessPlatform(a), g.journalJson());
        ok(back.stateHash().equals(g.stateHash()), back.stateHash() + " vs " + g.stateHash());
        apkpygame.core.Entity hero = g.scene().find("hero");
        ok(hero.transform.x != 104 || hero.transform.y != 104, "the tap walked the hero");
    }

    static void raster() {
        apkpygame.core.render.Camera3D cam = new apkpygame.core.render.Camera3D();
        cam.pitch = 15;                                       // the top of a 40-degree view looks 5 degrees above the horizon
        cam.distance = 100;
        cam.update(0, 0, 0, 0.5);
        apkpygame.core.render.View3D v = new apkpygame.core.render.View3D();
        v.viewProjection.set(cam.viewProjection);
        v.width = 100;
        v.height = 200;
        apkpygame.core.render.Raster3D r = new apkpygame.core.render.Raster3D();
        r.begin(100, 200);
        apkpygame.core.render.DrawCommand ground = new apkpygame.core.render.DrawCommand();
        ground.kind = apkpygame.core.render.DrawCommand.Kind.QUAD3D;
        ground.view3d = v;
        ground.color = 0xFF33AA33;
        ground.alpha = 1;
        ground.cutout = true;
        double big = 1000;                                    // reaches far behind the camera: needs near clipping
        apkpygame.core.render.Quads.corner(ground, 0, -big, big, 0);
        apkpygame.core.render.Quads.corner(ground, 1, big, big, 0);
        apkpygame.core.render.Quads.corner(ground, 2, big, -big, 0);
        apkpygame.core.render.Quads.corner(ground, 3, -big, -big, 0);
        r.quad(ground, null, 0, 0);
        int[] px = r.pixels();
        ok(px[199 * 100 + 50] == 0xFF33AA33, "the bottom row is ground: " + Integer.toHexString(px[199 * 100 + 50]));
        ok(px[100 * 100 + 50] == 0xFF33AA33, "the middle too");
        ok(px[0] == 0, "the top-left corner is sky (nothing drawn): " + Integer.toHexString(px[0]));
    }
}
