package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Entity;
import apkpygame.core.render.Texture;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * A keyboard drawn in the game (to name things), with no system keyboard in
 * the way. Letters are capital until the first one is typed. Scripts:
 * self.keyboard.text, .changed and .done (for one step; done is its OK key).
 */
public final class Keyboard extends Component {
    public final List<String> rows = new ArrayList<String>();
    public String text = "";
    public int maxLength = 12;
    public boolean changed, done;
    public double width = 260, height = 150;
    public double gap = 2;
    public String okLabel = "OK", shiftLabel = "Aa", deleteLabel = "<";
    public Texture image;
    public int border = 4;
    public int color = 0xFF3A4252, line = 0xFFE8E8E8, textColor = 0xFFFFFFFF;
    public String font;
    public double textSize = 14;
    public int layer, order;
    public String sound;

    private final List<Button> letters = new ArrayList<Button>();
    private final List<Character> chars = new ArrayList<Character>();
    private Button shift, space, delete, ok;
    private boolean capital = true;

    private Button key(String label, double x, double y, double w, double h) {
        Button b = new Button();
        b.label = label;
        b.width = w - gap;
        b.height = h - gap;
        b.pivotX = b.pivotY = 0;
        b.image = image;
        b.border = border;
        b.color = color;
        b.line = line;
        b.layer = layer;
        b.order = order;
        b.sound = sound;
        b.text.font = font;
        b.text.size = textSize;
        b.text.color = textColor;
        Entity child = new Entity("key");
        child.transform.x = x;
        child.transform.y = y;
        child.add(b);
        entity().addChild(child);
        return b;
    }

    @Override protected void start() {
        if (rows.isEmpty()) {
            rows.add("QWERTYUIOP");
            rows.add("ASDFGHJKL");
            rows.add("ZXCVBNM");
        }
        int most = 1;
        for (String r : rows) most = Math.max(most, r.length());
        double w = width / most, h = height / (rows.size() + 1);
        for (int r = 0; r < rows.size(); r++) {
            String row = rows.get(r);
            double left = (width - row.length() * w) / 2;
            for (int i = 0; i < row.length(); i++) {
                letters.add(key(row.substring(i, i + 1), left + i * w, r * h, w, h));
                chars.add(row.charAt(i));
            }
        }
        double y = rows.size() * h, unit = width / 8;
        shift = key(shiftLabel, 0, y, unit * 1.5, h);
        space = key(" ", unit * 1.5, y, unit * 3.5, h);
        delete = key(deleteLabel, unit * 5, y, unit * 1.5, h);
        ok = key(okLabel, unit * 6.5, y, unit * 1.5, h);
        show();
    }

    private void show() {
        for (int i = 0; i < letters.size(); i++) {
            String s = String.valueOf(chars.get(i));
            letters.get(i).label = capital ? s.toUpperCase(Locale.ROOT) : s.toLowerCase(Locale.ROOT);
        }
    }

    private void type(String s) {
        if (text.length() >= maxLength) return;
        text += s;
        changed = true;
    }

    @Override protected void update(double dt) {
        changed = false;
        done = false;
        for (int i = 0; i < letters.size(); i++) {
            if (letters.get(i).clicked) {
                type(letters.get(i).label);
                capital = false;
                show();
            }
        }
        if (space.clicked) type(" ");
        if (delete.clicked && !text.isEmpty()) {
            text = text.substring(0, text.length() - 1);
            changed = true;
            if (text.isEmpty()) {
                capital = true;
                show();
            }
        }
        if (shift.clicked) {
            capital = !capital;
            show();
        }
        if (ok.clicked) done = true;
    }
}
