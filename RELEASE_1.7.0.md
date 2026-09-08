# ApkPy 1.7.0 — Device features and actionable notifications

Write native Android apps in the supported Python subset. The generated APK
still contains Java/XML, not a Python runtime.

## New

- **Notifications:** channels and importance, icons, big text/pictures/inbox,
  up to three actions, tap/dismiss callbacks, grouping and progress.
  `notifications` adds permission controls and cancellation. The existing
  `notify(title, message, id)` form remains compatible.
- **Previewer drawer:** persistent rounded cards inside the device window,
  fixed header, readable light/dark themes, full-area action buttons, wrapped
  labels, picture/inbox expansion and permission/empty states. A temporary
  heads-up expires without removing its card. Android retains its own system UI.
- **Sensors:** accelerometer, gyroscope and pressure streams join shake,
  compass, steps, light and proximity. Availability and lifecycle are explicit.
- **Wallpapers:** home, lock or both, with an image preview and mandatory
  confirmation. The Previewer simulates the result without changing the desktop.
- **Regular expressions:** `re.match`, `re.search`, `re.findall` and `re.sub`
  in a documented portable subset. Constant patterns/flags, native Java output,
  Match captures and clear errors for unsupported forms.

## Fixed

- Supported `set_value()` changes survive Android Activity recreation instead
  of reverting to the original layout text, including empty values and forms.
- Button drawables with different styles no longer overwrite one another
  across screens and make labels invisible.
- The Order Desk demo's View opens details; Later cancels with confirmation
  and intentionally does not schedule a reminder. Job callbacks use `task()`.
- Notification workers use application Context, bundled pictures go into
  Android assets, and cancelled or superseded image loads cannot post stale cards.
- Sensor registration and queued readings respect stop/pause; unrelated sensors
  no longer emit references to a missing step-permission launcher.

## Examples and documentation

- [Full update](https://repo-apkpy.pages.dev/version-1.7.0/)
- [Notification API and complete Order Desk app](https://repo-apkpy.pages.dev/guides/notifications/)
- [Sensors and battery](https://repo-apkpy.pages.dev/guides/sensors/)
- [Static wallpapers](https://repo-apkpy.pages.dev/guides/wallpaper/)
- [Regex subset and limitations](https://repo-apkpy.pages.dev/compatibility/#regular-expressions-170-subset)

Downloads contain application code and assets, not the compiler's source.

## Verification and limits

The release preparation passed **970 feature tests, 35 general tests and
258 transpiler checks**. The dedicated notification Previewer tests cover
real Tk action events, compact/wide layouts, scroll and state handling.
Notification examples generate Java/XML; the native lab and Firebase integration
projects compile with Gradle. The notification lab passed 39 native checkpoints
on Android 16, with separate actual system-drawer View/Later taps.

Sensor motion, wallpaper application and Activity recreation were also checked
on the connected Android 16 phone during development. This is not a device
matrix. Physical pressure was not verified because the phone has no barometer;
remote FCM delivery and hardware process-death restoration were not tested.

Notifications do not guarantee sound, heads-up or lock-screen display; Android
policy and channel settings win. `when` is a timestamp, not scheduling. Regex
calls are synchronous and are not timeout-protected.

## Upgrade

```shell
python -m pip install --upgrade apkpy==1.7.0
```

Regenerate and rebuild existing Android projects to include these fixes. The
minimum Android version remains API 24; generated projects target API 35.
