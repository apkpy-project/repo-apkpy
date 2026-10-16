package __PACKAGE__;

import android.app.Activity;
import android.app.StatusBarManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.drawable.Icon;
import android.os.Build;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

/**
 * quick_tile.* -- the app's tile in quick settings.
 *
 * The tile is drawn by the system, from what ApkpyTileService tells it: lit
 * or not, and a line under the name. The app decides both and they are kept
 * on disk, because the system asks for them with the app closed.
 *
 * A tap on the tile opens the app at its first screen, which asks
 * quick_tile.opened() to learn that this is how the person arrived -- the
 * same shape as a link that opened the app.
 */
public final class ApkpyTile {

    private static final String STORE = "apkpy_tile";
    static final String LABEL = "__TILE_LABEL__";

    /** Set by the tile when it is tapped; the process it starts is this one. */
    static volatile boolean sOpened;

    private ApkpyTile() { }

    public static String set(Activity activity, String active, String subtitle) {
        Context app = activity.getApplicationContext();
        app.getSharedPreferences(STORE, 0).edit()
                .putBoolean("active", ApkpyKit.truth(active))
                .putString("subtitle", ApkpyKit.text(subtitle))
                .apply();
        refresh(app);
        return "ok";
    }

    public static String isActive(Activity activity) {
        return ApkpyKit.flag(activity.getApplicationContext()
                .getSharedPreferences(STORE, 0).getBoolean("active", false));
    }

    public static String opened(Activity activity) {
        return ApkpyKit.flag(sOpened);
    }

    public static String clear(Activity activity) {
        sOpened = false;
        return "ok";
    }

    /** Ask the person to add the tile. Android 13 brought the question. */
    public static void offer(final Activity activity, final ApkpyKit.Done done) {
        if (Build.VERSION.SDK_INT < 33) {
            ApkpyKit.answer(done, false, "unsupported");
            return;
        }
        try {
            Asking.ask(activity, done);
        } catch (Throwable refused) {
            ApkpyKit.answer(done, false, "unsupported");
        }
    }

    /** Apart, so a phone before Android 13 never has to look at it. */
    private static final class Asking {
        static void ask(Activity activity, final ApkpyKit.Done done) {
            StatusBarManager bar = activity.getSystemService(StatusBarManager.class);
            int icon = activity.getResources().getIdentifier(
                    "ic_apkpy_tile", "drawable", activity.getPackageName());
            if (bar == null || icon == 0) {
                ApkpyKit.answer(done, false, "unsupported");
                return;
            }
            bar.requestAddTileService(
                    new ComponentName(activity, ApkpyTileService.class), LABEL,
                    Icon.createWithResource(activity, icon), activity.getMainExecutor(),
                    new java.util.function.Consumer<Integer>() {
                        @Override public void accept(Integer result) {
                            int code = result == null ? -1 : result;
                            if (code == StatusBarManager.TILE_ADD_REQUEST_RESULT_TILE_ADDED) {
                                refresh(activity.getApplicationContext());
                                ApkpyKit.answer(done, true, "added");
                            } else if (code
                                    == StatusBarManager.TILE_ADD_REQUEST_RESULT_TILE_ALREADY_ADDED) {
                                ApkpyKit.answer(done, true, "already");
                            } else if (code
                                    == StatusBarManager.TILE_ADD_REQUEST_RESULT_TILE_NOT_ADDED) {
                                ApkpyKit.answer(done, false, "dismissed");
                            } else {
                                ApkpyKit.answer(done, false, "unsupported");
                            }
                        }
                    });
        }
    }

    /** Tell quick settings to ask again what the tile shows. */
    static void refresh(Context app) {
        try {
            TileService.requestListeningState(
                    app, new ComponentName(app, ApkpyTileService.class));
        } catch (Throwable notAdded) {
            // The tile is not in quick settings: nothing to redraw.
        }
    }

    /** Put what is kept on the tile. */
    static void show(Context context, Tile tile) {
        if (tile == null) return;
        SharedPreferences store = context.getApplicationContext().getSharedPreferences(STORE, 0);
        String subtitle = ApkpyKitRules.trim(store.getString("subtitle", ""));
        tile.setState(store.getBoolean("active", false)
                ? Tile.STATE_ACTIVE : Tile.STATE_INACTIVE);
        tile.setLabel(LABEL);
        if (Build.VERSION.SDK_INT >= 29) tile.setSubtitle(subtitle.isEmpty() ? null : subtitle);
        tile.setContentDescription(subtitle.isEmpty() ? LABEL : LABEL + ", " + subtitle);
        tile.updateTile();
    }
}
