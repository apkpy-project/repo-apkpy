# -*- coding: utf-8 -*-
"""A job that ends in `return` has to compile.

doWork() always got a closing `return Result.success();` after the try/catch,
without asking whether the body already returned on every path. In Java a
statement that cannot be reached is a compile error, so the most natural way
to write a job -- `def task(): ... return "ok"` -- stopped the build on
generated code nobody wrote by hand. The published example escaped by
accident: it ends in a call, not a return.

The opposite mistake costs the same: drop the closing return from a body that
does NOT always return and the method has no return at all. So both directions
are pinned here, on both generators -- the Worker and the Activity.
"""

import unittest

from apkpy_lib.core.compiler import translate_python_to_android

TAIL = (
    'j = background_job("sync", run=task)\n'
    'button("Go", id="b", screen=home, command=lambda: j.enqueue())\n'
    'run(start_screen=home)\n'
)
HEAD = (
    'from apkpy_lib import Screen, background_job, button, label, permissions, '
    'storage, run\n'
    'home = Screen(id="home")\n'
    'out = label("", id="out", screen=home)\n'
)

# O que fecha um doWork() que ja devolveu por si: o catch, e mais nada.
CLOSES_ON_THE_CATCH = 'return Result.retry();\n        }\n    }'
# Um job fecha pelo _jobFinish: deixa a ultima palavra onde o status() le.
CLOSES_ON_A_RESULT = '        }\n        return _jobFinish(true);\n    }'


def _files(body):
    return translate_python_to_android(
        HEAD + 'def task():\n' + body + '\n' + TAIL)


def _do_work(body):
    files = _files(body)
    if 'error.txt' in files:
        raise AssertionError(files['error.txt'][:400])
    worker = [text for name, text in files.items()
              if name.endswith('JobWorker.java')]
    if not worker:
        raise AssertionError('nenhum Worker foi gerado')
    text = worker[0]
    start = text.index('    public Result doWork()')
    return text[start:text.index('\n    }', start) + 6]


class TheWorkerStopsWhereTheBodyStops(unittest.TestCase):

    def test_a_body_that_just_returns(self):
        java = _do_work('    storage.set("k", "1")\n    return "ok"\n')
        self.assertTrue(java.endswith(CLOSES_ON_THE_CATCH), java)

    def test_both_branches_of_an_if_returning(self):
        java = _do_work(
            '    if storage.get("flag") == "on":\n'
            '        return "on"\n'
            '    else:\n'
            '        return "off"\n')
        self.assertTrue(java.endswith(CLOSES_ON_THE_CATCH), java)

    def test_both_sides_of_a_try_returning(self):
        java = _do_work(
            '    try:\n'
            '        storage.set("k", "1")\n'
            '        return "ok"\n'
            '    except Exception as e:\n'
            '        return "bad"\n')
        self.assertTrue(java.endswith(CLOSES_ON_THE_CATCH), java)

    def test_retry_then_return_closes_on_the_outcome_too(self):
        java = _do_work('    j.retry()\n    return "later"\n')
        self.assertIn('_apkpyJobOutcome', java)
        self.assertTrue(java.endswith(CLOSES_ON_THE_CATCH), java)
        self.assertNotIn('if ("fail".equals(_apkpyJobOutcome)) return', java)


class TheWorkerStillClosesWhenItHasTo(unittest.TestCase):
    """Cortar o return final a mais era trocar um erro de compilacao por outro."""

    def test_the_published_shape_ends_in_a_call(self):
        java = _do_work('    storage.set("k", "1")\n')
        self.assertTrue(java.endswith(CLOSES_ON_A_RESULT), java)

    def test_an_if_without_an_else(self):
        java = _do_work(
            '    if storage.get("flag") == "on":\n'
            '        return "on"\n')
        self.assertTrue(java.endswith(CLOSES_ON_A_RESULT), java)

    def test_a_try_where_only_the_body_returns(self):
        java = _do_work(
            '    try:\n'
            '        return "ok"\n'
            '    except Exception as e:\n'
            '        storage.set("k", "0")\n')
        self.assertTrue(java.endswith(CLOSES_ON_A_RESULT), java)

    def test_a_permission_check_whose_branches_both_return(self):
        """O Worker deitava fora o `if permissions.has()` inteiro, e por isso
        tinha de NAO o contar como devolvido. Agora escreve-o (ver
        test_job_bodies.py), e os dois ramos a devolver fecham o metodo."""
        java = _do_work(
            '    if permissions.has("CAMERA"):\n'
            '        return "yes"\n'
            '    else:\n'
            '        return "no"\n')
        self.assertIn('checkSelfPermission(getApplicationContext()', java)
        self.assertTrue(java.endswith(CLOSES_ON_THE_CATCH), java)

    def test_retry_alone_still_reads_the_outcome(self):
        java = _do_work('    j.retry()\n')
        self.assertIn('if ("retry".equals(_apkpyJobOutcome)) return Result.retry();', java)


ACTIVITY = (
    'from apkpy_lib import Screen, button, label, storage, run\n'
    'home = Screen(id="home")\n'
    'out = label("", id="out", screen=home)\n'
)


def _callback(body):
    source = (ACTIVITY + 'def pick():\n' + body + '\n'
              'def go():\n    out.set_value(pick())\n\n'
              'button("Go", id="b", screen=home, command=go)\n'
              'run(start_screen=home)\n')
    files = translate_python_to_android(source)
    if 'error.txt' in files:
        raise AssertionError(files['error.txt'][:400])
    text = files['java/Screen_homeActivity.java']
    start = text.index('    private String pythonCallback_pick(')
    return text[start:text.index('\n    }', start) + 6]


class TheActivityCountsTryAsReturning(unittest.TestCase):
    """O mesmo buraco existia aqui: o guarda nao conhecia try/except."""

    def test_both_sides_of_a_try_returning(self):
        java = _callback(
            '    try:\n'
            '        return "ok"\n'
            '    except Exception as e:\n'
            '        return "bad"\n')
        self.assertFalse(java.rstrip().endswith('return ApkpyValues.NONE;\n    }'), java)
        self.assertNotIn('        return ApkpyValues.NONE;', java)

    def test_a_try_where_only_the_body_returns_still_closes(self):
        java = _callback(
            '    try:\n'
            '        return "ok"\n'
            '    except Exception as e:\n'
            '        storage.set("k", "0")\n')
        # Python returns None when it falls off the end.
        self.assertIn('        return ApkpyValues.NONE;', java)

    def test_an_if_else_that_returns_was_already_right(self):
        java = _callback(
            '    if storage.get("flag") == "on":\n'
            '        return "on"\n'
            '    else:\n'
            '        return "off"\n')
        self.assertNotIn('        return ApkpyValues.NONE;', java)


if __name__ == '__main__':
    unittest.main()
