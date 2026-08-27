# Themes and styling

## Global theme

~~~ python
from apkpy_lib import Theme

app_theme = Theme(
    mode="dark",
    primary="#8B5CF6",
    secondary="#22D3EE",
    background="#09090B",
    surface="#18181B",
    text="#FAFAFA",
    text_secondary="#A1A1AA",
    border="#3F3F46",
    error="#FCA5A5",
    success="#4ADE80",
    radius=16,
    spacing=14,
    font_family="sans-serif",
)
~~~

Pass the theme to <code>run()</code>:

~~~ python
run(start_screen=home, theme=app_theme)
~~~

The theme styles screens, text, buttons, inputs, containers, cards, lists, navigation, player surfaces and Android system bars.

## Design tokens

Reference normalized theme values from CSS:

~~~ css
body {
    background-color: var(--background);
    color: var(--text);
}

panel {
    background-color: var(--surface);
    border-color: var(--border);
    border-radius: var(--radius);
    padding: var(--spacing);
}

danger_action {
    background-color: var(--error);
}
~~~

Available tokens:

<code>primary</code>, <code>secondary</code>, <code>background</code>, <code>surface</code>, <code>text</code>, <code>text_secondary</code>, <code>on_primary</code>, <code>error</code>, <code>success</code>, <code>border</code>, <code>radius</code>, <code>spacing</code>, <code>motion</code>, <code>nav_indicator</code> and <code>font-family</code>.

A dash reads as an underscore, so <code>var(--text-secondary)</code> and
<code>var(--text_secondary)</code> are the same token.

### Tokens work without a theme

An app that never calls <code>run(theme=...)</code> still has a theme: the
generated <code>apkpy_theme.xml</code> is written from ApkPy's default
Material palette. <code>var(--primary)</code> reads that palette and
resolves to <code>#6750A4</code>, which is the same colour the built app
uses for a filled button.

~~~ python
from apkpy_lib import Screen, button, label, run

home = Screen(id="home")
label("Welcome", id="title", screen=home)
button("Continue", id="go", variant="filled", screen=home)
run(start_screen=home)          # no theme named

style = """
title { color: var(--primary); }
"""
~~~

Declaring a theme changes what the token resolves to, never whether it
resolves.

### Switching appearance while the app runs

```python
from apkpy_lib import appearance

appearance.set("light")     # "dark", "light" or "system"
appearance.get()            # what is in force
```

The choice is remembered, so the app opens the way it was left.

What makes this possible is that a colour which came from a token is not
written into the layout at all -- a reference to it is:

```xml
<!-- res/layout/activity_screen_chat.xml -->
<TextView android:textColor="@color/apkpy_text" ... />
```

```xml
<!-- res/values/apkpy_theme.xml -->
<color name="apkpy_text">#1D1B20</color>

<!-- res/values-night/apkpy_theme.xml -->
<color name="apkpy_text">#F5F4EF</color>
```

Android answers that reference from one table or the other depending on the
mode in force. Switching costs nothing at run time: the resource system does
the work while the layout inflates.

**A colour you wrote by hand is left exactly as you wrote it.**
`#C96442` in a stylesheet was a decision, not a default, and a decision that
changes on its own is a bug. Only tokens move.

#### Where the second palette comes from

You declare one appearance; ApkPy builds the other from the same `Theme`. The
accent carries over and the surfaces flip:

| Token | In the counterpart |
| --- | --- |
| `primary`, `secondary`, `on_primary`, `error`, `success` | kept |
| `background`, `surface`, `text`, `text_secondary`, `border` | from the opposite palette |

A background you chose at `#1B1B19` was chosen *because* the mode was dark.
Carrying it into light mode would give a light mode that is still dark -- a
switch that appears to do nothing.

An app that never calls `appearance.set(...)` is pinned to the mode it
declared, on a phone set either way, exactly as before.

### A name with no token behind it

<code>var(--muted)</code> is not a token, so it is reported as
<strong>U2028</strong> the moment the stylesheet is read -- by the
Previewer and by <code>apkpy build</code> alike, since both resolve
tokens through the same module:

~~~ text
APKPY U2028 - This stylesheet asks for a theme token that does not exist

Received:
  title { color: var(--muted); }

How to fix:
  1. Did you mean var(--text_secondary)?
  2. The tokens are: background, border, error, font-family, motion,
     nav_indicator, on_primary, primary, radius, secondary, spacing,
     success, surface, text, text_secondary.
~~~

A colour of your own goes in as itself -- <code>#C96442</code> -- rather
than through <code>var()</code>.

## Cascade

Styles resolve in this order:

~~~ text
Theme defaults → component selector → component ID
~~~

~~~ css
button {
    border-radius: 12px;
}

save_button {
    background-color: var(--secondary);
}
~~~

The ID rule changes the background of <code>save_button</code> without losing the shared button radius.

## The whole vocabulary

An ApkPy stylesheet is not a browser stylesheet. It reads **97 properties**,
and a name outside this table is reported as
[`U2029`](friendly-errors.md#u2001-components-and-arguments) and ignored:

| Area | Properties |
| --- | --- |
| Colour | <code>color</code>, <code>background-color</code>, <code>border-color</code>, <code>border-left-color</code>, <code>border-top-color</code>, <code>pressed-color</code>, <code>focus-color</code>, <code>focus-border-color</code>, <code>accent-color</code>, <code>active-color</code>, <code>hint-color</code>, <code>icon-color</code>, <code>placeholder-color</code>, <code>secondary-color</code>, <code>subtitle-color</code>, <code>title-color</code>, <code>trailing-color</code>, <code>meta-color</code>, <code>badge-color</code>, <code>badge-background-color</code>, <code>item-background-color</code>, <code>item-border-color</code>, <code>divider-color</code>, <code>indicator-color</code>, <code>tint</code> |
| Type | <code>font-size</code>, <code>font-weight</code>, <code>font-family</code>, <code>font-style</code>, <code>text-align</code>, <code>text-transform</code>, <code>letter-spacing</code>, <code>line-height</code>, <code>title-lines</code>, <code>subtitle-lines</code>, <code>subtitle-size</code>, <code>trailing-size</code>, <code>rows</code>, <code>max-rows</code> |
| Shape | <code>border-width</code>, <code>border-left-width</code>, <code>border-top-width</code>, <code>border-radius</code>, <code>box-shadow</code> |
| Space | <code>padding</code>, <code>padding-top</code>, <code>padding-right</code>, <code>padding-bottom</code>, <code>padding-left</code>, <code>margin</code>, <code>margin-top</code>, <code>margin-right</code>, <code>margin-bottom</code>, <code>margin-left</code>, <code>gap</code>, <code>divider-width</code>, <code>divider-inset</code> |
| Size | <code>width</code>, <code>height</code>, <code>min-width</code>, <code>min-height</code>, <code>max-width</code>, <code>max-height</code>, <code>aspect-ratio</code>, <code>icon-size</code>, <code>item-size</code> |
| Layout | <code>display</code>, <code>flex-direction</code>, <code>flex-grow</code>, <code>flex-shrink</code>, <code>flex-basis</code>, <code>flex-wrap</code>, <code>justify-content</code>, <code>align-items</code>, <code>align-self</code>, <code>align-content</code>, <code>grid-template-columns</code>, <code>grid-column</code>, <code>grid-row</code>, <code>position</code>, <code>top</code>, <code>right</code>, <code>bottom</code>, <code>left</code>, <code>z-index</code> |
| Effects | <code>opacity</code>, <code>object-fit</code>, <code>filter</code>, <code>scale</code> |
| Behaviour | <code>transition</code>, <code>press</code>, <code>code-copy</code>, <code>animation</code>, <code>animation-name</code>, <code>animation-duration</code>, <code>animation-delay</code>, <code>animation-iteration-count</code> |

It is a warning, not a failure -- the build carries on, the way it does for an
icon name the catalogue does not have. What it buys you is the difference
between "that value did not work" and "that name does not exist", which is the
difference between adjusting and guessing.

```css
card { elevation: 4px; }     /* U2029: did you mean box-shadow? */
card { background: #fff; }   /* U2029: did you mean background-color? */
```

### Depth

`box-shadow` is written to Android as `android:elevation`, and the first pixel
value in the declaration is the depth:

```css
card { box-shadow: 0 6px 16px #00000030; }   /* 6dp */
```

Android draws that shadow *outside* the view's own box, and a `ViewGroup`
clips its children to its padding. ApkPy stops the clipping on the parents of
anything that asks for a shadow, which is the other half of why `box-shadow`
used to look like it did nothing. Only a screen that asks for one is touched.

The Previewer approximates -- Tk has no blurred shadow, so it offsets two
rounded layers. What matches is the presence and the ordering, not the blur.

### Padding, all four ways

`padding` reads the way CSS reads: one value, two, three or four, and the long
names on top of them.

```css
card { padding: 16px; }              /* every side */
card { padding: 8px 16px; }          /* vertical, horizontal */
card { padding: 4px 8px 12px; }      /* top, horizontal, bottom */
card { padding: 0 20px 24px 20px; }  /* top, right, bottom, left */
card { padding: 10px; padding-bottom: 30px; }
```

## The ones worth a paragraph

### Button labels

Material shouts button labels, so ApkPy uppercases them -- `"Opus 5"` reaches
the screen as `OPUS 5`. `text-transform: none` opts out, which is what a chip,
a pill or a chat composer wants:

~~~ css
model_chip {
    text-transform: none;
    border-radius: 999px;
}
~~~

`uppercase` and `none` are the two values offered, because they are the two
Android can express as a display attribute (`android:textAllCaps`).
`capitalize` and `lowercase` would mean rewriting the label at build time and
would then not apply to text you set while the app runs -- so ApkPy reports
them as `U2021` instead of half-doing them. Write the label with the casing you
want and use `text-transform: none`.

### A settings row instead of a fat pill

A button centres its label, and three of them stacked read as three pills, not
as a list. `text-align: left` moves the label to the leading edge and brings
the icon with it -- on Android that is `android:gravity="start"` plus
`app:iconGravity="start"`, which is the difference between Material's
icon-and-label-in-the-middle and a settings row:

~~~ css
pref_model, pref_theme, pref_bell {
    background-color: var(--surface);
    text-align: left;
    text-transform: none;
    letter-spacing: 0px;
    padding: 0px 18px;
    min-height: 52px;
    border-radius: 16px;
    width: 100%;
}
~~~

`left`, `center` and `right` are the three values, and they are written to
Android as `start` / `center` / `end` so a right-to-left locale mirrors the row
without the app asking. `justify` is reported as `U2022` rather than half-done:
it needs `android:justificationMode`, which arrived at API 26 while ApkPy
targets 24, so it would be an effect only newer phones ever showed.

Alignment needs room to move something. A label in a `display: flex` row is
sized to its own content -- the same as a shrink-to-fit box in CSS -- so give
it `width: 100%` if you want the alignment to bite.

`text-align: center` on the app bar centres its title, the way a settings
screen or a chat header usually wants it:

~~~ css
app_bar { text-align: center; font-family: "Tiempos"; }
~~~

Android centres it in the whole toolbar rather than in what the leading icon
and the actions leave over, and the Previewer copies that -- otherwise the
title drifted left as soon as an action appeared.

### Tracking and leading

`letter-spacing` opens or tightens the gaps between letters, and `line-height`
sets how tall one line of text stands. They are what makes a small-caps section
header read as a header and a paragraph read as prose:

~~~ css
kicker  { font-size: 11px; font-weight: bold; letter-spacing: 1.2px; }
name    { font-size: 24px; letter-spacing: -0.4px; }
blurb   { font-size: 14px; line-height: 1.6; }
~~~

`letter-spacing` takes `px` or `em` (`0.08em` and `1.28px` mean the same thing
at 16px) and negative values, which is what a large heading usually wants.
`line-height` follows CSS: a bare number is a multiple of the font size, a
length is the height of the line itself. `normal` on either one leaves the
component's own spacing alone.

Write `letter-spacing: 0px` on a button when you mean it. Material tracks
button labels at about `0.089em` on its own, so a row that says nothing keeps
that spacing on the phone.

**What the Previewer does not do.** Tk has no tracking and no line spacing on a
label, so the Previewer shows the right words at the right size without the
gaps between them. What it does honour is the measuring: `letter-spacing`
changes where a button's label wraps and how wide the button asks to be, and
`line-height` adds the leading above and below the text, so a single line takes
the same height it takes on the phone. A paragraph that wraps comes out shorter
in the Previewer than on the device, by the leading of each line after the
first. Check that one on a phone.

### Your own typeface

Everything above is spacing. The font is the part that makes an app stop
looking like every other app built with the same tool. Point `font()` at the
files and name the family in CSS:

~~~ python
from apkpy_lib import font

font("Tiempos",
     regular="fonts/Tiempos-Regular.ttf",
     bold="fonts/Tiempos-Bold.ttf",
     italic="fonts/Tiempos-Italic.ttf")

theme = Theme(font_family="Tiempos")
~~~

~~~ css
app_bar     { font-family: "Tiempos"; }   /* the title, in the serif */
account_name { font-family: "Tiempos"; font-size: 26px; }
body        { font-family: sans-serif; }  /* and the reading, in the sans */
~~~

The Android build copies the files into `res/font`, writes the `<font-family>`
that maps weights onto them, and reaches them through `app:fontFamily` -- the
AppCompat attribute, because the framework one only learned to take a font
resource at API 26 and ApkPy targets 24. The Previewer loads the same files
into the session without installing anything on your machine.

Serif for the things that carry the name and sans for the things people read
is most of what makes a screen look designed, and it costs two declarations.

**Four slots, and no more.** `regular`, `bold`, `italic` and `bold_italic` are
what both sides can address: Tk has a family plus the two modifiers, and
Android expresses the same four as `fontWeight`/`fontStyle` pairs. A `medium`
or a `semibold` would render on the phone and not on the desktop, so `font()`
refuses them (`U2024`) rather than half-doing it. If you need a third weight,
register it as its own family and name it where you want it.

A slot you leave out is synthesised -- faux bold, a sheared italic -- by
Android and by Tk alike, so the two agree about what they are faking. A file
that is missing or is not a `.ttf`/`.otf` is reported at build time (`U2025`,
`U2026`) and that slot is dropped; the family still ships with whatever
survived, and a family with nothing left is never referenced by a layout.

**What the Previewer does not do.** Loading a font file into Tk is
platform-specific. Windows and Linux work. macOS declines, falls back to the
nearest system family and says so once in the console -- driving CoreText
through ctypes without a Mac to test on is how you put a crash in someone
else's Previewer. The APK is unaffected either way.

Text drawn by Android rather than by your layout does not pick the family up
yet: the labels in a `bottom_nav` and the rows of a `virtual_collection` stay
on the system font. The app bar title does carry it, through a generated text
appearance.

### Borderless surfaces

`border-width: 0` means no border, focused or not, and `background-color:
#00000000` is a transparent surface -- an input that sits directly on the
container behind it, with no box of its own. Both work in the Previewer and on
the phone.

~~~ css
composer {
    background-color: var(--surface);
    border-color: var(--border);
    border-width: 1px;
    border-radius: 28px;
    padding: 16px;
}

field {
    background-color: #00000000;
    border-width: 0px;
    placeholder-color: var(--text-secondary);
}
~~~

Colours are written the way Android reads them: `#RRGGBB` or `#AARRGGBB`, and
the `#RGB` / `#ARGB` shorthands expand to those. Anything else is reported as
`U2020` at build time rather than throwing while the screen is created.

### A composer that grows with what you write

On a `type="textarea"`, `rows` is the height it starts at and `max-rows` is
where it stops growing. Between the two it follows the text:

~~~ css
field {
    rows: 1;
    max-rows: 6;
}
~~~

One line is the right start for a reply box -- two fixed lines are half an
empty composer waiting -- and six is where a draft stops eating the thread.
Past the ceiling the field scrolls instead of growing.

Without `max-rows` the ceiling stays what it always was: twice `rows`, and
never less than eight.

### Copying a code block

`code-copy: button` puts a tappable **Copy** under every fenced block a
`markdown()` component or a collection's `markdown` slot renders. It copies
that block and nothing else -- not the paragraph above it, not the whole
message.

~~~ css
thread { code-copy: button; }
~~~

On Android 13 and later the system shows its own confirmation, so the app
stays quiet; below that it says "Copied" itself.

### A row of controls

`display: flex; flex-direction: row` lays children across, and an empty
`flex-grow: 1` container is the spacer that pushes the rest to the far edge:

~~~ css
controls {
    display: flex; flex-direction: row; align-items: center;
    gap: 8px; width: 100%;
}
spacer  { flex-grow: 1; }
chip    { flex-grow: 0; flex-shrink: 0; }
~~~

Each child asks for the width of its own content, the same as Android's
`wrap_content`. When the row is wider than the screen, `flex-shrink` decides
what gives: the default of `1` squeezes the children, and Android answers a
squeezed button by wrapping its label mid-word. `flex-shrink: 0` keeps a pill
at its natural width instead — and then a row that still does not fit is
clipped rather than wrapped. Neither is a good look, so count the row: on a
400dp phone, four or five controls is the ceiling.

A hidden child takes no space in either runtime, so swapping one control for
another with `show()` / `hide()` re-flows the row rather than leaving a gap.

### Rows that hold more than a line

A list or collection row shows one line of title and one of subtitle, and cuts
the rest off. That is right for a list and wrong for a chat, where the message
*is* the content:

~~~ css
thread {
    height: 430px;
    subtitle-lines: 4;
    item-background-color: var(--surface);
    title-color: var(--text);
    subtitle-color: var(--text-secondary);
}
~~~

`title-lines` does the same for the title. The row's own height still does the
cutting off, so raise `item_height=` alongside it.

## Responsive style rules

Use media rules when only style values change across widths:

~~~ css
content {
    padding: 18px;
}

@media (min-width: 600px) {
    content {
        padding: 32px;
        max-width: 900px;
    }
}
~~~

Use <code>responsive()</code> when the component arrangement itself must change.

## Animations

~~~ css
@keyframes appear {
    from { opacity: 0; scale: 0.96; }
    to   { opacity: 1; scale: 1; }
}

hero_card {
    animation: appear 320ms ease-out;
}
~~~

Keep motion brief and functional. Confirm the result in both the Previewer and Android build.
