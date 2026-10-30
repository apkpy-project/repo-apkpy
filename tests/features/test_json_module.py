# -*- coding: utf-8 -*-
"""json.loads() and json.dumps() answer as in CPython.

The Java that comes out and the refusals are held in test_python_vocabulary.py
(TheJsonTests). Here the generated Java runs on the PC's JVM, button by button,
next to CPython running the same app (test_classes has the two runners): the
messages of a text that is not JSON, word for word with the line, the column
and the position; the values read back with their types; dumps() with each of
its options; floats appended to a list, which went in
as text.

The org.json jar the JVM uses keeps a dict's keys in no order (Android keeps
the order they came in), so every dict written here has one key or goes
through sort_keys=True.
"""

import unittest

from test_classes import HEAD, TOOLING, _cpython, _generated

JSON_APP = HEAD.replace("from apkpy_lib", "import json\nfrom json import loads, dumps, "
                                          "JSONDecodeError\nfrom apkpy_lib") + r'''
BAD = ['', ' ', '{', '[', '[1,]', '{"a":1,}', '{"a" 1}', '{"a":1 "b":2}', "{'a':1}",
       '[1 2]', '"abc', '"a\\qb"', '"\\u12"', '"\\u12G4"', '"a\tb"', '01', '1.', '-', '-a',
       '1e', '.5', 'nul', '[1, 2] x', '[1,\n 2,\n x]', '﻿[]', '"\U0001F600" x']
GOOD = ['{"a": [1, {"b": null}]}', '"\\ud83d\\ude00"', '1.5e3', '-0', '-0.0', '1E2',
        'true', 'false', 'null', '"\\u00e9\\n\\"\\\\\\/"', '{"a":1, "a":2}', '  [ ]  ',
        '{ }', '[1, [2, [3]]]', '"ok"', '3', '2.50', '[1, 2.5, "x", null, true]',
        '{"k": "v"}', '123456789012345678901234567890']

CONFIG = loads('{"theme": "dark", "size": 2, "tags": ["a", "b"], "ratio": 0.5}')
EXAMPLE = dumps({"a": [1, 2.0, None]}, indent=1)
data = None


class Task:
    def __init__(self, title):
        self.title = title


def show(v):
    if isinstance(v, (bool, int, float, str)) or v is None:
        return str(v)
    return json.dumps(v, sort_keys=True)


def bad():
    lines = []
    for text in BAD:
        try:
            json.loads(text)
            lines.append("no error")
        except json.JSONDecodeError as e:
            lines.append(str(e))
    try:
        json.loads(field.get_value() + "}")
    except ValueError as e:
        lines.append("ValueError: " + str(e))
    out.set_value(" | ".join(lines).replace("\n", "<NL>"))


def good():
    lines = [show(json.loads(text)) for text in GOOD]
    out.set_value(" | ".join(lines).replace("\n", "<NL>"))


def write():
    parsed = json.loads('{"b": [1, 2.5, {"c": null}], "a": "\\u00e9\\n\\ud83d\\ude00"}'
                      + field.get_value())
    nums = [1, 2]
    nums.append(len(field.get_value()) + 3)
    lines = [
        json.dumps(parsed, sort_keys=True),
        json.dumps(parsed, sort_keys=True, indent=2),
        json.dumps(parsed, sort_keys=True, ensure_ascii=False),
        json.dumps(parsed, sort_keys=True, separators=(",", ":")),
        json.dumps(parsed, sort_keys=True, indent="\t"),
        json.dumps(parsed, sort_keys=True, indent=0),
        json.dumps(nums),
        json.dumps(nums, indent=4),
        json.dumps(1.5 * len(field.get_value() + "ab")),
        json.dumps(len(field.get_value()) > 100),
        json.dumps(field.get_value() + "\x7f"),
        json.dumps([]),
        json.dumps(json.loads("[]" + field.get_value()), indent=4),
        json.dumps(json.loads("{}" + field.get_value()), indent=4),
    ]
    out.set_value(" | ".join(lines).replace("\n", "<NL>"))


def save(value):
    return dumps(value, sort_keys=True)


def spellings():
    lines = [str(int(CONFIG["size"]) + 1), CONFIG["theme"], str(len(CONFIG["tags"])),
             str(float(CONFIG["ratio"]) * 2), EXAMPLE.replace("\n", "<NL>")]
    rows = [{"n": 1}, {"n": 2}]
    lines.append(save(rows))
    lines.append(save({"k": field.get_value() or "v"}))
    try:
        json.dumps(Task("x"))
    except TypeError as e:
        lines.append("TypeError: " + str(e))
    try:
        loads("{" + field.get_value())
    except JSONDecodeError as e:
        lines.append(str(e))
    prices = []
    prices.append(len(field.get_value()) + 10.5)
    prices.append(len(field.get_value()) + 9.25)
    lines.append(dumps(prices) + " " + str(sorted(prices)) + " " + str(max(prices)))
    back = json.loads(dumps(rows))
    lines.append(str(back[1]["n"] + 10))
    for row in back:
        lines.append(str(row["n"]))
    out.set_value(" | ".join(lines))


def load():
    global data
    data = json.loads('{"theme": "dark", "n": 4' + field.get_value() + '}')


def later():
    load()
    out.set_value(data["theme"] + " | " + str(int(data["n"]) * 2) + " | " + str(data is None))


button("1", id="b1", command=bad, screen=home)
button("2", id="b2", command=good, screen=home)
button("3", id="b3", command=write, screen=home)
button("4", id="b4", command=spellings, screen=home)
button("5", id="b5", command=later, screen=home)
button("6", id="b6", command=lambda: out.set_value(json.dumps([field.get_value(), 1])),
       screen=home)
'''


class TheJsonAnswersTests(unittest.TestCase):
    """The generated Java reads and writes what CPython reads and writes."""

    def test_the_same_answers_as_cpython(self):
        if not TOOLING or not TOOLING[2]:
            self.skipTest("no JDK or no org.json jar on this machine")
        inputs = ["", " "]
        self.assertEqual(_cpython(JSON_APP, inputs), _generated(JSON_APP, inputs))


if __name__ == "__main__":
    unittest.main()
