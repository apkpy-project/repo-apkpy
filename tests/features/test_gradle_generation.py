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

    def _app_gradle(self, **options):
        with tempfile.TemporaryDirectory() as directory:
            generate_gradle_files(directory, "com.apkpy.app", "gradle-test", **options)
            return Path(directory, "app", "build.gradle").read_text(encoding="utf-8")

    def test_run_release_is_signed_with_the_debug_key(self):
        # apkpy run --release made an unsigned APK, which no phone installs:
        # --usb and --qr failed on it (06-11-2026).
        gradle = self._app_gradle(debug_key=True)
        self.assertIn("signingConfig signingConfigs.debug", gradle)
        self.assertNotIn("minifyEnabled", gradle)

    def test_a_published_build_keeps_its_own_key_and_r8(self):
        signing = {"keystore": "C:/keys/app.jks", "store_password": "s",
                   "key_alias": "app", "key_password": "k"}
        gradle = self._app_gradle(signing=signing, debug_key=True)
        self.assertIn("signingConfig signingConfigs.release", gradle)
        self.assertIn("minifyEnabled true", gradle)
        self.assertNotIn("signingConfigs.debug", gradle)

    def test_a_project_for_android_studio_has_no_build_types(self):
        self.assertNotIn("buildTypes", self._app_gradle())


if __name__ == "__main__":
    unittest.main()
