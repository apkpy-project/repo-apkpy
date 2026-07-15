<div class="hero">
  <h1>Android apps. Pure Python.</h1>
  <p>ApkPy turns a Python interface and CSS-inspired styles into native Android Java and XML. Preview quickly on your computer, then generate an Android Studio project or an installable APK.</p>
</div>

[:material-rocket-launch: Get started](getting-started.md){ .md-button .md-button--primary }
[:material-book-open-variant: Browse the API](api-reference.md){ .md-button }

## Why ApkPy?

<div class="feature-grid">
  <div class="feature-card"><strong>Native output</strong>Real Android Activities, views, resources and services — not a WebView.</div>
  <div class="feature-card"><strong>Fast feedback</strong>Run the same app in the desktop Hot Previewer before compiling Android.</div>
  <div class="feature-card"><strong>One language</strong>Build layouts, app logic, storage, networking and media flows in Python.</div>
  <div class="feature-card"><strong>Consistent design</strong>Theme tokens and CSS-inspired rules are shared by Previewer and Android output.</div>
</div>

## A complete app starts small

~~~ python
from apkpy_lib import Screen, Theme, button, label, run, toast

home = Screen(id="home")
label("Hello from ApkPy", id="title", screen=home)
button(
    "Build something native",
    variant="filled",
    icon="arrow_forward",
    command=lambda: toast("Ready!"),
    screen=home,
)

theme = Theme(
    mode="dark",
    primary="#8B5CF6",
    secondary="#22D3EE",
    background="#09090B",
    surface="#18181B",
    text="#FAFAFA",
)

if __name__ == "__main__":
    run(start_screen=home, theme=theme)
~~~

Preview it:

~~~ powershell
python writehere.py
~~~

Build it:

~~~ powershell
apkpy run
~~~

## What is included in 1.0.0?

Version 1.0.0 brings together the full native app workflow:

- responsive rows, columns, flex, grid, cards and layered layouts;
- Material-style buttons, app bars, bottom navigation, overlays and content states;
- rich lists, carousels and grids;
- background audio, queues, player controls, favourites and editable playlists;
- offline file downloads and OAuth login for Google, Spotify and GitHub;
- encrypted storage, PBKDF2 password hashing, AES-256-GCM on Android and parameterized SQLite;
- direct APK builds, QR/USB installation and signed releases.

See [Version 1.0.0](version-1.0.0.md) for the release overview.

!!! note "Closed source and documentation"
    The ApkPy implementation can remain in a private repository. A documentation build publishes only the generated <code>site/</code> directory. See [Cloudflare Pages](cloudflare-pages.md) for the safe deployment configuration.
