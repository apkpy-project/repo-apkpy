"""Android parsing and code-generation helpers for incremental feeds."""

from __future__ import annotations

import ast


def _callback(transpiler, call, keyword, py_var):
    node = transpiler._kw_node(call.keywords, keyword)
    if isinstance(node, ast.Lambda):
        name = transpiler._unique_function_name(
            f"{py_var or 'collection'}_{keyword}"
        )
        statement = ast.Expr(value=node.body)
        ast.fix_missing_locations(statement)
        transpiler.functions[name] = {
            "args": [],
            "cmds": transpiler._parse_statements([statement]),
            "string_args": set(),
        }
        return name
    if isinstance(node, ast.Name):
        return node.id
    return transpiler._kw(call.keywords, keyword)


def parse_pagination(transpiler, call, comp, py_var):
    """Read pagination-only arguments from ``virtual_collection``."""
    comp["on_end_reached"] = _callback(
        transpiler, call, "on_end_reached", py_var
    )
    comp["on_refresh"] = _callback(
        transpiler, call, "on_refresh", py_var
    )
    try:
        comp["prefetch"] = max(
            0, min(
                100,
                int(transpiler._kw(call.keywords, "prefetch", 4) or 0),
            ),
        )
    except (TypeError, ValueError):
        comp["prefetch"] = 4


def is_paginated(comp):
    return bool(comp.get("on_end_reached") or comp.get("on_refresh"))


def emit_fields(lines, comp):
    """Emit Activity fields only for collections using pagination."""
    if not is_paginated(comp):
        return
    jv = comp["_java_var"]
    lines.extend([
        f"    private RecyclerView {jv};",
        f"    private boolean {jv}Loading = false;",
        f"    private boolean {jv}Refreshing = false;",
        f"    private boolean {jv}HasMore = true;",
    ])
    if comp.get("on_end_reached"):
        lines.append(
            f"    private android.widget.ProgressBar {jv}LoadingView;"
        )
    if comp.get("on_refresh"):
        lines.append(
            "    private androidx.swiperefreshlayout.widget."
            f"SwipeRefreshLayout {jv}Refresh;"
        )


def emit_mutation_fields(lines, comp):
    """Keep rollback history beside the dataset only in mutation-enabled apps."""
    jv = comp["_java_var"]
    lines.append(
        "    private final java.util.LinkedHashMap<String, "
        f"java.util.ArrayList<String>> {jv}Optimistic = "
        "new java.util.LinkedHashMap<>();"
    )
    lines.append(
        "    private final java.util.LinkedHashMap<String, String> "
        f"{jv}OptimisticKeys = new java.util.LinkedHashMap<>();"
    )


def emit_lookup_helpers(lines):
    """Emit the key/index lookup on its own.

    Finding a row by its key is what a mutation and a scroll both need, and a
    collection that only scrolls should not carry merge and rollback code it
    never calls.
    """
    lines.extend([
        "",
        "    private String _apkpyVcKey(String raw, String key) {",
        "        try {",
        "            org.json.JSONObject item = new org.json.JSONObject(raw);",
        "            if (item.has(key) && !item.isNull(key)) {",
        "                return String.valueOf(item.get(key));",
        "            }",
        "        } catch (Exception ignored) { }",
        "        return raw == null ? \"\" : raw;",
        "    }",
        "",
        "    private int _apkpyVcFind(java.util.ArrayList<String> items,",
        "            String key, String wanted) {",
        "        for (int index = 0; index < items.size(); index++) {",
        "            if (java.util.Objects.equals(",
        "                    _apkpyVcKey(items.get(index), key), wanted)) {",
        "                return index;",
        "            }",
        "        }",
        "        return -1;",
        "    }",
    ])


def emit_scroll_helper(lines):
    """Emit the one method that brings a row into view.

    ``ms`` comes from the shared motion table, so the phone and the desktop
    take the same time to get there -- and ``motion="none"`` jumps on both.
    A very long jump takes longer than ``ms``: the RecyclerView re-aims as it
    goes, because it cannot know a row's height before laying it out.
    """
    lines.extend([
        "",
        "    private void _apkpyScrollTo(RecyclerView view, int position, final int ms) {",
        "        if (view == null || position < 0) return;",
        "        RecyclerView.LayoutManager manager = view.getLayoutManager();",
        "        if (manager == null || ms <= 0) { view.scrollToPosition(position); return; }",
        "        androidx.recyclerview.widget.LinearSmoothScroller scroller =",
        "                new androidx.recyclerview.widget.LinearSmoothScroller(view.getContext()) {",
        "            @Override protected int calculateTimeForScrolling(int dx) { return ms; }",
        "            @Override protected int getVerticalSnapPreference() { return SNAP_TO_START; }",
        "        };",
        "        scroller.setTargetPosition(position);",
        "        manager.startSmoothScroll(scroller);",
        "    }",
    ])


def emit_mutation_helpers(lines):
    """Emit shared merge, diff and optimistic-history helpers once."""
    lines.extend([
        "",
        "    private String _apkpyVcMergeJson(String raw, String patch) {",
        "        try {",
        "            org.json.JSONObject base = new org.json.JSONObject(raw);",
        "            org.json.JSONObject changes = new org.json.JSONObject(patch);",
        "            java.util.Iterator<String> keys = changes.keys();",
        "            while (keys.hasNext()) {",
        "                String key = keys.next();",
        "                base.put(key, changes.get(key));",
        "            }",
        "            return base.toString();",
        "        } catch (Exception ignored) {",
        "            return patch;",
        "        }",
        "    }",
        "",
        "    private void _apkpyVcSnapshot(",
        "            java.util.LinkedHashMap<String, java.util.ArrayList<String>> history,",
        "            java.util.LinkedHashMap<String, String> historyKeys,",
        "            String token, String key, java.util.ArrayList<String> items) {",
        "        if (token != null && !token.isEmpty() && !history.containsKey(token)) {",
        "            history.put(token, new java.util.ArrayList<>(items));",
        "            historyKeys.put(token, key);",
        "        }",
        "    }",
        "",
        "    private String _apkpyVcLastToken(",
        "            java.util.LinkedHashMap<String, java.util.ArrayList<String>> history) {",
        "        String latest = null;",
        "        for (String token : history.keySet()) latest = token;",
        "        return latest;",
        "    }",
        "",
        "    private void _apkpyVcApplyDiff(",
        "            java.util.ArrayList<String> target,",
        "            java.util.ArrayList<String> next,",
        "            RecyclerView.Adapter<?> adapter, String key) {",
        "        java.util.ArrayList<String> previous = new java.util.ArrayList<>(target);",
        "        DiffUtil.DiffResult result = DiffUtil.calculateDiff(",
        "                new DiffUtil.Callback() {",
        "            @Override public int getOldListSize() { return previous.size(); }",
        "            @Override public int getNewListSize() { return next.size(); }",
        "            @Override public boolean areItemsTheSame(int oldPosition, int newPosition) {",
        "                return java.util.Objects.equals(",
        "                        _apkpyVcKey(previous.get(oldPosition), key),",
        "                        _apkpyVcKey(next.get(newPosition), key));",
        "            }",
        "            @Override public boolean areContentsTheSame(int oldPosition, int newPosition) {",
        "                return java.util.Objects.equals(",
        "                        previous.get(oldPosition), next.get(newPosition));",
        "            }",
        "        }, true);",
        "        target.clear();",
        "        target.addAll(next);",
        "        result.dispatchUpdatesTo(adapter);",
        "    }",
    ])


def emit_helpers(lines, comp):
    """Emit bounded request/finish helpers for one generated collection."""
    if not is_paginated(comp):
        return
    jv = comp["_java_var"]
    end_callback = comp.get("on_end_reached")
    refresh_callback = comp.get("on_refresh")
    prefetch = max(0, int(comp.get("prefetch", 4) or 0))

    lines.extend([
        "",
        f"    private void _apkpyFinish{jv.title()}Load(boolean hasMore) {{",
        f"        {jv}Loading = false;",
        f"        {jv}Refreshing = false;",
        f"        {jv}HasMore = hasMore;",
    ])
    if end_callback:
        lines.append(
            f"        if ({jv}LoadingView != null) "
            f"{jv}LoadingView.setVisibility(android.view.View.GONE);"
        )
    if refresh_callback:
        lines.append(
            f"        if ({jv}Refresh != null) {jv}Refresh.setRefreshing(false);"
        )
    lines.append("    }")

    if end_callback:
        lines.extend([
            "",
            f"    private void _apkpyRequest{jv.title()}Page() {{",
            f"        if ({jv}Loading || !{jv}HasMore) return;",
            f"        {jv}Loading = true;",
            f"        {jv}Refreshing = false;",
            f"        if ({jv}LoadingView != null) "
            f"{jv}LoadingView.setVisibility(android.view.View.VISIBLE);",
            f"        pythonCallback_{end_callback}();",
            "    }",
            "",
            f"    private void _apkpyMaybeLoad{jv.title()}Page() {{",
            f"        if ({jv} == null || {jv}Loading || !{jv}HasMore) return;",
            f"        RecyclerView.LayoutManager manager = {jv}.getLayoutManager();",
            "        int lastVisible = -1;",
            "        if (manager instanceof LinearLayoutManager) {",
            "            lastVisible = ((LinearLayoutManager) manager)"
            ".findLastVisibleItemPosition();",
            "        }",
            f"        int total = {jv}_items == null ? 0 : {jv}_items.size();",
            f"        if (total == 0 || lastVisible >= "
            f"Math.max(0, total - 1 - {prefetch})) {{",
            f"            _apkpyRequest{jv.title()}Page();",
            "        }",
            "    }",
        ])

    if refresh_callback:
        lines.extend([
            "",
            f"    private void _apkpyRequest{jv.title()}Refresh() {{",
            f"        if ({jv}Loading) {{",
            f"            if ({jv}Refresh != null) "
            f"{jv}Refresh.setRefreshing({jv}Refreshing);",
            "            return;",
            "        }",
            f"        {jv}Loading = true;",
            f"        {jv}Refreshing = true;",
            f"        {jv}HasMore = true;",
            f"        if ({jv}Refresh != null) {jv}Refresh.setRefreshing(true);",
            f"        pythonCallback_{refresh_callback}();",
            "    }",
        ])


def emit_setup(lines, indent, comp):
    """Attach native scroll and refresh listeners during ``onCreate``."""
    if not is_paginated(comp):
        return
    jv = comp["_java_var"]
    if comp.get("on_end_reached"):
        lines.extend([
            f"{indent}{jv}LoadingView = findViewById(R.id.{jv}_loading);",
            f"{indent}{jv}.addOnScrollListener(new RecyclerView.OnScrollListener() {{",
            f"{indent}    @Override public void onScrolled("
            "RecyclerView recyclerView, int dx, int dy) {",
            f"{indent}        _apkpyMaybeLoad{jv.title()}Page();",
            f"{indent}    }}",
            f"{indent}}});",
            f"{indent}{jv}.post("
            f"() -> _apkpyMaybeLoad{jv.title()}Page());",
        ])
    if comp.get("on_refresh"):
        lines.extend([
            f"{indent}{jv}Refresh = findViewById(R.id.{jv}_refresh);",
            f"{indent}{jv}Refresh.setColorSchemeResources("
            "com.google.android.material.R.color.design_default_color_primary);",
            f"{indent}{jv}Refresh.setOnRefreshListener("
            f"this::_apkpyRequest{jv.title()}Refresh);",
        ])


def layout_xml(comp, jv, indent, height, weight_attr, margin_xml, bg_attr):
    """Return a paginated collection wrapper, or ``None`` for legacy output."""
    if not is_paginated(comp):
        return None

    child = indent + "    "
    inner = child + "    "
    lines = [
        f"{indent}<FrameLayout",
        f'{indent}    android:id="@+id/{jv}_feed"',
        f'{indent}    android:layout_width="match_parent"',
        f'{indent}    android:layout_height="{height}"'
        f"{weight_attr}{margin_xml}>",
    ]

    if comp.get("on_refresh"):
        lines.extend([
            f"{child}<androidx.swiperefreshlayout.widget.SwipeRefreshLayout",
            f'{child}    android:id="@+id/{jv}_refresh"',
            f'{child}    android:layout_width="match_parent"',
            f'{child}    android:layout_height="match_parent">',
        ])
        recycler_indent = inner
    else:
        recycler_indent = child

    lines.extend([
        f"{recycler_indent}<androidx.recyclerview.widget.RecyclerView",
        f'{recycler_indent}    android:id="@+id/{jv}"',
        f'{recycler_indent}    android:layout_width="match_parent"',
        f'{recycler_indent}    android:layout_height="match_parent"{bg_attr}',
        f'{recycler_indent}    android:clipToPadding="false"',
        f'{recycler_indent}    android:nestedScrollingEnabled="true"',
        f'{recycler_indent}    android:overScrollMode="never" />',
    ])

    if comp.get("on_refresh"):
        lines.append(
            f"{child}</androidx.swiperefreshlayout.widget.SwipeRefreshLayout>"
        )
    if comp.get("on_end_reached"):
        lines.extend([
            f"{child}<ProgressBar",
            f'{child}    android:id="@+id/{jv}_loading"',
            f'{child}    style="?android:attr/progressBarStyleSmall"',
            f'{child}    android:layout_width="wrap_content"',
            f'{child}    android:layout_height="wrap_content"',
            f'{child}    android:layout_gravity="bottom|center_horizontal"',
            f'{child}    android:layout_marginBottom="8dp"',
            f'{child}    android:visibility="gone" />',
        ])
    lines.extend([f"{indent}</FrameLayout>", ""])
    return lines


__all__ = [
    "emit_fields",
    "emit_helpers",
    "emit_lookup_helpers",
    "emit_mutation_fields",
    "emit_mutation_helpers",
    "emit_scroll_helper",
    "emit_setup",
    "is_paginated",
    "layout_xml",
    "parse_pagination",
]
