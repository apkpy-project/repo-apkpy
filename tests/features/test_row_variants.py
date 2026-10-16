# -*- coding: utf-8 -*-
"""Rows in one collection that are not all the same shape.

A collection drew every row identically, which is fine for a settings list and
wrong for a conversation: what you asked and what was answered are not the same
kind of thing. ``variant="{field}"`` picks the shape per row, and
``thread:name { }`` refines its look through the cascade the button and card
variants already use.

The row itself stays one set of views -- an unused slot goes away, which is
what an empty format string always did -- so this buys the difference without
buying a second ViewHolder.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.theme import component_style
from apkpy_lib.core.style_parser import parse_css
from apkpy_lib.ui import Screen, virtual_collection


TURNS = (
    '[{"state": "SENT", "author": "You", "message": "ola"},'
    ' {"state": "ORA", "author": "Ora", "message": "## oi"}]'
)

APP = (
    'from apkpy_lib import Screen, Theme, app_bar, virtual_collection, run\n'
    'home = Screen(id="home")\n'
    'app_bar("Chat", screen=home)\n'
    'TURNS = ' + TURNS + '\n'
    'virtual_collection(TURNS,\n'
    '%s'
    '    id="thread", item_height="auto", screen=home)\n'
    'run(start_screen=home, theme=Theme(mode="dark"))\n'
    'style = """\n%s\n"""\n'
)

WITH_VARIANTS = (
    '    variant="{state}",\n'
    '    template={"SENT": {"markdown": "{message}"},\n'
    '              "ORA": {"avatar": "{author}", "title": "{author}",\n'
    '                      "markdown": "{message}"}},\n'
)
WITHOUT = '    template={"title": "{author}", "markdown": "{message}"},\n'


def _java(body, css=''):
    files = translate_python_to_android(APP % (body, css))
    if not files or 'error.txt' in files:
        raise AssertionError((files or {}).get('error.txt', 'no output')[:400])
    return files['java/Screen_homeActivity.java']


class TheApiAcceptsTwoShapes(unittest.TestCase):

    def _make(self, **kwargs):
        return virtual_collection(
            [], id='thread', screen=Screen(id='s'), **kwargs)

    def test_the_union_decides_which_slots_exist(self):
        comp = self._make(
            variant='{role}',
            template={'user': {'markdown': '{message}'},
                      'assistant': {'avatar': '{author}',
                                    'markdown': '{message}'}},
        )
        used = {k for k, v in comp.kwargs['template'].items() if v}
        self.assertEqual(used, {'markdown', 'avatar'})

    def test_each_variant_keeps_only_its_own_slots(self):
        comp = self._make(
            variant='{role}',
            template={'user': {'markdown': '{message}'},
                      'assistant': {'avatar': '{author}',
                                    'markdown': '{message}'}},
        )
        user = {k for k, v in comp.kwargs['variants']['user'].items() if v}
        self.assertEqual(user, {'markdown'})

    def test_a_flat_template_still_works(self):
        comp = self._make(template={'title': '{author}'})
        self.assertEqual(comp.kwargs['variants'], {})
        self.assertIsNone(comp.kwargs['variant'])

    def test_a_variant_without_shapes_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            self._make(variant='{role}', template={'user': '{message}'})
        self.assertIn('dict of slots', str(caught.exception))

    def test_a_slot_that_does_not_exist_is_refused(self):
        # Silently dropping it is the bug this whole file is descended from.
        with self.assertRaises(ValueError) as caught:
            self._make(template={'titel': '{author}'})
        message = str(caught.exception)
        self.assertIn('titel', message)
        self.assertIn('Did you mean title?', message)


class TheStylesheetRefinesOneKindOfRow(unittest.TestCase):

    CSS = (
        'thread { item-background-color: #111111; title-color: #AAAAAA; }\n'
        'thread:SENT { item-background-color: #222222; }\n'
    )

    def _style(self, variant):
        styles, _ = parse_css(self.CSS)
        return component_style(
            styles, 'virtual_collection', 'thread', row_variant=variant)

    def test_the_variant_wins_over_the_id(self):
        self.assertEqual(
            self._style('SENT')['item-background-color'], '#222222')

    def test_it_still_inherits_what_it_does_not_change(self):
        self.assertEqual(self._style('SENT')['title-color'], '#AAAAAA')

    def test_an_undeclared_variant_falls_back(self):
        self.assertEqual(
            self._style('ORA')['item-background-color'], '#111111')


class TheGeneratedAdapterCarriesThem(unittest.TestCase):

    def test_the_variant_field_and_shapes_reach_java(self):
        java = _java(WITH_VARIANTS)
        self.assertIn('setVariants("{state}"', java)
        self.assertIn('_shapes.put("SENT"', java)
        self.assertIn('_shapes.put("ORA"', java)

    def test_the_per_variant_colour_reaches_java(self):
        java = _java(
            WITH_VARIANTS, 'thread:SENT { item-background-color: #2A2438; }')
        self.assertIn('#2A2438', java)

    def test_a_collection_without_variants_gains_nothing(self):
        java = _java(WITHOUT)
        for marker in ('setVariants', 'shapeFor', 'variantPattern'):
            self.assertNotIn(marker, java)

    def test_the_two_renderers_read_the_same_shapes(self):
        # The compiler parses the template out of the source text and the
        # Previewer builds it from the call. If those ever disagree, a row is
        # one shape on the desktop and another on the phone.
        comp = virtual_collection(
            [], id='thread', screen=Screen(id='s'),
            variant='{state}',
            template={'SENT': {'markdown': '{message}'},
                      'ORA': {'avatar': '{author}', 'title': '{author}',
                              'markdown': '{message}'}},
        )
        java = _java(WITH_VARIANTS)
        for name, shape in comp.kwargs['variants'].items():
            for slot, fmt in shape.items():
                if fmt:
                    self.assertIn(
                        '_shape_%s.put("%s", "%s");' % (name, slot, fmt), java,
                        '%s/%s' % (name, slot))


if __name__ == '__main__':
    unittest.main()
