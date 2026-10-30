"""AGENTS.md -- what an AI coding assistant needs to know to write ApkPy.

No language model knows ApkPy from its training: asked to add a screen, an
assistant writes Kivy, or plain Python that ApkPy cannot translate. So every
project teaches it instead. ``apkpy start``, ``apkpy init`` and
``apkpy examples`` put an ``AGENTS.md`` next to ``writehere.py`` -- the file
coding agents read before they touch a project -- plus a ``CLAUDE.md`` that
points Claude Code at it. ``apkpy agents`` writes or refreshes them in a
project that already exists.

A file the person has edited is never replaced. The first line carries the
hash of what ApkPy wrote; if the text below it no longer matches, the file is
theirs and stays as it is (``apkpy agents --force`` replaces it anyway).

Every rule below is one the build enforces, with the code it stops with, so
the guide can be checked against the compiler (tests/features/
test_agents_guide.py) rather than trusted.
"""

import hashlib
import os
import re

AGENTS_FILE = "AGENTS.md"
CLAUDE_FILE = "CLAUDE.md"
DOCS = "https://repo-apkpy.pages.dev"

# Rule 10 describes the compiler as of 1.11.0: set_value/show/hide/set_items
# reach a component on another screen (pending_views); the other feed
# operations and get_value do not. When they learn it, change the rule here.
_MARKER = re.compile(r"^<!-- apkpy:agents version=(\S+) sha=([0-9a-f]{12}) -->\n")

_BODY = '''# AGENTS.md -- this is an ApkPy app

This project is written with **ApkPy** (`pip install apkpy`, imported as
`apkpy_lib`); this guide was written for apkpy {version}. ApkPy reads
`writehere.py` and translates it into a native Android project -- Java, XML
and Gradle -- that builds an APK. **There is no Python on the phone**: only
the Python listed below is translated, and anything else stops the build with
a coded error instead of running.

It is not Kivy, BeeWare, Flet, Chaquopy or python-for-android. Do not write
their code, do not add a `buildozer.spec`, and do not `pip install` packages
for the app to use at run time.

## Files

- `writehere.py` -- the whole app: screens, components, `style`, callbacks,
  and one `run()` at the end.
- `apkpy.toml` -- app name, `application_id`, version and icon.
- Plain Python modules beside it, imported with `import helpers`: functions,
  classes and constants. Screens, themes and CSS stay in `writehere.py`.
- The generated Android project is output (`~/.apkpy/build/<name>`). Never
  edit it: change `writehere.py` and build again.

## Commands

| Task | Command |
| --- | --- |
| Desktop Previewer | `python writehere.py` |
| Debug APK, left in this folder | `apkpy run` (`--usb` also installs it through adb) |
| Signed APK / Play Store bundle | `apkpy release` / `apkpy release --aab` |
| Android Studio project as a ZIP | `apkpy build` |
| What the app prints on a USB-connected phone, live | `apkpy logs` |
| Check JDK 17-21 and the Android SDK | `apkpy doctor` |
| Example apps | `apkpy examples` |

A change is finished when the Previewer runs it **and** `apkpy build` passes.
The Previewer is Python and runs things the translator refuses.

## The shape of an app

```python
from apkpy_lib import *

home = Screen(id="home")
details = Screen(id="details")

title = label("Hello", id="title", screen=home)
name = inputs("Your name", id="name", screen=home)


def greet():
    value = name.get_value()
    if value == "":
        toast("Type a name first")
        return
    title.set_value(f"Hello, {{value}}")


button("Greet", id="greet", command=greet, screen=home)
button("Details", command=lambda: on_click_navigate(details, data={{"from": "home"}}),
       screen=home)
label("Details", id="details_title", screen=details)

style = """
title {{ font-size: 28px; font-weight: bold; }}
#greet {{ border-radius: 14px; }}
"""

run(start_screen=home, theme=Theme(mode="dark"))
```

## A list that changes, backed by SQLite

```python
from apkpy_lib import *

home = Screen(id="home")
db.execute("CREATE TABLE IF NOT EXISTS habits (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, done_on TEXT)")


def toggle(item):
    # item is the tapped row: every column the query returned
    today = datetime.date()
    db.execute("UPDATE habits SET done_on = CASE WHEN done_on = ? THEN '' ELSE ? END WHERE id = ?",
               [today, today, item["id"]])
    refresh()


habits = virtual_collection([], template={{"title": "{{name}}", "subtitle": "{{status}}"}},
                            on_click=toggle, screen=home)


def refresh():
    rows = db.query("SELECT id, name, CASE WHEN done_on = ? THEN 'Done today' ELSE 'Not yet' END AS status FROM habits ORDER BY id",
                    [datetime.date()])
    habits.set_items(rows)


refresh()
run(start_screen=home)
```

`list_view` works the same way for shorter lists: `set_items(rows,
title="name", subtitle="status")` and its `on_click` receives the row, so
`item["id"]` is there too. `virtual_collection` is for long or rich lists.

## Rules that decide whether it works

Where a rule names a code, breaking it stops the build with that code.
Rules 3 and 10 are the dangerous ones: break them and the app still builds,
then misbehaves without a word.

1. Every component takes `screen=` or `parent=` (`U2001`). Keep the object it
   returns to change it later: `get_value()`, `set_value()`, `show()`,
   `hide()`.
2. A button's action is `command=` -- a function name or a `lambda` -- not
   `on_click=`.
3. `style` is one module-level string in **triple double quotes**
   (`style = """..."""`). A one-line `style = "..."` or `\'\'\'...\'\'\'` is
   ignored without a warning. A selector is an id (`title` or `#title`) or a
   component type (`label`, `button`); the id wins.
4. Text from an input or from storage stays text: `float(price.get_value()) * 2`,
   never `price.get_value() * 2`. Between values not known to be numbers, `+`
   joins text.
5. f-strings take `{{x}}`, `{{x:.2f}}` and `{{x:,.2f}}` only. No `%` formatting and no
   `.format()`.
6. A call to one of your functions passes every parameter, by position or by
   name: default values are not read (`U2037`).
7. A function that builds UI (it calls `label`, `card`, ...) is called on its
   own line at module level -- never from a tap, a callback or another
   function (`U2038`). A module-level `for` over a list written in the file
   (`for page, title in [(home, "Home"), (more, "More")]:`) is unrolled when
   it builds UI, and `command=lambda t=page: on_click_navigate(t)` inside it
   keeps each turn's value, as in Python -- a default that the program
   changes later is refused (`U2039`).
8. A background job (`background_job`, `service.every`, `service.once`) may
   call your functions, `permissions.has()`, `db` and `files.download()` /
   `files.delete()`. Anything that needs a screen stops the build (`J7004`,
   `J7005`): report with `job.progress()` and show it from `job.observe()`.
9. One `run()` call, last.
10. **Another screen's component changes when that screen comes back.**
    Each `Screen` is its own Android Activity. `set_value()`, `show()`,
    `hide()` and `set_items()` on a component of another screen reach it when
    that screen comes to the front. Reading it (`get_value()`) and the other
    list operations (`append_items`, `merge_items`, `update_item`, ...) do
    not: keep the value in `state()` or the database, and change such a list
    from code on its own screen, e.g. `lifecycle(stats, on_resume=refresh)`.
11. **Rows that change while the app runs go in one list**
    (`virtual_collection` or `list_view`), filled with `.set_items(rows)` --
    see "A list that changes" above. Never pre-build a fixed number of hidden
    rows, and never keep components in a list (`rows[i].show()` stops the
    build).

## The Python that is translated

- `if` / `elif` / `else`, `while`, `for`, `break`, `continue`, `return`,
  `pass`; `for ... else` inside a function; `try` / `except` (several, with
  types and `as error`) / `else` / `finally`; `raise ValueError("...")`;
  `assert`.
- Conditions with `==`, `!=`, `<`, `>`, `<=`, `>=`, chained (`0 < x < 10`),
  `in`, `is None`, `isinstance(x, (int, float))`, `and`, `or`, `not`.
- Functions with positional and keyword arguments, defaults, `*args` and
  `**kwargs`; a function inside a function, recursion, `lambda`, `global`.
- Assignment, `a = b = 0`, unpacking (`a, b = parts`), every augmented
  operator; `row["k"] = v`, `items[i] += 1`, `del items[0]`; lists, dicts
  and tuples; indexes and slices with a step; `a if test else b`; list and
  dict comprehensions inside a function.
- `for` over `range()`, a list, a tuple, a dict, text, `split()`,
  `d.items()`, `enumerate()`, `zip()`, `reversed()` and `sorted()`.
- `len`, `int`, `float`, `str`, `bool`, `round`, `list`, `tuple`, `abs`,
  `min`, `max`, `sum`, `sorted`, `any`, `all`, `divmod`, `pow`,
  `chr`, `ord`; `print` writes to Logcat. Text methods, f-strings with format
  specs (`{{x:.2f}}`), `.format()` and `%`; list and dict methods;
  `import math`, `import random`; `import re` with constant patterns.
- `sorted()`, `list.sort()`, `min()` and `max()` with `key=` inside a
  function: a lambda (`key=lambda r: r["price"]`), a function's name
  (`key=len`), `str.lower` or `d.get`; `reverse=` and `default=` too.
- `import json`: `json.loads(text)` and `json.dumps(value)` with `indent=`,
  `sort_keys=`, `ensure_ascii=`, `separators=` and `allow_nan=`;
  `except json.JSONDecodeError`. For a file:
  `json.loads(files.read("data.json"))`.
- Classes: `__init__`, methods, one parent class and `super()`, class
  attributes, `@staticmethod`, `@property`, `__str__`, `__repr__` and
  `__eq__`. Objects are shared as in Python: every name for an object sees
  its changes. `@dataclass` with `field(default=..., default_factory=list)`
  and `__post_init__`. Errors of your own for `raise` and `except`:
  `class TooLong(ValueError): pass`.

These stop the build with `U2033`, which names the line and a form that works:
sets, generators and `yield`, `match`, `nonlocal`, `:=`, `with` and `open()`
(use `files`), `json.load()` and `json.dump()` (use `files` with
`json.loads()` and `json.dumps()`), a comprehension, a `key=` or a
`json` call on a value only known while the app runs at the top of the file,
setting an attribute of a component (use `set_value()`), and, in a class,
more than one parent, `@classmethod` or other special methods,
`@dataclass(frozen=True)` or `order=True`, and fields or methods on an error
class (put the detail in its message).

A list or a dict is a value on the phone, not one object under two names.
Copy on purpose (`l2 = list(l1)`, `row = rows[0].copy()`), change the
original where it lives (`rows[0]["done"] = True`), write a default list as
`tags=None` and make it in the body, and take back what a function changes:
`cart = add(cart, x)`. The forms that would share one list in CPython
(`l2 = l1` then `l2.append(x)`, `def f(tags=[])` that changes `tags`) stop
the build with `U2033`.
`uuid` and Python's `datetime` are not translated: use ApkPy's
`datetime` and its APIs.

Never available on the phone: `requests`, `numpy`, `pandas`, `os`,
`pathlib`, `threading`, `sqlite3` or any other package. Use ApkPy's APIs.

## APIs to reach for

| Need | Use |
| --- | --- |
| Screens and navigation | `Screen(id, scroll=False)`, `on_click_navigate(screen, data=None)`, `back()` (close this screen -- use it for back arrows, not `on_click_navigate(previous)`), `screen.get_param(key, default)`, `bottom_nav(screens, labels=, icons=)`, `app_bar(title, leading=, actions=)` with `action(icon, command=)` |
| Components | `label`, `button(text, command=, variant=)`, `inputs(placeholder, type=)`, `image`, `card`, `container`, `row`, `column`, `list_view`, `virtual_collection`, `pager` and `tab`, `chart`, `chips`, `segmented`, `markdown`, `avatar`, `video` |
| Feedback and overlays | `toast(message)`, `snackbar(message, action=, on_action=)`, `alert(title, message)`, `confirm(title, message, on_result=)`, `modal(...)` and `bottom_sheet(...)` with `.open()` |
| Reactive values | `state(initial)` with `.bind(component, template="{{value}}")` |
| Key-value storage | `storage.set(key, value)`, `storage.get(key, default)` -- encrypted |
| Text files | `files.write(name, text)`, `files.append(name, text)` -> `"ok"`, `"invalid"` or `"failed"`; `text = files.read(name)` (`""` when there is no such file); `files.exists(name)`, `files.delete(name)` -- the app's own folder, no permission |
| Database, plain SQL | `db.execute(sql, params)` and `rows = db.query(sql, params)` -- `?` placeholders; rows are records: `rows[0]["n"]` |
| Database, typed | `db.model`, `db.schema`, `model.insert/find/update/delete(..., on_result=)`, `model.observe(...)` |
| Today's date and time | `datetime.date()` -> `"2026-09-23"`, `datetime.now()` -> `"2026-09-23 21:53:48"`, `datetime.time()`, `datetime.year()`, `datetime.month()`, `datetime.day()` (text) |
| HTTP | `https.get/post(url, data=dict, headers=, on_response=)`; the callback takes `(success, body)`; `json_get(body, "items.0.title")` |
| Background work | `background_job(name, run=function, requires_network=True)`, `service.every(function, minutes)` |
| Later, or again and again | `timer.after(2, function)`, `timer.every(1, function)`, `timer.cancel(function)`, `if timer.running(function):` -- while the screen is on show; never `time.sleep` |
| The connection | `if network.online():`, `network.kind()` -> `"wifi"`, `"mobile"`, `"ethernet"`, `"other"`, `"none"`, `if network.metered():`, `network.on_change(function)` -- no permission to ask for |
| The app lock | `app_lock.after(5)` as the first screen opens (`lifecycle(home, on_mount=opened)`), `app_lock.now()`, `app_lock.off()`, `if app_lock.locked():` -- the phone's own fingerprint, face or screen lock opens it; `"no_lock"` on a phone with none |
| The display | `display.keep_on()`, `display.brightness(0.9)` or `"auto"`, `display.immersive()`, `display.orientation("landscape")` -- this screen's, asked from a function; `Screen(id="player", orientation="landscape")`, `run(start_screen=home, orientation="portrait")` |
| Device | `permissions`, `camera`, `gallery`, `location`, `notify`, `push`, `audio`, `sensors`, `nfc`, `contacts`, `biometrics`, `flashlight`, `clipboard`, `share` |
| Past the app | `haptics.tap()`, `speech.say(text)`, `speech.listen(on_result=)`, `browser.open(url)`, `browser.show(url=, html=)`, `phone.dial(number)`, `phone.sms(number, text)`, `calendar.add_event(title, start)`, `files.save_as(name, text, on_result=)`, `downloads.start(url, on_result=)`, `printing.html(html)`, `recorder.start(on_result=)`, `incoming.links(scheme)`, `incoming.shares("text")` |
| Outside the app | `home_widget.define(title, text, caption=, icon=)` then `home_widget.set(text)`; `quick_tile.define(label, icon=)` then `quick_tile.set(True, subtitle=)`; `ads.setup("test")` then `ads.banner("test")`, `ads.interstitial("test", on_result=)`, `ads.rewarded("test", on_result=)`; `updates.check(on_result=)`, `updates.start("flexible", on_result=)`, `updates.install()`; `health.policy(url)` then `health.ask("steps, sleep", on_result=)`, `health.read("steps", on_result=)` |
| Anything else Android can do | `X = native.use("android.os.X")` and a `@native(preview=...)` function whose body calls it, translated to Java at build time; or `native.java()`, your own Java block. Both need the answer the Previewer gives instead |

## Icons

`icon=`, `icons=` and `action(icon)` take any Material Icons name, as on
fonts.google.com/icons with spaces as underscores (`share`,
`chat_bubble_outline`, `favorite_border`, `cameraswitch`); an unknown name
draws a plain circle (`U2015`). ApkPy's own short names also work: {icons}.

## Layout that looks like the app you mean

- A `display: flex` row with no `justify-content` centres its children. Chips,
  a caption of two labels, an avatar with a name: add
  `justify-content: flex-start`.
- A `Theme` gives `body` a 12px `gap` and `padding`, and the body reaches every
  container. A tight row (icons in a pill, actions under a photo) needs
  `gap: 0px`.
- `position: absolute` on a screen's own child floats it over the screen (a
  floating button, a composer at `bottom: 0`); inside a `position: relative`
  container it floats over that container (a close button on a story).
- A chat is a `virtual_collection` with `variant=` and `id:kind` rules
  (`align-self`, `max-width`, `item-border-radius`); a chat list uses
  `badge-position: end`.
- A feed, comments or product cards: `virtual_collection(items, row=post_row)`,
  where `def post_row(row):` builds one row from components with
  `parent=row` and `"{{field}}"` texts; a `command=lambda item: ...` inside gets
  the row's item.
- An icon button is `button("", icon=..., describe=...)`; `describe` is what a
  screen reader says.
- Tabs inside a screen (Posts / Reels / Tagged): `tabs = pager(id=..., screen=...)`,
  then `posts = tab("Posts", icon=..., parent=tabs)` for each page, and the
  page's components with `parent=posts`. A photo grid is
  `virtual_collection(items, row=tile, layout="grid", columns=3)`; its
  `height: auto` makes it scroll with the screen.
- Rows swipe and move: `virtual_collection(..., swipe_right=swipe("archive",
  "Archive", on_swipe=fn, undo="Archived"), swipe_left=swipe("delete", "Delete",
  on_swipe=fn), on_reorder=fn)` -- `on_swipe(item)`, `on_reorder(item, index)`;
  lists only, and each gesture is also a TalkBack action.
- Charts are native: `chart(items, kind="bar")` (or `"line"` with `fill=True`,
  `"donut"`, `"ring"` with `value=`/`max=`), items read by `x=`/`y=`;
  `set_items()` and `set_value()` update them. No matplotlib: it cannot run on
  the phone.
- Filters and choices that stay selected: `chips(["All", "Unread"],
  selected="All", on_change=fn)` (`multiple=True` gives fn a list) and
  `segmented(["Day", "Week", "Month"], selected="Week", on_change=fn)`, 2 to 5
  segments; `check=False` hides the check mark, `required=True` keeps one
  always selected. Not rows of buttons.
- An Android class ApkPy has no function for: name it at the top of the file,
  `Vibrator = native.use("android.os.Vibrator")`, and write
  `@native(preview=lambda ms: None)` over `def buzz(ms: int):` with a body that
  calls Java -- `context.getSystemService(Vibrator).vibrate(ms)`. The body is
  translated to Java when the app is built and checked against android.jar; it
  sees its arguments, `context`, `activity` and those classes, never the app's
  own functions, and returns text or a number. Something newer than Android
  7.0 goes under `if Build.VERSION.SDK_INT >= 26:`. This is not pyjnius: there
  is no `autoclass` and no `jnius` import.
- A call past the app answers in one of three ways. Handing over
  (`phone.dial`, `phone.sms`, `calendar.add_event`, `browser.open`) and
  `haptics` answer a word at once: `"ok"`, or why not (`"no_app"`,
  `"invalid"`). What needs the person or takes time (`speech.listen`,
  `files.save_as`, `downloads.start`, `recorder.start`, `printing.html`,
  `browser.show`) answers in `on_result=fn`, where `def fn(ok, value):` takes
  exactly those two -- the words heard or the file's name, or the word for
  why not (`"cancelled"`, `"permission_denied"`). A question
  (`recorder.is_recording()`, `speech.can_listen()`) goes in an `if`. No
  permission to ask for and no manifest to write: `recorder.start()` asks for
  the microphone itself. `calendar.add_event("Dentist", "2026-11-03 15:30")`
  takes its times as text; a date alone is a whole day. None of these runs
  inside a background job (`J7004`); a wrong call stops the build (`U2048`).
- A link or a share that opens the app: at the top of the file,
  `incoming.links("notes", preview="notes://open/42")` (or
  `incoming.links("https", host="notes.example.com")`) and
  `incoming.shares("text", preview="...")` -- `"image"` or `"file"` too. Then
  in the first screen's `lifecycle(home, on_mount=arrived)`, read
  `incoming.link()`, `incoming.text()` or `incoming.file()` (`""` when
  nothing came) and call `incoming.clear()`.
- What an app has outside its screens starts with one line at the top of the
  file, with its arguments written out (not variables):
  `home_widget.define("Steps today", "0", caption="steps", icon="directions_walk")`,
  `quick_tile.define("Walk", icon="directions_walk")`, `ads.setup("test")`,
  `health.policy("https://example.com/privacy")`. Without it the build stops
  (`U2048`) and says which line to add; `updates` needs none. Then, from a
  function: `home_widget.set("6 482", caption="steps")`;
  `quick_tile.set(True, subtitle="On a walk")`, and in the first screen's
  `on_mount`, `if quick_tile.opened(): ... quick_tile.clear()` -- a tap on the
  tile opens the app. Ads: `ads.banner("test")` in `on_mount` (it is that
  screen's), `ads.interstitial("test", on_result=carry_on)` at a pause,
  `ads.rewarded("test", on_result=paid)` where `paid(ok, amount)`; `"test"`
  is Google's sample ad and is what to write until the person has AdMob ids;
  consent is asked by itself. `updates.check(on_result=found)` answers
  `"available"`, `"none"` or, for an app not installed from Play,
  `"not_from_play"`. Health: `health.ask("steps, heart_rate", on_result=asked)`
  then `health.read("steps", on_result=got)` -- today when no `start=`/`end=`
  (`"2026-10-04"` or `"2026-10-04 20:00"`); the kind is a literal, one of
  steps, distance, active_calories, calories, heart_rate, resting_heart_rate,
  sleep, weight, floors, exercise, hydration; the value is text. Android 14+,
  read only.
- A function run later, or again and again: `timer.after(2, hide_banner)`
  once, `timer.every(1, tick)` every second, `timer.cancel(tick)` to stop it
  and `if timer.running(tick):` to ask. The function is one written with
  `def` at the top level that takes nothing -- no lambda, and no brackets
  after its name. A timer is known by its function: there is no handle to
  keep, and starting it again starts it over, so `timer.after(0.4, search)`
  in an `on_change` searches once, when the typing stops. Start it from a
  function (`lifecycle(home, on_mount=start)`), never from the top of the
  file (`U2048`). It runs only while its screen is on show -- nothing runs
  with the app in the background, and coming back runs what fell due, once
  -- and it ends when the screen is closed. Keep a count in a label or in
  `storage`, not in a `global`. Work with the app closed is
  `service.every` or `background_job`, not a timer.
- The connection: `network.online()` is whether the phone reaches the
  internet now, `network.kind()` what it is over (`"wifi"`, `"mobile"`,
  `"ethernet"`, `"other"`, or `"none"`), `network.metered()` whether the
  person pays for it (wait for it to be False before a big download).
  `network.on_change(changed)` calls `changed()` -- a `def` at the top level
  that takes nothing -- when one of those answers changes; it is not called
  as it is asked for, so call it once yourself:
  `def opened(): changed(); network.on_change(changed)` with
  `lifecycle(home, on_mount=opened)`. It is told only while its screen is on
  show, and never from the top of the file (`U2048`). A Wi-Fi that wants a
  login page is `kind() == "wifi"` with `online()` False. For "show this
  when offline" bind a state: `online = state(True)`,
  `online.bind_visibility(banner, when=False)`, `online.set(network.online())`.
  Write `if network.online(): ... else: ...`, not `x = not network.online()`.
  In the Previewer a click on the connection in the status bar takes it
  from Wi-Fi to mobile data to none, and `https` fails while there is none.
  Work that must wait for a connection with the app closed is
  `background_job(..., requires_network=True)`.
- The app lock: `app_lock.after(5)` locks the whole app after 5 minutes
  away or untouched (`0` = every time it comes back; `0.5` = 30 s); say it in
  the first screen's `on_mount` -- never at the top of the file (`U2048`) --
  or in a switch with `app_lock.off()` to undo. The rule is kept on the phone
  (closing the app does not open it); the phone draws the prompt, so never
  build a PIN screen of your own or use `biometrics.unlock()` for this.
  `app_lock.now()` for a "Lock" button (`command=app_lock.now`). `after()`
  and `now()` answer `"no_lock"` on a phone with no screen lock: say so to the
  person. In the Previewer, minimising the window is going to the background.
- The display: `display.keep_on()` (screen does not sleep),
  `display.brightness(0.9)` (0 to 1, `"auto"` gives it back; not 90),
  `display.immersive()` (no status or navigation bar) and
  `display.orientation("portrait" | "landscape" | "auto")`, each with
  `(False)` or `"auto"` to undo. They belong to the screen on show: ask in
  its `on_mount` or a button, never at the top of the file (`U2048`); they
  end when the screen is closed and survive a rotation. A whole app upright
  is `run(start_screen=home, orientation="portrait")`, one screen on its side
  `Screen(id="player", orientation="landscape")` -- not a manifest edit or
  `native.java()`. A switch's `on_change` value goes straight in:
  `display.keep_on(on)`. Tablets (600dp and wider) ignore orientation on
  Android 16, so lay out both ways. In the Previewer Ctrl+Left / Ctrl+Right
  turn the phone.
- A picture that opens full screen with pinch zoom: `image(src, zoom=True)`;
  from a function, `view_image(src)` (a list's `on_click=lambda item:
  view_image(item["photo"])`). No zoom library, no second screen for it.
- A sheet of controls: `filters = bottom_sheet("Filters", screen=home)`, then
  `chips(..., parent=filters)`, `button("Apply", command=apply, parent=filters)`;
  `filters.open()` / `filters.close()`. It drags down to close. Without
  `screen=` it only takes `items=[...]` and `on_select=`.
- Forms: `inputs("Email", help="...", required=True)` puts help text under a
  text field; `if not validate(name, email): return` shows every empty
  required field at once; `email.set_error("...")` shows your own message and
  `set_error("")` clears it. Not a label you colour red yourself.
- A control that answers as it changes: `inputs("Name", on_change=fn)` or
  `on_change=lambda value: greeting.set_value("Hello, " + value)` -- one
  parameter, the new value: the text, `"true"`/`"false"` from a switch or a
  checkbox, a slider's number as text.

## When the guide is not enough

`apkpy examples` writes a complete example app into a folder you choose --
notes in SQLite, settings, a REST client, permissions, camera. Read one before
guessing an API. A keyword a function does not take stops the build with
`U2030`, which lists the keywords it does take.

## Errors

Errors come as `APKPY <code>`, with the line and a fix. `E1xxx` Python and
environment, `U2xxx` components, arguments and untranslated Python, `D2xxx`
database, `P3xxx` Previewer runtime, `J7xxx` background jobs. Read the code's
entry before changing anything: {docs}/friendly-errors/

## Documentation

- Everything in one file, to read in full: {docs}/llms-full.txt
- Exact signatures: {docs}/reference/essential/
- What is translated and what is not: {docs}/compatibility/
- Example apps: https://github.com/apkpy-project/repo-apkpy/tree/main/examples
'''

_CLAUDE = '''# Claude Code: this project's instructions are in AGENTS.md

@AGENTS.md
'''


def installed_version():
    """The apkpy the person has installed -- the version the guide is for."""
    try:
        from importlib.metadata import version
        return version("apkpy")
    except Exception:
        return "unknown"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def render(version=None):
    """The AGENTS.md text, with the marker that lets it be refreshed later."""
    from . import icons
    version = version or installed_version()
    body = _BODY.format(version=version, docs=DOCS,
                        icons=", ".join(f"`{name}`" for name in sorted(icons.names())))
    return f"<!-- apkpy:agents version={version} sha={_sha(body)} -->\n" + body


def is_untouched(text):
    """True when ``text`` is an AGENTS.md ApkPy wrote and nobody edited."""
    found = _MARKER.match(text)
    return bool(found) and found.group(2) == _sha(text[found.end():])


def write(directory=".", force=False, version=None):
    """Write AGENTS.md and CLAUDE.md into ``directory``.

    Returns ``[(file name, what happened)]``, where what happened is one of
    ``created``, ``updated``, ``up to date`` and ``kept`` -- the last for a
    file the person wrote or edited, which is never replaced unless
    ``force``.
    """
    results = []
    agents = os.path.join(directory, AGENTS_FILE)
    wanted = render(version)
    if not os.path.exists(agents):
        _write(agents, wanted)
        results.append((AGENTS_FILE, "created"))
    else:
        with open(agents, encoding="utf-8") as handle:
            current = handle.read()
        if current == wanted:
            results.append((AGENTS_FILE, "up to date"))
        elif force or is_untouched(current):
            _write(agents, wanted)
            results.append((AGENTS_FILE, "updated"))
        else:
            results.append((AGENTS_FILE, "kept"))

    claude = os.path.join(directory, CLAUDE_FILE)
    if not os.path.exists(claude):
        _write(claude, _CLAUDE)
        results.append((CLAUDE_FILE, "created"))
    else:
        with open(claude, encoding="utf-8") as handle:
            current = handle.read()
        if current == _CLAUDE:
            results.append((CLAUDE_FILE, "up to date"))
        elif force:
            _write(claude, _CLAUDE)
            results.append((CLAUDE_FILE, "updated"))
        else:
            # Somebody's own instructions. Pointing them at AGENTS.md is a
            # line they can add; overwriting them is not ours to do.
            results.append((CLAUDE_FILE, "kept"))
    return results


def _write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
