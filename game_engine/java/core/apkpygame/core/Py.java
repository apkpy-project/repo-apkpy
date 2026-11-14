package apkpygame.core;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Python's meaning of the operations Java does differently, for the code
 * apkpygame build translates: floor division and modulo with the sign of the
 * divisor, round half to even, str() of floats, negative list indexes, and
 * errors named like Python's (IndexError...). Tested against CPython by
 * src/python/tests/test_semantics.py.
 */
public final class Py {
    private Py() { }

    /** A Python error (the message starts with its Python name). */
    public static final class PyError extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public PyError(String message) {
            super(message);
        }
    }

    // ── numbers ──────────────────────────────────────────────────────────

    public static int floorDiv(int a, int b) {
        if (b == 0) throw new PyError("ZeroDivisionError: integer division or modulo by zero");
        return Math.floorDiv(a, b);
    }

    public static double floorDiv(double a, double b) {
        if (b == 0) throw new PyError("ZeroDivisionError: float floor division by zero");
        return Math.floor(a / b);
    }

    public static int mod(int a, int b) {
        if (b == 0) throw new PyError("ZeroDivisionError: integer division or modulo by zero");
        return Math.floorMod(a, b);
    }

    public static double mod(double a, double b) {
        if (b == 0) throw new PyError("ZeroDivisionError: float modulo");
        double r = a % b;
        if (r != 0 && ((r < 0) != (b < 0))) r += b;
        return r;
    }

    public static double div(double a, double b) {
        if (b == 0) throw new PyError("ZeroDivisionError: division by zero");
        return a / b;
    }

    public static int ipow(int a, int b) {
        if (b < 0) throw new PyError("ValueError: an int to a negative power is a float: write " + a + ".0 ** " + b);
        int r = 1;
        for (int i = 0; i < b; i++) r *= a;
        return r;
    }

    /** round(x): half to even, an int. */
    public static int round(double x) {
        return (int) Math.rint(x);
    }

    /** round(x, n) */
    public static double round(double x, int n) {
        if (Double.isNaN(x) || Double.isInfinite(x)) return x;
        // the exact binary value, rounded half to even: what Python does (round(2.675, 2) == 2.67)
        return new java.math.BigDecimal(x).setScale(n, java.math.RoundingMode.HALF_EVEN).doubleValue();
    }

    /** int(x) for a float: towards zero. */
    public static int toInt(double x) {
        if (Double.isNaN(x) || Double.isInfinite(x)) throw new PyError("ValueError: cannot convert " + x + " to int");
        return (int) x;
    }

    public static int toInt(String s) {
        try {
            return Integer.parseInt(s.trim());
        } catch (NumberFormatException e) {
            throw new PyError("ValueError: invalid literal for int(): '" + s + "'");
        }
    }

    public static double toFloat(String s) {
        try {
            return Double.parseDouble(s.trim());
        } catch (NumberFormatException e) {
            throw new PyError("ValueError: could not convert string to float: '" + s + "'");
        }
    }

    public static int sign(double x) {
        return x > 0 ? 1 : x < 0 ? -1 : 0;
    }

    // ── text ─────────────────────────────────────────────────────────────

    /** str(x) as Python writes it. */
    public static String str(double d) {
        if (Double.isNaN(d)) return "nan";
        if (Double.isInfinite(d)) return d > 0 ? "inf" : "-inf";
        if (d == Math.rint(d) && Math.abs(d) < 1e16) {
            String s = String.valueOf((long) d) + ".0";
            return d == 0 && 1 / d < 0 ? "-0.0" : s;
        }
        String s = Double.toString(d);           // shortest repr, as Python's
        int e = s.indexOf('E');
        if (e < 0) {
            double a = Math.abs(d);
            if (a < 1e-4) return sci(s, d);
            return s;
        }
        return sci(s, d);
    }

    private static String sci(String javaRepr, double d) {
        // Java: 1.0E16 / 1.2E-5 ; Python: 1e+16 / 1.2e-05
        java.math.BigDecimal b = new java.math.BigDecimal(javaRepr).stripTrailingZeros();
        String digits = b.unscaledValue().abs().toString();
        int exp = digits.length() - 1 - b.scale();
        String mantissa = digits.length() == 1 ? digits : digits.charAt(0) + "." + digits.substring(1);
        if (exp >= -4 && exp < 16) return Double.toString(d);
        return (d < 0 ? "-" : "") + mantissa + "e" + (exp < 0 ? "-" : "+") + (Math.abs(exp) < 10 ? "0" : "")
                + Math.abs(exp);
    }

    public static String str(int i) {
        return String.valueOf(i);
    }

    public static String str(boolean b) {
        return b ? "True" : "False";
    }

    public static String str(String s) {
        return s;
    }

    public static String str(Object o) {
        if (o == null) return "None";
        if (o instanceof Double) return str(((Double) o).doubleValue());
        if (o instanceof Boolean) return str(((Boolean) o).booleanValue());
        if (o instanceof Entity) return "<Entity " + ((Entity) o).name + ">";
        if (o instanceof List) {
            StringBuilder b = new StringBuilder("[");
            List<?> l = (List<?>) o;
            for (int i = 0; i < l.size(); i++) {
                if (i > 0) b.append(", ");
                Object x = l.get(i);
                b.append(repr(x));
            }
            return b.append(']').toString();
        }
        if (o instanceof Map) {
            StringBuilder b = new StringBuilder("{");
            boolean first = true;
            for (Map.Entry<?, ?> e : ((Map<?, ?>) o).entrySet()) {
                if (!first) b.append(", ");
                first = false;
                b.append(repr(e.getKey())).append(": ").append(repr(e.getValue()));
            }
            return b.append('}').toString();
        }
        return o.toString();
    }

    /** Python's repr for the values scripts hold: text in quotes, the rest as str(). */
    public static String repr(Object o) {
        if (o instanceof String) {
            String s = (String) o;
            return s.indexOf('\'') >= 0 && s.indexOf('"') < 0 ? "\"" + s + "\"" : "'" + s.replace("'", "\\'") + "'";
        }
        return str(o);
    }

    /** f"{x:.2f}", f"{n:03d}", f"{x:,}"... for the specs games use. */
    public static String format(double x, String spec) {
        if (spec.isEmpty()) return str(x);
        try {
            char type = spec.charAt(spec.length() - 1);
            String body = Character.isLetter(type) ? spec.substring(0, spec.length() - 1) : spec;
            if (type == 'd') return String.format(Locale.ROOT, "%" + body + "d", (long) x);
            if (type == '%') return String.format(Locale.ROOT, "%" + body.replace("%", "") + "f", x * 100) + "%";
            if (type == 'f' || type == 'e' || type == 'g') {
                return String.format(Locale.ROOT, "%" + body + type, x);
            }
            return String.format(Locale.ROOT, "%" + spec + "f", x);
        } catch (java.util.IllegalFormatException e) {
            throw new PyError("ValueError: format spec '" + spec + "' is not supported here");
        }
    }

    public static String format(int x, String spec) {
        if (spec.isEmpty()) return String.valueOf(x);
        char type = spec.charAt(spec.length() - 1);
        if (type == 'f' || type == 'e' || type == 'g' || type == '%') return format((double) x, spec);
        String body = type == 'd' ? spec.substring(0, spec.length() - 1) : spec;
        return String.format(Locale.ROOT, "%" + body + "d", x);
    }

    public static String format(String s, String spec) {
        if (spec.isEmpty()) return s;
        return String.format(Locale.ROOT, "%" + (spec.startsWith("<") ? "-" + spec.substring(1) : spec.replace(">", ""))
                + "s", s);
    }

    public static String repeat(String s, int n) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n; i++) b.append(s);
        return b.toString();
    }

    // ── lists and dicts ──────────────────────────────────────────────────

    private static int index(int size, int i) {
        int j = i < 0 ? size + i : i;
        if (j < 0 || j >= size) throw new PyError("IndexError: list index out of range (" + i + ", size " + size + ")");
        return j;
    }

    public static <T> T get(List<T> list, int i) {
        return list.get(index(list.size(), i));
    }

    public static <T> T set(List<T> list, int i, T value) {
        list.set(index(list.size(), i), value);
        return value;
    }

    /** d.get(key, default) */
    public static <T> T getOr(Map<String, T> map, String key, T otherwise) {
        return map.containsKey(key) ? map.get(key) : otherwise;
    }

    /** d.pop(key) */
    public static <T> T pop(Map<String, T> map, String key) {
        if (!map.containsKey(key)) throw new PyError("KeyError: '" + key + "'");
        return map.remove(key);
    }

    public static <T> T pop(List<T> list) {
        if (list.isEmpty()) throw new PyError("IndexError: pop from empty list");
        return list.remove(list.size() - 1);
    }

    public static <T> T pop(List<T> list, int i) {
        return list.remove(index(list.size(), i));
    }

    public static <T> T get(Map<String, T> map, String key) {
        T v = map.get(key);
        if (v == null && !map.containsKey(key)) throw new PyError("KeyError: '" + key + "'");
        return v;
    }

    @SafeVarargs
    public static <T> ArrayList<T> list(T... items) {
        ArrayList<T> out = new ArrayList<T>();
        for (T t : items) out.add(t);
        return out;
    }

    /** A dict literal for exit_game / open_app: "k1", v1, "k2", v2... (numbers become doubles, as in JSON). */
    public static Map<String, Object> map(Object... kv) {
        Map<String, Object> out = new LinkedHashMap<String, Object>();
        for (int i = 0; i + 1 < kv.length; i += 2) {
            Object v = kv[i + 1];
            if (v instanceof Integer) v = ((Integer) v).doubleValue();
            out.put((String) kv[i], v);
        }
        return out;
    }

    public static <T> T notNone(T value, String what) {
        if (value == null) throw new PyError("AttributeError: " + what + " is None");
        return value;
    }

    public static void print(Game game, String text) {
        game.platform.logger().info("print: " + text);
    }
}
