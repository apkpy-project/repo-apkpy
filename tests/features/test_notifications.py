"""Notification API contract, native generation and headless Preview model."""
import ast
import os
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import notifications as contract
from apkpy_lib.features import notifications as preview
from apkpy_lib import ui


def source(body='notify("Hello", "World")', module=''):
    return '''from apkpy_lib import *
home = Screen(id="home")
detail = Screen(id="detail")
out = label("Ready", screen=home)
def selected():
    out.set_value("Selected")
def dismissed():
    out.set_value("Dismissed")
%s
def send():
%s
button("Send", command=send, screen=home)
run(start_screen=home)
''' % (module, '\n'.join('    '+line for line in body.splitlines()))


def build(body='notify("Hello", "World")', module=''):
    result = translate_python_to_android(source(body, module))
    if 'error.txt' in result:
        raise AssertionError(result['error.txt'])
    return result


class NotificationCompilerTests(unittest.TestCase):
    def test_old_signature_and_feature_gate(self):
        files = build('notify("Hello", "World", "stable-id")')
        self.assertIn('java/ApkpyNotifications.java', files)
        self.assertIn('POST_NOTIFICATIONS', files['AndroidManifest.xml'])
        self.assertIn('String.valueOf("stable-id")', files['java/Screen_homeActivity.java'])
        self.assertNotIn('private void _notify(', files['java/Screen_homeActivity.java'])
        plain = build('out.set_value("No notifications")')
        self.assertNotIn('java/ApkpyNotifications.java', plain)
        self.assertNotIn('POST_NOTIFICATIONS', plain['AndroidManifest.xml'])
        self.assertNotIn('_apkpyNotification', plain['java/Screen_homeActivity.java'])

    def test_shared_tables_and_all_styles(self):
        native = build()['java/ApkpyNotifications.java']
        self.assertIs(preview.IMPORTANCE, contract.IMPORTANCE)
        self.assertIs(preview.STYLES, contract.STYLES)
        for name, constant in contract.IMPORTANCE.items():
            self.assertIn('case "%s": return android.app.NotificationManager.%s;' % (name, constant), native)
        for style in contract.STYLES:
            self.assertIn('"%s"' % style, native)
        self.assertIn('i<3', native)

    def test_permission_and_immutable_intents(self):
        files = build()
        java = files['java/Screen_homeActivity.java']
        self.assertIn('registerForActivityResult', java)
        self.assertIn('TIRAMISU', java)
        self.assertIn('RequestPermission()', java)
        self.assertNotIn('ActivityCompat.requestPermissions(this, new String[]{android.Manifest.permission.POST_NOTIFICATIONS}', java)
        native = files['java/ApkpyNotifications.java']
        self.assertIn('PendingIntent.FLAG_IMMUTABLE', native)
        self.assertIn('PendingIntent.getActivity', native)
        self.assertIn('PendingIntent.getBroadcast', native)
        self.assertIn('android:exported="false"', files['AndroidManifest.xml'])

    def test_callbacks_cold_warm_and_screen_routes(self):
        files = build('notify("Title", "Body", on_tap=detail, on_dismiss=dismissed, actions=[("View", selected)])')
        java = files['java/Screen_homeActivity.java']
        native = files['java/ApkpyNotifications.java']
        self.assertIn('protected void onNewIntent', java)
        self.assertIn('ApkpyNotifications.open(this, intent)', java)
        self.assertIn('pythonCallback_selected(); return;', java)
        self.assertIn('pythonCallback_dismissed(); return;', java)
        self.assertIn('open(a,a.getIntent())', native)
        self.assertIn('case "detail": return Screen_detailActivity.class;', native)
        self.assertIn('case "home": return true;', native)
        self.assertNotIn('startActivity(', native)  # dismiss receivers cannot launch notification trampolines

    def test_allowed_condition_and_value(self):
        java = build('if notifications.allowed():\n    out.set_value("yes")\nvalue=notifications.allowed()\nout.set_value(value)')['java/Screen_homeActivity.java']
        self.assertIn('ApkpyNotifications.allowed(getApplicationContext())', java)
        self.assertIn('? "True" : "False"', java)

    def test_channel_cancel_progress_group_lines(self):
        java = build('notify("Title", "Body", channel="orders", style="inbox", lines=["A", "B"], progress=50, group="orders", when=1700000000000)\nnotifications.cancel("one")\nnotifications.cancel_all()\nnotifications.ask()',
                     'notifications.channel("orders", "Orders", importance="high")')['java/Screen_homeActivity.java']
        self.assertIn('ApkpyNotifications.channel(', java)
        self.assertIn('ApkpyNotifications.cancel(', java)
        self.assertIn('ApkpyNotifications.cancelAll(', java)
        self.assertIn('_apkpyNotificationAsk();', java)

    def test_invalid_declarations_are_diagnostics(self):
        for code, expected in (
            ('notify("A","B",actions=[("a",selected)]*4)', '3 actions'),
            ('notify("A","B",actions=[("a",selected),("b",selected),("c",selected),("d",selected)])', '3 actions'),
            ('notify("A","B",style="big_picture")', 'requires picture'),
            ('notify("A","B",style="other")', 'style'),
            ('notify("A","B",progress=101)', '0 to 100'),
            ('notify("A","B",lines=["x"])', 'inbox'),
            ('notify("A","B",on_tap=missing)', 'declared callback'),
            ('notify("A","B",icon="oops_not_real")', 'icon'),
            ('notifications.channel("x","X",importance="loud")', 'importance'),
            ('notifications.remove("x")', 'Unknown notifications'),
        ):
            with self.subTest(code=code):
                files = translate_python_to_android(source(code))
                self.assertIn('error.txt', files)
                self.assertIn(expected.lower(), files['error.txt'].lower())

    def test_callback_arity_and_lambda(self):
        files = translate_python_to_android(source('notify("A","B",on_tap=needs_value)', 'def needs_value(value):\n    out.set_value(value)'))
        self.assertIn('no parameters', files.get('error.txt',''))
        java = build('notify("A","B",actions=[("Change",lambda: out.set_value("lambda"))])')['java/Screen_homeActivity.java']
        self.assertIn('notification_action', java)

    def test_worker(self):
        module = '''def task():
    notifications.channel("work", "Work")
    if notifications.allowed():
        notify("Done", "Background work finished", channel="work")
worker = background_job("notice", run=task)
'''
        files = build('worker.enqueue({})', module)
        worker_java = '\n'.join(v for k,v in files.items() if k.endswith('.java') and 'Worker' in k and isinstance(v,str))
        self.assertIn('ApkpyNotifications.post(getApplicationContext()', worker_java)
        self.assertIn('ApkpyNotifications.allowed(getApplicationContext())', worker_java)
        self.assertNotIn('_apkpyNotify(', worker_java)
        self.assertIn('getApplicationContext().getPackageManager()', worker_java)
        self.assertNotIn('private void _apkpyOpenStore(', worker_java)

    def test_push_uses_same_publisher(self):
        files = build('push.simulate("Hello", "Push")', 'push.listen(screen=home, auto_notify=True, channel_id="updates", channel_name="Updates")')
        java = files['java/ApkpyFirebaseMessagingService.java']
        self.assertIn('ApkpyNotifications.post(', java)
        self.assertNotIn('new androidx.core.app.NotificationCompat.Builder', java)

    def test_push_target_screen_is_preserved(self):
        files=build('push.simulate("Hello", "Push")', 'push.listen(screen=detail, auto_notify=False)')
        self.assertIn('new android.content.Intent(context, Screen_detailActivity.class)',files['java/ApkpyFirebaseMessagingService.java'])
        self.assertIn('autoNotificationsEnabled()',files['java/Screen_detailActivity.java'])

    def test_picture_is_inside_android_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            image=Path(directory)/'test.png'
            image.write_bytes(b'fixture')
            files=translate_python_to_android(source('notify("A","B",style="big_picture",picture="test.png")'),project_root=directory)
            self.assertNotIn('error.txt',files)
            assets=[k for k in files if k.startswith('app/src/main/assets/apkpy_notifications/')]
            self.assertEqual(len(assets),1)
            kind,copied=files[assets[0]]
            self.assertEqual(kind,'COPY_FILE')
            # The same file, however the path is spelled: a Windows temporary
            # folder can be named short (RUNNER~1) on one side and long on the other.
            self.assertEqual(os.path.normcase(os.path.realpath(copied)),
                             os.path.normcase(os.path.realpath(str(image))))

    def test_permission_queue_survives_activity_recreation(self):
        files=build()
        for screen in ('home','detail'):
            java=files['java/Screen_%sActivity.java'%screen]
            self.assertIn('_apkpyNotificationRestore(savedInstanceState);',java)
            self.assertIn('_apkpyNotificationSave(outState);',java)
            self.assertIn('!_apkpyNotificationRequestActive',java)

    def test_bad_inbox_lines_and_lambda_parameters(self):
        for code in ('notify("A","B",style="inbox",lines=[1])',
                     'notify("A","B",on_tap=lambda x: selected())',
                     'notify("A","B",actions=[("View",lambda x:selected())])'):
            self.assertIn('error.txt',translate_python_to_android(source(code)))


class NotificationModelTests(unittest.TestCase):
    def setUp(self):
        self.api = preview.NotificationsAPI()
        self.bind = patch.object(preview, 'notifications', self.api)
        self.bind.start()
        self.root = patch.object(ui, 'live_preview_root', return_value=None)
        self.root.start()

    def tearDown(self):
        self.root.stop()
        self.bind.stop()

    def test_headless_does_not_create_a_window(self):
        before = getattr(ui._app, '_instance', None)
        preview.notify('Hello', 'World')
        self.assertIs(getattr(ui._app, '_instance', None), before)
        self.assertEqual(len(self.api.items),1)

    def test_channel_importance_is_immutable(self):
        self.api.channel('orders','Orders','low')
        self.api.channel('orders','Renamed','high')
        self.assertEqual(self.api.channels['orders'],{'name':'Renamed','importance':'low'})

    def test_update_replaces_same_id(self):
        preview.notify('One','A','one',progress=20)
        preview.notify('One','B','one',progress=80)
        self.assertEqual(len(self.api.items),1)
        self.assertEqual(self.api.items['one']['progress'],80)

    def test_tap_action_and_dismiss(self):
        events=[]
        preview.notify('One','A','one',actions=[('View',lambda:events.append('action'))],on_tap=lambda:events.append('tap'))
        self.api._action('one',0)
        self.api._action('one',0)
        self.assertIn('one',self.api.items)
        self.api._tap('one')
        self.assertNotIn('one',self.api.items)
        preview.notify('Two','B','two',on_dismiss=lambda:events.append('dismiss'))
        self.api._dismiss('two')
        self.assertEqual(events,['action','action','tap','dismiss'])

    def test_cancel_does_not_call_dismiss_and_ongoing_is_protected(self):
        called=[]
        preview.notify('One','A','one',ongoing=True,on_dismiss=lambda:called.append(1))
        self.assertFalse(self.api._dismiss('one'))
        self.api.cancel('one')
        self.assertEqual(called,[])
        self.assertFalse(self.api.items)

    def test_permission_denied(self):
        self.api._allowed=False
        preview.notify('Hidden','Denied')
        self.assertFalse(self.api.items)

    def test_runtime_validation(self):
        for kwargs in ({'progress':-1},{'style':'bogus'},{'style':'big_picture'}, {'when':float('nan')}, {'channel':'undeclared'}, {'actions':[('x',123)]}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                preview.notify('A','B',**kwargs)


if __name__ == '__main__':
    unittest.main()
