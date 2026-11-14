# -*- coding: utf-8 -*-
"""container(on_click=) / card(on_click=) and component.set_state().

An answer card that is tapped and wears its "selected" look: the box takes a
tap like a button, and ``answer:selected { ... }`` in the stylesheet is what
set_state("selected") puts on (None takes it off). On the phone each state is
a drawable and a text colour compiled at build time; in the Previewer the
component is drawn again with the state's block.
"""

import tkinter as tk
import unittest

from apkpy_lib.core.compiler import translate_python_to_android

_APP = '''
from apkpy_lib import *
home = Screen(id="home")
def pick(letter):
    box.set_state("selected")
    tag.set_state("selected")
def clear():
    box.set_state(None)
box = container(id="box", screen=home, on_click=lambda: pick("A"))
tag = label("A", id="tag", parent=box)
card(title="More", id="more", screen=home, on_click=clear)
style = """
box { background-color: #222222; border-radius: 12px; }
box:selected { background-color: #7C5CFF; border-color: #FFFFFF; border-width: 2px; }
tag:selected { color: #FFFFFF; }
"""
run(start_screen=home)
'''


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = translate_python_to_android(_APP, package="dev.apkpy.check.state")
        cls.java = next(v for k, v in cls.files.items()
                        if k.endswith("Activity.java") and "pythonCallback_pick" in v)

    def test_a_tapped_box_calls_its_function(self):
        self.assertIn("findViewById(R.id.cnt1).setOnClickListener", self.java)
        self.assertIn('pythonCallback_pick(String.valueOf("A"))', self.java)

    def test_a_tapped_card_too(self):
        card = self.java[self.java.index("findViewById(R.id.card1).setOnClickListener"):]
        # clear() is written where the card is tapped.
        self.assertIn("_apkpySetState(R.id.cnt1, null);", card[:300])

    def test_set_state_in_a_function(self):
        body = self.java[self.java.index("void pythonCallback_pick"):]
        body = body[:body.index("\n    }")]
        self.assertIn('_apkpySetState(R.id.cnt1, String.valueOf("selected"));', body)
        self.assertIn("_apkpySetState(R.id.cnt1, null);", self.java)

    def test_each_state_is_a_drawable_and_a_colour(self):
        shape = self.files["res/drawable/box_selected_state_shape.xml"]
        self.assertIn("#7C5CFF", shape.upper())
        self.assertIn('android:width="2dp"', shape)
        self.assertIn("R.drawable.box_selected_state_shape", self.java)
        self.assertIn('parseColor("#FFFFFF")', self.java)

    def test_no_state_no_helper(self):
        files = translate_python_to_android(
            _APP.replace("box.set_state", "print").replace("tag.set_state", "print")
            .replace(":selected", "_x"), package="dev.apkpy.check.state")
        java = "".join(v for k, v in files.items() if k.endswith(".java"))
        self.assertNotIn("_apkpySetState", java)


class ThePreviewer(unittest.TestCase):

    def test_set_state_draws_it_again_with_the_block(self):
        from apkpy_lib import ui
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(str(exc))
        root.withdraw()
        saved = dict(ui.global_styles)
        animate, proxy = ui._animate_widget, ui._app
        tapped = []
        try:
            ui.global_styles.clear()
            ui.global_styles.update({
                "box": {"background-color": "#222222", "padding": "8px"},
                "box:selected": {"background-color": "#7C5CFF"},
            })
            ui._animate_widget = lambda *a, **kw: None
            app = ui.AppPreview.__new__(ui.AppPreview)
            app.root = root
            app._content_width = None
            ui._app = type("App", (), {"root": root, "_get": lambda self: app})()
            root.attributes("-alpha", 0.0)
            root.geometry("300x200+-4000+-4000")
            root.deiconify()
            host = tk.Frame(root)
            host.pack()
            box = ui.container(id="box", on_click=lambda: tapped.append(1))
            ui.label("A", parent=box)
            app._render_comp(box, host, False, None, "#101010")
            root.update()

            def colours():
                found = set()
                pending = list(box._apkpy_made)
                while pending:
                    w = pending.pop()
                    pending.extend(w.winfo_children())
                    if isinstance(w, tk.Frame):
                        found.add(str(w.cget("bg")).upper())
                return found

            self.assertIn("#222222", colours())
            box.set_state("selected")
            root.update()
            self.assertIn("#7C5CFF", colours())
            self.assertNotIn("#222222", colours())
            box.set_state(None)
            root.update()
            self.assertIn("#222222", colours())
            # A tap anywhere on it.
            box._apkpy_made[0].event_generate("<ButtonRelease-1>")
            root.update()
            self.assertEqual(tapped, [1])
        finally:
            ui._animate_widget, ui._app = animate, proxy
            ui.global_styles.clear()
            ui.global_styles.update(saved)
            root.destroy()


if __name__ == "__main__":
    unittest.main()
