---
title: Version 1.6.0
description: ApkPy 1.6.0 makes the app say what it could not do instead of doing nothing, adds Bluetooth, in-app purchases, languages, crash reports and code scanning, and repairs a backup rule that was quietly emptying people's data.
---

# ApkPy 1.6.0 — Things that failed quietly

Almost everything in this release began the same way: something did not work,
and **nothing said so**.

An app that changed phone came back with every saved value empty. `math.sqrt(x)`
compiled to a blank label. `items.append(x)` generated no line at all, so the
chat example that ships with the library never worked on a phone. `round(2.5)`
gave 2 on the desktop and 3 on the device. A crash on somebody else's phone was
invisible. An image with no description was announced, by a screen reader, as
nothing.

None of those produced an error. Every one of them produced an app that built,
installed and ran — and was wrong in a way you would only find months later, if
at all. This version is mostly about ending that, and partly about the things a
business app could not do at all.

---

## Part 1 — The silence

### `U2033` — Python with no translation now says so

ApkPy reads your module and writes Java. It translates a fixed vocabulary of
Python rather than running it, and anything outside that vocabulary used to
fall out of the generator as the empty string.

```python
out.set_value(math.sqrt(16))     # before: an empty label, no warning
```

Now it stops and names the construct, and says which of two things it is:

- **A gap.** `re`, `json.dumps`, `base64` all have Java equivalents ApkPy has
  not wired up yet. The message says so and suggests something that compiles
  today.
- **A wall.** `requests`, `numpy`, `pandas`, `os` need a Python interpreter,
  and there is none on the phone. The message points at the ApkPy API that
  covers the same ground — `https`, `db`, `files`.

It also catches a mistyped helper (`refrsh()` → *"Did you mean refresh?"*),
`print()` — which used to compile to a call to a method nobody wrote — and a
modal opened above the line that creates it, which is about order rather than
vocabulary.

The full list of translated Python now lives on
[Compatibility and limits](compatibility.md). It did not exist before, which
made *"check the list on the docs page"* poor advice.

### `try` / `except` / `finally`

The body of a `try` used to be dropped whole.

```python
try:
    total = int(field.get_value())
    storage.set("total", total)
except Exception as problem:
    total = "0"
    toast(problem)
finally:
    count.set_value(total)
```

**One `except`, deliberately.** Python's exception types have no equivalent on
the phone — every value there is text, and the errors that arrive are Java ones
with different names. Telling two kinds apart is a promise ApkPy cannot keep,
so a second handler is refused with its reason rather than quietly running the
first. `except ... as e` binds a **String**, because that is what every use of
it does: show it, store it, send it.

Variables first assigned inside the block are declared before it. Python has no
block scope and Java does, and without that the `finally` above could not see
`total`.

### `items.append(x)`

It generated no line at all — not even a wrong one. It now works, and so does
reading the list back: `items[0]`, `items[-1]`, `len(items)`, `for x in items`.

Indexing used to emit `(x)[Integer.parseInt(...)]`, which is not Java; you
cannot index a String with brackets. It now goes through a helper, with
Python's negative indexing.

**A list written at module level that the app appends to is now one list for
the whole app**, kept in the process-wide store — exactly what a module-level
list means in Python. A copy per screen would reset every time somebody opened
one. Lists nobody appends to keep the old inlining, so no existing app gains a
field it never asked for.

`set_items()` also stopped substituting the original literal, which is why the
screen used to keep showing the starting list after it had grown.

### `math`, and four builtins

Write `import math` and use the standard module; the Previewer gets Python's
own, and the phone gets `java.lang.Math`.

```
sqrt exp log log10 fabs pow hypot floor ceil trunc
sin cos tan asin acos atan atan2 degrees radians
pi e tau        plus abs, min, max and sum
```

Only names where Java's answer *is* Python's answer. `math.log2` is left out
because Java has no `Math.log2` and `log(x)/log(2)` disagrees with `math.log2`
on **8 of the first 60 powers of two**; `math.inf` because Python writes `inf`
where Java writes `Infinity`. A translation that is right most of the time is
worse than one that says no.

`abs`, `min`, `max` and `sum` go through helpers rather than straight to
`Math`, because Python distinguishes an integer from a decimal — `abs(-3)` is
`3`, not `3.0` — and every value here is text.

---

## Part 2 — Hardware, and money

### Bluetooth, classic and low energy

Both radios, the same four verbs, the same result contract:
`devices()`/`scan()`, `connect()`, `send()`, `disconnect()`. Lines of text out,
lines of text back.

**Classic declares no location permission at all.** `devices()` lists paired
devices rather than scanning, because an RFCOMM socket needs a bonded device
anyway. An app that only talks to a printer should never have to ask where its
user is.

`ble` defaults to the Nordic UART Service — what an ESP32, a micro:bit or an
HM-10 exposes — so the common case names no UUIDs. Ten possible reasons, never
an empty string. Verified against a real smartwatch: the permission prompts,
the scan, the connection, service discovery, `no_service`, and every failure
word.

The link belongs to the app rather than to a screen, so it survives navigation.

### In-app purchases

One-time unlocks and subscriptions: `prices()`, `buy()`, `subscribe()`,
`owned()`, `consume()`.

**Google refunds any purchase an app fails to acknowledge within three days.**
The library acknowledges every purchase before it reports success — there is no
call you can forget. A purchase completed while the app was closed is found and
settled on the next launch, which is the case nobody was watching and the one
that was losing money.

Prices are never written by hand: they come from Play, in the local currency.

!!! warning "Compiled and reviewed, never sold"

    Play billing cannot be tested without a Play Console account, an uploaded
    build and a licensed tester. What can be shown is that it compiles against
    Billing Library 7.1.1 and that the generated Java was read line by line
    against the classic mistakes — which found three real bugs, including the
    refund hole above.

---

## Part 3 — Keeping things

### The backup rule that was emptying people's data

`android:allowBackup` was `true`, so Android copied the app's stored values to
a new phone. Those values are encrypted with a key in the **old** phone's
Keystore, which never travels. On the new phone every read decrypted to `""`
and was reported as never saved.

**Somebody changed phone and everything the app had stored was gone, with no
error.** The encrypted store and the login token are now excluded from both
cloud backup and direct device transfer, on every Android version. This changes
the manifest of every app, and it is right, because the alternative is losing
data.

### Encryption that travels, and a second factor

- `crypto.encrypt(text, password=...)` — PBKDF2-HMAC-SHA256 at 200 000 rounds
  into real AES-256-GCM, in a **standard format** any language or `openssl` can
  open. Portability is the whole point.
- `crypto.totp(secret)` — RFC 6238, verified against all six published test
  vectors.
- `crypto.token()`, `crypto.hash()`, `crypto.hash_file()`, and
  `secure_screen()` for `FLAG_SECURE`.

### Certificate pinning

```python
https.pin("api.example.com", [current_pin, backup_pin], expires="2027-06-01")
```

Android checks that a certificate chains to a trusted authority, not *which*
one — so anyone who can obtain a trusted certificate can read the traffic, and
on a managed device that includes whoever installed the company's root.

Written as configuration, so Android applies it underneath every HTTP library
in the app. **Two pins are required**: an app pinned only to the certificate
you can see today stops reaching its own server the day it is replaced, for
everyone at once, fixable only by a store update.

The Previewer opens a real handshake and **refuses the request while printing
the pin the host is actually using**, so a mistyped pin appears on your desk
instead of on somebody's phone.

---

## Part 4 — What a business app was missing

### Languages

```python
translations({"en": {"title": "Warehouse"},
              "pt": {"title": "Armazem"}}, default="en")

label(t("title"), id="head", screen=home)
```

Text used to be written straight into each screen, so an app spoke exactly one
language. Now each language becomes its own `res/values-<tag>/` folder and the
phone picks by its own locale. `language.set("pt")` switches while the app
runs.

A key missing from the default language is refused while you build, rather than
becoming a missing-resource error against XML nobody wrote.

### Crash reports

`crash.last()` hands you the previous crash — time, thread, Android version,
device and stack trace — and `crash.clear()` forgets it. ApkPy chooses no
vendor and invents no endpoint: everything needed to send it already exists.

The handler passes the crash on to Android's own, which is what stops the app
and tells the person. Swallowing it would leave a frozen window.

### Reading barcodes and QR codes

`scan.code(on_result=...)`, with **no CAMERA permission** — the camera runs
inside Play services and the app never sees a frame. One fewer permission on
the store listing, and one fewer thing to explain in a security review.

### Forcing an update

`app.version_code()` and `app.version_name()` read the **installed** package;
`app.open_store()` tries Play and falls back to the web listing; and
`modal(..., dismissable=False)` is a wall rather than a dialog — no back
button, no tap outside, no cancel.

The protocol stays yours. An app distributed through a company's own device
management is not asking Play anything.

### Accessibility

`describe=` on anything without words of its own:

```python
image("shelf.png", id="shelf", screen=home, describe="Aisle 4, third shelf")
image("divider.png", id="rule", screen=home, describe="")      # decoration
```

An **empty** description is a decision, not an omission: it marks the element
as decorative and a screen reader skips it, instead of announcing a file name.

And a `U2035` report during the build, listing what a screen reader or a
low-vision user would struggle with — undescribed images, unlabelled icon
buttons, text below WCAG contrast, tap targets under 48dp. It reports and lets
the build finish, because every app has an image somebody forgot to describe
and refusing to build would only teach people to switch the check off.

---

## Also fixed

- **`round(2.5)` gave 2 in the Previewer and 3 on the phone.** Python rounds a
  half to the even neighbour; `Math.round` always rounds up. Over 4001 values,
  the old rule disagreed with Python on **1000** of them.
- **Decimals printed differently on the two sides.** Java switches to exponent
  notation from 1e7 and Python only from 1e16, so `math.pow(10, 8)` was
  `1.0E8` on the phone and `100000000.0` on the desktop. Now written with
  Python's rule — proven against `repr()` across 90 022 values.
- **`math.floor(2.7)` printed `2.0`** on the phone. `floor`, `ceil` and `trunc`
  return an `int` in Python 3.
- **`math.sqrt(-1)` returned NaN** on the phone and put that word on screen,
  where Python raises. Both sides now raise, and one `try`/`except` covers
  them.
- **`label(MSG)` and `label("a" + "b")` produced an empty attribute** — the text
  showed in the Previewer and nothing on the phone.
- **`sync.input()` inside a job**, `get_value()` from another screen, and
  `job.attempt()` were being reported as untranslatable by the new guard. They
  are not; each belongs to the other generated runtime.
- **Two shipped examples were broken.** `22_chat_composer.py` appended to a
  list, which did nothing; `23_settings_rows.py` opened a modal declared eleven
  lines below its own button.
- **A test that tested nothing.** It searched the whole generated file for a
  string every app contains, so it passed while the line it was checking came
  out blank.

---

## Verification

| | |
| --- | --- |
| `playground/transpile_tests.py` | 256 |
| `tests/` | 35 |
| `tests/features/` | 778 |
| Examples that transpile | 28 of 28 |
| `mkdocs build --strict` | clean |

Beyond the counts: a real APK was built for every feature in this release and
the generated Java read line by line — which is where nine logic bugs were
found that both `javac` and the test suites had passed. Bluetooth was verified
against a real smartwatch. The contrast maths was checked against WCAG's own
published values, the TOTP against RFC 6238's six vectors, and the rounding and
number formatting against Python itself over tens of thousands of values.

Play billing is the one thing here nobody has been able to test.

---

## Upgrading

```powershell
python -m pip install --upgrade apkpy
```

!!! warning "An app that built before may now refuse to build"

    This is the intended change, and the important one. Code that ApkPy could
    not translate used to compile to an empty value; it now stops with
    `U2033` and names it. If your app used `math`, `abs`, `min`, `max` or
    `sum` it will now work rather than being blank — but if it used something
    still outside the vocabulary, the build will tell you instead of shipping
    a blank label.

    That failure was already there. It was just being kept from you.

Four behaviours changed without an opt-in, all four because they were defects:

1. **`round()` on an exact half** now answers the way Python does. `round(2.5)`
   is 2 on both sides; it was 3 on the phone.
2. **Decimals are written the way Python writes them.** A value at or above
   1e7 no longer appears as `1.0E8`.
3. **The encrypted store is excluded from backup.** Every app's manifest gains
   the rules. Existing installs keep their data; what changes is that it stops
   travelling to a phone that cannot read it.
4. **`math.floor`, `ceil` and `trunc` return whole numbers**, not `2.0`.
Everything else in 1.6.0 is opt-in. An app that names none of it generates the
project it generated on 1.5.0.
