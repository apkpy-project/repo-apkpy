# Core concepts

ApkPy has one source language and two execution targets: the desktop Hot Previewer and generated native Android code.

## The source of truth

Your app lives in <code>writehere.py</code>. ApkPy parses its Python syntax tree and maps supported operations to Android Java, XML and resources.

The generated Android project is an output, not the place to maintain app behavior. If you rebuild, generated files can be replaced.

## Screens become Activities

~~~ python
from apkpy_lib import Screen

home = Screen(id="home")
library = Screen(id="library", scroll=True)
~~~

Each <code>Screen</code> becomes a separate Android Activity. Use <code>scroll=True</code> when the complete screen should scroll as one page.

## Components attach to a screen or parent

~~~ python
from apkpy_lib import container, label

summary = container(id="summary", screen=home)
label("12 tracks", id="count", parent=summary)
~~~

Passing <code>screen=</code> places a component at the screen root. Passing <code>parent=</code> nests it inside a container or composable card.

Keep the returned component when it will change later:

~~~ python
status = label("Waiting", screen=home)
status.set_value("Ready")
status.hide()
status.show()
~~~

## Styles use selectors

The global <code>style</code> string supports component selectors and ID selectors:

~~~ python
style = """
label {
    color: #A1A1AA;
    font-size: 14px;
}

page_title {
    color: #FAFAFA;
    font-size: 30px;
    font-weight: bold;
}
"""
~~~

An ID selector wins over the component selector. A <code>Theme</code> supplies the defaults underneath both.

## Callbacks hold app logic

~~~ python
from apkpy_lib import button, inputs, toast

name = inputs("Your name", screen=home)

def save():
    value = name.get_value()
    if value == "":
        toast("Enter your name first")
        return
    toast("Saved: " + value)

button("Save", command=save, screen=home)
~~~

Keep callbacks small and move reusable behavior into normal Python functions. Supported control flow includes conditions, <code>for</code>, <code>while</code>, <code>break</code>, <code>continue</code> and common string/number operations.

## Preview and Android parity

The Previewer simulates Android behavior using desktop widgets. The generated app uses native Android components.

The API and state flow should match, while platform-specific presentation can differ slightly:

| Area | Hot Previewer | Android |
| --- | --- | --- |
| UI | Desktop rendering calibrated to Android dimensions | Native Android views |
| Storage | Encrypted local JSON file | Encrypted SharedPreferences |
| Database | Python SQLite | Android SQLiteDatabase |
| Network | Background Python request | Background HttpURLConnection |
| Audio | Desktop media backend | Android foreground media service |
| Pickers | Desktop dialogs | Native Material/system dialogs |

Always test device-only functionality on Android before release.

## App entry point

~~~ python
if __name__ == "__main__":
    run(start_screen=home, theme=app_theme)
~~~

Use one <code>run()</code> call after the screens, components, navigation and styles have been declared.
