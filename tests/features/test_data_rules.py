# -*- coding: utf-8 -*-
"""Do the two runtimes answer the database's questions the same way?

This is the test that was missing. The rules of the data layer are written
twice -- once for your computer, once for the Java that goes on the phone --
and when they drift apart nothing notices: the app works at the desk and
answers something else in your hand. An audit found eight such places. Not one
of them was loud.

So each rule now lives in one place, :mod:`apkpy_lib.data_rules`, and this
walks its table asking both sides in turn:

* the **Previewer**, by calling the code it really runs (``_coerce_value``,
  ``_compile_filter``, ``_decode_row``) -- not a copy of it;
* the **compiler**, by looking for the agreed expression in the Java it emits.

Looking for an expression proves the Java mentions the rule, not that it
behaves. So :class:`TheEmittedJavaAnswersTheSameWay` goes further: it lifts
the helper methods **verbatim out of the generated file**, compiles them with
``javac`` against the same ``org.json`` the Android build uses, and runs the
same questions through both languages. That class skips itself where there is
no JDK, which is why the inspection tests stay -- they are the part that works
everywhere.
"""

import glob
import io
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from apkpy_lib import SQLiteAPI, data_rules
from apkpy_lib.core.compiler import translate_python_to_android

APP = '''
from apkpy_lib import *

things = db.model("things", fields={
    "id": db.integer(primary_key=True, auto_increment=True),
    "n": db.integer(),
    "value": db.real(min_value=0, max_value=1),
    "name": db.text(max_length=1),
    "title": db.text(),
    "flag": db.boolean(),
    "picked": db.boolean(choices=[True, False]),
    "payload": db.json(),
    "raw": db.blob(),
})
schema = db.schema("apkpy_app", version=1, models=[things])

home = Screen(id="home")
out = label("", id="out", screen=home)

def loaded(rows):
    out.set_value(str(len(rows)))

def failed(error):
    out.set_value(error)

def go():
    things.find(filters=[db.in_("flag", [True]), db.contains("title", "x")],
                on_result=loaded, on_error=failed)

button("Go", id="b", screen=home, command=go)
run(start_screen=home)
'''

_GENERATED = {}


def generated_database_java():
    """The ApkpyDatabase.java the compiler writes for the app above."""
    if not _GENERATED:
        files = translate_python_to_android(APP, package="com.example.data")
        assert "error.txt" not in files, files.get("error.txt", "")[:400]
        _GENERATED["java"] = files["java/ApkpyDatabase.java"]
    return _GENERATED["java"]


def previewer_with(kind, options):
    """A real database with one field of this kind, and the model to use it."""
    database = SQLiteAPI()
    database._path = os.path.join(
        tempfile.mkdtemp(prefix="apkpy-rules-"), "test.db")
    field = getattr(database, kind)(**options)
    model = database.model("probe", fields={
        "id": database.integer(primary_key=True, auto_increment=True),
        "subject": field,
    })
    return database, model


def previewer_answer(case):
    """What the Previewer says to one case: accepted, or refused with a reason."""
    database, model = previewer_with(case.kind, case.options)
    try:
        return data_rules.accept(
            database._coerce_value(model, "subject", case.value))
    except Exception as error:
        return data_rules.refuse(str(error))


def describe(case):
    return "%s: %s(%r) com %r" % (case.rule, case.kind, case.options, case.value)


RELATED_APP = '''
from apkpy_lib import *

a = db.model("a", fields={"id": db.integer(primary_key=True, auto_increment=True)})
b = db.model("b", fields={"id": db.integer(primary_key=True, auto_increment=True),
                          "a_id": db.integer()})
c = db.model("c", fields={"id": db.integer(primary_key=True, auto_increment=True),
                          "b_id": db.integer()})
# Com nome, e nao em linha: o compilador recolhe nomes de variaveis da
# lista de relacoes e deita fora tudo o que nao seja um nome -- sem um aviso.
# Ver a tarefa "Relacao declarada em linha desaparece".
b_para_c = db.relation("b_para_c", b, c, "b_id", "pai_b", "filhos_c", on_delete="cascade")
a_para_b = db.relation("a_para_b", a, b, "a_id", "pai_a", "filhos_b", on_delete="cascade")
schema = db.schema("apkpy_app", version=1, models=[a, b, c],
                   relations=[b_para_c, a_para_b])

home = Screen(id="home")
out = label("", id="out", screen=home)

def loaded(rows):
    out.set_value(str(len(rows)))

def failed(error):
    out.set_value(error)

watcher = c.observe(on_change=loaded, on_error=failed, screen=home)
run(start_screen=home)
'''

_RELATED = {}


def related_database_java():
    """ApkpyDatabase.java for a schema that actually declares relations.

    The flat schema above never reaches the cascading code, so asking it about
    the fixpoint would be asking the wrong file.
    """
    if not _RELATED:
        files = translate_python_to_android(RELATED_APP, package="com.example.rel")
        assert "error.txt" not in files, files.get("error.txt", "")[:400]
        _RELATED["java"] = files["java/ApkpyDatabase.java"]
    return _RELATED["java"]


def previewer_with_relations(triples):
    """A real schema shaped like one of the CASCADE_CASES triples."""
    database = SQLiteAPI()
    database._path = os.path.join(
        tempfile.mkdtemp(prefix="apkpy-casc-"), "test.db")
    tables = sorted({name for parent, child, _ in triples for name in (parent, child)})
    models = {}
    for table in tables:
        models[table] = database.model(table, fields={
            "id": database.integer(primary_key=True, auto_increment=True),
            # set_null exige a chave estrangeira opcional; sem isto o
            # esquema recusa-se a nascer e o teste morre antes da pergunta.
            "parent_id": database.integer(optional=True),
        })
    relations = [
        database.relation("r_%s_%s" % (parent, child), models[parent],
                          models[child], "parent_id",
                          "pai_%s" % parent, "filhos_%s" % child,
                          on_delete=on_delete)
        for parent, child, on_delete in triples
    ]
    database.schema("apkpy_app", version=1,
                    models=[models[t] for t in tables], relations=relations)
    return database


class TheTableAgreesWithItself(unittest.TestCase):
    """Before asking anyone else: does the rule module answer its own table?"""

    def test_the_cascade_cases(self):
        wrong = []
        for triples, changed, expected, note in data_rules.CASCADE_CASES:
            reached = data_rules.invalidated_by(set(changed), triples)
            if reached != set(expected):
                wrong.append("%s a mudar %s -> %s, esperado %s (%s)"
                             % (list(triples), list(changed), sorted(reached),
                                sorted(expected), note))
        self.assertEqual([], wrong, "\n" + "\n".join(wrong))

    def test_every_case(self):
        wrong = []
        for case in data_rules.CASES:
            verdict = data_rules.normalize(case.kind, case.value, **case.options)
            if verdict.ok != case.ok:
                wrong.append("%s -> %s (esperado %s) %s" % (
                    describe(case),
                    "aceite" if verdict.ok else "recusado: " + verdict.reason,
                    "aceite" if case.ok else "recusado", case.note))
        self.assertEqual([], wrong, "\n" + "\n".join(wrong))


class ThePreviewerAnswersTheTable(unittest.TestCase):
    """The side that runs on your computer, asked through its own code."""

    def test_a_delete_reaches_as_far_as_the_relations_go(self):
        wrong = []
        for triples, changed, expected, note in data_rules.CASCADE_CASES:
            database = previewer_with_relations(triples)
            reached = database._data_expand_invalidations(set(changed))
            if reached != set(expected):
                wrong.append("%s a mudar %s -> %s, esperado %s (%s)"
                             % (list(triples), list(changed), sorted(reached),
                                sorted(expected), note))
        self.assertEqual([], wrong, "\n" + "\n".join(wrong))

    def test_every_case(self):
        wrong = []
        for case in data_rules.CASES:
            answer = previewer_answer(case)
            if answer.ok != case.ok:
                wrong.append("%s -> Previewer %s; a regra diz %s (%s)" % (
                    describe(case),
                    "aceita" if answer.ok else "recusa",
                    "aceitar" if case.ok else "recusar", case.note))
        self.assertEqual([], wrong, "\n" + "\n".join(wrong))

    def test_a_blob_reads_back_the_same_text_as_the_phone(self):
        database, model = previewer_with("blob", {})
        row = database._decode_row(model, {"id": 1, "subject": b"ABC"})
        self.assertEqual(data_rules.blob_to_text(b"ABC"), row["subject"],
                         "o Previewer devolve hexadecimal e o telemovel Base64")

    def test_a_search_for_a_wildcard_searches_for_the_character(self):
        database, model = previewer_with("text", {})
        wrong = []
        for operation, typed, expected, note in data_rules.LIKE_CASES:
            filtro = getattr(database, operation)("subject", typed)
            _sql, args = database._compile_filter(model, filtro)
            if args and args[0] != expected:
                wrong.append("%s(%r) -> %r, esperado %r (%s)" % (
                    operation, typed, args[0], expected, note))
        self.assertEqual([], wrong, "\n" + "\n".join(wrong))

    def test_ordering_against_nothing_is_refused_out_loud(self):
        database, model = previewer_with("integer", {})
        wrong = []
        for operation, allowed, note in data_rules.ORDERING_CASES:
            filtro = getattr(database, operation)("subject", None)
            try:
                database._compile_filter(model, filtro)
                refused = False
            except Exception:
                refused = True
            if refused == allowed:
                wrong.append("%s(campo, None) -> %s; esperado %s (%s)" % (
                    operation, "recusado" if refused else "aceite",
                    "aceite" if allowed else "recusado", note))
        self.assertEqual([], wrong, "\n" + "\n".join(wrong))


class TheGeneratedJavaCarriesTheSameRules(unittest.TestCase):
    """The side that goes on the phone, read out of the Java it emits."""

    def _assert_java_has(self, key, why):
        java = generated_database_java()
        self.assertIn(data_rules.JAVA[key], java,
                      "%s -- falta %r no ApkpyDatabase.java gerado"
                      % (why, data_rules.JAVA[key]))

    def test_text_length_counts_characters(self):
        self._assert_java_has(
            "text_length",
            "String.length() conta unidades UTF-16: um emoji conta 2")

    def test_a_fraction_in_an_integer_field_is_refused(self):
        self._assert_java_has(
            "whole_number", "longValue() trunca 1.9 para 1 sem dizer nada")

    def test_a_boolean_in_an_in_filter_is_compared_as_one_or_zero(self):
        self._assert_java_has(
            "boolean_in_filter",
            "o filtro in manda \"true\" para uma coluna que guarda 1")

    def test_choices_are_compared_after_normalising(self):
        self._assert_java_has(
            "choices_normalised",
            "compara String.valueOf(true) com String.valueOf(1L)")

    def test_a_number_that_is_not_a_number_is_refused(self):
        self._assert_java_has(
            "real_number", "NaN passa os dois limites e o SQLite grava NULL")

    def test_what_the_person_typed_is_escaped_before_the_like(self):
        self._assert_java_has(
            "like_escape", "procurar % devolve todas as linhas")

    def test_the_like_carries_the_same_escape_clause_as_the_previewer(self):
        self._assert_java_has(
            "like_escape_clause",
            "o Previewer emite ESCAPE e o Java nao, por isso a barra "
            "invertida significa coisas diferentes")

    def test_ordering_against_nothing_is_refused(self):
        self._assert_java_has(
            "ordering_with_null",
            "gt/gte/lt/lte com NULL viram IS NULL e devolvem as linhas opostas")

    def test_json_has_to_be_json_to_the_end(self):
        self._assert_java_has(
            "json_to_the_end",
            "nextValue() le o objecto e ignora o resto do texto")

    def test_the_invalidation_repeats_until_nothing_new_appears(self):
        java = related_database_java()
        self.assertIn(data_rules.JAVA["invalidation_fixpoint"], java,
                      "sem o ciclo, uma cascata de dois niveis parava a meio")

    def test_a_blob_is_written_in_base64(self):
        self._assert_java_has(
            "blob_base64", "e o Previewer tem de passar a fazer o mesmo")


def _tooling():
    """javac, java and the org.json jar -- or None, and the JVM test skips.

    The jar is found rather than written down: its path carries a Gradle
    cache hash that is different on every machine.
    """
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        return None
    cache = os.path.join(os.path.expanduser("~"), ".gradle", "caches",
                         "modules-2", "files-2.1", "org.json", "json")
    jars = sorted(glob.glob(os.path.join(cache, "*", "*", "json-*.jar")))
    if not jars:
        return None
    return javac, java, jars[-1]


TOOLING = _tooling()

HARNESS = u'''import org.json.JSONTokener;
import org.json.JSONObject;
import org.json.JSONArray;

public class RulesHarness {
    static class Model { String table = "t"; }
    static class Field { String name = "f"; }
    private IllegalArgumentException type(Model model, Field field, String expected) {
        return new IllegalArgumentException("expects " + expected);
    }

__HELPERS__

    private static void say(String rule, String input, String answer) {
        System.out.println(rule + "|" + input + "|" + answer);
    }

    private static String attempt(java.util.concurrent.Callable<String> work) {
        try { return work.call(); } catch (Exception error) { return "REFUSED"; }
    }

    public static void main(String[] args) throws Exception {
        final RulesHarness h = new RulesHarness();
        String emoji = new String(Character.toChars(0x1F600));

        say("text_length", "emoji", String.valueOf(h._apkpyTextLength(emoji)));
        say("text_length", "ab", String.valueOf(h._apkpyTextLength("ab")));
        say("whole_number", "1.9", String.valueOf(h._apkpyIsWholeNumber(1.9)));
        say("whole_number", "2.0", String.valueOf(h._apkpyIsWholeNumber(2.0)));
        say("whole_number", "7", String.valueOf(h._apkpyIsWholeNumber(7)));
        say("boolean_arg", "true", h._apkpyBooleanArg(Boolean.TRUE));
        say("boolean_arg", "false", h._apkpyBooleanArg(Boolean.FALSE));
        say("choice_text", "true", h._apkpyChoiceText(Boolean.TRUE));
        say("choice_text", "1L", h._apkpyChoiceText(1L));
        say("like_escape", "percent", h._apkpyLikeEscape("%"));
        say("like_escape", "underscore", h._apkpyLikeEscape("_"));
        say("like_escape", "plain", h._apkpyLikeEscape("plain"));
        say("like_escape", "backslash", h._apkpyLikeEscape("a" + ((char) 92) + "b"));

        for (final String op : new String[]{"gt", "gte", "lt", "lte", "eq", "ne"}) {
            say("ordering", op, attempt(new java.util.concurrent.Callable<String>() {
                public String call() { h._apkpyRefuseNullOrdering(op, "score"); return "ALLOWED"; }
            }));
        }

        String[] texts = {"{BRACE_A} rubbish", "hello", "{BRACE_A}",
                          "{BRACE_A}" + ((char) 10), "QUOTEhelloQUOTE", "123"};
        String[] names = {"trailing", "bare word", "object", "trailing newline",
                          "json string", "number"};
        for (int i = 0; i < texts.length; i++) {
            final String text = texts[i];
            say("json", names[i], attempt(new java.util.concurrent.Callable<String>() {
                public String call() throws Exception {
                    h._apkpyRequireJson(new Model(), new Field(), text);
                    return "ALLOWED";
                }
            }));
        }
    }
}
'''


@unittest.skipUnless(TOOLING, "no JDK on this machine, or no org.json jar in the Gradle cache")
class TheEmittedJavaAnswersTheSameWay(unittest.TestCase):
    """Not "does the Java mention the rule" -- "does it decide the same".

    The helper methods are lifted out of the generated ApkpyDatabase.java
    exactly as the compiler wrote them, so what runs here is the code that
    ships, not a copy of it that could drift on its own.
    """

    QUOTE = chr(34)
    BACKSLASH = chr(92)

    def _harness_source(self):
        java = generated_database_java()
        # A declaracao, nao a chamada: filter() tambem e private e chama tres
        # destes na mesma linha.
        helpers = [line.strip() for line in java.splitlines()
                   if re.match(r"\s*private\s+\S+\s+_apkpy\w+\(", line)]
        self.assertEqual(7, len(helpers),
                         "esperava 7 ajudantes no Java gerado, encontrei %d"
                         % len(helpers))
        body = HARNESS.replace("__HELPERS__",
                               "\n".join("    " + line for line in helpers))
        obj = "{" + self.QUOTE + "a" + self.QUOTE + ":1}"
        escaped = obj.replace(self.QUOTE, self.BACKSLASH + self.QUOTE)
        return (body.replace("{BRACE_A}", escaped)
                .replace("QUOTEhelloQUOTE",
                         self.BACKSLASH + self.QUOTE + "hello"
                         + self.BACKSLASH + self.QUOTE))

    def _run_java(self):
        javac, java, jar = TOOLING
        work = tempfile.mkdtemp(prefix="apkpy-jvm-")
        source = os.path.join(work, "RulesHarness.java")
        with io.open(source, "w", encoding="utf-8") as handle:
            handle.write(self._harness_source())
        built = subprocess.run([javac, "-encoding", "UTF-8", "-cp", jar,
                                "-d", work, source],
                               capture_output=True, text=True)
        self.assertEqual(0, built.returncode,
                         "o Java gerado nao compila:\n" + built.stdout + built.stderr)
        ran = subprocess.run([java, "-Dfile.encoding=UTF-8",
                              "-cp", work + os.pathsep + jar, "RulesHarness"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, ran.returncode, ran.stdout + ran.stderr)
        answers = {}
        for line in ran.stdout.splitlines():
            if line.count("|") == 2:
                rule, key, value = line.split("|")
                answers[(rule, key)] = value
        return answers

    def test_both_languages_answer_the_table_the_same(self):
        java = self._run_java()
        back = self.BACKSLASH
        python = {
            ("text_length", "emoji"): str(data_rules.text_length(u"\U0001F600")),
            ("text_length", "ab"): str(data_rules.text_length("ab")),
            ("whole_number", "1.9"): str(data_rules.is_whole_number(1.9)).lower(),
            ("whole_number", "2.0"): str(data_rules.is_whole_number(2.0)).lower(),
            ("whole_number", "7"): str(data_rules.is_whole_number(7)).lower(),
            ("boolean_arg", "true"): str(data_rules.boolean_as_stored(True)),
            ("boolean_arg", "false"): str(data_rules.boolean_as_stored(False)),
            ("choice_text", "true"): str(data_rules.boolean_as_stored(True)),
            ("choice_text", "1L"): "1",
            ("like_escape", "percent"): back + "%",
            ("like_escape", "underscore"): back + "_",
            ("like_escape", "plain"): "plain",
            ("like_escape", "backslash"): "a" + back + back + "b",
        }
        for text, name in ((chr(123) + self.QUOTE + "a" + self.QUOTE
                            + ":1}" + " rubbish", "trailing"),
                           ("hello", "bare word"),
                           (chr(123) + self.QUOTE + "a" + self.QUOTE + ":1}", "object"),
                           (chr(123) + self.QUOTE + "a" + self.QUOTE + ":1}\n",
                            "trailing newline"),
                           (self.QUOTE + "hello" + self.QUOTE, "json string"),
                           ("123", "number")):
            python[("json", name)] = ("ALLOWED" if data_rules.is_json(text)
                                      else "REFUSED")
        for operation, allowed, _note in data_rules.ORDERING_CASES:
            python[("ordering", operation)] = "ALLOWED" if allowed else "REFUSED"

        wrong = []
        for key in sorted(python):
            mine = python[key]
            theirs = java.get(key, "(sem resposta)")
            if mine != theirs:
                wrong.append("%s/%s -> Python %r, Java %r"
                             % (key[0], key[1], mine, theirs))
        self.assertEqual([], wrong, "\n" + "\n".join(wrong))
        self.assertEqual(len(python), len(java),
                         "o arnes respondeu a %d perguntas, esperava %d"
                         % (len(java), len(python)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
