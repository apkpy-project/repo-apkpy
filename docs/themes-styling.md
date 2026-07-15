# Themes and styling

## Global theme

~~~ python
from apkpy_lib import Theme

app_theme = Theme(
    mode="dark",
    primary="#8B5CF6",
    secondary="#22D3EE",
    background="#09090B",
    surface="#18181B",
    text="#FAFAFA",
    text_secondary="#A1A1AA",
    border="#3F3F46",
    error="#FCA5A5",
    success="#4ADE80",
    radius=16,
    spacing=14,
    font_family="sans-serif",
)
~~~

Pass the theme to <code>run()</code>:

~~~ python
run(start_screen=home, theme=app_theme)
~~~

The theme styles screens, text, buttons, inputs, containers, cards, lists, navigation, player surfaces and Android system bars.

## Design tokens

Reference normalized theme values from CSS:

~~~ css
body {
    background-color: var(--background);
    color: var(--text);
}

panel {
    background-color: var(--surface);
    border-color: var(--border);
    border-radius: var(--radius);
    padding: var(--spacing);
}

danger_action {
    background-color: var(--error);
}
~~~

Available tokens:

<code>primary</code>, <code>secondary</code>, <code>background</code>, <code>surface</code>, <code>text</code>, <code>text_secondary</code>, <code>on_primary</code>, <code>error</code>, <code>success</code>, <code>border</code>, <code>radius</code>, <code>spacing</code> and <code>font-family</code>.

## Cascade

Styles resolve in this order:

~~~ text
Theme defaults → component selector → component ID
~~~

~~~ css
button {
    border-radius: 12px;
}

save_button {
    background-color: var(--secondary);
}
~~~

The ID rule changes the background of <code>save_button</code> without losing the shared button radius.

## Useful properties

| Area | Properties |
| --- | --- |
| Colour | <code>color</code>, <code>background-color</code>, <code>border-color</code>, <code>pressed-color</code> |
| Type | <code>font-size</code>, <code>font-weight</code>, <code>font-family</code>, <code>text-align</code> |
| Shape | <code>border-width</code>, <code>border-radius</code>, <code>box-shadow</code> |
| Space | <code>padding</code>, <code>margin</code>, <code>gap</code> |
| Size | <code>width</code>, <code>height</code>, <code>min-width</code>, <code>max-width</code> |
| Layout | <code>display</code>, flex/grid properties, positioning and z-index |

## Responsive style rules

Use media rules when only style values change across widths:

~~~ css
content {
    padding: 18px;
}

@media (min-width: 600px) {
    content {
        padding: 32px;
        max-width: 900px;
    }
}
~~~

Use <code>responsive()</code> when the component arrangement itself must change.

## Animations

~~~ css
@keyframes appear {
    from { opacity: 0; scale: 0.96; }
    to   { opacity: 1; scale: 1; }
}

hero_card {
    animation: appear 320ms ease-out;
}
~~~

Keep motion brief and functional. Confirm the result in both the Previewer and Android build.
