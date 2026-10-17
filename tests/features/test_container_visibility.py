# -*- coding: utf-8 -*-
"""hide() and show() on a container, in the Previewer.

On the phone a hidden container is GONE: it takes no room, its margin and
the gap before it go with it, and what follows moves up. In the Previewer
hide() used to act on the frame the children are in. For a container with
rounded corners that frame is a window inside a canvas, which the call did
nothing to -- the box stayed where it was -- and the show() after it packed
the frame out of the canvas: half the width, in the middle, over the shape.
Found by looking at a picture of an app with a banner that would not go.

These hold the whole box going and coming back to the same place and size.
"""

import unittest

from test_real_screens import Previewed

APP = ('home = Screen(id="home", scroll=%(scroll)s)\n'
       'label("Title", id="title", screen=home)\n'
       'banner = container(id="banner", screen=home)\n'
       'label("No connection", id="banner_title", parent=banner)\n'
       'label("What you send waits here.", id="banner_text", parent=banner)\n'
       'card = container(id="card", screen=home)\n'
       'label("Card", id="card_title", parent=card)\n'
       '%(more)s')
CSS = ('home { background-color: #FFFFFF; padding: 24px; %(gap)s }\n'
       'banner { background-color: #B3261E; %(radius)s padding: 14px 4px; gap: 2px; }\n'
       'banner_title { color: #FFFFFF; font-weight: bold; }\n'
       'banner_text { color: #FFFFFF; }\n'
       'card { background-color: #EEEEEE; border-radius: 18px; padding: 18px 4px; }\n')
SHAPES = {"round": "border-radius: 18px;", "square": ""}
GAPS = ("gap: 14px;", "")


def _box(shown, name):
    """(drawn, x, y, width, height) of a component's own frame in the window."""
    widget, root = shown.ns[name].widget, shown.app.root
    return (bool(widget.winfo_viewable()),
            widget.winfo_rootx() - root.winfo_rootx(), widget.winfo_rooty() - root.winfo_rooty(),
            widget.winfo_width(), widget.winfo_height())


def _unmapped(shown, name):
    """Which frames, from the component up, are not mapped: the message a
    failed "drawn" check carries, since a machine without a screen (the CI's
    Xvfb) is where it has failed and nobody can look at it there."""
    widget, chain = shown.ns[name].widget, []
    while widget is not None:
        if not widget.winfo_ismapped():
            chain.append("%s [%s]" % (widget, widget.winfo_manager() or "no manager"))
        widget = widget.master
    return "%s not mapped: %s" % (name, ", ".join(chain) or "nothing")


class AContainerHiddenAndShown(unittest.TestCase):

    def _each(self, more=""):
        for shape, radius in SHAPES.items():
            for gap in GAPS:
                with self.subTest(shape=shape, gap=gap or "no gap"):
                    with Previewed(APP % {"scroll": "True", "more": more},
                                   CSS % {"gap": gap, "radius": radius}) as shown:
                        try:
                            yield shown
                        except GeneratorExit:
                            # The test failed and let go of the loop. Close
                            # the window and stop; left to subTest, the exit
                            # was reported as an error of its own and the loop
                            # opened the next case.
                            return

    def test_it_goes_and_what_follows_takes_its_place(self):
        for shown in self._each():
            banner, card = _box(shown, "banner"), _box(shown, "card")
            self.assertTrue(banner[0])
            shown.ns["banner"].hide()
            shown.settle(0.35)
            self.assertFalse(_box(shown, "banner")[0])
            moved = _box(shown, "card")
            self.assertTrue(moved[0])
            # Up by the whole box: its height, and the gap that was before it.
            self.assertLess(moved[2], card[2] - banner[4] + 1)
            self.assertEqual(moved[1], card[1])
            self.assertEqual(moved[3:], card[3:])

    def test_it_comes_back_to_the_same_place_and_size(self):
        for shown in self._each():
            banner, card = _box(shown, "banner"), _box(shown, "card")
            for _again in range(2):
                shown.ns["banner"].hide()
                shown.settle(0.35)
                shown.ns["banner"].show()
                shown.settle(0.35)
                self.assertEqual(_box(shown, "banner"), banner)
                self.assertEqual(_box(shown, "card"), card)
            # And it is still where its parent laid it out: among the
            # children it was made between, not after them.
            self.assertLess(_box(shown, "banner")[2], _box(shown, "card")[2])

    def test_hidden_as_the_screen_opens(self):
        more = 'def opened():\n    banner.hide()\nlifecycle(home, on_mount=opened)\n'
        for shown in self._each(more):
            self.assertFalse(_box(shown, "banner")[0])
            hidden = _box(shown, "card")
            shown.ns["banner"].show()
            shown.settle(0.35)
            banner, card = _box(shown, "banner"), _box(shown, "card")
            self.assertTrue(banner[0])
            self.assertGreater(card[2], hidden[2] + banner[4] - 1)
            self.assertLess(banner[2], card[2])

    def test_bound_to_a_state_it_starts_hidden_and_follows_it(self):
        more = 'online = state(True)\nonline.bind_visibility(banner, when=False)\n'
        for shown in self._each(more):
            self.assertFalse(_box(shown, "banner")[0])
            hidden = _box(shown, "card")
            shown.ns["online"].set(False)
            shown.settle(0.35)
            banner = _box(shown, "banner")
            self.assertTrue(banner[0])
            self.assertLess(banner[2], _box(shown, "card")[2])
            shown.ns["online"].set(True)
            shown.settle(0.35)
            self.assertFalse(_box(shown, "banner")[0])
            self.assertEqual(_box(shown, "card"), hidden, _unmapped(shown, "card"))

    def test_the_last_of_its_siblings_comes_back_last(self):
        # On a screen that does not scroll, too.
        with Previewed(APP % {"scroll": "False", "more": ""},
                       CSS % {"gap": "gap: 14px;", "radius": "border-radius: 18px;"}) as shown:
            card = _box(shown, "card")
            shown.ns["card"].hide()
            shown.settle(0.35)
            self.assertFalse(_box(shown, "card")[0])
            shown.ns["card"].show()
            shown.settle(0.35)
            self.assertEqual(_box(shown, "card"), card)


if __name__ == "__main__":
    unittest.main()
