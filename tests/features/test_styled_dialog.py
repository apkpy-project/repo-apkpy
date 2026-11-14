# -*- coding: utf-8 -*-
"""alert() and confirm() in the app's own style.

A ``dialog { ... }`` block (with dialog_title, dialog_message, dialog_ok and
dialog_cancel) turns the system's dialog into the app's card, on the phone
and in the Previewer, from one set of fallbacks (dialog_rules.look).
"""

import unittest

from apkpy_lib import dialog_rules as rules

from test_real_screens import _build, _java

_APP = ('home = Screen(id="home")\n'
        'def done(ok):\n'
        '    toast("ok")\n'
        'def leave():\n'
        '    confirm("Leave?", "You lose this session.", on_result=done, ok="Leave", cancel="Stay")\n'
        'def info():\n'
        '    alert("Saved", "All good.")\n'
        'button("Leave", id="go", command=leave, screen=home)\n'
        'button("Info", id="inf", command=info, screen=home)\n')

_CSS = ('dialog { background-color: #12121D; border-color: #333344; border-width: 1px;'
        ' border-radius: 28px; padding: 24px; }\n'
        'dialog_title { color: #F4F3FF; font-size: 22px; }\n'
        'dialog_ok { background-color: #FF6B81; color: #33060E; }\n'
        'dialog_cancel { background: linear-gradient(90deg, #111111, #222222); }\n')


class TheRules(unittest.TestCase):

    def test_only_a_dialog_block_turns_it_on(self):
        self.assertFalse(rules.wanted({}))
        self.assertFalse(rules.wanted({'dialog_ok': {'color': '#FFFFFF'}}))
        self.assertTrue(rules.wanted({'dialog': {'border-radius': '20px'}}))

    def test_fallbacks_come_from_the_theme(self):
        look = rules.look({'dialog': {'padding': '20px 12px'},
                           '__theme__': {'surface': '#15151F', 'primary': '#7C5CFF',
                                         'text': '#F4F4F8', 'text_secondary': '#9A9AB0'}})
        self.assertEqual(look['card']['background'], '#15151F')
        self.assertEqual(look['card']['padding'], 20)
        self.assertEqual(look['card']['radius'], 28)
        self.assertEqual(look['title']['color'], '#F4F4F8')
        self.assertEqual(look['message']['color'], '#9A9AB0')
        self.assertEqual(look['ok']['background'], '#7C5CFF')
        self.assertTrue(look['title']['bold'])
        self.assertFalse(look['message']['bold'])

    def test_the_card_keeps_its_margins(self):
        self.assertEqual(rules.width(411), 340)
        self.assertEqual(rules.width(360), 312)


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.styled = _java(_build(_APP, _CSS))
        cls.plain = _java(_build(_APP))

    def test_both_dialogs_go_through_the_card(self):
        self.assertIn('private void _apkpyStyledDialog(', self.styled)
        self.assertIn('_apkpyStyledDialog(title, message, ok != null ? ok : '
                      'getString(android.R.string.ok), null, null, null);', self.styled)
        self.assertIn('cancel != null ? cancel : getString(android.R.string.cancel),', self.styled)
        self.assertNotIn('new AlertDialog.Builder', self.styled)

    def test_the_card_wears_the_stylesheet(self):
        self.assertIn('_apkpyDialogShape(0xFF12121D);', self.styled)
        self.assertIn('shape.setCornerRadius(28.0f * dp);', self.styled)
        self.assertIn('shape.setStroke(Math.round(1.0f * dp), 0xFF333344);', self.styled)
        self.assertIn('heading.setTextColor(0xFFF4F3FF);', self.styled)
        self.assertIn('_apkpyDialogShape(0xFFFF6B81)', self.styled)
        self.assertIn('Orientation.LEFT_RIGHT, new int[]{0xFF111111, 0xFF222222}', self.styled)
        self.assertIn('window.setDimAmount(0.60f);', self.styled)

    def test_without_the_block_the_system_dialog_stays(self):
        self.assertNotIn('_apkpyStyledDialog', self.plain)
        self.assertIn('new AlertDialog.Builder', self.plain)


if __name__ == '__main__':
    unittest.main()
