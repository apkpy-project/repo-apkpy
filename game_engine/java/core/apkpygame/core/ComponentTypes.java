package apkpygame.core;

import apkpygame.core.components.Animator;
import apkpygame.core.components.Billboard;
import apkpygame.core.components.Canvas;
import apkpygame.core.components.Block;
import apkpygame.core.components.GridController;
import apkpygame.core.components.Plane;
import apkpygame.core.components.Emitter;
import apkpygame.core.components.Follow;
import apkpygame.core.components.Lifetime;
import apkpygame.core.components.Mover;
import apkpygame.core.components.OnCollide;
import apkpygame.core.components.OnTap;
import apkpygame.core.components.Patrol;
import apkpygame.core.components.PlatformerController;
import apkpygame.core.components.Shape;
import apkpygame.core.components.Spawner;
import apkpygame.core.components.Spin;
import apkpygame.core.components.Sprite;
import apkpygame.core.components.Text;
import apkpygame.core.components.Panel;
import apkpygame.core.components.Button;
import apkpygame.core.components.Bar;
import apkpygame.core.components.ScrollList;
import apkpygame.core.components.Tabs;
import apkpygame.core.components.Toggle;
import apkpygame.core.components.Slider;
import apkpygame.core.components.Keyboard;
import apkpygame.core.components.Tilemap;
import apkpygame.core.components.Timer;
import apkpygame.core.components.TopDownController;
import apkpygame.core.components.TouchButton;
import apkpygame.core.components.Tween;
import apkpygame.core.physics2d.Body;
import apkpygame.core.physics2d.Collider;
import apkpygame.core.json.Json;
import apkpygame.core.math.Color;

import java.util.HashMap;
import java.util.Map;

/**
 * Component readers by "type" name, as written in the bundle. Built-ins are
 * registered here; generated game code registers its own (scripts) with
 * {@link #register}. No reflection: R8 keeps working without rules.
 */
public final class ComponentTypes {
    public interface Reader {
        Component read(Map<String, Object> json, Game game);
    }

    private static final Map<String, Reader> READERS = new HashMap<String, Reader>();

    /** An image field that may be left out (then a plain colour is drawn). */
    static apkpygame.core.render.Texture optionalTexture(Map<String, Object> o, String key, Game game) {
        String path = Json.str(o, key, null);
        return path == null || path.isEmpty() ? null : game.assets.texture(path);
    }

    private ComponentTypes() { }

    public static void register(String type, Reader reader) {
        READERS.put(type, reader);
    }

    public static Reader find(String type) {
        return READERS.get(type);
    }


    static {
        register("Sprite", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Sprite s = new Sprite(game.assets.texture(Json.str(o, "image", "")));
                java.util.List<Object> region = Json.list(o, "region");
                if (region.size() == 4) {
                    s.setRegion(((Number) region.get(0)).intValue(), ((Number) region.get(1)).intValue(),
                            ((Number) region.get(2)).intValue(), ((Number) region.get(3)).intValue());
                }
                double[] pivot = Json.pair(o, "pivot", 0.5, 0.5);
                s.pivotX = pivot[0];
                s.pivotY = pivot[1];
                s.tint = Color.parse(Json.str(o, "tint", null), Color.WHITE);
                s.alpha = Json.num(o, "alpha", 1);
                s.layer = (int) Json.num(o, "layer", 0);
                s.order = (int) Json.num(o, "order", 0);
                s.smooth = !"nearest".equals(Json.str(o, "filter", "linear"));
                s.flipX = Json.bool(o, "flip_x", false);
                s.flipY = Json.bool(o, "flip_y", false);
                return s;
            }
        });
        register("Canvas", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                String image = Json.str(o, "image", null);
                apkpygame.core.render.Png start = image == null || image.isEmpty() ? null
                        : game.assets.<apkpygame.core.render.Png>get("pixels", image);
                int rx = 0, ry = 0, rw = start == null ? 0 : start.width, rh = start == null ? 0 : start.height;
                java.util.List<Object> region = Json.list(o, "region");          // a frame of a sheet or an atlas
                if (start != null && region.size() == 4) {
                    rx = ((Number) region.get(0)).intValue();
                    ry = ((Number) region.get(1)).intValue();
                    rw = ((Number) region.get(2)).intValue();
                    rh = ((Number) region.get(3)).intValue();
                }
                Canvas c = new Canvas((int) Json.num(o, "width", start == null ? 64 : rw),
                        (int) Json.num(o, "height", start == null ? 64 : rh));
                String color = Json.str(o, "color", null);
                if (color != null) c.fill(color);
                if (start != null) c.start(start, rx, ry, rw, rh);
                double[] pivot = Json.pair(o, "pivot", 0.5, 0.5);
                c.pivotX = pivot[0];
                c.pivotY = pivot[1];
                c.alpha = Json.num(o, "alpha", 1);
                c.layer = (int) Json.num(o, "layer", 0);
                c.order = (int) Json.num(o, "order", 0);
                c.smooth = "linear".equals(Json.str(o, "filter", "nearest"));
                String brush = Json.str(o, "brush", null);
                if (brush != null && !brush.isEmpty()) c.setBrush(brush);
                c.brushSize = (int) Json.num(o, "brush_size", 1);
                return c;
            }
        });
        register("Shape", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Shape s = new Shape();
                s.circle = "circle".equals(Json.str(o, "shape", "rect"));
                if (s.circle) {
                    s.width = s.height = Json.num(o, "radius", 5) * 2;
                } else {
                    double[] size = Json.pair(o, "size", 10, 10);
                    s.width = size[0];
                    s.height = size[1];
                }
                double[] pivot = Json.pair(o, "pivot", 0.5, 0.5);
                s.pivotX = pivot[0];
                s.pivotY = pivot[1];
                s.color = Color.parse(Json.str(o, "color", null), Color.WHITE);
                s.alpha = Json.num(o, "alpha", 1);
                s.filled = Json.bool(o, "filled", true);
                s.stroke = Json.num(o, "stroke", 1);
                s.layer = (int) Json.num(o, "layer", 0);
                s.order = (int) Json.num(o, "order", 0);
                return s;
            }
        });
        register("Text", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                String key = Json.str(o, "key", null);
                Text t = new Text(key == null ? Json.str(o, "text", "") : game.text(key, Json.str(o, "text", key)));
                t.size = Json.num(o, "size", 16);
                t.color = Color.parse(Json.str(o, "color", null), Color.WHITE);
                t.alpha = Json.num(o, "alpha", 1);
                String align = Json.str(o, "align", "left");
                t.align = align.equals("center") ? 0 : align.equals("right") ? 1 : -1;
                t.layer = (int) Json.num(o, "layer", 0);
                t.order = (int) Json.num(o, "order", 0);
                t.font = Json.str(o, "font", null);
                t.maxWidth = Json.num(o, "max_width", 0);
                t.lineSpacing = Json.num(o, "line_spacing", 1);
                t.maxLines = (int) Json.num(o, "max_lines", 0);
                return t;
            }
        });
        register("Panel", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Panel p = new Panel();
                String image = Json.str(o, "image", null);
                if (image != null) p.texture = game.assets.texture(image);
                double[] size = Json.pair(o, "size", p.width, p.height);
                p.width = size[0];
                p.height = size[1];
                p.border = (int) Json.num(o, "border", p.border);
                double[] pivot = Json.pair(o, "pivot", 0.5, 0.5);
                p.pivotX = pivot[0];
                p.pivotY = pivot[1];
                p.tint = Color.parse(Json.str(o, "tint", null), p.tint);
                p.color = Color.parse(Json.str(o, "color", null), p.color);
                p.line = Color.parse(Json.str(o, "line", null), p.line);
                p.alpha = Json.num(o, "alpha", 1);
                p.layer = (int) Json.num(o, "layer", 0);
                p.order = (int) Json.num(o, "order", 0);
                p.smooth = "linear".equals(Json.str(o, "filter", "nearest"));
                p.modal = Json.bool(o, "modal", false);
                return p;
            }
        });
        register("Button", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Button b = new Button();
                String key = Json.str(o, "key", null);
                b.label = key == null ? Json.str(o, "label", "") : game.text(key, Json.str(o, "label", key));
                double[] size = Json.pair(o, "size", b.width, b.height);
                b.width = size[0];
                b.height = size[1];
                double[] pivot = Json.pair(o, "pivot", 0.5, 0.5);
                b.pivotX = pivot[0];
                b.pivotY = pivot[1];
                b.border = (int) Json.num(o, "border", b.border);
                String image = Json.str(o, "image", null);
                if (image != null) b.image = game.assets.texture(image);
                image = Json.str(o, "pressed", null);
                if (image != null) b.pressedImage = game.assets.texture(image);
                image = Json.str(o, "disabled", null);
                if (image != null) b.disabledImage = game.assets.texture(image);
                b.color = Color.parse(Json.str(o, "color", null), b.color);
                b.pressedColor = Color.parse(Json.str(o, "pressed_color", null), b.pressedColor);
                b.disabledColor = Color.parse(Json.str(o, "disabled_color", null), b.disabledColor);
                b.line = Color.parse(Json.str(o, "line", null), b.line);
                b.alpha = Json.num(o, "alpha", 1);
                b.layer = (int) Json.num(o, "layer", 0);
                b.order = (int) Json.num(o, "order", 0);
                b.smooth = "linear".equals(Json.str(o, "filter", "nearest"));
                b.enabled = Json.bool(o, "enabled", true);
                b.sound = Json.str(o, "sound", null);
                if (b.sound != null) game.assets.get("sound", b.sound);
                b.actions.addAll(Actions.read(Json.list(o, "actions"), game));
                b.text.font = Json.str(o, "font", null);
                b.text.size = Json.num(o, "text_size", 14);
                b.text.color = Color.parse(Json.str(o, "text_color", null), Color.WHITE);
                return b;
            }
        });
        register("Bar", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Bar b = new Bar();
                b.max = Json.num(o, "max", 1);
                b.value = Json.num(o, "value", b.max);
                double[] size = Json.pair(o, "size", b.width, b.height);
                b.width = size[0];
                b.height = size[1];
                double[] pivot = Json.pair(o, "pivot", 0, 0.5);
                b.pivotX = pivot[0];
                b.pivotY = pivot[1];
                b.color = Color.parse(Json.str(o, "color", null), b.color);
                b.midColor = Color.parse(Json.str(o, "mid_color", null), b.midColor);
                b.lowColor = Color.parse(Json.str(o, "low_color", null), b.lowColor);
                b.back = Color.parse(Json.str(o, "back", null), b.back);
                b.midAt = Json.num(o, "mid_at", b.midAt);
                b.lowAt = Json.num(o, "low_at", b.lowAt);
                b.speed = Json.num(o, "speed", b.speed);
                b.alpha = Json.num(o, "alpha", 1);
                b.layer = (int) Json.num(o, "layer", 0);
                b.order = (int) Json.num(o, "order", 0);
                return b;
            }
        });
        register("ScrollList", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                ScrollList l = new ScrollList();
                l.template = Json.obj(o, "row");
                l.count = (int) Json.num(o, "count", 0);
                double[] size = Json.pair(o, "size", l.width, l.height);
                l.width = size[0];
                l.height = size[1];
                double[] item = Json.pair(o, "item_size", size[0], l.itemHeight);
                l.itemWidth = item[0];
                l.itemHeight = item[1];
                l.columns = Math.max(1, (int) Json.num(o, "columns", 1));
                l.gap = Json.num(o, "gap", 0);
                double[] pivot = Json.pair(o, "pivot", 0, 0);
                l.pivotX = pivot[0];
                l.pivotY = pivot[1];
                l.barColor = Color.parse(Json.str(o, "bar_color", null), l.barColor);
                l.layer = (int) Json.num(o, "layer", 0);
                l.order = (int) Json.num(o, "order", 0);
                return l;
            }
        });
        register("Tabs", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Tabs t = new Tabs();
                for (Object label : Json.list(o, "labels")) t.labels.add(String.valueOf(label));
                t.selected = (int) Json.num(o, "selected", 0);
                double[] size = Json.pair(o, "size", t.width, t.height);
                t.width = size[0];
                t.height = size[1];
                String image = Json.str(o, "image", null);
                if (image != null) t.image = game.assets.texture(image);
                image = Json.str(o, "selected_image", null);
                if (image != null) t.selectedImage = game.assets.texture(image);
                t.border = (int) Json.num(o, "border", t.border);
                t.color = Color.parse(Json.str(o, "color", null), t.color);
                t.selectedColor = Color.parse(Json.str(o, "selected_color", null), t.selectedColor);
                t.line = Color.parse(Json.str(o, "line", null), t.line);
                t.textColor = Color.parse(Json.str(o, "text_color", null), t.textColor);
                t.font = Json.str(o, "font", null);
                t.textSize = Json.num(o, "text_size", t.textSize);
                t.layer = (int) Json.num(o, "layer", 0);
                t.order = (int) Json.num(o, "order", 0);
                t.sound = Json.str(o, "sound", null);
                return t;
            }
        });
        register("Toggle", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Toggle t = new Toggle();
                String key = Json.str(o, "key", null);
                t.label = key == null ? Json.str(o, "label", "") : game.text(key, Json.str(o, "label", key));
                t.value = Json.bool(o, "value", false);
                double[] size = Json.pair(o, "size", t.width, t.height);
                t.width = size[0];
                t.height = size[1];
                double[] pivot = Json.pair(o, "pivot", 0, 0.5);
                t.pivotX = pivot[0];
                t.pivotY = pivot[1];
                String image = Json.str(o, "image", null);
                if (image != null) t.image = game.assets.texture(image);
                image = Json.str(o, "on_image", null);
                if (image != null) t.onImage = game.assets.texture(image);
                t.border = (int) Json.num(o, "border", t.border);
                t.color = Color.parse(Json.str(o, "color", null), t.color);
                t.onColor = Color.parse(Json.str(o, "on_color", null), t.onColor);
                t.line = Color.parse(Json.str(o, "line", null), t.line);
                t.text.font = Json.str(o, "font", null);
                t.text.size = Json.num(o, "text_size", 14);
                t.text.color = Color.parse(Json.str(o, "text_color", null), Color.WHITE);
                t.layer = (int) Json.num(o, "layer", 0);
                t.order = (int) Json.num(o, "order", 0);
                t.smooth = "linear".equals(Json.str(o, "filter", "nearest"));
                t.sound = Json.str(o, "sound", null);
                return t;
            }
        });
        register("Slider", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Slider s = new Slider();
                s.min = Json.num(o, "min", 0);
                s.max = Json.num(o, "max", 1);
                s.value = Json.num(o, "value", s.min);
                s.step = Json.num(o, "step", 0);
                double[] size = Json.pair(o, "size", s.width, s.height);
                s.width = size[0];
                s.height = size[1];
                double[] pivot = Json.pair(o, "pivot", 0, 0.5);
                s.pivotX = pivot[0];
                s.pivotY = pivot[1];
                s.color = Color.parse(Json.str(o, "color", null), s.color);
                s.back = Color.parse(Json.str(o, "back", null), s.back);
                s.thumb = Color.parse(Json.str(o, "thumb", null), s.thumb);
                String image = Json.str(o, "image", null);
                if (image != null) s.image = game.assets.texture(image);
                s.layer = (int) Json.num(o, "layer", 0);
                s.order = (int) Json.num(o, "order", 0);
                s.smooth = "linear".equals(Json.str(o, "filter", "nearest"));
                return s;
            }
        });
        register("Keyboard", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Keyboard k = new Keyboard();
                for (Object row : Json.list(o, "rows")) k.rows.add(String.valueOf(row));
                k.text = Json.str(o, "text", "");
                k.maxLength = (int) Json.num(o, "max_length", k.maxLength);
                double[] size = Json.pair(o, "size", k.width, k.height);
                k.width = size[0];
                k.height = size[1];
                k.gap = Json.num(o, "gap", k.gap);
                k.okLabel = Json.str(o, "ok_label", k.okLabel);
                k.shiftLabel = Json.str(o, "shift_label", k.shiftLabel);
                k.deleteLabel = Json.str(o, "delete_label", k.deleteLabel);
                String image = Json.str(o, "image", null);
                if (image != null) k.image = game.assets.texture(image);
                k.border = (int) Json.num(o, "border", k.border);
                k.color = Color.parse(Json.str(o, "color", null), k.color);
                k.line = Color.parse(Json.str(o, "line", null), k.line);
                k.textColor = Color.parse(Json.str(o, "text_color", null), k.textColor);
                k.font = Json.str(o, "font", null);
                k.textSize = Json.num(o, "text_size", k.textSize);
                k.layer = (int) Json.num(o, "layer", 0);
                k.order = (int) Json.num(o, "order", 0);
                k.sound = Json.str(o, "sound", null);
                return k;
            }
        });
        register("Spin", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                return new Spin(Json.num(o, "speed", 90));
            }
        });
        register("OnTap", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                OnTap tap = new OnTap();
                double[] size = Json.pair(o, "size", 0, 0);
                tap.setArea(Json.num(o, "radius", 0), size[0], size[1]);
                tap.actions.addAll(Actions.read(Json.list(o, "actions"), game));
                return tap;
            }
        });
        register("Mover", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                double[] v = Json.pair(o, "velocity", 0, 0);
                return new Mover(v[0], v[1], Json.bool(o, "bounce", false));
            }
        });
        register("Collider", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Collider c = new Collider();
                c.circle = "circle".equals(Json.str(o, "shape", "box"));
                double[] size = Json.pair(o, "size", 10, 10);
                c.width = size[0];
                c.height = size[1];
                c.radius = Json.num(o, "radius", 5);
                double[] off = Json.pair(o, "offset", 0, 0);
                c.offsetX = off[0];
                c.offsetY = off[1];
                c.solid = Json.bool(o, "solid", false);
                c.trigger = Json.bool(o, "trigger", false);
                return c;
            }
        });
        register("Body", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Body b = new Body();
                double[] v = Json.pair(o, "velocity", 0, 0);
                b.vx = v[0];
                b.vy = v[1];
                b.gravity = Json.num(o, "gravity", 0);
                b.maxFall = Json.num(o, "max_fall", 1200);
                b.bounce = Json.num(o, "bounce", 0);
                b.collide = Json.bool(o, "collide", true);
                return b;
            }
        });
        register("OnCollide", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                OnCollide c = new OnCollide();
                c.tag = Json.str(o, "tag", "");
                c.side = Json.str(o, "side", "any");
                c.actions.addAll(Actions.read(Json.list(o, "actions"), game));
                return c;
            }
        });
        register("PlatformerController", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                PlatformerController p = new PlatformerController();
                p.speed = Json.num(o, "speed", 120);
                p.jump = Json.num(o, "jump", 330);
                p.coyote = Json.num(o, "coyote", 0.1);
                p.buffer = Json.num(o, "buffer", 0.12);
                return p;
            }
        });
        register("TopDownController", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                TopDownController t = new TopDownController();
                t.speed = Json.num(o, "speed", 200);
                t.axis = Json.str(o, "axis", "both");
                t.pointer = Json.bool(o, "pointer", true);
                t.clamp = Json.bool(o, "clamp", true);
                t.margin = Json.num(o, "margin", 16);
                return t;
            }
        });
        register("Follow", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Follow f = new Follow();
                f.target = Json.str(o, "target", "");
                f.tag = Json.str(o, "tag", "");
                f.speed = Json.num(o, "speed", 80);
                f.stop = Json.num(o, "stop", 4);
                return f;
            }
        });
        register("Patrol", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Patrol p = new Patrol();
                p.speed = Json.num(o, "speed", 60);
                p.distance = Json.num(o, "distance", 0);
                p.edges = Json.bool(o, "edges", true);
                p.direction = Json.num(o, "direction", 1) < 0 ? -1 : 1;
                return p;
            }
        });
        register("Spawner", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Spawner s = new Spawner();
                s.template = Json.obj(o, "entity");
                s.every = Json.num(o, "every", 1);
                s.jitter = Json.num(o, "jitter", 0);
                s.delay = Json.num(o, "delay", 0);
                double[] off = Json.pair(o, "offset", 0, 0);
                s.offsetX = off[0];
                s.offsetY = off[1];
                java.util.List<Object> area = Json.list(o, "area");
                if (area.size() == 4) {
                    s.area = new double[]{((Number) area.get(0)).doubleValue(), ((Number) area.get(1)).doubleValue(),
                            ((Number) area.get(2)).doubleValue(), ((Number) area.get(3)).doubleValue()};
                }
                s.limit = (int) Json.num(o, "limit", 0);
                s.total = (int) Json.num(o, "total", 0);
                return s;
            }
        });
        register("Lifetime", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Lifetime l = new Lifetime();
                l.seconds = Json.num(o, "seconds", 1);
                l.actions.addAll(Actions.read(Json.list(o, "actions"), game));
                return l;
            }
        });
        register("Timer", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Timer t = new Timer();
                t.every = Json.num(o, "every", 1);
                t.delay = Json.num(o, "delay", 0);
                t.repeat = Json.bool(o, "repeat", true);
                t.actions.addAll(Actions.read(Json.list(o, "actions"), game));
                return t;
            }
        });
        register("Tween", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Tween t = new Tween();
                t.property = Json.str(o, "property", "scale");
                t.to = Json.num(o, "to", 1);
                t.duration = Json.num(o, "duration", 1);
                t.delay = Json.num(o, "delay", 0);
                t.ease = Json.str(o, "ease", "inout");
                t.mode = Json.str(o, "mode", "pingpong");
                return t;
            }
        });
        register("Animator", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Animator a = new Animator();
                Map<String, Object> anims = Json.obj(o, "animations");
                if (anims != null) {
                    for (Map.Entry<String, Object> e : anims.entrySet()) {
                        if (!(e.getValue() instanceof Map)) continue;
                        @SuppressWarnings("unchecked")
                        Map<String, Object> an = (Map<String, Object>) e.getValue();
                        java.util.List<Object> frames = Json.list(an, "frames");
                        int[][] regions = new int[frames.size()][];
                        for (int i = 0; i < regions.length; i++) {
                            java.util.List<?> r = (java.util.List<?>) frames.get(i);
                            regions[i] = new int[]{((Number) r.get(0)).intValue(), ((Number) r.get(1)).intValue(),
                                    ((Number) r.get(2)).intValue(), ((Number) r.get(3)).intValue()};
                        }
                        a.animations.put(e.getKey(), new Animator.Animation(regions, Json.num(an, "fps", 8),
                                Json.bool(an, "loop", true)));
                    }
                }
                a.current = Json.str(o, "play", "");
                a.auto = Json.bool(o, "auto", true);
                return a;
            }
        });
        register("Emitter", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Emitter e = new Emitter();
                e.rate = Json.num(o, "rate", 0);
                e.burst = (int) Json.num(o, "burst", 0);
                e.duration = Json.num(o, "duration", 0);
                double[] life = Json.pair(o, "lifetime", 0.4, 0.8);
                e.lifeMin = life[0];
                e.lifeMax = life[1];
                double[] speed = Json.pair(o, "speed", 40, 120);
                e.speedMin = speed[0];
                e.speedMax = speed[1];
                double[] angle = Json.pair(o, "angle", 0, 360);
                e.angleMin = angle[0];
                e.angleMax = angle[1];
                e.gravity = Json.num(o, "gravity", 0);
                double[] size = Json.pair(o, "size", 6, 1);
                e.sizeStart = size[0];
                e.sizeEnd = size[1];
                e.color = Color.parse(Json.str(o, "color", null), Color.WHITE);
                e.colorEnd = Color.parse(Json.str(o, "color_end", null), e.color);
                e.layer = (int) Json.num(o, "layer", 5);
                String image = Json.str(o, "image", null);
                if (image != null) e.texture = game.assets.texture(image);
                return e;
            }
        });
        register("Tilemap", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Tilemap t = new Tilemap();
                t.path = Json.str(o, "map", "");
                t.layer = (int) Json.num(o, "layer", -10);
                t.smooth = !"nearest".equals(Json.str(o, "filter", "nearest"));
                return t;
            }
        });
        register("Billboard", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Billboard b = new Billboard();
                b.texture = game.assets.texture(Json.str(o, "image", ""));
                double[] frame = Json.pair(o, "frame_size", 0, 0);       // written by the build for a sheet
                b.frameW = (int) frame[0];
                b.frameH = (int) frame[1];
                b.directions = (int) Json.num(o, "directions", 1);
                b.fps = Json.num(o, "fps", 8);
                b.facing = Json.num(o, "facing", 0);
                b.autoFacing = Json.bool(o, "auto_facing", true);
                b.stand = Json.bool(o, "stand", true);
                b.tint = Color.parse(Json.str(o, "tint", null), Color.WHITE);
                b.alpha = Json.num(o, "alpha", 1);
                b.smooth = "linear".equals(Json.str(o, "filter", "nearest"));
                double[] pivot = Json.pair(o, "pivot", 0.5, 1);
                b.pivotX = pivot[0];
                b.pivotY = pivot[1];
                return b;
            }
        });
        register("Block", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Block b = new Block();
                double[] size = Json.pair(o, "size", 16, 16);
                b.width = size[0];
                b.depth = size[1];
                b.height = Json.num(o, "height", 16);
                b.top = optionalTexture(o, "top", game);
                b.side = optionalTexture(o, "side", game);
                b.topColor = Color.parse(Json.str(o, "top_color", null), Color.WHITE);
                b.sideColor = Color.parse(Json.str(o, "side_color", null), Color.WHITE);
                b.smooth = "linear".equals(Json.str(o, "filter", "nearest"));
                return b;
            }
        });
        register("Plane", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                Plane p = new Plane();
                p.texture = optionalTexture(o, "image", game);
                p.color = Color.parse(Json.str(o, "color", null), Color.WHITE);
                p.alpha = Json.num(o, "alpha", 1);
                double[] size = Json.pair(o, "size", 16, 16);
                p.width = size[0];
                p.height = size[1];
                p.flat = Json.bool(o, "flat", false);
                p.cross = Json.bool(o, "cross", false);
                p.smooth = "linear".equals(Json.str(o, "filter", "nearest"));
                return p;
            }
        });
        register("GridController", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                GridController g = new GridController();
                g.tile = Json.num(o, "tile", 16);
                g.speed = Json.num(o, "speed", 4);
                g.tap = Json.bool(o, "tap", true);
                java.util.List<Object> tags = Json.list(o, "block");
                if (!o.containsKey("block")) g.block.add("solid");
                for (Object t : tags) g.block.add(String.valueOf(t));
                return g;
            }
        });
        register("TouchButton", new Reader() {
            @Override public Component read(Map<String, Object> o, Game game) {
                TouchButton b = new TouchButton();
                b.key = Json.str(o, "key", "space");
                double[] size = Json.pair(o, "size", 0, 0);
                b.setArea(Json.num(o, "radius", 0), size[0], size[1]);
                return b;
            }
        });
    }
}
