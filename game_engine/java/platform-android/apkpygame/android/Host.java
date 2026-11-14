package apkpygame.android;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import apkpygame.core.Game;
import apkpygame.core.GameException;
import apkpygame.core.GameHost;
import apkpygame.core.json.Json;
import apkpygame.testkit.Snapshot;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * What the ApkPy glue calls (the game_* functions in writehere.py).
 * Everything answers a String, as native.java blocks must.
 */
public final class Host {
    /** The glue adapts ApkPy's done.run(ok, value) to this. */
    public interface Listener {
        void onResult(boolean ok, String json);
    }

    static final String LAST = "apkpygame.last_result";

    private static Listener pending;
    private static Game suspended;

    private Host() { }

    public static String version() {
        return Game.VERSION;
    }

    /** game_play(scene, args_json): opens GameActivity; the answer comes when the game ends. */
    public static void play(Activity activity, String scene, String argsJson, Listener listener) {
        suspended = null;
        forget(activity);
        launch(activity, scene, argsJson, false, listener);
    }

    /** game_resume(): continues a game suspended by openApp(), or answers "none". */
    public static void resume(Activity activity, Listener listener) {
        if (suspended == null && !saved(activity).isFile()) {
            listener.onResult(true, "{\"v\":1,\"action\":\"none\",\"suspended\":false}");
            return;
        }
        // with no game in memory (the process died), GameActivity brings it back from the saved journal
        launch(activity, suspended != null ? suspended.scene().name : "", "", true, listener);
    }

    private static void launch(Activity activity, String scene, String argsJson, boolean resume,
                               Listener listener) {
        pending = listener;
        Intent intent = new Intent(activity, GameActivity.class);
        intent.putExtra(GameActivity.EXTRA_SCENE, scene);
        intent.putExtra(GameActivity.EXTRA_ARGS, argsJson);
        intent.putExtra(GameActivity.EXTRA_RESUME, resume);
        activity.startActivity(intent);
    }

    /**
     * The game opened an ApkPy screen. It stays in memory, and its journal is
     * saved too: if Android kills the app's process meanwhile, game_resume()
     * plays the journal again (Game.restore) to the same world.
     */
    static void suspend(Context context, Game game) {
        suspended = game;
        String journal = game.journalJson();
        if (journal == null) return;
        File file = saved(context);
        try {
            file.getParentFile().mkdirs();
            File tmp = new File(file.getPath() + ".tmp");
            OutputStream out = new FileOutputStream(tmp);
            try {
                out.write(journal.getBytes("UTF-8"));
            } finally {
                out.close();
            }
            if (!tmp.renameTo(file)) AndroidPlatform.LOGGER.warn("could not save the suspended game");
        } catch (IOException e) {
            AndroidPlatform.LOGGER.warn("could not save the suspended game: " + e);
        }
    }

    /** The saved journal of the suspended game, or null. */
    static String savedJournal(Context context) {
        File file = saved(context);
        if (!file.isFile()) return null;
        try {
            InputStream in = new FileInputStream(file);
            try {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] buf = new byte[8192];
                for (int n; (n = in.read(buf)) > 0; ) out.write(buf, 0, n);
                return out.toString("UTF-8");
            } finally {
                in.close();
            }
        } catch (IOException e) {
            return null;
        }
    }

    /** No suspended game any more (a new game, or the game ended). */
    static void forget(Context context) {
        File file = saved(context);
        if (file.isFile() && !file.delete()) AndroidPlatform.LOGGER.warn("could not delete " + file);
    }

    private static File saved(Context context) {
        return new File(new File(context.getFilesDir(), "apkpygame"), "suspended.json");
    }

    static boolean holds(Game game) {
        return suspended == game;
    }

    static Game takeSuspended(boolean resume) {
        Game game = resume ? suspended : null;
        suspended = null;
        return game;
    }

    /** Called once per GameActivity, on the UI thread. */
    static void finished(Context context, String json) {
        AndroidPlatform.prefs(context).edit().putString(LAST, json).apply();
        Listener listener = pending;
        pending = null;
        if (listener == null) return;
        try {
            listener.onResult(!json.contains("\"action\":\"error\""), json);
        } catch (RuntimeException gone) {
            // the ApkPy screen that asked is gone: game_last_result() still has the answer
            AndroidPlatform.LOGGER.warn("the screen that opened the game is gone: " + gone);
        }
    }

    static String errorJson(RuntimeException e) {
        Map<String, Object> error = new LinkedHashMap<String, Object>();
        if (e instanceof GameException) {
            error.put("code", ((GameException) e).code);
            error.put("message", e.getMessage());
            error.put("fix", ((GameException) e).fix);
        } else {
            error.put("code", "G3999");
            error.put("message", String.valueOf(e));
        }
        Map<String, Object> out = new LinkedHashMap<String, Object>();
        out.put("v", 1.0);
        out.put("action", "error");
        out.put("error", error);
        out.put("suspended", false);
        return Json.stringify(out);
    }

    public static String get(Context context, String key) {
        return AndroidPlatform.prefs(context).getString(key, "");
    }

    public static String set(Context context, String key, String value) {
        AndroidPlatform.prefs(context).edit().putString(key, value).apply();
        return "ok";
    }

    /** The last answer, once (for an ApkPy screen recreated while the game ran). */
    public static String lastResult(Context context) {
        SharedPreferences p = AndroidPlatform.prefs(context);
        String value = p.getString(LAST, "");
        p.edit().remove(LAST).apply();
        return value;
    }

    /** An older glue of ApkPyGame 0.1.0, from before journals: knows only the game in memory. */
    public static String isSuspended() {
        return suspended != null ? "true" : "false";
    }

    /** game_suspended(): a game in memory, or one saved before the process died. */
    public static String isSuspended(Context context) {
        return suspended != null || saved(context).isFile() ? "true" : "false";
    }

    /**
     * Runs a scene for {@code steps} fixed steps with no window and answers
     * the state hash (the phone half of the parity check).
     */
    public static String snapshot(Context context, String scene, String argsJson, String steps) {
        try {
            return Snapshot.run(AndroidPlatform.assets(context), scene, argsJson, Integer.parseInt(steps.trim()));
        } catch (RuntimeException e) {
            return "error: " + e;
        }
    }

    /** Plays a key script with no window (testkit Replay) and answers its summary: compare it with the PC's. */
    public static String replay(Context context, String scene, String script, String steps) {
        try {
            return apkpygame.testkit.Replay.run(AndroidPlatform.assets(context), scene, "", script,
                    Integer.parseInt(steps.trim())).summary();
        } catch (RuntimeException e) {
            return "error: " + e;
        }
    }

    /**
     * Experimental: runs a scene inside an ApkPy container, marked with
     * label("apkpygame:slot:<slot>", parent=container). ApkPy's own ids are
     * positional, so the marker is how the container is found.
     */
    public static String embed(Activity activity, String slot, String scene, String heightDp) {
        View marker = findText(activity.getWindow().getDecorView(), "apkpygame:slot:" + slot);
        if (marker == null || !(marker.getParent() instanceof ViewGroup)) {
            return "error: no label \"apkpygame:slot:" + slot + "\" on this screen";
        }
        ViewGroup container = (ViewGroup) marker.getParent();
        marker.setVisibility(View.GONE);
        try {
            Game game = Game.load(new AndroidPlatform(activity));
            game.start(scene, "");
            game.setHost(new GameHost() {
                @Override public void ended(String resultJson) { }
            });
            final GameView view = new GameView(activity, game, new GameSurface.Failure() {
                @Override public void failed(RuntimeException error) {
                    AndroidPlatform.LOGGER.error("embedded game stopped", error);
                }
            });
            int height = (int) (Double.parseDouble(heightDp) * activity.getResources().getDisplayMetrics().density);
            container.addView(view, new ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, height));
            view.start();
            return "ok";
        } catch (RuntimeException e) {
            return "error: " + e;
        }
    }

    private static View findText(View view, String text) {
        if (view instanceof TextView && text.contentEquals(((TextView) view).getText())) return view;
        if (view instanceof ViewGroup) {
            ViewGroup g = (ViewGroup) view;
            for (int i = 0; i < g.getChildCount(); i++) {
                View hit = findText(g.getChildAt(i), text);
                if (hit != null) return hit;
            }
        }
        return null;
    }
}
