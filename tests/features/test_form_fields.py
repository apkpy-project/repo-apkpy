"""Text fields with help, an error and a required rule.

`inputs(..., help=, error=, required=)`, `field.set_error()` and
`validate(a, b)` are drawn by the Previewer and by ApkpyField on the phone.
What the line under the field says and when a field counts as empty are one
set of rules (apkpy_lib/field_rules.py); the last class compiles the Java and
asks it the same questions.
"""

import io
import os
import subprocess
import tempfile
import unittest

from apkpy_lib import field_rules as rules
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import field as field_feature
from apkpy_lib.diagnostics import ApkpyError

from test_data_rules import TOOLING
from test_real_screens import Previewed, _build, _layouts

FORM = (
    'home = Screen(id="home")\n'
    'name = inputs("Full name", id="name", required=True, screen=home)\n'
    'email = inputs("Email", id="email", help="We only use it to sign you in",\n'
    '               required="Enter your email", screen=home)\n'
    'code = inputs("Invite code", id="code", error="That code has expired", screen=home)\n'
    'plain = inputs("Nickname", id="plain", screen=home)\n'
    'def send():\n'
    '    if not validate(name, email):\n'
    '        return\n'
    '    if "@" not in email.get_value():\n'
    '        email.set_error("That is not an email address")\n'
    '        return\n'
    '    code.set_error("")\n'
    '    toast("Sent")\n'
    'button("Send", id="go", command=send, screen=home)\n'
)
CSS = 'email { border-width: 1px; border-color: #79747E; border-radius: 8px; }'


def _java(files):
    return ''.join(v for k, v in files.items() if k.endswith('Activity.java'))


class TheSharedRules(unittest.TestCase):

    def test_what_the_line_says(self):
        self.assertEqual(rules.supporting('Help', ''), ('Help', False))
        self.assertEqual(rules.supporting('Help', 'Wrong'), ('Wrong', True))
        self.assertEqual(rules.supporting('', ''), ('', False))

    def test_required(self):
        self.assertEqual(rules.required_message(True), rules.REQUIRED)
        self.assertEqual(rules.required_message("Enter your name"), "Enter your name")
        self.assertEqual(rules.required_message(False), '')
        self.assertEqual(rules.required_message(None), '')
        self.assertEqual(rules.check('', 'Required'), 'Required')
        self.assertEqual(rules.check('   ', 'Required'), 'Required')     # spaces do not fill it
        self.assertEqual(rules.check(' a ', 'Required'), '')
        self.assertEqual(rules.check('', ''), '')                        # no rule, no complaint

    def test_which_fields_get_the_line(self):
        self.assertFalse(rules.wanted('', '', ''))
        self.assertTrue(rules.wanted('Help', '', ''))
        self.assertTrue(rules.wanted('', 'Wrong', ''))
        self.assertTrue(rules.wanted('', '', 'Required'))

    def test_the_outline_of_an_error(self):
        self.assertEqual(rules.stroke(0), 1)        # a field with no border still shows one
        self.assertEqual(rules.stroke(2), 2)

    def test_colours_come_from_the_theme(self):
        self.assertEqual(rules.colors({'text_secondary': '#111111', 'error': '#222222'}),
                         {'help': '#111111', 'error': '#222222'})
        self.assertEqual(set(rules.colors({})), {'help', 'error'})

    def test_refusals(self):
        for call in (lambda: rules.check_type('switch'),
                     lambda: rules.required_message(3),
                     lambda: rules.required_message('  '),
                     lambda: rules.words(5, 'help')):
            with self.assertRaises(ApkpyError) as caught:
                call()
            self.assertEqual(caught.exception.code, 'U2044')


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(FORM, CSS)
        cls.layout = ''.join(_layouts(cls.files).values())
        cls.java = _java(cls.files)

    def _box(self, number):
        return self.layout.split('android:id="@+id/inp%d_box"' % number)[1].split(
            '</com.apkpy.app.ApkpyField>')[0]

    def test_a_field_with_help_sits_in_a_box_with_its_words(self):
        box = self._box(2)
        self.assertIn('android:id="@+id/inp2"', box)
        self.assertIn('android:id="@+id/inp2_support"', box)
        self.assertIn('android:text="We only use it to sign you in"', box)
        self.assertIn('android:hint="Enter your email"', box)          # the required words
        self.assertIn('android:textSize="%dsp"' % rules.SUPPORT_SIZE, box)
        self.assertIn('android:accessibilityLiveRegion="polite"', box)

    def test_nothing_to_say_yet_is_gone(self):
        box = self._box(1)
        self.assertIn('android:hint="%s"' % rules.REQUIRED, box)
        self.assertIn('android:visibility="gone"', box)

    def test_the_box_takes_the_fields_place(self):
        # The margin and the width go to the box; the EditText fills it.
        opening = self.layout.split('android:id="@+id/inp2_box"')[1].split('<EditText')[0]
        self.assertIn('android:layout_marginTop=', opening)
        field = self._box(2).split('<EditText')[1].split('/>')[0]
        self.assertIn('android:layout_width="match_parent"', field)
        self.assertNotIn('layout_margin', field)

    def test_a_plain_field_is_the_edittext_it_always_was(self):
        self.assertNotIn('inp4_box', self.layout)
        self.assertNotIn('inp4_support', self.layout)
        files = _build('home = Screen(id="home")\ninputs("Nickname", id="plain", screen=home)\n')
        self.assertNotIn('java/ApkpyField.java', files)
        self.assertNotIn('ApkpyField', ''.join(_layouts(files).values()))

    def test_the_class_ships_and_is_configured(self):
        self.assertIn('java/ApkpyField.java', self.files)
        line = self.java.split('inp3_box.configure(')[1].split('\n')[0]
        self.assertTrue(line.endswith('"That code has expired");'), line)
        self.assertIn('ApkpyField inp1_box = findViewById(R.id.inp1_box);', self.java)

    def test_an_outlined_field_gets_an_error_outline(self):
        wrong = self.files['res/drawable/email_error_shape.xml']
        self.assertIn('<stroke android:width="1dp"', wrong)
        self.assertNotIn('#79747E', wrong)
        line = self.java.split('inp2_box.configure(')[1].split('\n')[0]
        self.assertIn('R.drawable.email_shape, R.drawable.email_error_shape', line)

    def test_validate_and_set_error_reach_the_boxes(self):
        self.assertIn('if (!(ApkpyField.valid(findViewById(R.id.inp1_box), '
                      'findViewById(R.id.inp2_box)))) {', self.java)
        self.assertIn('ApkpyField.error(findViewById(R.id.inp2_box), '
                      '"That is not an email address");', self.java)
        self.assertIn('ApkpyField.error(findViewById(R.id.inp3_box), "");', self.java)

    def test_set_error_alone_is_enough_to_get_the_line(self):
        files = _build('home = Screen(id="home")\n'
                       'pin = inputs("PIN", id="pin", type="number", screen=home)\n'
                       'def check():\n'
                       '    pin.set_error("Wrong PIN")\n'
                       'button("OK", command=check, screen=home)\n')
        layout = ''.join(_layouts(files).values())
        self.assertIn('android:id="@+id/inp1_box"', layout)
        self.assertIn('ApkpyField.error(findViewById(R.id.inp1_box), "Wrong PIN");', _java(files))

    def test_the_method_form_and_the_value_form(self):
        files = _build('home = Screen(id="home")\n'
                       'name = inputs("Name", id="name", required=True, screen=home)\n'
                       'said = label("", screen=home)\n'
                       'def check():\n'
                       '    if name.validate():\n'
                       '        said.set_value("ok")\n'
                       '    validate(name)\n'
                       'button("OK", command=check, screen=home)\n')
        java = _java(files)
        self.assertIn('if (ApkpyField.valid(findViewById(R.id.inp1_box))) {', java)
        self.assertIn('ApkpyField.valid(findViewById(R.id.inp1_box));', java)

    def test_hide_takes_the_words_with_the_field(self):
        files = _build('home = Screen(id="home")\n'
                       'name = inputs("Name", id="name", help="As on your card", screen=home)\n'
                       'def away():\n'
                       '    name.hide()\n'
                       'button("Hide", command=away, screen=home)\n')
        java = _java(files)
        self.assertRegex(java, r'R\.id\.inp1_box\)?[^\n]*(GONE|false)')
        self.assertNotRegex(java, r'findViewById\(R\.id\.inp1\)\.setVisibility')

    def test_translated_words_follow_the_language(self):
        files = _build('translations({"en": {"hint": "As on your card", "need": "Tell us"},\n'
                       '              "pt": {"hint": "Como no cartão", "need": "Diz-nos"}})\n'
                       'home = Screen(id="home")\n'
                       'inputs("Name", id="name", help=t("hint"), required=t("need"), screen=home)\n')
        layout = ''.join(_layouts(files).values())
        self.assertRegex(layout, r'android:text="@string/\w*hint"')
        self.assertRegex(layout, r'android:hint="@string/\w*need"')

    def test_a_field_nobody_types_in_is_refused(self):
        for body in ('inputs("Wi-Fi", type="switch", help="Uses data", screen=home)\n',
                     'volume = inputs("", type="range", screen=home)\n'
                     'def bad():\n    volume.set_error("Too loud")\n'
                     'button("x", command=bad, screen=home)\n',
                     'inputs("Name", required=3, screen=home)\n'):
            with self.assertRaises(AssertionError) as caught:
                _build('home = Screen(id="home")\n' + body)
            self.assertIn('U2044', str(caught.exception), body)


class ThePreviewer(unittest.TestCase):

    def _words(self, comp):
        label = comp._field.label
        if label is None or not label.winfo_ismapped():
            return None
        return label.cget('text'), str(label.cget('fg')).lower()

    def test_help_shows_and_an_error_takes_its_place(self):
        with Previewed(FORM, CSS) as p:
            email = p.ns['email']
            help_words = self._words(email)
            self.assertEqual(help_words[0], 'We only use it to sign you in')
            email.set_error('That is not an email address')
            p.settle(0.1)
            wrong = self._words(email)
            self.assertEqual(wrong[0], 'That is not an email address')
            self.assertNotEqual(wrong[1], help_words[1])
            email.set_error('')
            p.settle(0.1)
            self.assertEqual(self._words(email), help_words)

    def test_an_error_given_at_the_start_is_there(self):
        with Previewed(FORM, CSS) as p:
            self.assertEqual(self._words(p.ns['code'])[0], 'That code has expired')
            self.assertIsNone(self._words(p.ns['name']))          # required, nothing wrong yet

    def test_validate_shows_every_empty_field_at_once(self):
        with Previewed(FORM, CSS) as p:
            from apkpy_lib import validate
            self.assertFalse(validate(p.ns['name'], p.ns['email']))
            p.settle(0.1)
            self.assertEqual(self._words(p.ns['name'])[0], rules.REQUIRED)
            self.assertEqual(self._words(p.ns['email'])[0], 'Enter your email')
            p.ns['name'].set_value('Ada')
            p.ns['email'].set_value('ada@example.com')
            self.assertTrue(validate(p.ns['name'], p.ns['email']))
            p.settle(0.1)
            self.assertIsNone(self._words(p.ns['name']))
            self.assertEqual(self._words(p.ns['email'])[0], 'We only use it to sign you in')

    def test_typing_clears_the_error(self):
        with Previewed(FORM, CSS) as p:
            code = p.ns['code']
            code._field._typed(type('Key', (), {'keysym': 'a'})())
            p.settle(0.1)
            self.assertIsNone(self._words(code))
            self.assertTrue(code.validate())                      # no rule of its own

    def test_a_plain_field_has_no_line_until_asked(self):
        with Previewed(FORM, CSS) as p:
            plain = p.ns['plain']
            self.assertIsNone(self._words(plain))
            plain.set_error('Taken')
            p.settle(0.1)
            self.assertEqual(self._words(plain)[0], 'Taken')

    def test_the_words_sit_under_the_field(self):
        with Previewed(FORM, CSS) as p:
            email = p.ns['email']
            field_bottom = email.widget.winfo_rooty() + email.widget.winfo_height()
            label = email._field.label
            self.assertGreaterEqual(label.winfo_rooty(), field_bottom)
            self.assertLess(label.winfo_rooty() - field_bottom, 24)

    def test_a_password_shows_its_hint_and_hides_what_is_typed(self):
        body = ('home = Screen(id="home")\n'
                'secret = inputs("Password", id="secret", type="password", screen=home)\n')
        with Previewed(body, '') as p:
            entry = p.ns['secret'].widget
            self.assertEqual(entry.get(), 'Password')
            self.assertEqual(entry.cget('show'), '')            # the hint reads as words
            p.ns['secret'].set_value('hunter2')
            self.assertEqual(entry.cget('show'), '*')
            self.assertEqual(p.ns['secret'].get_value(), 'hunter2')
            p.ns['secret'].set_value('')
            self.assertEqual(entry.cget('show'), '')

    def test_a_switch_refuses(self):
        from apkpy_lib import inputs
        with self.assertRaises(ApkpyError) as caught:
            inputs("Wi-Fi", type="switch", help="Uses data")
        self.assertEqual(caught.exception.code, 'U2044')


class JavaAnswersTheSameWay(unittest.TestCase):
    """The static rules of ApkpyField, lifted from the class as it ships."""

    VALUES = ['', ' ', '   ', 'a', ' a ', '\t', ' ', '0']
    PAIRS = [('Help', ''), ('Help', 'Wrong'), ('', ''), ('', 'Wrong')]

    @staticmethod
    def _literal(text):
        return '"' + ''.join('\\u%04x' % ord(c) for c in text) + '"'

    def _harness(self):
        java = field_feature.java_source('x')
        start = java.index('    /** field_rules.supporting: the words')
        end = java.index('    public void setError')
        calls = []
        for index, value in enumerate(self.VALUES):
            for required in ('', 'Required'):
                calls.append('System.out.println("check|%d|%s|" + check(%s, %s));'
                             % (index, required, self._literal(value), self._literal(required)))
        for index, (help_text, error) in enumerate(self.PAIRS):
            calls.append('System.out.println("says|%d|" + supportingText(%s, %s) + "|" '
                         '+ supportingIsError(%s, %s));'
                         % (index, self._literal(help_text), self._literal(error),
                            self._literal(help_text), self._literal(error)))
        return ('public class FieldRulesHarness {\n' + java[start:end] +
                '    public static void main(String[] args) {\n        '
                + '\n        '.join(calls) + '\n    }\n}\n')

    def test_both_languages_agree(self):
        if not TOOLING:
            self.skipTest("no JDK on this machine")
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix='apkpy-field-')
        source = os.path.join(work, 'FieldRulesHarness.java')
        with io.open(source, 'w', encoding='utf-8') as handle:
            handle.write(self._harness())
        built = subprocess.run([javac, '-encoding', 'UTF-8', '-d', work, source],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, '-cp', work, 'FieldRulesHarness'],
                             capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
        lines = [line.split('|') for line in ran.stdout.splitlines()]
        checks = {(int(i), required): answer for kind, i, required, answer in
                  (line for line in lines if line[0] == 'check')}
        for index, value in enumerate(self.VALUES):
            for required in ('', 'Required'):
                self.assertEqual(checks[(index, required)], rules.check(value, required),
                                 (value, required))
        says = {int(line[1]): (line[2], line[3] == 'true') for line in lines if line[0] == 'says'}
        for index, (help_text, error) in enumerate(self.PAIRS):
            self.assertEqual(says[index], rules.supporting(help_text, error))

    def test_the_sizes_are_the_rules(self):
        files = _build(FORM, CSS)
        layout = ''.join(_layouts(files).values())
        self.assertIn('android:paddingTop="%ddp"' % rules.SUPPORT_GAP, layout)
        self.assertNotRegex(field_feature.java_source('x'), r'__[A-Z_]+__')


if __name__ == '__main__':
    unittest.main()
