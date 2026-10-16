# -*- coding: utf-8 -*-
"""Languages, crash reports and code scanning.

Three things a business app is asked for and could not have. What they share
is that each one was previously impossible rather than merely awkward: text
was written into the layout so an app spoke one language; a crash on somebody
else's phone was invisible; and reading a barcode -- the sensor most warehouse
and ticketing apps are built around -- had no answer at all.
"""

import unittest

from apkpy_lib.core import i18n
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import scan as scan_feature


def _files(body, header=''):
    source = (
        'from apkpy_lib import (Screen, button, crash, https, label, language,\n'
        '                       lifecycle, run, scan, t, translations)\n'
        '%s'
        'home = Screen(id="home")\n'
        'out = label("", id="out", screen=home)\n'
        '\n\ndef go():\n%s\n\n\n'
        'button("Go", id="b", screen=home, command=go)\n'
        'run(start_screen=home)\n'
    ) % (header, body)
    return translate_python_to_android(source)


def _java(body, header=''):
    files = _files(body, header)
    if 'error.txt' in files:
        raise AssertionError(files['error.txt'][:400])
    return "\n".join(v for k, v in files.items() if k.endswith('.java'))


TABLE = ('translations({"en": {"save": "Save"}, "pt": {"save": "Guardar"}},\n'
         '             default="en")\n')


class TheLanguageTableTests(unittest.TestCase):
    """The rules both runtimes read, so neither can drift from the other."""

    def test_a_region_becomes_androids_own_folder_name(self):
        # Without the r, the folder never matches and every translation in it
        # is ignored on every device -- silently.
        self.assertEqual(i18n.resource_dir('pt'), 'values-pt')
        self.assertEqual(i18n.resource_dir('pt-BR'), 'values-pt-rBR')

    def test_a_tag_android_cannot_match_is_refused(self):
        self.assertIsNone(i18n.resource_dir('zh-Hans'))
        self.assertIsNone(i18n.canonical('not a language'))

    def test_falling_back_follows_android(self):
        # Full tag, then the language alone, then the default.
        self.assertEqual(i18n.match_language('pt-BR', ['pt', 'en'], 'en'), 'pt')
        self.assertEqual(i18n.match_language('fr', ['pt', 'en'], 'en'), 'en')
        self.assertEqual(i18n.match_language('pt', ['pt-BR', 'en'], 'en'), 'pt-BR')

    def test_an_apostrophe_is_escaped_because_aapt_reads_it(self):
        # An unescaped apostrophe is a build error, and most languages have one.
        built = i18n.strings_xml({'x': "L'ecran"})
        self.assertIn("L\\'ecran", built)


class TheLanguagesReachThePhoneTests(unittest.TestCase):

    def test_each_language_gets_its_own_resource_file(self):
        files = _files('    out.set_value(t("save"))\n', header=TABLE)
        self.assertIn('res/values/apkpy_strings.xml', files)
        self.assertIn('res/values-pt/apkpy_strings.xml', files)
        self.assertIn('Guardar', files['res/values-pt/apkpy_strings.xml'])

    def test_a_components_text_becomes_a_resource_reference(self):
        source = (
            'from apkpy_lib import Screen, label, run, t, translations\n'
            + TABLE +
            'home = Screen(id="home")\n'
            'label(t("save"), id="x", screen=home)\n'
            'run(start_screen=home)\n'
        )
        layout = translate_python_to_android(source)['res/layout/activity_screen_home.xml']
        self.assertIn('android:text="@string/apkpy_save"', layout)
        self.assertNotIn(i18n.MARK, layout)

    def test_a_word_read_while_running_asks_android_for_it(self):
        java = _java('    out.set_value(t("save"))\n', header=TABLE)
        self.assertIn('getString(R.string.apkpy_save)', java)

    def test_a_key_missing_from_the_default_language_is_refused(self):
        """Android answers @string/x from res/values/ and nowhere else.

        A key only translated into Portuguese would compile to a reference
        with nothing behind it -- an aapt error against generated XML, in a
        file nobody wrote.
        """
        header = ('translations({"en": {"save": "Save"},\n'
                  '              "pt": {"save": "Guardar", "extra": "Mais"}},\n'
                  '             default="en")\n')
        text = _files('    out.set_value(t("extra"))\n', header=header)['error.txt']
        self.assertIn('default language', text)

    def test_a_translation_joined_to_other_text_is_refused(self):
        # Android draws a reference as text unless it is the whole value.
        source = (
            'from apkpy_lib import Screen, label, run, t, translations\n'
            + TABLE +
            'home = Screen(id="home")\n'
            'label("Hello " + t("save"), id="x", screen=home)\n'
            'run(start_screen=home)\n'
        )
        self.assertIn('error.txt', translate_python_to_android(source))

    def test_switching_language_uses_appcompat_and_survives_a_restart(self):
        java = _java('    language.set("pt")\n', header=TABLE)
        self.assertIn('setApplicationLocales', java)
        # AppCompat only persists the choice from API 33; below that the app
        # has to put it back itself on the next launch.
        self.assertIn('_apkpyStorageSet("__apkpy_language"', java)
        self.assertIn('_apkpyStorageGet("__apkpy_language"', java)

    def test_an_app_with_no_table_gains_nothing(self):
        files = _files('    out.set_value("plain")\n')
        self.assertNotIn('res/values/apkpy_strings.xml', files)
        java = "\n".join(v for k, v in files.items() if k.endswith('.java'))
        self.assertNotIn('__apkpy_language', java)


class ThePreviewerSpeaksTheSameLanguageTests(unittest.TestCase):

    def setUp(self):
        from apkpy_lib import ui
        ui.storage.delete(ui.LanguageAPI._KEY)

    tearDown = setUp

    def test_the_words_come_from_the_same_table(self):
        from apkpy_lib import language, t, translations
        translations({"en": {"save": "Save"}, "pt": {"save": "Guardar"}},
                     default="en")
        language.set("pt")
        self.assertEqual(t("save"), "Guardar")
        language.set("en")
        self.assertEqual(t("save"), "Save")

    def test_it_falls_back_the_way_the_phone_does(self):
        from apkpy_lib import language, t, translations
        translations({"en": {"save": "Save"}, "pt": {"save": "Guardar"}},
                     default="en")
        language.set("pt-BR")           # only pt is declared
        self.assertEqual(t("save"), "Guardar")
        language.set("fr")              # nothing close
        self.assertEqual(t("save"), "Save")

    def test_a_key_missing_from_every_language_is_refused_when_declared(self):
        from apkpy_lib import translations
        with self.assertRaises(ValueError):
            translations({"en": {"a": "A"}, "pt": {"a": "A", "b": "B"}},
                         default="en")

    def test_the_desktop_language_is_read_as_a_tag(self):
        """Windows answers "Portuguese_Portugal", which matches nothing.

        Left as it came, a Portuguese desktop previewed the fallback language
        while the phone showed Portuguese -- a divergence with no symptom
        except the wrong words.
        """
        from apkpy_lib import ui
        tag = ui._system_language()
        self.assertNotIn('_', tag)
        if tag:
            self.assertIsNotNone(i18n.normalise_tag(tag), tag)


class TheCrashReportTests(unittest.TestCase):

    def test_the_handler_is_installed_before_anything_can_fail(self):
        java = _java('    out.set_value(crash.last())\n')
        self.assertIn('ApkpyCrashHandler.install(this);', java)
        self.assertLess(java.index('ApkpyCrashHandler.install'),
                        java.index('setContentView'))

    def test_it_hands_the_crash_on_instead_of_swallowing_it(self):
        """Android's own handler is what stops the app and tells the person.

        Swallowing the throwable leaves a frozen window that never comes
        back, which is worse than the crash it was hiding.
        """
        files = _files('    out.set_value(crash.last())\n')
        handler = files['java/ApkpyCrashHandler.java']
        self.assertIn('previous.uncaughtException(thread, error)', handler)
        self.assertIn('killProcess', handler)

    def test_writing_the_report_cannot_itself_crash_the_handler(self):
        handler = _files('    out.set_value(crash.last())\n')['java/ApkpyCrashHandler.java']
        self.assertIn('catch (Throwable ignored)', handler)

    def test_installing_twice_is_harmless(self):
        handler = _files('    out.set_value(crash.last())\n')['java/ApkpyCrashHandler.java']
        self.assertIn('instanceof ApkpyCrashHandler', handler)

    def test_an_app_that_never_asks_gets_no_handler(self):
        files = _files('    out.set_value("plain")\n')
        self.assertNotIn('java/ApkpyCrashHandler.java', files)

    def test_the_previewer_records_and_forgets_the_same_way(self):
        from apkpy_lib import crash, ui
        crash.clear()
        self.assertEqual(crash.last(), "")
        try:
            raise ValueError("boom")
        except ValueError as problem:
            ui._record_preview_crash(problem)
        report = crash.last()
        self.assertIn("ValueError: boom", report)
        self.assertIn("when:", report)
        crash.clear()
        self.assertEqual(crash.last(), "")


class TheCodeScannerTests(unittest.TestCase):

    def test_it_asks_for_googles_scanner_rather_than_the_camera(self):
        """No CAMERA permission: the camera runs in Play services.

        One fewer permission on the listing, and one fewer argument in a
        company's security review.
        """
        files = _files('    scan.code(on_result=go)\n')
        java = "\n".join(v for k, v in files.items() if k.endswith('.java'))
        self.assertIn('GmsBarcodeScanning', java)
        self.assertNotIn('android.permission.CAMERA',
                         files['AndroidManifest.xml'])

    def test_backing_out_answers_cancelled_rather_than_nothing(self):
        # Without the cancel listener the screen waits for a value that never
        # arrives, which looks exactly like a hang.
        java = _java('    scan.code(on_result=go)\n')
        self.assertIn('addOnCanceledListener', java)
        self.assertIn('"cancelled"', java)

    def test_a_code_it_cannot_read_is_not_reported_as_an_empty_one(self):
        java = _java('    scan.code(on_result=go)\n')
        self.assertIn('"unreadable"', java)

    def test_asking_for_one_symbology_asks_android_for_that_one(self):
        java = _java('    scan.code(on_result=go, formats=["qr"])\n')
        self.assertIn('Barcode.FORMAT_QR_CODE', java)
        self.assertIn('setBarcodeFormats', java)

    def test_a_format_nobody_recognises_is_refused(self):
        # Dropping it would read every symbology instead -- the wrong label
        # off the same box, into the right field.
        text = _files('    scan.code(on_result=go, formats=["qr", "nonsense"])\n')['error.txt']
        self.assertIn('nonsense', text)

    def test_the_names_map_to_real_barcode_constants(self):
        self.assertEqual(scan_feature.normalise_formats(['qr', 'ean13']),
                         ('QR_CODE', 'EAN_13'))
        self.assertEqual(scan_feature.normalise_formats([]), ())

    def test_an_app_that_never_scans_carries_no_scanner(self):
        java = _java('    out.set_value("plain")\n')
        self.assertNotIn('_apkpyScanCode', java)


if __name__ == "__main__":
    unittest.main()


A_PIN = 'sha256/K87oWBWM9UZfyddvDfoxL+8lpNyoUB2ptGtn0fv6G2Q='
B_PIN = 'sha256/JbQbUG5JMJUoI6brnx0x3vZF6jilxsapbXGVfjhN8Fg='


def _pinned_app(call):
    source = (
        'from apkpy_lib import Screen, https, label, run\n'
        '%s\n'
        'home = Screen(id="home")\n'
        'label("x", id="o", screen=home)\n'
        'run(start_screen=home)\n' % call
    )
    return translate_python_to_android(source)


class ThePinningTests(unittest.TestCase):
    """Which certificate counts for a host -- written as configuration."""

    def test_one_pin_is_refused_because_it_bricks_the_app(self):
        """A single pin is an outage waiting for a certificate renewal.

        The day it is replaced every copy of the app stops reaching its own
        server at once, and only a store update fixes it. The spare pin is the
        difference between that and a routine.
        """
        from apkpy_lib.core.features import pinning
        self.assertIn('only one pin', pinning.check_pins([A_PIN]))
        self.assertEqual(pinning.check_pins([A_PIN, B_PIN]), '')

    def test_the_same_pin_twice_is_not_two_pins(self):
        from apkpy_lib.core.features import pinning
        self.assertIn('listed twice', pinning.check_pins([A_PIN, A_PIN]))

    def test_a_star_is_refused_rather_than_pinning_nothing(self):
        from apkpy_lib.core.features import pinning
        self.assertIn('include_subdomains', pinning.check_host('*.example.com'))

    def test_the_config_is_android_s_own_format(self):
        files = _pinned_app(
            'https.pin("api.example.com", ["%s", "%s"], expires="2027-06-01")'
            % (A_PIN, B_PIN))
        config = files['res/xml/apkpy_network_security.xml']
        self.assertIn('<pin-set expiration="2027-06-01">', config)
        self.assertIn('<pin digest="SHA-256">K87oWBWM9UZ', config)
        self.assertIn('android:networkSecurityConfig="@xml/apkpy_network_security"',
                      files['AndroidManifest.xml'])

    def test_a_debug_build_can_still_be_watched_through_a_proxy(self):
        # Android reads debug-overrides only when the app is debuggable, so a
        # release build is untouched -- and without it, pinning would mean
        # never being able to look at your own traffic again.
        config = _pinned_app(
            'https.pin("api.example.com", ["%s", "%s"])' % (A_PIN, B_PIN)
        )['res/xml/apkpy_network_security.xml']
        self.assertIn('<debug-overrides>', config)
        self.assertIn('src="user"', config)

    def test_a_bad_pin_stops_the_build_rather_than_the_app(self):
        files = _pinned_app('https.pin("api.example.com", ["nonsense", "%s"])' % B_PIN)
        self.assertIn('error.txt', files)
        self.assertIn('nonsense', files['error.txt'])

    def test_an_app_that_pins_nothing_gets_no_config(self):
        files = _pinned_app('')
        self.assertNotIn('res/xml/apkpy_network_security.xml', files)
        self.assertNotIn('networkSecurityConfig', files['AndroidManifest.xml'])

    def test_the_previewer_refuses_a_request_whose_pin_does_not_match(self):
        """The whole point: a wrong pin shows up here, not on a phone.

        Skipped when the machine is offline or has no ``cryptography`` -- a
        handshake that never happened is not a verdict.
        """
        from apkpy_lib import https, ui
        live = ui._live_pin('github.com')
        if live is None:
            self.skipTest('no network, or cryptography is not installed')
        wrong = 'sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
        https.pin('github.com', [wrong, B_PIN])
        ui.HttpsAPI._checked.clear()
        refusal = https._refuse_unpinned('https://github.com/robots.txt')
        self.assertIn('does not match any pin', refusal)
        self.assertIn(live, refusal)      # the real one, ready to copy

        https.pin('github.com', [live, B_PIN])
        ui.HttpsAPI._checked.clear()
        self.assertEqual(https._refuse_unpinned('https://github.com/robots.txt'), '')
        ui._PINNED_HOSTS.pop('github.com', None)


class TheForcedUpdateTests(unittest.TestCase):

    APP = (
        'from apkpy_lib import Screen, app, button, label, modal, run\n'
        'home = Screen(id="home")\n'
        'label("x", id="o", screen=home)\n'
        'wall = modal("Update", content="c", confirm_text="Update", %s'
        'on_confirm=lambda: app.open_store())\n'
        'button("go", id="b", screen=home, command=lambda: wall.open())\n'
        'run(start_screen=home)\n'
    )

    def _java(self, extra=''):
        files = translate_python_to_android(self.APP % extra)
        if 'error.txt' in files:
            raise AssertionError(files['error.txt'][:300])
        return files['java/Screen_homeActivity.java']

    def test_a_blocking_dialog_has_no_way_out(self):
        java = self._java('dismissable=False, ')
        self.assertIn('builder.setCancelable(false);', java)
        # A Cancel on a screen nobody can leave is a button that does nothing.
        self.assertNotIn('setNegativeButton', java)

    def test_an_ordinary_dialog_is_untouched(self):
        java = self._java()
        self.assertNotIn('setCancelable(false)', java)
        self.assertIn('setNegativeButton', java)

    def test_the_version_comes_from_the_installed_package(self):
        # Not from the source: what matters is the build actually running.
        java = self._java()
        self.assertIn('getPackageInfo(getPackageName(), 0)', java)
        self.assertIn('getLongVersionCode()', java)

    def test_opening_the_store_falls_back_to_the_web_page(self):
        # A managed distribution lands on devices without the Play app, which
        # are exactly the ones that need the fallback.
        java = self._java()
        self.assertIn('market://details?id=', java)
        self.assertIn('https://play.google.com/store/apps/details?id=', java)

    def test_the_previewer_reads_the_same_version(self):
        from apkpy_lib import app
        self.assertTrue(app.version_name())
        self.assertTrue(app.version_code().isdigit())


class TheAccessibilityTests(unittest.TestCase):
    """What a screen reader announces, and what nobody can read.

    Both fail without a symptom: an undescribed image is announced as nothing
    at all, and text below the contrast minimum looks fine to whoever chose
    the colours. Neither shows up in a build, a test or a screenshot.
    """

    @staticmethod
    def _audit(body, style=''):
        import contextlib
        import io as _io
        source = (
            'from apkpy_lib import Screen, Theme, button, image, label, run\n'
            'home = Screen(id="home")\n'
            '%s\n'
            'style = """%s"""\n'
            'run(start_screen=home)\n' % (body, style)
        )
        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            translate_python_to_android(source)
        return buffer.getvalue()

    def test_the_contrast_maths_is_wcags_and_not_an_approximation(self):
        from apkpy_lib.core.features import accessibility as a
        for front, back, expected in (('#000000', '#FFFFFF', 21.0),
                                      ('#FFFFFF', '#FFFFFF', 1.0),
                                      ('#767676', '#FFFFFF', 4.54),
                                      ('#0000FF', '#FFFFFF', 8.59)):
            self.assertAlmostEqual(a.contrast_ratio(front, back), expected, delta=0.02)

    def test_large_text_is_measured_in_points_not_in_sp(self):
        """WCAG says 18pt, or 14pt bold. Android sizes text in sp.

        Written as 18 and 14 the thresholds let 18sp body text pass at 3:1
        when it needs 4.5:1 -- the kind of nearly-right this check exists to
        catch, and it was nearly-right here first.
        """
        from apkpy_lib.core.features import accessibility as a
        self.assertEqual(a.required_contrast(18, bold=False), 4.5)
        self.assertEqual(a.required_contrast(24, bold=False), 3.0)
        self.assertEqual(a.required_contrast(18, bold=True), 4.5)
        self.assertEqual(a.required_contrast(19, bold=True), 3.0)

    def test_an_image_with_no_description_is_named(self):
        found = self._audit('image("p.png", id="photo", screen=home)')
        self.assertIn('U2035', found)
        self.assertIn('home.photo', found)

    def test_decoration_is_marked_as_such_and_not_nagged_about(self):
        source = ('from apkpy_lib import Screen, image, run\n'
                  'home = Screen(id="home")\n'
                  'image("bg.png", id="deco", screen=home, describe="")\n'
                  'run(start_screen=home)\n')
        files = translate_python_to_android(source)
        layout = files['res/layout/activity_screen_home.xml']
        # TalkBack skips it instead of reading out a file name.
        self.assertIn('android:importantForAccessibility="no"', layout)
        self.assertNotIn('U2035', self._audit(
            'image("bg.png", id="deco", screen=home, describe="")'))

    def test_a_description_reaches_the_layout(self):
        source = ('from apkpy_lib import Screen, image, run\n'
                  'home = Screen(id="home")\n'
                  'image("p.png", id="photo", screen=home, describe="The team")\n'
                  'run(start_screen=home)\n')
        layout = translate_python_to_android(source)['res/layout/activity_screen_home.xml']
        self.assertIn('android:contentDescription="The team"', layout)

    def test_an_icon_only_button_is_announced(self):
        found = self._audit('button("", id="gear", screen=home, icon="settings")')
        self.assertIn('home.gear', found)
        self.assertNotIn('U2035', self._audit(
            'button("", id="gear", screen=home, icon="settings", '
            'describe="Settings")'))

    def test_a_button_with_words_needs_no_description(self):
        self.assertNotIn('U2035', self._audit(
            'button("Save", id="save", screen=home)'))

    def test_low_contrast_text_is_named_with_its_numbers(self):
        found = self._audit('label("Hi", id="t", screen=home)',
                            style='\nhome { background-color: #FFFFFF; }\n'
                                  't { color: #AAAAAA; }\n')
        self.assertIn('home.t', found)
        self.assertIn(':1', found)

    def test_the_background_is_the_one_actually_painted(self):
        """Reading only body/theme said white for every app.

        Apps paint the background on the screen itself, so the check reported
        white-on-white at 1.05:1 for text that is perfectly legible -- and a
        check that cries wolf is a check somebody turns off.
        """
        found = self._audit('label("Hi", id="t", screen=home)',
                            style='\nhome { background-color: #0F172A; }\n'
                                  't { color: #F8FAFC; }\n')
        self.assertNotIn('U2035', found)

    def test_a_tap_target_under_a_fingertip_is_named(self):
        found = self._audit('button("Go", id="tiny", screen=home)',
                            style='\ntiny { height: 32px; }\n')
        self.assertIn('fingertip', found)

    def test_it_reports_and_lets_the_build_finish(self):
        # Every app has an image somebody forgot to describe. Refusing to
        # build would only teach people to switch the check off.
        source = ('from apkpy_lib import Screen, image, run\n'
                  'home = Screen(id="home")\n'
                  'image("p.png", id="photo", screen=home)\n'
                  'run(start_screen=home)\n')
        files = translate_python_to_android(source)
        self.assertNotIn('error.txt', files)
        self.assertIn('res/layout/activity_screen_home.xml', files)

    def test_a_clean_screen_says_nothing_at_all(self):
        self.assertEqual(self._audit(
            'label("Hi", id="t", screen=home)\n'
            'image("p.png", id="p", screen=home, describe="A photo")',
            style='\nhome { background-color: #FFFFFF; }\nt { color: #111111; }\n'
        ).strip(), '')



    # -- The background a component is really sitting on -----------------

    CARD = ('card = container(id="card", screen=home)\n'
            'label("TOTAL", id="kicker", parent=card)\n'
            'label("30.12", id="total", parent=card)\n')

    @staticmethod
    def _audit_with_container(body, style=''):
        import contextlib
        import io as _io
        source = (
            'from apkpy_lib import Screen, Theme, container, label, run\n'
            'home = Screen(id="home")\n'
            '%s\n'
            'style = """%s"""\n'
            'run(start_screen=home, theme=Theme(mode="light", '
            'background="#F3F0E9"))\n' % (body, style)
        )
        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            translate_python_to_android(source)
        return buffer.getvalue()

    def test_text_on_a_coloured_card_is_measured_against_the_card(self):
        """White on a navy card is 13:1, and it was reported as 1.14:1.

        The cascade starts at ``body``, which carries the theme's page
        background, so every component's merged style claimed to paint the
        page -- the container's own colour was computed, passed down, and
        then never used. A check that cries wolf gets switched off.
        """
        found = self._audit_with_container(self.CARD, (
            'card { background-color: #16324F; padding: 20px; }'
            'kicker { color: #C9D6E4; font-size: 11px; }'
            'total { color: #FFFFFF; font-size: 30px; }'))
        self.assertNotIn('U2035', found)

    def test_white_on_the_page_background_is_still_caught(self):
        found = self._audit_with_container(self.CARD, (
            'card { padding: 20px; }'
            'kicker { color: #FFFFFF; font-size: 11px; }'
            'total { color: #FFFFFF; font-size: 30px; }'))
        self.assertIn('U2035', found)
        self.assertIn('home.kicker', found)

    def test_a_card_colour_written_as_a_token_works_the_same_way(self):
        found = self._audit_with_container(self.CARD, (
            'card { background-color: var(--primary); padding: 20px; }'
            'kicker { color: #FFFFFF; font-size: 11px; }'
            'total { color: #FFFFFF; font-size: 30px; }'))
        self.assertNotIn('U2035', found)

    def test_a_nested_container_without_a_colour_keeps_the_one_above(self):
        body = ('outer = container(id="outer", screen=home)\n'
                'inner = container(id="inner", parent=outer)\n'
                'label("30.12", id="total", parent=inner)\n')
        found = self._audit_with_container(body, (
            'outer { background-color: #16324F; padding: 20px; }'
            'inner { padding: 8px; }'
            'total { color: #FFFFFF; font-size: 30px; }'))
        self.assertNotIn('U2035', found)

class TheLabelBackgroundTests(unittest.TestCase):
    """`background-color` on a label reached the Previewer and vanished.

    The TextView never carried a background at all, so a band of colour with
    dark text on it looked right on the desktop and came out as invisible text
    on the phone. Found while photographing something else, which is the only
    way it could have been found.
    """

    @staticmethod
    def _files(style):
        source = ('from apkpy_lib import Screen, label, run\n'
                  'home = Screen(id="home")\n'
                  'label("Banner", id="t", screen=home)\n'
                  'label("Plain", id="u", screen=home)\n'
                  'style = """%s"""\n'
                  'run(start_screen=home)\n' % style)
        return translate_python_to_android(source)

    def test_a_declared_background_reaches_the_layout(self):
        files = self._files('\nt { background-color: #C96442; color: #FFFFFF; }\n')
        layout = files['res/layout/activity_screen_home.xml']
        self.assertIn('android:background="@drawable/t_shape"', layout)
        self.assertIn('res/drawable/t_shape.xml', files)

    def test_a_label_without_one_gains_nothing(self):
        # No app should grow a drawable it never asked for.
        files = self._files('\nt { background-color: #C96442; color: #FFFFFF; }\n')
        layout = files['res/layout/activity_screen_home.xml']
        plain = layout[layout.index('Plain') - 400:layout.index('Plain')]
        self.assertNotIn('android:background', plain)

    def test_the_page_colour_is_not_painted_over_every_label(self):
        """The cascade folds `body` into every component.

        Without reading the label's own background, each one would paint the
        screen colour over the card or row it sits on -- the same bug
        containers had.
        """
        files = self._files('\nbody { background-color: #101010; }\n')
        layout = files['res/layout/activity_screen_home.xml']
        self.assertNotIn('android:background="@drawable/t_shape"', layout)

    def test_the_contrast_check_now_measures_a_real_background(self):
        """The audit read the declared colour; the phone painted nothing.

        So it was reporting a ratio against a background that did not exist.
        Now that the band is painted, the number describes what is on screen.
        """
        import contextlib
        import io as _io
        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            files = self._files('\nt { background-color: #C96442; color: #1B1B19; }\n')
        self.assertIn('android:background="@drawable/t_shape"',
                      files['res/layout/activity_screen_home.xml'])
        # 
        found = buffer.getvalue()
        if 'U2035' in found:
            self.assertIn('home.t', found)
