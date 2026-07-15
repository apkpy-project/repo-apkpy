# Troubleshooting

## Start with the doctor

~~~ powershell
apkpy doctor
~~~

This checks the JDK, Android SDK and build requirements before a long Gradle operation.

## The Previewer works but Android differs

1. Run a new <code>apkpy build</code>; an older ZIP/project will not contain generator fixes.
2. Extract the new ZIP into a clean directory.
3. Open that new directory in Android Studio.
4. Let Gradle finish synchronizing.
5. Uninstall the old test app if application state may be stale.
6. Compare the generated project only after confirming it came from the current <code>writehere.py</code>.

Generated Java/XML files are build outputs. Fix application behavior in Python/CSS and regenerate.

## A Material component crashes on open

The generated application must use an ApkPy-generated Material-compatible theme. Do not replace it with a legacy <code>Theme.AppCompat</code> theme.

If the project was manually modified, regenerate it. A MaterialCardView, MaterialToolbar or BottomNavigationView can fail during layout inflation when its Activity uses an incompatible theme.

## Content is hidden behind bottom navigation

Regenerate with the current ApkPy version. Current builds reserve space for bottom navigation. Avoid manual layout changes that move screen content outside the generated root wrapper.

## A long screen is clipped

Use:

~~~ python
screen = Screen(id="screen", scroll=True)
~~~

Do not assign an unnecessary fixed height to a list inside a scrolling screen. Let content size naturally unless the list needs an intentional independent scroll area.

## An async screen stays in loading

Hide the loading state at the first line of every success/error callback:

~~~ python
def loaded(success, response):
    loading.hide()
    if success:
        content.show()
    else:
        failed.show()
~~~

Also handle empty successful responses separately from failed responses.

## Storage cannot decrypt an old/copy value

Encrypted values are device-bound. Data encrypted by Android Keystore on one installation is not intended to decrypt on another device. Treat portable data export as a separate application feature.

## OAuth returns to the wrong place

- Register <code>apkpy://auth</code> for Android.
- Register the Previewer loopback callback shown by the flow.
- Confirm the client ID belongs to the same provider configuration.
- Never place a provider client secret in the APK.

## Cloudflare build fails

Run the exact strict build locally:

~~~ powershell
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
~~~

Then confirm Cloudflare uses:

- root directory: empty;
- build output directory: <code>site</code>;
- production branch: <code>main</code>.

See [Cloudflare Pages](cloudflare-pages.md).
