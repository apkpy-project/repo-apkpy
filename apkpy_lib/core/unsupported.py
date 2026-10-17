# -*- coding: utf-8 -*-
"""What ApkPy cannot translate yet -- said out loud instead of left blank.

ApkPy reads your module and writes Java. Anything it did not recognise fell out
of ``_val_to_java`` as the empty string, so ``math.sqrt(x)`` compiled cleanly,
installed cleanly, ran cleanly, and showed nothing. The app was not broken in
any way a build could report: it was missing a value nobody asked about. That
is the worst shape a failure can take, and it is the reason this module exists.

Two families, and the difference matters to whoever reads the message:

``PLANNED``
    Python that Java could do perfectly well and ApkPy has simply not mapped
    yet. ``math.floor`` is ``Math.floor``. Saying "not yet" here is honest.

``NO_RUNTIME``
    Python that cannot work on a phone at all, because **there is no Python on
    the phone**. ``requests`` is not slow to add, it is not addable: it would
    need an interpreter, a socket stack and a package manager inside the APK.
    Someone hitting this needs redirecting to the ApkPy API that does the job
    (``https``, ``files``, ``db``), not a promise.

Every replacement named here was checked against the real exported names, so a
suggestion can be copied straight into the file.
"""

import ast

DOCS = 'https://repo-apkpy.pages.dev/compatibility/'

# Exact call -> the line to write instead. Only entries whose replacement really
# exists in apkpy_lib, so no suggestion sends anyone to an API that is not there.
REPLACEMENTS = {
    'time.time': 'datetime.now()',
    'time.sleep': 'timer.after(seconds, function) -- the phone must not block',
    'datetime.datetime.now': 'datetime.now()',
    'datetime.date.today': 'datetime.date()',
    'uuid.uuid4': 'crypto.token(16)',
    'uuid.uuid1': 'crypto.token(16)',
    'secrets.token_hex': 'crypto.token(16)',
    'secrets.token_urlsafe': 'crypto.token(16)',
    'hashlib.sha256': 'crypto.hash(text)',
    'hashlib.md5': 'crypto.hash(text)',
    'json.loads': 'json_get(text, "key")',
    'requests.get': 'https.get(url, on_result=done)',
    'requests.post': 'https.post(url, json=body, on_result=done)',
    'urllib.request.urlopen': 'https.get(url, on_result=done)',
    'os.path.exists': 'files.exists(path)',
    # sqrt / pow / fabs used to live here with hand-written workarounds. They
    # are translated now, so a suggestion pointing away from them would send
    # somebody the long way round.
}

# A module whose cause is written out in full, because the standard opening
# ("X is not part of the vocabulary yet") would be wrong for it.
FULL_CAUSES = {
    're': (
        'ApkPy translates re.match, re.search, re.sub and re.findall with '
        'constant Unicode patterns and flags. Other re APIs and dynamic '
        'patterns are not supported yet; use the documented portable subset.'
    ),
    'math': (
        'Most of math is translated -- sqrt, floor, the trigonometry, pi -- '
        'but this name is not, and each one left out was left out for a '
        'reason. log2 because Java has no Math.log2 and log(x)/log(2) '
        'disagrees with Python on 8 of the first 60 powers of two; inf and '
        'nan because Python writes "inf" where Java writes "Infinity". A '
        'translation that is right most of the time is the thing this '
        'library refuses to ship.'
    ),
}

# Modules Java can already do; ApkPy has not wired them up yet.
PLANNED = {
    'math': '',   # a causa inteira está em FULL_CAUSES
    'json': 'ApkPy can read JSON with json_get(); writing it is not mapped yet.',
    'base64': 'Android has android.util.Base64, so this is a gap in ApkPy.',
    'statistics': 'Add it up in a loop for now -- for and += both translate.',
    'decimal': 'Not mapped yet. For money, keep whole cents in an integer.',
    'csv': 'Not mapped yet. split(",") on each line translates today.',
    'textwrap': 'Not mapped yet.',
    'string': 'Not mapped yet. The str methods upper, strip, split and replace do translate.',
    'collections': 'Not mapped yet. Plain lists and dicts translate.',
    'itertools': 'Not mapped yet. A for loop translates.',
    'functools': 'Not mapped yet.',
    'fractions': 'Not mapped yet.',
    'unicodedata': 'Not mapped yet.',
}

# No Python runs on the phone, so these can never be translated. Each one names
# the ApkPy API that covers the same ground.
NO_RUNTIME = {
    'requests': 'Use https.get() / https.post(), which reach the network the Android way.',
    'urllib': 'Use https.get() / https.post().',
    'http': 'Use https.get() / https.post().',
    'socket': 'Use https for requests, or websocket for a live connection.',
    'os': 'Use files for reading and writing, and storage for settings.',
    'sys': 'There is no interpreter to inspect on the phone.',
    'pathlib': 'Use files.',
    'shutil': 'Use files.',
    'glob': 'Use files.',
    'tempfile': 'Use files.',
    'subprocess': 'A phone app cannot start processes.',
    'threading': 'Use background_job for work that must outlive the screen.',
    'multiprocessing': 'Use background_job.',
    'asyncio': 'ApkPy is callback-based: pass on_result= instead of awaiting.',
    'sqlite3': 'Use db, which is the same SQLite through the Android API.',
    'pickle': 'Use storage, or JSON, which survives an app update.',
    'logging': 'Use toast() while developing.',
    'argparse': 'A phone app has no command line.',
    'tkinter': 'The Previewer is Tk; the phone is not. Use the ApkPy components.',
    'numpy': 'Not installable on a phone. Loops and arithmetic translate.',
    'pandas': 'Not installable on a phone. Use db for tabular data.',
    'scipy': 'Not installable on a phone.',
    'matplotlib': 'Not installable on a phone.',
    'PIL': 'Not installable on a phone. Use image() and gallery.',
    'Pillow': 'Not installable on a phone. Use image() and gallery.',
    'bs4': 'Not installable on a phone.',
    'lxml': 'Not installable on a phone.',
    'flask': 'This builds an app, not a server.',
    'django': 'This builds an app, not a server.',
    'selenium': 'Not installable on a phone.',
    'pygame': 'Not installable on a phone.',
    'openpyxl': 'Not installable on a phone.',
}

# Builtins with no translation. The value is a workaround that compiles today.
BUILTINS = {
    'any': 'a for loop with a flag',
    'all': 'a for loop with a flag',
    'zip': 'a for over range(len(items)) and index both lists',
    'enumerate': 'a for over range(len(items))',
    'map': 'a for loop',
    'filter': 'a for loop with an if',
    'reversed': 'a for over range() counting down',
    'set': 'a list, checking with in before appending',
    'tuple': 'a list',
    'open': 'files.read(name) / files.write(name, text)',
    'input': 'an input_field() and a button',
    'eval': 'not translatable, and not safe to add',
    'exec': 'not translatable, and not safe to add',
    'isinstance': 'not translatable: every value is text on the phone',
    'type': 'not translatable: every value is text on the phone',
    # print looks supported and is not: it compiles to a call to a method that
    # was never written, so the build stops on cannot-find-symbol far away.
    'print': 'toast(text), which you can see while the app runs',
}

# Statements ApkPy drops on purpose. Nothing is lost by ignoring them, so they
# must never reach the diagnostic -- every real app is full of them.
IGNORED_STATEMENTS = (
    ast.FunctionDef,      # a nested callback; collected by a separate pass
    ast.AsyncFunctionDef,
    ast.Pass,
    ast.Import,
    ast.ImportFrom,
    ast.Global,           # Java has no such concept and needs none
    ast.Nonlocal,
)


def dotted_name(node):
    """``math.sqrt`` for a call or an attribute, ``abs`` for a bare name."""
    if isinstance(node, ast.Call):
        return dotted_name(node.func)
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return '.'.join(reversed(parts))
    return ''


def describe(node):
    """The offending source, as close to what was written as possible."""
    unparse = getattr(ast, 'unparse', None)   # 3.9+; ApkPy supports 3.8
    if unparse is not None:
        try:
            return unparse(node)
        except Exception:
            pass
    name = dotted_name(node)
    if name:
        return name + '(...)' if isinstance(node, ast.Call) else name
    if isinstance(node, ast.Constant):
        return repr(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return ('-' if isinstance(node.op, ast.USub) else '+') + describe(node.operand)
    return type(node).__name__


def advice(name):
    """(cause, suggestions) for a dotted name.

    Returns an empty cause when the name means nothing to us, which is the
    common case for a typo or a helper that was never defined.
    """
    if not name:
        return '', []
    root = name.split('.')[0]
    exact = REPLACEMENTS.get(name)

    if root in NO_RUNTIME:
        cause = (
            'There is no Python interpreter on the phone. ApkPy translates '
            'your module into Java, so a package with no Java translation '
            'cannot come along -- however it was installed on your computer. '
            + NO_RUNTIME[root]
        )
        return cause, (['Write it as ' + exact + '.'] if exact else [])

    if root in FULL_CAUSES:
        return FULL_CAUSES[root], (['Write it as ' + exact + '.'] if exact else [])

    if root in PLANNED:
        cause = (
            'ApkPy translates a fixed vocabulary of Python into Java, and '
            + root + ' is not part of it yet. ' + PLANNED[root]
        )
        return cause, (['Write it as ' + exact + '.'] if exact else [])

    if '.' not in name and name in BUILTINS:
        return (
            'ApkPy translates a fixed vocabulary of Python into Java, and the '
            'builtin ' + name + ' is not part of it yet.',
            ['Write it as ' + BUILTINS[name] + '.'],
        )

    # A call with a line to write instead, from a module none of the tables
    # above names (time, uuid, hashlib, secrets): the line is still the
    # answer. Ten of the fifteen replacements were never said to anyone --
    # time.sleep() among them, which is the one a timer is for.
    return '', (['Write it as ' + exact + '.'] if exact else [])


def shape_advice(node):
    """(cause, suggestions) for constructs with no name to look up."""
    if isinstance(node, ast.Subscript) and isinstance(
            getattr(node, 'slice', None), ast.Slice):
        return (
            'Taking a slice is not translated yet. Every value is Java text on '
            'the phone, and ApkPy has no mapping from [a:b] onto substring().',
            ['Use the whole value.',
             'Split it with split() and take one piece.'],
        )
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                         ast.GeneratorExp)):
        return (
            'A comprehension is not translated in this position.',
            ['Build the list with a for loop and append().'],
        )
    if isinstance(node, ast.Lambda):
        return (
            'A lambda has no name, and ApkPy writes one Java method per named '
            'function.',
            ['Define it with def, and pass the name.'],
        )
    if isinstance(node, (ast.Compare, ast.BoolOp)):
        return (
            'A comparison is understood inside if and while, but not as a '
            'value on its own.',
            ['Assign the two outcomes with an if instead.'],
        )
    return '', []


# Method calls on a name ApkPy does not know as a modal, a sheet or a menu.
# The names are learnt from the top of the file before any function is read,
# so a function may open a sheet written below it; what is left is a name
# given its overlay somewhere ApkPy does not look.
CALL_ATTR_ADVICE = {
    'open': (
        'ApkPy opens a modal, sheet or menu it was given at the top of the '
        'file: name = modal(...) on a line of its own, outside any function.',
        ['Create the modal(), bottom_sheet() or popup_menu() at the top level '
         'of the file and keep its name.'],
    ),
    'close': (
        'ApkPy closes a modal or sheet it was given at the top of the file: '
        'name = bottom_sheet(...) on a line of its own, outside any function.',
        ['Create the modal(), bottom_sheet() or popup_menu() at the top level '
         'of the file and keep its name.'],
    ),
}

# Statements with no translation. The value is (cause, suggestions).
STATEMENT_ADVICE = {
    'With': (
        'with needs a context manager, which has no Java equivalent here.',
        ['Use files.read(name) and files.write(name, text).'],
    ),
    'Raise': (
        'raise has no translation: there is no Python exception machinery on '
        'the phone.',
        ['Return early instead, or show the problem with toast().'],
    ),
    'Assert': (
        'assert is a development check, and it is not translated.',
        ['Use an if, and show the problem with toast().'],
    ),
    'ClassDef': (
        'ApkPy writes one Java class per screen, so a Python class inside your '
        'module has nowhere to go.',
        ['Use functions, and keep values in storage or state().'],
    ),
    'Delete': (
        'del is not translated.',
        ['Assign "" instead, or use storage.remove(key).'],
    ),
    'AnnAssign': (
        'A type annotation on an assignment is not read yet, and the whole '
        'line is dropped with it.',
        ['Write it without the annotation: name = value.'],
    ),
    'Match': (
        'match is not translated yet.',
        ['Use if and elif.'],
    ),
    'While': (
        'This while condition is not one of the shapes ApkPy translates.',
        ['Compare two values, or use a for over range().'],
    ),
    'Try': (
        'This try is not one of the shapes ApkPy translates.',
        ['Use one except, with or without a type, and an optional finally.'],
    ),
}


def raise_unsupported(node, cause='', suggestions=(), received=''):
    """Stop the build naming the construct, instead of writing "" and going on."""
    from ..diagnostics import ApkpyError   # the layer above this one

    source = received or describe(node)
    name = dotted_name(node)
    if not cause:
        cause, extra = advice(name)
        suggestions = list(suggestions) + list(extra)
    # `from math import sqrt` then `sqrt(16)`: the name is right there in the
    # import, so "no function called sqrt" would be true and useless.
    if not cause and isinstance(node, ast.Call) \
            and isinstance(node.func, ast.Name) and _is_math_name(node.func.id):
        cause = (
            'ApkPy reads math through its module name, so it recognises '
            'math.' + node.func.id + '(...) but not ' + node.func.id
            + '(...) on its own.'
        )
        suggestions = list(suggestions) + [
            'Write it as math.' + node.func.id + '(...), with import math above.']

    if not cause and isinstance(node, ast.Call) \
            and isinstance(node.func, ast.Attribute):
        known = CALL_ATTR_ADVICE.get(node.func.attr)
        if known:
            cause, extra = known
            suggestions = list(suggestions) + list(extra)
    if not cause:
        cause, extra = shape_advice(node)
        suggestions = list(suggestions) + list(extra)
    if not cause:
        cause = (
            'ApkPy reads your module and writes Java, and it translates a '
            'fixed vocabulary of Python rather than running it. This is '
            'outside that vocabulary, so there is nothing it could write.'
        )

    tips = list(suggestions)
    tips.append('The full list of translated Python is on the '
               'Compatibility and limits page.')

    raise ApkpyError(
        'ApkPy cannot translate %s into Java.' % source,
        code='U2033',
        title='This Python has no translation yet',
        cause=cause,
        expected='Python that ApkPy knows how to translate',
        received=source,
        suggestions=tips,
        docs=DOCS,
        line=getattr(node, 'lineno', 0),
        # A node spliced in from a helper module carries the file it came
        # from, so the line number points at the right file.
        path=getattr(node, '_apkpy_file', ''),
    )


# Expression shapes that unambiguously asked for something. Anything else that
# reaches the end of _val_to_java keeps the old empty string: this list grows
# on evidence, not on guesses, because a false positive here refuses to build
# an app that works today.
_LOUD_VALUES = (
    ast.Call, ast.Attribute, ast.Lambda, ast.ListComp, ast.SetComp,
    ast.DictComp, ast.GeneratorExp, ast.Compare, ast.BoolOp,
    # not x as a value: "" on the phone, True or False in the Previewer.
    ast.UnaryOp,
)

# Attribute calls that belong to the *other* generated runtime. A background job
# has its body written twice -- once into the Activity, once into the Worker --
# from one parsed tree, so each copy of _val_to_java is handed calls addressed
# to the other one. ``job.input("k")`` resolves in the Worker and is empty in
# the Activity, and that empty is correct rather than a translation we missed.
OTHER_RUNTIME_ATTRS = frozenset({'input', 'attempt'})


def reaches_other_runtime(node):
    """True when the node calls into the other generated runtime.

    Its empty value in this copy is the right answer, not a translation that
    failed, so a guard against empty comparison sides must not refuse it.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr in OTHER_RUNTIME_ATTRS:
            return True
    return False


def check_value(node):
    """Called where _val_to_java used to give up. Raises, or returns None."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in OTHER_RUNTIME_ATTRS:
        return
    if isinstance(node, _LOUD_VALUES):
        raise_unsupported(node)
    if isinstance(node, ast.Subscript) and isinstance(
            getattr(node, 'slice', None), ast.Slice):
        raise_unsupported(node)


def raise_unknown_function(name, lineno=0, known=()):
    """A call to a name that will have no Java method behind it.

    ``print("x")`` generated ``pythonCallback_print(...)`` and the build stopped
    on cannot-find-symbol inside a file nobody wrote, pointing at a line number
    in generated Java. So did every mistyped helper. Both are the same mistake
    and both deserve to be named here.
    """
    from ..diagnostics import ApkpyError

    cause, tips = advice(name)
    if not cause and _is_math_name(name):
        # `from math import sqrt` then `sqrt(16)`. Saying "no function called
        # sqrt" would be true and useless: it is right there in the import.
        cause = (
            'ApkPy reads math through its module name, so it recognises '
            'math.' + name + '(...) but not ' + name + '(...) on its own.'
        )
        tips = ['Write it as math.' + name + '(...), with import math above.']
    if not cause:
        cause = (
            'ApkPy writes one Java method per function you define, and there '
            'is no function called ' + name + ' in your module. The call was '
            'written anyway, and the build stopped on a name that does not '
            'exist in a file you never wrote.'
        )
        near = _did_you_mean(name, known)
        tips = (['Did you mean ' + near + '?'] if near else []) + [
            'Define it with def above the call, or remove the call.']

    raise ApkpyError(
        'ApkPy cannot translate %s() into Java.' % name,
        code='U2033',
        title='This Python has no translation yet',
        cause=cause,
        expected='a function defined in your module, or a translated builtin',
        received=name + '(...)',
        suggestions=tips,
        docs=DOCS,
        line=lineno or 0,
    )


def _is_math_name(name):
    """A math function ApkPy translates, asked for without its module name.

    The tables live in the compiler and are imported here on use: the compiler
    imports this module at load time, so the other direction has to be lazy.
    """
    try:
        from .compiler import (_MATH_CALLS, _MATH_CONSTANTS, _MATH_INT_CALLS)
    except Exception:
        return False
    return name in _MATH_CALLS or name in _MATH_INT_CALLS or name in _MATH_CONSTANTS


def _did_you_mean(name, candidates):
    """The closest defined name, when it is close enough to be worth saying."""
    import difflib
    matches = difflib.get_close_matches(name, [c for c in candidates], 1, 0.7)
    return matches[0] if matches else None


def check_statement(stmt):
    """Called where _parse_statements used to drop a line. Raises, or returns."""
    if isinstance(stmt, IGNORED_STATEMENTS):
        return
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return   # a docstring
    known = STATEMENT_ADVICE.get(type(stmt).__name__)
    if known:
        raise_unsupported(stmt, cause=known[0], suggestions=known[1],
                          received=_statement_source(stmt))
    raise_unsupported(stmt, received=_statement_source(stmt))


def _statement_source(stmt):
    """The head of a statement -- a whole for loop in the message helps nobody."""
    text = describe(stmt).strip()
    first = text.splitlines()[0] if text else type(stmt).__name__
    return first if len(first) <= 70 else first[:67] + '...'


# An if, a ternary or a module-level if whose test ApkPy cannot write. Each
# used to be dropped: the branch left the app, or the value became "", and the
# build said nothing. The suggestions are all shapes that compile today.
CONDITION_CAUSE = (
    'This condition is not translated. The branch it guards would have been '
    'left out of the app -- or, inside a value, replaced by empty text -- '
    'without a word.'
)
CONDITION_SUGGESTIONS = (
    'Compare with ==, !=, <, >, <= or >=, or test membership with in and '
    'not in.',
    'Join the parts with and, or and not -- one comparison each, not a chain '
    'like 0 < x < 10.',
    'Work the value out on its own line first, then test the name.',
)


def raise_untranslated_condition(node):
    """Stop the build naming a condition, instead of dropping what it guards."""
    raise_unsupported(node, cause=CONDITION_CAUSE,
                      suggestions=list(CONDITION_SUGGESTIONS),
                      received=describe(node))


def raise_untranslated_format(node, spec):
    """An f-string format the phone would have ignored.

    The Previewer runs the real f-string, so {n:03d} read 007 on the desktop and
    7 on the phone. Two screens disagreeing with no word said is the failure
    this module exists to end.
    """
    raise_unsupported(
        node,
        cause=('The format %r is not translated. On the phone the value would '
               'have appeared unformatted, while the Previewer formatted it.'
               % (spec,)),
        suggestions=[
            'Use {value:.2f} for a fixed number of decimals -- that format is '
            'translated.',
            'For anything else, build the text before the f-string. Leading '
            'zeros, for example: if n < 10: text = "00" + str(n)',
        ],
        received=describe(node),
    )


def raise_module_comprehension(node):
    """A comprehension assigned at module level, which used to become []."""
    raise_unsupported(
        node,
        cause=('A comprehension at module level is not translated. On the phone '
               'the list would have been created empty, with no word said.'),
        suggestions=[
            'Fill the list in a function that runs when the screen opens -- '
            'lifecycle(home, on_mount=load) -- with a for loop and append(), '
            'then show it with set_items().',
        ],
        received=describe(node),
    )


def raise_untranslated_arithmetic(node):
    """Arithmetic ApkPy could not write, which used to become empty text.

    "n=%s" % n, and price * 2 on text read from an input, both reached the end
    of the arithmetic branch and came back as "". The Previewer ran the real
    Python; the phone showed nothing, and the build said nothing.
    """
    def is_text(side):
        return isinstance(side, ast.JoinedStr) or (
            isinstance(side, ast.Constant) and isinstance(side.value, str))

    if isinstance(node.op, ast.Mod) and is_text(node.left):
        raise_unsupported(
            node,
            cause=('Formatting text with % is not translated. On the phone the '
                   'whole text would have been empty, while the Previewer '
                   'formatted it.'),
            suggestions=[
                'Use an f-string: f"n={n}". {value} and {value:.2f} are '
                'translated.',
            ],
            received=describe(node),
        )
    if isinstance(node.op, ast.Mult) and (
            is_text(node.left) or is_text(node.right)
            or isinstance(node.left, ast.List) or isinstance(node.right, ast.List)):
        raise_unsupported(
            node,
            cause=('Repeating text or a list with * is not translated. On the '
                   'phone the result would have been empty.'),
            suggestions=[
                'Write the repeated text out in full, or build it up in a for '
                'loop over range().',
            ],
            received=describe(node),
        )
    raise_unsupported(
        node,
        cause=('ApkPy could not tell that the values in this arithmetic are '
               'numbers, so it had nothing to write. On the phone the result '
               'would have been empty text, while the Previewer worked it out.'),
        suggestions=[
            'Say which kind of number it is: int(value) % 2, or '
            'float(price) * 2. Text from an input or from storage stays text '
            'until you do.',
            'A range() loop index, and a name assigned from int() or float(), '
            'are already known to be numbers.',
        ],
        received=describe(node),
    )


def raise_untranslated_assignment(stmt):
    """An assignment ApkPy could not write.

    It used to leave the app, line and all. When the name was read later the
    build stopped on a Java symbol nobody wrote; when it was not, nobody knew.
    """
    targets = getattr(stmt, 'targets', [])
    target = targets[0] if len(targets) == 1 else None
    value = getattr(stmt, 'value', None)
    if len(targets) > 1:
        cause = ('Assigning one value to several names in one line is not '
                 'translated.')
        tips = ['Assign each name on its own line: a = 0, then b = 0.']
    elif isinstance(target, (ast.Tuple, ast.List)):
        cause = ('Unpacking into several names is not translated. The line '
                 'would have been left out of the app, and every name in it '
                 'undeclared.')
        tips = ['Keep the list and read each item by position: '
                'parts = text.split(","), then a = parts[0] and b = parts[1].']
    elif isinstance(target, ast.Subscript):
        cause = ('Changing one item of a list or dict in place is not '
                 'translated. The line would have been left out of the app, '
                 'and the old value kept without a word.')
        tips = ['Build the dict again with the new value: '
                'row = {"title": title, "meta": meta}.',
                'For a list, build a new one with a for loop and append().']
    elif isinstance(target, ast.Attribute):
        cause = ('Setting an attribute is not translated. The line would have '
                 'been left out of the app.')
        tips = ['Change a component through its methods, such as '
                'status.set_value("Saved").']
    elif isinstance(value, (ast.ListComp, ast.SetComp, ast.DictComp,
                            ast.GeneratorExp)):
        cause = ('A comprehension assigned to a name is not translated. The '
                 'line would have been left out of the app, and the name '
                 'undeclared.')
        tips = ['Build the list with a for loop: result = [], then '
                'result.append(item) inside the loop.']
    elif isinstance(value, (ast.BoolOp, ast.Compare, ast.UnaryOp)):
        cause = ('A condition used as a value is not translated. The line '
                 'would have been left out of the app, and the name '
                 'undeclared.')
        tips = ['Choose the value with a conditional expression, which is '
                'translated: shown = query if query else "none".',
                'Or with an if and an else, one assignment in each.']
    elif isinstance(value, (ast.Tuple, ast.Set)):
        cause = ('A tuple or a set is not translated as a value. The line '
                 'would have been left out of the app.')
        tips = ['Use a list instead: sizes = [1, 2].']
    else:
        cause = ('This value is not translated when it is assigned to a name. '
                 'The line would have been left out of the app, and the name '
                 'undeclared.')
        tips = ['Work the value out in steps, one translated expression per '
                'line.']
    raise_unsupported(stmt, cause=cause, suggestions=tips,
                      received=_statement_source(stmt))


def raise_untranslated_loop(stmt):
    """A for loop ApkPy would have left out, or run over nothing."""
    iterable = stmt.iter
    if not isinstance(stmt.target, ast.Name):
        cause = ('Unpacking in a for loop is not translated. The whole loop '
                 'would have been left out of the app without a word.')
        tips = ['Loop over the items and read each part by position: '
                'for pair in pairs:, then name = pair[0].',
                'For a position, loop over range(len(items)) and read '
                'items[i].']
    elif stmt.orelse:
        cause = ('A for loop with an else block is not translated. The loop '
                 'would have been left out of the app, else and all.')
        tips = ['Keep a flag: found = "no" before the loop, found = "yes" '
                'inside it, then test found after it.']
    elif isinstance(iterable, ast.Dict):
        cause = ('Looping over a dict is not translated. On the phone the loop '
                 'would have run no times, while the Previewer ran it.')
        tips = ['Keep the keys in a list and loop over that list.']
    elif isinstance(iterable, ast.Set):
        cause = ('Looping over a set is not translated. On the phone the loop '
                 'would have run no times, while the Previewer ran it.')
        tips = ['Use a list instead: for size in [1, 2]:']
    else:
        cause = ('Looping over the letters of a text is not translated. On the '
                 'phone the loop would have run no times, while the Previewer '
                 'ran it.')
        tips = ['Loop over positions and slice: for i in range(len(text)):, '
                'then letter = text[i:i + 1].']
    raise_unsupported(stmt, cause=cause, suggestions=tips,
                      received=_statement_source(stmt))
