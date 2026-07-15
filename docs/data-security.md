# Data, network and security

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

Encrypted values are device-bound by design. A copied database or storage file should not be treated as a portable backup.

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
