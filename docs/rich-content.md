# Native rich content

Build the three components together in the
[native knowledge app guide](guides/knowledge-app.md).

ApkPy can render styled text, Markdown and expandable hierarchies without
embedding a browser in the application. The Previewer uses native desktop text
widgets; the Android build emits `Spannable` text and a `RecyclerView`.

This is useful for:

- notes, release notes and local documentation;
- formatted posts, comments and Reddit-style discussions;
- Notion-style workspace indexes and nested page trees;
- help centres, changelogs and knowledge bases;
- selectable technical text with headings, code and links.

## Choose the smallest component that fits

| Component | Use it when | Native Android output |
| --- | --- | --- |
| `rich_text()` | Each inline span needs an exact colour, size or emphasis | `TextView` + `SpannableStringBuilder` |
| `markdown()` | The content already has document structure | `TextView` + native spans |
| `tree_view()` | Records have recursive parent/child relationships | `RecyclerView` + visible-row adapter |

The rich-content Android helpers are included only when one of these components
appears in the source. A normal app does not ship the extra runtime.

## `rich_text()`: precise inline typography

Each span is a dictionary with a required `text` value. Optional keys are
`bold`, `italic`, `underline`, `strike`, `code`, `color`, `size` and `link`.

~~~ python
from apkpy_lib import Screen, rich_text

article = Screen(id="article", scroll=True)

rich_text(
    [
        {
            "text": "FIELD NOTE  /  04\n",
            "bold": True,
            "color": "#22D3EE",
            "size": 12,
        },
        {
            "text": "Small interfaces, ",
            "bold": True,
            "size": 23,
        },
        {
            "text": "deep structure.",
            "bold": True,
            "italic": True,
            "color": "#C4B5FD",
            "size": 23,
        },
        {
            "text": "\nOne component, several native text styles.",
            "color": "#A1A1AA",
            "size": 14,
        },
    ],
    id="article_lead",
    selectable=True,
    screen=article,
)
~~~

Use spans when visual meaning lives inside a sentence. Do not split the
sentence into several labels just to colour one word: separate labels wrap and
align independently on narrow screens.

## `markdown()`: readable documents

The supported subset includes:

- headings;
- bold, italic and strike-through text;
- links;
- inline and fenced code;
- quotes;
- ordered and unordered lists;
- task-list checkboxes;
- dividers.

~~~ python
from apkpy_lib import Screen, markdown

notes = Screen(id="notes", scroll=True)

markdown(
    """## Build log · 1.2

> Content remains selectable and native.

- [x] Headings, quotes and dividers
- [x] **Bold**, *italic*, ~~strike~~ and `inline code`
- [x] Ordered lists and task lists
- [ ] Connect the editor to your own storage

### Why this matters

A notes app can render structured content without a WebView.
""",
    id="release_notes",
    selectable=True,
    screen=notes,
)
~~~

`markdown()` is a renderer, not a hosted editor or a WebView. Store the source
in SQLite, encrypted storage or an API according to the application's needs,
then construct the component from that source.

## `tree_view()`: large expandable hierarchies

Every node accepts:

| Key | Required | Meaning |
| --- | --- | --- |
| `title` | yes | Primary row text |
| `subtitle` | no | Secondary row text |
| `key` | no | Stable application identifier |
| `expanded` | no | Explicit initial open/closed state |
| `children` | no | Recursive list of child nodes |

`expand_depth` chooses how many levels start open. `row_height` is clamped to a
safe range from 48 to 96 density-independent pixels.

~~~ python
from apkpy_lib import Screen, tree_view

workspace = Screen(id="workspace", scroll=True)

tree_view(
    [
        {
            "key": "product",
            "title": "Product",
            "subtitle": "18 pages",
            "children": [
                {
                    "key": "roadmap",
                    "title": "Roadmap",
                    "subtitle": "Q3 planning",
                    "children": [
                        {"title": "Mobile foundations", "subtitle": "In review"},
                        {"title": "Offline mode", "subtitle": "Draft"},
                    ],
                },
                {"title": "Release notes", "subtitle": "12 entries"},
            ],
        },
        {
            "key": "archive",
            "title": "Archive",
            "subtitle": "Collapsed by default",
            "expanded": False,
            "children": [
                {"title": "2025", "subtitle": "31 documents"},
                {"title": "2024", "subtitle": "19 documents"},
            ],
        },
    ],
    id="workspace_tree",
    expand_depth=1,
    row_height=60,
    screen=workspace,
)
~~~

Android keeps one flat adapter list containing only the rows currently visible.
Opening a branch adds its direct visible descendants; closing it removes them.
Collapsed subtrees are not inflated into hidden Views.

## App pattern: API or SQLite knowledge base

The content source and the renderer stay separate:

1. fetch or query the records;
2. validate them into the node/span schema;
3. render the document or hierarchy;
4. let the Android adapter manage visible rows.

For an API, return a normal JSON object whose nested `children` fields match the
tree schema. For SQLite, rebuild the hierarchy from parent IDs before creating
`tree_view()`. ApkPy does not silently upload document contents or coordinates,
and it does not add a JavaScript runtime.

## Previewer and Android parity

- Text remains selectable when `selectable=True`.
- Explicit span sizes, wrapping, card padding and content height are measured
  independently for each viewport.
- Android links use native URL spans.
- Tree rows use stable IDs and a recycled native adapter.
- Preview and Android use the same normalized content model, but final device
  testing is still recommended for font metrics and accessibility scale.

## Complete app examples

The repository contains two runnable starting points:

- `examples/16_knowledge_base.py` combines all three components in a compact
  native knowledge browser.
- `examples/17_discussion_tree.py` demonstrates a formatted post and nested
  discussion structure.

Copy either file into an ApkPy project, run it with Python for the Previewer,
then use `apkpy build` and inspect the generated Android project.
