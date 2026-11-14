package apkpygame.core;

import apkpygame.core.render.Texture;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * Loads and caches the files of the bundle, by type. Each type has its own
 * loader ("image" today; "sound", "atlas", and later "mesh", "material"...),
 * so a new kind of asset never touches the others.
 */
public final class Assets {
    /** Reads what it needs through {@code assets} (bytes, or only the path, as Android audio does). */
    public interface Loader<T> {
        T load(String path, Assets assets);
    }

    private final Platform.AssetSource source;
    private final Map<String, Loader<?>> loaders = new HashMap<String, Loader<?>>();
    private final Map<String, Object> cache = new HashMap<String, Object>();

    Assets(Platform.AssetSource source) {
        this.source = source;
    }

    public <T> void register(String type, Loader<T> loader) {
        loaders.put(type, loader);
    }

    @SuppressWarnings("unchecked")
    public <T> T get(String type, String path) {
        String key = type + ":" + path;
        Object hit = cache.get(key);
        if (hit != null) return (T) hit;
        Loader<?> loader = loaders.get(type);
        if (loader == null) {
            throw new GameException("G3020", "no loader for assets of type '" + type + "'",
                    "This engine version does not know that type of asset.");
        }
        Object value = loader.load(path, this);
        cache.put(key, value);
        return (T) value;
    }

    public Texture texture(String path) {
        return get("image", path);
    }

    public String text(String path) {
        try {
            return new String(bytes(path), "UTF-8");
        } catch (java.io.UnsupportedEncodingException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    public boolean exists(String path) {
        return source.exists(path);
    }

    public byte[] bytes(String path) {
        try {
            return source.read(path);
        } catch (IOException e) {
            throw new GameException("G3021", "the asset '" + path + "' is not in the game bundle",
                    "Check the path (it is relative to the bundle) and that apkpygame build packed it.", e);
        }
    }

    /** Forgets everything (a new scene, a lost graphics context). */
    public void clear() {
        cache.clear();
    }
}
