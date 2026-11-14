package apkpygame.android;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.res.AssetManager;
import android.util.Log;

import apkpygame.core.Platform;
import apkpygame.core.render.RenderBackend;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;

/**
 * Android side of the core: the bundle is in the APK's assets under
 * {@code apkpygame/} (put there by game.aar), the store is the
 * SharedPreferences file "apkpygame" (the same one game_get/game_set read).
 */
final class AndroidPlatform implements Platform {
    static final String BUNDLE = "apkpygame/";
    static final String PREFS = "apkpygame";

    private final Context context;
    final CanvasBackend renderer = new CanvasBackend();
    /** Set when the game is drawn with OpenGL ES (GlGameView); textures are Bitmaps either way. */
    GlesBackend gles;
    final AndroidAudio audio;

    AndroidPlatform(Context context) {
        this.context = context.getApplicationContext();
        this.audio = new AndroidAudio(this.context.getAssets());
    }

    @Override public String language() {
        return java.util.Locale.getDefault().getLanguage();
    }

    @Override public AudioDevice audio() {
        return audio;
    }

    @Override public RenderBackend renderer() {
        return gles != null ? gles : renderer;
    }

    @Override public AssetSource assets() {
        return assets(context);
    }

    static AssetSource assets(Context context) {
        final AssetManager manager = context.getApplicationContext().getAssets();
        return new AssetSource() {
            @Override public byte[] read(String path) throws IOException {
                InputStream in = manager.open(BUNDLE + path);
                try {
                    ByteArrayOutputStream out = new ByteArrayOutputStream();
                    byte[] buffer = new byte[16384];
                    int n;
                    while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
                    return out.toByteArray();
                } finally {
                    in.close();
                }
            }

            @Override public boolean exists(String path) {
                try {
                    manager.open(BUNDLE + path).close();
                    return true;
                } catch (IOException e) {
                    return false;
                }
            }
        };
    }

    @Override public SaveStore saves() {
        return new apkpygame.core.FileSaves(new java.io.File(context.getFilesDir(), "apkpygame/saves"), logger());
    }

    @Override public KeyValueStore store() {
        final SharedPreferences prefs = prefs(context);
        return new KeyValueStore() {
            @Override public String get(String key) {
                return prefs.getString(key, "");
            }

            @Override public void set(String key, String value) {
                prefs.edit().putString(key, value).apply();
            }
        };
    }

    static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    @Override public Logger logger() {
        return LOGGER;
    }

    static final Logger LOGGER = new Logger() {
        @Override public void info(String message) {
            Log.i("apkpygame", message);
        }

        @Override public void warn(String message) {
            Log.w("apkpygame", message);
        }

        @Override public void error(String message, Throwable error) {
            Log.e("apkpygame", message, error);
        }
    };
}
