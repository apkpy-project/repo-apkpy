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
