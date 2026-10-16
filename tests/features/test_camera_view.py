import unittest
from pathlib import Path
from apkpy_lib import Screen, camera_view
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features.camera_view import validate

SOURCE='''from apkpy_lib import *
home=Screen(id="home")
status=label("Ready",screen=home)
def ready():
    status.set_value("live")
def photo(ok,path):
    if ok:
        status.set_value(path)
def error(reason):
    status.set_value(reason)
visor=camera_view(screen=home,on_ready=ready,on_capture=photo,on_error=error)
def take():
    visor.capture()
    visor.set_zoom(2)
    visor.set_flash("auto")
    visor.set_torch(True)
    visor.flip()
    visor.stop()
    visor.start()
    visor.hide()
    visor.show()
button("Take",command=take,screen=home)
run(start_screen=home)
'''


class EmbeddedCameraTests(unittest.TestCase):
    def test_public_contract(self):
        view=camera_view(screen=Screen(id='camera_test'),autostart=False)
        self.assertEqual(view.comp_type,'camera_view')
        for method in ('capture','start','stop','flip','set_zoom','set_torch','set_flash'):
            self.assertTrue(callable(getattr(view,method)))
        for opt in ({'fit':'fill'},{'lens':'rear'},{'zoom':0},{'zoom':float('nan')},{'autostart':1},{'mirror':'yes'},{'video':True}):
            with self.subTest(opt=opt),self.assertRaises(ValueError):validate(opt)
        with self.assertRaises(ValueError):camera_view()
    def test_generation(self):
        files=translate_python_to_android(SOURCE)
        self.assertNotIn('error.txt',files,files.get('error.txt'))
        native=files['java/ApkpyCameraView.java'];activity=files['java/Screen_homeActivity.java']
        xml=files['res/layout/activity_screen_home.xml']
        self.assertIn('.ApkpyCameraView',xml)
        self.assertIn('cameraView1.configure(this',activity)
        for call in ('.capture()', '.setZoom(','.setFlash(','.setTorch(','.flip()', '.stop()', '.start()'):
            self.assertIn('cameraView1'+call,activity)
        for token in ('bindToLifecycle','RequestPermission','FileProvider.getUriForFile','revision!=generation','onPause','provider.unbind(preview)','isShown()'):
            self.assertIn(token,native)
        self.assertNotIn('unbindAll()',native)
        self.assertIn('android.permission.CAMERA',files['AndroidManifest.xml'])
        self.assertNotIn('android.permission.RECORD_AUDIO',files['AndroidManifest.xml'])
    def test_nested_and_multiple_screens(self):
        source=SOURCE.replace('visor=camera_view(screen=home,','box=container(screen=home)\nvisor=camera_view(parent=box,')
        source=source.replace('run(start_screen=home)','other=Screen(id="other")\nlabel("Other",screen=other)\nrun(start_screen=home)')
        files=translate_python_to_android(source)
        self.assertNotIn('error.txt',files,files.get('error.txt'))
        self.assertIn('cameraView1',files['res/layout/activity_screen_home.xml'])
        self.assertNotIn('cameraView1.capture()',files['java/Screen_otherActivity.java'])
    def test_invalid_compile(self):
        for text in ('camera_view(screen=home,fit="stretch")','camera_view(screen=home,on_ready=photo)', 'camera_view(screen=home,on_capture=ready)','camera_view(screen=home,controls=False)'):
            source=SOURCE.replace('camera_view(screen=home,on_ready=ready,on_capture=photo,on_error=error)',text)
            with self.subTest(text=text):
                files=translate_python_to_android(source)
                self.assertIn('C1800',files.get('error.txt',''))
        for action in ('visor.record()','visor.capture(True)','visor.set_zoom(-1)','visor.set_torch("yes")'):
            with self.subTest(action=action):
                files=translate_python_to_android(SOURCE.replace('visor.capture()',action))
                self.assertIn('C1800',files.get('error.txt',''))
    def test_plain_project_unchanged(self):
        files=translate_python_to_android('from apkpy_lib import *\nhome=Screen(id="home")\nlabel("Hello",screen=home)\nrun(start_screen=home)')
        self.assertNotIn('java/ApkpyCameraView.java',files)
        self.assertNotIn('java/ApkpyCameraActivity.java',files)
        self.assertNotIn('CAMERA',files['AndroidManifest.xml'])

if __name__=='__main__':unittest.main()
