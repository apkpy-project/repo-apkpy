"""ApkPy 1.2 example: formatted post with a nested discussion tree."""

from apkpy_lib import Screen, app_bar, markdown, rich_text, run, tree_view


thread = Screen(id="thread", scroll=True)
app_bar(title="Design Systems", screen=thread)

rich_text(
    [
        {"text": "ENGINEERING  /  8 MIN READ\n", "bold": True,
         "color": "#34D399", "size": 12},
        {"text": "Why native text still matters", "bold": True, "size": 24},
        {"text": "\nA discussion screen can stay structured without a browser.",
         "color": "#A1A1AA", "size": 14},
    ],
    id="post_header",
    screen=thread,
)

markdown(
    """## One data model, two feedback loops

The desktop Previewer keeps iteration fast. The Android build turns the same
content into **native spans** and recycled rows.

> The renderer handles presentation. Your API, SQLite schema and moderation
> policy remain application code.

1. Load the post.
2. Validate the comment tree.
3. Render only the branches the reader opens.
""",
    id="post_body",
    screen=thread,
)

tree_view(
    [
        {
            "key": "comment-104",
            "title": "Avery · 12 min",
            "subtitle": "The visible-row adapter is the important part.",
            "children": [
                {
                    "key": "comment-105",
                    "title": "Mika · 8 min",
                    "subtitle": "It also keeps deeply nested threads responsive.",
                    "children": [
                        {
                            "key": "comment-106",
                            "title": "Sam · 3 min",
                            "subtitle": "And collapsed replies allocate no row.",
                        }
                    ],
                }
            ],
        },
        {
            "key": "comment-107",
            "title": "Jordan · 5 min",
            "subtitle": "Selectable text is useful for technical discussions.",
        },
    ],
    id="comment_tree",
    expand_depth=1,
    row_height=68,
    screen=thread,
)

style = """
thread {
    background-color: #0B0D10;
    color: #F5F7FA;
    padding: 20px;
}
post_header, post_body, comment_tree {
    background-color: #15181D;
    border-color: #323842;
    border-width: 1px;
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 16px;
}
"""


if __name__ == "__main__":
    run(start_screen=thread)
