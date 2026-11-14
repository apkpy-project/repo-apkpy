"""The Java that travels with the app: JSON, values, errors, crypto."""
from ..features import json_module as json_feature
from ..features import classes as classes_feature

from .expressions import _HTTPS_MAX_TIMEOUT_MS


# json.loads / json.dumps (features/json_module.py), written into an app
# only when it calls them. CPython's json, read and written the same way:
# the parser follows Modules/_json.c, error messages included.
_JSON_MODULE_JAVA = r'''
    /** json.loads(text): o que o json do CPython le, com as mesmas mensagens
     *  (JSONDecodeError e' um ValueError). Um objeto ou uma lista volta como o
     *  JSON da app; o resto como o valor que e'. 91 e 93 sao os parenteses
     *  retos, 123 e 125 as chavetas: escritos por numero para nao ficarem
     *  soltos em texto. */
    private String _apkpyJsonLoads(String text) {
        String s = text == null ? "" : text;
        if (s.length() > 0 && s.charAt(0) == (char) 0xFEFF) {
            throw _apkpyJsonError(s, "Unexpected UTF-8 BOM (decode using utf-8-sig)", 0);
        }
        int[] at = new int[1];
        Object value = _apkpyJsonValue(s, at, _apkpyJsonSkip(s, 0));
        int end = _apkpyJsonSkip(s, at[0]);
        if (end != s.length()) throw _apkpyJsonError(s, "Extra data", end);
        if (value instanceof org.json.JSONObject || value instanceof org.json.JSONArray) {
            return value.toString();
        }
        if (value instanceof Double) {
            double d = (Double) value;
            if (d == 0d && 1d / d > 0d) return ApkpyValues.ZERO_FLOAT;
            return _apkpyFloat(d);
        }
        return _apkpyFromJson(value);
    }

    /** O JSONDecodeError do Python: a mensagem, a linha, a coluna e a posicao,
     *  contadas em letras como o Python as conta (um emoji e' uma). */
    private RuntimeException _apkpyJsonError(String doc, String msg, int pos) {
        int line = 1, lastNewline = -1;
        for (int i = 0; i < pos && i < doc.length(); i++) {
            if (doc.charAt(i) == '\n') {
                line++;
                lastNewline = i;
            }
        }
        int chars = doc.codePointCount(0, Math.min(pos, doc.length())) + Math.max(0, pos - doc.length());
        int column = lastNewline < 0 ? chars + 1 : doc.codePointCount(lastNewline, Math.min(pos, doc.length()));
        return new ApkpyValues.Raised("JSONDecodeError",
                msg + ": line " + line + " column " + column + " (char " + chars + ")");
    }

    private int _apkpyJsonSkip(String s, int i) {
        while (i < s.length()) {
            char c = s.charAt(i);
            if (c != ' ' && c != '\t' && c != '\n' && c != '\r') break;
            i++;
        }
        return i;
    }

    /** Um valor a partir de idx; at[0] fica logo a seguir a ele. */
    private Object _apkpyJsonValue(String s, int[] at, int idx) {
        if (idx >= s.length()) throw _apkpyJsonError(s, "Expecting value", idx);
        char c = s.charAt(idx);
        if (c == '"') return _apkpyJsonString(s, at, idx + 1);
        if (c == (char) 123) return _apkpyJsonObject(s, at, idx + 1);
        if (c == (char) 91) return _apkpyJsonArray(s, at, idx + 1);
        if (s.startsWith("null", idx)) { at[0] = idx + 4; return org.json.JSONObject.NULL; }
        if (s.startsWith("true", idx)) { at[0] = idx + 4; return Boolean.TRUE; }
        if (s.startsWith("false", idx)) { at[0] = idx + 5; return Boolean.FALSE; }
        if (s.startsWith("NaN", idx)) { at[0] = idx + 3; return Double.valueOf(Double.NaN); }
        if (s.startsWith("Infinity", idx)) { at[0] = idx + 8; return Double.valueOf(Double.POSITIVE_INFINITY); }
        if (s.startsWith("-Infinity", idx)) { at[0] = idx + 9; return Double.valueOf(Double.NEGATIVE_INFINITY); }
        return _apkpyJsonNumber(s, at, idx);
    }

    private boolean _apkpyJsonDigit(String s, int i) {
        return i < s.length() && s.charAt(i) >= '0' && s.charAt(i) <= '9';
    }

    /** Um numero como o do CPython: 1 e' int, 1.0 e 1e2 sao float, e o que
     *  sobra ("1." ou "01") fica para o "Extra data". */
    private Object _apkpyJsonNumber(String s, int[] at, int start) {
        int n = s.length(), idx = start;
        if (s.charAt(idx) == '-') {
            idx++;
            if (idx >= n) throw _apkpyJsonError(s, "Expecting value", start);
        }
        char c = s.charAt(idx);
        if (c >= '1' && c <= '9') {
            idx++;
            while (_apkpyJsonDigit(s, idx)) idx++;
        } else if (c == '0') {
            idx++;
        } else {
            throw _apkpyJsonError(s, "Expecting value", start);
        }
        boolean isFloat = false;
        if (idx < n - 1 && s.charAt(idx) == '.' && _apkpyJsonDigit(s, idx + 1)) {
            isFloat = true;
            idx += 2;
            while (_apkpyJsonDigit(s, idx)) idx++;
        }
        if (idx < n - 1 && (s.charAt(idx) == 'e' || s.charAt(idx) == 'E')) {
            int eStart = idx;
            idx++;
            if (idx < n - 1 && (s.charAt(idx) == '-' || s.charAt(idx) == '+')) idx++;
            while (_apkpyJsonDigit(s, idx)) idx++;
            if (_apkpyJsonDigit(s, idx - 1)) isFloat = true;
            else idx = eStart;
        }
        String number = s.substring(start, idx);
        at[0] = idx;
        if (isFloat) return Double.valueOf(Double.parseDouble(number));
        try {
            return Long.valueOf(Long.parseLong(number));
        } catch (NumberFormatException e) {
            return new java.math.BigInteger(number);
        }
    }

    private int _apkpyJsonHex(String s, int from, int to) {
        int code = 0;
        for (int i = from; i < to; i++) {
            int digit = Character.digit(s.charAt(i), 16);
            char c = s.charAt(i);
            boolean ascii = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
            if (digit < 0 || !ascii) return -1;
            code = code * 16 + digit;
        }
        return code;
    }

    /** O texto entre aspas que comeca em end (logo a seguir a abrir). */
    private String _apkpyJsonString(String s, int[] at, int end) {
        int n = s.length(), begin = end - 1;
        StringBuilder out = new StringBuilder();
        while (true) {
            int next = end;
            char c = 0;
            for (; next < n; next++) {
                c = s.charAt(next);
                if (c == '"' || c == '\\') break;
                if (c <= 0x1f) throw _apkpyJsonError(s, "Invalid control character at", next);
            }
            if (next >= n) throw _apkpyJsonError(s, "Unterminated string starting at", begin);
            out.append(s, end, next);
            next++;
            if (c == '"') {
                at[0] = next;
                return out.toString();
            }
            if (next == n) throw _apkpyJsonError(s, "Unterminated string starting at", begin);
            c = s.charAt(next);
            if (c != 'u') {
                end = next + 1;
                switch (c) {
                    case '"': case '\\': case '/': break;
                    case 'b': c = '\b'; break;
                    case 'f': c = '\f'; break;
                    case 'n': c = '\n'; break;
                    case 'r': c = '\r'; break;
                    case 't': c = '\t'; break;
                    default: throw _apkpyJsonError(s, "Invalid \\escape", end - 2);
                }
                out.append(c);
                continue;
            }
            next++;
            end = next + 4;
            if (end >= n) throw _apkpyJsonError(s, "Invalid \\uXXXX escape", next - 1);
            int code = _apkpyJsonHex(s, next, end);
            if (code < 0) throw _apkpyJsonError(s, "Invalid \\uXXXX escape", end - 5);
            if (code >= 0xD800 && code <= 0xDBFF && end + 6 < n
                    && s.charAt(end) == '\\' && s.charAt(end + 1) == 'u') {
                int low = _apkpyJsonHex(s, end + 2, end + 6);
                if (low < 0) throw _apkpyJsonError(s, "Invalid \\uXXXX escape", end + 1);
                if (low >= 0xDC00 && low <= 0xDFFF) {
                    out.append((char) code).append((char) low);
                    end += 6;
                    continue;
                }
            }
            out.append((char) code);
        }
    }

    /** NaN e Infinity cabem num float do Python mas nao no JSON do Android:
     *  dentro de uma lista ou de um dict ficam como o texto do Python. */
    private Object _apkpyJsonSafe(Object v) {
        if (v instanceof Double) {
            double d = (Double) v;
            if (Double.isNaN(d) || Double.isInfinite(d)) return _apkpyFloat(d);
        }
        return v;
    }

    private org.json.JSONObject _apkpyJsonObject(String s, int[] at, int idx) {
        org.json.JSONObject obj = new org.json.JSONObject();
        int n = s.length();
        idx = _apkpyJsonSkip(s, idx);
        if (idx >= n || s.charAt(idx) != (char) 125) {
            while (true) {
                if (idx >= n || s.charAt(idx) != '"') {
                    throw _apkpyJsonError(s, "Expecting property name enclosed in double quotes", idx);
                }
                String key = _apkpyJsonString(s, at, idx + 1);
                idx = _apkpyJsonSkip(s, at[0]);
                if (idx >= n || s.charAt(idx) != ':') throw _apkpyJsonError(s, "Expecting ':' delimiter", idx);
                idx = _apkpyJsonSkip(s, idx + 1);
                Object value = _apkpyJsonValue(s, at, idx);
                try {
                    obj.put(key, _apkpyJsonSafe(value));
                } catch (org.json.JSONException e) {
                    throw new IllegalArgumentException(e.getMessage());
                }
                idx = _apkpyJsonSkip(s, at[0]);
                if (idx < n && s.charAt(idx) == (char) 125) break;
                if (idx >= n || s.charAt(idx) != ',') throw _apkpyJsonError(s, "Expecting ',' delimiter", idx);
                int comma = idx;
                idx = _apkpyJsonSkip(s, idx + 1);
                if (idx < n && s.charAt(idx) == (char) 125) {
                    throw _apkpyJsonError(s, "Illegal trailing comma before end of object", comma);
                }
            }
        }
        at[0] = idx + 1;
        return obj;
    }

    private org.json.JSONArray _apkpyJsonArray(String s, int[] at, int idx) {
        org.json.JSONArray arr = new org.json.JSONArray();
        int n = s.length();
        idx = _apkpyJsonSkip(s, idx);
        if (idx >= n || s.charAt(idx) != (char) 93) {
            while (true) {
                arr.put(_apkpyJsonSafe(_apkpyJsonValue(s, at, idx)));
                idx = _apkpyJsonSkip(s, at[0]);
                if (idx < n && s.charAt(idx) == (char) 93) break;
                if (idx >= n || s.charAt(idx) != ',') throw _apkpyJsonError(s, "Expecting ',' delimiter", idx);
                int comma = idx;
                idx = _apkpyJsonSkip(s, idx + 1);
                if (idx < n && s.charAt(idx) == (char) 93) {
                    throw _apkpyJsonError(s, "Illegal trailing comma before end of array", comma);
                }
            }
        }
        at[0] = idx + 1;
        return arr;
    }

    /** json.dumps(v, ...): o texto que o CPython escreve. mode 1: o valor e' o
     *  que o codigo diz; mode 0: o codigo nao diz, e decide-se pelo valor --
     *  True/False/None da app, o JSON de uma lista ou de um dict, ou texto. */
    private String _apkpyJsonDumps(Object value, int mode, Object indent, boolean sortKeys,
                                   boolean ascii, String itemSep, String keySep, boolean allowNan) {
        String pad = null;
        if (indent instanceof Number) {
            StringBuilder spaces = new StringBuilder();
            for (int i = 0; i < ((Number) indent).intValue(); i++) spaces.append(' ');
            pad = spaces.toString();
        } else if (indent instanceof String) {
            pad = (String) indent;
        }
        if (itemSep == null) itemSep = pad == null ? ", " : ",";
        if (keySep == null) keySep = ": ";
        StringBuilder out = new StringBuilder();
        _apkpyJsonWrite(out, mode == 0 ? _apkpyJsonGuess(value) : value, pad, 0, sortKeys, ascii,
                itemSep, keySep, allowNan);
        return out.toString();
    }

    private Object _apkpyJsonGuess(Object v) {
        if (!(v instanceof String)) return v;
        String t = (String) v;
        if (t == ApkpyValues.TRUE) return Boolean.TRUE;
        if (t == ApkpyValues.FALSE) return Boolean.FALSE;
        if (t == ApkpyValues.NONE) return org.json.JSONObject.NULL;
        if (t == ApkpyValues.ZERO) return Long.valueOf(0);
        if (t == ApkpyValues.ZERO_FLOAT) return Double.valueOf(0);
        String peek = t.trim();
        int shape = _apkpyJsonShape(peek);
        try {
            if (shape == 91) return new org.json.JSONArray(peek);
            if (shape == 123) return new org.json.JSONObject(peek);
        } catch (Exception ignored) { }
        return t;
    }

    private String _apkpyJsonRepeat(String pad, int times) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < times; i++) out.append(pad);
        return out.toString();
    }

    private void _apkpyJsonWrite(StringBuilder out, Object v, String pad, int level, boolean sortKeys,
                                 boolean ascii, String itemSep, String keySep, boolean allowNan) {
        if (v == null || v == org.json.JSONObject.NULL) {
            out.append("null");
        } else if (v instanceof Boolean) {
            out.append(((Boolean) v) ? "true" : "false");
        } else if (v instanceof Long || v instanceof Integer || v instanceof Short
                || v instanceof Byte || v instanceof java.math.BigInteger) {
            out.append(v.toString());
        } else if (v instanceof Number) {
            double d = ((Number) v).doubleValue();
            if (Double.isNaN(d) || Double.isInfinite(d)) {
                if (!allowNan) {
                    throw new ApkpyValues.Raised("ValueError",
                            "Out of range float values are not JSON compliant: " + _apkpyFloat(d));
                }
                out.append(Double.isNaN(d) ? "NaN" : d > 0 ? "Infinity" : "-Infinity");
            } else {
                out.append(_apkpyFloat(d));
            }
        } else if (v instanceof org.json.JSONArray) {
            org.json.JSONArray arr = (org.json.JSONArray) v;
            out.append((char) 91);
            if (arr.length() > 0) {
                String inner = pad == null ? "" : "\n" + _apkpyJsonRepeat(pad, level + 1);
                for (int i = 0; i < arr.length(); i++) {
                    if (i > 0) out.append(itemSep);
                    out.append(inner);
                    _apkpyJsonWrite(out, arr.opt(i), pad, level + 1, sortKeys, ascii, itemSep, keySep, allowNan);
                }
                if (pad != null) out.append('\n').append(_apkpyJsonRepeat(pad, level));
            }
            out.append((char) 93);
        } else if (v instanceof org.json.JSONObject) {
            org.json.JSONObject obj = (org.json.JSONObject) v;
            java.util.List<String> keys = new java.util.ArrayList<String>();
            java.util.Iterator<String> names = obj.keys();
            while (names.hasNext()) keys.add(names.next());
            if (sortKeys) {
                java.util.Collections.sort(keys, new java.util.Comparator<String>() {
                    @Override public int compare(String a, String b) {
                        return _apkpyTextCmp(a, b);
                    }
                });
            }
            out.append((char) 123);
            if (!keys.isEmpty()) {
                String inner = pad == null ? "" : "\n" + _apkpyJsonRepeat(pad, level + 1);
                for (int i = 0; i < keys.size(); i++) {
                    if (i > 0) out.append(itemSep);
                    out.append(inner);
                    _apkpyJsonQuote(out, keys.get(i), ascii);
                    out.append(keySep);
                    _apkpyJsonWrite(out, obj.opt(keys.get(i)), pad, level + 1, sortKeys, ascii, itemSep, keySep, allowNan);
                }
                if (pad != null) out.append('\n').append(_apkpyJsonRepeat(pad, level));
            }
            out.append((char) 125);
        } else {
            String t = String.valueOf(v);
            if (ApkpyValues.isObjectText(t)) {
                throw new ApkpyValues.Raised("TypeError", "Object of type "
                        + t.substring(10, t.indexOf(" object at 0x")) + " is not JSON serializable");
            }
            _apkpyJsonQuote(out, t, ascii);
        }
    }

    /** Um texto entre aspas como o do CPython: com ensure_ascii, o que nao e'
     *  ASCII sai em escapes de quatro digitos (um emoji em dois). */
    private void _apkpyJsonQuote(StringBuilder out, String t, boolean ascii) {
        out.append('"');
        for (int i = 0; i < t.length(); i++) {
            char c = t.charAt(i);
            switch (c) {
                case '"': out.append('\\').append('"'); break;
                case '\\': out.append('\\').append('\\'); break;
                case '\n': out.append('\\').append('n'); break;
                case '\r': out.append('\\').append('r'); break;
                case '\t': out.append('\\').append('t'); break;
                case '\b': out.append('\\').append('b'); break;
                case '\f': out.append('\\').append('f'); break;
                default:
                    if (c < 0x20 || (ascii && c > 0x7e)) {
                        String hex = Integer.toHexString(c);
                        out.append('\\').append('u');
                        for (int k = hex.length(); k < 4; k++) out.append('0');
                        out.append(hex);
                    } else {
                        out.append(c);
                    }
            }
        }
        out.append('"');
    }
'''


def _emit_json_build_helpers(lines, ctx=""):
    """Helpers de JSON e de corpo HTTP, injetados sempre (como o _jsonGet)."""
    lines.append("")
    if json_feature.STATE.get('used'):
        # json.loads / json.dumps: only into an app that calls them.
        lines.extend(_JSON_MODULE_JAVA.split("\n"))
        lines.append("")
    lines.append("    /** {\"k\": v, ...} — os tipos do literal chegam intactos ao fio. */")
    lines.append("    private org.json.JSONObject _apkpyJsonObj(Object... kv) {")
    lines.append("        org.json.JSONObject obj = new org.json.JSONObject();")
    lines.append("        for (int i = 0; i + 1 < kv.length; i += 2) {")
    lines.append("            try { obj.put(String.valueOf(kv[i]), kv[i + 1]); }")
    lines.append("            catch (Exception ignored) {}")
    lines.append("        }")
    lines.append("        return obj;")
    lines.append("    }")
    lines.append("")
    lines.append("    private org.json.JSONArray _apkpyJsonArr(Object... items) {")
    lines.append("        org.json.JSONArray arr = new org.json.JSONArray();")
    lines.append("        for (Object item : items) arr.put(item);")
    lines.append("        return arr;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** A versao INSTALADA, nao a que o codigo esperava. */")
    lines.append("    private String _apkpyVersionCode() {")
    lines.append("        try {")
    lines.append(f"            android.content.pm.PackageInfo info = {ctx}getPackageManager()")
    lines.append(f"                    .getPackageInfo({ctx}getPackageName(), 0);")
    lines.append("            if (android.os.Build.VERSION.SDK_INT >= 28) {")
    lines.append("                return String.valueOf(info.getLongVersionCode());")
    lines.append("            }")
    lines.append("            return String.valueOf(info.versionCode);")
    lines.append("        } catch (Exception e) {")
    lines.append("            return \"0\";")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyVersionName() {")
    lines.append("        try {")
    lines.append(f"            String name = {ctx}getPackageManager()")
    lines.append(f"                    .getPackageInfo({ctx}getPackageName(), 0).versionName;")
    lines.append("            return name == null ? \"\" : name;")
    lines.append("        } catch (Exception e) {")
    lines.append("            return \"\";")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    # A Worker has an application Context, not Activity navigation methods.
    if not ctx:
        lines.append("    /** A ficha na loja, ou um endereco proprio.")
        lines.append("     *  Tenta a app da Play e recua para a pagina web: uma")
        lines.append("     *  distribuicao gerida chega a aparelhos sem a Play, que sao")
        lines.append("     *  exactamente os que precisam do recuo. */")
        lines.append("    private void _apkpyOpenStore(String url) {")
        lines.append("        String target = (url == null || String.valueOf(url).isEmpty())")
        lines.append("                ? (\"market://details?id=\" + getPackageName())")
        lines.append("                : String.valueOf(url);")
        lines.append("        try {")
        lines.append("            startActivity(new android.content.Intent(")
        lines.append("                    android.content.Intent.ACTION_VIEW,")
        lines.append("                    android.net.Uri.parse(target)));")
        lines.append("        } catch (Exception e) {")
        lines.append("            try {")
        lines.append("                startActivity(new android.content.Intent(")
        lines.append("                        android.content.Intent.ACTION_VIEW,")
        lines.append("                        android.net.Uri.parse(")
        lines.append("                                \"https://play.google.com/store/apps/details?id=\"")
        lines.append("                                + getPackageName())));")
        lines.append("            } catch (Exception ignored) { }")
        lines.append("        }")
        lines.append("    }")
        lines.append("")
    lines.append("    /** texto[a:b], com a tolerancia do Python.")
    lines.append("     *")
    lines.append("     *  O substring do Java REBENTA fora dos limites; o Python")
    lines.append("     *  apara: \"abc\"[0:99] da' \"abc\". Indices negativos contam")
    lines.append("     *  do fim, como la'. Uma fatia que rebentasse a app onde o")
    lines.append("     *  Previewer devolve texto seria a divergencia mais crua de")
    lines.append("     *  todas: uma funciona, a outra fecha. */")
    lines.append("    private String _apkpySlice(String text, String from, String to) {")
    lines.append("        String value = text == null ? \"\" : text;")
    lines.append("        // Contado como o Python conta: um emoji e' uma letra, e o")
    lines.append("        // substring em unidades UTF-16 partia-o ao meio.")
    lines.append("        int size = value.codePointCount(0, value.length());")
    lines.append("        int start = _apkpySliceEdge(from, 0, size);")
    lines.append("        int end = _apkpySliceEdge(to, size, size);")
    lines.append("        if (start >= end) return \"\";")
    lines.append("        return value.substring(value.offsetByCodePoints(0, start),")
    lines.append("                value.offsetByCodePoints(0, end));")
    lines.append("    }")
    lines.append("")
    lines.append("    private int _apkpySliceEdge(String raw, int fallback, int size) {")
    lines.append("        String t = raw == null ? \"\" : raw.trim();")
    lines.append("        if (t.isEmpty()) return fallback;")
    lines.append("        int at;")
    lines.append("        try { at = (int) Math.rint(Double.parseDouble(t)); }")
    lines.append("        catch (Exception e) { return fallback; }")
    lines.append("        if (at < 0) at += size;")
    lines.append("        if (at < 0) return 0;")
    lines.append("        if (at > size) return size;")
    lines.append("        return at;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** \", \".join(lista) -- a lista e texto JSON aqui. */")
    lines.append("    private String _apkpyJoin(String sep, String jsonArr) {")
    lines.append("        StringBuilder out = new StringBuilder();")
    lines.append("        try {")
    lines.append("            org.json.JSONArray arr = new org.json.JSONArray(String.valueOf(jsonArr));")
    lines.append("            for (int i = 0; i < arr.length(); i++) {")
    lines.append("                if (i > 0) out.append(sep == null ? \"\" : sep);")
    lines.append("                out.append(String.valueOf(arr.get(i)));")
    lines.append("            }")
    lines.append("        } catch (Exception e) {")
    lines.append("            return String.valueOf(jsonArr);")
    lines.append("        }")
    lines.append("        return out.toString();")
    lines.append("    }")
    lines.append("")
    lines.append("    /** texto.count(x) -- ocorrencias sem sobreposicao, como o Python. */")
    lines.append("    private String _apkpyCount(String text, String needle) {")
    lines.append("        String value = text == null ? \"\" : text;")
    lines.append("        String find = needle == null ? \"\" : needle;")
    lines.append("        if (find.isEmpty()) return String.valueOf(value.length() + 1);")
    lines.append("        int total = 0;")
    lines.append("        int at = value.indexOf(find);")
    lines.append("        while (at >= 0) {")
    lines.append("            total++;")
    lines.append("            at = value.indexOf(find, at + find.length());")
    lines.append("        }")
    lines.append("        return String.valueOf(total);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** texto.title() -- primeira letra de cada palavra. */")
    lines.append("    private String _apkpyTitle(String text) {")
    lines.append("        String value = text == null ? \"\" : text;")
    lines.append("        StringBuilder out = new StringBuilder(value.length());")
    lines.append("        boolean fresh = true;")
    lines.append("        for (int i = 0; i < value.length(); i++) {")
    lines.append("            char c = value.charAt(i);")
    lines.append("            if (Character.isLetter(c)) {")
    lines.append("                out.append(fresh ? Character.toUpperCase(c) : Character.toLowerCase(c));")
    lines.append("                fresh = false;")
    lines.append("            } else {")
    lines.append("                out.append(c);")
    lines.append("                fresh = true;")
    lines.append("            }")
    lines.append("        }")
    lines.append("        return out.toString();")
    lines.append("    }")
    lines.append("")
    lines.append("    /** str() de um decimal, com as regras do Python.")
    lines.append("     *")
    lines.append("     *  O Double.toString do Java passa a notacao cientifica a partir")
    lines.append("     *  de 1e7; o Python so' a partir de 1e16. Por isso math.pow(10,8)")
    lines.append("     *  escrevia \"1.0E8\" no telemovel e \"100000000.0\" no Previewer.")
    lines.append("     *  Os digitos sao os mesmos nos dois (ambos usam a representacao")
    lines.append("     *  mais curta que volta ao mesmo double) -- o que muda e' so' a")
    lines.append("     *  apresentacao, e e' isso que isto arruma. */")
    lines.append("    private String _apkpyFloat(double value) {")
    lines.append("        if (Double.isNaN(value)) return \"nan\";")
    lines.append("        if (Double.isInfinite(value)) return value > 0d ? \"inf\" : \"-inf\";")
    lines.append("        if (value == 0d) return (1d / value < 0d) ? \"-0.0\" : \"0.0\";")
    lines.append("        java.math.BigDecimal dec =")
    lines.append("                new java.math.BigDecimal(Double.toString(value));")
    lines.append("        double size = Math.abs(value);")
    lines.append("        if (size >= 1e16 || size < 1e-4) {")
    lines.append("            java.math.BigDecimal abs = dec.abs();")
    lines.append("            String digits = abs.unscaledValue().toString();")
    lines.append("            int exp = digits.length() - 1 - abs.scale();")
    lines.append("            digits = digits.replaceAll(\"0+$\", \"\");")
    lines.append("            if (digits.isEmpty()) digits = \"0\";")
    lines.append("            StringBuilder out = new StringBuilder();")
    lines.append("            if (value < 0d) out.append('-');")
    lines.append("            out.append(digits.charAt(0));")
    lines.append("            if (digits.length() > 1) out.append('.').append(digits.substring(1));")
    lines.append("            out.append('e').append(exp < 0 ? '-' : '+');")
    lines.append("            String power = String.valueOf(Math.abs(exp));")
    lines.append("            if (power.length() < 2) out.append('0');")
    lines.append("            out.append(power);")
    lines.append("            return out.toString();")
    lines.append("        }")
    lines.append("        String plain = dec.stripTrailingZeros().toPlainString();")
    lines.append("        return plain.indexOf('.') < 0 ? plain + \".0\" : plain;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** O Python LEVANTA onde o Java devolve NaN: math.sqrt(-1) e'")
    lines.append("     *  um ValueError no Previewer e era a palavra \"NaN\" a chegar ao")
    lines.append("     *  ecra do telemovel. Assim os dois lados falham juntos, e o")
    lines.append("     *  try/except apanha-o nos dois. */")
    lines.append("    private double _apkpyMathCheck(double result) {")
    lines.append("        if (Double.isNaN(result) || Double.isInfinite(result)) {")
    lines.append("            throw new ApkpyValues.Raised(\"ValueError\", \"math domain error\");")
    lines.append("        }")
    lines.append("        return result;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a / b. O Python para com ZeroDivisionError; o / do Java entre")
    lines.append("     *  doubles dava Infinity ou NaN e seguia em frente. */")
    lines.append("    private double _apkpyDiv(double a, double b) {")
    lines.append("        if (b == 0d) throw new ApkpyValues.Raised(\"ZeroDivisionError\", \"division by zero\");")
    lines.append("        return a / b;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a % b entre decimais, com o sinal do divisor, como o float_rem")
    lines.append("     *  do CPython: -7.5 % 2 da' 0.5 la' e dava -1.5 aqui. */")
    lines.append("    private double _apkpyModF(double a, double b) {")
    lines.append("        if (b == 0d) throw new ApkpyValues.Raised(\"ZeroDivisionError\", \"float modulo by zero\");")
    lines.append("        double mod = a % b;")
    lines.append("        if (mod != 0d) {")
    lines.append("            if ((b < 0d) != (mod < 0d)) mod += b;")
    lines.append("        } else {")
    lines.append("            mod = Math.copySign(0d, b);")
    lines.append("        }")
    lines.append("        return mod;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a // b entre decimais: o float_divmod do CPython, passo a passo,")
    lines.append("     *  incluindo o acerto final ao inteiro mais proximo. */")
    lines.append("    private double _apkpyFloorDivF(double a, double b) {")
    lines.append("        if (b == 0d) throw new ApkpyValues.Raised(\"ZeroDivisionError\", \"float floor division by zero\");")
    lines.append("        double mod = a % b;")
    lines.append("        double div = (a - mod) / b;")
    lines.append("        if (mod != 0d && ((b < 0d) != (mod < 0d))) div -= 1d;")
    lines.append("        if (div == 0d) return Math.copySign(0d, a / b);")
    lines.append("        double floor = Math.floor(div);")
    lines.append("        if (div - floor > 0.5d) floor += 1d;")
    lines.append("        return floor;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a ** b com decimais. Onde o Python para, isto tambem para: 0.0")
    lines.append("     *  elevado a um negativo, e um resultado que deixa de caber. Um")
    lines.append("     *  negativo elevado a uma fracao e' um complexo em Python, que")
    lines.append("     *  aqui nao existe -- para em vez de mostrar NaN. */")
    lines.append("    private double _apkpyPowF(double a, double b) {")
    lines.append("        if (a == 0d && b < 0d) {")
    lines.append("            throw new ApkpyValues.Raised(\"ZeroDivisionError\", \"0.0 cannot be raised to a negative power\");")
    lines.append("        }")
    lines.append("        if (a < 0d && b != Math.rint(b) && !Double.isInfinite(b)) {")
    lines.append("            throw new ArithmeticException(\"a negative number to a fractional power has no real answer\");")
    lines.append("        }")
    lines.append("        double result = Math.pow(a, b);")
    lines.append("        if (Double.isInfinite(result) && !Double.isInfinite(a) && !Double.isInfinite(b)) {")
    lines.append("            throw new ApkpyValues.Raised(\"OverflowError\", \"Numerical result out of range\");")
    lines.append("        }")
    lines.append("        return result;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** int ** int, exato. O Python nunca transborda; isto para em vez")
    lines.append("     *  de dar a volta. Um expoente negativo da' um decimal em Python,")
    lines.append("     *  e o tipo da resposta nao pode depender do valor -- para. */")
    lines.append("    private long _apkpyPowL(long base, long exp) {")
    lines.append("        if (exp < 0L) {")
    lines.append("            throw new ArithmeticException(\"a negative exponent gives a decimal: write float(x) ** n\");")
    lines.append("        }")
    lines.append("        long result = 1L;")
    lines.append("        long square = base;")
    lines.append("        long left = exp;")
    lines.append("        while (left > 0L) {")
    lines.append("            if ((left & 1L) == 1L) result = Math.multiplyExact(result, square);")
    lines.append("            left >>= 1;")
    lines.append("            if (left > 0L) square = Math.multiplyExact(square, square);")
    lines.append("        }")
    lines.append("        return result;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a << b. Python's ints grow; Java's << drops the bits that")
    lines.append("     *  leave the long and uses only the low six bits of b (1 << 64")
    lines.append("     *  is 1). This stops instead, as the other ints here do. */")
    lines.append("    private long _apkpyShiftL(long a, long b) {")
    lines.append("        if (b < 0L) throw new ApkpyValues.Raised(\"ValueError\", \"negative shift count\");")
    lines.append("        if (a == 0L) return 0L;")
    lines.append("        if (b >= 63L) throw new ArithmeticException(\"long overflow\");")
    lines.append("        long r = a << b;")
    lines.append("        if ((r >> b) != a) throw new ArithmeticException(\"long overflow\");")
    lines.append("        return r;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** s.startswith(t) / s.endswith(t) with t a tuple in a name: any item. */")
    lines.append("    private boolean _apkpyAffixAny(String text, String items, boolean start) {")
    lines.append("        try {")
    lines.append("            org.json.JSONArray a = new org.json.JSONArray(items);")
    lines.append("            for (int i = 0; i < a.length(); i++) {")
    lines.append("                String s = String.valueOf(a.opt(i));")
    lines.append("                if (start ? text.startsWith(s) : text.endsWith(s)) return true;")
    lines.append("            }")
    lines.append("        } catch (Exception ignored) {}")
    lines.append("        return false;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a >> b, rounding towards minus infinity like Python, for any b. */")
    lines.append("    private long _apkpyShiftR(long a, long b) {")
    lines.append("        if (b < 0L) throw new ApkpyValues.Raised(\"ValueError\", \"negative shift count\");")
    lines.append("        if (b >= 64L) return a < 0L ? -1L : 0L;")
    lines.append("        return a >> b;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** for x in v, quando o codigo nao diz o que v e': uma lista JSON")
    lines.append("     *  percorre os itens e um objeto JSON as chaves, como uma lista e")
    lines.append("     *  um dict em Python; o resto e' texto, e texto percorre as letras.")
    lines.append("     *  \"\" nao percorre nada. */")
    lines.append("    private org.json.JSONArray _apkpyItems(String value) {")
    lines.append("        String text = value == null ? \"\" : value;")
    lines.append("        int shape = _apkpyJsonShape(text);")
    lines.append("        try {")
    lines.append("            if (shape == 91) return new org.json.JSONArray(text.trim());")
    lines.append("            if (shape == 123) return _apkpyKeys(new org.json.JSONObject(text.trim()).toString());")
    lines.append("        } catch (Exception ignored) {}")
    lines.append("        return _apkpyChars(text);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** As chaves de um dict, pela ordem em que foram escritas. */")
    lines.append("    private org.json.JSONArray _apkpyKeys(String json) {")
    lines.append("        org.json.JSONArray keys = new org.json.JSONArray();")
    lines.append("        try {")
    lines.append("            org.json.JSONObject obj = new org.json.JSONObject(json == null ? \"{}\" : json);")
    lines.append("            java.util.Iterator<String> names = obj.keys();")
    lines.append("            while (names.hasNext()) keys.put(names.next());")
    lines.append("        } catch (Exception ignored) {}")
    lines.append("        return keys;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** As letras de um texto, uma a uma como o Python as conta: um")
    lines.append("     *  emoji e' uma so', e nao as duas metades que o Java guarda. */")
    lines.append("    private org.json.JSONArray _apkpyChars(String text) {")
    lines.append("        org.json.JSONArray chars = new org.json.JSONArray();")
    lines.append("        String value = text == null ? \"\" : text;")
    lines.append("        int i = 0;")
    lines.append("        while (i < value.length()) {")
    lines.append("            int code = value.codePointAt(i);")
    lines.append("            chars.put(new String(Character.toChars(code)));")
    lines.append("            i += Character.charCount(code);")
    lines.append("        }")
    lines.append("        return chars;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** O passo de range(), que em Python nao pode ser zero. */")
    lines.append("    private int _apkpyRangeStep(String step) {")
    lines.append("        int value = Integer.parseInt(String.valueOf(step).trim());")
    lines.append("        if (value == 0) throw new ApkpyValues.Raised(\"ValueError\", \"range() arg 3 must not be zero\");")
    lines.append("        return value;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** int() de um valor que no Python e' um numero (sum(), a - b, um item")
    lines.append("     *  vezes outro): o texto lido como esse numero e cortado para o lado do")
    lines.append("     *  zero. int(\"6.75\") e' um ValueError; int(6.75) e' 6. */")
    lines.append("    private long _apkpyIntOfNumber(String text) {")
    lines.append("        String t = String.valueOf(text).trim();")
    lines.append("        if (_apkpyIsNumber(t) && !_apkpyIsWhole(t)) return _apkpyTrunc(Double.parseDouble(t));")
    lines.append("        return ApkpyValues.toInt(t, 10);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** int(decimal): corta para o lado do zero, como o Python. O cast")
    lines.append("     *  do Java fazia de NaN um 0 e de um numero enorme o maior long,")
    lines.append("     *  em silencio; o Python para nos dois. */")
    lines.append("    private long _apkpyTrunc(double value) {")
    lines.append("        if (Double.isNaN(value) || Double.isInfinite(value)) {")
    lines.append("            throw new ApkpyValues.Raised(\"ValueError\", \"cannot convert float NaN or infinity to integer\");")
    lines.append("        }")
    lines.append("        if (Math.abs(value) >= 9.223372036854775807E18) {")
    lines.append("            throw new ApkpyValues.Raised(\"OverflowError\", \"integer too large\");")
    lines.append("        }")
    lines.append("        return (long) value;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a + b com um numero de um lado e, do outro, um valor que o codigo")
    lines.append("     *  nao diz o que e'. Dois numeros somam como no Python; texto e numero")
    lines.append("     *  e' o TypeError do Python. Colar os dois dava \"01\" para 0 + 1. */")
    lines.append("    private String _apkpyAdd(String a, String b) {")
    lines.append("        String x = String.valueOf(a).trim(), y = String.valueOf(b).trim();")
    lines.append("        if (!_apkpyIsNumber(x) || !_apkpyIsNumber(y)) {")
    lines.append("            throw new ApkpyValues.Raised(\"TypeError\", \"unsupported operand type(s) for +: '\" + a + \"' and '\" + b + \"'\");")
    lines.append("        }")
    lines.append("        if (_apkpyIsWhole(x) && _apkpyIsWhole(y)) {")
    lines.append("            return String.valueOf(Math.addExact(Long.parseLong(x), Long.parseLong(y)));")
    lines.append("        }")
    lines.append("        return _apkpyFloat(Double.parseDouble(x) + Double.parseDouble(y));")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a[k] + b[k]: os itens como o JSON os guarda. 10 + 7 da 17 e \"10\" + \"7\"")
    lines.append("     *  da \"107\"; um numero com texto e' o TypeError do Python (ou a soma,")
    lines.append("     *  se o texto for um numero, como em _apkpyAdd). */")
    lines.append("    private String _apkpyAddRaw(Object a, Object b) {")
    lines.append("        if (a instanceof Number || b instanceof Number) {")
    lines.append("            return _apkpyAdd(String.valueOf(a), String.valueOf(b));")
    lines.append("        }")
    lines.append("        if (a instanceof org.json.JSONArray && b instanceof org.json.JSONArray) {")
    lines.append("            return _apkpyListConcat(a.toString(), b.toString());")
    lines.append("        }")
    lines.append("        return _apkpyFromJson(a) + _apkpyFromJson(b);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** O que _apkpyArith deu, para guardar numa lista ou num dict: o numero")
    lines.append("     *  que e', a lista repetida, ou o texto repetido. */")
    lines.append("    private Object _apkpyArithValue(String text) {")
    lines.append("        String t = text == null ? \"\" : text.trim();")
    lines.append("        if (_apkpyIsNumber(t)) return _apkpyNumberOf(t);")
    lines.append("        if (t.startsWith(\"[\")) {")
    lines.append("            try { return new org.json.JSONArray(t); } catch (Exception ignored) { }")
    lines.append("        }")
    lines.append("        return text;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** A set's key for an item: 1, 1.0 and True are one item, as in Python. */")
    lines.append('    private String _apkpySetKey(Object v) {')
    lines.append('        if (v instanceof String) v = _apkpyJsonOut((String) v);')
    lines.append('        if (v == null || v == org.json.JSONObject.NULL) return "N";')
    lines.append('        if (v instanceof Boolean) return ((Boolean) v) ? "n1" : "n0";')
    lines.append('        if (v instanceof Integer || v instanceof Long) return "n" + ((Number) v).longValue();')
    lines.append('        if (v instanceof Number) {')
    lines.append('            double d = ((Number) v).doubleValue();')
    lines.append('            if (d == Math.rint(d) && Math.abs(d) < 9.0e15) return "n" + (long) d;')
    lines.append('            return "n" + d;')
    lines.append('        }')
    lines.append('        if (v instanceof String) return "s" + v;')
    lines.append('        if (v instanceof org.json.JSONObject) throw new ApkpyValues.Raised("TypeError", "unhashable type: \'dict\'");')
    lines.append('        return "o" + v;')
    lines.append('    }')
    lines.append("")
    lines.append("    /** CPython's hash of an int: what places it in a set's table. */")
    lines.append('    private long _apkpyPyHash(long x) {')
    lines.append('        long p = (1L << 61) - 1;')
    lines.append('        long a = (x == Long.MIN_VALUE ? Long.MAX_VALUE : Math.abs(x)) % p;')
    lines.append('        long h = x < 0 ? -a : a;')
    lines.append('        return h == -1L ? -2L : h;')
    lines.append('    }')
    lines.append("")
    lines.append("    /** CPython's hash of a float (_Py_HashDouble): 2.0 is 2, 1.5 is 2**60 + 1. */")
    lines.append('    private long _apkpyPyHashDouble(double v) {')
    lines.append('        if (Double.isInfinite(v)) return v > 0 ? 314159L : -314159L;')
    lines.append('        if (v == 0.0) return 0L;')
    lines.append('        long p = (1L << 61) - 1;')
    lines.append('        int shift = 0;')
    lines.append('        if (Math.getExponent(v) < Double.MIN_EXPONENT) { v = Math.scalb(v, 64); shift = 64; }')
    lines.append('        int e = Math.getExponent(v) + 1;')
    lines.append('        double m = Math.scalb(v, -e);')
    lines.append('        e -= shift;')
    lines.append('        long sign = 1;')
    lines.append('        if (m < 0) { sign = -1; m = -m; }')
    lines.append('        long x = 0;')
    lines.append('        while (m != 0) {')
    lines.append('            x = ((x << 28) & p) | (x >>> 33);')
    lines.append('            m *= 268435456.0;')
    lines.append('            e -= 28;')
    lines.append('            long y = (long) m;')
    lines.append('            m -= y;')
    lines.append('            x += y;')
    lines.append('            if (x >= p) x -= p;')
    lines.append('        }')
    lines.append('        e = e >= 0 ? e % 61 : 61 - 1 - ((-1 - e) % 61);')
    lines.append('        x = ((x << e) & p) | (x >>> (61 - e));')
    lines.append('        x = x * sign;')
    lines.append('        return x == -1L ? -2L : x;')
    lines.append('    }')
    lines.append("")
    lines.append("    /** The empty slot CPython's set_insert_clean gives a hash. */")
    lines.append('    private int _apkpySetProbe(int[] table, int mask, long hash) {')
    lines.append('        long perturb = hash;')
    lines.append('        long i = hash & mask;')
    lines.append('        while (true) {')
    lines.append('            if (table[(int) i] < 0) return (int) i;')
    lines.append('            if (i + 9 <= mask) {')
    lines.append('                for (int j = 1; j <= 9; j++) if (table[(int) (i + j)] < 0) return (int) (i + j);')
    lines.append('            }')
    lines.append('            perturb >>>= 5;')
    lines.append('            i = (i * 5 + 1 + perturb) & mask;')
    lines.append('        }')
    lines.append('    }')
    lines.append("")
    lines.append("    /** A set's items, added in this order, in the order CPython walks them:")
    lines.append('     *  {3, 1, 2} is {1, 2, 3}, {100, 5} is {100, 5}. Only numbers and bools have')
    lines.append('     *  a hash that is the same on every run; text keeps the order it was')
    lines.append("     *  added in, as CPython's changes from one run to the next. */")
    lines.append('    private org.json.JSONArray _apkpySetOrder(org.json.JSONArray items) {')
    lines.append('        int n = items.length();')
    lines.append('        long[] hash = new long[n];')
    lines.append('        for (int k = 0; k < n; k++) {')
    lines.append('            Object v = items.opt(k);')
    lines.append('            if (v instanceof Boolean) hash[k] = ((Boolean) v) ? 1L : 0L;')
    lines.append('            else if (v instanceof Integer || v instanceof Long) hash[k] = _apkpyPyHash(((Number) v).longValue());')
    lines.append('            else if (v instanceof Double || v instanceof Float || v instanceof java.math.BigDecimal) {')
    lines.append('                double d = ((Number) v).doubleValue();')
    lines.append('                if (Double.isNaN(d)) return items;')
    lines.append('                hash[k] = _apkpyPyHashDouble(d);')
    lines.append('            }')
    lines.append('            else return items;')
    lines.append('        }')
    lines.append('        int mask = 7;')
    lines.append('        int[] table = new int[8];')
    lines.append('        java.util.Arrays.fill(table, -1);')
    lines.append('        int fill = 0;')
    lines.append('        for (int k = 0; k < n; k++) {')
    lines.append('            table[_apkpySetProbe(table, mask, hash[k])] = k;')
    lines.append('            fill++;')
    lines.append('            if ((long) fill * 5 >= (long) mask * 3) {')
    lines.append('                long minused = fill > 50000 ? (long) fill * 2 : (long) fill * 4;')
    lines.append('                int size = 8;')
    lines.append('                while (size <= minused) size <<= 1;')
    lines.append('                int[] fresh = new int[size];')
    lines.append('                java.util.Arrays.fill(fresh, -1);')
    lines.append('                for (int s = 0; s <= mask; s++) {')
    lines.append('                    if (table[s] >= 0) fresh[_apkpySetProbe(fresh, size - 1, hash[table[s]])] = table[s];')
    lines.append('                }')
    lines.append('                table = fresh;')
    lines.append('                mask = size - 1;')
    lines.append('            }')
    lines.append('        }')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        for (int s = 0; s <= mask; s++) if (table[s] >= 0) out.put(items.opt(table[s]));')
    lines.append('        return out;')
    lines.append('    }')
    lines.append("")
    lines.append('    private org.json.JSONArray _apkpySetItems(String json) {')
    lines.append('        try {')
    lines.append('            return new org.json.JSONArray(json == null || json.trim().isEmpty() ? "[]" : json.trim());')
    lines.append('        } catch (Exception e) {')
    lines.append('            return new org.json.JSONArray();')
    lines.append('        }')
    lines.append('    }')
    lines.append("")
    lines.append("    /** The items without repeats, in the order they came, then CPython's. */")
    lines.append('    private org.json.JSONArray _apkpySetUnique(org.json.JSONArray in) {')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        java.util.HashSet<String> keys = new java.util.HashSet<>();')
    lines.append('        for (int i = 0; i < in.length(); i++) {')
    lines.append('            Object v = in.opt(i);')
    lines.append('            if (keys.add(_apkpySetKey(v))) out.put(v);')
    lines.append('        }')
    lines.append('        return out;')
    lines.append('    }')
    lines.append("")
    lines.append('    private java.util.HashSet<String> _apkpySetKeys(org.json.JSONArray in) {')
    lines.append('        java.util.HashSet<String> keys = new java.util.HashSet<>();')
    lines.append('        for (int i = 0; i < in.length(); i++) keys.add(_apkpySetKey(in.opt(i)));')
    lines.append('        return keys;')
    lines.append('    }')
    lines.append("")
    lines.append('    /** set(items), {a, b}, {x for ...}. */')
    lines.append('    private String _apkpySetOf(String items) {')
    lines.append('        return _apkpySetOrder(_apkpySetUnique(_apkpySetItems(items))).toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** s.add(x): s with x, or s as it was. */')
    lines.append('    private String _apkpySetAdd(String set, Object item) {')
    lines.append('        org.json.JSONArray arr = _apkpySetItems(set);')
    lines.append('        if (_apkpySetKeys(arr).contains(_apkpySetKey(item))) return arr.toString();')
    lines.append('        arr.put(item instanceof String ? _apkpyJsonOut((String) item) : item);')
    lines.append('        return _apkpySetOrder(arr).toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** s.discard(x) and s.remove(x) (KeyError when x is not there). */')
    lines.append('    private String _apkpySetRemove(String set, Object item, boolean strict) {')
    lines.append('        org.json.JSONArray arr = _apkpySetItems(set);')
    lines.append('        String key = _apkpySetKey(item);')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        boolean found = false;')
    lines.append('        for (int i = 0; i < arr.length(); i++) {')
    lines.append('            if (!found && _apkpySetKey(arr.opt(i)).equals(key)) { found = true; continue; }')
    lines.append('            out.put(arr.opt(i));')
    lines.append('        }')
    lines.append('        if (!found && strict) {')
    lines.append('            org.json.JSONArray one = new org.json.JSONArray();')
    lines.append('            one.put(item instanceof String ? _apkpyJsonOut((String) item) : item);')
    lines.append('            String shown = _apkpyShow(one.toString());')
    lines.append('            throw new ApkpyValues.Raised("KeyError", shown.substring(1, shown.length() - 1));')
    lines.append('        }')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append("    /** a | b: a's items, then b's that a does not have. */")
    lines.append('    private String _apkpySetUnion(String a, String b) {')
    lines.append('        org.json.JSONArray out = _apkpySetItems(a);')
    lines.append('        java.util.HashSet<String> keys = _apkpySetKeys(out);')
    lines.append('        org.json.JSONArray more = _apkpySetItems(b);')
    lines.append('        for (int i = 0; i < more.length(); i++) {')
    lines.append('            if (keys.add(_apkpySetKey(more.opt(i)))) out.put(more.opt(i));')
    lines.append('        }')
    lines.append('        return _apkpySetOrder(out).toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** a & b: CPython walks the smaller set (b when b is not a set). */')
    lines.append('    private String _apkpySetInter(String a, String b, boolean bothSets) {')
    lines.append('        org.json.JSONArray x = _apkpySetItems(a), y = _apkpySetUnique(_apkpySetItems(b));')
    lines.append('        org.json.JSONArray walk = y, other = x;')
    lines.append('        if (bothSets && y.length() > x.length()) { walk = x; other = y; }')
    lines.append('        java.util.HashSet<String> keys = _apkpySetKeys(other);')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        for (int i = 0; i < walk.length(); i++) {')
    lines.append('            if (keys.contains(_apkpySetKey(walk.opt(i)))) out.put(walk.opt(i));')
    lines.append('        }')
    lines.append('        return _apkpySetOrder(out).toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** a - b. */')
    lines.append('    private String _apkpySetDiff(String a, String b) {')
    lines.append('        org.json.JSONArray x = _apkpySetItems(a);')
    lines.append('        java.util.HashSet<String> keys = _apkpySetKeys(_apkpySetItems(b));')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        for (int i = 0; i < x.length(); i++) {')
    lines.append('            if (!keys.contains(_apkpySetKey(x.opt(i)))) out.put(x.opt(i));')
    lines.append('        }')
    lines.append('        return _apkpySetOrder(out).toString();')
    lines.append('    }')
    lines.append("")
    lines.append("    /** Counter(items) and Counter(mapping): each item and how many times it is")
    lines.append("     *  there, in the order first seen. */")
    lines.append('    private String _apkpyCounterOf(String items, boolean mapping) {')
    lines.append('        return _apkpyCounterUpdate("{}", items, mapping, 1);')
    lines.append('    }')
    lines.append("")
    lines.append("    /** c.update(items) (sign 1) and c.subtract(items) (sign -1). */")
    lines.append('    private String _apkpyCounterUpdate(String counter, String items, boolean mapping, int sign) {')
    lines.append('        String start = counter == null || counter.trim().isEmpty() ? "{}" : counter.trim();')
    lines.append('        String text = items == null ? "" : items.trim();')
    lines.append('        try {')
    lines.append('            org.json.JSONObject out = new org.json.JSONObject(start);')
    lines.append('            if (mapping) {')
    lines.append('                org.json.JSONObject add = new org.json.JSONObject(text.isEmpty() ? "{}" : text);')
    lines.append('                java.util.Iterator<String> keys = add.keys();')
    lines.append('                while (keys.hasNext()) {')
    lines.append('                    String key = keys.next();')
    lines.append('                    out.put(key, _apkpyCounterPlus(out.opt(key), add.opt(key), sign));')
    lines.append('                }')
    lines.append('            } else {')
    lines.append('                org.json.JSONArray arr = new org.json.JSONArray(text.isEmpty() ? "[]" : text);')
    lines.append('                for (int i = 0; i < arr.length(); i++) {')
    lines.append('                    Object item = arr.opt(i);')
    lines.append('                    if (item instanceof org.json.JSONArray) throw new ApkpyValues.Raised("TypeError", "unhashable type: \'list\'");')
    lines.append('                    if (item instanceof org.json.JSONObject) throw new ApkpyValues.Raised("TypeError", "unhashable type: \'dict\'");')
    lines.append('                    String key = _apkpyFromJson(item);')
    lines.append('                    out.put(key, _apkpyCounterPlus(out.opt(key), Long.valueOf(1), sign));')
    lines.append('                }')
    lines.append('            }')
    lines.append('            return out.toString();')
    lines.append('        } catch (org.json.JSONException e) {')
    lines.append('            return start;')
    lines.append('        }')
    lines.append('    }')
    lines.append("")
    lines.append("    /** had + n (or had - n): whole numbers stay whole, as in Python. */")
    lines.append('    private Object _apkpyCounterPlus(Object had, Object n, int sign) {')
    lines.append('        if (n instanceof String) {')
    lines.append('            try { n = Long.valueOf(Long.parseLong((String) n)); }')
    lines.append('            catch (NumberFormatException e) { n = Double.valueOf(Double.parseDouble((String) n)); }')
    lines.append('        }')
    lines.append('        boolean whole = (had == null || had instanceof Integer || had instanceof Long)')
    lines.append('            && (n instanceof Integer || n instanceof Long);')
    lines.append('        if (whole) return Long.valueOf((had == null ? 0L : ((Number) had).longValue()) + sign * ((Number) n).longValue());')
    lines.append('        double a = had instanceof Number ? ((Number) had).doubleValue() : 0.0;')
    lines.append('        double b = n instanceof Number ? ((Number) n).doubleValue() : 0.0;')
    lines.append('        return Double.valueOf(a + sign * b);')
    lines.append('    }')
    lines.append("")
    lines.append("    /** c.most_common(n): [item, count] pairs, the most first; a tie keeps the")
    lines.append("     *  order first seen, as CPython's sort does (Long.MIN_VALUE: all of them). */")
    lines.append('    private String _apkpyCounterMostCommon(String counter, long n) {')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        try {')
    lines.append('            final org.json.JSONObject obj = new org.json.JSONObject(counter == null || counter.trim().isEmpty() ? "{}" : counter.trim());')
    lines.append('            java.util.ArrayList<String> keys = new java.util.ArrayList<>();')
    lines.append('            java.util.Iterator<String> it = obj.keys();')
    lines.append('            while (it.hasNext()) keys.add(it.next());')
    lines.append('            java.util.Collections.sort(keys, new java.util.Comparator<String>() {')
    lines.append('                @Override public int compare(String x, String y) {')
    lines.append('                    return Double.compare(obj.optDouble(y, 0), obj.optDouble(x, 0));')
    lines.append('                }')
    lines.append('            });')
    lines.append('            for (int i = 0; i < keys.size() && (n == Long.MIN_VALUE || i < n); i++) {')
    lines.append('                org.json.JSONArray pair = new org.json.JSONArray();')
    lines.append('                pair.put(keys.get(i));')
    lines.append('                pair.put(obj.opt(keys.get(i)));')
    lines.append('                out.put(pair);')
    lines.append('            }')
    lines.append('        } catch (org.json.JSONException e) {')
    lines.append('            return "[]";')
    lines.append('        }')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append("    /** str() of a Counter: Counter({'tea': 2, 'jam': 1}), the most first. */")
    lines.append('    private String _apkpyCounterShow(String counter) {')
    lines.append('        try {')
    lines.append('            org.json.JSONArray pairs = new org.json.JSONArray(_apkpyCounterMostCommon(counter, Long.MIN_VALUE));')
    lines.append('            if (pairs.length() == 0) return "Counter()";')
    lines.append('            StringBuilder out = new StringBuilder("Counter({");')
    lines.append('            for (int i = 0; i < pairs.length(); i++) {')
    lines.append('                org.json.JSONArray pair = pairs.getJSONArray(i);')
    lines.append('                if (i > 0) out.append(", ");')
    lines.append('                out.append(_apkpyShowItem(pair.opt(0))).append(": ").append(_apkpyShowItem(pair.opt(1)));')
    lines.append('            }')
    lines.append('            return out.append("})").toString();')
    lines.append('        } catch (org.json.JSONException e) {')
    lines.append('            return "Counter()";')
    lines.append('        }')
    lines.append('    }')
    lines.append("")
    lines.append("    /** str() of a defaultdict: defaultdict(<class 'int'>, {'a': 1}). */")
    lines.append('    private String _apkpyDefaultShow(String dict, String factory) {')
    lines.append('        String shown = _apkpyShow(dict == null || dict.trim().isEmpty() ? "{}" : dict);')
    lines.append('        return "defaultdict(" + factory + ", " + shown + ")";')
    lines.append('    }')
    lines.append("")
    lines.append("    /** s -= t: the items of t taken out of s where they are (no new table). */")
    lines.append('    private String _apkpySetWithout(String a, String b) {')
    lines.append('        org.json.JSONArray x = _apkpySetItems(a);')
    lines.append('        java.util.HashSet<String> keys = _apkpySetKeys(_apkpySetItems(b));')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        for (int i = 0; i < x.length(); i++) {')
    lines.append('            if (!keys.contains(_apkpySetKey(x.opt(i)))) out.put(x.opt(i));')
    lines.append('        }')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** a ^ b: CPython starts from b and adds or takes out each item of a. */')
    lines.append('    private String _apkpySetSymDiff(String a, String b) {')
    lines.append('        org.json.JSONArray x = _apkpySetItems(a), y = _apkpySetUnique(_apkpySetItems(b));')
    lines.append('        java.util.HashSet<String> inA = _apkpySetKeys(x), inB = _apkpySetKeys(y);')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        for (int i = 0; i < y.length(); i++) if (!inA.contains(_apkpySetKey(y.opt(i)))) out.put(y.opt(i));')
    lines.append('        for (int i = 0; i < x.length(); i++) if (!inB.contains(_apkpySetKey(x.opt(i)))) out.put(x.opt(i));')
    lines.append('        return _apkpySetOrder(out).toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** a <= b, a < b, a == b, a.isdisjoint(b) and the rest. */')
    lines.append('    private boolean _apkpySetCompare(String op, String a, String b) {')
    lines.append('        java.util.HashSet<String> x = _apkpySetKeys(_apkpySetItems(a)), y = _apkpySetKeys(_apkpySetItems(b));')
    lines.append('        switch (op) {')
    lines.append('            case "issubset": return y.containsAll(x);')
    lines.append('            case "issuperset": return x.containsAll(y);')
    lines.append('            case "lt": return y.containsAll(x) && x.size() < y.size();')
    lines.append('            case "gt": return x.containsAll(y) && x.size() > y.size();')
    lines.append('            case "eq": return x.equals(y);')
    lines.append('            case "ne": return !x.equals(y);')
    lines.append('            default:')
    lines.append('                for (String k : x) if (y.contains(k)) return false;')
    lines.append('                return true;')
    lines.append('        }')
    lines.append('    }')
    lines.append("")
    lines.append("    /** str() of a set: {1, 'a'}, and set() when it is empty. */")
    lines.append('    private String _apkpySetShow(String set) {')
    lines.append('        org.json.JSONArray arr = _apkpySetItems(set);')
    lines.append('        if (arr.length() == 0) return "set()";')
    lines.append('        String shown = _apkpyShow(arr.toString());')
    lines.append('        return "{" + shown.substring(1, shown.length() - 1) + "}";')
    lines.append('    }')
    lines.append("")
    lines.append("    /** x = s.pop(): the first item CPython's table gives. */")
    lines.append('    private String _apkpySetPopValue(String set) {')
    lines.append('        org.json.JSONArray arr = _apkpySetItems(set);')
    lines.append('        if (arr.length() == 0) throw new ApkpyValues.Raised("KeyError", "\'pop from an empty set\'");')
    lines.append('        return _apkpyFromJson(arr.opt(0));')
    lines.append('    }')
    lines.append("")
    lines.append('    /** s after s.pop(). */')
    lines.append('    private String _apkpySetRest(String set) {')
    lines.append('        org.json.JSONArray arr = _apkpySetItems(set);')
    lines.append('        if (arr.length() == 0) throw new ApkpyValues.Raised("KeyError", "\'pop from an empty set\'");')
    lines.append('        arr.remove(0);')
    lines.append('        return arr.toString();')
    lines.append('    }')
    lines.append("")
    lines.append("    /** a + b com um lado que _apkpyArith deu (um numero, ou um texto ou uma")
    lines.append("     *  lista repetidos com *): dois numeros somam, dois textos juntam-se, duas")
    lines.append("     *  listas tambem; um com o outro e' o TypeError do Python. aText: o codigo")
    lines.append("     *  diz que o lado e' um str, mesmo que escreva um numero. */")
    lines.append("    private String _apkpyAddAny(String a, boolean aText, String b, boolean bText) {")
    lines.append("        String x = String.valueOf(a).trim(), y = String.valueOf(b).trim();")
    lines.append("        boolean xNum = !aText && _apkpyIsNumber(x), yNum = !bText && _apkpyIsNumber(y);")
    lines.append("        if (xNum && yNum) return _apkpyAdd(x, y);")
    lines.append("        if (!xNum && !yNum) {")
    lines.append("            if (!aText && !bText && x.startsWith(\"[\") && y.startsWith(\"[\")) {")
    lines.append("                try { return _apkpyListConcat(x, y); } catch (Exception ignored) { }")
    lines.append("            }")
    lines.append("            return String.valueOf(a) + String.valueOf(b);")
    lines.append("        }")
    lines.append("        String number = _apkpyIsWhole(xNum ? x : y) ? \"int\" : \"float\";")
    lines.append("        if (xNum) {")
    lines.append("            throw new ApkpyValues.Raised(\"TypeError\", \"unsupported operand type(s) for +: '\" + number + \"' and 'str'\");")
    lines.append("        }")
    lines.append("        throw new ApkpyValues.Raised(\"TypeError\", \"can only concatenate str (not \\\"\" + number + \"\\\") to str\");")
    lines.append("    }")
    lines.append("")
    lines.append("    /** Um lado de _apkpyArith como o valor do Python que e': Long (um int,")
    lines.append("     *  e um bool, que no Python e' um int), Double, String (um str), uma")
    lines.append("     *  JSONArray (uma lista) ou o que nenhuma conta aceita (None, dict).")
    lines.append("     *  mode: 0 texto que o codigo nao diz o que e' (lido como o numero que")
    lines.append("     *  escreve, se escrever um), 1 um item como o JSON o tem, 2 um str,")
    lines.append("     *  3 uma lista. */")
    lines.append("    private Object _apkpyArithSide(Object v, int mode) {")
    lines.append("        if (mode == 2) return String.valueOf(v);")
    lines.append("        if (mode == 3) {")
    lines.append("            // O JSONException do Android e' verificado; o do jar do PC nao.")
    lines.append("            try { return new org.json.JSONArray(String.valueOf(v)); } catch (Exception e) { return String.valueOf(v); }")
    lines.append("        }")
    lines.append("        if (mode == 1) {")
    lines.append("            if (v instanceof Boolean) return ((Boolean) v) ? 1L : 0L;")
    lines.append("            if (v instanceof Integer || v instanceof Long) return ((Number) v).longValue();")
    lines.append("            if (v instanceof java.math.BigInteger) return ((java.math.BigInteger) v).longValueExact();")
    lines.append("            if (v instanceof Number) return ((Number) v).doubleValue();")
    lines.append("            return v;")
    lines.append("        }")
    lines.append("        if (v == ApkpyValues.TRUE) return 1L;")
    lines.append("        if (v == ApkpyValues.FALSE) return 0L;")
    lines.append("        if (v == null || v == ApkpyValues.NONE) return org.json.JSONObject.NULL;")
    lines.append("        String t = String.valueOf(v).trim();")
    lines.append("        if (_apkpyIsNumber(t)) return _apkpyIsWhole(t) ? (Object) Long.valueOf(Long.parseLong(t)) : (Object) Double.valueOf(Double.parseDouble(t));")
    lines.append("        if (t.startsWith(\"[\")) {")
    lines.append("            try { return new org.json.JSONArray(t); } catch (Exception ignored) { }")
    lines.append("        }")
    lines.append("        return String.valueOf(v);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** O nome do tipo de um lado, para o TypeError: o do Python. */")
    lines.append("    private String _apkpyArithName(Object raw, int mode, Object value) {")
    lines.append("        if (mode == 1) return _apkpyTypeName(raw);")
    lines.append("        if (mode == 0 && (raw == ApkpyValues.TRUE || raw == ApkpyValues.FALSE)) return \"bool\";")
    lines.append("        return _apkpyTypeName(value);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a - b, a * b, a / b, a // b, a % b, a ** b e -a (\"neg\") quando o")
    lines.append("     *  codigo nao diz o que um lado e': o item de uma lista de dicts")
    lines.append("     *  (item[\"price\"] * item[\"qty\"]), um parametro, a resposta de uma API.")
    lines.append("     *  A resposta e' a do CPython -- 2 * 2.5 da' 5.0, 7 // 2 da' 3, \"ab\" * 2")
    lines.append("     *  da' \"abab\" -- e onde ele para, o TypeError dele, com a mensagem. */")
    lines.append("    private String _apkpyArith(String op, Object a, int am, Object b, int bm) {")
    lines.append("        Object x = _apkpyArithSide(a, am), y = _apkpyArithSide(b, bm);")
    lines.append("        boolean xNum = x instanceof Long || x instanceof Double;")
    lines.append("        boolean yNum = y instanceof Long || y instanceof Double;")
    lines.append("        if (op.equals(\"neg\")) {")
    lines.append("            if (x instanceof Long) return String.valueOf(Math.negateExact((Long) x));")
    lines.append("            if (x instanceof Double) return _apkpyFloat(-((Double) x));")
    lines.append("            throw new ApkpyValues.Raised(\"TypeError\", \"bad operand type for unary -: '\" + _apkpyArithName(a, am, x) + \"'\");")
    lines.append("        }")
    lines.append("        if (op.equals(\"*\")) {")
    lines.append("            boolean xSeq = x instanceof String || x instanceof org.json.JSONArray;")
    lines.append("            boolean ySeq = y instanceof String || y instanceof org.json.JSONArray;")
    lines.append("            if (xSeq || ySeq) {")
    lines.append("                Object seq = xSeq ? x : y, times = xSeq ? y : x;")
    lines.append("                if (!(times instanceof Long)) {")
    lines.append("                    String name = xSeq ? _apkpyArithName(b, bm, y) : _apkpyArithName(a, am, x);")
    lines.append("                    throw new ApkpyValues.Raised(\"TypeError\", \"can't multiply sequence by non-int of type '\" + name + \"'\");")
    lines.append("                }")
    lines.append("                boolean list = seq instanceof org.json.JSONArray;")
    lines.append("                return _apkpyRepeat(list ? seq.toString() : (String) seq, (Long) times, list);")
    lines.append("            }")
    lines.append("        }")
    lines.append("        if (!xNum || !yNum) {")
    lines.append("            if (op.equals(\"%\") && x instanceof String) {")
    lines.append("                throw new ApkpyValues.Raised(\"TypeError\", \"formatting text with % is translated only when the text is written in the code; use an f-string\");")
    lines.append("            }")
    lines.append("            throw new ApkpyValues.Raised(\"TypeError\", \"unsupported operand type(s) for \"")
    lines.append("                    + (op.equals(\"**\") ? \"** or pow()\" : op) + \": '\" + _apkpyArithName(a, am, x)")
    lines.append("                    + \"' and '\" + _apkpyArithName(b, bm, y) + \"'\");")
    lines.append("        }")
    lines.append("        if (x instanceof Long && y instanceof Long) {")
    lines.append("            long p = (Long) x, q = (Long) y;")
    lines.append("            switch (op) {")
    lines.append("                case \"-\": return String.valueOf(Math.subtractExact(p, q));")
    lines.append("                case \"*\": return String.valueOf(Math.multiplyExact(p, q));")
    lines.append("                case \"/\": return _apkpyFloat(_apkpyDiv((double) p, (double) q));")
    lines.append("                case \"//\":")
    lines.append("                    if (q == 0L) throw new ApkpyValues.Raised(\"ZeroDivisionError\", \"integer division or modulo by zero\");")
    lines.append("                    return String.valueOf(Math.floorDiv(p, q));")
    lines.append("                case \"%\":")
    lines.append("                    if (q == 0L) throw new ApkpyValues.Raised(\"ZeroDivisionError\", \"integer modulo by zero\");")
    lines.append("                    return String.valueOf(Math.floorMod(p, q));")
    lines.append("                default:")
    lines.append("                    // 2 ** -1 e' 0.5 no Python: o expoente diz o tipo.")
    lines.append("                    if (q < 0L) return _apkpyFloat(_apkpyPowF((double) p, (double) q));")
    lines.append("                    return String.valueOf(_apkpyPowL(p, q));")
    lines.append("            }")
    lines.append("        }")
    lines.append("        double p = ((Number) x).doubleValue(), q = ((Number) y).doubleValue();")
    lines.append("        switch (op) {")
    lines.append("            case \"-\": return _apkpyFloat(p - q);")
    lines.append("            case \"*\": return _apkpyFloat(p * q);")
    lines.append("            case \"/\": return _apkpyFloat(_apkpyDiv(p, q));")
    lines.append("            case \"//\": return _apkpyFloat(_apkpyFloorDivF(p, q));")
    lines.append("            case \"%\": return _apkpyFloat(_apkpyModF(p, q));")
    lines.append("            default: return _apkpyFloat(_apkpyPowF(p, q));")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /** O item tal como o JSON o tem (Integer, String, ...); o texto de")
    lines.append("     *  sempre se o contentor nao for JSON ou o item nao existir. */")
    lines.append("    private Object _apkpyRawOr(String container, String key, String fallback) {")
    lines.append("        try {")
    lines.append("            String c = container == null ? \"\" : container.trim();")
    lines.append("            if (c.startsWith(\"[\")) {")
    lines.append("                org.json.JSONArray arr = new org.json.JSONArray(c);")
    lines.append("                int i = Integer.parseInt(key.trim());")
    lines.append("                return arr.get(i < 0 ? i + arr.length() : i);")
    lines.append("            }")
    lines.append("            return new org.json.JSONObject(c).get(key);   // lanca se nao for um dict")
    lines.append("        } catch (Exception ignored) { }")
    lines.append("        return fallback;")
    lines.append("    }")
    lines.append("")
    lines.append('    /** O nome do tipo como o Python o diz, para as mensagens de TypeError. */')
    lines.append('    private String _apkpyTypeName(Object v) {')
    lines.append('        if (v == null || v == org.json.JSONObject.NULL || v == ApkpyValues.NONE) return "NoneType";')
    lines.append('        if (v instanceof Boolean || v == ApkpyValues.TRUE || v == ApkpyValues.FALSE) return "bool";')
    lines.append('        if (v instanceof Integer || v instanceof Long || v instanceof java.math.BigInteger) return "int";')
    lines.append('        if (v instanceof Number) return "float";')
    lines.append('        if (v instanceof org.json.JSONArray) return "list";')
    lines.append('        if (v instanceof org.json.JSONObject) return "dict";')
    lines.append('        return "str";')
    lines.append('    }')
    lines.append("")
    lines.append('    /** Um item para comparar: o True/False/None da app como JSON, e um bool')
    lines.append('     *  como numero (no Python True == 1). */')
    lines.append('    private Object _apkpyComparable(Object v) {')
    lines.append('        if (v instanceof String) v = _apkpyJsonOut((String) v);')
    lines.append('        if (v instanceof Boolean) return ((Boolean) v) ? 1L : 0L;')
    lines.append('        return v;')
    lines.append('    }')
    lines.append("")
    lines.append('    private int _apkpyNumCmp(Number a, Number b) {')
    lines.append('        try {')
    lines.append('            return new java.math.BigDecimal(a.toString()).compareTo(new java.math.BigDecimal(b.toString()));')
    lines.append('        } catch (Exception e) {')
    lines.append('            return Double.compare(a.doubleValue(), b.doubleValue());')
    lines.append('        }')
    lines.append('    }')
    lines.append("")
    lines.append('    /** Texto contra texto pela ordem do Python: ponto de codigo a ponto de codigo. */')
    lines.append('    private int _apkpyTextCmp(String a, String b) {')
    lines.append('        int i = 0, j = 0;')
    lines.append('        while (i < a.length() && j < b.length()) {')
    lines.append('            int x = a.codePointAt(i), y = b.codePointAt(j);')
    lines.append('            if (x != y) return x < y ? -1 : 1;')
    lines.append('            i += Character.charCount(x);')
    lines.append('            j += Character.charCount(y);')
    lines.append('        }')
    lines.append('        return (i < a.length() ? 1 : 0) - (j < b.length() ? 1 : 0);')
    lines.append('    }')
    lines.append("")
    lines.append('    /** a == b entre itens, como o Python: 1 == 1.0, listas item a item. Um')
    lines.append('     *  numero e o seu texto ("3" e 3) contam como iguais, como no x in lista:')
    lines.append('     *  no telemovel um numero chega muitas vezes como texto. */')
    lines.append('    private boolean _apkpyEq(Object a, Object b) {')
    lines.append('        a = _apkpyComparable(a);')
    lines.append('        b = _apkpyComparable(b);')
    lines.append('        if (a instanceof Number && b instanceof Number) return _apkpyNumCmp((Number) a, (Number) b) == 0;')
    lines.append('        if (a instanceof org.json.JSONArray && b instanceof org.json.JSONArray) {')
    lines.append('            org.json.JSONArray x = (org.json.JSONArray) a, y = (org.json.JSONArray) b;')
    lines.append('            if (x.length() != y.length()) return false;')
    lines.append('            for (int i = 0; i < x.length(); i++) if (!_apkpyEq(x.opt(i), y.opt(i))) return false;')
    lines.append('            return true;')
    lines.append('        }')
    lines.append('        if (a instanceof org.json.JSONObject && b instanceof org.json.JSONObject) {')
    lines.append('            org.json.JSONObject x = (org.json.JSONObject) a, y = (org.json.JSONObject) b;')
    lines.append('            if (x.length() != y.length()) return false;')
    lines.append('            java.util.Iterator<String> keys = x.keys();')
    lines.append('            while (keys.hasNext()) {')
    lines.append('                String k = keys.next();')
    lines.append('                if (!y.has(k) || !_apkpyEq(x.opt(k), y.opt(k))) return false;')
    lines.append('            }')
    lines.append('            return true;')
    lines.append('        }')
    lines.append('        return _apkpyFromJson(a).equals(_apkpyFromJson(b));')
    lines.append('    }')
    lines.append("")
    lines.append('    /** a < b para o sort(): numeros com numeros, texto com texto, listas item')
    lines.append("     *  a item. O resto e' o TypeError do Python. */")
    lines.append('    private int _apkpyCmp(Object a, Object b) {')
    lines.append('        a = _apkpyComparable(a);')
    lines.append('        b = _apkpyComparable(b);')
    lines.append('        if (a instanceof Number && b instanceof Number) return _apkpyNumCmp((Number) a, (Number) b);')
    lines.append('        if (a instanceof String && b instanceof String) return _apkpyTextCmp((String) a, (String) b);')
    lines.append('        if (a instanceof org.json.JSONArray && b instanceof org.json.JSONArray) {')
    lines.append('            org.json.JSONArray x = (org.json.JSONArray) a, y = (org.json.JSONArray) b;')
    lines.append('            for (int i = 0; i < Math.min(x.length(), y.length()); i++) {')
    lines.append('                if (!_apkpyEq(x.opt(i), y.opt(i))) return _apkpyCmp(x.opt(i), y.opt(i));')
    lines.append('            }')
    lines.append('            return Integer.compare(x.length(), y.length());')
    lines.append('        }')
    lines.append('        throw new ApkpyValues.Raised("TypeError", "\'<\' not supported between instances of \'"')
    lines.append('                + _apkpyTypeName(a) + "\' and \'" + _apkpyTypeName(b) + "\'");')
    lines.append('    }')
    lines.append('')
    lines.append('    /** a < b entre dois valores que a fonte nao diz o que sao (um item de uma')
    lines.append('     *  lista, a variavel de um for): pelo que cada um tem, lido como o')
    lines.append('     *  isinstance() o le. Como texto, o maior de 9, 12 e 10 num for dava 9. */')
    lines.append('    private int _apkpyCompare(Object a, Object b, int raw, String op) {')
    lines.append('        // raw: 1 when a is the item as the JSON holds it, 2 when b is; the')
    lines.append("        // other side is the app's text, read by its digits.")
    lines.append('        Object x = _apkpyComparable((raw & 1) != 0 ? a : _apkpyTyped(a));')
    lines.append('        Object y = _apkpyComparable((raw & 2) != 0 ? b : _apkpyTyped(b));')
    lines.append('        // A text that only looked like a number stays text against text.')
    lines.append('        if (x instanceof Number && (raw & 1) == 0 && y instanceof String) x = _apkpyComparable(a);')
    lines.append('        if (y instanceof Number && (raw & 2) == 0 && x instanceof String) y = _apkpyComparable(b);')
    lines.append('        boolean same = (x instanceof Number && y instanceof Number)')
    lines.append('                || (x instanceof String && y instanceof String)')
    lines.append('                || (x instanceof org.json.JSONArray && y instanceof org.json.JSONArray);')
    lines.append('        if (!same) {')
    lines.append('            throw new ApkpyValues.Raised("TypeError", "\'" + op + "\' not supported between instances of \'"')
    lines.append('                    + _apkpyTypeName(x) + "\' and \'" + _apkpyTypeName(y) + "\'");')
    lines.append('        }')
    lines.append('        return _apkpyCmp(x, y);')
    lines.append('    }')
    lines.append('')
    lines.append('    /** O texto de um valor sem tipo como o isinstance() o le: numero pelos')
    lines.append('     *  digitos, lista ou dict pelo JSON, o resto texto (ApkpyValues.pyType). */')
    lines.append('    private Object _apkpyTyped(Object v) {')
    lines.append('        if (!(v instanceof String)) return v;')
    lines.append('        String s = (String) v;')
    lines.append('        if (s == ApkpyValues.ZERO || s == ApkpyValues.ZERO_FLOAT) return s;')
    lines.append('        String type = ApkpyValues.pyType(s);')
    lines.append('        try {')
    lines.append('            if ("int".equals(type)) {')
    lines.append('                try { return Long.valueOf(s); } catch (NumberFormatException big) { return new java.math.BigInteger(s); }')
    lines.append('            }')
    lines.append('            if ("float".equals(type)) return Double.valueOf(s);')
    lines.append('            if ("list".equals(type)) return new org.json.JSONArray(s.trim());')
    lines.append('            if ("dict".equals(type)) return new org.json.JSONObject(s.trim());')
    lines.append('        } catch (Exception ignored) { }')
    lines.append('        return s;')
    lines.append('    }')
    lines.append('')
    lines.append('    /** isinstance() of an item as the JSON holds it: "10" read from a list is')
    lines.append('     *  str. An object of a class of the app is asked as before. */')
    lines.append('    private boolean _apkpyIsA(Object v, String names) {')
    lines.append('        if (v instanceof String && ApkpyValues.isObjectText((String) v)) {')
    lines.append('            return ApkpyValues.isInstance((String) v, names);')
    lines.append('        }')
    lines.append('        String type = _apkpyTypeName(v instanceof String ? _apkpyJsonOut((String) v) : v);')
    lines.append('        String all = "," + names + ",";')
    lines.append('        return all.contains("," + type + ",") || ("bool".equals(type) && all.contains(",int,"));')
    lines.append('    }')
    lines.append("")
    lines.append("    /** A lista de um metodo de lista; outra coisa e' o AttributeError do Python. */")
    lines.append('    private org.json.JSONArray _apkpyListArg(String json, String method) {')
    lines.append('        String text = json == null ? "" : json.trim();')
    lines.append('        if (_apkpyJsonShape(text) == 91) {')
    lines.append('            try { return new org.json.JSONArray(text); } catch (Exception ignored) { }')
    lines.append('        }')
    lines.append('        String kind = _apkpyJsonShape(text) == 123 ? "dict" : "str";')
    lines.append('        throw new ApkpyValues.Raised("AttributeError", "\'" + kind + "\' object has no attribute \'" + method + "\'");')
    lines.append('    }')
    lines.append("")
    lines.append('    private Object _apkpyStored(Object value) {')
    lines.append('        return value instanceof String ? _apkpyJsonOut((String) value) : value;')
    lines.append('    }')
    lines.append("")
    lines.append("    /** lista.insert(i, v): como o Python, uma posicao para la' do fim")
    lines.append('     *  acrescenta, e uma negativa demais poe a frente. */')
    lines.append('    private String _apkpyInsert(String json, String index, Object value) {')
    lines.append('        org.json.JSONArray arr = _apkpyListArg(json, "insert");')
    lines.append('        int n = arr.length(), at;')
    lines.append('        try { at = Integer.parseInt(String.valueOf(index).trim()); }')
    lines.append('        catch (Exception e) { throw new ApkpyValues.Raised("TypeError", "\'str\' object cannot be interpreted as an integer"); }')
    lines.append('        if (at < 0) at = Math.max(0, at + n);')
    lines.append('        if (at > n) at = n;')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        for (int i = 0; i < n; i++) {')
    lines.append('            if (i == at) out.put(_apkpyStored(value));')
    lines.append('            out.put(arr.opt(i));')
    lines.append('        }')
    lines.append('        if (at == n) out.put(_apkpyStored(value));')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append("    /** lista.remove(v): o primeiro igual; nenhum e' o ValueError do Python. */")
    lines.append('    private String _apkpyRemove(String json, Object value) {')
    lines.append('        org.json.JSONArray arr = _apkpyListArg(json, "remove");')
    lines.append('        for (int i = 0; i < arr.length(); i++) {')
    lines.append('            if (_apkpyEq(arr.opt(i), value)) {')
    lines.append('                arr.remove(i);')
    lines.append('                return arr.toString();')
    lines.append('            }')
    lines.append('        }')
    lines.append('        throw new ApkpyValues.Raised("ValueError", "list.remove(x): x not in list");')
    lines.append('    }')
    lines.append("")
    lines.append('    /** lista.extend(xs): os itens de uma lista, as letras de um texto, as')
    lines.append('     *  chaves de um dict -- o que o for percorreria. */')
    lines.append('    private String _apkpyExtend(String json, String items) {')
    lines.append('        org.json.JSONArray arr = _apkpyListArg(json, "extend");')
    lines.append('        org.json.JSONArray more = _apkpyItems(items);')
    lines.append('        for (int i = 0; i < more.length(); i++) arr.put(more.opt(i));')
    lines.append('        return arr.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** sort() e sorted(): estavel, como o do Python, tambem ao contrario. */')
    lines.append('    private String _apkpySort(String json, final boolean reverse) {')
    lines.append('        org.json.JSONArray arr = _apkpyListArg(json, "sort");')
    lines.append('        java.util.List<Object> items = new java.util.ArrayList<Object>();')
    lines.append('        for (int i = 0; i < arr.length(); i++) items.add(arr.opt(i));')
    lines.append('        java.util.Collections.sort(items, new java.util.Comparator<Object>() {')
    lines.append('            @Override public int compare(Object x, Object y) {')
    lines.append('                return reverse ? _apkpyCmp(y, x) : _apkpyCmp(x, y);')
    lines.append('            }')
    lines.append('        });')
    lines.append('        return new org.json.JSONArray(items).toString();')
    lines.append('    }')
    lines.append("")
    lines.append("    /** sorted(xs, key=...) e xs.sort(key=...): os itens pela ordem das chaves,")
    lines.append("     *  que vem numa lista a parte, uma por item. Estavel, como o do Python,")
    lines.append("     *  tambem ao contrario; os itens nao mudam de tipo. */")
    lines.append('    private String _apkpySortBy(org.json.JSONArray arr, String keysJson, final boolean reverse) {')
    lines.append('        org.json.JSONArray parsed;')
    lines.append('        try { parsed = new org.json.JSONArray(keysJson == null ? "[]" : keysJson); }')
    lines.append('        catch (Exception e) { parsed = new org.json.JSONArray(); }')
    lines.append('        final org.json.JSONArray keys = parsed;')
    lines.append('        Integer[] order = new Integer[arr.length()];')
    lines.append('        for (int i = 0; i < order.length; i++) order[i] = i;')
    lines.append('        java.util.Arrays.sort(order, new java.util.Comparator<Integer>() {')
    lines.append('            @Override public int compare(Integer x, Integer y) {')
    lines.append('                return reverse ? _apkpyCmp(keys.opt(y), keys.opt(x)) : _apkpyCmp(keys.opt(x), keys.opt(y));')
    lines.append('            }')
    lines.append('        });')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        for (Integer i : order) out.put(arr.opt(i));')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append("    /** A chave de um abs()/round()/sum() como o numero que e': o texto de um")
    lines.append("     *  int do Python nao tem ponto, o de um float tem sempre. */")
    lines.append('    private Object _apkpyNumberOf(String text) {')
    lines.append('        String t = text == null ? "" : text.trim();')
    lines.append('        try { return Long.valueOf(Long.parseLong(t)); } catch (Exception ignored) { }')
    lines.append('        try { return Double.valueOf(Double.parseDouble(t)); } catch (Exception ignored) { }')
    lines.append('        return text;')
    lines.append('    }')
    lines.append("")
    lines.append("    /** min/max(xs, key=...): o primeiro item com a menor ou a maior chave.")
    lines.append("     *  Sem itens, o default= ou o ValueError do Python. */")
    lines.append('    private String _apkpyExtremeBy(org.json.JSONArray arr, String keysJson, String fn, String fallback, boolean hasFallback) {')
    lines.append('        if (arr.length() == 0) {')
    lines.append('            if (hasFallback) return fallback;')
    lines.append('            throw new ApkpyValues.Raised("ValueError", fn + "() iterable argument is empty");')
    lines.append('        }')
    lines.append('        org.json.JSONArray keys;')
    lines.append('        try { keys = new org.json.JSONArray(keysJson == null ? "[]" : keysJson); }')
    lines.append('        catch (Exception e) { keys = new org.json.JSONArray(); }')
    lines.append('        boolean wantMax = "max".equals(fn);')
    lines.append('        int best = 0;')
    lines.append('        for (int i = 1; i < arr.length(); i++) {')
    lines.append('            int cmp = _apkpyCmp(keys.opt(i), keys.opt(best));')
    lines.append('            if (wantMax ? cmp > 0 : cmp < 0) best = i;')
    lines.append('        }')
    lines.append('        return _apkpyFromJson(arr.opt(best));')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpyReverse(String json) {')
    lines.append('        org.json.JSONArray arr = _apkpyListArg(json, "reverse");')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        for (int i = arr.length() - 1; i >= 0; i--) out.put(arr.opt(i));')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpyClear(String json) {')
    lines.append('        return _apkpyJsonShape(json) == 123 ? "{}" : "[]";')
    lines.append('    }')
    lines.append("")
    lines.append('    /** lista.pop(i) e d.pop(k, padrao). value=true devolve o item tirado;')
    lines.append('     *  false, a lista ou o dict sem ele. Vazio, fora ou sem a chave para,')
    lines.append('     *  como o IndexError e o KeyError do Python. */')
    lines.append('    private String _apkpyPop(String json, String key, boolean value, Object fallback, boolean hasFallback) {')
    lines.append('        String text = json == null ? "" : json.trim();')
    lines.append('        int shape = _apkpyJsonShape(text);')
    lines.append('        try {')
    lines.append('            if (shape == 123) {')
    lines.append('                org.json.JSONObject obj = new org.json.JSONObject(text);')
    lines.append('                if (!obj.has(key)) {')
    lines.append('                    if (!hasFallback) throw new ApkpyValues.Raised("KeyError", _apkpyRepr(String.valueOf(key)));')
    lines.append('                    return value ? _apkpyFromJson(fallback) : obj.toString();')
    lines.append('                }')
    lines.append('                Object item = obj.remove(key);')
    lines.append('                return value ? _apkpyFromJson(item) : obj.toString();')
    lines.append('            }')
    lines.append('            if (shape == 91 && !hasFallback) {')
    lines.append('                org.json.JSONArray arr = new org.json.JSONArray(text);')
    lines.append('                if (arr.length() == 0) throw new ApkpyValues.Raised("IndexError", "pop from empty list");')
    lines.append('                Object item = arr.remove(_apkpyListIndex(arr.length(), key, "pop index out of range"));')
    lines.append('                return value ? _apkpyFromJson(item) : arr.toString();')
    lines.append('            }')
    lines.append('        } catch (org.json.JSONException e) {')
    lines.append('            throw new IllegalArgumentException(e.getMessage());')
    lines.append('        }')
    lines.append('        throw new ApkpyValues.Raised("AttributeError", "\'" + (shape == 91 ? "list" : "str") + "\' object has no attribute \'pop\'");')
    lines.append('    }')
    lines.append("")
    lines.append("    /** lista.index(x) e texto.index(sub): onde esta', ou o ValueError. No")
    lines.append('     *  texto conta pontos de codigo, como o Python (kind 3 = texto). */')
    lines.append('    private String _apkpyIndexOf(String container, Object needle, int kind) {')
    lines.append('        String text = container == null ? "" : container;')
    lines.append('        if (kind != 3 && _apkpyJsonShape(text) == 91) {')
    lines.append('            org.json.JSONArray arr = _apkpyListArg(text, "index");')
    lines.append('            for (int i = 0; i < arr.length(); i++) {')
    lines.append('                if (_apkpyEq(arr.opt(i), needle)) return String.valueOf(i);')
    lines.append('            }')
    lines.append('            Object shown = _apkpyComparable(needle);')
    lines.append('            throw new ApkpyValues.Raised("ValueError", (shown instanceof String ? "\'" + shown + "\'" : _apkpyFromJson(shown))')
    lines.append('                    + " is not in list");')
    lines.append('        }')
    lines.append('        int at = text.indexOf(_apkpyFromJson(needle));')
    lines.append('        if (at < 0) throw new ApkpyValues.Raised("ValueError", "substring not found");')
    lines.append('        return String.valueOf(text.codePointCount(0, at));')
    lines.append('    }')
    lines.append("")
    lines.append("    /** O item que lista.pop(i) / d.pop(k, padrao) tira, como o JSON o tem:")
    lines.append("     *  9 e nao \"9\". So' le: a lista muda na linha seguinte (_apkpyPop). */")
    lines.append('    private Object _apkpyRawPop(String json, String key, Object fallback, boolean hasFallback) {')
    lines.append('        String text = json == null ? "" : json.trim();')
    lines.append('        int shape = _apkpyJsonShape(text);')
    lines.append('        try {')
    lines.append('            if (shape == 123) {')
    lines.append('                org.json.JSONObject obj = new org.json.JSONObject(text);')
    lines.append('                if (!obj.has(key)) {')
    lines.append('                    if (!hasFallback) throw new ApkpyValues.Raised("KeyError", _apkpyRepr(String.valueOf(key)));')
    lines.append('                    return fallback;')
    lines.append('                }')
    lines.append('                return obj.opt(key);')
    lines.append('            }')
    lines.append('            if (shape == 91 && !hasFallback) {')
    lines.append('                org.json.JSONArray arr = new org.json.JSONArray(text);')
    lines.append('                if (arr.length() == 0) throw new ApkpyValues.Raised("IndexError", "pop from empty list");')
    lines.append('                return arr.opt(_apkpyListIndex(arr.length(), key, "pop index out of range"));')
    lines.append('            }')
    lines.append('        } catch (org.json.JSONException e) {')
    lines.append('            throw new IllegalArgumentException(e.getMessage());')
    lines.append('        }')
    lines.append('        throw new ApkpyValues.Raised("AttributeError", "\'" + (shape == 91 ? "list" : "str") + "\' object has no attribute \'pop\'");')
    lines.append('    }')
    lines.append("")
    lines.append('    /** d.get(k, padrao) a entrar numa lista (as chaves de um sorted): o valor')
    lines.append("     *  como o JSON o tem, 3 e nao \"3\", ou o padrao com o seu tipo. */")
    lines.append('    private Object _apkpyRawGet(String json, String key, Object fallback) {')
    lines.append('        String text = json == null ? "" : json.trim();')
    lines.append('        int shape = _apkpyJsonShape(text);')
    lines.append('        if (shape != 123) {')
    lines.append('            throw new ApkpyValues.Raised("AttributeError", "\'" + (shape == 91 ? "list" : "str") + "\' object has no attribute \'get\'");')
    lines.append('        }')
    lines.append('        try {')
    lines.append('            org.json.JSONObject obj = new org.json.JSONObject(text);')
    lines.append('            return obj.has(key) ? obj.get(key) : fallback;')
    lines.append('        } catch (org.json.JSONException e) {')
    lines.append('            throw new IllegalArgumentException(e.getMessage());')
    lines.append('        }')
    lines.append('    }')
    lines.append("")
    lines.append('    /** d.get(k, padrao): o valor, ou o padrao -- None sem ele, como no Python. */')
    lines.append('    private String _apkpyDictGetOr(String json, String key, String fallback) {')
    lines.append('        String text = json == null ? "" : json.trim();')
    lines.append('        int shape = _apkpyJsonShape(text);')
    lines.append('        if (shape != 123) {')
    lines.append('            throw new ApkpyValues.Raised("AttributeError", "\'" + (shape == 91 ? "list" : "str") + "\' object has no attribute \'get\'");')
    lines.append('        }')
    lines.append('        try {')
    lines.append('            org.json.JSONObject obj = new org.json.JSONObject(text);')
    lines.append('            return obj.has(key) ? _apkpyFromJson(obj.opt(key)) : fallback;')
    lines.append('        } catch (org.json.JSONException e) {')
    lines.append('            throw new IllegalArgumentException(e.getMessage());')
    lines.append('        }')
    lines.append('    }')
    lines.append("")
    lines.append('    private org.json.JSONObject _apkpyDictArg(String json, String method) {')
    lines.append('        String text = json == null ? "" : json.trim();')
    lines.append('        int shape = _apkpyJsonShape(text);')
    lines.append('        if (shape == 123) {')
    lines.append('            try { return new org.json.JSONObject(text); } catch (Exception ignored) { }')
    lines.append('        }')
    lines.append('        throw new ApkpyValues.Raised("AttributeError", "\'" + (shape == 91 ? "list" : "str") + "\' object has no attribute \'" + method + "\'");')
    lines.append('    }')
    lines.append("")
    lines.append('    /** d.keys(), d.values(), d.items(): listas, pela ordem em que as chaves entraram. */')
    lines.append('    private String _apkpyKeyList(String json) {')
    lines.append('        return _apkpyKeys(_apkpyDictArg(json, "keys").toString()).toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpyValues(String json) {')
    lines.append('        org.json.JSONObject obj = _apkpyDictArg(json, "values");')
    lines.append('        org.json.JSONArray keys = _apkpyKeys(obj.toString());')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        for (int i = 0; i < keys.length(); i++) out.put(obj.opt(keys.optString(i)));')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpyPairs(String json) {')
    lines.append('        org.json.JSONObject obj = _apkpyDictArg(json, "items");')
    lines.append('        org.json.JSONArray keys = _apkpyKeys(obj.toString());')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        for (int i = 0; i < keys.length(); i++) {')
    lines.append('            org.json.JSONArray pair = new org.json.JSONArray();')
    lines.append('            pair.put(keys.optString(i));')
    lines.append('            pair.put(obj.opt(keys.optString(i)));')
    lines.append('            out.put(pair);')
    lines.append('        }')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** d.update(outro): as chaves do outro por cima, as novas no fim. */')
    lines.append('    private String _apkpyUpdate(String json, String other) {')
    lines.append('        org.json.JSONObject obj = _apkpyDictArg(json, "update");')
    lines.append('        org.json.JSONObject more = _apkpyDictArg(other, "keys");')
    lines.append('        org.json.JSONArray keys = _apkpyKeys(more.toString());')
    lines.append('        try {')
    lines.append('            for (int i = 0; i < keys.length(); i++) obj.put(keys.optString(i), more.opt(keys.optString(i)));')
    lines.append('        } catch (org.json.JSONException e) {')
    lines.append('            throw new IllegalArgumentException(e.getMessage());')
    lines.append('        }')
    lines.append('        return obj.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** O texto em pontos de codigo: as posicoes que o Python conta. */')
    lines.append('    private int[] _apkpyCodes(String s) {')
    lines.append('        return (s == null ? "" : s).codePoints().toArray();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** str.isspace() de um ponto de codigo. */')
    lines.append('    private boolean _apkpyPySpace(int c) {')
    lines.append('        return Character.isWhitespace(c) || Character.isSpaceChar(c) || c == 133;')
    lines.append('    }')
    lines.append("")
    lines.append('    private boolean _apkpyStripped(int c, int[] drop) {')
    lines.append('        if (drop == null) return _apkpyPySpace(c);')
    lines.append('        for (int d : drop) if (d == c) return true;')
    lines.append('        return false;')
    lines.append('    }')
    lines.append("")
    lines.append('    /** strip/lstrip/rstrip, com ou sem os caracteres a tirar (mode 0 os dois')
    lines.append('     *  lados, 1 a esquerda, 2 a direita). O argumento era ignorado. */')
    lines.append('    private String _apkpyStrip(String s, String chars, int mode) {')
    lines.append('        int[] cp = _apkpyCodes(s);')
    lines.append('        int[] drop = chars == null ? null : _apkpyCodes(chars);')
    lines.append('        int a = 0, b = cp.length;')
    lines.append('        if (mode != 2) while (a < b && _apkpyStripped(cp[a], drop)) a++;')
    lines.append('        if (mode != 1) while (b > a && _apkpyStripped(cp[b - 1], drop)) b--;')
    lines.append('        return new String(cp, a, b - a);')
    lines.append('    }')
    lines.append("")
    lines.append('    /** find/rfind contam pontos de codigo, como o Python; -1 se nao estiver. */')
    lines.append('    private String _apkpyFind(String s, String sub, boolean last) {')
    lines.append('        String t = s == null ? "" : s;')
    lines.append('        int at = last ? t.lastIndexOf(sub) : t.indexOf(sub);')
    lines.append('        return String.valueOf(at < 0 ? -1 : t.codePointCount(0, at));')
    lines.append('    }')
    lines.append("")
    lines.append('    /** "42".zfill(5) = "00042", "-42".zfill(5) = "-0042". */')
    lines.append('    private String _apkpyZfill(String s, long width) {')
    lines.append('        int[] cp = _apkpyCodes(s);')
    lines.append('        long fill = width - cp.length;')
    lines.append('        if (fill <= 0) return s;')
    lines.append('        StringBuilder out = new StringBuilder();')
    lines.append('        int start = 0;')
    lines.append('        if (cp.length > 0 && (cp[0] == 43 || cp[0] == 45)) {')
    lines.append('            out.appendCodePoint(cp[0]);')
    lines.append('            start = 1;')
    lines.append('        }')
    lines.append("        for (long i = 0; i < fill; i++) out.append('0');")
    lines.append('        out.append(new String(cp, start, cp.length - start));')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** ljust (mode 0), rjust (1), center (2): o centro como o do CPython. */')
    lines.append('    private String _apkpyPad(String s, long width, String fillchar, int mode) {')
    lines.append('        int[] cp = _apkpyCodes(s);')
    lines.append('        int[] f = _apkpyCodes(fillchar);')
    lines.append('        if (f.length != 1) throw new ApkpyValues.Raised("TypeError", "The fill character must be exactly one character long");')
    lines.append('        long marg = width - cp.length;')
    lines.append('        if (marg <= 0) return s;')
    lines.append('        long left = mode == 0 ? 0 : mode == 1 ? marg : marg / 2 + (marg & width & 1);')
    lines.append('        StringBuilder out = new StringBuilder();')
    lines.append('        for (long i = 0; i < left; i++) out.appendCodePoint(f[0]);')
    lines.append('        out.append(s);')
    lines.append('        for (long i = 0; i < marg - left; i++) out.appendCodePoint(f[0]);')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** A primeira em titulo, o resto em minusculas. */')
    lines.append('    private String _apkpyCapitalize(String s) {')
    lines.append('        int[] cp = _apkpyCodes(s);')
    lines.append('        if (cp.length == 0) return "";')
    lines.append('        return new String(Character.toChars(Character.toTitleCase(cp[0])))')
    lines.append('                + new String(cp, 1, cp.length - 1).toLowerCase(java.util.Locale.ROOT);')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpySwapcase(String s) {')
    lines.append('        StringBuilder out = new StringBuilder();')
    lines.append('        for (int c : _apkpyCodes(s)) {')
    lines.append('            String one = new String(Character.toChars(c));')
    lines.append('            if (Character.isUpperCase(c)) out.append(one.toLowerCase(java.util.Locale.ROOT));')
    lines.append('            else if (Character.isLowerCase(c)) out.append(one.toUpperCase(java.util.Locale.ROOT));')
    lines.append('            else out.append(one);')
    lines.append('        }')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** splitlines(): as quebras que o Python conhece, sem a parte vazia do fim. */')
    lines.append('    private String _apkpySplitLines(String s, boolean keep) {')
    lines.append('        org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('        String t = s == null ? "" : s;')
    lines.append('        int i = 0, start = 0, n = t.length();')
    lines.append('        while (i < n) {')
    lines.append('            char c = t.charAt(i);')
    lines.append('            int eol = 0;')
    lines.append('            if (c == 13) eol = (i + 1 < n && t.charAt(i + 1) == 10) ? 2 : 1;')
    lines.append('            else if (c == 10 || c == 11 || c == 12 || c == 28 || c == 29 || c == 30')
    lines.append('                    || c == 133 || c == 8232 || c == 8233) eol = 1;')
    lines.append('            if (eol > 0) {')
    lines.append('                out.put(t.substring(start, keep ? i + eol : i));')
    lines.append('                i += eol;')
    lines.append('                start = i;')
    lines.append('            } else {')
    lines.append('                i++;')
    lines.append('            }')
    lines.append('        }')
    lines.append('        if (start < n) out.put(t.substring(start));')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append("    /** isalpha, isdigit, ... por ponto de codigo, como o Python; vazio e' falso")
    lines.append('     *  (menos isascii). */')
    lines.append('    private boolean _apkpyStrIs(String s, String what) {')
    lines.append('        int[] cp = _apkpyCodes(s);')
    lines.append('        if (what.equals("ascii")) {')
    lines.append('            for (int c : cp) if (c > 127) return false;')
    lines.append('            return true;')
    lines.append('        }')
    lines.append('        if (cp.length == 0) return false;')
    lines.append('        boolean cased = false;')
    lines.append('        for (int c : cp) {')
    lines.append('            int type = Character.getType(c);')
    lines.append('            boolean decimal = type == Character.DECIMAL_DIGIT_NUMBER;')
    lines.append('            boolean digit = decimal || (type == Character.OTHER_NUMBER')
    lines.append('                    && Character.getNumericValue(c) >= 0 && Character.getNumericValue(c) <= 9);')
    lines.append('            boolean numeric = decimal || type == Character.LETTER_NUMBER || type == Character.OTHER_NUMBER;')
    lines.append('            switch (what) {')
    lines.append('                case "alpha": if (!Character.isLetter(c)) return false; break;')
    lines.append('                case "alnum": if (!Character.isLetter(c) && !numeric) return false; break;')
    lines.append('                case "decimal": if (!decimal) return false; break;')
    lines.append('                case "digit": if (!digit) return false; break;')
    lines.append('                case "numeric": if (!numeric) return false; break;')
    lines.append('                case "space": if (!_apkpyPySpace(c)) return false; break;')
    lines.append('                case "upper":')
    lines.append('                    if (Character.isLowerCase(c) || Character.isTitleCase(c)) return false;')
    lines.append('                    if (Character.isUpperCase(c)) cased = true;')
    lines.append('                    break;')
    lines.append('                case "lower":')
    lines.append('                    if (Character.isUpperCase(c) || Character.isTitleCase(c)) return false;')
    lines.append('                    if (Character.isLowerCase(c)) cased = true;')
    lines.append('                    break;')
    lines.append('                default: return false;')
    lines.append('            }')
    lines.append('        }')
    lines.append('        return (what.equals("upper") || what.equals("lower")) ? cased : true;')
    lines.append('    }')
    lines.append("")
    lines.append('    /** texto.replace(a, b, n): so as n primeiras. */')
    lines.append('    private String _apkpyReplaceN(String s, String old, String now, long count) {')
    lines.append('        String t = s == null ? "" : s;')
    lines.append('        if (count < 0) return t.replace(old, now);')
    lines.append('        StringBuilder out = new StringBuilder();')
    lines.append('        int from = 0;')
    lines.append('        for (long done = 0; done < count; done++) {')
    lines.append('            int at = old.isEmpty() ? (from <= t.length() ? from : -1) : t.indexOf(old, from);')
    lines.append('            if (at < 0) break;')
    lines.append('            out.append(t, from, at).append(now);')
    lines.append('            if (old.isEmpty()) {')
    lines.append('                if (at < t.length()) out.appendCodePoint(t.codePointAt(at));')
    lines.append('                from = at + (at < t.length() ? Character.charCount(t.codePointAt(at)) : 1);')
    lines.append('            } else {')
    lines.append('                from = at + old.length();')
    lines.append('            }')
    lines.append('        }')
    lines.append('        if (from <= t.length()) out.append(t.substring(from));')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpyChr(long n) {')
    lines.append('        if (n < 0 || n > 1114111) throw new ApkpyValues.Raised("ValueError", "chr() arg not in range(0x110000)");')
    lines.append('        return new String(Character.toChars((int) n));')
    lines.append('    }')
    lines.append("")
    lines.append('    private long _apkpyOrd(String s) {')
    lines.append('        int[] cp = _apkpyCodes(s);')
    lines.append('        if (cp.length != 1) {')
    lines.append('            throw new ApkpyValues.Raised("TypeError", "ord() expected a character, but string of length " + cp.length + " found");')
    lines.append('        }')
    lines.append('        return cp[0];')
    lines.append('    }')
    lines.append("")
    lines.append('    /** "-" * 10 e [0] * 3. */')
    lines.append('    private String _apkpyRepeat(String s, long n, boolean list) {')
    lines.append('        if (list) {')
    lines.append('            org.json.JSONArray arr = _apkpyListArg(s, "__mul__");')
    lines.append('            org.json.JSONArray out = new org.json.JSONArray();')
    lines.append('            for (long k = 0; k < n; k++) for (int i = 0; i < arr.length(); i++) out.put(arr.opt(i));')
    lines.append('            return out.toString();')
    lines.append('        }')
    lines.append('        StringBuilder out = new StringBuilder();')
    lines.append('        for (long k = 0; k < n; k++) out.append(s);')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    private long _apkpySliceBound(String raw, long n, long step, boolean upper) {')
    lines.append('        if (raw == null || raw.trim().isEmpty()) {')
    lines.append('            if (step < 0) return upper ? -1 : n - 1;')
    lines.append('            return upper ? n : 0;')
    lines.append('        }')
    lines.append('        long i = Long.parseLong(raw.trim());')
    lines.append('        if (i < 0) {')
    lines.append('            i += n;')
    lines.append('            if (i < 0) i = step < 0 ? -1 : 0;')
    lines.append('        } else if (i >= n) {')
    lines.append('            i = step < 0 ? n - 1 : n;')
    lines.append('        }')
    lines.append('        return i;')
    lines.append('    }')
    lines.append("")
    lines.append('    /** a[i:j:k] com as regras do slice.indices do Python. kind 3 = texto,')
    lines.append('     *  1 = lista, 0 = pela forma do valor. */')
    lines.append('    private String _apkpySliceStep(String value, String lo, String hi, String step, int kind) {')
    lines.append('        String text = value == null ? "" : value;')
    lines.append('        boolean list = kind == 1 || (kind == 0 && _apkpyJsonShape(text) == 91);')
    lines.append('        org.json.JSONArray arr = list ? _apkpyListArg(text, "__getitem__") : null;')
    lines.append('        int[] cp = list ? null : _apkpyCodes(text);')
    lines.append('        long n = list ? arr.length() : cp.length;')
    lines.append('        long k = step.trim().isEmpty() ? 1 : Long.parseLong(step.trim());')
    lines.append('        if (k == 0) throw new ApkpyValues.Raised("ValueError", "slice step cannot be zero");')
    lines.append('        long a = _apkpySliceBound(lo, n, k, false);')
    lines.append('        long b = _apkpySliceBound(hi, n, k, true);')
    lines.append('        StringBuilder out = new StringBuilder();')
    lines.append('        org.json.JSONArray picked = new org.json.JSONArray();')
    lines.append('        for (long i = a; k > 0 ? i < b : i > b; i += k) {')
    lines.append('            if (list) picked.put(arr.opt((int) i));')
    lines.append('            else out.appendCodePoint(cp[(int) i]);')
    lines.append('        }')
    lines.append('        return list ? picked.toString() : out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** format(valor, spec) com a mini-linguagem do Python:')
    lines.append('     *  [[fill]align][sign][#][0][width][,|_][.precision][type], e as mesmas')
    lines.append('     *  recusas (ValueError). kind 1 = numero, 2 = texto, 0 = pelo tipo pedido. */')
    lines.append('    private String _apkpyFormat(String value, String spec, int kind) {')
    lines.append('        String v = value == null ? "" : value;')
    lines.append('        int[] sp = spec.codePoints().toArray();')
    lines.append('        int i = 0, n = sp.length;')
    lines.append('        int fill = -1, align = 0;')
    lines.append('        if (n >= 2 && "<>=^".indexOf(sp[1]) >= 0) { fill = sp[0]; align = sp[1]; i = 2; }')
    lines.append('        else if (n >= 1 && "<>=^".indexOf(sp[0]) >= 0) { align = sp[0]; i = 1; }')
    lines.append('        int sign = 0;')
    lines.append('        if (i < n && (sp[i] == 43 || sp[i] == 45 || sp[i] == 32)) sign = sp[i++];')
    lines.append('        boolean alt = false;')
    lines.append('        if (i < n && sp[i] == 35) { alt = true; i++; }')
    lines.append('        boolean zero = false;')
    lines.append('        if (i < n && sp[i] == 48) { zero = true; i++; }')
    lines.append('        int width = 0;')
    lines.append('        while (i < n && sp[i] >= 48 && sp[i] <= 57) width = width * 10 + (sp[i++] - 48);')
    lines.append('        int group = 0;')
    lines.append('        if (i < n && (sp[i] == 44 || sp[i] == 95)) group = sp[i++];')
    lines.append('        int precision = -1;')
    lines.append('        if (i < n && sp[i] == 46) {')
    lines.append('            i++;')
    lines.append('            int start = i;')
    lines.append('            precision = 0;')
    lines.append('            while (i < n && sp[i] >= 48 && sp[i] <= 57) precision = precision * 10 + (sp[i++] - 48);')
    lines.append('            if (i == start) throw new ApkpyValues.Raised("ValueError", "Format specifier missing precision");')
    lines.append('        }')
    lines.append('        int type = i < n ? sp[i++] : 0;')
    lines.append('        if (i != n) throw new ApkpyValues.Raised("ValueError", "Invalid format specifier \'" + spec + "\'");')
    lines.append('        String t = v.trim();')
    lines.append('        boolean number = kind == 1 || (kind == 0 && type != 0 && type != 115);')
    lines.append('        if (zero && fill < 0) fill = 48;')
    lines.append('        if (fill < 0) fill = 32;')
    lines.append('        String typeName = type == 0 ? "" : new String(Character.toChars(type));')
    lines.append('        if (!number) {')
    lines.append('            if (type != 0 && type != 115) {')
    lines.append('                throw new ApkpyValues.Raised("ValueError", "Unknown format code \'" + typeName + "\' for object of type \'str\'");')
    lines.append('            }')
    lines.append('            if (sign != 0) throw new ApkpyValues.Raised("ValueError", "Sign not allowed in string format specifier");')
    lines.append('            if (alt) throw new ApkpyValues.Raised("ValueError", "Alternate form (#) not allowed in string format specifier");')
    lines.append('            if (group != 0) throw new ApkpyValues.Raised("ValueError", "Cannot specify \'" + (char) group + "\' with \'s\'.");')
    lines.append('            if (align == 61) throw new ApkpyValues.Raised("ValueError", "\'=\' alignment not allowed in string format specifier");')
    lines.append('            int[] cp = v.codePoints().toArray();')
    lines.append('            String body = precision >= 0 && precision < cp.length ? new String(cp, 0, precision) : v;')
    lines.append('            return _apkpyAlign(body, "", fill, align == 0 ? 60 : align, width);')
    lines.append('        }')
    lines.append('        if (zero && align == 0) align = 61;')
    lines.append('        boolean whole = t.matches("[+-]?[0-9]+");')
    lines.append('        boolean intType = type == 0 && whole || type == 100 || type == 110 || type == 120')
    lines.append('                || type == 88 || type == 111 || type == 98 || type == 99;')
    lines.append('        String body;')
    lines.append('        String prefix = "";')
    lines.append('        boolean negative;')
    lines.append('        int every = 3;')
    lines.append('        if (intType) {')
    lines.append('            if (!whole) throw new ApkpyValues.Raised("ValueError", "Unknown format code \'" + typeName + "\' for object of type \'float\'");')
    lines.append('            if (precision >= 0) throw new ApkpyValues.Raised("ValueError", "Precision not allowed in integer format specifier");')
    lines.append('            if (group == 44 && type != 0 && type != 100) throw new ApkpyValues.Raised("ValueError", "Cannot specify \',\' with \'" + typeName + "\'.");')
    lines.append('            if (group == 95 && (type == 110 || type == 99)) throw new ApkpyValues.Raised("ValueError", "Cannot specify \'_\' with \'" + typeName + "\'.");')
    lines.append('            java.math.BigInteger big = new java.math.BigInteger(t.startsWith("+") ? t.substring(1) : t);')
    lines.append('            if (type == 99) {')
    lines.append('                if (sign != 0) throw new ApkpyValues.Raised("ValueError", "Sign not allowed with integer format specifier \'c\'");')
    lines.append('                if (alt) throw new ApkpyValues.Raised("ValueError", "Alternate form (#) not allowed with integer format specifier \'c\'");')
    lines.append('                if (big.signum() < 0 || big.compareTo(java.math.BigInteger.valueOf(1114111)) > 0) {')
    lines.append('                    throw new ApkpyValues.Raised("OverflowError", "%c arg not in range(0x110000)");')
    lines.append('                }')
    lines.append('                return _apkpyAlign(new String(Character.toChars(big.intValue())), "", fill, align == 0 ? 62 : align, width);')
    lines.append('            }')
    lines.append('            negative = big.signum() < 0;')
    lines.append('            int radix = type == 120 || type == 88 ? 16 : type == 111 ? 8 : type == 98 ? 2 : 10;')
    lines.append('            body = big.abs().toString(radix);')
    lines.append('            if (type == 88) body = body.toUpperCase(java.util.Locale.ROOT);')
    lines.append('            if (radix != 10) every = 4;')
    lines.append('            if (alt && radix != 10) prefix = type == 120 ? "0x" : type == 88 ? "0X" : type == 111 ? "0o" : "0b";')
    lines.append('        } else {')
    lines.append('            if (type != 0 && "fFeEgG%".indexOf(type) < 0) {')
    lines.append('                throw new ApkpyValues.Raised("ValueError", "Unknown format code \'" + typeName + "\' for object of type \'float\'");')
    lines.append('            }')
    lines.append('            double d = t.equals("inf") || t.equals("+inf") ? Double.POSITIVE_INFINITY')
    lines.append('                    : t.equals("-inf") ? Double.NEGATIVE_INFINITY')
    lines.append('                    : t.equals("nan") || t.equals("-nan") || t.equals("+nan") ? Double.NaN : Double.parseDouble(t);')
    lines.append('            negative = d < 0 || (d == 0 && 1 / d < 0);')
    lines.append('            double a = Math.abs(d);')
    lines.append('            boolean upper = type == 70 || type == 69 || type == 71;')
    lines.append('            if (Double.isNaN(d) || Double.isInfinite(d)) {')
    lines.append('                body = Double.isNaN(d) ? "nan" : "inf";')
    lines.append('                if (upper) body = body.toUpperCase(java.util.Locale.ROOT);')
    lines.append('                if (type == 37) body += "%";')
    lines.append('                negative = d < 0;')
    lines.append('            } else if (type == 102 || type == 70) {')
    lines.append('                body = _apkpyFixed(new java.math.BigDecimal(a), precision < 0 ? 6 : precision, alt);')
    lines.append('            } else if (type == 37) {')
    lines.append('                // x * 100 in floating point, as Python does it, then the digits.')
    lines.append('                body = _apkpyFixed(new java.math.BigDecimal(a * 100), precision < 0 ? 6 : precision, alt) + "%";')
    lines.append('            } else if (type == 101 || type == 69) {')
    lines.append('                body = _apkpySci(new java.math.BigDecimal(a), precision < 0 ? 6 : precision, alt, type == 69);')
    lines.append('            } else if (type == 0 && precision < 0) {')
    lines.append('                body = _apkpyFloat(a);')
    lines.append("                int e = body.indexOf('e');")
    lines.append('                if (alt && e >= 0 && body.lastIndexOf(\'.\', e) < 0) body = body.substring(0, e) + "." + body.substring(e);')
    lines.append('            } else {')
    lines.append('                int p = precision < 0 ? 6 : (precision == 0 ? 1 : precision);')
    lines.append('                body = _apkpyGeneral(new java.math.BigDecimal(a), p, alt, type == 71, type == 0);')
    lines.append('            }')
    lines.append('        }')
    lines.append('        String signText = negative ? "-" : sign == 43 ? "+" : sign == 32 ? " " : "";')
    lines.append('        if (align == 0) align = 62;')
    lines.append('        boolean finite = !body.startsWith("nan") && !body.startsWith("inf") && !body.startsWith("NAN") && !body.startsWith("INF");')
    lines.append('        int cut = body.length();')
    lines.append('        if (!intType) {')
    lines.append('            for (int k = 0; k < body.length(); k++) {')
    lines.append('                char c = body.charAt(k);')
    lines.append("                if (c == '.' || c == 'e' || c == 'E' || c == '%') { cut = k; break; }")
    lines.append('            }')
    lines.append('        }')
    lines.append('        String digits = body.substring(0, cut), tail = body.substring(cut);')
    lines.append('        if (group != 0 && finite) {')
    lines.append('            if (align == 61 && fill == 48) {')
    lines.append('                // Zeros padding a grouped number are grouped too, as in Python.')
    lines.append('                int room = width - signText.length() - prefix.length() - tail.length();')
    lines.append('                String grouped = _apkpyGroup(digits, group, every);')
    lines.append('                while (grouped.length() < room) {')
    lines.append('                    digits = "0" + digits;')
    lines.append('                    grouped = _apkpyGroup(digits, group, every);')
    lines.append('                }')
    lines.append('                return signText + prefix + grouped + tail;')
    lines.append('            }')
    lines.append('            body = _apkpyGroup(digits, group, every) + tail;')
    lines.append('        }')
    lines.append('        return _apkpyAlign(body, signText + prefix, fill, align, width);')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpyGroup(String digits, int sep, int every) {')
    lines.append('        if (sep == 0 || digits.length() <= every) return digits;')
    lines.append('        StringBuilder out = new StringBuilder();')
    lines.append('        int first = digits.length() % every;')
    lines.append('        if (first == 0) first = every;')
    lines.append('        out.append(digits, 0, first);')
    lines.append('        for (int k = first; k < digits.length(); k += every) out.appendCodePoint(sep).append(digits, k, k + every);')
    lines.append('        return out.toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpyAlign(String body, String sign, int fill, int align, int width) {')
    lines.append('        int len = sign.codePointCount(0, sign.length()) + body.codePointCount(0, body.length());')
    lines.append('        int pad = Math.max(0, width - len);')
    lines.append('        String f = new String(Character.toChars(fill));')
    lines.append('        int left = align == 60 ? 0 : align == 94 ? pad / 2 : pad;')
    lines.append('        StringBuilder before = new StringBuilder(), after = new StringBuilder();')
    lines.append('        for (int k = 0; k < left; k++) before.append(f);')
    lines.append('        for (int k = 0; k < pad - left; k++) after.append(f);')
    lines.append('        if (align == 61) return sign + before + after + body;')
    lines.append('        return before + sign + body + after;')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpyFixed(java.math.BigDecimal a, int precision, boolean alt) {')
    lines.append('        String s = a.setScale(precision, java.math.RoundingMode.HALF_EVEN).toPlainString();')
    lines.append('        return alt && precision == 0 ? s + "." : s;')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpySci(java.math.BigDecimal a, int precision, boolean alt, boolean upper) {')
    lines.append('        int exp = 0;')
    lines.append('        StringBuilder digits = new StringBuilder();')
    lines.append('        if (a.signum() == 0) {')
    lines.append("            for (int k = 0; k <= precision; k++) digits.append('0');")
    lines.append('        } else {')
    lines.append('            java.math.BigDecimal r = a.round(new java.math.MathContext(precision + 1, java.math.RoundingMode.HALF_EVEN));')
    lines.append('            exp = r.precision() - r.scale() - 1;')
    lines.append('            digits.append(r.unscaledValue().toString());')
    lines.append("            while (digits.length() < precision + 1) digits.append('0');")
    lines.append('            digits.setLength(precision + 1);')
    lines.append('        }')
    lines.append('        String mant = digits.substring(0, 1) + (precision > 0 || alt ? "." : "") + digits.substring(1);')
    lines.append('        return mant + (upper ? "E" : "e") + (exp < 0 ? "-" : "+") + (Math.abs(exp) < 10 ? "0" : "") + Math.abs(exp);')
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpyGeneral(java.math.BigDecimal a, int p, boolean alt, boolean upper, boolean none) {')
    lines.append('        int exp = 0;')
    lines.append('        if (a.signum() != 0) {')
    lines.append('            java.math.BigDecimal r = a.round(new java.math.MathContext(p, java.math.RoundingMode.HALF_EVEN));')
    lines.append('            exp = r.precision() - r.scale() - 1;')
    lines.append('        }')
    lines.append('        // With no type, CPython goes to the exponent one digit sooner.')
    lines.append('        if (-4 <= exp && exp < p - (none ? 1 : 0)) {')
    lines.append('            String s = _apkpyFixed(a, p - 1 - exp, false);')
    lines.append("            if (!alt && s.indexOf('.') >= 0) s = _apkpyTrimZeros(s);")
    lines.append('            if (s.indexOf(\'.\') < 0) s += none ? ".0" : alt ? "." : "";')
    lines.append('            return s;')
    lines.append('        }')
    lines.append('        String s = _apkpySci(a, p - 1, alt, upper);')
    lines.append('        if (alt) return s;')
    lines.append("        int e = s.indexOf(upper ? 'E' : 'e');")
    lines.append('        String m = s.substring(0, e);')
    lines.append("        return (m.indexOf('.') >= 0 ? _apkpyTrimZeros(m) : m) + s.substring(e);")
    lines.append('    }')
    lines.append("")
    lines.append('    private String _apkpyTrimZeros(String s) {')
    lines.append('        int end = s.length();')
    lines.append("        while (end > 0 && s.charAt(end - 1) == '0') end--;")
    lines.append("        if (end > 0 && s.charAt(end - 1) == '.') end--;")
    lines.append('        return s.substring(0, end);')
    lines.append('    }')
    lines.append("")
    lines.append('    /** "%d" % 3.7 = "3": a parte inteira, sem perder digitos num inteiro grande. */')
    lines.append('    private String _apkpyWholePart(String v) {')
    lines.append('        String t = v == null ? "" : v.trim();')
    lines.append('        if (t.matches("[+-]?[0-9]+")) return t;')
    lines.append('        return new java.math.BigDecimal(Double.toString(Double.parseDouble(t))).toBigInteger().toString();')
    lines.append('    }')
    lines.append("")
    lines.append('    /** O repr de um texto, como o Python: aspas simples, ou duplas se so')
    lines.append('     *  houver simples dentro, e os escapes. */')
    lines.append('    private String _apkpyRepr(String s) {')
    lines.append('        return ApkpyValues.repr(s);')
    lines.append('    }')
    lines.append("")
    lines.append("")
    lines.append("    /** str() of a list or dict as Python shows it: [1, 'a', None],")
    lines.append("     *  {'k': True}. The JSON it is kept as says the type of each item. */")
    lines.append('    private String _apkpyShow(String json) {')
    lines.append('        String text = json == null ? "" : json.trim();')
    lines.append('        try {')
    lines.append('            if (_apkpyJsonShape(text) == 91) return _apkpyShowItem(new org.json.JSONArray(text));')
    lines.append('            if (_apkpyJsonShape(text) == 123) return _apkpyShowItem(new org.json.JSONObject(text));')
    lines.append('        } catch (Exception ignored) {}')
    lines.append('        return json == null ? "" : json;')
    lines.append('    }')
    lines.append('')
    lines.append("    /** str() of a value read out of a list or a dict: a list or a dict in")
    lines.append("     *  it as Python shows it, ['tea'] and not [\"tea\"]; anything else as")
    lines.append("     *  text already says. */")
    lines.append('    private String _apkpyStrRaw(Object raw, String text) {')
    lines.append('        if (raw instanceof org.json.JSONArray || raw instanceof org.json.JSONObject)')
    lines.append('            return _apkpyShowItem(raw);')
    lines.append('        return text;')
    lines.append('    }')
    lines.append('')
    lines.append('    /** str() of a list of tuples: [(1, 2), (3, 4)], as zip(), items() and')
    lines.append('     *  most_common() give them. Kept as a list of lists. */')
    lines.append('    private String _apkpyShowTuples(String json) {')
    lines.append('        try {')
    lines.append('            org.json.JSONArray arr = new org.json.JSONArray(json == null ? "[]" : json.trim());')
    lines.append("            StringBuilder out = new StringBuilder().append('[');")
    lines.append('            for (int i = 0; i < arr.length(); i++) {')
    lines.append('                if (i > 0) out.append(", ");')
    lines.append('                Object item = arr.opt(i);')
    lines.append('                out.append(item instanceof org.json.JSONArray ? _apkpyShowTuple(item.toString()) : _apkpyShowItem(item));')
    lines.append('            }')
    lines.append("            return out.append(']').toString();")
    lines.append('        } catch (Exception ignored) {')
    lines.append('            return _apkpyShow(json);')
    lines.append('        }')
    lines.append('    }')
    lines.append('')
    lines.append('    /** str() of a tuple: (1, 2), and (1,) with one item. Kept as a list. */')
    lines.append('    private String _apkpyShowTuple(String json) {')
    lines.append('        try {')
    lines.append('            org.json.JSONArray arr = new org.json.JSONArray(json == null ? "[]" : json.trim());')
    lines.append("            StringBuilder out = new StringBuilder().append('(');")
    lines.append('            for (int i = 0; i < arr.length(); i++) {')
    lines.append('                if (i > 0) out.append(", ");')
    lines.append('                out.append(_apkpyShowItem(arr.opt(i)));')
    lines.append('            }')
    lines.append("            if (arr.length() == 1) out.append(',');")
    lines.append("            return out.append(')').toString();")
    lines.append('        } catch (Exception ignored) {')
    lines.append('            return _apkpyShow(json);')
    lines.append('        }')
    lines.append('    }')
    lines.append('')
    lines.append('    private String _apkpyShowItem(Object item) {')
    lines.append('        if (item == null || item == org.json.JSONObject.NULL) return "None";')
    lines.append('        if (item instanceof Boolean) return ((Boolean) item) ? "True" : "False";')
    lines.append('        if (item instanceof String) return _apkpyRepr((String) item);')
    lines.append('        if (item instanceof Double || item instanceof Float || item instanceof java.math.BigDecimal)')
    lines.append('            return _apkpyFloat(((Number) item).doubleValue());')
    lines.append('        if (item instanceof Number) return String.valueOf(((Number) item).longValue());')
    lines.append('        StringBuilder out = new StringBuilder();')
    lines.append('        if (item instanceof org.json.JSONArray) {')
    lines.append('            org.json.JSONArray arr = (org.json.JSONArray) item;')
    lines.append("            out.append('[');")
    lines.append('            for (int i = 0; i < arr.length(); i++) {')
    lines.append('                if (i > 0) out.append(", ");')
    lines.append('                out.append(_apkpyShowItem(arr.opt(i)));')
    lines.append('            }')
    lines.append("            return out.append(']').toString();")
    lines.append('        }')
    lines.append('        if (item instanceof org.json.JSONObject) {')
    lines.append('            org.json.JSONObject obj = (org.json.JSONObject) item;')
    lines.append('            out.append((char) 123);')
    lines.append('            java.util.Iterator<String> keys = obj.keys();')
    lines.append('            boolean first = true;')
    lines.append('            while (keys.hasNext()) {')
    lines.append('                String key = keys.next();')
    lines.append('                if (!first) out.append(", ");')
    lines.append('                first = false;')
    lines.append('                out.append(_apkpyRepr(key)).append(": ").append(_apkpyShowItem(obj.opt(key)));')
    lines.append('            }')
    lines.append('            return out.append((char) 125).toString();')
    lines.append('        }')
    lines.append('        return String.valueOf(item);')
    lines.append('    }')
    lines.append('')
    lines.append('    /** pow(a, b, m): exact, with the sign of m and, for b < 0, the inverse. */')
    lines.append('    private static long _apkpyPowMod(long base, long exp, long mod) {')
    lines.append('        if (mod == 0) throw new ApkpyValues.Raised("ValueError", "pow() 3rd argument cannot be 0");')
    lines.append('        java.math.BigInteger m = java.math.BigInteger.valueOf(mod).abs();')
    lines.append('        java.math.BigInteger r;')
    lines.append('        try {')
    lines.append('            r = java.math.BigInteger.valueOf(base).modPow(java.math.BigInteger.valueOf(exp), m);')
    lines.append('        } catch (ArithmeticException e) {')
    lines.append('            throw new ApkpyValues.Raised("ValueError", "base is not invertible for the given modulus");')
    lines.append('        }')
    lines.append('        long out = r.longValue();')
    lines.append('        return mod < 0 && out != 0 ? out + mod : out;')
    lines.append('    }')
    lines.append("")
    lines.append("    /** Um numero como o Python o escreve: 12, -3, 2.5, 1e-05. */")
    lines.append("    private boolean _apkpyIsNumber(String t) {")
    lines.append("        if (t == null || t.isEmpty()) return false;")
    lines.append("        for (int i = 0; i < t.length(); i++) {")
    lines.append("            char c = t.charAt(i);")
    lines.append("            if (!(Character.isDigit(c) || c == '.' || c == '-' || c == '+' || c == 'e' || c == 'E')) return false;")
    lines.append("        }")
    lines.append("        try {")
    lines.append("            Double.parseDouble(t);")
    lines.append("            if (_apkpyIsWhole(t)) Long.parseLong(t);")
    lines.append("            return true;")
    lines.append("        } catch (Exception e) {")
    lines.append("            return false;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /** round(x, n) de um decimal, como o CPython: o valor EXACTO do double")
    lines.append("     *  arredondado a n casas, meio para o par. Multiplicar por 10^n arredondava")
    lines.append("     *  antes do tempo: round(-0.025, 2) dava -0.02 e o Python -0.03. */")
    lines.append("    private double _apkpyRoundTo(double value, int digits) {")
    lines.append("        if (Double.isNaN(value) || Double.isInfinite(value)) return value;")
    lines.append("        double out = new java.math.BigDecimal(value)")
    lines.append("                .setScale(digits, java.math.RoundingMode.HALF_EVEN).doubleValue();")
    lines.append("        return out == 0d ? Math.copySign(0d, value) : out;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** round(n, -2) de um inteiro: 1250 da' 1200, meio para o par. */")
    lines.append("    private long _apkpyRoundL(long value, int digits) {")
    lines.append("        return java.math.BigDecimal.valueOf(value)")
    lines.append("                .setScale(digits, java.math.RoundingMode.HALF_EVEN).longValueExact();")
    lines.append("    }")
    lines.append("")
    lines.append("    /** abs() de um inteiro: o Math.abs do menor long devolve-o negativo. */")
    lines.append("    private long _apkpyAbsL(long value) {")
    lines.append("        if (value == Long.MIN_VALUE) throw new ArithmeticException(\"integer overflow\");")
    lines.append("        return Math.abs(value);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** Em Python abs(-3) e' 3 e nao 3.0. Aqui todos os valores sao")
    lines.append("     *  texto, por isso a diferenca entre inteiro e decimal e' ter")
    lines.append("     *  ponto -- e o resultado tem de a manter. */")
    lines.append("    private boolean _apkpyIsWhole(String text) {")
    lines.append("        String t = String.valueOf(text).trim();")
    lines.append("        return t.indexOf('.') < 0 && t.indexOf('e') < 0")
    lines.append("                && t.indexOf('E') < 0 && !t.isEmpty();")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyAbs(String value) {")
    lines.append("        try {")
    lines.append("            if (_apkpyIsWhole(value)) {")
    lines.append("                return String.valueOf(")
    lines.append("                        Math.abs(Long.parseLong(String.valueOf(value).trim())));")
    lines.append("            }")
    lines.append("            return String.valueOf(")
    lines.append("                    Math.abs(Double.parseDouble(String.valueOf(value).trim())));")
    lines.append("        } catch (Exception e) {")
    lines.append("            throw new ApkpyValues.Raised(\"TypeError\", \"abs() needs a number\");")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /** min/max. Um argumento so' e' uma lista, como em Python; devolve")
    lines.append('     *  o **texto original** para um inteiro continuar inteiro. Os itens de')
    lines.append('     *  uma lista comparam-se como o JSON os tem: numeros com numeros, texto')
    lines.append('     *  com texto ("9" e\' o maior de "10", "9", "011"), o resto TypeError. */')
    lines.append('    private String _apkpyExtreme(boolean wantMax, String... values) {')
    lines.append('        java.util.List<String> items = new java.util.ArrayList<>();')
    lines.append('        if (values.length == 1) {')
    lines.append('            org.json.JSONArray arr = null;')
    lines.append('            try {')
    lines.append('                arr = new org.json.JSONArray(String.valueOf(values[0]));')
    lines.append('            } catch (Exception e) {')
    lines.append('                items.add(String.valueOf(values[0]));')
    lines.append('            }')
    lines.append('            if (arr != null) {')
    lines.append('                if (arr.length() == 0) {')
    lines.append('                    throw new ApkpyValues.Raised("ValueError",')
    lines.append('                            (wantMax ? "max" : "min") + "() iterable argument is empty");')
    lines.append('                }')
    lines.append('                Object best = arr.opt(0);')
    lines.append('                for (int i = 1; i < arr.length(); i++) {')
    lines.append('                    Object item = arr.opt(i);')
    lines.append('                    int cmp = _apkpyCompare(item, best, 3, wantMax ? ">" : "<");')
    lines.append('                    if (wantMax ? cmp > 0 : cmp < 0) best = item;')
    lines.append('                }')
    lines.append('                return _apkpyFromJson(best);')
    lines.append('            }')
    lines.append('        } else {')
    lines.append("            for (String v : values) items.add(String.valueOf(v));")
    lines.append("        }")
    lines.append("        if (items.isEmpty()) {")
    lines.append("            throw new ApkpyValues.Raised(\"ValueError\", \"min/max of an empty list\");")
    lines.append("        }")
    lines.append("        String best = items.get(0);")
    lines.append("        for (String item : items) {")
    lines.append("            int cmp;")
    lines.append("            try {")
    lines.append("                cmp = Double.compare(Double.parseDouble(item.trim()),")
    lines.append("                                     Double.parseDouble(best.trim()));")
    lines.append("            } catch (Exception e) {")
    lines.append("                cmp = item.compareTo(best);")
    lines.append("            }")
    lines.append("            if (wantMax ? cmp > 0 : cmp < 0) best = item;")
    lines.append("        }")
    lines.append("        return best;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** sum(lista). Inteiros somam para inteiro, como em Python, e uma")
    lines.append("     *  lista vazia da' 0 em vez de rebentar. */")
    lines.append("    private String _apkpySum(String jsonArr) {")
    lines.append("        double total = 0d;")
    lines.append("        boolean whole = true;")
    lines.append("        try {")
    lines.append("            org.json.JSONArray arr =")
    lines.append("                    new org.json.JSONArray(String.valueOf(jsonArr));")
    lines.append("            for (int i = 0; i < arr.length(); i++) {")
    lines.append("                String item = String.valueOf(arr.get(i)).trim();")
    lines.append("                if (!_apkpyIsWhole(item)) whole = false;")
    lines.append("                total += Double.parseDouble(item);")
    lines.append("            }")
    lines.append("        } catch (Exception e) {")
    lines.append("            throw new ApkpyValues.Raised(\"TypeError\", \"sum() needs a list of numbers\");")
    lines.append("        }")
    lines.append("        return whole ? String.valueOf((long) total) : _apkpyFloat(total);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** lista.append(x). Uma lista é texto JSON aqui, por isso isto")
    lines.append("     *  devolve a lista nova em vez de mudar um objeto no sítio. */")
    lines.append("    private String _apkpyListAppend(String json, Object value) {")
    lines.append("        org.json.JSONArray arr;")
    lines.append("        try {")
    lines.append("            arr = new org.json.JSONArray(json == null ? \"[]\" : json);")
    lines.append("        } catch (Exception e) {")
    lines.append("            arr = new org.json.JSONArray();")
    lines.append("        }")
    lines.append("        // flags.append(n > 2): the app's True goes in as JSON true, not the word.")
    lines.append("        arr.put(value instanceof String ? _apkpyJsonOut((String) value) : value);")
    lines.append("        return arr.toString();")
    lines.append("    }")
    lines.append("")
    lines.append("    /** lista[i], com o índice negativo do Python. Fora dos limites")
    lines.append("     *  devolve vazio, como o resto do modelo -- menos dentro de um try")
    lines.append("     *  que apanha o IndexError, onde o levanta (ApkpyValues.strict). */")
    lines.append("    private String _apkpyListGet(String json, String index) {")
    lines.append("        org.json.JSONArray arr;")
    lines.append("        int i;")
    lines.append("        try {")
    lines.append("            arr = new org.json.JSONArray(json == null ? \"[]\" : json);")
    lines.append("            i = Integer.parseInt(String.valueOf(index).trim());")
    lines.append("        } catch (Exception e) {")
    lines.append("            return \"\";")
    lines.append("        }")
    lines.append("        if (i < 0) i += arr.length();")
    lines.append("        if (i < 0 || i >= arr.length()) {")
    lines.append("            if (ApkpyValues.strict()) throw new ApkpyValues.Raised(\"IndexError\", \"list index out of range\");")
    lines.append("            return \"\";")
    lines.append("        }")
    lines.append("        return _apkpyFromJson(arr.opt(i));")
    lines.append("    }")
    lines.append("")
    lines.append("    /** lista[a:b], com as pontas do Python. Fatiar a lista como texto")
    lines.append("     *  cortava o proprio JSON: itens[1:] dava '\"a\",\"b\"]'. */")
    lines.append("    private String _apkpyListSlice(String json, String from, String to) {")
    lines.append("        org.json.JSONArray arr;")
    lines.append("        try {")
    lines.append("            arr = new org.json.JSONArray(json == null ? \"[]\" : json);")
    lines.append("        } catch (Exception e) {")
    lines.append("            arr = new org.json.JSONArray();")
    lines.append("        }")
    lines.append("        int size = arr.length();")
    lines.append("        int start = _apkpySliceEdge(from, 0, size);")
    lines.append("        int end = _apkpySliceEdge(to, size, size);")
    lines.append("        org.json.JSONArray out = new org.json.JSONArray();")
    lines.append("        for (int i = start; i < end; i++) out.put(arr.opt(i));")
    lines.append("        return out.toString();")
    lines.append("    }")
    lines.append("")
    lines.append("    /** v[a:b] quando o codigo nao diz o que v e': lista se for JSON de")
    lines.append("     *  uma lista, texto se nao. */")
    lines.append("    private String _apkpySliceAny(String value, String from, String to) {")
    lines.append("        if (_apkpyJsonShape(value) == 91) {")
    lines.append("            try {")
    lines.append("                new org.json.JSONArray(value.trim());")
    lines.append("                return _apkpyListSlice(value.trim(), from, to);")
    lines.append("            } catch (Exception ignored) {}")
    lines.append("        }")
    lines.append("        return _apkpySlice(value, from, to);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** texto[i]: a letra, contada como o Python conta (um emoji e' uma),")
    lines.append("     *  com o indice negativo de la'. Fora do texto devolve vazio, como o")
    lines.append("     *  _apkpyListGet. */")
    lines.append("    private String _apkpyCharAt(String text, String index) {")
    lines.append("        String value = text == null ? \"\" : text;")
    lines.append("        int count = value.codePointCount(0, value.length());")
    lines.append("        int i;")
    lines.append("        try { i = Integer.parseInt(String.valueOf(index).trim()); }")
    lines.append("        catch (Exception e) { return \"\"; }")
    lines.append("        if (i < 0) i += count;")
    lines.append("        if (i < 0 || i >= count) {")
    lines.append("            if (ApkpyValues.strict()) throw new ApkpyValues.Raised(\"IndexError\", \"string index out of range\");")
    lines.append("            return \"\";")
    lines.append("        }")
    lines.append("        int at = value.offsetByCodePoints(0, i);")
    lines.append("        return new String(Character.toChars(value.codePointAt(at)));")
    lines.append("    }")
    lines.append("")
    lines.append("    /** d[chave] com a chave num nome. A chave e' uma chave, mesmo com")
    lines.append("     *  um ponto la' dentro; o que falta da' vazio, como o _jsonGet. */")
    lines.append("    private String _apkpyDictGet(String json, String key) {")
    lines.append("        org.json.JSONObject obj;")
    lines.append("        try {")
    lines.append("            obj = new org.json.JSONObject(json == null ? \"{}\" : json);")
    lines.append("        } catch (Exception e) {")
    lines.append("            return \"\";")
    lines.append("        }")
    lines.append("        String k = String.valueOf(key);")
    lines.append("        if (!obj.has(k)) {")
    lines.append("            if (ApkpyValues.strict()) throw new ApkpyValues.Raised(\"KeyError\", _apkpyRepr(k));")
    lines.append("            return \"\";")
    lines.append("        }")
    lines.append("        return _apkpyFromJson(obj.opt(k));")
    lines.append("    }")
    lines.append("")
    lines.append("    /** v[i] quando o codigo nao diz o que v e': item de uma lista JSON,")
    lines.append("     *  valor de um objeto JSON, ou letra de um texto. */")
    lines.append("    private String _apkpyItemAt(String value, String index) {")
    lines.append("        String text = value == null ? \"\" : value;")
    lines.append("        int shape = _apkpyJsonShape(text);")
    lines.append("        // Only the reading of the JSON is caught: the KeyError of a")
    lines.append("        // strict lookup has to get out.")
    lines.append("        boolean list = false, dict = false;")
    lines.append("        try {")
    lines.append("            if (shape == 91) {")
    lines.append("                new org.json.JSONArray(text.trim());")
    lines.append("                list = true;")
    lines.append("            }")
    lines.append("            if (shape == 123) {")
    lines.append("                new org.json.JSONObject(text.trim());")
    lines.append("                dict = true;")
    lines.append("            }")
    lines.append("        } catch (Exception ignored) {}")
    lines.append("        if (list) return _apkpyListGet(text.trim(), index);")
    lines.append("        if (dict) return _apkpyDictGet(text.trim(), index);")
    lines.append("        return _apkpyCharAt(text, index);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** 91 e 123 são o parêntesis reto e a chaveta de abrir, escritos")
    lines.append("     *  como código: uma chaveta solta dentro de uma string faria a")
    lines.append("     *  contagem de chavetas do ficheiro mentir, e é essa contagem que")
    lines.append("     *  os testes usam para saber se o Java gerado fecha. */")
    lines.append("    private int _apkpyJsonShape(String text) {")
    lines.append("        String peek = text == null ? \"\" : text.trim();")
    lines.append("        if (peek.isEmpty()) return 0;")
    lines.append("        char first = peek.charAt(0);")
    lines.append("        if (first == (char) 91) return 91;")
    lines.append("        if (first == (char) 123) return 123;")
    lines.append("        return 0;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** Texto que o gerador SABE ser JSON volta a ser estrutura, não")
    lines.append("     *  uma string entre aspas. Só chega aqui um nome que foi visto a")
    lines.append("     *  receber um literal — nunca texto que o utilizador escreveu. */")
    lines.append("    private Object _apkpyJsonVal(String text) {")
    lines.append("        String peek = text == null ? \"\" : text.trim();")
    lines.append("        int shape = _apkpyJsonShape(peek);")
    lines.append("        try {")
    lines.append("            if (shape == 91) return new org.json.JSONArray(peek);")
    lines.append("            if (shape == 123) return new org.json.JSONObject(peek);")
    lines.append("        } catch (Exception ignored) {}")
    lines.append("        return text;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** x in lista -- pertenca a uma lista que a app guarda. Cada elemento")
    lines.append("     *  e comparado pelo seu texto, como tudo no telemovel. */")
    lines.append("    private boolean _apkpyListHas(String json, String needle) {")
    lines.append("        String want = needle == null ? \"\" : needle;")
    lines.append("        try {")
    lines.append("            org.json.JSONArray arr = new org.json.JSONArray(json == null ? \"[]\" : json);")
    lines.append("            for (int i = 0; i < arr.length(); i++) {")
    lines.append("                if (want.equals(String.valueOf(arr.get(i)))) return true;")
    lines.append("            }")
    lines.append("        } catch (Exception ignored) {}")
    lines.append("        return false;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** chave in dicionario: pergunta as chaves. Procurar no texto do JSON")
    lines.append("     *  encontrava tambem os valores, e pedacos de chaves. */")
    lines.append("    private boolean _apkpyHasKey(String json, String key) {")
    lines.append("        try {")
    lines.append("            return new org.json.JSONObject(json == null ? \"{}\" : json).has(String.valueOf(key));")
    lines.append("        } catch (Exception e) {")
    lines.append("            return false;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /** lista.count(x): itens iguais a x, comparados pelo texto. Contar no")
    lines.append("     *  texto do JSON contava letras. */")
    lines.append("    private String _apkpyListCount(String json, String needle) {")
    lines.append("        String want = needle == null ? \"\" : needle;")
    lines.append("        int n = 0;")
    lines.append("        try {")
    lines.append("            org.json.JSONArray arr = new org.json.JSONArray(json == null ? \"[]\" : json);")
    lines.append("            for (int i = 0; i < arr.length(); i++) {")
    lines.append("                if (want.equals(String.valueOf(arr.opt(i)))) n++;")
    lines.append("            }")
    lines.append("        } catch (Exception ignored) {}")
    lines.append("        return String.valueOf(n);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a or b / a and b: o primeiro valor passa por aqui, lido logo a")
    lines.append("     *  seguir a ser escrito, para nao ser calculado duas vezes. */")
    lines.append("    private String _apkpyOrT;")
    lines.append("")
    lines.append("    /** if x: como o Python. None, False e o texto vazio sao falsos; o")
    lines.append("     *  texto \"False\" que alguem escreveu nao e' o False da app. */")
    lines.append("    private boolean _apkpyTruthy(Object v) {")
    lines.append("        if (v == null || v == ApkpyValues.NONE || v == ApkpyValues.FALSE) return false;")
    lines.append("        if (v == ApkpyValues.ZERO || v == ApkpyValues.ZERO_FLOAT) return false;")
    lines.append("        if (v instanceof Boolean) return (Boolean) v;")
    lines.append("        if (v instanceof Number) return ((Number) v).doubleValue() != 0;")
    lines.append("        if (v == org.json.JSONObject.NULL) return false;")
    lines.append("        if (v instanceof org.json.JSONArray) return ((org.json.JSONArray) v).length() > 0;")
    lines.append("        if (v instanceof org.json.JSONObject) return ((org.json.JSONObject) v).length() > 0;")
    lines.append("        return !String.valueOf(v).isEmpty();")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyBool(boolean b) {")
    lines.append("        return b ? ApkpyValues.TRUE : ApkpyValues.FALSE;")
    lines.append("    }")
    lines.append("")
    lines.append("    private boolean _apkpyIsNone(Object v) {")
    lines.append("        return v == null || v == ApkpyValues.NONE;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** Um valor lido de JSON, como o Python o veria: true e false sao True e")
    lines.append("     *  False, null e' None. Liam-se \"true\", \"false\" e \"null\", e todos eram")
    lines.append("     *  verdadeiros num if. */")
    lines.append("    private String _apkpyFromJson(Object v) {")
    lines.append("        if (v == null || v == org.json.JSONObject.NULL) return ApkpyValues.NONE;")
    lines.append("        if (v instanceof Boolean) return ((Boolean) v) ? ApkpyValues.TRUE : ApkpyValues.FALSE;")
    lines.append("        if (v instanceof Number && ((Number) v).doubleValue() == 0 && !String.valueOf(v).startsWith(\"-\")) {")
    lines.append("            // d.get(\"cake\") or \"out\": a 0 from JSON is false, as in Python.")
    lines.append("            return (v instanceof Double || v instanceof Float) ? ApkpyValues.ZERO_FLOAT : ApkpyValues.ZERO;")
    lines.append("        }")
    lines.append("        return String.valueOf(v);")
    lines.append("    }")
    lines.append("")
    lines.append("    /** E de volta: o True, o False e o None da app saem como JSON a serio. */")
    lines.append("    private Object _apkpyJsonOut(String v) {")
    lines.append("        if (v == ApkpyValues.TRUE) return Boolean.TRUE;")
    lines.append("        if (v == ApkpyValues.FALSE) return Boolean.FALSE;")
    lines.append("        if (v == ApkpyValues.NONE) return org.json.JSONObject.NULL;")
    lines.append("        if (v == ApkpyValues.ZERO) return Long.valueOf(0);")
    lines.append("        if (v == ApkpyValues.ZERO_FLOAT) return Double.valueOf(0);")
    lines.append("        return v;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** d[k] = v e lista[i] = v: o mesmo JSON com o item trocado. Uma lista")
    lines.append("     *  ou um dicionario sao texto aqui, por isso o nome recebe o texto novo.")
    lines.append("     *  aug (d[k] += 1): o que era numero continua numero. */")
    lines.append("    private String _apkpySetItem(String json, String key, Object value, int kind, boolean aug) {")
    lines.append("        if (value instanceof String) value = _apkpyJsonOut((String) value);")
    lines.append("        String text = json == null ? \"\" : json.trim();")
    lines.append("        int shape = kind == 1 ? 91 : kind == 2 ? 123 : _apkpyJsonShape(text);")
    lines.append("        try {")
    lines.append("            if (shape == 91) {")
    lines.append("                org.json.JSONArray arr = new org.json.JSONArray(text.isEmpty() ? \"[]\" : text);")
    lines.append("                int i = _apkpyListIndex(arr.length(), key, \"list assignment index out of range\");")
    lines.append("                arr.put(i, aug ? _apkpyKeepNumber(arr.opt(i), value) : value);")
    lines.append("                return arr.toString();")
    lines.append("            }")
    lines.append("            if (shape == 123) {")
    lines.append("                org.json.JSONObject obj = new org.json.JSONObject(text.isEmpty() ? \"{}\" : text);")
    lines.append("                if (aug && !obj.has(key)) throw new ApkpyValues.Raised(\"KeyError\", _apkpyRepr(String.valueOf(key)));")
    lines.append("                obj.put(key, aug ? _apkpyKeepNumber(obj.opt(key), value) : value);")
    lines.append("                return obj.toString();")
    lines.append("            }")
    lines.append("        } catch (org.json.JSONException e) {")
    lines.append("            throw new IllegalArgumentException(e.getMessage());")
    lines.append("        }")
    lines.append("        throw new ApkpyValues.Raised(\"TypeError\", \"'str' object does not support item assignment\");")
    lines.append("    }")
    lines.append("")
    lines.append("    /** del d[k] e del lista[i]: o que falta para, como o KeyError e o")
    lines.append("     *  IndexError do Python. */")
    lines.append("    private String _apkpyDelItem(String json, String key, int kind) {")
    lines.append("        String text = json == null ? \"\" : json.trim();")
    lines.append("        int shape = kind == 1 ? 91 : kind == 2 ? 123 : _apkpyJsonShape(text);")
    lines.append("        try {")
    lines.append("            if (shape == 91) {")
    lines.append("                org.json.JSONArray arr = new org.json.JSONArray(text.isEmpty() ? \"[]\" : text);")
    lines.append("                arr.remove(_apkpyListIndex(arr.length(), key, \"list assignment index out of range\"));")
    lines.append("                return arr.toString();")
    lines.append("            }")
    lines.append("            if (shape == 123) {")
    lines.append("                org.json.JSONObject obj = new org.json.JSONObject(text.isEmpty() ? \"{}\" : text);")
    lines.append("                if (!obj.has(key)) throw new ApkpyValues.Raised(\"KeyError\", _apkpyRepr(String.valueOf(key)));")
    lines.append("                obj.remove(key);")
    lines.append("                return obj.toString();")
    lines.append("            }")
    lines.append("        } catch (org.json.JSONException e) {")
    lines.append("            throw new IllegalArgumentException(e.getMessage());")
    lines.append("        }")
    lines.append("        throw new ApkpyValues.Raised(\"TypeError\", \"'str' object doesn't support item deletion\");")
    lines.append("    }")
    lines.append("")
    lines.append("    /** Uma posicao de lista como o Python a le: negativa conta do fim, e")
    lines.append("     *  fora da lista para (IndexError) em vez de crescer ou ficar vazia. */")
    lines.append("    private int _apkpyListIndex(int size, String raw, String message) {")
    lines.append("        int i;")
    lines.append("        try { i = Integer.parseInt(String.valueOf(raw).trim()); }")
    lines.append("        catch (Exception e) { throw new ApkpyValues.Raised(\"TypeError\", \"list indices must be integers\"); }")
    lines.append("        if (i < 0) i += size;")
    lines.append("        if (i < 0 || i >= size) throw new ApkpyValues.Raised(\"IndexError\", message);")
    lines.append("        return i;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** d[k] += 1 deixa um numero numero. O resultado chega como texto. */")
    lines.append("    private Object _apkpyKeepNumber(Object old, Object value) {")
    lines.append("        if (!(old instanceof Number) || value instanceof Number) return value;")
    lines.append("        String t = String.valueOf(value).trim();")
    lines.append("        try {")
    lines.append("            if (_apkpyIsWhole(t)) return Long.parseLong(t);")
    lines.append("            return Double.parseDouble(t);")
    lines.append("        } catch (Exception e) {")
    lines.append("            return value;")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /** a, b = valor: os itens, se forem tantos como os nomes. O Python")
    lines.append("     *  para com ValueError quando nao sao; deixar um de fora, ou um")
    lines.append("     *  nome vazio, seria responder outra coisa. */")
    lines.append("    private String _apkpyUnpack(org.json.JSONArray items, int before, int after, boolean star) {")
    lines.append("        int n = items.length();")
    lines.append("        if (star ? n < before + after : n != before) {")
    lines.append("            if (!star && n > before) {")
    lines.append("                throw new ApkpyValues.Raised(\"ValueError\", \"too many values to unpack (expected \" + before + \")\");")
    lines.append("            }")
    lines.append("            throw new ApkpyValues.Raised(\"ValueError\", \"not enough values to unpack (expected \"")
    lines.append("                    + (star ? \"at least \" : \"\") + (before + after) + \", got \" + n + \")\");")
    lines.append("        }")
    lines.append("        return items.toString();")
    lines.append("    }")
    lines.append("")
    lines.append("    /** lista + lista: uma lista so'. Colar os dois JSON dava")
    lines.append("     *  '[\"a\"][\"b\"]'. Somar uma lista a outra coisa para, como no Python. */")
    lines.append("    private String _apkpyListConcat(String left, String right) {")
    lines.append("        org.json.JSONArray out = new org.json.JSONArray();")
    lines.append("        for (String side : new String[] {left, right}) {")
    lines.append("            org.json.JSONArray arr;")
    lines.append("            try {")
    lines.append("                arr = new org.json.JSONArray(side == null ? \"\" : side.trim());")
    lines.append("            } catch (Exception e) {")
    lines.append("                throw new ApkpyValues.Raised(\"TypeError\", \"can only concatenate list to list\");")
    lines.append("            }")
    lines.append("            for (int i = 0; i < arr.length(); i++) out.put(arr.opt(i));")
    lines.append("        }")
    lines.append("        return out.toString();")
    lines.append("    }")
    lines.append("")
    lines.append("    /** texto.split(sep, maxsplit) com as regras do Python: o separador")
    lines.append("     *  e texto e nao regex, as partes vazias ficam, e sem separador")
    lines.append("     *  corta em espacos seguidos e ignora as pontas. Devolve JSON. */")
    lines.append("    private String _apkpySplit(String text, String sep, String maxsplit) {")
    lines.append("        String s = text == null ? \"\" : text;")
    lines.append("        int max = -1;")
    lines.append("        try { max = (int) Double.parseDouble(String.valueOf(maxsplit).trim()); } catch (Exception ignored) {}")
    lines.append("        org.json.JSONArray out = new org.json.JSONArray();")
    lines.append("        int n = s.length();")
    lines.append("        if (sep == null) {")
    lines.append("            int i = 0;")
    lines.append("            int left = max < 0 ? Integer.MAX_VALUE : max;")
    lines.append("            while (left-- > 0) {")
    lines.append("                while (i < n && _apkpyIsSpace(s.charAt(i))) i++;")
    lines.append("                if (i == n) break;")
    lines.append("                int j = i;")
    lines.append("                while (i < n && !_apkpyIsSpace(s.charAt(i))) i++;")
    lines.append("                out.put(s.substring(j, i));")
    lines.append("            }")
    lines.append("            while (i < n && _apkpyIsSpace(s.charAt(i))) i++;")
    lines.append("            if (i < n) out.put(s.substring(i));")
    lines.append("            return out.toString();")
    lines.append("        }")
    lines.append("        if (sep.isEmpty()) throw new ApkpyValues.Raised(\"ValueError\", \"empty separator\");")
    lines.append("        int from = 0;")
    lines.append("        while (max < 0 || out.length() < max) {")
    lines.append("            int at = s.indexOf(sep, from);")
    lines.append("            if (at < 0) break;")
    lines.append("            out.put(s.substring(from, at));")
    lines.append("            from = at + sep.length();")
    lines.append("        }")
    lines.append("        out.put(s.substring(from));")
    lines.append("        return out.toString();")
    lines.append("    }")
    lines.append("")
    lines.append("    /** str.isspace do Python. O isWhitespace do Java deixa de fora o")
    lines.append("     *  espaco que nao parte linhas e o NEL (133), que o Python conta. */")
    lines.append("    private boolean _apkpyIsSpace(char c) {")
    lines.append("        return Character.isWhitespace(c) || Character.isSpaceChar(c) || c == (char) 133;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** timeout= em segundos -> ms, com tecto e sem rebentar num valor mau. */")
    lines.append("    private int _apkpyTimeoutMs(String seconds, int fallback) {")
    lines.append("        try {")
    lines.append("            double secs = Double.parseDouble(String.valueOf(seconds).trim());")
    lines.append("            if (secs > 0d) return (int) Math.min(secs * 1000d, %dd);"
                 % _HTTPS_MAX_TIMEOUT_MS)
    lines.append("        } catch (Exception ignored) {}")
    lines.append("        return fallback;")
    lines.append("    }")
    lines.append("")
    lines.append("    /** Um corpo que abre em chaveta ou em parêntesis reto é JSON, e")
    lines.append("     *  dizê-lo evita uma classe inteira de 400s. Só quando quem chamou")
    lines.append("     *  não escolheu o header ele próprio. */")
    lines.append("    private void _apkpyTagJsonBody(java.net.HttpURLConnection conn, String data) {")
    lines.append("        if (data == null || conn.getRequestProperty(\"Content-Type\") != null) return;")
    lines.append("        if (_apkpyJsonShape(data) != 0) {")
    lines.append("            conn.setRequestProperty(\"Content-Type\", \"application/json; charset=utf-8\");")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    lines.append("    /** Lê o corpo inteiro em UTF-8. O readLine() que aqui estava colava")
    lines.append("     *  as linhas sem separador e decodificava no charset da plataforma. */")
    lines.append("    private String _apkpyReadBody(java.io.InputStream is) throws java.io.IOException {")
    lines.append("        if (is == null) return \"\";")
    lines.append("        java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();")
    lines.append("        byte[] chunk = new byte[8192];")
    lines.append("        int read;")
    lines.append("        while ((read = is.read(chunk)) != -1) buffer.write(chunk, 0, read);")
    lines.append("        is.close();")
    lines.append("        return buffer.toString(\"UTF-8\");")
    lines.append("    }")


def _emit_crypto_helpers(lines, ctx=""):
    """Acrescenta os helpers Java do módulo `crypto` e do storage encriptado.

    `hash_password` usa PBKDF2-HMAC (loop manual sobre javax.crypto.Mac —
    compatível com minSdk 24 e bit-a-bit idêntico ao hashlib.pbkdf2_hmac do
    Python, por isso o formato "pbkdf2-algo$iter$salt$hash" é portável entre
    Previewer e Android). O verify aceita também o formato legacy
    "algo$salt$hash" (1× SHA). Injetados incondicionalmente, tal como o
    _jsonGet.

    *ctx* é o prefixo para chegar ao Context — "" numa Activity,
    "getApplicationContext()." num Worker.
    """
    lines.append("")
    lines.append("    private String _apkpyHashPassword(String pw, String algo, int iter) {")
    lines.append("        try {")
    lines.append("            byte[] salt = new byte[16];")
    lines.append("            new java.security.SecureRandom().nextBytes(salt);")
    lines.append("            return \"pbkdf2-\" + algo + \"$\" + iter + \"$\" + _apkpyHex(salt) + \"$\" + _apkpyHex(_apkpyPbkdf2(pw, salt, iter, algo));")
    lines.append("        } catch (Exception e) { return \"\"; }")
    lines.append("    }")
    lines.append("")
    lines.append("    private boolean _apkpyVerifyPassword(String pw, String stored) {")
    lines.append("        try {")
    lines.append("            String[] p = stored.split(\"\\\\$\");")
    lines.append("            String actual;")
    lines.append("            String expected;")
    lines.append("            if (p.length == 4 && p[0].startsWith(\"pbkdf2-\")) {")
    lines.append("                String algo = \"pbkdf2-sha512\".equals(p[0]) ? \"sha512\" : \"sha256\";")
    lines.append("                actual = _apkpyHex(_apkpyPbkdf2(pw, _apkpyUnhex(p[2]), Integer.parseInt(p[1]), algo));")
    lines.append("                expected = p[3];")
    lines.append("            } else if (p.length == 3) {")
    lines.append("                actual = _apkpyDigest(pw, _apkpyUnhex(p[1]), p[0]);  // formato legacy")
    lines.append("                expected = p[2];")
    lines.append("            } else { return false; }")
    lines.append("            if (actual.isEmpty() || actual.length() != expected.length()) return false;")
    lines.append("            int diff = 0;  // comparação em tempo constante")
    lines.append("            for (int i = 0; i < actual.length(); i++) diff |= actual.charAt(i) ^ expected.charAt(i);")
    lines.append("            return diff == 0;")
    lines.append("        } catch (Exception e) { return false; }")
    lines.append("    }")
    lines.append("")
    lines.append("    private byte[] _apkpyPbkdf2(String pw, byte[] salt, int iter, String algo) throws Exception {")
    lines.append("        // PBKDF2 (RFC 2898) com 1 bloco de output (= tamanho do HMAC).")
    lines.append("        // Implementado à mão porque PBKDF2WithHmacSHA256 só existe em API 26+.")
    lines.append("        String macAlgo = \"sha512\".equals(algo) ? \"HmacSHA512\" : \"HmacSHA256\";")
    lines.append("        javax.crypto.Mac mac = javax.crypto.Mac.getInstance(macAlgo);")
    lines.append("        mac.init(new javax.crypto.spec.SecretKeySpec(pw.getBytes(\"UTF-8\"), macAlgo));")
    lines.append("        byte[] block = new byte[salt.length + 4];")
    lines.append("        System.arraycopy(salt, 0, block, 0, salt.length);")
    lines.append("        block[salt.length + 3] = 1;  // INT(1) big-endian")
    lines.append("        byte[] u = mac.doFinal(block);")
    lines.append("        byte[] t = u.clone();")
    lines.append("        for (int i = 1; i < iter; i++) {")
    lines.append("            u = mac.doFinal(u);")
    lines.append("            for (int j = 0; j < t.length; j++) t[j] ^= u[j];")
    lines.append("        }")
    lines.append("        return t;")
    lines.append("    }")
    lines.append("")
    lines.append("    private void _apkpyStorageSet(String key, String val) {")
    lines.append("        // Encriptação automática at-rest: o ficheiro de SharedPreferences")
    lines.append("        // fica ilegível para quem o roubar (chave no Android Keystore).")
    lines.append(f"        {ctx}getSharedPreferences(\"apkpy_storage\", Context.MODE_PRIVATE)")
    lines.append("            .edit().putString(key, _apkpyEncrypt(val)).apply();")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyStorageGet(String key, String def) {")
    lines.append(f"        String v = {ctx}getSharedPreferences(\"apkpy_storage\", Context.MODE_PRIVATE).getString(key, null);")
    lines.append("        if (v == null) return def;")
    lines.append("        return v.startsWith(\"enc1$\") ? _apkpyDecrypt(v) : v;  // fallback p/ dados antigos")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyDigest(String pw, byte[] salt, String algo) throws Exception {")
    lines.append("        String jn = \"sha512\".equals(algo) ? \"SHA-512\" : \"SHA-256\";")
    lines.append("        java.security.MessageDigest md = java.security.MessageDigest.getInstance(jn);")
    lines.append("        md.update(salt);")
    lines.append("        return _apkpyHex(md.digest(pw.getBytes(\"UTF-8\")));")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyHex(byte[] b) {")
    lines.append("        StringBuilder sb = new StringBuilder();")
    lines.append("        for (byte x : b) sb.append(String.format(\"%02x\", x));")
    lines.append("        return sb.toString();")
    lines.append("    }")
    lines.append("")
    lines.append("    private byte[] _apkpyUnhex(String s) {")
    lines.append("        int n = s.length() / 2;")
    lines.append("        byte[] b = new byte[n];")
    lines.append("        for (int i = 0; i < n; i++) b[i] = (byte) Integer.parseInt(s.substring(i * 2, i * 2 + 2), 16);")
    lines.append("        return b;")
    lines.append("    }")
    lines.append("")
    lines.append("    private javax.crypto.SecretKey _apkpyGetKey() throws Exception {")
    lines.append("        // Chave AES-256 no Android Keystore: gerada no primeiro uso, fica no")
    lines.append("        // hardware do dispositivo e nunca pode ser extraída (nem com root).")
    lines.append("        java.security.KeyStore ks = java.security.KeyStore.getInstance(\"AndroidKeyStore\");")
    lines.append("        ks.load(null);")
    lines.append("        if (!ks.containsAlias(\"apkpy_device_key\")) {")
    lines.append("            javax.crypto.KeyGenerator kg = javax.crypto.KeyGenerator.getInstance(")
    lines.append("                    android.security.keystore.KeyProperties.KEY_ALGORITHM_AES, \"AndroidKeyStore\");")
    lines.append("            kg.init(new android.security.keystore.KeyGenParameterSpec.Builder(\"apkpy_device_key\",")
    lines.append("                    android.security.keystore.KeyProperties.PURPOSE_ENCRYPT | android.security.keystore.KeyProperties.PURPOSE_DECRYPT)")
    lines.append("                    .setBlockModes(android.security.keystore.KeyProperties.BLOCK_MODE_GCM)")
    lines.append("                    .setEncryptionPaddings(android.security.keystore.KeyProperties.ENCRYPTION_PADDING_NONE)")
    lines.append("                    .setKeySize(256)")
    lines.append("                    .build());")
    lines.append("            kg.generateKey();")
    lines.append("        }")
    lines.append("        return (javax.crypto.SecretKey) ks.getKey(\"apkpy_device_key\", null);")
    lines.append("    }")
    lines.append("")
    # --- SHA-256 e aleatoriedade segura -------------------------------
    lines.append("    // Aleatoriedade a serio: java.util.Random e' previsivel a")
    lines.append("    // partir de duas saidas, e ninguem quer isso num id de sessao.")
    lines.append("    private String _apkpyToken(int count) {")
    lines.append("        try {")
    lines.append("            byte[] b = new byte[Math.max(1, Math.min(64, count))];")
    lines.append("            new java.security.SecureRandom().nextBytes(b);")
    lines.append("            return _apkpyHex(b);")
    lines.append("        } catch (Exception e) { return \"\"; }")
    lines.append("    }")
    lines.append("")
    lines.append("    // SHA-256 de dados. NAO serve para palavras-passe: e' rapido")
    lines.append("    // de proposito, que e' exactamente o que um atacante quer.")
    lines.append("    private String _apkpySha256(String text) {")
    lines.append("        try {")
    lines.append("            return _apkpyHex(java.security.MessageDigest")
    lines.append("                    .getInstance(\"SHA-256\").digest(text.getBytes(\"UTF-8\")));")
    lines.append("        } catch (Exception e) { return \"\"; }")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpySha256File(String path) {")
    lines.append("        java.io.InputStream in = null;")
    lines.append("        try {")
    lines.append("            java.security.MessageDigest d =")
    lines.append("                    java.security.MessageDigest.getInstance(\"SHA-256\");")
    lines.append("            // O picker devolve content://, o resto e' um caminho.")
    lines.append("            in = path.startsWith(\"content://\")")
    lines.append(f"                    ? {ctx}getContentResolver().openInputStream(")
    lines.append("                            android.net.Uri.parse(path))")
    lines.append("                    : new java.io.FileInputStream(path);")
    lines.append("            byte[] buf = new byte[8192];")
    lines.append("            int n;")
    lines.append("            while ((n = in.read(buf)) > 0) d.update(buf, 0, n);")
    lines.append("            return _apkpyHex(d.digest());")
    lines.append("        } catch (Exception e) {")
    lines.append("            return \"\";")
    lines.append("        } finally {")
    lines.append("            try { if (in != null) in.close(); } catch (Exception ig) { }")
    lines.append("        }")
    lines.append("    }")
    lines.append("")
    # --- Cifra com palavra-passe: portavel, ao contrario da do dispositivo --
    # O formato e' pw1$rondas$salt$nonce$caixa, tudo em hex, e a caixa e'
    # AES-256-GCM padrao -- abre-se com openssl ou com qualquer linguagem.
    # A chave sai de PBKDF2 sobre a palavra-passe, que e' a unica coisa que
    # nao viaja com os dados.
    # --- TOTP (RFC 6238): os seis digitos de um autenticador ---------------
    # Tudo local: HMAC-SHA1 sobre o numero de periodos desde 1970. E' por
    # isso que um autenticador funciona num aviao.
    lines.append("    private byte[] _apkpyBase32(String s) {")
    lines.append("        String clean = s.replace(\" \", \"\").replace(\"-\", \"\")")
    lines.append("                .replace(\"=\", \"\").toUpperCase();")
    lines.append("        String alphabet = \"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567\";")
    lines.append("        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();")
    lines.append("        int buffer = 0, bits = 0;")
    lines.append("        for (int i = 0; i < clean.length(); i++) {")
    lines.append("            int v = alphabet.indexOf(clean.charAt(i));")
    lines.append("            if (v < 0) return new byte[0];")
    lines.append("            buffer = (buffer << 5) | v;")
    lines.append("            bits += 5;")
    lines.append("            if (bits >= 8) {")
    lines.append("                out.write((buffer >> (bits - 8)) & 0xFF);")
    lines.append("                bits -= 8;")
    lines.append("            }")
    lines.append("        }")
    lines.append("        return out.toByteArray();")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyTotp(String secret, int digits, int period) {")
    lines.append("        try {")
    lines.append("            byte[] key = _apkpyBase32(secret);")
    lines.append("            if (key.length == 0) return \"\";")
    lines.append("            int d = Math.max(6, Math.min(8, digits));")
    lines.append("            int p = Math.max(1, period);")
    lines.append("            long counter = (System.currentTimeMillis() / 1000L) / p;")
    lines.append("            byte[] msg = new byte[8];")
    lines.append("            for (int i = 7; i >= 0; i--) {")
    lines.append("                msg[i] = (byte) (counter & 0xFF);")
    lines.append("                counter >>= 8;")
    lines.append("            }")
    lines.append("            javax.crypto.Mac mac = javax.crypto.Mac.getInstance(\"HmacSHA1\");")
    lines.append("            mac.init(new javax.crypto.spec.SecretKeySpec(key, \"HmacSHA1\"));")
    lines.append("            byte[] h = mac.doFinal(msg);")
    lines.append("            // Truncagem dinamica: o ultimo nibble diz onde ler.")
    lines.append("            int off = h[h.length - 1] & 0x0F;")
    lines.append("            int code = ((h[off] & 0x7F) << 24) | ((h[off + 1] & 0xFF) << 16)")
    lines.append("                     | ((h[off + 2] & 0xFF) << 8) | (h[off + 3] & 0xFF);")
    lines.append("            int mod = 1;")
    lines.append("            for (int i = 0; i < d; i++) mod *= 10;")
    lines.append("            StringBuilder out = new StringBuilder(String.valueOf(code % mod));")
    lines.append("            while (out.length() < d) out.insert(0, \"0\");")
    lines.append("            return out.toString();")
    lines.append("        } catch (Exception e) { return \"\"; }")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyEncryptPw(String text, String password) {")
    lines.append("        try {")
    lines.append("            byte[] salt = new byte[16];")
    lines.append("            byte[] nonce = new byte[12];")
    lines.append("            java.security.SecureRandom rnd = new java.security.SecureRandom();")
    lines.append("            rnd.nextBytes(salt);")
    lines.append("            rnd.nextBytes(nonce);")
    lines.append("            byte[] key = _apkpyPbkdf2(password, salt, 200000, \"sha256\");")
    lines.append("            javax.crypto.Cipher c =")
    lines.append("                    javax.crypto.Cipher.getInstance(\"AES/GCM/NoPadding\");")
    lines.append("            c.init(javax.crypto.Cipher.ENCRYPT_MODE,")
    lines.append("                   new javax.crypto.spec.SecretKeySpec(key, \"AES\"),")
    lines.append("                   new javax.crypto.spec.GCMParameterSpec(128, nonce));")
    lines.append("            byte[] box = c.doFinal(text.getBytes(\"UTF-8\"));")
    lines.append("            return \"pw1$200000$\" + _apkpyHex(salt) + \"$\"")
    lines.append("                    + _apkpyHex(nonce) + \"$\" + _apkpyHex(box);")
    lines.append("        } catch (Exception e) { return \"\"; }")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyDecryptPw(String stored, String password) {")
    lines.append("        try {")
    lines.append("            String[] p = stored.split(\"\\\\$\");")
    lines.append("            if (p.length != 5 || !\"pw1\".equals(p[0])) return \"\";")
    lines.append("            byte[] key = _apkpyPbkdf2(")
    lines.append("                    password, _apkpyUnhex(p[2]), Integer.parseInt(p[1]), \"sha256\");")
    lines.append("            javax.crypto.Cipher c =")
    lines.append("                    javax.crypto.Cipher.getInstance(\"AES/GCM/NoPadding\");")
    lines.append("            c.init(javax.crypto.Cipher.DECRYPT_MODE,")
    lines.append("                   new javax.crypto.spec.SecretKeySpec(key, \"AES\"),")
    lines.append("                   new javax.crypto.spec.GCMParameterSpec(128, _apkpyUnhex(p[3])));")
    lines.append("            return new String(c.doFinal(_apkpyUnhex(p[4])), \"UTF-8\");")
    lines.append("        // A palavra-passe errada falha a etiqueta do GCM, que e' o objectivo.")
    lines.append("        } catch (Exception e) { return \"\"; }")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyEncrypt(String text) {")
    lines.append("        try {")
    lines.append("            javax.crypto.Cipher c = javax.crypto.Cipher.getInstance(\"AES/GCM/NoPadding\");")
    lines.append("            c.init(javax.crypto.Cipher.ENCRYPT_MODE, _apkpyGetKey());")
    lines.append("            byte[] ct = c.doFinal(text.getBytes(\"UTF-8\"));")
    lines.append("            return \"enc1$\" + _apkpyHex(c.getIV()) + \"$\" + _apkpyHex(ct);")
    lines.append("        } catch (Exception e) { return \"\"; }")
    lines.append("    }")
    lines.append("")
    lines.append("    private String _apkpyDecrypt(String stored) {")
    lines.append("        try {")
    lines.append("            String[] p = stored.split(\"\\\\$\");")
    lines.append("            if (p.length != 3 || !\"enc1\".equals(p[0])) return \"\";")
    lines.append("            javax.crypto.Cipher c = javax.crypto.Cipher.getInstance(\"AES/GCM/NoPadding\");")
    lines.append("            c.init(javax.crypto.Cipher.DECRYPT_MODE, _apkpyGetKey(),")
    lines.append("                   new javax.crypto.spec.GCMParameterSpec(128, _apkpyUnhex(p[1])));")
    lines.append("            return new String(c.doFinal(_apkpyUnhex(p[2])), \"UTF-8\");")
    lines.append("        } catch (Exception e) { return \"\"; }")
    lines.append("    }")


# ApkpyValues' part for Python's errors: raise, except with types, str(e).
_VALUES_ERRORS_JAVA = r'''
    /** An error raised the Python way: raise ValueError("..."), and the
     *  helpers' own (list.remove of a missing item, a bad format spec). */
    public static final class Raised extends RuntimeException {
        public final String type;

        public Raised(String type, String message) {
            super(message);
            this.type = type;
        }

        @Override
        public String toString() {
            String m = getMessage();
            return m == null || m.isEmpty() ? type : type + ": " + m;
        }
    }

    /** Inside a try that catches a missing key or index, d[k] and xs[i]
     *  raise KeyError / IndexError as in Python; anywhere else they give the
     *  empty text they always have. Counted per thread: a job has its own. */
    private static final ThreadLocal<int[]> STRICT = new ThreadLocal<int[]>() {
        @Override
        protected int[] initialValue() {
            return new int[1];
        }
    };

    public static void strict(int step) {
        STRICT.get()[0] += step;
    }

    public static boolean strict() {
        return STRICT.get()[0] > 0;
    }

    private static Throwable unwrap(Throwable t) {
        while (t != null && t.getClass() == RuntimeException.class && t.getCause() != null) {
            t = t.getCause();
        }
        return t;
    }

    /** The Python type of an error. Raised says it; the Java errors that
     *  stand for one are read as it (NumberFormatException is int("x")'s
     *  ValueError). null for one of the VM's own, which no except catches. */
    public static String typeOf(Throwable error) {
        Throwable t = unwrap(error);
        if (t == null) return null;
        if (t instanceof Raised) return ((Raised) t).type;
        if (t instanceof ArithmeticException) {
            String m = String.valueOf(t.getMessage());
            if (m.contains("zero")) return "ZeroDivisionError";
            if (m.contains("overflow") || m.contains("too large")) return "OverflowError";
            return "ArithmeticError";
        }
        if (t instanceof IndexOutOfBoundsException) return "IndexError";
        if (t instanceof IllegalArgumentException) return "ValueError";
        if (t instanceof java.io.FileNotFoundException) return "FileNotFoundError";
        if (t instanceof java.net.SocketTimeoutException) return "TimeoutError";
        if (t instanceof java.io.IOException) return "OSError";
        if (t instanceof org.json.JSONException) return "ValueError";
        if (t instanceof StackOverflowError) return "RecursionError";
        if (t instanceof OutOfMemoryError) return "MemoryError";
        if (t instanceof Error) return null;
        return "Exception";
    }

    private static String parent(String type) {
        switch (type) {
            case "BaseException":
                return null;
            case "Exception":
                return "BaseException";
            case "ZeroDivisionError":
            case "OverflowError":
            case "FloatingPointError":
                return "ArithmeticError";
            case "KeyError":
            case "IndexError":
                return "LookupError";
            case "UnicodeError":
            case "JSONDecodeError":
                return "ValueError";
            case "RecursionError":
            case "NotImplementedError":
                return "RuntimeError";
            case "ModuleNotFoundError":
                return "ImportError";
            case "FileNotFoundError":
            case "PermissionError":
            case "FileExistsError":
            case "TimeoutError":
            case "ConnectionError":
            case "IsADirectoryError":
            case "NotADirectoryError":
                return "OSError";
            default:
                return "Exception";
        }
    }

    /** except A, B: whether the error is one of them, or of their family. */
    public static boolean isA(Throwable error, String... names) {
        for (String type = typeOf(error); type != null; type = parent(type)) {
            for (String name : names) {
                if (name.equals(type)) return true;
            }
        }
        return false;
    }

    /** str(e). A Java error without a message shows its class name rather
     *  than the word null. */
    public static String message(Throwable error) {
        Throwable t = unwrap(error);
        if (t == null) return "";
        String m = t.getMessage();
        if (t instanceof Raised) return m == null ? "" : m;
        return m != null ? m : t.getClass().getSimpleName();
    }

    /** raise on its own: the caught error again, as it was. */
    public static RuntimeException rethrow(Throwable t) {
        if (t instanceof RuntimeException) return (RuntimeException) t;
        if (t instanceof Error) throw (Error) t;
        return new RuntimeException(t);
    }
'''


# ApkpyValues' repr(), int() and float() of a text: Python's answers, and its
# errors -- int("x") is the ValueError a Python person knows, not Java's
# NumberFormatException with "For input string".
_VALUES_NUMBERS_JAVA = r'''
    /** repr() of a text, as Python writes it: single quotes, or double ones
     *  when only single ones are inside, and the escapes. */
    public static String repr(String s) {
        String t = s == null ? "" : s;
        if (isObjectText(t)) return t;
        char quote = t.indexOf('\'') >= 0 && t.indexOf('"') < 0 ? '"' : '\'';
        StringBuilder out = new StringBuilder().append(quote);
        for (int c : t.codePoints().toArray()) {
            if (c == quote || c == '\\') out.append('\\').appendCodePoint(c);
            else if (c == '\n') out.append("\\n");
            else if (c == '\r') out.append("\\r");
            else if (c == '\t') out.append("\\t");
            else if (c < 32 || c == 127) out.append(String.format("\\x%02x", c));
            else {
                int type = Character.getType(c);
                boolean hidden = type == Character.CONTROL || type == Character.FORMAT
                        || type == Character.SURROGATE || type == Character.PRIVATE_USE
                        || type == Character.UNASSIGNED || type == Character.LINE_SEPARATOR
                        || type == Character.PARAGRAPH_SEPARATOR
                        || (type == Character.SPACE_SEPARATOR && c != 32);
                if (!hidden) out.appendCodePoint(c);
                else if (c <= 255) out.append(String.format("\\x%02x", c));
                else if (c <= 65535) out.append(String.format("\\u%04x", c));
                else out.append(String.format("\\U%08x", c));
            }
        }
        return out.append(quote).toString();
    }

    /** int(text) and int(text, base) as Python reads them: the spaces
     *  around, _ between digits, 0x / 0o / 0b with their base (or base 0),
     *  and Python's ValueError for what is not a whole number. */
    public static long toInt(String text, long base) {
        if (text == null || text == NONE) {
            throw new Raised("TypeError", "int() argument must be a string, a bytes-like object or a real number, not 'NoneType'");
        }
        if (text == TRUE) return 1L;
        if (text == FALSE) return 0L;
        String s = text.trim();
        if (base == 10) {
            try {
                return Long.parseLong(s);
            } catch (NumberFormatException notPlain) {
                // _, or not a number: below
            }
        }
        if (base != 0 && (base < 2 || base > 36)) {
            throw new Raised("ValueError", "int() base must be >= 2 and <= 36, or 0");
        }
        int radix = (int) base;
        String sign = "";
        if (s.startsWith("+") || s.startsWith("-")) {
            sign = s.substring(0, 1);
            s = s.substring(1);
        }
        String low = s.toLowerCase(java.util.Locale.ROOT);
        int prefix = low.startsWith("0x") ? 16 : low.startsWith("0o") ? 8 : low.startsWith("0b") ? 2 : 0;
        boolean ok = true;
        if (prefix != 0 && (radix == 0 || radix == prefix)) {
            s = s.substring(2);
            if (s.startsWith("_")) s = s.substring(1);
            radix = prefix;
        } else if (radix == 0) {
            radix = 10;
            // base 0 takes 010 for an error, as Python 3 does: only zeros may start with 0
            ok = !(s.length() > 1 && s.charAt(0) == '0' && !s.replace("_", "").matches("0+"));
        }
        if (s.indexOf('_') >= 0) {
            ok = ok && !s.startsWith("_") && !s.endsWith("_") && !s.contains("__");
            s = s.replace("_", "");
        }
        ok = ok && !s.isEmpty() && s.charAt(0) != '+' && s.charAt(0) != '-';
        if (ok) {
            try {
                return Long.parseLong(sign + s, radix);
            } catch (NumberFormatException e) {
                boolean digits = true;
                for (int i = 0; i < s.length(); i++) {
                    if (Character.digit(s.charAt(i), radix) < 0) digits = false;
                }
                if (digits) throw new Raised("OverflowError", "integer too large");
            }
        }
        String shown = repr(text);
        if (shown.length() > 200) shown = shown.substring(0, 200);
        throw new Raised("ValueError", "invalid literal for int() with base " + base + ": " + shown);
    }

    private static final java.util.regex.Pattern PY_FLOAT = java.util.regex.Pattern.compile(
            "[+-]?([0-9](_?[0-9])*([.]([0-9](_?[0-9])*)?)?|[.][0-9](_?[0-9])*)([eE][+-]?[0-9](_?[0-9])*)?");

    /** float(text) as Python reads it. Java's parseDouble also took 1.5f,
     *  1.5d and 0x1p3, and gave NumberFormatException for the rest. */
    public static double toFloat(String text) {
        if (text == null || text == NONE) {
            throw new Raised("TypeError", "float() argument must be a string or a real number, not 'NoneType'");
        }
        if (text == TRUE) return 1d;
        if (text == FALSE) return 0d;
        String s = text.trim();
        if (PY_FLOAT.matcher(s).matches()) return Double.parseDouble(s.replace("_", ""));
        String low = s.toLowerCase(java.util.Locale.ROOT);
        if (low.matches("[+-]?(inf|infinity)")) {
            return low.startsWith("-") ? Double.NEGATIVE_INFINITY : Double.POSITIVE_INFINITY;
        }
        if (low.matches("[+-]?nan")) return Double.NaN;
        throw new Raised("ValueError", "could not convert string to float: " + repr(text));
    }
'''


# ApkpyValues' print(): Logcat, a line at a time.
_VALUES_TYPES_JAVA = r'''
    /** isinstance() of a value the source does not trace: the type the app
     *  reads it as. True, False and None by what they are, a list or a dict by
     *  its JSON, a whole number or a decimal by its digits, text otherwise. */
    public static String pyType(String v) {
        if (v == TRUE || v == FALSE) return "bool";
        if (v == null || v == NONE) return "NoneType";
        if (isObjectText(v)) return v.substring(10, v.indexOf(" object at 0x"));
        if (v == ZERO) return "int";
        if (v == ZERO_FLOAT) return "float";
        // 91 and 123 are [ and the opening brace: one loose in a string would
        // throw off the brace count the tests check the generated Java by.
        String t = v.trim();
        char first = t.isEmpty() ? ' ' : t.charAt(0);
        if (first == (char) 91) {
            try { new org.json.JSONArray(t); return "list"; } catch (Exception ignored) { }
        }
        if (first == (char) 123) {
            try { new org.json.JSONObject(t); return "dict"; } catch (Exception ignored) { }
        }
        if (v.matches("-?[0-9]+")) return "int";
        if (v.matches("-?[0-9]+[.][0-9]+([eE][-+]?[0-9]+)?") || v.matches("-?[0-9]+[eE][-+]?[0-9]+"))
            return "float";
        return "str";
    }

    /** str(v): the words of True, False, None and a 0 read from JSON, as text
     *  of its own -- not the app's value, which a list or JSON would read back. */
    public static String text(String v) {
        if (v == TRUE || v == FALSE || v == NONE || v == ZERO || v == ZERO_FLOAT) {
            return new String(v);
        }
        return v;
    }

    /** An object of one of the app's classes: the text CPython shows for it,
     *  <__main__.Task object at 0x...>, which is how ApkpyObjects keeps it. */
    public static boolean isObjectText(String v) {
        return v != null && v.startsWith("<__main__.") && v.endsWith(">")
                && v.indexOf(" object at 0x") > 10;
    }

    /** isinstance(v, (a, b)): bool counts as int, as in Python. */
    public static boolean isInstance(String v, String names) {
        String type = pyType(v);
        String all = "," + names + ",";
        return all.contains("," + type + ",") || ("bool".equals(type) && all.contains(",int,"));
    }

    /** True, once the value has been worked out: a call is still made. */
    public static boolean evaluated(Object value) {
        return true;
    }
'''


_VALUES_PRINT_JAVA = r'''
    private static final StringBuilder PRINTED = new StringBuilder();

    /** print(): to Logcat, tag apkpy (adb logcat -s apkpy), a line at a
     *  time. print("a", end="") waits for the rest of its line, as a
     *  terminal does. */
    public static synchronized void print(String text, String end) {
        PRINTED.append(text).append(end);
        int at;
        while ((at = PRINTED.indexOf("\n")) >= 0) {
            android.util.Log.i("apkpy", PRINTED.substring(0, at));
            PRINTED.delete(0, at + 1);
        }
    }
'''


def _values_errors_java():
    """The errors part of ApkpyValues, with the app's own error classes in the
    family tree: except ValueError catches class TooLong(ValueError)."""
    errors = classes_feature.STATE.get('errors') or {}
    if not errors:
        return _VALUES_ERRORS_JAVA
    marker = '            default:\n                return "Exception";'
    assert marker in _VALUES_ERRORS_JAVA
    cases = "".join('            case "%s":\n                return "%s";\n' % (name, parent)
                    for name, parent in sorted(errors.items()))
    return _VALUES_ERRORS_JAVA.replace(marker, cases + marker)


def _generate_values_java(package):
    """None, True and False as the app keeps them: text that reads like
    Python's, and objects of their own, so the words a person typed are not
    mistaken for them."""
    return f'''package {package};

/** None, True and False as values of the app. new String() keeps each one an
 *  object of its own: "False" typed into a field is not ApkpyValues.FALSE.
 *  ZERO is a 0 read from JSON: false in an if, where the "0" a person typed
 *  is true, as in Python. */
public final class ApkpyValues {{
    public static final String NONE = new String("None");
    public static final String TRUE = new String("True");
    public static final String FALSE = new String("False");
    public static final String ZERO = new String("0");
    public static final String ZERO_FLOAT = new String("0.0");
{_values_errors_java()}{_VALUES_NUMBERS_JAVA}{_VALUES_PRINT_JAVA}{_VALUES_TYPES_JAVA}
    private ApkpyValues() {{ }}
}}
'''


def _generate_reactive_state_java(package):
    """Process-wide, thread-safe state store used by generated Activities."""
    return f'''package {package};

import java.util.concurrent.ConcurrentHashMap;

public final class ApkpyReactiveState {{
    private static final ConcurrentHashMap<String, String> VALUES =
            new ConcurrentHashMap<>();

    private ApkpyReactiveState() {{ }}

    public static String get(String key, String fallback) {{
        String safeFallback = fallback == null ? "" : fallback;
        String current = VALUES.putIfAbsent(key, safeFallback);
        return current == null ? safeFallback : current;
    }}

    public static void set(String key, Object value) {{
        VALUES.put(key, value == null ? "" : String.valueOf(value));
    }}

    public static synchronized String increment(
            String key, double amount, String fallback) {{
        double current;
        try {{
            current = Double.parseDouble(get(key, fallback));
        }} catch (Exception ignored) {{
            current = 0.0d;
        }}
        double next = current + amount;
        String rendered = next == Math.rint(next)
                ? String.valueOf((long) next)
                : String.valueOf(next);
        VALUES.put(key, rendered);
        return rendered;
    }}

    public static synchronized String toggle(String key, String fallback) {{
        boolean next = !Boolean.parseBoolean(get(key, fallback));
        String rendered = String.valueOf(next);
        VALUES.put(key, rendered);
        return rendered;
    }}
}}
'''
