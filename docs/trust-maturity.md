---
title: Trust and maturity
description: ApkPy support policy, validation evidence, limitations and release confidence.
---

# Trust and maturity

ApkPy is a young compiler. Trust should come from inspectable output and
repeatable evidence, not from pretending the project is older than it is.

<section class="proof-band">
  <article><strong>164</strong><span>transpiler regression checks</span></article>
  <article><strong>16</strong><span>focused module checks</span></article>
  <article><strong>Real Gradle</strong><span>generated debug APK compiled</span></article>
  <article><strong>Strict docs</strong><span>warnings fail the build</span></article>
</section>

## What was validated

| Area | Evidence | What it proves |
| --- | --- | --- |
| Python compiler | 164 regression checks | supported source patterns continue to produce expected output |
| Modular runtimes | 16 focused checks | feeds, mutation hooks and conditional modules behave as designed |
| Generated Java/XML | structural and XML parsing checks | generated sources are internally consistent |
| Android toolchain | Gradle debug APK build | the checked release candidate reaches Android bytecode/resources |
| Documentation | `mkdocs build --strict` | navigation, internal links and configuration resolve |

Last documented validation: **ApkPy 1.2.2 release candidate, July 2026**.

These checks do not certify every phone, Android manufacturer, backend or app
design. They make regressions visible and give a reviewer concrete artifacts to
inspect.

## Supported environment

| Tool | Supported |
| --- | --- |
| Python | 3.8 through 3.13 |
| JDK | 17 through 21 |
| Android output | Java, XML and Gradle project |
| Desktop preview | Windows, macOS or Linux with Tk |
| APK runtime | native Android; no Python interpreter embedded |

Run `apkpy doctor` before a build. Validate notifications, background work,
media, permissions and location on a real Android device before release.

## Conditional output

ApkPy detects features before generation. A small app does not receive every
runtime:

- WebSocket helpers appear only when `websocket` is used;
- Firebase dependencies appear only with push code and configuration;
- `SwipeRefreshLayout` appears only for refreshable virtual collections;
- Media3 and the foreground media service appear only for media features;
- map, route and location helpers appear only when requested;
- rich-document helpers appear only for Markdown, rich text or trees.

This keeps generated projects reviewable and reduces unused dependencies.

## Stability contract

The documented names exported from `apkpy_lib` are the supported surface.
Generated helper classes are implementation details and may change between
versions. The Python declaration remains the source of truth; hand-edits in a
generated Android project can be replaced by the next build.

Patch releases should preserve existing declarations. New capabilities are
documented in a version page and must pass the existing regression suite.

## Honest limits

ApkPy does not currently promise:

- arbitrary Python library compatibility on Android;
- automatic backend generation or cloud deployment;
- end-to-end encrypted messaging;
- payment processing, DRM or proprietary map SDKs;
- collaborative CRDT editing;
- identical OEM behavior without device testing;
- conversion of unsupported dynamic Python into Java.

For a product-level view, read [Can ApkPy build this?](can-apkpy-build-this.md).
For renderer differences, read [Previewer versus Android](preview-android.md).
