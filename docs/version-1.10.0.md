---
title: Version 1.10.0
description: Several files instead of one, parameters that stay numbers, a page naming what ApkPy reaches, and a margin that no longer blanks the screen.
---

# ApkPy 1.10.0

Released 2026-09-19. `python -m pip install --upgrade apkpy==1.10.0`.

Nothing in 1.9.0 changes behaviour. An app that does not use the new names
generates exactly what it generated before.

## More than one file

ApkPy reads one `writehere.py` and does not translate Python classes, so an
application had nowhere to put anything: every screen, every callback and every
helper landed in the same file. The largest app in this repository is 212
lines, and that was not a coincidence.

Now `writehere.py` can `import` plain Python modules beside it.

```python
import money

total.set_value(money.euros(1999))     # EUR 19.99
```

The helper is merged into your application before anything is translated, so
`money.euros` becomes an ordinary method of the generated Activity and its
constants become fields. The Previewer needed no code at all: beside the
script, this is the import Python already does.

Only the whole-module form is accepted. `from money import euros` stops the
build with the new **`U2036`**, because ApkPy merges the whole file into one
namespace and the `from` form would leave your app holding names the
Previewer's own Python would not — the kind of difference between desktop and
phone this project spends its time removing. A name defined in two files stops
the build for the same reason.

A helper holds functions and constants. Screens, themes, widgets and CSS stay
in `writehere.py`, where the compiler reads them in order. Full rules in
[More than one file](guides/modules.md); a complete two-file app is in
[`examples/modules/`](https://github.com/apkpy-project/repo-apkpy/tree/main/examples/modules).

## Numbers that stay numbers

A function parameter used to be text, always. That is right at the boundary
between your Python and the generated Java, and wrong inside the function:
`cents / 100` stopped the build even when every call passed a number.

Now the call sites decide. A parameter counts as a number when the function is
called at least once and **every** call passes something ApkPy can prove is
one: a numeric literal, `int()`/`float()`/`len()`, arithmetic between those, a
name the module only ever assigns from them, or another function of yours whose
every `return` is a number. That last rule is what lets one helper feed
another, `euros(with_vat(cents))` — parameters and return values are settled
together rather than read once.

Numbers written at module level are emitted as fields, so `VAT = 23` works
inside a helper.

Everything else stays text, including every call with a keyword argument, which
does not say which position it fills. The rule is deliberately narrow: anything
ApkPy says yes to here becomes real arithmetic in the generated Java, and a
wrong yes would turn a sum into glued text without a word.

## What ApkPy reaches, and what it does not

A new page, [What it reaches](coverage.md), names every Android capability
ApkPy covers — 42 of the 60 an application actually uses — and every one it is
missing, with the mechanical numbers measured against `android.jar` rather than
estimated. The list is ours, which is exactly why it is printed in full.

## Fixed: a margin that blanked the screen

`margin: 24px 16px 0px 16px` meant a margin of **2,416,016**. Both renderers
stripped the non-digits out of the whole string and read what was left as a
single number, so the Previewer drew an empty screen and the phone pushed the
layout off the display — with no diagnostic on either side, which is the exact
failure this project exists to remove.

The CSS shorthand is now read once, in the module both renderers share, with
the real rules for one, two, three and four values. On Android each side goes
out as its own attribute, and a single value still uses `layout_margin`.

## Verified in this release

- 1,151 feature tests (29 new for the modules and the numbers, 8 for the
  margin), 35 general tests and 258 transpiler checks.
- 100 example apps and documented snippets transpiled before and after the
  change: nothing that built stopped building.
- The two-file example was rendered in the Previewer and built with Gradle —
  `BUILD SUCCESSFUL` — and its generated Java read by hand.
- A real 144-line showcase app split across two files, rendered and compiled.
- MkDocs strict build.

## Not verified

- **Nothing here was run on a phone.** The generated Java compiles and the
  Previewer renders; neither proves a screen behaves on a device.
- The coverage page's sixty capabilities are our list, not a standard. The
  signal used for each one is described on the page so it can be checked.
