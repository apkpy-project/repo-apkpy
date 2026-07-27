# Security Policy

## Supported Versions

| Version | Supported |
| :---: | :---: |
| 1.0.x | ✅ Yes |
| 0.9.x | ✅ Yes |
| < 0.9 | ❌ No |

## Built-in Security Features (v1.0.0)

ApkPy ships a security layer out of the box — no external dependencies, no new permissions:

- **Password hashing**: `crypto.hash_password()` / `crypto.verify_password()` — salted PBKDF2-HMAC (SHA-256/512, 200,000 iterations by default), constant-time verification. Never store plain-text passwords.
- **Two-way encryption**: `crypto.encrypt()` / `crypto.decrypt()` — AES-256-GCM on Android with a hardware-backed, non-extractable Android Keystore key.
- **Automatic storage encryption**: every `storage.set()` value is encrypted before it reaches the disk; `storage.get()` decrypts transparently.
- **SQL injection protection**: `db.execute(sql, [params])` / `db.query(sql, [params])` bind values with `?` placeholders via the SQLite engine — user input is never concatenated into SQL.

See the README sections *SQLite Database* and *Crypto / Password Hashing* for usage and the honest threat model (what these features do and do not protect against).

## Reporting a Vulnerability

If you discover a security vulnerability in ApkPy, **please do not open a public GitHub issue**. Instead, please report it by opening a private security advisory on GitHub or contacting the maintainers.

We will acknowledge your report within 48 hours and aim to release a patch within 7 days for confirmed vulnerabilities.

Please include:
- A description of the vulnerability
- Steps to reproduce it
- Potential impact
- Any suggested fix (if you have one)
