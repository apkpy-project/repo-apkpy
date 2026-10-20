"""What Socket's code review found in 1.13.1, and what stops it coming back.

Socket (socket.dev) runs an AI review over every release. Three of its points
were true:

* the Previewer switched the HTTPS certificate check off for audio, images,
  downloads and the city lookup, and https carried on unchecked when the check
  failed -- the phone does neither;
* ``apkpy run --qr`` served the APK's whole folder, with a listing, to the
  network, where it only has to serve the APK;
* ``apkpy setup`` unpacked the JDK, Gradle and the SDK tools without checking
  them against their publisher's checksum, and without looking where each
  entry of the archive would land.
"""
import hashlib
import io
import os
import pathlib
import ssl
import sys
import tarfile
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from apkpy_lib import native_build as nb  # noqa: E402


def _quiet(*_args, **_kwargs):
    pass


class TheCertificateCheckTests(unittest.TestCase):

    def test_no_code_switches_the_check_off(self):
        for path in (ROOT / "apkpy_lib").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("_create_unverified_context", text, path.name)
            self.assertNotIn("CERT_NONE", text, path.name)

    def test_the_previewer_context_checks_certificate_and_host(self):
        from apkpy_lib import ui
        context = ui._tls_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)
        self.assertIs(ui._tls_context(), context)   # made once

    def _answer(self, raised):
        """What https.get hands its callback when urlopen raises *raised*."""
        from apkpy_lib import ui
        seen = []
        done = threading.Event()
        original_urlopen = urllib.request.urlopen
        original_app = ui._app

        def urlopen(*_args, **_kwargs):
            raise raised

        def on_response(ok, text):
            seen.append((ok, text))
            done.set()

        urllib.request.urlopen = urlopen
        ui._app = None      # no window: the callback is called on the request's thread
        try:
            ui.https.get("https://self-signed.example/api", on_response=on_response)
            self.assertTrue(done.wait(10))
        finally:
            urllib.request.urlopen = original_urlopen
            ui._app = original_app
        return seen[0]

    def test_a_failed_check_fails_the_request_as_on_the_phone(self):
        failure = ssl.SSLCertVerificationError(1, "certificate verify failed")
        failure.verify_message = "self-signed certificate"
        # urlopen wraps it in a URLError; checked both ways.
        for raised in (urllib.error.URLError(failure), failure):
            ok, text = self._answer(raised)
            self.assertFalse(ok)
            self.assertIn("certificate of self-signed.example could not be verified", text)
            self.assertIn("self-signed certificate", text)
            self.assertIn("The phone refuses this connection too", text)

    def test_other_failures_keep_their_own_words(self):
        ok, text = self._answer(urllib.error.URLError("no route to host"))
        self.assertFalse(ok)
        self.assertIn("no route to host", text)
        self.assertNotIn("certificate", text)


class TheQrServerTests(unittest.TestCase):
    """The server is bound to 127.0.0.1 here; `apkpy run --qr` binds every
    interface, as the phone has to reach it."""

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.apk = os.path.join(self.folder, "My App-debug.apk")
        with open(self.apk, "wb") as f:
            f.write(b"PK-apk-bytes")
        with open(os.path.join(self.folder, "writehere.py"), "w") as f:
            f.write("SECRET = 'not for the network'\n")
        self.httpd, self.url = nb.make_apk_server(self.apk, port=0, tries=1, host="127.0.0.1")
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _get(self, path, method="GET"):
        request = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path), method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as e:
            return e.code, b""

    def test_the_apk_is_served(self):
        self.assertTrue(self.url.endswith("/My%20App-debug.apk"))
        self.assertEqual(self._get("/My%20App-debug.apk"), (200, b"PK-apk-bytes"))
        self.assertEqual(self._get("/My%20App-debug.apk", "HEAD")[0], 200)

    def test_nothing_else_is(self):
        for path in ("/", "/writehere.py", "/My%20App-debug.apk/", "/../writehere.py",
                     "/%2e%2e/writehere.py", "/?x=/My%20App-debug.apk"):
            status, body = self._get(path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"SECRET", body)


class TheDownloadCheckTests(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.source = os.path.join(self.folder, "tool.zip")
        self.data = b"the toolchain" * 1000
        with open(self.source, "wb") as f:
            f.write(self.data)
        self.url = pathlib.Path(self.source).as_uri()
        self.dest = os.path.join(self.folder, "got.zip")

    def test_a_matching_file_is_kept(self):
        good = hashlib.sha256(self.data).hexdigest()
        nb._download(self.url, self.dest, _quiet, sha256=good.upper())
        with open(self.dest, "rb") as f:
            self.assertEqual(f.read(), self.data)
        nb._download(self.url, self.dest, _quiet,
                     sha1=hashlib.sha1(self.data).hexdigest(), size=len(self.data))

    def test_a_file_that_does_not_match_is_deleted(self):
        with self.assertRaises(RuntimeError) as caught:
            nb._download(self.url, self.dest, _quiet, sha256="0" * 64)
        self.assertIn("does not match the checksum its publisher gives", str(caught.exception))
        self.assertFalse(os.path.exists(self.dest))

    def test_a_wrong_size_is_a_mismatch(self):
        with self.assertRaises(RuntimeError):
            nb._download(self.url, self.dest, _quiet,
                         sha1=hashlib.sha1(self.data).hexdigest(), size=len(self.data) + 1)
        self.assertFalse(os.path.exists(self.dest))

    def test_there_is_no_unchecked_download(self):
        with self.assertRaises(ValueError):
            nb._download(self.url, self.dest, _quiet)
        self.assertFalse(os.path.exists(self.dest))

    def test_the_sdk_tools_are_pinned_with_googles_checksums(self):
        self.assertEqual(set(nb._CMDLINE_TOOLS), {"win", "mac", "linux"})
        for url, sha1, size in nb._CMDLINE_TOOLS.values():
            self.assertTrue(url.startswith("https://dl.google.com/android/repository/"))
            self.assertRegex(sha1, r"^[0-9a-f]{40}$")
            self.assertGreater(size, 100000000)

    def test_the_jdk_comes_with_its_sha256(self):
        listing = [{"binary": {"package": {
            "link": "https://github.com/adoptium/x.zip", "checksum": "ab" * 32, "name": "x.zip"}}}]
        self.assertEqual(nb._jdk_asset(listing), ("https://github.com/adoptium/x.zip", "ab" * 32, "x.zip"))
        with self.assertRaises(RuntimeError):
            nb._jdk_asset([{"binary": {"package": {"link": "https://x/y.zip"}}}])

    def test_a_failed_bootstrap_says_so_and_returns_none(self):
        logged = []
        original_home, original_fetch = nb.apkpy_home, nb._fetch_text

        def fetch(_url):
            raise OSError("network is down")

        nb.apkpy_home = lambda: self.folder
        nb._fetch_text = fetch
        try:
            self.assertIsNone(nb.bootstrap_gradle(log=logged.append))
            self.assertIsNone(nb.bootstrap_jdk(log=logged.append))
        finally:
            nb.apkpy_home, nb._fetch_text = original_home, original_fetch
        self.assertIn("Gradle download failed: network is down", "\n".join(logged))
        self.assertIn("JDK download failed: network is down", "\n".join(logged))


class TheSafeUnpackTests(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.dest = os.path.join(self.folder, "out")
        os.makedirs(self.dest)

    def _zip(self, names):
        path = os.path.join(self.folder, "a.zip")
        with zipfile.ZipFile(path, "w") as z:
            for name in names:
                z.writestr(name, "x")
        return path

    def _tar(self, members):
        path = os.path.join(self.folder, "a.tar.gz")
        with tarfile.open(path, "w:gz") as t:
            for name, kind, link in members:
                info = tarfile.TarInfo(name)
                if kind == "file":
                    info.size = 1
                    t.addfile(info, io.BytesIO(b"x"))
                else:
                    info.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
                    info.linkname = link
                    t.addfile(info)
        return path

    def test_an_ordinary_archive_unpacks(self):
        nb._extract(self._zip(["jdk/bin/java", "jdk/lib/x"]), self.dest)
        self.assertTrue(os.path.isfile(os.path.join(self.dest, "jdk", "bin", "java")))
        nb._extract(self._tar([("gradle/bin/gradle", "file", "")]), self.dest)
        self.assertTrue(os.path.isfile(os.path.join(self.dest, "gradle", "bin", "gradle")))

    def test_a_zip_entry_outside_stops_before_anything_is_written(self):
        for bad in ("../evil.txt", "ok/../../evil.txt", "/abs/evil.txt"):
            with self.assertRaises(RuntimeError, msg=bad):
                nb._extract(self._zip(["fine.txt", bad]), self.dest)
            self.assertFalse(os.path.exists(os.path.join(self.dest, "fine.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.folder, "evil.txt")))

    def test_a_tar_entry_or_link_outside_stops(self):
        for members in ([("../evil.txt", "file", "")],
                        [("jdk/link", "symlink", "../../outside")],
                        [("jdk/link", "symlink", "/etc/passwd")],
                        [("jdk/hard", "hardlink", "../outside")]):
            with self.assertRaises(RuntimeError, msg=str(members)):
                nb._extract(self._tar(members), self.dest)
        self.assertEqual(os.listdir(self.dest), [])


if __name__ == "__main__":
    unittest.main()
