---
title: ApkPy 1.9.0 — NFC, contacts and your own Java
description: NFC tags, scoped contacts and a seam for your own Java, with complete apps, permission rules, lifecycle and verification limits.
---

# ApkPy 1.9.0 — NFC, contacts and your own Java

Touch a label to look up an item, show product information or select a preset
inside your app. Write a small text or URL record to your own spare tag. The
app generates native Android code; it does not bundle Python or a new Android
dependency for NFC.

This update also adds a scoped phone/email picker, permission-based contact
search and user-controlled creation/editing in Android's own Contacts app.
Use these for appointment clients, customer directories and selected recipients.
Neither feature sends data to a server on your behalf.

## NFC API

| Call | Behavior |
| --- | --- |
| `nfc.status(on_result=checked)` | `(True, "ready")` or a reason such as `off` / `unsupported` |
| `nfc.start(on_tag=read, on_error=failed)` | Starts foreground reading; tag results are JSON strings |
| `nfc.stop()` | Stops reading, cancels pending work and forgets callbacks |
| `nfc.write(text=..., on_result=written)` | Arms one text-record write on the next tag contact |
| `nfc.write(url=..., on_result=written)` | Arms one URI-record write; choose text **or** URL |
| `nfc.cancel_write()` | Cancels a pending attempt, not bytes already written |
| `nfc.settings()` | Opens Android NFC settings; the person controls the radio |

All callbacks take `(ok, value)` and return on the Android UI thread. Read
results always contain `id`, `type`, `text`, `url`, `records`, `writable`,
`size`, `used` and `tech`. Use `json_get()` to read them.

Start with the [complete reader, writer snippets and recovery table](guides/nfc.md).
For a runnable app with all controls, [download NFC Tags](downloads/nfc/nfc-tags.py).
Copy it to an ApkPy project's `writehere.py`, run it with the development
library, then use `apkpy build` to generate the Android project.

## NFC permission and lifecycle

The compiler emits `android.permission.NFC` and optional
`android.hardware.nfc` only when NFC is used. NFC is a normal manifest
permission, not a runtime permission prompt. A phone without NFC can still
install the app and receive `unsupported`.

Reading pauses with the Activity and resumes after a prior `start()`.
Leaving the screen cancels pending writes. An Activity recreation requires a
new reader session; the example starts it in `on_resume`. Background jobs may
stop/cancel existing sessions but cannot start a reader or arm a write.

## NFC Previewer

A panel inside the phone frame follows the light/dark theme. Six tag profiles
cover text, URL, empty/formatable, read-only, small-capacity and unknown
technology. A separate control simulates losing a tag. Writes update simulated
contents, so a later tap reads the new value. This is explicitly **NO RADIO**.

## NFC safety and limits

- A write replaces all existing NDEF records with one text or URL record.
- Each armed write is one attempt, including a failed attempt. Retry explicitly.
- Tag IDs are not secure authentication credentials. Validate tag text/URLs
  before acting on them; do not open arbitrary links automatically.
- Writes are not transactions. Verify important data afterwards.
- A freshly formatted tag needs a new contact for independent NDEF read-back
  and fresh capacity; the immediate result is the acknowledged message.
- No HCE/card emulation, bank-card protocol, raw APDU, MIFARE Classic
  authentication, Beam, closed-app launch or screen-off reading is included.

## Contacts API

| Call | Behavior |
| --- | --- |
| `contacts.pick(kind="phone", on_result=picked)` | Select one phone number; use `kind="email"` for an email |
| `contacts.list(query="", limit=50, offset=0, on_result=loaded)` | Search display names and return a JSON array with a bounded page |
| `contacts.get(id, on_result=loaded)` | Read one contact by numeric id or lookup URI |
| `contacts.create(name="", phone="", email="", on_result=returned)` | Open Android's editor with suggested fields; the user decides whether to save |
| `contacts.edit(id, on_result=returned)` | Open the chosen contact in the system editor |
| `contacts.settings(on_result=opened)` | Open the app's settings for user-controlled permissions |

Callbacks take `(ok, value)`. Picker/get results are JSON strings with `id`,
`uri`, `name`, `phone`, `email`, `phones` and `emails`; list returns an array of
that shape. Cancellation, denied access, unavailable editors and stale contact
references have explicit reason strings. Reads run off the Android UI thread.

**Editor return is not save confirmation.** A successful create/edit callback
means the editor returned, with `status`, `result_code` and `uri`. Some Android
editors return `cancelled` even after saving. Pick or reload the contact to
verify changes; do not display “Saved” based only on this callback.

### Permission boundaries

| Operation | Manifest/runtime access |
| --- | --- |
| NFC | Normal `NFC` permission and optional hardware; no runtime grant dialog |
| Pick one phone/email | No address-book permission; access delegated to the selected detail |
| List/get contacts | `READ_CONTACTS` declared automatically and requested when called |
| Create/edit contacts | No `WRITE_CONTACTS`; native editor owns the save/cancel decision |
| Unused feature | No helper or feature-specific permission is emitted |

There is no direct delete API, bulk write, contact observer, photo/group access
or automatic synchronization. The native editor may save to a synchronized
account if the user chooses one. A contact id is not a stable authentication
identity. Use only the details needed for the action the person requested.

The Contacts Previewer uses a themed **CONTACTS · SIMULATED** panel with
fictional data, picker/editor flows and permission outcomes. It never accesses
the desktop address book; its data resets when the process exits. Android
provider, account and OEM-editor behavior still require a device test.

### Complete apps and API examples

- [NFC Tags guide](guides/nfc.md) and [full app source](downloads/nfc/nfc-tags.py).
- [Contacts guide](guides/contacts.md): complete minimal picker, all signatures,
  search, pagination, editor results, lifecycle, reasons and privacy.
- [People Desk app source](downloads/contacts/people-desk.py): phone/email
  selection, search, load details, creation, editing and permission settings.

These are application programs, not library engine source. Run them and use `apkpy build` to generate the Android project.

## Your own Java

ApkPy translates a documented subset of Python, and until now the answer to
anything outside it was to wait. Editing the generated project in Android
Studio was never an answer: `apkpy build` rewrites it.

`native` declares the gap instead of hiding it -- a Java block with a name,
arguments, and the answer the Previewer gives while the phone runs the Java:

```python
battery = native.java(
    "batteryLevel",
    imports=["android.os.BatteryManager", "android.content.Context"],
    code="""
        BatteryManager bm = (BatteryManager)
                context.getSystemService(Context.BATTERY_SERVICE);
        return String.valueOf(bm.getIntProperty(
                BatteryManager.BATTERY_PROPERTY_CAPACITY));
    """,
    preview=lambda: "87",
)

reading.set_value("Battery: " + battery() + "%")
```

`native.java_async()` covers the Android APIs that answer later: the block gets
a `done` it may call from any thread, and ApkPy moves the answer to the UI
thread before your callback runs. `native.gradle()`, `native.manifest()` and
`native.keep()` add the dependency, the manifest entry and the R8 rule that
usually come with it.

`preview=` is required. Without it a block would work on the phone and do
nothing on the desktop, which is the divergence 1.6.0 and 1.8.0 were about.
Inside a block, keeping the two halves in step is the app author's promise,
not ApkPy's -- and that is said plainly in the
[guide](guides/native.md).

## Verification

### NFC

The development run on 12 September 2026 included:

- 26 focused NFC tests, including 95 Python/generated-Java decoder comparisons.
- 1066 feature-suite tests, 258 transpiler tests and 35 general tests passing.
- `apkpy build`, a real Gradle debug build and APK inspection for absence of Python.
- Previewer light/dark visual checks and simulated read/write/error/cancel flows.
- Phone installation, settings navigation, off/on recovery, reader stop/start
  and rejection of a write without an active reader. NFC was restored on.

No physical tag was available during those directly observed device checks.
The maintainer confirmed on 13 September 2026 that their NFC test worked, but did not
specify a tag model or individual read/write scenarios. This is a user report,
not a full hardware compatibility claim. Physical formatting, capacity,
read-only and interrupted-write behavior still need repeatable tag tests.

The work also fixed nested generated NFC callback scope, boolean callback
forwarding and UTF-16 parity, and made normal NDEF read-back bypass cached
pre-write data. These are development changes, not claims about a released
1.9.0 package.

### Your own Java

- 29 focused tests: the generated method and its doc comment, the UI-thread
  wrapper, imports added once each, the manifest and build files, every refusal
  (`U2035`), and the Previewer half answering through `preview=`.
- An app with two blocks -- the battery level and the vibrator -- was built with
  Gradle: `BUILD SUCCESSFUL`, with the permission in the manifest and the keep
  rule in `proguard-rules.pro`. The first build failed on `javac` because the
  callback was written with a `String` where the boolean goes; that is fixed and
  covered by a test.
- Not verified: no block was run on a physical device in this work, and ApkPy
  cannot check that a block's Java and its `preview=` agree.

### Contacts

The development integration passed 19 focused tests, a full run of 1085
feature tests, 258 transpiler tests and 35 general tests. People Desk compiled
through a real Gradle build; its APK was checked for Python source/runtime.
On the connected phone, opening and cancelling the native phone picker were
checked. No real address-book listing or contact modification was performed.

Creation/save, editing and Activity recreation still need end-to-end device
checks. The simulator picker/callback was exercised; its latest layout
refinement has not had a final visual pass. These limits are not represented
as failures, nor as already-verified hardware behavior.

Related: [API overview](api-reference.md), [Device reference](reference/device.md),
[Previewer versus Android](preview-android.md), [Troubleshooting](troubleshooting.md).

### Documentation validation — 14 September 2026

The 45 focused NFC/Contacts tests were rerun successfully, including all 95
Java/Python NFC decoder comparisons. Nine complete or composed documentation
programs transpiled, including both downloadable apps and the guide snippets.
Download copies match the corresponding example source. The local site passed
`mkdocs build --strict`. No package, release or site was published.
