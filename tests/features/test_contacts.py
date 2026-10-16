"""Contacts permissions, code generation, lifecycle and synthetic address book."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from apkpy_lib.core.compiler import translate_python_to_android
from apkpy_lib.core.features import contacts as codegen
from apkpy_lib.features import contacts as preview

APP = '''from apkpy_lib import Screen, button, label, contacts, run, json_get
home = Screen(id="home")
status = label("Choose a contact", id="status", screen=home)
def result(ok, value):
    if ok:
        status.set_value(json_get(value, "name"))
    else:
        status.set_value(value)
def pick():
    contacts.pick(on_result=result)
button("Pick", screen=home, command=pick)
run(start_screen=home)
'''

def generate(source=APP):
    files = translate_python_to_android(source)
    if not files or 'error.txt' in files: raise AssertionError(files)
    return files

class CompilerTests(unittest.TestCase):
    def test_pick_has_no_contacts_permission(self):
        files = generate()
        self.assertIn('java/ApkpyContacts.java', files)
        self.assertNotIn('READ_CONTACTS', files['AndroidManifest.xml'])
        self.assertNotIn('WRITE_CONTACTS', files['AndroidManifest.xml'])
        self.assertIn('pythonCallback_result(boolean ok, String value)', files['java/Screen_homeActivity.java'])

    def test_list_get_permission_only(self):
        for call in ('contacts.list(on_result=result)', 'contacts.get("1", on_result=result)'):
            files = generate(APP.replace('contacts.pick(on_result=result)', call))
            self.assertIn('android.permission.READ_CONTACTS', files['AndroidManifest.xml'])
            self.assertNotIn('WRITE_CONTACTS', files['AndroidManifest.xml'])

    def test_editor_no_write_permission(self):
        for call in ('contacts.create("Test", phone="123", email="t@example.com", on_result=result)', 'contacts.edit("1", on_result=result)', 'contacts.settings(on_result=result)'):
            files = generate(APP.replace('contacts.pick(on_result=result)', call))
            self.assertNotIn('READ_CONTACTS', files['AndroidManifest.xml'])
            self.assertNotIn('WRITE_CONTACTS', files['AndroidManifest.xml'])

    def test_no_feature_no_runtime(self):
        files = generate(APP.replace('contacts.pick(on_result=result)', 'status.set_value("No contacts")'))
        self.assertNotIn('ApkpyContacts', '\n'.join(files.values()))

    def test_invalid_shapes_fail(self):
        calls = ('contacts.delete("1")', 'contacts.pick(kind="all")', 'contacts.pick(other=True)',
                 'contacts.get()', 'contacts.list(limit=0)', 'contacts.list(limit=101)',
                 'contacts.list(offset=-1)', 'contacts.list(limit=True)', 'contacts.create(name=10)',
                 'contacts.pick(**options)', 'contacts.pick("phone", kind="phone")')
        for call in calls:
            with self.subTest(call=call):
                files = translate_python_to_android(APP.replace('contacts.pick(on_result=result)', call))
                self.assertIn('U2033', files['error.txt'])

    def test_callback_arity(self):
        files = translate_python_to_android(APP.replace('def result(ok, value):', 'def result(value):'))
        self.assertIn('(ok, value)', files['error.txt'])

    def test_lambda_and_nested_boolean_forward(self):
        source = APP.replace('contacts.pick(on_result=result)', 'contacts.pick(on_result=lambda ok, value: result(ok, value))')
        java = generate(source)['java/Screen_homeActivity.java']
        self.assertIn('pythonCallback_result((ok), String.valueOf(value))', java)

    def test_lifecycle_state_and_main_thread(self):
        files = generate()
        activity = files['java/Screen_homeActivity.java']
        self.assertIn('_contacts.restore(savedInstanceState)', activity)
        self.assertIn('_contacts.save(outState)', activity)
        java = files['java/ApkpyContacts.java']
        for token in ('newSingleThreadExecutor', 'runOnUiThread', 'CancellationSignal',
                      'onDestroy', 'onPause', 'onResume', '"editor_returned"', 'try (Cursor',
                      'shouldShowRequestPermissionRationale', '"permission_blocked"', '"busy"'):
            self.assertIn(token, java)

    def test_bound_queries_and_batched_details(self):
        java = codegen.shared_class_java('com.test')
        self.assertIn('LIKE ? ESCAPE', java)
        self.assertIn('IN (?,?)', java)
        self.assertIn('Collections.nCopies(rows.size(), "?")', java)
        self.assertIn('if (limit < 1 || limit > 100', java)
        self.assertNotIn('WRITE_CONTACTS', java)
        self.assertNotIn('getContentResolver().delete', java)

    def test_module_and_background(self):
        source = APP.replace('run(start_screen=home)', 'contacts.pick(on_result=result)\nrun(start_screen=home)')
        self.assertIn('_contacts.call(', generate(source)['java/Screen_homeActivity.java'])
        source = APP.replace('from apkpy_lib import Screen,', 'from apkpy_lib import background_job, Screen,')
        source = source.replace('run(start_screen=home)', '''def task(job, payload):
    contacts.list(on_result=result)
    return True
work = background_job("contacts", run=task)
run(start_screen=home)''')
        self.assertIn('foreground screen', translate_python_to_android(source)['error.txt'])

class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.api = preview.ContactsAPI()
        self.events = []
        self.cb = lambda ok, value: self.events.append((ok, value))
        self.api._show = lambda mode: None

    def request(self, verb, options):
        self.api._pending = (verb, options, self.cb, object())
        self.api._run()

    def test_no_window_no_access(self):
        with patch.object(preview, '_window', return_value=(None, None)):
            self.api.pick(on_result=self.cb)
        self.assertEqual(self.events, [(False, 'unavailable')])

    def test_shared_reasons(self):
        self.assertIs(self.api.reasons, codegen.REASONS)

    def test_permission_and_denials(self):
        for state, reason in (('denied', 'permission_denied'), ('blocked', 'permission_blocked')):
            self.request('list', {'query': '', 'limit': 50, 'offset': 0})
            self.api._grant(state)
            self.assertEqual(self.events[-1], (False, reason))
            self.api._permission = 'ask'

    def test_listing_paging_literal_search(self):
        self.api._permission = 'granted'
        self.request('list', {'query': '', 'limit': 2, 'offset': 1})
        rows = json.loads(self.events[-1][1])
        self.assertEqual([r['name'] for r in rows], ['Jamie Lee', 'Sam Rivera'])
        self.assertEqual(set(rows[0]), set(codegen.FIELDS))
        self.assertEqual(self.api._book.list('%', 50, 0), [])
        self.assertEqual(self.api._book.list("' OR 1=1 --", 50, 0), [])
        self.assertEqual(len(self.api._book.list('aLeX', 50, 0)), 1)

    def test_picker_scopes_selected_value(self):
        self.request('pick', {'kind': 'phone'})
        self.api._select('1')
        value = json.loads(self.events[-1][1])
        self.assertEqual(value['email'], '')
        self.assertEqual(value['emails'], [])
        self.assertTrue(value['phone'])
        self.assertEqual(self.api._permission, 'ask')

    def test_get_missing(self):
        self.api._permission = 'granted'
        self.request('get', {'id': '999'})
        self.assertEqual(self.events, [(False, 'not_found')])

    def test_editor_save_cancel_edit(self):
        self.request('create', {})
        self.api._editor_done(True, ['Test', '123', 'test@example.com'])
        outcome = json.loads(self.events[-1][1])
        self.assertEqual(outcome['status'], 'editor_returned')
        self.assertEqual(len(self.api._book.rows), 5)
        self.request('edit', {'id': outcome['uri']})
        self.api._editor_done(True, ['Edited', '456', ''])
        self.assertEqual(self.api._book.get('5')['name'], 'Edited')
        self.request('create', {})
        self.api._cancel()
        self.assertEqual(len(self.api._book.rows), 5)
        self.assertEqual(json.loads(self.events[-1][1])['result_code'], 'cancelled')

    def test_invalid_arguments(self):
        for kwargs in ({'limit': 0}, {'limit': True}, {'offset': -1}, {'query': None}):
            with self.assertRaises(ValueError): self.api.list(**kwargs)
        with self.assertRaises(ValueError): self.api.pick('all')

    def test_busy_and_cancel(self):
        screen = object(); ui = SimpleNamespace(_screen_lifecycles={})
        with patch.object(preview, '_window', return_value=(ui, SimpleNamespace(_active_screen=screen))):
            self.api.pick(on_result=self.cb)
            self.api.pick(on_result=self.cb)
            self.assertEqual(self.events[-1], (False, 'busy'))
            self.api._cancel()
            self.assertEqual(self.events[-1], (False, 'cancelled'))

class APositionalCallbackReachesTheBuild(unittest.TestCase):
    """`contacts.pick("phone", picked)` ran here and stopped the build.

    The library's own signature is ``pick(kind="phone", on_result=None)``, so
    both arguments are reachable by position, and nfc, camera and flashlight
    already accept a callback that way. Only the compiler's contacts table
    listed the option names and left the callback out, so it allowed one
    argument fewer than the signature promised -- silently in the Previewer,
    loudly at build time.
    """

    def _app(self, call):
        return APP.replace('contacts.pick(on_result=result)', call)

    def test_the_call_from_the_report(self):
        files = generate(self._app('contacts.pick("phone", result)'))
        self.assertIn('pythonCallback_result(boolean ok, String value)',
                      files['java/Screen_homeActivity.java'])

    def test_an_id_and_a_callback_by_position(self):
        files = generate(self._app('contacts.get("1", result)'))
        self.assertIn('pythonCallback_result(boolean ok, String value)',
                      files['java/Screen_homeActivity.java'])

    def test_a_verb_whose_only_argument_is_the_callback(self):
        files = generate(self._app('contacts.settings(result)'))
        self.assertIn('pythonCallback_result(boolean ok, String value)',
                      files['java/Screen_homeActivity.java'])

    def test_every_option_and_the_callback_by_position(self):
        files = generate(self._app('contacts.list("ana", 10, 0, result)'))
        self.assertIn('pythonCallback_result(boolean ok, String value)',
                      files['java/Screen_homeActivity.java'])

    def test_by_name_still_works(self):
        files = generate(self._app('contacts.pick(kind="email", on_result=result)'))
        self.assertIn('pythonCallback_result(boolean ok, String value)',
                      files['java/Screen_homeActivity.java'])

    def test_the_same_callback_twice_is_refused(self):
        with self.assertRaises(AssertionError) as caught:
            generate(self._app('contacts.pick("phone", result, on_result=result)'))
        self.assertIn('U2033', str(caught.exception))

    def test_one_argument_too_many_says_how_many_there_are(self):
        with self.assertRaises(AssertionError) as caught:
            generate(self._app('contacts.pick("phone", result, "extra")'))
        message = str(caught.exception)
        self.assertIn('U2033', message)
        self.assertIn('at most 2', message)
        self.assertIn('on_result', message)


class TheTwoSidesTakeTheSameArguments(unittest.TestCase):
    """The guard, rather than one more example.

    This is how the bug happened: a verb's options live in two places, and
    only one of them counted the callback. Comparing the arities directly
    means the next option added to a verb is caught here instead of on
    somebody's build.
    """

    def test_every_verb_accepts_as_many_arguments_on_both_sides(self):
        import inspect
        wrong = []
        for verb in codegen.VERBS:
            # Lido do compilador, nao recalculado aqui: senao o teste
            # concordava consigo proprio mesmo depois de alguem partir isto.
            compiler_slots = len(codegen.positional_slots(verb))
            signature = inspect.signature(getattr(preview.ContactsAPI, verb))
            previewer_slots = len(
                [p for p in signature.parameters if p != 'self'])
            if compiler_slots != previewer_slots:
                wrong.append(
                    'contacts.%s: Previewer aceita %d posicionais %s, '
                    'compilador aceita %d'
                    % (verb, previewer_slots,
                       tuple(p for p in signature.parameters if p != 'self'),
                       compiler_slots))
        self.assertEqual([], wrong, '\n' + '\n'.join(wrong))

    def test_the_callback_is_the_last_parameter_on_the_previewer_side(self):
        """The compiler puts on_result last, so the signature has to as well."""
        import inspect
        wrong = []
        for verb in codegen.VERBS:
            names = [p for p in inspect.signature(
                getattr(preview.ContactsAPI, verb)).parameters if p != 'self']
            if names[-1] != 'on_result':
                wrong.append('contacts.%s termina em %r, nao em on_result'
                             % (verb, names[-1]))
        self.assertEqual([], wrong, '\n' + '\n'.join(wrong))

class DenyingOnceDoesNotDenyForEver(unittest.TestCase):
    """The simulator used to close the door on the first Deny.

    Android reopens it: a plain deny leaves
    ``shouldShowRequestPermissionRationale`` true and the next request shows
    the dialog again -- only "do not ask again" is final, which is what the
    generated Java checks. Until this was fixed, the recovery path could not
    be tried in the Previewer at all, and it is the path that breaks most
    often in real apps.
    """

    def setUp(self):
        self.api = preview.ContactsAPI()
        self.events = []
        self.panels = []
        self.api._show = lambda mode: self.panels.append(mode)

    def ask(self):
        self.api._pending = ('list', {'query': '', 'limit': 50, 'offset': 0},
                             lambda ok, value: self.events.append((ok, value)),
                             object())
        self.api._run()

    def test_a_plain_deny_is_asked_again_next_time(self):
        self.ask()
        self.assertEqual(['permission'], self.panels)
        self.api._grant('denied')
        self.assertEqual((False, 'permission_denied'), self.events[-1])

        self.ask()
        self.assertEqual(['permission', 'permission'], self.panels,
                         'a segunda chamada tinha de voltar a perguntar')

    def test_refusing_for_good_is_final(self):
        self.ask()
        self.api._grant('blocked')
        self.assertEqual((False, 'permission_blocked'), self.events[-1])

        self.ask()
        self.assertEqual(['permission'], self.panels,
                         'depois do bloqueio definitivo nao se pergunta mais')
        self.assertEqual((False, 'permission_blocked'), self.events[-1])

    def test_a_deny_does_not_reopen_the_panel_on_the_spot(self):
        """The trap in the fix: _grant calls _run, so letting "denied" open
        the panel again would put one panel after another for ever."""
        self.ask()
        self.api._grant('denied')
        self.assertEqual(['permission'], self.panels)

    def test_allowing_goes_on_with_the_operation(self):
        self.ask()
        self.api._grant('granted')
        self.assertTrue(self.events, 'a operacao tinha de seguir em frente')
        self.assertTrue(self.events[-1][0])


if __name__ == '__main__': unittest.main()
