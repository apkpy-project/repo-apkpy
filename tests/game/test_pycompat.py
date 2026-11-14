"""apkpy_lib/game/_pycompat.py: what lets the package run on Python 3.8 (as ApkPy promises) as well as on 3.13."""
import ast
import sys

import pytest

from apkpy_lib.game import _pycompat, glue

SOURCE = '''x = native.java(
    "name",   # a comment that has to go
    args=("a", "b"),
    code="""
        return a + b;
    """,
    preview=lambda a, b: a + b,
)
y = [1,
     -2, {"k": 3}]
'''


def same_program(a, b):
    return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b))


def test_one_line_is_the_same_statements_on_one_line():
    line = "; ".join(_pycompat.one_line(ast.get_source_segment(SOURCE, n)) for n in ast.parse(SOURCE).body)
    assert "\n" not in line and "#" not in line
    assert same_program(line, SOURCE)


@pytest.mark.skipif(not hasattr(ast, "unparse"), reason="Python 3.8 has no ast.unparse to compare with")
def test_one_line_agrees_with_unparse():
    tree = ast.parse(SOURCE)
    assert same_program(_pycompat.statements_on_one_line(SOURCE), "; ".join(ast.unparse(n) for n in tree.body))


def test_the_glue_line_keeps_the_line_numbers():
    """enable_game() becomes one line on every Python, so an error in writehere.py still names the right line."""
    text = "from apkpy_lib import *\nenable_game()\nx = 1\n"
    out = glue.expand(text)
    assert out.split("\n")[2] == "x = 1"
    assert "apkpygamePlay" in out.split("\n")[1]


def test_subscript_slice_on_this_python():
    one = ast.parse("list[str]").body[0].value
    two = ast.parse("dict[str, int]").body[0].value
    assert isinstance(_pycompat.subscript_slice(one), ast.Name)
    assert isinstance(_pycompat.subscript_slice(two), ast.Tuple)


def test_source_text_quotes_an_annotation():
    source = "class A:\n    items: list[Ref[Move]] = []\n"
    node = ast.parse(source).body[0].body[0].annotation
    assert _pycompat.source_text(node, source).replace(" ", "") == "list[Ref[Move]]"


def test_this_python_is_one_apkpy_supports():
    assert sys.version_info >= (3, 8)
