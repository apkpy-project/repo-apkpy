package apkpygame.core;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * The custom properties of the Tiled object an entity was made from
 * (self.props.get_str("event") in scripts). Values are what Tiled saves:
 * texts, numbers and true/false. A missing key gives the default.
 */
public final class Props {
    public static final Props NONE = new Props(Collections.<String, Object>emptyMap());

    private final Map<String, Object> values;

    public Props(Map<String, Object> values) {
        this.values = new LinkedHashMap<String, Object>(values);
    }

    public boolean has(String key) {
        return values.containsKey(key);
    }

    public String getStr(String key, String otherwise) {
        Object v = values.get(key);
        return v == null ? otherwise : v instanceof Double ? Py.str((Double) v) : String.valueOf(v);
    }

    public int getInt(String key, int otherwise) {
        Object v = values.get(key);
        if (v instanceof Double) return (int) Math.floor((Double) v);
        if (v instanceof Boolean) return ((Boolean) v) ? 1 : 0;
        if (v instanceof String) {
            try {
                return Integer.parseInt(((String) v).trim());
            } catch (NumberFormatException e) {
                return otherwise;
            }
        }
        return otherwise;
    }

    public double getFloat(String key, double otherwise) {
        Object v = values.get(key);
        if (v instanceof Double) return (Double) v;
        if (v instanceof String) {
            try {
                return Double.parseDouble(((String) v).trim());
            } catch (NumberFormatException e) {
                return otherwise;
            }
        }
        return otherwise;
    }

    public boolean getBool(String key, boolean otherwise) {
        Object v = values.get(key);
        if (v instanceof Boolean) return (Boolean) v;
        if (v instanceof String) return "true".equalsIgnoreCase(((String) v).trim());
        return otherwise;
    }
}
