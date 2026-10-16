package __PACKAGE__;

import android.app.Activity;
import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.widget.RemoteViews;

/**
 * home_widget.* -- the app's widget on the home screen.
 *
 * A widget is not drawn by the app. The launcher draws it, in its own
 * process, from a description the app hands over: a layout of the app's and
 * the texts to put in it. So what the widget shows is kept here, on disk, and
 * handed over again whenever it changes or the launcher asks -- after a
 * restart of the phone, with the app not running, there is nobody else to
 * remember it.
 *
 * It has two drawings and takes the one that fits the room the person gave
 * it: a row -- title over a number with its caption beside it -- for a
 * widget one cell high, and a card with the number large for a taller one.
 * A tap on either opens the app.
 */
public final class ApkpyWidget {

    private static final String STORE = "apkpy_widget";
    private static final String TITLE = "__WIDGET_TITLE__";
    private static final String TEXT = "__WIDGET_TEXT__";
    private static final String CAPTION = "__WIDGET_CAPTION__";

    /** The height, in dp, from which the card fits. */
    private static final int CARD_FROM = 128;

    private ApkpyWidget() { }

    /** What the widget shows from now on. An empty title keeps the one it has. */
    public static String set(Activity activity, String text, String caption, String title) {
        Context app = activity.getApplicationContext();
        SharedPreferences.Editor editor = app.getSharedPreferences(STORE, 0).edit();
        editor.putString("text", ApkpyKit.text(text));
        editor.putString("caption", ApkpyKit.text(caption));
        if (!ApkpyKitRules.trim(title).isEmpty()) editor.putString("title", title);
        editor.apply();
        draw(app);
        return "ok";
    }

    /** How many of them are on the home screen. */
    public static String count(Activity activity) {
        return String.valueOf(ids(activity.getApplicationContext()).length);
    }

    /** Ask the launcher to put one on the home screen; the person places it. */
    public static String pin(Activity activity) {
        Context app = activity.getApplicationContext();
        if (Build.VERSION.SDK_INT < 26) return "unsupported";
        try {
            AppWidgetManager manager = AppWidgetManager.getInstance(app);
            if (manager == null || !manager.isRequestPinAppWidgetSupported()) return "unsupported";
            return manager.requestPinAppWidget(provider(app), null, null) ? "ok" : "unsupported";
        } catch (Throwable refused) {
            return "unsupported";
        }
    }

    private static ComponentName provider(Context app) {
        return new ComponentName(app, ApkpyWidgetProvider.class);
    }

    private static int[] ids(Context app) {
        try {
            AppWidgetManager manager = AppWidgetManager.getInstance(app);
            int[] found = manager == null ? null : manager.getAppWidgetIds(provider(app));
            return found == null ? new int[0] : found;
        } catch (Throwable unknown) {
            return new int[0];
        }
    }

    /** Hand every widget on the home screen what it shows now. */
    static void draw(Context app) {
        AppWidgetManager manager = AppWidgetManager.getInstance(app);
        if (manager == null) return;
        for (int id : ids(app)) draw(app, manager, id);
    }

    static void draw(Context app, AppWidgetManager manager, int id) {
        try {
            Bundle room = manager.getAppWidgetOptions(id);
            // A launcher reports the room a widget has both ways up: the
            // tallest it gets is with the phone upright, the shortest on its
            // side. Each way up gets the drawing that fits it.
            int upright = room == null ? 0 : room.getInt(AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT);
            int sideways = room == null ? 0 : room.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT);
            RemoteViews standing = views(app, upright >= CARD_FROM);
            if (standing == null) return;
            if ((upright >= CARD_FROM) == (sideways >= CARD_FROM)) {
                manager.updateAppWidget(id, standing);
                return;
            }
            RemoteViews lying = views(app, sideways >= CARD_FROM);
            manager.updateAppWidget(id, lying == null ? standing : new RemoteViews(lying, standing));
        } catch (Throwable gone) {
            // A widget removed between the list and the update.
        }
    }

    private static RemoteViews views(Context app, boolean card) {
        String ours = app.getPackageName();
        String drawing = "apkpy_widget";
        if (card) drawing += "_card";
        int layout = app.getResources().getIdentifier(drawing, "layout", ours);
        if (layout == 0) return null;
        SharedPreferences store = app.getSharedPreferences(STORE, 0);
        String caption = store.getString("caption", CAPTION);
        RemoteViews views = new RemoteViews(ours, layout);
        views.setTextViewText(id(app, "apkpy_widget_title"), store.getString("title", TITLE));
        views.setTextViewText(id(app, "apkpy_widget_text"), store.getString("text", TEXT));
        views.setTextViewText(id(app, "apkpy_widget_caption"), caption);
        views.setViewVisibility(id(app, "apkpy_widget_caption"),
                ApkpyKitRules.trim(caption).isEmpty() ? View.GONE : View.VISIBLE);
        Intent launch = app.getPackageManager().getLaunchIntentForPackage(ours);
        if (launch != null) {
            launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            views.setOnClickPendingIntent(android.R.id.background, PendingIntent.getActivity(
                    app, 0, launch,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE));
        }
        return views;
    }

    private static int id(Context app, String name) {
        return app.getResources().getIdentifier(name, "id", app.getPackageName());
    }
}
