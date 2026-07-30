---
title: SQLite and protected local data
description: Use parameterized SQLite, transactions, password hashing and encrypted values with ApkPy.
---

# SQLite and protected local data

Create tables with bound parameters and keep secrets out of source code.

```python
from apkpy_lib import crypto, db, storage

db.execute(
    "CREATE TABLE IF NOT EXISTS notes ("
    "id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL)"
)

def save_note(title, body):
    db.begin()
    try:
        db.execute(
            "INSERT INTO notes(title, body) VALUES (?, ?)",
            [title, body],
        )
        db.commit()
    except Exception:
        db.rollback()

notes = db.query(
    "SELECT id, title, body FROM notes ORDER BY id DESC",
    [],
)

password_hash = crypto.hash_password("user-password")
is_valid = crypto.verify_password("user-password", password_hash)

# storage encrypts values automatically
storage.set("session", "short-lived-token")
token = storage.get("session", "")

# use crypto directly for a database field that must be read later
protected_body = crypto.encrypt("private note")
plain_body = crypto.decrypt(protected_body)
```

## Boundaries that matter

- parameter binding protects SQL structure; it does not authorize a user;
- password hashing is deliberately slow; do not encrypt passwords;
- encryption protects local values, not traffic or your remote database;
- API secrets that grant privileged access belong on a server, never in an APK.

Read [Data, network and security](../data-security.md) before shipping.
