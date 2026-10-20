# -*- coding: utf-8 -*-
"""Sign-in with OpenID Connect: Microsoft (Entra ID), any issuer found by its
discovery document, the token renewed before it expires, and the claims of
the id_token.

    auth.login("microsoft", client_id="...", tenant="contoso.onmicrosoft.com", then=home)
    auth.login(issuer="https://login.example.com", client_id="...", then=home)
    auth.claims()["email"]

On the phone everything lives in one generated class, ApkpyAuth.java, so the
screen that starts the sign-in and ApkpyAuthActivity, which receives the
redirect, read and write the same things:

- PKCE (S256) and a random ``state``, checked when the browser comes back:
  an answer to a sign-in the app did not start is dropped;
- for an issuer, its ``/.well-known/openid-configuration``, read when the
  sign-in starts (endpoints are not baked into the build);
- the access, refresh and id tokens kept encrypted with a key of the Android
  Keystore, in the preferences file the backup rules already leave behind;
- the access token renewed with the refresh token a few minutes before it
  expires: when it is read, and on a timer while the app runs. A refresh
  token the server refuses (``invalid_grant``) ends the session;
- ``auth.claims()``: the id_token's payload, as a dict. It came straight from
  the token endpoint over TLS, which is what OIDC asks of a client before
  trusting it (Core 3.1.3.7).
"""

MICROSOFT_SCOPES = 'openid profile email offline_access User.Read'
OIDC_SCOPES = 'openid profile email offline_access'
MICROSOFT_USERINFO = 'https://graph.microsoft.com/oidc/userinfo'


def microsoft_endpoints(tenant):
    """Authorize and token endpoints for a tenant: common, organizations,
    consumers, a domain or a tenant id."""
    name = str(tenant or 'common').strip().strip('/') or 'common'
    base = 'https://login.microsoftonline.com/%s/oauth2/v2.0' % name
    return base + '/authorize', base + '/token'


def _lit(value):
    text = str(value or '')
    return '"%s"' % (text.replace('\\', '\\\\').replace('"', '\\"')
                     .replace('\n', '\\n').replace('\r', '\\r'))


def generate_auth_java(package, auth):
    """ApkpyAuth.java for the app's auth.login() (or empty settings, when the
    app only reads auth.token() / auth.is_logged_in())."""
    auth = auth or {}
    return (_AUTH_JAVA
            .replace('@PACKAGE@', package)
            .replace('@CLIENT_ID@', _lit(auth.get('client_id')))
            .replace('@REDIRECT@', _lit(auth.get('redirect') or 'apkpy://auth'))
            .replace('@SCOPES@', _lit(auth.get('scopes')))
            .replace('@AUTH_URL@', _lit(auth.get('auth_url')))
            .replace('@TOKEN_URL@', _lit(auth.get('token_url')))
            .replace('@USERINFO_URL@', _lit(auth.get('userinfo_url')))
            .replace('@ISSUER@', _lit(auth.get('issuer'))))


def generate_auth_activity_java(package, then_class):
    """ApkpyAuthActivity.java: receives the redirect and hands it to ApkpyAuth."""
    return (_ACTIVITY_JAVA
            .replace('@PACKAGE@', package)
            .replace('@THEN@', then_class))


_ACTIVITY_JAVA = r'''package @PACKAGE@;

import android.app.Activity;
import android.os.Bundle;

// Receives the redirect of auth.login(), declared in the manifest with an
// intent-filter for the redirect's scheme and host. ApkpyAuth checks the
// state, trades the code for tokens and keeps them; then the app goes on.
public class ApkpyAuthActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ApkpyAuth.finish(this, getIntent() != null ? getIntent().getData() : null, new Runnable() {
            public void run() {
                goNext();
            }
        });
    }

    private void goNext() {
        try {
            android.content.Intent i = new android.content.Intent(this, @THEN@.class);
            i.addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP | android.content.Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(i);
        } catch (Exception e) { }
    }
}
'''


_AUTH_JAVA = r'''package @PACKAGE@;

import android.content.Context;
import android.content.SharedPreferences;

/** auth.login() and what follows it: PKCE and a checked state, the discovery
 *  of an issuer, the tokens kept encrypted with a key of the Android
 *  Keystore, renewed with the refresh token before they expire, and the
 *  claims of the id_token. The screen and ApkpyAuthActivity both use it. */
public final class ApkpyAuth {
    static final String CLIENT_ID = @CLIENT_ID@;
    static final String REDIRECT = @REDIRECT@;
    static final String SCOPES = @SCOPES@;
    static final String AUTH_URL = @AUTH_URL@;
    static final String TOKEN_URL = @TOKEN_URL@;
    static final String USERINFO_URL = @USERINFO_URL@;
    static final String ISSUER = @ISSUER@;

    private static final String PREFS = "apkpy_auth";
    // Renewed this long before it expires: a request started just before the
    // hour is up still carries a token that works.
    private static final long EARLY = 5 * 60 * 1000L;
    private static final Object LOCK = new Object();
    private static boolean renewing;

    private ApkpyAuth() { }

    private static SharedPreferences prefs(Context c) {
        return c.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    // ── What the app reads ───────────────────────────────────────────────

    /** auth.token(): the access token. Close to expiring, the renewal starts
     *  in the background; this answer is the token there is now. */
    public static String token(Context c) {
        SharedPreferences p = prefs(c);
        String token = get(p, "token");
        if (!token.isEmpty() && dueForRenewal(p)) renewSoon(c);
        return token;
    }

    public static boolean loggedIn(Context c) {
        return !token(c).isEmpty();
    }

    /** auth.logout(): the tokens go; the discovered endpoints may stay. */
    public static void clear(Context c) {
        prefs(c).edit().remove("token").remove("refresh").remove("id_token")
                .remove("expires").remove("verifier").remove("state").apply();
    }

    /** auth.claims(): the id_token's payload as JSON, or {} without one. */
    public static String claims(Context c) {
        String id = get(prefs(c), "id_token");
        String[] parts = id.split("[.]");
        if (parts.length < 2) return "{}";
        try {
            byte[] raw = android.util.Base64.decode(parts[1],
                    android.util.Base64.URL_SAFE | android.util.Base64.NO_WRAP | android.util.Base64.NO_PADDING);
            return new org.json.JSONObject(new String(raw, "UTF-8")).toString();
        } catch (Exception e) {
            return "{}";
        }
    }

    /** The userinfo endpoint: the issuer's, when it was discovered. */
    public static String userinfoUrl(Context c) {
        String found = prefs(c).getString("userinfo_url", "");
        return found.isEmpty() ? USERINFO_URL : found;
    }

    // ── Signing in ───────────────────────────────────────────────────────

    /** auth.login(): a new verifier and state, the endpoints (from the
     *  issuer's discovery document when there is one), then the browser. */
    public static void start(final android.app.Activity a) {
        new Thread(new Runnable() {
            public void run() {
                try {
                    String[] ends = endpoints();
                    String verifier = random(64);
                    String state = random(16);
                    prefs(a).edit().putString("verifier", verifier).putString("state", state)
                            .putString("token_url", ends[1]).putString("userinfo_url", ends[2]).apply();
                    final String url = ends[0] + (ends[0].indexOf('?') >= 0 ? "&" : "?")
                            + "response_type=code"
                            + "&client_id=" + enc(CLIENT_ID)
                            + "&redirect_uri=" + enc(REDIRECT)
                            + "&scope=" + enc(SCOPES)
                            + "&code_challenge=" + challenge(verifier)
                            + "&code_challenge_method=S256"
                            + "&state=" + state;
                    a.runOnUiThread(new Runnable() {
                        public void run() {
                            try {
                                a.startActivity(new android.content.Intent(
                                        android.content.Intent.ACTION_VIEW, android.net.Uri.parse(url)));
                            } catch (Exception e) {
                                android.util.Log.w("apkpy", "auth: no browser to open the sign-in");
                            }
                        }
                    });
                } catch (Exception e) {
                    android.util.Log.w("apkpy", "auth: the sign-in could not start: " + e);
                }
            }
        }).start();
    }

    private static String[] endpoints() throws Exception {
        if (ISSUER.isEmpty()) return new String[]{AUTH_URL, TOKEN_URL, USERINFO_URL};
        String base = ISSUER.endsWith("/") ? ISSUER.substring(0, ISSUER.length() - 1) : ISSUER;
        org.json.JSONObject d = new org.json.JSONObject(
                read(open(base + "/.well-known/openid-configuration")));
        return new String[]{d.getString("authorization_endpoint"), d.getString("token_endpoint"),
                d.optString("userinfo_endpoint", "")};
    }

    /** The redirect: checks the state and trades the code for tokens, off
     *  the UI thread. done runs on the UI thread, whatever happened. */
    /** The redirect: checked, traded for tokens, kept. `signedIn` runs only
     *  when that worked; either way the activity closes. */
    public static void finish(final android.app.Activity a, android.net.Uri data, final Runnable signedIn) {
        final SharedPreferences p = prefs(a);
        final String code = data != null ? data.getQueryParameter("code") : null;
        String state = data != null ? data.getQueryParameter("state") : null;
        String expected = p.getString("state", "");
        if (code == null || code.isEmpty() || expected.isEmpty() || !expected.equals(state)) {
            // Cancelled, refused, or an answer to a sign-in this app did not start.
            String error = data != null ? data.getQueryParameter("error") : null;
            if (error != null) {
                String why = data.getQueryParameter("error_description");
                android.util.Log.w("apkpy", "auth: " + error + (why != null ? " - " + why : ""));
            } else if (code != null) {
                android.util.Log.w("apkpy", "auth: the answer's state is not the one sent; ignored");
            }
            leave(a);
            return;
        }
        final String verifier = p.getString("verifier", "");
        p.edit().remove("state").remove("verifier").apply();
        new Thread(new Runnable() {
            public void run() {
                boolean kept;
                try {
                    save(a, post(tokenUrl(a), "grant_type=authorization_code"
                            + "&code=" + enc(code)
                            + "&redirect_uri=" + enc(REDIRECT)
                            + "&client_id=" + enc(CLIENT_ID)
                            + "&code_verifier=" + enc(verifier)));
                    kept = true;
                } catch (Exception e) {
                    android.util.Log.w("apkpy", "auth: no token: " + e.getMessage());
                    kept = false;
                }
                final boolean ok = kept;
                a.runOnUiThread(new Runnable() {
                    public void run() {
                        if (ok) {
                            signedIn.run();
                            a.finish();
                        } else {
                            leave(a);
                        }
                    }
                });
            }
        }).start();
    }

    /** Not signed in: back to the screen under this one, or to the app's
     *  first screen when nothing is under it. */
    private static void leave(android.app.Activity a) {
        if (a.isTaskRoot()) {
            android.content.Intent i = a.getPackageManager().getLaunchIntentForPackage(a.getPackageName());
            if (i != null) a.startActivity(i);
        }
        a.finish();
    }

    private static String tokenUrl(Context c) {
        String found = prefs(c).getString("token_url", "");
        return found.isEmpty() ? TOKEN_URL : found;
    }

    /** A token answer: kept, encrypted, with when it expires. */
    static void save(Context c, String answer) throws Exception {
        org.json.JSONObject jo = new org.json.JSONObject(answer);
        String access = jo.optString("access_token", "");
        if (access.isEmpty()) {
            throw new Exception(jo.optString("error", "no access_token") + " "
                    + jo.optString("error_description", ""));
        }
        SharedPreferences.Editor e = prefs(c).edit();
        put(e, "token", access);
        // A renewal may come without a new refresh token: the old one stays.
        String refresh = jo.optString("refresh_token", "");
        if (!refresh.isEmpty()) put(e, "refresh", refresh);
        String id = jo.optString("id_token", "");
        if (!id.isEmpty()) put(e, "id_token", id);
        long seconds = jo.optLong("expires_in", 0);
        if (seconds > 0) e.putLong("expires", System.currentTimeMillis() + seconds * 1000L);
        else e.remove("expires");
        e.apply();
        // apply() has already changed what prefs() reads, in this process.
        if (seconds > 0 && !get(prefs(c), "refresh").isEmpty()) schedule(c, seconds * 1000L - EARLY);
    }

    // ── Renewing ─────────────────────────────────────────────────────────

    private static boolean dueForRenewal(SharedPreferences p) {
        long expires = p.getLong("expires", 0);
        return expires > 0 && System.currentTimeMillis() > expires - EARLY
                && !get(p, "refresh").isEmpty();
    }

    private static void schedule(Context c, long delay) {
        final Context app = c.getApplicationContext();
        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(new Runnable() {
            public void run() {
                if (dueForRenewal(prefs(app))) renewSoon(app);
            }
        }, Math.max(1000L, delay));
    }

    private static void renewSoon(final Context c) {
        synchronized (LOCK) {
            if (renewing) return;
            renewing = true;
        }
        final Context app = c.getApplicationContext();
        new Thread(new Runnable() {
            public void run() {
                try {
                    renewNow(app);
                } finally {
                    synchronized (LOCK) {
                        renewing = false;
                    }
                }
            }
        }).start();
    }

    private static void renewNow(Context c) {
        SharedPreferences p = prefs(c);
        String refresh = get(p, "refresh");
        if (refresh.isEmpty() || !dueForRenewal(p)) return;
        try {
            String answer = post(tokenUrl(c), "grant_type=refresh_token"
                    + "&refresh_token=" + enc(refresh)
                    + "&client_id=" + enc(CLIENT_ID));
            org.json.JSONObject jo = new org.json.JSONObject(answer);
            if (jo.optString("access_token", "").length() > 0) {
                save(c, answer);
            } else if ("invalid_grant".equals(jo.optString("error", ""))) {
                // Revoked, expired, or the password changed: signed out.
                android.util.Log.w("apkpy", "auth: the session ended (" + jo.optString("error_description", "") + ")");
                clear(c);
            }
        } catch (Exception e) {
            // No network: the next read of the token tries again.
        }
    }

    // ── The tokens, encrypted ────────────────────────────────────────────

    private static javax.crypto.SecretKey key() throws Exception {
        java.security.KeyStore ks = java.security.KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (!ks.containsAlias("apkpy_auth_key")) {
            javax.crypto.KeyGenerator kg = javax.crypto.KeyGenerator.getInstance(
                    android.security.keystore.KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            kg.init(new android.security.keystore.KeyGenParameterSpec.Builder("apkpy_auth_key",
                    android.security.keystore.KeyProperties.PURPOSE_ENCRYPT
                            | android.security.keystore.KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(android.security.keystore.KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(android.security.keystore.KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build());
            kg.generateKey();
        }
        return (javax.crypto.SecretKey) ks.getKey("apkpy_auth_key", null);
    }

    private static void put(SharedPreferences.Editor e, String name, String value) {
        try {
            javax.crypto.Cipher cipher = javax.crypto.Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(javax.crypto.Cipher.ENCRYPT_MODE, key());
            byte[] iv = cipher.getIV();
            byte[] box = cipher.doFinal(value.getBytes("UTF-8"));
            byte[] all = new byte[iv.length + box.length];
            System.arraycopy(iv, 0, all, 0, iv.length);
            System.arraycopy(box, 0, all, iv.length, box.length);
            e.putString(name, "k:" + android.util.Base64.encodeToString(all, android.util.Base64.NO_WRAP));
        } catch (Exception ex) {
            // A Keystore that will not work (it happens after some restores):
            // kept as it is, in a file private to the app and out of backups.
            e.putString(name, "p:" + value);
        }
    }

    private static String get(SharedPreferences p, String name) {
        String v = p.getString(name, "");
        if (v.startsWith("p:")) return v.substring(2);
        // A token kept by an app built before 1.14, before encryption: as it is.
        if (!v.startsWith("k:")) return v;
        try {
            byte[] all = android.util.Base64.decode(v.substring(2), android.util.Base64.NO_WRAP);
            javax.crypto.Cipher cipher = javax.crypto.Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(javax.crypto.Cipher.DECRYPT_MODE, key(),
                    new javax.crypto.spec.GCMParameterSpec(128, all, 0, 12));
            return new String(cipher.doFinal(all, 12, all.length - 12), "UTF-8");
        } catch (Exception ex) {
            return "";
        }
    }

    // ── Plumbing ─────────────────────────────────────────────────────────

    private static String random(int n) {
        byte[] b = new byte[n];
        new java.security.SecureRandom().nextBytes(b);
        return android.util.Base64.encodeToString(b,
                android.util.Base64.URL_SAFE | android.util.Base64.NO_WRAP | android.util.Base64.NO_PADDING);
    }

    private static String challenge(String verifier) throws Exception {
        byte[] d = java.security.MessageDigest.getInstance("SHA-256").digest(verifier.getBytes("US-ASCII"));
        return android.util.Base64.encodeToString(d,
                android.util.Base64.URL_SAFE | android.util.Base64.NO_WRAP | android.util.Base64.NO_PADDING);
    }

    private static String enc(String s) throws Exception {
        return java.net.URLEncoder.encode(s, "UTF-8");
    }

    private static java.net.HttpURLConnection open(String url) throws Exception {
        java.net.HttpURLConnection conn = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(15000);
        conn.setRequestProperty("Accept", "application/json");
        return conn;
    }

    private static String post(String url, String body) throws Exception {
        java.net.HttpURLConnection conn = open(url);
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded");
        java.io.OutputStream os = conn.getOutputStream();
        os.write(body.getBytes("UTF-8"));
        os.close();
        return read(conn);
    }

    private static String read(java.net.HttpURLConnection conn) throws Exception {
        int rc = conn.getResponseCode();
        java.io.InputStream is = rc < 400 ? conn.getInputStream() : conn.getErrorStream();
        if (is == null) return "";
        java.io.BufferedReader r = new java.io.BufferedReader(new java.io.InputStreamReader(is, "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = r.readLine()) != null) sb.append(line);
        r.close();
        conn.disconnect();
        return sb.toString();
    }
}
'''
