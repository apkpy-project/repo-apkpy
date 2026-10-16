import json
import unittest

from apkpy_lib.core import APP_IR_SCHEMA_VERSION, compile_to_ir
from apkpy_lib.core.compiler import translate_python_to_android


SAMPLE_APP = '''
from apkpy_lib import Screen, label, inputs, button, bottom_nav, run

home = Screen(id="home", scroll=True)
about = Screen(id="about", scroll=False)

label("Hello", id="title", screen=home)
inputs("Name", id="name", type="text", screen=home)
button("Save", id="save", screen=home)
label("About", screen=about)

bottom_nav(
    [home, about],
    labels=["Home", "About"],
    icons=["home", "info"],
)
run(start_screen=home)
'''


class AppIrTests(unittest.TestCase):
    def test_compiles_json_safe_versioned_snapshot(self):
        result = compile_to_ir(
            SAMPLE_APP, source_name="sample.py", revision=7,
        )
        self.assertTrue(result.ok, result.to_dict())
        payload = result.ir.to_dict()
        self.assertEqual(APP_IR_SCHEMA_VERSION, payload["schemaVersion"])
        self.assertEqual(7, payload["revision"])
        self.assertEqual("home", payload["startScreenId"])
        self.assertEqual(["home", "about"], [
            screen["id"] for screen in payload["screens"]
        ])
        json.dumps(payload, ensure_ascii=False)

    def test_explicit_and_automatic_node_ids_are_stable(self):
        first = compile_to_ir(SAMPLE_APP, source_name="stable.py")
        second = compile_to_ir(SAMPLE_APP, source_name="stable.py")
        first_ids = [
            node.node_id
            for screen in first.ir.screens
            for node in screen.components
        ]
        second_ids = [
            node.node_id
            for screen in second.ir.screens
            for node in screen.components
        ]
        self.assertEqual(first_ids, second_ids)
        self.assertIn("title", first_ids)
        self.assertIn("name", first_ids)
        self.assertIn("save", first_ids)
        self.assertTrue(any(value.startswith("auto_") for value in first_ids))

    def test_source_map_points_back_to_python(self):
        result = compile_to_ir(SAMPLE_APP, source_name="mapped.py")
        source_map = result.ir.source_map
        self.assertTrue(source_map["title"]["file"].endswith("mapped.py"))
        self.assertGreater(source_map["title"]["line"], 0)
        self.assertIn("screen:home", source_map)

    def test_syntax_error_is_a_structured_diagnostic(self):
        result = compile_to_ir(
            "from apkpy_lib import Screen\nhome = Screen(\n",
            source_name="broken.py",
        )
        self.assertFalse(result.ok)
        diagnostic = result.diagnostics[0].to_dict()
        self.assertEqual("PY1001", diagnostic["code"])
        self.assertEqual("parser", diagnostic["stage"])
        self.assertTrue(diagnostic["file"].endswith("broken.py"))
        self.assertGreater(diagnostic["line"], 0)

    def test_source_without_screen_is_rejected(self):
        result = compile_to_ir(
            "from apkpy_lib import label\nlabel('Hello')\n",
            source_name="legacy.py",
        )
        self.assertFalse(result.ok)
        self.assertEqual("IR1001", result.diagnostics[0].code)

    def test_bottom_navigation_is_described(self):
        result = compile_to_ir(SAMPLE_APP, source_name="navigation.py")
        self.assertIsNotNone(result.ir.bottom_navigation)
        self.assertTrue(result.ir.feature_manifest["bottomNavigation"])
        self.assertEqual(
            ["home", "about"],
            result.ir.bottom_navigation["screen_ids"],
        )

    def test_java_xml_generation_reuses_the_same_analysis(self):
        result = compile_to_ir(SAMPLE_APP, source_name="shared.py")
        shared_files = result.generate_android_files(
            package="com.apkpy.studiofixture",
        )
        direct_files = translate_python_to_android(
            SAMPLE_APP,
            package="com.apkpy.studiofixture",
            source_name="shared.py",
        )
        self.assertEqual(set(direct_files), set(shared_files))
        self.assertEqual(direct_files, shared_files)
        self.assertIn("AndroidManifest.xml", shared_files)


if __name__ == "__main__":
    unittest.main()
