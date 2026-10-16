"""Form fields: the words under a field and what `required` checks.

A text field with ``help=``, ``error=`` or ``required=`` gets a line of
supporting text under it. It is drawn twice -- by the Previewer and by
ApkpyField on the phone -- so what that line says, when a field counts as
empty and how wide the error outline is are decided here, and ApkpyField
mirrors ``supporting`` and ``check`` one for one.

Sizes are Material 3's (body-small under the field, 4 above it), in dp on the
phone and px in the Previewer, which is the same number.
"""

CODE = "U2044"
DOCS = "https://repo-apkpy.pages.dev/ui-components/#fields-with-help-and-errors"

# The fields somebody types in. A switch, a slider or a date has no text to
# be wrong about.
TYPES = ('text', 'password', 'search', 'number', 'textarea')

SUPPORT_SIZE = 12       # sp / px
SUPPORT_GAP = 4         # between the field and the words under it
ERROR_STROKE = 1        # an outlined field in error is at least this wide
REQUIRED = "Required"   # what required=True says about an empty field

# Material 3's on-surface-variant and error, for an app with no Theme.
_HELP = '#49454F'
_ERROR = '#B3261E'


def refuse(message, received, line=0, suggestions=None):
    from .diagnostics import ApkpyError
    raise ApkpyError(
        message,
        code=CODE,
        title="A form field ApkPy cannot build",
        cause=("help=, error= and required= put a line of text under a field "
               "somebody types in, so they need words and a text field."),
        expected=('inputs("Email", id="email", help="We never share it", '
                  'required=True, screen=signup)'),
        received=received,
        suggestions=suggestions or [
            'required="Enter your email"  -- your own words for an empty field',
            'email.set_error("That is not an email address")  and  email.set_error("")',
            'if not validate(name, email): return',
        ],
        docs=DOCS,
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
