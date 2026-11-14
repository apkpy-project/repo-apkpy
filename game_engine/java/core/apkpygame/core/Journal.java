package apkpygame.core;

import apkpygame.core.json.Json;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * What a run needs to be played again to the very same state: the scene it
 * started with, and everything that came from outside the engine, step by
 * step (touches and keys in virtual units, Back, the surface size, and each
 * value read from the store). The simulation is deterministic, so playing the
 * journal again with no sound gives the same world: that is how a game
 * suspended by open_app survives the death of the app's process
 * ({@link Game#restore}). It also covers the translated scripts, whose state
 * is whatever their code made of these inputs.
 *
 * <p>One line per event, "STEP KIND ...":
 * <pre>
 *   d|m|u ID X Y    pointer down / move / up (virtual units)
 *   kd|ku KEY       key down / up
 *   back            Back (between steps)
 *   size W H        the surface size
 *   (reads are kept apart, in the order they happened)
 * </pre>
 */
public final class Journal {
    public static final int VERSION = 1;

    final String scene, args;
    final List<String> lines = new ArrayList<String>();
    final List<String> reads = new ArrayList<String>();
    private int lastWidth = -1, lastHeight = -1;

    Journal(String scene, String args) {
        this.scene = scene == null ? "" : scene;
        this.args = args == null ? "" : args;
    }

    void pointer(long step, int type, int id, double x, double y) {
        lines.add(step + " " + "dmu".charAt(type) + " " + id + " " + x + " " + y);
    }

    void key(long step, boolean down, String key) {
        lines.add(step + (down ? " kd " : " ku ") + key);
    }

    void back(long step) {
        lines.add(step + " back");
    }

    void size(long step, int width, int height) {
        if (width == lastWidth && height == lastHeight) return;
        lastWidth = width;
        lastHeight = height;
        lines.add(step + " size " + width + " " + height);
    }

    void read(String value) {
        reads.add(value == null ? "" : value);
    }

    /** The journal as JSON, with the step and the state hash it must reach again. */
    public String toJson(long steps, String stateHash) {
        Map<String, Object> out = new LinkedHashMap<String, Object>();
        out.put("v", (double) VERSION);
        out.put("engine", Game.VERSION);
        out.put("scene", scene);
        out.put("args", args);
        out.put("steps", (double) steps);
        out.put("hash", stateHash);
        out.put("events", new ArrayList<Object>(lines));
        out.put("reads", new ArrayList<Object>(reads));
        return Json.stringify(out);
    }

    /** The parts of a journal read back from JSON. */
    static final class Saved {
        Journal journal;
        long steps;
        String hash;
    }

    static Saved parse(String json) {
        Map<String, Object> o = Json.parseObject(json);
        if (Json.num(o, "v", 0) != VERSION || !Game.VERSION.equals(Json.str(o, "engine", ""))) {
            throw new GameException("G3031", "the suspended game was saved by another engine version",
                    "start a new game (game_play)");
        }
        Saved s = new Saved();
        s.journal = new Journal(Json.str(o, "scene", ""), Json.str(o, "args", ""));
        s.steps = (long) Json.num(o, "steps", 0);
        s.hash = Json.str(o, "hash", "");
        for (Object line : Json.list(o, "events")) s.journal.lines.add(String.valueOf(line));
        for (Object read : Json.list(o, "reads")) s.journal.reads.add(String.valueOf(read));
        return s;
    }
}
