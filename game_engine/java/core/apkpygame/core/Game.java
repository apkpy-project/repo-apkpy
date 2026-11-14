package apkpygame.core;

import apkpygame.core.json.Json;
import apkpygame.core.math.Mat3;
import apkpygame.core.math.Rng;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;
import apkpygame.core.render.View3D;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The running game: one scene at a time, logic in fixed steps, drawing as
 * often as the platform asks.
 *
 * The platform owns the loop. Each display frame it calls
 * {@link #advance(double)} with the real time that passed, then
 * {@link #render(int, int)}. Logic always moves in steps of 1/fixedHz
 * seconds, so the same input gives the same game on every device; drawing
 * interpolates between the last two steps.
 */
public final class Game {
    public static final String VERSION = "1.0.0";
    private static final int MAX_STEPS_PER_FRAME = 5;

    public final Platform platform;
    public final GameConfig config;
    public final Assets assets;
    public final Input input = new Input();
    public final Viewport viewport;
    public final Rng random;

    private static volatile Game current;

    /**
     * The game being stepped: what plain functions and @dataclass methods of
     * the translated scripts use for random (they get no game of their own).
     */
    public static Game current() {
        if (current == null) throw new GameException("G3100", "no game is running", "call this while the game runs");
        return current;
    }
    public final double stepSeconds;

    private GameHost host;
    private Scene scene;
    private Journal journal;
    private boolean replaying;
    private int readCursor;
    private double accumulator;
    private long steps;
    private boolean ended;
    private String endJson;

    private final RenderQueue queue = new RenderQueue();
    private final Mat3 screen = new Mat3(), camera = new Mat3(), view = new Mat3(), inverseView = new Mat3(),
            overlay = new Mat3();
    private long fpsStart;
    private int frames, fps;

    public Game(Platform platform, GameConfig config) {
        this.platform = platform;
        this.config = config;
        this.assets = new Assets(platform.assets());
        this.viewport = new Viewport(config.width, config.height, config.scale, config.pixelScale,
                platform.phoneShortSide());
        this.random = new Rng(config.seed);
        this.stepSeconds = 1.0 / config.fixedHz;
        for (Map.Entry<String, Double> v : config.vars.entrySet()) vars.put(v.getKey(), v.getValue());
        assets.register("image", new Assets.Loader<Texture>() {
            @Override public Texture load(String path, Assets assets) {
                return Game.this.platform.renderer().loadTexture(path, assets.bytes(path));
            }
        });
        assets.register("pixels", new Assets.Loader<apkpygame.core.render.Png>() {   // a Canvas's images
            @Override public apkpygame.core.render.Png load(String path, Assets assets) {
                return apkpygame.core.render.Png.decode(path, assets.bytes(path));
            }
        });
        assets.register("font", new Assets.Loader<apkpygame.core.render.FontData>() {
            @Override public apkpygame.core.render.FontData load(String path, Assets assets) {
                return new apkpygame.core.render.FontData(
                        apkpygame.core.json.Json.parseObject(assets.text(path + ".json")));
            }
        });
        assets.register("sound", new Assets.Loader<Object>() {
            @Override public Object load(String path, Assets assets) {
                if (!assets.exists(path)) assets.bytes(path);      // the G3021 error, with the path
                return Game.this.platform.audio().loadSound(path);
            }
        });
    }

    // ── variables: score, lives... (the game's own numbers; texts show them as {name}) ──

    private final Map<String, Double> vars = new LinkedHashMap<String, Double>();
    private int varsVersion;
    private String pendingScene;

    public double var(String name) {
        Double v = vars.get(name);
        return v == null ? 0 : v;
    }

    public void setVar(String name, double value) {
        Double old = vars.put(name, value);
        if (old == null || old != value) varsVersion++;
    }

    /** Changes each time a variable changes (texts redraw only then). */
    public int varsVersion() {
        return varsVersion;
    }

    public Map<String, Double> vars() {
        return java.util.Collections.unmodifiableMap(vars);
    }

    /** 3.0 is "3", 2.5 is "2.5". */
    public static String number(double v) {
        return v == Math.rint(v) && Math.abs(v) < 1e15 ? String.valueOf((long) v) : String.valueOf(v);
    }

    /** "Score: {score}" with the variable's value. */
    public String format(String template) {
        if (template == null || template.indexOf('{') < 0) return template;
        StringBuilder out = new StringBuilder();
        int i = 0;
        while (i < template.length()) {
            char ch = template.charAt(i);
            int close = ch == '{' ? template.indexOf('}', i) : -1;
            if (close > i + 1 && isName(template, i + 1, close)) {
                out.append(number(var(template.substring(i + 1, close))));
                i = close + 1;
            } else {
                out.append(ch);
                i++;
            }
        }
        return out.toString();
    }

    private static boolean isName(String s, int from, int to) {
        for (int i = from; i < to; i++) {
            char c = s.charAt(i);
            if (!(Character.isLetterOrDigit(c) || c == '_')) return false;
        }
        return true;
    }

    /** A copy of a result/data map where "{name}" becomes the variable's number and other texts are formatted. */
    @SuppressWarnings("unchecked")
    public Map<String, Object> substitute(Map<String, Object> in) {
        Map<String, Object> out = new LinkedHashMap<String, Object>();
        if (in == null) return out;
        for (Map.Entry<String, Object> e : in.entrySet()) {
            Object v = e.getValue();
            if (v instanceof String) {
                String s = (String) v;
                if (s.startsWith("{") && s.endsWith("}") && isName(s, 1, s.length() - 1)) {
                    v = var(s.substring(1, s.length() - 1));
                } else {
                    v = format(s);
                }
            } else if (v instanceof Map) {
                v = substitute((Map<String, Object>) v);
            }
            out.put(e.getKey(), v);
        }
        return out;
    }

    /** Changes scene at the end of the step; variables carry over. */
    public void gotoScene(String name) {
        gotoScene(name, null, 0);
    }

    /** at: where entities tagged "arrives" appear (see Scene.arrive); fade: seconds to black and back. */
    public void gotoScene(String name, String at, double fade) {
        pendingScene = name;
        pendingAt = at == null || at.isEmpty() ? null : at;
        pendingFade = fade;
    }

    /** The last game.goto's "at" ("" if none). */
    public String arrival = "";
    private String pendingAt;
    private double pendingFade;
    private int fadePhase, fadeSteps, fadeLeft;                   // 1: to black, 2: back

    private void changeScene() {
        String next = pendingScene, at = pendingAt;
        pendingAt = null;
        java.util.List<Entity> carried = scene.takePersistent();
        start(next, null);
        for (Entity e : carried) scene.receive(e);
        arrival = at == null ? "" : at;
        if (at != null) scene.arrive(at);
        scene.settleCamera();
    }

    private Map<String, Object> texts;

    /**
     * A text of the app's translations() (copied into the bundle as texts.json
     * by apkpygame build): the device's language, else the default one, else
     * {@code fallback}.
     */
    @SuppressWarnings("unchecked")
    public String text(String key, String fallback) {
        if (texts == null) {
            texts = assets.exists("texts.json") ? Json.parseObject(assets.text("texts.json"))
                    : new LinkedHashMap<String, Object>();
        }
        Map<String, Object> languages = Json.obj(texts, "languages");
        if (languages == null) return fallback;
        for (String lang : new String[]{platform.language(), Json.str(texts, "default", "en")}) {
            Map<String, Object> words = Json.obj(languages, lang == null ? "" : lang);
            if (words != null && words.get(key) instanceof String) return (String) words.get(key);
        }
        return fallback;
    }

    /** Back (Android) / Esc (desktop): the scene's on_back actions, or the end of the game. */
    public void back() {
        if (scene == null || ended) return;
        if (journal != null && !replaying) journal.back(steps);
        if (scene.backToScripts()) return;
        if (scene.onBack.isEmpty()) {
            Map<String, Object> result = new LinkedHashMap<String, Object>();
            result.put("reason", "back");
            exit(result);
        } else {
            Actions.runAll(scene.onBack, this, null, null);
        }
    }

    /** Plays a sound of the bundle (loaded once, then cached). */
    public void playSound(String path, double volume) {
        if (replaying) return;
        platform.audio().play(assets.get("sound", path), volume * soundVolume);
    }

    /** Every sound is multiplied by this (the options screen). */
    public double soundVolume = 1;
    private boolean musicOn = true;

    /** The scene's music on or off; it stays so across scenes. */
    public void setMusicOn(boolean on) {
        musicOn = on;
        if (replaying || scene == null) return;
        if (on && scene.music != null) platform.audio().playMusic(scene.music, scene.musicVolume, scene.musicLoop);
        else platform.audio().stopMusic();
    }

    /**
     * The store shared with the app (game_get / game_set), as the game sees it:
     * each value read goes into the journal, and a journal played again reads
     * those values back (and writes nothing), so a restored game sees what the
     * first run saw.
     */
    public Platform.KeyValueStore store() {
        return store;
    }

    /**
     * The save slots, as the game sees them. Like the store: a read is an input
     * of the game, so it goes into the journal ("1" + text, or "0" for an empty
     * slot) and a journal played again reads it from there, not from the disk
     * (which may have changed since); writes are skipped while replaying.
     */
    public Platform.SaveStore saves() {
        return saves;
    }

    private final Platform.SaveStore saves = new Platform.SaveStore() {
        @Override public String read(String slot) {
            check(slot);
            if (replaying && journal != null && readCursor < journal.reads.size()) {
                String r = journal.reads.get(readCursor++);
                return r.startsWith("1") ? r.substring(1) : null;
            }
            String value = platform.saves().read(slot);
            if (journal != null && !replaying) journal.read(value == null ? "0" : "1" + value);
            return value;
        }

        @Override public void write(String slot, String text) {
            check(slot);
            if (!replaying) platform.saves().write(slot, text);
        }

        @Override public void delete(String slot) {
            check(slot);
            if (!replaying) platform.saves().delete(slot);
        }

        private void check(String slot) {
            if (slot == null || !slot.matches("[A-Za-z0-9_-]{1,40}")) {
                throw new Py.PyError("ValueError: a save slot is 1 to 40 letters, digits, _ or - (got '" + slot + "')");
            }
        }
    };

    private final Platform.KeyValueStore store = new Platform.KeyValueStore() {
        @Override public String get(String key) {
            if (replaying && journal != null && readCursor < journal.reads.size()) {
                return journal.reads.get(readCursor++);
            }
            String value = platform.store().get(key);
            if (journal != null && !replaying) journal.read(value);
            return value;
        }

        @Override public void set(String key, String value) {
            if (!replaying) platform.store().set(key, value);
        }
    };

    private static boolean scriptsLoaded;

    /**
     * The game's translated scripts (game.aar / game.jar) register their
     * component readers in apkpygame.game.GameScripts.register(). Found by
     * name once; a game without scripts has no such class.
     */
    static synchronized void loadScripts(Platform platform) {
        if (scriptsLoaded) return;
        scriptsLoaded = true;
        try {
            Class.forName("apkpygame.game.GameScripts").getMethod("register").invoke(null);
        } catch (ClassNotFoundException none) {
            // no scripts in this game
        } catch (Exception e) {
            platform.logger().error("the game's scripts could not be registered", e);
        }
    }

    /** Reads game.json from the bundle. */
    public static Game load(Platform platform) {
        loadScripts(platform);
        ScriptState.resetAll();                // a new game (or a journal played again) starts from the same state
        Assets probe = new Assets(platform.assets());
        return new Game(platform, GameConfig.read(probe.text("game.json")));
    }

    public void setHost(GameHost host) {
        this.host = host;
    }

    /** Loads scenes/{name}.json and makes it the current scene. */
    public Scene start(String sceneName, String argsJson) {
        current = this;
        Map<String, Object> args = argsJson == null || argsJson.trim().isEmpty()
                ? new LinkedHashMap<String, Object>() : Json.parseObject(argsJson);
        String name = sceneName == null || sceneName.isEmpty() ? config.startScene : sceneName;
        if (journal == null) journal = new Journal(sceneName, argsJson);
        pendingScene = null;
        scene = SceneLoader.load(this, name, args);
        accumulator = 0;
        ended = false;
        endJson = null;
        if (replaying) return scene;
        if (musicOn && scene.music != null) platform.audio().playMusic(scene.music, scene.musicVolume, scene.musicLoop);
        else platform.audio().stopMusic();
        return scene;
    }

    public Scene scene() {
        return scene;
    }

    public long steps() {
        return steps;
    }

    public int fps() {
        return fps;
    }

    public boolean isEnded() {
        return ended;
    }

    // ── the loop ─────────────────────────────────────────────────────────

    /** Runs as many fixed steps as {@code elapsedSeconds} covers (5 at most). Answers how many. */
    public int advance(double elapsedSeconds) {
        if (scene == null || ended) return 0;
        accumulator += Math.min(Math.max(elapsedSeconds, 0), MAX_STEPS_PER_FRAME * stepSeconds);
        int n = 0;
        while (accumulator >= stepSeconds && n < MAX_STEPS_PER_FRAME && !ended) {
            step();
            accumulator -= stepSeconds;
            n++;
        }
        return n;
    }

    private final Input.Picker picker2d = new Input.Picker() {
        @Override public void toWorld(double vx, double vy, double[] out) {
            out[0] = inverseView.mapX(vx, vy);
            out[1] = inverseView.mapY(vx, vy);
        }
    };

    /** 2.5D: the ray from the camera through the touched point, to the ground at the camera target's height. */
    private final Input.Picker picker3d = new Input.Picker() {
        @Override public void toWorld(double vx, double vy, double[] out) {
            double ndcX = vx / viewport.width * 2 - 1, ndcY = 1 - vy / viewport.height * 2;
            if (!scene.camera3d.pick(ndcX, ndcY, scene.cameraElevation, out)) {
                out[0] = scene.camera.x;
                out[1] = scene.camera.y;
            }
        }
    };

    /** One fixed step (tests and headless runs call this directly). */
    public void step() {
        current = this;
        Input.Picker picker;
        if (scene.is25d()) {
            scene.aimCamera3d(1, viewport.width / viewport.height);
            picker = picker3d;
        } else {
            scene.camera.viewMatrix(viewport.width, viewport.height, inverseView);
            inverseView.invert();
            picker = picker2d;
        }
        if (!replaying && viewport.surfaceWidth > 0) journal.size(steps, viewport.surfaceWidth, viewport.surfaceHeight);
        input.apply(viewport, picker, replaying ? null : journal, steps);
        if (fadePhase == 1) {                                     // to black: nothing moves
            scene.holdStill();
            steps++;
            if (--fadeLeft <= 0) {
                changeScene();
                fadePhase = 2;
                fadeLeft = fadeSteps;
            }
            return;
        }
        if (fadePhase == 2 && --fadeLeft <= 0) fadePhase = 0;
        scene.step(stepSeconds);
        steps++;
        if (pendingScene != null && !ended && fadePhase == 0) {
            if (pendingFade > 0) {
                fadePhase = 1;
                fadeSteps = fadeLeft = Math.max(1, (int) Math.round(pendingFade / 2 / stepSeconds));
                pendingFade = 0;
            } else {
                changeScene();
            }
        }
    }

    public void render(int surfaceWidth, int surfaceHeight) {
        if (scene == null) return;
        viewport.update(surfaceWidth, surfaceHeight);
        long now = System.nanoTime();
        frames++;
        if (now - fpsStart >= 1000000000L) {
            fps = frames;
            frames = 0;
            fpsStart = now;
        }
        double alpha = Math.min(1, accumulator / stepSeconds);
        viewport.screenMatrix(screen);
        scene.camera.viewMatrix(viewport.width, viewport.height, camera);
        view.set(screen).multiply(camera);
        platform.renderer().begin(surfaceWidth, surfaceHeight, config.background);
        if (scene.is25d()) {
            scene.aimCamera3d(alpha, viewport.width / viewport.height);
            View3D v = scene.view3d;
            v.viewProjection.set(scene.camera3d.viewProjection);
            v.x = viewport.offsetX;
            v.y = viewport.offsetY;
            v.width = viewport.width * viewport.scale;
            v.height = viewport.height * viewport.scale;
            v.eyeX = scene.camera3d.eyeX;
            v.eyeY = scene.camera3d.eyeY;
            v.eyeZ = scene.camera3d.eyeZ;
        }
        if (viewport.offsetX > 0 || viewport.offsetY > 0 || scene.background != config.background || scene.is25d()) {
            DrawCommand bg = queue.add(DrawCommand.Kind.RECT);
            bg.layer = Integer.MIN_VALUE;
            bg.matrix.set(screen);
            bg.w = viewport.width;
            bg.h = viewport.height;
            bg.color = scene.background;
        }
        scene.render(queue, view, screen, alpha);
        queue.drawingUi = true;
        if (fadePhase != 0) {
            DrawCommand f = queue.add(DrawCommand.Kind.RECT);
            f.layer = Integer.MAX_VALUE - 2;
            f.matrix.set(screen);
            f.w = viewport.width;
            f.h = viewport.height;
            double dark = fadePhase == 1 ? 1 - (double) fadeLeft / fadeSteps : (double) fadeLeft / fadeSteps;
            f.color = apkpygame.core.math.Color.withAlpha(0xFF000000, dark);
        }
        letterbox(surfaceWidth, surfaceHeight);
        if (config.debug) {
            if (!scene.is25d()) scene.physics.debugDraw(queue, view);     // 2D outlines: the 2D view only
            debugOverlay();
        }
        queue.drawingUi = false;
        queue.clip(surfaceWidth, surfaceHeight);
        queue.flush(platform.renderer());
        platform.renderer().end();
    }

    /** Covers what was drawn outside the game area ("fit" bars), on every backend the same way. */
    private void letterbox(int surfaceWidth, int surfaceHeight) {
        double gameW = viewport.width * viewport.scale, gameH = viewport.height * viewport.scale;
        if (viewport.offsetY > 0) {
            bar(0, 0, surfaceWidth, viewport.offsetY);
            bar(0, viewport.offsetY + gameH, surfaceWidth, surfaceHeight - viewport.offsetY - gameH);
        }
        if (viewport.offsetX > 0) {
            bar(0, 0, viewport.offsetX, surfaceHeight);
            bar(viewport.offsetX + gameW, 0, surfaceWidth - viewport.offsetX - gameW, surfaceHeight);
        }
    }

    private void bar(double x, double y, double w, double h) {
        DrawCommand b = queue.add(DrawCommand.Kind.RECT);
        b.layer = Integer.MAX_VALUE - 1;
        b.x = x;
        b.y = y;
        b.w = w + 1;
        b.h = h + 1;
        b.color = config.background;
    }

    private void debugOverlay() {
        DrawCommand t = queue.add(DrawCommand.Kind.TEXT);
        t.layer = Integer.MAX_VALUE;
        t.matrix.set(viewport.screenMatrix(overlay));
        t.x = 8;
        t.y = 20;
        t.size = 14;
        t.color = 0xFFFFFFFF;
        t.text = fps + " fps  " + scene.entityCount() + " entities  " + queue.culled() + " culled  step " + steps;
    }

    // ── ending: back to the ApkPy app ────────────────────────────────────

    /** Ends the game; the ApkPy screen that opened it gets {"action":"exit","result":...}. */
    public void exit(Map<String, Object> result) {
        Map<String, Object> out = protocol("exit");
        out.put("result", result == null ? new LinkedHashMap<String, Object>() : result);
        out.put("suspended", false);
        end(Json.stringify(out));
    }

    /** Opens an ApkPy screen; the game stays suspended and game_resume() continues it. */
    public void openApp(String screenId, Map<String, Object> data) {
        Map<String, Object> out = protocol("open");
        out.put("screen", screenId);
        out.put("data", data == null ? new LinkedHashMap<String, Object>() : data);
        out.put("suspended", true);
        end(Json.stringify(out));
    }

    /** Continues after openApp (the platform calls this on game_resume). */
    public void resumeAfterOpen() {
        ended = false;
        endJson = null;
        accumulator = 0;
        if (!replaying && scene != null && scene.music != null) {
            platform.audio().playMusic(scene.music, scene.musicVolume, scene.musicLoop);
        }
    }

    private static Map<String, Object> protocol(String action) {
        Map<String, Object> out = new LinkedHashMap<String, Object>();
        out.put("v", 1.0);
        out.put("action", action);
        return out;
    }

    private void end(String json) {
        if (ended) return;
        ended = true;
        endJson = json;
        if (replaying) return;
        platform.audio().stopMusic();
        if (host != null) host.ended(json);
    }

    /** What the game ended with, or null. */
    public String endJson() {
        return endJson;
    }

    // ── suspended games that outlive the process ─────────────────────────

    /**
     * Everything needed to bring this run back after the app's process dies
     * (see {@link Journal}). Platforms save it when the game is suspended by
     * open_app, and hand it to {@link #restore} on game_resume.
     */
    public String journalJson() {
        return journal == null ? null : journal.toJson(steps, stateHash());
    }

    /**
     * The suspended game of a journal, rebuilt by playing the journal again
     * with no sound and no store writes, step for step. It ends suspended, as
     * it was saved; the platform then calls {@link #resumeAfterOpen}. Fails
     * with G3030 if the world it reaches is not the one that was saved (its
     * state hash), rather than continue a different game.
     */
    public static Game restore(Platform platform, String journalJson) {
        Journal.Saved saved = Journal.parse(journalJson);
        Game game = load(platform);
        game.journal = saved.journal;
        game.replaying = true;
        String lastOpen = null;
        try {
            game.start(saved.journal.scene, saved.journal.args);
            java.util.List<String> lines = saved.journal.lines;
            int next = 0;
            for (long n = 0; ; n++) {
                while (next < lines.size()) {
                    String[] e = lines.get(next).split(" ");
                    if (Long.parseLong(e[0]) != n) break;
                    next++;
                    String kind = e[1];
                    if (kind.equals("back")) {
                        game.back();
                        lastOpen = game.keepGoing(lastOpen);
                    } else if (kind.equals("size")) {
                        game.viewport.update(Integer.parseInt(e[2]), Integer.parseInt(e[3]));
                    } else if (kind.equals("kd") || kind.equals("ku")) {
                        game.input.inject(kind.equals("kd") ? 3 : 4, 0, 0, 0, e[2]);
                    } else {
                        game.input.inject("dmu".indexOf(kind.charAt(0)), Integer.parseInt(e[2]),
                                Double.parseDouble(e[3]), Double.parseDouble(e[4]), null);
                    }
                }
                if (n >= saved.steps) break;
                game.step();
                lastOpen = game.keepGoing(lastOpen);
            }
        } finally {
            game.replaying = false;
        }
        if (lastOpen == null || !game.stateHash().equals(saved.hash)) {
            throw new GameException("G3030", "the suspended game could not be brought back exactly (saved "
                    + saved.hash + ", reached " + game.stateHash() + ")", "start a new game (game_play)");
        }
        game.ended = true;
        game.endJson = lastOpen;
        return game;
    }

    /** While a journal is played again: an open_app on the way is passed (the run went on after it). */
    private String keepGoing(String lastOpen) {
        if (!ended) return lastOpen;
        if (endJson == null || !endJson.contains("\"suspended\":true")) {
            throw new GameException("G3030", "the suspended game ended while it was brought back",
                    "start a new game (game_play)");
        }
        String open = endJson;
        resumeAfterOpen();
        return open;
    }

    /** See {@link Scene#stateHash()}. */
    public String stateHash() {
        return scene == null ? "" : steps + ":" + scene.stateHash();
    }
}
