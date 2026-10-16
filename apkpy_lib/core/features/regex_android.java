package __PACKAGE__;

/** Native runtime for the compiler's validated Python re subset. */
public final class ApkpyRegex {
    private static final org.json.JSONArray SPECS;
    static {
        try { SPECS = new org.json.JSONArray(__SPECS__); }
        catch (org.json.JSONException e) { throw new ExceptionInInitializerError(e); }
    }
    private static final java.util.LinkedHashMap<String, java.util.regex.Pattern> CACHE =
        new java.util.LinkedHashMap<String, java.util.regex.Pattern>(32, .75f, true) {
            @Override protected boolean removeEldestEntry(java.util.Map.Entry<String, java.util.regex.Pattern> e) {
                return size() > 32;
            }
        };
    private ApkpyRegex() { }

    private static synchronized java.util.regex.Pattern pattern(int id, boolean consuming) {
        String key = id + ":" + consuming;
        java.util.regex.Pattern p = CACHE.get(key);
        if (p == null) {
            try {
                String source = SPECS.getJSONObject(id).getString("java");
                // Python >= 3.7 permits a nonempty match at the same position
                // immediately after an empty match; plain Matcher.find skips it.
                // ICU's \\G does not consistently track a new region start.
                // Capture the remaining suffix in an atomic lookahead, then
                // forbid that same suffix at the end of the match. The extra
                // internal capture is hidden by Scan's MatchResult adapter.
                if (consuming) source = "(?=([\\s\\S]*))(?:" + source + ")(?!\\1\\z)";
                p = java.util.regex.Pattern.compile(source);
                CACHE.put(key, p);
            } catch (Exception e) {
                throw new IllegalArgumentException("ApkPy regex: invalid generated pattern " + id + ": " + e.getMessage(), e);
            }
        }
        return p;
    }

    private static void validText(String input) {
        if (input == null) throw new IllegalArgumentException("ApkPy regex expects a string, not None");
        for (int i = 0; i < input.length(); i++) {
            char c = input.charAt(i);
            if (Character.isHighSurrogate(c)) {
                if (++i == input.length() || !Character.isLowSurrogate(input.charAt(i)))
                    throw new IllegalArgumentException("ApkPy regex: unpaired Unicode surrogate");
            } else if (Character.isLowSurrogate(c)) {
                throw new IllegalArgumentException("ApkPy regex: unpaired Unicode surrogate");
            }
        }
    }
    public static String text(Object value) {
        if (!(value instanceof String)) throw new IllegalArgumentException("ApkPy regex expects string input/replacement, not None or another type");
        return (String)value;
    }

    public static String match(int id, String text) { return first(id, text, false); }
    public static String search(int id, String text) { return first(id, text, true); }
    private static String first(int id, String text, boolean search) {
        validText(text);
        java.util.regex.Matcher m = pattern(id, false).matcher(text);
        return (search ? m.find() : m.lookingAt()) ? snapshot(id, m, text) : null;
    }
    private static String snapshot(int id, java.util.regex.Matcher m, String text) {
        try {
            org.json.JSONArray groups = new org.json.JSONArray(), starts = new org.json.JSONArray(), ends = new org.json.JSONArray();
            for (int i = 0; i <= m.groupCount(); i++) {
                groups.put(m.group(i) == null ? org.json.JSONObject.NULL : m.group(i));
                starts.put(m.start(i) < 0 ? -1 : text.codePointCount(0, m.start(i)));
                ends.put(m.end(i) < 0 ? -1 : text.codePointCount(0, m.end(i)));
            }
            return new org.json.JSONObject().put("p", id).put("g", groups).put("s", starts).put("e", ends).toString();
        } catch (org.json.JSONException e) { throw new IllegalStateException(e); }
    }
    private static org.json.JSONObject result(String value) {
        if (value == null) throw new IllegalStateException("ApkPy regex: no match. Check 'if result:' before reading a group.");
        try { return new org.json.JSONObject(value); }
        catch (org.json.JSONException e) { throw new IllegalArgumentException("ApkPy regex: expected a Match result", e); }
    }
    private static int index(org.json.JSONObject result, String key) throws org.json.JSONException {
        int number;
        if (key.startsWith("i:")) number = Integer.parseInt(key.substring(2));
        else {
            if (!key.startsWith("n:")) throw new IllegalArgumentException("ApkPy regex: invalid group selector");
            key = key.substring(2);
            org.json.JSONObject names = SPECS.getJSONObject(result.getInt("p")).getJSONObject("names");
            if (!names.has(key)) throw new IllegalArgumentException("ApkPy regex: unknown group '" + key + "'");
            number = names.getInt(key);
        }
        if (number < 0 || number >= result.getJSONArray("g").length())
            throw new IllegalArgumentException("ApkPy regex: group index out of range: " + key);
        return number;
    }
    public static String group(String value, String key) {
        org.json.JSONObject r = result(value);
        try {
            org.json.JSONArray groups = r.getJSONArray("g"); int i = index(r, key);
            return groups.isNull(i) ? null : groups.getString(i);
        } catch (org.json.JSONException e) { throw new IllegalStateException(e); }
    }
    public static String groups(String value, String fallback) {
        try {
            org.json.JSONArray src = result(value).getJSONArray("g"), out = new org.json.JSONArray();
            for (int i = 1; i < src.length(); i++) out.put(src.isNull(i)
                    ? (fallback == null ? org.json.JSONObject.NULL : fallback) : src.get(i));
            return out.toString();
        } catch (org.json.JSONException e) { throw new IllegalStateException(e); }
    }
    private static int position(String value, String key, String field) {
        org.json.JSONObject r = result(value);
        try { return r.getJSONArray(field).getInt(index(r, key)); }
        catch (org.json.JSONException e) { throw new IllegalStateException(e); }
    }
    public static String start(String value, String key) { return String.valueOf(position(value, key, "s")); }
    public static String end(String value, String key) { return String.valueOf(position(value, key, "e")); }
    public static String span(String value, String key) {
        return new org.json.JSONArray().put(position(value, key, "s")).put(position(value, key, "e")).toString();
    }
    public static String nonempty(String value) {
        try { return String.valueOf(new org.json.JSONArray(value).length() > 0); }
        catch (Exception e) { throw new IllegalArgumentException("ApkPy regex: expected result sequence", e); }
    }

    private static final class Scan {
        final int id; final String text; int offset; boolean afterEmpty;
        Scan(int id, String text) { validText(text); this.id = id; this.text = text; }
        java.util.regex.MatchResult next() {
            while (offset <= text.length()) {
                java.util.regex.Matcher m = pattern(id, afterEmpty).matcher(text)
                    .region(offset, text.length()).useTransparentBounds(true).useAnchoringBounds(false);
                boolean found = afterEmpty ? m.lookingAt() : m.find();
                if (found) {
                    if (afterEmpty && m.start() == m.end())
                        throw new IllegalStateException("ApkPy regex: engine did not advance after an empty match");
                    final int shift = afterEmpty ? 1 : 0;
                    offset = m.end(); afterEmpty = m.start() == m.end();
                    return new java.util.regex.MatchResult() {
                        private int at(int i) { return i == 0 ? 0 : i + shift; }
                        public int groupCount() { return m.groupCount() - shift; }
                        public String group() { return m.group(); }
                        public String group(int i) { return m.group(at(i)); }
                        public int start() { return m.start(); }
                        public int start(int i) { return m.start(at(i)); }
                        public int end() { return m.end(); }
                        public int end(int i) { return m.end(at(i)); }
                    };
                }
                if (!afterEmpty || offset == text.length()) return null;
                offset = text.offsetByCodePoints(offset, 1); afterEmpty = false;
            }
            return null;
        }
    }
    public static String findall(int id, String text) {
        Scan scan = new Scan(id, text); org.json.JSONArray out = new org.json.JSONArray(); java.util.regex.MatchResult m;
        while ((m = scan.next()) != null) {
            if (m.groupCount() == 0) out.put(m.group());
            else if (m.groupCount() == 1) out.put(m.group(1) == null ? "" : m.group(1));
            else {
                org.json.JSONArray row = new org.json.JSONArray();
                for (int i = 1; i <= m.groupCount(); i++) row.put(m.group(i) == null ? "" : m.group(i));
                out.put(row);
            }
        }
        return out.toString();
    }

    private static java.util.List<Object> replacement(int id, String text) {
        validText(text);
        java.util.List<Object> parts = new java.util.ArrayList<>(); StringBuilder literal = new StringBuilder();
        int groupCount = pattern(id, false).matcher("").groupCount();
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c != '\\') { literal.append(c); continue; }
            if (++i >= text.length()) throw new IllegalArgumentException("ApkPy regex replacement: trailing backslash");
            c = text.charAt(i); Integer group = null;
            if (c == 'g') {
                if (++i >= text.length() || text.charAt(i) != '<') throw new IllegalArgumentException("ApkPy regex replacement: expected \\g<group>");
                int close = text.indexOf('>', ++i);
                if (close < 0) throw new IllegalArgumentException("ApkPy regex replacement: missing >");
                String key = text.substring(i, close);
                if (key.matches("[0-9]+")) group = Integer.valueOf(key);
                else {
                    try {
                        org.json.JSONObject names = SPECS.getJSONObject(id).getJSONObject("names");
                        if (!names.has(key)) throw new IllegalArgumentException("ApkPy regex replacement: unknown group " + key);
                        group = names.getInt(key);
                    } catch (org.json.JSONException e) { throw new IllegalArgumentException(e); }
                }
                i = close;
            } else if (c >= '0' && c <= '9') {
                int begin = i;
                boolean octal = c == '0' || (c <= '7' && i + 2 < text.length()
                    && text.charAt(i + 1) >= '0' && text.charAt(i + 1) <= '7'
                    && text.charAt(i + 2) >= '0' && text.charAt(i + 2) <= '7');
                if (octal) {
                    while (i + 1 < text.length() && i - begin < 2 && text.charAt(i + 1) >= '0' && text.charAt(i + 1) <= '7') i++;
                    int value = Integer.parseInt(text.substring(begin, i + 1), 8);
                    if (value > 255) throw new IllegalArgumentException("ApkPy regex replacement: octal escape exceeds 377");
                    literal.append((char)value);
                } else {
                    if (i + 1 < text.length() && text.charAt(i + 1) >= '0' && text.charAt(i + 1) <= '9') i++;
                    group = Integer.valueOf(text.substring(begin, i + 1));
                }
            } else {
                String escapes = "abfnrtv\\", values = "\u0007\b\f\n\r\t\u000b\\";
                int at = escapes.indexOf(c);
                if (at >= 0) literal.append(values.charAt(at));
                else if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'))
                    throw new IllegalArgumentException("ApkPy regex replacement: unknown escape \\" + c);
                else literal.append('\\').append(c);
            }
            if (group != null) {
                if (group > groupCount) throw new IllegalArgumentException("ApkPy regex replacement: group out of range " + group);
                parts.add(literal.toString()); literal.setLength(0); parts.add(group);
            }
        }
        parts.add(literal.toString()); return parts;
    }
    public static String sub(int id, String repl, String text, String countText) {
        validText(text); int count;
        try { count = Integer.parseInt(countText); }
        catch (NumberFormatException e) { throw new IllegalArgumentException("ApkPy regex count must be an integer", e); }
        java.util.List<Object> parts = replacement(id, repl); // Validate even with no matches.
        if (count < 0) return text;
        Scan scan = new Scan(id, text); java.util.regex.MatchResult m; StringBuilder out = new StringBuilder();
        int copied = 0, replacements = 0;
        while ((count == 0 || replacements < count) && (m = scan.next()) != null) {
            out.append(text, copied, m.start());
            for (Object part : parts) {
                String value = part instanceof Integer ? m.group((Integer)part) : (String)part;
                if (value != null) out.append(value);
            }
            copied = m.end(); replacements++;
        }
        return out.append(text, copied, text.length()).toString();
    }
}
