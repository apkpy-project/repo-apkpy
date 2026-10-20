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
        # any() is translated now (phase 1, group 7); filter() is not.
        text = _error('    out.set_value(str(filter(None, [1, 2])))')
        self.assertIn('filter', text)
        self.assertIn('a for loop with an if', text)

    def test_a_slice_with_a_step_takes_every_kth(self):
        # Refused until phase 1, group 8; returning every character when the
        # author asked for every second one would have been worse.
        java = _java('    out.set_value("abcdef"[0:6:2])')
        self.assertIn('_apkpySliceStep(String.valueOf("abcdef"), String.valueOf(0), '
                      'String.valueOf(6), String.valueOf(2), 3)', java)

    def test_slicing_never_writes_the_broken_java_it_used_to(self):
        # It generated `(x)[Integer.parseInt("")]`, which is not Java at all.
        java = _java('    out.set_value("abcdef"[0:2])')
        self.assertNotIn('[Integer.parseInt', java)
        self.assertIn('_apkpySlice', java)

    def test_print_is_not_quietly_turned_into_a_missing_method(self):
        # print("x") compiled to pythonCallback_print(...) and the build died
        # on cannot-find-symbol, pointing into a file nobody wrote. Since
        # phase 1 (group 12) it goes to Logcat.
        java = _java('    print("hello")')
        self.assertNotIn('pythonCallback_print', java)
        self.assertIn('ApkpyValues.print(String.valueOf("hello"), "\\n");', java)

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
        self.assertIn('catch (Throwable _te_', java)
        self.assertIn('finally {', java)

    def test_a_variable_first_set_inside_the_try_survives_the_block(self):
        """Python has no block scope and Java does.

        Declaring `total` inside the try would leave the finally unable to see
        it: cannot-find-symbol, after running fine in the Previewer.
        """
        java = _java(self.BODY)
        body = java[java.index('void pythonCallback_go()'):]
        self.assertIn('String total = "";', body)
        self.assertLess(body.index('String total = "";'), body.index('try {'))

    def test_the_caught_name_is_text_and_never_the_word_null(self):
        # A NullPointerException has no message, and showing somebody the word
        # "null" is worse than showing them the class name.
        java = _java(self.BODY)
        self.assertIn('problem = ApkpyValues.message(_te_', java)
        self.assertIn('return m != null ? m : t.getClass().getSimpleName();', java)

    def test_a_bare_except_needs_no_name(self):
        java = _java('    try:\n        out.set_value("a")\n'
                     '    except:\n        toast("failed")\n')
        self.assertIn('catch (Throwable _te_', java)
        self.assertRegex(java, r'ApkpyValues\.isA\(_te_\d+, "BaseException"\)')

    def test_each_except_tests_its_own_type(self):
        # Phase 1, group 11: this was refused, because one handler caught
        # everything and a second could not be told apart.
        java = _java('    try:\n        out.set_value("a")\n'
                     '    except ValueError:\n        toast("v")\n'
                     '    except (KeyError, IndexError):\n        toast("k")\n')
        self.assertRegex(java, r'if \(ApkpyValues\.isA\(_te_\d+, "ValueError"\)\) \{')
        self.assertRegex(java, r'\} else if \(ApkpyValues\.isA\(_te_\d+, "KeyError", "IndexError"\)\) \{')
        # One that no except names goes on, as in Python.
        self.assertRegex(java, r'throw ApkpyValues\.rethrow\(_te_\d+\);')

    def test_an_else_runs_only_when_nothing_failed(self):
        java = _java('    try:\n        n = int(field.get_value())\n'
                     '    except ValueError:\n        toast("e")\n'
                     '    else:\n        out.set_value(str(n))\n')
        # The flag is set on the body's last line; the else is outside the
        # try, so its own errors are not caught by the except.
        self.assertIn('_apkpy_ok1 = ApkpyValues.TRUE;', java)
        self.assertLess(java.index('catch (Throwable'), java.index('if (_apkpyTruthy(_apkpy_ok1)) {'))

    def test_a_try_nested_in_a_loop_still_generates(self):
        java = _java('    for i in range(3):\n'
                     '        try:\n            out.set_value(i)\n'
                     '        except:\n            toast("e")\n')
        self.assertIn('catch (Throwable _te_', java)


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
        # _apkpyTrunc is the cast that also refuses nan and inf, as round() does.
        self.assertIn('String.valueOf(_apkpyTrunc(Math.rint(', java)

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
        # The exact value rounded half to even, as CPython: rint(x * 100) / 100
        # rounded the product first and disagreed on round(-0.025, 2).
        self.assertIn('_apkpyFloat(_apkpyRoundTo(((double)(3.14159)), 2))', java)
        self.assertNotIn('* 100.0) / 100.0', java)


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
        self.assertIn('_apkpyBool(String.valueOf("abc").startsWith(', java)
        self.assertIn('public static final String TRUE = new String("True");', java)

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
                      '    if {q}:\n'
                      '        out.set_value("never")')
        self.assertIn('U2033', text)
        self.assertIn('This condition is not translated', text)

    def test_a_chained_comparison_keeps_every_pair(self):
        # It compiled as its first comparison and lost the rest, then it was
        # refused; now each pair is joined with &&, as Python reads it.
        java = _java('    n = len(field.get_value())\n'
                     '    if 0 < n < 10:\n'
                     '        out.set_value("inside")')
        self.assertRegex(java, r'if \(\(\(0\) < .*n.*\)\) && \(.*n.*< 10\)\)')

    def test_a_chain_around_len_is_translated(self):
        java = _java('    q = field.get_value()\n'
                     '    if 0 < len(q) <= 10:\n'
                     '        out.set_value("fits")')
        self.assertIn('"fits"', java)

    def test_a_chain_around_a_function_of_the_app_says_why(self):
        # Read twice on the phone and once in Python: a function could answer
        # differently, or change something, the second time.
        text = _error('    if 0 < count() < 10:\n'
                      '        out.set_value("inside")',
                      module_lines='def count():\n    return 3\n')
        self.assertIn('U2033', text)
        self.assertIn('Put the value in a name first', text)

    def test_a_ternary_with_no_translation_stops_the_build(self):
        text = _error('    q = field.get_value()\n'
                      '    out.set_value("a" if {q} else "b")')
        self.assertIn('U2033', text)

    def test_a_ternary_on_none_is_translated(self):
        java = _java('    q = field.get_value()\n'
                     '    out.set_value("a" if q is None else "b")')
        self.assertIn('_apkpyIsNone(q)', java)

    def test_is_with_anything_but_none_true_or_false_says_why(self):
        text = _error('    q = field.get_value()\n'
                      '    if q is "a":\n'
                      '        out.set_value("x")')
        self.assertIn('U2033', text)
        self.assertIn('Use == to compare values', text)

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

    def test_a_format_spec_is_pythons(self):
        # {n:03d} stopped the build (the phone had shown 7 for 007). Now every
        # spec goes through _apkpyFormat, checked against CPython's format().
        java = _java('    n = 7\n'
                     '    out.set_value(f"{n:03d}")')
        self.assertIn('_apkpyFormat(String.valueOf(n), "03d", 1)', java)

    def test_a_format_python_refuses_stops_the_build(self):
        text = _error('    n = 7\n'
                      '    out.set_value(f"{n:.2q}")')
        self.assertIn('U2033', text)
        self.assertIn("'.2q'", text)

    def test_a_fixed_decimal_rounds_as_python_does(self):
        # String.format("%.2f") rounded the short text half up: 2.675 was
        # 2.68 on the phone and 2.67 in the Previewer.
        java = _java('    n = 7\n'
                     '    out.set_value(f"{n:.2f}")')
        self.assertIn('_apkpyFormat(String.valueOf(n), ".2f", 1)', java)
        self.assertIn('setScale(precision, java.math.RoundingMode.HALF_EVEN)', java)
        self.assertNotIn('String.format(java.util.Locale.US, "%.2f"', java)


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
        self.assertIn('_apkpyItems(String.valueOf(_apkpySplit(', java)

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
        self.assertIn('throw new ApkpyValues.Raised("ValueError", "empty separator");', java)
        self.assertIn('Character.isSpaceChar(c) || c == (char) 133', java)


class TheArithmeticTests(unittest.TestCase):
    """Arithmetic ApkPy could not write came back as "" and the build went on."""

    def test_percent_formatting_is_translated(self):
        java = _java('    n = field.get_value()\n'
                     '    out.set_value("n=%s %.1f" % (n, 2.5))')
        self.assertIn('"n=" + String.valueOf(n) + " " + _apkpyFormat(String.valueOf(2.5), ".1f", 1)', java)

    def test_text_times_a_number_repeats_it_as_python_does(self):
        # It stopped the build with "float(price) * 2". CPython answers
        # "1212" for "12" * 2, and so does the Previewer: the phone agrees now.
        java = _java('    price = field.get_value()\n'
                     '    out.set_value(price * 2)')
        self.assertIn('_apkpyRepeat(String.valueOf(price), 2, false)', java)

    def test_repeating_text_is_translated(self):
        java = _java('    out.set_value("-" * 20)')
        self.assertIn('_apkpyRepeat(String.valueOf("-"), 20, false)', java)

    def test_not_as_a_value_is_pythons(self):
        # It stopped the build; it is True or False now, printed as Python does.
        java = _java('    out.set_value(not field.get_value())')
        self.assertIn('_apkpyBool(!(_apkpyTruthy(', java)

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
        self.assertIn('Math.addExact((long)(Long.parseLong(String.valueOf(i))), (long)(1))', java)
        self.assertIn('Math.floorMod((long)(Long.parseLong(String.valueOf(i))), (long)(2))', java)
        self.assertNotIn('String.valueOf(i + 1)', java)

    def test_a_total_over_a_range_adds(self):
        # n += i was "0" + "0" + "1" + "2": 0012 instead of 3.
        java = _java('    n = 0\n'
                     '    for i in range(3):\n'
                     '        n += i\n'
                     '    out.set_value(n)')
        self.assertIn('Math.addExact((long)(Long.parseLong(String.valueOf(n))), '
                      '(long)(Long.parseLong(String.valueOf(i))))', java)

    def test_a_negative_number(self):
        java = _java('    x = -1\n'
                     '    out.set_value(x)\n'
                     '    out.set_value(-int(field.get_value()))')
        self.assertIn('String x = "-1";', java)
        self.assertIn('Math.negateExact((long)(Long.parseLong(', java)

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

    def test_unpacking_into_an_item_still_says_so(self):
        # a, b = parts is translated since 1.14 (TheUnpackingTests); a target
        # that is not a name is not.
        self._says('    row = {"k": "v"}\n    row["k"], b = field.get_value().split(",")',
                   'Unpacking into several names')

    def test_setting_an_item_of_a_loop_variable_still_says_so(self):
        # row["k"] = v is translated since 1.14; on the variable of a for loop
        # it would change a copy where CPython changes the list's item.
        self._says('    for row in [{"k": "v"}]:\n        row["k"] = field.get_value()',
                   'variable of a for loop', 'range(len(rows))')

    def test_setting_an_attribute(self):
        self._says('    out.text = "x"', 'set_value(')

    def test_a_set_comprehension_in_a_function(self):
        # A list comprehension is translated now; a set has nothing to become.
        self._says('    x = {p for p in field.get_value().split(",")}', 'no sets on the phone')

    def test_changing_a_tuple_still_says_so(self):
        # x = (1, 2) is translated since 1.14 (TheTupleTests); changing it is not.
        self._says('    x = (1, 2)\n    x[0] = 5', 'item assignment', 'use a list')

    def test_one_list_for_several_names_still_says_so(self):
        # a = b = 0 is translated since 1.14 (TheChainedAssignmentTests).
        self._says('    a = b = []', 'own line', 'a = [] and then b = []')

    def test_unpacking_in_a_for_loop_with_else_is_translated(self):
        # It stopped the build up to 1.13; the else is now the lines after
        # the loop, as there is no break to skip them.
        java = _java('    for a, b in [["1", "2"]]:\n        out.set_value(a)\n'
                     '    else:\n        out.set_value("done")')
        self.assertIn('_apkpyUnpack(', java)
        self.assertIn('setText(String.valueOf("done"));', java)

    def test_looping_over_letters_is_translated(self):
        # It ran no times on the phone; since 1.14 it walks the letters, and a
        # dict written out walks its keys.
        java = _java('    for letter in "abc":\n        out.set_value(letter)\n'
                     '    for key in {"a": 1}:\n        out.set_value(key)')
        self.assertIn('_apkpyChars(String.valueOf("abc"))', java)
        self.assertIn('_apkpyKeys(String.valueOf(', java)

    def test_looping_over_a_set_still_says_so(self):
        self._says('    for size in {1, 2}:\n        out.set_value(str(size))', 'set')

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
        # pair comes from a loop over a literal: its kind is decided by the
        # JSON when the app runs, a list here.
        self.assertIn('_apkpyItemAt(String.valueOf(pair), String.valueOf(0))', java)
        self.assertIn('_apkpySlice(String.valueOf(text), String.valueOf(i), ', java)
        self.assertIn('Math.PI', java)
        self.assertIn('new String[]{String.valueOf(1), String.valueOf(2)}', java)


MODULE = (
    'ITEMS = ["a", "b", "c"]\n'
    'PRICES = {"tea": 2, "cake": 3}\n'
    'COUNT = 0\n'
    'def twice(n):\n'
    '    return int(n) * 2\n'
    'def greet(name, greeting="Hello"):\n'
    '    return greeting + " " + name\n'
)


class TheBasicsThatAnsweredWrongTests(unittest.TestCase):
    """Python that built, ran, and gave the phone a different answer.

    Found by reading the Java of the constructs that "translated" (17-10-2026):
    // and ** came out empty, a list was sliced and joined as JSON text, a loop
    over a dict ran no times, and len(name) + 1 glued "3" and "1" together.
    The answers are checked against CPython by compiling these helpers on
    their own; here the build is held to the shape that gives them.
    """

    def _java(self, body):
        return _java(body, module_lines=MODULE)

    def _error(self, body):
        return _error(body, module_lines=MODULE)

    # arithmetic -----------------------------------------------------------

    def test_floor_division_power_and_modulo_are_pythons(self):
        java = self._java('    n = int(field.get_value())\n'
                          '    out.set_value(str(n // 2) + str(n ** 2) + str(n % 3))')
        self.assertIn('Math.floorDiv((long)(Long.parseLong(String.valueOf(n))), (long)(2))', java)
        self.assertIn('_apkpyPowL((long)(Long.parseLong(String.valueOf(n))), (long)(2))', java)
        self.assertIn('Math.floorMod((long)(Long.parseLong(String.valueOf(n))), (long)(3))', java)

    def test_decimals_and_division_by_zero(self):
        java = self._java('    x = float(field.get_value())\n'
                          '    out.set_value(str(x % 2) + str(x // 2) + str(x / 4) + str(2 ** -1))')
        self.assertIn('_apkpyModF(', java)
        self.assertIn('_apkpyFloorDivF(', java)
        self.assertIn('_apkpyDiv((double)(Double.parseDouble(String.valueOf(x))), (double)(4))', java)
        self.assertIn('_apkpyPowF((double)(2), (double)((-1)))', java)
        self.assertIn('throw new ApkpyValues.Raised("ZeroDivisionError", "division by zero")', java)

    def test_an_int_does_not_wrap_round(self):
        java = self._java('    n = int(field.get_value())\n'
                          '    out.set_value(str(n * 100000 + 1 - n) + str(-n))')
        self.assertIn('Math.multiplyExact(', java)
        self.assertIn('Math.addExact(', java)
        self.assertIn('Math.subtractExact(', java)
        self.assertIn('Math.negateExact((long)(Long.parseLong(String.valueOf(n))))', java)

    def test_round_is_the_exact_value_half_to_even(self):
        java = self._java('    x = float(field.get_value())\n'
                          '    out.set_value(str(round(x, 2)) + str(round(1250, -2)))')
        self.assertIn('_apkpyRoundTo(((double)(Double.parseDouble(String.valueOf(x)))), 2)', java)
        self.assertIn('_apkpyRoundL((long)(1250), -2)', java)
        self.assertNotIn('0.01.0', java)

    # a call that answers a number, in a sum -------------------------------

    def test_len_plus_one_is_a_sum(self):
        # "abc" showed "31" on the phone.
        java = self._java('    out.set_value(str(len(field.get_value()) + 1))')
        self.assertIn('Math.addExact((long)(((long) _apkpyTextLen(', java)

    def test_abs_max_min_and_a_function_of_the_app(self):
        java = self._java('    n = int(field.get_value())\n'
                          '    out.set_value(str(abs(n) + max(n, 3) + min(n, 3) + twice(n)))')
        self.assertIn('_apkpyAbsL(Long.parseLong(String.valueOf(n)))', java)
        self.assertIn('Math.max((long)(Long.parseLong(String.valueOf(n))), (long)(3))', java)
        self.assertIn('Math.min((long)(Long.parseLong(String.valueOf(n))), (long)(3))', java)
        self.assertIn('Long.parseLong(String.valueOf(pythonCallback_twice(', java)

    def test_text_plus_a_number_stops_like_cpython(self):
        text = _flat(self._error('    n = int(field.get_value())\n'
                                 '    out.set_value("Total: " + n)'))
        self.assertIn('U2033', text)
        self.assertIn('TypeError', text)

    def test_a_number_plus_something_unknown_is_added_when_it_runs(self):
        # show() is never called here, so nothing says what index holds.
        # (When every call passes a number, index + 1 is a plain sum.)
        java = _java('    out.set_value("x")', module_lines='def show(index):\n'
                     '    out.set_value(str(index + 1))\n')
        self.assertIn('_apkpyAdd(String.valueOf(index), String.valueOf(1))', java)

    # lists, dicts and text ------------------------------------------------

    def test_a_module_list_and_dict_are_fields(self):
        java = self._java('    out.set_value(str(len(ITEMS)) + PRICES["tea"])')
        self.assertIn('private static final String ITEMS = "[\\"a\\",\\"b\\",\\"c\\"]";', java)
        self.assertIn('private static final String PRICES = "{\\"tea\\":2,\\"cake\\":3}";', java)

    def test_a_field_only_where_it_is_read(self):
        java = self._java('    out.set_value("x")')
        self.assertNotIn('private static final String ITEMS', java)

    def test_slices_and_items_by_kind(self):
        java = self._java('    text = field.get_value()\n'
                          '    key = text\n'
                          '    out.set_value(str(len(ITEMS[1:])) + text[0] + text[1:3]'
                          ' + str(PRICES[key]) + ITEMS[-1])')
        self.assertIn('_apkpyListSlice(String.valueOf(ITEMS), String.valueOf(1), String.valueOf(""))', java)
        self.assertIn('_apkpyCharAt(String.valueOf(text), String.valueOf(0))', java)
        self.assertIn('_apkpySlice(String.valueOf(text), String.valueOf(1), String.valueOf(3))', java)
        self.assertIn('_apkpyDictGet(String.valueOf(PRICES), String.valueOf(key))', java)
        self.assertIn('_apkpyListGet(String.valueOf(ITEMS), String.valueOf(-1))', java)

    def test_a_text_slice_counts_letters_as_python_does(self):
        java = self._java('    out.set_value(field.get_value()[1:3])')
        self.assertIn('value.offsetByCodePoints(0, start)', java)

    def test_lists_join_as_one_list(self):
        java = self._java('    both = ITEMS + ["d"]\n    out.set_value(str(len(both)))')
        self.assertIn('_apkpyListConcat(String.valueOf(ITEMS), ', java)
        self.assertIn('_apkpyLen(String.valueOf(both))', java)

    def test_in_and_count_ask_the_keys_and_the_items(self):
        java = self._java('    if "tea" in PRICES:\n        out.set_value(str(ITEMS.count("a")))')
        self.assertIn('_apkpyHasKey(String.valueOf(PRICES), String.valueOf("tea"))', java)
        self.assertIn('_apkpyListCount(String.valueOf(ITEMS), String.valueOf("a"))', java)

    def test_len_of_a_dict_counts_keys(self):
        java = self._java('    out.set_value(str(len(PRICES)))')
        self.assertIn('_apkpyLen(String.valueOf(PRICES))', java)

    # loops ----------------------------------------------------------------

    def test_a_loop_over_a_dict_walks_its_keys(self):
        java = self._java('    for k in PRICES:\n        out.set_value(k)')
        self.assertIn('_apkpyKeys(String.valueOf(PRICES))', java)

    def test_a_loop_over_text_walks_its_letters(self):
        java = self._java('    for ch in field.get_value():\n        out.set_value(ch)')
        self.assertIn('_apkpyChars(String.valueOf(', java)

    def test_an_error_in_the_loop_body_is_not_swallowed(self):
        java = self._java('    for x in ITEMS:\n        out.set_value(x)')
        self.assertNotIn('catch (Exception _fe_', java)

    def test_range_keeps_its_step_and_reads_its_end_once(self):
        java = self._java('    for i in range(10, 0, -3):\n        out.set_value(str(i))')
        self.assertRegex(java, r'for \(int _i_(\w+) = [^,]+, _e_\1 = [^;]+; _i_\1 > _e_\1; _i_\1 -= 3\)')

    def test_a_step_in_a_name_is_checked_when_it_runs(self):
        java = self._java('    step = int(field.get_value())\n'
                          '    for i in range(0, 10, step):\n        out.set_value(str(i))')
        self.assertIn('_apkpyRangeStep(', java)

    def test_a_zero_step_stops_the_build(self):
        self.assertIn('U2033', self._error('    for i in range(0, 10, 0):\n        out.set_value(str(i))'))

    # functions ------------------------------------------------------------

    def test_a_default_value_is_passed_where_the_call_leaves_it_out(self):
        java = self._java('    out.set_value(greet("Ana") + greet(greeting="Hi", name="Rui"))')
        self.assertIn('pythonCallback_greet(String.valueOf("Ana"), String.valueOf("Hello"))', java)
        self.assertIn('pythonCallback_greet(String.valueOf("Rui"), String.valueOf("Hi"))', java)

    def test_a_missing_parameter_stops_the_build(self):
        text = self._error('    out.set_value(greet(greeting="Hi"))')
        self.assertIn('U2037', text)
        self.assertIn('name', text)

    def test_a_none_default_left_out_is_passed_as_none(self):
        java = _java('    out.set_value(pick())',
                     module_lines='def pick(x=None):\n'
                     '    if x is None:\n        return "none"\n    return x\n')
        self.assertIn('pythonCallback_pick(ApkpyValues.NONE)', java)
        self.assertIn('if (_apkpyIsNone(x)) {', java)

    def test_a_button_calls_a_function_with_defaults(self):
        files = translate_python_to_android(
            'from apkpy_lib import Screen, button, label, run\n'
            'home = Screen(id="home")\n'
            'out = label("", id="out", screen=home)\n'
            'def refresh(tag="tap"):\n'
            '    out.set_value(tag)\n'
            'button("Go", id="b", screen=home, command=refresh)\n'
            'run(start_screen=home)\n')
        self.assertNotIn('error.txt', files)
        self.assertIn('pythonCallback_refresh(String.valueOf("tap"));',
                      files['java/Screen_homeActivity.java'])

    def test_global_keeps_one_value_for_the_app(self):
        files = _files('    global COUNT\n    COUNT += 1\n    out.set_value(str(COUNT))',
                       module_lines=MODULE)
        java = files['java/Screen_homeActivity.java']
        self.assertIn('ApkpyReactiveState.set("__apkpy_global_COUNT", String.valueOf(COUNT));', java)
        self.assertIn('ApkpyReactiveState.get("__apkpy_global_COUNT", "0")', java)
        self.assertIn('java/ApkpyReactiveState.java', files)

    def test_a_local_with_the_name_of_a_global_stops_the_build(self):
        text = _error('    global COUNT\n    COUNT += 1',
                      module_lines=MODULE + 'def reset():\n    COUNT = 0\n')
        self.assertIn('U2033', text)
        self.assertIn('global COUNT', text)

    def test_a_global_needs_a_starting_value_written_out(self):
        text = _error('    global TOTAL\n    TOTAL += 1',
                      module_lines=MODULE + 'TOTAL = len(ITEMS)\n')
        self.assertIn('U2033', text)
        self.assertIn('starting value', text)

    # True and False -------------------------------------------------------

    def test_false_kept_in_a_name_is_the_apps_false(self):
        # It wrote `String flag = false;`, which javac refused.
        java = self._java('    flag = False\n    out.set_value(str(flag))')
        self.assertIn('String flag = ApkpyValues.FALSE;', java)

    def test_false_reaches_a_text_parameter_as_the_apps_false(self):
        java = _java('    show(False)', module_lines='def show(flag):\n'
                     '    out.set_value(str(flag))\n')
        self.assertIn('pythonCallback_show(ApkpyValues.FALSE)', java)

    def test_false_tested_with_if_in_the_function_skips_the_branch(self):
        # "False" is not empty, so a test for empty text ran the branch Python
        # skips. The app's False is an object of its own, and false.
        java = _java('    show(False)', module_lines='def show(flag):\n'
                     '    if flag:\n        out.set_value("on")\n')
        self.assertIn('if (_apkpyTruthy(flag)) {', java)
        self.assertIn('v == ApkpyValues.NONE || v == ApkpyValues.FALSE) return false;', java)


PHASE_ONE = ('PRICES = {"tea": 2, "cake": 3}\n'
             'ITEMS = ["a", "b", "c"]\n'
             'CART = {}\n')


class TheUnpackingTests(unittest.TestCase):
    """a, b = parts and its relatives, inside a function (phase 1, group 1).

    Each one is rewritten before translation into the reads Python does:
    one temporary that checks the length, then an item per name.
    """

    def _java(self, body):
        return _java(body, module_lines=PHASE_ONE)

    def test_two_names_from_a_split(self):
        java = self._java('    a, b = field.get_value().split(",")\n'
                          '    out.set_value(a + b)')
        self.assertIn('_apkpyUnpack(', java)
        self.assertIn(', 2, 0, false);', java)       # exactly two, no *rest
        self.assertIn('String b = _apkpyListGet(String.valueOf(_apkpy_u1), String.valueOf(1));', java)

    def test_a_starred_name_takes_the_rest(self):
        java = self._java('    first, *rest = ITEMS\n'
                          '    out.set_value(first + str(len(rest)))')
        self.assertIn(', 1, 0, true);', java)
        self.assertIn('String rest = _apkpyListSlice(String.valueOf(_apkpy_u1), String.valueOf(1),', java)

    def test_a_swap_reads_both_before_writing(self):
        java = self._java('    x = 1\n    y = 2\n    x, y = y, x\n    out.set_value(str(x))')
        self.assertIn('String _apkpy_u1 = y;\n        String _apkpy_u2 = x;\n'
                      '        x = _apkpy_u1;\n        y = _apkpy_u2;', java)

    def test_items_of_a_dict(self):
        java = self._java('    t = ""\n    for k, v in PRICES.items():\n'
                          '        t += k + str(v)\n    out.set_value(t)')
        self.assertIn('_apkpyKeys(String.valueOf(PRICES))', java)
        self.assertIn('v = _apkpyDictGet(String.valueOf(PRICES), String.valueOf(k));', java)

    def test_enumerate_with_a_start(self):
        java = self._java('    t = ""\n    for i, item in enumerate(ITEMS, start=1):\n'
                          '        t += str(i) + item\n    out.set_value(t)')
        self.assertIn('String _apkpy_u1 = "1";', java)
        self.assertIn('item = _apkpyListGet(String.valueOf(ITEMS),', java)

    def test_zip_stops_at_the_shorter(self):
        java = self._java('    t = ""\n    for a, b in zip(ITEMS, field.get_value().split(",")):\n'
                          '        t += a + b\n    out.set_value(t)')
        self.assertIn('_apkpyExtreme(false, ', java)    # min() of the two lengths

    def test_a_name_v_in_a_button_function_does_not_clash(self):
        # The button writes the function's body inside onClick(View v): a
        # `String v` there stopped javac (found building the phase 1 APK).
        java = self._java('    t = ""\n    for k, v in PRICES.items():\n'
                          '        t += k + str(v)\n    out.set_value(t)')
        self.assertIn('public void onClick(View _apkpyTapped) {', java)
        self.assertNotIn('onClick(View v)', java)

    def test_the_wrong_number_of_names_fails_like_python(self):
        # ValueError: too many values to unpack -- the helper says the same.
        java = self._java('    a, b = field.get_value().split(",")\n    out.set_value(a)')
        self.assertIn('too many values to unpack', java)


class TheItemChangeTests(unittest.TestCase):
    """d[k] = v, d[k] += v, del d[k], rows[0]["n"] = v (phase 1, group 2).

    The phone keeps a list or a dict as JSON text, so a change is a new text
    written back to the name -- and to the shared store for a module name.
    """

    def _java(self, body):
        return _java(body, module_lines=PHASE_ONE)

    def test_setting_adding_and_deleting_a_key_of_a_module_dict(self):
        java = self._java('    CART["tea"] = 1\n    CART["tea"] += 2\n'
                          '    del CART["tea"]\n    out.set_value(str(CART))')
        self.assertIn('String CART = _apkpySetItem(String.valueOf(ApkpyReactiveState.get('
                      '"__apkpy_global_CART", "{}")), String.valueOf("tea"), 1, 2, false);', java)
        self.assertIn('_apkpyAdd(', java)
        self.assertIn('CART = _apkpyDelItem(', java)
        self.assertIn('ApkpyReactiveState.set("__apkpy_global_CART", String.valueOf(CART));', java)

    def test_an_item_inside_an_item_stays_json(self):
        # The inner dict went back as a quoted string before.
        java = self._java('    rows = [{"n": 1}]\n    rows[0]["n"] = 5\n'
                          '    out.set_value(str(rows))')
        self.assertIn('rows = _apkpySetItem(String.valueOf(rows), String.valueOf(0), '
                      '_apkpyJsonVal(String.valueOf(_apkpySetItem(', java)


class TheNoneAndTruthTests(unittest.TestCase):
    """None, True and False as values (phase 1, groups 3 and 4).

    Every value on the phone is text, so they are three texts of their own
    (ApkpyValues): they print as Python prints them, and `is None` and
    `if flag:` tell them from the words a person typed.
    """

    def test_the_three_values_are_objects_of_their_own(self):
        files = _files('    out.set_value("x")')
        values = files['java/ApkpyValues.java']
        self.assertIn('public static final String NONE = new String("None");', values)
        self.assertIn('public static final String FALSE = new String("False");', values)

    def test_none_kept_in_a_name_and_asked_with_is(self):
        java = _java('    found = None\n    if found is None:\n        out.set_value("none")\n'
                     '    if found is not None:\n        out.set_value("some")')
        self.assertIn('String found = ApkpyValues.NONE;', java)
        self.assertIn('if (_apkpyIsNone(found)) {', java)
        self.assertIn('if (!_apkpyIsNone(found)) {', java)

    def test_a_function_that_falls_off_the_end_returns_none(self):
        java = _java('    out.set_value(str(find("x") is None))',
                     module_lines='def find(name):\n'
                     '    if name == "a":\n        return "found"\n')
        self.assertIn('return ApkpyValues.NONE;', java)
        self.assertIn('_apkpyBool(_apkpyIsNone(pythonCallback_find(', java)

    def test_or_gives_one_of_the_two_values(self):
        java = _java('    name = field.get_value() or "nobody"\n    out.set_value(name)')
        self.assertIn('(_apkpyTruthy(_apkpyOrT = String.valueOf(', java)
        self.assertIn('? _apkpyOrT : String.valueOf("nobody"))', java)
        self.assertIn('private String _apkpyOrT;', java)

    def test_and_gives_the_first_false_value(self):
        java = _java('    v = field.get_value() and "typed"\n    out.set_value(v)')
        self.assertIn('(!_apkpyTruthy(_apkpyOrT = String.valueOf(', java)

    def test_a_comparison_and_not_as_values(self):
        java = _java('    same = field.get_value() == "a"\n'
                     '    empty = not field.get_value()\n'
                     '    out.set_value(str(same) + str(empty))')
        self.assertIn('String same = _apkpyBool(', java)
        self.assertIn('String empty = _apkpyBool(!(_apkpyTruthy(', java)

    def test_str_of_false_is_spelled_like_python(self):
        java = _java('    out.set_value(str(False) + str(None))')
        self.assertIn('"False" + "None"', java)

    def test_module_names_that_hold_none_true_or_false_are_declared(self):
        # Nothing declared them: cannot find symbol, in generated code.
        java = _java('    if DEBUG:\n        out.set_value("debug")\n'
                     '    if MISSING is None:\n        out.set_value("none")',
                     module_lines='DEBUG = False\nMISSING = None\n')
        self.assertIn('private static final String DEBUG = ApkpyValues.FALSE;', java)
        self.assertIn('private static final String MISSING = ApkpyValues.NONE;', java)
        self.assertIn('if (_apkpyTruthy(DEBUG)) {', java)

    def test_a_global_that_starts_false_starts_as_the_apps_false(self):
        # The words "False" are not empty: not ON was False on the first tap.
        java = _java('    global ON\n    ON = not ON\n    out.set_value(str(ON))',
                     module_lines='ON = False\n')
        self.assertIn('ApkpyReactiveState.get("__apkpy_global_ON", ApkpyValues.FALSE)', java)

    def test_a_global_can_start_as_none(self):
        java = _java('    global LAST\n    LAST = field.get_value()\n    out.set_value(LAST)',
                     module_lines='LAST = None\n')
        self.assertNotIn('error.txt', java)

    def test_json_true_false_and_null_read_as_python_values(self):
        java = _java('    if ROW["done"]:\n        out.set_value("done")',
                     module_lines='ROW = {"done": False}\n')
        self.assertIn('if (_apkpyTruthy(_jsonGet(', java)
        self.assertIn('if (v instanceof Boolean) return ((Boolean) v) ? ApkpyValues.TRUE : ApkpyValues.FALSE;', java)
        self.assertIn('if (v == null || v == org.json.JSONObject.NULL) return ApkpyValues.NONE;', java)

    def test_the_apps_true_goes_into_json_as_true(self):
        java = _java('    row = {"done": False}\n    row["done"] = field.get_value() == "y"\n'
                     '    out.set_value(str(row))')
        self.assertIn('_apkpyJsonOut(String.valueOf(_apkpyBool(', java)
        self.assertIn('if (v == ApkpyValues.TRUE) return Boolean.TRUE;', java)

    def test_a_kit_answer_of_true_or_false_is_the_apps(self):
        # network.online() kept in a name and tested later was always true.
        java = _java('    ok = network.online()\n    if ok:\n        out.set_value("on")',
                     extra_imports=', network')
        self.assertIn('if (value.equals("False")) return ApkpyValues.FALSE;', java)
        self.assertIn('if (_apkpyTruthy(ok)) {', java)

    def test_the_truth_of_text_from_a_method(self):
        java = _java('    if field.get_value().strip():\n        out.set_value("typed")')
        self.assertIn('if (_apkpyTruthy(_apkpyStrip(String.valueOf(', java)

    def test_a_number_is_false_at_zero(self):
        java = _java('    n = len(field.get_value())\n    if n:\n        out.set_value("some")')
        self.assertIn(') != 0)', java)

    def test_a_list_is_false_when_empty(self):
        java = _java('    if ITEMS:\n        out.set_value("some")', module_lines='ITEMS = ["a"]\n')
        self.assertIn('(_apkpyLen(String.valueOf(ITEMS)) > 0)', java)

    def test_a_function_with_no_return_used_as_a_value_gives_none(self):
        # The method was void and str(log()) could not compile.
        java = _java('    out.set_value(str(log()))',
                     module_lines='def log():\n    out.set_value("logged")\n')
        self.assertIn('private String pythonCallback_log() {', java)
        self.assertIn('return ApkpyValues.NONE;', java)

    def test_a_function_called_on_its_own_line_stays_void(self):
        java = _java('    log()', module_lines='def log():\n    out.set_value("logged")\n')
        self.assertIn('private void pythonCallback_log() {', java)

    def test_a_bare_return_in_a_function_with_a_value_returns_none(self):
        # `return;` in a method that returns String: javac refused it.
        java = _java('    out.set_value(str(pick(field.get_value())))',
                     module_lines='def pick(x):\n'
                     '    if x == "":\n        return\n    return x\n')
        self.assertIn('            return ApkpyValues.NONE;', java)

    def test_appending_a_comparison_stores_json_true(self):
        java = _java('    flags = []\n    flags.append(field.get_value() == "y")\n'
                     '    if flags[0] is True:\n        out.set_value("yes")')
        self.assertIn('arr.put(value instanceof String ? _apkpyJsonOut((String) value) : value);', java)

    def test_two_items_are_added_as_json_holds_them(self):
        # rows[0]["n"] + rows[1]["n"] showed 107 for 10 and 7.
        java = _java('    rows = [{"n": 10}, {"n": 7}]\n'
                     '    out.set_value(str(rows[0]["n"] + rows[1]["n"]))')
        self.assertIn('_apkpyAddRaw(_apkpyRawOr(', java)
        self.assertIn('if (a instanceof Number || b instanceof Number) {', java)

    def test_a_default_of_none(self):
        java = _java('    out.set_value(greet())',
                     module_lines='def greet(name=None):\n'
                     '    if name is None:\n        return "hi"\n    return "hi " + name\n')
        self.assertIn('pythonCallback_greet(ApkpyValues.NONE)', java)


class TheListMethodTests(unittest.TestCase):
    """insert, remove, sort, reverse, extend, clear, pop, index, sorted,
    reversed (phase 1, group 5).

    A method that changes a list gives the name the changed list, as d[k] = v
    does (features/item_assignment.py). The answers were checked against
    CPython by running the generated Java on the JVM.
    """

    def _java(self, body, module_lines=PHASE_ONE):
        return _java(body, module_lines=module_lines)

    def test_the_methods_give_the_name_the_changed_list(self):
        java = self._java('    xs = [3, 1, 2]\n    xs.sort()\n    xs.insert(0, 9)\n'
                          '    xs.remove(2)\n    xs.extend([5, 4])\n    xs.reverse()\n'
                          '    xs.clear()\n    out.set_value(str(xs))')
        self.assertIn('xs = _apkpySort(String.valueOf(xs), false);', java)
        self.assertIn('xs = _apkpyInsert(String.valueOf(xs), String.valueOf(0), 9);', java)
        self.assertIn('xs = _apkpyRemove(String.valueOf(xs), 2);', java)
        self.assertIn('xs = _apkpyExtend(String.valueOf(xs), ', java)
        self.assertIn('xs = _apkpyReverse(String.valueOf(xs));', java)
        self.assertIn('xs = _apkpyClear(String.valueOf(xs));', java)

    def test_pop_answers_the_item_and_takes_it_out(self):
        java = self._java('    xs = [3, 1, 2]\n    last = xs.pop()\n    out.set_value(last)')
        self.assertIn('String last = _apkpyPop(String.valueOf(xs), String.valueOf(-1), true, null, false);', java)
        self.assertIn('xs = _apkpyPop(String.valueOf(xs), String.valueOf(-1), false, null, false);', java)

    def test_a_position_worked_out_is_worked_out_once(self):
        java = self._java('    xs = [3, 1, 2]\n    x = xs.pop(len(xs) - 1)\n    out.set_value(x)')
        self.assertIn('String _apkpy_p1 = String.valueOf(Math.subtractExact(', java)
        self.assertIn('String x = _apkpyPop(String.valueOf(xs), String.valueOf(_apkpy_p1), true', java)
        self.assertIn('xs = _apkpyPop(String.valueOf(xs), String.valueOf(_apkpy_p1), false', java)

    def test_pop_inside_an_expression_says_how_to_write_it(self):
        text = _error('    xs = [3, 1]\n    out.set_value(xs.pop())')
        self.assertIn('U2033', text)
        self.assertIn('item = items.pop()', text)

    def test_a_dict_pop_with_a_default(self):
        java = self._java('    d = {"a": 1}\n    z = d.pop("z", 0)\n    out.set_value(str(z))')
        self.assertIn('String z = _apkpyPop(String.valueOf(d), String.valueOf("z"), true, 0, true);', java)

    def test_a_module_list_is_sorted_for_every_screen(self):
        java = self._java('    NAMES.sort(reverse=True)\n    out.set_value(str(NAMES))',
                          module_lines='NAMES = ["b", "a"]\n')
        self.assertIn('_apkpySort(String.valueOf(ApkpyReactiveState.get("__apkpy_global_NAMES"', java)
        self.assertIn('ApkpyReactiveState.set("__apkpy_global_NAMES", String.valueOf(NAMES));', java)

    def test_the_apps_own_calls_are_left_alone(self):
        # storage.clear() is the app's call, not a list's.
        java = self._java('    storage.clear()\n    out.set_value("x")')
        self.assertNotIn('storage = _apkpyClear(', java)
        self.assertNotIn('String storage', java)

    def test_a_list_parameter_cannot_be_changed_in_place(self):
        text = _flat(_error('    tidy(["b"])', module_lines='def tidy(xs):\n    xs.sort()\n'))
        self.assertIn('U2033', text)
        self.assertIn('cart = add_item(cart, name)', text)

    def test_sort_with_a_key_says_why(self):
        text = _error('    xs = ["bb", "a"]\n    xs.sort(key=len)\n    out.set_value(str(xs))')
        self.assertIn('U2033', text)
        self.assertIn('sort(key=...) is not translated', text)

    def test_sorted_and_reversed_are_lists(self):
        java = self._java('    words = sorted(field.get_value().split(","), reverse=True)\n'
                          '    back = reversed(words)\n'
                          '    out.set_value(str(len(words) + len(back)))')
        self.assertIn('_apkpySort(_apkpyItems(String.valueOf(_apkpySplit(', java)
        self.assertIn('), true);', java)
        self.assertIn('_apkpyReverse(_apkpyItems(String.valueOf(words)).toString())', java)

    def test_reversed_range_counts_down(self):
        java = self._java('    t = ""\n    for i in reversed(range(3)):\n'
                          '        t += str(i)\n    out.set_value(t)')
        self.assertIn('_i_', java)
        self.assertIn('-= 1)', java)

    def test_index_is_a_number(self):
        java = self._java('    xs = ["a", "b"]\n    out.set_value(str(xs.index("b") + 1))')
        self.assertIn('Math.addExact((long)(Long.parseLong(String.valueOf(_apkpyIndexOf(', java)

    def test_the_order_is_pythons(self):
        # Stable, True == 1, text by code point, mixed types a TypeError.
        java = self._java('    xs = [True, 0]\n    xs.sort()\n    out.set_value(str(xs))')
        self.assertIn('java.util.Collections.sort(items, new java.util.Comparator<Object>() {', java)
        self.assertIn('if (v instanceof Boolean) return ((Boolean) v) ? 1L : 0L;', java)
        self.assertIn('int x = a.codePointAt(i), y = b.codePointAt(j);', java)
        self.assertIn("'<' not supported between instances of '", java)

    def test_an_item_of_an_item_can_be_appended_to(self):
        java = self._java('    rows = [{"tags": []}]\n    rows[0]["tags"].append("new")\n'
                          '    out.set_value(str(rows))')
        self.assertIn('_apkpyListAppend(String.valueOf(_jsonGet(', java)


class TheDictMethodTests(unittest.TestCase):
    """get(k, default), keys(), values(), items(), update(), copy()
    (phase 1, group 6). pop() came with group 5.

    storage.get(), state.get(), storage.keys() and clipboard.copy(text) are
    the app's own calls: a dict's method is one on a name the module gives a
    value to and does not import.
    """

    def _java(self, body, module_lines=PHASE_ONE):
        return _java(body, module_lines=module_lines)

    def test_get_answers_the_value_the_default_or_none(self):
        java = self._java('    a = PRICES.get(field.get_value(), 0)\n'
                          '    b = PRICES.get("milk")\n    out.set_value(str(a) + str(b))')
        self.assertIn('_apkpyDictGetOr(String.valueOf(PRICES), String.valueOf(', java)
        self.assertIn('), String.valueOf(0));', java)
        self.assertIn('String.valueOf("milk"), ApkpyValues.NONE);', java)

    def test_get_in_a_condition_is_the_truth_of_the_value(self):
        java = self._java('    if PRICES.get(field.get_value()):\n        out.set_value("sold")')
        self.assertIn('if (_apkpyTruthy(_apkpyDictGetOr(', java)

    def test_keys_values_and_items_are_lists(self):
        java = self._java('    out.set_value(str(len(PRICES.keys())) + str(sum(PRICES.values()))'
                          ' + str(len(PRICES.items())))')
        self.assertIn('_apkpyKeyList(String.valueOf(PRICES))', java)
        self.assertIn('_apkpySum(String.valueOf(_apkpyValues(String.valueOf(PRICES))))', java)
        self.assertIn('_apkpyPairs(String.valueOf(PRICES))', java)

    def test_update_gives_the_name_the_merged_dict(self):
        java = self._java('    d = {"a": 1}\n    d.update({"b": 2})\n    out.set_value(str(d))')
        self.assertIn('d = _apkpyUpdate(String.valueOf(d), String.valueOf(', java)

    def test_a_copy_is_the_same_text(self):
        java = self._java('    d = {"a": 1}\n    e = d.copy()\n    e["a"] = 2\n'
                          '    out.set_value(str(d["a"]))')
        self.assertIn('String e = String.valueOf(d);', java)

    def test_the_apps_own_get_and_keys_are_left_alone(self):
        java = self._java('    a = storage.get("k", "")\n    out.set_value(a)')
        self.assertIn('_apkpyStorageGet(', java)
        self.assertNotIn('_apkpyDictGetOr(String.valueOf(storage)', java)

    def test_a_zero_read_from_json_is_false(self):
        # stock.get("cake") or "out": 0 is false in Python; the text "0" was not.
        java = self._java('    v = PRICES.get("x", 0) or "none"\n    out.set_value(v)')
        self.assertIn('public static final String ZERO = new String("0");', java)
        self.assertIn('if (v == ApkpyValues.ZERO || v == ApkpyValues.ZERO_FLOAT) return false;', java)


class TheComprehensionTests(unittest.TestCase):
    """[x for x in xs if c], {k: v for ...}, any(), all() (phase 1, group 7).

    Each is the loop it stands for (features/comprehensions.py), with its
    own names, so a name of the function spelled the same is not touched.
    """

    def _java(self, body, module_lines=PHASE_ONE):
        return _java(body, module_lines=module_lines)

    def test_a_list_comprehension_is_its_loop(self):
        java = self._java('    names = [p.upper() for p in field.get_value().split(",") if p]\n'
                          '    out.set_value(str(len(names)))')
        self.assertIn('String names = _apkpyJsonArr().toString();', java)
        self.assertIn('names = _apkpyListAppend(String.valueOf(names), ', java)
        self.assertIn('String _apkpy_c1 = _apkpyFromJson(', java)

    def test_the_loop_variable_does_not_leak(self):
        java = self._java('    x = "kept"\n    ys = [x.upper() for x in ITEMS]\n    out.set_value(x)')
        self.assertIn('String x = "kept";', java)
        self.assertNotIn('x = _apkpyFromJson(', java)

    def test_a_dict_comprehension_sets_each_key(self):
        java = self._java('    ages = {n: len(n) for n in ITEMS}\n    out.set_value(str(len(ages)))')
        self.assertIn('ages = _apkpySetItem(String.valueOf(ages), String.valueOf(_apkpy_c1), ', java)

    def test_one_inside_a_line_is_worked_out_on_the_line_before(self):
        java = self._java('    out.set_value(", ".join([w + "!" for w in ITEMS]))')
        self.assertIn('String _apkpy_c1 = _apkpyJsonArr().toString();', java)
        self.assertIn('_apkpyJoin(String.valueOf(", "), String.valueOf(_apkpy_c1))', java)

    def test_a_list_read_by_its_own_comprehension(self):
        # names = [n for n in names if n] reads the old list.
        java = self._java('    names = field.get_value().split(",")\n'
                          '    names = [n for n in names if n]\n    out.set_value(str(len(names)))')
        self.assertIn('names = _apkpy_c1;', java)

    def test_any_and_all_stop_at_the_first_answer(self):
        java = self._java('    long_one = any(len(w) > 3 for w in ITEMS)\n'
                          '    every = all(ITEMS)\n    out.set_value(str(long_one) + str(every))')
        self.assertIn('String long_one = ApkpyValues.FALSE;', java)
        self.assertIn('long_one = ApkpyValues.TRUE;', java)
        self.assertIn('break;', java)
        self.assertIn('every = ApkpyValues.FALSE;', java)

    def test_one_python_may_never_work_out_says_so(self):
        text = _error('    q = field.get_value()\n'
                      '    v = q or [w for w in ITEMS]\n    out.set_value(str(v))')
        self.assertIn('U2033', text)
        self.assertIn('Work it out on a line of its own first', text)

    def test_one_in_the_test_of_a_while_says_so(self):
        text = _error('    while any(w == "a" for w in ITEMS):\n        break')
        self.assertIn('U2033', text)
        self.assertIn('asked again on every turn', text)


class TheTextMethodTests(unittest.TestCase):
    """strip(chars), lstrip, rstrip, zfill, ljust/rjust/center, capitalize,
    swapcase, splitlines, the is*() tests, find by code point, chr/ord,
    "-" * 10 and text[::-1] (phase 1, group 8).

    Each counts code points, as Python does; checked against CPython on the
    JVM with emoji and accented letters.
    """

    def test_strip_takes_the_characters_it_is_given(self):
        # strip("x") was .trim(): the argument was ignored.
        java = _java('    out.set_value("xxhixx".strip("x") + field.get_value().lstrip())')
        self.assertIn('_apkpyStrip(String.valueOf("xxhixx"), String.valueOf("x"), 0)', java)
        self.assertIn(', null, 1)', java)

    def test_padding_and_zeros(self):
        java = _java('    t = field.get_value()\n'
                     '    out.set_value(t.zfill(5) + t.ljust(7, ".") + t.center(8, "*"))')
        self.assertIn('_apkpyZfill(String.valueOf(t), Long.parseLong(String.valueOf(5).trim()))', java)
        self.assertIn('_apkpyPad(String.valueOf(t), Long.parseLong(String.valueOf(7).trim()), '
                      'String.valueOf("."), 0)', java)
        self.assertIn('long left = mode == 0 ? 0 : mode == 1 ? marg : marg / 2 + (marg & width & 1);', java)

    def test_the_is_tests_follow_unicode(self):
        java = _java('    t = field.get_value()\n    if t.isdigit():\n        out.set_value("n")\n'
                     '    out.set_value(str(t.isalpha()))')
        self.assertIn('if (_apkpyStrIs(String.valueOf(t), "digit")) {', java)
        self.assertIn('_apkpyBool(_apkpyStrIs(String.valueOf(t), "alpha"))', java)
        self.assertNotIn('matches("\\\\d+")', java)

    def test_find_counts_code_points(self):
        java = _java('    out.set_value(str(field.get_value().find("a") + 1))')
        self.assertIn('Long.parseLong(String.valueOf(_apkpyFind(', java)
        self.assertIn('t.codePointCount(0, at)', java)

    def test_chr_and_ord(self):
        java = _java('    out.set_value(chr(233) + str(ord("A") + 1))')
        self.assertIn('_apkpyChr(Long.parseLong(String.valueOf(233).trim()))', java)
        self.assertIn('Math.addExact((long)(_apkpyOrd(String.valueOf("A"))), (long)(1))', java)

    def test_text_and_lists_times_a_number(self):
        java = _java('    out.set_value("-" * 10 + str(len([0] * 3)))')
        self.assertIn('_apkpyRepeat(String.valueOf("-"), 10, false)', java)
        self.assertIn(', 3, true)', java)

    def test_reversed_text(self):
        java = _java('    out.set_value(field.get_value()[::-1])')
        self.assertIn('_apkpySliceStep(', java)
        self.assertIn('"", "", String.valueOf(-1), 3)', java)    # 3: get_value() is text

    def test_splitlines_is_a_list(self):
        java = _java('    out.set_value(str(len(field.get_value().splitlines())))')
        self.assertIn('_apkpySplitLines(String.valueOf(', java)

    def test_replace_with_a_count(self):
        java = _java('    out.set_value("a-b-c".replace("-", "+", 1))')
        self.assertIn('_apkpyReplaceN(String.valueOf("a-b-c"), String.valueOf("-"), String.valueOf("+"), ', java)


class TheFormatTests(unittest.TestCase):
    """f-string specs, format(), str.format() and % (phase 1, group 9).

    One helper, _apkpyFormat, with Python's whole format-spec mini-language;
    checked against CPython's format() on ~48 000 random value/spec pairs.
    """

    def test_the_spec_mini_language(self):
        java = _java('    n = int(field.get_value())\n'
                     '    out.set_value(f"{n:>8,}|{n:#x}|{n / 3:.1%}")')
        self.assertIn('_apkpyFormat(String.valueOf(n), ">8,", 1)', java)
        self.assertIn('_apkpyFormat(String.valueOf(n), "#x", 1)', java)
        self.assertIn('"Precision not allowed in integer format specifier"', java)

    def test_a_spec_built_from_another_value(self):
        java = _java('    w = 9\n    out.set_value(f"[{field.get_value():>{w}}]")')
        self.assertIn('">" + String.valueOf(w), 2)', java)

    def test_repr_of_text(self):
        java = _java('    out.set_value(f"{field.get_value()!r}")')
        self.assertIn('_apkpyRepr(String.valueOf(', java)

    def test_format_and_str_format(self):
        java = _java('    out.set_value(format(2.5, ".1f") + "{} {:>4} {name}".format(1, "a", name="b"))')
        self.assertIn('_apkpyFormat(String.valueOf(2.5), ".1f", 1)', java)
        self.assertIn('String.valueOf(1) + " " + _apkpyFormat(String.valueOf("a"), ">4", 2) + " " + String.valueOf("b")', java)

    def test_str_format_reading_into_a_value_says_why(self):
        text = _flat(_error('    out.set_value("{0[1]}".format(ITEMS))', module_lines=PHASE_ONE))
        self.assertIn('U2033', text)
        self.assertIn('Only {}, {0} and {name} are translated', text)

    def test_percent_d_takes_the_whole_part(self):
        java = _java('    out.set_value("%d%%" % 7.9)')
        self.assertIn('_apkpyFormat(String.valueOf(_apkpyWholePart(String.valueOf(7.9))), "d", 1) + "%"', java)

    def test_percent_with_too_few_values_stops_the_build(self):
        text = _error('    out.set_value("%s %s" % ("a",))')
        self.assertIn('U2033', text)
        self.assertIn('not enough arguments', text)


FACT_FIB = ('def fact(n):\n'
            '    if n <= 1:\n'
            '        return 1\n'
            '    return n * fact(n - 1)\n'
            '\n\n'
            'def fib(n):\n'
            '    return n if n < 2 else fib(n - 1) + fib(n - 2)\n')


class TheNestedFunctionTests(unittest.TestCase):
    """A function inside a function, a lambda kept in a name, and recursion
    (phase 1, group 10). The inner function moves out to the module, with the
    outer names it reads as its first arguments."""

    def test_an_inner_function_gets_the_outer_names_it_reads(self):
        java = _java('    rate = len(field.get_value())\n'
                     '    def scaled(n):\n'
                     '        return n * rate + 1\n'
                     '    out.set_value(str(scaled(3)))')
        self.assertIn('private String pythonCallback_go__scaled(String rate, String n) {', java)
        self.assertIn('pythonCallback_go__scaled(String.valueOf(rate), String.valueOf(3))', java)

    def test_a_lambda_kept_in_a_name_is_a_function(self):
        java = _java('    double = lambda n: n * 2\n'
                     '    out.set_value(str(double(4)))')
        self.assertIn('private String pythonCallback_go__double(String n) {', java)

    def test_a_sibling_that_calls_it_needs_the_name_too(self):
        java = _java('    rate = len(field.get_value())\n'
                     '    def scaled(n):\n'
                     '        return n * rate\n'
                     '    def twice(n):\n'
                     '        return scaled(n) + scaled(1)\n'
                     '    out.set_value(str(twice(3)))')
        self.assertIn('private String pythonCallback_go__twice(String rate, String n) {', java)

    def test_recursion_adds_numbers(self):
        # fib(n - 1) + fib(n - 2) was text glued together: 1011010110...
        java = _java('    out.set_value(str(fib(10)) + str(fact(5)))', module_lines=FACT_FIB)
        fib = java[java.index('private String pythonCallback_fib('):]
        self.assertIn('Math.addExact(', fib[:fib.index('\n    }')])
        fact = java[java.index('private String pythonCallback_fact('):]
        self.assertIn('Math.multiplyExact(', fact[:fact.index('\n    }')])

    def test_a_name_handed_in_stays_a_number_outside(self):
        # rate became a parameter of go__scaled, and stopped being a number in
        # go as well: fact(rate) stopped the build.
        _java('    rate = len(field.get_value())\n'
              '    def scaled(n):\n'
              '        return n * rate\n'
              '    out.set_value(str(fact(rate) + scaled(2)))',
              module_lines=FACT_FIB[:FACT_FIB.index('def fib')])

    def test_nonlocal_says_why(self):
        text = _flat(_error('    n = 0\n'
                            '    def bump():\n'
                            '        nonlocal n\n'
                            '        n += 1\n'
                            '    bump()'))
        self.assertIn('U2033', text)
        self.assertIn('an argument cannot be changed from inside', text)

    def test_changing_the_outer_list_says_why(self):
        text = _flat(_error('    items = []\n'
                            '    def add(v):\n'
                            '        items.append(v)\n'
                            '    add(1)'))
        self.assertIn('U2033', text)
        self.assertIn('gets a copy', text)

    def test_handing_over_one_that_reads_outer_names_says_why(self):
        text = _flat(_error('    word = field.get_value()\n'
                            '    def shout():\n'
                            '        out.set_value(word.upper())\n'
                            '    handler = shout\n'
                            '    handler()'))
        self.assertIn('U2033', text)
        self.assertIn('whoever calls it later has no word to give it', text)

    def test_a_default_read_from_the_outer_function_says_why(self):
        text = _flat(_error('    k = 2\n'
                            '    def f(v=k):\n'
                            '        return v\n'
                            '    out.set_value(str(f()))'))
        self.assertIn('U2033', text)
        self.assertIn('when the def line runs', text)


class TheErrorTests(unittest.TestCase):
    """raise, except with Python's types, try ... else (phase 1, group 11).

    The helpers throw their errors by Python name (ApkpyValues.Raised), the
    Java errors that stand for one are read as it, and ApkpyValues.isA knows
    the family tree. Checked on the JVM against CPython: 55/55.
    """

    def test_raise_names_the_error(self):
        java = _java('    if field.get_value() == "":\n'
                     '        raise ValueError("empty")\n'
                     '    out.set_value("ok")')
        # if (true): Java refuses a line after a throw as unreachable.
        self.assertIn('if (true) throw new ApkpyValues.Raised("ValueError", String.valueOf("empty"));', java)

    def test_a_key_error_shows_the_key_quoted(self):
        java = _java('    raise KeyError(field.get_value())')
        self.assertIn('new ApkpyValues.Raised("KeyError", _apkpyRepr(', java)

    def test_raise_on_its_own_throws_the_caught_one_again(self):
        java = _java('    try:\n        out.set_value(int(field.get_value()))\n'
                     '    except ValueError as e:\n        toast(e)\n        raise\n')
        self.assertRegex(java, r'if \(true\) throw ApkpyValues\.rethrow\(_te_\d+\);')

    def test_raise_on_its_own_outside_an_except_says_why(self):
        text = _flat(_error('    raise'))
        self.assertIn('U2033', text)
        self.assertIn('only means something inside an except', text)

    def test_an_error_of_your_own_says_why(self):
        for body in ('    raise BadInput("x")',
                     '    try:\n        out.set_value("a")\n    except BadInput:\n        toast("b")'):
            text = _flat(_error(body))
            self.assertIn('U2033', text)
            self.assertIn("not one of Python's built-in errors", text)

    def test_two_values_in_one_error_say_why(self):
        text = _flat(_error('    raise ValueError("a", 1)'))
        self.assertIn('U2033', text)
        self.assertIn('one text per error', text)

    def test_a_missing_key_raises_only_where_it_is_caught(self):
        caught = _java('    d = {"a": 1}\n'
                       '    try:\n        out.set_value(d[field.get_value()])\n'
                       '    except KeyError:\n        out.set_value("none")\n')
        self.assertIn('ApkpyValues.strict(1);', caught)
        self.assertIn('if (ApkpyValues.strict()) throw new ApkpyValues.Raised("KeyError", _apkpyRepr(k));', caught)
        # An except that does not catch it leaves d[k] the empty text it was.
        other = _java('    d = {"a": 1}\n'
                      '    try:\n        out.set_value(d[field.get_value()])\n'
                      '    except ValueError:\n        out.set_value("none")\n')
        self.assertNotIn('ApkpyValues.strict(1);', other)

    def test_try_with_only_a_finally_has_no_catch(self):
        java = _java('    try:\n        out.set_value("a")\n    finally:\n        toast("b")')
        self.assertIn('} finally {', java)
        self.assertNotIn('catch (Throwable', java)

    def test_ioerror_is_oserror_and_from_is_dropped(self):
        java = _java('    try:\n        out.set_value("a")\n'
                     '    except IOError:\n        raise ValueError("x") from None\n')
        self.assertRegex(java, r'ApkpyValues\.isA\(_te_\d+, "OSError"\)')
        self.assertIn('new ApkpyValues.Raised("ValueError", String.valueOf("x"))', java)

    def test_the_family_tree(self):
        java = _java('    out.set_value("a")')
        self.assertIn('case "KeyError":', java)
        self.assertIn('return "LookupError";', java)
        self.assertIn('if (t instanceof IllegalArgumentException) return "ValueError";', java)


class TheSmallBuiltinTests(unittest.TestCase):
    """print(), bool(), divmod(), pow(), assert, and str() of a list
    (phase 1, group 12). Checked on the JVM against CPython: 60/60, the
    printed lines included."""

    def test_print_joins_with_sep_and_keeps_end(self):
        java = _java('    print("a", 1, sep="-", end="")')
        self.assertIn('ApkpyValues.print(String.valueOf("a") + String.valueOf("-") + String.valueOf(1), '
                      'String.valueOf(""));', java)
        # A line at a time to Logcat, as a terminal shows it.
        self.assertIn('android.util.Log.i("apkpy", PRINTED.substring(0, at));', java)

    def test_print_to_a_file_says_why(self):
        text = _flat(_error('    print("a", file=None)'))
        self.assertIn('U2033', text)
        self.assertIn('a file= has nowhere to go', text)

    def test_an_app_print_of_its_own_is_called(self):
        java = _java('    print("a")', module_lines='def print(text):\n    out.set_value(text)\n')
        self.assertIn('pythonCallback_print(', java)
        self.assertNotIn('ApkpyValues.print(String.valueOf("a")', java)

    def test_bool_is_pythons_truth(self):
        java = _java('    out.set_value(str(bool(field.get_value())) + str(bool(0)) + str(bool()))')
        self.assertIn('(_apkpyTruthy(', java)
        self.assertIn('? ApkpyValues.TRUE : ApkpyValues.FALSE)', java)
        self.assertIn('((0) != 0)', java)

    def test_divmod_on_its_own_line_keeps_numbers(self):
        # In a pair, q and r would come back as text and f"{r:02d}" would stop.
        java = _java('    total = len(field.get_value()) * 61\n'
                     '    m, s = divmod(total, 60)\n'
                     '    out.set_value(f"{m}:{s:02d}")')
        self.assertIn('Math.floorDiv(', java)
        self.assertIn('Math.floorMod(', java)

    def test_divmod_reads_a_target_once(self):
        from apkpy_lib.core.features import basics
        import ast
        tree = basics.desugar(ast.parse('def f(a, b):\n    a, b = divmod(a, b)\n'))
        code = ast.dump(tree)
        self.assertIn("Name(id='_apkpy_d1'", code)
        self.assertIn("Name(id='_apkpy_d2'", code)

    def test_pow_with_two_and_three_arguments(self):
        java = _java('    n = len(field.get_value())\n'
                     '    out.set_value(str(pow(2, n)) + str(pow(3, n, 7)))')
        self.assertIn('_apkpyPowL((long)(2), (long)(', java)
        self.assertIn('_apkpyPowMod((long)(3), (long)(', java)
        self.assertIn('"pow() 3rd argument cannot be 0"', java)

    def test_assert_raises_assertion_error(self):
        java = _java('    assert field.get_value() != "", "empty"\n    out.set_value("ok")')
        self.assertIn('if (true) throw new ApkpyValues.Raised("AssertionError", String.valueOf("empty"));', java)

    def test_str_of_a_list_is_what_python_shows(self):
        java = _java('    xs = [1, "a", None]\n    out.set_value(str(xs))')
        self.assertIn('_apkpyShow(String.valueOf(xs))', java)
        self.assertIn('if (item instanceof String) return _apkpyRepr((String) item);', java)
        # Text that looks like a list stays the text it is.
        other = _java('    out.set_value(str(field.get_value()))')
        self.assertNotIn('_apkpyShow(String.valueOf(((android', other)


PHASE_TWO = ('ITEMS = ["a", "b", "c"]\n'
             'PAIRS = [(1, 2), (3, 4)]\n'
             'ORIGIN = (0, 0)\n')


class TheLoopElseTests(unittest.TestCase):
    """for ... else and while ... else (phase 2). Checked on the JVM against
    CPython with nested loops, a break in an inner else and a while that runs
    out: 24/24."""

    def test_a_break_clears_the_flag_and_the_else_tests_it(self):
        java = _java('    for x in ITEMS:\n'
                     '        if x == field.get_value():\n'
                     '            break\n'
                     '    else:\n'
                     '        out.set_value("none")', module_lines=PHASE_TWO)
        self.assertIn('String _apkpy_nb1 = ApkpyValues.TRUE;', java)
        self.assertRegex(java, r'_apkpy_nb1 = ApkpyValues\.FALSE;\s+break;')
        self.assertIn('if (_apkpyTruthy(_apkpy_nb1)) {', java)

    def test_a_loop_without_a_break_always_runs_its_else(self):
        java = _java('    n = 0\n'
                     '    while n < 3:\n'
                     '        n += 1\n'
                     '    else:\n'
                     '        out.set_value("done")')
        self.assertNotIn('_apkpy_nb', java)
        self.assertIn('setText(String.valueOf("done"));', java)

    def test_the_else_of_a_while_is_no_longer_left_out(self):
        # 1.13.1 wrote the loop and dropped its else without a word.
        java = _java('    word = field.get_value()\n'
                     '    while word != "stop":\n'
                     '        word = "stop"\n'
                     '        if field.get_value() == "x":\n'
                     '            break\n'
                     '    else:\n'
                     '        out.set_value("ELSE-RAN")')
        self.assertIn('"ELSE-RAN"', java)

    @unittest.skipUnless(hasattr(__import__('ast'), 'unparse'), 'ast.unparse is 3.9+')
    def test_only_the_loops_own_breaks_count(self):
        from apkpy_lib.core.features import loop_else
        import ast
        tree = loop_else.desugar(ast.parse(
            'def f(grid, word):\n'
            '    for row in grid:\n'
            '        for cell in row:\n'
            '            if cell == word:\n'
            '                break\n'
            '        else:\n'
            '            break\n'
            '    else:\n'
            '        return "all"\n'
            '    return "some"\n'))
        code = ast.unparse(tree)
        # The inner loop's break is its own; the one in its else is the outer one's.
        self.assertIn('if cell == word:\n                _apkpy_nb1 = False\n                break', code)
        self.assertIn('if _apkpy_nb1:\n            _apkpy_nb2 = False\n            break', code)
        self.assertIn("if _apkpy_nb2:\n        return 'all'", code)

    def test_at_the_top_of_the_file_it_says_where_it_works(self):
        text = _flat(_error('    out.set_value("x")',
                            module_lines='ITEMS = ["a"]\nfor x in ITEMS:\n    pass\n'
                                         'else:\n    pass\n'))
        self.assertIn('U2033', text)
        self.assertIn('at the top level of the file is not translated. Inside a function it is', text)
        self.assertIn('Move the loop into a function and call it.', text)


class TheChainedAssignmentTests(unittest.TestCase):
    """a = b = 0 inside a function (phase 2)."""

    def test_a_value_written_out_goes_to_each_name(self):
        java = _java('    a = b = 0\n    out.set_value(str(a + b))')
        self.assertIn('String a = "0";', java)
        self.assertIn('String b = "0";', java)

    def test_a_call_is_made_once(self):
        java = _java('    a = b = len(field.get_value())\n    out.set_value(str(a + b))')
        body = java[java.index('void pythonCallback_go()'):]
        body = body[:body.index('\n    }')]
        self.assertEqual(body.count('getText().toString()'), 1)
        self.assertIn('String a = _apkpy_u1;', java)
        self.assertIn('String b = _apkpy_u1;', java)

    def test_one_list_for_two_names_says_why(self):
        text = _flat(_error('    a = b = []\n    a.append(1)\n    out.set_value(str(b))'))
        self.assertIn('U2033', text)
        self.assertIn('every name here holds the same list', text)
        self.assertIn('a = [] and then b = []', text)


class TheTupleTests(unittest.TestCase):
    """A tuple is kept as a list, shown with round brackets and never changed
    (phase 2). On the JVM against CPython: 24/24, emoji included."""

    def _java(self, body):
        return _java(body, module_lines=PHASE_TWO)

    def test_a_tuple_written_out_is_translated(self):
        java = self._java('    pair = (1, 2)\n    out.set_value(str(pair[0]))')
        self.assertIn('String pair = _apkpyJsonArr(1, 2).toString();', java)

    def test_str_of_a_tuple_has_round_brackets(self):
        java = self._java('    pair = (field.get_value(), 1)\n    out.set_value(str(pair))')
        self.assertIn('_apkpyShowTuple(String.valueOf(pair))', java)
        self.assertIn('if (arr.length() == 1) out.append(\',\');', java)

    def test_a_function_that_returns_a_tuple_is_shown_as_one(self):
        java = _java('    out.set_value(str(stats(field.get_value())))',
                     module_lines='def stats(text):\n    return len(text), text.upper()\n')
        self.assertIn('_apkpyShowTuple(String.valueOf(pythonCallback_stats(', java)

    def test_a_list_of_tuples_gives_tuples(self):
        java = self._java('    for p in PAIRS:\n'
                          '        out.set_value(str(p))\n'
                          '    out.set_value(str(PAIRS[0]) + str(ORIGIN))')
        self.assertIn('_apkpyShowTuple(String.valueOf(p))', java)
        self.assertIn('_apkpyShowTuple(String.valueOf(ORIGIN))', java)

    def test_tuple_of_a_list_is_a_copy_shown_as_a_tuple(self):
        java = self._java('    copy = tuple(ITEMS)\n    out.set_value(str(copy))')
        self.assertIn('_apkpyShowTuple(String.valueOf(copy))', java)

    def test_a_number_in_a_tuple_stays_a_number(self):
        # (word, len(word)) showed ('tea', '3'): the count went in as text.
        java = self._java('    word = field.get_value()\n'
                          '    pair = (word, len(word))\n'
                          '    out.set_value(str(pair))')
        self.assertIn('Long.valueOf(((long) _apkpyTextLen(String.valueOf(word))))', java)

    def test_changing_a_tuple_stops_as_cpython_does(self):
        text = _flat(_error('    pair = (1, 2)\n    pair[0] = 5\n    out.set_value(str(pair))'))
        self.assertIn("'tuple' object does not support item assignment", text)
        text = _flat(_error('    pair = (1, 2)\n    pair.append(3)\n    out.set_value(str(pair))'))
        self.assertIn("'tuple' object has no attribute 'append'", text)

    def test_an_f_string_shows_a_list_and_a_tuple_as_str_does(self):
        # f"{ITEMS}" showed the JSON, ["a","b","c"], where CPython shows ['a', 'b', 'c'].
        java = self._java('    pair = (1, 2)\n    out.set_value(f"{pair} {ITEMS}")')
        self.assertIn('_apkpyShowTuple(String.valueOf(pair)) + " " + _apkpyShow(String.valueOf(ITEMS))', java)


class TheIsinstanceTests(unittest.TestCase):
    """isinstance() (phase 2): answered when the app is built where the source
    says what the value is, and by the type the app reads it as otherwise."""

    def _java(self, body):
        return _java(body, module_lines=PHASE_TWO)

    def test_what_the_source_says_is_answered_at_build(self):
        java = self._java('    pair = (1, 2)\n'
                          '    if isinstance(ITEMS, list) and isinstance(pair, tuple):\n'
                          '        out.set_value("yes")\n'
                          '    if isinstance(ITEMS, tuple):\n'
                          '        out.set_value("no")')
        self.assertIn('if ((true) && (true)) {', java)
        self.assertIn('if (false) {', java)

    def test_bool_counts_as_int(self):
        java = self._java('    out.set_value(str(isinstance(True, int)))')
        self.assertIn('(true ? ApkpyValues.TRUE : ApkpyValues.FALSE)', java)

    def test_a_parameter_is_asked_when_the_app_runs(self):
        java = _java('    out.set_value(kind(field.get_value()))',
                     module_lines='def kind(v):\n'
                                  '    if isinstance(v, (int, float)):\n'
                                  '        return "num"\n'
                                  '    return "other"\n')
        self.assertIn('ApkpyValues.isInstance(String.valueOf(v), "int,float")', java)
        self.assertIn('public static String pyType(String v) {', java)

    def test_a_call_is_still_made(self):
        java = self._java('    out.set_value(str(isinstance(field.get_value(), str)))')
        self.assertIn('ApkpyValues.evaluated(', java)

    def test_none_is_asked_as_type_of_none(self):
        java = self._java('    v = None\n    out.set_value(str(isinstance(v, type(None))))')
        self.assertIn('"NoneType"', java)

    def test_another_type_says_which_are_translated(self):
        text = _flat(_error('    if isinstance(field.get_value(), set):\n        out.set_value("x")'))
        self.assertIn('str, int, float, bool, list, dict, tuple and type(None)', text)
