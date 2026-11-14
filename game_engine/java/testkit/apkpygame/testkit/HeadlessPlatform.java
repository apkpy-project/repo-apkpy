package apkpygame.testkit;

import apkpygame.core.Platform;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderBackend;
import apkpygame.core.render.Texture;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * A platform with no window: assets come from any AssetSource, images are
 * read for their size only, and drawing is counted instead of done. Used
 * by tests and by the parity check (the same steps on the JVM and on the phone).
 */
public final class HeadlessPlatform implements Platform {
    private final AssetSource assets;
    private final Map<String, String> store = new HashMap<String, String>();
    public int drawn;

    public HeadlessPlatform(AssetSource assets) {
        this.assets = assets;
    }

    private final RenderBackend renderer = new RenderBackend() {
        @Override public Texture loadTexture(String path, byte[] data) {
            int[] size = pngSize(data);
            return new Texture(path, size[0], size[1], null);
        }

        @Override public Object loadFont(String path, byte[] data) { return null; }
        @Override public void begin(int w, int h, int clear) { }

        @Override public void draw(DrawCommand command) {
            drawn++;
        }

        @Override public void end() { }
    };

    @Override public RenderBackend renderer() {
        return renderer;
    }

    @Override public AssetSource assets() {
        return assets;
    }

    /** "en" unless set (tests of translated texts). */
    public String language = "en";

    @Override public String language() {
        return language;
    }

    @Override public AudioDevice audio() {
        return SILENT;
    }

    /** In memory: a replay never touches the files of the Previewer or the phone. */
    public final java.util.Map<String, String> saveSlots = new java.util.HashMap<String, String>();

    @Override public SaveStore saves() {
        return new SaveStore() {
            @Override public String read(String slot) { return saveSlots.get(slot); }
            @Override public void write(String slot, String text) { saveSlots.put(slot, text); }
            @Override public void delete(String slot) { saveSlots.remove(slot); }
        };
    }

    @Override public KeyValueStore store() {
        return new KeyValueStore() {
            @Override public String get(String key) {
                String v = store.get(key);
                return v == null ? "" : v;
            }

            @Override public void set(String key, String value) {
                store.put(key, value);
            }
        };
    }

    @Override public Logger logger() {
        return new Logger() {
            @Override public void info(String message) { }

            @Override public void warn(String message) {
                System.err.println("[apkpygame] " + message);
            }

            @Override public void error(String message, Throwable error) {
                System.err.println("[apkpygame] " + message + ": " + error);
            }
        };
    }

    /** Width and height from a PNG header (other formats: 1x1, enough for logic). */
    static int[] pngSize(byte[] d) {
        if (d != null && d.length > 24 && (d[0] & 0xFF) == 0x89 && d[1] == 'P' && d[2] == 'N' && d[3] == 'G') {
            return new int[]{readInt(d, 16), readInt(d, 20)};
        }
        return new int[]{1, 1};
    }

    private static int readInt(byte[] d, int at) {
        return ((d[at] & 0xFF) << 24) | ((d[at + 1] & 0xFF) << 16) | ((d[at + 2] & 0xFF) << 8) | (d[at + 3] & 0xFF);
    }

    /** Assets kept in memory (tests). */
    public static final class MemoryAssets implements AssetSource {
        private final Map<String, byte[]> files = new HashMap<String, byte[]>();

        public MemoryAssets put(String path, String text) {
            try {
                files.put(path, text.getBytes("UTF-8"));
            } catch (java.io.UnsupportedEncodingException impossible) {
                throw new IllegalStateException(impossible);
            }
            return this;
        }

        public MemoryAssets put(String path, byte[] data) {
            files.put(path, data);
            return this;
        }

        @Override public byte[] read(String path) throws IOException {
            byte[] d = files.get(path);
            if (d == null) throw new IOException("no " + path);
            return d;
        }

        @Override public boolean exists(String path) {
            return files.containsKey(path);
        }
    }
}
