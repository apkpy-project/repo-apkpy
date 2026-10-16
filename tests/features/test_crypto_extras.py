# -*- coding: utf-8 -*-
"""Backup that does not lose data, secure random, hashing, and FLAG_SECURE."""

import hashlib
import re
import unittest

from apkpy_lib.core.compiler import translate_python_to_android, _generate_manifest


def _files(source):
    return translate_python_to_android(source)


def _java(source):
    return "\n".join(b for n, b in _files(source).items() if n.endswith(".java"))


PLAIN = '''from apkpy_lib import Screen, button, label, run, storage
home = Screen(id="home")
label("x", id="t", screen=home)


def save():
    storage.set("k", "v")


button("Save", id="b", screen=home, command=save)
run(start_screen=home)
'''


class TheBackupDataLossTests(unittest.TestCase):
    """Changing phone used to empty everything the app had stored.

    Auto-backup copies SharedPreferences to a new device. The AES key that
    encrypted them lives in the old phone's Keystore and does not travel, so
    the restored app decrypted every value to "" and reported it as never
    saved -- no error, no warning, months after the fact.
    """

    def test_the_encrypted_store_is_excluded_from_backup(self):
        rules = _files(PLAIN)["res/xml/apkpy_backup_rules.xml"]
        self.assertIn('domain="sharedpref" path="apkpy_storage.xml"', rules)

    def test_a_direct_device_transfer_is_excluded_too(self):
        # Phone-to-phone transfer cannot carry a Keystore key either.
        rules = _files(PLAIN)["res/xml/apkpy_backup_rules.xml"]
        transfer = rules[rules.index("<device-transfer>"):]
        self.assertIn("apkpy_storage.xml", transfer)

    def test_older_android_gets_the_rules_it_reads(self):
        # Below API 31 the attribute is fullBackupContent, not
        # dataExtractionRules, and an app that only sets the new one is
        # unprotected on every older phone.
        files = _files(PLAIN)
        self.assertIn("res/xml/apkpy_backup_legacy.xml", files)
        self.assertIn("apkpy_storage.xml", files["res/xml/apkpy_backup_legacy.xml"])

    def test_the_manifest_points_at_both(self):
        manifest = _files(PLAIN)["AndroidManifest.xml"]
        self.assertIn('android:dataExtractionRules="@xml/apkpy_backup_rules"', manifest)
        self.assertIn('android:fullBackupContent="@xml/apkpy_backup_legacy"', manifest)

    def test_the_stored_login_token_stays_home_as_well(self):
        rules = _files(PLAIN)["res/xml/apkpy_backup_rules.xml"]
        self.assertIn("apkpy_auth.xml", rules)


class TheSecureRandomTests(unittest.TestCase):

    def test_a_token_is_hex_of_the_length_asked_for(self):
        from apkpy_lib import crypto
        value = crypto.token(24)
        self.assertEqual(len(value), 48)
        self.assertTrue(re.fullmatch("[0-9a-f]+", value))

    def test_two_tokens_differ(self):
        from apkpy_lib import crypto
        self.assertNotEqual(crypto.token(16), crypto.token(16))

    def test_android_uses_a_secure_source(self):
        # java.util.Random gives away the rest of its output from two draws.
        java = _java(PLAIN.replace('storage.set("k", "v")',
                                   'storage.set("k", crypto.token(16))')
                     .replace("import Screen,", "import Screen, crypto,"))
        token = java[java.index("private String _apkpyToken(int count)"):]
        token = token[:token.index("private String _apkpySha256(")]
        self.assertIn("java.security.SecureRandom", token)
        # random.choice() and randint() keep java.util.Random on purpose --
        # shuffling a list is not a secret. Only the token must be strong.
        self.assertNotIn("java.util.Random", token)

    def test_the_length_is_clamped_rather_than_trusted(self):
        java = _java(PLAIN.replace('storage.set("k", "v")',
                                   'storage.set("k", crypto.token(9999))')
                     .replace("import Screen,", "import Screen, crypto,"))
        self.assertIn("_apkpyToken(64)", java)


class TheHashingTests(unittest.TestCase):

    def test_the_previewer_produces_real_sha256(self):
        from apkpy_lib import crypto
        self.assertEqual(crypto.hash("abc"),
                         hashlib.sha256(b"abc").hexdigest())

    def test_android_asks_for_the_same_algorithm(self):
        java = _java(PLAIN.replace('storage.set("k", "v")',
                                   'storage.set("k", crypto.hash("abc"))')
                     .replace("import Screen,", "import Screen, crypto,"))
        self.assertIn('getInstance("SHA-256")', java)

    def test_a_file_that_cannot_be_read_answers_the_same_on_both_sides(self):
        from apkpy_lib import crypto
        self.assertEqual(crypto.hash_file("/definitely/not/here"), "")
        java = _java(PLAIN.replace('storage.set("k", "v")',
                                   'storage.set("k", crypto.hash_file("/x"))')
                     .replace("import Screen,", "import Screen, crypto,"))
        head = java[java.index("_apkpySha256File(String path)"):]
        self.assertIn('return "";', head[:900])

    def test_a_picked_file_is_read_through_the_resolver(self):
        # files.pick returns a content:// Uri, which FileInputStream cannot open.
        java = _java(PLAIN.replace('storage.set("k", "v")',
                                   'storage.set("k", crypto.hash_file("/x"))')
                     .replace("import Screen,", "import Screen, crypto,"))
        self.assertIn('path.startsWith("content://")', java)

    def test_hashing_is_not_offered_as_password_storage(self):
        from apkpy_lib import crypto
        self.assertIn("Not for passwords", crypto.hash.__doc__)


class TheSecureScreenTests(unittest.TestCase):

    APP = '''from apkpy_lib import Screen, label, run, secure_screen
home = Screen(id="home")
vault = Screen(id="vault")
label("a", id="t", screen=home)
label("b", id="v", screen=vault)
%s
run(start_screen=home)
'''

    def test_naming_a_screen_protects_only_that_one(self):
        files = _files(self.APP % "secure_screen(vault)")
        protected = [n for n, b in files.items()
                     if n.endswith(".java") and "FLAG_SECURE" in b]
        self.assertEqual(protected, ["java/Screen_vaultActivity.java"])

    def test_naming_nothing_protects_every_screen(self):
        files = _files(self.APP % "secure_screen()")
        protected = [n for n, b in files.items()
                     if n.endswith(".java") and "FLAG_SECURE" in b]
        self.assertEqual(len(protected), 2)

    def test_the_flag_is_set_before_the_layout_is_shown(self):
        # Afterwards, the first frame can still be captured.
        java = _java(self.APP % "secure_screen()")
        self.assertLess(java.index("FLAG_SECURE"), java.index("setContentView"))

    def test_an_app_that_never_asks_has_no_flag(self):
        self.assertNotIn("FLAG_SECURE", _java(self.APP % ""))

    def test_the_previewer_records_it_without_claiming_to_do_it(self):
        from apkpy_lib import Screen, ui
        from apkpy_lib import secure_screen
        ui._secure_screens.clear()
        ui._secure_everything[0] = False
        one = Screen(id="secure_probe_one")
        two = Screen(id="secure_probe_two")
        secure_screen(one)
        self.assertTrue(ui.secure_screen_asked(one))
        self.assertFalse(ui.secure_screen_asked(two))
        self.assertIn("cannot honour it", secure_screen.__doc__)


if __name__ == "__main__":
    unittest.main()
