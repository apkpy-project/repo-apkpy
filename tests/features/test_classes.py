# -*- coding: utf-8 -*-
"""Classes: methods as functions, objects in the app's object store.

Until 1.14.1 a ``class`` stopped the build ("a Python class inside your module
has nowhere to go"). It is translated now by features/classes.py:

* an object is the text CPython shows for it without a ``__str__``, and the key
  of its fields in ApkpyObjects, so every name that holds it changes the same
  fields -- ``tasks[0].done = True`` is seen by every other name, as in CPython;
* a method is a function of the module, picked by the object's class when
  more than one class has it;
* a field every assignment of which gives one kind is read as that kind, so
  ``self.price * self.qty`` is arithmetic;
* an object made at the top of the file is made once per process;
* a ``@dataclass`` is written out as the class CPython makes of it (an
  ``__init__`` per field, ``__repr__``, ``__eq__``), and a class that extends
  an error (``class TooLong(ValueError): pass``) is one more error for raise
  and except, in ApkpyValues' family tree.

What is held here: the Java that comes out, the refusals with their reasons,
and -- with a JDK and the org.json jar -- the answers of the generated Java,
compared with CPython's for the same buttons.
"""

import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

from apkpy_lib.core.compiler import translate_python_to_android

from test_data_rules import TOOLING

HEAD = ('from apkpy_lib import Screen, button, inputs, label, run\n'
        'home = Screen(id="home")\n'
        'field = inputs("x", id="field", screen=home)\n'
        'out = label("", id="out", screen=home)\n\n')


def _source(top, body="    out.set_value('ok')\n", buttons=None):
    tail = buttons or 'button("Go", id="b1", command=go, screen=home)\n'
    return HEAD + top + "\n\ndef go():\n" + body + "\n\n" + tail + \
        'if __name__ == "__main__":\n    run(start_screen=home)\n'


def _files(top, body="    out.set_value('ok')\n"):
    return translate_python_to_android(_source(top, body))


def _java(top, body="    out.set_value('ok')\n"):
    files = _files(top, body)
    if "error.txt" in files:
        raise AssertionError(files["error.txt"][:600])
    return files


def _error(top, body="    out.set_value('ok')\n"):
    return _files(top, body).get("error.txt") or ""


TASK = '''class Task:
    def __init__(self, title, done=False):
        self.title = title
        self.done = done
        self.count = 0
        self.price = 0.0
        self.items = []

    def toggle(self):
        self.done = not self.done

    def add(self, name, price):
        self.items.append(name)
        self.count += 1
        self.price += price
'''


class TheTranslationTests(unittest.TestCase):

    def test_an_app_without_a_class_gets_no_object_store(self):
        files = _java("")
        self.assertNotIn("java/ApkpyObjects.java", files)

    def test_a_class_is_its_constructor_methods_and_the_store(self):
        files = _java(TASK, "    t = Task('a')\n    t.toggle()\n    out.set_value(t.title)\n")
        java = files["java/Screen_homeActivity.java"]
        self.assertIn("java/ApkpyObjects.java", files)
        self.assertIn('String self = ApkpyObjects.create("Task");', java)
        self.assertIn("pythonCallback__apkpy_Task___init__(String.valueOf(self)", java)
        self.assertIn("pythonCallback__apkpy_Task_toggle(String.valueOf(t));", java)
        self.assertIn('ApkpyObjects.get(String.valueOf(t), "title")', java)

    def test_setting_a_field_changes_the_object_itself(self):
        java = _java(TASK, "    t = Task('a')\n    t.toggle()\n")["java/Screen_homeActivity.java"]
        self.assertIn('ApkpyObjects.set(String.valueOf(self), "done", ', java)

    def test_a_field_always_given_whole_numbers_is_read_as_one(self):
        java = _java(TASK, "    t = Task('a')\n    out.set_value(str(t.count * 2))\n")[
            "java/Screen_homeActivity.java"]
        self.assertIn('Long.parseLong(String.valueOf(ApkpyObjects.get(String.valueOf(t), '
                      '"count")).trim())', java)

    def test_a_field_always_given_decimals_is_read_as_one(self):
        java = _java(TASK, "    t = Task('a')\n    t.add('x', 2.5)\n    out.set_value(str(t.price * 2))\n")[
            "java/Screen_homeActivity.java"]
        self.assertIn('Double.parseDouble(String.valueOf(ApkpyObjects.get(String.valueOf(t), '
                      '"price")))', java)

    def test_a_field_given_two_kinds_is_not_claimed(self):
        top = ('class Box:\n    def __init__(self):\n        self.v = 0\n'
               '    def text(self):\n        self.v = "a"\n')
        text = _error(top, "    b = Box()\n    out.set_value(str(b.v * 2))\n")
        self.assertIn("U2033", text)
        self.assertIn("could not tell that the values in this arithmetic are numbers", text)

    def test_a_list_field_is_changed_through_a_copy_and_given_back(self):
        java = _java(TASK, "    t = Task('a')\n    t.add('x', 1.0)\n")["java/Screen_homeActivity.java"]
        add = java[java.index("pythonCallback__apkpy_Task_add(String self"):]
        add = add[:add.index("\n    }\n")]
        self.assertIn('= ApkpyObjects.get(String.valueOf(self), "items");', add)
        self.assertIn("_apkpyListAppend(", add)
        self.assertIn('ApkpyObjects.set(String.valueOf(self), "items", ', add)

    def test_a_subclass_names_its_parent_and_overrides_go_through_a_dispatcher(self):
        top = ('class Shape:\n    def area(self):\n        return 0\n'
               'class Sq(Shape):\n    def __init__(self, s):\n        self.s = s\n'
               '    def area(self):\n        return self.s * self.s\n')
        files = _java(top, "    shapes = [Shape(), Sq(3)]\n    for x in shapes:\n"
                           "        out.set_value(str(x.area()))\n")
        self.assertIn('PARENTS.put("Sq", "Shape");', files["java/ApkpyObjects.java"])
        java = files["java/Screen_homeActivity.java"]
        self.assertIn("pythonCallback__apkpy_call_area(", java)
        self.assertIn('ApkpyObjects.classOf(String.valueOf(self))', java)

    def test_isinstance_of_a_class_asks_the_store(self):
        top = 'class A:\n    pass\nclass B(A):\n    pass\n'
        java = _java(top, "    x = B()\n    out.set_value(str(isinstance(x, A)))\n")[
            "java/Screen_homeActivity.java"]
        self.assertIn('ApkpyObjects.isInstance(String.valueOf(x), "A")', java)

    def test_str_of_an_object_uses_its___str__(self):
        top = 'class A:\n    def __str__(self):\n        return "an A"\n'
        java = _java(top, "    a = A()\n    out.set_value(str(a))\n")["java/Screen_homeActivity.java"]
        self.assertIn("pythonCallback__apkpy_A___str__(", java)

    def test_an_object_of_the_module_is_made_once(self):
        top = TASK + "\ncurrent = Task('first')\n"
        java = _java(top, "    current.toggle()\n")["java/Screen_homeActivity.java"]
        self.assertIn("private void pythonCallback__apkpy_init()", java)
        go = java[java.index("private void pythonCallback_go()"):]
        self.assertTrue(go.split("\n")[1].strip().startswith("pythonCallback__apkpy_ensure();"), go[:200])
        self.assertIn('ApkpyReactiveState.get("__apkpy_global_current", "")', go)

    def test_a_method_handed_to_a_button_becomes_a_call(self):
        top = TASK + "\ncurrent = Task('first')\n"
        files = translate_python_to_android(_source(
            top, buttons='button("Go", id="b1", command=current.toggle, screen=home)\n'))
        self.assertNotIn("error.txt", files, files.get("error.txt", "")[:300])
        java = files["java/Screen_homeActivity.java"]
        self.assertIn("pythonCallback__apkpy_Task_toggle(String.valueOf(pythonCallback__apkpy_mod_current()))",
                      java)

    def test_a_class_attribute_that_changes_is_kept_once(self):
        top = 'class C:\n    made = 0\n    def __init__(self):\n        C.made += 1\n'
        java = _java(top, "    C()\n    out.set_value(str(C.made))\n")["java/Screen_homeActivity.java"]
        self.assertIn('"__apkpy_global__apkpy_C_made"', java)

    def test_is_between_two_objects_is_the_same_object(self):
        top = 'class A:\n    pass\n'
        files = _java(top, "    a = A()\n    b = a\n    out.set_value(str(a is b))\n")
        self.assertIn("java/ApkpyObjects.java", files)

    def test_an_object_is_of_its_class_for_isinstance_of_python_types(self):
        files = _java('class A:\n    pass\n')
        values = files["java/ApkpyValues.java"]
        self.assertIn("if (isObjectText(v)) return v.substring(10", values)


    def test_a_function_that_returns_from_a_try_keeps_its_kind(self):
        # read() ends in a try whose two ways out return a float: it does not
        # fall off its end, so no None joins its kind and -self.amount is a sum.
        top = ('class Entry:\n    def __init__(self, amount):\n        self.amount = amount\n'
               '    def signed(self):\n        return -self.amount\n\n'
               'def read():\n    try:\n        return float(field.get_value())\n'
               '    except ValueError:\n        return 0.0\n')
        java = _java(top, "    out.set_value(str(Entry(read()).signed()))\n")[
            "java/Screen_homeActivity.java"]
        self.assertIn("pythonCallback__apkpy_Entry_signed(", java)


class TheRefusalTests(unittest.TestCase):

    def assertRefused(self, top, words, body="    out.set_value('ok')\n"):
        text = _error(top, body)
        self.assertIn("U2033", text, text[:300] or "the build did not stop")
        self.assertIn(words, " ".join(text.split()))

    def test_a_class_inside_a_function(self):
        self.assertRefused("", "A class inside a function",
                           body="    class A:\n        pass\n    out.set_value('x')\n")

    def test_two_parents(self):
        self.assertRefused("class A:\n    pass\nclass B:\n    pass\nclass C(A, B):\n    pass\n",
                           "more than one parent")

    def test_an_error_class_with_a_field(self):
        self.assertRefused("class Oops(Exception):\n    def __init__(self, code):\n"
                           "        super().__init__('x')\n        self.code = code\n",
                           "Fields and methods on an error are not translated yet")

    def test_a_parent_error_from_outside_the_file(self):
        self.assertRefused("class Oops(LibraryError):\n    pass\n",
                           "neither one of Python's built-in errors")

    def test_a_parent_from_outside_the_file(self):
        self.assertRefused("class A(dict):\n    pass\n", "not a class of this file")

    def test_a_decorated_class(self):
        self.assertRefused("def tag(c):\n    return c\n@tag\nclass P:\n    x = 0\n",
                           "@tag on a class")

    def test_a_classmethod(self):
        self.assertRefused("class A:\n    @classmethod\n    def make(cls):\n        return cls()\n",
                           "@classmethod on a method")

    def test_an_operator_method(self):
        self.assertRefused("class V:\n    def __add__(self, o):\n        return self\n",
                           "V.__add__ is not translated yet")

    def test_a_list_shared_by_every_object(self):
        self.assertRefused("class A:\n    items = []\n", "shared by every instance")

    def test_del_of_a_field(self):
        self.assertRefused("class A:\n    def __init__(self):\n        self.x = 1\n",
                           "del of an object's field",
                           body="    a = A()\n    del a.x\n")

    def test_part_of_the_screen_built_from_an_object(self):
        self.assertRefused("class A:\n    def __init__(self):\n        self.t = 'hi'\n"
                           "a = A()\nlabel(a.t, id='l2', screen=home)\n",
                           "builds a part of the screen from an object")

    def test_getattr_of_an_object(self):
        self.assertRefused("class A:\n    def __init__(self):\n        self.x = 1\n",
                           "getattr() of an object",
                           body="    a = A()\n    out.set_value(str(getattr(a, 'x')))\n")


# --- @dataclass ---------------------------------------------------------------
# HEAD names an input "field", so these use dataclasses.field.

ITEM = """import dataclasses


@dataclasses.dataclass
class Item:
    name: str
    price: float = 0.0
    tags: list = dataclasses.field(default_factory=list)
"""


class TheDataclassTests(unittest.TestCase):

    def assertRefused(self, top, words):
        text = _error(top, "    out.set_value(repr(P(1)))\n")
        self.assertIn("U2033", text, text[:300] or "the build did not stop")
        self.assertIn(words, " ".join(text.split()))

    def test_a_dataclass_is_written_out_as_init_repr_and_eq(self):
        java = _java(ITEM, "    a = Item('x', 2.0)\n    out.set_value(repr(a) + str(a == Item('x')))\n")[
            "java/Screen_homeActivity.java"]
        for name in ("pythonCallback__apkpy_Item___init__(", "pythonCallback__apkpy_Item___repr__(",
                     "pythonCallback__apkpy_Item___eq__("):
            self.assertIn(name, java)
        self.assertIn('ApkpyObjects.classOf(String.valueOf(other))', java)

    def test_a_method_the_class_writes_is_kept(self):
        top = ITEM + "\n    def __repr__(self):\n        return 'mine'\n"
        java = _java(top, "    out.set_value(repr(Item('x')))\n")["java/Screen_homeActivity.java"]
        self.assertIn('"mine"', java)
        self.assertNotIn('"price="', java)

    def test_eq_false_writes_no_eq(self):
        top = ITEM.replace("@dataclasses.dataclass", "@dataclasses.dataclass(eq=False)")
        java = _java(top, "    out.set_value(str(Item('x') == Item('x')))\n")[
            "java/Screen_homeActivity.java"]
        self.assertNotIn("_apkpy_Item___eq__", java)

    def test_frozen(self):
        self.assertRefused("import dataclasses\n@dataclasses.dataclass(frozen=True)\n"
                           "class P:\n    x: int\n", "A frozen dataclass is not translated yet")

    def test_order(self):
        self.assertRefused("import dataclasses\n@dataclasses.dataclass(order=True)\n"
                           "class P:\n    x: int\n", "order=True is not translated yet")

    def test_a_list_as_a_default(self):
        self.assertRefused("import dataclasses\n@dataclasses.dataclass\nclass P:\n"
                           "    x: int\n    tags: list = []\n",
                           "mutable default <class 'list'> for field tags is not allowed")

    def test_a_field_without_a_default_after_one_with_it(self):
        self.assertRefused("import dataclasses\n@dataclasses.dataclass\nclass P:\n"
                           "    x: int = 0\n    y: int\n",
                           "non-default argument 'y' follows default argument 'x'")

    def test_an_initvar(self):
        self.assertRefused("import dataclasses\n@dataclasses.dataclass\nclass P:\n"
                           "    x: dataclasses.InitVar[int]\n", "InitVar fields are not translated yet")

    def test_a_factory_that_is_a_function(self):
        self.assertRefused("import dataclasses\ndef make():\n    return []\n"
                           "@dataclasses.dataclass\nclass P:\n"
                           "    x: list = dataclasses.field(default_factory=make)\n",
                           "default_factory= is translated with list, dict")


# --- errors of your own -------------------------------------------------------

ERRORS = """class AppError(Exception):
    pass


class TooLong(ValueError):
    pass


class NotFound(AppError):
    def __init__(self, message="Nothing by that name"):
        super().__init__(message)
"""


class TheErrorClassTests(unittest.TestCase):

    def assertRefused(self, top, words):
        text = _error(top)
        self.assertIn("U2033", text, text[:300] or "the build did not stop")
        self.assertIn(words, " ".join(text.split()))

    def test_an_error_class_is_a_name_in_the_family_tree_and_not_an_object(self):
        files = _java(ERRORS, "    try:\n        raise TooLong('x')\n    except ValueError as e:\n"
                              "        out.set_value(str(e))\n")
        self.assertNotIn("java/ApkpyObjects.java", files)
        values = files["java/ApkpyValues.java"]
        self.assertIn('case "TooLong":\n                return "ValueError";', values)
        self.assertIn('case "NotFound":\n                return "AppError";', values)
        self.assertIn('case "AppError":\n                return "Exception";', values)
        java = files["java/Screen_homeActivity.java"]
        self.assertIn('throw new ApkpyValues.Raised("TooLong", ', java)

    def test_raise_without_a_message_gives_the_default_of_its_init(self):
        java = _java(ERRORS, "    raise NotFound()\n")["java/Screen_homeActivity.java"]
        self.assertRegex(java, r'throw new ApkpyValues\.Raised\("NotFound", '
                               r'(String\.valueOf\()?"Nothing by that name"')

    def test_except_names_it(self):
        java = _java(ERRORS, "    try:\n        out.set_value('a')\n    except NotFound:\n"
                             "        out.set_value('b')\n")["java/Screen_homeActivity.java"]
        self.assertIn('"NotFound"', java)

    def test_a_method_on_an_error(self):
        self.assertRefused("class Oops(Exception):\n    def why(self):\n        return 'x'\n",
                           "Fields and methods on an error are not translated yet")

    def test_a_name_that_hides_pythons_own(self):
        self.assertRefused("class KeyError(Exception):\n    pass\n",
                           "would hide Python's own KeyError")

    def test_an_unknown_error_says_how_to_write_one(self):
        text = " ".join(_error("", "    raise Missing('x')\n").split())
        self.assertIn("not an error ApkPy knows", text)
        self.assertIn("class Missing(Exception): pass", text)


# --- the answers, against CPython ------------------------------------------------

APP = HEAD + '''
class Shape:
    made = 0

    def __init__(self, name):
        self.name = name
        Shape.made += 1

    def area(self):
        return 0

    def describe(self):
        return self.name + " " + str(self.area())


class Rect(Shape):
    def __init__(self, w, h):
        super().__init__("rect")
        self.w = w
        self.h = h

    def area(self):
        return self.w * self.h


class Square(Rect):
    def __init__(self, side):
        super().__init__(side, side)
        self.name = "square"


class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


class Cart:
    TAX = 0.25

    def __init__(self):
        self.items = []
        self.total = 0.0

    def add(self, name, price):
        self.items.append(name)
        self.total += price
        return self

    def __str__(self):
        return f"Cart({len(self.items)}, {self.total * (1 + self.TAX):.2f})"


class Box:
    pass


cart = Cart()
TASKS = []
for word in ["milk", "bread"]:
    TASKS.append(Point(len(word), 0))


def grow(r, by):
    r.w = r.w + by


def shapes():
    items = [Rect(2, 3), Square(4), Shape("dot")]
    lines = [s.describe() for s in items]
    lines.append(str(Shape.made) + " " + type(items[1]).__name__)
    lines.append(str(isinstance(items[1], Rect)) + " " + str(isinstance(items[2], Rect)))
    out.set_value("|".join(lines))


def points():
    a = Point(1, 2)
    lines = [repr(a), str(a == Point(1, 2)), str(a is Point(1, 2)), str(TASKS), f"{TASKS[0]!r}"]
    out.set_value("|".join(lines))


def refs():
    r = Rect(1, 1)
    alias = r
    alias.h = 5
    grow(r, 2)
    keep = {"r": r}
    keep["r"].w = 10
    out.set_value(str(r.area()) + " " + str(r is alias))


def shop():
    cart.add(field.get_value() or "none", 2.0).add("tea", 1.5)
    out.set_value(str(cart) + " " + ",".join(cart.items))


def errors():
    b = Box()
    try:
        msg = "no " + str(b.missing)
    except AttributeError as e:
        msg = str(e)
    out.set_value(msg)


button("1", id="b1", command=shapes, screen=home)
button("2", id="b2", command=points, screen=home)
button("3", id="b3", command=refs, screen=home)
button("4", id="b4", command=shop, screen=home)
button("5", id="b5", command=errors, screen=home)
'''


def _cpython(source, inputs):
    """What CPython shows for each button, with a stand-in apkpy_lib."""
    widgets = {"inputs": [], "labels": [], "buttons": []}

    class _Input(object):
        def __init__(self, *a, **kw):
            self.value = ""
            widgets["inputs"].append(self)

        def get_value(self):
            return self.value

    class _Label(object):
        def __init__(self, *a, **kw):
            self.value = ""
            widgets["labels"].append(self)

        def set_value(self, v):
            self.value = v

    fake = types.ModuleType("apkpy_lib")
    fake.Screen = lambda *a, **kw: None
    fake.inputs = _Input
    fake.label = _Label
    fake.button = lambda *a, **kw: widgets["buttons"].append(kw.get("command"))
    fake.run = lambda *a, **kw: None
    saved = sys.modules.get("apkpy_lib")
    sys.modules["apkpy_lib"] = fake
    try:
        exec(compile(source, "app.py", "exec"), {"__name__": "app"})
    finally:
        if saved is not None:
            sys.modules["apkpy_lib"] = saved
    answers = []
    for typed in inputs:
        for box in widgets["inputs"]:
            box.value = typed
        for command in widgets["buttons"]:
            with contextlib.redirect_stdout(io.StringIO()):
                command()
            answers.append(str(widgets["labels"][0].value))
    return answers


def _generated(source, inputs):
    """What the generated Java shows for each button, on the PC's JVM."""
    javac, java_bin, jar = TOOLING
    files = translate_python_to_android(source)
    assert "error.txt" not in files, files.get("error.txt", "")[:600]
    java = files["java/Screen_homeActivity.java"]

    def definition(name):
        m = re.search(r"^    (?:private|public) (?:static )?(?:final )?[\w.<>\[\]]+ %s\("
                      % re.escape(name), java, re.M)
        if not m:
            return None
        return java[m.start():java.index("\n    }\n", m.start()) + 7]

    clicks = {}
    for m in re.finditer(r"(\w+)\.setOnClickListener\(new View\.OnClickListener\(\) \{\n"
                         r"\s*@Override\n\s*public void onClick\(View \w+\) \{\n(.*?)\n"
                         r"            \}\n        \}\);", java, re.S):
        clicks[m.group(1)] = m.group(2)
    done, order = set(), []
    todo = [d for code in clicks.values()
            for d in re.findall(r"\b((?:_apkpy|_json|pythonCallback_)\w+)\(", code)]
    while todo:
        name = todo.pop()
        if name in done or name == "_apkpyRememberText":
            continue
        done.add(name)
        found = definition(name)
        if found:
            order.append(found)
            todo.extend(re.findall(r"\b((?:_apkpy|_json|pythonCallback_)\w+)\(", found))
    buttons = sorted(clicks, key=lambda b: int(re.sub(r"\D", "", b) or 0))
    order += ["    void click_%s() {\n%s\n    }\n" % (b, clicks[b]) for b in buttons]
    fields = [line for line in java.splitlines()
              if re.match(r"    private (static final )?String \w+( = .*)?;$", line)]
    body = "\n".join(fields + order)
    body = re.sub(r"\(\(android\.widget\.EditText\)findViewById\(R\.id\.\w+\)\)\.getText\(\)"
                  r"\.toString\(\)", "INPUT", body)
    body = re.sub(r"\(\(android\.widget\.TextView\)findViewById\(R\.id\.\w+\)\)\.setText\(",
                  "show(", body)
    body = re.sub(r"\b(lbl\d+)\.setText\(", "show(", body)
    body = re.sub(r"\binp\d+\.getText\(\)\.toString\(\)", "INPUT", body)
    body = re.sub(r"_apkpyRememberText\(R\.id\.\w+\);", "", body)
    main = ('    String INPUT = "";\n    String SHOWN = "";\n'
            '    void show(Object v) { SHOWN = String.valueOf(v); }\n'
            '    public static void main(String[] args) throws Exception {\n'
            '        H app = new H();\n'
            '        java.io.PrintStream o = new java.io.PrintStream(System.out, true, "UTF-8");\n'
            '        for (String typed : args) {\n'
            '            app.INPUT = typed.substring(1);\n'
            + "".join('            app.click_%s(); o.println(app.SHOWN);\n' % b for b in buttons)
            + '        }\n    }\n')
    work = tempfile.mkdtemp(prefix="apkpy-classes-")
    try:
        os.makedirs(os.path.join(work, "android", "util"))
        with io.open(os.path.join(work, "android", "util", "Log.java"), "w", encoding="utf-8") as f:
            f.write("package android.util;\npublic final class Log {\n"
                    "    public static int i(String tag, String message) { return 0; }\n}\n")
        for name in ("ApkpyValues", "ApkpyReactiveState", "ApkpyObjects"):
            key = "java/%s.java" % name
            if key in files:
                with io.open(os.path.join(work, name + ".java"), "w", encoding="utf-8") as f:
                    f.write(files[key].replace("package com.apkpy.app;", ""))
        with io.open(os.path.join(work, "H.java"), "w", encoding="utf-8") as f:
            f.write("public class H {\n%s\n%s}\n" % (body, main))
        sources = [os.path.join(work, n) for n in os.listdir(work) if n.endswith(".java")]
        built = subprocess.run([javac, "-encoding", "UTF-8", "-nowarn", "-cp", jar, "-d", work]
                               + sources + [os.path.join(work, "android", "util", "Log.java")],
                               capture_output=True, text=True)
        assert built.returncode == 0, built.stdout + built.stderr
        ran = subprocess.run([java_bin, "-cp", work + os.pathsep + jar, "H"]
                             + ["=" + i for i in inputs],
                             capture_output=True, text=True, encoding="utf-8")
        assert ran.returncode == 0, ran.stdout + ran.stderr
        return ran.stdout.splitlines()
    finally:
        shutil.rmtree(work, ignore_errors=True)


class TheAnswersTests(unittest.TestCase):
    """The generated Java answers what CPython answers, button by button."""

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["ana", ""]
        want = _cpython(APP, inputs)
        got = _generated(APP, inputs)
        address = r" object at 0x[0-9a-fA-F]+>"
        want = [re.sub(address, " object at 0x...>", w) for w in want]
        got = [re.sub(address, " object at 0x...>", g) for g in got]
        self.assertEqual(want, got)

    def test_dataclasses_answer_as_in_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["milk", ""]
        self.assertEqual(_cpython(DC_APP, inputs), _generated(DC_APP, inputs))

    def test_errors_of_your_own_answer_as_in_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["abc", "", "none", "toolongname", "key", "app"]
        self.assertEqual(_cpython(EXC_APP, inputs), _generated(EXC_APP, inputs))


DC_APP = HEAD.replace("from apkpy_lib", "import dataclasses\nfrom typing import ClassVar\nfrom apkpy_lib") + '''

@dataclasses.dataclass
class Item:
    name: str
    price: float = 0.0
    qty: int = 1
    tags: list = dataclasses.field(default_factory=list)
    note: str = dataclasses.field(default="", repr=False, compare=False)

    def total(self):
        return self.price * self.qty


@dataclasses.dataclass
class Discounted(Item):
    off: float = 0.1
    label: str = dataclasses.field(init=False, default="")
    made: ClassVar[int] = 0

    def __post_init__(self):
        self.label = f"{self.name} -{self.off * 100:.0f}%"
        Discounted.made += 1


class Gift(Item):
    pass


@dataclasses.dataclass(eq=False)
class Point:
    x: int
    y: int = 0


def go():
    name = field.get_value()
    a = Item(name, 2.5, 2)
    b = Item(name, 2.5, 2, note="other")
    c = Item(name)
    a.tags.append("x")
    d = Discounted(name, 10.0, off=0.25)
    g = Gift(name, 1.0)
    p = Point(1)
    out.set_value(" | ".join([repr(a), repr(c), str(a == b), str(a == c), str(c.tags),
                              repr(d), d.label, f"{d.total():.2f}", repr(g),
                              str(g == Item(name, 1.0)), str(d == Item(name, 10.0)),
                              str(Discounted.made), repr(p), str(p == Point(1)), f"{c}"]))


button("Go", id="b1", command=go, screen=home)
'''

EXC_APP = HEAD + '''

class AppError(Exception):
    """Every error this app raises."""


class NotFound(AppError):
    def __init__(self, message="Nothing by that name"):
        super().__init__(message)


class TooLong(ValueError):
    pass


class MissingKey(KeyError):
    pass


class Empty(NotFound):
    pass


def find(text):
    if text == "":
        raise Empty()
    if text == "none":
        raise NotFound
    if len(text) > 5:
        raise TooLong(f"{len(text)} letters")
    if text == "key":
        raise MissingKey("key")
    if text == "app":
        raise AppError("general")
    return text.upper()


def kind_of(text):
    try:
        return "ok " + find(text)
    except Empty as e:
        return "empty: " + str(e)
    except NotFound as e:
        return "not found: " + str(e)
    except ValueError as e:
        return "value: " + str(e)
    except LookupError as e:
        return "lookup: " + str(e)
    except AppError as e:
        return "app: " + f"{e}"


def again(text):
    try:
        try:
            find(text)
            return "fine"
        except (TooLong, MissingKey):
            raise
    except Exception as e:
        return "outer " + str(e)


def go():
    text = field.get_value()
    out.set_value(kind_of(text) + " / " + again(text))


button("Go", id="b1", command=go, screen=home)
'''


if __name__ == "__main__":
    unittest.main()
