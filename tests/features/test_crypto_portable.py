# -*- coding: utf-8 -*-
"""Encryption that travels, and the six digits of an authenticator."""

import base64
import re
import unittest

from apkpy_lib.core.compiler import translate_python_to_android

try:  # the Previewer's AES comes from the optional extra: pip install apkpy[crypto]
    import cryptography  # noqa: F401
    HAS_AES = True
except ImportError:
    HAS_AES = False

RFC_SEED = base64.b32encode(b"12345678901234567890").decode()

# RFC 6238, appendix B: the published SHA-1 vectors, eight digits.
RFC_VECTORS = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


def _java(source):
    files = translate_python_to_android(source)
    return "\n".join(b for n, b in files.items() if n.endswith(".java"))


def _app(body):
    return ('from apkpy_lib import Screen, button, crypto, label, run\n'
            'home = Screen(id="home")\n'
            'out = label("", id="out", screen=home)\n'
            '\n\ndef go():\n    %s\n\n\n'
            'button("Go", id="b", screen=home, command=go)\n'
            'run(start_screen=home)\n' % body)


@unittest.skipUnless(HAS_AES, "cryptography is not installed (pip install apkpy[crypto])")
class ThePortableFormatTests(unittest.TestCase):
    """A password box has to open anywhere, or it is not portable."""

    def test_a_password_changes_the_format_not_just_the_key(self):
        from apkpy_lib import crypto
        box = crypto.encrypt("hello", password="pw")
        self.assertTrue(box.startswith("pw1$"))
        self.assertEqual(len(box.split("$")), 5)

    def test_the_round_trip_works(self):
        from apkpy_lib import crypto
        box = crypto.encrypt("segredo do cofre", password="abre-te sesamo")
        self.assertEqual(crypto.decrypt(box, password="abre-te sesamo"),
                         "segredo do cofre")

    def test_the_wrong_password_gets_nothing(self):
        # GCM's tag fails before anything is returned, which is the point of
        # using an authenticated cipher rather than plain AES.
        from apkpy_lib import crypto
        box = crypto.encrypt("x", password="right")
        self.assertEqual(crypto.decrypt(box, password="wrong"), "")

    def test_tampering_is_caught(self):
        from apkpy_lib import crypto
        box = crypto.encrypt("x", password="pw")
        self.assertEqual(crypto.decrypt(box[:-2] + "00", password="pw"), "")

    def test_no_password_on_a_password_box_gets_nothing(self):
        from apkpy_lib import crypto
        box = crypto.encrypt("x", password="pw")
        self.assertEqual(crypto.decrypt(box), "")

    def test_every_box_is_different(self):
        # A fresh salt and nonce each time, or two identical secrets would be
        # visibly identical on disk.
        from apkpy_lib import crypto
        self.assertNotEqual(crypto.encrypt("same", password="pw"),
                            crypto.encrypt("same", password="pw"))

    def test_the_device_key_path_is_untouched(self):
        from apkpy_lib import crypto
        box = crypto.encrypt("only here")
        self.assertTrue(box.startswith("enc1$"))
        self.assertEqual(crypto.decrypt(box), "only here")

    def test_android_uses_real_aes_gcm_so_the_box_travels(self):
        java = _java(_app('out.set_value(crypto.encrypt("x", password="p"))'))
        self.assertIn("_apkpyEncryptPw", java)
        self.assertIn('javax.crypto.Cipher.getInstance("AES/GCM/NoPadding")', java)
        self.assertIn('_apkpyPbkdf2(password, salt, 200000, "sha256")', java)

    def test_both_sides_write_the_same_header(self):
        # If the phone wrote pw2$ the desktop could not read it, and the whole
        # point of a password is that the data crosses.
        from apkpy_lib import crypto
        java = _java(_app('out.set_value(crypto.encrypt("x", password="p"))'))
        self.assertIn('"pw1$200000$"', java)
        self.assertTrue(crypto.encrypt("x", password="p").startswith("pw1$200000$"))

    def test_a_call_without_a_password_still_uses_the_device_key(self):
        # The helpers themselves are emitted unconditionally (pre-existing
        # bloat), so what matters is which one the call site picked.
        java = _java(_app('out.set_value(crypto.encrypt("x"))'))
        calls = [l for l in java.splitlines()
                 if "_apkpyEncrypt" in l and "private String" not in l]
        self.assertTrue(calls)
        for line in calls:
            self.assertNotIn("_apkpyEncryptPw", line)


class TheAuthenticatorTests(unittest.TestCase):
    """RFC 6238 publishes its answers, so this one can actually be proven."""

    def test_the_previewer_matches_every_published_vector(self):
        from apkpy_lib import crypto
        for moment, expected in RFC_VECTORS:
            self.assertEqual(crypto.totp(RFC_SEED, digits=8, at=moment),
                             expected, moment)

    def test_the_default_is_six_digits(self):
        from apkpy_lib import crypto
        code = crypto.totp("JBSWY3DPEHPK3PXP")
        self.assertTrue(re.fullmatch("[0-9]{6}", code), code)

    def test_a_code_holds_still_inside_its_period(self):
        from apkpy_lib import crypto
        # 990..1019 is one 30-second window; 1020 starts the next.
        self.assertEqual(crypto.totp(RFC_SEED, at=990),
                         crypto.totp(RFC_SEED, at=1019))
        self.assertNotEqual(crypto.totp(RFC_SEED, at=1019),
                            crypto.totp(RFC_SEED, at=1020))

    def test_spaces_and_case_are_forgiven(self):
        # Secrets get copied out of a web page by hand.
        from apkpy_lib import crypto
        self.assertEqual(crypto.totp("jbsw y3dp ehpk 3pxp", at=1),
                         crypto.totp("JBSWY3DPEHPK3PXP", at=1))

    def test_a_secret_that_is_not_base32_answers_empty(self):
        from apkpy_lib import crypto
        self.assertEqual(crypto.totp("!!!!"), "")
        self.assertEqual(crypto.totp(""), "")

    def test_the_java_base32_decoder_agrees_with_the_standard_one(self):
        """Transcribe the generated loop and run it against the real thing.

        Java cannot be executed here, but its base32 decoder is where an
        off-by-one hides, and the loop is short enough to re-read in Python
        and compare against the library.
        """
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"

        def as_java(secret):
            clean = secret.replace(" ", "").replace("-", "").replace("=", "").upper()
            out = bytearray()
            buffer = bits = 0
            for character in clean:
                value = alphabet.find(character)
                if value < 0:
                    return b""
                buffer = (buffer << 5) | value
                bits += 5
                if bits >= 8:
                    out.append((buffer >> (bits - 8)) & 0xFF)
                    bits -= 8
            return bytes(out)

        for raw in (b"12345678901234567890", b"Hello!", b"", b"a", b"ab",
                    b"abc", b"abcd", b"abcde", b"0123456789abcdef"):
            secret = base64.b32encode(raw).decode()
            self.assertEqual(as_java(secret), raw, secret)

    def test_the_generated_java_asks_for_the_right_algorithm(self):
        java = _java(_app('out.set_value(crypto.totp("JBSWY3DPEHPK3PXP"))'))
        self.assertIn('javax.crypto.Mac.getInstance("HmacSHA1")', java)
        self.assertIn("_apkpyTotp(", java)

    def test_the_digits_and_period_reach_the_call(self):
        java = _java(_app(
            'out.set_value(crypto.totp("JBSWY3DPEHPK3PXP", digits=8, period=60))'))
        self.assertIn("_apkpyTotp(String.valueOf(\"JBSWY3DPEHPK3PXP\"), 8, 60)", java)

    def test_the_digits_are_clamped_on_both_sides(self):
        from apkpy_lib import crypto
        self.assertEqual(len(crypto.totp(RFC_SEED, digits=99)), 8)
        java = _java(_app(
            'out.set_value(crypto.totp("JBSWY3DPEHPK3PXP", digits=99))'))
        self.assertIn(", 8, 30)", java)

    def test_an_app_that_never_asks_never_calls_it(self):
        java = _java(_app('out.set_value("plain")'))
        called = [l for l in java.splitlines()
                  if ("_apkpyTotp(" in l or "_apkpyEncryptPw(" in l)
                  and "private String" not in l]
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
