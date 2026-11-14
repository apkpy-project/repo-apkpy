package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Entity;
import apkpygame.core.render.Texture;

import java.util.ArrayList;
import java.util.List;

/** A row of tabs, one always selected. Scripts: self.tabs.selected, self.tabs.changed (for one step). */
public final class Tabs extends Component {
    public final List<String> labels = new ArrayList<String>();
    public int selected;
    public boolean changed;
    public double width = 240, height = 28;
    public Texture image, selectedImage;
    public int border = 8;
    public int color = 0xFF2A2E36, selectedColor = 0xFF596479, line = 0xFFE8E8E8, textColor = 0xFFFFFFFF;
    public String font;
    public double textSize = 14;
    public int layer, order;
    public String sound;

    private final List<Button> buttons = new ArrayList<Button>();

    @Override protected void start() {
        double w = width / Math.max(1, labels.size());
        for (int i = 0; i < labels.size(); i++) {
            Button b = new Button();
            b.label = labels.get(i);
            b.width = w;
            b.height = height;
            b.pivotX = b.pivotY = 0;
            b.border = border;
            b.line = line;
            b.layer = layer;
            b.order = order;
            b.sound = sound;
            b.text.font = font;
            b.text.size = textSize;
            b.text.color = textColor;
            Entity child = new Entity("tab" + i);
            child.transform.x = i * w;
            child.add(b);
            entity().addChild(child);
            buttons.add(b);
        }
        show();
    }

    private void show() {
        for (int i = 0; i < buttons.size(); i++) {
            Button b = buttons.get(i);
            boolean on = i == selected;
            b.color = on ? selectedColor : color;
            b.pressedColor = selectedColor;
            b.image = on && selectedImage != null ? selectedImage : image;
        }
    }

    @Override protected void update(double dt) {
        changed = false;
        for (int i = 0; i < buttons.size(); i++) {
            if (buttons.get(i).clicked && i != selected) {
                selected = i;
                changed = true;
            }
        }
        show();
    }
}
