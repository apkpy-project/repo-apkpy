# ApkPy 1.6.1 — What 1.6.0 missed by a few hours

Three fixes landed just after 1.6.0 was published, and a version on PyPI cannot
be replaced. If you are on 1.6.0, this is the one to take — **especially if you
publish to Google Play**.

---

## Google Play was going to refuse your app

1.6.0 generated projects with `targetSdk 34`. Google raises the minimum target
API every year and 34 had fallen below it, so a new app or an update built with
1.6.0 is **rejected at upload**.

1.6.1 targets API 35.

### Which meant drawing around the system bars

That is not a one-line change, and it is the reason the two ship together. From
API 35 Android draws the app **behind** the status and navigation bars, always.
Without handling it, the first line of every screen without an app bar would sit
under the clock.

Each screen's root now declares `fitsSystemWindows` — on the root deliberately,
because it *consumes* the insets, so the toolbar's own listener stops growing
and the top is not padded twice.

Checked on a phone running Android 16, on all five screen shapes: plain, with
an app bar, with a bottom bar, with a drawer, and with both.

!!! note "1.6.0 was not broken by this"

    It stayed on `targetSdk 34`, where Android does not enforce edge-to-edge —
    so the missing insets did no harm there. The two belong together, and they
    arrive together.

## `background-color` on a label did nothing on the phone

The `TextView` never carried a background at all. A band of colour with dark
text on it looked right in the Previewer and came out as **invisible text** on
the device — the text was drawn in a colour meant to sit on a background that
was never painted.

```python
label("Aisle 4", id="tag", screen=home)

style = """
tag { background-color: #C96442; color: #1B1B19; }
"""
```

It was found by accident, while photographing the system-bar work: two lines of
the test app simply were not there.

The accessibility report was affected by the same gap. It read the declared
background when it measured contrast, so it was reporting a ratio against
something the phone never drew. Now that the band is painted, the number
describes what is on screen.

---

## Verification

256 transpile tests, 35 unit tests, 782 feature tests, 28 examples,
`mkdocs build --strict`, and a signed App Bundle built at `targetSdk 35`. The
system bars and the label background were both checked on a real phone running
Android 16 rather than only in the generated XML.

---

## Upgrading

```powershell
python -m pip install --upgrade apkpy
```

**If you built anything with 1.6.0 and sent it to Play, rebuild it.** The
rejection is at upload, so nothing is live and broken — but the build you have
will not be accepted.

Nothing else changes. If your app positions something by hand near the top or
bottom of a screen, look at it once on a device: the app now draws around the
system bars rather than under them.
