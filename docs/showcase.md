# Built with ApkPy

The showcase is a visual test of the library, not a set of static mockups. Each app below is an executable Python program that was opened in the Hot Previewer, tested through its primary action and navigation, and transpiled into native Android sources.

Every case study now includes its complete application declaration and a
checksum-verified debug APK. The links expose app code only — not the private
source of the ApkPy compiler.

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
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/lumen_finance.py">View 144-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Lumen-debug.apk">Download verified debug APK</a></p>
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
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/onda_wellness.py">View 148-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Onda-debug.apk">Download verified debug APK</a></p>
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
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/northline_travel.py">View 170-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Northline-debug.apk">Download verified debug APK</a></p>
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
    <p class="showcase-actions"><a class="md-button" href="https://github.com/apkpy-project/repo-apkpy/blob/main/examples/showcase/afterglow_music.py">View 142-line source</a> <a class="md-button md-button--primary" href="../downloads/showcase/Afterglow-debug.apk">Download verified debug APK</a></p>
  </div>
</div>

## Verification record

The four checked programs are byte-for-byte identical to the sources used by a
clean-wheel Android verification run. That run generated and compiled four
projects, parsed 108 XML files, inspected 24 Java files and opened every one of
the 16 Activities on the same Pixel emulator without a fatal runtime exception.

| App | Python source | Debug APK | SHA-256 |
| --- | ---: | ---: | --- |
| Lumen | 144 lines | 5,642,176 bytes | `29725228d821…1bff1b8` |
| Onda | 148 lines | 5,644,411 bytes | `7686cd1222f5…be62d1` |
| Northline | 170 lines | 5,648,389 bytes | `3e701769b315…bc50bd7` |
| Afterglow | 142 lines | 7,418,424 bytes | `ca816cc90b18…89dce` |

Full hashes are published in
[`SHA256SUMS.txt`](downloads/showcase/SHA256SUMS.txt). Verification records the
exact tested artifact; it does not make a debug APK a signed production release.

!!! warning "Use the APKs only on a test device"

    These are historical debug builds from the verified ApkPy 1.1.0 showcase
    run. They are provided so the screenshots and source can be independently
    checked. Rebuild the unchanged source with the current ApkPy release for a
    new project, application ID and signing identity.

## Rebuild one app

1. Download its Python source.
2. Save it as `writehere.py` in an empty project directory.
3. Add any image asset referenced at the top of that source.
4. Run `python writehere.py` for the Previewer.
5. Run `apkpy build` and inspect the generated Java/XML.
6. Run `apkpy run` or compile the project in Android Studio.

The sources are kept under
[`examples/showcase/`](https://github.com/apkpy-project/repo-apkpy/tree/main/examples/showcase)
so each visual claim can be reviewed and regenerated instead of being treated
as a static mockup.
