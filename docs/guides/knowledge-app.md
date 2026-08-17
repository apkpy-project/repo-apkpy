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

## Store the document with Data Core 1.3.0

```python
documents = db.model(
    "documents",
    fields={
        "id": db.integer(primary_key=True, auto_increment=True),
        "title": db.text(required=True, max_length=120),
        "body": db.text(default=""),
        "favorite": db.boolean(default=False),
        "updated_at": db.datetime(default=db.now()),
    },
    indexes=[
        db.index("idx_documents_updated", ["updated_at"]),
    ],
)

schema = db.schema("knowledge_app", 1, [documents])
```

Load a native Markdown view without introducing a WebView:

```python
def document_loaded(document):
    if document == "":
        status.set_value("Document not found")
        return
    title_label.set_value(document["title"])
    body_markdown.set_value(document["body"])

documents.get(
    selected_id,
    on_result=document_loaded,
    on_error=lambda message: status.set_value(str(message)),
)
```

For a large workspace, query a page of titles into `virtual_collection()` and
only load the selected body with `get()`. Trees describe the visible hierarchy;
Data Core remains responsible for stored records and indexes.
