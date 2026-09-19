---
title: More than one file
description: Split an ApkPy app across Python files, and keep numbers as numbers across them.
---

# More than one file

ApkPy reads one `writehere.py` and does not translate Python classes, so for a
long time an application had nowhere to put anything: every screen, every
callback and every piece of arithmetic landed in the same file. The largest app
in this repository is 212 lines, and that is not a coincidence.

Now `writehere.py` can import plain Python modules that sit next to it.

```python
import money

from apkpy_lib import Screen, label, run

home = Screen(id="home")
total = label("", id="total", screen=home)

total.set_value(money.euros(1999))     # EUR 19.99
```

```python
# money.py, beside writehere.py
CURRENCY = "EUR"


def euros(cents):
    whole = cents / 100
    return CURRENCY + " " + str(round(whole, 2))
```

The helper is merged into your application before anything is translated, so
`money.euros` becomes an ordinary method of the generated Activity and
`CURRENCY` becomes a field. The Previewer needs nothing special: beside the
script, this is the import Python already does.

Run [the complete example](https://github.com/apkpy-project/repo-apkpy/tree/main/examples/modules)
with `python writehere.py`, then build it with `apkpy run`.

## What a helper holds

**Functions and constants.** Screens, themes, widgets and CSS stay in
`writehere.py`, where ApkPy reads them in the order they appear. A helper that
declares a `Screen` or calls `Theme(...)` stops the build with
[`U2036`](../friendly-errors.md) rather than being quietly ignored.

A helper may import another helper. They are merged innermost first, so a
helper can call the one it imports.

## Only `import helpers`, not `from helpers import`

```python
import money            # yes
import money as m       # yes
from money import euros # refused, with U2036
```

This is deliberate. ApkPy merges the whole file into one namespace, so the
`from` form would leave your app holding names that the Previewer's real Python
would not — a difference between the desktop and the phone that would only
appear later, which is the failure this project spends its time removing.

For the same reason, a name defined in two files stops the build. In one
namespace there is no way to keep both, and picking one silently is worse than
asking you to rename it.

## Numbers that stay numbers

A function parameter used to be text, always, because "everything is String" is
how values cross the boundary between your Python and the generated Java. That
is right at the boundary and wrong inside the function: `cents / 100` stopped
the build even when every call passed a number.

Now the call sites decide. A parameter counts as a number when the function is
called at least once and **every** call passes something ApkPy can prove is
one:

- a number written in the source, `2` or `19.99`;
- `int(...)`, `float(...)` or `len(...)`;
- arithmetic between those;
- a name the whole module only ever assigns from them;
- another function of yours whose every `return` is a number.

That last one is what lets helpers feed each other:

```python
def with_vat(cents):
    return cents + cents * VAT / 100


def euros(cents):
    return CURRENCY + " " + str(round(cents / 100, 2))


total.set_value(euros(with_vat(2449)))      # EUR 30.12
```

Everything else stays text. One call site that passes a value ApkPy cannot
prove is a number — including a keyword argument, which does not say which
position it fills — and the parameter is text again for every call.

This is deliberately narrow. Anything ApkPy says yes to here becomes real
arithmetic in the generated Java, and a wrong yes would turn a sum into glued
text without a word. Text and numbers only have to agree on the phone and on
the desktop; they do not have to be guessed.

## What this does not do

- **There are still no classes.** A helper holds functions and constants.
- **A helper cannot build UI.** Component reuse across screens is a different
  problem and is not solved here.
- **Only files beside your application.** No packages, no subfolders, no
  `from . import`. An import ApkPy does not recognise is left exactly as it
  was, so `import math` and everything the compiler already reads keep working.
- **Parameters travel as text.** The Java signature is still `String cents`;
  what changed is that arithmetic inside the body is allowed to treat it as a
  number.

## Checked for this change

- 29 focused tests, plus 1,151 feature tests, 35 general tests and 258
  transpiler checks.
- 100 example apps and documented snippets transpiled before and after:
  nothing that built stopped building.
- The example above was rendered in the Previewer and built with Gradle —
  `BUILD SUCCESSFUL` — and the generated Java read by hand.
- Not checked on a phone.
