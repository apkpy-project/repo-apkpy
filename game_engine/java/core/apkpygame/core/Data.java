package apkpygame.core;

import apkpygame.core.json.Json;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * JSON for the translated scripts: to_json(x) / from_json(text, Type) and the
 * rows of data tables. The text written is the same as CPython's
 * json.dumps(value, separators=(",", ":")) (ensure_ascii, Python's float
 * repr), so a save written on the PC, on the phone and in a CPython test is
 * the same text.
 */
public final class Data {
    private Data() { }

    /** A translated @dataclass. */
    public interface Record {
        void writeJson(StringBuilder out);
    }

    /** How one value of a list or dict is made from JSON. */
    public interface Maker<T> {
        T make(Object json);
    }

    // ── writing ──────────────────────────────────────────────────────────

    public static String json(Object value) {
        StringBuilder b = new StringBuilder();
        write(b, value);
        return b.toString();
    }

    public static void write(StringBuilder b, Object v) {
        if (v == null) {
            b.append("null");
        } else if (v instanceof Boolean) {
            b.append(((Boolean) v) ? "true" : "false");
        } else if (v instanceof Integer) {
            b.append(((Integer) v).intValue());
        } else if (v instanceof Double) {
            double d = (Double) v;
            if (Double.isNaN(d)) b.append("NaN");
            else if (Double.isInfinite(d)) b.append(d > 0 ? "Infinity" : "-Infinity");
            else b.append(Py.str(d));
        } else if (v instanceof String) {
            string(b, (String) v);
        } else if (v instanceof Record) {
            ((Record) v).writeJson(b);
        } else if (v instanceof List) {
            b.append('[');
            List<?> l = (List<?>) v;
            for (int i = 0; i < l.size(); i++) {
                if (i > 0) b.append(',');
                write(b, l.get(i));
            }
            b.append(']');
        } else if (v instanceof Map) {
            b.append('{');
            boolean first = true;
            for (Map.Entry<?, ?> e : ((Map<?, ?>) v).entrySet()) {
                if (!first) b.append(',');
                first = false;
                string(b, String.valueOf(e.getKey()));
                b.append(':');
                write(b, e.getValue());
            }
            b.append('}');
        } else {
            throw new Py.PyError("TypeError: " + v.getClass().getSimpleName() + " is not JSON serializable");
        }
    }

    /** A field of a record: "name": value (with the comma before it when it is not the first). */
    public static void field(StringBuilder b, boolean first, String name, Object value) {
        if (!first) b.append(',');
        string(b, name);
        b.append(':');
        write(b, value);
    }

    private static void string(StringBuilder b, String s) {
        b.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                case '\b': b.append("\\b"); break;
                case '\f': b.append("\\f"); break;
                default:
                    if (c < 0x20 || c > 0x7e && c != 0x7f) b.append(String.format("\\u%04x", (int) c));
                    else b.append(c);
            }
        }
        b.append('"');
    }

    // ── reading ──────────────────────────────────────────────────────────

    public static Object parse(String text) {
        try {
            return Json.parse(text);
        } catch (RuntimeException e) {
            throw new Py.PyError("ValueError: not JSON (" + e.getMessage() + ")");
        }
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> object(Object v, String what) {
        if (v instanceof Map) return (Map<String, Object>) v;
        throw new Py.PyError("ValueError: " + what + " is a JSON object, got " + shown(v));
    }

    public static Py.PyError missing(String type, String field) {
        return new Py.PyError("ValueError: " + type + " needs '" + field + "' (it has no default)");
    }

    public static int toInt(Object v) {
        if (v instanceof Integer) return (Integer) v;
        if (v instanceof Double) {
            double d = (Double) v;
            if (d == Math.rint(d) && Math.abs(d) <= Integer.MAX_VALUE) return (int) d;
        }
        throw new Py.PyError("ValueError: expected a whole number, got " + shown(v));
    }

    public static double toFloat(Object v) {
        if (v instanceof Double) return (Double) v;
        if (v instanceof Integer) return (Integer) v;
        throw new Py.PyError("ValueError: expected a number, got " + shown(v));
    }

    public static boolean toBool(Object v) {
        if (v instanceof Boolean) return (Boolean) v;
        throw new Py.PyError("ValueError: expected true or false, got " + shown(v));
    }

    public static String toStr(Object v) {
        if (v instanceof String) return (String) v;
        throw new Py.PyError("ValueError: expected a text, got " + shown(v));
    }

    /** An Optional field: JSON null is None. */
    public static <T> T orNull(Object v, Maker<T> make) {
        return v == null ? null : make.make(v);
    }

    public static <T> ArrayList<T> list(Object v, Maker<T> make) {
        if (!(v instanceof List)) throw new Py.PyError("ValueError: expected a list, got " + shown(v));
        ArrayList<T> out = new ArrayList<T>();
        for (Object x : (List<?>) v) out.add(make.make(x));
        return out;
    }

    public static <T> LinkedHashMap<String, T> dict(Object v, Maker<T> make) {
        Map<String, Object> m = object(v, "a dict");
        LinkedHashMap<String, T> out = new LinkedHashMap<String, T>();
        for (Map.Entry<String, Object> e : m.entrySet()) out.put(e.getKey(), make.make(e.getValue()));
        return out;
    }

    private static String shown(Object v) {
        if (v == null) return "null";
        if (v instanceof String) return "\"" + v + "\"";
        if (v instanceof Map) return "an object";
        if (v instanceof List) return "a list";
        return String.valueOf(v);
    }
}
