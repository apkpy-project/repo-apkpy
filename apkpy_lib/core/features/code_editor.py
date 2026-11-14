"""Colours in a textarea while you type, on the phone.

``codigo { syntax: html; }`` on an ``inputs(type="textarea")`` installs a
TextWatcher that colours the words after every change with the same table
the Previewer uses (core/code_highlight.py): the alternatives of one regular
expression per language, group ``n`` being kind ``n``.
"""

from .. import code_highlight as _code

JAVA_FILE = "java/ApkpyCodeColors.java"


def language(style):
    """The table the stylesheet names with ``syntax:``, or None."""
    return _code.language((style or {}).get("syntax"))


def setup_java(indent, java_var, lang):
    return "%sApkpyCodeColors.watch(%s, \"%s\");" % (indent, java_var, lang)


_JAVA = '''package __PACKAGE__;

import android.text.Editable;
import android.text.Spannable;
import android.text.TextWatcher;
import android.text.style.ForegroundColorSpan;
import android.widget.EditText;
import java.util.regex.Matcher;

/** Colours the words of an EditText as an editor does (ApkPy, syntax: in the CSS). */
final class ApkpyCodeColors {
    private ApkpyCodeColors() {}

    /** Ours, so a recolour removes only what it put there. */
    private static final class Word extends ForegroundColorSpan {
        Word(int colour) { super(colour); }
    }

    // __CODE_TABLES__

    static void watch(final EditText field, String language) {
        int found = -1;
        String name = CODE_ALIASES.containsKey(language) ? CODE_ALIASES.get(language) : language;
        for (int i = 0; i < CODE_LANGS.length; i++) if (CODE_LANGS[i].equals(name)) found = i;
        if (found < 0) return;
        final int lang = found;
        int text = field.getCurrentTextColor();
        int brightness = (299 * ((text >> 16) & 0xFF) + 587 * ((text >> 8) & 0xFF)
                + 114 * (text & 0xFF)) / 1000;
        final int[] palette = brightness > 140 ? CODE_DARK : CODE_LIGHT;
        field.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {}
            @Override public void afterTextChanged(Editable s) { paint(s, lang, palette); }
        });
        paint(field.getText(), lang, palette);
    }

    static void paint(Editable text, int lang, int[] palette) {
        if (text == null) return;
        for (Word old : text.getSpans(0, text.length(), Word.class)) text.removeSpan(old);
        String all = text.toString();
        int lineStart = 0;
        while (lineStart <= all.length()) {
            int lineEnd = all.indexOf('\\n', lineStart);
            if (lineEnd < 0) lineEnd = all.length();
            Matcher words = CODE_PATTERNS[lang].matcher(all.substring(lineStart, lineEnd));
            while (words.find()) {
                if (words.end() == words.start()) continue;
                for (int g = 1; g <= words.groupCount(); g++) {
                    if (words.group(g) == null) continue;
                    text.setSpan(new Word(palette[CODE_KINDS[lang][g - 1]]),
                            lineStart + words.start(), lineStart + words.end(),
                            Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);
                    break;
                }
            }
            lineStart = lineEnd + 1;
        }
    }
}
'''


def java_source(package):
    return (_JAVA.replace("__PACKAGE__", package)
            .replace("    // __CODE_TABLES__", _code.java_tables()))
