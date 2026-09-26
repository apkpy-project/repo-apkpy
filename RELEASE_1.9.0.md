# ApkPy 1.9.0 — NFC, scoped contacts and your own Java

Write native Android apps in the supported Python subset. The generated APK
still contains Java/XML, not a Python runtime.

## New

- **NFC tags.** `nfc.status()`, `start(on_tag=..., on_error=...)`, `stop()`,
  `write(text=... / url=...)`, `cancel_write()` and `settings()`. Foreground
  reading with NDEF text and URLs, the tag reported as JSON, and one-shot writes
  to a rewritable tag. The normal `NFC` manifest permission is declared, the
  hardware is marked optional so the Play Store still shows your app to phones
  without it, and there is no runtime permission dialog. The Previewer has a
  themed in-frame simulator with six tag profiles, write failures, cancellation
  and tag loss -- so every branch can be exercised without a tag.
- **Scoped contacts.** `contacts.pick()` chooses one phone number or email with
  **no address-book permission at all**. `list()` and `get()` declare
  `READ_CONTACTS` and ask for it when they are called, never at start-up.
  `create()` and `edit()` open the native editor instead of writing to the
  provider: there is no `WRITE_CONTACTS`, no direct insert or update, and no
  delete API. A successful editor callback means the editor returned, not that
  a contact was saved. The Previewer address book is fictional and
  process-local; it never reads your desktop contacts.
- **Your own Java.** `native.java()` and `native.java_async()` declare a Java
  block with the arguments it takes, the `imports=` it needs and the `preview=`
  that answers on the desktop. A block becomes a private method of the screen's
  Activity; an async block answers `(ok, value)` through `done` from any thread
  and ApkPy moves it to the UI thread. `native.gradle()`, `native.manifest()`
  and `native.keep()` add the Gradle dependency, the manifest entry and the R8
  keep rule that usually come with an SDK.

## Upgrading

Nothing in 1.8.0 changes behaviour. The three additions are new names; an app
that does not use them generates exactly what it generated before -- no
permission, no helper Java, no `<uses-feature>` and no extra dependency.

`preview=` is required on every native block. Without it a block would work on
the phone and do nothing in the Previewer, which is the divergence 1.6.0 and
1.8.0 were about; the build refuses it with `U2035`.

## Verified in this release

- 1,114 feature tests, 35 general tests and 258 transpiler checks passed.
- NFC: 95 parity cases run the generated Java NDEF decoder and the Previewer's
  Python decoder over the same bytes and compare the result.
- Your own Java: 29 focused tests, and an app with two blocks (battery level and
  vibrator) built with Gradle -- `BUILD SUCCESSFUL`, with the declared
  permission in the manifest and the keep rule in `proguard-rules.pro`.
- 99 example apps and documented snippets were transpiled before and after the
  change; nothing that built stopped building.
- MkDocs strict build, and every documented verb checked against the code.

## Not verified

- **NFC on a phone:** *(updated 2026-09-20)* direct checks covered settings,
  turning the radio off and on, and the reader controls. The maintainer then
  reported reading one NDEF tag and writing to a second one on a physical
  phone. That is one person, one handset and two tags -- enough to say a read
  and a write happened, not enough to call NFC certified across tag types,
  chipsets and manufacturers.
- **Contacts on a phone:** the recorded check opened and cancelled the picker.
  Native editor saving, provider behaviour, accounts, OEM editors and rotation
  still need an end-to-end device test.
- **Native blocks on a phone:** *(updated 2026-09-20)* the example was
  installed on a Xiaomi 25069PTEBG running Android 16 and both blocks
  answered: the synchronous one read **92%**, matching `dumpsys battery`,
  and the asynchronous one reported back through `done` on the UI thread.
  For a block you write yourself the limit is unchanged: `javac` proves a
  block compiles; it does not
  prove the Android API inside it answers what you expect. ApkPy also cannot
  check that a block's Java and its `preview=` agree -- inside a block, that
  promise is the app author's.
- One device, one manufacturer, for everything above.

Full notes: [1.9.0](docs/version-1.9.0.md) · [NFC guide](docs/guides/nfc.md) ·
[contacts guide](docs/guides/contacts.md) ·
[your own Java](docs/guides/native.md) ·
[compatibility](docs/compatibility.md)
