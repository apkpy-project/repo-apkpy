"""A picture that opens over the whole screen and zooms.

`image(src, zoom=True)` and `view_image(src)` are drawn by the Previewer
and by ApkpyZoom on the phone. Where the picture sits, how far it zooms and
where a drag stops are one set of rules (apkpy_lib/zoom_rules.py); the last
class compiles the Java and asks it the same questions.
"""

import io
import os
import subprocess
import tempfile
import unittest

from PIL import Image

from apkpy_lib import zoom_rules as rules
from apkpy_lib.core.features import zoom as zoom_feature
from apkpy_lib.diagnostics import ApkpyError

from test_data_rules import TOOLING
from test_real_screens import Previewed, _build

HERE = tempfile.mkdtemp(prefix='apkpy-zoom-')
PHOTO = os.path.join(HERE, 'harbour.png').replace('\\', '/')
Image.new('RGB', (1200, 800), (40, 60, 120)).save(PHOTO)

APP = (
    'home = Screen(id="home")\n'
    'photo = image("%s", id="photo", zoom=True, describe="A harbour", screen=home)\n'
    'plain = image("%s", id="plain", screen=home)\n'
    'def open_it():\n'
    '    view_image("%s", describe="A harbour")\n'
    'button("Open", id="open", command=open_it, screen=home)\n'
) % (PHOTO, PHOTO, PHOTO)
CSS = 'photo, plain { width: 200px; height: 120px; object-fit: cover; }'


def _java(files, screen='home'):
    return files['java/Screen_%sActivity.java' % screen]


class TheSharedRules(unittest.TestCase):

    def test_fitted(self):
        self.assertEqual(rules.fit(1200, 800, 400, 800), 400 / 1200)       # by the width
        self.assertEqual(rules.fit(800, 1200, 400, 400), 400 / 1200)       # by the height
        self.assertEqual(rules.fit(0, 800, 400, 800), 0.0)
        # Fitted and centred: nothing to drag.
        zoom, x, y = rules.place(1, -50, 999, 1200, 800, 400, 800)
        self.assertEqual((zoom, x), (1.0, 0.0))
        self.assertAlmostEqual(y, (800 - 800 * 400 / 1200) / 2, places=6)

    def test_the_zoom_stays_in_range(self):
        self.assertEqual(rules.clamp_zoom(0.2), rules.MIN_ZOOM)
        self.assertEqual(rules.clamp_zoom(99), rules.MAX_ZOOM)
        zoom, _x, _y = rules.zoom_at(3.5, 0, 0, 200, 400, 10, 1200, 800, 400, 800)
        self.assertEqual(zoom, rules.MAX_ZOOM)

    def test_the_point_under_the_fingers_stays_put(self):
        # 1200x800 in 400x400: fitted it is 400 wide and starts at y=66.67.
        zoom, x, y = rules.zoom_at(1, 0, 66.6667, 100, 200, 3, 1200, 800, 400, 400)
        self.assertEqual(zoom, 3)
        self.assertAlmostEqual(x, 100 - 100 * 3, places=3)              # the point at x=100 stays
        self.assertAlmostEqual(y, 200 - (200 - 66.6667) * 3, places=3)

    def test_a_picture_cannot_be_dragged_off_its_edges(self):
        self.assertEqual(rules.clamp_offset(50, 1000, 400), 0.0)           # not past the left
        self.assertEqual(rules.clamp_offset(-900, 1000, 400), -600.0)      # nor the right
        self.assertEqual(rules.clamp_offset(-123, 300, 400), 50.0)         # smaller: centred

    def test_a_double_tap_goes_in_and_back(self):
        self.assertEqual(rules.double_tap(1.0), rules.DOUBLE_TAP)
        self.assertEqual(rules.double_tap(rules.DOUBLE_TAP), rules.MIN_ZOOM)
        self.assertEqual(rules.double_tap(rules.MAX_ZOOM), rules.MIN_ZOOM)

    def test_pulling_down_closes_only_a_fitted_picture(self):
        self.assertTrue(rules.can_dismiss(1.0))
        self.assertFalse(rules.can_dismiss(1.5))
        self.assertFalse(rules.dismisses(rules.DISMISS - 1))
        self.assertTrue(rules.dismisses(rules.DISMISS))
        self.assertEqual(rules.backdrop_alpha(0, 800), 1.0)
        self.assertEqual(rules.backdrop_alpha(300, 800), 0.5)
        self.assertEqual(rules.backdrop_alpha(5000, 800), 0.0)

    def test_it_opens_from_its_thumbnail(self):
        # Covering a 100x100 thumbnail at (20, 300): scaled by the height.
        scale, x, y = rules.thumb_start((20, 300, 100, 100), 1200, 800, 400, 800)
        self.assertEqual(scale, 100 / 800)
        self.assertEqual((x, y), (20 + (100 - 150) / 2, 300.0))

    def test_refusals(self):
        for call in (lambda: rules.check_image(True, object()),
                     lambda: rules.check_image(True, None, avatar=True)):
            with self.assertRaises(ApkpyError) as caught:
                call()
            self.assertEqual(caught.exception.code, 'U2046')
        rules.check_image(False, object())
        rules.check_image(True, None)


class ThePhone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.files = _build(APP, CSS)
        cls.java = _java(cls.files)

    def test_a_tap_hands_the_picture_to_the_viewer(self):
        self.assertIn('img1.setOnClickListener(_zoomed -> '
                      'ApkpyZoom.show(this, _zoomed, "A harbour"));', self.java)
        self.assertNotIn('img2.setOnClickListener', self.java)             # no zoom, no tap

    def test_view_image_opens_by_name(self):
        self.assertIn('ApkpyZoom.show(Screen_homeActivity.this, "%s", "A harbour");' % PHOTO,
                      self.java)

    def test_the_class_ships_only_when_used(self):
        self.assertIn('java/ApkpyZoom.java', self.files)
        self.assertNotRegex(self.files['java/ApkpyZoom.java'], r'__[A-Z_]+__')
        plain = _build('home = Screen(id="home")\nimage("%s", screen=home)\n' % PHOTO)
        self.assertNotIn('java/ApkpyZoom.java', plain)

    def test_a_picture_only_view_image_names_is_packaged(self):
        # A name beside the app is packaged; a full path is a file on the phone.
        files = _build('home = Screen(id="home")\n'
                       'button("Map", command=lambda: view_image("map.png"), screen=home)\n')
        self.assertEqual(files['res/drawable/map.png'], ('COPY_FILE', 'map.png'))
        self.assertIn('ApkpyZoom.show(Screen_homeActivity.this, "map.png", "");',
                      _java(files))

    def test_a_picture_from_an_item_asks_for_the_network(self):
        files = _build('home = Screen(id="home")\n'
                       'PHOTOS = [{"title": "One", "photo": "https://example.com/1.jpg"}]\n'
                       'list_view(PHOTOS, id="photos", screen=home,\n'
                       '          on_click=lambda item: view_image(item["photo"]))\n')
        java = _java(files)
        self.assertRegex(java, r'ApkpyZoom\.show\(Screen_homeActivity\.this, String\.valueOf\(')
        self.assertIn('android.permission.INTERNET', files['AndroidManifest.xml'])

    def test_pictures_a_list_names_are_packaged(self):
        # Named only inside the list, opened by its key: nobody's layout
        # carried it, and the viewer opened on nothing.
        files = _build('home = Screen(id="home")\n'
                       'def open_photo(item):\n'
                       '    view_image(item["photo"])\n'
                       'PHOTOS = [{"title": "One", "photo": "coast.jpg"},\n'
                       '          {"title": "Two", "photo": "https://example.com/2.jpg"},\n'
                       '          {"title": "Three", "photo": "notes.txt"}]\n'
                       'list_view(PHOTOS, id="photos", on_click=open_photo, screen=home)\n')
        self.assertEqual(files['res/drawable/coast.jpg'], ('COPY_FILE', 'coast.jpg'))
        self.assertFalse([name for name in files if 'notes' in name or '2.jpg' in name])

    def test_what_is_refused(self):
        for body in ('image("%s", zoom=True, command=lambda: toast("x"), screen=home)\n' % PHOTO,
                     'avatar("%s", zoom=True, screen=home)\n' % PHOTO,
                     'def bad():\n    view_image()\nbutton("x", command=bad, screen=home)\n'):
            with self.assertRaises(AssertionError) as caught:
                _build('home = Screen(id="home")\n' + body)
            self.assertIn('U2046', str(caught.exception), body)


class ThePreviewer(unittest.TestCase):

    def _open(self, p):
        p.settle(0.4)                                   # the picture loads
        p.ns['photo'].widget.event_generate('<Button-1>', x=10, y=10)
        p.settle(0.6)                                   # and grows from its thumbnail
        from apkpy_lib.features import zoom
        return zoom.active()

    def test_a_tap_opens_the_picture_fitted_and_centred(self):
        with Previewed(APP, CSS) as p:
            viewer = self._open(p)
            self.assertIsNotNone(viewer)
            vw, vh = viewer.size()
            self.assertEqual(viewer.image_size(), (1200, 800))
            self.assertEqual(viewer.zoom, rules.MIN_ZOOM)
            self.assertAlmostEqual(viewer.y, (vh - 800 * vw / 1200) / 2, places=3)
            self.assertEqual(viewer.progress, 1.0)
            viewer.close(animate=False)

    def test_the_wheel_zooms_about_the_pointer_and_a_drag_pans(self):
        with Previewed(APP, CSS) as p:
            viewer = self._open(p)
            vw, vh = viewer.size()
            viewer.wheel(vw * 0.25, vh * 0.5, 3)
            self.assertAlmostEqual(viewer.zoom, rules.WHEEL_STEP ** 3, places=4)
            before = viewer.x
            viewer.drag(40, 0)
            self.assertAlmostEqual(viewer.x, min(0.0, before + 40), places=3)
            viewer.drag(100000, 0)
            self.assertEqual(viewer.x, 0.0)                         # stops at the edge
            viewer.wheel(vw / 2, vh / 2, 50)
            self.assertEqual(viewer.zoom, rules.MAX_ZOOM)
            viewer.close(animate=False)

    def test_a_double_click_goes_in_and_back(self):
        with Previewed(APP, CSS) as p:
            viewer = self._open(p)
            viewer.double_tap(100, 300)
            self.assertEqual(viewer.zoom, rules.DOUBLE_TAP)
            viewer.double_tap(100, 300)
            self.assertEqual(viewer.zoom, rules.MIN_ZOOM)
            viewer.close(animate=False)

    def test_pulling_a_fitted_picture_down_closes_it(self):
        with Previewed(APP, CSS) as p:
            from apkpy_lib.features import zoom
            viewer = self._open(p)
            viewer.drag(0, rules.DISMISS - 10)
            self.assertEqual(viewer.release(), 'open')
            self.assertEqual(viewer.drag_y, 0.0)
            viewer.drag(0, rules.DISMISS + 10)
            self.assertEqual(viewer.release(), 'closed')
            p.settle(0.5)
            self.assertIsNone(zoom.active())

    def test_view_image_opens_a_file(self):
        with Previewed(APP, CSS) as p:
            from apkpy_lib.features import zoom
            p.ns['open_it']()
            p.settle(0.3)
            viewer = zoom.active()
            self.assertEqual(viewer.image_size(), (1200, 800))
            viewer.close()
            p.settle(0.2)
            self.assertIsNone(zoom.active())

    def test_a_picture_without_zoom_does_not_open(self):
        with Previewed(APP, CSS) as p:
            from apkpy_lib.features import zoom
            p.settle(0.4)
            p.ns['plain'].widget.event_generate('<Button-1>', x=10, y=10)
            p.settle(0.3)
            self.assertIsNone(zoom.active())

    def test_zoom_and_command_together_are_refused(self):
        from apkpy_lib import image
        with self.assertRaises(ApkpyError) as caught:
            image("x.jpg", zoom=True, command=lambda: None)
        self.assertEqual(caught.exception.code, 'U2046')


class JavaAnswersTheSameWay(unittest.TestCase):
    """The static rules of ApkpyZoom, lifted from the class as it ships."""

    PLACES = [(1, -50, 999, 1200, 800, 400, 800), (2.5, -100, -40, 1200, 800, 400, 800),
              (9, 30, 30, 800, 1200, 400, 400), (0.2, 0, 0, 640, 640, 360, 780),
              (3, -5000, -5000, 1200, 800, 400, 800)]
    ZOOMS = [(1, 0, 266.667, 100, 400, 3, 1200, 800, 400, 800),
             (2, -200, 133.3, 399, 10, 0.5, 1200, 800, 400, 800),
             (3.5, -300, -200, 200, 400, 10, 1200, 800, 400, 800),
             (1, 0, 0, 0, 0, 1.2, 640, 640, 360, 780)]
    THUMBS = [(20, 300, 100, 100, 1200, 800, 400, 800), (0, 0, 411, 274, 1800, 1200, 411, 914),
              (10, 10, 0, 0, 1200, 800, 400, 800)]
    DRAGS = [(0, 800), (300, 800), (5000, 800), (40, 0)]
    TAPS = [1.0, 1.74, 1.76, 2.5, 4.0]

    @staticmethod
    def _floats(values):
        return ', '.join('%rf' % float(v) for v in values)

    def _harness(self):
        java = zoom_feature.java_source('x')
        start = java.index('    /** zoom_rules.fit */')
        end = java.index('    // ── the picture')
        constants = java[java.index('    static final float MIN_ZOOM'):
                         java.index('    interface Ready')]
        calls = []
        for i, case in enumerate(self.PLACES):
            calls.append('show("place|%d", place(%s));' % (i, self._floats(case)))
        for i, case in enumerate(self.ZOOMS):
            calls.append('show("zoom|%d", zoomAt(%s));' % (i, self._floats(case)))
        for i, case in enumerate(self.THUMBS):
            calls.append('show("thumb|%d", thumbStart(%s));' % (i, self._floats(case)))
        for i, case in enumerate(self.DRAGS):
            calls.append('show("drag|%d", new float[]{backdropAlpha(%s)});' % (i, self._floats(case)))
        for i, zoom in enumerate(self.TAPS):
            calls.append('show("tap|%d", new float[]{doubleTap(%rf)});' % (i, zoom))
        return ('public class ZoomRulesHarness {\n' + constants + java[start:end] +
                '    static void show(String name, float[] values) {\n'
                '        StringBuilder out = new StringBuilder(name);\n'
                '        for (float value : values) out.append("|").append(value);\n'
                '        System.out.println(out);\n'
                '    }\n'
                '    public static void main(String[] args) {\n        '
                + '\n        '.join(calls) + '\n    }\n}\n')

    def test_both_languages_agree(self):
        if not TOOLING:
            self.skipTest("no JDK on this machine")
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix='apkpy-zoomrules-')
        source = os.path.join(work, 'ZoomRulesHarness.java')
        with io.open(source, 'w', encoding='utf-8') as handle:
            handle.write(self._harness())
        built = subprocess.run([javac, '-encoding', 'UTF-8', '-d', work, source],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, '-cp', work, 'ZoomRulesHarness'],
                             capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
        answers = {}
        for line in ran.stdout.splitlines():
            kind, index, *values = line.split('|')
            answers[(kind, int(index))] = [float(v) for v in values]

        def same(kind, index, expected):
            got = answers[(kind, index)]
            self.assertEqual(len(got), len(expected), (kind, index))
            for a, b in zip(got, expected):
                self.assertAlmostEqual(a, b, delta=0.01, msg=(kind, index, got, expected))

        for i, case in enumerate(self.PLACES):
            same('place', i, rules.place(*case))
        for i, case in enumerate(self.ZOOMS):
            same('zoom', i, rules.zoom_at(*case))
        for i, case in enumerate(self.THUMBS):
            same('thumb', i, rules.thumb_start(case[:4], *case[4:]))
        for i, case in enumerate(self.DRAGS):
            same('drag', i, [rules.backdrop_alpha(*case)])
        for i, zoom in enumerate(self.TAPS):
            same('tap', i, [rules.double_tap(zoom)])

    def test_the_numbers_are_the_rules(self):
        java = zoom_feature.java_source('x')
        for name, value in (('MIN_ZOOM', rules.MIN_ZOOM), ('MAX_ZOOM', rules.MAX_ZOOM),
                            ('DOUBLE_TAP', rules.DOUBLE_TAP), ('DISMISS', float(rules.DISMISS)),
                            ('CLOSE', float(rules.CLOSE))):
            self.assertIn('static final float %s = %sf;' % (name, value), java)
        self.assertIn('static final long OPEN_MS = %dL;' % rules.OPEN_MS, java)


if __name__ == '__main__':
    unittest.main()
