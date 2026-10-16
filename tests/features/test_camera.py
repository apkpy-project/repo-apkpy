"""Advanced camera contract, feature gate and Android callback generation."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import camera as contract
from apkpy_lib.features.camera import CameraAPI, CameraSimulator
from apkpy_lib.cli import generate_gradle_files


def build(command="camera.capture(on_result=done, on_error=failed)"):
    source='''from apkpy_lib import *
home=Screen(id="home")
out=label("Ready",screen=home)
def done(success,path):
    if success:
        out.set_value(path)
def failed(reason):
    out.set_value(reason)
def info(data):
    out.set_value(str(data))
def go():
    %s
button("Open",command=go,screen=home)
run(start_screen=home)
''' % command.replace('\n','\n    ')
    return translate_python_to_android(source)


class CameraContractTests(unittest.TestCase):
    def test_defaults_and_validation(self):
        self.assertEqual(contract.validate({}),contract.OPTIONS)
        for key,value in (("mode","portrait"),("lens","rear"),("zoom",0),("zoom",float('nan')),("timer",-1),("timer",1.5),("audio","False"),("jpeg_quality",101),("quality","8k"),("unknown",100),("focus_distance",-.5)):
            with self.subTest(key=key),self.assertRaises(ValueError):contract.validate({key:value})

    def test_no_implicit_webcam_or_fake_success(self):
        api=CameraAPI();answers=[];errors=[]
        with patch('apkpy_lib.ui.live_preview',return_value=None):
            api.capture(lambda *args:answers.append(args),on_error=errors.append)
        self.assertEqual(answers,[(False,"")]);self.assertEqual(errors,["unavailable"])
        self.assertTrue(api.capabilities()["simulated"])

    def test_busy_guard(self):
        api=CameraAPI();api._session=object();results=[];errors=[]
        api.open(lambda *args:results.append(args),on_error=errors.append)
        self.assertEqual(errors,["busy"]);self.assertEqual(results,[(False,"")])

    def test_simulated_frame_zoom_mirror_and_exposure(self):
        s=CameraSimulator(None,CameraAPI(),contract.OPTIONS,None,None)
        one=s.sample(120,90)
        s.options["zoom"]=2
        self.assertNotEqual(one.tobytes(),s.sample(120,90).tobytes())
        s.options["zoom"]=1;s.options["lens"]="front"
        from PIL import ImageOps
        self.assertEqual(ImageOps.mirror(one).tobytes(),s.sample(120,90).tobytes())

    def test_empty_apps_have_no_camera_runtime(self):
        files=build('out.set_value("plain")')
        self.assertNotIn("java/ApkpyCameraActivity.java",files)
        self.assertNotIn("CAMERA",files["AndroidManifest.xml"])
        self.assertNotIn("_apkpyCamera",files["java/Screen_homeActivity.java"])

    def test_capture_backwards_compatibility_and_dispatch(self):
        files=build();self.assertNotIn('error.txt',files)
        source=files['java/Screen_homeActivity.java']
        self.assertIn('_apkpyCameraOpen(',source)
        self.assertIn('case "done": pythonCallback_done(ok, path);',source)
        self.assertIn('case "failed": pythonCallback_failed(reason);',source)
        self.assertIn('_apkpyCameraRestore(savedInstanceState)',source)
        self.assertIn('_apkpyCameraSave(outState)',source)
        self.assertNotIn('ActivityResultContracts.TakePicture()',source)
        self.assertIn('path="apkpy_camera/"',files['res/xml/file_paths.xml'])

    def test_all_options_and_lambdas(self):
        files=build('camera.open(mode="video",lens="front",flash="off",quality="uhd",aspect_ratio="16:9",zoom=2,exposure=1,timer=3,grid=False,audio=False,mirror=False,max_duration=5,jpeg_quality=80,on_result=lambda ok,path: out.set_value(path))\ncamera.capture(on_result=lambda ok,path: out.set_value(path))')
        self.assertNotIn('error.txt',files)
        source=files['java/Screen_homeActivity.java']
        self.assertIn('camera_result_2',source)
        self.assertIn('"max_duration", String.valueOf(5)',source)

    def test_capabilities_and_available(self):
        files=build('camera.capabilities(on_result=info)\nif camera.available():\n    out.set_value("yes")')
        self.assertNotIn('error.txt',files)
        java=files['java/Screen_homeActivity.java']
        self.assertIn('pythonCallback_info(ApkpyCameraActivity.capabilities(getApplicationContext()))',java)
        self.assertIn('hasSystemFeature("android.hardware.camera.any")',java)

    def test_invalid_declarations_fail(self):
        for expr in ('camera.open(mode="8k")','camera.open(zom=2)','camera.open(timer=-1)','camera.open(on_result=lambda a: toast(a))','camera.record(mode="photo")','camera.fake()'):
            with self.subTest(expr=expr):
                result=build(expr)
                self.assertTrue('error.txt' in result, expr)
                self.assertIn('C1800',result['error.txt'])

    def test_manual_controls_and_constraints(self):
        files=build('camera.open(iso=200,shutter_ms=10,focus_distance=2,white_balance="daylight",on_result=done)')
        self.assertNotIn('error.txt',files)
        native=files['java/ApkpyCameraActivity.java']
        for token in ('CONTROL_AE_MODE_OFF','SENSOR_SENSITIVITY','SENSOR_EXPOSURE_TIME','CONTROL_AF_MODE_OFF','LENS_FOCUS_DISTANCE','CONTROL_AWB_MODE','SENSOR_INFO_SENSITIVITY_RANGE','setCaptureRequestOptions','ExifInterface'):
            self.assertIn(token,native)
        for expr in ('camera.open(iso=200)','camera.open(shutter_ms=10)','camera.open(focus_distance=-.5)','camera.capture(on_result=info)','camera.open(white_balance="guess")'):
            with self.subTest(expr=expr):self.assertTrue('error.txt' in build(expr),expr)

    def test_preview_manual_pair_rejected_before_ui(self):
        with self.assertRaises(ValueError):CameraAPI().open(iso=200)

    def test_preview_background_open_rejected_before_tk(self):
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future=executor.submit(CameraAPI().open)
            with self.assertRaisesRegex(RuntimeError, 'visible screen'):
                future.result()

    def test_stale_native_events_are_discarded(self):
        java=build()['java/ApkpyCameraActivity.java']
        self.assertIn('m!=manualGeneration',java)
        self.assertIn('if(destroyed){if(event instanceof VideoRecordEvent.Finalize)recordingFile.delete();return;}',java)
        self.assertIn('if(done||destroyed||pending==null',java)
        self.assertIn('preview.setTargetRotation(rotation)',java)

    def test_permissions_export_and_lifecycle(self):
        files=build('camera.record(audio=False,on_result=done)')
        self.assertNotIn('RECORD_AUDIO',files['AndroidManifest.xml'])
        self.assertIn('android:exported="false"',files['AndroidManifest.xml'])
        java=files['java/ApkpyCameraActivity.java']
        for token in ('bindToLifecycle','provider.unbindAll()','recording.stop()','withAudioEnabled()','onRequestPermissionsResult','FileProvider.getUriForFile','setReversedHorizontal','FocusMeteringAction','setExposureCompensationIndex'):
            self.assertIn(token,java)

    def test_gradle_feature_gate(self):
        with tempfile.TemporaryDirectory() as d:
            generate_gradle_files(d,'com.test.app','Test')
            self.assertNotIn('androidx.camera:',(Path(d)/'app/build.gradle').read_text())
            generate_gradle_files(d,'com.test.app','Test',needs_camera=True)
            gradle=(Path(d)/'app/build.gradle').read_text()
            for artifact in ('camera-camera2','camera-lifecycle','camera-view','camera-video'):
                self.assertIn('androidx.camera:'+artifact+':'+contract.CAMERAX_VERSION,gradle)

    def test_custom_ui_validation(self):
        invalid = ({'controls':['close']}, {'controls':['shutter']},
                   {'controls':['close','shutter','shutter']}, {'controls':['close','shutter','guess']},
                   {'controls':'close,shutter'}, {'labels':{'capture':''}},
                   {'labels':{'capture':'a\nb'}}, {'labels':{'unknown':'x'}},
                   {'colors':{'accent':'blue'}}, {'colors':{'guess':'#ffffff'}},
                   {'title':''}, {'button_radius':-1}, {'button_radius':float('nan')},
                   {'controls_position':'floating'})
        for value in invalid:
            with self.subTest(value=value),self.assertRaises(ValueError):contract.validate(value)

    def test_custom_ui_serialized_as_json(self):
        files=build('camera.capture(controls=["close","shutter","flip"], title="Receipt", labels={"capture":"Save \\"shot\\"","use_photo":"Keep"}, colors={"accent":"#a5b4fc"}, button_radius=8, controls_position="top", on_result=done)')
        self.assertNotIn('error.txt',files)
        java=files['java/Screen_homeActivity.java']
        self.assertIn('\\"shutter\\"',java)
        self.assertIn('\\"accent\\"',java)
        self.assertIn('"controls_position", String.valueOf("top")',java)
        native=files['java/ApkpyCameraActivity.java']
        self.assertNotIn('__CAMERA_UI_',native)
        self.assertIn('controlViews.get(key)',native)
        self.assertIn('controlsScroll.setVisibility(View.GONE)',native)
        # A plain View with WRAP_CONTENT fills the available height on Android.
        # The optional Pro placeholder must have a real intrinsic text height.
        self.assertNotIn('cell(header,new View(this))',native)
        self.assertIn('root.addView(header,new LinearLayout.LayoutParams(-1,-2))',native)

    def test_invalid_ui_fails_android_generation(self):
        for args in ('controls=["close"]', 'labels={"capture":""}', 'colors={"accent":"red"}',
                     'controls=some_controls','button_radius=100','title=""'):
            with self.subTest(args=args):
                result=build('camera.open('+args+')')
                self.assertIn('C1800',result.get('error.txt',''))

    def test_control_order_and_isolation(self):
        from apkpy_lib.core.features.camera_ui import control_rows
        order=['close','shutter','flip','zoom','torch','pause']
        self.assertEqual(control_rows(order,'photo'),[['shutter','flip'],['zoom'],['torch']])
        opts=contract.validate({'controls':order,'labels':{'capture':'My photo'},'colors':{'accent':'#123456'}})
        session=CameraSimulator(None,CameraAPI(),opts,None,None)
        self.assertEqual(session.ACCENT,'#123456')
        self.assertEqual(session.control_label('shutter'),'My photo')
        session.recording=True
        self.assertEqual(session.control_label('shutter'),'Stop')
        order.append('pro')
        self.assertNotIn('pro',session.order)
        other=CameraSimulator(None,CameraAPI(),contract.OPTIONS,None,None)
        self.assertEqual(other.ACCENT,'#95edc7')


if __name__=='__main__':unittest.main()
