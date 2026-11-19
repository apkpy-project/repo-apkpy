# -*- coding: utf-8 -*-
"""What rebuilding a real app's screens (a learning app made with Tauri) found.

Each of these looked right in one place and wrong in the other, or wrong in
both, and each was fixed on 31-10-2026:

* a ring chart with ``width: 92px`` took the whole row on the phone;
* a column with no width in a flex row was measured as wide as the row;
* ``label { padding-left: 0 }`` beat ``badge { padding: 6px 12px }``;
* an empty 32x32 circle was a 32x44 capsule in the Previewer;
* a shaped label (avatar, badge) repainted itself forever in the Previewer;
* a long screen with a gradient took minutes to draw in the Previewer.
"""

import tkinter as tk
import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.theme import component_style

_APP = '''
from apkpy_lib import *
home = Screen(id="home")
row = container(id="row", screen=home)
chart(kind="ring", value=10, max=40, center="10/40", id="ring", parent=row)
side = container(id="side", parent=row)
label("Faltam 30 XP", id="left", parent=side)
chart(kind="ring", value=3, max=4, id="wide", screen=home)
button("Tab", id="key", screen=home)
button("Reply", id="reply", icon="reply", screen=home)
style = """
row { display: flex; flex-direction: row; gap: 16px; }
ring { width: 92px; height: 92px; }
side { flex-grow: 1; }
key { padding: 8px 0px; }
reply { height: 40px; padding: 12px 16px; }
"""
run(start_screen=home)
'''


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = translate_python_to_android(_APP, package="dev.apkpy.check.fix")
        cls.layout = cls.files["res/layout/activity_screen_home.xml"]

    def _chart(self, number):
        start = self.layout.index('android:id="@+id/cht%d"' % number)
        return self.layout[start:start + 200]

    def test_a_chart_is_as_wide_as_its_width(self):
        self.assertIn('android:layout_width="92dp"', self._chart(1))

    def test_a_chart_without_one_fills_the_line(self):
        self.assertIn('android:layout_width="match_parent"', self._chart(2))

    def test_a_button_wears_its_padding(self):
        # On the shape alone, MaterialButton's own 16dp at the sides won.
        start = self.layout.index('android:text="Tab"')
        button = self.layout[self.layout.rfind("<Button", 0, start):start]
        self.assertIn('android:paddingLeft="0dp"', button)
        self.assertIn('android:paddingTop="8dp"', button)

    def test_a_fixed_height_and_a_padding_write_each_side_once(self):
        # 13-11-2026: the replicas app stopped building. A 40px button with a
        # padding had paddingTop twice -- 0dp to centre its text in the height,
        # and the stylesheet's -- and AAPT refuses a repeated attribute.
        start = self.layout.index('android:text="Reply"')
        end = self.layout.index("/>", start)
        button = self.layout[self.layout.rfind("<Button", 0, start):end]
        self.assertEqual(button.count("android:paddingTop="), 1, button)
        self.assertEqual(button.count("android:paddingBottom="), 1, button)
        self.assertIn('android:paddingTop="0dp"', button)
        self.assertIn('android:paddingLeft="16dp"', button)

    def test_every_layout_is_xml_aapt_can_read(self):
        import xml.etree.ElementTree as ET
        for name, text in self.files.items():
            if name.endswith(".xml") and isinstance(text, str):
                ET.fromstring(text)          # a repeated attribute is a ParseError

    def test_a_box_in_a_row_starts_from_its_content(self):
        java = self.files["java/ApkpyLayout.java"]
        self.assertIn("boolean flexRow", java)
        self.assertIn("((ApkpyLayout) child).shrinkToFit = true;", java)
        # Set before the child is measured, or it has no effect.
        self.assertLess(java.index("((ApkpyLayout) child).shrinkToFit = true;"),
                        java.index("measureView(child,\n"))

    def test_a_label_width_in_the_tag_is_its_width(self):
        java = self.files["java/ApkpyLayout.java"]
        self.assertIn('dim(item.css.get("width"), innerW, -1)', java)

    def test_a_grid_measures_a_cell_at_its_own_width(self):
        java = self.files["java/ApkpyLayout.java"]
        grid = java[java.index("private int layoutGrid"):]
        grid = grid[:grid.index("placeMeasured")]
        self.assertIn("measureView(item.view, MeasureSpec.makeMeasureSpec(Math.max(1, cellW", grid)

    def test_a_child_is_not_measured_again_for_the_same_answer(self):
        # Three measures a child, three for each of its children: a label four
        # boxes deep was measured 81 times before the first frame (06-11).
        java = self.files["java/ApkpyLayout.java"]
        body = java[java.index("private void measureView"):]
        body = body[:body.index("private static boolean same")]
        self.assertIn("view.measure(widthSpec, heightSpec);", body)
        self.assertIn("!(view instanceof android.widget.TextView)", body)
        self.assertIn("specs.clear();", java)
        layout = java[java.index("@Override protected void onMeasure"):java.index("@Override protected void onLayout")]
        # Every child measure of a pass goes through the memo.
        self.assertEqual(layout.count(".measure("), 0)
        self.assertGreaterEqual(layout.count("measureView("), 6)

    def test_a_tag_is_read_once(self):
        java = self.files["java/ApkpyLayout.java"]
        self.assertIn("PARSED.get(text)", java)
        self.assertNotIn('replaceAll("[^0-9.+-]"', java)


class TheDialogButtons(unittest.TestCase):
    """confirm()/alert() wrote "OK" and "Cancel" in English into every app."""

    _SOURCE = """
from apkpy_lib import *
home = Screen(id="home")
def done(yes):
    pass
def ask():
    confirm("Sair?", "Perdes o progresso.", on_result=done%s)
def tell():
    alert("Pronto", "Guardado."%s)
button("Sair", id="out", screen=home, command=ask)
button("Info", id="info", screen=home, command=tell)
run(start_screen=home)
"""

    def _java(self, confirm_extra="", alert_extra=""):
        files = translate_python_to_android(self._SOURCE % (confirm_extra, alert_extra),
                                            package="dev.apkpy.check.dlg")
        return next(v for k, v in files.items() if k.endswith("MainActivity.java")
                    or k.endswith("Screen_homeActivity.java") or "home" in k.lower()
                    and k.endswith(".java") and "_confirmDialog" in v)

    def test_without_texts_the_buttons_are_the_system_s(self):
        java = self._java()
        self.assertIn("getString(android.R.string.ok)", java)
        self.assertIn("getString(android.R.string.cancel)", java)
        self.assertNotIn('"Cancel"', java)

    def test_ok_and_cancel_are_the_button_texts(self):
        java = self._java(', ok="Sair", cancel="Ficar"', ', ok="Entendi"')
        self.assertIn('"Sair"', java)
        self.assertIn('"Ficar"', java)
        self.assertIn('"Entendi"', java)

    def test_the_previewer_uses_them(self):
        from apkpy_lib import ui
        asked = []
        original = ui._make_dialog
        ui._make_dialog = lambda title, message, buttons: asked.append(buttons) or True
        try:
            ui.confirm("Sair?", "x", ok="Sair", cancel="Ficar")
            ui.confirm("Sair?", "x")
            ui.alert("Pronto", "x", ok="Entendi")
        finally:
            ui._make_dialog = original
        self.assertEqual([b[0] for b in asked[0]], ["Sair", "Ficar"])
        self.assertEqual([b[0] for b in asked[1]], ["OK", "Cancel"])
        self.assertEqual(asked[2][0][0], "Entendi")


class TheCascade(unittest.TestCase):

    def test_a_shorthand_resets_what_a_wider_rule_said(self):
        styles = {"label": {"padding-left": "0px", "color": "red"},
                  "badge": {"padding": "6px 12px"}}
        merged = component_style(styles, "label", "badge", include_body=False)
        self.assertEqual(merged["padding"], "6px 12px")
        self.assertNotIn("padding-left", merged)
        self.assertEqual(merged["color"], "red")

    def test_a_longhand_still_beats_a_wider_shorthand(self):
        styles = {"label": {"padding": "8px"}, "badge": {"padding-left": "0px"}}
        merged = component_style(styles, "label", "badge", include_body=False)
        self.assertEqual((merged["padding"], merged["padding-left"]), ("8px", "0px"))

    def test_margin_and_corners_too(self):
        styles = {"container": {"margin-top": "0px", "border-top-left-radius": "0px"},
                  "box": {"margin": "4px", "border-radius": "12px"}}
        merged = component_style(styles, "container", "box", include_body=False)
        self.assertNotIn("margin-top", merged)
        self.assertNotIn("border-top-left-radius", merged)

    def test_it_is_a_plain_dict(self):
        self.assertIs(type(component_style({"label": {}}, "label", "x")), dict)


def _root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:          # no display
        raise unittest.SkipTest(str(exc))
    root.withdraw()
    return root


class ThePreviewer(unittest.TestCase):

    def _render(self, kind, styles, comp_id):
        from apkpy_lib import ui
        root = _root()
        app = ui.AppPreview.__new__(ui.AppPreview)
        saved = dict(ui.global_styles)
        animate, proxy = ui._animate_widget, ui._app
        try:
            ui.global_styles.clear()
            ui.global_styles.update(styles)
            ui._animate_widget = lambda *a, **kw: None
            ui._app = type("App", (), {"root": root})()
            app.root = root
            # Mapped, so <Configure> reaches the panel, but invisible and off
            # the screen.
            root.attributes("-alpha", 0.0)
            root.geometry("300x300+-4000+-4000")
            root.deiconify()
            host = tk.Frame(root, bg="#101010", width=300, height=300)
            host.pack()
            if kind == "chart":
                comp = ui.ComponentDef("chart", kind="ring", value=1, max=4, comp_id=comp_id)
                ui.AppPreview._render_chart(app, comp, host, False, None, "#101010")
            else:
                comp = ui.ComponentDef("container", comp_id=comp_id)
                ui.AppPreview._render_container(app, comp, host, False, None, "#101010")
            for _ in range(5):
                root.update()
            return comp.widget, root
        finally:
            ui._animate_widget, ui._app = animate, proxy
            ui.global_styles.clear()
            ui.global_styles.update(saved)

    def test_a_chart_keeps_its_width(self):
        canvas, root = self._render("chart", {"ring": {"width": "92px", "height": "92px"}},
                                    "ring")
        try:
            self.assertEqual(int(float(canvas.cget("width"))), 92)
        finally:
            root.destroy()

    def test_an_empty_circle_is_as_tall_as_it_is_wide(self):
        style = {"dot": {"width": "32px", "height": "32px", "border-radius": "16px",
                         "background-color": "#333333", "padding": "0px"}}
        widget, root = self._render("container", style, "dot")
        try:
            def everything(w):
                yield w
                for child in w.winfo_children():
                    yield from everything(child)
            panel = next(w for w in everything(root) if isinstance(w, tk.Canvas))
            root.update()
            self.assertEqual(int(float(panel.cget("height"))), 32)
        finally:
            root.destroy()


    def test_a_narrow_child_follows_the_column_align_items(self):
        from apkpy_lib import ui
        root = _root()
        saved = dict(ui.global_styles)
        animate, proxy = ui._animate_widget, ui._app
        try:
            ui.global_styles.clear()
            ui.global_styles.update({
                "track": {"align-items": "flex-start", "padding": "0px"},
                "fill": {"width": "60px", "height": "7px", "background-color": "#7C5CFF"},
            })
            ui._animate_widget = lambda *a, **kw: None
            ui._app = type("App", (), {"root": root})()
            app = ui.AppPreview.__new__(ui.AppPreview)
            app.root = root
            track = ui.ComponentDef("container", comp_id="track")
            fill = ui.ComponentDef("container", comp_id="fill")
            track.children = [fill]
            host = tk.Frame(root, width=300, height=100)
            host.pack()
            ui.AppPreview._render_container(app, track, host, False, None, "#101010")
            root.update()

            def everything(w):
                yield w
                for child in w.winfo_children():
                    yield from everything(child)
            anchors = [w.pack_info().get("anchor") for w in everything(host)
                       if w.winfo_manager() == "pack" and int(float(w.cget("width") or 0)) == 60]
            self.assertIn("w", anchors)
        finally:
            ui._animate_widget, ui._app = animate, proxy
            ui.global_styles.clear()
            ui.global_styles.update(saved)
            root.destroy()


class TheGradientUnderWidgets(unittest.TestCase):

    def test_a_flattened_picture_is_kept(self):
        from PIL import Image
        from apkpy_lib.features import gradient_under
        picture = Image.new("RGBA", (400, 3000), (255, 0, 0, 128))
        first = gradient_under.flatten(picture, (0, 0, 0))
        self.assertIs(gradient_under.flatten(picture, (0, 0, 0)), first)
        self.assertEqual(first.mode, "RGB")
        self.assertAlmostEqual(first.getpixel((10, 10))[0], 128, delta=1)
        self.assertIsNot(gradient_under.flatten(picture, (255, 255, 255)), first)

    def test_a_size_tk_gives_back_as_an_object(self):
        # The Tk of Python 3.8 to 3.11 gives a label's padx and bd as a
        # Tcl_Obj: int() refused it, and the label lost its rounded or
        # gradient background in the Previewer. This stands for one.
        from apkpy_lib.features import gradient_under

        class TclObj(object):
            def __str__(self):
                return "26"

        root = _root()
        try:
            label = tk.Label(root, text="M")
            with self.assertRaises(TypeError):
                int(TclObj())
            self.assertEqual(gradient_under._px(label, TclObj()), 26)
            self.assertEqual(gradient_under._px(label, 3), 3)
            self.assertEqual(gradient_under._px(label, "0"), 0)
        finally:
            root.destroy()

    def test_a_shaped_label_paints_once(self):
        from apkpy_lib import ui
        from apkpy_lib.features import gradient_under
        root = _root()
        calls = []
        original = gradient_under.paint_label

        def counting(label, region):
            calls.append(1)
            return original(label, region)
        try:
            root.attributes("-alpha", 0.0)
            root.geometry("300x120+-4000+-4000")
            root.deiconify()
            host = tk.Frame(root, bg="#101010", width=300, height=120)
            host.pack(fill="both", expand=True)
            label = tk.Label(host, text="M", bg="#101010", fg="white", padx=26, pady=18)
            label.place(x=10, y=10)
            gradient_under.paint_label = counting
            ui._shape_label(label, {"background-color": "#726CF7", "border-radius": "36px"},
                            None)
            import time
            end = time.time() + 1.0
            while time.time() < end:
                root.update()
                time.sleep(0.01)
            self.assertLessEqual(len(calls), 3)
            self.assertTrue(str(label.cget("image")))
        finally:
            gradient_under.paint_label = original
            root.destroy()


if __name__ == "__main__":
    unittest.main()
