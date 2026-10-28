# Security Policy

## Supported versions

Security fixes go into the latest release. On an older one, the fix is to
upgrade (`python -m pip install --upgrade apkpy`) and build the app again.

| Version | Supported |
| :---: | :---: |
| The latest release on [PyPI](https://pypi.org/project/apkpy/) | ✅ Yes |
| Any earlier release | ❌ No |

## Reporting a vulnerability

**Please do not open a public issue.** Report it privately: on this
repository's **Security** tab, choose **Report a vulnerability**.

We will acknowledge your report within 48 hours and aim to release a patch
within 7 days for confirmed vulnerabilities.

Please include:

- A description of the vulnerability
- Steps to reproduce it
- Potential impact
- Any suggested fix (if you have one)

## What is in scope

ApkPy is a build tool, and what it writes ends up inside other people's apps.
Both are in scope:

- **ApkPy itself:** the `apkpy` command, the build and the Previewer.
- **What ApkPy writes into an app:** the Java, the manifest and the Gradle
  files of a built project — a permission an app did not ask for, a secret
  written where another app can read it, an encryption or a password hash
  weaker than the documentation says.

A flaw in a library the built apps depend on (AndroidX, Material Components,
OkHttp, Google's) belongs to that library; tell us too, so the version ApkPy
asks for can be raised.

## What ApkPy does for the apps it builds

Encrypted storage, password hashing, encryption with a key held by the
Android Keystore, parameterised SQL and certificate pinning are described,
with what each does and does not protect against, in
[Data, network and security](https://repo-apkpy.pages.dev/data-security/).
