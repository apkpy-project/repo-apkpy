# Native Android features

Task guides: [Firebase push](guides/push-firebase.md),
[streaming uploads](guides/uploads.md) and
[maps with continuous location](guides/maps-tracking.md).

## Permissions

Declare permissions before running the app:

~~~ python
declare_permissions([
    "android.permission.CAMERA",
    "android.permission.ACCESS_FINE_LOCATION",
])
~~~

Request dangerous permissions at runtime:

~~~ python
def permission_result(granted):
    if granted:
        toast("Permission granted")
    else:
        toast("Permission denied")

permissions.request(
    "android.permission.CAMERA",
    on_response=permission_result,
)
~~~

Only request permissions when a user action needs them, and explain the reason in the interface.

## Notifications and sharing

~~~ python
notify("Download complete", "Midnight Drive is available offline")
share("Listen to Midnight Drive", title="Share track")
clipboard.copy("https://example.com/track/42")
~~~

<code>notify</code> creates a system notification. <code>toast</code> is for brief in-app feedback. <code>snackbar</code> is useful when the message belongs to the current screen and may include an action.

## Camera and gallery

~~~ python
def image_selected(success, path):
    if success:
        avatar.set_value(path)

camera.capture(on_result=image_selected)
gallery.pick(on_result=image_selected)
~~~

The Previewer uses a file picker to simulate the flow. Android opens the native camera or content picker.

<code>camera</code> and <code>gallery</code> are image-only. For documents, archives, audio or anything else use <code>files.pick</code>, or <code>upload_button</code> to pick and send in one step:

~~~ python
def file_chosen(success, path, name, size, mime):
    if success:
        chosen.set_value(name + " - " + size + " bytes")

files.pick(on_result=file_chosen, types=["pdf", "zip"])
~~~

See [Streaming multipart uploads](guides/uploads.md).

## Location

~~~ python
def location_result(success, latitude, longitude, city):
    if success:
        location_label.set_value(city + " · " + latitude + ", " + longitude)
    else:
        location_label.set_value("Location unavailable")

location.get_current(on_result=location_result)
~~~

Declare and request the appropriate location permission before reading the device position.

## Talking to an API

`https` sends the request off the UI thread and hands the answer back on it,
so nothing you write here can freeze the screen. The `INTERNET` permission is
added to the manifest for you.

~~~ python
def answered(success, response):
    if success:
        reply.set_value(json_get(response, "content.0.text"))
    else:
        reply.set_value("That did not go through. " + response)


def ask():
    https.post(
        "https://api.example.com/v1/messages",
        data={
            "model": "some-model",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": question.get_value()}],
        },
        headers={"x-api-key": storage.get("api_key", "")},
        timeout=120,
        on_response=answered,
    )
~~~

Three things worth knowing:

**A dict is JSON, and keeps its types.** `max_tokens` arrives as the number
`1024`, not the string `"1024"` — an API that validates its input rejects the
second. Nested lists and objects survive too. And because the serialiser does
the writing, a quote or a newline in what the user typed is escaped properly
instead of breaking the body, which is what string concatenation would do.

**`timeout=` is in seconds, and the default is 60.** Most endpoints answer in
under a second, but anything that thinks before it replies does not. Raise it
rather than discovering the ceiling in the field.

**The callback needs a name.** `on_response=answered` compiles;
`on_response=lambda ok, body: ...` does not. The callback also cannot see
variables from the function that started the request — ApkPy reads your module
rather than running it, so a value set at call time does not exist for the
generated code. Hand it over through `storage` instead:

~~~ python
def ask():
    storage.set("pending_row", row_id)
    https.post(URL, data=body, on_response=answered)


def answered(success, response):
    thread.stream_item(storage.get("pending_row", ""), "message",
                       json_get(response, "content.0.text"))
~~~

### About API keys

Anything inside an APK is readable by whoever installs it. Unzipping one takes
about thirty seconds, and no amount of obfuscation changes that — the app has
to be able to read the key to use it, so anyone holding the app can too.

There are two honest shapes:

- **The user brings their own key**, pasted into a settings screen and kept in
  `storage` (which is encrypted at rest). Right for a personal app, a developer
  tool, or anything where the user already has an account.
- **Your server holds the key** and the app talks to your server. Necessary the
  moment the app speaks on *your* account, because that is the only way the key
  never ships.

## Background work

~~~ python
def sync_library():
    https.get(API_URL, on_response=save_library)

service.every(
    run=sync_library,
    minutes=15,
    id="library_sync",
    only_on_wifi=True,
    only_when_charging=True,
)

service.once(run=sync_library, after_minutes=5, id="initial_sync")
service.cancel(id="library_sync")
~~~

Android compiles scheduled work to WorkManager. The operating system controls the exact execution time, particularly for periodic jobs.

`service.every` is a *schedule*. When you instead need a *queue* — work that is
handed over once and must survive the app closing, the network dropping or a
reboot — declare a persistent job:

~~~ python
outbox = background_job(
    "outbox",
    run=deliver_message,
    requires_network=True,
    retry="exponential",
    unique=True,
)

outbox.enqueue({"text": message_input.get_value()})
outbox.observe(on_change=queue_changed, screen=home)
~~~

Read [Background jobs and offline queue](background-jobs.md) for constraints,
retries, unique-work policies, cancellation and observable progress.

## App inspection

~~~ python
apps.list(on_result=show_apps)
apps.permissions("com.example.app", on_result=show_permissions)
apps.extract("com.example.app", on_result=extracted)
apps.hash("com.example.app", on_result=hashed)
~~~

These APIs inspect packages available to the Android device and simulate results where possible in the Previewer.

!!! warning "Google Play package visibility"
    Broad package visibility, especially <code>QUERY_ALL_PACKAGES</code>, is restricted by Google Play policy. Use it only when the app's core purpose qualifies, and prefer targeted package queries where possible.

## Native dialogs

~~~ python
alert("Saved", "Your settings were updated.")

confirm(
    "Delete playlist?",
    "This cannot be undone.",
    on_result=lambda accepted: delete_if_confirmed(accepted),
)
~~~

Use [Overlays and content states](overlays-states.md) for richer Material sheets, modals, menus, pickers and snackbars.
