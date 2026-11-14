# -*- coding: utf-8 -*-
"""The pieces of Python that answered wrong without a word, found by measuring.

plans/vocab/coverage/ runs a probe for each piece of the language through
CPython and through the generated Java, and compares what the two show. These
were the ones that built and showed something else, or stopped in javac far
from the line that wrote them:

- & | ^ << >> and ~ (and &= ...) glued or refused;
- s.startswith(("a", "b")) asked for the text of the tuple;
- list("abc") gave the word back;
- `if x:` on an item of a list read [] as the text "[]";
- (a, b), c = ... lost the inner pair;
- def f(a, /, b) and def f(a, *, b=1) never declared the names;
- *args, **kwargs, f(*items) and f(**options) reached javac;
- True + True was Java's true + true; b"abc" was Java's b'abc';
- str(re.findall(...)) showed the JSON;
- a list parameter: `if xs:` was true for an empty one.
"""

import ast
import unittest

from apkpy_lib.core import compiler
from apkpy_lib.core.compiler import translate_python_to_android
from test_classes import HEAD, _cpython, _generated
from test_data_rules import TOOLING
from test_python_vocabulary import _error, _flat, _java


APP = HEAD + '''

def sub(a, b, /):
    return a - b


def box(w, *, h=2):
    return w * h


def first(xs):
    return xs[0] if xs else None


def count(xs):
    if not xs:
        return 0
    return 1 + count(xs[1:])


def keys_of(d):
    if d:
        return ", ".join(d)
    return "none"


def bits():
    n = len(field.get_value())
    m = n
    m |= 8
    m ^= 1
    out.set_value(str(n & 3) + " " + str(n | 4) + " " + str(n ^ 5) + " " + str(n << 2)
                  + " " + str(n >> 1) + " " + str(~n) + " " + str(m) + " " + str(True + True + n))


def texts():
    s = field.get_value()
    out.set_value(str(s.startswith(("a", "b"))) + str(s.endswith(("x", "c"))) + " " + str(list(s)))


def items():
    n = len(field.get_value())
    found = []
    for v in [[], {}, "", 0, None, [n], "x"]:
        if v:
            found.append("T")
        else:
            found.append("F")
    (a, b), c = (n, n + 1), n + 2
    out.set_value("".join(found) + " " + str(a + b + c) + " " + str(sub(10, n))
                  + " " + str(box(n)) + " " + str(box(n, h=3)))


def params():
    n = len(field.get_value())
    local = [n, n]
    out.set_value(str(first([n])) + str(first([])) + " " + str(count(local)) + str(count([]))
                  + " " + keys_of({}) + keys_of({"k": n}))


button("1", id="b1", command=bits, screen=home)
button("2", id="b2", command=texts, screen=home)
button("3", id="b3", command=items, screen=home)
button("4", id="b4", command=params, screen=home)
run(start_screen=home)
'''


class TheAnswersTests(unittest.TestCase):
    """The generated Java shows what CPython shows, button by button."""

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["abc", "", "bx"]
        self.assertEqual(_cpython(APP, inputs), _generated(APP, inputs))


class TheJavaTests(unittest.TestCase):

    def test_true_plus_true_is_a_number(self):
        java = _java('    out.set_value(str(True + True + len(field.get_value())))')
        self.assertNotIn('true + true', java)
        self.assertIn('1L', java)

    def test_findall_is_shown_as_a_list(self):
        java = _java('    out.set_value(str(re.findall(r"\\d", field.get_value())))',
                     module_lines='import re\n')
        # The list's str(), as Python writes it: ['1', '2'], not ["1","2"].
        self.assertIn('_apkpyShow(String.valueOf(ApkpyRegex.findall(', java)

    def test_an_unread_star_parameter_is_dropped(self):
        java = _java('    out.set_value(str(pick(field.get_value())))',
                     module_lines='def pick(a, *_rest):\n    return a\n')
        self.assertIn('pythonCallback_pick(', java)


class TheRefusalTests(unittest.TestCase):
    """What javac used to stop on far away stops at its line, with what to write."""

    def test_star_args_that_the_body_reads(self):
        text = _flat(_error('    out.set_value(str(total(1, 2)))',
                            module_lines='def total(*nums):\n'
                                         '    t = 0\n'
                                         '    for x in nums:\n'
                                         '        t += x\n'
                                         '    return t\n'))
        self.assertIn('U2033', text)
        self.assertIn('Take a list instead: def total(nums) and call total([1, 2, 3])', text)

    def test_double_star_kwargs_that_the_body_reads(self):
        text = _flat(_error('    out.set_value(describe(a=1))',
                            module_lines='def describe(**info):\n'
                                         '    return str(len(info))\n'))
        self.assertIn('Take a dict instead', text)

    def test_spreading_a_list_into_a_call(self):
        text = _flat(_error('    xs = [1, 2]\n    out.set_value(str(add(*xs)))',
                            module_lines='def add(a, b):\n    return a + b\n'))
        self.assertIn('Pass the values one by one: add(items[0], items[1])', text)

    def test_spreading_a_dict_into_a_call(self):
        text = _flat(_error('    d = {"a": 1, "b": 2}\n    out.set_value(str(add(**d)))',
                            module_lines='def add(a, b):\n    return a + b\n'))
        self.assertIn('Pass the values one by one', text)

    def test_required_keyword_only_after_a_default(self):
        text = _flat(_error('    out.set_value(str(box(1, h=2, w=3)))',
                            module_lines='def box(x, *, h=1, w):\n    return x\n'))
        self.assertIn('keyword-only parameter without a default', text)
        self.assertIn('Give w a default', text)

    def test_bytes_complex_and_ellipsis(self):
        for value in ('b"abc"', '2j'):
            text = _flat(_error('    v = %s\n    out.set_value(str(v))' % value))
            self.assertIn('bytes', text, value)
            self.assertIn('Write text instead', text, value)

    def test_range_as_a_value_says_where_it_is_translated(self):
        text = _flat(_error('    out.set_value(str(list(range(len(field.get_value())))))'))
        self.assertIn('range() is translated as the list of a for loop', text)
        self.assertIn('for i in range(n): items.append(i)', text)


class TheMethodTests(unittest.TestCase):
    """A method takes / and * as a function does; f(*items) names it as written."""

    CART = HEAD + '''
class Cart:
    def __init__(self):
        self.items = []
        self.count = 0

    def add(self, name, /, *, qty=1):
        self.items.append(name)
        self.count += qty


cart = Cart()


def go():
    cart.add(field.get_value())
    cart.add("x", qty=3)
    out.set_value(str(cart.count) + " " + str(cart.items) + " " + str(list(cart.items)))


button("Go", id="b1", command=go, screen=home)
run(start_screen=home)
'''

    def test_a_method_with_slash_and_star(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        self.assertEqual(_cpython(self.CART, ["a", "b"]), _generated(self.CART, ["a", "b"]))

    def test_spreading_into_a_method_names_the_method(self):
        source = self.CART.replace('cart.add("x", qty=3)', 'xs = ["x"]\n    cart.add(*xs)')
        text = _flat(translate_python_to_android(source).get("error.txt"))
        self.assertIn("cart.add(*...) and cart.add(**...) are not translated yet", text)
        self.assertNotIn("_apkpy_Cart_add(*", text)

    def test_star_args_on_a_method_is_still_refused(self):
        source = self.CART.replace("def add(self, name, /, *, qty=1):", "def add(self, *names, qty=1):")
        source = source.replace("self.items.append(name)", "self.items.append(names)")
        text = _flat(translate_python_to_android(source).get("error.txt"))
        self.assertIn("*args and **kwargs on a method are not translated yet", text)


class TheParameterKindTests(unittest.TestCase):
    """_param_kinds: what the calls give a parameter, when every call says."""

    def kinds(self, source):
        return compiler._param_kinds(ast.parse(source))

    def test_every_call_gives_a_list(self):
        self.assertEqual(self.kinds('def f(xs):\n    return xs\n\nf([])\nf([1])\n'),
                         {'f': {'xs': 'list'}})

    def test_a_dict_and_a_keyword(self):
        self.assertEqual(self.kinds('def f(a, d=None):\n    return d\n\nf(1, d={})\n'),
                         {'f': {'d': 'dict'}})

    def test_one_call_with_text_says_nothing(self):
        self.assertEqual(self.kinds('def f(xs):\n    return xs\n\nf([])\nf("")\n'), {})

    def test_a_function_handed_on_is_called_by_something_else(self):
        self.assertEqual(self.kinds('def f(xs):\n    return xs\n\nf([])\ng = sorted([], key=f)\n'), {})

    def test_a_parameter_the_body_reassigns(self):
        self.assertEqual(self.kinds('def f(xs):\n    xs = len(xs)\n    return xs\n\nf([])\n'), {})

    def test_a_call_from_a_comprehension_is_not_read(self):
        self.assertEqual(self.kinds('def f(xs):\n    return xs\n\nys = [f(x) for x in [[1]]]\n'), {})

    def test_a_recursive_call_keeps_it_when_it_passes_one_too(self):
        source = ('def count(xs):\n    if not xs:\n        return 0\n'
                  '    return 1 + count(xs[1:])\n\ncount([1, 2])\n')
        self.assertEqual(self.kinds(source), {'count': {'xs': 'list'}})

    def test_a_name_holding_a_list_in_the_caller(self):
        source = ('def f(xs):\n    return xs\n\n\ndef go():\n    items = []\n    f(items)\n')
        self.assertEqual(self.kinds(source), {'f': {'xs': 'list'}})


if __name__ == "__main__":
    unittest.main()
