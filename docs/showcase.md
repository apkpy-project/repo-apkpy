# Built with ApkPy

The showcase is a visual test of the library, not a set of static mockups. Each app below is an executable Python program that was opened in the Hot Previewer, tested through its primary action and navigation, and transpiled into native Android sources.

Every case study includes its complete application declaration and a
**signed release APK built by ApkPy 1.11.0** — R8 shrinking on,
`targetSdk` 35, around 1.6 MB. Install one, then read the source that produced
it. The links expose app code only — not the private source of the ApkPy
compiler. The pictures are those APKs running on a phone (a Xiaomi on
Android 16), not the Previewer.

## Lumen — personal finance

<div class="showcase-detail">
  <div class="app-shot app-shot--detail"><img src="../assets/showcase/lumen-finance.png" alt="Lumen personal finance app"></div>
  <div>
    <span class="showcase-tag">LIGHT THEME · RICH LISTS</span>
    <h3>Money without visual noise</h3>
    <p>Lumen combines a high-contrast balance surface with restrained supporting color. The screen uses themed containers, a rich transaction list, Material actions, toast feedback and a four-destination bottom navigation.</p>
    <ul>
      <li>Global light theme and reusable color tokens</li>
      <li>Responsive action row and financial summary card</li>
      <li>Interactive rich list and bottom navigation</li>
    </ul>
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/lumen_finance.py">View 144-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Lumen-1.11.0.apk">Download signed APK (1.6 MB)</a></p>
  </div>
</div>

## Onda — daily wellbeing

<div class="showcase-detail showcase-detail--reverse">
  <div class="app-shot app-shot--detail"><img src="../assets/showcase/onda-wellness.png" alt="Onda wellbeing app"></div>
  <div>
    <span class="showcase-tag">DARK THEME · RESPONSIVE CARDS</span>
    <h3>A dashboard that knows when to stay quiet</h3>
    <p>Onda uses a limited lime-and-coral palette to make readiness, recovery and the next useful action immediately legible. Flex containers keep paired metrics balanced at phone width.</p>
    <ul>
      <li>Custom dark theme with clear semantic color roles</li>
      <li>Flexible metric cards and compact schedule composition</li>
      <li>Button feedback and state-preserving tab navigation</li>
    </ul>
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/onda_wellness.py">View 148-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Onda-1.11.0.apk">Download signed APK (1.6 MB)</a></p>
  </div>
</div>

## Northline — travel companion

<div class="showcase-detail">
  <div class="app-shot app-shot--detail"><img src="../assets/showcase/northline-travel.png" alt="Northline travel app"></div>
  <div>
    <span class="showcase-tag">APP BAR · STRUCTURED LAYOUTS</span>
    <h3>Every travel detail in the right place</h3>
    <p>Northline treats the boarding pass as the primary object and lets the itinerary recede behind it. Nested containers build the route, timeline and trip actions without a custom Android layout.</p>
    <ul>
      <li>Native-style top app bar and four-screen navigation</li>
      <li>Nested horizontal composition for flight information</li>
      <li>Action feedback and itinerary hierarchy</li>
    </ul>
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/northline_travel.py">View 170-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Northline-1.11.0.apk">Download signed APK (1.6 MB)</a></p>
  </div>
</div>

## Afterglow — music discovery

<div class="showcase-detail showcase-detail--reverse">
  <div class="app-shot app-shot--detail"><img src="../assets/showcase/afterglow-music.png" alt="Afterglow music app"></div>
  <div>
    <span class="showcase-tag">LOCAL IMAGES · MEDIA UI</span>
    <h3>An editorial listening surface</h3>
    <p>Afterglow pairs local artwork with a compact listening queue and warm, tactile actions. The image is packaged into Android resources while the same source renders immediately in the Previewer.</p>
    <ul>
      <li>Local image asset with cover fitting and rounded corners</li>
      <li>Composed feature card and track queue</li>
      <li>Interactive playback action and saved-library navigation</li>
    </ul>
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/afterglow_music.py">View 142-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Afterglow-1.11.0.apk">Download signed APK (3.2 MB)</a></p>
  </div>
</div>

## Verification record

The four programs are byte-for-byte the sources linked above. Each one was
transpiled and compiled by **ApkPy 1.11.0** into a signed release APK: R8
code shrinking and resource shrinking on, `minSdk` 24, `targetSdk` 35. After
shrinking, `aapt2` confirms that each APK still declares its package, its
`versionName` and the launcher Activity R8 could have removed. All four were
installed on a phone — a Xiaomi on Android 16 — and every tab was opened.

Until September 2026 this page handed out debug builds from the ApkPy 1.1.0
run. They are gone; the same four apps now look like this:

The 1.10.0 builds also fixed four icon names that were not in the catalogue.
ApkPy draws a plain circle for a name it does not know -- there is nothing else
it could draw -- so Lumen shipped with a circle where "Cards" should be. A test
now fails if any example or guide names an icon the catalogue does not have,
because the build already said so and a build prints a lot of lines.

The 1.11.0 builds fixed something worse. Each app builds three of its tabs
with a loop — `for page, title, copy in [...]:` — and the compiler dropped
that loop without a word: on a phone those tabs were empty, and Afterglow had
no tracks. The 1.10.0 APKs this page handed out had that fault. The loop is
translated now; every tab of the four apps has its title and text on a phone.

| App | Python source | 1.1.0 debug APK | 1.11.0 signed release |
| --- | ---: | ---: | ---: |
| Lumen | 144 lines | 5,642,176 bytes | **1,633,429 bytes** (3.5x smaller) |
| Onda | 148 lines | 5,644,411 bytes | **1,626,010 bytes** (3.5x smaller) |
| Northline | 170 lines | 5,648,389 bytes | **1,639,509 bytes** (3.4x smaller) |
| Afterglow | 142 lines | 7,418,424 bytes | **3,317,806 bytes** (2.2x smaller) |

Afterglow is the odd one because it packages 1,777,049 bytes of PNG artwork —
more than half of its APK. Take the picture out and it is the same size as the
other three.

The difference is not a different compiler. It is a release build instead of a
debug one: R8 removes the code the app never calls, unused resources go, and
the debug APK's debugging support is not there. Names are kept readable
(`-dontobfuscate`) so a crash report still means something.

| App | SHA-256 |
| --- | --- |
| Lumen | `97CCDB0B2F4C0B91B051FF18889CFF48F0FBFC410995DDF4990C04D7BE1BFC05` |
| Onda | `A6FD0B370E04F4374A75DF32EE88FFBE8C0FF2FFF1F33C5DE0B089D8D46BAF7C` |
| Northline | `BB786990E499C873348B9A5041E7B28156D5F9F1D9EFAAF8E39AAD6DF6A2D3DE` |
| Afterglow | `BB217DC55E0F81227A9B6DBDF04D9B76E8FEC44508A958F4C6B091E39FA3B54C` |

They are also in
[`SHA256SUMS.txt`](downloads/showcase/SHA256SUMS.txt).

!!! warning "Signed for this page, not for a store"

    The key was generated for these four demos. Android installs them without
    an "unsigned" warning, but they are not Play Store releases and they are
    not updates of the old debug builds — different application id, different
    key, so if you still have a July one installed both can sit side by side.

    These four were installed on a phone and every tab was opened; the
    pictures above are those screens. The source is above — build it and
    compare.

## Rebuild one app

1. Download its Python source.
2. Save it as `writehere.py` in an empty project directory.
3. Add any image asset referenced at the top of that source.
4. Run `python writehere.py` for the Previewer.
5. Run `apkpy build` and inspect the generated Java/XML.
6. Run `apkpy run` for a debug APK, `apkpy release` for a signed one, or
   compile the project in Android Studio.

The sources are kept under
[`examples/showcase/`](https://github.com/apkpy-project/repo-apkpy/tree/main/examples/showcase)
so each visual claim can be reviewed and regenerated instead of being treated
as a static mockup.

## Apps you know, rebuilt

A fair test of a UI library is to rebuild screens everybody has used and look
at them next to the originals. These four were rebuilt with ApkPy 1.11.0 and
photographed on the same phone, a Xiaomi on Android 16. Everything on them
works: a message you type is appended with its time, the tracks play with
their covers, shuffle and repeat light up, the like button turns red on its own
post and counts, a story advances when tapped, and choosing a ride changes the
button.

The photo feed is data: each post is a row built from components
(`virtual_collection(posts, row=post_row)`), recycled as it scrolls.

<div class="replica-strip">
  <figure><div class="app-shot"><img src="../assets/showcase/replica-chat-list.png" alt="A chat list with unread counts, rebuilt with ApkPy"></div><figcaption>Chat list: the unread count under the time</figcaption></figure>
  <figure><div class="app-shot"><img src="../assets/showcase/replica-chat.png" alt="A conversation with message bubbles, rebuilt with ApkPy"></div><figcaption>A conversation you can type into</figcaption></figure>
  <figure><div class="app-shot"><img src="../assets/showcase/replica-music-home.png" alt="A music app home screen with covers, rebuilt with ApkPy"></div><figcaption>Music home: covers packaged with the app</figcaption></figure>
  <figure><div class="app-shot"><img src="../assets/showcase/replica-music-player.png" alt="A music player playing a track, rebuilt with ApkPy"></div><figcaption>A player that plays, in the background too</figcaption></figure>
  <figure><div class="app-shot"><img src="../assets/showcase/replica-photo-feed.png" alt="A photo feed with a liked post, rebuilt with ApkPy"></div><figcaption>Feed: every post a row, the heart red on its own</figcaption></figure>
  <figure><div class="app-shot"><img src="../assets/showcase/replica-photo-story.png" alt="A full-screen story with progress bars, rebuilt with ApkPy"></div><figcaption>Stories that advance when tapped</figcaption></figure>
  <figure><div class="app-shot"><img src="../assets/showcase/replica-ride.jpg" alt="A ride sheet over a map, rebuilt with ApkPy"></div><figcaption>A ride sheet over a map (map data &copy; OpenStreetMap contributors)</figcaption></figure>
</div>

The source is [`examples/replicas/`](https://github.com/apkpy-project/repo-apkpy/tree/main/examples/replicas):
one `writehere.py`, and a `make_assets.py` that draws the pictures and writes
the three short tracks it uses. They are replicas made to test the library,
not affiliated with or endorsed by the companies whose apps they imitate; every
picture, name and sound in them is made up.
