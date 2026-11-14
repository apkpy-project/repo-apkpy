"""web_page(): a web page inside the screen, on the phone.

A WebView in the layout. ``html=`` is loaded as a document of the app (its
<style> and <script> run); ``url=`` loads the address, and asks for the
INTERNET permission. ``page.set_value(...)`` goes through ApkpyWeb.show(),
which tells an address from HTML the way the Previewer does
(features/web_page.is_address).
"""

COMPONENT = "web_page"
JAVA_FILE = "java/ApkpyWeb.java"


def parse(transpiler, call, comp):
    comp["id"] = transpiler._kw(call.keywords, "id")
    html = transpiler._kw(call.keywords, "html")
    if html is None and call.args:
        html = transpiler._get_str(call.args[0]) if hasattr(transpiler, "_get_str") else None
    comp["html"] = "" if html is None else str(html)
    url = transpiler._kw(call.keywords, "url")
    comp["url"] = "" if url is None else str(url)
    if comp["url"] and "INTERNET" not in transpiler.declared_permissions:
        transpiler.declared_permissions.append("INTERNET")


def uses(components):
    return any(c.get("comp_type") == COMPONENT or uses(c.get("children", []))
               for c in components)


def layout_xml(indent, number, height, margin_xml, background=None):
    lines = [
        "%s<WebView" % indent,
        '%s    android:id="@+id/web%d"' % (indent, number),
        '%s    android:layout_width="match_parent"' % indent,
        '%s    android:layout_height="%s"%s' % (indent, height, margin_xml),
    ]
    if background:
        lines.append('%s    android:background="%s"' % (indent, background))
    lines[-1] += " />"
    lines.append("")
    return lines


def _java_string(text):
    out = []
    for char in str(text):
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            continue
        elif char == "\t":
            out.append("\\t")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def java_setup(indent, comp, java_var, background=None):
    lines = ["%sandroid.webkit.WebView %s = findViewById(R.id.%s);" % (indent, java_var, java_var),
             "%sApkpyWeb.setup(%s);" % (indent, java_var)]
    if background:
        lines.append("%s%s.setBackgroundColor(android.graphics.Color.parseColor(\"%s\"));"
                     % (indent, java_var, background))
    content = comp.get("url") or comp.get("html") or ""
    if content:
        lines.append("%sApkpyWeb.show(%s, %s);" % (indent, java_var, _java_string(content)))
    return lines


def warm_java():
    """The start screen's line that loads Chromium while the app is idle."""
    return "        ApkpyWeb.warm(this);"


def set_java(java_var, value_java):
    return ("ApkpyWeb.show((android.webkit.WebView) findViewById(R.id.%s), String.valueOf(%s));"
            % (java_var, value_java))


_JAVA = '''package __PACKAGE__;

import android.webkit.WebView;
import android.webkit.WebViewClient;

/** web_page(): HTML of the app, or an address, inside the screen (ApkPy). */
final class ApkpyWeb {
    private ApkpyWeb() {}

    static void setup(WebView view) {
        view.getSettings().setJavaScriptEnabled(true);
        view.getSettings().setDomStorageEnabled(true);
        // Links open in the page, not in another app.
        view.setWebViewClient(new WebViewClient());
        view.setVerticalScrollBarEnabled(false);
    }

    /** The first WebView of a process loads Chromium: 130 ms on the main
     *  thread, paid by whichever screen opens first. Done once the first
     *  screen is up and the app is idle, the page's screen opens without it. */
    static void warm(final android.content.Context context) {
        android.os.Looper.myQueue().addIdleHandler(() -> {
            try { new WebView(context.getApplicationContext()).destroy(); } catch (Throwable ignored) {}
            return false;
        });
    }

    static void show(WebView view, String content) {
        String text = content == null ? "" : content;
        String trimmed = text.trim();
        if (trimmed.regionMatches(true, 0, "http://", 0, 7)
                || trimmed.regionMatches(true, 0, "https://", 0, 8)) {
            view.loadUrl(trimmed);
        } else {
            view.loadDataWithBaseURL("https://appassets.androidplatform.net/", text,
                    "text/html", "utf-8", null);
        }
    }
}
'''


def java_source(package):
    return _JAVA.replace("__PACKAGE__", package)
