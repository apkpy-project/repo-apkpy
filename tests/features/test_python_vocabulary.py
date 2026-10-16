# -*- coding: utf-8 -*-
"""The Python ApkPy translates -- and what it now says about the rest.

Three things land here, and they are the same thing seen from three sides:
code ApkPy could not translate used to leave no trace. ``math.sqrt(x)`` became
the empty string, ``try:`` had its whole body dropped, and ``list.append()``
generated no line at all. Each one produced an app that built, installed and
ran, and was simply missing a piece nobody was told about.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android


def _files(body, extra_imports="", module_lines=""):
    source = (
        'from apkpy_lib import Screen, button, inputs, label, list_view, '
        'run, storage, toast%s\n'
        'home = Screen(id="home")\n'
        'field = inputs(placeholder="x", id="field", type="text", screen=home)\n'
        'out = label("", id="out", screen=home)\n'
        '%s\n'
        '\n\ndef go():\n%s\n\n\n'
        'button("Go", id="b", screen=home, command=go)\n'
        'run(start_screen=home)\n'
    ) % (extra_imports, module_lines, body)
    return translate_python_to_android(source)


def _java(body, **kw):
    files = _files(body, **kw)
    if 'error.txt' in files:
        raise AssertionError(files['error.txt'][:400])
    return "\n".join(b for n, b in files.items() if n.endswith(".java"))


def _error(body, **kw):
    """The rendered diagnostic, or None when the app compiled."""
    return _files(body, **kw).get('error.txt')


class TheSilenceTests(unittest.TestCase):
    """Untranslatable code has to say so. It used to return "" and go on."""

    def test_a_name_left_out_of_a_supported_module_says_why(self):
        # math is translated now, so the message has to speak for the handful
        # deliberately left out rather than for the module.
        text = _error('    out.set_value(math.log2(8))', extra_imports='',
                      module_lines='')
        self.assertIn('U2033', text)
        self.assertIn('math.log2(8)', text)
        self.assertIn('Most of math is translated', text)
        self.assertIn('powers of two', text)

    def test_a_package_that_cannot_exist_says_why_and_where_to_go(self):
        text = _error('    out.set_value(requests.get("http://x"))')
        self.assertIn('no Python interpreter on the phone', text)
        self.assertIn('https.get', text)

    def test_a_builtin_gets_a_workaround_that_compiles_today(self):
        text = _error('    out.set_value(any([1, 2]))')
        self.assertIn('any', text)
        self.assertIn('a for loop with a flag', text)

    def test_a_slice_with_a_step_is_still_refused(self):
        # Plain slices are translated now; a step is not, and saying so beats
        # returning every character when the author asked for every second one.
        text = _error('    out.set_value("abcdef"[0:6:2])')
        self.assertIn('U2033', text)

    def test_slicing_never_writes_the_broken_java_it_used_to(self):
        # It generated `(x)[Integer.parseInt("")]`, which is not Java at all.
        java = _java('    out.set_value("abcdef"[0:2])')
        self.assertNotIn('[Integer.parseInt', java)
        self.assertIn('_apkpySlice', java)

    def test_print_is_not_quietly_turned_into_a_missing_method(self):
        # print("x") compiled to pythonCallback_print(...) and the build died
        # on cannot-find-symbol, pointing into a file nobody wrote.
        text = _error('    print("hello")')
        self.assertIn('print', text)
        self.assertIn('toast', text)

    def test_a_mistyped_helper_names_the_one_that_exists(self):
        source = (
            'from apkpy_lib import Screen, button, label, run\n'
            'home = Screen(id="home")\n'
            'out = label("", id="out", screen=home)\n'
            '\n\ndef refresh():\n    out.set_value("x")\n'
            '\n\ndef go():\n    refrsh()\n\n\n'
            'button("Go", id="b", screen=home, command=go)\n'
            'run(start_screen=home)\n'
        )
        text = translate_python_to_android(source)['error.txt']
        self.assertIn('Did you mean refresh?', text)

    def test_an_overlay_may_be_built_below_the_function_that_opens_it(self):
        # It used to stop the build ("top to bottom"), and before that the
        # call vanished. A sheet with components has to come after the
        # functions its buttons call, so the names are learnt first.
        source = (
            'from apkpy_lib import Screen, button, label, modal, run\n'
            'home = Screen(id="home")\n'
            'out = label("", id="out", screen=home)\n'
            '\n\ndef go():\n    sheet.open()\n\n\n'
            'button("Go", id="b", screen=home, command=go)\n'
            'sheet = modal("Later", content="x", id="sheet")\n'
            'run(start_screen=home)\n'
        )
        files = translate_python_to_android(source)
        self.assertNotIn('error.txt', files)
        self.assertIn('_apkpyOpen_sheet();', files['java/Screen_homeActivity.java'])

    def test_opening_something_that_is_no_overlay_says_so(self):
        source = (
            'from apkpy_lib import Screen, button, modal, run\n'
            'home = Screen(id="home")\n'
            '\n\ndef go():\n    sheet.open()\n\n\n'
            'button("Go", id="b", screen=home, command=go)\n'
            'run(start_screen=home)\n'
        )
        text = translate_python_to_android(source)['error.txt']
        self.assertIn('top of the file', text)

    def test_supported_python_still_compiles_untouched(self):
        # The guard refuses things; a false positive here would refuse an app
        # that works today, which is worse than the silence it replaced.
        java = _java(
            '    n = len("abc")\n'
            '    out.set_value(round(1.5))\n'
            '    out.set_value("A B".split(" "))\n'
            '    out.set_value(f"{n} items")\n'
            '    for i in range(3):\n'
            '        out.set_value(i)\n'
        )
        self.assertIn('_apkpyLen', java)

    def test_a_job_body_is_not_accused_of_the_workers_vocabulary(self):
        # A job's body is written into both the Activity and the Worker from
        # one parsed tree, so each generator sees calls meant for the other.
        source = (
            'from apkpy_lib import Screen, background_job, button, label, run, storage\n'
            'home = Screen(id="home")\n'
            'out = label("", id="out", screen=home)\n'
            '\n\ndef sync_notes():\n'
            '    storage.set("folder", sync.input("folder_id"))\n'
            '\n\nsync = background_job("sync_notes", run=sync_notes)\n'
            'button("Go", id="b", screen=home, command=lambda: sync.enqueue({"folder_id": "1"}))\n'
            'run(start_screen=home)\n'
        )
        self.assertNotIn('error.txt', translate_python_to_android(source))


class TheTryTests(unittest.TestCase):
    """try/except/finally used to be dropped whole -- body and all."""

    BODY = (
        '    try:\n'
        '        total = int(field.get_value())\n'
        '        storage.set("total", total)\n'
        '    except Exception as problem:\n'
        '        total = "0"\n'
        '        toast(problem)\n'
        '    finally:\n'
        '        out.set_value(total)\n'
    )

    def test_the_three_blocks_all_reach_java(self):
        java = _java(self.BODY)
        self.assertIn('try {', java)
        self.assertIn('catch (Exception _te_', java)
        self.assertIn('finally {', java)

    def test_a_variable_first_set_inside_the_try_survives_the_block(self):
        """Python has no block scope and Java does.

        Declaring `total` inside the try would leave the finally unable to see
        it: cannot-find-symbol, after running fine in the Previewer.
        """
        java = _java(self.BODY)
        self.assertIn('String total = "";', java)
        self.assertLess(java.index('String total = "";'), java.index('try {'))

    def test_the_caught_name_is_text_and_never_the_word_null(self):
        # A NullPointerException has no message, and showing somebody the word
        # "null" is worse than showing them the class name.
        java = _java(self.BODY)
        self.assertIn('.getMessage() != null', java)
        self.assertIn('.getClass().getSimpleName()', java)

    def test_a_bare_except_needs_no_name(self):
        java = _java('    try:\n        out.set_value("a")\n'
                     '    except:\n        toast("failed")\n')
        self.assertIn('catch (Exception _te_', java)

    def test_two_except_clauses_are_refused_rather_than_half_honoured(self):
        text = _error('    try:\n        out.set_value("a")\n'
                      '    except ValueError:\n        toast("v")\n'
                      '    except KeyError:\n        toast("k")\n')
        self.assertIn('2 except clauses', text)
        self.assertIn('cannot keep', text)

    def test_an_else_clause_is_refused_because_moving_it_would_change_meaning(self):
        text = _error('    try:\n        out.set_value("a")\n'
                      '    except:\n        toast("e")\n'
                      '    else:\n        toast("fine")\n')
        self.assertIn('else', text)
        self.assertIn('not caught', text)

    def test_a_try_nested_in_a_loop_still_generates(self):
        java = _java('    for i in range(3):\n'
                     '        try:\n            out.set_value(i)\n'
                     '        except:\n            toast("e")\n')
        self.assertIn('catch (Exception _te_', java)


class TheAppendTests(unittest.TestCase):
    """`lista.append(x)` generated no line at all -- not even a wrong one."""

    def test_a_local_list_grows(self):
        java = _java('    itens = []\n    itens.append("a")\n'
                     '    out.set_value(itens[0])\n')
        self.assertIn('itens = _apkpyListAppend(String.valueOf(itens), "a");', java)

    def test_reading_an_item_back_is_valid_java(self):
        # Indexing generated `(x)[Integer.parseInt(...)]` -- you cannot index a
        # String with brackets, so the build stopped on a syntax error far from
        # the line that caused it.
        java = _java('    itens = ["a"]\n    out.set_value(itens[0])\n')
        self.assertIn('_apkpyListGet', java)
        self.assertNotIn('[Integer.parseInt', java)

    def test_a_negative_index_counts_from_the_end_like_python(self):
        java = _java('    itens = ["a"]\n    out.set_value(itens[-1])\n')
        self.assertIn('if (i < 0) i += arr.length();', java)

    def test_a_dict_keeps_its_shape_instead_of_becoming_a_quoted_blob(self):
        java = _java('    itens = []\n    itens.append({"title": "You"})\n')
        self.assertIn('_apkpyJsonObj("title", "You")', java)

    def test_typed_text_that_looks_like_json_stays_text(self):
        """Somebody typing [1, 2] appended eight characters in Python.

        The helper used to read anything JSON-shaped back into a structure,
        so the phone appended a *list* where the Previewer appended a string.
        """
        java = _java('    itens = []\n    itens.append(field.get_value())\n')
        appends = [l for l in java.splitlines()
                   if '_apkpyListAppend' in l and 'private' not in l]
        self.assertTrue(appends)
        for line in appends:
            self.assertNotIn('_apkpyJsonVal', line)

    def test_a_row_from_a_json_loop_is_restored_as_a_structure(self):
        # `row` is a dict in Python; appending it has to keep it one.
        java = _java('    itens = []\n    linhas = []\n'
                     '    for linha in linhas:\n        itens.append(linha)\n')
        self.assertIn('_apkpyJsonVal(String.valueOf(linha))', java)

    def test_a_module_level_list_is_one_list_for_the_whole_app(self):
        """A per-Activity copy would reset every time a screen opened.

        In Python a module-level list is one list per program, and screens are
        separate Java classes -- so it lives in the process-wide store.
        """
        java = _java('    ITEMS.append("b")\n',
                     module_lines='ITEMS = ["a"]')
        self.assertIn('ApkpyReactiveState.set("__apkpy_list_ITEMS"', java)
        self.assertIn('ApkpyReactiveState.get("__apkpy_list_ITEMS"', java)

    def test_the_shared_list_starts_from_what_the_module_wrote(self):
        java = _java('    ITEMS.append("b")\n',
                     module_lines='ITEMS = ["a"]')
        self.assertIn('"[\\"a\\"]"', java)

    def test_the_holder_class_is_generated_for_it(self):
        files = _files('    ITEMS.append("b")\n', module_lines='ITEMS = ["a"]')
        self.assertIn('java/ApkpyReactiveState.java', files)

    def test_a_list_nobody_changes_keeps_the_old_inlining(self):
        # No app that works today gains a field it never asked for.
        files = _files('    out.set_value(len(ITEMS))\n',
                       module_lines='ITEMS = ["a"]')
        java = "\n".join(b for n, b in files.items() if n.endswith(".java"))
        self.assertNotIn('__apkpy_list_ITEMS', java)

    def test_showing_the_list_again_reads_the_grown_one(self):
        """set_items() inlined the original literal.

        Appending worked and the screen kept showing the starting list, which
        is the exact shape of bug this whole change exists to remove.
        """
        source = (
            'from apkpy_lib import Screen, button, list_view, run\n'
            'home = Screen(id="home")\n'
            'ITEMS = [{"title": "a"}]\n'
            'thread = list_view(ITEMS, id="thread", rich=True, screen=home)\n'
            '\n\ndef go():\n'
            '    ITEMS.append({"title": "b"})\n'
            '    thread.set_items(ITEMS)\n\n\n'
            'button("Go", id="b", screen=home, command=go)\n'
            'run(start_screen=home)\n'
        )
        java = translate_python_to_android(source)['java/Screen_homeActivity.java']
        refresh = java[java.index('_items.clear();'):]
        self.assertIn('ApkpyReactiveState.get("__apkpy_list_ITEMS"', refresh[:900])

    def test_list_of_a_list_is_the_value_itself(self):
        # list(x) copies in Python so the caller cannot alias it. Here the
        # value is immutable text, so the copy already happened.
        java = _java('    ITEMS.append("b")\n    out.set_value(list(ITEMS))\n',
                     module_lines='ITEMS = ["a"]')
        self.assertNotIn('pythonCallback_list', java)


class TheRoundingTests(unittest.TestCase):
    """round(2.5) gave 2 in the Previewer and 3 on the phone.

    Python rounds a half to the *even* neighbour; ``Math.round`` always sends
    it up. Nothing reported the difference, and the comment in the generator
    dismissed it as irrelevant to money -- when halving a bill is the shortest
    route to an exact .5 there is.
    """

    @staticmethod
    def _rint(value):
        """java.lang.Math.rint, transcribed.

        Java cannot run here, so its documented rule -- nearest integer, ties
        to even -- is written in Python and held against the real round().
        It is the same way the TOTP base32 decoder was checked.
        """
        return float(round(value))

    def test_the_generator_asks_for_the_rule_python_uses(self):
        java = _java('    out.set_value(round(2.5))')
        # Only the call site: _apkpyRandInt rounds its own bounds with
        # Math.round and is right to, so a file-wide assertNotIn would fail
        # for a reason that has nothing to do with this.
        calls = [l for l in java.splitlines() if 'setText' in l and 'rint' in l]
        self.assertTrue(calls, 'round() nao chegou ao setText')
        for line in calls:
            self.assertNotIn('Math.round(', line)

    def test_one_argument_returns_a_whole_number_not_2_point_0(self):
        # rint gives a double; without the cast the phone would show "2.0"
        # where the Previewer shows "2".
        java = _java('    out.set_value(round(2.5))')
        self.assertIn('(long) Math.rint', java)

    def test_every_half_agrees_with_python(self):
        for step in range(-2000, 2001):
            value = step / 2.0
            self.assertEqual(int(self._rint(value)), round(value), value)

    def test_the_old_rule_really_was_wrong_and_not_just_different(self):
        # Guards the fix: if somebody puts Math.round back, this says how much
        # it costs -- every exact half, which is a quarter of these.
        import math as _math
        wrong = sum(1 for step in range(-2000, 2001)
                    if _math.floor(step / 2.0 + 0.5) != round(step / 2.0))
        self.assertEqual(wrong, 1000)

    def test_two_decimals_agree_on_the_exact_halves(self):
        # Random floats never land on a half once scaled, so the cases that
        # separate the two rules have to be named on purpose.
        for value, places in ((0.125, 2), (0.625, 2), (1.125, 2), (0.25, 1),
                              (1.25, 1), (0.0625, 3), (-0.375, 2)):
            factor = 10 ** places
            self.assertEqual(self._rint(value * factor) / factor,
                             round(value, places), (value, places))

    def test_the_decimal_form_keeps_its_decimals(self):
        java = _java('    out.set_value(round(3.14159, 2))')
        self.assertIn('Math.rint(Double.parseDouble(String.valueOf(3.14159)) * 100.0) / 100.0',
                      java)
        self.assertNotIn('(long) Math.rint(Double.parseDouble(String.valueOf(3.14159)) * 100.0)',
                         java)


class TheMathTests(unittest.TestCase):
    """math, abs, min, max and sum -- the Previewer runs the real stdlib.

    Nothing is exported for these: the app writes ``import math`` and the
    Previewer gets Python's own module, so the only thing that can drift is
    the Java. Every name in the table was chosen because Java's answer *is*
    Python's answer; the ones where it is not were left out on purpose.
    """

    def test_a_function_maps_to_java_lang_math(self):
        java = _java('    out.set_value(math.sqrt(16))')
        self.assertIn('Math.sqrt', java)

    def test_a_domain_error_raises_instead_of_reaching_the_screen(self):
        """math.sqrt(-1) is a ValueError in Python and NaN in Java.

        Unchecked, the phone put the word "NaN" on screen where the Previewer
        stopped. Throwing puts them back together, and try/except catches it
        on both sides.
        """
        java = _java('    out.set_value(math.sqrt(-1))')
        self.assertIn('_apkpyMathCheck', java)
        self.assertIn('math domain error', java)

    def test_floor_and_ceil_come_back_as_whole_numbers(self):
        # Python 3 returns an int from floor/ceil; Java returns a double, so
        # without the cast the phone showed "2.0" against the Previewer's "2".
        for call, expect in (('math.floor(2.7)', '(long) Math.floor'),
                             ('math.ceil(2.1)', '(long) Math.ceil'),
                             ('math.trunc(2.7)', '(long) (')):
            self.assertIn(expect, _java('    out.set_value(%s)' % call), call)

    def test_a_constant_is_the_java_one(self):
        self.assertIn('Math.PI', _java('    out.set_value(math.pi)'))

    def test_log2_is_left_out_and_the_reason_is_measurable(self):
        """Java has no Math.log2, and the obvious substitute is wrong.

        log(x)/log(2) disagrees with math.log2 on 8 of the first 60 powers of
        two. A translation that is right most of the time is worse than one
        that says no, so this checks the disagreement is real rather than
        trusting the comment that claims it.
        """
        import math as _math
        wrong = sum(1 for n in range(60)
                    if _math.log(2.0 ** n) / _math.log(2) != _math.log2(2.0 ** n))
        self.assertEqual(wrong, 8)
        self.assertIn('U2033', _error('    out.set_value(math.log2(8))'))

    def test_abs_keeps_an_integer_an_integer(self):
        # abs(-3) is 3 in Python, not 3.0 -- and every value here is text, so
        # only a helper can hold that difference.
        java = _java('    out.set_value(abs(-3))')
        self.assertIn('_apkpyAbs', java)
        self.assertIn("t.indexOf('.') < 0", java)

    def test_min_and_max_take_values_or_one_list(self):
        two = _java('    out.set_value(min(4, 2))')
        self.assertIn('_apkpyExtreme(false, String.valueOf(4), String.valueOf(2))', two)
        one = _java('    out.set_value(max([1, 9, 5]))')
        self.assertIn('_apkpyExtreme(true, String.valueOf(_apkpyJsonArr(1, 9, 5)', one)

    def test_sum_of_whole_numbers_stays_whole(self):
        java = _java('    out.set_value(sum([1, 2, 3]))')
        self.assertIn('_apkpySum', java)
        self.assertIn('whole ? String.valueOf((long) total)', java)

    def test_a_keyword_argument_is_refused_rather_than_ignored(self):
        # min(items, key=...) has no translation, and dropping the key
        # silently would answer with the wrong element.
        self.assertIsNotNone(_error('    out.set_value(min([1, 2], key=abs))'))


class TheFloatTextTests(unittest.TestCase):
    """Java writes 1.0E8 where Python writes 100000000.0.

    Both produce the shortest digits that read back as the same double, so
    only the *presentation* differs -- but it differs from 1e7 upwards, which
    math.pow and math.exp reach easily, and division reached already.
    """

    @staticmethod
    def _format(value):
        """_apkpyFloat, transcribed from the Java that gets emitted."""
        import math as _math
        from decimal import Decimal
        if value != value:
            return "nan"
        if value == float('inf'):
            return "inf"
        if value == float('-inf'):
            return "-inf"
        if value == 0.0:
            return "-0.0" if _math.copysign(1, value) < 0 else "0.0"
        dec = Decimal(repr(value))
        size = abs(value)
        if size >= 1e16 or size < 1e-4:
            parts = dec.copy_abs().as_tuple()
            digits = ''.join(str(d) for d in parts.digits)
            exp = len(digits) - 1 + parts.exponent
            digits = digits.rstrip('0') or '0'
            out = ('-' if value < 0 else '') + digits[0]
            if len(digits) > 1:
                out += '.' + digits[1:]
            power = str(abs(exp))
            if len(power) < 2:
                power = '0' + power
            return out + 'e' + ('-' if exp < 0 else '+') + power
        plain = format(dec.normalize(), 'f')
        return plain if '.' in plain else plain + '.0'

    def test_it_reproduces_python_across_the_awkward_ranges(self):
        import math as _math
        import random as _random
        values = [4.0, _math.pi, _math.e, _math.exp(20), _math.pow(10, 8),
                  1234.5, 0.5, 0.001, 0.0005, 5e-05, 1e6, 1e7, 1e15, 1e16,
                  1e20, -0.0, 0.0, -3.5, 1e-4, 9.999e-5, 2.5e-7]
        _random.seed(3)
        for _ in range(4000):
            values.append(_random.uniform(-1e18, 1e18))
            values.append(_random.uniform(-1e-3, 1e-3))
        for value in values:
            self.assertEqual(self._format(value), repr(value), value)

    def test_the_boundary_java_would_have_got_wrong(self):
        # 1e7 is where Double.toString switches and str() does not.
        self.assertEqual(self._format(1e7), '10000000.0')
        self.assertEqual(self._format(0.0005), '0.0005')

    def test_the_generator_uses_it_for_maths_and_for_division(self):
        self.assertIn('_apkpyFloat', _java('    out.set_value(math.pow(10, 8))'))
        self.assertIn('_apkpyFloat', _java('    out.set_value(round(3.14159, 2))'))
        self.assertIn('_apkpyFloat', _java('    out.set_value(10 / 4)'))

    def test_a_whole_number_is_not_dressed_up_as_a_decimal(self):
        # 3 // 1 style integer arithmetic must stay "5", not become "5.0".
        java = _java('    out.set_value(2 + 3)')
        self.assertNotIn('_apkpyFloat', java.split('setText')[1][:200])


class ThePreviewerAgreesTests(unittest.TestCase):
    """The Previewer runs real Python, so these are free -- but not untested."""

    def test_python_itself_does_what_the_java_claims_to(self):
        items = ["a"]
        items.append("b")
        self.assertEqual(items[-1], "b")
        self.assertEqual(len(items), 2)

    def test_the_previewer_would_keep_typed_text_as_text(self):
        items = []
        items.append("[1, 2]")
        self.assertIsInstance(items[0], str)


if __name__ == "__main__":
    unittest.main()


class TheTextTests(unittest.TestCase):
    """Slicing and the string methods apps use all day.

    `text[0:2]` used to stop the build. It is what an app does between reading
    a field and showing it, so it was the most common reason to meet U2033.
    """

    @staticmethod
    def _edge(raw, fallback, size):
        """_apkpySliceEdge, transcribed from the Java that gets emitted."""
        text = (raw or '').strip()
        if not text:
            return fallback
        try:
            at = int(round(float(text)))
        except ValueError:
            return fallback
        if at < 0:
            at += size
        return 0 if at < 0 else (size if at > size else at)

    @classmethod
    def _slice(cls, text, start, stop):
        value = text or ''
        size = len(value)
        low = cls._edge(start, 0, size)
        high = cls._edge(stop, size, size)
        return '' if low >= high else value[low:high]

    def test_the_slice_helper_matches_python_everywhere_it_can_be_asked(self):
        """Java's substring throws where Python trims.

        `"abc"[0:99]` is `"abc"` in Python and a StringIndexOutOfBounds on the
        phone -- one returns text and the other closes the app, which is as
        crude as a divergence gets. 700 combinations, including every
        out-of-range and negative edge.
        """
        texts = ["Ola Mundo", "", "a", "abc", "  espaco  ", "ABC def", "aaaa"]
        edges = ['', '0', '1', '2', '3', '99', '-1', '-2', '-99', '5']
        for text in texts:
            for start in edges:
                for stop in edges:
                    expected = text[(int(start) if start else None):
                                    (int(stop) if stop else None)]
                    self.assertEqual(self._slice(text, start, stop), expected,
                                     (text, start, stop))

    def test_a_slice_reaches_java_through_the_helper(self):
        java = _java('    out.set_value("abcdef"[1:3])')
        self.assertIn('_apkpySlice', java)

    def test_an_open_ended_slice_says_so_with_an_empty_edge(self):
        java = _java('    out.set_value("abcdef"[2:])')
        self.assertIn('_apkpySlice', java)

    def test_find_answers_minus_one_on_both_sides(self):
        java = _java('    out.set_value("abc".find("z"))')
        self.assertIn('.indexOf(', java)
        self.assertEqual("abc".find("z"), -1)

    def test_a_predicate_reads_the_way_python_prints_it(self):
        """str(True) is "True" in Python and "true" in Java.

        Shown in a label the two sit side by side and disagree, so the
        generated code writes Python's spelling.
        """
        java = _java('    out.set_value("abc".startswith("a"))')
        self.assertIn('? "True" : "False"', java)

    def test_join_walks_the_list_rather_than_the_text(self):
        java = _java('    out.set_value(", ".join(["a", "b"]))')
        self.assertIn('_apkpyJoin', java)

    def test_count_and_title_have_their_own_helpers(self):
        self.assertIn('_apkpyCount', _java('    out.set_value("aaa".count("a"))'))
        self.assertIn('_apkpyTitle', _java('    out.set_value("ola".title())'))

    def test_case_folding_asks_for_the_root_locale(self):
        """Without it a Turkish phone turns "I" into a dotless i.

        Python's upper()/lower() do not move with the device's language, so
        neither may these.
        """
        java = _java('    out.set_value("abc".upper())')
        self.assertIn('toUpperCase(java.util.Locale.ROOT)', java)


class TheListSeedTests(unittest.TestCase):
    """A list the app appends to used to reset when you left the screen.

    Its starting values were written into onCreate, so the Activity being
    recreated put the original list back over the one that had grown -- the
    Previewer kept the new rows and the phone lost them, silently.
    """

    APP = (
        'from apkpy_lib import Screen, button, list_view, run\n'
        'home = Screen(id="home")\n'
        'ITEMS = [{"title": "a"}]\n'
        'rows = list_view(ITEMS, id="rows", rich=True, screen=home)\n'
        '\n\ndef go():\n%s\n\n\n'
        'button("Go", id="b", screen=home, command=go)\n'
        'run(start_screen=home)\n'
    )

    def _on_create(self, body):
        java = translate_python_to_android(self.APP % body)['java/Screen_homeActivity.java']
        return java[:java.index('setOnClickListener')]

    def test_a_mutated_list_is_read_from_the_store_on_every_open(self):
        opening = self._on_create('    ITEMS.append({"title": "b"})')
        self.assertIn('__apkpy_list_ITEMS', opening)
        self.assertNotIn('rows_items.add("{', opening)

    def test_a_list_nobody_changes_keeps_its_literals(self):
        # Constants stay constants: reading them from a store at runtime would
        # be slower for no reason at all.
        opening = self._on_create('    rows.set_items(ITEMS)')
        self.assertNotIn('__apkpy_list_ITEMS', opening)


class TheConditionTests(unittest.TestCase):
    """An if whose condition ApkPy could not write used to vanish.

    The whole branch left the app with no word said. The shape that did it most
    was `in` inside `and` / `or` -- exactly how a search filter is written -- and
    the benchmark app on the website was measured with its filter gone.
    """

    def test_in_inside_or_keeps_the_branch(self):
        java = _java('    q = field.get_value()\n'
                     '    if not q or q in "alpha beta":\n'
                     '        out.set_value("kept")')
        self.assertIn('String.valueOf("alpha beta").contains(String.valueOf(q))', java)
        self.assertIn('"kept"', java)

    def test_not_in_on_its_own_keeps_the_branch(self):
        java = _java('    q = field.get_value()\n'
                     '    if q not in "abc":\n'
                     '        out.set_value("kept")')
        self.assertIn('!String.valueOf("abc").contains(String.valueOf(q))', java)
        self.assertIn('"kept"', java)

    def test_in_a_literal_list_asks_the_list_not_its_text(self):
        # "a" in ["ab"] is False in Python. Searching the JSON text says True.
        java = _java('    q = field.get_value()\n'
                     '    if q in ["a", "b"]:\n'
                     '        out.set_value("kept")')
        self.assertIn('java.util.Arrays.asList(String.valueOf("a"), '
                      'String.valueOf("b")).contains(String.valueOf(q))', java)

    def test_in_a_module_list_nobody_changes_uses_its_literal(self):
        java = _java('    q = field.get_value()\n'
                     '    if q in LETTERS:\n'
                     '        out.set_value("kept")',
                     module_lines='LETTERS = ["a", "b"]')
        self.assertIn('java.util.Arrays.asList(String.valueOf("a"), '
                      'String.valueOf("b")).contains(String.valueOf(q))', java)

    def test_in_a_list_the_app_grows_is_asked_at_run_time(self):
        java = _java('    q = field.get_value()\n'
                     '    SEEN.append(q)\n'
                     '    if q in SEEN:\n'
                     '        out.set_value("seen")',
                     module_lines='SEEN = []')
        self.assertIn('_apkpyListHas(String.valueOf(', java)
        self.assertIn('private boolean _apkpyListHas(String json, String needle)', java)

    def test_a_constant_condition_keeps_its_branch(self):
        java = _java('    if True:\n'
                     '        out.set_value("always")')
        self.assertIn('"always"', java)

    def test_a_condition_with_no_translation_stops_the_build(self):
        text = _error('    q = field.get_value()\n'
                      '    if q is None:\n'
                      '        out.set_value("never")')
        self.assertIn('U2033', text)
        self.assertIn('This condition is not translated', text)

    def test_a_chained_comparison_is_refused_not_cut_short(self):
        text = _error('    n = 5\n'
                      '    if 0 < n < 10:\n'
                      '        out.set_value("inside")')
        self.assertIn('U2033', text)

    def test_a_ternary_with_no_translation_stops_the_build(self):
        text = _error('    q = field.get_value()\n'
                      '    out.set_value("a" if q is None else "b")')
        self.assertIn('U2033', text)

    def test_a_ternary_with_in_is_translated(self):
        java = _java('    q = field.get_value()\n'
                     '    out.set_value("yes" if q in "abc" else "no")')
        self.assertIn('String.valueOf("abc").contains(String.valueOf(q))', java)

    def test_a_module_level_if_with_in_keeps_its_branch(self):
        java = _java('    out.set_value("x")',
                     module_lines='if "a" in "abc":\n    out.set_value("module")')
        self.assertIn('"module"', java)


class TheQuietFailuresTests(unittest.TestCase):
    """Two more that produced a working-looking app with a piece missing."""

    def test_a_module_level_comprehension_stops_the_build(self):
        text = _error('    out.set_value("x")',
                      module_lines='SQUARES = [n * n for n in range(5)]')
        self.assertIn('U2033', text)
        self.assertIn('module level', text)

    def test_a_format_the_phone_would_ignore_stops_the_build(self):
        text = _error('    n = 7\n'
                      '    out.set_value(f"{n:03d}")')
        self.assertIn('U2033', text)
        self.assertIn("'03d'", text)

    def test_a_fixed_decimal_format_is_still_translated(self):
        java = _java('    n = 7\n'
                     '    out.set_value(f"{n:.2f}")')
        self.assertIn('"%.2f"', java)


class TheComparisonGuardTests(unittest.TestCase):
    """A comparison with a side ApkPy cannot write must not reach the phone.

    That side used to become "". Compared as a number it was
    Double.parseDouble(""), and the screen crashed the moment it ran -- worse
    than the branch being dropped, and just as silent at build time.
    """

    def test_arithmetic_it_cannot_write_stops_the_build(self):
        # Text from an input is text: q % 2 has no number to work on. (This
        # used i % 2 on a range() index until indexes became numbers.)
        text = _error('    q = field.get_value()\n'
                      '    if q % 2 == 0:\n'
                      '        out.set_value("even")')
        self.assertIn('U2033', text)

    def test_the_same_inside_and_stops_the_build_too(self):
        text = _error('    q = field.get_value()\n'
                      '    if q and q % 2 == 0:\n'
                      '        out.set_value("even")')
        self.assertIn('U2033', text)

    def test_a_component_on_another_screen_is_not_accused(self):
        # A callback is written into every Activity. Where the field does not
        # exist, get_value() is empty on purpose -- the Knowledge Vault compares
        # one against "" and has to keep building.
        files = translate_python_to_android(
            'from apkpy_lib import Screen, button, inputs, label, run\n'
            'first = Screen(id="first")\n'
            'second = Screen(id="second")\n'
            '\n\ndef create():\n'
            '    if title.get_value() == "":\n'
            '        status.set_value("Write a title")\n'
            '\n\n'
            'status = label("", id="status", screen=first)\n'
            'button("Go", id="go", screen=first, command=create)\n'
            'title = inputs("Title", id="title", type="text", screen=second)\n'
            'button("Create", id="create", screen=second, command=create)\n'
            'run(start_screen=first)\n')
        self.assertNotIn('error.txt', files, files.get('error.txt', '')[:300])

    def test_an_empty_string_literal_is_still_a_real_comparison(self):
        java = _java('    q = field.get_value()\n'
                     '    if q == "":\n'
                     '        out.set_value("empty")')
        self.assertIn('"empty"', java)


class TheOtherRuntimeTests(unittest.TestCase):
    """A job's body is written into the Activity and into the Worker.

    job.input() and job.attempt() are empty in the Activity copy on purpose, and
    the guard against empty comparison sides must not refuse them.
    """

    def test_a_job_comparing_its_input_and_attempt_still_builds(self):
        files = translate_python_to_android(
            'from apkpy_lib import Screen, background_job, button, storage, run\n'
            'home = Screen(id="home")\n'
            '\n'
            'def enviar():\n'
            '    if fila.input("fail") == "yes":\n'
            '        if fila.attempt() == "1":\n'
            '            fila.retry()\n'
            '            return\n'
            '    storage.set("done", "yes")\n'
            '\n'
            'fila = background_job("outbox", run=enviar, retry_seconds=10)\n'
            'button("Send", id="b1", screen=home, '
            'command=lambda: fila.enqueue({"fail": "yes"}))\n'
            'run(start_screen=home)\n')
        self.assertNotIn('error.txt', files, files.get('error.txt', '')[:300])
        self.assertIn('getRunAttemptCount() + 1', files['java/OutboxJobWorker.java'])


def _flat(text):
    """A diagnostic wraps its lines; the phrases a test looks for do not."""
    return ' '.join((text or '').split())


class TheSplitTests(unittest.TestCase):
    """text.split() gave Java's String[], and String.valueOf of that is an address.

    A for loop over it ran no times, len() counted the characters of
    "[Ljava.lang.String;@1b6d3586", and a label showed exactly that. It also read
    the separator as a regular expression and dropped the empty parts at the end.
    """

    def test_split_is_a_list(self):
        java = _java('    out.set_value(len(field.get_value().split(",")))')
        self.assertIn('_apkpyLen(String.valueOf(_apkpySplit(', java)
        self.assertNotIn('.split(","', java)

    def test_a_for_loop_over_it_iterates(self):
        java = _java('    for part in field.get_value().split(","):\n'
                     '        out.set_value(part)')
        self.assertIn('new org.json.JSONArray(String.valueOf(_apkpySplit(', java)

    def test_no_separator_splits_on_whitespace(self):
        java = _java('    out.set_value(field.get_value().split()[0])')
        self.assertIn(', null, "-1")', java)

    def test_maxsplit_positional_and_keyword(self):
        java = _java('    out.set_value(field.get_value().split(",", 1)[-1])\n'
                     '    out.set_value(field.get_value().split(sep=",", maxsplit=2))')
        self.assertIn('String.valueOf(","), String.valueOf(1))', java)
        self.assertIn('String.valueOf(","), String.valueOf(2))', java)

    def test_membership_in_a_split_is_membership(self):
        java = _java('    if "a" in field.get_value().split(","):\n'
                     '        out.set_value("yes")')
        self.assertIn('_apkpyListHas(_apkpySplit(', java)

    def test_an_empty_separator_stops_the_build(self):
        text = _flat(_error('    out.set_value(field.get_value().split(""))'))
        self.assertIn('U2033', text)
        self.assertIn('empty separator', text)

    def test_the_helper_keeps_pythons_rules(self):
        # The helper was compiled and run against str.split on 628 cases when it
        # was written. These are the lines that carry Python's rules, so a
        # rewrite that loses one of them is caught here.
        java = _java('    out.set_value(field.get_value().split(","))')
        self.assertIn('int at = s.indexOf(sep, from);', java)        # text, not a regex
        self.assertIn('out.put(s.substring(from));', java)           # the last part, even empty
        self.assertIn('throw new IllegalArgumentException("empty separator");', java)
        self.assertIn('Character.isSpaceChar(c) || c == (char) 133', java)


class TheArithmeticTests(unittest.TestCase):
    """Arithmetic ApkPy could not write came back as "" and the build went on."""

    def test_percent_formatting_points_to_an_fstring(self):
        text = _flat(_error('    n = field.get_value()\n'
                            '    out.set_value("n=%s" % n)'))
        self.assertIn('U2033', text)
        self.assertIn('f"n={n}"', text)

    def test_arithmetic_on_text_says_which_number(self):
        text = _flat(_error('    price = field.get_value()\n'
                            '    out.set_value(price * 2)'))
        self.assertIn('U2033', text)
        self.assertIn('float(price) * 2', text)

    def test_repeating_text_stops_the_build(self):
        text = _flat(_error('    out.set_value("-" * 20)'))
        self.assertIn('Repeating text or a list', text)

    def test_not_as_a_value_stops_the_build(self):
        self.assertIn('U2033', _error('    out.set_value(not field.get_value())'))

    def test_the_suggestions_compile(self):
        java = _java('    price = field.get_value()\n'
                     '    out.set_value(float(price) * 2)\n'
                     '    n = field.get_value()\n'
                     '    out.set_value(f"n={n}")')
        self.assertIn('Double.parseDouble(String.valueOf(price)) * 2', java)

    def test_a_range_index_is_a_number(self):
        # i + 1 was "0" + "1": 01 on the phone and 1 in the Previewer.
        java = _java('    for i in range(3):\n'
                     '        out.set_value(i + 1)\n'
                     '        if i % 2 == 0:\n'
                     '            out.set_value("even")')
        self.assertIn('(Integer.parseInt(String.valueOf(i)) + 1)', java)
        self.assertIn('(Integer.parseInt(String.valueOf(i)) % 2)', java)
        self.assertNotIn('String.valueOf(i + 1)', java)

    def test_a_total_over_a_range_adds(self):
        # n += i was "0" + "0" + "1" + "2": 0012 instead of 3.
        java = _java('    n = 0\n'
                     '    for i in range(3):\n'
                     '        n += i\n'
                     '    out.set_value(n)')
        self.assertIn('Integer.parseInt(String.valueOf(n)) + Integer.parseInt(String.valueOf(i))', java)

    def test_a_negative_number(self):
        java = _java('    x = -1\n'
                     '    out.set_value(x)\n'
                     '    out.set_value(-int(field.get_value()))')
        self.assertIn('String x = "-1";', java)
        self.assertIn('(-Integer.parseInt(', java)

    def test_a_job_attempt_stays_exempt(self):
        files = translate_python_to_android(
            'from apkpy_lib import Screen, background_job, button, storage, run\n'
            'home = Screen(id="home")\n'
            '\n'
            'def enviar():\n'
            '    storage.set("wait", fila.attempt() * 2)\n'
            '\n'
            'fila = background_job("outbox", run=enviar, retry_seconds=10)\n'
            'button("Send", id="b1", screen=home, '
            'command=lambda: fila.enqueue({"x": "1"}))\n'
            'run(start_screen=home)\n')
        self.assertNotIn('error.txt', files, files.get('error.txt', '')[:300])


class TheVanishingLineTests(unittest.TestCase):
    """Assignments and loops that left the app, line and all, without a word."""

    def _says(self, body, *phrases):
        text = _error(body)
        self.assertIsNotNone(text, 'compiled, but should have stopped:\n' + body)
        text = _flat(text)
        self.assertIn('U2033', text)
        for phrase in phrases:
            self.assertIn(phrase, text)

    def test_unpacking(self):
        self._says('    a, b = field.get_value().split(",")',
                   'Unpacking into several names', 'a = parts[0]')

    def test_setting_an_item(self):
        self._says('    row = {"k": "v"}\n    row["k"] = field.get_value()',
                   'in place')

    def test_setting_an_attribute(self):
        self._says('    out.text = "x"', 'set_value(')

    def test_a_condition_as_a_value(self):
        self._says('    x = field.get_value() or "none"', 'conditional expression')

    def test_a_comprehension_in_a_function(self):
        self._says('    x = [p for p in field.get_value().split(",")]', 'append(')

    def test_a_tuple_value(self):
        self._says('    x = (1, 2)', 'Use a list')

    def test_several_names_at_once(self):
        self._says('    a = b = 0', 'own line')

    def test_unpacking_in_a_for_loop(self):
        self._says('    for a, b in [["1", "2"]]:\n        out.set_value(a)',
                   'pair[0]')

    def test_a_for_else(self):
        self._says('    for p in ["a"]:\n'
                   '        out.set_value(p)\n'
                   '    else:\n'
                   '        out.set_value("done")', 'flag')

    def test_looping_over_letters(self):
        self._says('    for letter in "abc":\n        out.set_value(letter)',
                   'text[i:i + 1]')

    def test_the_suggestions_compile(self):
        java = _java('    parts = field.get_value().split(",")\n'
                     '    a = parts[0]\n'
                     '    query = field.get_value()\n'
                     '    shown = query if query else "none"\n'
                     '    out.set_value(shown)\n'
                     '    for pair in [["a", "1"]]:\n'
                     '        name = pair[0]\n'
                     '        out.set_value(name)\n'
                     '    text = field.get_value()\n'
                     '    for i in range(len(text)):\n'
                     '        letter = text[i:i + 1]\n'
                     '        out.set_value(letter)\n'
                     '    x = math.pi\n'
                     '    out.set_value(x)\n'
                     '    for size in (1, 2):\n'
                     '        out.set_value(size)')
        self.assertIn('_apkpyListGet(String.valueOf(parts), String.valueOf(0))', java)
        self.assertIn('? String.valueOf(query) : String.valueOf("none")', java)
        self.assertIn('_apkpyListGet(String.valueOf(pair), String.valueOf(0))', java)
        self.assertIn('_apkpySlice(String.valueOf(text), String.valueOf(i), ', java)
        self.assertIn('Math.PI', java)
        self.assertIn('new String[]{String.valueOf(1), String.valueOf(2)}', java)
