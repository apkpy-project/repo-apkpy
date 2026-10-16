"""Regression coverage for incremental virtual collections."""

import unittest

import apkpy_lib
from apkpy_lib.core.compiler import translate_python_to_android


PAGINATED_SOURCE = r'''
from apkpy_lib import Screen, button, virtual_collection

home = Screen(id="home")

def load_more():
    feed.append_items([
        {"author": "Nova", "message": "An incremental row", "time": "now"},
        {"author": "Orion", "message": "No full rebuild", "time": "1m"},
    ], has_more=False)

def reload_feed():
    feed.set_items([
        {"author": "Fresh", "message": "Reloaded", "time": "now"},
    ], has_more=True)

feed = virtual_collection(
    [{"author": "Ada", "message": "First", "time": "2m"}],
    template={
        "title": "{author}",
        "subtitle": "{message}",
        "meta": "{time}",
    },
    on_end_reached=load_more,
    on_refresh=reload_feed,
    prefetch=4,
    screen=home,
)

def retry():
    feed.finish_load(has_more=True)
    feed.refresh()

button("Retry", command=retry, screen=home)
button("Refresh now", command=feed.refresh, screen=home)
'''

MUTATION_SOURCE = r'''
from apkpy_lib import Screen, button, virtual_collection

home = Screen(id="home")

def prepend():
    feed.prepend_items([{"id": "new", "title": "New"}])

def mutate():
    feed.update_item(
        "a", {"liked": True, "likes": 5}, optimistic="like-a"
    )
    feed.remove_item("b", optimistic="delete-b")
    feed.merge_items([
        {"id": "a", "title": "Alpha live"},
        {"id": "c", "title": "Gamma"},
    ])

def undo():
    feed.rollback("delete-b")
    feed.commit("like-a")

feed = virtual_collection(
    [
        {"id": "a", "title": "Alpha"},
        {"id": "b", "title": "Beta"},
    ],
    screen=home,
)
button("Prepend", command=prepend, screen=home)
button("Mutate", command=mutate, screen=home)
button("Undo", command=undo, screen=home)
'''


class FeedRuntimeTests(unittest.TestCase):
    def test_custom_template_omits_undeclared_visual_slots(self):
        screen = apkpy_lib.Screen(id="custom-template")
        feed = apkpy_lib.virtual_collection(
            [{"title": "Text only"}],
            template={"title": "{title}"},
            screen=screen,
        )
        self.assertEqual(feed.kwargs["template"]["title"], "{title}")
        self.assertEqual(feed.kwargs["template"]["image"], "")
        self.assertEqual(feed.kwargs["template"]["subtitle"], "")

        default_feed = apkpy_lib.virtual_collection(
            [{"title": "Default", "image": "cover.png"}],
            screen=screen,
        )
        self.assertEqual(default_feed.kwargs["template"]["image"], "{image}")

    def test_loading_latch_append_refresh_and_has_more(self):
        screen = apkpy_lib.Screen(id="feed-runtime")
        events = []
        feed = None

        def load_more():
            events.append("end")

        def refresh():
            events.append("refresh")

        feed = apkpy_lib.virtual_collection(
            [{"id": 1}],
            on_end_reached=load_more,
            on_refresh=refresh,
            screen=screen,
        )

        from apkpy_lib.features import feeds

        self.assertTrue(feeds.request_end(feed))
        self.assertFalse(feeds.request_end(feed))
        self.assertEqual(events, ["end"])
        self.assertEqual(feed.append_items([{"id": 2}], has_more=False), 1)
        self.assertFalse(feeds.request_end(feed))
        self.assertEqual(feed._initial_value, [{"id": 1}, {"id": 2}])

        self.assertTrue(feed.refresh())
        self.assertFalse(feed.refresh())
        self.assertEqual(events, ["end", "refresh"])
        feed.set_items([{"id": 3}], has_more=True)
        self.assertEqual(feed._initial_value, [{"id": 3}])
        self.assertTrue(feeds.state_for(feed)["has_more"])

    def test_keyed_mutations_merge_and_optimistic_history(self):
        screen = apkpy_lib.Screen(id="feed-mutations")
        feed = apkpy_lib.virtual_collection(
            [
                {"id": "a", "title": "Alpha", "likes": 1},
                {"id": "b", "title": "Beta", "likes": 2},
            ],
            screen=screen,
        )

        self.assertEqual(
            feed.prepend_items([{"id": "new", "title": "New"}]), 1
        )
        self.assertEqual(
            [row["id"] for row in feed._initial_value],
            ["new", "a", "b"],
        )

        self.assertTrue(feed.update_item(
            "a", {"likes": 2}, optimistic="like-a"
        ))
        self.assertTrue(feed.remove_item(
            "b", optimistic="delete-b"
        ))
        self.assertEqual(
            [row["id"] for row in feed._initial_value], ["new", "a"]
        )
        self.assertTrue(feed.rollback("delete-b"))
        self.assertEqual(
            [row["id"] for row in feed._initial_value], ["new", "a", "b"]
        )
        self.assertTrue(feed.commit("like-a"))
        self.assertFalse(feed.rollback("like-a"))
        self.assertEqual(feed._initial_value[1]["likes"], 2)

        self.assertEqual(feed.merge_items([
            {"id": "a", "title": "Alpha live", "likes": 3},
            {"id": "c", "title": "Gamma", "likes": 0},
        ]), 2)
        self.assertEqual(
            [row["id"] for row in feed._initial_value],
            ["new", "a", "b", "c"],
        )
        self.assertEqual(feed._initial_value[1]["title"], "Alpha live")

    def test_reused_optimistic_token_keeps_first_snapshot(self):
        screen = apkpy_lib.Screen(id="feed-transaction")
        feed = apkpy_lib.virtual_collection(
            [{"id": 1, "liked": False, "likes": 4}], screen=screen
        )
        feed.update_item(1, {"liked": True}, optimistic="like-1")
        feed.update_item(1, {"likes": 5}, optimistic="like-1")
        self.assertTrue(feed.rollback("like-1"))
        self.assertEqual(
            feed._initial_value,
            [{"id": 1, "liked": False, "likes": 4}],
        )

    def test_android_uses_incremental_notifications_and_refresh(self):
        files = translate_python_to_android(
            PAGINATED_SOURCE, "com.example.feeds"
        )
        java = files["java/Screen_homeActivity.java"]
        layout = files["res/layout/activity_screen_home.xml"]

        self.assertIn("new RecyclerView.OnScrollListener()", java)
        self.assertIn("notifyItemRangeInserted", java)
        self.assertIn("vc1Loading || !vc1HasMore", java)
        self.assertIn("_apkpyRequestVc1Refresh", java)
        self.assertIn("findLastVisibleItemPosition", java)
        self.assertIn("post(() -> _apkpyMaybeLoadVc1Page())", java)
        self.assertNotIn("post(this::_apkpyMaybeLoadVc1Page)", java)
        self.assertIn("btn2.setOnClickListener", java)
        self.assertIn('vc1_template.put("image", "")', java)
        self.assertNotIn('vc1_template.put("image", "{image}")', java)
        self.assertIn(
            "androidx.swiperefreshlayout.widget.SwipeRefreshLayout", layout
        )
        self.assertIn('android:id="@+id/vc1_loading"', layout)

    def test_android_emits_targeted_mutations_diff_and_rollback(self):
        files = translate_python_to_android(
            MUTATION_SOURCE, "com.example.mutations"
        )
        java = files["java/Screen_homeActivity.java"]

        self.assertIn("notifyItemRangeInserted(0,", java)
        self.assertIn("notifyItemChanged(", java)
        self.assertIn("notifyItemRemoved(", java)
        self.assertIn("DiffUtil.calculateDiff", java)
        self.assertIn("_apkpyVcApplyDiff", java)
        self.assertIn("vc1Optimistic", java)
        self.assertIn("vc1OptimisticKeys", java)
        self.assertIn("private RecyclerView vc1;", java)
        self.assertIn("vc1 = findViewById(R.id.vc1);", java)
        self.assertNotIn(
            "RecyclerView vc1 = findViewById(R.id.vc1);", java
        )
        self.assertIn('\"like-a\"', java)
        self.assertIn('\"delete-b\"', java)

    def test_plain_virtual_collection_has_no_pagination_runtime(self):
        files = translate_python_to_android(
            'from apkpy_lib import Screen, virtual_collection\n'
            'home = Screen(id="home")\n'
            'virtual_collection([{"title": "One"}], screen=home)\n'
        )
        java = files["java/Screen_homeActivity.java"]
        layout = files["res/layout/activity_screen_home.xml"]

        self.assertNotIn("OnScrollListener", java)
        self.assertNotIn("notifyItemRangeInserted", java)
        self.assertNotIn("SwipeRefreshLayout", java)
        self.assertNotIn("SwipeRefreshLayout", layout)
        self.assertNotIn("vc1Loading", java)
        self.assertNotIn("DiffUtil", java)
        self.assertNotIn("Optimistic", java)


if __name__ == "__main__":
    unittest.main()
