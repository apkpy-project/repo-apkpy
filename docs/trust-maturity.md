---
title: Trust and maturity
description: ApkPy support policy, validation evidence, limitations and release confidence.
---

# Trust and maturity

ApkPy is a young compiler. Trust should come from inspectable output and
repeatable evidence, not from pretending the project is older than it is.

<section class="proof-band">
  <article><strong>167</strong><span>transpiler regression checks</span></article>
  <article><strong>21</strong><span>Data Core and Reactive Data checks</span></article>
  <article><strong>Real Gradle</strong><span>generated debug APK compiled</span></article>
  <article><strong>Strict docs</strong><span>warnings fail the build</span></article>
</section>

## What was validated

| Area | Evidence | What it proves |
| --- | --- | --- |
| Python compiler | 167 regression checks | supported source patterns continue to produce expected output |
| Reactive Data | 21 focused Data Core and Reactive Data checks | relations, includes, lifecycle, invalidation, rollback and conditional code generation are exercised |
| Data Core | CRUD, transaction and migration tests | typed values, rollback, schema paths and destructive recovery are exercised |
| Generated Java/XML | structural and XML parsing checks | generated sources are internally consistent |
| Android toolchain | Gradle debug APK build | the checked release reaches Android bytecode/resources |
| Runtime floor | same-app Android benchmark | APK size, cold start and PSS are reported with programs and raw samples |
| Documentation | `mkdocs build --strict` | navigation, internal links and configuration resolve |

Last documented validation: **ApkPy 1.3.1, published on 20 August 2026**.

These checks do not certify every phone, Android manufacturer, backend or app
design. They make regressions visible and give a reviewer concrete artifacts to
inspect.

The [Android benchmark](benchmark.md) is deliberately narrow: one 100-note
debug app on one emulator. It publishes the competing app programs, line-count
rule, raw starts, memory samples and hashes instead of presenting a marketing
number without context.

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
- Data Core repositories, executor and migration runtime appear only when
  `db.model()` is declared.
- relation metadata and batched hydration appear only with `db.relation()`;
- the invalidation tracker and observable-query runtime appear only when
  `observe()` is used.

This keeps generated projects reviewable and reduces unused dependencies.

## Stability contract

The documented names exported from `apkpy_lib` are the supported surface.
Generated helper classes are implementation details and may change between
versions. The Python declaration remains the source of truth; hand-edits in a
generated Android project can be replaced by the next build.

Patch releases should preserve existing declarations. New capabilities are
documented in a version page and must pass the existing regression suite.

## Ownership and continuity

The compiler core is proprietary while ApkPy is under active development. The
maintainer may consider open-sourcing it later and commits to releasing the
core as open source if active development is permanently discontinued. This is
a continuity commitment, not an open-source licence for current releases.

A temporary pause or slower release cadence does not change the licence. Read
[Project continuity and source availability](project-continuity.md) for the
exact boundary and the public transition that would be required.

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
