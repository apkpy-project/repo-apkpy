# Data, network and security

For an end-to-end local example, start with
[SQLite and protected local data](guides/sqlite-security.md).

## Encrypted key/value storage

~~~ python
storage.set("display_name", "Marta")
name = storage.get("display_name", "Guest")

storage.delete("display_name")
storage.clear()
keys = storage.keys()
~~~

Storage values are encrypted automatically before being written. Existing plain-text values from older versions remain readable for migration.

- Android uses AES-256-GCM with a key held by Android Keystore.
- The Previewer uses an authenticated local encryption format and a device key.

Encrypted values are device-bound by design. A copied storage file is not a
portable backup -- the key that opens it never leaves the phone.

!!! warning "Which is why backup has to leave it alone"
    Android's auto-backup copies preferences to a new phone, but the Keystore
    key does not travel. A restored app would decrypt every value to `""` and
    report it as never saved -- silent data loss, noticed months later. ApkPy
    excludes the encrypted store from both cloud backup and direct
    device-to-device transfer, so the data stays home rather than arriving
    corrupted. If you want it to travel, encrypt it with a password instead.

## Encryption that travels

~~~ python
box = crypto.encrypt("the secret", password="open sesame")
crypto.decrypt(box, password="open sesame")     # "the secret"
crypto.decrypt(box, password="wrong")           # ""
~~~

With `password=`, the key comes from that password instead of from the phone,
and the result is portable: encrypt on the phone, open it on the desktop, in a
Python script, or with `openssl`. Nothing but the password is needed to open
it -- and nothing but the password can.

The format is `pw1$rounds$salt$nonce$box`, all hex: PBKDF2-HMAC-SHA256 over
200,000 rounds for the key, then AES-256-GCM. Both runtimes write and read the
same thing, which is the whole point -- a box that only ApkPy could open would
not be portable at all.

A wrong password and tampered data both return `""`. GCM's tag fails before
anything comes out, which is why an authenticated cipher is worth the extra
bytes.

!!! note "The Previewer needs one package for this"
    Python has no AES of its own, so the desktop side uses `cryptography`:
    `pip install cryptography`, or `pip install apkpy[crypto]`. The built
    Android app needs nothing extra. Calling it without the package raises
    `U2032`, which says exactly that.

## Random that cannot be guessed

~~~ python
crypto.token()        # 16 bytes as hex
crypto.token(32)      # longer
~~~

For session ids, one-time links and nonces. `random.choice()` and
`random.randint()` stay on the ordinary generator on purpose -- shuffling a
list is not a secret -- but two of its outputs give away the rest, so it must
never hold one.

## Hashing data

~~~ python
crypto.hash("some text")          # SHA-256, as hex
crypto.hash_file(path)            # the same, read in chunks
~~~

For integrity and comparison: has this file changed, are these two the same,
have I seen this before. `hash_file` reads a `content://` handle from
`files.pick` as happily as a path.

**Not for passwords.** SHA-256 is fast by design, which is exactly what
somebody guessing them wants. Use `crypto.hash_password`.

## Two-factor codes

~~~ python
crypto.totp("JBSWY3DPEHPK3PXP")                  # "492039"
crypto.totp(secret, digits=8, period=60)
~~~

The digits an authenticator app shows, from the base32 secret a QR code
carries. RFC 6238: HMAC-SHA1 over the number of periods since 1970. It is
entirely local -- no network, no account -- which is why an authenticator
works on a plane.

Spaces and case are forgiven, because people copy these by hand. A secret that
is not base32 returns `""` on both sides.

This one is checked against the six vectors published in the RFC itself, so it
is the rare piece of ApkPy that can be proven right rather than merely
reviewed.

## Screens that cannot be photographed

~~~ python
secure_screen(vault)     # just that screen
secure_screen()          # every screen
~~~

Android's `FLAG_SECURE`: screenshots and recordings come out black, and the
app is blank in the recents carousel. Banking and messaging apps use it for
exactly this.

**The Previewer cannot honour it and does not pretend to** -- Tk has no
equivalent, and a desktop capture tool would grab the window anyway. On the
phone the flag is invisible too, right up until somebody tries to capture the
screen.

## Password hashing

Passwords should be hashed, not encrypted:

~~~ python
stored_hash = crypto.hash_password(password)
is_valid = crypto.verify_password(candidate, stored_hash)
~~~

The default is salted PBKDF2 with 200,000 iterations. The stored value contains the algorithm, iteration count, salt and derived hash — never the original password.

Use two-way encryption only for values the application must read back:

~~~ python
encrypted = crypto.encrypt("private note")
plain_text = crypto.decrypt(encrypted)
~~~

Decryption returns an empty string for malformed, altered or foreign-device values.

## SQLite

~~~ python
db.execute(
    "CREATE TABLE IF NOT EXISTS tracks "
    "(id INTEGER PRIMARY KEY, title TEXT, artist TEXT)"
)

db.execute(
    "INSERT INTO tracks(title, artist) VALUES (?, ?)",
    ["Midnight Drive", "Nova"],
)

rows = db.query(
    "SELECT id, title, artist FROM tracks WHERE artist = ?",
    ["Nova"],
)
~~~

Always use <code>?</code> placeholders for user-controlled values. Parameter binding prevents SQL injection and correctly handles apostrophes and special characters.

Queries return a JSON array string so the same value can cross the Previewer/Android boundary:

~~~ python
title = json_get(rows, "0.title")
track_list.set_items(rows, title="title", subtitle="artist")
~~~

Transactions group writes:

~~~ python
db.begin()
db.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", [10, 1])
db.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", [10, 2])
db.commit()
~~~

Call <code>db.rollback()</code> when a grouped operation fails.

## HTTPS

~~~ python
def loaded(success, response):
    if success:
        result.set_value(json_get(response, "title"))
    else:
        result.set_value("Request failed")

https.get(
    "https://api.example.com/tracks/42",
    headers={"Authorization": "Bearer " + auth.token()},
    on_response=loaded,
)
~~~

Full REST operations:

~~~ python
https.post(url, data={"title": "New"}, headers=headers, on_response=done)
https.put(url, data={"title": "Replacement"}, headers=headers, on_response=done)
https.patch(url, data={"title": "Changed"}, headers=headers, on_response=done)
https.delete(url, headers=headers, on_response=done)
~~~

Requests run away from the UI thread. A 4xx/5xx response delivers the server response body to the callback, which is useful for structured API errors.

## Security boundaries

Encryption at rest does not make every value safe:

- do not embed permanent service secrets in <code>writehere.py</code>;
- use OAuth with PKCE or short-lived tokens for user authorization;
- use HTTPS for all remote APIs;
- validate server responses and user input;
- keep signing keys outside the repository and back them up securely;
- remember that a determined user can inspect any client application.

For privileged operations, keep the secret and authorization decision on a server you control.

## Certificate pinning

Android checks that a server's certificate chains to a trusted authority. It
does not check *which* authority — so anyone who can obtain a certificate the
phone trusts can read the traffic, and on a managed device that includes
whoever installed the company's own root. Pinning says which public key is
acceptable for one host, and nothing else is.

~~~python
from apkpy_lib import https

https.pin("api.example.com", [
    "sha256/K87oWBWM9UZfyddvDfoxL+8lpNyoUB2ptGtn0fv6G2Q=",   # in use
    "sha256/JbQbUG5JMJUoI6brnx0x3vZF6jilxsapbXGVfjhN8Fg=",   # the spare
], expires="2027-06-01", subdomains=True)
~~~

This becomes `res/xml/apkpy_network_security.xml` and a manifest attribute, so
Android applies it **underneath every HTTP library in the app**. Done in code
it would only cover the requests that remembered to ask.

!!! warning "Two pins, and the second one is not optional"

    An app pinned only to the certificate you can see today stops reaching its
    own server the day that certificate is replaced — every copy, at once,
    fixable only by a store update people may not install for weeks. The spare
    is what turns a renewal back into a routine, so a set with one pin is
    refused while you build.

    Use the pin of the *next* certificate, or of the issuing authority.

`expires` is the date Android stops enforcing the set. It is a safety valve
rather than a schedule: past it the app keeps working with ordinary
certificate checking instead of refusing to connect for ever.

### The Previewer checks the pins for you

A mistyped pin is otherwise invisible until the app is on somebody's phone,
refusing to reach its own server. The Previewer opens a real handshake with the
host the first time you call it, and if nothing matches it **refuses the
request and prints the pin the host is actually using** — ready to paste. This
needs the optional `cryptography` package; without it the check is skipped
rather than guessed.

A **debug** build keeps trusting certificates you installed yourself, so a
proxy still works while you develop. Android reads that block only when the app
is debuggable, so a release build is untouched.
