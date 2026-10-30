# -*- coding: utf-8 -*-
"""Ten problems found by someone building a real app with 1.14.1.

Each built without a word and then went wrong on the phone or in the
Previewer, and the two sides disagreed:

    storage.set(name, v)                 every value under the key ""
    on_click_navigate(detail, {...})     the next screen opened empty
    set_items([{"title": text}])         a row with nothing in it
    markdown().set_value(text)           ClassCastException on the phone
    speech.say() alone                   javac: no ApkpyKitActivity
    a list or a text above 64 KB         javac: cannot find symbol / too long
    gap on virtual_collection(row=)      the rows stuck together
    int(screen.get_param("id"))          TypeError in the Previewer
    json_get(text, "items.0")            {'id': 1} in the Previewer
    a field filled while hidden          grey, as if empty, once shown

The Java is read where only the phone can run it, run on the PC's JVM where
it can, and the Previewer is opened, invisible, where the fault was there.
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest

from apkpy_lib import ui
from apkpy_lib.core.compiler import translate_python_to_android

from test_classes import TOOLING

HEAD = ('from apkpy_lib import *\n'
        'home = Screen(id="home")\n'
        'out = label("", id="out", screen=home)\n')


def _files(body):
    return translate_python_to_android(HEAD + body + '\nrun(start_screen=home)\n')


def _java(body):
    files = _files(body)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"][:600])
    return files["java/Screen_homeActivity.java"], files


def _lines(java, pattern):
    return [line.strip() for line in java.splitlines() if re.search(pattern, line)]


class StorageKeysAreWhatTheCodeSays(unittest.TestCase):

    def test_a_key_in_a_name_is_that_name(self):
        java, _ = _java('''
def go():
    name = "theme"
    fallback = "light"
    storage.set(name, "dark")
    v = storage.get(name, fallback)
    storage.delete(name)
    storage.set(f"note_{v}", "x")
    out.set_value(v)
button("Go", id="b", command=go, screen=home)
''')
        self.assertNotIn('_apkpyStorageSet("",', java)
        self.assertNotIn('_apkpyStorageGet("",', java)
        self.assertIn('_apkpyStorageSet(String.valueOf(name), String.valueOf("dark"));', java)
        self.assertIn('_apkpyStorageGet(String.valueOf(name), String.valueOf(fallback));', java)
        self.assertIn('.edit().remove(String.valueOf(name)).apply();', java)
        self.assertIn('_apkpyStorageSet(String.valueOf("note_" + String.valueOf(v))', java)

    def test_a_key_written_out_is_the_literal_it_was(self):
        java, _ = _java('''
def go():
    storage.set("theme", "dark")
    storage.set('say "hi"', 1)
    v = storage.get("theme", "light")
    storage.delete("theme")
    storage.delete("theme")
    out.set_value(v)
button("Go", id="b", command=go, screen=home)
''')
        self.assertIn('_apkpyStorageSet("theme", String.valueOf("dark"));', java)
        self.assertIn('_apkpyStorageSet("say \\"hi\\"", String.valueOf(1));', java)
        self.assertIn('String v = _apkpyStorageGet("theme", "light");', java)
        # Two deletes in one function: there was a variable per key, declared
        # twice, which javac refused.
        self.assertEqual(len(_lines(java, r'remove\("theme"\)')), 2 * 2)   # Activity + method
        self.assertNotIn('prefs_del_', java)

    def test_a_key_at_the_top_of_the_file(self):
        java, _ = _java('''
KEY = "lang"
saved = storage.get(KEY, "pt")
out.set_value(saved)
''')
        self.assertIn('_apkpyStorageGet(String.valueOf(KEY), "pt")', java)


class NavigationCarriesItsData(unittest.TestCase):

    def test_data_given_without_its_name(self):
        java, _ = _java('''
detail = Screen(id="detail")
def go(item):
    on_click_navigate(detail, {"id": item, 'say "x"': 2})
def go2():
    on_click_navigate(detail, data={"id": "8"})
def go3():
    on_click_navigate(detail, {"id": "9"}, "slide")
button("Go", id="b", command=lambda: go("7"), screen=home)
button("Go2", id="b2", command=go2, screen=home)
button("Go3", id="b3", command=go3, screen=home)
''')
        self.assertIn('_navIntent.putExtra("id", String.valueOf(item));', java)
        self.assertIn('_navIntent.putExtra("say \\"x\\"", String.valueOf(2));', java)
        self.assertIn('_navIntent.putExtra("id", String.valueOf("8"));', java)
        self.assertIn('_navIntent.putExtra("id", String.valueOf("9"));', java)
        self.assertIn('apkpy_slide_enter', java)

    def test_data_the_build_cannot_see_stops_it(self):
        for data in ('d', '{k: "1"}'):
            files = _files('''
detail = Screen(id="detail")
def go():
    d = {"id": "1"}
    k = "id"
    on_click_navigate(detail, %s)
button("Go", id="b", command=go, screen=home)
''' % data)
            error = files.get("error.txt", "")
            self.assertIn("U2033", error, data)
            self.assertIn('on_click_navigate(detail, {"id": item["id"]})', error)


class RowsWrittenInTheCall(unittest.TestCase):

    def test_a_row_that_holds_a_name_is_filled_while_the_app_runs(self):
        java, _ = _java('''
detail = virtual_collection([], template={"title": "{titulo}"}, id="detail", screen=home)
names = list_view([], id="names", screen=home)
def go():
    texto = "ola"
    detail.set_items([{"titulo": texto}, {"titulo": "fixo"}])
    names.set_items([texto, "b"])
button("Go", id="b", command=go, screen=home)
''')
        self.assertNotIn('_items.add("{}")', java)
        self.assertIn('_apkpyJsonObj("titulo", _apkpyJsonOut(String.valueOf(texto)))', java)
        self.assertIn('_apkpyJsonArr(_apkpyJsonOut(String.valueOf(texto)), "b")', java)

    def test_rows_written_out_are_the_literals_they_were(self):
        java, _ = _java('''
detail = virtual_collection([], template={"title": "{titulo}"}, id="detail", screen=home)
def go():
    detail.set_items([{"titulo": "a"}])
button("Go", id="b", command=go, screen=home)
''')
        self.assertIn('vc1_items.add("{\\"titulo\\":\\"a\\"}");', java)


class MarkdownTakesANewText(unittest.TestCase):

    def test_the_phone_calls_set_markdown_and_the_view_has_it(self):
        java, files = _java('''
md = markdown("", id="md", screen=home)
def go():
    md.set_value("# Title")
button("Go", id="b", command=go, screen=home)
''')
        self.assertIn('((ApkpyRichContentView) findViewById(R.id.rich1))'
                      '.setMarkdown(String.valueOf("# Title"));', java)
        self.assertNotIn('rich1.setText', java)
        self.assertNotIn('(android.widget.TextView)findViewById(R.id.rich1)', java)
        self.assertIn('public void setMarkdown(CharSequence source)',
                      files["java/ApkpyRichContentView.java"])

    def test_rich_text_and_tree_view_say_they_cannot(self):
        error = _files('''
rt = rich_text([{"text": "a"}], id="rt", screen=home)
def go():
    rt.set_value("x")
button("Go", id="b", command=go, screen=home)
''').get("error.txt", "")
        self.assertIn("U2033", error)
        self.assertIn("markdown()", error)

    def test_the_previewer_draws_the_new_text(self):
        from test_real_screens import Previewed
        with Previewed('home = Screen(id="home")\n'
                       'md = markdown("**old** text", id="md", screen=home)\n',
                       '', screen='home') as view:
            comp = view.ns['md']
            text = comp._rich_text_widget
            self.assertEqual(text.get('1.0', 'end-1c').strip(), 'old text')
            comp.set_value('# New title\n\nSome **bold**')
            view.settle(0.3)
            shown = text.get('1.0', 'end-1c')
            self.assertIn('New title', shown)
            self.assertNotIn('#', shown)
            self.assertNotIn('old text', shown)
            self.assertEqual(comp.kwargs['source'], '# New title\n\nSome **bold**')


class SpeechAloneBuilds(unittest.TestCase):
    """ApkpySpeech held listen(), which names ApkpyKitActivity, in an app that
    only said things and so had no ApkpyKitActivity: javac stopped. The
    methods only the screen that waits uses are left out of such an app."""

    def _files(self, call):
        _, files = _java('''
def heard(ok, value):
    out.set_value(value)
def go():
    %s
button("Go", id="b", command=go, screen=home)
''' % call)
        return files

    def _naming_it(self, files):
        return [name for name, text in files.items()
                if name.endswith(".java") and name != "java/ApkpyKitActivity.java"
                and "ApkpyKitActivity" in text]

    def test_say_alone_has_no_screen_that_waits_and_nothing_naming_it(self):
        for call in ('speech.say("ola")', 'recorder.stop()'):
            files = self._files(call)
            self.assertNotIn("java/ApkpyKitActivity.java", files, call)
            self.assertNotIn("ApkpyKitActivity", files["AndroidManifest.xml"], call)
            self.assertEqual(self._naming_it(files), [], call)
        self.assertNotIn("listen(", self._files('speech.say("ola")')["java/ApkpySpeech.java"])

    def test_the_calls_that_wait_keep_their_method_and_bring_the_screen(self):
        for call, klass in (('speech.listen(on_result=heard)', "ApkpySpeech"),
                            ('recorder.start()', "ApkpyRecorder")):
            files = self._files(call)
            self.assertIn("java/ApkpyKitActivity.java", files, call)
            self.assertIn("ApkpyKitActivity", files["AndroidManifest.xml"], call)
            self.assertEqual(self._naming_it(files), ["java/%s.java" % klass], call)
            self.assertNotIn("apkpy:launcher", files["java/%s.java" % klass])

    def test_a_family_that_never_names_it_goes_without(self):
        files = self._files("haptics.vibrate(100)")
        self.assertNotIn("java/ApkpyKitActivity.java", files)
        self.assertNotIn("ApkpyKitActivity", files["AndroidManifest.xml"])


class BigConstantsCompile(unittest.TestCase):
    BIG_LIST = ", ".join('"palavra %05d çé 😀"' % i for i in range(3000))
    BIG_DICT = ", ".join('"k%05d": "valor %05d"' % (i, i) for i in range(4000))

    def _java(self):
        java, _ = _java('''
DADOS = [%s]
TABELA = {%s}
TEXTO = "%s"
def go():
    out.set_value(DADOS[5] + TABELA["k00007"] + TEXTO)
button("Go", id="b", command=go, screen=home)
''' % (self.BIG_LIST, self.BIG_DICT, "x" * 70000))
        return java

    def test_each_is_declared_from_pieces(self):
        java = self._java()
        for name in ("DADOS", "TABELA", "TEXTO"):
            self.assertTrue(_lines(java, r"private static final String %s = new StringBuilder\(" % name),
                            name)

    def test_javac_takes_them_and_the_jvm_reads_them_back(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        fields = [line for line in self._java().splitlines()
                  if re.match(r"    private static final String (DADOS|TABELA|TEXTO) = ", line)]
        javac, java_bin, jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-big-")
        try:
            source = ("public class Big {\n" + "\n".join(fields) + "\n"
                      "    public static void main(String[] a) throws Exception {\n"
                      "        org.json.JSONArray d = new org.json.JSONArray(DADOS);\n"
                      "        org.json.JSONObject t = new org.json.JSONObject(TABELA);\n"
                      "        java.io.PrintStream o = new java.io.PrintStream(System.out, true, \"UTF-8\");\n"
                      "        o.println(d.length() + \"|\" + d.getString(2999) + \"|\" + t.length()"
                      " + \"|\" + TEXTO.length());\n"
                      "    }\n}\n")
            with open(os.path.join(work, "Big.java"), "w", encoding="utf-8") as f:
                f.write(source)
            built = subprocess.run([javac, "-encoding", "UTF-8", "-cp", jar, "-d", work,
                                    os.path.join(work, "Big.java")],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([java_bin, "-cp", work + os.pathsep + jar, "Big"],
                                 capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(ran.stdout.strip(), "3000|palavra 02999 çé 😀|4000|70000")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def test_a_small_one_is_still_a_literal(self):
        java, _ = _java('''
NAMES = ["a", "b"]
def go():
    out.set_value(NAMES[0])
button("Go", id="b", command=go, screen=home)
''')
        self.assertIn('private static final String NAMES = "[\\"a\\",\\"b\\"]";', java)


class RowGap(unittest.TestCase):

    BODY = '''
style = """
rows { %s }
"""
def card(item):
    label("{t}", id="t")
rows = virtual_collection([{"t": "a"}, {"t": "b"}], row=card, id="rows", screen=home)
'''

    def test_gap_reaches_the_row_adapter(self):
        java, _ = _java(self.BODY % "gap: 10px;")
        self.assertIn("vc1Adapter.setGap(10);", java)
        self.assertIn("void setGap(int dp)", java)

    def test_no_gap_no_call(self):
        java, _ = _java(self.BODY % "height: 300px;")
        self.assertNotIn("Adapter.setGap(", java)


class GetParamIsText(unittest.TestCase):

    def test_it_reads_as_the_text_it_stands_for(self):
        screen = ui.Screen(id="reported_details")
        ref = screen.get_param("id", "0")
        self.assertEqual(int(ref), 0)
        self.assertTrue(ref == "0")
        screen._params = {"id": "42"}
        self.assertEqual(int(ref), 42)
        self.assertEqual(float(ref), 42.0)
        self.assertTrue(ref == "42")
        self.assertFalse(ref != "42")
        self.assertEqual("n" + ref, "n42")
        self.assertEqual(ref + "!", "42!")
        self.assertEqual(f"[{ref}]", "[42]")
        self.assertEqual(ref.zfill(4), "0042")
        self.assertIn("4", ref)
        self.assertEqual({ref: 1}, {"42": 1})
        with self.assertRaises(ValueError):
            screen._params = {"id": "abc"}
            int(ref)


class JsonGetGivesJson(unittest.TestCase):

    TEXT = ('{"itens": [{"id": 1, "titulo": "Ol\\u00e1/at\\u00e9 \\"x\\"", "pre\\u00e7o": 2.5, '
            '"inteiro": 1.0, "ok": true, "nada": null, "tags": ["a", "b"]}], "n": 2}')

    def test_an_object_or_a_list_is_written_as_android_does(self):
        self.assertEqual(
            ui.json_get(self.TEXT, "itens.0"),
            '{"id":1,"titulo":"Olá\\/até \\"x\\"","preço":2.5,"inteiro":1,'
            '"ok":true,"nada":null,"tags":["a","b"]}')
        self.assertEqual(ui.json_get(self.TEXT, "itens.0.tags"), '["a","b"]')

    def test_a_value_is_as_it_was(self):
        self.assertEqual(ui.json_get(self.TEXT, "itens.0.titulo"), 'Olá/até "x"')
        self.assertEqual(ui.json_get(self.TEXT, "n"), "2")
        self.assertEqual(ui.json_get(self.TEXT, "itens.0.ok"), "True")
        self.assertEqual(ui.json_get(self.TEXT, "itens.9"), "")


class HiddenThenShown(unittest.TestCase):

    def test_a_field_filled_while_hidden_comes_back_with_its_text_colour(self):
        from test_real_screens import Previewed
        body = ('home = Screen(id="home")\n'
                'box = container(id="box", screen=home)\n'
                'field = inputs("Your name", id="field", parent=box)\n')
        with Previewed(body, '', screen='home') as view:
            entry = [w for w in view.ns['box'].widget.winfo_children()
                     if w.winfo_class() == 'Entry'] or None
            if entry is None:
                found = []

                def walk(widget):
                    for child in widget.winfo_children():
                        if child.winfo_class() == 'Entry':
                            found.append(child)
                        walk(child)
                walk(view.ns['box'].widget)
                entry = found
            entry = entry[0]
            placeholder = entry.cget('fg')
            view.ns['box'].hide()
            view.settle(0.6)
            view.ns['field'].set_value('Ana')
            view.settle(0.2)
            view.ns['box'].show()
            view.settle(0.8)
            self.assertEqual(entry.get(), 'Ana')
            self.assertNotEqual(entry.cget('fg'), placeholder)
            # Emptied the same way, the hint comes back in its own grey.
            view.ns['box'].hide()
            view.settle(0.6)
            view.ns['field'].set_value('')
            view.settle(0.2)
            view.ns['box'].show()
            view.settle(0.8)
            self.assertEqual(entry.cget('fg'), placeholder)


if __name__ == "__main__":
    unittest.main()
