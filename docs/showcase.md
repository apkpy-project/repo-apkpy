# Built with ApkPy

The showcase is a visual test of the library, not a set of static mockups. Each app below is an executable Python program that was opened in the Hot Previewer, tested through its primary action and navigation, and transpiled into native Android sources.

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
  </div>
</div>

## Validation snapshot

The current local review generated four Android projects with a total of sixteen
screen Activities. The wider 1.2.2 release-candidate validation completed 164
transpiler regression checks, 16 focused module checks and a real Gradle debug
APK build.

The runnable showcase sources are kept with the project examples so they can be
reviewed and regenerated instead of being treated as static mockups.
