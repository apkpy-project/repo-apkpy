package __PACKAGE__;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;

/**
 * Starts ApkpyAppLock with the app's process, before any of its screens.
 *
 * A provider is made by Android as the process starts, whatever starts it --
 * the launcher, a notification, the recent apps -- and before the first
 * screen is. That is the moment the lock has to be watching from: an app
 * closed from the recent apps and opened again must come back locked, with
 * none of its own code run first. It holds nothing and answers nothing.
 */
public final class ApkpyAppLockStart extends ContentProvider {

    @Override public boolean onCreate() {
        if (getContext() != null) ApkpyAppLock.start(getContext());
        return true;
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection,
                                  String[] arguments, String order) {
        return null;
    }

    @Override public String getType(Uri uri) {
        return null;
    }

    @Override public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override public int delete(Uri uri, String selection, String[] arguments) {
        return 0;
    }

    @Override public int update(Uri uri, ContentValues values, String selection,
                                String[] arguments) {
        return 0;
    }
}
