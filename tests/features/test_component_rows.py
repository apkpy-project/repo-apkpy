# -*- coding: utf-8 -*-
"""Rows built from components: virtual_collection(items, row=post_row).

A virtual_collection row had fixed slots -- title, subtitle, image, meta,
badge -- enough for a chat list and nothing more. A feed post (header, photo,
actions, likes, caption), a comment or a product card could not be written,
so the Instagram replica built two posts by hand and could show no others.

``row=`` takes a function that builds one row from ordinary components. The
Previewer calls it once and draws a copy per item; the compiler expands it
once into a template on no screen, writes it as a layout of its own, and a
RecyclerView adapter fills each ``{field}`` from the item and hands the item
to the commands that take one. Checked on a phone (26-09-2026): four posts
from data, a square photo each, and the like button's toast names its post.
"""

import re
import unittest

from apkpy_lib import ui
from apkpy_lib.core.compiler import translate_python_to_android

try:
    from tests.features.test_real_screens import Previewed
except ImportError:                                      # run from tests/features
    from test_real_screens import Previewed


def _build(body, css=''):
    source = ('from apkpy_lib import *\n' + body +
              '\nstyle = """\n' + css + '\n"""\n' +
              'run(start_screen=home)\n')
    return translate_python_to_android(source)


def _java(files):
    return ''.join(v for k, v in files.items() if k.endswith('Activity.java'))


FEED = '''
home = Screen(id="home")
POSTS = [
    {"user": "mara", "face": "face2.png", "picture": "post1.jpg", "likes": "12"},
    {"user": "liv", "face": "https://example.com/liv.png", "picture": "post2.jpg", "likes": "8"},
]

def like(item):
    toast("liked " + item["user"])

def share():
    toast("share")

def post_row(row):
    head = container(id="head", parent=row)
    avatar("{face}", size=34, id="face", parent=head, describe="{user}")
    label("{user}", id="user", parent=head)
    image("{picture}", id="pic", parent=row, aspect_ratio="1:1", describe="")
    button("", id="like", icon="favorite_border", describe="Like", parent=row,
           command=lambda item: like(item))
    button("", id="send", icon="send", describe="Share", parent=row, command=share)
    button("", id="save", icon="bookmark_border", describe="Save", parent=row, command=like)
    label("{likes} likes", id="count", parent=row)

feed = virtual_collection(POSTS, row=post_row, id="feed", screen=home)
'''
CSS = 'feed_row { background-color: #FFFFFF; padding: 0px 0px 8px 0px; }\nface { border-radius: 17px; }'


class ThePhone(unittest.TestCase):

    def setUp(self):
        self.files = _build(FEED, CSS)
        self.assertNotIn('error.txt', self.files, self.files.get('error.txt', '')[:800])
        self.java = _java(self.files)
        self.row = self.files['res/layout/apkpy_row_home_vc1.xml']

    def test_the_row_is_a_layout_of_its_own(self):
        self.assertTrue(self.row.startswith('<?xml'))
        self.assertIn('<FrameLayout', self.row)
        # its components are not on the screen
        screen = self.files['res/layout/activity_screen_home.xml']
        self.assertNotIn('{user}', screen)
        self.assertIn('{user}', self.row)

    def test_a_field_picture_names_no_drawable(self):
        self.assertNotIn('@drawable/picture', self.row)
        self.assertNotIn('@drawable/face"', self.row)

    def test_the_adapter_fills_every_field_and_finds_every_view(self):
        setup = self.java[self.java.index('new ApkpyRowAdapter('):]
        setup = setup[:setup.index(';\n')]
        ids = re.findall(r'R\.id\.(\w+)', setup)
        for view in set(ids):
            self.assertIn('android:id="@+id/%s"' % view, self.row, view)
        for pattern in ('"{face}"', '"{user}"', '"{picture}"', '"{likes} likes"'):
            self.assertIn(pattern, setup)
        self.assertIn('R.layout.apkpy_row_home_vc1', setup)

    def test_a_command_gets_the_item_when_it_takes_one(self):
        setup = self.java[self.java.index('new ApkpyRowAdapter('):]
        setup = setup[:setup.index(';\n')]
        self.assertRegex(setup, r'_item -> pythonCallback_\w+_cmd\(_item\)')   # the lambda
        self.assertIn('_item -> pythonCallback_share()', setup)            # takes none
        self.assertIn('_item -> pythonCallback_like(_item)', setup)        # takes one

    def test_the_square_photo_keeps_its_ratio(self):
        self.assertRegex(self.java, r'new float\[\]\{1\.000000f\}')

    def test_the_class_is_written_once(self):
        self.assertEqual(self.java.count('private final class ApkpyRowAdapter'), 1)
        self.assertIn('private ApkpyRowAdapter vc1Adapter;', self.java)

    def test_local_pictures_ship_and_web_ones_do_not(self):
        for name in ('face2.png', 'post1.jpg', 'post2.jpg'):
            self.assertIn('res/drawable/%s' % name, self.files)
        self.assertFalse([k for k in self.files if 'liv' in k])
        manifest = self.files.get('AndroidManifest.xml', '')
        self.assertIn('android.permission.INTERNET', manifest)

    def test_the_row_itself_is_styled_by_its_id(self):
        self.assertIn('res/drawable/feed_row_shape.xml', self.files)
        self.assertIn('RoundedImg_face', self.files.get('res/values/image_shapes.xml', ''))


class WhatStaysTheSame(unittest.TestCase):

    def test_a_slot_collection_has_no_row_adapter(self):
        files = _build('home = Screen(id="home")\n'
                       'virtual_collection([{"title": "a"}], template={"title": "{title}"}, screen=home)\n')
        java = _java(files)
        self.assertNotIn('ApkpyRowAdapter', java)
        self.assertFalse([k for k in files if 'apkpy_row_' in k])


class Mistakes(unittest.TestCase):

    def test_a_row_function_takes_the_row_and_nothing_else(self):
        files = _build('home = Screen(id="home")\n'
                       'def two(row, extra):\n'
                       '    label("{title}", parent=row)\n'
                       'virtual_collection([{"title": "a"}], row=two, screen=home)\n')
        self.assertIn('U2038', files.get('error.txt', ''))

    def test_the_previewer_refuses_template_and_row_together(self):
        with self.assertRaises(ValueError):
            ui.virtual_collection([], template={"title": "{t}"}, row=lambda row: None)


class ThePreviewer(unittest.TestCase):

    def test_the_function_runs_once_and_its_result_is_the_template(self):
        calls = []

        def builder(row):
            calls.append(row)
            ui.label("{name}", parent=row)

        comp = ui.virtual_collection([{"name": "a"}, {"name": "b"}], row=builder, id="people")
        self.assertIsNone(comp)            # no screen: nothing to add it to
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].kwargs.get('comp_id'), 'people_row')

    def test_a_copy_per_item(self):
        template = ui.ComponentDef('container', comp_id='r')
        seen = []
        ui.label("{name} ({age})", parent=template)
        ui.button("", icon="favorite", parent=template, command=lambda item: seen.append(item))
        ui.button("", icon="send", parent=template, command=lambda t="fixed": seen.append(t))

        def fill(pattern, item):
            return re.sub(r'\{(\w+)\}', lambda m: str(item.get(m.group(1), '')), pattern)

        copy = ui._row_instance(template, {"name": "Ana", "age": 30}, fill)
        self.assertEqual(copy.children[0].kwargs['text'], 'Ana (30)')
        copy.children[1].kwargs['command']()
        copy.children[2].kwargs['command']()
        self.assertEqual(seen, [{"name": "Ana", "age": 30}, "fixed"])
        self.assertEqual(template.children[0].kwargs['text'], '{name} ({age})')

    def test_rows_are_drawn_one_under_the_other(self):
        body = ('home = Screen(id="home")\n'
                'def person(row):\n'
                '    label("{name}", id="who", parent=row)\n'
                '    label("{city}", id="where", parent=row)\n'
                'people = virtual_collection([{"name": "Ana", "city": "Porto"},\n'
                '                             {"name": "Rui", "city": "Faro"}],\n'
                '                            row=person, id="people", screen=home)\n')
        with Previewed(body, 'people { height: 400px; }') as p:
            p.settle(1.0)
            labels = [w for w in ui._see_walk(p.app.root)
                      if isinstance(w, ui.tk.Label) and w.winfo_ismapped()
                      and w.cget('text') in ('Ana', 'Porto', 'Rui', 'Faro')]
            tops = {w.cget('text'): w.winfo_rooty() for w in labels}
            self.assertEqual(set(tops), {'Ana', 'Porto', 'Rui', 'Faro'})
            self.assertLess(tops['Ana'], tops['Porto'])
            self.assertLess(tops['Porto'], tops['Rui'], 'the second row was drawn over the first')

    def test_new_items_draw_new_rows(self):
        body = ('home = Screen(id="home")\n'
                'def person(row):\n'
                '    label("{name}", id="who", parent=row)\n'
                'people = virtual_collection([{"name": "Ana"}], row=person, id="people", screen=home)\n')
        with Previewed(body, 'people { height: 300px; }') as p:
            p.settle(0.6)
            p.ns['people'].set_items([{"name": "Rui"}, {"name": "Eva"}])
            p.settle(0.8)
            shown = {w.cget('text') for w in ui._see_walk(p.app.root)
                     if isinstance(w, ui.tk.Label) and w.winfo_ismapped()}
            self.assertIn('Rui', shown)
            self.assertIn('Eva', shown)
            self.assertNotIn('Ana', shown)


class StatePerRow(unittest.TestCase):
    """A row changes after it is drawn: the heart of a liked post is red.

    ``visible="{field}"`` shows a component only when the item's field is on,
    ``active="{field}"`` lights a button's ``active_icon`` in its
    ``active-color``, and ``update_item(id, {...})`` patches one item and
    draws its row again. What counts as off is data_rules.FIELD_OFF, on both
    runtimes."""

    def test_the_shared_rule(self):
        from apkpy_lib.data_rules import field_is_on
        for off in ('', 'false', 'False', '0', 'no', 'off', 'none', 'null', None, False, 0, '  '):
            self.assertFalse(field_is_on(off), repr(off))
        for on in ('yes', 'true', '1', 'x', True, 1, 12):
            self.assertTrue(field_is_on(on), repr(on))

    def test_the_phone_reads_the_same_values(self):
        from apkpy_lib.data_rules import FIELD_OFF
        files = _build(FEED.replace('icon="favorite_border", describe="Like"',
                                    'icon="favorite_border", active_icon="favorite", '
                                    'active="{liked}", describe="Like"'), CSS)
        java = _java(files)
        self.assertIn('new String[]{%s}' % ', '.join('"%s"' % v for v in FIELD_OFF), java)

    def test_a_lit_button_has_its_own_vector_in_the_active_colour(self):
        body = FEED.replace('icon="favorite_border", describe="Like"',
                            'icon="favorite_border", active_icon="favorite", '
                            'active="{liked}", describe="Like"')
        files = _build(body, CSS + '\nlike { active-color: #FF3040; }')
        active = [k for k in files if k.endswith('_active.xml')]
        self.assertEqual(len(active), 1, active)
        self.assertIn('#FF3040', files[active[0]].upper())
        setup = _java(files)
        setup = setup[setup.index('new ApkpyRowAdapter('):]
        self.assertIn('new String[]{"{liked}"}', setup)
        self.assertIn('R.drawable.' + active[0].split('/')[-1][:-4], setup)

    def test_visible_hides_a_view_on_the_phone(self):
        body = FEED.replace('label("{user}", id="user", parent=head)',
                            'label("{user}", id="user", parent=head)\n'
                            '    label("Sponsored", id="ad", parent=head, visible="{sponsored}")')
        setup = _java(_build(body, CSS))
        setup = setup[setup.index('new ApkpyRowAdapter('):]
        self.assertIn('"visible"', setup)
        self.assertIn('"{sponsored}"', setup)

    def test_row_views_have_names_of_their_own(self):
        files = _build(FEED, CSS)
        row = files['res/layout/apkpy_row_home_vc1.xml']
        ids = re.findall(r'android:id="@\+id/(\w+)"', row)
        self.assertTrue(ids)
        self.assertTrue(all(i.startswith('apkpy_row_home_vc1_') for i in ids), ids)

    def test_a_copy_honours_visible_and_active(self):
        template = ui.ComponentDef('container', comp_id='r')
        ui.label("Sponsored", parent=template, visible="{ad}")
        ui.button("", icon="favorite_border", active_icon="favorite", active="{liked}",
                  parent=template)

        def fill(pattern, item):
            return re.sub(r'\{(\w+)\}', lambda m: str(item.get(m.group(1), '')), pattern)

        plain = ui._row_instance(template, {"ad": "", "liked": ""}, fill)
        self.assertEqual([c.comp_type for c in plain.children], ['button'])
        self.assertIsNone(getattr(plain.children[0], '_dynamic_icon', None))
        lit = ui._row_instance(template, {"ad": "yes", "liked": "yes"}, fill)
        self.assertEqual([c.comp_type for c in lit.children], ['label', 'button'])
        self.assertEqual(lit.children[1]._dynamic_icon, 'favorite')

    def test_update_item_draws_the_row_again(self):
        body = ('home = Screen(id="home")\n'
                'def person(row):\n'
                '    label("{name}", id="who", parent=row)\n'
                '    label("online", id="dot", parent=row, visible="{online}")\n'
                'people = virtual_collection([{"id": "a", "name": "Ana", "online": "yes"}],\n'
                '                            row=person, id="people", screen=home)\n')
        with Previewed(body, 'people { height: 300px; }') as p:
            p.settle(0.6)

            def shown():
                return {w.cget('text') for w in ui._see_walk(p.app.root)
                        if isinstance(w, ui.tk.Label) and w.winfo_ismapped()}
            self.assertIn('online', shown())
            p.ns['people'].update_item("a", {"online": ""})
            p.settle(0.6)
            self.assertNotIn('online', shown())
            self.assertIn('Ana', shown())


class MutationsOnThePhone(unittest.TestCase):

    def test_append_and_set_items_reach_the_row_adapter(self):
        files = _build('home = Screen(id="home")\n'
                       'def person(row):\n'
                       '    label("{name}", id="who", parent=row)\n'
                       'people = virtual_collection([{"name": "Ana"}], row=person, screen=home)\n'
                       'def more():\n'
                       '    people.append_items([{"name": "Rui"}])\n'
                       'button("More", screen=home, command=more)\n')
        self.assertNotIn('error.txt', files, files.get('error.txt', '')[:600])
        java = _java(files)
        self.assertIn('private ApkpyRowAdapter vc1Adapter;', java)
        self.assertRegex(java, r'vc1Adapter\.notify\w+\(')


if __name__ == '__main__':
    unittest.main()


class TheAuditLooksInsideRows(unittest.TestCase):
    """U2035 walked a screen's components and their children, and a row's
    components live beside those, in the collection's row template: a feed's
    heart with no describe= was never reported."""

    @staticmethod
    def _audit(row_body):
        import contextlib
        import io as _io
        source = (
            'from apkpy_lib import *\n'
            'home = Screen(id="home")\n'
            'def post(row):\n'
            + row_body +
            'virtual_collection([{"id": "a"}], row=post, id="feed", screen=home)\n'
            'run(start_screen=home)\n')
        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            translate_python_to_android(source)
        return buffer.getvalue()

    def test_an_icon_without_words_in_a_row_is_reported(self):
        found = self._audit('    button("", icon="favorite_border", id="like", parent=row)\n')
        self.assertIn('U2035', found)
        self.assertIn('home.like', found)

    def test_a_described_row_is_left_alone(self):
        found = self._audit('    button("", icon="favorite_border", id="like", '
                            'describe="Like", parent=row)\n')
        self.assertNotIn('home.like', found)
