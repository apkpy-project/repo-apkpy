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
