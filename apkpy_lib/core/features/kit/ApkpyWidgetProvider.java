package __PACKAGE__;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.Context;
import android.os.Bundle;

/**
 * Who the launcher talks to about the app's widget.
 *
 * Android calls this when a widget is put on the home screen, when the phone
 * starts, when the app is updated, and when the person drags the widget to
 * another size. Every time the answer is the same: what ApkpyWidget keeps.
 */
public final class ApkpyWidgetProvider extends AppWidgetProvider {

    @Override
    public void onUpdate(Context context, AppWidgetManager manager, int[] ids) {
        if (ids == null) return;
        for (int id : ids) ApkpyWidget.draw(context.getApplicationContext(), manager, id);
    }

    @Override
    public void onAppWidgetOptionsChanged(Context context, AppWidgetManager manager, int id,
                                          Bundle options) {
        ApkpyWidget.draw(context.getApplicationContext(), manager, id);
    }
}
