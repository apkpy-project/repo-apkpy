import tempfile
import unittest
from pathlib import Path

from apkpy_lib.cli import generate_gradle_files


class GradleGenerationTests(unittest.TestCase):
    def _generate(self, needs_firebase, needs_swiperefresh=False):
        with tempfile.TemporaryDirectory() as directory:
            generate_gradle_files(
                directory,
                "com.apkpy.app",
                "gradle-test",
                needs_firebase=needs_firebase,
                needs_swiperefresh=needs_swiperefresh,
                application_id="com.example.gradle_test",
            )
            return (
                Path(directory, "build.gradle").read_text(encoding="utf-8"),
                Path(directory, "app", "build.gradle").read_text(
                    encoding="utf-8"
                ),
            )

    def test_firebase_uses_android_datastore_variant(self):
        root_gradle, gradle = self._generate(needs_firebase=True)

        self.assertIn("com.google.firebase:firebase-messaging", gradle)
        self.assertIn("id 'org.jetbrains.kotlin.android'", gradle)
        self.assertIn("useLegacyPackaging true", gradle)
        self.assertIn(
            "id 'org.jetbrains.kotlin.android' version '2.0.21' apply false",
            root_gradle,
        )

    def test_plain_app_does_not_ship_firebase_or_datastore(self):
        root_gradle, gradle = self._generate(needs_firebase=False)

        self.assertNotIn("com.google.firebase", gradle)
        self.assertNotIn("androidx.datastore", gradle)
        self.assertNotIn("org.jetbrains.kotlin.android", gradle)
        self.assertNotIn("useLegacyPackaging true", gradle)
        self.assertNotIn("org.jetbrains.kotlin.android", root_gradle)

    def test_swipe_refresh_dependency_is_conditional(self):
        _, feed_gradle = self._generate(
            needs_firebase=False, needs_swiperefresh=True
        )
        _, plain_gradle = self._generate(needs_firebase=False)

        dependency = (
            "androidx.swiperefreshlayout:swiperefreshlayout:1.2.0"
        )
        self.assertIn(dependency, feed_gradle)
        self.assertNotIn(dependency, plain_gradle)

    def test_generated_toolchain_supports_swipe_refresh_1_2(self):
        with tempfile.TemporaryDirectory() as directory:
            generate_gradle_files(
                directory,
                "com.apkpy.app",
                "feed-toolchain",
                needs_swiperefresh=True,
            )
            root = Path(directory, "build.gradle").read_text(encoding="utf-8")
            app = Path(directory, "app", "build.gradle").read_text(
                encoding="utf-8"
            )
            wrapper = Path(
                directory, "gradle", "wrapper",
                "gradle-wrapper.properties",
            ).read_text(encoding="utf-8")

        self.assertIn("version '8.6.1'", root)
        self.assertIn("compileSdk 36", app)
        self.assertIn("gradle-8.7-bin.zip", wrapper)


if __name__ == "__main__":
    unittest.main()
