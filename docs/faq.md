---
title: Frequently asked questions
description: Direct answers about ApkPy output, compatibility, Previewer limits and production use.
---

# Frequently asked questions

## Does an ApkPy APK contain Python?

No. ApkPy generates Java, XML, resources and a Gradle project. The APK runs as
a native Android application without embedding a Python interpreter.

## Can I open the result in Android Studio?

Yes. `apkpy build` creates a normal Android project that can be inspected and
compiled in Android Studio.

## Does every Python library work on Android?

No. ApkPy translates its documented declarative API and supported Python
patterns. An arbitrary desktop Python package does not automatically become
Java.

## Is the Hot Previewer an Android emulator?

No. It is a fast desktop renderer for layout and callbacks. Android permissions,
services, codecs, FCM, GPS and OEM behavior require an emulator or device.

## Can ApkPy build a complete social or delivery app?

It can generate much of the native client. Accounts, moderation, payments,
recommendations, dispatch and canonical server data remain application
infrastructure. See [Can ApkPy build this?](can-apkpy-build-this.md).

## Is local data encrypted?

ApkPy provides encrypted local values and password hashing, but security still
depends on correct key handling, server authorization and threat modeling.

## Is the generated project conditional?

Yes. Feature helpers and dependencies are emitted only when the source uses the
matching capability.

## Is ApkPy open source?

Not currently. ApkPy is actively developed as proprietary software. The
maintainer may choose to open-source the core later and commits to doing so if
the project is permanently abandoned, allowing others to continue it. A pause
or slower release cadence does not change the present licence; an open-source
transition requires an explicit announcement, published source and a named new
licence. See [Project continuity](project-continuity.md).

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "Does an ApkPy APK contain Python?",
      "acceptedAnswer": {"@type": "Answer", "text": "No. ApkPy generates Java, XML, resources and a Gradle project. The APK runs without an embedded Python interpreter."}
    },
    {
      "@type": "Question",
      "name": "Can I open an ApkPy project in Android Studio?",
      "acceptedAnswer": {"@type": "Answer", "text": "Yes. ApkPy generates a normal Android Gradle project that can be inspected and compiled in Android Studio."}
    },
    {
      "@type": "Question",
      "name": "Is the ApkPy Previewer an Android emulator?",
      "acceptedAnswer": {"@type": "Answer", "text": "No. It is a fast desktop renderer. Device APIs and Android lifecycle behavior must be tested on Android."}
    },
    {
      "@type": "Question",
      "name": "Is ApkPy open source?",
      "acceptedAnswer": {"@type": "Answer", "text": "Not currently. ApkPy is proprietary while actively developed. The maintainer may open-source it later and commits to releasing the core as open source if active development is permanently discontinued."}
    }
  ]
}
</script>
