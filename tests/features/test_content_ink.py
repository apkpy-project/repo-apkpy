"""The text of markdown, a tree and a list's rows that name no colour.

The phone gave them a dark theme's colours whatever the app: on a light app
without a Theme, markdown was white on white and template rows were dark
cards. The Previewer gave them black text, even on a screen its author made
dark. Both now ask theme.content_ink(): the screen's `color` (inherited, as
CSS does), then the Theme's text, then the ink that reads on what is under
the content.
"""

import base64
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from apkpy_lib import theme  # noqa: E402
from apkpy_lib.core.compiler import translate_python_to_android  # noqa: E402

HEAD = 'from apkpy_lib import *\nhome = Screen(id="home")\n'
CONTENT = ('md = markdown("# Title", id="md", screen=home)\n'
           'tree = tree_view([{"title": "a"}], id="tree", screen=home)\n'
           'rows = virtual_collection([{"t": "a"}], template={"title": "{t}", "subtitle": "s"},'
           ' id="rows", screen=home)\n')


def _colours(source):
    files = translate_python_to_android(source)
    assert "error.txt" not in files, files.get("error.txt")
    found = {}
    for kind, encoded in re.findall(r'apkpy-(rich|tree):([^"]+)',
                                    files["res/layout/activity_screen_home.xml"]):
        data = json.loads(base64.b64decode(encoded))
        found[data["kind"]] = (data["textColor"], data["secondaryColor"])
    adapter = re.search(r'new ApkpyVirtualAdapter\((.*?)\);',
                        files["java/Screen_homeActivity.java"], re.S).group(1)
    found["rows"] = re.findall(r'parseColor\("([^"]+)"\)', adapter)
    return found


def _app(style="", run="run(start_screen=home)\n"):
    return HEAD + CONTENT + (('style = """\n%s\n"""\n' % style) if style else "") + run


class OnThePhone(unittest.TestCase):

    def test_a_light_app_without_a_theme_has_dark_text_and_rows_on_the_screen(self):
        c = _colours(_app())
        self.assertEqual(c["markdown"], ("#212121", "#64748B"))
        self.assertEqual(c["tree_view"], ("#212121", "#64748B"))
        bg, title, subtitle, _meta, badge, _badge_text, border, _accent = c["rows"]
        self.assertEqual((bg, title, subtitle, border), ("#00000000", "#212121", "#64748B", "#E2E8F0"))
        self.assertEqual(badge, "#6750A4")

    def test_a_screen_made_dark_gets_light_text(self):
        c = _colours(_app("home {\n    background-color: #0B0D10;\n}"))
        self.assertEqual(c["markdown"], ("#FAFAFA", "#A1A1AA"))
        self.assertEqual(c["rows"][1:3], ["#FAFAFA", "#A1A1AA"])
        self.assertEqual(c["rows"][6], "#3F3F46")

    def test_the_screens_colour_is_inherited(self):
        c = _colours(_app("home {\n    background-color: #08090B;\n    color: #F7F7F8;\n}"))
        self.assertEqual(c["markdown"][0], "#F7F7F8")
        self.assertEqual(c["rows"][1], "#F7F7F8")

    def test_a_dark_card_on_a_light_screen_gets_light_text(self):
        c = _colours(_app("md {\n    background-color: #17181C;\n}\n"
                          "rows {\n    item-background-color: #17181C;\n}"))
        self.assertEqual(c["markdown"][0], "#FAFAFA")
        self.assertEqual(c["tree_view"][0], "#212121")
        self.assertEqual(c["rows"][:2], ["#17181C", "#FAFAFA"])

    def test_a_colour_of_its_own_still_wins(self):
        c = _colours(_app("md {\n    color: #B00020;\n}\nrows {\n    title-color: #0000FF;\n}"))
        self.assertEqual(c["markdown"][0], "#B00020")
        self.assertEqual(c["rows"][1], "#0000FF")

    def test_a_theme_gives_its_text(self):
        c = _colours(_app(run='run(start_screen=home, theme=Theme(mode="dark", primary="#8B5CF6"))\n'))
        tokens = theme.Theme(mode="dark", primary="#8B5CF6").tokens
        self.assertEqual(c["markdown"][0].upper(), str(tokens["text"]).upper())
        self.assertEqual(c["rows"][1].upper(), str(tokens["text"]).upper())


LABELS = ('from apkpy_lib import *\nhome = Screen(id="home")\n'
          'label("on screen", id="a", screen=home)\n'
          'box = card(screen=home, id="box")\n'
          'label("in card", id="b", screen=home, parent=box)\n%s\nrun(start_screen=home%s)\n')


def _label_colours(style="", run=""):
    files = translate_python_to_android(
        LABELS % (('style = """\n%s\n"""' % style) if style else "", run))
    assert "error.txt" not in files, files.get("error.txt")
    found = []
    for attrs in re.findall(r"<TextView(.*?)/>", files["res/layout/activity_screen_home.xml"], re.S):
        colour = re.search(r'android:textColor="([^"]*)"', attrs)
        found.append(colour.group(1) if colour else None)
    return found


class Labels(unittest.TestCase):
    """A label with no colour was Material's secondary grey (#757575) on the
    phone and #212121 in the Previewer; it takes content_ink on both now."""

    def test_a_light_app(self):
        self.assertEqual(_label_colours(), ["#212121", "#212121"])

    def test_a_dark_card_on_a_light_screen(self):
        self.assertEqual(_label_colours("box {\n    background-color: #17181C;\n}"),
                         ["#212121", "#FAFAFA"])

    def test_the_screens_colour_stops_at_a_white_card(self):
        self.assertEqual(
            _label_colours("home {\n    background-color: #0B0D10;\n    color: #F7F7F8;\n}"),
            ["#F7F7F8", "#212121"])

    def test_a_theme_keeps_its_night_colour(self):
        self.assertEqual(_label_colours(run=', theme=Theme(mode="dark")'),
                         ["@color/apkpy_text", "@color/apkpy_text"])

    def test_a_colour_of_its_own_is_left_to_the_stylesheet(self):
        self.assertEqual(_label_colours("b {\n    color: #B00020;\n}")[1], "#B00020")

    def test_a_themed_app_reads_the_card_and_the_screens_colour(self):
        # body carries the Theme's text; written as every label's own, it put
        # dark text in a dark card and hid the screen's `color:`.
        self.assertEqual(
            _label_colours("box {\n    background-color: #17181C;\n}",
                           run=', theme=Theme(primary="#0F766E")'),
            ["@color/apkpy_text", "#FAFAFA"])
        self.assertEqual(
            _label_colours("home {\n    background-color: #0B0D10;\n    color: #F7F7F8;\n}",
                           run=', theme=Theme(primary="#0F766E")')[0],
            "#F7F7F8")

    def test_the_audit_reads_the_colour_that_is_drawn(self):
        import contextlib
        import io
        from apkpy_lib.core import compiler

        def findings(style, run):
            found = []
            original = compiler._audit_accessibility

            def keep(screens, styles):
                found.extend(original(screens, styles))
                return found
            compiler._audit_accessibility = keep
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    translate_python_to_android(
                        LABELS % ('style = """\n%s\n"""' % style, run))
            finally:
                compiler._audit_accessibility = original
            return found

        themed = ', theme=Theme(primary="#0F766E")'
        self.assertEqual(findings("box {\n    background-color: #17181C;\n}", themed), [])
        self.assertEqual(findings(
            "home {\n    background-color: #0B0D10;\n    color: #F7F7F8;\n}", themed), [])
        # What is unreadable as drawn is still said.
        self.assertEqual(len(findings("b {\n    color: #18181B;\n}\n"
                                      "box {\n    background-color: #17181C;\n}", "")), 1)


BAR = ('from apkpy_lib import *\nhome = Screen(id="home")\napp_bar("Notes", screen=home)\n'
       'label("hi", id="hi", screen=home)\n%s\nrun(start_screen=home%s)\n')


def _bar(style="", run=""):
    files = translate_python_to_android(
        BAR % (('style = """\n%s\n"""' % style) if style else "", run))
    xml = files["res/layout/activity_screen_home.xml"]
    toolbar = re.search(r"<com\.google\.android\.material\.appbar\.MaterialToolbar(.*?)/>",
                        xml, re.S).group(1)
    return (re.search(r'android:background="([^"]+)"', toolbar).group(1),
            re.search(r'app:titleTextColor="([^"]+)"', toolbar).group(1))


class TheTopBar(unittest.TestCase):
    """The Previewer drew the bar on the screen's colour with the dark bar's
    white title; on the phone a light body did the same."""

    def test_dark_without_a_theme_on_both(self):
        self.assertEqual(_bar(), ("#18181B", "#FAFAFA"))
        self.assertEqual(theme.app_bar_colors({}), ("#18181B", "#FAFAFA"))

    def test_a_light_body_or_bar_gets_dark_text(self):
        self.assertEqual(_bar("body {\n    background-color: #FFFFFF;\n}"), ("#FFFFFF", "#212121"))
        self.assertEqual(_bar("app_bar {\n    background-color: #FFE082;\n}"), ("#FFE082", "#212121"))

    def test_a_theme_stays_tied_to_its_colours(self):
        self.assertEqual(_bar(run=', theme=Theme(mode="dark")'),
                         ("@color/apkpy_surface", "@color/apkpy_text"))

    def test_the_bar_runs_under_the_status_bar(self):
        # The root took the status bar's height, so the toolbar never grew
        # under it: a light band of the screen's colour over a dark bar.
        files = translate_python_to_android(BAR % ("", ""))
        root = files["res/layout/activity_screen_home.xml"].split("<androidx", 1)[0]
        self.assertNotIn("fitsSystemWindows", root)
        java = files["java/Screen_homeActivity.java"]
        self.assertIn("setDecorFitsSystemWindows(getWindow(), false)", java)
        self.assertIn("view.setPadding(apkpyEdges.left, 0, apkpyEdges.right, apkpyEdges.bottom)",
                      java)
        # ...and the clock follows the bar's colour, not the screen's.
        self.assertIn("_apkpyLightBehind(findViewById(R.id.apkpy_toolbar))", java)
        self.assertIn("_apkpySystemIconsFollowBackground();", java)

    def test_a_title_size_of_its_own_reaches_the_phone(self):
        java = translate_python_to_android(
            BAR % ('style = """\napp_bar {\n    font-size: 19px;\n}\n"""', "")
        )["java/Screen_homeActivity.java"]
        self.assertIn("setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, 19f)", java)
        self.assertNotIn("COMPLEX_UNIT_SP", translate_python_to_android(
            BAR % ("", ""))["java/Screen_homeActivity.java"].split("apkpyToolbar", 1)[1]
            .split("setNavigationOnClickListener", 1)[0])

    def test_the_previewer_asks_the_same(self):
        from apkpy_lib import ui

        class Bar(object):
            comp_type = "app_bar"
            kwargs = {"comp_id": None}

        class Shown(object):
            app_bar = Bar()

        saved = dict(ui.global_styles)
        try:
            ui.global_styles.clear()
            self.assertEqual(ui.AppPreview._app_bar_palette(None, Shown(), "#FFFFFF"),
                             ("#18181B", "#FAFAFA"))
            ui.global_styles["body"] = {"background-color": "#FFFFFF"}
            self.assertEqual(ui.AppPreview._app_bar_palette(None, Shown(), "#FFFFFF"),
                             ("#FFFFFF", "#212121"))
        finally:
            ui.global_styles.clear()
            ui.global_styles.update(saved)


class ThePreviewersPlainButton(unittest.TestCase):
    """A button with no colour is Material's own on the phone: primary fill,
    white 14sp text, a 36dp fill in 48dp. The Previewer drew it #E0E0E0."""

    def test_primary_white_and_the_phones_size(self):
        import tkinter as tk
        from apkpy_lib import ui
        try:
            app = ui.AppPreview.__new__(ui.AppPreview)
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        root.withdraw()
        drawn = {}

        def keep(self_, text, bg, fg, radius, *a, **kw):
            drawn.update(bg=bg, fg=fg, radius=radius, font=kw.get('font'),
                         inset=kw.get('material_inset'))
            return tk.Canvas(root)

        saved = dict(ui.global_styles)
        original = ui.AppPreview._draw_material_button
        animate, proxy = ui._animate_widget, ui._app
        try:
            ui.global_styles.clear()
            ui.AppPreview._draw_material_button = keep
            # It reads ui._app.root, and the proxy would build a real window.
            ui._animate_widget = lambda *a, **kw: None
            ui._app = type('App', (), {'root': root})()
            app.root = root
            comp = ui.ComponentDef('button', text='Next', comp_id='go')
            ui.AppPreview._render_button(app, comp, root, False, None, '#FFFFFF')
            self.assertEqual((drawn['bg'], drawn['fg'], drawn['radius'], drawn['inset']),
                             ('#6750A4', '#FFFFFF', 4, True))
            self.assertEqual(abs(drawn['font'][1]), 14)
        finally:
            ui.AppPreview._draw_material_button = original
            ui._animate_widget, ui._app = animate, proxy
            ui.global_styles.clear()
            ui.global_styles.update(saved)
            root.destroy()


class TheSameCssOnBothSides(unittest.TestCase):

    def test_markdown_and_tree_take_either_muted_key_on_the_phone(self):
        for key in ("secondary-color", "subtitle-color"):
            c = _colours(_app("md {\n    %s: #123456;\n}\ntree {\n    %s: #654321;\n}" % (key, key)))
            self.assertEqual(c["markdown"][1], "#123456", key)
            self.assertEqual(c["tree_view"][1], "#654321", key)


class PreviewerText(unittest.TestCase):
    """**bold** was 11px beside 14px text: the font helper read the base in
    points and wrote it back as pixels."""

    def test_bold_italic_and_code_keep_the_texts_size(self):
        import tkinter as tk
        import tkinter.font as tkfont
        from apkpy_lib.features.rich_content import _font
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        root.withdraw()
        try:
            for size in (-14, 11):
                base = tkfont.Font(family="Segoe UI", size=size)
                for made in (_font(base, bold=True), _font(base, italic=True),
                             _font(base, family="Consolas")):
                    self.assertEqual(made.cget("size"), size)
                self.assertEqual(_font(base, scale=1.75, least=9, bold=True).cget("size"),
                                 -24 if size < 0 else 19)
        finally:
            root.destroy()


class TheRule(unittest.TestCase):

    def test_what_is_under_the_content_decides_the_ink(self):
        self.assertEqual(theme.content_ink({})["text"], "#212121")
        self.assertEqual(theme.content_ink({}, screen_bg="#0B0D10")["text"], "#FAFAFA")
        self.assertEqual(theme.content_ink({}, own_bg="#17181C", screen_bg="#FFFFFF")["text"],
                         "#FAFAFA")
        # Transparent says nothing: the screen under it decides.
        self.assertEqual(theme.content_ink({}, own_bg="#00000000", screen_bg="#0B0D10")["text"],
                         "#FAFAFA")

    def test_the_screens_colour_then_the_theme_while_they_read(self):
        self.assertEqual(theme.content_ink({"text": "#111111"}, screen_fg="#F7F7F8",
                                           screen_bg="#0B0D10")["text"], "#F7F7F8")
        # Light on light does not read: the Theme's text does.
        self.assertEqual(theme.content_ink({"text": "#111111"}, screen_fg="#F7F7F8")["text"],
                         "#111111")
        # Nor does the Theme's dark text on black: the ink does.
        self.assertEqual(theme.content_ink({"text": "#111111"}, screen_bg="#000000")["text"],
                         "#FAFAFA")
        # A muted grey the author chose stays, short of unreadable.
        self.assertEqual(theme.content_ink({}, screen_fg="#888888")["text"], "#888888")

    def test_the_previewer_asks_the_same(self):
        from apkpy_lib.features import rich_content

        class App(object):
            _screen_ink_style = {"background-color": "#0B0D10"}

        for style in ({}, {"background-color": "#FFFFFF"}, {"background-color": "#17181C"}):
            self.assertEqual(
                rich_content._ink_for(App(), {}, style),
                theme.content_ink({}, own_bg=style.get("background-color"),
                                  screen_bg="#0B0D10"))


if __name__ == "__main__":
    unittest.main()
