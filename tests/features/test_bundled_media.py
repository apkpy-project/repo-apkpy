# -*- coding: utf-8 -*-
"""A music app with its own tracks and covers, on a phone.

The replicas went onto a phone (25-09-2026) and the Spotify screens were
empty where the Previewer was full:

* every cover of a ``grid()`` / ``carousel()`` shelf -- and of a rich
  ``list_view()`` row -- named a file in the app's folder. Nothing packaged
  it, and the phone looked for "cover1.png" as a file path;
* ``audio.play_playlist(["track1.wav", ...])`` and ``audio.play("song.mp3")``
  were never packaged either, and the media service opened the bare name: a
  player stuck at 0:00 with a play button that did nothing;
* the cover of the track playing (``arts=``) reached the mini-player and the
  now-playing view the same way.

Local files now go into ``res/raw`` (audio) and ``res/drawable`` (pictures),
named as the compiler names every picture, and the Activity and the media
service find them by that name. Three smaller things the same phone showed are
pinned here too: an avatar's ``describe=`` was dropped, a chat list's time
shrank to "2..." beside its badge, and a slider ignored ``accent-color``.
"""

import re
import unittest

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
    return ''.join(v for k, v in files.items() if k.endswith('.java'))


PLAYER = (
    'home = Screen(id="home")\n'
    'TRACKS = ["track1.wav", "Track 2.mp3"]\n'
    'ARTS = ["cover1.png", "https://example.com/c.png"]\n'
    'def go():\n'
    '    audio.play_playlist(TRACKS, titles=["A", "B"], arts=ARTS)\n'
    'button("Play", id="go", screen=home, command=go)\n'
    'grid([{"title": "Night", "subtitle": "x", "image": "shelf/cover2.png"}], id="g", screen=home)\n'
    'carousel([{"title": "Gold", "subtitle": "y", "image": "cover3.jpg"}], id="c", screen=home)\n'
    'mini_player(open=home)\n'
)


class PackagedWithTheApp(unittest.TestCase):

    def setUp(self):
        self.files = _build(PLAYER)

    def test_local_tracks_go_into_raw(self):
        self.assertEqual(self.files.get('res/raw/track1.wav'), ('COPY_FILE', 'track1.wav'))
        self.assertEqual(self.files.get('res/raw/track_2.mp3'), ('COPY_FILE', 'Track 2.mp3'))

    def test_local_covers_go_into_drawable_and_web_ones_do_not(self):
        for key, source in (('res/drawable/cover1.png', 'cover1.png'),
                            ('res/drawable/cover2.png', 'shelf/cover2.png'),
                            ('res/drawable/cover3.jpg', 'cover3.jpg')):
            self.assertEqual(self.files.get(key), ('COPY_FILE', source), key)
        self.assertFalse([k for k in self.files if k.startswith('res/drawable/c.')])

    def test_the_activity_and_the_service_find_them_by_name(self):
        java = _java(self.files)
        self.assertIn('private int _apkpyBundled(String source, String type)', java)
        self.assertIn('_apkpyBundled(url, "drawable")', java)
        self.assertIn('private int bundledRaw(String source)', java)
        self.assertIn('"android.resource://" + getPackageName()', java)

    def test_the_java_names_them_as_the_compiler_does(self):
        # _android_drawable_name: basename, no extension, lower case,
        # [a-z0-9_], "img_" before a leading digit. The Java has to agree.
        java = _java(self.files)
        helper = java[java.index('private int _apkpyBundled('):]
        helper = helper[:helper.index('    }')]
        self.assertIn("lastIndexOf('/')", helper)
        self.assertIn('lastIndexOf(92)', helper)
        self.assertIn('replaceAll("[^a-z0-9_]", "_")', helper)
        self.assertIn('"img_" + name', helper)


class PlayAfterTheLastTrack(unittest.TestCase):
    """A queue that ends stops the media service (stopSelf). Play then reached
    a new service with no queue and did nothing -- on a phone, after the
    three tracks of the replica had played."""

    def test_the_service_keeps_the_last_queue(self):
        java = _java(_build(PLAYER))
        service = java[java.index('public class ApkpyMediaService'):]
        self.assertIn('private static org.json.JSONArray sPlSrcs', service)
        resume = service[service.index('private void doResume()'):]
        resume = resume[:resume.index('\n    }\n')]
        self.assertIn('plSrcs = sPlSrcs;', resume)
        self.assertIn('playCurrent();', resume)

    def test_the_bar_goes_back_to_the_start(self):
        # It stayed at the end, and the time read "0:00 / 0:00".
        java = _java(_build(
            'home = Screen(id="home")\n'
            'bar = inputs("", type="range", id="progress", screen=home)\n'
            'clock = label("0:00", id="clock", screen=home)\n'
            'audio.now_playing(progress=bar, time=clock)\n'))
        self.assertIn('_npBar.setProgress(0);', java)
        self.assertIn('_npFmt(_dur > 0 ? _dur : _npLastDur)', java)

    def test_the_previewer_keeps_the_last_track_and_plays_it_again(self):
        from apkpy_lib import ui
        audio = ui.AudioAPI()
        played = []
        audio._play_current = lambda: played.append(audio._index)
        audio._has_mci = lambda: False
        audio._playlist, audio._order = ['a.mp3', 'b.mp3'], [0, 1]
        audio._index, audio._pos, audio._repeat = 1, 1, 0
        audio._cur_title = 'B'
        audio._advance()                       # the end of the queue
        self.assertEqual(audio._cur_title, 'B', 'the mini-player lost the track')
        audio.resume()
        self.assertEqual(played, [1])

    def test_shuffle_and_repeat_toggle_what_the_buttons_show(self):
        service = _java(_build(PLAYER))
        self.assertIn('sShuffle = !sShuffle;', service)
        self.assertIn('sRepeat = (sRepeat + 1) % 3;', service)


class TheLibrarysOwnWordsAreEnglish(unittest.TestCase):
    """confirm() said "Cancel" in the Previewer and "Cancelar" on the phone,
    and a radio with no options offered "Opção 1" on both."""

    def test_confirm_on_the_phone(self):
        java = _java(_build('home = Screen(id="home")\n'
                            'def done(ok):\n'
                            '    toast("x")\n'
                            'def ask():\n'
                            '    confirm("Delete?", "Sure?", on_result=done)\n'
                            'button("Go", screen=home, command=ask)\n'))
        self.assertIn('setNegativeButton("Cancel"', java)
        self.assertNotIn('Cancelar', java)

    def test_default_radio_options(self):
        files = _build('home = Screen(id="home")\ninputs("", type="radio", screen=home)\n')
        text = ''.join(v for v in files.values() if isinstance(v, str))
        self.assertIn('Option 1', text)
        self.assertNotIn('Opção', text)


class ClosingTheAppClosesAPausedPlayer(unittest.TestCase):
    """Swiped away from recents with the music paused, the app left its
    notification, its media session and the Xiaomi media island behind."""

    def setUp(self):
        java = _java(_build(PLAYER))
        self.service = java[java.index('public class ApkpyMediaService'):]

    def test_a_paused_player_goes_with_the_app(self):
        removed = self.service[self.service.index('public void onTaskRemoved'):]
        removed = removed[:removed.index('\n    }\n')]
        self.assertIn('if (!playing) doStop();', removed)

    def test_a_paused_notification_can_be_swiped_away_and_that_stops_it(self):
        pause = self.service[self.service.index('private void doPause()'):]
        pause = pause[:pause.index('\n    }\n')]
        self.assertIn('stopForeground(false);', pause)
        self.assertIn('setDeleteIntent(actionIntent("apkpy.STOP"))', self.service)


class AnAppWithoutLocalFilesIsUnchanged(unittest.TestCase):

    def test_no_helper(self):
        java = _java(_build('home = Screen(id="home")\nlabel("x", screen=home)\n'))
        self.assertNotIn('_apkpyBundled', java)


class WhatThePhoneShowed(unittest.TestCase):

    def test_an_avatar_is_described(self):
        files = _build('home = Screen(id="home")\n'
                       'avatar("face.png", size=62, id="ring", screen=home, describe="mara")\n')
        xml = ''.join(v for k, v in files.items() if k.startswith('res/layout'))
        self.assertIn('android:contentDescription="mara"', xml)

    def test_the_time_beside_a_badge_keeps_its_width(self):
        java = _java(_build(
            'home = Screen(id="home")\n'
            'virtual_collection([{"n": "Mara", "t": "21:42", "u": "2"}],\n'
            '    template={"title": "{n}", "meta": "{t}", "badge": "{u}"},\n'
            '    id="chats", screen=home)\n', 'chats { badge-position: end; }'))
        trail = java[java.index('if (!grid && badgeEnd) {'):]
        trail = trail[:trail.index('trail.addView(meta)')]
        self.assertRegex(trail, r'meta\.setLayoutParams\(new android\.widget\.LinearLayout\.LayoutParams\(\s*'
                                r'android\.view\.ViewGroup\.LayoutParams\.WRAP_CONTENT')

    def test_a_slider_takes_its_accent(self):
        files = _build('home = Screen(id="home")\n'
                       'inputs("", type="range", id="progress", screen=home)\n',
                       'progress { accent-color: #FFFFFF; }')
        xml = ''.join(v for k, v in files.items() if k.startswith('res/layout'))
        self.assertIn('android:thumbTint="#FFFFFF"', xml)
        self.assertIn('android:progressTint="#FFFFFF"', xml)

    def test_the_now_playing_bar_takes_its_accent_too(self):
        body = ('home = Screen(id="home")\n'
                'bar = inputs("", type="range", id="progress", screen=home)\n'
                'audio.now_playing(progress=bar)\n')
        java = _java(_build(body, 'progress { accent-color: #FFFFFF; }'))
        self.assertIn('_npThumb.setColor(android.graphics.Color.parseColor("#FFFFFF"))', java)
        self.assertNotIn('0xFF38BDF8', java)
        # Nothing said: the sky blue it always had.
        self.assertIn('_npThumb.setColor(0xFF38BDF8)', _java(_build(body)))

    def test_a_slider_without_one_is_unchanged(self):
        files = _build('home = Screen(id="home")\ninputs("", type="range", screen=home)\n')
        xml = ''.join(v for k, v in files.items() if k.startswith('res/layout'))
        self.assertNotIn('thumbTint', xml)


if __name__ == '__main__':
    unittest.main()
