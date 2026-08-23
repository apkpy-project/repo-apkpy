---
title: Motion
description: One dial for how an ApkPy app moves — transitions, press feedback and screen changes.
---

# Motion

Four moments change what is on screen: a component appears or disappears, a
button is pressed, a bottom-bar item becomes active, one screen replaces
another. They share one dial.

```python
run(start_screen=home, theme=Theme(motion="standard"))
```

| preset | base | feel |
|---|---|---|
| `none` | 0 ms | nothing animates, anywhere |
| `subtle` | 120 ms | quick, close to instant |
| `standard` | 180 ms | the default |
| `expressive` | 260 ms | deliberate |

Each moment scales the base, so raising or lowering `motion` speeds up or slows
down the whole app coherently instead of one widget at a time:

| moment | ×base | at `standard` |
|---|---|---|
| press | 0.5 | 90 ms |
| bottom-bar item | 0.8 | 144 ms |
| appear / disappear | 1.0 | 180 ms |
| screen change | 1.5 | 270 ms |

Both runtimes resolve durations from the same shared module, and a test asserts
they agree for every combination. A transition cannot last 180 ms on the phone
and 300 ms on the desktop.

The curve is Material's standard easing, the cubic bezier `(0.4, 0, 0.2, 1)`.
The Previewer evaluates it in Python and the generated Android animation names
`@android:interpolator/fast_out_slow_in` — the same curve, named once on each
side.

## Appearing and disappearing

`show()` and `hide()` fade instead of popping. Per-component timing comes from
CSS:

```python
receipt = container(id="receipt", visible=False, screen=home)

def upload_started():
    receipt.show()
```

```css
receipt { transition: 240ms; }   /* or: none */
```

On Android this becomes a real alpha animation. In the Previewer, where Tk has
no per-widget alpha, it interpolates colours towards the theme background —
an approximation of the pixels, but the same duration and the same moment.

## Press feedback

```css
add_item { press: tint; }    /* none | tint | scale */
```

`tint` is the default: the button eases towards its pressed colour instead of
swapping in one frame, which is closer to the ripple Android draws for free.
`none` silences the feedback on both sides, including the Android ripple.

## The bottom bar

The active item fills: a pill lights up behind the icon and the icon goes from
outline to solid. See [Icons](icons.md#outlined-variants).

```python
bottom_nav([home, about], labels=["Home", "About"],
           icons=["home", "info"], indicator="pill")   # pill | line | none
```

The pill is a tint of the surface, not the full-strength primary — the active
icon is drawn in the primary colour and would otherwise disappear inside it.

## Screen transitions

```python
def open_detail():
    on_click_navigate(detail, transition="slide")   # none | slide | slide_up
```

On Android this uses `overrideActivityTransition` on API 34 and above and
`overridePendingTransition` below it, because the older call is deprecated at
the `targetSdk` ApkPy generates. Without that guard the animation is silently
dropped on new Android versions.

Bottom-bar tabs deliberately do not slide. Tabs are siblings, not a stack.

## Accessibility

Turning off animations in Android's settings turns them off in your app.
The generated code reads `ANIMATOR_DURATION_SCALE` and skips the animation when
it is zero.

## What ApkPy will not pretend to do

**No fade between screens.** Tk cannot cross-fade two widget trees, so a screen
`fade` would work on the phone and not in the Previewer. The vocabulary is
limited to what both runtimes can actually do.

**No shared-element transitions** — the list item that grows into the detail
screen. ApkPy screens are Activities, and that effect needs Fragments.

**A small, closed set of names** rather than a free-form animation API. The
Previewer runs on Tk, which has no vsync; an open API would drift from the
phone in *timing*, and timing drift is not something a test catches after the
fact.
