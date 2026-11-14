# -*- coding: utf-8 -*-
"""The private methods a generated class never reaches are not written.

A friend opened an ApkPy app in Android Studio and found ten thousand lines
he did not need (06-11-2026). He was right: every screen carried the whole
kit of helpers and a callback for every function of the app, and on the
first screen of a four-screen app 2 400 of 2 700 lines never ran. R8 kept
them too, because proguard-rules.pro keeps every member of the generated
classes.
"""

import unittest

from apkpy_lib.core import dead_methods
from apkpy_lib.core.compiler import translate_python_to_android

_CLASS = '''package com.apkpy.app;

public class Screen_homeActivity extends AppCompatActivity {
    private final Runnable tick = () -> fromField();
    private static final String BRACES = "}}{ not a block // nor a comment";

    @Override
    protected void onCreate(Bundle state) {
        char open = '{';
        used("x");
        java.util.function.Function<String, String> f = this::byReference;
    }

    public void forOthers() {}

    private void used(String s) {
        chained();
    }

    private void chained() {}

    private void fromField() {}

    private String byReference(String s) { return s; }

    // Never called: its comment goes with it.
    private String unused(String s) {
        return "}" + alsoUnused();
    }

    private String alsoUnused() { return "{"; }

    private void overloaded(int a) {}

    public void overloaded(String a) {}

    @android.webkit.JavascriptInterface
    private void fromJavaScript() {}

    @SuppressWarnings("unchecked")
    private void quiet() {}

    private interface Callback { void onDone(String value); }
}
'''


class TheClassKeepsWhatIsReached(unittest.TestCase):

    def setUp(self):
        self.java = dead_methods.drop_unreached(_CLASS)

    def test_a_private_method_nothing_names_goes_with_its_comment(self):
        self.assertNotIn("unused(", self.java)
        self.assertNotIn("Never called", self.java)
        self.assertNotIn("alsoUnused", self.java)
        self.assertNotIn("quiet", self.java)

    def test_what_is_called_named_or_public_stays(self):
        for kept in ("protected void onCreate", "public void forOthers",
                     "private void used", "private void chained",
                     "private void fromField", "private String byReference",
                     "private void overloaded(int a)", "public void overloaded(String a)",
                     "private void fromJavaScript", "void onDone(String value);",
                     'BRACES = "}}{ not a block // nor a comment"'):
            self.assertIn(kept, self.java)

    def test_the_braces_still_close(self):
        self.assertEqual(self.java.count("{") - self.java.count("}"),
                         _CLASS.count("{") - _CLASS.count("}"))
        self.assertTrue(self.java.rstrip().endswith("}"))
        self.assertNotIn("\n\n\n", self.java)

    def test_a_class_with_nothing_to_drop_is_left_as_it_is(self):
        self.assertEqual(dead_methods.drop_unreached(self.java), self.java)
        self.assertEqual(dead_methods.drop_unreached("class A {}"), "class A {}")


_APP = '''
from apkpy_lib import *
home = Screen(id="home")
other = Screen(id="other")
out = label("", id="out", screen=home)


def pick(letter):
    out.set_value("{:.2f}".format(3.14159) + letter)


button("A", id="a", command=lambda: pick("A"), screen=home)
label("Nothing here", id="quiet", screen=other)
run(start_screen=home)
'''


class EachScreenCarriesOnlyItsOwn(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = translate_python_to_android(_APP)
        assert "error.txt" not in cls.files, cls.files.get("error.txt")

    def test_a_function_is_written_only_where_it_is_called(self):
        home = self.files["java/Screen_homeActivity.java"]
        other = self.files["java/Screen_otherActivity.java"]
        self.assertIn("private void pythonCallback_pick(", home)
        self.assertNotIn("pythonCallback_pick", other)

    def test_a_helper_is_written_only_where_it_is_used(self):
        self.assertIn("private String _apkpyFormat(", self.files["java/Screen_homeActivity.java"])
        self.assertNotIn("_apkpyFormat", self.files["java/Screen_otherActivity.java"])

    def test_a_screen_with_one_label_is_short(self):
        # 2 600 lines before; what is left is onCreate and the theme.
        self.assertLess(self.files["java/Screen_otherActivity.java"].count("\n"), 300)


if __name__ == "__main__":
    unittest.main()
