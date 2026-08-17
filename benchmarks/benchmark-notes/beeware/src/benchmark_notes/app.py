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
    return BenchmarkNotes("Benchmark Notes", "com.apkpy.benchmark.benchmark_notes").main_loop()
