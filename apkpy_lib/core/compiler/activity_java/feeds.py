"""virtual_collection: its adapter, and the commands that add, change and take rows."""
import ast
import json

from ...features import feeds as feeds_feature
from .... import motion
from ....theme import AVATAR_PALETTE, avatar_text_color
from ..expressions import (
    _collection_item_java_literal, _emit_json_add_collection_items, _escape_java_literal,
)


class Feeds:
    """virtual_collection: its adapter, and the commands that add, change and take rows."""

    def _emit_virtual_collection_adapter(self):
        lines = self.lines
        lines.append("    private interface ApkpyVirtualClick { void onClick(String item); }")
        lines.append("")
        lines.append("    private final class ApkpyVirtualAdapter extends RecyclerView.Adapter<ApkpyVirtualAdapter.Holder> {")
        lines.append("        private final java.util.ArrayList<String> items;")
        lines.append("        private final java.util.Map<String, String> template;")
        lines.append("        private final boolean grid;")
        lines.append("        private final int itemHeight;")
        lines.append("        // Com autoHeight cada linha toma o que precisa; sem ele todas")
        lines.append("        // tomam itemHeight, que e' como isto sempre funcionou.")
        lines.append("        private final boolean autoHeight;")
        lines.append("        private final int accentColor;")
        if self.has_vc_avatar:
            # A tabela sai do theme.py em vez de ser escrita a mao: a cor de
            # um nome tem de ser a mesma nos dois lados, e duas listas
            # separadas divergem no dia em que alguem mexe numa.
            _bg = ", ".join(
                "0xFF" + colour.lstrip("#").upper()
                for colour in AVATAR_PALETTE
            )
            _ink = ", ".join(
                "0xFF" + avatar_text_color(colour)
                .lstrip("#").upper()
                for colour in AVATAR_PALETTE
            )
            lines.append(
                "        private final int[] avatarBg = { " + _bg + " };"
            )
            lines.append(
                "        private final int[] avatarInk = { " + _ink + " };"
            )
        if self.has_vc_markdown:
            lines.append("        private final boolean copyCode;")
        lines.append("        private final int itemBg, titleColor, subtitleColor, metaColor, badgeBg, badgeColor, borderColor;")
        lines.append("        private final int titleLines, subtitleLines;")
        lines.append("        private final ApkpyVirtualClick click;")
        if self.has_vc_badge_end:
            lines.append("        private boolean badgeEnd = false;")
            lines.append("        void setBadgeEnd(boolean end) { this.badgeEnd = end; }")
        if self.has_vc_bubbles:
            lines.append("        // name -> {align (0 start, 1 end, 2 centre), max width, 1 if a percentage}")
            lines.append("        private java.util.Map<String, float[]> bubbles = new java.util.HashMap<>();")
            lines.append("        private int itemRadius = -1, itemGap = -1;")
            lines.append("        void setBubbles(java.util.Map<String, float[]> layout) { this.bubbles = layout; }")
            lines.append("        void setItemShape(int radiusDp, int gapDp) { this.itemRadius = radiusDp; this.itemGap = gapDp; }")
        lines.append("        private final java.util.regex.Pattern token = java.util.regex.Pattern.compile(\"\\\\{([A-Za-z_][A-Za-z0-9_.-]*)\\\\}\");")
        lines.append("")
        lines.append("        ApkpyVirtualAdapter(java.util.ArrayList<String> items, java.util.Map<String, String> template,")
        lines.append("                boolean grid, int itemHeight, boolean autoHeight, int itemBg, int titleColor, int subtitleColor,")
        lines.append("                int metaColor, int badgeBg, int badgeColor, int borderColor, int accentColor,")
        if self.has_vc_markdown:
            lines.append("                int titleLines, int subtitleLines, boolean copyCode, ApkpyVirtualClick click) {")
        else:
            lines.append("                int titleLines, int subtitleLines, ApkpyVirtualClick click) {")
        lines.append("            this.items = items; this.template = template; this.grid = grid;")
        lines.append("            this.itemHeight = itemHeight; this.autoHeight = autoHeight;")
        lines.append("            this.accentColor = accentColor;")
        if self.has_vc_markdown:
            lines.append("            this.copyCode = copyCode;")
        lines.append("            this.itemBg = itemBg; this.titleColor = titleColor;")
        lines.append("            this.subtitleColor = subtitleColor; this.metaColor = metaColor;")
        lines.append("            this.badgeBg = badgeBg; this.badgeColor = badgeColor;")
        lines.append("            this.borderColor = borderColor; this.click = click;")
        lines.append("            this.titleLines = titleLines; this.subtitleLines = subtitleLines;")
        lines.append("            setHasStableIds(false);")
        lines.append("        }")
        lines.append("")
        lines.append("        private int dp(android.view.ViewGroup parent, float value) {")
        lines.append("            return Math.max(1, Math.round(value * parent.getResources().getDisplayMetrics().density));")
        lines.append("        }")
        lines.append("")
        lines.append("        private android.widget.TextView text(android.content.Context context, float size, int color, boolean bold) {")
        lines.append("            return text(context, size, color, bold, 1);")
        lines.append("        }")
        lines.append("")
        if self.has_vc_avatar:
            lines.append("        private String initials(String value) {")
            lines.append("            String trimmed = value == null ? \"\" : value.trim();")
            lines.append("            if (trimmed.isEmpty()) return \"\";")
            lines.append("            StringBuilder out = new StringBuilder();")
            lines.append("            for (String part : trimmed.split(\"\\\\s+\")) {")
            lines.append("                if (part.isEmpty()) continue;")
            lines.append("                out.append(Character.toUpperCase(part.charAt(0)));")
            lines.append("                if (out.length() == 2) break;")
            lines.append("            }")
            lines.append("            return out.toString();")
            lines.append("        }")
            lines.append("")
            lines.append("        // A soma das unidades UTF-16, que e' o que o lado")
            lines.append("        // Python soma tambem -- so' o indice e' calculado aqui.")
            lines.append("        private int avatarSlot(String value) {")
            lines.append("            int sum = 0;")
            lines.append("            for (int i = 0; i < value.length(); i++) sum += value.charAt(i);")
            lines.append("            return Math.abs(sum) % avatarBg.length;")
            lines.append("        }")
            lines.append("")
        lines.append("        private android.widget.TextView text(android.content.Context context, float size, int color, boolean bold, int maxLines) {")
        lines.append("            android.widget.TextView view = new android.widget.TextView(context);")
        lines.append("            view.setTextSize(size); view.setTextColor(color); view.setMaxLines(maxLines);")
        lines.append("            view.setEllipsize(android.text.TextUtils.TruncateAt.END);")
        lines.append("            if (bold) view.setTypeface(android.graphics.Typeface.DEFAULT, android.graphics.Typeface.BOLD);")
        lines.append("            return view;")
        lines.append("        }")
        lines.append("")
        lines.append("        @NonNull @Override")
        lines.append("        public Holder onCreateViewHolder(@NonNull android.view.ViewGroup parent, int viewType) {")
        lines.append("            android.content.Context context = parent.getContext();")
        lines.append("            int pad = dp(parent, 10);")
        lines.append("            android.widget.LinearLayout root = new android.widget.LinearLayout(context);")
        lines.append("            root.setOrientation(grid ? android.widget.LinearLayout.VERTICAL : android.widget.LinearLayout.HORIZONTAL);")
        lines.append("            root.setGravity(grid || autoHeight ? android.view.Gravity.START")
        lines.append("                    : android.view.Gravity.CENTER_VERTICAL);")
        lines.append("            root.setPadding(pad, pad, pad, pad);")
        lines.append("            RecyclerView.LayoutParams rootParams = new RecyclerView.LayoutParams(")
        lines.append("                    android.view.ViewGroup.LayoutParams.MATCH_PARENT,")
        lines.append("                    autoHeight ? android.view.ViewGroup.LayoutParams.WRAP_CONTENT")
        lines.append("                               : dp(parent, itemHeight));")
        lines.append("            if (autoHeight) root.setMinimumHeight(dp(parent, 40));")
        lines.append("            int gap = grid ? dp(parent, 5) : 0;")
        lines.append("            rootParams.setMargins(gap, gap, gap, gap); root.setLayoutParams(rootParams);")
        lines.append("            android.graphics.drawable.GradientDrawable shape = new android.graphics.drawable.GradientDrawable();")
        if self.has_vc_bubbles:
            lines.append("            shape.setColor(itemBg); shape.setCornerRadius(itemRadius >= 0 ? dp(parent, itemRadius) : (grid ? dp(parent, 12) : 0));")
            lines.append("            if (itemRadius >= 0 || itemGap >= 0) shape.setStroke(0, 0);")
        else:
            lines.append("            shape.setColor(itemBg); shape.setCornerRadius(grid ? dp(parent, 12) : 0);")
        if self.has_vc_bubbles:
            lines.append("            if (!(itemRadius >= 0 || itemGap >= 0)) shape.setStroke(dp(parent, 1), borderColor);")
            lines.append("            root.setBackground(shape);")
        else:
            lines.append("            shape.setStroke(dp(parent, 1), borderColor); root.setBackground(shape);")
        lines.append("")
        lines.append("            android.widget.TextView avatar = null;")
        if self.has_vc_avatar:
            lines.append("            String avatarPattern = template.get(\"avatar\");")
            lines.append("            if (avatarPattern != null && !avatarPattern.isEmpty()) {")
            lines.append("                avatar = new android.widget.TextView(context);")
            lines.append("                avatar.setTextSize(15);")
            lines.append("                avatar.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);")
            lines.append("                avatar.setGravity(android.view.Gravity.CENTER);")
            lines.append("                int avatarSize = dp(parent, 40);")
            lines.append("                android.widget.LinearLayout.LayoutParams avatarParams =")
            lines.append("                        new android.widget.LinearLayout.LayoutParams(avatarSize, avatarSize);")
            lines.append("                if (!grid) avatarParams.setMargins(0, 0, dp(parent, 10), 0);")
            lines.append("                // Encostado ao topo: numa linha alta um circulo a meio")
            lines.append("                // nao aponta para o inicio da mensagem.")
            lines.append("                avatarParams.gravity = android.view.Gravity.TOP;")
            lines.append("                avatar.setLayoutParams(avatarParams);")
            lines.append("                root.addView(avatar);")
            lines.append("            }")
        lines.append("            android.widget.ImageView image = null;")
        lines.append("            String imagePattern = template.get(\"image\");")
        lines.append("            if (imagePattern != null && !imagePattern.isEmpty()) {")
        lines.append("                image = new android.widget.ImageView(context);")
        lines.append("                int imageHeight = grid ? Math.max(dp(parent, 72), dp(parent, itemHeight - 102)) : dp(parent, Math.min(64, itemHeight - 20));")
        lines.append("                android.widget.LinearLayout.LayoutParams imageParams = new android.widget.LinearLayout.LayoutParams(")
        lines.append("                        grid ? android.view.ViewGroup.LayoutParams.MATCH_PARENT : imageHeight, imageHeight);")
        lines.append("                if (!grid) imageParams.setMargins(0, 0, dp(parent, 12), 0);")
        lines.append("                image.setLayoutParams(imageParams);")
        lines.append("                image.setScaleType(android.widget.ImageView.ScaleType.CENTER_CROP);")
        lines.append("                image.setBackgroundColor(0xFF1E293B); root.addView(image);")
        lines.append("            }")
        lines.append("")
        lines.append("            android.widget.LinearLayout content = new android.widget.LinearLayout(context);")
        lines.append("            content.setOrientation(android.widget.LinearLayout.VERTICAL);")
        lines.append("            content.setGravity(android.view.Gravity.CENTER_VERTICAL);")
        lines.append("            content.setLayoutParams(new android.widget.LinearLayout.LayoutParams(")
        lines.append("                    grid ? android.view.ViewGroup.LayoutParams.MATCH_PARENT : 0,")
        lines.append("                    grid || autoHeight ? android.view.ViewGroup.LayoutParams.WRAP_CONTENT")
        lines.append("                                       : android.view.ViewGroup.LayoutParams.MATCH_PARENT,")
        lines.append("                    grid ? 0f : 1f));")
        lines.append("            android.widget.TextView title = text(context, grid ? 15 : 16, titleColor, true, titleLines);")
        lines.append("            android.widget.TextView subtitle = text(context, grid ? 12 : 13, subtitleColor, false, subtitleLines);")
        lines.append("            android.widget.TextView badge = text(context, 11, badgeColor, true);")
        lines.append("            android.widget.TextView meta = text(context, 12, metaColor, true);")
        lines.append("            subtitle.setPadding(0, dp(parent, 3), 0, 0);")
        lines.append("            badge.setPadding(dp(parent, 6), dp(parent, 2), dp(parent, 6), dp(parent, 2));")
        lines.append("            android.widget.LinearLayout.LayoutParams badgeParams = new android.widget.LinearLayout.LayoutParams(")
        lines.append("                    android.view.ViewGroup.LayoutParams.WRAP_CONTENT, android.view.ViewGroup.LayoutParams.WRAP_CONTENT);")
        lines.append("            badgeParams.topMargin = dp(parent, 4); badge.setLayoutParams(badgeParams);")
        lines.append("            android.graphics.drawable.GradientDrawable badgeShape = new android.graphics.drawable.GradientDrawable();")
        lines.append("            badgeShape.setColor(badgeBg); badgeShape.setCornerRadius(dp(parent, 10)); badge.setBackground(badgeShape);")
        lines.append("            android.widget.TextView markdown = null;")
        if self.has_vc_markdown:
            lines.append("            String markdownPattern = template.get(\"markdown\");")
            lines.append("            if (markdownPattern != null && !markdownPattern.isEmpty()) {")
            lines.append("                markdown = new android.widget.TextView(context);")
            lines.append("                markdown.setTextSize(15); markdown.setTextColor(titleColor);")
            lines.append("                // Sem maxLines nem ellipsize: uma resposta cortada a meio")
            lines.append("                // e' pior do que uma linha alta.")
            lines.append("                markdown.setLineSpacing(dp(parent, 3), 1.06f);")
            lines.append("                markdown.setTextIsSelectable(true);")
            lines.append("                markdown.setMovementMethod(android.text.method.LinkMovementMethod.getInstance());")
            lines.append("                markdown.setPadding(0, dp(parent, 2), 0, 0);")
            lines.append("            }")
        lines.append("            content.addView(title); content.addView(subtitle);")
        lines.append("            if (markdown != null) content.addView(markdown);")
        if self.has_vc_badge_end:
            lines.append("            if (grid || !badgeEnd) content.addView(badge);")
        else:
            lines.append("            content.addView(badge);")
        lines.append("            root.addView(content);")
        if self.has_vc_badge_end:
            lines.append("            if (!grid && badgeEnd) {")
            lines.append("                // A conversation row: the time level with the name, the")
            lines.append("                // unread count under it, both at the end.")
            lines.append("                android.widget.LinearLayout trail = new android.widget.LinearLayout(context);")
            lines.append("                trail.setOrientation(android.widget.LinearLayout.VERTICAL);")
            lines.append("                trail.setGravity(android.view.Gravity.END | android.view.Gravity.TOP);")
            lines.append("                android.widget.LinearLayout.LayoutParams trailParams = new android.widget.LinearLayout.LayoutParams(")
            lines.append("                        android.view.ViewGroup.LayoutParams.WRAP_CONTENT, android.view.ViewGroup.LayoutParams.WRAP_CONTENT);")
            lines.append("                trailParams.leftMargin = dp(parent, 8); trailParams.gravity = android.view.Gravity.TOP;")
            lines.append("                trail.setLayoutParams(trailParams);")
            lines.append("                meta.setTypeface(android.graphics.Typeface.DEFAULT); meta.setGravity(android.view.Gravity.END);")
            lines.append("                // Its own width: a vertical LinearLayout gives a child without")
            lines.append("                // params MATCH_PARENT, and the time shrank to the badge's 20dp (\"2...\").")
            lines.append("                meta.setLayoutParams(new android.widget.LinearLayout.LayoutParams(")
            lines.append("                        android.view.ViewGroup.LayoutParams.WRAP_CONTENT, android.view.ViewGroup.LayoutParams.WRAP_CONTENT));")
            lines.append("                meta.setPadding(0, dp(parent, 2), 0, 0);")
            lines.append("                badge.setMinWidth(dp(parent, 20)); badge.setMinHeight(dp(parent, 20));")
            lines.append("                badge.setMinimumWidth(dp(parent, 20)); badge.setMinimumHeight(dp(parent, 20));")
            lines.append("                badge.setGravity(android.view.Gravity.CENTER);")
            lines.append("                badge.setPadding(dp(parent, 5), 0, dp(parent, 5), 0);")
            lines.append("                badgeParams.topMargin = dp(parent, 6); badgeParams.gravity = android.view.Gravity.END;")
            lines.append("                trail.addView(meta); trail.addView(badge); root.addView(trail);")
            lines.append("            } else if (grid) {")
        else:
            lines.append("            if (grid) {")
        lines.append("                android.widget.LinearLayout.LayoutParams metaParams = new android.widget.LinearLayout.LayoutParams(")
        lines.append("                        android.view.ViewGroup.LayoutParams.MATCH_PARENT, android.view.ViewGroup.LayoutParams.WRAP_CONTENT);")
        lines.append("                metaParams.topMargin = dp(parent, 5); meta.setLayoutParams(metaParams);")
        lines.append("                meta.setGravity(android.view.Gravity.END); content.addView(meta);")
        lines.append("            } else {")
        lines.append("                android.widget.LinearLayout.LayoutParams metaParams = new android.widget.LinearLayout.LayoutParams(")
        lines.append("                        android.view.ViewGroup.LayoutParams.WRAP_CONTENT, android.view.ViewGroup.LayoutParams.MATCH_PARENT);")
        lines.append("                metaParams.leftMargin = dp(parent, 8); meta.setLayoutParams(metaParams);")
        lines.append("                meta.setGravity(android.view.Gravity.CENTER_VERTICAL | android.view.Gravity.END); root.addView(meta);")
        lines.append("            }")
        if self.has_vc_bubbles:
            lines.append("            android.view.View itemView = root;")
            lines.append("            if (!grid && (!bubbles.isEmpty() || itemGap >= 0)) {")
            lines.append("                // A row that is a bubble sits in a full-width frame, so it can")
            lines.append("                // hug its text and lean to one side, as a message does.")
            lines.append("                android.widget.FrameLayout frame = new android.widget.FrameLayout(context);")
            lines.append("                frame.setLayoutParams(new RecyclerView.LayoutParams(")
            lines.append("                        android.view.ViewGroup.LayoutParams.MATCH_PARENT,")
            lines.append("                        android.view.ViewGroup.LayoutParams.WRAP_CONTENT));")
            lines.append("                android.widget.FrameLayout.LayoutParams inner = new android.widget.FrameLayout.LayoutParams(")
            lines.append("                        android.view.ViewGroup.LayoutParams.MATCH_PARENT,")
            lines.append("                        autoHeight ? android.view.ViewGroup.LayoutParams.WRAP_CONTENT : dp(parent, itemHeight));")
            lines.append("                int half = itemGap > 0 ? dp(parent, itemGap) / 2 : 0;")
            lines.append("                inner.setMargins(0, half, 0, half);")
            lines.append("                root.setLayoutParams(inner); frame.addView(root); itemView = frame;")
            lines.append("            }")
            lines.append("            return new Holder(itemView, image, title, subtitle, badge, meta, markdown, avatar, root, content);")
        else:
            lines.append("            return new Holder(root, image, title, subtitle, badge, meta, markdown, avatar);")
        lines.append("        }")
        lines.append("")
        lines.append("        private String field(org.json.JSONObject row, String path) {")
        lines.append("            Object value = row;")
        lines.append("            try {")
        lines.append("                for (String part : path.split(\"\\\\.\")) {")
        lines.append("                    if (!(value instanceof org.json.JSONObject)) return \"\";")
        lines.append("                    value = ((org.json.JSONObject) value).opt(part);")
        lines.append("                }")
        lines.append("                return value == null || value == org.json.JSONObject.NULL ? \"\" : String.valueOf(value);")
        lines.append("            } catch (Exception ignored) { return \"\"; }")
        lines.append("        }")
        lines.append("")
        lines.append("        private String format(String pattern, org.json.JSONObject row) {")
        lines.append("            if (pattern == null || pattern.isEmpty()) return \"\";")
        lines.append("            java.util.regex.Matcher matcher = token.matcher(pattern);")
        lines.append("            StringBuffer result = new StringBuffer();")
        lines.append("            while (matcher.find()) matcher.appendReplacement(result, java.util.regex.Matcher.quoteReplacement(field(row, matcher.group(1))));")
        lines.append("            matcher.appendTail(result); return result.toString();")
        lines.append("        }")
        lines.append("")
        lines.append("        private void slot(android.widget.TextView view, String value) {")
        lines.append("            view.setText(value);")
        lines.append("            view.setVisibility(value == null || value.isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);")
        lines.append("        }")
        lines.append("")
        if self.has_vc_variants:
            # One collection, more than one shape of row. The row itself is
            # still the same set of views -- an unused slot goes GONE, which is
            # what an empty format string already did -- so nothing here needs
            # a second ViewHolder type.
            lines.append("        private String variantPattern = null;")
            lines.append("        private java.util.Map<String, java.util.Map<String, String>> variants =")
            lines.append("                new java.util.HashMap<>();")
            lines.append("        private java.util.Map<String, int[]> variantColors =")
            lines.append("                new java.util.HashMap<>();")
            lines.append("")
            lines.append("        void setVariants(String pattern,")
            lines.append("                java.util.Map<String, java.util.Map<String, String>> shapes,")
            lines.append("                java.util.Map<String, int[]> colors) {")
            lines.append("            this.variantPattern = pattern;")
            lines.append("            this.variants = shapes;")
            lines.append("            this.variantColors = colors;")
            lines.append("        }")
            lines.append("")
            lines.append("        private String variantOf(org.json.JSONObject row) {")
            lines.append("            if (variantPattern == null) return null;")
            lines.append("            String name = format(variantPattern, row);")
            lines.append("            return name == null ? null : name.trim();")
            lines.append("        }")
            lines.append("")
            lines.append("        private java.util.Map<String, String> shapeFor(String name) {")
            lines.append("            if (name == null) return template;")
            lines.append("            java.util.Map<String, String> shape = variants.get(name);")
            lines.append("            return shape == null ? template : shape;")
            lines.append("        }")
            lines.append("")
        lines.append("        @Override public void onBindViewHolder(@NonNull Holder holder, int position) {")
        lines.append("            final String raw = items.get(position);")
        lines.append("            org.json.JSONObject row;")
        lines.append("            try { row = new org.json.JSONObject(raw); }")
        lines.append("            catch (Exception ignored) { row = new org.json.JSONObject(); try { row.put(\"title\", raw); } catch (Exception ignored2) { } }")
        if self.has_vc_variants:
            lines.append("            final String variantName = variantOf(row);")
            lines.append("            final java.util.Map<String, String> template = shapeFor(variantName);")
            lines.append("            int[] shades = variantName == null ? null : variantColors.get(variantName);")
            lines.append("            if (shades != null) {")
            lines.append("                android.graphics.drawable.Drawable bg = " + ("holder.card" if self.has_vc_bubbles else "holder.itemView") + ".getBackground();")
            lines.append("                if (bg instanceof android.graphics.drawable.GradientDrawable) {")
            lines.append("                    ((android.graphics.drawable.GradientDrawable) bg.mutate()).setColor(shades[0]);")
            lines.append("                }")
            lines.append("                holder.title.setTextColor(shades[1]);")
            lines.append("                holder.subtitle.setTextColor(shades[2]);")
            lines.append("                if (shades.length > 3) holder.meta.setTextColor(shades[3]);")
            lines.append("            }")
        lines.append("            slot(holder.title, format(template.get(\"title\"), row));")
        lines.append("            slot(holder.subtitle, format(template.get(\"subtitle\"), row));")
        lines.append("            slot(holder.badge, format(template.get(\"badge\"), row));")
        lines.append("            slot(holder.meta, format(template.get(\"meta\"), row));")
        if self.has_vc_bubbles:
            lines.append("            if (holder.card != holder.itemView) {")
            lines.append("                float[] bubble = " + ("variantName == null ? null : bubbles.get(variantName)" if self.has_vc_variants else "null") + ";")
            lines.append("                android.widget.FrameLayout.LayoutParams cardParams =")
            lines.append("                        (android.widget.FrameLayout.LayoutParams) holder.card.getLayoutParams();")
            lines.append("                android.widget.LinearLayout.LayoutParams contentParams =")
            lines.append("                        (android.widget.LinearLayout.LayoutParams) holder.content.getLayoutParams();")
            lines.append("                if (bubble != null) {")
            lines.append("                    cardParams.width = android.view.ViewGroup.LayoutParams.WRAP_CONTENT;")
            lines.append("                    cardParams.gravity = bubble[0] == 1f ? android.view.Gravity.END")
            lines.append("                            : bubble[0] == 2f ? android.view.Gravity.CENTER_HORIZONTAL : android.view.Gravity.START;")
            lines.append("                    contentParams.width = android.view.ViewGroup.LayoutParams.WRAP_CONTENT; contentParams.weight = 0f;")
            lines.append("                    android.util.DisplayMetrics metrics = holder.card.getResources().getDisplayMetrics();")
            lines.append("                    int parentWidth = holder.itemView.getWidth() > 0 ? holder.itemView.getWidth() : metrics.widthPixels;")
            lines.append("                    int widest = bubble[1] <= 0f ? parentWidth")
            lines.append("                            : bubble[2] == 1f ? Math.round(parentWidth * bubble[1] / 100f)")
            lines.append("                            : Math.round(bubble[1] * metrics.density);")
            lines.append("                    int metaWidth = holder.meta.getVisibility() == android.view.View.VISIBLE")
            lines.append("                            ? Math.round(holder.meta.getPaint().measureText(String.valueOf(holder.meta.getText()))) + Math.round(8 * metrics.density) : 0;")
            lines.append("                    int textWidth = Math.max(Math.round(48 * metrics.density), widest - holder.card.getPaddingLeft()")
            lines.append("                            - holder.card.getPaddingRight() - metaWidth);")
            lines.append("                    holder.title.setMaxWidth(textWidth); holder.subtitle.setMaxWidth(textWidth);")
            lines.append("                } else {")
            lines.append("                    cardParams.width = android.view.ViewGroup.LayoutParams.MATCH_PARENT;")
            lines.append("                    cardParams.gravity = android.view.Gravity.START;")
            lines.append("                    contentParams.width = 0; contentParams.weight = 1f;")
            lines.append("                    holder.title.setMaxWidth(Integer.MAX_VALUE); holder.subtitle.setMaxWidth(Integer.MAX_VALUE);")
            lines.append("                }")
            lines.append("                holder.card.setLayoutParams(cardParams); holder.content.setLayoutParams(contentParams);")
            lines.append("            }")
        if self.has_vc_markdown:
            lines.append("            if (holder.markdown != null) {")
            lines.append("                String source = format(template.get(\"markdown\"), row);")
            lines.append("                holder.markdown.setText(ApkpyRichContentView.apkpyMarkdown(")
            lines.append("                        holder.markdown.getContext(), source, titleColor, subtitleColor,")
            lines.append("                        accentColor, copyCode));")
            lines.append("                holder.markdown.setVisibility(source.isEmpty()")
            lines.append("                        ? android.view.View.GONE : android.view.View.VISIBLE);")
            lines.append("            }")
        if self.has_vc_avatar:
            lines.append("            if (holder.avatar != null) {")
            lines.append("                String who = format(template.get(\"avatar\"), row);")
            lines.append("                String mark = initials(who);")
            lines.append("                if (mark.isEmpty()) {")
            lines.append("                    holder.avatar.setVisibility(android.view.View.GONE);")
            lines.append("                } else {")
            lines.append("                    int slot = avatarSlot(who);")
            lines.append("                    android.graphics.drawable.GradientDrawable circle =")
            lines.append("                            new android.graphics.drawable.GradientDrawable();")
            lines.append("                    circle.setShape(android.graphics.drawable.GradientDrawable.OVAL);")
            lines.append("                    circle.setColor(avatarBg[slot]);")
            lines.append("                    holder.avatar.setBackground(circle);")
            lines.append("                    holder.avatar.setTextColor(avatarInk[slot]);")
            lines.append("                    holder.avatar.setText(mark);")
            lines.append("                    holder.avatar.setVisibility(android.view.View.VISIBLE);")
            lines.append("                }")
            lines.append("            }")
        lines.append("            if (holder.image != null) {")
        lines.append("                String imageUrl = format(template.get(\"image\"), row);")
        lines.append("                holder.image.setTag(imageUrl); holder.image.setImageDrawable(null);")
        lines.append("                holder.image.setVisibility(imageUrl.isEmpty() ? android.view.View.GONE : android.view.View.VISIBLE);")
        lines.append("                if (!imageUrl.isEmpty()) _loadVirtualThumb(holder.image, imageUrl);")
        lines.append("            }")
        lines.append("            holder.itemView.setOnClickListener(click == null ? null : view -> click.onClick(raw));")
        lines.append("        }")
        lines.append("")
        lines.append("        @Override public int getItemCount() { return items.size(); }")
        lines.append("")
        lines.append("        final class Holder extends RecyclerView.ViewHolder {")
        lines.append("            final android.widget.ImageView image;")
        lines.append("            final android.widget.TextView title, subtitle, badge, meta, markdown, avatar;")
        if self.has_vc_bubbles:
            lines.append("            final android.view.View card;")
            lines.append("            final android.widget.LinearLayout content;")
        lines.append("            Holder(android.view.View root, android.widget.ImageView image, android.widget.TextView title,")
        lines.append("                    android.widget.TextView subtitle, android.widget.TextView badge, android.widget.TextView meta,")
        if self.has_vc_bubbles:
            lines.append("                    android.widget.TextView markdown, android.widget.TextView avatar,")
            lines.append("                    android.view.View card, android.widget.LinearLayout content) {")
        else:
            lines.append("                    android.widget.TextView markdown, android.widget.TextView avatar) {")
        lines.append("                super(root); this.image = image; this.title = title; this.subtitle = subtitle;")
        lines.append("                this.badge = badge; this.meta = meta; this.markdown = markdown;")
        lines.append("                this.avatar = avatar;")
        if self.has_vc_bubbles:
            lines.append("                this.card = card; this.content = content;")
        lines.append("            }")
        lines.append("        }")
        lines.append("    }")
        lines.append("")

    def _emit_feed_command(self, command, indent):
        """Emit incremental virtual-collection mutations in one shared path."""
        lines = self.lines
        jv = self._get_jv_from_py_var(command.get('py_var'))
        component = self._get_comp_from_py_var(command.get('py_var'))
        if not jv or not component or component.get('comp_type') != 'virtual_collection':
            return

        action = command.get('type')
        has_more_node = command.get('has_more_node')
        has_more_java = (
            self._val_to_java(has_more_node)
            if has_more_node is not None else 'true'
        )
        has_more_bool = (
            f"Boolean.parseBoolean(String.valueOf({has_more_java}))"
        )

        if action == 'comp_refresh':
            if component.get('on_refresh'):
                lines.append(
                    f"{indent}_apkpyRequest{jv.title()}Refresh();"
                )
            return
        if action == 'comp_finish_load':
            if feeds_feature.is_paginated(component):
                lines.append(
                    f"{indent}_apkpyFinish{jv.title()}Load({has_more_bool});"
                )
            return

        suffix = id(command) & 0xFFFF

        def _emit_runtime_row(target, element, row_suffix):
            """Build one collection row out of values known only at runtime."""
            if not isinstance(element, ast.Dict):
                lines.append(
                    f"{indent}{target}.add(String.valueOf("
                    f"{self._val_to_java(element)}));"
                )
                return
            row = f"_apkpyRow{row_suffix}"
            lines.append(f"{indent}{{")
            lines.append(
                f"{indent}    org.json.JSONObject {row} = "
                "new org.json.JSONObject();"
            )
            lines.append(f"{indent}    try {{")
            for key_node, value_node in zip(element.keys, element.values):
                if not isinstance(key_node, ast.Constant):
                    continue
                key = _escape_java_literal(str(key_node.value))
                lines.append(
                    f'{indent}        {row}.put("{key}", String.valueOf('
                    f"{self._val_to_java(value_node)}));"
                )
            lines.append(f"{indent}    }} catch (Exception ignored) {{ }}")
            lines.append(f"{indent}    {target}.add({row}.toString());")
            lines.append(f"{indent}}}")

        def _emit_items_into(target, items_node, item_suffix):
            if isinstance(items_node, (ast.List, ast.Tuple)):
                for position, element in enumerate(items_node.elts):
                    try:
                        value = ast.literal_eval(element)
                    except (ValueError, TypeError, SyntaxError):
                        # A row built from what the user just typed is the
                        # normal case for a chat, and it is not a literal.
                        # Dropping it silently produced Java that compiled,
                        # ran, and added nothing.
                        _emit_runtime_row(
                            target, element, f"{item_suffix}_{position}"
                        )
                        continue
                    lines.append(
                        f"{indent}{target}.add("
                        f"{_collection_item_java_literal(value)});"
                    )
            elif items_node is not None:
                _emit_json_add_collection_items(
                    lines, indent, target, self._val_to_java(items_node),
                    item_suffix,
                )

        if action == 'comp_append_items':
            start_var = f"_apkpyStart{suffix}"
            inserted_var = f"_apkpyInserted{suffix}"
            lines.append(f"{indent}int {start_var} = {jv}_items.size();")
            _emit_items_into(
                f"{jv}_items", command.get('items_node'), suffix
            )
            lines.append(
                f"{indent}int {inserted_var} = "
                f"{jv}_items.size() - {start_var};"
            )
            lines.append(
                f"{indent}if ({inserted_var} > 0) "
                f"{jv}Adapter.notifyItemRangeInserted("
                f"{start_var}, {inserted_var});"
            )
            if feeds_feature.is_paginated(component):
                lines.append(
                    f"{indent}_apkpyFinish{jv.title()}Load({has_more_bool});"
                )
                if component.get('on_end_reached'):
                    lines.append(
                        f"{indent}{jv}.post("
                        f"() -> _apkpyMaybeLoad{jv.title()}Page());"
                    )
            return

        if action == 'comp_prepend_items':
            page = f"_apkpyPage{suffix}"
            count = f"_apkpyCount{suffix}"
            manager = f"_apkpyManager{suffix}"
            first = f"_apkpyFirst{suffix}"
            offset = f"_apkpyOffset{suffix}"
            first_view = f"_apkpyFirstView{suffix}"
            lines.append(f"{indent}{{")
            inner = indent + "    "
            lines.append(
                f"{inner}java.util.ArrayList<String> {page} = "
                "new java.util.ArrayList<>();"
            )
            old_indent = indent
            indent = inner
            _emit_items_into(page, command.get('items_node'), suffix)
            indent = old_indent
            lines.append(
                f"{inner}int {count} = {page}.size();"
            )
            lines.append(
                f"{inner}RecyclerView.LayoutManager {manager} = "
                f"{jv}.getLayoutManager();"
            )
            lines.append(f"{inner}int {first} = -1;")
            lines.append(f"{inner}int {offset} = 0;")
            lines.append(
                f"{inner}if ({manager} instanceof LinearLayoutManager) {{"
            )
            lines.append(
                f"{inner}    {first} = ((LinearLayoutManager) {manager})"
                ".findFirstVisibleItemPosition();"
            )
            lines.append(
                f"{inner}    android.view.View {first_view} = "
                f"{manager}.findViewByPosition({first});"
            )
            lines.append(
                f"{inner}    if ({first_view} != null) "
                f"{offset} = {first_view}.getTop() - {jv}.getPaddingTop();"
            )
            lines.append(f"{inner}}}")
            lines.append(
                f"{inner}if ({count} > 0) {{"
            )
            lines.append(f"{inner}    {jv}_items.addAll(0, {page});")
            lines.append(
                f"{inner}    {jv}Adapter.notifyItemRangeInserted(0, {count});"
            )
            lines.append(
                f"{inner}    if ({first} >= 0 && "
                f"{manager} instanceof LinearLayoutManager) {{"
            )
            lines.append(
                f"{inner}        ((LinearLayoutManager) {manager})"
                f".scrollToPositionWithOffset({first} + {count}, {offset});"
            )
            lines.append(f"{inner}    }}")
            lines.append(f"{inner}}}")
            lines.append(f"{indent}}}")
            return

        key_node = command.get('key_node')
        key_java = (
            self._val_to_java(key_node) if key_node is not None else '"id"'
        )

        if action == 'comp_scroll_to':
            mode = command.get('mode') or 'end'
            # A duracao sai da mesma tabela que o Previewer le; motion="none"
            # da' zero, e zero e' um salto instantaneo nos dois lados.
            scroll_ms = motion.duration('nav', self._theme_motion)
            if mode == 'top':
                lines.append(f"{indent}_apkpyScrollTo({jv}, 0, {scroll_ms});")
            elif mode == 'end':
                lines.append(
                    f"{indent}_apkpyScrollTo({jv}, "
                    f"{jv}_items.size() - 1, {scroll_ms});"
                )
            else:
                index = f"_apkpyScrollIndex{suffix}"
                item_id_java = self._val_to_java(command.get('item_id_node'))
                block = indent + "    "
                lines.append(f"{indent}{{")
                lines.append(
                    f"{block}int {index} = _apkpyVcFind({jv}_items, "
                    f"String.valueOf({key_java}), "
                    f"String.valueOf({item_id_java}));"
                )
                lines.append(
                    f"{block}if ({index} >= 0) "
                    f"_apkpyScrollTo({jv}, {index}, {scroll_ms});"
                )
                lines.append(f"{indent}}}")
            return

        if action in ('comp_update_item', 'comp_remove_item'):
            item_id_java = self._val_to_java(command.get('item_id_node'))
            optimistic_node = command.get('optimistic_node')
            block = indent + "    "
            item_id = f"_apkpyItemId{suffix}"
            key_var = f"_apkpyKey{suffix}"
            index = f"_apkpyIndex{suffix}"
            token = f"_apkpyToken{suffix}"
            lines.append(f"{indent}{{")
            lines.append(
                f"{block}String {item_id} = String.valueOf({item_id_java});"
            )
            lines.append(
                f"{block}String {key_var} = String.valueOf({key_java});"
            )
            lines.append(
                f"{block}int {index} = _apkpyVcFind("
                f"{jv}_items, {key_var}, {item_id});"
            )
            lines.append(f"{block}if ({index} >= 0) {{")
            nested = block + "    "
            if optimistic_node is None:
                lines.append(f"{nested}String {token} = null;")
            else:
                optimistic_java = self._val_to_java(optimistic_node)
                raw = f"_apkpyOptimistic{suffix}"
                lines.append(
                    f"{nested}String {raw} = "
                    f"String.valueOf({optimistic_java});"
                )
                lines.append(
                    f"{nested}String {token} = "
                    f"\"true\".equalsIgnoreCase({raw}) ? {item_id} : "
                    f"(\"false\".equalsIgnoreCase({raw}) || {raw}.isEmpty() "
                    f"? null : {raw});"
                )
            lines.append(
                f"{nested}_apkpyVcSnapshot({jv}Optimistic, "
                f"{jv}OptimisticKeys, {token}, {key_var}, {jv}_items);"
            )
            if action == 'comp_update_item':
                changes_node = command.get('changes_node')
                try:
                    literal_patch = ast.literal_eval(changes_node)
                except (ValueError, TypeError, SyntaxError):
                    literal_patch = None
                if isinstance(literal_patch, dict):
                    patch_java = (
                        '"' + _escape_java_literal(json.dumps(
                            literal_patch, ensure_ascii=False,
                            separators=(',', ':'),
                        )) + '"'
                    )
                else:
                    patch_java = (
                        f"String.valueOf({self._val_to_java(changes_node)})"
                    )
                lines.append(
                    f"{nested}{jv}_items.set({index}, _apkpyVcMergeJson("
                    f"{jv}_items.get({index}), {patch_java}));"
                )
                lines.append(
                    f"{nested}{jv}Adapter.notifyItemChanged({index});"
                )
            else:
                lines.append(f"{nested}{jv}_items.remove({index});")
                lines.append(
                    f"{nested}{jv}Adapter.notifyItemRemoved({index});"
                )
            lines.append(f"{block}}}")
            lines.append(f"{indent}}}")
            return

        if action == 'comp_merge_items':
            incoming = f"_apkpyIncoming{suffix}"
            merged = f"_apkpyMerged{suffix}"
            key_var = f"_apkpyKey{suffix}"
            lines.append(f"{indent}{{")
            block = indent + "    "
            lines.append(
                f"{block}String {key_var} = String.valueOf({key_java});"
            )
            lines.append(
                f"{block}java.util.ArrayList<String> {incoming} = "
                "new java.util.ArrayList<>();"
            )
            old_indent = indent
            indent = block
            _emit_items_into(
                incoming, command.get('items_node'), suffix
            )
            indent = old_indent
            lines.append(
                f"{block}java.util.ArrayList<String> {merged} = "
                f"new java.util.ArrayList<>({jv}_items);"
            )
            lines.append(f"{block}for (String row : {incoming}) {{")
            lines.append(
                f"{block}    String itemKey = _apkpyVcKey(row, {key_var});"
            )
            lines.append(
                f"{block}    int position = _apkpyVcFind("
                f"{merged}, {key_var}, itemKey);"
            )
            lines.append(f"{block}    if (position >= 0) {{")
            lines.append(
                f"{block}        {merged}.set(position, _apkpyVcMergeJson("
                f"{merged}.get(position), row));"
            )
            lines.append(f"{block}    }} else {{")
            lines.append(f"{block}        {merged}.add(row);")
            lines.append(f"{block}    }}")
            lines.append(f"{block}}}")
            lines.append(
                f"{block}_apkpyVcApplyDiff("
                f"{jv}_items, {merged}, {jv}Adapter, {key_var});"
            )
            lines.append(f"{indent}}}")
            return

        if action in ('comp_feed_rollback', 'comp_feed_commit'):
            mutation_node = command.get('mutation_node')
            token_java = (
                f"String.valueOf({self._val_to_java(mutation_node)})"
                if mutation_node is not None else '""'
            )
            token = f"_apkpyMutation{suffix}"
            lines.append(f"{indent}{{")
            block = indent + "    "
            lines.append(f"{block}String {token} = {token_java};")
            lines.append(
                f"{block}if ({token}.isEmpty()) "
                f"{token} = _apkpyVcLastToken({jv}Optimistic);"
            )
            lines.append(f"{block}if ({token} != null) {{")
            if action == 'comp_feed_rollback':
                snapshot = f"_apkpySnapshot{suffix}"
                rollback_key = f"_apkpyRollbackKey{suffix}"
                lines.append(
                    f"{block}    java.util.ArrayList<String> {snapshot} = "
                    f"{jv}Optimistic.remove({token});"
                )
                lines.append(
                    f"{block}    String {rollback_key} = "
                    f"{jv}OptimisticKeys.remove({token});"
                )
                lines.append(f"{block}    if ({snapshot} != null) {{")
                lines.append(
                    f"{block}        _apkpyVcApplyDiff({jv}_items, "
                    f"{snapshot}, {jv}Adapter, "
                    f"{rollback_key} == null ? \"id\" : {rollback_key});"
                )
                lines.append(f"{block}    }}")
            else:
                lines.append(f"{block}    {jv}Optimistic.remove({token});")
                lines.append(
                    f"{block}    {jv}OptimisticKeys.remove({token});"
                )
            lines.append(f"{block}}}")
            lines.append(f"{indent}}}")
            return
