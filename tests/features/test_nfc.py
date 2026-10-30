"""NFC contracts, generated Java, lifecycle and simulator parity."""
import json
import base64
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from apkpy_lib.core.features import nfc as codegen
from apkpy_lib.features import nfc as preview
from apkpy_lib.core.compiler import translate_python_to_android

APP = '''from apkpy_lib import Screen, button, label, nfc, run, json_get
home = Screen(id="home")
result = label("Tap start", id="result", screen=home)
def tagged(ok, tag):
    result.set_value(json_get(tag, "text"))
def failed(ok, reason):
    result.set_value(reason)
def start():
    nfc.status(on_result=failed)
    nfc.start(on_tag=tagged, on_error=failed)
def stop():
    nfc.stop()
button("Start", id="start", screen=home, command=start)
button("Stop", id="stop", screen=home, command=stop)
button("Settings", id="settings", screen=home, command=lambda: nfc.settings())
run(start_screen=home)
'''


def generate(source=APP):
    files = translate_python_to_android(source)
    if not files or "error.txt" in files:
        raise AssertionError(files)
    return files


class NfcCompilerTests(unittest.TestCase):
    def test_gate(self):
        files = generate()
        self.assertIn("java/ApkpyNfc.java", files)
        self.assertIn('android.permission.NFC', files['AndroidManifest.xml'])
        self.assertIn('android.hardware.nfc" android:required="false"', files['AndroidManifest.xml'])
        plain = generate('from apkpy_lib import Screen, label, run\nhome=Screen(id="home")\nlabel("Hi", screen=home)\nrun(start_screen=home)')
        body = "\n".join(plain.values())
        for term in ('ApkpyNfc', 'NfcAdapter', 'android.permission.NFC', 'android.hardware.nfc'):
            self.assertNotIn(term, body)

    def test_verbs_and_both_activity_emitters(self):
        activity = generate()['java/Screen_homeActivity.java']
        for marker in ('_nfc.status(', '_nfc.start(', '_nfc.stop();', '_nfc.settings();'):
            self.assertIn(marker, activity)
        self.assertIn('pythonCallback_tagged(boolean ok, String tag)', activity)
        for event, call in (('onResume', '_nfc.resume();'), ('onPause', '_nfc.pause();'), ('onDestroy', '_nfc.close();')):
            self.assertIn(call, activity[activity.index('protected void '+event):][:500])

    def test_nested_callback_scope_and_boolean_forwarding(self):
        source = APP.replace('def tagged(ok, tag):\n    result.set_value(json_get(tag, "text"))',
                                'def tagged(ok, tag):\n    nfc.status(on_result=failed)\n    failed(ok, tag)')
        java = generate(source)['java/Screen_homeActivity.java']
        self.assertIn('new ApkpyNfc.Listener()', java)
        self.assertIn('pythonCallback_failed((ok), String.valueOf(tag));', java)
        self.assertNotIn('_nfc.status((ok, value) ->', java)

    def test_invalid_method_and_arguments_are_u2033(self):
        for invalid in ('nfc.scan()', 'nfc.start(on_tags=tagged)', 'nfc.write()',
                        'nfc.write(text="x", url="https://x")', 'nfc.stop(1)', 'nfc.write(text=None)'):
            with self.subTest(invalid=invalid):
                files = translate_python_to_android(APP.replace('nfc.stop()', invalid))
                self.assertIn('U2033', files['error.txt'])
                self.assertIn('nfc.start()', files['error.txt'])

    def test_callback_arity(self):
        files = translate_python_to_android(APP.replace('def tagged(ok, tag):', 'def tagged(tag):'))
        self.assertIn('U2033', files['error.txt'])
        self.assertIn('(ok, value)', files['error.txt'])

    def test_module_level_and_nested_gate(self):
        source = APP.replace('def start():\n    nfc.status(on_result=failed)', 'def start():\n    if True:\n        nfc.status(on_result=failed)')
        self.assertIn('java/ApkpyNfc.java', generate(source))
        self.assertIn('_nfc.status(', generate(APP.replace('run(start_screen=home)', 'nfc.status(on_result=failed)\nrun(start_screen=home)'))['java/Screen_homeActivity.java'])

    def test_reader_thread_guards_and_close(self):
        java = codegen.shared_class_java('com.test')
        for term in ('enableReaderMode', 'disableReaderMode', 'runOnUiThread', 'getCachedNdefMessage',
                     'finally { try { ndef.close()', 'generation == revision', 'FLAG_READER_NO_PLATFORM_SOUNDS'):
            self.assertIn(term, java)
        self.assertNotIn('FLAG_READER_SKIP_NDEF_CHECK', java)
        self.assertNotIn('enableForegroundDispatch', java)

    def test_worker_stop_is_not_silently_dropped(self):
        source = APP.replace('from apkpy_lib import Screen,', 'from apkpy_lib import background_job, Screen,')
        source = source.replace('run(start_screen=home)', '''def task(job, payload):
    nfc.stop()
    return True
worker = background_job("stop_nfc", run=task)
run(start_screen=home)''')
        files = generate(source)
        workers = '\n'.join(v for k, v in files.items() if 'Worker' in k and k.endswith('.java'))
        self.assertIn('ApkpyNfc.stopAll();', workers)

    def test_documented_example_and_cli_build(self):
        from click.testing import CliRunner
        from apkpy_lib.cli import main
        from zipfile import ZipFile
        import _layout
        if _layout.examples() is None:
            self.skipTest('the examples are not in this checkout')
        source = (_layout.examples() / '29_nfc_tags.py').read_text(encoding='utf-8')
        files = generate(source)
        self.assertIn('_nfc.write(', files['java/Screen_homeActivity.java'])
        from unittest import mock
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path('writehere.py').write_text(source, encoding='utf-8')
            Path('apkpy.toml').write_text('[app]\nname="NFC Lab"\napplication_id="com.apkpy.nfctest"\n', encoding='utf-8')
            # The build keeps its map of lines for apkpy logs in ~/.apkpy:
            # here, in the throwaway folder instead.
            with mock.patch('apkpy_lib.native_build.apkpy_home',
                            return_value=str(Path('home').resolve())):
                result = runner.invoke(main, ['build'])
            self.assertEqual(result.exit_code, 0, result.output + str(result.exception))
            archives = list(Path('.').glob('*.zip'))
            self.assertEqual(len(archives), 1)
            with ZipFile(archives[0]) as archive:
                self.assertTrue(any(n.endswith('/ApkpyNfc.java') for n in archive.namelist()))

    def test_background_reader_is_refused(self):
        source = APP.replace('from apkpy_lib import Screen,', 'from apkpy_lib import background_job, Screen,')
        source = source.replace('run(start_screen=home)', '''def task(job, payload):
    nfc.start(on_tag=tagged, on_error=failed)
    return True
worker = background_job("read_nfc", run=task)
run(start_screen=home)''')
        self.assertIn('U2033', translate_python_to_android(source)['error.txt'])


class NfcPreviewTests(unittest.TestCase):
    def test_shared_reasons(self):
        self.assertIs(preview.REASONS, codegen.REASONS)
        self.assertIs(preview.nfc.reasons, codegen.REASONS)

    def test_no_window_is_constructed(self):
        from apkpy_lib import ui
        old = ui._app._instance
        with patch.object(ui._app, '_instance', None):
            seen = []
            preview.NfcAPI().start(on_error=lambda *args: seen.append(args))
            self.assertEqual([(False, 'unsupported')], seen)
            self.assertIsNone(ui._app._instance)
        self.assertIs(ui._app._instance, old)

    def test_status_is_explicit_simulation_ready(self):
        seen = []
        preview.NfcAPI().status(lambda *args: seen.append(args))
        self.assertEqual(seen, [(True, 'ready')])

    def session(self):
        class Screen: pass
        screen = Screen()
        ui = SimpleNamespace(_screen_lifecycles={})
        app = SimpleNamespace(_active_screen=screen)
        session = preview._Session(ui, app, screen)
        session.open_panel = lambda: None
        return session, screen

    def test_six_tags_and_lifecycle(self):
        session, screen = self.session()
        seen = []
        session.tap('Text tag')
        self.assertEqual(seen, [])
        session.start(lambda ok, value: seen.append(json.loads(value)), None)
        for name in session.tags:
            session.tap(name)
        self.assertEqual(len(seen), 6)
        self.assertEqual(seen[0]['text'], 'Olá, ApkPy!')
        self.assertEqual(seen[1]['url'], 'https://example.com/nfc')
        self.assertEqual(seen[2]['type'], 'FORMATABLE')
        self.assertEqual(seen[3]['writable'], 'no')
        self.assertEqual(seen[4]['size'], '12')
        self.assertEqual(seen[5]['used'], '')
        self.assertEqual(len(seen[5]), 9)
        session.app._active_screen = object()
        session.tap('Text tag')
        self.assertEqual(len(seen), 6)
        session.app._active_screen = screen
        session.stop(); session.tap('Text tag')
        self.assertEqual(len(seen), 6)


class NfcWriteTests(NfcPreviewTests):
    def test_write_without_start(self):
        seen = []
        api = preview.NfcAPI()
        api.write(text="Hello", on_result=lambda *args: seen.append(args))
        self.assertEqual(seen, [(False, 'not_started')])

    def test_each_write_failure_and_one_shot(self):
        for tag, reason in [('Read-only', 'read_only'), ('Small (12 B)', 'too_small'),
                            ('Unknown tech', 'no_ndef'), ('Tag lost', 'tag_lost')]:
            with self.subTest(tag=tag):
                session, screen = self.session()
                seen = []
                session.start(lambda *v: seen.append(('tag',) + v), None)
                session.write('text', 'A message longer than twelve bytes', lambda *v: seen.append(v))
                session.tap(tag)
                self.assertEqual(seen, [(False, reason)])
                self.assertIsNone(session.pending)
                session.tap('Text tag')
                self.assertEqual(seen[-1][0], 'tag')

    def test_write_success_order_and_updated_data(self):
        for tag in ('Text tag', 'URL tag', 'Empty tag'):
            session, screen = self.session()
            seen = []
            session.start(lambda ok, value: seen.append(('tag', json.loads(value))), None)
            session.write('text', 'Olá 🌍', lambda *args: seen.append(args))
            self.assertEqual(seen, [])
            session.tap(tag)
            self.assertEqual(seen[0], (True, 'ok'))
            self.assertEqual(seen[1][1]['text'], 'Olá 🌍')
            self.assertEqual(seen[1][1]['used'], str(preview._message_size([codegen.write_record('text', 'Olá 🌍')])))
            if tag == 'Empty tag':
                self.assertEqual(seen[1][1]['size'], '')
                session.tap(tag)
                self.assertEqual(seen[-1][1]['size'], '492')

    def test_url_normalization_and_all_prefixes(self):
        for prefix in codegen.URI_PREFIXES:
            value = prefix + 'example'
            record = codegen.write_record('url', value)
            decoded = codegen.decode_tag(b'', 'NDEF', 'yes', '', '', '', [record])
            self.assertEqual(decoded['url'], value)
        self.assertEqual(codegen.write_record('url', 'HTTPS://example.com')[2], b'\x04example.com')

    def test_cancel_stop_pause_replace_and_empty_url(self):
        session, screen = self.session()
        seen = []
        session.start(lambda *v: None, None)
        for action in (session.cancel_write, session.pause, session.stop):
            session.started = True
            session.write('text', 'first', lambda *v: seen.append(v))
            action()
            self.assertIsNone(session.pending)
        self.assertEqual(seen, [])
        session.started = True
        session.write('url', '', lambda *v: seen.append(v))
        self.assertEqual(seen, [(False, 'unknown')])
        session.write('text', 'first', lambda *v: seen.append(v))
        session.write('text', 'last', lambda *v: seen.append(v))
        session.tap('Text tag')
        self.assertEqual(session.tags['Text tag']['records'], [codegen.write_record('text', 'last')])

    def test_capacity_counts_bytes_and_header_not_characters(self):
        session, screen = self.session()
        seen = []
        session.start(None, None)
        session.write('text', '12345', lambda *v: seen.append(v))
        session.tap('Small (12 B)')
        self.assertEqual(seen[-1], (True, 'ok'))  # 4-byte header + status/lang + 5 chars.
        session.write('text', 'ééé', lambda *v: seen.append(v))
        session.tap('Small (12 B)')
        self.assertEqual(seen[-1], (False, 'too_small'))

    def test_write_generator(self):
        source = APP.replace('nfc.stop()', 'nfc.write(text="Olá", on_result=failed)\n    nfc.write(url="https://example.com", on_result=failed)\n    nfc.cancel_write()')
        activity = generate(source)['java/Screen_homeActivity.java']
        self.assertIn('_nfc.write("text",', activity)
        self.assertIn('_nfc.write("url",', activity)
        self.assertIn('_nfc.cancelWrite();', activity)
        java = codegen.shared_class_java('com.test')
        for term in ('getAndSet(null)', 'createTextRecord("en", value)', 'createUri(value)',
                     'isWritable()', 'getMaxSize()', 'writeNdefMessage(', 'formatable.format(',
                     'read(tag, true)', 'finally { try { formatable.close()', 'writeRevision.get() != request.revision'):
            self.assertIn(term, java)


class NfcJavaParityTests(unittest.TestCase):
    def test_actual_java_decoder_matches_python(self):
        jdk = Path(r'C:\Program Files\Android\Android Studio\jbr\bin')
        javac = str(jdk / 'javac.exe') if jdk.exists() else shutil.which('javac')
        java = str(jdk / 'java.exe') if jdk.exists() else shutil.which('java')
        if not javac or not java:
            self.skipTest('JDK needed for real Java codec parity')
        records = [[], [(0, b'', b'')], [(1, b'T', b'')], [(1, b'T', b'\x02en')],
                   [(1, b'T', b'\x05pt-PT' + 'Olá 🌍'.encode())],
                   [(1, b'T', b'\x82en' + 'Olá 🌍'.encode('utf-16'))],
                   [(1, b'T', b'\x85pt-PT' + 'Olá'.encode('utf-16-be'))],
                   [(1, b'T', b'\x82en\xfe\xff' + 'Olá'.encode('utf-16-be'))],
                   [(1, b'T', b'\x3fenX')], [(1, b'T', b'\x02en\xff')],
                   [(1, b'U', b'\xffx')], [(1, b'U', b'')],
                   [(2, b'text/plain', b'hello\nworld')], [(2, b'image/png', b'\x89PNG\x00')],
                   [(4, b'example.com:note', 'Hello 🌍'.encode())],
                   [(1, b'T', b'\x02en'), (1, b'T', b'\x02enSecond')],
                   [(1, b'U', b'\x04first'), (1, b'U', b'\x04second')],
                   [(2, b'image/png', b'\x00'), (1, b'T', b'\x02enReadable')]]
        records += [[(1, b'U', bytes([i]) + b'example')] for i in range(36)]
        records += [[(1, b'U', bytes([i]))] for i in range(36)]
        records += [[(1, b'T', b'\x02en' + ('x' * n).encode())] for n in (1, 252, 253, 256, 1000)]
        source = codegen.shared_class_java('com.test')
        codec = source.split('// BEGIN PORTABLE CODEC')[1].split('\n', 1)[1].split('// END PORTABLE CODEC')[0]
        harness = '''public class NfcHarness {
__CODEC__
public static void main(String[] args) throws Exception {
 System.setOut(new java.io.PrintStream(System.out, true, "UTF-8"));
 java.io.BufferedReader in = new java.io.BufferedReader(new java.io.InputStreamReader(System.in, "UTF-8"));
 String line;
 while ((line = in.readLine()) != null) {
  String[] parts = line.isEmpty() ? new String[0] : line.split(";", -1);
  Codec.Record[] records = new Codec.Record[parts.length];
  for (int i=0; i<parts.length; i++) {
   String[] p=parts[i].split(",", -1);
   records[i]=new Codec.Record(Integer.parseInt(p[0]), java.util.Base64.getDecoder().decode(p[1]), java.util.Base64.getDecoder().decode(p[2]));
  }
  System.out.println(Codec.tagJson(new byte[]{4,(byte)162,36}, "NDEF", "yes", "492", "", "NfcA,Ndef", records));
 }
}
}'''.replace('__CODEC__', codec)
        with tempfile.TemporaryDirectory(prefix='apkpy-nfc-') as folder:
            path = Path(folder) / 'NfcHarness.java'
            path.write_text(harness, encoding='utf-8')
            subprocess.run([javac, '-encoding', 'UTF-8', str(path)], check=True, capture_output=True)
            fixture = '\n'.join(';'.join(str(tnf) + ',' + base64.b64encode(t).decode() + ',' + base64.b64encode(p).decode() for tnf, t, p in rs) for rs in records) + '\n'
            completed = subprocess.run([java, '-Dfile.encoding=UTF-8', '-cp', folder, 'NfcHarness'], input=fixture,
                                       text=True, encoding='utf-8', capture_output=True, check=True)
        actual = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(len(actual), len(records))
        for rs, got in zip(records, actual):
            self.assertEqual(got, codegen.decode_tag(bytes([4, 162, 36]), 'NDEF', 'yes', '492', '', 'NfcA,Ndef', rs), rs)
        print('NFC decoder: %d real Java/Python parity cases' % len(records))


class ANewReaderDoesNotInheritTheOldTag(NfcPreviewTests):
    """Restarting the reader inside a write callback delivered the old tag.

    After a write, tap() reports the write result and then goes on to report
    the tag it read. The checks in between only asked whether the reader was
    started and the screen current -- both still true after a restart -- so
    the finished session"s tag arrived at the new session"s handler, with
    nobody having tapped anything. Android holds a revision number and
    re-checks it after the callback for exactly this reason.
    """

    def test_the_tag_of_the_closed_session_is_dropped(self):
        session, screen = self.session()
        seen = []

        def wrote(*values):
            seen.append(("write",) + values)
            session.start(lambda *v: seen.append(("second",) + v), None)

        session.start(lambda *v: seen.append(("first",) + v), None)
        session.write("text", "old write", wrote)
        session.tap("Text tag")

        self.assertEqual(["write"], [event[0] for event in seen],
                         "a leitura da sessao fechada chegou a nova: %r" % (seen,))

    def test_without_a_restart_the_tag_still_arrives(self):
        session, screen = self.session()
        seen = []
        session.start(lambda *v: seen.append(("tag",) + v), None)
        session.write("text", "written", lambda *v: seen.append(("write",) + v))
        session.tap("Text tag")

        self.assertEqual(["write", "tag"], [event[0] for event in seen])

    def test_stopping_inside_the_callback_also_drops_it(self):
        session, screen = self.session()
        seen = []

        def wrote(*values):
            seen.append(("write",) + values)
            session.stop()

        session.start(lambda *v: seen.append(("tag",) + v), None)
        session.write("text", "written", wrote)
        session.tap("Text tag")

        self.assertEqual(["write"], [event[0] for event in seen])


if __name__ == '__main__':
    unittest.main()
