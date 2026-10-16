# -*- coding: utf-8 -*-
"""What a screen reader would announce, and what nobody can read.

Accessibility fails quietly. An unlabelled image is announced as nothing at
all; text at 3:1 against its background is invisible to a good share of people
and looks fine to everyone who signed it off. Neither shows up in a build, in
a test, or in a screenshot -- which is exactly the shape of problem this
project keeps finding and refusing to leave alone.

So this is a **report**, not a refusal. Every app in existence has an image
somebody forgot to describe, and stopping the build over it would only teach
people to turn the check off. It names what it found, says why it matters, and
lets the build finish.

The numbers are WCAG's, not opinions: 4.5:1 for body text, 3:1 for large text
(24sp, or 18.7sp bold -- see the constants below for why those and not 18/14),
and 48dp for anything you tap, which is Material's own minimum and roughly the
width of an adult fingertip.
"""

MIN_CONTRAST_BODY = 4.5
MIN_CONTRAST_LARGE = 3.0
# WCAG defines large text in POINTS -- 18pt, or 14pt bold -- and Android sizes
# text in sp. At the default density 1pt is 1.333sp, so the thresholds are 24sp
# and 18.7sp, not 18 and 14. Written as 18 and 14 they let 18sp body text pass
# at 3:1 when it actually needs 4.5:1, which is the sort of "nearly right" this
# whole check exists to catch.
LARGE_TEXT_SP = 24.0        # 18pt
LARGE_BOLD_SP = 18.66       # 14pt
MIN_TOUCH_DP = 48

CODE = 'U2035'
DOCS = 'https://repo-apkpy.pages.dev/ui-components/'


def _channel(value):
    """One sRGB channel, linearised the way WCAG defines it."""
    portion = value / 255.0
    if portion <= 0.03928:
        return portion / 12.92
    return ((portion + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    red, green, blue = rgb
    return (0.2126 * _channel(red)
            + 0.7152 * _channel(green)
            + 0.0722 * _channel(blue))


def parse_colour(value):
    """``#RGB`` / ``#RRGGBB`` / ``#AARRGGBB`` -> (r, g, b), or None.

    The alpha of an eight-digit colour is dropped rather than guessed at: what
    it ends up looking like depends on whatever is behind it, and inventing a
    blend would produce a confident number that means nothing.
    """
    text = str(value or '').strip().lstrip('#')
    if len(text) == 3:
        text = ''.join(c * 2 for c in text)
    if len(text) == 8:
        text = text[2:]
    if len(text) != 6:
        return None
    try:
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except ValueError:
        return None


def contrast_ratio(foreground, background):
    """WCAG contrast, 1.0 to 21.0. None when either colour is unreadable."""
    front = parse_colour(foreground)
    back = parse_colour(background)
    if front is None or back is None:
        return None
    lighter = max(relative_luminance(front), relative_luminance(back))
    darker = min(relative_luminance(front), relative_luminance(back))
    return (lighter + 0.05) / (darker + 0.05)


def required_contrast(size_sp, bold=False):
    """The ratio this text has to reach. Large text is allowed less."""
    try:
        size = float(size_sp)
    except (TypeError, ValueError):
        size = 16.0
    if size >= LARGE_TEXT_SP or (bold and size >= LARGE_BOLD_SP):
        return MIN_CONTRAST_LARGE
    return MIN_CONTRAST_BODY


def describes(component):
    """The description an author gave, or None when they gave none.

    An **empty** description is a decision, not an omission: it means the thing
    is decorative and a screen reader should skip it rather than announce a
    file name. The two are told apart here so the report never nags about a
    choice somebody already made.
    """
    if 'describe' not in component:
        return None
    return str(component.get('describe') or '')


def is_decorative(component):
    return describes(component) == ''


def needs_a_label(component):
    """Whether this component would be announced as nothing.

    Only for things with no text of their own. A button that says "Save" is
    already announced as "Save"; an icon is announced as whatever we write, and
    an image as nothing at all.
    """
    kind = component.get('comp_type')
    if describes(component) is not None:
        return False
    if kind == 'image':
        return True
    if kind in ('button', 'card_action'):
        return not str(component.get('text') or '').strip()
    return False


def touch_target_problem(style):
    """A tap target smaller than a fingertip, or None.

    Only an explicit size counts. A component that takes its height from
    padding usually lands above the minimum anyway, and guessing at the
    rendered size would produce warnings nobody can act on.
    """
    for name in ('height', 'width'):
        raw = str(style.get(name, '') or '').strip().lower()
        if not raw:
            continue
        digits = ''.join(c for c in raw if c.isdigit() or c == '.')
        if not digits:
            continue
        try:
            size = float(digits)
        except ValueError:
            continue
        if 0 < size < MIN_TOUCH_DP:
            return '%s is %gdp' % (name, size)
    return None


def report(findings):
    """Say what was found, once, and let the build carry on.

    Not a refusal: every app in existence has an image somebody forgot to
    describe, and stopping a build over it would only teach people to switch
    the check off. Naming it is what makes it fixable.
    """
    if not findings:
        return ''
    from ...diagnostics import Diagnostic, report_diagnostic

    # One row function can draw two lists (today's notifications and this
    # week's): its button is one thing to fix, not one per list.
    findings = list(dict.fromkeys(findings))
    lines = []
    for kind, where, detail in findings:
        lines.append('%s (%s): %s' % (where, kind, detail))

    return report_diagnostic(Diagnostic(
        code=CODE,
        title='Some of this app cannot be used by everyone',
        message='%d thing%s a screen reader or a low-vision user would '
                'struggle with.' % (len(findings), '' if len(findings) == 1 else 's'),
        cause=(
            'Accessibility fails quietly. An image with no description is '
            'announced as nothing at all, and text below the contrast minimum '
            'looks fine to whoever chose the colours. Neither shows up in a '
            'build, a test or a screenshot, so this is the only place it gets '
            'said. The app was written anyway.'
        ),
        expected='a description on anything without text, and %.1f:1 contrast '
                 'for body text' % MIN_CONTRAST_BODY,
        received='\n  '.join([''] + lines),
        suggestions=[
            'Add describe="..." to an image or an icon-only button.',
            'Use describe="" for decoration, so a screen reader skips it '
            'instead of reading a file name.',
            'Darken or lighten the text colour until it reaches the ratio.',
        ],
        docs=DOCS,
    ))
