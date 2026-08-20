---
title: Project continuity and source availability
description: ApkPy's current proprietary status and its long-term open-source continuity commitment.
---

# Project continuity and source availability

ApkPy is actively developed and maintained as proprietary software. Its public
documentation, examples, generated-project contract and release evidence are
open for inspection, but the core compiler is **not open source today**.

## Current source status

There is no current plan to publish the core compiler while active development
and maintenance continue. Installation or access to a packaged release does
not grant permission to redistribute, modify or republish its source. The
current [`LICENSE`](https://github.com/apkpy-project/repo-apkpy/blob/main/LICENSE)
remains the authoritative licence for today's releases.

This model lets the maintainer develop the compiler as one coherent product
while exposing a clear public API, reproducible examples and inspectable native
Android output.

## Long-term continuity commitment

Open-sourcing may be considered later even while the project is healthy. More
importantly, if the maintainer ever decides to **permanently abandon ApkPy**,
the core source will be released as open source so users can inspect it,
maintain it and continue the project.

That transition will include:

- an explicit public announcement that active development has ended;
- publication of the core source in an accessible repository;
- a named open-source licence that applies from that release onward;
- enough build and architecture information for another maintainer to resume
  development.

## What does not count as abandonment

A gap between releases, slower maintenance, an unanswered issue or a temporary
pause does not automatically change ApkPy's licence. Until an explicit
transition is announced and the source is published under a new licence, every
existing ApkPy release remains proprietary under the terms distributed with
that release.

This distinction protects both sides: users have a clear continuity promise,
while the current package is not accidentally presented as open source before
an actual source release exists.

## What remains public now

Even while the compiler core remains private, the project publishes the parts
developers need to evaluate the product:

- the supported Python API and its deliberate limits;
- complete application examples without private compiler source;
- generated Java, XML and Gradle architecture explanations;
- reproducible benchmark programs, methods and scoped results;
- release notes, migration guidance and validation evidence;
- a public issue tracker for reproducible defects and feature requests.

Read [Trust and maturity](trust-maturity.md) for current validation evidence and
[Community and support](community.md) for the public support process.
