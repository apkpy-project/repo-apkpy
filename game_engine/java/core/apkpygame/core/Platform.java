package apkpygame.core;

import apkpygame.core.render.RenderBackend;

/**
 * Everything the core needs from where it runs. Android and the desktop each
 * implement it; the core itself never imports android.* or java.awt.*.
 */
public interface Platform {
    RenderBackend renderer();

    AssetSource assets();

    KeyValueStore store();

    /** The game's save slots (saves.write / saves.read in scripts). */
    SaveStore saves();

    Logger logger();

    AudioDevice audio();

    /** The device's language ("en", "pt"...), for the texts shared with the app's translations(). */
    String language();

    /**
     * The short side, in pixels, of the phone screen the surface stands for; 0
     * when the surface is a real screen (the phone). The Previewer answers 1080.
     */
    default int phoneShortSide() {
        return 0;
    }

    /**
     * Sounds (short, several at once) and one music track. Paths are bundle
     * paths; a platform may read another encoding of the same file (the
     * desktop reads audio-desktop/PATH.wav, made by apkpygame build).
     */
    interface AudioDevice {
        /** Prepares a sound; answers the platform's handle. */
        Object loadSound(String path);

        void play(Object sound, double volume);

        void playMusic(String path, double volume, boolean loop);

        void stopMusic();

        /** The app went to the background (and came back). */
        void pause();

        void resume();

        void release();
    }

    /** No sound at all (headless runs, tests, screenshots). */
    AudioDevice SILENT = new AudioDevice() {
        @Override public Object loadSound(String path) { return path; }
        @Override public void play(Object sound, double volume) { }
        @Override public void playMusic(String path, double volume, boolean loop) { }
        @Override public void stopMusic() { }
        @Override public void pause() { }
        @Override public void resume() { }
        @Override public void release() { }
    };

    /** Reads files of the game bundle, by path relative to the bundle root. */
    interface AssetSource {
        byte[] read(String path) throws java.io.IOException;

        boolean exists(String path);
    }

    /** The key-value store shared with the ApkPy app (game_get / game_set). */
    interface KeyValueStore {
        String get(String key);

        void set(String key, String value);
    }

    /** Save slots: a text per slot name; read answers null when the slot is empty. */
    interface SaveStore {
        String read(String slot);

        void write(String slot, String text);

        void delete(String slot);
    }

    interface Logger {
        void info(String message);

        void warn(String message);

        void error(String message, Throwable error);
    }
}
