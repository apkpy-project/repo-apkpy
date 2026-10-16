# -*- coding: utf-8 -*-
"""Two things a notifications list showed on a phone (27-09-2026).

* A label in an ApkpyLayout was written with gravity="center". It changes
  nothing while the TextView hugs its words, and centred every line once the
  text wrapped -- "mentioned you: @mara.vale next week?" broke onto a second
  line in the middle of the row. CSS (text-align: start) and the Previewer's
  layout-engine slot keep it at the start; the phone does too now, and
  text-align still wins.
* ApkpyLayout lets its children draw outside their box (setClipChildren(false),
  for shadows and transforms), and a centerCrop photo scales past a box of
  another shape: a 44dp square thumbnail of a portrait story ran the full
  height of its row. The ImageView crops its own drawing now
  (cropToPadding), which leaves the shadow alone.
"""

import unittest

from test_real_screens import _build, _layouts

ROW = (
    'home = Screen(id="home")\n'
    'row = container(id="row", screen=home)\n'
    'words = container(id="words", parent=row)\n'
    'label("liv.moreau", id="who", parent=words)\n'
    'label("mentioned you: @mara.vale next week?", id="what", parent=words)\n'
    'image("story.jpg", id="thumb", parent=row, aspect_ratio="1:1", describe="")\n'
)
CSS = '''
row { display: flex; flex-direction: row; align-items: center; gap: 12px; }
words { flex-grow: 1; display: flex; flex-direction: column; align-items: flex-start; }
thumb { width: 44px; height: 44px; object-fit: cover; }
'''


def _layout(css=CSS):
    return _layouts(_build(ROW, css))['res/layout/activity_screen_home.xml']


def _view(layout, text):
    start = layout.rindex('<TextView', 0, layout.index('android:text="%s"' % text))
    return layout[start:layout.index('/>', start)]


class ALabelInAFlexContainer(unittest.TestCase):

    def test_keeps_its_text_at_the_start(self):
        view = _view(_layout(), 'mentioned you: @mara.vale next week?')
        self.assertIn('android:gravity="start|center_vertical"', view)

    def test_text_align_still_wins(self):
        view = _view(_layout(CSS + 'what { text-align: center; }'),
                     'mentioned you: @mara.vale next week?')
        self.assertIn('android:gravity="center"', view)

    def test_a_label_on_the_screen_itself_is_unchanged(self):
        layout = _layouts(_build('home = Screen(id="home")\nlabel("Hi", id="hi", screen=home)\n'))[
            'res/layout/activity_screen_home.xml']
        self.assertIn('android:gravity="start"', _view(layout, 'Hi'))


class ACroppedPhoto(unittest.TestCase):

    def test_crops_its_own_drawing(self):
        layout = _layout()
        image = layout[layout.index('<ImageView'):]
        image = image[:image.index('/>')]
        self.assertIn('android:scaleType="centerCrop" android:cropToPadding="true"', image)

    def test_a_photo_that_fits_inside_needs_nothing(self):
        layout = _layout(CSS.replace('object-fit: cover', 'object-fit: contain'))
        self.assertNotIn('cropToPadding', layout)


class AColumnIsAsWideAsItsBox(unittest.TestCase):
    """The edit-profile header: an avatar over "Edit picture or avatar" in a
    full-width column with align-items: center. ApkpyLayout took the widest
    child as the column's width, so the avatar was centred under the caption
    and the pair sat against the left edge. layout_engine.py (the Previewer)
    has always used the box's width for a column that does not wrap."""

    def _java(self):
        body = ('home = Screen(id="home")\n'
                'box = container(id="box", screen=home)\n'
                'avatar("me.png", size=86, id="face", parent=box, describe="me")\n'
                'button("Edit picture", id="pick", parent=box)\n')
        files = _build(body, 'box { display: flex; flex-direction: column; align-items: center; }')
        return files['java/ApkpyLayout.java']

    def test_the_phone_uses_the_box_width(self):
        self.assertIn('if (!row && !wrap) lineCross = Math.max(1, innerW);', self._java())

    def test_a_child_with_its_own_width_is_not_stretched(self):
        self.assertIn('!item.css.containsKey(row ? "height" : "width")) crossSize = lineCross;',
                      self._java())

    def test_the_shared_engine_agrees(self):
        from apkpy_lib import layout_engine
        boxes, _height = layout_engine.compute_layout_boxes(
            {'display': 'flex', 'flex-direction': 'column', 'align-items': 'center'},
            [{'width': 86, 'height': 86, 'style': {}},
             {'width': 200, 'height': 30, 'style': {}}],
            400)
        self.assertEqual(round(boxes[0][0]), (400 - 86) // 2)
        self.assertEqual(round(boxes[1][0]), (400 - 200) // 2)


if __name__ == '__main__':
    unittest.main()
