# -*- coding: utf-8 -*-
"""Screens as the well-known apps draw them, on both runtimes.

Rebuilding WhatsApp, Spotify, Instagram and Uber a second time (25-09-2026),
looking at every pixel, turned up the places where a real app could not be
written -- or looked wrong only on the desktop, where people judge ApkPy:

* A composer's rounded pill measured 19px (its own text, before its buttons
  were placed) and never learnt it was 50: sizes travelled up only when the
  *width* changed. The pill also stayed as wide as its content with
  ``flex-grow: 1``, leaving a hole before the send button.
* A label in a ``display: flex`` row had 8px each side and a doubled
  margin-top on the desktop; the phone gives it none.
* "Music" wrapped to "Musi / c" in a chip: the width was rounded down.
* A field with a background but no border kept the Material underline in the
  Previewer; on the phone a shape drawable replaces it.
* Content started under the Previewer's status strip, and ``height: 100%``
  was measured on the whole window.
* The clock was dark on a dark screen in a light app, on both runtimes.
* ``margin: 4px 14px 0px 14px`` on a label wrote layout_marginTop twice --
  AAPT refuses that -- and the label indent missed its left side.
* Grid and carousel cards were white on the phone whatever the stylesheet
  said, and the body's text colour on the desktop.
* A chat list's unread count sat under the message instead of under the time.
* Anything transparent over a picture was a black box in the Previewer.
"""

import os
import re
import time
import tkinter as tk
import unittest

import __main__

from apkpy_lib import theme, ui
from apkpy_lib.core.compiler import translate_python_to_android

_MISSING = object()


def _build(body, css=''):
    source = ('from apkpy_lib import *\n' + body +
              '\nstyle = """\n' + css + '\n"""\n' +
              'run(start_screen=home)\n')
    files = translate_python_to_android(source)
    if not files or 'error.txt' in files:
        raise AssertionError((files or {}).get('error.txt', 'no output')[:600])
    return files


def _java(files):
    return ''.join(v for k, v in files.items() if k.endswith('Activity.java'))


def _layouts(files):
    return {k: v for k, v in files.items() if k.startswith('res/layout/')}


class Previewed:
    """Render ``body`` in a real Previewer, invisible, and let it settle."""

    def __init__(self, body, css, screen='home'):
        self.body, self.css, self.screen = body, css, screen

    def __enter__(self):
        self._old_style = getattr(__main__, 'style', _MISSING)
        __main__.style = self.css
        ui._app._instance = None
        try:
            self.app = ui._app._get()
        except tk.TclError as exc:
            raise unittest.SkipTest(str(exc))
        root = self.app.root
        root.attributes('-alpha', 0.0)
        root.geometry('411x914+-3000+0')
        self.ns = {}
        try:
            exec('from apkpy_lib import *\n' + self.body, self.ns)
            ui.load_styles_now()
            self.app.render_screen(self.ns[self.screen])
            self.settle()
        except BaseException:
            # A body that stops half way leaves its window open, and every
            # fixture after it then fails on an image of the wrong window --
            # which reads as a skip, not as a failure.
            self.__exit__()
            raise
        return self

    def settle(self, seconds=0.6):
        end = time.time() + seconds
        while time.time() < end:
            self.app.root.update()
            time.sleep(0.01)

    def until(self, condition, seconds=6.0):
        """Run the Previewer until condition() is true, for at most *seconds*,
        and answer what it last said. A fixed settle() lost the race on a
        busy machine: Play's update sheet was not up after 0.5 s."""
        end = time.time() + seconds
        while True:
            self.app.root.update()
            found = condition()
            if found or time.time() >= end:
                return found
            time.sleep(0.01)

    def widget(self, comp):
        return self.ns[comp].widget if isinstance(comp, str) else comp.widget

    def __exit__(self, *exc):
        try:
            self.app.root.destroy()
        finally:
            ui._app._instance = None
            if self._old_style is _MISSING:
                try:
                    del __main__.style
                except AttributeError:
                    pass
            else:
                __main__.style = self._old_style
        return False


def _box(widget):
    return (widget.winfo_rootx(), widget.winfo_rooty(),
            widget.winfo_width(), widget.winfo_height())


COMPOSER = (
    'home = Screen(id="home")\n'
    'composer = container(id="composer", screen=home)\n'
    'pill = container(id="pill", parent=composer)\n'
    'button("", id="emoji", icon="mood", describe="Emoji", parent=pill)\n'
    'message = inputs("Message", id="message", parent=pill)\n'
    'button("", id="attach", icon="attach_file", describe="Attach", parent=pill)\n'
    'send = button("", id="send", icon="send", describe="Send", parent=composer)\n'
)
COMPOSER_CSS = '''
home { background-color: #0B141A; padding: 0px; }
composer { position: absolute; left: 6px; right: 6px; bottom: 6px;
           display: flex; flex-direction: row; align-items: center; gap: 6px;
           background-color: #00000000; padding: 0px; }
pill { flex-grow: 1; display: flex; flex-direction: row; align-items: center; gap: 0px;
       background-color: #202C33; border-radius: 26px; padding: 0px 4px; }
emoji, attach { width: 48px; height: 48px; background-color: #00000000; }
message { flex-grow: 1; background-color: #00000000; border-width: 0px; color: #E9EDEF; }
send { width: 50px; height: 50px; border-radius: 25px; background-color: #21C063; }
'''


class TheComposer(unittest.TestCase):

    def test_the_pill_is_as_tall_as_its_buttons_and_reaches_the_send_button(self):
        with Previewed(COMPOSER, COMPOSER_CSS) as p:
            pill = p.widget('pill')
            # The container's widget is the frame inside its rounded panel.
            while not isinstance(pill, tk.Canvas):
                pill = pill.master
            send = p.widget('send')
            px, py, pw, ph = _box(pill)
            sx, _sy, _sw, _sh = _box(send)
            self.assertGreaterEqual(ph, 44, 'the pill kept its first, text-only height')
            # gap: 6px between the pill and the send button, not a hole.
            self.assertLessEqual(sx - (px + pw), 12)

    def test_a_field_with_a_background_has_no_underline(self):
        with Previewed(COMPOSER, COMPOSER_CSS) as p:
            entry = p.widget('message')
            lines = [w for w in entry.master.winfo_children()
                     if isinstance(w, tk.Frame) and w.winfo_ismapped()
                     and int(w.cget('height') or 0) in (1, 2)]
            self.assertEqual(lines, [])


class RowsOfWords(unittest.TestCase):

    CHIPS = ('home = Screen(id="home")\n'
             'row = container(id="chips", screen=home)\n'
             'button("All", id="chip", parent=row)\n'
             'music = button("Music", id="chip2", parent=row)\n'
             'groups = button("Groups", id="chip3", parent=row)\n'
             'cap = container(id="cap", screen=home)\n'
             'user = label("mara.vale", id="cap_user", parent=cap)\n'
             'text = label("Last light", id="cap_text", parent=cap)\n')
    CSS = '''
home { background-color: #121212; padding: 16px; }
chips { display: flex; flex-direction: row; justify-content: flex-start; gap: 8px; padding: 0px; }
chip, chip2, chip3 { border-radius: 16px; font-size: 13px; text-transform: none;
                     height: 32px; padding: 0px 14px; }
cap { display: flex; flex-direction: row; justify-content: flex-start; gap: 6px; padding: 0px; }
cap_user { font-size: 14px; font-weight: bold; }
cap_text { font-size: 14px; }
'''

    def test_a_chip_is_one_line(self):
        with Previewed(self.CHIPS, self.CSS) as p:
            for name in ('music', 'groups'):
                canvas = [w for w in ui._see_walk(p.widget(name).master)
                          if isinstance(w, tk.Canvas)][0]
                texts = [canvas.itemcget(i, 'text') for i in canvas.find_all()
                         if canvas.type(i) == 'text']
                self.assertTrue(texts, name)
                self.assertNotIn('\n', ''.join(texts), name)

    def test_labels_in_a_row_have_no_padding_of_their_own(self):
        with Previewed(self.CHIPS, self.CSS) as p:
            user, text = p.widget('user'), p.widget('text')
            self.assertEqual(int(user.cget('padx')), 0)
            ux, _uy, uw, _uh = _box(user)
            tx = text.winfo_rootx()
            self.assertLessEqual(tx - (ux + uw), 8)

    def test_the_row_starts_below_the_status_strip(self):
        with Previewed(self.CHIPS, self.CSS) as p:
            chip = p.widget('music')
            self.assertGreaterEqual(chip.winfo_rooty() - p.app.root.winfo_rooty(),
                                    ui._STATUS_STRIP_HEIGHT + 16)


class LabelsInAColumn(unittest.TestCase):

    def test_margin_left_is_measured_from_the_edge_as_on_the_phone(self):
        body = ('home = Screen(id="home")\n'
                'a = label("1284 likes", id="likes", screen=home)\n'
                'b = label("plain", id="plain", screen=home)\n')
        css = 'home { padding: 0px; }\nlikes { margin-left: 14px; }'
        with Previewed(body, css) as p:
            likes, plain = p.widget('a'), p.widget('b')
            self.assertEqual(int(likes.cget('padx')), 0)
            self.assertEqual(likes.winfo_rootx() - p.app.root.winfo_rootx(), 14)
            self.assertEqual(int(plain.cget('padx')), 16)
        xml = ''.join(_layouts(_build(body, css)).values())
        likes_xml = xml[xml.rfind('<TextView', 0, xml.find('1284 likes')):xml.find('1284 likes')]
        self.assertIn('layout_marginLeft="14dp"', likes_xml)
        self.assertNotIn('paddingLeft', likes_xml)

    BOX = ('home = Screen(id="home")\n'
           'box = container(id="box", screen=home)\n'
           'a = label("Spending", id="title", parent=box)\n'
           'b = label("$486.20", id="value", parent=box)\n'
           'c = label("Wide", id="wide", parent=box)\n')
    BOX_CSS = ('home { padding: 0px; }\n'
               'box { padding: 0px; background-color: #FFFFFF; }\n'
               'value { padding: 0px; }\n'
               'wide { padding: 4px 24px 2px 8px; }')

    def test_its_own_padding_replaces_the_indent(self):
        # "$486.20" with padding: 0px sat 16 right of "Spending" in the
        # same card, on both runtimes (Lumen, 14-11-2026).
        with Previewed(self.BOX, self.BOX_CSS) as p:
            left = p.app.root.winfo_rootx()
            title, value, wide = p.widget('a'), p.widget('b'), p.widget('c')
            self.assertEqual(int(title.cget('padx')), 16)
            self.assertEqual(int(value.cget('padx')), 0)
            self.assertEqual(value.winfo_rootx() - left, 0)
            self.assertEqual(int(wide.cget('padx')), 0)
            self.assertEqual(wide.winfo_rootx() - left, 8)
        xml = ''.join(_layouts(_build(self.BOX, self.BOX_CSS)).values())

        def view(text):
            return xml[xml.rfind('<TextView', 0, xml.find(text)):xml.find(text)]
        self.assertIn('paddingLeft="16dp"', view('Spending'))
        self.assertIn('paddingLeft="0dp" android:paddingRight="0dp"', view('$486.20'))
        self.assertIn('paddingLeft="8dp" android:paddingRight="24dp"', view('Wide'))
        self.assertIn('paddingTop="4dp" android:paddingBottom="2dp"', view('Wide'))

    def test_a_pill_in_a_column_keeps_its_padding(self):
        body = ('home = Screen(id="home")\n'
                'label("NEW", id="tag", screen=home)\n')
        css = ('home { padding: 0px; }\n'
               'tag { background-color: #EEEBFF; border-radius: 12px; padding: 5px 12px; }')
        xml = ''.join(_layouts(_build(body, css)).values())
        tag = xml[xml.rfind('<TextView', 0, xml.find('NEW')):xml.find('NEW')]
        # Left and right are the stylesheet's; top and bottom stay with the
        # shape drawable, which carries the same numbers.
        self.assertIn('paddingLeft="12dp" android:paddingRight="12dp"', tag)
        self.assertNotIn('paddingTop', tag)
        for tag_match in re.finditer(r'<([\w.]+)\b([^>]*)>', xml, re.S):
            attrs = re.findall(r'([\w:]+)="', tag_match.group(2))
            self.assertEqual(len(attrs), len(set(attrs)), tag_match.group(1))


class TheMarginShorthand(unittest.TestCase):

    def test_no_attribute_is_written_twice(self):
        files = _build(
            'home = Screen(id="home")\n'
            'label("First", id="first", screen=home)\n'
            'label("View all 48 comments", id="more", screen=home)\n'
            'image("a.png", id="cover", screen=home, describe="")\n',
            'more { margin: 4px 14px 0px 14px; }\ncover { margin: 18px 0px 20px 0px; }')
        for name, xml in _layouts(files).items():
            for tag in re.finditer(r'<([\w.]+)\b([^>]*)>', xml, re.S):
                attrs = re.findall(r'([\w:]+)="', tag.group(2))
                self.assertEqual(len(attrs), len(set(attrs)), (name, tag.group(1)))
        xml = ''.join(_layouts(files).values())
        more = xml[xml.rfind('<TextView', 0, xml.find('View all')):xml.find('View all')]
        # 4px of its own plus the 6dp between stacked views; the left side
        # counts as a margin-left, so no 16dp indent.
        self.assertIn('layout_marginTop="10dp"', more)
        self.assertIn('layout_marginLeft="14dp"', more)
        self.assertNotIn('paddingLeft', more)

    def test_a_negative_margin_counts_as_zero_on_both_sides(self):
        # Northline's "8 places in 7 countries" with margin: -8px 0px 16px
        # 0px closed the Previewer ("bad pad value") and was +8dp on the
        # phone: the sign was dropped.
        body = ('home = Screen(id="home")\n'
                'label("Saved", id="title", screen=home)\n'
                'note = label("8 places", id="note", screen=home)\n'
                'tip = label("Tap a place", id="tip", screen=home)\n')
        css = ('note { margin: -8px 0px 16px 0px; }\n'
               'tip { margin-top: -4px; margin-left: -10px; }')
        with Previewed(body, css) as p:
            self.assertTrue(p.widget('note').winfo_exists())
            self.assertEqual(ui._parse_margin({'margin': '-8px 0px 16px 0px'}), (0, 0, 16, 0))
            self.assertEqual(ui._parse_margin({'margin-left': '-10px'}), (0, 0, 0, 0))
        xml = ''.join(_layouts(_build(body, css)).values())
        note = xml[xml.rfind('<TextView', 0, xml.find('8 places')):xml.find('8 places')]
        tip = xml[xml.rfind('<TextView', 0, xml.find('Tap a place')):xml.find('Tap a place')]
        self.assertNotIn('layout_marginTop="8dp"', note)
        self.assertNotIn('layout_marginTop="2dp"', note)
        self.assertIn('layout_marginBottom="16dp"', note)
        self.assertNotIn('layout_marginLeft="10dp"', tip)


class TheStatusBarReadsAgainstTheScreen(unittest.TestCase):

    def test_the_shared_rule(self):
        self.assertEqual(theme.system_icon_color('#0B141A'), '#FFFFFF')
        self.assertEqual(theme.system_icon_color('#FFFFFF'), '#1D1B20')

    def test_the_activity_reads_the_colour_behind_the_clock(self):
        java = _java(_build('home = Screen(id="home")\nlabel("x", screen=home)\n',
                            'home { background-color: #0B141A; }'))
        self.assertIn('_apkpySystemIconsFollowBackground();', java)
        self.assertIn('setAppearanceLightStatusBars(_light)', java)
        self.assertIn('> %s;' % theme.LIGHT_SURFACE_LUMINANCE, java)

    def test_the_previewer_clock_is_light_on_a_dark_screen(self):
        body = 'home = Screen(id="home")\nlabel("x", screen=home)\n'
        with Previewed(body, 'home { background-color: #0B141A; }') as p:
            self.assertEqual(p.app._status_clock.cget('fg').upper(), '#FFFFFF')


class PercentHeights(unittest.TestCase):

    def test_full_height_ends_at_the_bottom_of_the_screen(self):
        self.assertEqual(ui._resolve_css_size_tk('100%', 'height'),
                         ui._style_viewport[1] - ui._STATUS_STRIP_HEIGHT)
        self.assertEqual(ui._resolve_css_size_tk('100%', 'width'), ui._style_viewport[0])


class CardsOnAShelf(unittest.TestCase):

    BODY = ('home = Screen(id="home")\n'
            'grid([{"title": "Night Drive", "subtitle": "Mara", "image": ""}], id="shelf", screen=home)\n'
            'carousel([{"title": "Gold Hour", "subtitle": "Mix", "image": ""}], id="mixes", screen=home)\n')

    def test_the_shared_rule(self):
        self.assertEqual(theme.card_text_colors({}), ('#FFFFFF', '#B3B3B3'))
        self.assertEqual(theme.card_text_colors({'color': '#111111'}), ('#111111', '#B3B3B3'))
        self.assertEqual(theme.card_text_colors({'title-color': '#222222', 'color': '#111111',
                                                 'subtitle-color': '#333333'}),
                         ('#222222', '#333333'))

    def test_the_phone_paints_what_the_stylesheet_says(self):
        java = _java(_build(self.BODY, 'shelf { title-color: #123456; subtitle-color: #654321; }'))
        self.assertIn('_t.setTextColor(android.graphics.Color.parseColor("#123456"))', java)
        self.assertIn('_sub.setTextColor(android.graphics.Color.parseColor("#654321"))', java)
        # The carousel was not styled: the old white and grey.
        self.assertIn('_t.setTextColor(android.graphics.Color.parseColor("#FFFFFF"))', java)

    def test_the_body_colour_does_not_reach_a_card(self):
        java = _java(_build(self.BODY, 'body { color: #1D1B20; }'))
        self.assertNotIn('parseColor("#1D1B20")); _t.setTextSize', java)


CHATS = ('home = Screen(id="home")\n'
         'virtual_collection([{"name": "Mara", "last": "Yes!", "time": "21:42", "unread": "2"}],\n'
         '    template={"avatar": "{name}", "title": "{name}", "subtitle": "{last}",\n'
         '              "meta": "{time}", "badge": "{unread}"},\n'
         '    id="chats", item_height="auto", screen=home)\n')


class TheUnreadCount(unittest.TestCase):

    def test_the_shared_rule(self):
        self.assertTrue(theme.badge_at_end({'badge-position': 'end'}))
        self.assertFalse(theme.badge_at_end({}))

    def test_the_phone_puts_it_under_the_time(self):
        java = _java(_build(CHATS, 'chats { badge-position: end; }'))
        self.assertIn('Adapter.setBadgeEnd(true);', java)
        self.assertIn('trail.addView(meta); trail.addView(badge);', java)

    def test_an_app_that_does_not_ask_keeps_its_adapter(self):
        java = _java(_build(CHATS))
        self.assertNotIn('badgeEnd', java)

    def test_the_previewer_puts_it_under_the_time_and_round(self):
        with Previewed(CHATS, 'chats { badge-position: end; height: 300px; }') as p:
            badges = [w for w in ui._see_walk(p.app.root) if isinstance(w, ui._PillBadge)
                      and w.cget('text') == '2' and w.winfo_ismapped()]
            self.assertTrue(badges)
            badge = badges[0]
            meta = [w for w in badge.master.winfo_children()
                    if isinstance(w, tk.Label) and w.cget('text') == '21:42']
            self.assertTrue(meta, 'the badge is not beside the time')
            self.assertGreater(badge.winfo_rooty(), meta[0].winfo_rooty())
            self.assertEqual(badge.winfo_width(), badge.winfo_height())


class SeeThroughOverAPicture(unittest.TestCase):

    BODY = ('home = Screen(id="home")\n'
            'stage = container(id="stage", screen=home)\n'
            'img = image(PICTURE, id="pic", parent=stage, describe="")\n'
            'close = button("", id="close", icon="close", describe="Close", parent=stage)\n'
            'hint = label("Tap for the next one", id="hint", parent=stage)\n')
    CSS = '''
home { background-color: #000000; padding: 0px; }
stage { position: relative; width: 100%; height: 400px; background-color: #000000; padding: 0px; }
pic { width: 100%; height: 100%; object-fit: cover; }
close { position: absolute; right: 8px; top: 8px; width: 48px; height: 48px;
        background-color: #00000000; icon-color: #FFFFFF; }
hint { position: absolute; left: 0px; right: 0px; bottom: 20px; color: #FFFFFF; text-align: center; }
'''

    def setUp(self):
        from PIL import Image
        import tempfile
        self.folder = tempfile.mkdtemp()
        picture = os.path.join(self.folder, 'pic.png')
        Image.new('RGB', (200, 200), (230, 120, 60)).save(picture)
        self.body = 'PICTURE = %r\n' % picture.replace(os.sep, '/') + self.BODY

    def test_a_transparent_button_and_label_show_the_picture(self):
        with Previewed(self.body, self.CSS) as p:
            p.settle(1.0)
            close = p.widget('close')
            canvas = [w for w in ui._see_walk(close.master if not isinstance(close, tk.Canvas) else close)
                      if isinstance(w, tk.Canvas)][0]
            self.assertTrue(canvas.find_withtag('apkpy_see'),
                            'the button kept its black square')
            hint = p.widget('hint')
            self.assertTrue(str(hint.cget('image')), 'the caption kept its black strip')

    def test_words_placed_over_it_are_as_wide_as_their_text(self):
        # Onda's hero (14-11-2026): a column at left/top only over a picture,
        # in an app with a Theme, was 25px wide for good -- "DAILY CALM" read
        # "DAIL" and "Morning reset" read "M". The slot's stale width capped
        # what its content asked for, so it could never grow.
        body = ('from apkpy_lib import ui as _ui\n'
                '_theme = Theme(mode="light")\n'
                '_ui._active_theme = _theme\n'
                '_ui._declared_theme[0] = _theme\n'
                'home = Screen(id="home")\n'
                'hero = container(id="hero", screen=home)\n'
                'image(PICTURE, id="art", parent=hero, describe="")\n'
                'words = container(id="words", parent=hero)\n'
                'kicker = label("DAILY CALM", id="kicker", parent=words)\n'
                'title = label("Morning reset", id="title", parent=words)\n')
        css = '''
home { padding: 20px; }
hero { position: relative; height: 230px; padding: 0px; }
art { width: 100%; height: 100%; object-fit: cover; }
words { position: absolute; left: 22px; top: 22px; display: flex;
        flex-direction: column; align-items: flex-start; background-color: #00000000; }
title { font-size: 26px; font-weight: bold; }
'''
        source = self.body[:self.body.index('\n') + 1] + body
        # The Theme stays declared after the window closes; its body's 12px
        # gap then moved every Previewer test that came after this one.
        saved = (ui._active_theme, ui._declared_theme[0])

        def _restore():
            ui._active_theme, ui._declared_theme[0] = saved
        self.addCleanup(_restore)
        with Previewed(source, css) as p:
            p.settle(1.0)
            for name in ('kicker', 'title'):
                text = p.widget(name)
                slot = text.master.master
                self.assertGreaterEqual(slot.winfo_width(), text.winfo_reqwidth(), name)

    def test_a_transparent_button_draws_no_body(self):
        with Previewed(self.body, self.CSS) as p:
            close = p.widget('close')
            canvas = [w for w in ui._see_walk(close.master if not isinstance(close, tk.Canvas) else close)
                      if isinstance(w, tk.Canvas)][0]
            registry = canvas.__dict__.get('_apkpy_aa') or {}
            fills = [entry[0].get('fill') for entry in registry.values()]
            self.assertNotIn('#000000', [str(f).lower() for f in fills])


class TheAuditOverAPicture(unittest.TestCase):
    """White words over a photo were reported at 1.07:1 against the page
    (Northline's hero, 14-11-2026): what is behind them is the picture, and
    no colour stands for it."""

    STYLES = """
        home { background-color: #F6F7F9; }
        hero { position: relative; height: 300px; }
        words { position: absolute; left: 20px; bottom: 20px; background-color: #00000000; }
        title { color: #FFFFFF; font-size: 30px; }
        pill { position: absolute; top: 16px; left: 16px; color: #FFFFFF; background-color: #FFFFFF; }
        loose { color: #FFFFFF; }
    """

    def _found(self, children):
        from apkpy_lib.core.compiler import _audit_accessibility
        from apkpy_lib.core.style_parser import _parse_style_blocks
        styles = dict(_parse_style_blocks(self.STYLES))
        screens = {"home": [{"comp_type": "container", "id": "hero", "children": children},
                            {"comp_type": "label", "id": "loose", "text": "Below"}]}
        return {where: text for _, where, text in _audit_accessibility(screens, styles)}

    def test_words_over_the_picture_are_not_measured_against_the_page(self):
        found = self._found([
            {"comp_type": "image", "id": "art", "src": "a.jpg", "describe": ""},
            {"comp_type": "container", "id": "words",
             "children": [{"comp_type": "label", "id": "title", "text": "Porto"}]},
        ])
        self.assertNotIn("home.title", found)
        # The same white anywhere else on the page is still reported.
        self.assertIn("home.loose", found)

    def test_a_pill_over_the_picture_is_measured_on_its_own_fill(self):
        found = self._found([
            {"comp_type": "image", "id": "art", "src": "a.jpg", "describe": ""},
            {"comp_type": "label", "id": "pill", "text": "In 21 days"},
        ])
        self.assertIn("home.pill", found)

    def test_without_a_picture_the_words_are_measured(self):
        found = self._found([
            {"comp_type": "container", "id": "words",
             "children": [{"comp_type": "label", "id": "title", "text": "Porto"}]},
        ])
        self.assertIn("home.title", found)


if __name__ == '__main__':
    unittest.main()
