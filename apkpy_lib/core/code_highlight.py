"""Colours for code: one table of patterns for both sides.

A fenced block in ``markdown()`` names its language (```` ```cpp ````) and its
words are coloured as an editor colours them: keywords, types, strings,
numbers, comments, function names; tags and attributes in HTML; properties and
values in CSS. ```` ```cpp numbers ```` puts line numbers in front.

The Previewer tokenizes with these patterns in Python; the phone gets the same
patterns written into its Java (``java_tables``), so a word is the same colour
on both. Each pattern is one alternative of a single regular expression, tried
in the order written: the first that matches at a place wins. Inside a
pattern only non-capturing groups, ``(?:...)``, so that alternative ``n`` is
group ``n`` on both sides.
"""

import re

KINDS = ("keyword", "type", "string", "number", "comment", "function",
         "tag", "attr", "punct")

_NUMBER = r"\b\d+(?:\.\d+)?\b"
_DQ = r'"(?:[^"\\]|\\.)*"'
_SQ = r"'(?:[^'\\]|\\.)*'"
_CALL = r"\b[A-Za-z_]\w*(?=\s*\()"

_TABLE = {
    "python": [
        ("comment", r"#.*"),
        ("string", _DQ + "|" + _SQ),
        ("keyword", r"\b(?:def|class|return|if|elif|else|for|while|in|import|from|as|with"
                    r"|try|except|finally|raise|pass|break|continue|and|or|not|is|lambda"
                    r"|yield|global|nonlocal|async|await|None|True|False)\b"),
        ("type", r"\b(?:int|float|str|bool|list|dict|tuple|set|bytes|object|self)\b"),
        ("number", _NUMBER),
        ("function", _CALL),
    ],
    "js": [
        ("comment", r"//.*|/\*.*?\*/"),
        ("string", _DQ + "|" + _SQ + r"|`(?:[^`\\]|\\.)*`"),
        ("keyword", r"\b(?:const|let|var|function|return|if|else|for|while|do|of|in|new"
                    r"|class|extends|import|export|from|default|async|await|try|catch"
                    r"|finally|throw|typeof|instanceof|switch|case|break|continue|this"
                    r"|null|undefined|true|false)\b"),
        ("type", r"\b(?:document|window|console|Math|JSON|Array|Object|String|Number"
                 r"|Promise|Map|Set)\b"),
        ("number", _NUMBER),
        ("function", _CALL),
    ],
    "c": [
        ("comment", r"//.*|/\*.*?\*/"),
        ("string", _DQ + "|" + _SQ),
        ("keyword", r"#\s*\w+|\b(?:if|else|for|while|do|return|switch|case|break"
                    r"|continue|class|struct|public|private|protected|static|const|new"
                    r"|delete|using|namespace|template|typename|true|false|nullptr|null"
                    r"|this|import|package|void)\b"),
        ("type", r"\b(?:int|float|double|char|bool|boolean|long|short|unsigned|auto"
                 r"|string|String|byte|var|val|fun|std|cout|cin|endl|vector|map)\b"),
        ("number", _NUMBER),
        ("function", _CALL),
    ],
    "html": [
        ("comment", r"<!--.*?-->"),
        ("tag", r"</?[A-Za-z][\w-]*|/?>"),
        ("attr", r"\b[\w-]+(?==)"),
        ("string", r'"[^"]*"|' + r"'[^']*'"),
    ],
    "css": [
        ("comment", r"/\*.*?\*/"),
        ("attr", r"[\w-]+(?=\s*:[^:])"),
        ("number", r"#[0-9A-Fa-f]{3,8}\b|-?\b\d+(?:\.\d+)?(?:px|em|rem|vh|vw|%|s|ms|deg)?"),
        ("string", _DQ + "|" + _SQ),
        ("tag", r"[.#]?[A-Za-z][\w-]*(?=[^{};]*\{)"),
    ],
}

ALIASES = {
    "py": "python", "python3": "python",
    "javascript": "js", "ts": "js", "typescript": "js", "jsx": "js", "json": "js",
    "cpp": "c", "c++": "c", "cc": "c", "h": "c", "java": "c", "kotlin": "c",
    "kt": "c", "cs": "c", "csharp": "c", "go": "c", "rust": "c", "swift": "c",
    "xml": "html", "htm": "html", "svg": "html",
}

# What each kind looks like on a dark code block and on a light one.
PALETTES = {
    "dark": {"keyword": "#C084FC", "type": "#60A5FA", "string": "#86EFAC",
             "number": "#FDBA74", "comment": "#6B7280", "function": "#67E8F9",
             "tag": "#F472B6", "attr": "#FDE68A", "punct": "#CBD5E1",
             "lineno": "#4B5563"},
    "light": {"keyword": "#7C3AED", "type": "#2563EB", "string": "#15803D",
              "number": "#C2410C", "comment": "#6B7280", "function": "#0E7490",
              "tag": "#BE185D", "attr": "#A16207", "punct": "#475569",
              "lineno": "#9CA3AF"},
}

LANGUAGES = tuple(sorted(_TABLE))
_COMPILED = {}


def language(info):
    """The table a fence's info string names (``cpp numbers`` -> ``c``), or
    None for a language it does not know (the block stays one colour)."""
    words = str(info or "").strip().lower().split()
    if not words:
        return None
    name = ALIASES.get(words[0], words[0])
    return name if name in _TABLE else None


def numbered(info):
    """True when the fence asks for line numbers (```` ```cpp numbers ````)."""
    return "numbers" in str(info or "").strip().lower().split()[1:]


def _pattern(lang):
    if lang not in _COMPILED:
        _COMPILED[lang] = re.compile("|".join("(%s)" % p for _, p in _TABLE[lang]))
    return _COMPILED[lang]


def tokens(line, lang):
    """``[(start, end, kind), ...]`` for one line; [] for an unknown language."""
    if lang not in _TABLE:
        return []
    kinds = [k for k, _ in _TABLE[lang]]
    found = []
    for match in _pattern(lang).finditer(line):
        if match.end() == match.start():
            continue
        group = match.lastindex
        if group:
            found.append((match.start(), match.end(), kinds[group - 1]))
    return found


def palette(text_colour):
    """The dark palette for light text (a dark block), the light one else."""
    value = str(text_colour or "").lstrip("#")
    if len(value) == 8:
        value = value[2:]
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return PALETTES["light"]
    return PALETTES["dark"] if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else PALETTES["light"]


def _java_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def java_tables():
    """The Java the phone tokenizes with: the same alternatives, the kind of
    each group, and the two palettes as ARGB ints."""
    lines = []
    lines.append("    static final String[] CODE_LANGS = {%s};"
                 % ", ".join(_java_string(l) for l in LANGUAGES))
    lines.append("    static final java.util.regex.Pattern[] CODE_PATTERNS = {")
    for lang in LANGUAGES:
        joined = "|".join("(%s)" % p for _, p in _TABLE[lang])
        lines.append("        java.util.regex.Pattern.compile(%s)," % _java_string(joined))
    lines.append("    };")
    lines.append("    static final int[][] CODE_KINDS = {")
    for lang in LANGUAGES:
        lines.append("        {%s}," % ", ".join(str(KINDS.index(k)) for k, _ in _TABLE[lang]))
    lines.append("    };")
    for name in ("dark", "light"):
        colours = [PALETTES[name][k] for k in KINDS] + [PALETTES[name]["lineno"]]
        lines.append("    static final int[] CODE_%s = {%s};" % (
            name.upper(), ", ".join("0xFF%s" % c.lstrip("#").upper() for c in colours)))
    lines.append("    static final java.util.Map<String, String> CODE_ALIASES = new java.util.HashMap<>();")
    lines.append("    static {")
    for alias, target in sorted(ALIASES.items()):
        lines.append("        CODE_ALIASES.put(%s, %s);" % (_java_string(alias), _java_string(target)))
    lines.append("    }")
    return "\n".join(lines)
