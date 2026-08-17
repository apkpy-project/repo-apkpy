---
title: Android benchmark
description: Reproducible debug APK, build, cold-start, memory and source-line comparison of the same notes app in ApkPy, Flet, BeeWare/Toga and Kivy.
---

<section class="benchmark-hero">
  <span>MEASURED / 2026-08-17</span>
  <h1>One small app.<br>Four Python Android paths.</h1>
  <p>Benchmark Notes fixes the dataset and user-visible behavior, then measures the Android package each stack actually produces. The programs and raw samples are included so the comparison can be challenged and repeated.</p>
</section>

<div class="benchmark-metrics">
  <article><span>ApkPy debug APK</span><strong>5.38 MiB</strong><small>5,637,396 bytes</small></article>
  <article><span>Cold-start median</span><strong>590 ms</strong><small>three force-stopped launches</small></article>
  <article><span>Total PSS median</span><strong>46.3 MiB</strong><small>sampled two seconds after launch</small></article>
  <article><span>App source</span><strong>83 lines</strong><small>66 non-blank, non-comment</small></article>
</div>

## Result

All available APKs were debug builds installed on the same Pixel 9 emulator,
Android API 35 and x86_64 ABI. “Cached build” excludes first-time toolchain
downloads.

!!! warning "Development-build evidence"

    Android recommends measuring optimized release-like builds for conclusions
    about production performance. This run intentionally uses debug builds so
    every artifact is inspectable and uses the same build class. Treat it as a
    reproducible development-floor comparison, not a store-release ranking.

| Stack | App source | APK | Cached build | Cold start | PSS | UI smoke |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| **ApkPy 1.3.0 candidate** | 83 lines | **5.38 MiB** | 20.9 s | **590 ms** | **46.3 MiB** | 4/4 |
| Flet 0.86.5 | **70 lines** | 25.28 MiB | 143.0 s | 1,824 ms | 206.1 MiB | 4/4 |
| BeeWare/Toga 0.5.6 | 73 lines | 33.98 MiB | **17.8 s** | 2,334 ms | 79.7 MiB | 4/4 |
| Kivy 2.3.1 | 78 lines | not produced | not produced | not produced | not produced | source smoke |

For this app, ApkPy's debug APK was **4.70x smaller than Flet** and **6.32x
smaller than BeeWare/Toga**. Its measured PSS was **4.46x lower than Flet**
and **1.72x lower than BeeWare/Toga**.

!!! warning "Read the claim at the correct size"

    This is evidence for one deliberately small application, not a universal
    framework ranking. Release signing, R8, assets, plugins, backend code and
    application architecture can change size, memory and startup.

## What this result answers

| Question | Answer from this run |
| --- | --- |
| Which measured debug artifact was smallest? | ApkPy, at 5.38 MiB. |
| Which measured app had the lowest median cold start? | ApkPy, at 590 ms. |
| Which measured app had the lowest median total PSS? | ApkPy, at 46.3 MiB. |
| Was every implementation asked to do the same thing? | Yes: the same 100 records and four visible actions. |
| Does this prove every ApkPy app beats every alternative? | No. The result is scoped to this app, device, ABI and debug configuration. |
| Is Kivy slower or larger here? | Unknown. No Kivy APK was produced, so no Android number is claimed. |

## Packaging paths compared

| Stack | Android path used by the measured program |
| --- | --- |
| ApkPy | Python declaration transpiled to generated Java/XML, then built by Gradle. |
| Flet | Python application packaged with the Flet/Flutter Android toolchain. |
| BeeWare/Toga | Python application packaged through Briefcase. |
| Kivy | Source prepared for Buildozer/python-for-Android; Android packaging was blocked on this Windows host. |

The benchmark compares complete application artifacts, not just source syntax.
It does not attempt to make the generated internals identical because that is
precisely where each stack makes a different architectural choice.

## The app contract

Every implementation starts with the same deterministic 100-note list and
must expose the same four behaviors:

1. search note title and subtitle;
2. show favorites only;
3. add a new note;
4. scroll the result list.

There is no network, database, media asset or framework-specific plugin. This
keeps the run focused on the small UI/runtime floor. It deliberately does
**not** measure the new [Data Core](data-core.md).

The Android UI tree was checked for the same four labels after launch:
`Benchmark Notes`, `Search notes`, `FAVORITES ONLY` and `ADD NOTE`. ApkPy,
Flet and BeeWare/Toga each passed 4/4.

## Exact application code

Only application programs are shown below. No private ApkPy compiler source is
included.

=== "ApkPy — 83 lines"

    ~~~ python
    from apkpy_lib import Screen, button, inputs, label, list_view, run, state


    NOTES = [
        {
            "title": f"Note {index:03d}",
            "subtitle": "Same deterministic row in every framework",
            "meta": "Favorite" if index % 5 == 0 else "Standard",
        }
        for index in range(1, 101)
    ]

    home = Screen(id="home", scroll=True)
    query_state = state("", id="benchmark_query")
    favorites_state = state(False, id="benchmark_favorites")
    next_state = state(101, id="benchmark_next")


    def visible_notes():
        query = query_state.get().strip().lower()
        return [
            item for item in NOTES
            if (not favorites_state.get() or item["meta"] == "Favorite")
            and (not query or query in item["title"].lower()
                 or query in item["subtitle"].lower())
        ]


    def refresh_rows():
        notes.set_items(visible_notes())
        status.set_value(f"Showing {len(visible_notes())} notes")


    def search_changed(value):
        query_state.set(value)
        refresh_rows()


    def toggle_favorites(value=None):
        favorites_state.toggle()
        refresh_rows()


    def add_note():
        index = next_state.get()
        NOTES.append({
            "title": f"Note {index:03d}",
            "subtitle": "Added from the shared benchmark action",
            "meta": "Standard",
        })
        next_state.increment()
        refresh_rows()


    label("BENCHMARK NOTES / 0.1", id="kicker", screen=home)
    label("One small app. Four native packaging paths.", id="title", screen=home)
    label(
        "Search 100 notes, add a row, toggle favorites and scroll the same dataset.",
        id="copy", screen=home,
    )
    inputs(
        "Search notes", id="search", type="search", screen=home,
        on_change=search_changed,
    )
    button("FAVORITES ONLY", id="favorites", icon="star", screen=home,
           command=toggle_favorites)
    button("ADD NOTE", id="add", icon="add", screen=home, command=add_note)
    status = label("Showing 100 notes", id="status", screen=home)
    notes = list_view(NOTES, id="notes", screen=home, rich=True)

    style = """
    home { background-color: #090B10; padding: 18px; }
    kicker { color: #50E3C2; font-size: 11px; font-weight: bold; margin-bottom: 8px; }
    title { color: #F5F7FB; font-size: 26px; font-weight: bold; margin-bottom: 8px; }
    copy, status { color: #9EA8BA; font-size: 13px; margin-bottom: 12px; }
    search { background-color: #10141C; color: #F5F7FB; placeholder-color: #9EA8BA; border-color: #30394A; border-radius: 14px; min-height: 48px; margin-bottom: 10px; }
    favorites, add { border-radius: 14px; min-height: 48px; font-weight: bold; margin-bottom: 10px; }
    favorites { background-color: #1D5660; color: #FFFFFF; }
    add { background-color: #7C5CFF; color: #24164A; }
    notes { height: 560px; background-color: #090B10; color: #F5F7FB; item-background-color: #151922; title-color: #F5F7FB; subtitle-color: #9EA8BA; meta-color: #50E3C2; item-border-color: #30394A; }
    """

    run(start_screen=home)
    ~~~

=== "Flet — 70 lines"

    ~~~ python
    import flet as ft


    NOTES = [
        {"title": f"Note {index:03d}",
         "subtitle": "Same deterministic row in every framework",
         "meta": "Favorite" if index % 5 == 0 else "Standard"}
        for index in range(1, 101)
    ]


    def main(page: ft.Page):
        page.title = "Benchmark Notes"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 18
        query = {"value": ""}
        favorites = {"value": False}
        next_index = {"value": 101}
        rows = ft.Column(spacing=1, scroll=ft.ScrollMode.AUTO, expand=True)
        status = ft.Text("Showing 100 notes", color="#9EA8BA", size=13)

        def visible():
            q = query["value"].strip().lower()
            return [item for item in NOTES if (not favorites["value"] or item["meta"] == "Favorite") and (not q or q in item["title"].lower() or q in item["subtitle"].lower())]

        def refresh():
            rows.controls = [
                ft.Container(
                    content=ft.Column([
                        ft.Text(item["title"], weight=ft.FontWeight.BOLD),
                        ft.Text(f'{item["subtitle"]} · {item["meta"]}', color="#9EA8BA", size=12),
                    ], spacing=3),
                    bgcolor="#151922", padding=10,
                )
                for item in visible()
            ]
            status.value = f"Showing {len(visible())} notes"
            page.update()

        def on_search(event):
            query["value"] = event.control.value
            refresh()

        def toggle_favorites(_event):
            favorites["value"] = not favorites["value"]
            refresh()

        def add_note(_event):
            index = next_index["value"]
            NOTES.append({"title": f"Note {index:03d}", "subtitle": "Added from the shared benchmark action", "meta": "Standard"})
            next_index["value"] += 1
            refresh()

        page.add(ft.Column([
            ft.Text("BENCHMARK NOTES / 0.1", color="#50E3C2", size=11, weight=ft.FontWeight.BOLD),
            ft.Text("One small app. Four native packaging paths.", size=26, weight=ft.FontWeight.BOLD),
            ft.Text("Search 100 notes, add a row, toggle favorites and scroll the same dataset.", color="#9EA8BA", size=13),
            ft.TextField(hint_text="Search notes", on_change=on_search, border_radius=14, height=48),
            ft.Row([
                ft.FilledButton("FAVORITES ONLY", on_click=toggle_favorites),
                ft.FilledButton("ADD NOTE", on_click=add_note),
            ], spacing=10),
            status,
            rows,
        ], expand=True, spacing=10))
        refresh()


    if __name__ == "__main__":
        ft.run(main)
    ~~~

=== "Kivy — 78 lines"

    ~~~ python
    from kivy.app import App
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.textinput import TextInput


    NOTES = [
        {"title": f"Note {index:03d}",
         "subtitle": "Same deterministic row in every framework",
         "meta": "Favorite" if index % 5 == 0 else "Standard"}
        for index in range(1, 101)
    ]


    class BenchmarkNotes(App):
        def build(self):
            self.query = ""
            self.favorites = False
            self.next_index = 101
            root = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(10))
            root.background_color = (0.035, 0.043, 0.063, 1)
            root.add_widget(Label(text="BENCHMARK NOTES / 0.1", size_hint_y=None, height=dp(22), color=(0.31, 0.89, 0.76, 1)))
            root.add_widget(Label(text="One small app. Four native packaging paths.", size_hint_y=None, height=dp(62), font_size=dp(24), halign="left", text_size=(None, None)))
            root.add_widget(Label(text="Search 100 notes, add a row, toggle favorites and scroll the same dataset.", size_hint_y=None, height=dp(48), color=(0.62, 0.66, 0.73, 1)))
            self.search = TextInput(hint_text="Search notes", multiline=False, size_hint_y=None, height=dp(48))
            self.search.bind(text=self.on_search)
            root.add_widget(self.search)
            actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
            favorites = Button(text="FAVORITES ONLY")
            favorites.bind(on_release=self.toggle_favorites)
            add = Button(text="ADD NOTE")
            add.bind(on_release=self.add_note)
            actions.add_widget(favorites)
            actions.add_widget(add)
            root.add_widget(actions)
            self.status = Label(text="Showing 100 notes", size_hint_y=None, height=dp(26), color=(0.62, 0.66, 0.73, 1))
            root.add_widget(self.status)
            self.scroll = ScrollView(do_scroll_x=False)
            self.rows = BoxLayout(orientation="vertical", spacing=dp(1), size_hint_y=None)
            self.rows.bind(minimum_height=self.rows.setter("height"))
            self.scroll.add_widget(self.rows)
            root.add_widget(self.scroll)
            self.refresh_rows()
            return root

        def visible(self):
            query = self.query.strip().lower()
            return [item for item in NOTES if (not self.favorites or item["meta"] == "Favorite") and (not query or query in item["title"].lower() or query in item["subtitle"].lower())]

        def refresh_rows(self):
            self.rows.clear_widgets()
            items = self.visible()
            for item in items:
                row = BoxLayout(orientation="vertical", padding=dp(10), size_hint_y=None, height=dp(66))
                row.add_widget(Label(text=item["title"], halign="left", text_size=(None, None)))
                row.add_widget(Label(text=f'{item["subtitle"]} · {item["meta"]}', color=(0.62, 0.66, 0.73, 1), halign="left", text_size=(None, None)))
                self.rows.add_widget(row)
            self.status.text = f"Showing {len(items)} notes"

        def on_search(self, _widget, value):
            self.query = value
            self.refresh_rows()

        def toggle_favorites(self, _button):
            self.favorites = not self.favorites
            self.refresh_rows()

        def add_note(self, _button):
            NOTES.append({"title": f"Note {self.next_index:03d}", "subtitle": "Added from the shared benchmark action", "meta": "Standard"})
            self.next_index += 1
            self.refresh_rows()


    if __name__ == "__main__":
        BenchmarkNotes().run()
    ~~~

=== "BeeWare/Toga — 73 lines"

    ~~~ python
    import toga
    from toga.style import Pack
    from toga.style.pack import COLUMN, ROW


    NOTES = [
        {"title": f"Note {index:03d}",
         "subtitle": "Same deterministic row in every framework",
         "meta": "Favorite" if index % 5 == 0 else "Standard"}
        for index in range(1, 101)
    ]


    class BenchmarkNotes(toga.App):
        def startup(self):
            self.query = ""
            self.favorites = False
            self.next_index = 101
            self.rows = toga.Box(style=Pack(direction=COLUMN, flex=1))
            self.status = toga.Label("Showing 100 notes", style=Pack(padding_bottom=8))
            self.search = toga.TextInput(placeholder="Search notes", on_change=self.on_search, style=Pack(flex=1, padding_right=8))
            search_row = toga.Box(children=[self.search], style=Pack(direction=ROW, padding_bottom=8))
            favorites = toga.Button("FAVORITES ONLY", on_press=self.toggle_favorites, style=Pack(flex=1, padding_right=5))
            add = toga.Button("ADD NOTE", on_press=self.add_note, style=Pack(flex=1, padding_left=5))
            actions = toga.Box(children=[favorites, add], style=Pack(direction=ROW, padding_bottom=8))
            content = toga.Box(children=[
                toga.Label("BENCHMARK NOTES / 0.1", style=Pack(padding_bottom=8)),
                toga.Label("One small app. Four native packaging paths.", style=Pack(padding_bottom=8)),
                toga.Label("Search 100 notes, add a row, toggle favorites and scroll the same dataset.", style=Pack(padding_bottom=8)),
                search_row, actions, self.status, self.rows,
            ], style=Pack(direction=COLUMN, padding=18, flex=1))
            self.main_window = toga.MainWindow(title=self.formal_name)
            self.main_window.content = content
            self.main_window.show()
            self.refresh_rows()

        def visible(self):
            query = self.query.strip().lower()
            return [item for item in NOTES if (not self.favorites or item["meta"] == "Favorite") and (not query or query in item["title"].lower() or query in item["subtitle"].lower())]

        def refresh_rows(self):
            self.rows.children.clear()
            items = self.visible()
            for item in items:
                self.rows.add(toga.Box(children=[
                    toga.Label(item["title"], style=Pack(font_weight="bold")),
                    toga.Label(f'{item["subtitle"]} · {item["meta"]}', style=Pack(font_size=10)),
                ], style=Pack(direction=COLUMN, padding=10)))
            self.status.text = f"Showing {len(items)} notes"

        def on_search(self, widget):
            self.query = widget.value or ""
            self.refresh_rows()

        def toggle_favorites(self, _widget):
            self.favorites = not self.favorites
            self.refresh_rows()

        def add_note(self, _widget):
            index = self.next_index
            NOTES.append({"title": f"Note {index:03d}", "subtitle": "Added from the shared benchmark action", "meta": "Standard"})
            self.next_index += 1
            self.refresh_rows()


    def main():
        """Launch the same benchmark app through Briefcase's Android entrypoint."""
        return BenchmarkNotes(
            "Benchmark Notes",
            "com.apkpy.benchmark.benchmark_notes",
        ).main_loop()

    # src/benchmark_notes/__main__.py
    from .app import main


    if __name__ == "__main__":
        main()
    ~~~

The public repository stores the exact, unshortened programs and packaging
files under
[`benchmarks/benchmark-notes`](https://github.com/apkpy-project/repo-apkpy/tree/main/benchmarks/benchmark-notes).

## Source lines

“Physical” counts every line in the application entry files, including blank
lines. “Code” removes blank lines and lines beginning with `#`. Generated Java,
XML and Gradle files are not counted; neither are TOML/spec packaging files.

| Stack | Entry files | Physical | Code |
| --- | --- | ---: | ---: |
| ApkPy | `writehere.py` | 83 | 66 |
| Flet | `main.py` | 70 | 58 |
| Kivy | `main.py` | 78 | 67 |
| BeeWare/Toga | `app.py` + `__main__.py` | 73 | 60 |

Line count helps audit how much handwritten app code was compared. It is not,
on its own, a quality or productivity score.

## How the Android measurements were taken

1. Build each debug APK after dependencies were cached.
2. Install it on the same emulator.
3. Force-stop before every launch.
4. Run `adb shell am start -W` three times and take the median.
5. Wait two seconds and read total PSS from `dumpsys meminfo`.
6. Verify the four required labels in the UI tree.

For a future release-grade performance study, the same contract should be
rebuilt with release optimization, measured with Android Macrobenchmark and
inspected with Perfetto. This recorded run is kept immutable rather than
silently replacing its debug samples with a different methodology.

The raw cold-start samples were:

| Stack | Run 1 | Run 2 | Run 3 | Median |
| --- | ---: | ---: | ---: | ---: |
| ApkPy | 611 ms | 590 ms | 580 ms | **590 ms** |
| Flet | 1,824 ms | 1,845 ms | 1,733 ms | 1,824 ms |
| BeeWare/Toga | 2,346 ms | 2,334 ms | 2,327 ms | 2,334 ms |

The raw PSS samples are included in the
[benchmark JSON](https://github.com/apkpy-project/repo-apkpy/blob/main/benchmarks/benchmark-notes/results/benchmark.json),
together with SHA-256 hashes for each measured APK.

## Why Kivy has no APK row

The Kivy 2.3.1 application passed a Python source smoke check. The Windows host
did not have Buildozer/python-for-Android or an installed WSL distribution, so
it could not produce a Kivy Android artifact in this run. An empty measurement
is more useful than a guessed one.

Kivy's own Android packaging guide recommends Buildozer as the easiest path and
directs Windows users to WSL. That environment was unavailable for this run;
the source and `buildozer.spec` remain included so a later Linux/WSL run can
fill the missing row without changing the application contract.

## Reproduce or challenge it

The public evidence bundle contains:

- the four unshortened application programs;
- every packaging file used by those programs;
- APK size, SHA-256, build-time, launch and memory samples;
- emulator and tool versions;
- the PowerShell device-measurement script.

Start with the [raw benchmark folder](https://github.com/apkpy-project/repo-apkpy/tree/main/benchmarks/benchmark-notes)
and read its README before comparing a new run. Keep the dataset, behavior,
device, ABI and build class unchanged; otherwise publish the result as a new
scenario instead of overwriting this one.

Primary measurement and packaging references:

- [Android performance measurement](https://developer.android.com/topic/performance/measuring-performance)
- [Android app startup time](https://developer.android.com/topic/performance/vitals/launch-time)
- [Kivy Android packaging](https://kivy.org/doc/stable/guide/packaging-android.html)
- [BeeWare Android tutorial](https://tutorial.beeware.org/en/latest/)

## What 1.3.0 adds beyond this benchmark

Benchmark Notes deliberately keeps its dataset in memory. ApkPy 1.3.0 adds a
separate production-oriented [Data Core](data-core.md): typed SQLite models,
bound filters, asynchronous CRUD, batch writes, transactions, pagination and
explicit migrations with backup/restore safety.

Use the benchmark to inspect the small application/runtime floor. Use the
[1.3.0 release page](version-1.3.0.md) and
[Knowledge Vault example](guides/knowledge-app.md) to evaluate the data layer.
