# Public API

This is the supported surface exported by <code>apkpy_lib</code>. Import individual names for clarity:

~~~ python
from apkpy_lib import Screen, Theme, button, label, run
~~~

## App structure

| API | Purpose |
| --- | --- |
| <code>Screen(id, background_image=None, scroll=False)</code> | Defines an Android screen/Activity |
| <code>run(start_screen=None, theme=None)</code> | Starts the Previewer and defines the app entry |
| <code>Theme(...)</code> | Supplies global design tokens and component defaults |
| <code>device(name)</code> | Selects a Previewer device preset or responsive mode |
| <code>declare_permissions(perms)</code> | Adds Android manifest permissions |

<code>Screen</code> methods:

| Method | Purpose |
| --- | --- |
| <code>get_param(key, default="")</code> | Reads a value passed during navigation |
| <code>on_click_navigate(button, to, data=None)</code> | Connects an existing button to a screen |

## Components

| API | Important arguments |
| --- | --- |
| <code>label</code> | <code>text</code>, <code>id</code>, <code>variant</code>, <code>screen</code>, <code>parent</code> |
| <code>button</code> | <code>text</code>, <code>command</code>, <code>variant</code>, <code>icon</code> |
| <code>inputs</code> / <code>input_field</code> | <code>placeholder</code>, <code>type</code>, <code>on_change</code> |
| <code>image</code> | local path or HTTPS URL in <code>src</code> |
| <code>video</code> | Media3 video with poster, controls, callbacks, seek, speed and mute |
| <code>container</code> | composable parent surface |
| <code>card</code> | title, subtitle, image, content, actions and variant |
| <code>card_action</code> | detached action for semantic cards |
| <code>list_view</code> | items, click callback and optional rich rows |
| <code>virtual_collection</code> | virtualized list/grid, reusable template, recycled Android ViewHolders |
| <code>rich_text</code> | native inline spans with emphasis, colour, size, code and links |
| <code>markdown</code> | native structured text without a WebView |
| <code>tree_view</code> | expandable hierarchy backed by visible recycled rows |
| <code>carousel</code> | horizontal rich-item shelf |
| <code>grid</code> | rich-item grid with <code>cols</code> |
| <code>spinner</code> | circular loading indicator |
| <code>skeleton</code> | animated content placeholder |
| <code>empty_state</code> | empty result with optional action |
| <code>error_state</code> | error result with optional retry |

Common component methods:

| Method | Purpose |
| --- | --- |
| <code>get_value()</code> | Reads the current input/value |
| <code>set_value(value)</code> | Updates text, image or input state where supported |
| <code>show()</code> / <code>hide()</code> | Controls visibility |
| <code>set_items(items, ...)</code> | Replaces list/carousel/grid content |

## Reactive state and lifecycle

| API | Purpose |
| --- | --- |
| <code>state(initial, id=None)</code> | Creates an observable value shared by Previewer and Android |
| <code>ReactiveState.bind(component, template="{value}")</code> | Updates a component value automatically |
| <code>ReactiveState.bind_visibility(component, when=True)</code> | Connects component visibility to a boolean state |
| <code>lifecycle(screen, on_mount=None, on_resume=None, on_pause=None, on_destroy=None)</code> | Scopes work to one screen lifecycle |

State objects also expose <code>get</code>, <code>set</code>, <code>increment</code>,
<code>decrement</code> and <code>toggle</code>.

## Native documents

| API | Signature and model |
| --- | --- |
| <code>rich_text(spans, id=None, screen=None, parent=None, selectable=True)</code> | Span keys: <code>text</code>, <code>bold</code>, <code>italic</code>, <code>underline</code>, <code>strike</code>, <code>code</code>, <code>color</code>, <code>size</code>, <code>link</code> |
| <code>markdown(source, id=None, screen=None, parent=None, selectable=True)</code> | Headings, emphasis, links, code, quotes, lists, checkboxes and dividers |
| <code>tree_view(nodes, id=None, screen=None, parent=None, expand_depth=1, row_height=58)</code> | Node keys: <code>title</code>, <code>subtitle</code>, <code>key</code>, <code>expanded</code>, recursive <code>children</code> |

Android uses `SpannableStringBuilder` for text and a `RecyclerView` containing
only visible tree rows. The helper classes are generated only when these APIs
are present. See [Native rich content](rich-content.md) for complete examples,
data-model notes and Previewer/Android behavior.

## Layout

| API | Purpose |
| --- | --- |
| <code>row(*children)</code> | Describes a horizontal arrangement |
| <code>column(*children)</code> | Describes a vertical arrangement |
| <code>responsive(mobile, tablet=None, landscape=None, breakpoint=600, ...)</code> | Switches arrangements by viewport |

## Navigation and screen chrome

| API | Purpose |
| --- | --- |
| <code>on_click_navigate(screen, data=None)</code> | Navigates from a callback |
| <code>bottom_nav(screens, labels=None, icons=None)</code> | Adds top-level bottom navigation |
| <code>app_bar(...)</code> | Adds a fixed Material toolbar |
| <code>sliver_app_bar(...)</code> | Adds a collapsible image toolbar |
| <code>action(icon, ...)</code> | Creates an app-bar icon action |
| <code>mini_player(open=None)</code> | Adds the persistent audio mini-player |

## Overlays and feedback

| API | Purpose |
| --- | --- |
| <code>bottom_sheet</code> | Selectable Material bottom sheet |
| <code>modal</code> | Confirm/cancel modal |
| <code>menu</code> / <code>popup_menu</code> | Anchored compact menu |
| <code>context_menu</code> | Right-click/long-press menu |
| <code>tooltip</code> | Accessible help attached to a component |
| <code>date_picker</code> / <code>time_picker</code> | Native date/time selection |
| <code>snackbar</code> | Transient message with optional action |
| <code>toast</code> | Brief platform message |
| <code>alert</code> / <code>confirm</code> | Native informational/confirmation dialogs |

Overlay definitions returned by sheets, modals, menus and pickers expose <code>open()</code> and <code>close()</code>.

## Data and security

| Object/helper | Methods |
| --- | --- |
| <code>storage</code> | <code>set</code>, <code>get</code>, <code>delete</code>, <code>clear</code>, <code>keys</code> |
| <code>crypto</code> | <code>hash_password</code>, <code>verify_password</code>, <code>encrypt</code>, <code>decrypt</code> |
| <code>db</code> | <code>execute</code>, <code>query</code>, <code>last_insert_id</code>, <code>begin</code>, <code>commit</code>, <code>rollback</code> |
| <code>https</code> | <code>get</code>, <code>post</code>, <code>put</code>, <code>patch</code>, <code>delete</code> |
| <code>json_get(json_string, path)</code> | Reads a safe dotted JSON path |
| <code>random</code> | <code>randint</code>, <code>choice</code>, <code>random</code> |
| <code>datetime</code> | <code>now</code>, <code>date</code>, <code>time</code>, and numeric date/time parts |

## Media, files and identity

| Object/helper | Methods |
| --- | --- |
| <code>audio</code> | playback, background playback, seek, queue, controls, favourites and playlists |
| <code>uploads</code> | streaming multipart file, image, audio and video uploads with progress/cancel |
| <code>websocket</code> | persistent WS/WSS connections, send queue, reconnect and close |
| <code>files</code> | <code>download</code>, <code>path</code>, <code>exists</code>, <code>delete</code> |
| <code>auth</code> | <code>login</code>, <code>user</code>, <code>token</code>, <code>is_logged_in</code>, <code>logout</code> |

Audio methods:

<code>play</code>, <code>play_background</code>, <code>pause</code>, <code>resume</code>, <code>stop</code>, <code>seek</code>, <code>play_playlist</code>, <code>next</code>, <code>previous</code>, <code>shuffle</code>, <code>repeat</code>, <code>now_playing</code>, <code>controls</code>, <code>is_liked</code>, <code>toggle_like</code>, <code>like_button</code>, <code>liked_list</code>, <code>add_to_playlist</code>, <code>play_saved_playlist</code>, <code>playlists_list</code>, <code>edit_playlist</code>, <code>playlist_editor</code>, <code>remove_from_playlist</code> and <code>delete_playlist</code>.

On Android, background playback is owned by a generated foreground service and
native `MediaSession`. It supplies notification and lock-screen metadata and
transport actions, audio-focus handling, buffering state and guarded player
polling. This API currently describes normal source playback and explicit
offline files; it does not promise automatic audio caching, adaptive quality or
gapless transitions.

## Device integrations

| Object/API | Purpose |
| --- | --- |
| <code>permissions</code> | Runtime Android permission requests |
| <code>notify</code> | System notifications |
| <code>share</code> | Native share sheet |
| <code>clipboard</code> | System clipboard |
| <code>camera</code> | Native camera capture |
| <code>gallery</code> | Native media picker |
| <code>location</code> | Current position and city |
| <code>map_view</code> | OpenStreetMap tiles, markers, route, user layer and follow controls |
| <code>routes</code> | cancellable driving, walking or cycling route calculation |
| <code>push</code> | FCM listener, device token, topic subscription and Preview simulation |
| <code>service</code> | Periodic and one-shot background work |
| <code>apps</code> | Installed-app listing, permissions, extraction and hashing |

For behavior and security notes, use the topic guides rather than relying on this compact index alone.

The full 1.2.0 examples, callback signatures and Previewer/Android differences
are documented in the [Version 1.2.0 release guide](version-1.2.0.md).
