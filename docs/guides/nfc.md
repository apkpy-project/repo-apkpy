---
title: NFC tags
description: Foreground NFC reading, one-shot NDEF writes and an honest desktop simulator.
---

# NFC tags

NFC is short-range radio: hold a compatible tag within a few centimetres of
the phone. A tag can label equipment, carry a contact link, or store a small
note. The app reads the tag locally; no cloud service is required.

ApkPy reads NDEF text and URI records and can write **one text or URI record**
to a compatible, writable tag. The Android implementation uses the platform
`NfcAdapter` reader mode, not foreground dispatch. No Python or new Android
dependency is included in the generated APK.

## Complete app

Want the full lab instead? [Download NFC Tags](../downloads/nfc/nfc-tags.py),
save it as `writehere.py` in your ApkPy project.
It includes settings, reading, writing, cancellation and messages for every
reason. The published 1.8.0 package does not contain these methods.

## What you can build

- **Equipment and inventory:** store a short item reference or URL on a label,
  then look it up in your own database or API after the tag callback.
- **Exhibitions and product information:** display a description when a visitor
  touches a tag while your app is open.
- **Personal shortcuts:** use tags to select a project, timer preset or checklist
  inside the running app. Launching a closed app from a tag is not included.
- **Tag-writing utilities:** let the person inspect and explicitly replace a
  spare tag's text or URL. Always explain that existing records are overwritten.

NFC supplies the tag event, not a backend, authorization system or secure proof
of identity. Do not use a plain tag ID as the only credential for door access,
payments or attendance fraud prevention.

## A complete reader

```python
from apkpy_lib import Screen, button, json_get, label, nfc, run

home = Screen(id="home")
status = label("Tap Start, then hold a tag near the phone.", screen=home)
content = label("No tag yet", screen=home)

def read_tag(ok, tag):
    content.set_value("ID: " + json_get(tag, "id")
                      + "\nText: " + json_get(tag, "text")
                      + "\nURL: " + json_get(tag, "url"))

def failed(ok, reason):
    status.set_value("NFC: " + reason)

def checked(ok, reason):
    if ok:
        status.set_value("Ready. Hold a tag near the phone.")
        nfc.start(on_tag=read_tag, on_error=failed)
    else:
        failed(ok, reason)

def start():
    nfc.status(on_result=checked)

button("Start", screen=home, command=start)
button("Stop", screen=home, command=lambda: nfc.stop())
button("NFC settings", screen=home, command=lambda: nfc.settings())
run(start_screen=home)
```

All NFC callbacks accept **two arguments**, `(ok, value)`, and Android delivers
them on the UI thread. `status()` reports `(True, "ready")`, or
`(False, "off")` / `(False, "unsupported")`. Unexpected platform errors report
`unknown` and log technical details. NFC is a normal manifest permission;
there is no runtime permission prompt and the app cannot switch the radio on.

The compiler includes `android.permission.NFC` and
`android.hardware.nfc` with `required="false"` only when NFC is used. An app
without NFC calls gets no NFC Java, permission or feature declaration.

## What a tag contains

The callback receives **JSON text**, not a Python dictionary. Read fields with
`json_get`. Every field below is always present:

```json
{"id":"04A224B2C15E80","type":"NDEF","text":"Hello","url":"","records":1,"writable":"yes","size":"492","used":"12","tech":"NfcA,Ndef"}
```

| Field | Meaning |
| --- | --- |
| `id` | Uppercase hexadecimal identifier, no separators; may be empty or change on some devices |
| `type` | `NDEF`, `FORMATABLE`, `UNKNOWN`, or the first MIME/external record type |
| `text` | First text record, decoded as UTF-8/UTF-16 using its language length; readable MIME/external text is also accepted |
| `url` | First URI record, expanding all NFC Forum prefixes from 0x00 to 0x23 |
| `records` | Number of records, as a JSON number |
| `writable` | `yes` or `no` |
| `size` | NDEF capacity in bytes, as text; `""` if unknown |
| `used` | Encoded NDEF message size in bytes, as text; `""` for unknown technology |
| `tech` | Comma-separated Android technology names |

A formatable empty tag returns `FORMATABLE`, `writable="yes"`, no records and
unknown capacity. A non-NDEF tag still returns its ID and technology list;
it is not an error merely because it has no text. Empty or malformed record
payloads do not crash the reader; unreadable binary data is not guessed as text.
The complete raw record list is not exposed in this version.

**Security:** tag content is untrusted input. Display or validate URLs before
opening them. A tag ID is not a secret or an authentication credential; NFC
proximity alone does not make an access-control system secure.

## Write on the next contact

```python
def written(ok, reason):
    if ok:
        status.set_value("Written. Keep the tag still for read-back.")
    else:
        status.set_value("Write failed: " + reason)

def save_text():
    nfc.write(text="Hello from ApkPy", on_result=written)

def save_url():
    nfc.write(url="https://example.com/help", on_result=written)

# Add these buttons to the reader above, before run().
button("Write text", screen=home, command=save_text)
button("Write URL", screen=home, command=save_url)
button("Cancel write", screen=home, command=lambda: nfc.cancel_write())
```

Call `start()` first. `write()` **arms the next tag contact**; it does not
write immediately or retain the last tag for later use. Remove and re-present
a tag if it was already touching the phone before you armed the write.
Choose exactly one of `text=` or `url=`. Empty text is allowed; an empty URL
fails with `unknown`. The new single-record message **replaces all existing
NDEF records**. Use only your own spare, rewritable test tags.

- One attempt consumes the pending write, on success **or failure**. Arm it
  again to retry. Calling `write()` again replaces an earlier pending request.
- `cancel_write()` silently cancels pending work, not a physical write already
  in progress. It cannot undo bytes already written. Old queued callbacks are
  discarded after cancellation, stopping or leaving the screen.
- Capacity is checked against the complete encoded message, including NDEF
  headers, language bytes and UTF-8 byte lengths—not character count.
- Normal NDEF tags are read back from the tag, bypassing the pre-write cache.
  `on_result(True, "ok")` is delivered before `on_tag(True, updated_json)`.
- If writing succeeded but read-back failed, the write still reports `ok`,
  followed by `on_error(False, reason)`. Do not interpret that as a rolled-back
  write.
- **Formatting exception:** Android's discovered `Tag` has an immutable
  technology list. After formatting an empty tag, the immediate callback
  carries the message acknowledged by `format()`, with unknown capacity and
  the original technology list. Remove and re-present it for an independent
  NDEF read-back and fresh metadata. The simulator follows this distinction.
- NFC writes are not transactions. Removing a tag or losing power can leave
  incomplete content; always verify important data afterwards.

## Reasons and recovery

| Reason | What happened | What to do |
| --- | --- | --- |
| `unsupported` | No NFC adapter | Offer a manual/QR alternative |
| `off` | Radio disabled | Open `nfc.settings()`; the user enables it |
| `not_started` | Write without a started reader | Call `nfc.start()` first |
| `no_ndef` | Neither NDEF nor formatable | Choose a compatible tag |
| `read_only` | Tag cannot be written | Use a spare rewritable tag |
| `too_small` | Encoded message exceeds capacity | Shorten it or choose a larger tag |
| `tag_lost` | Tag moved away during I/O | Keep it still, then retry explicitly |
| `unknown` | Other I/O, format or platform failure | Inspect Android logcat / Previewer console |

For a formatable tag, capacity may not be known before formatting. A platform
format failure can therefore be `unknown`, rather than `too_small`.

## Screens, lifecycle and background jobs

Reading belongs to the foreground Activity. ApkPy disables reader mode in
`onPause`, re-enables it in `onResume` only after a prior `start()`, and removes
callbacks in `onDestroy`. Leaving the screen cancels a pending write to prevent
an accidental write when returning. `stop()` also forgets its callbacks.
An Activity recreation starts a new session: use a screen `on_resume` callback
to call `start()` again if the app should always listen on arrival.

Tag I/O runs on Android's reader callback thread, not on the UI thread. Stale
results are rejected before touching a paused/destroyed screen.

Background jobs cannot start reading, query status, open settings or arm a
write: compilation stops with `U2033`. `nfc.stop()` and `cancel_write()` may be
used in a job to stop/cancel this app's existing reader sessions through the
main-thread dispatcher. There is no screen-off NFC reader.

## Previewer simulation

`start()` opens a **190 px panel inside the phone frame**, in the current theme.
Its header says `NFC SIMULATOR · NO RADIO`. It does not use desktop NFC hardware
or create a separate window. With no running Previewer, `start()` reports
`unsupported` without constructing Tk; `status()` is a simulated `ready` value,
not a hardware check.

| Button | Simulated tag |
| --- | --- |
| Text tag | UTF-8 text with a five-byte `pt-PT` language code |
| URL tag | An HTTPS URI record |
| Empty tag | A formatable empty tag |
| Read-only | Readable NDEF that rejects writes |
| Small (12 B) | Capacity checked against actual encoded length |
| Unknown tech | ID/technology only, no NDEF |
| Simulate tag lost | Reading/writing interrupted |

The same buttons become write destinations when a write is pending. Successful
writes update the simulated tag for subsequent taps. Closing the panel stops
reading. Simulated tag contents last for the screen session, not across app
restarts. This tests callbacks and recovery, **not RF range, antenna position,
tag hardware, real capacity or physical write reliability**.

## Complete example and device verification

The repository example is `examples/29_nfc_tags.py` ([download NFC Tags](../downloads/nfc/nfc-tags.py)). It includes
status, reading, settings, text/URL writes, cancellation and all error messages.
`apkpy build` generates its Android project.

Before shipping your app, test on a real NFC phone with a spare NDEF tag and
with NFC disabled. Without a physical tag, opening settings and exercising
lifecycle only proves those paths—not a successful read or write.

The [1.9.0 verification summary](../version-1.9.0.md#verification) separates
automated tests, directly observed device behavior and what the maintainer
reported. On 20 September 2026 that report became specific: one NDEF tag read,
and a write to a second tag, on a physical phone. That is one person, one
handset and two tags. It says a read and a write happened; it does not certify
NFC across tag types, chipsets and manufacturers, which is why the advice above
still stands.

## Outside this version

- **HCE / card emulation:** requires a service, registered AIDs and its own
  security model; not included.
- **Android Beam / peer-to-peer:** removed from Android starting with API 33;
  not a supported transport.
- **MIFARE Classic authentication/raw access:** proprietary keys and hardware
  variability; no general support promised. Generic NDEF may work where the
  device exposes it, but there is no Classic-specific API.
- **Raw ISO-DEP/APDU**, payment cards and identity documents: no command
  exchange, credential copying or protocol support.
- **Launch the app by tapping a tag:** no `NDEF_DISCOVERED` intent filters;
  this version reads only while the app is already in front.
- **Screen-off reading:** unsupported by this foreground reader mode.

Platform references: [NfcAdapter](https://developer.android.com/reference/android/nfc/NfcAdapter),
[Ndef](https://developer.android.com/reference/android/nfc/tech/Ndef), and
[NdefRecord](https://developer.android.com/reference/android/nfc/NdefRecord).
