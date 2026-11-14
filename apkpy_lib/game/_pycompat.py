"""What differs between the Pythons ApkPyGame runs on, from 3.8 (as ApkPy) to 3.13, kept in one place.

Python 3.8:
  - wraps what is inside x[...] in ast.Index, where 3.9+ gives the expression itself (subscript_slice)
  - has no ast.unparse (source_text, one_line)
  - cannot evaluate list[X] in a type hint (type_hints)
"""
import ast
import io
import sys
import tokenize
import typing

_INDEX = getattr(ast, "Index", None)        # gone from the parser's output in 3.9, and from ast later


def subscript_slice(node):
    """What is inside the brackets of an ast.Subscript: list[str] gives the Name str, dict[str, int] the Tuple."""
    inside = node.slice
    if _INDEX is not None and isinstance(inside, _INDEX) and hasattr(inside, "value"):
        return inside.value
    return inside


def type_hints(cls):
    """typing.get_type_hints, also on 3.8 for a class written with list[X] or dict[K, V] under
    from __future__ import annotations: 3.8 cannot subscript list itself, so there they mean typing.List and typing.Dict."""
    try:
        return typing.get_type_hints(cls)
    except TypeError:
        if sys.version_info >= (3, 9):
            raise
        old_names = {"list": typing.List, "dict": typing.Dict, "tuple": typing.Tuple, "set": typing.Set}
        return typing.get_type_hints(cls, localns=old_names)


def one_line(source):
    """One statement written over several lines, on one line, and the same statement: comments go, the lines inside
    brackets join, and a string written over lines becomes one with \\n in it."""
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER):
            continue
        text = tok.string
        if tok.type == tokenize.STRING and "\n" in text:
            text = repr(ast.literal_eval(text))
        out.append(text)
    return " ".join(out)


def source_text(node, source=None):
    """The Python of a node, to quote it in a message: ast.unparse where there is one (3.9+), else the text of the
    file it came from, on one line."""
    if hasattr(ast, "unparse"):
        return ast.unparse(node)
    segment = ast.get_source_segment(source, node) if source else None
    return one_line(segment) if segment else "..."


def statements_on_one_line(source):
    """Every statement of a piece of code, on one line, with "; " between them (so the lines below keep their numbers).
    The statements have to be simple ones (no if, for, def)."""
    tree = ast.parse(source)
    if hasattr(ast, "unparse"):
        return "; ".join(ast.unparse(node) for node in tree.body)
    return "; ".join(one_line(ast.get_source_segment(source, node)) for node in tree.body)
