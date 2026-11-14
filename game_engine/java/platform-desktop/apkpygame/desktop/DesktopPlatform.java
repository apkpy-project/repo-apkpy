package apkpygame.desktop;

import apkpygame.core.Platform;
import apkpygame.core.json.Json;
import apkpygame.core.render.RenderBackend;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Desktop side of the core: the bundle is a folder, the store a JSON file
 * (the Previewer's game_get / game_set read the same file).
 */
final class DesktopPlatform implements Platform {
    final Java2DBackend renderer = new Java2DBackend();
    private final File bundle;
    private final File storeFile;

    private final AudioDevice audio;
    private final int phoneShortSide;

    DesktopPlatform(File bundle, File storeFile, boolean sound) {
        this(bundle, storeFile, sound, 0);
    }

    /** phoneShortSide: 1080 in the Previewer (a phone's screen, shown smaller); 0 in a window of its own. */
    DesktopPlatform(File bundle, File storeFile, boolean sound, int phoneShortSide) {
        this.bundle = bundle;
        this.storeFile = storeFile;
        this.audio = sound ? new JavaSoundAudio(bundle, logger()) : SILENT;
        this.phoneShortSide = phoneShortSide;
    }

    @Override public int phoneShortSide() {
        return phoneShortSide;
    }

    /** APKPYGAME_LANG (to try a translation on the PC), else the system's language. */
    @Override public String language() {
        String forced = System.getenv("APKPYGAME_LANG");
        return forced != null && !forced.isEmpty() ? forced : java.util.Locale.getDefault().getLanguage();
    }

    @Override public AudioDevice audio() {
        return audio;
    }

    @Override public RenderBackend renderer() {
        return renderer;
    }

    @Override public AssetSource assets() {
        return folder(bundle);
    }

    static AssetSource folder(final File root) {
        return new AssetSource() {
            @Override public byte[] read(String path) throws IOException {
                return Files.readAllBytes(new File(root, path).toPath());
            }

            @Override public boolean exists(String path) {
                return new File(root, path).isFile();
            }
        };
    }

    /** Beside the store (build/apkpygame/saves/): the Previewer has saves of its own. */
    @Override public SaveStore saves() {
        File base = storeFile.getAbsoluteFile().getParentFile();
        return new apkpygame.core.FileSaves(new File(base, "saves"), logger());
    }

    @Override public KeyValueStore store() {
        return new KeyValueStore() {
            @Override public String get(String key) {
                Object v = load().get(key);
                return v == null ? "" : String.valueOf(v);
            }

            @Override public void set(String key, String value) {
                Map<String, Object> data = load();
                data.put(key, value);
                try {
                    if (storeFile.getParentFile() != null) storeFile.getParentFile().mkdirs();
                    Files.write(storeFile.toPath(), Json.stringify(data).getBytes("UTF-8"));
                } catch (IOException e) {
                    logger().error("could not write " + storeFile, e);
                }
            }
        };
    }

    private Map<String, Object> load() {
        try {
            return Json.parseObject(new String(Files.readAllBytes(storeFile.toPath()), "UTF-8"));
        } catch (IOException | IllegalArgumentException e) {
            return new LinkedHashMap<String, Object>();
        }
    }

    @Override public Logger logger() {
        return new Logger() {
            @Override public void info(String message) {
                System.err.println("[apkpygame] " + message);
            }

            @Override public void warn(String message) {
                System.err.println("[apkpygame] warning: " + message);
            }

            @Override public void error(String message, Throwable error) {
                System.err.println("[apkpygame] " + message + ": " + error);
            }
        };
    }
}
