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
