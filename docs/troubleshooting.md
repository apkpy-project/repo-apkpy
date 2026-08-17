# Troubleshooting

Start with the first failing layer instead of changing several things at once:

| Symptom | Check first |
| --- | --- |
| `ImportError` before the Previewer opens | project filenames and installed ApkPy version |
| Previewer error | the first Python traceback and callback argument types |
| `apkpy build` error | `apkpy doctor` and the smallest reproducible `writehere.py` |
| Gradle error | the first `FAILURE` cause, not the final summary line |
| App closes on Android | the first `FATAL EXCEPTION` in Logcat |
| Platform feature does nothing | permission, configuration file and device capability |

## Start with the doctor

~~~ powershell
apkpy doctor
~~~

This checks the JDK, Android SDK and build requirements before a long Gradle operation.

Also record the versions used for a report:

```powershell
python --version
python -m pip show apkpy
java -version
apkpy doctor
```

## Import fails before the app starts

Do not name an application file after a Python standard-library or ApkPy module.
For example, a local `random.py`, `json.py`, `sqlite3.py` or `websocket.py` can
be imported instead of the real module and create a circular import.

1. Rename the conflicting file.
2. Remove the matching `__pycache__` directory.
3. Run the app again from the project directory.

If the error says that a public name such as `bottom_nav` cannot be imported,
check the installed version and interpreter:

```powershell
python -m pip show apkpy
python -c "import apkpy_lib; print(apkpy_lib.__file__)"
```

Use `python -m pip`, not a bare `pip`, so installation and execution target the
same interpreter.

## The Previewer works but Android differs

1. Run a new <code>apkpy build</code>; an older ZIP/project will not contain generator fixes.
2. Extract the new ZIP into a clean directory.
3. Open that new directory in Android Studio.
4. Let Gradle finish synchronizing.
5. Uninstall the old test app if application state may be stale.
6. Compare the generated project only after confirming it came from the current <code>writehere.py</code>.

Generated Java/XML files are build outputs. Fix application behavior in Python/CSS and regenerate.

If only a platform-owned element differs — notification, permission dialog,
video controls, keyboard, GPS provider — compare behavior rather than forcing
the desktop simulation to copy every system pixel.

## A Material component crashes on open

The generated application must use an ApkPy-generated Material-compatible theme. Do not replace it with a legacy <code>Theme.AppCompat</code> theme.

If the project was manually modified, regenerate it. A MaterialCardView, MaterialToolbar or BottomNavigationView can fail during layout inflation when its Activity uses an incompatible theme.

## Android Studio still shows an old screen

`apkpy build` creates fresh output; it does not update every separately
extracted project on your disk.

- confirm the build time of the generated ZIP;
- extract it to a new directory;
- open that directory, not a previous similarly named project;
- use **Build > Clean Project** only after checking the correct directory;
- reinstall the APK if persisted app data affects the result.

## Content is hidden behind bottom navigation

Regenerate with the current ApkPy version. Current builds reserve space for bottom navigation. Avoid manual layout changes that move screen content outside the generated root wrapper.

## A long screen is clipped

Use:

~~~ python
screen = Screen(id="screen", scroll=True)
~~~

Do not assign an unnecessary fixed height to a list inside a scrolling screen. Let content size naturally unless the list needs an intentional independent scroll area.

For a feed with bottom navigation, give the collection a deliberate height only
when it is the independent scroll surface. Do not nest multiple full-height
scroll containers.

## Text or buttons are clipped

- remove fixed component heights while diagnosing;
- allow a button label to wrap or shorten the copy on narrow screens;
- keep horizontal action rows responsive with `responsive()`;
- test the same screen at phone and tablet widths;
- do not use spaces to align content — use `row`, `column`, padding and gap.

If the Previewer and Android disagree, reduce the screen to one component and
report the ID plus its CSS-like rules. That isolates a renderer mismatch from a
layout interaction.

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

Callback shapes matter. Common contracts are:

| API | Callback |
| --- | --- |
| `https` | `on_response(success, body)` |
| `uploads` progress | `on_progress(percent, bytes_sent, total_bytes)` |
| `uploads` result | `on_result(success, response)` |
| typed `db` success | result value only |
| typed `db` failure | `on_error(message)` |
| route calculation | `on_result(success, route_json, distance, duration, error)` |

Convert numbers before concatenating them with text:

```python
def progress(percent, sent, total):
    status.set_value("Uploading · " + str(percent) + "%")
```

## A feed repeatedly loads the same page

Every `on_end_reached` attempt must eventually call one of:

- `append_items(items, has_more=...)`;
- `set_items(items, has_more=...)`;
- `finish_load(has_more=...)` after an empty or failed request.

Use `has_more=False` when the server has no next page. ApkPy guards duplicate
callbacks while a load is active, but it cannot infer the backend cursor.

## Pull-to-refresh appears to do nothing

`refresh()` starts `on_refresh`; the callback must then replace the
authoritative first page with `set_items(...)` or release the latch with
`finish_load()`. Changing only a status label does not change collection data.

## Data Core reports a schema or migration error

- increase the schema version when a model definition changes;
- provide every consecutive migration step up to the new version;
- do not reuse an index name for a different definition;
- mark destructive operations explicitly;
- keep a copy of production data before testing a destructive upgrade.

A stored schema hash intentionally rejects silent model changes. Fix the model
or migration rather than deleting the database during an upgrade test.

## A database callback never updates the screen

Declare the schema before the first model operation and attach loading to a
screen lifecycle:

```python
db.schema("app", version=1, models=[notes])
lifecycle(home, on_mount=load_notes)
```

Do not expect a return value from asynchronous public CRUD calls. Update the UI
inside `on_result` or `on_error`.

## Storage cannot decrypt an old/copy value

Encrypted values are device-bound. Data encrypted by Android Keystore on one installation is not intended to decrypt on another device. Treat portable data export as a separate application feature.

If an app is reinstalled or its key material is removed, old ciphertext may be
unrecoverable. Store server credentials on the server and design an explicit
export/recovery format for user-owned data.

## OAuth returns to the wrong place

- Register <code>apkpy://auth</code> for Android.
- Register the Previewer loopback callback shown by the flow.
- Confirm the client ID belongs to the same provider configuration.
- Never place a provider client secret in the APK.

## WebSocket reconnect logs repeat

`getaddrinfo failed` means the hostname could not be resolved. A forced remote
close means the server or intermediary closed the socket. Check:

- the URL uses `ws://` or `wss://` and contains a real host;
- the emulator/device has network access;
- the certificate and hostname match for `wss://`;
- authorization headers and subprotocols match the server;
- the endpoint actually supports WebSocket upgrades.

Automatic reconnect uses bounded backoff. Call `websocket.close(id)` when the
screen intentionally leaves the room, or scope cleanup with `lifecycle`.

## Firebase push says it is not initialized

Push on Android needs a Firebase Android app whose package ID exactly matches
the application ID. Place its `google-services.json` beside `writehere.py`
before generation, then create a fresh project.

Do not copy a configuration file from a different package. In the Previewer,
`push.simulate(...)` tests application flow but does not prove FCM delivery.

## Upload reaches 100% and then fails

100% means all request bytes were sent. The server can still reject the
request, return an error, time out while processing or close the connection.
Treat upload progress and server result as separate states:

```python
def finished(success, response):
    if success:
        status.set_value("Upload complete")
    else:
        status.set_value("Upload failed · " + str(response))
```

Verify the endpoint, field name, authorization header and expected multipart
fields. Do not present 100% as success until `on_result` succeeds.

## Video works differently on desktop and Android

Android uses Media3 and the device codec/audio stack. The Previewer uses a
desktop backend. Check that:

- the source URL/file is reachable by the platform being tested;
- the format contains a supported audio track;
- `muted=False` and system volume is audible;
- autoplay restrictions are not being mistaken for a playback failure;
- controls, seek and lifecycle are tested on Android before release.

Use a poster/fallback for network media and handle `on_error` visibly.

## GPS does not move in the Previewer

Desktop Preview has no Android GPS. Pass an explicit `preview_route` to
`location.watch(...)` to simulate movement. Android uses device/emulator
location only after tracking starts and permission is granted.

On the Android emulator, use **Extended controls > Location** to send points or
a route. Moving the physical computer does not move an emulator's virtual GPS.

The route line and the current-location dot are separate: calculating a route
does not fabricate device movement.

## A background feature stops after leaving the app

Android applies platform restrictions to location, media, notifications and
scheduled work. Confirm the required permission, foreground notification,
battery policy and device-specific restrictions. A Previewer daemon or
simulation is not proof that Android will keep the same process alive.

## A release build is much smaller or faster than the benchmark

That can be normal. ApkPy's published framework comparison uses debug artifacts
for equal, inspectable development builds. Release shrinking, R8, signing,
assets and plugins change size and startup. Compare like with like and publish
the build mode with every result.

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

## Reporting a useful bug

Include:

- the smallest `writehere.py` that reproduces the problem;
- component IDs and relevant style rules;
- ApkPy, Python, JDK and Android versions;
- whether it fails in Previewer, generation, Gradle or Android runtime;
- the first traceback or `FATAL EXCEPTION`;
- a screenshot only when the issue is visual.

Do not include API tokens, signing keys, `google-services.json` or private user
data. Start from the repository's bug-report template.
