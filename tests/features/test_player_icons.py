# -*- coding: utf-8 -*-
"""A music player drawn with icons, as every player is.

``audio.controls``, ``audio.like_button`` and the mini-player used to write
their state as text with emoji: "▶ Play", "⏸ Pausa", "🔀 Shuffle: ON",
"❤️"/"🤍", and a bare "⏸" on the mini-player. The Previewer drew the emoji as
empty circles, some phones as colour emoji, and the texts were half in
Portuguese. An icon button (an icon, no text) bound to one of them now swaps
Material icons -- play_arrow and pause, shuffle and repeat lit in the
button's ``active-color``, favorite_border and favorite -- and a text button
keeps its words, in English.
"""

import unittest

from apkpy_lib import ui
from apkpy_lib.core.compiler import translate_python_to_android


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


ICON_PLAYER = (
    'home = Screen(id="home")\n'
    'p = button("", id="play", icon="play_arrow", describe="Play", screen=home)\n'
    's = button("", id="shuf", icon="shuffle", describe="Shuffle", screen=home)\n'
    'r = button("", id="rep", icon="repeat", describe="Repeat", screen=home)\n'
    'h = button("", id="heart", icon="favorite_border", describe="Like", screen=home)\n'
    'audio.controls(play_pause=p, shuffle=s, repeat=r)\n'
    'audio.like_button(h)\n'
    'button("Start", id="go", screen=home,\n'
    '       command=lambda: audio.play_playlist(["a.mp3"], titles=["A"]))\n'
)
ICON_CSS = 'shuf { active-color: #1ED760; }\nrep { active-color: #1ED760; }\nheart { active-color: #FF3040; }'


class IconButtonsOnThePhone(unittest.TestCase):

    def setUp(self):
        self.files = _build(ICON_PLAYER, ICON_CSS)
        self.java = _java(self.files)

    def _drawables(self, suffix):
        return [k for k in self.files
                if k.startswith('res/drawable/ic_btn_') and k.endswith(suffix + '.xml')]

    def test_every_state_has_its_own_vector(self):
        for suffix in ('_play', '_pause', '_on', '_off', '_all', '_one',
                       '_liked', '_unliked'):
            self.assertTrue(self._drawables(suffix), suffix)

    def test_a_lit_state_is_drawn_in_the_active_colour(self):
        on = self.files[self._drawables('_on')[0]]
        self.assertIn('#1ED760', on.upper())
        liked = self.files[self._drawables('_liked')[0]]
        self.assertIn('#FF3040', liked.upper())

    def test_the_activity_swaps_icons_and_writes_no_text(self):
        self.assertIn('_acPlay).setIcon(', self.java)
        self.assertIn('_acShuf).setIcon(', self.java)
        self.assertIn('_acRep).setIcon(', self.java)
        self.assertIn('_likeBtn).setIcon(', self.java)
        for gone in ('_acPlay.setText', '_acShuf.setText', '_acRep.setText',
                     '_likeBtn.setText'):
            self.assertNotIn(gone, self.java)

    def test_the_repeat_one_state_uses_its_own_glyph(self):
        self.assertRegex(self.java, r'_rm == 2 \? R\.drawable\.ic_btn_\w+_one')


class TextButtonsKeepTheirWords(unittest.TestCase):

    def test_the_default_words_are_english_and_plain(self):
        java = _java(_build(
            'home = Screen(id="home")\n'
            'p = button("Play", id="play", screen=home)\n'
            's = button("Shuffle", id="shuf", screen=home)\n'
            'h = button("Like", id="heart", screen=home)\n'
            'audio.controls(play_pause=p, shuffle=s)\n'
            'audio.like_button(h)\n'))
        self.assertIn('"Pause"', java)
        self.assertIn('"Shuffle: on"', java)
        self.assertIn('"Liked"', java)
        for emoji in ('⏸', '▶', '🔀', '🔁', '❤', '🤍', '"Pausa"', 'Repeat: tudo'):
            self.assertNotIn(emoji, java)


class ShuffleAndRepeatDoSomething(unittest.TestCase):
    """audio.controls wired the play/pause click and left shuffle and repeat
    doing nothing unless the app wrote command=audio.shuffle -- which the
    media guide's own example does not. Found tapping them on a phone."""

    def test_the_phone_toggles_them(self):
        java = _java(_build(ICON_PLAYER, ICON_CSS))
        self.assertIn('_acShuf.setOnClickListener', java)
        self.assertIn('_ci.setAction("apkpy.SHUFFLE")', java)
        self.assertIn('_ci.setAction("apkpy.REPEAT")', java)

    def test_a_command_of_its_own_is_kept(self):
        java = _java(_build(
            'home = Screen(id="home")\n'
            'def mine():\n'
            '    toast("mine")\n'
            's = button("", id="shuf", icon="shuffle", describe="Shuffle", screen=home, command=mine)\n'
            'audio.controls(shuffle=s)\n'))
        self.assertNotIn('_ci.setAction("apkpy.SHUFFLE")', java)

    def test_the_previewer_toggles_them(self):
        class Button:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
        audio = ui.AudioAPI()
        shuffle, repeat = Button(icon='shuffle'), Button(icon='repeat', command=print)
        audio.controls(shuffle=shuffle, repeat=repeat)
        self.assertEqual(shuffle._dynamic_command, audio.shuffle)
        self.assertFalse(hasattr(repeat, '_dynamic_command'))


class TheIconVariant(unittest.TestCase):
    """``button("Play", variant="icon", icon="play_arrow")`` -- how the media
    guide writes a player -- draws the icon alone, so it swaps icons too."""

    BODY = ('home = Screen(id="home")\n'
            'p = button("Play", variant="icon", icon="play_arrow", screen=home)\n'
            'audio.controls(play_pause=p)\n')

    def test_on_the_phone(self):
        java = _java(_build(self.BODY))
        self.assertIn('_acPlay).setIcon(', java)
        self.assertNotIn('_acPlay.setText', java)

    def test_in_the_previewer(self):
        class Fake:
            kwargs = {'icon': 'play_arrow', 'text': 'Play', 'variant': 'icon'}
        self.assertTrue(ui._is_icon_button(Fake()))


class AnIconAloneIsATouchTarget(unittest.TestCase):
    """Centring the icon took the button's padding and minimum away, and a
    button with no size in the stylesheet shrank to its 20dp icon: Onda's
    profile button was a 20x32dp sliver on a phone. It is a 48dp square now,
    as the Previewer draws it; a size the stylesheet gives still wins."""

    def _button_xml(self, css=''):
        files = _build('home = Screen(id="home")\n'
                       'bar = container(id="bar", screen=home)\n'
                       'button("", id="me", icon="person", variant="icon", parent=bar)\n'
                       'button("Save", id="save", parent=bar)\n',
                       'bar { display: flex; flex-direction: row; }\n' + css)
        xml = files['res/layout/activity_screen_home.xml']
        buttons = xml.split('<Button')[1:]
        return buttons[0].split('/>')[0], buttons[1].split('/>')[0]

    def test_with_no_size_it_is_48dp_square(self):
        icon, _text = self._button_xml()
        self.assertIn('android:minWidth="48dp"', icon)
        self.assertIn('android:minHeight="48dp"', icon)
        self.assertIn('android:padding="0dp"', icon)

    def test_a_size_from_the_stylesheet_wins(self):
        icon, _text = self._button_xml('me { width: 32px; height: 32px; }')
        self.assertIn('android:layout_width="32dp"', icon)
        self.assertIn('android:layout_height="32dp"', icon)
        self.assertNotIn('48dp', icon)

    def test_a_button_with_words_keeps_hugging_them(self):
        _icon, text = self._button_xml()
        self.assertIn('android:minWidth="0dp"', text)
        self.assertNotIn('48dp', text)

    def test_the_previewer_draws_the_same_square(self):
        from apkpy_lib.core.features import accessibility
        self.assertEqual(ui._material_button_height(18, compact=True),
                         accessibility.MIN_TOUCH_DP)
        # min-height: 40px is the height on the phone (android:minHeight
        # with nothing taller inside), so it is here too.
        self.assertEqual(ui._material_button_height(18, compact=True, min_height=40), 40)


class AFixedHeightLeavesRoomForTheWords(unittest.TestCase):
    """MaterialButton keeps 4dp of padding above and below its words, and a
    34dp "Edit profile" button cut the bottom of its letters on a phone
    (27-09-2026). A height from the stylesheet drops that padding; a button
    that sizes itself keeps it."""

    def _save_xml(self, css=''):
        files = _build('home = Screen(id="home")\n'
                       'button("Save", id="save", screen=home)\n', css)
        xml = files['res/layout/activity_screen_home.xml']
        return xml.split('<Button')[1].split('/>')[0]

    def test_a_fixed_height_drops_the_padding_above_and_below(self):
        button = self._save_xml('save { height: 34px; }')
        self.assertIn('android:layout_height="34dp"', button)
        self.assertIn('android:paddingTop="0dp"', button)
        self.assertIn('android:paddingBottom="0dp"', button)

    def test_a_button_that_sizes_itself_keeps_it(self):
        for css in ('', 'save { height: auto; }', 'save { height: 100%; }'):
            with self.subTest(css=css):
                self.assertNotIn('android:paddingTop="0dp"', self._save_xml(css))


class NoPlayerNoExtraIcons(unittest.TestCase):

    def test_an_icon_button_of_an_app_without_a_player_gets_one_vector(self):
        # The like check compared None with None for a button kept in no
        # variable, and gave Onda's icon button two stray heart vectors.
        files = _build('home = Screen(id="home")\n'
                       'button("", id="go", icon="add", describe="Add", screen=home)\n')
        vectors = [k for k in files if k.startswith('res/drawable/ic_btn_')]
        self.assertEqual(len(vectors), 1, vectors)


class TheMiniPlayer(unittest.TestCase):

    def test_play_and_pause_are_icons(self):
        files = _build(
            'home = Screen(id="home")\n'
            'player = Screen(id="player")\n'
            'label("Home", screen=home)\n'
            'label("Now playing", screen=player)\n'
            'mini_player(open=player)\n')
        self.assertIn('res/drawable/apkpy_mp_play.xml', files)
        self.assertIn('res/drawable/apkpy_mp_pause.xml', files)
        layouts = ''.join(v for k, v in files.items() if k.startswith('res/layout'))
        self.assertIn('@drawable/apkpy_mp_pause', layouts)
        self.assertNotIn('⏸', layouts)
        java = _java(files)
        self.assertIn('R.drawable.apkpy_mp_play', java)
        self.assertNotIn('⏸', java)


class TheMiniPlayerHasAStylesheet(unittest.TestCase):
    """It could only follow the theme: a light app had a light bar over a
    dark player screen (the Spotify replica, on a phone, 26-09-2026)."""

    BODY = ('home = Screen(id="home")\n'
            'player = Screen(id="player")\n'
            'label("Home", screen=home)\n'
            'mini_player(open=player, id="mini")\n')

    def test_the_shared_rule(self):
        from apkpy_lib import theme
        tokens = {'surface': '#FFFBFE', 'text': '#1D1B20', 'text_secondary': '#49454F'}
        self.assertEqual(theme.mini_player_colors(tokens),
                         ('#FFFBFE', '#1D1B20', '#49454F'))
        self.assertEqual(theme.mini_player_colors(tokens, {
            'background-color': '#2A1E24', 'color': '#FFFFFF', 'subtitle-color': '#B3B3B3'}),
            ('#2A1E24', '#FFFFFF', '#B3B3B3'))
        self.assertEqual(theme.mini_player_colors({}), ('#181818', '#FFFFFF', '#B3B3B3'))

    def test_the_phone_draws_what_the_stylesheet_says(self):
        files = _build(self.BODY, 'mini { background-color: #2A1E24; color: #FFFFFF;'
                                  ' subtitle-color: #B3B3B3; }')
        layout = files['res/layout/activity_screen_home.xml']
        bar = layout[layout.index('apkpy_miniplayer'):]
        self.assertIn('android:background="#2A1E24"', bar)
        self.assertIn('android:textColor="#FFFFFF"', bar)
        self.assertIn('android:textColor="#B3B3B3"', bar)
        self.assertIn('#FFFFFF', files['res/drawable/apkpy_mp_play.xml'].upper())

    def test_the_type_selector_works_too(self):
        files = _build(self.BODY.replace(', id="mini"', ''),
                       'mini_player { background-color: #2A1E24; }')
        self.assertIn('android:background="#2A1E24"', files['res/layout/activity_screen_home.xml'])


class ThePreviewerAgrees(unittest.TestCase):

    def test_an_icon_button_is_one_with_an_icon_and_no_words(self):
        class Fake:
            def __init__(self, **kw):
                self.kwargs = kw
        self.assertTrue(ui._is_icon_button(Fake(icon='play_arrow', text='')))
        self.assertTrue(ui._is_icon_button(Fake(icon='play_arrow', text='  ')))
        self.assertFalse(ui._is_icon_button(Fake(icon='play_arrow', text='Play')))
        self.assertFalse(ui._is_icon_button(Fake(text='')))

    def test_the_previewer_defaults_match_the_phone(self):
        import inspect
        params = inspect.signature(ui.AudioAPI.controls).parameters
        self.assertEqual(params['pause_text'].default, 'Pause')
        self.assertEqual(params['repeat_all'].default, 'Repeat: all')
        like = inspect.signature(ui.AudioAPI.like_button).parameters
        self.assertEqual((like['liked'].default, like['unliked'].default),
                         ('Liked', 'Like'))


if __name__ == '__main__':
    unittest.main()
