"""ApkPy 1.2 example: native knowledge base without a WebView."""

from apkpy_lib import Screen, app_bar, action, markdown, rich_text, run, tree_view


home = Screen(id="knowledge", scroll=True)
app_bar(
    title="Knowledge Lab",
    actions=[action("search", label="Search documents")],
    screen=home,
)

rich_text(
    [
        {
            "text": "FIELD NOTE  /  04\n",
            "bold": True,
            "color": "#22D3EE",
            "size": 12,
        },
        {"text": "Small interfaces, ", "bold": True, "size": 23},
        {
            "text": "deep structure.",
            "bold": True,
            "italic": True,
            "color": "#C4B5FD",
            "size": 23,
        },
        {
            "text": "\nNative text remains selectable and readable.",
            "color": "#A1A1AA",
            "size": 14,
        },
    ],
    id="knowledge_lead",
    selectable=True,
    screen=home,
)

markdown(
    """## Build log · 1.2

> Content stays native on Android.

- [x] Headings, quotes and dividers
- [x] **Bold**, *italic*, ~~strike~~ and `inline code`
- [x] Ordered lists and task lists
- [ ] Connect the renderer to your own storage

### Architecture

There is no WebView and no JavaScript runtime in this screen.
""",
    id="knowledge_document",
    screen=home,
)

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
            "key": "research",
            "title": "Research",
            "subtitle": "7 collections",
            "children": [
                {"title": "Field interviews", "subtitle": "24 recordings"},
                {"title": "Usability sessions", "subtitle": "9 reports"},
            ],
        },
    ],
    id="workspace_tree",
    expand_depth=1,
    row_height=60,
    screen=home,
)

style = """
knowledge {
    background-color: #08090B;
    color: #F7F7F8;
    padding: 20px;
}
knowledge_lead, knowledge_document, workspace_tree {
    background-color: #17181C;
    border-color: #3F3F46;
    border-width: 1px;
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 16px;
}
"""


if __name__ == "__main__":
    run(start_screen=home)
