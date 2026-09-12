# Build and release

## Application identity

Create the configuration file:

~~~ powershell
apkpy init
~~~

Example <code>apkpy.toml</code>:

~~~ toml
[app]
name = "My ApkPy App"
application_id = "com.example.myapkpyapp"
version_name = "1.0.0"
version_code = 1
icon = "icon.png"
~~~

| Field | Purpose |
| --- | --- |
| <code>name</code> | Label displayed below the app icon |
| <code>application_id</code> | Permanent unique Android/Play Store identifier |
| <code>version_name</code> | Human-readable release version |
| <code>version_code</code> | Integer increased for every store upload |
| <code>icon</code> | Optional square source image for launcher assets |

Do not change <code>application_id</code> after publishing the application.

## Development builds

Generate an Android Studio project:

~~~ powershell
apkpy build
~~~

Compile a debug APK directly:

~~~ powershell
apkpy run
~~~

Install helpers:

~~~ powershell
apkpy run --qr
apkpy run --usb
~~~

## Signed releases

~~~ powershell
apkpy release
apkpy release --aab
~~~

The APK is useful for direct signed distribution. The AAB is the standard upload format for Google Play.

On the first release ApkPy creates a signing keystore under the user's ApkPy configuration directory. Future updates must use the same signing identity.

!!! danger "Back up the signing key"
    Losing the keystore can prevent you from publishing updates under the same application identity. Keep an encrypted backup outside the development computer. Never commit the keystore or its password.

## Your release is shrunk, not renamed

`apkpy release` runs **R8**, Android's own shrinker. It walks the app, works out
which library code can actually be reached, and drops the rest. A screen using
two Material widgets was shipping the whole of Material.

Measured on the same app, both signed release builds:

| | APK |
| --- | --- |
| before | 4,496 KB |
| after | **1,536 KB** |

An app pulling in Firebase, WorkManager, media3 and RecyclerView still comes to
**2,085 KB**.

You do not write anything different. This is a build setting, and your Python,
your API and your screens are untouched.

### Names stay readable, on purpose

R8 normally also *renames* everything -- `Screen_homeActivity` becomes `a.b.c`.
ApkPy turns that half off, with `-dontobfuscate` in the generated
`proguard-rules.pro`.

Renaming would mean two things you would not enjoy. `crash.last()` would hand
your app a stack trace made of `a.a.b`, and every published version would need
its mapping file kept forever to read its own crash reports. The size saving is
in the shrinking, not in the renaming, so ApkPy keeps the saving and skips the
cost.

Line numbers are kept too, so a stack trace still points at a real line.

If you want obfuscation -- normally as a mild deterrent against someone reading
your app -- remove that line from `proguard-rules.pro` in the generated project
and keep the `mapping.txt` that each build produces.

### What it improves, and what it does not

Measured on a phone, cold starts, same app with and without:

| | without R8 | with R8 |
| --- | --- | --- |
| APK on disk | 4,496 KB | **1,536 KB** |
| code resident in RAM | 14,756 KB | **8,964 KB** |
| total memory (PSS) | 119,169 KB | **113,153 KB** |
| cold start | 312 / 246 / 233 ms | 270 / 223 / 231 ms |

So: **storage and download shrink a lot**, and **memory drops by about 6 MB**,
because the code your app never calls is no longer mapped into it.

**Start-up barely moves.** The difference above is inside the noise of three
runs, and you should not expect users to feel it. Code that is never called is
also never loaded, so removing it saves the space it occupied rather than time
that was being spent on it.

### The cost

Release builds get slower, because R8 analyses the whole program. On the test
machine a small app went from 49 s to about 1 m 50 s, and one with Firebase,
WorkManager and media3 took 2 m 45 s.

`apkpy run` is a development build and does **not** shrink, so your everyday
loop is unaffected.

### Test a release build before you publish

Shrinking removes code it believes nothing reaches. A library that finds its
classes by name at run time can defeat that analysis, and the result compiles
cleanly and fails only when that screen opens.

ApkPy's own libraries were checked on a phone -- WorkManager ran a job to
completion, media3 decoded audio, Firebase registered for push, RecyclerView
drew a list, and the camera, gallery and wallpaper flows all worked. Even so,
install your signed release on a real device and walk through the features that
touch the network, the camera, notifications and background jobs before you send
it to anybody.

## Before shipping

- Run <code>apkpy doctor</code>.
- Test every screen in the Previewer and on Android.
- Test permissions on both a fresh install and a previously denied install.
- Verify offline/error/loading states.
- Check background audio and notification controls.
- Confirm the application ID and version code.
- Search the generated project for placeholder secrets or test endpoints.
- Build the exact release artifact that will be distributed.

Android may warn when installing an APK outside an app store. Signing proves update identity and integrity; it does not remove normal sideloading warnings.
