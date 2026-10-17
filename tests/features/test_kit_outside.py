# -*- coding: utf-8 -*-
"""What an app has outside its own screens: a widget on the home screen, a
tile in quick settings, ads, a newer version from Play, the health records.

These five are in the same table as the rest of the calls that reach past the
app (``test_kit.py`` checks the table itself, and that every class compiles).
What is different about them is what they write besides Java: a manifest
entry each, resources for the widget and the tile, libraries for ads and
updates -- and that four of them mean nothing until one line at the top of
the file has said what the app is built with.
"""
import datetime
import io
import os
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

from apkpy_lib import kit_rules as rules
from apkpy_lib.core.features import kit
from apkpy_lib.diagnostics import ApkpyError
from apkpy_lib.features import kit as preview
from apkpy_lib.features import kit_surfaces

from test_data_rules import TOOLING
from test_kit import _built, _error, needs_sdk
from test_real_screens import Previewed

ANDROID = "{http://schemas.android.com/apk/res/android}"
WIDGET = 'home_widget.define("Steps today", "0", caption="steps", icon="directions_walk")\n'
TILE = 'quick_tile.define("Walk", icon="directions_walk")\n'
ADS = 'ads.setup("test")\n'
HEALTH = 'health.policy("https://example.com/privacy")\n'


def _manifest(files):
    return ET.fromstring(files["AndroidManifest.xml"])


def _named(manifest, tag, name):
    for element in manifest.iter(tag):
        if element.get(ANDROID + "name") == name:
            return element
    return None


def _stops(case, body, *words, top=""):
    text = _error(body, top)
    case.assertIn("U2048", text)
    for word in words:
        case.assertIn(word, text)
    return text


def _fresh():
    """The five as they are when a script starts."""
    for api in (preview.home_widget, preview.quick_tile, preview.ads, preview.updates,
                preview.health):
        api.__init__()


class TheWidgetIsBuilt(unittest.TestCase):
    """One line, and the app has a widget: a receiver, two drawings, colours
    for day and night, and the class that hands them to the launcher."""

    def test_what_one_line_writes(self):
        files = _built('home_widget.set("6482", caption="steps")', top=WIDGET)
        for name in ("java/ApkpyWidget.java", "java/ApkpyWidgetProvider.java",
                     "res/layout/apkpy_widget.xml", "res/layout/apkpy_widget_card.xml",
                     "res/xml/apkpy_widget_info.xml", "res/values/apkpy_widget.xml",
                     "res/values-night/apkpy_widget.xml", "res/drawable/apkpy_widget_bg.xml",
                     "res/drawable-v31/apkpy_widget_bg.xml",
                     "res/drawable/apkpy_widget_badge.xml", "res/drawable/ic_apkpy_widget.xml"):
            self.assertIn(name, files)
        receiver = _named(_manifest(files), "receiver", ".ApkpyWidgetProvider")
        self.assertEqual(receiver.get(ANDROID + "exported"), "true")
        self.assertEqual(receiver.find("intent-filter/action").get(ANDROID + "name"),
                         "android.appwidget.action.APPWIDGET_UPDATE")
        self.assertEqual(receiver.find("meta-data").get(ANDROID + "resource"),
                         "@xml/apkpy_widget_info")
        # It is inside <application>, where a receiver has to be.
        self.assertIsNotNone(_manifest(files).find("application/receiver"))

    def test_a_release_build_is_told_to_keep_what_is_found_by_name(self):
        files = _built('home_widget.set("1")', top=WIDGET + TILE)
        kept = ET.fromstring(files["res/raw/apkpy_kit_keep.xml"]).get(
            "{http://schemas.android.com/tools}keep").split(",")
        self.assertEqual(kept, ["@drawable/apkpy_widget_badge", "@drawable/apkpy_widget_bg",
                                "@drawable/ic_apkpy_tile", "@drawable/ic_apkpy_widget",
                                "@layout/apkpy_widget", "@layout/apkpy_widget_card"])
        self.assertNotIn("res/raw/apkpy_kit_keep.xml", _built('haptics.tap()'))

    def test_the_declaration_alone_is_enough(self):
        # A widget that only ever shows what it was declared with is still one.
        files = _built('out.set_value("x")', top=WIDGET)
        self.assertIn("java/ApkpyWidgetProvider.java", files)
        self.assertIn("res/layout/apkpy_widget.xml", files)

    def test_both_drawings_are_layouts_a_launcher_can_draw(self):
        files = _built('home_widget.set("1")', top=WIDGET)
        allowed = {"LinearLayout", "TextView", "ImageView"}
        for name in ("res/layout/apkpy_widget.xml", "res/layout/apkpy_widget_card.xml"):
            root = ET.fromstring(files[name])
            self.assertEqual({element.tag for element in root.iter()} - allowed, set(), name)
            # The corner Android 12 rounds, and what the tap is hung on.
            self.assertEqual(root.get(ANDROID + "id"), "@android:id/background")
            ids = {element.get(ANDROID + "id") for element in root.iter("TextView")}
            self.assertEqual(ids, {"@+id/apkpy_widget_title", "@+id/apkpy_widget_text",
                                   "@+id/apkpy_widget_caption"}, name)

    def test_what_it_shows_before_the_app_has_said_anything(self):
        files = _built('home_widget.set("1")', top=WIDGET)
        root = ET.fromstring(files["res/layout/apkpy_widget.xml"])
        shown = {element.get(ANDROID + "id"): element.get(ANDROID + "text")
                 for element in root.iter("TextView")}
        self.assertEqual(shown["@+id/apkpy_widget_title"], "Steps today")
        self.assertEqual(shown["@+id/apkpy_widget_text"], "0")
        self.assertEqual(shown["@+id/apkpy_widget_caption"], "steps")
        java = files["java/ApkpyWidget.java"]
        self.assertIn('TITLE = "Steps today"', java)
        self.assertIn('CAPTION = "steps"', java)

    def test_text_a_layout_would_misread_is_written_safely(self):
        top = 'home_widget.define("Tom\'s \\"list\\" & more <1>", "@home", caption="?x")\n'
        files = _built('home_widget.set("1")', top=top)
        root = ET.fromstring(files["res/layout/apkpy_widget.xml"])
        shown = {element.get(ANDROID + "id"): element.get(ANDROID + "text")
                 for element in root.iter("TextView")}
        # What aapt reads back: the quote marks escaped, and no resource
        # reference where the app wrote an at-sign.
        self.assertEqual(shown["@+id/apkpy_widget_title"], 'Tom\\\'s \\"list\\" & more <1>')
        self.assertEqual(shown["@+id/apkpy_widget_text"], "\\@home")
        self.assertEqual(shown["@+id/apkpy_widget_caption"], "\\?x")
        self.assertIn('TITLE = "Tom\'s \\"list\\" & more <1>"', files["java/ApkpyWidget.java"])

    def test_no_icon_no_badge(self):
        files = _built('home_widget.set("1")', top='home_widget.define("Steps")\n')
        self.assertNotIn("res/drawable/ic_apkpy_widget.xml", files)
        for name in ("res/layout/apkpy_widget.xml", "res/layout/apkpy_widget_card.xml"):
            self.assertIsNone(ET.fromstring(files[name]).find(".//ImageView"), name)
        # With no caption, its line takes no room.
        caption = [element for element in ET.fromstring(
            files["res/layout/apkpy_widget.xml"]).iter("TextView")
            if element.get(ANDROID + "id") == "@+id/apkpy_widget_caption"][0]
        self.assertEqual(caption.get(ANDROID + "visibility"), "gone")

    def test_the_colours_are_the_apps_in_both_modes(self):
        theme = ('\nbutton("Go", id="go", screen=home, command=go)\n'
                 'run(start_screen=home, theme=Theme(primary="#0B7A6B", surface="#FAFFFE", '
                 'text="#101010", text_secondary="#505050"))\n')
        from test_kit import HEAD
        from apkpy_lib.core.compiler import translate_python_to_android
        files = translate_python_to_android(
            HEAD + WIDGET + 'def go():\n    home_widget.set("1")\n' + theme)

        def colours(name):
            return {element.get("name"): element.text
                    for element in ET.fromstring(files[name]).iter("color")}
        day = colours("res/values/apkpy_widget.xml")
        night = colours("res/values-night/apkpy_widget.xml")
        self.assertEqual(day["apkpy_widget_surface"].upper(), "#FAFFFE")
        self.assertEqual(day["apkpy_widget_text"].upper(), "#101010")
        self.assertEqual(day["apkpy_widget_primary"].upper(), "#0B7A6B")
        # The home screen follows the phone, not the app: night has a dark
        # surface of its own, and the accent is carried over.
        self.assertNotEqual(night["apkpy_widget_surface"].upper(), "#FAFFFE")
        red, green, blue = (int(night["apkpy_widget_surface"][i:i + 2], 16) for i in (1, 3, 5))
        self.assertLess(red + green + blue, 3 * 96)
        self.assertEqual(set(day), set(night))
        self.assertEqual(len(day), 5)

    def test_its_name_in_the_launchers_list(self):
        files = _built('home_widget.set("1")',
                       top='home_widget.define("Steps", name="Steps & stairs")\n')
        receiver = _named(_manifest(files), "receiver", ".ApkpyWidgetProvider")
        self.assertEqual(receiver.get(ANDROID + "label"), "Steps & stairs")

    def test_an_app_with_no_widget_has_none_of_it(self):
        files = _built('haptics.tap()')
        self.assertEqual([name for name in files if "widget" in name.lower()], [])
        self.assertEqual([name for name in files if "tile" in name.lower()], [])


class TheTileIsBuilt(unittest.TestCase):

    def test_what_one_line_writes(self):
        files = _built('quick_tile.set(True, subtitle="On a walk")', top=TILE)
        self.assertIn("java/ApkpyTile.java", files)
        self.assertIn("java/ApkpyTileService.java", files)
        service = _named(_manifest(files), "service", ".ApkpyTileService")
        self.assertEqual(service.get(ANDROID + "label"), "Walk")
        self.assertEqual(service.get(ANDROID + "icon"), "@drawable/ic_apkpy_tile")
        self.assertEqual(service.get(ANDROID + "permission"),
                         "android.permission.BIND_QUICK_SETTINGS_TILE")
        self.assertEqual(service.find("intent-filter/action").get(ANDROID + "name"),
                         "android.service.quicksettings.action.QS_TILE")
        # Quick settings asks when told there is news, not every time it opens.
        self.assertEqual(service.find("meta-data").get(ANDROID + "name"),
                         "android.service.quicksettings.ACTIVE_TILE")
        self.assertIn('LABEL = "Walk"', files["java/ApkpyTile.java"])

    def test_the_icon_is_white_for_the_system_to_tint(self):
        files = _built('quick_tile.set(True)', top=TILE)
        self.assertIn('android:fillColor="#FFFFFFFF"', files["res/drawable/ic_apkpy_tile.xml"])
        plain = _built('quick_tile.set(True)', top='quick_tile.define("Walk")\n')
        self.assertIn("res/drawable/ic_apkpy_tile.xml", plain)      # a tile always has one

    def test_true_and_false_cross_as_text(self):
        java = _built('quick_tile.set(False)', top=TILE)["java/Screen_homeActivity.java"]
        self.assertIn('_apkpyNative_quick_tile_set(String.valueOf(false), String.valueOf(""))',
                      java)
        self.assertIn("ApkpyTile.set(this, active, subtitle)", java)

    def test_whether_the_tile_opened_the_app_is_a_yes_or_no(self):
        java = _built('if quick_tile.opened():\n    quick_tile.clear()', top=TILE)[
            "java/Screen_homeActivity.java"]
        self.assertIn("ApkpyTile.opened(this)", java)
        self.assertIn("ApkpyTile.clear(this)", java)


class AdsAreBuilt(unittest.TestCase):

    def test_what_one_line_writes(self):
        files = _built('ads.banner("test")', top=ADS)
        self.assertIn("java/ApkpyAds.java", files)
        manifest = _manifest(files)
        which = _named(manifest, "meta-data", "com.google.android.gms.ads.APPLICATION_ID")
        self.assertEqual(which.get(ANDROID + "value"), rules.ADS_TEST["app"])
        asked = [element.get(ANDROID + "name") for element in manifest.iter("uses-permission")]
        self.assertIn("android.permission.INTERNET", asked)
        self.assertIn("android.permission.ACCESS_NETWORK_STATE", asked)
        self.assertEqual(len(asked), len(set(asked)))
        for line in rules.GRADLE["ads"]:
            self.assertIn(line, files["native/gradle.txt"])

    def test_the_apps_own_id(self):
        files = _built('ads.banner("ca-app-pub-1234567890123456/1234567890")',
                       top='ads.setup("ca-app-pub-1234567890123456~1234567890")\n')
        which = _named(_manifest(files), "meta-data",
                       "com.google.android.gms.ads.APPLICATION_ID")
        self.assertEqual(which.get(ANDROID + "value"), "ca-app-pub-1234567890123456~1234567890")

    def test_test_is_googles_sample_on_the_phone_too(self):
        rules_java = kit.java_source("ApkpyKitRules", "p")
        for kind in ("banner", "interstitial", "rewarded"):
            self.assertIn('"%s"' % rules.ADS_TEST[kind], rules_java)

    def test_the_library_is_only_brought_by_an_app_that_uses_it(self):
        files = _built('haptics.tap()')
        self.assertNotIn("play-services-ads", files.get("native/gradle.txt", ""))
        self.assertNotIn("java/ApkpyAds.java", files)

    def test_an_answer_that_comes_later(self):
        java = _built('ads.rewarded("test", on_result=answered)', top=ADS)[
            "java/Screen_homeActivity.java"]
        self.assertIn("ApkpyAds.rewarded(this, unit, new ApkpyKit.Done()", java)


class UpdatesAreBuilt(unittest.TestCase):

    def test_what_a_call_writes(self):
        files = _built('updates.check(on_result=answered)')
        self.assertIn("java/ApkpyUpdates.java", files)
        for line in rules.GRADLE["updates"]:
            self.assertIn(line, files["native/gradle.txt"])
        # Play's own screen answers to an Activity: the one that waits.
        self.assertIsNotNone(_named(_manifest(files), "activity", ".ApkpyKitActivity"))
        self.assertIn("java/ApkpyKitActivity.java", files)

    def test_nothing_has_to_be_declared(self):
        java = _built('updates.start("immediate", on_result=answered)\n'
                      'out.set_value(updates.install())')["java/Screen_homeActivity.java"]
        self.assertIn("ApkpyUpdates.start(this, mode, new ApkpyKit.Done()", java)
        self.assertIn("ApkpyUpdates.install(this)", java)


class HealthIsBuilt(unittest.TestCase):

    def test_only_the_kinds_the_app_names_are_asked_for(self):
        files = _built('health.ask("steps, heart_rate", on_result=answered)\n'
                       'health.read("sleep", on_result=answered)', top=HEALTH)
        asked = [element.get(ANDROID + "name")
                 for element in _manifest(files).iter("uses-permission")]
        self.assertEqual(asked, ["android.permission.health.READ_STEPS",
                                 "android.permission.health.READ_HEART_RATE",
                                 "android.permission.health.READ_SLEEP"])
        # Beside <application>, where a permission has to be.
        self.assertEqual(len(_manifest(files).findall("uses-permission")), 3)

    def test_where_the_privacy_policy_is(self):
        files = _built('health.read("steps", on_result=answered)', top=HEALTH)
        screen = _named(_manifest(files), "activity", ".ApkpyHealthPolicyActivity")
        self.assertEqual(screen.get(ANDROID + "permission"),
                         "android.permission.START_VIEW_PERMISSION_USAGE")
        self.assertEqual(screen.find("intent-filter/action").get(ANDROID + "name"),
                         "android.intent.action.VIEW_PERMISSION_USAGE")
        self.assertEqual(screen.find("intent-filter/category").get(ANDROID + "name"),
                         "android.intent.category.HEALTH_PERMISSIONS")
        self.assertIn('POLICY = "https://example.com/privacy"', files["java/ApkpyHealth.java"])
        self.assertIn("java/ApkpyHealthPolicyActivity.java", files)

    def test_every_kind_has_its_permission_in_the_class(self):
        java = kit.java_source("ApkpyHealth", "p")
        for kind, (permission, _unit, _icon, _sample) in rules.HEALTH_KINDS.items():
            self.assertIn('if ("%s".equals(kind)) return "android.permission.health.%s";'
                          % (kind, permission), java)
            self.assertIn('"%s".equals(kind)' % kind, java.split("class Records")[1], kind)
        for kind in rules.HEALTH_AVERAGES:
            self.assertIn(kind, rules.HEALTH_KINDS)

    def test_asking_needs_the_screen_that_waits(self):
        files = _built('health.ask("steps", on_result=answered)', top=HEALTH)
        self.assertIsNotNone(_named(_manifest(files), "activity", ".ApkpyKitActivity"))


class WhatStopsTheBuild(unittest.TestCase):
    """A call that has nothing behind it, or names something that does not
    exist, is found while the app is built."""

    def test_a_family_that_was_never_declared(self):
        _stops(self, 'home_widget.set("1")', "home_widget.set(): this app has no widget",
               "Add this at the top of the file", "home_widget.define(")
        _stops(self, 'quick_tile.set(True)', "this app has no tile", "quick_tile.define(")
        _stops(self, 'ads.banner("test")', "AdMob does not know which app this is",
               'ads.setup("test")')
        _stops(self, 'health.read("steps", on_result=answered)',
               "no privacy policy to show", "health.policy(")

    def test_the_error_points_at_the_page_that_explains_it(self):
        text = _stops(self, 'ads.banner("test")', "AdMob does not know which app this is")
        self.assertIn("https://repo-apkpy.pages.dev/guides/outside-the-app/", text)
        self.assertIn("/guides/outside-the-app/", _stops(self, 'updates.cheque()',
                                                         "updates has no cheque()"))
        # The calls that were there before keep their own page.
        self.assertIn("/guides/phone-actions/", _error('haptics.buzz()'))

    def test_a_declaration_is_written_once_at_the_top(self):
        _stops(self, WIDGET.strip(), "written once, on a line of its own at the top")
        _stops(self, 'out.set_value("x")', "home_widget.define() is written once",
               top=WIDGET + WIDGET)
        _stops(self, 'out.set_value("x")', "has to be text written in the source",
               top='NAME = "Steps"\nhome_widget.define(NAME)\n')
        _stops(self, 'out.set_value("x")', "preview= is True or False, got 1",
               top='quick_tile.define("Walk", preview=1)\n')
        _stops(self, 'out.set_value("x")', "preview= has to be True or False written",
               top='SHOW = True\nquick_tile.define("Walk", preview=SHOW)\n')

    def test_a_declaration_that_says_nothing(self):
        _stops(self, 'out.set_value("x")', "a widget has at least a title",
               top='home_widget.define("  ")\n')
        _stops(self, 'out.set_value("x")', "a tile has a name", top='quick_tile.define("")\n')
        _stops(self, 'out.set_value("x")', "app_id= is the id AdMob gives the app",
               top='ads.setup("my-app")\n')
        _stops(self, 'out.set_value("x")', "starting with https://",
               top='health.policy("privacy.html")\n')

    def test_an_ad_unit_that_is_not_one(self):
        _stops(self, 'ads.banner("banner-1")', "ads.banner(): 'banner-1' is not an ad unit",
               '"test" shows', top=ADS)
        # An app id where a unit goes is the mistake everybody makes once.
        _stops(self, 'ads.interstitial("ca-app-pub-1234567890123456~1234567890", '
                     'on_result=answered)', "is not an ad unit", top=ADS)
        _stops(self, 'ads.banner("test", position="left")',
               'position= is "bottom" or "top"', top=ADS)

    def test_a_unit_worked_out_while_the_app_runs_is_let_through(self):
        java = _built('unit = storage.get("unit", "test")\nads.banner(unit)', top=ADS)[
            "java/Screen_homeActivity.java"]
        self.assertIn("ApkpyAds.banner(this, unit, position)", java)

    def test_a_kind_of_update_that_does_not_exist(self):
        _stops(self, 'updates.start("silent", on_result=answered)',
               'mode= is "flexible" or "immediate"')

    def test_health_kinds_are_written_out(self):
        _stops(self, 'health.read("stepz", on_result=answered)', "there is no kind 'stepz'",
               "One of: steps", top=HEALTH)
        _stops(self, 'kind = "steps"\nhealth.read(kind, on_result=answered)',
               "kind= has to be written in the source",
               "a permission in the app's manifest", top=HEALTH)
        _stops(self, 'health.read("steps, sleep", on_result=answered)',
               "health.read() takes one kind", top=HEALTH)
        _stops(self, 'health.ask("", on_result=answered)', "takes at least one kind", top=HEALTH)

    def test_inside_a_background_job(self):
        from test_kit import HEAD, TAIL
        from apkpy_lib.core.compiler import translate_python_to_android
        source = (HEAD + WIDGET +
                  'def work(job):\n'
                  '    home_widget.set("1")\n\n'
                  'sync = background_job("sync", run=work)\n'
                  'def go():\n'
                  '    sync.enqueue()\n' + TAIL)
        text = " ".join(translate_python_to_android(source).get("error.txt", "").split())
        self.assertIn("J7004", text)
        self.assertIn("home_widget.set() cannot run inside a background job", text)


class TheRules(unittest.TestCase):
    """What both sides read, in Python."""

    NOW = datetime.datetime(2026, 10, 5, 14, 30, 12)

    def test_the_period_of_a_reading(self):
        day = datetime.datetime(2026, 10, 5)
        period = rules.health_period
        self.assertEqual(period("", "", self.NOW), (day, self.NOW))
        self.assertEqual(period("2026-10-01", "", self.NOW),
                         (datetime.datetime(2026, 10, 1), self.NOW))
        # An end with no hour is the whole of that day.
        self.assertEqual(period("2026-10-01", "2026-10-03", self.NOW),
                         (datetime.datetime(2026, 10, 1), datetime.datetime(2026, 10, 4)))
        self.assertEqual(period("2026-10-04 20:00", "2026-10-05 08:00", self.NOW),
                         (datetime.datetime(2026, 10, 4, 20), datetime.datetime(2026, 10, 5, 8)))
        self.assertIsNone(period("2026-10-05", "2026-10-04", self.NOW))
        self.assertIsNone(period("yesterday", "", self.NOW))
        self.assertIsNone(period("", "soon", self.NOW))
        self.assertIsNone(period("2026-10-06", "", self.NOW))       # starts tomorrow
        # Asked at midnight exactly, today has only just begun.
        self.assertEqual(period("", "", day), (day, day + datetime.timedelta(seconds=1)))

    def test_kinds(self):
        self.assertEqual(rules.health_kinds(" steps , heart_rate,steps "),
                         (["steps", "heart_rate"], ""))
        self.assertEqual(rules.health_kinds("steps, pulse"), (None, "pulse"))
        self.assertEqual(rules.health_kinds(""), ([], ""))
        for kind, (permission, unit, icon, sample) in rules.HEALTH_KINDS.items():
            self.assertRegex(permission, r"^READ_[A-Z_]+$")
            self.assertTrue(unit and icon)
            self.assertEqual(rules.health_value(kind, float(sample)), sample, kind)

    def test_a_reading_as_text(self):
        self.assertEqual(rules.health_value("steps", 6481.6), "6482")
        self.assertEqual(rules.health_value("steps", 0.5), "0")       # half to even
        self.assertEqual(rules.health_value("steps", 1.5), "2")
        self.assertEqual(rules.health_value("weight", 72.449), "72.4")
        self.assertEqual(rules.health_value("hydration", 1.255), "1.25")

    def test_the_desks_reading_is_the_same_every_time_and_differs_by_day(self):
        day = datetime.datetime(2026, 10, 5)
        one = datetime.timedelta(days=1)
        first = rules.health_sample("steps", day, day + one)
        self.assertEqual(first, rules.health_sample("steps", day, day + one))
        week = [int(rules.health_sample("steps", day + one * n, day + one * (n + 1)))
                for n in range(7)]
        self.assertGreater(len(set(week)), 4)
        usual = int(rules.HEALTH_KINDS["steps"][3])
        for steps in week:
            self.assertTrue(usual * 0.8 <= steps <= usual * 1.2, steps)
        # A week of steps is seven days of them; a week's heart rate is still one.
        self.assertEqual(int(rules.health_sample("steps", day, day + one * 7)), sum(week))
        rate = int(rules.health_sample("heart_rate", day, day + one * 7))
        self.assertTrue(50 < rate < 90, rate)

    def test_ad_ids(self):
        self.assertEqual(rules.ad_app_id(" test "), rules.ADS_TEST["app"])
        self.assertEqual(rules.ad_app_id("ca-app-pub-1234567890123456~1234567890"),
                         "ca-app-pub-1234567890123456~1234567890")
        self.assertEqual(rules.ad_app_id("ca-app-pub-1234567890123456/1234567890"), "")
        self.assertEqual(rules.ad_unit("test", "rewarded"), rules.ADS_TEST["rewarded"])
        self.assertEqual(rules.ad_unit("ca-app-pub-1234567890123456/1234567890", "banner"),
                         "ca-app-pub-1234567890123456/1234567890")
        self.assertEqual(rules.ad_unit("ca-app-pub-1234567890123456~1234567890", "banner"), "")
        self.assertEqual(rules.ad_unit("", "banner"), "")

    def test_every_declared_family_says_what_to_write(self):
        for namespace, (verb, why, example) in rules.DECLARED_BY.items():
            self.assertEqual(rules.verb(namespace, verb).mode, rules.DECLARE)
            self.assertTrue(example.startswith("%s.%s(" % (namespace, verb)), example)
            self.assertFalse(why.endswith("."), why)


@needs_sdk
class TheTwoLanguagesAgree(unittest.TestCase):
    """The period, the number and the ad unit are worked out twice -- once
    for the desk, once for the phone -- and have to come out the same."""

    def test_the_same_answers(self):
        now = datetime.datetime(2026, 10, 5, 14, 30, 12)
        epoch = datetime.datetime(1970, 1, 1)
        now_ms = int((now - epoch).total_seconds() * 1000)
        periods = [("", ""), ("2026-10-01", ""), ("2026-10-01", "2026-10-03"),
                   ("2026-10-04 20:00", "2026-10-05 08:00"), ("2026-10-05", "2026-10-04"),
                   ("yesterday", ""), ("", "soon"), ("2026-10-06", ""), ("", "2026-10-05"),
                   ("", "2026-10-04"), ("2026-02-30", ""), (" 2026-10-01 ", " 2026-10-01 ")]
        numbers = [("steps", 6481.6), ("steps", 0.5), ("steps", 1.5), ("steps", 2.5),
                   ("weight", 72.449), ("weight", 72.45), ("weight", 0.05), ("weight", 0.15),
                   ("hydration", 1.255), ("hydration", 1.005), ("hydration", 0.125),
                   ("sleep", 436.99999), ("heart_rate", 68.0), ("floors", 9.5)]
        units = [("test", "banner"), (" test ", "interstitial"), ("test", "rewarded"),
                 ("ca-app-pub-1234567890123456/1234567890", "banner"),
                 ("ca-app-pub-1234567890123456~1234567890", "banner"),
                 ("ca-app-pub-123/1234567890", "banner"), ("", "rewarded"), ("Test", "banner"),
                 ("ca-app-pub-١٢٣٤٥٦٧٨٩٠١٢٣٤٥٦/1234567890", "banner")]

        def literal(text):
            return '"' + "".join("\\u%04x" % ord(ch) for ch in text) + '"'

        lines = []
        for index, (start, end) in enumerate(periods):
            lines.append('System.out.println("period|%d|" + java.util.Arrays.toString('
                         'ApkpyKitRules.healthPeriod(%s, %s, %dL, '
                         'java.util.TimeZone.getTimeZone("UTC"))));'
                         % (index, literal(start), literal(end), now_ms))
        for index, (kind, number) in enumerate(numbers):
            lines.append('System.out.println("number|%d|" + ApkpyKitRules.healthValue(%s, %r));'
                         % (index, literal(kind), number))
        for index, (text, kind) in enumerate(units):
            lines.append('System.out.println("unit|%d|" + ApkpyKitRules.adUnit(%s, %s));'
                         % (index, literal(text), literal(kind)))

        if not TOOLING:
            self.skipTest("no JDK on this machine")
        javac, java_bin, _jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-kit-outside-")
        with io.open(os.path.join(work, "ApkpyKitRules.java"), "w", encoding="utf-8") as handle:
            handle.write(kit.java_source("ApkpyKitRules", "p").replace("package p;", ""))
        with io.open(os.path.join(work, "Harness.java"), "w", encoding="utf-8") as handle:
            handle.write("public class Harness {\n    public static void main(String[] a) {\n"
                         "        " + "\n        ".join(lines) + "\n    }\n}\n")
        built = subprocess.run([javac, "-encoding", "UTF-8", "-d", work,
                                os.path.join(work, "ApkpyKitRules.java"),
                                os.path.join(work, "Harness.java")],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        ran = subprocess.run([java_bin, "-cp", work, "Harness"],
                             capture_output=True, text=True, encoding="ascii")
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)

        seen = 0
        for line in ran.stdout.splitlines():
            kind, index, answer = line.split("|", 2)
            index = int(index)
            seen += 1
            if kind == "period":
                found = rules.health_period(periods[index][0], periods[index][1], now)
                if found is None:
                    self.assertEqual(answer, "null", periods[index])
                else:
                    wanted = [int((moment - epoch).total_seconds() * 1000) for moment in found]
                    self.assertEqual(answer, str(wanted), periods[index])
            elif kind == "number":
                self.assertEqual(answer, rules.health_value(*numbers[index]), numbers[index])
            else:
                self.assertEqual(answer, rules.ad_unit(*units[index]), units[index])
        self.assertEqual(seen, len(lines))


class TheLibraryClasses(unittest.TestCase):
    """ApkpyAds and ApkpyUpdates are written against a library, so javac
    alone cannot check them: a Gradle build does. What can be checked here
    is that they are whole, and say only words the table has."""

    def test_they_are_found_and_whole(self):
        for name in ("ApkpyAds", "ApkpyUpdates"):
            source = kit.java_source(name, "com.example.app")
            self.assertTrue(source.startswith("package com.example.app;"), name)
            self.assertEqual(re.findall(r"__[A-Z_]+__", source), [], name)
            self.assertEqual(source.count("{"), source.count("}"), name)

    def test_every_call_of_the_table_has_its_method(self):
        for namespace, name in (("ads", "ApkpyAds"), ("updates", "ApkpyUpdates"),
                                ("home_widget", "ApkpyWidget"), ("quick_tile", "ApkpyTile"),
                                ("health", "ApkpyHealth")):
            source = kit.java_source(name, "p")
            self.assertEqual(rules.SPEC[namespace]["class"], name)
            for verb in rules.verbs(namespace):
                found = rules.verb(namespace, verb)
                if found.mode == rules.DECLARE:
                    continue
                wanted = "public static %s %s(" % (
                    "void" if found.mode == rules.LATER else "String", found.java)
                self.assertIn(wanted, source, (namespace, verb))

    def test_a_banner_takes_its_room_before_the_ad_arrives(self):
        source = kit.java_source("ApkpyAds", "p")
        # The height is the ad's own, known before anything is loaded.
        self.assertIn("size.getHeightInPixels(activity)", source)
        self.assertIn("getCurrentOrientationAnchoredAdaptiveBannerAdSize", source)
        # And no ad is requested before the question of consent is settled.
        self.assertIn("consent.canRequestAds()", source)
        self.assertLess(source.index("settle(activity, new Settled()"),
                        source.index("view.loadAd("))

    def test_the_question_of_consent_is_put_once_however_many_ads_are_asked_for(self):
        # A banner and two ads fetched ahead are three requests at once; on a
        # phone each put Google's form up for itself.
        source = kit.java_source("ApkpyAds", "p")
        settle = source[source.index("private static void settle("):
                        source.index("/**", source.index("private static void settle("))]
        self.assertLess(settle.index("SETTLING.add(waiting);"),
                        settle.index("if (sSettling) return;"))
        self.assertLess(settle.index("if (sSettling) return;"),
                        settle.index("requestConsentInfoUpdate"))
        self.assertEqual(source.count("requestConsentInfoUpdate("), 1)

    def test_nothing_is_requested_until_the_library_has_started(self):
        source = kit.java_source("ApkpyAds", "p")
        started = source[source.index("private static void started("):]
        self.assertLess(started.index("MobileAds.initialize(app);"),
                        started.index("for (Runnable each : all) each.run();"))
        self.assertNotIn("work.run();\n                    }\n                });\n            }\n"
                         "        });\n    }\n\n    public static void consent",
                         source)
        self.assertIn("started(activity, work);", source)

    def test_a_copy_that_is_not_from_play_says_so_before_play_is_asked(self):
        source = kit.java_source("ApkpyUpdates", "p")
        ask = source[source.index("private static void ask("):]
        self.assertLess(ask.index('then.run(null, "not_from_play");'),
                        ask.index("getAppUpdateInfo()"))


class OnTheDeskWithNoWindow(unittest.TestCase):
    """A script, a test: every call still answers, and none opens a window."""

    def setUp(self):
        _fresh()
        self.heard = []
        self.answer = lambda ok, value: self.heard.append((ok, value))

    tearDown = staticmethod(_fresh)

    def test_a_widget(self):
        widget = preview.home_widget
        widget.define("Steps today", "0", caption="steps", icon="directions_walk")
        self.assertEqual((widget.title, widget.text, widget.caption), ("Steps today", "0", "steps"))
        self.assertEqual(widget.count(), "0")
        self.assertEqual(widget.set(6482, caption="so far"), "ok")
        self.assertEqual((widget.title, widget.text, widget.caption),
                         ("Steps today", "6482", "so far"))
        # No caption given takes the caption away; no title keeps the title.
        widget.set("7000", title="Steps this week")
        self.assertEqual((widget.title, widget.text, widget.caption),
                         ("Steps this week", "7000", ""))
        self.assertEqual(widget.pin(), "ok")
        self.assertEqual(widget.count(), "1")

    def test_a_tile(self):
        tile = preview.quick_tile
        tile.define("Walk", icon="directions_walk")
        self.assertIs(tile.is_active(), False)
        self.assertIs(tile.opened(), False)
        self.assertEqual(tile.set(True, subtitle="On a walk"), "ok")
        self.assertIs(tile.is_active(), True)
        self.assertEqual(tile.set("false"), "ok")       # as the phone reads text
        self.assertIs(tile.is_active(), False)
        tile.offer(on_result=self.answer)
        tile.offer(on_result=self.answer)
        self.assertEqual(self.heard, [(True, "added"), (True, "already")])

    def test_a_tile_that_opened_the_app(self):
        tile = preview.quick_tile
        tile.define("Walk", preview=True)
        self.assertIs(tile.opened(), True)
        self.assertEqual(tile.clear(), "ok")
        self.assertIs(tile.opened(), False)

    def test_ads(self):
        ads = preview.ads
        ads.setup("test")
        self.assertEqual(ads.banner("test"), "ok")
        self.assertEqual(ads.last, ("banner", "test", "bottom"))
        self.assertEqual(ads.banner("test", position="top"), "ok")
        self.assertEqual(ads.last, ("banner", "test", "top"))
        self.assertEqual(ads.banner("nonsense"), "invalid")
        self.assertEqual(ads.hide_banner(), "ok")
        self.assertEqual(ads.prepare(interstitial="test", rewarded="test"), "ok")
        self.assertEqual(ads.prepare(rewarded="nonsense"), "invalid")
        ads.interstitial("test", on_result=self.answer)
        ads.rewarded("test", on_result=self.answer)
        ads.rewarded("nonsense", on_result=self.answer)
        self.assertEqual(self.heard, [(True, "closed"), (True, rules.AD_REWARD),
                                      (False, "invalid")])

    def test_consent(self):
        ads = preview.ads
        ads.setup("test")
        self.assertIs(ads.needs_privacy_options(), False)
        ads.consent(on_result=self.answer)
        self.assertIs(ads.needs_privacy_options(), True)
        ads.privacy_options(on_result=self.answer)
        self.assertEqual(self.heard, [(True, "ok"), (True, "ok")])

    def test_an_update_from_start_to_finish(self):
        updates = preview.updates
        self.assertEqual(updates.install(), "nothing")
        updates.check(on_result=self.answer)
        updates.start(on_result=self.answer)
        updates.check(on_result=self.answer)
        self.assertEqual(updates.install(), "ok")
        updates.check(on_result=self.answer)
        updates.start("immediate", on_result=self.answer)
        self.assertEqual(self.heard, [(True, "available"), (True, "downloaded"),
                                      (True, "downloaded"), (False, "none"), (False, "none")])

    def test_an_update_that_cannot_wait(self):
        preview.updates.start("immediate", on_result=self.answer)
        preview.updates.check(on_result=self.answer)
        self.assertEqual(self.heard, [(True, "ok"), (False, "none")])

    def test_health(self):
        health = preview.health
        health.policy("https://example.com/privacy")
        self.assertIs(health.available(), True)
        self.assertIs(health.allowed("steps"), False)
        health.read("steps", on_result=self.answer)
        health.ask("steps, heart_rate", on_result=self.answer)
        self.assertIs(health.allowed("steps"), True)
        self.assertIs(health.allowed("sleep"), False)
        health.read("steps", on_result=self.answer)
        health.read("steps", start="2026-10-05", end="2026-10-01", on_result=self.answer)
        health.read("sleep", on_result=self.answer)
        self.assertEqual(self.heard[0], (False, "no_permission"))
        self.assertEqual(self.heard[1], (True, "ok"))
        self.assertIs(self.heard[2][0], True)
        self.assertRegex(self.heard[2][1], r"^[0-9]+$")
        self.assertEqual(self.heard[3:], [(False, "invalid"), (False, "no_permission")])

    def test_a_family_that_was_never_declared_is_said_as_the_build_says_it(self):
        for call, words in ((lambda: preview.home_widget.set("1"),
                             "home_widget.set(): this app has no widget"),
                            (lambda: preview.quick_tile.is_active(), "this app has no tile"),
                            (lambda: preview.ads.banner("test"),
                             "AdMob does not know which app this is"),
                            (lambda: preview.health.available(), "no privacy policy to show")):
            with self.assertRaises(ApkpyError) as caught:
                call()
            error = caught.exception
            self.assertEqual(error.code, "U2048")
            self.assertIn(words, str(error))
            self.assertTrue(any(hint.startswith("Add this at the top of the file: ")
                                for hint in error.suggestions), error.suggestions)

    def test_a_declaration_that_says_nothing_is_refused_here_too(self):
        for call in (lambda: preview.home_widget.define(" "),
                     lambda: preview.quick_tile.define(""),
                     lambda: preview.ads.setup("my-app"),
                     lambda: preview.health.policy("privacy.html")):
            with self.assertRaises(ApkpyError) as caught:
                call()
            self.assertEqual(caught.exception.code, "U2048")

    def test_a_kind_that_does_not_exist(self):
        preview.health.policy("https://example.com/privacy")
        with self.assertRaises(ApkpyError) as caught:
            preview.health.read("stepz", on_result=self.answer)
        self.assertIn("there is no kind 'stepz'", str(caught.exception))
        with self.assertRaises(ApkpyError):
            preview.health.read("steps, sleep", on_result=self.answer)


class OnTheDeskInThePreviewer(unittest.TestCase):
    """With the window open, what is outside the app is drawn where it can
    be seen, and what takes the screen can be answered."""

    APP = (WIDGET + TILE + ADS + HEALTH +
           'home = Screen(id="home")\n'
           'out = label("", id="out", screen=home)\n'
           'other = Screen(id="other")\n'
           'label("Other", id="there", screen=other)\n'
           'HEARD = []\n'
           'def answered(ok, value):\n'
           '    HEARD.append((ok, value))\n')

    def setUp(self):
        _fresh()

    def tearDown(self):
        kit_surfaces.close_all()
        _fresh()

    def test_a_change_to_the_widget_is_a_glimpse_of_it(self):
        with Previewed(self.APP, "") as p:
            self.assertIsNone(kit_surfaces.current_peek())
            p.ns["home_widget"].set("6482", caption="steps")
            p.settle(0.4)
            glimpse = kit_surfaces.current_peek()
            self.assertEqual(glimpse.apkpy_peek, "Home screen")
            # At the top of the window, inside it.
            root = p.app.root
            self.assertGreaterEqual(glimpse.winfo_rootx(), root.winfo_rootx())
            self.assertLessEqual(glimpse.winfo_rootx() + glimpse.winfo_width(),
                                 root.winfo_rootx() + root.winfo_width())
            self.assertLess(glimpse.winfo_rooty(), root.winfo_rooty() + 80)
            texts = [glimpse.winfo_children()[0].itemcget(item, "text")
                     for item in glimpse.winfo_children()[0].find_all()
                     if glimpse.winfo_children()[0].type(item) == "text"]
            self.assertEqual(texts, ["Home screen", "Steps today", "6482", "steps"])
            # A second change replaces it rather than stacking another.
            p.ns["quick_tile"].set(True, subtitle="On a walk")
            p.settle(0.3)
            self.assertEqual(kit_surfaces.current_peek().apkpy_peek, "Quick settings")
            self.assertEqual(len(kit_surfaces._peeks), 1)

    def test_a_tile_says_on_or_off_when_it_has_no_line_of_its_own(self):
        with Previewed(self.APP, "") as p:
            for active, under in ((True, "On"), (False, "Off")):
                p.ns["quick_tile"].set(active)
                p.settle(0.3)
                canvas = kit_surfaces.current_peek().winfo_children()[0]
                texts = [canvas.itemcget(item, "text") for item in canvas.find_all()
                         if canvas.type(item) == "text"]
                self.assertEqual(texts, ["Quick settings", "Walk", under])

    def test_the_launcher_asks_before_a_widget_is_added(self):
        with Previewed(self.APP, "") as p:
            self.assertEqual(p.ns["home_widget"].pin(), "ok")
            p.settle(0.5)
            sheet = kit_surfaces.current()
            self.assertEqual((sheet.kind, sheet.title), ("pin", "Add to Home screen?"))
            self.assertEqual(p.ns["home_widget"].count(), "0")
            sheet.choose("add")
            p.settle(0.6)
            self.assertEqual(p.ns["home_widget"].count(), "1")

    def test_android_asks_before_a_tile_is_added(self):
        with Previewed(self.APP, "") as p:
            p.ns["quick_tile"].offer(on_result=p.ns["answered"])
            p.settle(0.5)
            sheet = kit_surfaces.current()
            self.assertEqual((sheet.kind, sheet.title), ("tile", "Add Walk to Quick Settings?"))
            sheet.close()
            p.settle(0.6)
            p.ns["quick_tile"].offer(on_result=p.ns["answered"])
            p.settle(0.5)
            kit_surfaces.current().choose("add")
            p.settle(0.6)
            self.assertEqual(p.ns["HEARD"], [(False, "dismissed"), (True, "added")])

    def test_a_banner_takes_its_room_from_the_screen(self):
        with Previewed(self.APP, "") as p:
            body = p.app.body
            before = body.winfo_height()
            self.assertEqual(p.ns["ads"].banner("test"), "ok")
            p.settle(0.3)
            self.assertIs(p.ns["ads"].banner_shown, True)
            frame = p.ns["ads"]._banner.frame
            self.assertEqual(body.winfo_height(), before - kit_surfaces.BANNER_HEIGHT)
            # Along the bottom edge, as wide as the window.
            self.assertEqual(frame.winfo_rooty() + frame.winfo_height(),
                             p.app.root.winfo_rooty() + p.app.root.winfo_height())
            self.assertEqual(frame.winfo_width(), p.app.root.winfo_width())
            p.ns["ads"].hide_banner()
            p.settle(0.3)
            self.assertIs(p.ns["ads"].banner_shown, False)
            self.assertEqual(body.winfo_height(), before)

    def test_a_banner_along_the_top_sits_under_the_clock(self):
        with Previewed(self.APP, "") as p:
            body = p.app.body
            before = (body.winfo_rooty(), body.winfo_height())
            p.ns["ads"].banner("test", position="top")
            p.settle(0.3)
            frame = p.ns["ads"]._banner.frame
            strip = p.app.root.winfo_rooty() + 24
            self.assertEqual(frame.winfo_rooty(), strip)
            self.assertEqual(body.winfo_rooty(), strip + kit_surfaces.BANNER_HEIGHT)
            p.ns["ads"].hide_banner()
            p.settle(0.3)
            self.assertEqual((body.winfo_rooty(), body.winfo_height()), before)

    def test_a_banner_is_its_screens_and_comes_back_with_it(self):
        with Previewed(self.APP, "") as p:
            p.ns["ads"].banner("test")
            p.settle(0.3)
            p.app.render_screen(p.ns["other"])
            p.settle(0.3)
            self.assertIs(p.ns["ads"].banner_shown, False)
            p.app.render_screen(p.ns["home"])
            p.settle(0.3)
            self.assertIs(p.ns["ads"].banner_shown, True)

    def test_a_full_screen_ad_has_the_window_until_it_is_closed(self):
        with Previewed(self.APP, "") as p:
            p.ns["ads"].interstitial("test", on_result=p.ns["answered"])
            p.settle(0.5)
            cover = kit_surfaces.current_cover()
            self.assertEqual(cover.kind, "interstitial")
            root = p.app.root
            self.assertEqual((cover.win.winfo_rootx(), cover.win.winfo_rooty(),
                              cover.win.winfo_width(), cover.win.winfo_height()),
                             (root.winfo_rootx(), root.winfo_rooty(),
                              root.winfo_width(), root.winfo_height()))
            self.assertEqual(p.ns["HEARD"], [])
            # The pointer goes there first, as a mouse does: the Tk of
            # Python 3.8 delivers a click on a canvas item only then.
            cover.canvas.event_generate("<Motion>", x=cover.width - 38, y=56)
            cover.canvas.event_generate("<Button-1>", x=cover.width - 38, y=56)
            p.settle(0.3)
            self.assertIsNone(kit_surfaces.current_cover())
            self.assertEqual(p.ns["HEARD"], [(True, "closed")])

    def test_leaving_a_rewarded_ad_early_gives_the_reward_up(self):
        with Previewed(self.APP, "") as p:
            p.ns["ads"].rewarded("test", on_result=p.ns["answered"])
            p.settle(0.5)
            cover = kit_surfaces.current_cover()
            self.assertGreater(cover.state["left"], 0)
            cover.close(cover.state["left"] <= 0)
            p.settle(0.3)
            self.assertEqual(p.ns["HEARD"], [(False, "skipped")])
            # Staying to the end: the count runs out and the reward is earned.
            p.ns["ads"].rewarded("test", on_result=p.ns["answered"])
            p.settle(0.4)
            cover = kit_surfaces.current_cover()
            cover.state["left"] = 0
            cover.close(cover.state["left"] <= 0)
            p.settle(0.3)
            self.assertEqual(p.ns["HEARD"][-1], (True, rules.AD_REWARD))

    def test_consent_is_googles_form_and_closing_it_settles_nothing(self):
        with Previewed(self.APP, "") as p:
            p.ns["ads"].consent(on_result=p.ns["answered"])
            p.settle(0.5)
            sheet = kit_surfaces.current()
            self.assertEqual((sheet.kind, sheet.app_name), ("consent", "Google"))
            sheet.close()
            p.settle(0.6)
            p.ns["ads"].consent(on_result=p.ns["answered"])
            p.settle(0.5)
            kit_surfaces.current().choose("no")
            p.settle(0.6)
            # Asked and answered: it is not asked again.
            p.ns["ads"].consent(on_result=p.ns["answered"])
            p.settle(0.3)
            self.assertIsNone(kit_surfaces.current())
            self.assertEqual(p.ns["HEARD"], [(False, "failed"), (True, "ok"), (True, "ok")])

    def test_a_flexible_update_is_plays_sheet_and_then_a_download(self):
        with Previewed(self.APP, "") as p:
            p.ns["updates"].start(on_result=p.ns["answered"])
            p.settle(0.5)
            sheet = kit_surfaces.current()
            self.assertEqual((sheet.kind, sheet.app_name), ("update", "Google Play"))
            sheet.choose("no")
            p.settle(0.6)
            self.assertEqual(p.ns["HEARD"], [(False, "cancelled")])
            p.ns["updates"].start(on_result=p.ns["answered"])
            p.settle(0.5)
            kit_surfaces.current().choose("yes")
            p.settle(2.6)
            self.assertEqual(p.ns["HEARD"][-1], (True, "downloaded"))
            self.assertEqual(p.ns["updates"].install(), "ok")

    def test_an_update_that_cannot_wait_takes_the_screen(self):
        with Previewed(self.APP, "") as p:
            p.ns["updates"].start("immediate", on_result=p.ns["answered"])
            p.settle(0.5)
            cover = kit_surfaces.current_cover()
            self.assertEqual(cover.kind, "update")
            box = cover.canvas.bbox("leave")
            # The pointer first, as above.
            cover.canvas.event_generate("<Motion>", x=(box[0] + box[2]) // 2,
                                        y=(box[1] + box[3]) // 2)
            cover.canvas.event_generate("<Button-1>", x=(box[0] + box[2]) // 2,
                                        y=(box[1] + box[3]) // 2)
            p.settle(0.3)
            self.assertEqual(p.ns["HEARD"], [(False, "cancelled")])
            p.ns["updates"].start("immediate", on_result=p.ns["answered"])
            p.settle(0.5)
            cover = kit_surfaces.current_cover()
            box = cover.canvas.bbox("go")
            cover.canvas.event_generate("<Motion>", x=(box[0] + box[2]) // 2,
                                        y=(box[1] + box[3]) // 2)
            cover.canvas.event_generate("<Button-1>", x=(box[0] + box[2]) // 2,
                                        y=(box[1] + box[3]) // 2)
            p.settle(3.2)
            self.assertIsNone(kit_surfaces.current_cover())
            self.assertEqual(p.ns["HEARD"][-1], (True, "ok"))

    def test_health_connect_asks_for_each_kind_by_name(self):
        with Previewed(self.APP, "") as p:
            p.ns["health"].ask("steps, heart_rate, sleep", on_result=p.ns["answered"])
            p.settle(0.5)
            sheet = kit_surfaces.current()
            self.assertEqual((sheet.kind, sheet.app_name), ("health", "Health Connect"))
            self.assertEqual([text for _icon, text in sheet.rows],
                             ["Steps", "Heart rate", "Sleep"])
            sheet.choose("deny")
            p.settle(0.6)
            self.assertIs(p.ns["health"].allowed("steps"), False)
            p.ns["health"].ask("steps", on_result=p.ns["answered"])
            p.settle(0.5)
            kit_surfaces.current().choose("allow")
            p.settle(0.6)
            self.assertIs(p.ns["health"].allowed("steps"), True)
            self.assertEqual(p.ns["HEARD"], [(False, "denied"), (True, "ok")])


if __name__ == "__main__":
    unittest.main()
