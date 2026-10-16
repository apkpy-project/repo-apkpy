# -*- coding: utf-8 -*-
"""Languages: one table of words, two runtimes reading it.

Text used to be written straight into the layout, so an app spoke exactly one
language and changing it meant editing every screen. This module is the shared
half of the fix -- the Previewer and the Android generator both read the rules
from here, which is what stops the two from disagreeing about which language is
in force or what a missing word falls back to.

**How a word reaches the phone.** The generator does not run your module, so
``t("save")`` reaches it as syntax rather than as a value. Where a component's
text is read (``_kw`` and ``_first_arg``) the call is replaced by a *mark* --
a single character from the Unicode private use area followed by the key. The
mark survives every string operation and every XML escape untouched, and one
pass over the finished layout turns ``android:text="<mark>save"`` into
``android:text="@string/apkpy_save"``. One substitution instead of forty call
sites, and a mark left over anywhere afterwards means somebody used ``t()``
where a resource reference cannot go -- which is then said out loud rather than
shipped.

**Falling back.** Android answers a missing translation from ``res/values/``,
the default language. The Previewer does the same, from the same table, so a
half-translated app looks the same on both.
"""

import re

# U+E000 is the first private use character: it has no meaning of its own, no
# font draws it by accident, and no real interface text contains one.
MARK = ''

# An Android resource name: letters, digits and underscore, never leading with
# a digit. Anything else would not compile into R.string.
KEY_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

# Language tags this understands: "pt", "en", "pt-BR". Anything richer (script
# subtags such as "zh-Hans") needs Android's b+ form and is refused rather than
# quietly written into a folder that no device will ever match.
TAG_PATTERN = re.compile(r'^([A-Za-z]{2,3})(?:[-_]([A-Za-z]{2}))?$')

RESOURCE_PREFIX = 'apkpy_'

DOCS = 'https://repo-apkpy.pages.dev/themes-styling/'

_MARKED = re.compile(MARK + r'([A-Za-z_][A-Za-z0-9_]*)')
_MARKED_ATTRIBUTE = re.compile(r'="' + MARK + r'([A-Za-z_][A-Za-z0-9_]*)"')


def mark(key):
    """The stand-in the generator carries around until the layout is written."""
    return MARK + key


def is_marked(text):
    return isinstance(text, str) and MARK in text


def key_of(text):
    """The key inside a mark, or '' -- used to report a misplaced t()."""
    found = _MARKED.search(text or '')
    return found.group(1) if found else ''


def normalise_tag(tag):
    """``pt-BR`` -> ``('pt', 'BR')``, ``pt`` -> ``('pt', '')``; None if unusable."""
    found = TAG_PATTERN.match(str(tag or '').strip())
    if not found:
        return None
    language, region = found.group(1), found.group(2)
    return (language.lower(), (region or '').upper())


def resource_dir(tag):
    """The res/ folder Android matches this tag from.

    ``pt`` -> ``values-pt``; ``pt-BR`` -> ``values-pt-rBR``. The ``r`` is not
    decoration: without it the folder never matches and the translation is
    silently ignored on every device.
    """
    parts = normalise_tag(tag)
    if parts is None:
        return None
    language, region = parts
    return 'values-%s-r%s' % (language, region) if region else 'values-%s' % language


def canonical(tag):
    """``pt_br`` -> ``pt-BR``, so one spelling reaches both runtimes."""
    parts = normalise_tag(tag)
    if parts is None:
        return None
    language, region = parts
    return '%s-%s' % (language, region) if region else language


def resource_name(key):
    return RESOURCE_PREFIX + key


def apply_to_xml(xml):
    """Turn whole marked attribute values into resource references.

    Anchored on the quotes on purpose: a mark in the middle of a longer value
    cannot become ``@string/...`` -- Android would draw the reference as text.
    Those are left in place for :func:`stray_key` to report.
    """
    return _MARKED_ATTRIBUTE.sub(
        lambda found: '="@string/%s"' % resource_name(found.group(1)), xml)


def stray_key(xml):
    """A key that survived :func:`apply_to_xml`, meaning t() was misplaced."""
    return key_of(xml)


def match_language(wanted, available, default):
    """Which declared language answers, with Android's own falling back.

    Android tries the full tag, then the language alone, then ``values/``.
    Doing the same here is the whole reason a half-translated app looks the
    same in the Previewer as it does on a phone.
    """
    parts = normalise_tag(wanted)
    if parts is not None:
        language, region = parts
        exact = '%s-%s' % (language, region) if region else language
        if exact in available:
            return exact
        if language in available:
            return language
        for tag in available:
            if str(tag).split('-')[0] == language:
                return tag
    return default


def strings_xml(entries):
    """One res/values*/strings.xml.

    Apostrophes and quotes are escaped with a backslash because Android's own
    string parser reads them, and an unescaped apostrophe is a build error in
    every language that has one -- which is most of them.
    """
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<resources>']
    for key in sorted(entries):
        lines.append('    <string name="%s">%s</string>'
                     % (resource_name(key), escape(entries[key])))
    lines.append('</resources>')
    return '\n'.join(lines) + '\n'


def escape(text):
    """Escape for an Android string resource."""
    out = str(text)
    # Backslash first, or every escape added below gets doubled by this line.
    out = out.replace('\\', '\\\\')
    out = out.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    out = out.replace("'", "\\'").replace('"', '\\"')
    return out
