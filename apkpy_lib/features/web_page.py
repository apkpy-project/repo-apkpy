"""web_page(): a web page inside the screen.

On the phone it is a WebView (core/features/web_page.py): your HTML, with its
<style> and its JavaScript, or an address. Tk draws no web pages, so the
Previewer draws the HTML a lab or a help page writes -- headings, paragraphs,
lists, bold, italics, code, links, and the colours, sizes and fonts its
<style> gives tags, classes and ids -- on a white page with the browser's 8px
margin. Scripts do not run here; an address shows as a card that opens it in
the computer's browser.

``page.set_value(html_or_address)`` replaces what it shows, on both sides.
"""

import html.parser
import re
import tkinter as tk
import tkinter.font as tkfont

_HEADINGS = {"h1": (2.0, 0.67), "h2": (1.5, 0.83), "h3": (1.17, 1.0),
             "h4": (1.0, 1.33), "h5": (0.83, 1.67), "h6": (0.67, 2.33)}
_BLOCKS = {"p", "div", "section", "article", "header", "footer", "main", "nav",
           "aside", "ul", "ol", "li", "pre", "blockquote", "table", "tr", "form",
           "figure", "figcaption", "hr", "body", "html", "dl", "dt", "dd", "address",
           "h1", "h2", "h3", "h4", "h5", "h6"}
_HIDDEN = {"script", "style", "head", "title", "template", "noscript", "meta", "link"}
_MONO = {"code", "pre", "kbd", "samp", "tt"}
_VOID = {"br", "hr", "img", "input", "meta", "link", "wbr", "source", "area", "col"}
_LINK = "#0000EE"


def web_page(html="", id=None, screen=None, parent=None, url=""):
    """A web page inside the screen: your ``html=`` (with its <style> and
    <script>) or an ``url=``. ``page.set_value(...)`` shows other HTML, or an
    address. Its height is the page's, or the stylesheet's ``height``."""
    from ..ui import ComponentDef
    from .rich_content import _attach
    if html is not None and not isinstance(html, str):
        raise TypeError("web_page(html=...) must be a string")
    return _attach(ComponentDef("web_page", html=str(html or ""), url=str(url or ""),
                                comp_id=id),
                   screen=screen, parent=parent)


def is_address(value):
    return bool(re.match(r"\s*https?://", str(value or ""), re.I))


def _rules(css):
    """``[(specificity, order, selector, {prop: value})]`` for simple selectors."""
    css = re.sub(r"/\*.*?\*/", "", css or "", flags=re.S)
    found = []
    for order, (selectors, body) in enumerate(re.findall(r"([^{}]+)\{([^{}]*)\}", css)):
        props = {}
        for name, value in re.findall(r"([\w-]+)\s*:\s*([^;]+)", body):
            props[name.strip().lower()] = value.strip()
        for selector in selectors.split(","):
            selector = selector.strip()
            if not re.match(r"^(\*|[a-zA-Z][\w-]*|\.[\w-]+|#[\w-]+|[a-zA-Z][\w-]*\.[\w-]+)$", selector):
                continue
            weight = 100 if selector.startswith("#") else 10 if "." in selector else 1
            found.append((weight, order, selector.lower(), props))
    found.sort(key=lambda rule: (rule[0], rule[1]))
    return found


def _matches(selector, tag, attrs):
    if selector in ("*", tag):
        return True
    classes = (attrs.get("class") or "").lower().split()
    if selector.startswith("."):
        return selector[1:] in classes
    if selector.startswith("#"):
        return selector[1:] == (attrs.get("id") or "").lower()
    if "." in selector:
        name, cls = selector.split(".", 1)
        return name == tag and cls in classes
    return False


def _length(value, parent_size):
    raw = str(value or "").strip().lower()
    match = re.match(r"(-?[\d.]+)\s*(px|em|rem|%|pt)?", raw)
    if not match:
        return {"small": parent_size * 0.83, "large": parent_size * 1.2,
                "x-large": 24.0, "xx-large": 32.0, "medium": 16.0}.get(raw)
    number, unit = float(match.group(1)), match.group(2) or "px"
    return {"px": number, "em": number * parent_size, "rem": number * 16.0,
            "%": number * parent_size / 100.0, "pt": number * 4.0 / 3.0}[unit]


class _Page(html.parser.HTMLParser):
    """HTML -> runs of text, each with the look the cascade gives it."""

    def __init__(self, rules):
        super().__init__(convert_charrefs=True)
        self.rules = rules
        self.root = {"color": "#000000", "family": "sans-serif", "size": 16.0,
                     "bold": False, "italic": False, "underline": False,
                     "align": "left", "indent": 0, "margin": 0.0, "pre": False,
                     "background": None}
        self.stack = [("html", self.root, {})]
        self.runs = []          # (text, look)
        self.lists = []         # [kind, count]
        self.hidden = 0
        self.page_background = None
        # A fragment has no <body>, and a browser still gives it one: the
        # body { } rules reach every word, and its background is the page's.
        self.stack = [("body", self._look("body", {}), {})]

    def _look(self, tag, attrs):
        parent = self.stack[-1][1]
        look = dict(parent)
        look["margin"] = 0.0
        look["background"] = None
        if tag in _HEADINGS:
            scale, margin = _HEADINGS[tag]
            look["size"] = parent["size"] * scale
            look["bold"] = True
            look["margin"] = look["size"] * margin * 0.5
        elif tag == "p":
            look["margin"] = look["size"]
        elif tag in ("strong", "b", "th"):
            look["bold"] = True
        elif tag in ("em", "i", "cite", "var"):
            look["italic"] = True
        elif tag in ("u", "ins"):
            look["underline"] = True
        elif tag == "a":
            look["color"] = _LINK
            look["underline"] = True
        elif tag in _MONO:
            look["family"] = "monospace"
            look["size"] = parent["size"] * 0.8125
            look["pre"] = look["pre"] or tag == "pre"
        elif tag == "small":
            look["size"] = parent["size"] * 0.83
        elif tag in ("ul", "ol"):
            look["indent"] = parent["indent"] + 40
            look["margin"] = look["size"] if not self.lists else 0.0
        elif tag == "blockquote":
            look["indent"] = parent["indent"] + 40
            look["margin"] = look["size"]
        elif tag == "center":
            look["align"] = "center"
        declared = {}
        for _weight, _order, selector, props in self.rules:
            if _matches(selector, tag, attrs):
                declared.update(props)
        for name, value in re.findall(r"([\w-]+)\s*:\s*([^;]+)", attrs.get("style") or ""):
            declared[name.strip().lower()] = value.strip()
        for name, value in declared.items():
            value = re.sub(r"\s*!important\s*$", "", value)
            if name == "color":
                look["color"] = value
            elif name == "font-family":
                look["family"] = value.split(",")[0].strip().strip("'\"").lower()
            elif name == "font-size":
                size = _length(value, parent["size"])
                if size:
                    look["size"] = size
            elif name == "font-weight":
                look["bold"] = value in ("bold", "bolder") or (value.isdigit() and int(value) >= 600)
            elif name == "font-style":
                look["italic"] = value == "italic"
            elif name == "text-decoration":
                look["underline"] = "underline" in value
            elif name == "text-align":
                look["align"] = value if value in ("left", "center", "right") else "left"
            elif name in ("background", "background-color"):
                look["background"] = value.split()[0]
        if tag in ("body", "html") and look["background"]:
            self.page_background = look["background"]
            look["background"] = None
        return look

    def handle_starttag(self, tag, attrs):
        attrs = {name: (value or "") for name, value in attrs}
        if tag in _HIDDEN:
            self.hidden += tag not in ("meta", "link")
            return
        if tag == "br":
            self.runs.append(("\n", self.stack[-1][1]))
            return
        look = self._look(tag, attrs)
        if tag in _BLOCKS:
            self._break(look)
        if tag in ("ul", "ol"):
            self.lists.append([tag, 0])
        if tag == "li" and self.lists:
            kind = self.lists[-1]
            kind[1] += 1
            marker = "•  " if kind[0] == "ul" else "%d. " % kind[1]
            self.runs.append((marker, dict(look, bold=False, underline=False)))
        if tag == "hr":
            self.runs.append(("─" * 24 + "\n", dict(look, color="#888888")))
        if tag not in _VOID:
            self.stack.append((tag, look, attrs))

    def handle_endtag(self, tag):
        if tag in _HIDDEN:
            self.hidden = max(0, self.hidden - (tag not in ("meta", "link")))
            return
        if tag in _VOID:
            return
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index][0] == tag:
                look = self.stack[index][1]
                del self.stack[index:]
                if tag in ("ul", "ol") and self.lists:
                    self.lists.pop()
                if tag in _BLOCKS:
                    self._break(look, closing=True)
                return

    def _last(self):
        """The text drawn last, past the spacing markers."""
        return next((text for text, look in reversed(self.runs) if "gap" not in look), "")

    def _break(self, look, closing=False):
        if self._last() and not self._last().endswith("\n"):
            self.runs.append(("\n", look if not closing else self.stack[-1][1]))
        if look.get("margin"):
            self.runs.append(("", dict(look, gap=look["margin"])))

    def handle_data(self, data):
        if self.hidden:
            return
        look = self.stack[-1][1]
        if not look["pre"]:
            data = re.sub(r"\s+", " ", data)
            last = self._last()
            if not data.strip() and (not last or last.endswith(("\n", " "))):
                return
            if not last or last.endswith(("\n", " ")):
                data = data.lstrip()
        if data:
            self.runs.append((data, look))


def parse(markup):
    """``(runs, page_background)`` for a document or a fragment."""
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", markup or "", re.S | re.I))
    page = _Page(_rules(css))
    page.feed(markup or "")
    page.close()
    return page.runs, page.page_background


def _family(name, default):
    if name in ("monospace", "courier", "courier new", "consolas", "menlo", "monaco"):
        return "Consolas"
    if name in ("serif", "times", "times new roman", "georgia"):
        return "Times New Roman"
    return default


def fill(text_widget, markup, default_family, colour_of):
    """Draw ``markup`` into a Tk Text. ``colour_of`` turns a CSS colour into
    one Tk paints (None when it cannot)."""
    runs, background = parse(markup)
    text_widget.configure(state="normal")
    text_widget.delete("1.0", "end")
    for tag in text_widget.tag_names():
        if tag.startswith("web_"):
            text_widget.tag_delete(tag)
    fonts, tags = [], {}
    gap = 0.0
    for chunk, look in runs:
        if "gap" in look:
            gap = max(gap, look["gap"])
            continue
        key = (look["family"], round(look["size"], 1), look["bold"], look["italic"],
               look["underline"], look["color"], look["align"], look["indent"],
               look.get("background"), round(gap))
        name = tags.get(key)
        if name is None:
            name = "web_%d" % len(tags)
            tags[key] = name
            font = tkfont.Font(family=_family(look["family"], default_family),
                               size=-max(6, int(round(look["size"]))),
                               weight="bold" if look["bold"] else "normal",
                               slant="italic" if look["italic"] else "roman",
                               underline=bool(look["underline"]))
            fonts.append(font)
            options = {"font": font, "justify": look["align"],
                       "lmargin1": look["indent"], "lmargin2": look["indent"],
                       "spacing1": int(round(gap))}
            colour = colour_of(look["color"])
            if colour:
                options["foreground"] = colour
            if look.get("background"):
                shade = colour_of(look["background"])
                if shade:
                    options["background"] = shade
            text_widget.tag_configure(name, **options)
        text_widget.insert("end", chunk, (name,))
        if chunk.strip():
            gap = 0.0
    # The last line's newline would leave an empty line at the bottom.
    while text_widget.get("end-2c", "end-1c") == "\n":
        text_widget.delete("end-2c", "end-1c")
    text_widget._apkpy_web_fonts = fonts
    text_widget.configure(state="disabled")
    return background


def render_web_page_preview(app, comp, parent_widget, is_flex, pack_side, bg_color):
    import webbrowser
    from ..ui import _build_tk_font, _merge_with_body, _resolve_css_size_tk, _style_viewport, _tk_color
    from .rich_content import _pack_outer
    from ..ui import _parse_margin

    style = _merge_with_body(comp.kwargs.get("comp_id"), "web_page")
    own = __import__("apkpy_lib.ui", fromlist=["global_styles"]).global_styles.get(
        comp.kwargs.get("comp_id") or "", {}) or {}
    page_bg = _tk_color(own.get("background-color"), "#FFFFFF") or "#FFFFFF"
    holder = tk.Frame(parent_widget, bg=page_bg, bd=0, highlightthickness=0)
    _pack_outer(holder, is_flex=is_flex, pack_side=pack_side, margin=_parse_margin(style))
    fixed = _resolve_css_size_tk(own.get("height"), "height", _style_viewport)
    default_family = _build_tk_font({"font-size": "16px"}, default_size=16)[0]

    def colour_of(value):
        try:
            seen = _tk_color(value, page_bg)
            holder.winfo_rgb(seen)
            return seen
        except Exception:
            return None

    text = tk.Text(holder, wrap="word", width=1, height=1, bd=0, relief="flat",
                   highlightthickness=0, padx=8, pady=8, bg=page_bg, cursor="arrow")
    text.pack(fill="both", expand=True)
    if fixed:
        holder.configure(height=int(fixed))
        holder.pack_propagate(False)

    def show(content):
        content = str(content or "")
        if is_address(content):
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.tag_configure("web_address", foreground=_LINK, underline=True)
            text.insert("end", "A web page\n", ())
            text.insert("end", content.strip(), ("web_address",))
            text.insert("end", "\n(the phone shows it here; click to open it in this computer's browser)")
            text.tag_bind("web_address", "<Button-1>", lambda _e: webbrowser.open(content.strip()))
            text.configure(state="disabled", bg=page_bg)
        else:
            background = fill(text, content, default_family, colour_of)
            shade = colour_of(background) if background else None
            text.configure(bg=shade or page_bg)
            holder.configure(bg=shade or page_bg)
        if not fixed:
            text.after_idle(fit)

    def fit(_event=None):
        try:
            if text.winfo_width() < 40:
                text.after(30, fit)
                return
            pixels = text.count("1.0", "end", "update", "ypixels")
            pixels = pixels[0] if isinstance(pixels, (tuple, list)) else pixels
            wanted = int(pixels or 0) + 16 + 4
            if holder.cget("height") != wanted:
                holder.configure(height=wanted)
                holder.pack_propagate(False)
        except (tk.TclError, TypeError, ValueError):
            pass

    if not fixed:
        text.bind("<Configure>", lambda _e: text.after_idle(fit), add="+")
    show(comp.kwargs.get("url") or comp.kwargs.get("html") or "")
    comp._web_show = show
    comp.widget = text
