"""alert() and confirm() in the app's own style, on the phone.

A Dialog with no frame of its own holding a card built in code: a rounded
GradientDrawable, the title, the message and a row of buttons (one for
alert, two for confirm, the confirming one on the right). The parts and
their fallbacks are dialog_rules.look(), the same answer the Previewer
draws from (features/styled_dialog.py).
"""

import re

from ... import dialog_rules as rules
from .. import gradients


def _argb(colour, resolve):
    """A colour as a Java int literal, ``0xAARRGGBB``."""
    value = gradients.argb(resolve(colour)) if colour else None
    if value is None:
        return "0x00000000"
    return "0x%02X%02X%02X%02X" % value


def _orientation(angle):
    """The GradientDrawable orientation nearest a CSS angle."""
    names = ["BOTTOM_TOP", "BL_TR", "LEFT_RIGHT", "TL_BR",
             "TOP_BOTTOM", "TR_BL", "RIGHT_LEFT", "BR_TL"]
    return names[int(round((angle % 360.0) / 45.0)) % 8]


def _background(part, resolve):
    """Java for a GradientDrawable: a gradient's colours, or one colour."""
    gradient = gradients.gradient_of({"background": part["gradient"]}) if part.get("gradient") else None
    if gradient is not None and gradient.kind == "linear" and gradient.stops:
        colours = ", ".join(_argb(colour, resolve) for colour, _ in gradient.stops)
        return ("new android.graphics.drawable.GradientDrawable("
                "android.graphics.drawable.GradientDrawable.Orientation.%s, new int[]{%s})"
                % (_orientation(gradient.angle_for(1, 1)), colours))
    return ("_apkpyDialogShape(%s)" % _argb(part["background"], resolve))


def java_helper(styles, resolve):
    """The Activity's ``_apkpyStyledDialog`` method, as lines."""
    look = rules.look(styles)
    card, title, message = look["card"], look["title"], look["message"]
    lines = [
        "",
        "    private android.graphics.drawable.GradientDrawable _apkpyDialogShape(int colour) {",
        "        android.graphics.drawable.GradientDrawable shape = new android.graphics.drawable.GradientDrawable();",
        "        shape.setColor(colour);",
        "        return shape;",
        "    }",
        "",
        "    private TextView _apkpyDialogButton(String text, android.graphics.drawable.GradientDrawable shape,",
        "            int radius, int stroke, int strokeColour, int colour, float size, boolean bold, int pad,",
        "            final android.app.Dialog dialog, final Runnable then) {",
        "        float dp = getResources().getDisplayMetrics().density;",
        "        shape.setCornerRadius(radius * dp);",
        "        if (stroke > 0) shape.setStroke(Math.round(stroke * dp), strokeColour);",
        "        TextView button = new TextView(this);",
        "        button.setText(text);",
        "        button.setGravity(android.view.Gravity.CENTER);",
        "        button.setTextColor(colour);",
        "        button.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, size);",
        "        if (bold) button.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);",
        "        int p = Math.round(pad * dp);",
        "        button.setPadding(p, p, p, p);",
        "        button.setBackground(new android.graphics.drawable.RippleDrawable(",
        "                android.content.res.ColorStateList.valueOf(0x33FFFFFF), shape, null));",
        "        button.setOnClickListener(v -> { dialog.dismiss(); if (then != null) then.run(); });",
        "        return button;",
        "    }",
        "",
        "    // dialog { ... } in the stylesheet: the app's own card (dialog_rules.py).",
        "    private void _apkpyStyledDialog(String title, String message, String ok, String cancel,",
        "            final Runnable onOk, final Runnable onCancel) {",
        "        float dp = getResources().getDisplayMetrics().density;",
        "        final android.app.Dialog dialog = new android.app.Dialog(this);",
        "        dialog.requestWindowFeature(android.view.Window.FEATURE_NO_TITLE);",
        "        LinearLayout card = new LinearLayout(this);",
        "        card.setOrientation(LinearLayout.VERTICAL);",
        "        android.graphics.drawable.GradientDrawable shape = _apkpyDialogShape(%s);" % _argb(card["background"], resolve),
        "        shape.setCornerRadius(%.1ff * dp);" % card["radius"],
    ]
    if card["border"] and card["border_width"] > 0:
        lines.append("        shape.setStroke(Math.round(%.1ff * dp), %s);"
                     % (card["border_width"], _argb(card["border"], resolve)))
    lines += [
        "        card.setBackground(shape);",
        "        int pad = Math.round(%.1ff * dp);" % card["padding"],
        "        card.setPadding(pad, pad, pad, pad);",
        "        TextView heading = new TextView(this);",
        "        heading.setText(title);",
        "        heading.setTextColor(%s);" % _argb(title["color"], resolve),
        "        heading.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, %.1ff);" % title["size"],
    ]
    if title["bold"]:
        lines.append("        heading.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);")
    lines += [
        "        card.addView(heading);",
        "        TextView body = new TextView(this);",
        "        body.setText(message);",
        "        body.setTextColor(%s);" % _argb(message["color"], resolve),
        "        body.setTextSize(android.util.TypedValue.COMPLEX_UNIT_SP, %.1ff);" % message["size"],
        "        LinearLayout.LayoutParams bodyAt = new LinearLayout.LayoutParams(",
        "                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);",
        "        bodyAt.setMargins(0, Math.round(8 * dp), 0, Math.round(24 * dp));",
        "        card.addView(body, bodyAt);",
        "        LinearLayout row = new LinearLayout(this);",
        "        row.setOrientation(LinearLayout.HORIZONTAL);",
        "        card.addView(row);",
        "        int gap = Math.round(%d * dp);" % rules.BUTTON_GAP,
    ]
    for name, text_var, then in (("cancel", "cancel", "onCancel"), ("ok", "ok", "onOk")):
        part = look[name]
        stroke = int(part["border_width"]) if part["border"] else 0
        guard = "        if (cancel != null) {" if name == "cancel" else "        {"
        lines += [
            guard,
            "            TextView b = _apkpyDialogButton(%s, %s, %d, %d, %s, %s, %.1ff, %s, %d, dialog, %s);" % (
                text_var, _background(part, resolve), int(part["radius"]), stroke,
                _argb(part["border"], resolve) if part["border"] else "0",
                _argb(part["color"], resolve), part["size"],
                "true" if part["bold"] else "false", int(part["padding"]), then),
            "            LinearLayout.LayoutParams at = new LinearLayout.LayoutParams(0,",
            "                    LinearLayout.LayoutParams.WRAP_CONTENT, 1f);",
        ]
        if name == "cancel":
            lines.append("            at.setMarginEnd(gap);")
        lines += [
            "            row.addView(b, at);",
            "        }",
        ]
    lines += [
        "        dialog.setContentView(card);",
        "        dialog.setOnCancelListener(d -> { if (onCancel != null) onCancel.run(); });",
        "        android.view.Window window = dialog.getWindow();",
        "        if (window != null) {",
        "            window.setBackgroundDrawable(new android.graphics.drawable.ColorDrawable(0));",
        "            int screen = getResources().getDisplayMetrics().widthPixels;",
        "            int width = Math.min(Math.round(%d * dp), screen - Math.round(%d * dp));"
        % (rules.MAX_WIDTH, 2 * rules.SIDE_GAP),
        "            window.setLayout(width, android.view.ViewGroup.LayoutParams.WRAP_CONTENT);",
        "            window.addFlags(android.view.WindowManager.LayoutParams.FLAG_DIM_BEHIND);",
        "            window.setDimAmount(%.2ff);" % rules.SCRIM,
        "        }",
        "        dialog.show();",
        "        ApkpyWeight.watch(dialog.getWindow());",
        "    }",
    ]
    # Not every Activity imports these two.
    return [re.sub(r"(?<![\w.])(LinearLayout|TextView)\b", r"android.widget.\1", line)
            for line in lines]
