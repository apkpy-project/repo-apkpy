import io
import os
import unittest
from contextlib import redirect_stderr

from apkpy_lib import SQLiteAPI
from apkpy_lib.core.compiler import (
    translate_python_to_android,
    translate_python_to_java,
)
from apkpy_lib.diagnostics import (
    diagnose_build_failure,
    diagnose_exception,
    format_exception,
    install_tk_exception_hook,
)


class FriendlyDiagnosticsTests(unittest.TestCase):
    def test_syntax_error_has_code_location_source_and_fix(self):
        source = "from apkpy_lib import Screen\nhome = Screen(\n"
        try:
            compile(source, "writehere.py", "exec")
        except SyntaxError as error:
            rendered = format_exception(
                error, context="Android compiler", source_code=source,
                filename="writehere.py",
            )
        else:
            self.fail("Expected a SyntaxError")

        self.assertIn("APKPY E1001", rendered)
        self.assertIn("writehere.py:2", rendered)
        self.assertIn("home = Screen(", rendered)
        self.assertIn("How to fix:", rendered)
        self.assertIn("APKPY_DEBUG=1", rendered)

    def test_import_error_offers_close_public_name(self):
        error = ImportError("cannot import name 'bottom_nva' from 'apkpy_lib'")
        rendered = format_exception(error, context="Application startup")
        self.assertIn("APKPY E1102", rendered)
        self.assertIn("bottom_nav", rendered)
        self.assertIn("Essential API", rendered)

    def test_common_callback_type_error_has_actionable_correction(self):
        try:
            percent = 10
            _ = "Uploading " + percent
        except TypeError as error:
            diagnostic = diagnose_exception(error, context="Previewer callback")
            rendered = format_exception(
                error, context="Previewer callback",
            )
        else:
            self.fail("Expected a TypeError")
        self.assertEqual("E1401", diagnostic.code)
        self.assertIn("str(percent)", rendered)
        self.assertIn("test_diagnostics.py", rendered)

    def test_data_core_message_keeps_original_cause(self):
        database = SQLiteAPI()
        try:
            database.model("bad-name", fields={"id": database.integer()})
        except Exception as error:
            rendered = format_exception(error, context="Data Core declaration")
        else:
            self.fail("Expected a DataCoreError")

        self.assertIn("APKPY D2001", rendered)
        self.assertIn("Invalid model name", rendered)
        self.assertIn("letters, digits and underscores", rendered)

    def test_multi_screen_compiler_returns_friendly_error_file(self):
        source = "from apkpy_lib import Screen\nhome = Screen(\n"
        files = translate_python_to_android(source)
        self.assertIn("error.txt", files)
        self.assertIn("APKPY E1001", files["error.txt"])
        self.assertIn("writehere.py:2", files["error.txt"])

    def test_single_screen_compiler_marks_diagnostic_instead_of_raw_comment(self):
        source = "from apkpy_lib import label\nlabel(\n"
        java, _ = translate_python_to_java(source)
        self.assertIn("APKPY_DIAGNOSTIC", java)
        self.assertIn("APKPY E1001", java)
        self.assertNotIn("Erro na tradução", java)

    def test_debug_mode_keeps_full_traceback_available(self):
        previous = os.environ.get("APKPY_DEBUG")
        os.environ["APKPY_DEBUG"] = "1"
        try:
            try:
                raise RuntimeError("boom")
            except RuntimeError as error:
                rendered = format_exception(error, context="Previewer callback")
        finally:
            if previous is None:
                os.environ.pop("APKPY_DEBUG", None)
            else:
                os.environ["APKPY_DEBUG"] = previous

        self.assertIn("Full traceback", rendered)
        self.assertIn("RuntimeError: boom", rendered)

    def test_tk_callback_hook_replaces_raw_traceback(self):
        class FakeRoot:
            report_callback_exception = None

        root = FakeRoot()
        install_tk_exception_hook(root)
        output = io.StringIO()
        try:
            raise RuntimeError("callback exploded")
        except RuntimeError as error:
            with redirect_stderr(output):
                root.report_callback_exception(
                    RuntimeError, error, error.__traceback__,
                )

        rendered = output.getvalue()
        self.assertIn("APKPY P3001", rendered)
        self.assertIn("Previewer callback", rendered)
        self.assertIn("callback exploded", rendered)
        self.assertNotIn("Traceback (most recent call last)", rendered)



class ExpandedDiagnosticsTests(unittest.TestCase):
    """Every library message should explain itself, not fall back to a stub."""

    GENERIC = (
        "Check the value passed to this function against the API reference.",
        "Check the accepted values in the API reference and the highlighted call.",
        "Inspect the callback shown under Where and validate the values it receives.",
    )

    def assert_specific(self, error, expected_code):
        diagnostic = diagnose_exception(error, context="Previewer callback")
        self.assertEqual(expected_code, diagnostic.code, str(error))
        self.assertTrue(diagnostic.cause, "no cause for: %s" % error)
        for stub in self.GENERIC:
            self.assertNotIn(stub, diagnostic.suggestions, str(error))
        return diagnostic

    def test_component_argument_messages_are_classified(self):
        cases = [
            (ValueError("blur must be a non-negative number"), "U2007"),
            (ValueError("avatar size must be a positive integer"), "U2007"),
            (ValueError("zoom must be an integer between 2 and 19"), "U2007"),
            (TypeError("card actions must be buttons"), "U2005"),
            (TypeError("markdown(source=...) must be a string"), "U2008"),
            (TypeError("tree_view(nodes=...) must be a list"), "U2008"),
            (ValueError("video fit must be contain, cover or fill"), "U2006"),
            (ValueError("Theme mode must be 'light' or 'dark'"), "U2006"),
            (TypeError("context_menu(target=...) expects an ApkPy component"), "U2003"),
            (TypeError("lifecycle(on_start=...) expects a callable"), "U2004"),
            (TypeError("video(screen=...) expects an ApkPy Screen"), "U2002"),
            (ValueError("video() requires screen= or parent= in declarative apps"), "U2001"),
            (ValueError("aspect_ratio must be greater than zero"), "U2009"),
            (ValueError("action(icon=...) requires a Material icon name"), "U2011"),
            (TypeError("run(theme=...) expects an apkpy_lib.Theme instance"), "U2014"),
        ]
        for error, code in cases:
            with self.subTest(message=str(error)):
                self.assert_specific(error, code)

    def test_runtime_failures_are_classified(self):
        cases = [
            (AttributeError("'NoneType' object has no attribute 'set_value'"), "P3002"),
            (KeyError("title"), "P3003"),
            (IndexError("list index out of range"), "P3004"),
            (TypeError("string indices must be integers"), "P3005"),
            (ValueError("invalid literal for int() with base 10: ''"), "P3011"),
            (ZeroDivisionError("division by zero"), "P3010"),
        ]
        for error, code in cases:
            with self.subTest(message=str(error)):
                self.assert_specific(error, code)

    def test_network_and_job_messages_are_classified(self):
        self.assert_specific(
            ValueError("WebSocket URL must use ws:// or wss://"), "N6001",
        )
        self.assert_specific(
            ValueError("upload URL must use http:// or https://"), "N6001",
        )
        self.assert_specific(
            ValueError(
                'job.observe(on_change=...) needs a function that receives '
                'the status document.'
            ),
            "J7003",
        )

    def test_key_error_names_the_missing_key(self):
        diagnostic = diagnose_exception(KeyError("subtitle"), context="Previewer callback")
        self.assertEqual("P3003", diagnostic.code)
        self.assertIn("subtitle", diagnostic.received)

    def test_number_conversion_reports_the_value_received(self):
        try:
            int("")
        except ValueError as error:
            diagnostic = diagnose_exception(error, context="Previewer callback")
        else:
            self.fail("Expected a ValueError")
        self.assertEqual("P3011", diagnostic.code)
        self.assertEqual("''", diagnostic.received)

    def test_rendered_diagnostic_carries_why_and_read_more(self):
        rendered = format_exception(
            ValueError("blur must be a non-negative number"),
            context="Previewer callback",
        )
        self.assertIn("Why this happened:", rendered)
        self.assertIn("Read more:", rendered)
        self.assertIn("https://", rendered)

    def test_rendered_diagnostic_is_ascii_safe(self):
        rendered = format_exception(
            ValueError("background_job(retry=...) must be \u201cexponential\u201d "
                       "\u2014 received \u2018daily\u2019"),
            context="Previewer callback",
        )
        rendered.encode("ascii")  # raises if a smart quote or dash survived


class CompilerLocationTests(unittest.TestCase):
    """A compiler diagnostic must point at the application, never at ApkPy."""

    def test_missing_job_function_points_at_writehere(self):
        source = (
            "from apkpy_lib import Screen, background_job, run\n"
            'home = Screen(id="home")\n'
            'sync = background_job("sync", run=missing_fn)\n'
            "run(start_screen=home)\n"
        )
        files = translate_python_to_android(source)
        self.assertIn("error.txt", files)
        report = files["error.txt"]
        self.assertIn("APKPY J7002", report)
        self.assertIn("writehere.py:3", report)
        self.assertIn("background_job", report)
        self.assertNotIn("compiler.py", report)

    def test_models_without_schema_point_at_the_model(self):
        source = (
            "from apkpy_lib import Screen, SQLiteAPI, run\n"
            "db = SQLiteAPI()\n"
            'home = Screen(id="home")\n'
            'notes = db.model("notes", fields={"id": db.integer(primary_key=True)})\n'
            "run(start_screen=home)\n"
        )
        files = translate_python_to_android(source)
        self.assertIn("error.txt", files)
        report = files["error.txt"]
        self.assertIn("APKPY C4003", report)
        self.assertIn("writehere.py:4", report)
        self.assertNotIn("compiler.py", report)

    def test_library_only_traceback_reports_no_misleading_location(self):
        error = ValueError("blur must be a non-negative number")
        diagnostic = diagnose_exception(error, context="Android multi-screen compiler")
        self.assertIsNone(diagnostic.location)


class BuildFailureTests(unittest.TestCase):
    """Gradle failures should say what failed, not "see the output above"."""

    def test_unsupported_java_version_is_recognised(self):
        output = (
            "> Task :app:compileDebugJavaWithJavac FAILED\n"
            "FAILURE: Build failed with an exception.\n"
            "* What went wrong:\n"
            "Unsupported class file major version 70\n"
        )
        diagnostic = diagnose_build_failure(output, task="assembleDebug")
        self.assertEqual("B5002", diagnostic.code)
        self.assertIn("apkpy setup", " ".join(diagnostic.suggestions))
        self.assertIn("Unsupported class file major version 70", diagnostic.received)

    def test_resource_linking_failure_is_recognised(self):
        output = (
            "> Task :app:processDebugResources FAILED\n"
            "ERROR: Android resource linking failed\n"
            "AAPT: error: resource drawable/ic_missing not found.\n"
        )
        diagnostic = diagnose_build_failure(output, task="assembleDebug")
        self.assertEqual("B5004", diagnostic.code)

    def test_unknown_failure_still_carries_gradle_reason(self):
        output = (
            "FAILURE: Build failed with an exception.\n"
            "* What went wrong:\n"
            "Something entirely new went wrong here.\n"
        )
        diagnostic = diagnose_build_failure(
            output, task="assembleDebug", project_dir="C:/tmp/project",
        )
        self.assertEqual("B5009", diagnostic.code)
        self.assertIn("What went wrong", diagnostic.received)
        self.assertIn("C:/tmp/project", " ".join(diagnostic.suggestions))
        self.assertTrue(diagnostic.cause)

if __name__ == "__main__":
    unittest.main()
