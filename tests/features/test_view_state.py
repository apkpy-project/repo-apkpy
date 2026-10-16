"""Generated Activities preserve only runtime-mutated TextView contents."""
import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import view_state

# One of everything that holds text or a value, each changed after the screen
# is built, and a second screen that reuses the first one's ids.
APP = '''from apkpy_lib import Screen, Theme, app_bar, label, inputs, button, list_row, run

home = Screen(id="home", scroll=True)
other = Screen(id="other", scroll=True)
app_bar("State regression", screen=home)
app_bar("Other screen", screen=other)
label("Activity state regression", screen=home)
status = label("XML default", screen=home)
empty = label("Erase this", screen=home)
draft = inputs("Draft", screen=home)
checked = inputs("Checkbox", type="checkbox", screen=home)
switched = inputs("Switch", type="switch", screen=home)
progress = inputs("", type="range", screen=home)
selected = inputs("A|B|C", type="select", screen=home)
radio = inputs("A|B|C", type="radio", screen=home)
date = inputs("Date", type="date", screen=home)
time = inputs("Time", type="time", screen=home)
row = list_row("Row default", subtitle="Subtitle default", trailing="Old", screen=home)
renamed = button("Button default", screen=home)


def mutate():
    status.set_value("Saved text: 123")
    empty.set_value("")
    draft.set_value("Saved draft")
    checked.set_value(True)
    switched.set_value(True)
    progress.set_value("37")
    selected.set_value("B")
    radio.set_value("C")
    date.set_value("06/09/2026")
    time.set_value("13:42")
    row.set_value("Saved row")
    row.set_subtitle("Saved subtitle")
    row.set_trailing("New")
    renamed.set_value("Saved button")


status.set_value("Module default")
button("Change values", screen=home, command=mutate)
open_other = button("Other screen", screen=home)
home.on_click_navigate(button=open_other, to=other)
other_status = label("Other default", screen=other)
button("Change other", screen=other,
       command=lambda: other_status.set_value("Other saved"))
back = button("Back", screen=other)
other.on_click_navigate(button=back, to=home)
run(start_screen=home, theme=Theme(mode="dark"))
'''


def build(source):
    files = translate_python_to_android(source)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"])
    return files


class ViewStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = build(APP)
        cls.java = cls.files["java/Screen_homeActivity.java"]

    def test_uses_native_instance_state_not_global_storage(self):
        self.assertIn("setFreezesText(true)", self.java)
        self.assertIn("super.onSaveInstanceState(outState);", self.java)
        self.assertIn('outState.putIntegerArrayList("apkpy:frozenText"', self.java)
        self.assertNotIn("java/ApkpyReactiveState.java", self.files)
        self.assertNotIn("configChanges=", self.files["AndroidManifest.xml"])
        self.assertNotIn("screenOrientation=", self.files["AndroidManifest.xml"])

    def test_policy_is_restored_after_inflation_before_initializers(self):
        java = self.java
        self.assertLess(java.index("setContentView("), java.index("_apkpyRestoreTextPolicy(savedInstanceState)"))
        self.assertLess(java.index("_apkpyRestoreTextPolicy(savedInstanceState)"), java.index('setText(String.valueOf("Module default"))'))
        self.assertIn("for (Integer id : ids) _apkpyRememberText(id)", java)

    def test_inline_and_named_callbacks_remember_changed_text(self):
        for target in ("lbl2", "lbl3", "btn1", "lrow1_title", "lrow1_subtitle", "lrow1_trailing"):
            self.assertGreaterEqual(self.java.count(f"_apkpyRememberText(R.id.{target});"), 2, target)

    def test_native_inputs_keep_their_existing_state_handling(self):
        for number in range(1, 7):
            self.assertNotIn(f"_apkpyRememberText(R.id.inp{number});", self.java)

    def test_date_time_picker_and_set_value_both_remember(self):
        for number in (7, 8):
            self.assertGreaterEqual(self.java.count(f"_apkpyRememberText(R.id.inp{number});"), 3)

    def test_unchanged_labels_are_not_frozen(self):
        self.assertNotIn("_apkpyRememberText(R.id.lbl1);", self.java)
        self.assertNotIn('android:freezesText="true"', self.files["res/layout/activity_screen_home.xml"])

    def test_screen_ids_are_not_shared_in_a_static_store(self):
        other = self.files["java/Screen_otherActivity.java"]
        self.assertIn("_apkpyRememberText(R.id.lbl1);", other)
        self.assertNotIn("_apkpyRememberText(R.id.lbl2);", other)
        self.assertNotIn("static final java.util.HashSet", other)

    def test_plain_app_has_no_added_code(self):
        files = build('from apkpy_lib import *\nhome=Screen(id="home")\nlabel("Static",screen=home)\nrun(start_screen=home)')
        self.assertNotIn("_apkpyFrozenText", files["java/Screen_homeActivity.java"])
        self.assertNotIn("onSaveInstanceState", files["java/Screen_homeActivity.java"])

    def test_native_input_only_app_has_no_added_code(self):
        files = build('from apkpy_lib import *\nhome=Screen(id="home")\nx=inputs("Draft",screen=home)\nbutton("Set",screen=home,command=lambda: x.set_value("new"))\nrun(start_screen=home)')
        self.assertNotIn("_apkpyFrozenText", files["java/Screen_homeActivity.java"])

    def test_command_walker_checks_every_branch(self):
        component = {"comp_type": "label", "_py_var": "status"}
        for key in view_state.BODY_KEYS:
            commands = [{"type": "branch", key: [{"type": "comp_set_value", "py_var": "status"}]}]
            self.assertTrue(view_state.used_by([component], {"go": {"cmds": commands}}), key)
            self.assertTrue(view_state.used_by([component], {}, commands), key)

    def test_optional_row_slots_are_guarded(self):
        self.assertIn("view instanceof android.widget.TextView", self.java)


if __name__ == "__main__":
    unittest.main()
