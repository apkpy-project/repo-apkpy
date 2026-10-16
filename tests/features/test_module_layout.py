"""Regression test for the additive feature-module boundary."""

import importlib
import unittest


class FeatureModuleLayoutTests(unittest.TestCase):
    def test_new_runtime_namespace_is_importable(self):
        module = importlib.import_module("apkpy_lib.features")
        self.assertIn("push", module.__all__)
        self.assertIn("PushAPI", module.__all__)
        self.assertIn("markdown", module.__all__)
        self.assertIn("rich_text", module.__all__)
        self.assertIn("tree_view", module.__all__)

    def test_new_codegen_namespace_is_importable(self):
        module = importlib.import_module("apkpy_lib.core.features")
        self.assertIn("push", module.__all__)
        self.assertIn("rich_content", module.__all__)
        self.assertIn("file_picker", module.__all__)

    def test_file_picker_is_exported_from_both_namespaces(self):
        runtime = importlib.import_module("apkpy_lib.features")
        self.assertIn("upload_button", runtime.__all__)
        apkpy = importlib.import_module("apkpy_lib")
        self.assertIn("upload_button", apkpy.__all__)
        self.assertTrue(callable(apkpy.upload_button))
        self.assertTrue(callable(apkpy.files.pick))

    def test_legacy_public_api_is_unchanged(self):
        apkpy = importlib.import_module("apkpy_lib")
        self.assertTrue(callable(apkpy.button))
        self.assertTrue(callable(apkpy.video))
        self.assertTrue(hasattr(apkpy, "websocket"))
        self.assertTrue(hasattr(apkpy, "push"))


if __name__ == "__main__":
    unittest.main()
