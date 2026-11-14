package apkpygame.testkit;

import apkpygame.core.Entity;
import apkpygame.core.Game;
import apkpygame.core.Platform;
import apkpygame.core.json.Json;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Plays a game with no window from a script of keys and taps:
 * "STEP:KEY:down,STEP:KEY:up,STEP:tap:X:Y,..." (a tap is down at STEP and up at the next
 * step, at virtual-screen X, Y).
 * The engine is deterministic, so the same script gives the same game (the same
 * end, variables and state hash) on the JVM and on the phone: the proof that
 * a level can be won, and that it plays the same everywhere.
 */
public final class Replay {
    public long steps;
    public String endJson;
    public String vars;
    public String hash;
    public double maxPlayerX;
    /** One line per variable change: "step vars". */
    public final List<String> events = new ArrayList<String>();
    /** With a trace: one line per step, "step scene name:x:y ..." for the entities traced (dev tools, bots). */
    public final List<String> trace = new ArrayList<String>();

    private Replay() { }

    public static Replay run(Platform.AssetSource assets, String scene, String argsJson, String script, int maxSteps) {
        return run(assets, scene, argsJson, script, maxSteps, null);
    }

    /** The same, and where the entities with these names or tags (comma separated) are after each step. */
    public static Replay run(Platform.AssetSource assets, String scene, String argsJson, String script, int maxSteps,
                             String traced) {
        Map<Long, List<String[]>> keys = parse(script);
        String[] watch = traced == null || traced.isEmpty() ? new String[0] : traced.split(",");
        Game game = Game.load(new HeadlessPlatform(assets));
        game.start(scene, argsJson);
        game.viewport.update((int) game.config.width, (int) game.config.height);
        Replay r = new Replay();
        int version = game.varsVersion();
        for (long step = 0; step < maxSteps && !game.isEnded(); step++) {
            apply(game, keys, step);
            game.step();
            Entity p = game.scene().find("player");
            if (p != null) r.maxPlayerX = Math.max(r.maxPlayerX, p.transform.x);
            if (watch.length > 0) r.trace.add(game.steps() + " " + game.scene().name + where(game, watch));
            if (game.varsVersion() != version) {
                version = game.varsVersion();
                r.events.add(game.steps() + " " + Json.stringify(game.vars()));
            }
        }
        r.steps = game.steps();
        r.endJson = game.endJson();
        r.vars = Json.stringify(game.vars());
        r.hash = game.stateHash();
        return r;
    }

    private static String where(Game game, String[] watch) {
        StringBuilder out = new StringBuilder();
        for (Entity e : game.scene().entities()) {
            if (e.isDestroyed() || !e.activeInTree()) continue;
            for (String w : watch) {
                if (e.name.equals(w) || e.hasTag(w)) {
                    out.append(' ').append(e.name.replace(' ', '_')).append(':')
                            .append(Math.round(e.transform.x * 10) / 10.0).append(':')
                            .append(Math.round(e.transform.y * 10) / 10.0);
                    break;
                }
            }
        }
        return out.toString();
    }

    /** The events of a replay script, by step. */
    public static Map<Long, List<String[]>> parse(String script) {
        Map<Long, List<String[]>> keys = new TreeMap<Long, List<String[]>>();
        for (String item : script == null ? new String[0] : script.split(",")) {
            String[] p = item.trim().split(":");
            if (p.length == 4 && p[1].equals("tap")) {
                long step = Long.parseLong(p[0]);
                add(keys, step, new String[]{"@" + p[2] + ":" + p[3], "down"});
                add(keys, step + 1, new String[]{"@" + p[2] + ":" + p[3], "up"});
                continue;
            }
            if (p.length == 7 && p[1].equals("drag")) {        // STEP:drag:X1:Y1:X2:Y2:STEPS
                long step = Long.parseLong(p[0]);
                double x1 = Double.parseDouble(p[2]), y1 = Double.parseDouble(p[3]);
                double x2 = Double.parseDouble(p[4]), y2 = Double.parseDouble(p[5]);
                int n = Integer.parseInt(p[6]);
                add(keys, step, new String[]{"@" + x1 + ":" + y1, "down"});
                for (int k = 1; k <= n; k++) {
                    add(keys, step + k, new String[]{"@" + (x1 + (x2 - x1) * k / n) + ":" + (y1 + (y2 - y1) * k / n), "move"});
                }
                add(keys, step + n + 1, new String[]{"@" + x2 + ":" + y2, "up"});
                continue;
            }
            if (p.length != 3) continue;
            add(keys, Long.parseLong(p[0]), new String[]{p[1], p[2]});
        }
        return keys;
    }

    /** Gives the game the events of this step (call it just before game.step()). */
    public static void apply(Game game, Map<Long, List<String[]>> keys, long step) {
        List<String[]> now = keys.get(step);
        if (now != null) {
            for (String[] e : now) {
                if (e[0].equals("back")) {
                game.back();
            } else if (e[0].startsWith("@")) {             // a tap: the surface is the virtual screen here
                    String[] xy = e[0].substring(1).split(":");
                    double x = Double.parseDouble(xy[0]), y = Double.parseDouble(xy[1]);
                    if (e[1].equals("down")) game.input.pointerDown(0, x, y);
                    else if (e[1].equals("move")) game.input.pointerMove(0, x, y);
                    else game.input.pointerUp(0, x, y);
                } else if (e[1].equals("down")) {
                    game.input.keyDown(e[0]);
                } else {
                    game.input.keyUp(e[0]);
                }
            }
        }
    }

    private static void add(Map<Long, List<String[]>> keys, long step, String[] event) {
        if (!keys.containsKey(step)) keys.put(step, new ArrayList<String[]>());
        keys.get(step).add(event);
    }

    /** One line: what the phone shows and the PC prints, to compare. */
    public String summary() {
        return "steps=" + steps + " vars=" + vars + " end=" + endJson + " state=" + hash;
    }
}
