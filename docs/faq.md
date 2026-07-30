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
    }
  ]
}
</script>
