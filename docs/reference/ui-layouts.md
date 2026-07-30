---
title: UI and layout API
description: ApkPy screens, components, layouts, themes and navigation reference.
---

# UI and layout API

## Structure

| API | Purpose |
| --- | --- |
| `Screen(id, background_image=None, scroll=False)` | define an Android screen/Activity |
| `run(start_screen=None, theme=None)` | start the Previewer and set the app entry |
| `Theme(...)` | global colors, typography, radius and component defaults |
| `device(name)` | Previewer device preset or responsive mode |

## Components

`label`, `button`, `inputs`, `input_field`, `image`, `video`, `avatar`,
`container`, `card`, `card_action`, `list_view`, `carousel`, `grid`, `spinner`,
`skeleton`, `empty_state` and `error_state`.

Common component operations are `get_value()`, `set_value(value)`, `show()` and
`hide()`. Images also expose source/effect operations; videos expose playback,
seek, speed and mute operations.

## Layout

| API | Important arguments |
| --- | --- |
| `row(*children)` | horizontal composition |
| `column(*children)` | vertical composition |
| `responsive(...)` | mobile, tablet and landscape alternatives |
| `container(...)` | styled parent surface |
| `card(...)` | semantic grouped content and actions |

## Navigation and chrome

`on_click_navigate`, `bottom_nav`, `BottomNav`, `app_bar`,
`sliver_app_bar`, `action` and `mini_player`.

## Overlays and feedback

`bottom_sheet`, `modal`, `menu`, `popup_menu`, `context_menu`, `snackbar`,
`tooltip`, `date_picker`, `time_picker`, `toast`, `alert` and `confirm`.

Read [Components and layouts](../ui-components.md),
[Themes and styling](../themes-styling.md) and
[Screens and navigation](../navigation.md) for complete examples.
