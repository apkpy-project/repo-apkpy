import tempfile
import unittest
import zipfile
from pathlib import Path

from apkpy_lib.core import compile_to_ir, write_android_project_zip


SOURCE = '''\
from apkpy_lib import Screen, label, run

home = Screen(id="home")
label("Python-free output", id="title", screen=home)
run(start_screen=home)
'''


class AndroidProjectArchiveTests(unittest.TestCase):
    def test_archive_is_buildable_shape_and_has_no_python(self):
        result = compile_to_ir(SOURCE, source_name="writehere.py", project_root=".")
        self.assertTrue(result.ok)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "project.zip")
            metadata = write_android_project_zip(result, output, app_name="Studio Test")
            self.assertFalse(metadata["pythonIncluded"])
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("settings.gradle", names)
                self.assertIn("app/build.gradle", names)
                self.assertIn("app/src/main/AndroidManifest.xml", names)
                self.assertTrue(any(name.endswith("Screen_homeActivity.java") for name in names))
                self.assertFalse(any(name.endswith((".py", ".pyc")) for name in names))
                self.assertNotIn("chaquopy", "\n".join(names).lower())

    def test_invalid_application_id_is_rejected(self):
        result = compile_to_ir(SOURCE, source_name="writehere.py", project_root=".")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                write_android_project_zip(
                    result, Path(directory, "project.zip"), application_id="invalid"
                )


if __name__ == "__main__":
    unittest.main()
