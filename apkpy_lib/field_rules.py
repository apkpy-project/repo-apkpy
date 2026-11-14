"""Form fields: the words under a field and what `required` checks.

A text field with ``help=``, ``error=`` or ``required=`` gets a line of
supporting text under it. It is drawn twice -- by the Previewer and by
ApkpyField on the phone -- so what that line says, when a field counts as
empty and how wide the error outline is are decided here, and ApkpyField
mirrors ``supporting`` and ``check`` one for one.

Sizes are Material 3's (body-small under the field, 4 above it), in dp on the
phone and px in the Previewer, which is the same number.

The keyboard of a field is decided here too: ``type="email"|"phone"|"url"``,
``action=`` (the key in the keyboard's corner), ``on_submit=`` (what it does)
and ``autofill=`` -- read by features/keyboard.py in the Previewer and by
core/features/keyboard.py for the phone.
"""

CODE = "U2044"
DOCS = "https://repo-apkpy.pages.dev/ui-components/#fields-with-help-and-errors"

# Text fields with a keyboard of their own. Everywhere else they are a "text"
# field (base_type): what changes is the keyboard and what the phone's
# autofill knows about them.
KEYBOARD_TYPES = ('email', 'phone', 'url')

# The fields somebody types in. A switch, a slider or a date has no text to
# be wrong about.
TYPES = ('text', 'password', 'search', 'number', 'textarea') + KEYBOARD_TYPES

# Every kind of field inputs() makes, on both sides.
ALL_TYPES = TYPES + ('switch', 'checkbox', 'radio', 'select', 'range', 'date', 'time')

SUPPORT_SIZE = 12       # sp / px
# The text of a field you type in with no font-size: what an EditText draws in
# the app's theme (Widget.AppCompat.EditText, textAppearanceMediumInverse).
# The Previewer drew 13px; measured on the phone 14-11-2026: an "E" 13.5dp tall.
EDIT_TEXT_SIZE = 18     # sp / px
SUPPORT_GAP = 4         # between the field and the words under it
ERROR_STROKE = 1        # an outlined field in error is at least this wide
REQUIRED = "Required"   # what required=True says about an empty field

# Material 3's on-surface-variant and error, for an app with no Theme.
_HELP = '#49454F'
_ERROR = '#B3261E'


KEYBOARD_DOCS = "https://repo-apkpy.pages.dev/ui-components/#the-keyboard"


def refuse(message, received, line=0, suggestions=None, keyboard=False):
    from .diagnostics import ApkpyError
    if keyboard:
        cause = ("type= picks the keyboard, action= the key in its corner and "
                 "on_submit= what that key does, on a one-line field you type in.")
        expected = ('inputs("Email", type="email", autofill="email", action="next", '
                    'screen=login)')
    else:
        cause = ("help=, error= and required= put a line of text under a field "
                 "somebody types in, so they need words and a text field.")
        expected = ('inputs("Email", id="email", help="We never share it", '
                    'required=True, screen=signup)')
    raise ApkpyError(
        message,
        code=CODE,
        title="A form field ApkPy cannot build",
        cause=cause,
        expected=expected,
        received=received,
        suggestions=suggestions or [
            'required="Enter your email"  -- your own words for an empty field',
            'email.set_error("That is not an email address")  and  email.set_error("")',
            'if not validate(name, email): return',
        ],
        docs=KEYBOARD_DOCS if keyboard else DOCS,
        line=line,
    )


def words(value, name, line=0):
    """``help=`` or ``error=`` as text: nothing, or a string."""
    if value is None or value is False:
        return ''
    if isinstance(value, str):
        return value
    refuse('%s= of inputs() is text.' % name, '%s=%r' % (name, value), line)


def required_message(value, line=0):
    """What an empty field says: '' when it may stay empty, ``REQUIRED`` for
    ``required=True``, or the words given."""
    if value is None or value is False:
        return ''
    if value is True:
        return REQUIRED
    if isinstance(value, str) and value.strip():
        return value
    refuse('required= of inputs() is True or the words to show for an empty field.',
           'required=%r' % (value,), line,
           ['required=True', 'required="Enter your name"'])


def wanted(help_text, error_text, required):
    """Whether the field gets a line under it at all. A field with none of
    the three is exactly the field it always was."""
    return bool(help_text or error_text or required)


def check_type(input_type, line=0):
    if input_type not in TYPES:
        refuse('help=, error= and required= are for fields somebody types in; '
               'type="%s" is not one.' % input_type,
               'inputs(..., type="%s", help=/error=/required=)' % input_type, line,
               ['Use them on type="text", "password", "search", "number" or "textarea".',
                'Put a label() under a switch, a slider or a date instead.'])


def check_known(input_type, line=0):
    """A type inputs() does not make. The Previewer drew a text field for it
    and the phone left the field out of the screen, so the build stopped in
    javac on a field it could not find (06-11-2026, type="phone")."""
    if not isinstance(input_type, str) or input_type in ALL_TYPES:
        return
    import difflib
    from .diagnostics import ApkpyError
    close = difflib.get_close_matches(input_type, ALL_TYPES, n=1, cutoff=0.6)
    raise ApkpyError(
        'inputs() has no type="%s".' % input_type,
        code=CODE,
        title="A form field ApkPy cannot build",
        cause="Each type is a different field on the phone, and this one is "
              "none of them.",
        expected=", ".join('"%s"' % kind for kind in ALL_TYPES),
        received='type="%s"' % input_type,
        suggestions=(['Did you mean type="%s"?' % close[0]] if close else []) + [
            'A phone number, an email or an address has its own keyboard: '
            'type="phone", type="email", type="url"'],
        docs=DOCS,
        line=line,
    )


# -- The keyboard: which one, what its Enter key does, what autofill fills --

def base_type(input_type):
    """The field a type is everywhere but the keyboard: email, phone and url are text."""
    return 'text' if input_type in KEYBOARD_TYPES else input_type


# The one-line fields whose Enter key can do something. A textarea's Enter
# is a new line.
SUBMIT_TYPES = ('text', 'password', 'search', 'number') + KEYBOARD_TYPES

# action= -> android:imeOptions. What follows on_submit is Android's own:
# "next" moves to the next field, "done" closes the keyboard, "send" keeps it
# open (a chat goes on), and "search"/"go" close it too (Android leaves it
# open there, a search that keeps the keyboard over its results is in the way).
ACTIONS = {'send': 'actionSend', 'next': 'actionNext', 'done': 'actionDone',
           'search': 'actionSearch', 'go': 'actionGo'}
HIDES_KEYBOARD = ('done', 'search', 'go')

# autofill= -> android:autofillHints: the words password managers and the
# keyboard's one-time-code suggestion read.
AUTOFILL = {'email': 'emailAddress', 'username': 'username', 'password': 'password',
            'new_password': 'newPassword', 'otp': 'smsOTPCode', 'name': 'personName',
            'phone': 'phoneNumber', 'address': 'postalAddress', 'postal_code': 'postalCode'}

# type -> android:inputType for a one-line text field.
INPUT_TYPES = {'text': 'text', 'search': 'text', 'password': 'textPassword',
               'number': 'numberDecimal|numberSigned', 'email': 'textEmailAddress',
               'phone': 'phone', 'url': 'textUri'}

# What a phone keyboard types into a type="phone" field (Android's
# DialerKeyListener), so the Previewer takes the same.
PHONE_CHARS = frozenset('0123456789#*+-(),/N.; ')


def _pick(value, name, allowed, line, example):
    import difflib
    if value is None:
        return None
    if isinstance(value, str) and value in allowed:
        return value
    close = difflib.get_close_matches(str(value), list(allowed), n=1, cutoff=0.6)
    refuse('%s= of inputs() is one of: %s.' % (name, ', '.join('"%s"' % a for a in allowed)),
           '%s=%r' % (name, value), line,
           (['Did you mean %s="%s"?' % (name, close[0])] if close else []) + [example],
           keyboard=True)


def action_of(input_type, action, has_submit, line=0):
    """What the keyboard's corner key is (a key of ACTIONS), or None for
    Android's own: "next" while there is a field after this one, else "done"."""
    action = _pick(action, 'action', ACTIONS, line,
                   'inputs("Message", action="send", on_submit=send, screen=chat)')
    if (action or has_submit) and input_type not in SUBMIT_TYPES:
        refuse('on_submit= and action= are for a one-line field you type in; '
               'type="%s" is not one.' % input_type,
               'inputs(..., type="%s", on_submit=/action=)' % input_type, line,
               ['A textarea\'s Enter is a new line: put a send button() beside it.',
                'inputs("Message", type="text", action="send", on_submit=send)'],
               keyboard=True)
    if action is None and input_type == 'search':
        return 'search'
    if action is None and has_submit:
        return 'done'
    return action


def autofill_of(autofill, line=0):
    """The autofill hint (a key of AUTOFILL), or None."""
    return _pick(autofill, 'autofill', AUTOFILL, line,
                 'inputs("Email", type="email", autofill="email", screen=login)')


def check_autofill_type(input_type, autofill, line=0):
    """autofill= is for a field you type in: a switch has nothing to fill."""
    if autofill and input_type not in TYPES:
        refuse('autofill= is for a field you type in; type="%s" is not one.' % input_type,
               'inputs(..., type="%s", autofill="%s")' % (input_type, autofill), line,
               ['inputs("Email", type="email", autofill="email")'], keyboard=True)


def check_submit_arity(count, line=0, name='on_submit'):
    """on_submit= gets the field's text, or nothing: its function takes 0 or 1."""
    if count > 1:
        refuse('%s= of inputs() is called with the field\'s text, or with nothing; '
               'its function takes %d.' % (name, count),
               '%s with %d parameters' % (name, count), line,
               ['def send(text):  ...  then  inputs("Message", on_submit=send)',
                'inputs("Search", type="search", on_submit=lambda: run_search())'],
               keyboard=True)


def check_focus(input_type, line=0):
    """field.focus() puts the cursor in a field you type in and opens the keyboard."""
    if input_type not in TYPES:
        refuse('focus() is for a field you type in; type="%s" is not one.' % input_type,
               'field.focus() on type="%s"' % input_type, line,
               ['name = inputs("Name", screen=signup)  ...  name.focus()'], keyboard=True)


def supporting(help_text, error_text):
    """(words, is_error) for the line under the field. An error takes the
    place of the help while it lasts, as Material's text fields do."""
    if error_text:
        return error_text, True
    return help_text or '', False


def check(value, required):
    """The error an unfinished field shows, or '' when it is fine.
    ``required`` is the message from ``required_message``. Spaces alone do
    not fill a field."""
    if required and not str(value if value is not None else '').strip():
        return required
    return ''


def stroke(border_width):
    """How wide the outline of a field in error is."""
    try:
        width = int(border_width or 0)
    except (TypeError, ValueError):
        width = 0
    return max(ERROR_STROKE, width)


def colors(tokens):
    tokens = tokens or {}
    return {
        'help': tokens.get('text_secondary') or _HELP,
        'error': tokens.get('error') or _ERROR,
    }
