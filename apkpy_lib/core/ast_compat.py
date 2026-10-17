# -*- coding: utf-8 -*-
"""The tree ``ast.parse`` gives, in the shape Python 3.9 and later give it.

Python 3.8 wraps what goes between square brackets: ``parts[0]`` is
``Subscript(slice=Index(value=Constant(0)))`` there, and ``Constant(0)``
directly from 3.9 on. The translator reads the 3.9 shape. On 3.8 an index
it did not unwrap was not an error: ``parts[0]`` reached the phone as the
item at index "", which is nothing, and the Previewer -- running Python --
showed the right item. So the tree is put in one shape as it is read, and
everything after this sees the same thing on every version.
"""

import ast
import sys


class _To39(ast.NodeTransformer):
    """``Index(value=x)`` becomes ``x``; ``ExtSlice(dims)`` a tuple of them."""

    def visit_Index(self, node):
        # An Index has no position of its own; what it holds does.
        return self.visit(node.value)

    def visit_ExtSlice(self, node):
        dims = [self.visit(dim) for dim in node.dims]
        tuple_node = ast.Tuple(elts=dims, ctx=ast.Load())
        return ast.copy_location(tuple_node, dims[0]) if dims else tuple_node


def normalise(tree):
    """``tree`` in the 3.9 shape. On 3.9 and later it is returned untouched."""
    if sys.version_info >= (3, 9):
        return tree
    tree = _To39().visit(tree)
    return ast.fix_missing_locations(tree)


def parse(source, filename="<unknown>"):
    """``ast.parse``, in the 3.9 shape on every version."""
    return normalise(ast.parse(source, filename=filename))
