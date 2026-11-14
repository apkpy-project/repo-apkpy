package apkpygame.core.json;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * A small JSON reader and writer. The core runs on Android (which has
 * org.json) and on the desktop JVM (which has nothing), so it carries its own.
 *
 * Objects are {@code LinkedHashMap<String, Object>} (key order kept), arrays
 * {@code ArrayList<Object>}, numbers {@code Double}, plus String, Boolean, null.
 */
public final class Json {
    private final String text;
    private int at;

    private Json(String text) {
        this.text = text;
    }

    public static Object parse(String text) {
        Json reader = new Json(text);
        reader.space();
        Object value = reader.value();
        reader.space();
        if (reader.at != text.length()) {
            throw reader.error("text after the end of the value");
        }
        return value;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> parseObject(String text) {
        Object value = parse(text);
        if (!(value instanceof Map)) {
            throw new IllegalArgumentException("JSON: expected an object");
        }
        return (Map<String, Object>) value;
    }

    // ── reading ──────────────────────────────────────────────────────────

    private Object value() {
        if (at >= text.length()) throw error("unexpected end");
        char c = text.charAt(at);
        switch (c) {
            case '{': return object();
            case '[': return array();
            case '"': return string();
            case 't': word("true"); return Boolean.TRUE;
            case 'f': word("false"); return Boolean.FALSE;
            case 'n': word("null"); return null;
            default:
                if (c == '-' || (c >= '0' && c <= '9')) return number();
                throw error("unexpected '" + c + "'");
        }
    }

    private Map<String, Object> object() {
        Map<String, Object> map = new LinkedHashMap<String, Object>();
        at++;
        space();
        if (peek() == '}') { at++; return map; }
        while (true) {
            space();
            if (peek() != '"') throw error("expected a key");
            String key = string();
            space();
            expect(':');
            space();
            map.put(key, value());
            space();
            char c = next();
            if (c == '}') return map;
            if (c != ',') throw error("expected ',' or '}'");
        }
    }

    private List<Object> array() {
        List<Object> list = new ArrayList<Object>();
        at++;
        space();
        if (peek() == ']') { at++; return list; }
        while (true) {
            space();
            list.add(value());
            space();
            char c = next();
            if (c == ']') return list;
            if (c != ',') throw error("expected ',' or ']'");
        }
    }

    private String string() {
        at++;
        StringBuilder out = new StringBuilder();
        while (true) {
            if (at >= text.length()) throw error("unterminated string");
            char c = text.charAt(at++);
            if (c == '"') return out.toString();
            if (c != '\\') { out.append(c); continue; }
            char e = next();
            switch (e) {
                case '"': out.append('"'); break;
                case '\\': out.append('\\'); break;
                case '/': out.append('/'); break;
                case 'b': out.append('\b'); break;
                case 'f': out.append('\f'); break;
                case 'n': out.append('\n'); break;
                case 'r': out.append('\r'); break;
                case 't': out.append('\t'); break;
                case 'u':
                    if (at + 4 > text.length()) throw error("bad \\u escape");
                    out.append((char) Integer.parseInt(text.substring(at, at + 4), 16));
                    at += 4;
                    break;
                default: throw error("bad escape \\" + e);
            }
        }
    }

    private Double number() {
        int start = at;
        if (peek() == '-') at++;
        while (at < text.length()) {
            char c = text.charAt(at);
            if ((c >= '0' && c <= '9') || c == '.' || c == 'e' || c == 'E' || c == '+' || c == '-') at++;
            else break;
        }
        try {
            return Double.valueOf(text.substring(start, at));
        } catch (NumberFormatException e) {
            throw error("bad number");
        }
    }

    private void word(String word) {
        if (!text.startsWith(word, at)) throw error("expected " + word);
        at += word.length();
    }

    private void space() {
        while (at < text.length() && Character.isWhitespace(text.charAt(at))) at++;
    }

    private char peek() {
        return at < text.length() ? text.charAt(at) : '\0';
    }

    private char next() {
        if (at >= text.length()) throw error("unexpected end");
        return text.charAt(at++);
    }

    private void expect(char c) {
        if (next() != c) throw error("expected '" + c + "'");
    }

    private IllegalArgumentException error(String what) {
        int line = 1;
        for (int i = 0; i < Math.min(at, text.length()); i++) if (text.charAt(i) == '\n') line++;
        return new IllegalArgumentException("JSON line " + line + ": " + what);
    }

    // ── writing ──────────────────────────────────────────────────────────

    public static String stringify(Object value) {
        StringBuilder out = new StringBuilder();
        write(out, value);
        return out.toString();
    }

    @SuppressWarnings("unchecked")
    private static void write(StringBuilder out, Object value) {
        if (value == null) {
            out.append("null");
        } else if (value instanceof String) {
            quote(out, (String) value);
        } else if (value instanceof Boolean) {
            out.append(value.toString());
        } else if (value instanceof Double || value instanceof Float) {
            double d = ((Number) value).doubleValue();
            if (d == Math.rint(d) && Math.abs(d) < 1e15) out.append((long) d);
            else out.append(d);
        } else if (value instanceof Number) {
            out.append(((Number) value).longValue());
        } else if (value instanceof Map) {
            out.append('{');
            boolean first = true;
            for (Map.Entry<String, Object> e : ((Map<String, Object>) value).entrySet()) {
                if (!first) out.append(',');
                first = false;
                quote(out, e.getKey());
                out.append(':');
                write(out, e.getValue());
            }
            out.append('}');
        } else if (value instanceof List) {
            out.append('[');
            boolean first = true;
            for (Object item : (List<Object>) value) {
                if (!first) out.append(',');
                first = false;
                write(out, item);
            }
            out.append(']');
        } else {
            quote(out, value.toString());
        }
    }

    private static void quote(StringBuilder out, String s) {
        out.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': out.append("\\\""); break;
                case '\\': out.append("\\\\"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default:
                    if (c < 0x20) out.append(String.format("\\u%04x", (int) c));
                    else out.append(c);
            }
        }
        out.append('"');
    }

    // ── typed access, with defaults (bundle readers use these) ───────────

    public static double num(Map<String, Object> obj, String key, double fallback) {
        Object v = obj.get(key);
        return v instanceof Number ? ((Number) v).doubleValue() : fallback;
    }

    public static String str(Map<String, Object> obj, String key, String fallback) {
        Object v = obj.get(key);
        return v instanceof String ? (String) v : fallback;
    }

    public static boolean bool(Map<String, Object> obj, String key, boolean fallback) {
        Object v = obj.get(key);
        return v instanceof Boolean ? (Boolean) v : fallback;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> obj(Map<String, Object> obj, String key) {
        Object v = obj.get(key);
        return v instanceof Map ? (Map<String, Object>) v : null;
    }

    @SuppressWarnings("unchecked")
    public static List<Object> list(Map<String, Object> obj, String key) {
        Object v = obj.get(key);
        return v instanceof List ? (List<Object>) v : new ArrayList<Object>();
    }

    /** A pair written as [a, b], or one number used for both. */
    public static double[] pair(Map<String, Object> obj, String key, double a, double b) {
        Object v = obj.get(key);
        if (v instanceof Number) {
            double d = ((Number) v).doubleValue();
            return new double[]{d, d};
        }
        if (v instanceof List && ((List<?>) v).size() == 2) {
            List<?> l = (List<?>) v;
            return new double[]{((Number) l.get(0)).doubleValue(), ((Number) l.get(1)).doubleValue()};
        }
        return new double[]{a, b};
    }
}
