# ApkPy 1.10.0 — several files, and numbers that stay numbers

Write native Android apps in the supported Python subset. The generated APK
still contains Java/XML, not a Python runtime.

## New

- **More than one file.** `writehere.py` can `import` plain Python modules
  beside it and share their functions and constants across screens. The helper
  is merged before anything is translated, so its functions become ordinary
  methods of the generated Activity and its constants become fields. The
  Previewer needed no code: beside the script, this is the import Python
  already does. Only `import helpers` is accepted; `from helpers import x` and
  a name defined in two files stop the build with the new **`U2036`**, because
  either one would leave the desktop and the phone holding different names.
- **Numbers that stay numbers.** A parameter every call site fills with a
  number now counts as one inside the body, so `cents / 100` is arithmetic
  instead of a refusal. Numbers written at module level are emitted as fields,
  and a function whose every `return` is a number lets one helper feed another.
  Anything ApkPy cannot prove is a number stays text — a deliberately narrow
  rule, because a wrong yes would turn a sum into glued text without a word.
- **What ApkPy reaches, and what it does not.** A page naming all 60
  capabilities an application uses: the 42 covered, and the 18 that are not,
  with the mechanical numbers measured against `android.jar` rather than
  estimated.

## Fixed

- **`margin` with more than one value.** `margin: 24px 16px 0px 16px` meant a
  margin of **2,416,016**: both renderers stripped the non-digits out of the
  whole string and read the rest as one number. The Previewer drew an empty
  screen and the phone pushed the layout off the display, with no diagnostic on
  either side. The CSS shorthand is now read once, in the module both renderers
  share.

## Upgrading

Nothing in 1.9.0 changes behaviour. An app that does not import a helper
generates exactly what it generated before. If a stylesheet used a multi-value
`margin`, the layout will move — to where the stylesheet actually said.

## Verified in this release

- 1,151 feature tests (29 new for the modules and the numbers, 8 for the
  margin), 35 general tests and 258 transpiler checks.
- 100 example apps and documented snippets transpiled before and after the
  change: nothing that built stopped building.
- The two-file example was rendered in the Previewer and built with Gradle
  (`BUILD SUCCESSFUL`), and the generated Java read by hand.
- A 144-line showcase app split across two files, rendered and compiled.
- MkDocs strict build.
- **On a phone:** the two-file example installed on a Xiaomi 25069PTEBG running
  Android 16, opened in 561 ms, showed `EUR 30.12`, ran its button callback and
  survived a rotation with no exception in `logcat`.

## Not verified

- The coverage page's sixty capabilities are our list, not a standard. Each
  one's signal is described on the page so it can be checked rather than
  believed.

Full notes: [1.10.0](docs/version-1.10.0.md) ·
[More than one file](docs/guides/modules.md) ·
[what it reaches](docs/coverage.md) ·
[compatibility](docs/compatibility.md)
