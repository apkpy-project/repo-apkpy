# -*- coding: utf-8 -*-
"""The keyboard of a text field: which one, its corner key, autofill.

``inputs(type="email"|"phone"|"url")`` opens the keyboard for it,
``action=`` puts a key in the keyboard's corner and ``on_submit=`` is what it
does, ``autofill=`` tells password managers what the field is.
``hide_keyboard()`` closes the keyboard and ``field.focus()`` opens it.

The Previewer (features/keyboard.py) and the phone (core/features/keyboard.py)
read the same words from ``field_rules``. A plain one-line field also gets
``android:inputType="text"``: without it an EditText is multi-line, and
Enter typed a new line on the phone where the Previewer's field moved on.
"""

import unittest
import xml.etree.ElementTree as ET

from apkpy_lib import field_rules as rules
from apkpy_lib import ui
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.diagnostics import ApkpyError

from test_real_screens import Previewed, _build, _layouts

ANDROID = '{http://schemas.android.com/apk/res/android}'

APP = (
    'home = Screen(id="home")\n'
    'SEEN = []\n'
    'def send(text):\n'
    '    SEEN.append(text)\n'
    'def searched():\n'
    '    SEEN.append("searched")\n'
    'def find():\n'
    '    hide_keyboard()\n'
    'status = label("", id="status", screen=home)\n'
    'email = inputs("Email", type="email", autofill="email", action="next", screen=home)\n'
    'phone = inputs("Phone", type="phone", autofill="phone", screen=home)\n'
    'site = inputs("Website", type="url", screen=home)\n'
    'code = inputs("Code", type="number", autofill="otp", on_submit=lambda: SEEN.append("code"), screen=home)\n'
    'message = inputs("Message", action="send", on_submit=send, screen=home)\n'
    'query = inputs("Search", type="search", on_submit=searched, screen=home)\n'
    'plain = inputs("Plain", screen=home)\n'
    'secret = inputs("Password", type="password", autofill="password", screen=home)\n'
    'notes = inputs("Notes", type="textarea", screen=home)\n'
    'button("Find", id="find", command=find, screen=home)\n'
    'button("Write", id="write", command=lambda: message.focus(), screen=home)\n'
)


def _fields(layout):
    """The EditTexts of a layout, in order, as {attribute: value} without the namespace."""
    found = []
    for node in ET.fromstring(layout).iter('EditText'):
        found.append({k.replace(ANDROID, ''): v for k, v in node.attrib.items()})
    return found


def _refusal(body):
    source = 'from apkpy_lib import *\nhome = Screen(id="home")\n' + body + 'run(start_screen=home)\n'
    return translate_python_to_android(source).get('error.txt', '')


class TheSharedRules(unittest.TestCase):

    def test_keyboard_types_are_text_fields(self):
        for kind in ('email', 'phone', 'url'):
            self.assertIn(kind, rules.TYPES)
            self.assertIn(kind, rules.ALL_TYPES)
            self.assertEqual(rules.base_type(kind), 'text')
        self.assertEqual(rules.base_type('password'), 'password')
        rules.check_known('phone')          # type="phone" used to stop the build in javac

    def test_the_corner_key(self):
        self.assertIsNone(rules.action_of('text', None, False))       # Android's own
        self.assertEqual(rules.action_of('search', None, False), 'search')
        self.assertEqual(rules.action_of('text', None, True), 'done')
        self.assertEqual(rules.action_of('email', 'next', False), 'next')
        self.assertEqual(rules.action_of('search', 'go', True), 'go')
        for bad in (dict(input_type='textarea', action='send', has_submit=False),
                    dict(input_type='textarea', action=None, has_submit=True),
                    dict(input_type='switch', action='done', has_submit=False),
                    dict(input_type='text', action='sned', has_submit=False),
                    dict(input_type='text', action=3, has_submit=False)):
            with self.assertRaises(ApkpyError) as caught:
                rules.action_of(**bad)
            self.assertEqual(caught.exception.code, rules.CODE)

    def test_a_close_word_is_suggested(self):
        with self.assertRaises(ApkpyError) as caught:
            rules.action_of('text', 'sned', False)
        self.assertIn('Did you mean action="send"?', caught.exception.suggestions)
        self.assertEqual(caught.exception.docs, rules.KEYBOARD_DOCS)

    def test_autofill(self):
        self.assertIsNone(rules.autofill_of(None))
        self.assertEqual(rules.AUTOFILL[rules.autofill_of('otp')], 'smsOTPCode')
        with self.assertRaises(ApkpyError):
            rules.autofill_of('mail')
        with self.assertRaises(ApkpyError):
            rules.check_autofill_type('switch', 'email')

    def test_on_submit_takes_the_text_or_nothing(self):
        rules.check_submit_arity(0)
        rules.check_submit_arity(1)
        with self.assertRaises(ApkpyError):
            rules.check_submit_arity(2)

    def test_focus_is_for_a_field_you_type_in(self):
        rules.check_focus('textarea')
        rules.check_focus('email')
        with self.assertRaises(ApkpyError):
            rules.check_focus('switch')


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(APP)
        cls.java = cls.files['java/Screen_homeActivity.java']
        cls.layout = _layouts(cls.files)['res/layout/activity_screen_home.xml']
        cls.fields = _fields(cls.layout)

    def test_each_field_has_its_keyboard(self):
        kinds = [f.get('inputType') for f in self.fields]
        self.assertEqual(kinds, ['textEmailAddress', 'phone', 'textUri', 'numberDecimal|numberSigned',
                                 'text', 'text', 'text', 'textPassword', 'textMultiLine'])

    def test_the_corner_keys(self):
        self.assertEqual([f.get('imeOptions') for f in self.fields],
                         ['actionNext', None, None, 'actionDone', 'actionSend', 'actionSearch',
                          None, None, None])

    def test_autofill(self):
        self.assertEqual([f.get('autofillHints') for f in self.fields],
                         ['emailAddress', 'phoneNumber', None, 'smsOTPCode', None, None, None,
                          'password', None])
        self.assertEqual(self.fields[0].get('importantForAutofill'), 'yes')
        self.assertNotIn('importantForAutofill', self.fields[2])

    def test_on_submit_gets_the_text_or_nothing(self):
        self.assertIn('pythonCallback_send(_v.getText().toString());', self.java)
        self.assertIn('pythonCallback_searched();', self.java)
        self.assertIn('pythonCallback_code_submit();', self.java)

    def test_done_and_search_close_the_keyboard_send_keeps_it(self):
        def listener(jv):
            return self.java.split('%s.setOnEditorActionListener(' % jv)[1].split('});')[0]
        self.assertIn('_apkpyHideKeyboard();', listener('inp4'))      # number, on_submit: done
        self.assertIn('_apkpyHideKeyboard();', listener('inp6'))      # search
        self.assertNotIn('_apkpyHideKeyboard();', listener('inp5'))   # send: the chat goes on
        for jv in ('inp1', 'inp2', 'inp3', 'inp7', 'inp8', 'inp9'):   # Android's own
            self.assertNotIn('%s.setOnEditorActionListener' % jv, self.java)

    def test_an_enter_key_event_runs_once(self):
        block = self.java.split('inp5.setOnEditorActionListener(')[1].split('});')[0]
        self.assertIn('if (_key.getAction() != android.view.KeyEvent.ACTION_DOWN) return true;', block)
        self.assertEqual(block.count('return true;'), 2)

    def test_hide_keyboard_and_focus(self):
        find = self.java.split('btn1.setOnClickListener(')[1].split('});')[0]   # find() is written in place
        self.assertIn('_apkpyHideKeyboard();', find)
        self.assertIn('_apkpyShowKeyboard(findViewById(R.id.inp5));', self.java)
        self.assertIn('private void _apkpyHideKeyboard() {', self.java)
        self.assertIn('addOnWindowFocusChangeListener', self.java)

    def test_a_field_that_opens_with_the_cursor(self):
        files = _build('home = Screen(id="home")\nname = inputs("Name", screen=home)\nname.focus()\n')
        java = files['java/Screen_homeActivity.java']
        on_create = java.split('protected void onCreate(')[1].split('\n    }\n')[0]
        self.assertIn('_apkpyShowKeyboard(findViewById(R.id.inp1));', on_create)

    def test_an_app_that_never_asks_carries_no_helpers(self):
        files = _build('home = Screen(id="home")\ninputs("Name", screen=home)\n')
        java = files['java/Screen_homeActivity.java']
        self.assertNotIn('_apkpyHideKeyboard', java)
        self.assertNotIn('_apkpyShowKeyboard', java)
        self.assertNotIn('setOnEditorActionListener', java)

    def test_a_field_of_another_screen_is_not_looked_for(self):
        files = _build('home = Screen(id="home")\nother = Screen(id="other")\n'
                       'name = inputs("Name", screen=home)\n'
                       'button("Go", command=lambda: name.focus(), screen=other)\n')
        self.assertNotIn('_apkpyShowKeyboard(findViewById', files['java/Screen_otherActivity.java'])

    def test_the_apps_own_hide_keyboard_is_the_apps(self):
        files = _build('home = Screen(id="home")\n'
                       'def hide_keyboard():\n    toast("mine")\n'
                       'button("Go", command=hide_keyboard, screen=home)\n')
        java = files['java/Screen_homeActivity.java']
        self.assertNotIn('_apkpyHideKeyboard', java)
        self.assertIn('"mine"', java)

    def test_the_field_the_keyboard_opens_over_is_kept_in_sight(self):
        # Seen on the phone (14-11-2026, targetSdk 36, edge to edge): a field low
        # on a scrolling screen stayed under the keyboard, and so did the next
        # one "next" moved to. onCreate now asks for it, on a screen with a field.
        on_create = self.java.split('protected void onCreate(')[1].split('\n    }\n')[0]
        self.assertIn('_apkpyKeepFieldAboveKeyboard();', on_create)
        helper = self.java.split('private void _apkpyKeepFieldAboveKeyboard() {')[1].split('\n    }\n')[0]
        self.assertIn('addOnGlobalLayoutListener', helper)
        self.assertIn('addOnGlobalFocusChangeListener', helper)      # "next" is no layout
        self.assertIn('WindowInsetsCompat.Type.ime()', helper)
        for body in ('home = Screen(id="home")\nlabel("x", screen=home)\n',
                     'home = Screen(id="home")\ninputs("On", type="switch", screen=home)\n'):
            java = _build(body)['java/Screen_homeActivity.java']
            self.assertNotIn('_apkpyKeepFieldAboveKeyboard', java, body)

    def test_a_textarea_keeps_its_new_line(self):
        self.assertEqual(self.fields[-1].get('inputType'), 'textMultiLine')
        self.assertNotIn('imeOptions', self.fields[-1])

    def test_every_layout_reads(self):
        for name, value in self.files.items():
            if name.endswith('.xml') and isinstance(value, str):
                ET.fromstring(value)

    def test_what_the_build_refuses(self):
        for body in ('inputs("Notes", type="textarea", on_submit=print, screen=home)\n',
                     'inputs("Notes", type="textarea", action="send", screen=home)\n',
                     'inputs("A", action="sned", screen=home)\n',
                     'kind = "send"\ninputs("A", action=kind, screen=home)\n',
                     'inputs("A", autofill="mail", screen=home)\n',
                     'inputs("On", type="switch", autofill="email", screen=home)\n',
                     'def f(a, b):\n    pass\ninputs("A", on_submit=f, screen=home)\n',
                     'inputs("A", on_submit=lambda a, b: None, screen=home)\n',
                     'on = inputs("On", type="switch", screen=home)\n'
                     'def f():\n    on.focus()\nbutton("x", command=f, screen=home)\n',
                     'def f():\n    hide_keyboard(1)\nbutton("x", command=f, screen=home)\n'):
            self.assertIn(rules.CODE, _refusal(body), body)

    def test_the_compiler_knows_the_new_arguments(self):
        error = _refusal('inputs("A", type="email", action="go", autofill="email", '
                         'on_submit=lambda: None, screen=home)\n')
        self.assertEqual(error, '')


class ThePreviewer(unittest.TestCase):

    def _last_focus(self, p):
        root = p.app.root
        return str(root.tk.call('focus', '-lastfor', root))

    def _press_enter(self, p, entry):
        entry.focus_force()
        p.settle(0.05)
        entry.event_generate('<Return>')
        p.settle(0.1)

    def test_the_fields_keep_their_keyboard(self):
        with Previewed(APP, '') as p:
            email = p.ns['email']
            self.assertEqual(email.kwargs['input_type'], 'text')
            self.assertEqual(email.kwargs['keyboard'], 'email')
            self.assertEqual(email.kwargs['ime_action'], 'next')
            self.assertEqual(p.ns['query'].kwargs['ime_action'], 'search')
            self.assertEqual(p.ns['message'].kwargs['ime_action'], 'send')

    def test_enter_runs_on_submit_with_the_text(self):
        with Previewed(APP, '') as p:
            entry = p.widget('message')
            entry.focus_force()
            p.settle(0.05)
            entry.delete(0, 'end')
            entry.insert(0, 'hello')
            self._press_enter(p, entry)
            self.assertEqual(p.ns['SEEN'], ['hello'])
            self.assertEqual(self._last_focus(p), str(entry))          # send keeps the keyboard

    def test_next_moves_to_the_next_field(self):
        with Previewed(APP, '') as p:
            self._press_enter(p, p.widget('email'))
            self.assertEqual(self._last_focus(p), str(p.widget('phone')))

    def test_a_field_with_no_action_moves_on_as_android_does(self):
        with Previewed(APP, '') as p:
            self._press_enter(p, p.widget('phone'))
            self.assertEqual(self._last_focus(p), str(p.widget('site')))

    def test_search_takes_the_cursor_out(self):
        with Previewed(APP, '') as p:
            self._press_enter(p, p.widget('query'))
            self.assertEqual(p.ns['SEEN'], ['searched'])
            self.assertEqual(self._last_focus(p), '.')

    def test_the_phone_field_takes_the_dial_pad(self):
        with Previewed(APP, '') as p:
            entry = p.widget('phone')
            entry.focus_force()
            p.settle(0.05)
            for keysym in ('1', '2', 'a', 'plus', 'b', '3'):
                entry.event_generate('<KeyPress>', keysym=keysym)
            p.settle(0.1)
            self.assertEqual(entry.get(), '12+3')

    def test_hide_keyboard_and_focus(self):
        with Previewed(APP, '') as p:
            p.ns['message'].focus()
            p.settle(0.05)
            self.assertEqual(self._last_focus(p), str(p.widget('message')))
            p.ns['find']()
            p.settle(0.05)
            self.assertEqual(self._last_focus(p), '.')

    def test_focus_before_the_screen_is_drawn(self):
        with Previewed('home = Screen(id="home")\nname = inputs("Name", screen=home)\n'
                       'notes = inputs("Notes", type="textarea", screen=home)\nnotes.focus()\n', '') as p:
            self.assertEqual(self._last_focus(p), str(p.widget('notes')))

    def test_a_fields_text_is_the_phones_size(self):
        # 13px here and 18sp on the phone (an EditText's own size) until 14-11-2026.
        import tkinter.font as tkfont
        with Previewed('home = Screen(id="home")\nname = inputs("Name", screen=home)\n'
                       'small = inputs("Small", id="small", screen=home)\n'
                       'on = inputs("On", type="checkbox", screen=home)\n',
                       'small {\n    font-size: 12px;\n}') as p:
            def size(widget):
                return tkfont.Font(font=widget.cget('font')).cget('size')

            def written(px):     # what the Previewer makes of font-size: Npx
                return tkfont.Font(font=ui._build_tk_font({'font-size': '%dpx' % px})).cget('size')
            self.assertEqual(size(p.widget('name')), written(rules.EDIT_TEXT_SIZE))
            self.assertEqual(size(p.widget('small')), written(12))
            self.assertNotEqual(written(rules.EDIT_TEXT_SIZE), written(13))

    def test_hide_keyboard_before_the_app_opens_no_window(self):
        ui._app._instance = None
        ui.hide_keyboard()
        self.assertIsNone(ui._app._instance)

    def test_what_the_previewer_refuses(self):
        from apkpy_lib import Screen, inputs
        home = Screen(id="kb_refusals")
        for bad in (dict(type='textarea', on_submit=print), dict(action='sned'),
                    dict(autofill='mail'), dict(type='switch', autofill='email'),
                    dict(on_submit=lambda a, b: None)):
            with self.assertRaises(ApkpyError) as caught:
                inputs('x', screen=home, **bad)
            self.assertEqual(caught.exception.code, rules.CODE)
        switch = inputs('On', type='switch', screen=home)
        with self.assertRaises(ApkpyError):
            switch.focus()


class InsideABackgroundJob(unittest.TestCase):
    """None of these can run without a screen. They read "not translated yet"
    (J7005) and named the internal command ("keyboard.call()"); the Previewer
    ran them."""

    def test_the_build_names_what_was_written(self):
        for body, said in (('hide_keyboard()', 'hide_keyboard()'),
                           ('name.focus()', 'name.focus()'),
                           ('name.set_error("x")', 'name.set_error()'),
                           ('validate(name)', 'validate()'),
                           ('pad.clear()', 'pad.clear()')):
            error = _refusal('name = inputs("Name", screen=home)\npad = draw_pad(screen=home)\n'
                             'def work():\n    %s\n' % body +
                             'job = background_job("sync", run=work)\n'
                             'button("Go", command=lambda: job.enqueue(), screen=home)\n')
            self.assertIn('J7004', error, body)
            self.assertIn('%s cannot run inside a background job' % said, error, body)

    def test_the_previewer_refuses_the_same(self):
        from apkpy_lib import Screen, draw_pad, hide_keyboard, inputs, validate
        from apkpy_lib import job_rules
        home = Screen(id="kb_jobs")
        name = inputs("Name", required=True, screen=home)
        pad = draw_pad(screen=home)
        for call in (hide_keyboard, name.focus, lambda: name.set_error("x"),
                     lambda: validate(name), name.validate, pad.clear):
            with job_rules.running_job():
                with self.assertRaises(ApkpyError) as caught:
                    call()
            self.assertEqual(caught.exception.code, 'J7004')


if __name__ == '__main__':
    unittest.main()
