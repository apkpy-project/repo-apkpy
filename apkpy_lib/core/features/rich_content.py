"""Android parser and native views for rich ApkPy documents."""

from __future__ import annotations

import ast
import base64
import json


COMPONENT_NAMES = ("markdown", "rich_text", "tree_view")


def _kw_node(transpiler, call, name):
    return transpiler._kw_node(call.keywords, name)


def _kw(transpiler, call, name, default=None):
    return transpiler._kw(call.keywords, name, default)


def _literal(transpiler, node, fallback):
    if isinstance(node, ast.Name):
        if node.id in transpiler.list_assignments:
            node = transpiler.list_assignments[node.id]
        elif node.id in transpiler.dict_assignments:
            node = transpiler.dict_assignments[node.id]
        elif node.id in transpiler.string_constants:
            return transpiler.string_constants[node.id]
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return fallback


def _normalise_spans(value):
    if isinstance(value, str):
        value = [{"text": value}]
    if not isinstance(value, (list, tuple)):
        return []
    result = []
    for item in value:
        if isinstance(item, str):
            result.append({"text": item})
            continue
        if not isinstance(item, dict):
            continue
        span = {
            "text": str(item.get("text", "")),
            "bold": bool(item.get("bold", False)),
            "italic": bool(item.get("italic", False)),
            "underline": bool(item.get("underline", False)),
            "strike": bool(item.get("strike", False)),
            "code": bool(item.get("code", False)),
        }
        for key in ("color", "link"):
            if item.get(key):
                span[key] = str(item[key])
        if item.get("size") is not None:
            try:
                span["size"] = max(8, min(72, int(item["size"])))
            except (TypeError, ValueError):
                pass
        result.append(span)
    return result


def _normalise_nodes(value, expand_depth=1, depth=0, path=""):
    if not isinstance(value, (list, tuple)) or depth > 24:
        return []
    result = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            item = {"title": item}
        if not isinstance(item, dict):
            continue
        node_path = f"{path}.{index}" if path else str(index)
        children = _normalise_nodes(
            item.get("children", []), expand_depth, depth + 1, node_path
        )
        expanded = (
            bool(item["expanded"])
            if "expanded" in item
            else bool(children and depth < expand_depth)
        )
        result.append({
            "key": str(item.get("key", node_path)),
            "title": str(item.get("title", "")),
            "subtitle": str(item.get("subtitle", "")),
            "expanded": expanded,
            "children": children,
        })
    return result


def parse_component(transpiler, comp_type, call, comp):
    """Populate a normal component dictionary from a rich-content call."""
    comp["id"] = _kw(transpiler, call, "id")
    comp["selectable"] = bool(_kw(transpiler, call, "selectable", True))

    first = call.args[0] if call.args else None
    if comp_type == "markdown":
        source_node = first or _kw_node(transpiler, call, "source")
        comp["source"] = str(_literal(transpiler, source_node, ""))
        return

    if comp_type == "rich_text":
        spans_node = first or _kw_node(transpiler, call, "spans")
        comp["spans"] = _normalise_spans(
            _literal(transpiler, spans_node, [])
        )
        return

    nodes_node = first or _kw_node(transpiler, call, "nodes")
    try:
        expand_depth = max(
            0, min(12, int(_kw(transpiler, call, "expand_depth", 1)))
        )
    except (TypeError, ValueError):
        expand_depth = 1
    try:
        row_height = max(
            48, min(96, int(_kw(transpiler, call, "row_height", 58)))
        )
    except (TypeError, ValueError):
        row_height = 58
    comp["expand_depth"] = expand_depth
    comp["row_height"] = row_height
    comp["nodes"] = _normalise_nodes(
        _literal(transpiler, nodes_node, []), expand_depth=expand_depth
    )


def encoded_payload(comp, *, text_color, secondary_color, accent_color,
                    background_color, border_color, border_width,
                    radius, padding, font_size, copy_code=False):
    payload = {
        "kind": comp["comp_type"],
        "selectable": bool(comp.get("selectable", True)),
        "textColor": text_color,
        "secondaryColor": secondary_color,
        "accentColor": accent_color,
        "backgroundColor": background_color,
        "borderColor": border_color,
        "borderWidth": max(0, int(border_width or 0)),
        "radius": max(0, int(radius or 0)),
        "padding": [max(0, int(value or 0)) for value in padding],
        "fontSize": max(8, min(72, int(font_size or 14))),
    }
    if comp["comp_type"] == "markdown":
        payload["source"] = comp.get("source", "")
        # Only written when asked for: the payload is embedded in the layout
        # XML, so a key nobody uses would change every existing app's build.
        if copy_code:
            payload["copyCode"] = True
    elif comp["comp_type"] == "rich_text":
        payload["spans"] = comp.get("spans", [])
    else:
        payload["nodes"] = comp.get("nodes", [])
        payload["rowHeight"] = max(48, int(comp.get("row_height", 58)))
    raw = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def generate_rich_content_view_java(package):
    return _RICH_CONTENT_VIEW_JAVA.replace("__PACKAGE__", package)


def generate_tree_view_java(package):
    return _TREE_VIEW_JAVA.replace("__PACKAGE__", package)


_RICH_CONTENT_VIEW_JAVA = r'''package __PACKAGE__;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.Spannable;
import android.text.SpannableStringBuilder;
import android.text.method.LinkMovementMethod;
import android.text.style.AbsoluteSizeSpan;
import android.text.style.BackgroundColorSpan;
import android.text.style.ForegroundColorSpan;
import android.text.style.LeadingMarginSpan;
import android.text.style.RelativeSizeSpan;
import android.text.style.StrikethroughSpan;
import android.text.style.ClickableSpan;
import android.text.style.StyleSpan;
import android.text.style.TypefaceSpan;
import android.text.style.UnderlineSpan;
import android.text.style.URLSpan;
import android.text.TextPaint;
import android.util.AttributeSet;
import android.util.Base64;
import android.util.TypedValue;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class ApkpyRichContentView extends LinearLayout {
    private static final Pattern INLINE = Pattern.compile(
        "\\[([^\\]]+)\\]\\(([^)]+)\\)|\\*\\*([^*]+)\\*\\*|~~([^~]+)~~|`([^`]+)`|\\*([^*]+)\\*"
    );
    private static final Pattern HEADING = Pattern.compile("^(#{1,6})\\s+(.*)$");
    private static final Pattern QUOTE = Pattern.compile("^\\s*>\\s?(.*)$");
    private static final Pattern CHECK = Pattern.compile(
        "^\\s*[-*]\\s+\\[([ xX])\\]\\s+(.*)$"
    );
    private static final Pattern ORDERED = Pattern.compile(
        "^\\s*(\\d+)[.)]\\s+(.*)$"
    );
    private static final Pattern BULLET = Pattern.compile("^\\s*[-*+]\\s+(.*)$");

    public ApkpyRichContentView(Context context) {
        this(context, null);
    }

    public ApkpyRichContentView(Context context, AttributeSet attrs) {
        super(context, attrs);
        setOrientation(VERTICAL);
        setClipToPadding(false);
        post(this::renderPayload);
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private int color(String value, int fallback) {
        try { return Color.parseColor(value); }
        catch (Exception ignored) { return fallback; }
    }

    private JSONObject payload() throws Exception {
        CharSequence description = getContentDescription();
        Object value = description == null ? getTag() : description;
        String encoded = value == null ? "" : String.valueOf(value);
        if (encoded.startsWith("apkpy-rich:")) {
            encoded = encoded.substring("apkpy-rich:".length());
        }
        byte[] bytes = Base64.decode(encoded, Base64.NO_WRAP);
        return new JSONObject(new String(bytes, StandardCharsets.UTF_8));
    }

    private void renderPayload() {
        removeAllViews();
        try {
            JSONObject data = payload();
            setContentDescription(null);
            int textColor = color(data.optString("textColor"), Color.WHITE);
            int secondary = color(data.optString("secondaryColor"), 0xFF9CA3AF);
            int accent = color(data.optString("accentColor"), 0xFF6750A4);
            int background = color(data.optString("backgroundColor"), Color.TRANSPARENT);
            int border = color(data.optString("borderColor"), Color.TRANSPARENT);
            int borderWidth = data.optInt("borderWidth", 0);
            int radius = data.optInt("radius", 0);
            JSONArray padding = data.optJSONArray("padding");

            GradientDrawable surface = new GradientDrawable();
            surface.setColor(background);
            surface.setCornerRadius(dp(radius));
            if (borderWidth > 0) surface.setStroke(dp(borderWidth), border);
            setBackground(surface);
            if (padding != null && padding.length() == 4) {
                setPadding(
                    dp(padding.optInt(3)), dp(padding.optInt(0)),
                    dp(padding.optInt(1)), dp(padding.optInt(2))
                );
            }

            TextView body = new TextView(getContext());
            body.setTextColor(textColor);
            body.setTextSize(TypedValue.COMPLEX_UNIT_SP, data.optInt("fontSize", 14));
            body.setLineSpacing(dp(3), 1.08f);
            body.setTextIsSelectable(data.optBoolean("selectable", true));
            body.setHighlightColor((accent & 0x00FFFFFF) | 0x44000000);
            body.setMovementMethod(LinkMovementMethod.getInstance());
            body.setLinksClickable(true);

            SpannableStringBuilder output = new SpannableStringBuilder();
            if ("markdown".equals(data.optString("kind"))) {
                appendMarkdown(
                    output, data.optString("source"), textColor, secondary, accent,
                    getResources().getDisplayMetrics().density,
                    data.optBoolean("copyCode", false)
                );
            } else {
                appendRich(output, data.optJSONArray("spans"), textColor, accent);
            }
            body.setText(output);
            addView(body, new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            ));
        } catch (Exception error) {
            TextView fallback = new TextView(getContext());
            fallback.setText("Unable to render rich content");
            fallback.setTextColor(0xFFB3261E);
            addView(fallback);
        }
    }

    private void appendRich(SpannableStringBuilder out, JSONArray spans,
                            int defaultColor, int accent) {
        if (spans == null) return;
        for (int index = 0; index < spans.length(); index++) {
            JSONObject span = spans.optJSONObject(index);
            if (span == null) continue;
            int start = out.length();
            out.append(span.optString("text"));
            int end = out.length();
            if (start == end) continue;
            if (span.optBoolean("bold")) {
                out.setSpan(ApkpyWeight.boldSpan(), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            if (span.optBoolean("italic")) {
                out.setSpan(new StyleSpan(Typeface.ITALIC), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            if (span.optBoolean("underline")) {
                out.setSpan(new UnderlineSpan(), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            if (span.optBoolean("strike")) {
                out.setSpan(new StrikethroughSpan(), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            if (span.optBoolean("code")) {
                out.setSpan(new TypefaceSpan("monospace"), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new BackgroundColorSpan(0x33222222), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            if (span.has("size")) {
                out.setSpan(
                    new AbsoluteSizeSpan(span.optInt("size", 14), true),
                    start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE
                );
            }
            out.setSpan(
                new ForegroundColorSpan(color(span.optString("color"), defaultColor)),
                start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE
            );
            String link = span.optString("link");
            if (!link.isEmpty()) {
                out.setSpan(new URLSpan(link), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new ForegroundColorSpan(accent), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
        }
    }

    /** Markdown com estilos, para quem nao usa esta View inteira -- uma linha
     *  de virtual_collection, por exemplo. Uma implementacao so': duas seriam
     *  duas maneiras de desenhar um bloco de codigo. */
    public static CharSequence apkpyMarkdown(Context context, String source,
                                             int textColor, int secondary, int accent,
                                             boolean copyCode) {
        SpannableStringBuilder out = new SpannableStringBuilder();
        float density = context == null ? 1f
            : context.getResources().getDisplayMetrics().density;
        appendMarkdown(out, source == null ? "" : source,
                       textColor, secondary, accent, density, copyCode);
        // O markdown termina cada linha com \n; o ultimo deixa uma linha vazia
        // por baixo de cada mensagem, que numa conversa se ve logo.
        int end = out.length();
        while (end > 0 && out.charAt(end - 1) == '\n') end--;
        return out.subSequence(0, end);
    }

    private static void appendMarkdown(SpannableStringBuilder out, String source,
                                int textColor, int secondary, int accent,
                                float density, boolean copyCode) {
        boolean codeBlock = false;
        int blockStart = -1;
        String[] lines = source.replace("\r\n", "\n").replace('\r', '\n').split("\n", -1);
        for (String raw : lines) {
            String trimmed = raw.trim();
            if (trimmed.startsWith("```")) {
                if (codeBlock && copyCode && blockStart >= 0) {
                    appendCopyLabel(out, blockStart, accent);
                }
                codeBlock = !codeBlock;
                blockStart = codeBlock ? out.length() : -1;
                continue;
            }
            int lineStart = out.length();
            if (codeBlock) {
                out.append(raw).append('\n');
                int lineEnd = out.length();
                out.setSpan(new TypefaceSpan("monospace"), lineStart, lineEnd, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new BackgroundColorSpan(0x33222222), lineStart, lineEnd, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                continue;
            }

            Matcher heading = HEADING.matcher(raw);
            if (heading.matches()) {
                appendInline(out, heading.group(2), textColor, accent);
                out.append('\n');
                int end = out.length();
                int level = heading.group(1).length();
                float factor = level == 1 ? 1.75f : level == 2 ? 1.5f :
                    level == 3 ? 1.3f : level == 4 ? 1.15f : level == 5 ? 1.05f : 1f;
                out.setSpan(ApkpyWeight.boldSpan(), lineStart, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new RelativeSizeSpan(factor), lineStart, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                continue;
            }
            if (trimmed.equals("---") || trimmed.equals("***") || trimmed.equals("___")) {
                out.append("────────────────").append('\n');
                out.setSpan(new ForegroundColorSpan(secondary), lineStart, out.length(), Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                continue;
            }
            Matcher quote = QUOTE.matcher(raw);
            if (quote.matches()) {
                out.append("▌ ");
                appendInline(out, quote.group(1), textColor, accent);
                out.append('\n');
                out.setSpan(new ForegroundColorSpan(secondary), lineStart, out.length(), Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new LeadingMarginSpan.Standard(Math.round(8f * density)), lineStart, out.length(), Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                continue;
            }
            Matcher check = CHECK.matcher(raw);
            if (check.matches()) {
                out.append(check.group(1).equalsIgnoreCase("x") ? "[x] " : "[ ] ");
                appendInline(out, check.group(2), textColor, accent);
                out.append('\n');
                out.setSpan(new ForegroundColorSpan(accent), lineStart, Math.min(lineStart + 3, out.length()), Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                continue;
            }
            Matcher ordered = ORDERED.matcher(raw);
            if (ordered.matches()) {
                out.append(ordered.group(1)).append(". ");
                appendInline(out, ordered.group(2), textColor, accent);
                out.append('\n');
                out.setSpan(new ForegroundColorSpan(accent), lineStart, Math.min(lineStart + ordered.group(1).length() + 1, out.length()), Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new LeadingMarginSpan.Standard(Math.round(8f * density), Math.round(24f * density)), lineStart, out.length(), Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                continue;
            }
            Matcher bullet = BULLET.matcher(raw);
            if (bullet.matches()) {
                out.append("• ");
                appendInline(out, bullet.group(1), textColor, accent);
                out.append('\n');
                out.setSpan(new ForegroundColorSpan(accent), lineStart, Math.min(lineStart + 1, out.length()), Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new LeadingMarginSpan.Standard(Math.round(8f * density), Math.round(20f * density)), lineStart, out.length(), Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                continue;
            }
            appendInline(out, raw, textColor, accent);
            out.append('\n');
        }
    }

    /** Puts a tappable "Copy" under a fenced block, holding that block's text. */
    private static void appendCopyLabel(SpannableStringBuilder out, int blockStart,
                                        int accent) {
        final String snippet = out.subSequence(blockStart, out.length()).toString();
        int labelStart = out.length();
        out.append("⧉ Copy");
        int labelEnd = out.length();
        out.append('\n');
        out.setSpan(new ClickableSpan() {
            @Override public void onClick(View widget) {
                Context context = widget.getContext();
                android.content.ClipboardManager clipboard =
                    (android.content.ClipboardManager) context.getSystemService(
                        Context.CLIPBOARD_SERVICE);
                if (clipboard == null) return;
                clipboard.setPrimaryClip(
                    android.content.ClipData.newPlainText("code", snippet));
                // Android 13 shows its own confirmation for every copy; a
                // second one is the app talking over the system.
                if (android.os.Build.VERSION.SDK_INT < 33) {
                    android.widget.Toast.makeText(
                        context, "Copied", android.widget.Toast.LENGTH_SHORT).show();
                }
            }

            @Override public void updateDrawState(TextPaint paint) {
                paint.setColor(accent);
                paint.setUnderlineText(false);
            }
        }, labelStart, labelEnd, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
        out.setSpan(new RelativeSizeSpan(0.85f), labelStart, labelEnd,
                    Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
    }

    private static void appendInline(SpannableStringBuilder out, String line,
                              int textColor, int accent) {
        Matcher matcher = INLINE.matcher(line);
        int cursor = 0;
        while (matcher.find()) {
            if (matcher.start() > cursor) out.append(line, cursor, matcher.start());
            int start = out.length();
            String value;
            int style = 0;
            String link = null;
            if (matcher.group(1) != null) {
                value = matcher.group(1); link = matcher.group(2);
            } else if (matcher.group(3) != null) {
                value = matcher.group(3); style = 1;
            } else if (matcher.group(4) != null) {
                value = matcher.group(4); style = 2;
            } else if (matcher.group(5) != null) {
                value = matcher.group(5); style = 3;
            } else {
                value = matcher.group(6); style = 4;
            }
            out.append(value);
            int end = out.length();
            if (style == 1) out.setSpan(ApkpyWeight.boldSpan(), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            if (style == 2) out.setSpan(new StrikethroughSpan(), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            if (style == 3) {
                out.setSpan(new TypefaceSpan("monospace"), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new BackgroundColorSpan(0x33222222), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            if (style == 4) out.setSpan(new StyleSpan(Typeface.ITALIC), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            if (link != null) {
                out.setSpan(new URLSpan(link), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                out.setSpan(new ForegroundColorSpan(accent), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            } else {
                out.setSpan(new ForegroundColorSpan(textColor), start, end, Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
            }
            cursor = matcher.end();
        }
        if (cursor < line.length()) out.append(line, cursor, line.length());
    }
}
'''


_TREE_VIEW_JAVA = r'''package __PACKAGE__;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.util.AttributeSet;
import android.util.Base64;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

public final class ApkpyTreeView extends RecyclerView {
    private final ArrayList<Node> roots = new ArrayList<>();
    private final ArrayList<Row> visible = new ArrayList<>();
    private TreeAdapter adapter;
    private int textColor = Color.WHITE;
    private int secondaryColor = 0xFF9CA3AF;
    private int accentColor = 0xFF6750A4;
    private int backgroundColor = Color.TRANSPARENT;
    private int borderColor = Color.TRANSPARENT;
    private int rowHeight = 58;
    private String selectedKey = "";

    public ApkpyTreeView(Context context) {
        this(context, null);
    }

    public ApkpyTreeView(Context context, AttributeSet attrs) {
        super(context, attrs);
        setLayoutManager(new LinearLayoutManager(context));
        setItemAnimator(null);
        setHasFixedSize(false);
        setClipToPadding(false);
        post(this::loadPayload);
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private int color(String value, int fallback) {
        try { return Color.parseColor(value); }
        catch (Exception ignored) { return fallback; }
    }

    private void loadPayload() {
        try {
            CharSequence description = getContentDescription();
            Object value = description == null ? getTag() : description;
            String encoded = value == null ? "" : String.valueOf(value);
            if (encoded.startsWith("apkpy-tree:")) {
                encoded = encoded.substring("apkpy-tree:".length());
            }
            JSONObject data = new JSONObject(new String(
                Base64.decode(encoded, Base64.NO_WRAP), StandardCharsets.UTF_8
            ));
            setContentDescription(null);
            textColor = color(data.optString("textColor"), textColor);
            secondaryColor = color(data.optString("secondaryColor"), secondaryColor);
            accentColor = color(data.optString("accentColor"), accentColor);
            backgroundColor = color(data.optString("backgroundColor"), backgroundColor);
            borderColor = color(data.optString("borderColor"), borderColor);
            rowHeight = data.optInt("rowHeight", rowHeight);

            int borderWidth = data.optInt("borderWidth", 0);
            int radius = data.optInt("radius", 0);
            GradientDrawable surface = new GradientDrawable();
            surface.setColor(backgroundColor);
            surface.setCornerRadius(dp(radius));
            if (borderWidth > 0) surface.setStroke(dp(borderWidth), borderColor);
            setBackground(surface);
            JSONArray padding = data.optJSONArray("padding");
            if (padding != null && padding.length() == 4) {
                setPadding(
                    dp(padding.optInt(3)), dp(padding.optInt(0)),
                    dp(padding.optInt(1)), dp(padding.optInt(2))
                );
            }

            roots.clear();
            readNodes(data.optJSONArray("nodes"), roots);
            rebuildVisible();
            adapter = new TreeAdapter();
            adapter.setHasStableIds(true);
            setAdapter(adapter);
        } catch (Exception ignored) {
            roots.clear();
            visible.clear();
        }
    }

    private void readNodes(JSONArray source, List<Node> target) {
        if (source == null) return;
        for (int index = 0; index < source.length(); index++) {
            JSONObject value = source.optJSONObject(index);
            if (value == null) continue;
            Node node = new Node();
            node.key = value.optString("key", String.valueOf(index));
            node.title = value.optString("title");
            node.subtitle = value.optString("subtitle");
            node.expanded = value.optBoolean("expanded", false);
            readNodes(value.optJSONArray("children"), node.children);
            target.add(node);
        }
    }

    private void rebuildVisible() {
        visible.clear();
        flatten(roots, 0);
    }

    private void flatten(List<Node> nodes, int depth) {
        for (Node node : nodes) {
            visible.add(new Row(node, depth));
            if (node.expanded && !node.children.isEmpty()) {
                flatten(node.children, depth + 1);
            }
        }
    }

    private final class TreeAdapter extends Adapter<TreeHolder> {
        @NonNull @Override
        public TreeHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            LinearLayout row = new LinearLayout(getContext());
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            row.setMinimumHeight(dp(rowHeight));
            row.setLayoutParams(new LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(rowHeight)
            ));

            TextView disclosure = new TextView(getContext());
            disclosure.setGravity(Gravity.CENTER);
            disclosure.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            row.addView(disclosure, new LinearLayout.LayoutParams(dp(30), dp(rowHeight)));

            LinearLayout labels = new LinearLayout(getContext());
            labels.setOrientation(LinearLayout.VERTICAL);
            labels.setGravity(Gravity.CENTER_VERTICAL);
            TextView title = new TextView(getContext());
            title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
            title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
            TextView subtitle = new TextView(getContext());
            subtitle.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            labels.addView(title, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ));
            labels.addView(subtitle, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT
            ));
            LinearLayout.LayoutParams labelParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.MATCH_PARENT, 1f
            );
            row.addView(labels, labelParams);
            return new TreeHolder(row, disclosure, title, subtitle);
        }

        @Override
        public void onBindViewHolder(@NonNull TreeHolder holder, int position) {
            Row row = visible.get(position);
            Node node = row.node;
            boolean branch = !node.children.isEmpty();
            holder.disclosure.setText(branch ? (node.expanded ? "▼" : "▶") : "•");
            holder.disclosure.setTextColor(branch ? accentColor : secondaryColor);
            holder.title.setText(node.title);
            holder.title.setTextColor(textColor);
            holder.subtitle.setText(node.subtitle);
            holder.subtitle.setTextColor(secondaryColor);
            holder.subtitle.setVisibility(node.subtitle.isEmpty() ? View.GONE : View.VISIBLE);
            holder.itemView.setPadding(dp(8 + Math.min(12, row.depth) * 20), 0, dp(8), 0);
            holder.itemView.setContentDescription(
                node.title + (branch ? (node.expanded ? ", expanded" : ", collapsed") : "")
            );
            holder.itemView.setOnClickListener(view -> {
                selectedKey = node.key;
                if (branch) node.expanded = !node.expanded;
                rebuildVisible();
                notifyDataSetChanged();
            });

            GradientDrawable item = new GradientDrawable();
            item.setColor(node.key.equals(selectedKey)
                ? ((accentColor & 0x00FFFFFF) | 0x22000000)
                : Color.TRANSPARENT);
            holder.itemView.setBackground(item);
        }

        @Override public int getItemCount() { return visible.size(); }
        @Override public long getItemId(int position) {
            return visible.get(position).node.key.hashCode();
        }
    }

    private static final class TreeHolder extends ViewHolder {
        final TextView disclosure;
        final TextView title;
        final TextView subtitle;

        TreeHolder(@NonNull View itemView, TextView disclosure,
                   TextView title, TextView subtitle) {
            super(itemView);
            this.disclosure = disclosure;
            this.title = title;
            this.subtitle = subtitle;
        }
    }

    private static final class Node {
        String key = "";
        String title = "";
        String subtitle = "";
        boolean expanded;
        final ArrayList<Node> children = new ArrayList<>();
    }

    private static final class Row {
        final Node node;
        final int depth;
        Row(Node node, int depth) { this.node = node; this.depth = depth; }
    }
}
'''


__all__ = [
    "COMPONENT_NAMES",
    "parse_component",
    "encoded_payload",
    "generate_rich_content_view_java",
    "generate_tree_view_java",
]
