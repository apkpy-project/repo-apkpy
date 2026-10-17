# -*- coding: utf-8 -*-
"""ApkPy's own code has to import on every Python setup.py names.

Python 3.12 let f-strings hold, inside their braces, a backslash, a comment,
a line break and the quote that encloses them (PEP 701). Code written that
way imports on 3.12 and later and is a SyntaxError before: two such lines,
in the Data Core migrations and in the Gradle writer, left `apkpy` unable to
start on Python 3.8 to 3.11 from 1.5.0 to 1.13.0, while every suite here --
run on 3.13 -- was green.

On an older Python every file is compiled, which is the real test. On 3.12
and later the compiler accepts all of it, so the tokenizer, which marks where
each f-string and each of its fields starts and ends, is asked instead.
"""

import io
import sys
import tokenize
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CHECKED = ("apkpy_lib", "tests", "setup.py")


def _sources():
    for name in CHECKED:
        path = ROOT / name
        if path.is_file():
            yield path
        elif path.is_dir():
            for source in sorted(path.rglob("*.py")):
                if "__pycache__" not in source.parts:
                    yield source


def _quote(token_text):
    text = token_text.lstrip("rRbBuUfF")
    for quote in ('"""', "'''", '"', "'"):
        if text.startswith(quote):
            return quote
    return ""


def _closes(inner, outer):
    """Would a string opened with ``inner`` have ended ``outer`` before 3.12?

    The whole f-string used to be read as one string first, so any quote that
    ends it ended it there: one double quote inside a double-quoted f-string,
    three inside a triple-quoted one -- but a single double quote inside a
    triple-quoted f-string was always fine.
    """
    if not inner:
        return False
    if len(outer) == 3:
        return inner == outer
    return inner[0] == outer


def newer_than_3_11(source):
    """[(line, why)] for each f-string only Python 3.12 and later can read."""
    found = []
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    # One entry per open f-string: its quote, and how many of its fields are
    # open. An f-string that opens while another is open is inside one of
    # that one's fields, since its text part cannot hold one.
    stack = []
    for token in tokens:
        kind, text, line = token.type, token.string, token.start[0]
        if kind == tokenize.FSTRING_START:
            quote = _quote(text)
            if any(_closes(quote, outer) for outer, _depth in stack):
                found.append((line, "an f-string inside a field reuses the outer quote"))
            stack.append([quote, 0])
            continue
        if not stack:
            continue
        if kind == tokenize.FSTRING_END:
            stack.pop()
            continue
        top = stack[-1]
        if kind == tokenize.FSTRING_MIDDLE:
            if len(stack) > 1 and "\\" in text:
                found.append((line, "a backslash in an f-string inside a field"))
            continue
        if kind == tokenize.OP and text == "{":
            top[1] += 1
            continue
        if kind == tokenize.OP and text == "}":
            top[1] = max(0, top[1] - 1)
            continue
        if top[1] == 0:
            continue
        if kind == tokenize.STRING:
            if any(_closes(_quote(text), outer) for outer, _depth in stack):
                found.append((line, "a string in a field reuses the f-string's quote"))
            if "\\" in text:
                found.append((line, "a backslash in a field"))
        elif kind == tokenize.COMMENT:
            found.append((line, "a comment in a field"))
        elif kind in (tokenize.NL, tokenize.NEWLINE) and any(
                len(outer) == 1 for outer, _depth in stack):
            found.append((line, "a line break in a one-line f-string"))
    return found


class EveryFileImportsOnTheOldestPython(unittest.TestCase):

    @unittest.skipIf(sys.version_info >= (3, 12), "3.12 compiles all of it; the tokenizer test below asks")
    def test_every_file_compiles_here(self):
        for path in _sources():
            with self.subTest(path=str(path.relative_to(ROOT))):
                compile(path.read_text(encoding="utf-8"), str(path), "exec")

    @unittest.skipUnless(sys.version_info >= (3, 12), "the f-string tokens came in 3.12")
    def test_no_f_string_needs_3_12(self):
        found = []
        for path in _sources():
            for line, why in sorted(set(newer_than_3_11(path.read_text(encoding="utf-8")))):
                found.append("%s:%d  %s" % (path.relative_to(ROOT), line, why))
        self.assertEqual(found, [], "\n" + "\n".join(found))

    @unittest.skipUnless(sys.version_info >= (3, 12), "the f-string tokens came in 3.12")
    def test_the_check_sees_each_kind(self):
        bad = {
            "a backslash in a field": 'x = f"{chr(10).join([\'\\\\n\'])}"\n',
            "a string in a field reuses the f-string's quote": 'x = f"{d["k"]}"\n',
            "a comment in a field": 'x = f"""{1 # one\n}"""\n',
            "a line break in a one-line f-string": 'x = f"{1 +\n 2}"\n',
            "an f-string inside a field reuses the outer quote": 'x = f"{f"{1}"}"\n',
            "a backslash in an f-string inside a field": "x = f\"{f'a\\\\tb'}\"\n",
        }
        for why, source in bad.items():
            with self.subTest(why=why):
                self.assertIn(why, [found for _line, found in newer_than_3_11(source)])
        fine = (
            'x = f"{d[\'k\']}"\n',
            'x = f"""{d["k"]}"""\n',
            'x = f"""{1 +\n 2}"""\n',
            "x = f\"{f'{1}'}\"\n",
            'x = f"a\\tb {1}"\n',
            'x = f"{{literal}} {1:>{width}}"\n',
        )
        for source in fine:
            with self.subTest(source=source):
                self.assertEqual(newer_than_3_11(source), [])


class TheMessagesQuoteTheCodeOnPython38(unittest.TestCase):
    """ast.unparse() is Python 3.9 and later. Where a message quoting the
    user's code called it directly, 3.8 answered a mistake in the app with an
    AttributeError of ApkPy's own. Here it is taken away, as 3.8 has it."""

    def test_a_refused_lambda_still_says_what_and_why(self):
        import ast
        from apkpy_lib.core.features import lambda_defaults
        from apkpy_lib.diagnostics import ApkpyError
        with patch.object(ast, "unparse", None, create=True):
            with self.assertRaises(ApkpyError) as caught:
                lambda_defaults.bind(ast.parse(
                    "n = 1" "\n" "f = lambda v=n: toast(v)" "\n" "n = 2"))
        self.assertEqual(caught.exception.code, "U2039")
        self.assertIn("v=n", str(caught.exception))

    def test_a_refused_gesture_still_says_what(self):
        import ast
        from apkpy_lib.core.compiler import translate_python_to_android
        source = "\n".join((
            'from apkpy_lib import *',
            'home = Screen(id="home")',
            'rows = virtual_collection(id="rows", items=[], screen=home, swipe_left=lambda: 1)',
            'run(start_screen=home)', ''))
        with patch.object(ast, "unparse", None, create=True):
            error = translate_python_to_android(source).get("error.txt", "")
        self.assertNotIn("AttributeError", error)
        self.assertIn("virtual_collection(swipe_left=...) takes swipe(", error)


if __name__ == "__main__":
    unittest.main()
