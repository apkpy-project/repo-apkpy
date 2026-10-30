# -*- coding: utf-8 -*-
"""Rows built from components: ``virtual_collection(items, row=post_row)``.

The slot rows of a virtual_collection -- title, subtitle, image, meta, badge --
draw a chat list or a track list, and nothing else. A feed post (a header, a
photo, a row of actions, a caption), a comment or a product card is a small
layout of its own, repeated for every item, and it could not be written.

``row=`` takes a function that builds one row out of ordinary components::

    def post_row(row):
        label("{user}", id="post_user", parent=row)
        image("{picture}", id="post_pic", parent=row, aspect_ratio="1:1")
        button("", icon="favorite_border", describe="Like", parent=row,
               command=lambda item: like(item))

The Previewer calls it once and draws a copy per item. The compiler expands it
once, into a template that belongs to no screen (``ui_functions``), writes the
template as a layout of its own (``res/layout/apkpy_row_<screen>_<vc>.xml``),
and gives the RecyclerView this adapter: it inflates that layout, and on every
bind fills each ``{field}`` -- a text, a picture, a description -- from the
item, and hands the item to the commands that take one.

The view ids the adapter looks up are decided before the Java and the XML are
written (``compiler._assign_row_ids``), and the XML generator is checked
against them; a picture is read from a web address, a file on the phone or a
drawable packaged with the app, at its own size, and kept in a small cache.
"""

JAVA = r'''
    private final class ApkpyRowAdapter extends RecyclerView.Adapter<ApkpyRowAdapter.Holder> {
        private final java.util.ArrayList<String> items;
        private final int layout;
        private final int[] bindIds;
        private final String[] bindKinds;
        private final String[] bindPatterns;
        private final int[] actionIds;
        private final ApkpyVirtualClick[] actions;
        private final int[] ratioIds;
        private final float[] ratios;
        private final int[] activeIds;
        private final String[] activePatterns;
        private final int[] activeOn;
        private final int[] activeOff;
        private final ApkpyVirtualClick click;
        private final java.util.regex.Pattern token = java.util.regex.Pattern.compile("\\{([A-Za-z_][A-Za-z0-9_.-]*)\\}");
        // Pictures decoded at their own size (a drawable read as mdpi grows
        // three times on this kind of screen) and kept while they fit.
        private final android.util.LruCache<String, android.graphics.Bitmap> pictures =
                new android.util.LruCache<String, android.graphics.Bitmap>(24 * 1024 * 1024) {
                    @Override protected int sizeOf(String key, android.graphics.Bitmap value) {
                        return value.getByteCount();
                    }
                };

        ApkpyRowAdapter(java.util.ArrayList<String> items, int layout,
                        int[] bindIds, String[] bindKinds, String[] bindPatterns,
                        int[] actionIds, ApkpyVirtualClick[] actions,
                        int[] ratioIds, float[] ratios,
                        int[] activeIds, String[] activePatterns, int[] activeOn, int[] activeOff,
                        ApkpyVirtualClick click) {
            this.items = items;
            this.layout = layout;
            this.bindIds = bindIds;
            this.bindKinds = bindKinds;
            this.bindPatterns = bindPatterns;
            this.actionIds = actionIds;
            this.actions = actions;
            this.ratioIds = ratioIds;
            this.ratios = ratios;
            this.activeIds = activeIds;
            this.activePatterns = activePatterns;
            this.activeOn = activeOn;
            this.activeOff = activeOff;
            this.click = click;
        }

        final class Holder extends RecyclerView.ViewHolder {
            final android.view.View[] bound;
            final android.view.View[] acting;
            final android.view.View[] lit;

            Holder(android.view.View view) {
                super(view);
                bound = new android.view.View[bindIds.length];
                for (int i = 0; i < bindIds.length; i++) bound[i] = view.findViewById(bindIds[i]);
                acting = new android.view.View[actionIds.length];
                for (int i = 0; i < actionIds.length; i++) acting[i] = view.findViewById(actionIds[i]);
                lit = new android.view.View[activeIds.length];
                for (int i = 0; i < activeIds.length; i++) lit[i] = view.findViewById(activeIds[i]);
            }
        }

        // gap: on the collection, half above and half below each row -- what
        // the template rows and the Previewer do. Only set when the CSS says.
        private int gapDp = 0;

        void setGap(int dp) { gapDp = Math.max(0, dp); }

        @NonNull @Override
        public Holder onCreateViewHolder(@NonNull android.view.ViewGroup parent, int viewType) {
            android.view.View view = android.view.LayoutInflater.from(parent.getContext())
                    .inflate(layout, parent, false);
            if (gapDp > 0 && view.getLayoutParams() instanceof android.view.ViewGroup.MarginLayoutParams) {
                android.view.ViewGroup.MarginLayoutParams spaced =
                        (android.view.ViewGroup.MarginLayoutParams) view.getLayoutParams();
                int gap = Math.round(gapDp * parent.getResources().getDisplayMetrics().density);
                spaced.topMargin += gap / 2;
                spaced.bottomMargin += gap - gap / 2;
                view.setLayoutParams(spaced);
            }
            for (int i = 0; i < ratioIds.length; i++) {
                final android.view.View picture = view.findViewById(ratioIds[i]);
                final float ratio = ratios[i];
                if (picture == null || ratio <= 0f) continue;
                // aspect_ratio: the height follows the width, once it is known.
                picture.addOnLayoutChangeListener((v, left, top, right, bottom, oldLeft, oldTop, oldRight, oldBottom) -> {
                    final int width = right - left;
                    final int wanted = Math.max(1, Math.round(width / ratio));
                    if (width > 0 && v.getLayoutParams().height != wanted) {
                        v.post(() -> {
                            android.view.ViewGroup.LayoutParams params = v.getLayoutParams();
                            params.height = wanted;
                            v.setLayoutParams(params);
                        });
                    }
                });
            }
            return new Holder(view);
        }

        @Override
        public void onBindViewHolder(@NonNull Holder holder, int position) {
            final String raw = items.get(position);
            org.json.JSONObject row;
            try { row = new org.json.JSONObject(raw); } catch (Exception e) { row = new org.json.JSONObject(); }
            for (int i = 0; i < bindIds.length; i++) {
                android.view.View view = holder.bound[i];
                if (view == null) continue;
                String value = format(bindPatterns[i], row);
                String kind = bindKinds[i];
                if ("text".equals(kind) && view instanceof android.widget.TextView) {
                    ((android.widget.TextView) view).setText(value);
                } else if ("describe".equals(kind)) {
                    view.setContentDescription(value);
                } else if ("src".equals(kind) && view instanceof android.widget.ImageView) {
                    picture((android.widget.ImageView) view, value);
                } else if ("visible".equals(kind)) {
                    view.setVisibility(isOn(value) ? android.view.View.VISIBLE : android.view.View.GONE);
                } else if ("visible_parent".equals(kind) && view.getParent() instanceof android.view.View) {
                    ((android.view.View) view.getParent()).setVisibility(
                            isOn(value) ? android.view.View.VISIBLE : android.view.View.GONE);
                }
            }
            for (int i = 0; i < activeIds.length; i++) {
                android.view.View view = holder.lit[i];
                if (!(view instanceof com.google.android.material.button.MaterialButton)) continue;
                ((com.google.android.material.button.MaterialButton) view).setIcon(
                        androidx.core.content.ContextCompat.getDrawable(view.getContext(),
                                isOn(format(activePatterns[i], row)) ? activeOn[i] : activeOff[i]));
            }
            for (int i = 0; i < actionIds.length; i++) {
                android.view.View view = holder.acting[i];
                if (view == null) continue;
                final ApkpyVirtualClick action = actions[i];
                view.setOnClickListener(v -> action.onClick(raw));
            }
            if (click != null) holder.itemView.setOnClickListener(v -> click.onClick(raw));
        }

        @Override
        public int getItemCount() { return items.size(); }

        // data_rules.FIELD_OFF -- the same values the Previewer reads as off.
        private boolean isOn(String value) {
            String text = value == null ? "" : value.trim().toLowerCase(java.util.Locale.ROOT);
            for (String off : new String[]{__FIELD_OFF__}) if (off.equals(text)) return false;
            return true;
        }

        private String field(org.json.JSONObject row, String path) {
            Object value = row;
            try {
                for (String part : path.split("\\.")) {
                    if (!(value instanceof org.json.JSONObject)) return "";
                    value = ((org.json.JSONObject) value).opt(part);
                }
                return value == null || value == org.json.JSONObject.NULL ? "" : String.valueOf(value);
            } catch (Exception ignored) { return ""; }
        }

        private String format(String pattern, org.json.JSONObject row) {
            if (pattern == null || pattern.isEmpty()) return "";
            java.util.regex.Matcher matcher = token.matcher(pattern);
            StringBuffer result = new StringBuffer();
            while (matcher.find()) matcher.appendReplacement(result, java.util.regex.Matcher.quoteReplacement(field(row, matcher.group(1))));
            matcher.appendTail(result);
            return result.toString();
        }

        private void picture(final android.widget.ImageView view, final String value) {
            view.setTag(value);
            if (value == null || value.isEmpty()) { view.setImageDrawable(null); return; }
            android.graphics.Bitmap cached = pictures.get(value);
            if (cached != null) { view.setImageBitmap(cached); return; }
            view.setImageDrawable(null);
            final boolean web = value.startsWith("http://") || value.startsWith("https://");
            final int bundled = web || new java.io.File(value).isAbsolute() ? 0 : _apkpyBundled(value, "drawable");
            new Thread(() -> {
                android.graphics.Bitmap bitmap = null;
                try {
                    if (web) {
                        java.net.HttpURLConnection connection = (java.net.HttpURLConnection) new java.net.URL(value).openConnection();
                        connection.setConnectTimeout(10000);
                        connection.setReadTimeout(15000);
                        connection.setInstanceFollowRedirects(true);
                        bitmap = android.graphics.BitmapFactory.decodeStream(connection.getInputStream());
                        connection.disconnect();
                    } else if (bundled != 0) {
                        android.graphics.BitmapFactory.Options options = new android.graphics.BitmapFactory.Options();
                        options.inScaled = false;
                        bitmap = android.graphics.BitmapFactory.decodeResource(getResources(), bundled, options);
                    } else {
                        bitmap = android.graphics.BitmapFactory.decodeFile(value);
                    }
                } catch (Exception ignored) { }
                if (bitmap == null) return;
                pictures.put(value, bitmap);
                final android.graphics.Bitmap shown = bitmap;
                view.post(() -> { if (value.equals(view.getTag())) view.setImageBitmap(shown); });
            }).start();
        }
    }
'''


def emit(lines):
    """Add the adapter class to an Activity that has a row= collection."""
    from ...data_rules import FIELD_OFF
    off = ", ".join('"%s"' % value for value in FIELD_OFF)
    lines.extend(JAVA.strip('\n').replace("__FIELD_OFF__", off).splitlines())
    lines.append("")


__all__ = ["JAVA", "emit"]
