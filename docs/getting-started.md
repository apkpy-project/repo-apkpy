# Installation

This guide takes you from a clean Python environment to the Hot Previewer and a native Android build.

## Requirements

- Python 3.8 or newer;
- a JDK between 17 and 21 for local Android compilation;
- the Android SDK, either from Android Studio or from <code>apkpy setup</code>.

Install or update ApkPy:

~~~ powershell
python -m pip install --upgrade apkpy
~~~

Check the Android toolchain:

~~~ powershell
apkpy doctor
~~~

If ApkPy cannot find a suitable JDK or Android SDK, let it install a compatible local toolchain:

~~~ powershell
apkpy setup
~~~

## Create the first project

~~~ powershell
apkpy start hello_apkpy
cd hello_apkpy
~~~

The project contains <code>writehere.py</code>, the source file in which you create screens and app logic.

Replace it with:

~~~ python
from apkpy_lib import Screen, button, label, run, toast

home = Screen(id="home")
label("My first native screen", id="title", screen=home)
button("Test action", command=lambda: toast("It works"), screen=home)

style = """
home {
    background-color: #09090B;
    padding: 24px;
    gap: 16px;
}

title {
    color: #FAFAFA;
    font-size: 28px;
    font-weight: bold;
}

button {
    background-color: #8B5CF6;
    color: #FFFFFF;
    border-radius: 14px;
    padding: 14px;
}
"""

if __name__ == "__main__":
    run(start_screen=home)
~~~

## Preview, build or run

=== "Hot Previewer"

    ~~~ powershell
    python writehere.py
    ~~~

    Use this during interface development. It starts quickly and lets you test navigation, inputs, state and callbacks on your computer.

=== "Android Studio project"

    ~~~ powershell
    apkpy build
    ~~~

    This creates a ZIP containing the generated Gradle project. Open the extracted project in Android Studio when you want to inspect Java/XML or use Android Studio tooling.

=== "Installable APK"

    ~~~ powershell
    apkpy run
    ~~~

    ApkPy generates the Android project, runs Gradle and places a debug APK beside the project.

Optional installation helpers:

~~~ powershell
apkpy run --qr
apkpy run --usb
~~~

## Start from an example

Use the interactive example picker:

~~~ powershell
apkpy examples
~~~

Examples cover basic UI, multiple screens, storage, permissions, background work, camera/gallery, dialogs, location, network images, loading, secure login, REST, SQLite lists and Python loops.

## Recommended workflow

1. Build the screen in <code>writehere.py</code>.
2. Test the behavior in the Hot Previewer.
3. Run <code>apkpy build</code> when checking generated Android code.
4. Test on an Android emulator or physical device.
5. Run <code>apkpy release</code> only when the app identity and signing key are ready.

Continue with [Core concepts](core-concepts.md).
