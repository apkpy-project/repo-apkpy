# -*- coding: utf-8 -*-
"""Things the desktop did and the phone did not.

Each of these transpiled without a word of complaint, which is what made them
expensive: the app worked in front of you and was wrong on the device, and
nothing in between said so.
"""

import re
import unittest

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.style_parser import KNOWN_PROPERTIES
from apkpy_lib.theme import has_responsive_styles


def _build(body, imports, css='', theme='mode="dark", motion="standard"'):
    source = (
        'from apkpy_lib import Screen, Theme, app_bar, run, ' + imports + '\n'
        'home = Screen(id="home")\n'
        'detalhe = Screen(id="detalhe")\n'
        'app_bar("T", screen=home)\n'
        + body + '\n'
        'run(start_screen=home, theme=Theme(' + theme + '))\n'
        'style = """\n' + css + '\n"""\n'
    )
    files = translate_python_to_android(source)
    if not files or 'error.txt' in files:
        raise AssertionError((files or {}).get('error.txt', 'no output')[:400])
    return files


class HidingAContainerReachesThePhone(unittest.TestCase):
    """The layout always had @+id/cntN. Nobody wrote the name down."""

    BODY = (
        'painel = container(id="painel", screen=home)\n'
        'label("dentro", id="l1", parent=painel)\n'
        'def alternar():\n'
        '    painel.hide()\n'
        'button("fechar", id="b", screen=home, command=alternar)'
    )

    def test_the_container_is_addressed_by_its_layout_id(self):
        files = _build(self.BODY, 'container, label, button')
        java = files['java/Screen_homeActivity.java']
        xml = files['res/layout/activity_screen_home.xml']
        used = set(re.findall(r'R\.id\.(cnt\d+)', java))
        self.assertTrue(used, 'the container was never referenced')
        for name in used:
            self.assertIn('@+id/%s' % name, xml)

    def test_the_two_passes_number_containers_the_same_way(self):
        # The Java pass and the layout pass count containers independently.
        # If they ever walk the tree differently, hide() addresses the wrong
        # box -- which is worse than doing nothing.
        body = (
            'primeiro = container(id="primeiro", screen=home)\n'
            'label("a", id="l0", parent=primeiro)\n'
            + self.BODY
        )
        files = _build(body, 'container, label, button')
        java = files['java/Screen_homeActivity.java']
        self.assertIn('R.id.cnt2', java)      # painel is the second container
        self.assertNotIn('R.id.cnt1', java)

    def test_markdown_can_be_hidden_too(self):
        body = (
            'primeiro = markdown("# um", id="m1", screen=home)\n'
            'doc = markdown("# dois", id="m2", screen=home)\n'
            'def esconder():\n'
            '    doc.hide()\n'
            'button("x", id="b", screen=home, command=esconder)'
        )
        files = _build(body, 'markdown, button')
        self.assertIn('R.id.rich2', files['java/Screen_homeActivity.java'])

    def test_an_app_that_hides_nothing_is_untouched(self):
        plain = _build('container(id="painel", screen=home)', 'container')
        self.assertNotIn(
            '_apkpySetVisible', plain['java/Screen_homeActivity.java'])


class EveryNavigateFormCarriesTheTransition(unittest.TestCase):
    """The published examples all use the form that dropped it."""

    TAIL = 'label("d", id="d", screen=detalhe)\n'

    def test_the_method_form(self):
        files = _build(
            self.TAIL
            + 'b = button("ir", id="b", screen=home)\n'
            + 'home.on_click_navigate(button=b, to=detalhe,'
              ' transition="slide")',
            'label, button')
        self.assertIn('overrideActivityTransition',
                      files['java/Screen_homeActivity.java'])

    def test_the_method_form_also_writes_the_animations_it_points_at(self):
        # Emitting R.anim.apkpy_slide_enter without the file is a build
        # failure, not a missing animation.
        files = _build(
            self.TAIL
            + 'b = button("ir", id="b", screen=home)\n'
            + 'home.on_click_navigate(button=b, to=detalhe,'
              ' transition="slide")',
            'label, button')
        self.assertIn('res/anim/apkpy_slide_enter.xml', files)
        self.assertIn('res/anim/apkpy_slide_exit.xml', files)

    def test_the_lambda_form(self):
        files = _build(
            self.TAIL
            + 'button("ir", id="b", screen=home,'
              ' command=lambda: on_click_navigate(detalhe,'
              ' transition="slide"))',
            'label, button, on_click_navigate')
        self.assertIn('overrideActivityTransition',
                      files['java/Screen_homeActivity.java'])

    def test_the_statement_form(self):
        files = _build(
            self.TAIL
            + 'def ir():\n'
            + '    on_click_navigate(detalhe, transition="slide")\n'
            + 'button("ir", id="b", screen=home, command=ir)',
            'label, button, on_click_navigate')
        self.assertIn('overrideActivityTransition',
                      files['java/Screen_homeActivity.java'])

    def test_no_transition_asked_means_no_animation_shipped(self):
        files = _build(
            self.TAIL
            + 'b = button("ir", id="b", screen=home)\n'
            + 'home.on_click_navigate(button=b, to=detalhe)',
            'label, button')
        self.assertEqual(
            [name for name in files if name.startswith('res/anim/')], [])
        self.assertNotIn('overrideActivityTransition',
                         files['java/Screen_homeActivity.java'])


class TransitionCascadesLikeEveryOtherProperty(unittest.TestCase):
    """It was the only one read from the id block alone."""

    BODY = (
        'alvo = label("a", id="aviso", screen=home)\n'
        'def f():\n'
        '    alvo.hide()\n'
        'button("x", id="b", screen=home, command=f)'
    )

    def _ms(self, css):
        java = _build(self.BODY, 'label, button', css)[
            'java/Screen_homeActivity.java']
        found = re.findall(
            r'_apkpySetVisible\(R\.id\.\w+, \w+, (\d+)L\)', java)
        return int(found[0]) if found else None

    def test_the_three_levels_agree(self):
        self.assertEqual(self._ms('aviso { transition: 400ms; }'), 400)
        self.assertEqual(self._ms('label { transition: 400ms; }'), 400)
        self.assertEqual(self._ms('body { transition: 400ms; }'), 400)

    def test_the_id_still_wins_over_the_type(self):
        self.assertEqual(
            self._ms('label { transition: 400ms; } '
                     'aviso { transition: 90ms; }'), 90)

    def test_without_a_declaration_the_preset_decides(self):
        self.assertEqual(self._ms(''), 180)


class LayoutVariantsCostSomething(unittest.TestCase):
    """Four extra layout files for a property that does nothing."""

    def _layouts(self, css):
        files = _build(
            'b = container(id="box", screen=home)\n'
            'label("a", id="l1", parent=b)', 'container, label', css)
        # _build declares two screens, so count only this screen's variants.
        return len([n for n in files
                    if n.startswith('res/layout')
                    and n.endswith('activity_screen_home.xml')])

    def test_an_inert_property_buys_nothing(self):
        self.assertEqual(self._layouts('l1 { min-width: 200px; }'), 1)

    def test_grid_tracks_without_a_grid_buy_nothing(self):
        self.assertEqual(
            self._layouts('box { grid-template-columns: 1fr 1fr; }'), 1)

    def test_a_real_grid_still_gets_its_variants(self):
        self.assertEqual(
            self._layouts('box { display: grid;'
                          ' grid-template-columns: 1fr 1fr; }'), 4)

    def test_the_properties_that_do_vary_still_get_them(self):
        self.assertEqual(self._layouts('l1 { max-width: 300px; }'), 4)
        self.assertEqual(self._layouts('l1 { min-height: 80px; }'), 4)

    def test_a_media_rule_still_gets_them(self):
        self.assertEqual(
            self._layouts('@media (max-width: 600px)'
                          ' { l1 { color: #000; } }'), 4)

    def test_the_responsive_trigger_only_names_readable_properties(self):
        # A property that triggers resource variants but that no renderer
        # reads is the exact shape of the bug this file is about.
        for name in ('max-width', 'min-height'):
            self.assertIn(name, KNOWN_PROPERTIES)
        self.assertFalse(
            has_responsive_styles({'x': {'min-width': '10px'}}, {'x'}))


class TheDrawerIsStyledOnBothSides(unittest.TestCase):
    """Four properties the Previewer read and the compiler did not."""

    BODY = (
        'label("b", id="lb", screen=detalhe)\n'
        'drawer([home, detalhe], labels=["Um", "Dois"],'
        ' icons=["home", "settings"], header="Ana", subtitle="ana@x.pt",'
        ' id="dw")'
    )

    def _files(self, css=''):
        return _build(self.BODY, 'drawer, label', css)

    def _changes(self, css):
        base = self._files()
        after = self._files(css)
        return sorted(name for name in set(base) | set(after)
                      if base.get(name) != after.get(name))

    def test_the_active_pill_takes_its_colour(self):
        self.assertIn('res/drawable/apkpy_drawer_item_bg.xml',
                      self._changes('dw { indicator-color: #ABCDEF; }'))

    def test_the_item_text_takes_its_size(self):
        self.assertIn('res/values/apkpy_drawer.xml',
                      self._changes('dw { item-size: 21px; }'))
        self.assertIn(
            '21sp',
            self._files('dw { item-size: 21px; }')[
                'res/values/apkpy_drawer.xml'])

    def test_the_header_hairline_takes_its_colour(self):
        self.assertIn('res/layout/apkpy_drawer_header.xml',
                      self._changes('dw { divider-color: #ABCDEF; }'))
        self.assertIn(
            '#ABCDEF',
            self._files('dw { divider-color: #ABCDEF; }')[
                'res/layout/apkpy_drawer_header.xml'])

    def test_the_navigation_view_points_at_both_new_resources(self):
        layout = self._files()['res/layout/activity_screen_home.xml']
        self.assertIn('app:itemBackground="@drawable/apkpy_drawer_item_bg"',
                      layout)
        self.assertIn('app:itemTextAppearance="@style/ApkpyDrawerItem"',
                      layout)

    def test_an_app_with_no_drawer_gains_none_of_it(self):
        plain = _build('label("x", id="x", screen=home)', 'label')
        for name in plain:
            self.assertNotIn('drawer', name)


class AMissingStorageKeyIsEmptyText(unittest.TestCase):
    """`"Last step: " + storage.get("k")` ran on the phone and raised here:
    Android answered "" for a key that was never written, the Previewer None."""

    def test_the_phone_answers_empty_text(self):
        files = _build(
            'out = label("", id="out", screen=home)\n'
            'def go():\n'
            '    out.set_value("Last: " + storage.get("never_written"))\n'
            'button("Go", id="b", screen=home, command=go)\n',
            'button, label, storage')
        self.assertIn('_apkpyStorageGet(String.valueOf("never_written"), '
                      'String.valueOf(""))',
                      files['java/Screen_homeActivity.java'])

    def test_the_previewer_answers_the_same(self):
        from apkpy_lib import storage
        self.assertEqual(storage.get("apkpy_test_never_written_key"), "")
        self.assertEqual("Last: " + storage.get("apkpy_test_never_written_key"),
                         "Last: ")

    def test_an_explicit_default_still_wins(self):
        from apkpy_lib import storage
        self.assertIsNone(storage.get("apkpy_test_never_written_key", None))
        self.assertEqual(storage.get("apkpy_test_never_written_key", "x"), "x")


if __name__ == '__main__':
    unittest.main()
