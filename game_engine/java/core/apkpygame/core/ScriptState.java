package apkpygame.core;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * The game's module-level state (STATE = GameState() in a game/ module),
 * translated to static fields of the module's class.
 *
 * <p>Each module with state registers here (from the generated GameScripts).
 * The engine resets all of it when a game is loaded, so a new game and a
 * journal played again (Game.restore) start from the same values, and mixes
 * it into the state hash, so the parity check sees it. A game without
 * module state registers nothing and its hashes do not change.
 */
public final class ScriptState {
    private ScriptState() { }

    /** A translated @dataclass: mixes its fields, in order, into a hash. */
    public interface Value {
        long mixState(long h);
    }

    /** The state of one module (generated). */
    public interface Module {
        void reset();

        long mix(long h);
    }

    private static final List<Module> modules = new ArrayList<Module>();

    public static synchronized void register(Module module) {
        modules.add(module);
    }

    public static synchronized boolean any() {
        return !modules.isEmpty();
    }

    /** Every module back to its starting values (a new game, or before a journal is played again). */
    public static synchronized void resetAll() {
        for (Module m : modules) m.reset();
    }

    public static synchronized long mixAll(long h) {
        for (Module m : modules) h = m.mix(h);
        return h;
    }

    /** FNV-1a over the value's parts; the same on every JVM (no identity hashes). */
    public static long mix(long h, Object v) {
        if (v == null) return mixLong(h, 0x6e6f6e65L);
        if (v instanceof Double) return mixLong(h, Double.doubleToLongBits((Double) v));
        if (v instanceof Integer) return mixLong(h, (Integer) v);
        if (v instanceof Boolean) return mixLong(h, ((Boolean) v) ? 1 : 2);
        if (v instanceof String) {
            String s = (String) v;
            h = mixLong(h, s.length());
            for (int i = 0; i < s.length(); i++) h = mixLong(h, s.charAt(i));
            return h;
        }
        if (v instanceof Value) return ((Value) v).mixState(h);
        if (v instanceof List) {
            List<?> l = (List<?>) v;
            h = mixLong(h, l.size());
            for (Object x : l) h = mix(h, x);
            return h;
        }
        if (v instanceof Map) {
            Map<?, ?> m = (Map<?, ?>) v;
            h = mixLong(h, m.size());
            for (Map.Entry<?, ?> e : m.entrySet()) {
                h = mix(h, e.getKey());
                h = mix(h, e.getValue());
            }
            return h;
        }
        if (v instanceof Entity) return mix(h, ((Entity) v).name);
        return mix(h, v.toString());
    }

    public static long mix(long h, double v) {
        return mixLong(h, Double.doubleToLongBits(v));
    }

    public static long mix(long h, int v) {
        return mixLong(h, v);
    }

    public static long mix(long h, boolean v) {
        return mixLong(h, v ? 1 : 2);
    }

    private static long mixLong(long h, long v) {
        for (int i = 0; i < 8; i++) {
            h ^= (v >>> (i * 8)) & 0xFF;
            h *= 0x100000001b3L;
        }
        return h;
    }
}
