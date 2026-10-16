# -*- coding: utf-8 -*-
"""AGENTS.md: what an AI coding assistant is told about ApkPy.

No model knows ApkPy from its training, so each project tells the assistant
working in it. What it is told has to be true today: the example has to build,
every API it names has to exist, and every code it cites has to be one the
library raises. A guide that drifts teaches the assistant to write code that
does not build -- worse than no guide.
"""

import os
import re
import tempfile
import unittest
from pathlib import Path

import apkpy_lib
from apkpy_lib import agents_guide
from apkpy_lib.core.compiler import translate_python_to_android

ROOT = Path(__file__).resolve().parents[2]
GUIDE = agents_guide.render("9.9.9")


def _section(title):
    start = GUIDE.index("## " + title)
    end = GUIDE.find("\n## ", start + 1)
    return GUIDE[start:end if end != -1 else len(GUIDE)]


class TheGuideIsTrue(unittest.TestCase):

    def test_the_example_builds_and_keeps_its_logic(self):
        code = re.search(r"```python\n(.*?)```", GUIDE, re.S).group(1)
        files = translate_python_to_android(code)
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:400])
        activity = files["java/Screen_homeActivity.java"]
        self.assertIn('"Type a name first"', activity)
        self.assertIn('"Hello, " + String.valueOf(value)', activity)
        self.assertIn('putExtra("from"', activity)

    def test_the_list_example_hands_the_tapped_row_to_its_callback(self):
        """The pattern both test agents missed: a row's column read in the
        click callback. It is what found the dropped subscript on list_view
        (fixed in 1.11.0, tests/features/test_rows_and_other_screens.py)."""
        blocks = re.findall(r"```python\n(.*?)```", GUIDE, re.S)
        self.assertEqual(len(blocks), 2)
        files = translate_python_to_android(blocks[1])
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:400])
        activity = files["java/Screen_homeActivity.java"]
        self.assertIn('_jsonGet(String.valueOf(item), "id")', activity)
        self.assertIn('new java.text.SimpleDateFormat("yyyy-MM-dd"', activity)

    def test_the_icon_names_are_the_catalogue(self):
        # Every name it shows draws, and the short list is all there. Any
        # Material Icons name draws since the full set shipped.
        from apkpy_lib import icons
        listed = set(re.findall(r"`([a-z0-9_]+)`", _section("Icons"))) - {"icon", "icons"}
        self.assertEqual([n for n in sorted(listed) if icons.resolve(n) is None], [])
        self.assertLessEqual(set(icons.names()), listed)
        for material in ("share", "chat_bubble_outline", "favorite_border", "cameraswitch"):
            self.assertIn(material, listed)

    def test_every_api_it_names_exists(self):
        names = set(re.findall(r"`([a-z_]+)[`(]", _section("APIs to reach for")))
        names |= set(re.findall(r"`([a-z_]+)\(", _section("The shape of an app")))
        missing = sorted(n for n in names if n not in apkpy_lib.__all__)
        self.assertEqual(missing, [])

    def test_every_code_it_cites_is_raised_somewhere(self):
        codes = set(re.findall(r"`([A-Z][0-9]{4})`", GUIDE))
        self.assertTrue({"U2001", "U2033", "U2037", "U2038", "J7004", "J7005"} <= codes)
        source = "\n".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in (ROOT / "apkpy_lib").rglob("*.py"))
        self.assertEqual(sorted(c for c in codes if c not in source), [])

    def test_it_points_at_pages_that_exist(self):
        docs = ROOT / "website" / "docs"
        if not docs.exists():
            self.skipTest("the site source is not in this checkout")
        for path in re.findall(re.escape(agents_guide.DOCS) + r"/([a-z0-9/._-]*)", GUIDE):
            path = path.rstrip("/")
            page = docs / (path if path.endswith(".txt") else path + ".md")
            self.assertTrue(page.exists(), path)

    def test_it_says_which_version_it_was_written_for(self):
        self.assertIn("written for apkpy 9.9.9", GUIDE)


DOCS_DIR = ROOT / "website" / "docs"


@unittest.skipUnless(DOCS_DIR.exists(), "the site source is not in this checkout")
class TheSiteFilesAreTrue(unittest.TestCase):
    """llms.txt is what an assistant with web access reads first, and
    llms-full.txt is what AGENTS.md sends it to. A dead link or a stale copy
    teaches it something the site no longer says."""

    def test_every_link_in_llms_txt_is_a_page(self):
        text = (DOCS_DIR / "llms.txt").read_text(encoding="utf-8")
        paths = re.findall(re.escape(agents_guide.DOCS) + r"/([a-z0-9/._-]*)\)", text)
        self.assertGreater(len(paths), 20)
        for path in paths:
            path = path.rstrip("/")
            page = DOCS_DIR / (path if path.endswith(".txt") else path + ".md")
            self.assertTrue(page.exists(), path)

    def test_llms_txt_names_the_release_the_package_is(self):
        text = (DOCS_DIR / "llms.txt").read_text(encoding="utf-8")
        setup = (ROOT / "setup.py").read_text(encoding="utf-8")
        package = re.search(r"version='([^']+)'", setup).group(1)
        stated = re.search(r"Latest release: ([0-9.]+)\.", text).group(1)
        # The site goes out after PyPI, so between releases llms.txt may be one
        # ahead of setup.py -- never behind it.
        as_tuple = lambda v: tuple(int(p) for p in v.split("."))
        self.assertGreaterEqual(as_tuple(stated), as_tuple(package))

    def test_the_home_page_announces_no_release_but_the_current_one(self):
        # The home page said "ApkPy 1.7.0 · available now" through three
        # later releases, and the structured data told search engines 1.5.0.
        # One number, mkdocs.yml's apkpy_version, is the site's release; the
        # home page may announce that one, or none -- never an older one.
        mkdocs = (DOCS_DIR.parent / "mkdocs.yml").read_text(encoding="utf-8")
        site = re.search(r'apkpy_version:\s*"([0-9.]+)"', mkdocs).group(1)
        setup = (ROOT / "setup.py").read_text(encoding="utf-8")
        package = re.search(r"version='([^']+)'", setup).group(1)
        as_tuple = lambda v: tuple(int(p) for p in v.split("."))
        self.assertGreaterEqual(as_tuple(site), as_tuple(package))
        index = (DOCS_DIR / "index.md").read_text(encoding="utf-8")
        lines = re.findall(r'<div class="release-line">(.*?)</div>', index, re.S)
        self.assertLessEqual(len(lines), 1, "announce one release at most")
        for line in lines:
            # A correction (1.12.1) brings nothing to announce: the line goes
            # on naming the release whose features it lists (1.12.0), which
            # is the same series and never ahead of the site.
            named = set(re.findall(r"\d+\.\d+\.\d+", line))
            self.assertEqual(len(named), 1, line)
            announced = as_tuple(named.pop())
            self.assertEqual(announced[:2], as_tuple(site)[:2], line)
            self.assertLessEqual(announced, as_tuple(site), line)

    def test_the_code_on_the_social_card_compiles(self):
        # The card every shared link shows used to print `from apkpy import
        # App, View` -- an API ApkPy never had. It is drawn from this file now.
        snippet = (ROOT / "tools" / "social_card_snippet.py").read_text(encoding="utf-8")
        files = translate_python_to_android(snippet)
        self.assertNotIn("error.txt", files or {"error.txt": "no output"})

    def test_llms_full_txt_is_built_from_the_pages_as_they_are(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_llms_full", ROOT / "tools" / "build_llms_full.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        on_disk = (DOCS_DIR / "llms-full.txt").read_text(encoding="utf-8")
        self.assertEqual(on_disk, builder.build(),
                         "stale: run python tools/build_llms_full.py")


class TheirFilesAreTheirs(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _read(self, name):
        return Path(self.dir, name).read_text(encoding="utf-8")

    def test_a_new_project_gets_both_files(self):
        self.assertEqual(agents_guide.write(self.dir, version="1.0"),
                         [("AGENTS.md", "created"), ("CLAUDE.md", "created")])
        self.assertIn("@AGENTS.md", self._read("CLAUDE.md"))

    def test_writing_twice_changes_nothing(self):
        agents_guide.write(self.dir, version="1.0")
        self.assertEqual(agents_guide.write(self.dir, version="1.0"),
                         [("AGENTS.md", "up to date"), ("CLAUDE.md", "up to date")])

    def test_an_untouched_guide_follows_the_installed_version(self):
        agents_guide.write(self.dir, version="1.0")
        result = agents_guide.write(self.dir, version="2.0")
        self.assertEqual(result[0], ("AGENTS.md", "updated"))
        self.assertIn("written for apkpy 2.0", self._read("AGENTS.md"))

    def test_an_edited_guide_is_kept(self):
        agents_guide.write(self.dir, version="1.0")
        with open(os.path.join(self.dir, "AGENTS.md"), "a", encoding="utf-8") as f:
            f.write("\nOur own rule.\n")
        self.assertEqual(agents_guide.write(self.dir, version="2.0")[0],
                         ("AGENTS.md", "kept"))
        self.assertIn("Our own rule.", self._read("AGENTS.md"))

    def test_force_replaces_it(self):
        Path(self.dir, "AGENTS.md").write_text("mine", encoding="utf-8")
        self.assertEqual(agents_guide.write(self.dir, force=True, version="1.0")[0],
                         ("AGENTS.md", "updated"))
        self.assertTrue(agents_guide.is_untouched(self._read("AGENTS.md")))

    def test_someone_elses_claude_md_is_never_rewritten(self):
        Path(self.dir, "CLAUDE.md").write_text("our rules\n", encoding="utf-8")
        self.assertEqual(agents_guide.write(self.dir, version="1.0")[1],
                         ("CLAUDE.md", "kept"))
        self.assertEqual(self._read("CLAUDE.md"), "our rules\n")


if __name__ == "__main__":
    unittest.main()
