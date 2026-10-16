"""Regression coverage for native rich text, Markdown and tree views."""

import base64
import json
import re
import unittest

import apkpy_lib
from apkpy_lib.core.compiler import translate_python_to_android


SOURCE = r'''
from apkpy_lib import Screen, markdown, rich_text, tree_view

home = Screen(id="home", scroll=True)

rich_text([
    {"text": "FIELD NOTE\n", "bold": True, "color": "#22D3EE", "size": 12},
    {"text": "Structured content without a WebView.", "bold": True, "size": 24},
], id="lead", screen=home)

markdown("""## Release notes

> Native text stays searchable and selectable.

- [x] headings and lists
- [x] **bold**, *italic* and `inline code`
""", id="notes", screen=home)

tree_view([
    {
        "key": "workspace",
        "title": "Workspace",
        "subtitle": "3 collections",
        "children": [
            {"title": "Design system", "subtitle": "12 pages"},
            {
                "title": "Research",
                "children": [{"title": "Interviews"}],
            },
        ],
    },
], id="knowledge_tree", expand_depth=1, row_height=60, screen=home)
'''


class RichContentTests(unittest.TestCase):
    def test_public_api_and_runtime_models(self):
        self.assertTrue(callable(apkpy_lib.markdown))
        self.assertTrue(callable(apkpy_lib.rich_text))
        self.assertTrue(callable(apkpy_lib.tree_view))

        screen = apkpy_lib.Screen(id="runtime")
        apkpy_lib.markdown("# One", screen=screen)
        apkpy_lib.rich_text([{"text": "Two", "bold": True}], screen=screen)
        tree = apkpy_lib.tree_view(
            [{"title": "Root", "children": [{"title": "Child"}]}],
            screen=screen,
        )

        self.assertEqual(
            [component.comp_type for component in screen.components],
            ["markdown", "rich_text", "tree_view"],
        )
        self.assertTrue(tree.kwargs["nodes"][0]["expanded"])

    def test_android_uses_native_views_and_encoded_content(self):
        files = translate_python_to_android(SOURCE, "com.example.rich")

        layout = files["res/layout/activity_screen_home.xml"]
        rich_java = files["java/ApkpyRichContentView.java"]
        tree_java = files["java/ApkpyTreeView.java"]

        self.assertIn("com.example.rich.ApkpyRichContentView", layout)
        self.assertIn("com.example.rich.ApkpyTreeView", layout)
        self.assertIn("androidx.recyclerview.widget.RecyclerView", tree_java)
        self.assertIn("SpannableStringBuilder", rich_java)
        self.assertNotIn("WebView", rich_java)
        self.assertIn("private static final Pattern ORDERED", rich_java)
        self.assertIn("rebuildVisible()", tree_java)
        self.assertIn("notifyDataSetChanged()", tree_java)

        encoded = re.search(
            r'contentDescription="apkpy-tree:([^"]+)"', layout
        ).group(1)
        payload = json.loads(base64.b64decode(encoded).decode("utf-8"))
        self.assertEqual(payload["nodes"][0]["title"], "Workspace")
        self.assertEqual(payload["nodes"][0]["children"][0]["title"], "Design system")
        self.assertEqual(payload["rowHeight"], 60)

    def test_plain_projects_do_not_ship_rich_content_runtime(self):
        files = translate_python_to_android(
            'from apkpy_lib import Screen, label\n'
            'home = Screen(id="home")\n'
            'label("Plain", screen=home)\n'
        )
        self.assertNotIn("java/ApkpyRichContentView.java", files)
        self.assertNotIn("java/ApkpyTreeView.java", files)


if __name__ == "__main__":
    unittest.main()
