---
title: Native knowledge app
description: Render Markdown, inline rich text and large expandable trees without a WebView.
---

# Native knowledge app

```python
from apkpy_lib import Screen, markdown, rich_text, run, tree_view

notes = Screen(id="notes", scroll=True)

rich_text(
    [
        {"text": "Small interfaces, ", "bold": True, "size": 22},
        {"text": "deep structure.", "bold": True, "italic": True, "color": "#A78BFA", "size": 22},
    ],
    screen=notes,
)

markdown(
    """
## Build log

> Content remains selectable and native.

- [x] headings, quotes and dividers
- [x] **bold**, *italic* and `inline code`
- [ ] connect the editor to your own storage
""",
    screen=notes,
)

tree_view(
    [
        {
            "key": "product",
            "title": "Product",
            "subtitle": "18 pages",
            "children": [
                {"key": "roadmap", "title": "Roadmap", "subtitle": "Q3 planning"},
                {"key": "releases", "title": "Release notes", "subtitle": "12 entries"},
            ],
        }
    ],
    expand_depth=1,
    screen=notes,
)

run(notes)
```

Android receives native spans and a `RecyclerView` for visible tree rows. No
WebView or JavaScript runtime is required. Persist the document in SQLite or
load it through an API; collaborative editing and merge algorithms remain
application responsibilities.
