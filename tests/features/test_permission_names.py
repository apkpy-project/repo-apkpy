# -*- coding: utf-8 -*-
"""A permission named in lower case is the same permission.

``permissions.has("camera")`` wrote ``Manifest.permission.camera``, which does
not exist: javac stopped the build on code nobody wrote by hand. And in the
Previewer ``request("camera")`` followed by ``has("CAMERA")`` answered no.
Android's names are upper case; both runtimes now read any case as them.
"""

import unittest

from apkpy_lib import ui
from apkpy_lib.core.compiler import translate_python_to_android

SOURCE = '''from apkpy_lib import *
home = Screen(id="home")

def answered(granted):
    toast("ok")

def check():
    if permissions.has("camera"):
        toast("yes")
    else:
        permissions.request("camera", on_response=answered)

button("Check", id="check", command=check, screen=home)
run(start_screen=home)
'''


class LowerCaseNames(unittest.TestCase):

    def test_the_phone_writes_the_android_constant(self):
        files = translate_python_to_android(SOURCE)
        self.assertNotIn('error.txt', files, files.get('error.txt', '')[:400])
        java = ''.join(v for k, v in files.items() if k.endswith('Activity.java'))
        self.assertIn('Manifest.permission.CAMERA', java)
        self.assertNotIn('Manifest.permission.camera', java)

    def test_asking_declares_it(self):
        # The request code PERMISSION_REQ_CAMERA comes from the manifest's
        # list; an app that asked without declare_permissions() did not build.
        files = translate_python_to_android(SOURCE)
        java = ''.join(v for k, v in files.items() if k.endswith('Activity.java'))
        self.assertIn('private static final int PERMISSION_REQ_CAMERA', java)
        self.assertIn('android:name="android.permission.CAMERA"', files['AndroidManifest.xml'])

    def test_the_previewer_reads_either_case(self):
        api = ui.PermissionsAPI()
        api._granted.add('CAMERA')
        self.assertTrue(api.has('camera'))
        self.assertTrue(api.has(' Camera '))
        self.assertTrue(api.has('android.permission.CAMERA'))
        self.assertFalse(api.has('microphone'))


class TheFormTheGuideShows(unittest.TestCase):
    """native-features.md declares and asks with the full name,
    "android.permission.CAMERA" -- which wrote
    Manifest.permission.android.permission.CAMERA."""

    def test_it_builds_one_permission(self):
        source = SOURCE.replace('home = Screen(id="home")\n',
                                'home = Screen(id="home")\n'
                                'declare_permissions(["android.permission.CAMERA"])\n'
                                ).replace('"camera"', '"android.permission.CAMERA"')
        files = translate_python_to_android(source)
        self.assertNotIn('error.txt', files, files.get('error.txt', '')[:400])
        java = ''.join(v for k, v in files.items() if k.endswith('Activity.java'))
        self.assertIn('Manifest.permission.CAMERA)', java)
        self.assertNotIn('Manifest.permission.android', java)
        self.assertEqual(java.count('private static final int PERMISSION_REQ_CAMERA'), 1)
        self.assertEqual(files['AndroidManifest.xml'].count('android.permission.CAMERA'), 1)

    def test_both_runtimes_name_it_alike(self):
        from apkpy_lib.core.compiler import _permission_symbol
        for raw in ('camera', 'CAMERA', ' android.permission.CAMERA ',
                    'BLUETOOTH|maxSdkVersion=30', 'com.android.vending.BILLING'):
            self.assertEqual(ui._permission_name(raw), _permission_symbol(raw), raw)


if __name__ == '__main__':
    unittest.main()
