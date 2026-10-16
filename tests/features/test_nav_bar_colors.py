# -*- coding: utf-8 -*-
"""The bottom bar: one colour rule for both runtimes, and room for the label.

Seen on a phone in dark mode, in an app with no Theme(): the bar was the dark
fallback (#1E293B) while the pill and the labels came from the light palette
-- a lilac pill and dark-grey labels on a navy bar -- and the 32dp pill
covered the top of the active label. The Previewer drew the same bar with
colours that belonged to it and the label clear of the pill.
"""

import re
import unittest

from apkpy_lib import theme
from apkpy_lib.core.compiler import translate_python_to_android

APP = '''from apkpy_lib import *
home = Screen(id="home")
other = Screen(id="other")
label("Home", screen=home)
label("Other", screen=other)
bottom_nav([home, other], labels=["Home", "Other"], icons=["home", "person"])
run(start_screen=home%s)
'''


def _files(theme_arg=""):
    files = translate_python_to_android(APP % theme_arg)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"][:400])
    return files


def _android_colors(files):
    layout = files["res/layout/activity_screen_home.xml"]
    bar = re.search(r'bottom_nav"[^/]*?android:background="(#[0-9A-Fa-f]+)"', layout,
                    re.S).group(1)
    selector = files["res/color/nav_item_color.xml"]
    active = re.search(r'state_checked="true" android:color="(#[0-9A-Fa-f]+)"', selector).group(1)
    inactive = re.findall(r'android:color="(#[0-9A-Fa-f]+)"', selector)[-1]
    pill = re.search(r'name="android:color">(#[0-9A-Fa-f]+)<',
                     files["res/values/apkpy_nav.xml"]).group(1)
    return tuple(color.upper() for color in (bar, active, inactive, pill))


class OneRuleForTheBar(unittest.TestCase):

    def test_without_a_theme_the_phone_uses_the_previewers_colours(self):
        expected = tuple(c.upper() for c in theme.nav_colors({}))
        self.assertEqual(_android_colors(_files()), expected)
        # and they are the dark bar's own, not the light palette's
        self.assertNotEqual(expected[3], "#D7CEE7")

    def test_a_theme_still_decides(self):
        """With a Theme() the colours stay resource references, so the night
        variant of each one keeps working."""
        files = _files(', theme=Theme(mode="light", primary="#0F766E")')
        layout = files["res/layout/activity_screen_home.xml"]
        self.assertIn('android:background="@color/apkpy_surface"', layout)
        selector = files["res/color/nav_item_color.xml"]
        self.assertIn('state_checked="true" android:color="@color/apkpy_primary"', selector)
        self.assertIn('android:color="@color/apkpy_text_secondary"', selector)
        self.assertIn(">@color/apkpy_nav_indicator<", files["res/values/apkpy_nav.xml"])

    def test_the_pill_is_a_tint_of_the_bar(self):
        bar, active, _inactive, pill = theme.nav_colors({})
        self.assertEqual(pill, theme._mix_color(bar, active, 0.22))


class TheBarReachesTheBottomEdge(unittest.TestCase):
    """On a phone the gesture area under the bar showed the page's colour --
    a black strip below a navy bar. The bar's parent took that area as
    padding; now the bar does, so its own colour runs to the edge."""

    def test_the_bar_takes_the_bottom_inset(self):
        activity = _files()["java/Screen_homeActivity.java"]
        self.assertIn("_hv.setPadding(_bars.left, _bars.top, _bars.right, 0);", activity)
        self.assertIn("bottomNav.getPaddingRight(), _bars.bottom);", activity)
        self.assertIn("return androidx.core.view.WindowInsetsCompat.CONSUMED;", activity)

    def test_only_where_the_parent_was_handling_it(self):
        activity = _files()["java/Screen_homeActivity.java"]
        self.assertIn("if (_apkpyNavHost.getFitsSystemWindows()) {", activity)

    def test_older_phones_paint_their_own_bar_to_match(self):
        activity = _files()["java/Screen_homeActivity.java"]
        self.assertIn("getWindow().setNavigationBarColor(_apkpyNavBg);", activity)
        self.assertIn("calculateLuminance(_apkpyNavBg) > 0.5", activity)


class TheLabelSitsBelowThePill(unittest.TestCase):

    def test_the_spacing_is_written(self):
        layout = _files()["res/layout/activity_screen_home.xml"]
        bar = layout[layout.index("BottomNavigationView"):]
        bar = bar[:bar.index("/>")]
        for attribute in ('app:itemPaddingTop="6dp"', 'app:itemPaddingBottom="6dp"',
                          'app:activeIndicatorLabelPadding="4dp"'):
            self.assertIn(attribute, bar)


class TheBarIsAsTallAsThePreviewers(unittest.TestCase):
    """Measured on a phone: the Material 2 bar kept its own 56dp while the
    Previewer drew 64, and the label sat on the bar's bottom edge. What the
    bar carries adds up to 64; the phone now gets the same number."""

    def test_the_height_is_written(self):
        layout = _files()["res/layout/activity_screen_home.xml"]
        bar = layout[layout.index("BottomNavigationView"):]
        bar = bar[:bar.index("/>")]
        self.assertIn(f'android:minHeight="{theme.NAV_BAR_DP}dp"', bar)
        self.assertEqual(theme.NAV_BAR_DP, 64)

    def test_what_the_bar_carries_adds_up_to_its_height(self):
        pill, label = 32, 16   # the 32dp pill; a 12sp label is ~16dp tall
        self.assertEqual(
            theme.NAV_ITEM_PAD_DP + pill + theme.NAV_LABEL_GAP_DP + label
            + theme.NAV_ITEM_PAD_DP,
            theme.NAV_BAR_DP)

    def test_the_previewer_reads_the_same_numbers(self):
        from apkpy_lib import ui
        self.assertIs(ui.NAV_BAR_DP, theme.NAV_BAR_DP)
        self.assertIs(ui.NAV_LABEL_GAP_DP, theme.NAV_LABEL_GAP_DP)


if __name__ == "__main__":
    unittest.main()
