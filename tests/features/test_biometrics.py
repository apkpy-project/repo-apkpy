# -*- coding: utf-8 -*-
"""The fingerprint prompt, and the vocabulary the two runtimes share."""

import unittest

from apkpy_lib.core.features import biometrics as codegen
from apkpy_lib.core.compiler import translate_python_to_android


APP_WITH_PROMPT = '''from apkpy_lib import Screen, biometrics, button, label, run, toast
home = Screen(id="home")
label("locked", id="t", screen=home)


def opened(ok, reason):
    if ok:
        toast("in")
    else:
        toast(reason)


def ask():
    biometrics.unlock(title="Unlock", subtitle="Confirm it's you",
                      cancel_text="Use password", on_result=opened)


button("Unlock", id="go", screen=home, command=ask)
run(start_screen=home)
'''

APP_WITHOUT = '''from apkpy_lib import Screen, button, label, run, toast
home = Screen(id="home")
label("plain", id="t", screen=home)
button("Tap", id="go", screen=home, command=lambda: toast("hi"))
run(start_screen=home)
'''


def _java(source):
    files = translate_python_to_android(source)
    return "\n".join(
        body for name, body in files.items() if name.endswith(".java"))


def _manifest(source):
    return translate_python_to_android(source).get("AndroidManifest.xml", "")


class TheVocabularyIsSharedTests(unittest.TestCase):
    """Neither side may invent a word the other does not know."""

    def test_the_previewer_imports_the_compiler_table(self):
        from apkpy_lib.features import biometrics as preview
        self.assertIs(preview.REASONS, codegen.REASONS)
        self.assertIs(preview.biometrics.reasons, codegen.REASONS)

    def test_every_android_error_code_lands_in_the_vocabulary(self):
        for code in list(codegen._ERROR_CODES) + [0, 99, -5]:
            self.assertIn(codegen.reason_for_error_code(code), codegen.REASONS)

    def test_every_status_code_lands_in_the_vocabulary(self):
        for code in list(codegen._STATUS_CODES) + [0, 77]:
            self.assertIn(codegen.reason_for_status_code(code), codegen.REASONS)

    def test_success_is_the_only_word_that_means_yes(self):
        self.assertEqual(codegen.reason_for_status_code(0), codegen.SUCCESS)
        for code in codegen._ERROR_CODES:
            self.assertNotEqual(codegen.reason_for_error_code(code),
                                codegen.SUCCESS)

    def test_a_reason_is_never_empty(self):
        # An app should always have something to say. "" would print nothing.
        for reason in codegen.REASONS:
            self.assertTrue(reason.strip(), reason)

    def test_the_generated_switch_carries_the_whole_table(self):
        runtime = codegen.activity_runtime_java()
        for code, reason in codegen._ERROR_CODES.items():
            self.assertIn('case %d: return "%s";' % (code, reason), runtime)
        for code, reason in codegen._STATUS_CODES.items():
            self.assertIn('case %d: return "%s";' % (code, reason), runtime)


class ThePromptReadsTheSameOnBothSidesTests(unittest.TestCase):

    def test_defaults_are_filled_in_rather_than_left_blank(self):
        prompt = codegen.normalise_prompt()
        self.assertEqual(prompt["title"], codegen.DEFAULT_TITLE)
        self.assertEqual(prompt["cancel_text"], codegen.DEFAULT_CANCEL)
        self.assertEqual(prompt["subtitle"], "")

    def test_allow_pin_removes_the_cancel_button(self):
        # PromptInfo.Builder throws when a negative button and
        # DEVICE_CREDENTIAL are both set, so the Previewer must not draw one.
        prompt = codegen.normalise_prompt(
            title="x", cancel_text="Nope", allow_pin=True)
        self.assertEqual(prompt["cancel_text"], "")
        self.assertTrue(prompt["allow_pin"])

    def test_whitespace_only_words_fall_back_to_the_default(self):
        self.assertEqual(
            codegen.normalise_prompt(title="   ")["title"], codegen.DEFAULT_TITLE)


class TheGeneratedAppTests(unittest.TestCase):

    def test_the_call_reaches_the_activity_with_its_words(self):
        java = _java(APP_WITH_PROMPT)
        self.assertIn('_biometricUnlock("Unlock", "Confirm it\'s you", '
                      '"Use password", false,', java)
        self.assertIn("pythonCallback_opened(success, reason)", java)

    def test_the_runtime_and_the_interface_are_emitted(self):
        java = _java(APP_WITH_PROMPT)
        self.assertIn("private interface BiometricResultCallback", java)
        self.assertIn("androidx.biometric.BiometricPrompt", java)
        self.assertIn("private void _biometricUnlock(", java)

    def test_the_status_is_checked_before_the_prompt_is_built(self):
        # A phone with no sensor has to get a reason, not a dialog that
        # cannot succeed.
        java = _java(APP_WITH_PROMPT)
        check = java.index("canAuthenticate(")
        build = java.index("new androidx.biometric.BiometricPrompt(")
        self.assertLess(check, build)

    def test_a_failed_scan_is_not_reported_as_a_result(self):
        # Overriding onAuthenticationFailed would report a failure the person
        # has not had yet: Android keeps the prompt open and lets them retry.
        # The comment above it explains why, so match the override itself.
        self.assertNotIn("public void onAuthenticationFailed",
                         codegen.activity_runtime_java())

    def test_it_survives_a_lambda_that_calls_a_helper(self):
        """The Activity has TWO command dispatchers, not one.

        `command=ask` is emitted by the first; `command=lambda: ask()` routes
        through the second, which generates the body of `pythonCallback_*`.
        Wiring only one is the failure this project calls bug class number
        one: the command silently disappears and the button does nothing.
        """
        source = APP_WITH_PROMPT.replace(
            'command=ask)', 'command=lambda: ask())')
        java = _java(source)
        calls = [line for line in java.splitlines()
                 if "_biometricUnlock(" in line and "private void" not in line]
        self.assertTrue(calls, "the call vanished through the second dispatcher")

    def test_a_direct_command_is_not_invoked_twice(self):
        # The button inlines the body AND a reusable pythonCallback_* exists.
        # They are alternatives: onClick must not also call the method, or the
        # prompt would open twice on one tap.
        java = _java(APP_WITH_PROMPT)
        click = java.index("public void onClick(View v) {")
        end = java.index("}", java.index("_biometricUnlock(", click))
        self.assertNotIn("pythonCallback_ask()", java[click:end])

    def test_the_permission_is_declared(self):
        self.assertIn("android.permission.USE_BIOMETRIC",
                      _manifest(APP_WITH_PROMPT))

    def test_an_app_that_never_asks_carries_none_of_it(self):
        java = _java(APP_WITHOUT)
        self.assertNotIn("BiometricResultCallback", java)
        self.assertNotIn("androidx.biometric", java)
        self.assertNotIn("USE_BIOMETRIC", _manifest(APP_WITHOUT))

    def test_the_gradle_dependency_is_gated_on_the_class_the_app_emits(self):
        # cli.py switches the dependency on by looking for this exact name.
        self.assertIn("androidx.biometric.BiometricPrompt", _java(APP_WITH_PROMPT))
        self.assertNotIn("androidx.biometric.BiometricPrompt", _java(APP_WITHOUT))

    def test_a_quote_in_the_title_does_not_break_the_java(self):
        source = APP_WITH_PROMPT.replace('title="Unlock"', r'title="Say \"hi\""')
        java = _java(source)
        self.assertIn(r'_biometricUnlock("Say \"hi\""', java)
        for opener, closer in (("{", "}"), ("(", ")")):
            self.assertEqual(java.count(opener), java.count(closer))


class ThePreviewerAnswersWithoutAWindowTests(unittest.TestCase):

    def test_no_window_reports_unavailable_rather_than_raising(self):
        from apkpy_lib import ui
        from apkpy_lib.features import biometrics as preview
        if ui._app._instance is not None:
            self.skipTest("a Previewer window already exists in this process")
        seen = []
        preview.biometrics.unlock(
            title="x", on_result=lambda ok, why: seen.append((ok, why)))
        self.assertEqual(seen, [(False, "unavailable")])

    def test_the_prompt_never_constructs_a_window(self):
        # ui._app is a lazy proxy. Reaching for .root here would open an empty
        # Previewer from `apkpy build` alone.
        from apkpy_lib import ui
        from apkpy_lib.features import biometrics as preview
        if ui._app._instance is not None:
            self.skipTest("a Previewer window already exists in this process")
        preview.biometrics.unlock(title="x", on_result=lambda *_: None)
        self.assertIsNone(ui._app._instance)

    def test_the_reason_it_reports_is_in_the_shared_table(self):
        from apkpy_lib import ui
        from apkpy_lib.features import biometrics as preview
        if ui._app._instance is not None:
            self.skipTest("a Previewer window already exists in this process")
        seen = []
        preview.biometrics.unlock(on_result=lambda ok, why: seen.append(why))
        self.assertIn(seen[0], codegen.REASONS)


class TheIconsTheFeatureNeedsTests(unittest.TestCase):

    def test_the_catalogue_has_the_three_glyphs(self):
        from apkpy_lib import icons
        for name in ("fingerprint", "lock", "lock_open"):
            self.assertIsNotNone(icons.resolve(name), name)
            self.assertNotEqual(icons.resolve(name), icons.resolve("circle"), name)

    def test_both_backends_draw_the_same_fingerprint(self):
        from apkpy_lib import icons
        from apkpy_lib.core.compiler import _material_icon_path
        for name in ("fingerprint", "lock", "lock_open"):
            self.assertEqual(_material_icon_path(name), icons.resolve(name), name)

    def test_the_aliases_reach_the_real_glyph(self):
        from apkpy_lib import icons
        self.assertEqual(icons.resolve("biometrics"), icons.resolve("fingerprint"))
        self.assertEqual(icons.resolve("unlock"), icons.resolve("lock_open"))


if __name__ == "__main__":
    unittest.main()
