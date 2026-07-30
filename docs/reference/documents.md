---
title: Rich documents API
description: Native ApkPy Markdown, rich text and tree view reference.
---

# Rich documents API

## `rich_text`

Accepts span dictionaries with `text`, `bold`, `italic`, `underline`, `strike`,
`code`, `color`, `size` and `link`.

## `markdown`

Supports headings, emphasis, links, inline and block code, quotes, lists,
checkboxes and dividers. Android renders native spans without a WebView.

## `tree_view`

Nodes use `key`, `title`, `subtitle`, `expanded` and recursive `children`.
Android maintains a flat RecyclerView dataset containing only visible rows.

Build a complete example in [Native knowledge app](../guides/knowledge-app.md)
or inspect [Rich text, Markdown and trees](../rich-content.md).
