# -*- coding: utf-8 -*-
"""Sign-in with OpenID Connect: Microsoft (Entra ID), an issuer found by its
discovery document, the token renewed, the claims of the id_token.

The Previewer's half runs the whole flow against a small OIDC provider on
127.0.0.1 that checks what a real one checks -- the PKCE verifier against
the challenge, the redirect, the state -- and rotates refresh tokens. The
phone's half is checked in the Java it writes (ApkpyAuth.java).
"""

import base64
import hashlib
import http.server
import json
import os
import shutil
import socket
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from unittest import mock

from apkpy_lib import ui
from apkpy_lib.core.compiler import translate_python_to_android


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class _Provider:
    """An OIDC provider that refuses what a real one refuses."""

    def __init__(self):
        self.port = _free_port()
        self.issuer = "http://127.0.0.1:%d" % self.port
        self.codes = {}          # code -> (challenge, redirect)
        self.refresh = {}        # live refresh token -> count
        self.issued = 0
        self.expires_in = 3600
        provider = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, status, body):
                data = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                url = urllib.parse.urlparse(self.path)
                q = dict(urllib.parse.parse_qsl(url.query))
                if url.path == "/.well-known/openid-configuration":
                    return self._json(200, {
                        "issuer": provider.issuer,
                        "authorization_endpoint": provider.issuer + "/authorize",
                        "token_endpoint": provider.issuer + "/token",
                        "userinfo_endpoint": provider.issuer + "/userinfo",
                    })
                if url.path == "/authorize":
                    assert q["response_type"] == "code" and q["client_id"] == "cid"
                    assert q["code_challenge_method"] == "S256" and q["state"]
                    code = "code%d" % len(provider.codes)
                    provider.codes[code] = (q["code_challenge"], q["redirect_uri"])
                    self.send_response(302)
                    self.send_header("Location", q["redirect_uri"] + "?" + urllib.parse.urlencode(
                        {"code": code, "state": q["state"]}))
                    self.end_headers()
                    return
                if url.path == "/userinfo":
                    if not self.headers.get("Authorization", "").startswith("Bearer access"):
                        return self._json(401, {"error": "invalid_token"})
                    return self._json(200, {"name": "Ana Lopes", "email": "ana@example.com",
                                            "picture": "https://example.com/ana.png"})
                self._json(404, {})

            def do_POST(self):
                body = dict(urllib.parse.parse_qsl(self.rfile.read(
                    int(self.headers.get("Content-Length", "0"))).decode("utf-8")))
                if body.get("client_id") != "cid":
                    return self._json(400, {"error": "invalid_client"})
                if body.get("grant_type") == "authorization_code":
                    challenge, redirect = provider.codes.pop(body.get("code"), (None, None))
                    verifier = body.get("code_verifier", "")
                    if challenge is None or redirect != body.get("redirect_uri") \
                            or _b64(hashlib.sha256(verifier.encode("ascii")).digest()) != challenge:
                        return self._json(400, {"error": "invalid_grant"})
                    return self._json(200, provider.tokens())
                if body.get("grant_type") == "refresh_token":
                    if provider.refresh.pop(body.get("refresh_token"), None) is None:
                        return self._json(400, {"error": "invalid_grant",
                                                "error_description": "refresh token revoked"})
                    return self._json(200, provider.tokens())
                self._json(400, {"error": "unsupported_grant_type"})

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tokens(self):
        self.issued += 1
        claims = {"iss": self.issuer, "aud": "cid", "name": "Ana Lopes",
                  "email": "ana@example.com", "oid": "1234", "n": self.issued}
        id_token = ".".join([_b64(b'{"alg":"none"}'), _b64(json.dumps(claims).encode("utf-8")), ""])
        refresh = "refresh%d" % self.issued
        self.refresh[refresh] = 1
        return {"access_token": "access%d" % self.issued, "token_type": "Bearer",
                "expires_in": self.expires_in, "refresh_token": refresh, "id_token": id_token}

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def _browser(url):
    """The browser: follows the provider's redirect to the loopback callback."""
    threading.Thread(target=lambda: urllib.request.urlopen(url, timeout=10).read(),
                     daemon=True).start()
    return True


class _Home(unittest.TestCase):
    """A home of its own (auth.json lives in ~/.apkpy), and no Tk window."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        patches = [mock.patch.dict(os.environ, {"HOME": self.home, "USERPROFILE": self.home}),
                   mock.patch.object(ui, "_app", None)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.home, True)
        self.auth = ui.AuthAPI()
        self.opened = []
        self.follow = True

        def browser(url):
            self.opened.append(url)
            if self.follow:
                _browser(url)
            return True
        p = mock.patch("webbrowser.open", browser)
        p.start()
        self.addCleanup(p.stop)

    def _wait(self, predicate, seconds=10):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if predicate():
                return True
            time.sleep(0.05)
        return False


class ThePreviewerSignsIn(_Home):

    def setUp(self):
        super().setUp()
        self.provider = _Provider()
        self.addCleanup(self.provider.close)

    def _sign_in(self):
        self.auth.login(issuer=self.provider.issuer, client_id="cid",
                        preview_port=_free_port())
        self.assertTrue(self._wait(lambda: self.auth._load().get("access_token")),
                        "no token after the sign-in")

    def test_an_issuer_by_discovery_with_pkce(self):
        self._sign_in()
        self.assertEqual(self.auth.token(), "access1")
        self.assertTrue(self.auth.is_logged_in())
        claims = self.auth.claims()
        self.assertEqual(claims["name"], "Ana Lopes")
        self.assertEqual(claims["oid"], "1234")
        # The discovered token endpoint is kept, for the renewals.
        self.assertEqual(self.auth._load()["token_url"], self.provider.issuer + "/token")

    def test_the_token_is_renewed_before_it_expires(self):
        self.provider.expires_in = 60          # inside the five minutes
        self._sign_in()
        self.assertEqual(self.auth.token(), "access2")
        state = self.auth._load()
        self.assertEqual(state["refresh_token"], "refresh2")    # rotated
        self.assertEqual(self.auth.claims()["n"], 2)

    def test_a_refused_refresh_token_ends_the_session(self):
        self.provider.expires_in = 60
        self._sign_in()
        self.provider.refresh.clear()          # revoked on the server
        self.assertEqual(self.auth.token(), "")
        self.assertFalse(self.auth.is_logged_in())
        self.assertEqual(self.auth.claims(), {})

    def test_an_answer_with_another_state_is_dropped(self):
        port = _free_port()
        self.follow = False
        self.auth.login(issuer=self.provider.issuer, client_id="cid", preview_port=port,
                        on_error=lambda why: None)
        self.assertTrue(self._wait(lambda: self.opened))
        urllib.request.urlopen("http://127.0.0.1:%d/callback?code=stolen&state=other" % port,
                               timeout=5).read()
        time.sleep(0.5)
        self.assertEqual(self.auth.token(), "")
        # on_error runs on the Tk thread; here it waits in the queue.
        self.assertTrue(self.auth._main_queue)

    def test_logout_forgets_everything(self):
        self._sign_in()
        self.auth.logout()
        self.assertEqual(self.auth.token(), "")
        self.assertEqual(self.auth.claims(), {})

    def test_the_user_comes_from_the_discovered_userinfo(self):
        self._sign_in()
        got = []
        self.auth._fetch_user(got.append, None)
        self.auth._main_queue.pop(0)()
        self.assertEqual(got[0]["email"], "ana@example.com")
        self.assertEqual(got[0]["picture"], "https://example.com/ana.png")


class TheMicrosoftSignIn(_Home):

    def test_the_tenant_and_localhost(self):
        self.follow = False
        port = _free_port()
        self.auth.login("microsoft", "11112222-aaaa", tenant="contoso.onmicrosoft.com",
                        preview_port=port)
        self.assertTrue(self._wait(lambda: self.opened))
        url = urllib.parse.urlparse(self.opened[0])
        q = dict(urllib.parse.parse_qsl(url.query))
        self.assertEqual(url.netloc + url.path,
                         "login.microsoftonline.com/contoso.onmicrosoft.com/oauth2/v2.0/authorize")
        # The Entra portal takes http://localhost, not http://127.0.0.1.
        self.assertEqual(q["redirect_uri"], "http://localhost:%d/callback" % port)
        self.assertIn("offline_access", q["scope"].split())
        self.assertEqual(q["code_challenge_method"], "S256")
        # Unblock the waiting server.
        urllib.request.urlopen("http://127.0.0.1:%d/callback?error=access_denied&state=x" % port,
                               timeout=5).read()

    def test_a_token_from_before_1_14_is_still_read(self):
        with open(os.path.join(self.auth._dir(), "auth_token.txt"), "w", encoding="utf-8") as f:
            f.write("old-token")
        self.assertEqual(self.auth.token(), "old-token")


def _app(body, extra=""):
    return translate_python_to_android(
        'from apkpy_lib import Screen, label, button, https, auth, run\n'
        'login = Screen(id="login")\n'
        'home = Screen(id="home")\n'
        'who = label("", id="who", screen=home)\n'
        '%s\n'
        'def go():\n%s\n'
        'button("Go", id="b", screen=login, command=go)\n'
        'run(start_screen=login)\n' % (extra, body))


class ThePhoneSignsIn(unittest.TestCase):

    def test_microsoft_with_a_tenant(self):
        files = _app('    auth.login("microsoft", "11112222-aaaa", tenant="contoso.onmicrosoft.com", then=home)')
        auth = files["java/ApkpyAuth.java"]
        self.assertIn('AUTH_URL = "https://login.microsoftonline.com/contoso.onmicrosoft.com/oauth2/v2.0/authorize";', auth)
        self.assertIn('TOKEN_URL = "https://login.microsoftonline.com/contoso.onmicrosoft.com/oauth2/v2.0/token";', auth)
        self.assertIn('SCOPES = "openid profile email offline_access User.Read";', auth)
        self.assertIn('CLIENT_ID = "11112222-aaaa";', auth)
        self.assertIn("ApkpyAuth.start(this);", files["java/Screen_loginActivity.java"])

    def test_an_issuer_is_discovered_when_the_sign_in_starts(self):
        files = _app('    auth.login(issuer="https://login.example.com", client_id="cid", then=home)')
        auth = files["java/ApkpyAuth.java"]
        self.assertIn('ISSUER = "https://login.example.com";', auth)
        self.assertIn('"/.well-known/openid-configuration"', auth)

    def test_the_state_is_random_and_checked(self):
        auth = _app('    auth.login("google", "cid", then=home)')["java/ApkpyAuth.java"]
        self.assertIn('String state = random(16);', auth)
        self.assertIn('!expected.equals(state)', auth)
        self.assertNotIn('state=apkpy', auth)

    def test_tokens_are_encrypted_and_renewed(self):
        auth = _app('    auth.login("microsoft", "cid", then=home)')["java/ApkpyAuth.java"]
        self.assertIn('"AndroidKeyStore"', auth)
        self.assertIn('"AES/GCM/NoPadding"', auth)
        self.assertIn('"grant_type=refresh_token"', auth)
        self.assertIn('"invalid_grant".equals(', auth)

    def test_the_activity_hands_the_redirect_over(self):
        activity = _app('    auth.login("microsoft", "cid", then=home)')["java/ApkpyAuthActivity.java"]
        self.assertIn('ApkpyAuth.finish(this, getIntent() != null ? getIntent().getData() : null', activity)
        self.assertIn('new android.content.Intent(this, Screen_homeActivity.class)', activity)

    def test_then_opens_only_when_signed_in(self):
        # Seen on the phone: a forged apkpy://auth link was refused but still
        # opened the `then` screen. Refused, cancelled or failed: back instead.
        files = _app('    auth.login("microsoft", "cid", then=home)')
        auth = files["java/ApkpyAuth.java"]
        refused = auth[auth.index("ignored\");"):auth.index("final String verifier")]
        self.assertIn("leave(a);", refused)
        self.assertNotIn("signedIn.run()", refused)
        self.assertIn("if (ok) {\n                            signedIn.run();", auth)
        self.assertIn("a.isTaskRoot()", auth)
        self.assertIn("getLaunchIntentForPackage(a.getPackageName())", auth)
        self.assertNotIn("finish();", files["java/ApkpyAuthActivity.java"].split("goNext();", 1)[1].split("}", 1)[0])

    def test_claims_are_a_dict(self):
        files = _app('    c = auth.claims()\n    who.set_value(c["email"] + str(auth.is_logged_in()))')
        java = files["java/Screen_loginActivity.java"]
        self.assertIn('String c = ApkpyAuth.claims(getApplicationContext());', java)
        self.assertIn('_jsonGet(String.valueOf(c), "email")', java)
        self.assertIn('ApkpyAuth.loggedIn(getApplicationContext()) ? ApkpyValues.TRUE : ApkpyValues.FALSE', java)

    def test_only_reading_the_token_still_gets_the_class(self):
        files = _app('    https.get("https://x.example.com", headers={"Authorization": "Bearer " + auth.token()})')
        self.assertIn("java/ApkpyAuth.java", files)
        self.assertNotIn("java/ApkpyAuthActivity.java", files)

    def test_an_app_without_auth_has_no_class(self):
        files = _app('    who.set_value("x")')
        self.assertNotIn("java/ApkpyAuth.java", files)


if __name__ == "__main__":
    unittest.main()
