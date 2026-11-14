"""Errors with a code, the file and line, why, and how to fix it (ApkPy's style).

Codes: G1xxx the build (declarations, assets, glue), G2xxx translated code,
G3xxx the engine at run time.
"""


class GameError(Exception):
    def __init__(self, code, message, path=None, line=None, cause="", fix=(), received=""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.line = line
        self.cause = cause
        self.fix = [fix] if isinstance(fix, str) else list(fix)
        self.received = received

    def __str__(self):
        where = ""
        if self.path:
            where = "  %s%s" % (self.path, ":%d" % self.line if self.line else "")
        lines = ["APKPY %s%s" % (self.code, where), "  " + self.message]
        if self.received:
            lines.append("  Received: " + self.received)
        if self.cause:
            lines.append("  Why: " + self.cause)
        for fix in self.fix:
            lines.append("  How to fix: " + fix)
        return "\n".join(lines)
