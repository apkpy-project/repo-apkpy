# Built with ApkPy

The showcase is a visual test of the library, not a set of static mockups. Each app below is an executable Python program that was opened in the Hot Previewer, tested through its primary action and navigation, and transpiled into native Android sources.

Every case study includes its complete application declaration and a
**signed release APK built by the published ApkPy 1.9.0** — R8 shrinking on,
`targetSdk` 35, around 1.6 MB. Install one, then read the source that produced
it. The links expose app code only — not the private source of the ApkPy
compiler.

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
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/lumen_finance.py">View 144-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Lumen-1.9.0.apk">Download signed APK (1.6 MB)</a></p>
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
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/onda_wellness.py">View 148-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Onda-1.9.0.apk">Download signed APK (1.6 MB)</a></p>
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
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/northline_travel.py">View 170-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Northline-1.9.0.apk">Download signed APK (1.6 MB)</a></p>
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
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/afterglow_music.py">View 142-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Afterglow-1.9.0.apk">Download signed APK (3.2 MB)</a></p>
  </div>
</div>

## Verification record

The four programs are byte-for-byte the sources linked above. Each one was
transpiled and compiled by the **published ApkPy 1.9.0 wheel** — the file
`pip install apkpy==1.9.0` downloads, installed into an empty virtual
environment — into a signed release APK: R8 code shrinking and resource
shrinking on, `minSdk` 24, `targetSdk` 35. After shrinking, `aapt2` confirms
that each APK still declares its package, its `versionName` and the launcher
Activity R8 could have removed, and all four install on an Android emulator.

Until September 2026 this page handed out debug builds from the ApkPy 1.1.0
run. They are gone; the same four apps now look like this:

| App | Python source | 1.1.0 debug APK | 1.9.0 signed release |
| --- | ---: | ---: | ---: |
| Lumen | 144 lines | 5,642,176 bytes | **1,629,609 bytes** (3.5x smaller) |
| Onda | 148 lines | 5,644,411 bytes | **1,621,930 bytes** (3.5x smaller) |
| Northline | 170 lines | 5,648,389 bytes | **1,635,757 bytes** (3.5x smaller) |
| Afterglow | 142 lines | 7,418,424 bytes | **3,309,750 bytes** (2.2x smaller) |

Afterglow is the odd one because it packages 1,777,049 bytes of PNG artwork —
more than half of its APK. Take the picture out and it is the same size as the
other three.

The difference is not a different compiler. It is a release build instead of a
debug one: R8 removes the code the app never calls, unused resources go, and
the debug APK's debugging support is not there. Names are kept readable
(`-dontobfuscate`) so a crash report still means something.

| App | SHA-256 |
| --- | --- |
| Lumen | `FCD8ED4CC416BDC9F1D330450B57C2217AE53B537EA5797E8E1F0A248FFBDBC1` |
| Onda | `8F598DA9F51816F2E09A559174AE2A2A93B826596738A844F6D0FC8FD1B78464` |
| Northline | `67EBE846A497AFFA02AE2E9DCDB70A6591D1CB4FD83D2D223B6AA160A303860D` |
| Afterglow | `C599AC20D163E6935D337A6F9D8065C3434F4D9948162B363E36B9A2E305F582` |

They are also in
[`SHA256SUMS.txt`](downloads/showcase/SHA256SUMS.txt).

!!! warning "Signed for this page, not for a store"

    The key was generated for these four demos. Android installs them without
    an "unsigned" warning, but they are not Play Store releases and they are
    not updates of the old debug builds — different application id, different
    key, so if you still have a July one installed both can sit side by side.

    What these four builds did **not** get: a run on a phone. `aapt2` shows the
    APK is complete and Android installs it; neither proves the screens behave.
    The source is above — build it and see.

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
