package apkpygame.core;

import apkpygame.core.json.Json;
import apkpygame.core.physics2d.Body;
import apkpygame.core.physics2d.Collider;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Small things a game does without code: sounds, destroying, spawning,
 * variables, scene changes, ending the game, opening an ApkPy screen. Used
 * by OnTap, OnCollide, Timer, Lifetime, rules and a scene's on_back.
 * In the bundle: {"do": "...", ...}.
 */
public final class Actions {
    /** Who an action is about: the entity that owns it (self) and, in a collision, the other one. */
    public static final class Context {
        public final Game game;
        public final Entity self, other;

        public Context(Game game, Entity self, Entity other) {
            this.game = game;
            this.self = self;
            this.other = other;
        }

        Entity target(String which) {
            return "other".equals(which) ? other : self;
        }
    }

    public interface Action {
        void run(Context c);
    }

    private Actions() { }

    public static void runAll(List<Action> actions, Game game, Entity self, Entity other) {
        Context c = new Context(game, self, other);
        for (Action a : actions) {
            if (game.isEnded()) return;
            a.run(c);
        }
    }

    // ── the actions ──────────────────────────────────────────────────────

    public static Action sound(final String path, final double volume) {
        return new Action() {
            @Override public void run(Context c) {
                c.game.playSound(path, volume);
            }
        };
    }

    public static Action destroy(final String target) {
        return new Action() {
            @Override public void run(Context c) {
                Entity e = c.target(target);
                if (e != null) e.destroy();
            }
        };
    }

    public static Action exit(final Map<String, Object> result) {
        return new Action() {
            @Override public void run(Context c) {
                c.game.exit(c.game.substitute(result));
            }
        };
    }

    public static Action open(final String screen, final Map<String, Object> data) {
        return new Action() {
            @Override public void run(Context c) {
                c.game.openApp(screen, c.game.substitute(data));
            }
        };
    }

    /** Adds to a number kept in the store shared with the ApkPy app; {@code var} adds that variable's value. */
    public static Action storeAdd(final String key, final double amount, final String var) {
        return new Action() {
            @Override public void run(Context c) {
                String old = c.game.store().get(key);
                double value;
                try {
                    value = old.isEmpty() ? 0 : Double.parseDouble(old);
                } catch (NumberFormatException e) {
                    value = 0;
                }
                value += var == null ? amount : c.game.var(var);
                c.game.store().set(key, Game.number(value));
            }
        };
    }

    public static Action storeSet(final String key, final String value) {
        return new Action() {
            @Override public void run(Context c) {
                c.game.store().set(key, c.game.format(value));
            }
        };
    }

    public static Action varAdd(final String name, final double amount) {
        return new Action() {
            @Override public void run(Context c) {
                c.game.setVar(name, c.game.var(name) + amount);
            }
        };
    }

    public static Action varSet(final String name, final double value) {
        return new Action() {
            @Override public void run(Context c) {
                c.game.setVar(name, value);
            }
        };
    }

    /** A new entity from a template, placed at self/other (+ offset), or at (x, y) in the world. */
    public static Action spawn(final Map<String, Object> template, final String at, final double dx, final double dy) {
        return new Action() {
            @Override public void run(Context c) {
                Entity where = "world".equals(at) ? null : c.target(at);
                double x = where == null ? 0 : where.worldX(), y = where == null ? 0 : where.worldY();
                c.game.scene().spawnTemplate(template, x + dx, y + dy);
            }
        };
    }

    public static Action gotoScene(final String scene, final String at, final double fade) {
        return new Action() {
            @Override public void run(Context c) {
                c.game.gotoScene(scene, at, fade);
            }
        };
    }

    /** Sets a Body's velocity (a jump on a stomp, a knock-back). */
    public static Action impulse(final String target, final double vx, final double vy, final boolean keepX) {
        return new Action() {
            @Override public void run(Context c) {
                Entity e = c.target(target);
                Body b = e == null ? null : e.get(Body.class);
                if (b == null) return;
                if (!keepX) b.vx = vx;
                b.vy = vy;
            }
        };
    }

    /**
     * A ball on a paddle: sends the Body away from what it touched, turned by where along it the touch was
     * (straight from the middle, {@code angle} degrees at the ends). Its speed stays. StrictMath: the same on
     * every platform.
     */
    public static Action deflect(final String target, final double angle) {
        return new Action() {
            @Override public void run(Context c) {
                Entity e = c.target(target), from = e == c.self ? c.other : c.self;
                Body b = e == null ? null : e.get(Body.class);
                if (b == null || from == null) return;
                double speed = StrictMath.sqrt(b.vx * b.vx + b.vy * b.vy);
                if (speed == 0) return;
                Collider mine = e.get(Collider.class), box = from.get(Collider.class);
                double dx = (mine != null ? mine.cx : e.worldX()) - (box != null ? box.cx : from.worldX());
                double dy = (mine != null ? mine.cy : e.worldY()) - (box != null ? box.cy : from.worldY());
                double hw = box != null && box.hw > 0 ? box.hw : 8, hh = box != null && box.hh > 0 ? box.hh : 8;
                boolean above = Math.abs(dy) * hw >= Math.abs(dx) * hh;     // it touched the top or the bottom
                double along = Math.max(-1, Math.min(1, above ? dx / hw : dy / hh));
                double turn = StrictMath.toRadians(angle) * along;
                double side = StrictMath.sin(turn) * speed, away = StrictMath.cos(turn) * speed;
                if (above) {
                    b.vx = side;
                    b.vy = dy < 0 ? -away : away;
                } else {
                    b.vy = side;
                    b.vx = dx < 0 ? -away : away;
                }
            }
        };
    }

    /** The actions after it, only when the condition holds now: a door that needs a key, a shop that needs coins. */
    public static Action onlyIf(final String var, final String countTag, final String op, final double value,
                                final List<Action> actions) {
        return new Action() {
            @Override public void run(Context c) {
                if (c.game.scene() == null || !Scene.Rule.test(c.game.scene(), var, countTag, op, value)) return;
                for (int i = 0; i < actions.size(); i++) {
                    if (c.game.isEnded()) return;
                    actions.get(i).run(c);
                }
            }
        };
    }

    /** Back to where it entered the scene, stopped. */
    public static Action respawn(final String target) {
        return new Action() {
            @Override public void run(Context c) {
                Entity e = c.target(target);
                if (e == null) return;
                e.transform.set(e.spawnX, e.spawnY);
                e.transform.snap();
                Body b = e.get(Body.class);
                if (b != null) b.vx = b.vy = 0;
            }
        };
    }

    // ── reading ──────────────────────────────────────────────────────────

    /** Reads a list of {"do": ...} objects; unknown kinds are warned about and skipped. */
    public static List<Action> read(List<Object> items, Game game) {
        List<Action> out = new ArrayList<Action>();
        for (Object item : items) {
            if (!(item instanceof Map)) continue;
            @SuppressWarnings("unchecked")
            Action a = read((Map<String, Object>) item, game);
            if (a != null) out.add(a);
        }
        return out;
    }

    static Action read(Map<String, Object> a, Game game) {
        String kind = Json.str(a, "do", "");
        if (kind.equals("sound")) {
            String path = Json.str(a, "sound", "");
            game.assets.get("sound", path);             // loaded with the scene, ready on the first use
            return sound(path, Json.num(a, "volume", 1));
        }
        if (kind.equals("destroy")) return destroy(Json.str(a, "target", "self"));
        if (kind.equals("exit")) return exit(Json.obj(a, "result"));
        if (kind.equals("open")) return open(Json.str(a, "screen", ""), Json.obj(a, "data"));
        if (kind.equals("store_add")) {
            return storeAdd(Json.str(a, "key", ""), Json.num(a, "amount", 1), Json.str(a, "var", null));
        }
        if (kind.equals("store_set")) return storeSet(Json.str(a, "key", ""), Json.str(a, "value", ""));
        if (kind.equals("var_add")) return varAdd(Json.str(a, "var", ""), Json.num(a, "amount", 1));
        if (kind.equals("var_set")) return varSet(Json.str(a, "var", ""), Json.num(a, "value", 0));
        if (kind.equals("spawn")) {
            Map<String, Object> template = Json.obj(a, "entity");
            if (template == null) return null;
            double[] offset = Json.pair(a, "offset", 0, 0);
            return spawn(template, Json.str(a, "at", "self"), offset[0], offset[1]);
        }
        if (kind.equals("goto")) return gotoScene(Json.str(a, "scene", ""), Json.str(a, "at", null), Json.num(a, "fade", 0));
        if (kind.equals("impulse")) {
            double[] v = Json.pair(a, "velocity", 0, 0);
            return impulse(Json.str(a, "target", "self"), v[0], v[1], Json.bool(a, "keep_x", false));
        }
        if (kind.equals("respawn")) return respawn(Json.str(a, "target", "self"));
        if (kind.equals("deflect")) return deflect(Json.str(a, "target", "self"), Json.num(a, "angle", 60));
        if (kind.equals("if")) {
            Map<String, Object> cond = Json.obj(a, "condition");
            if (cond == null) return null;
            return onlyIf(Json.str(cond, "var", null), Json.str(cond, "count", null), Json.str(cond, "op", "=="),
                    Json.num(cond, "value", 0), read(Json.list(a, "actions"), game));
        }
        game.platform.logger().warn("G3006 unknown action '" + kind + "' (ignored; update the engine)");
        return null;
    }

    static Map<String, Object> empty() {
        return new LinkedHashMap<String, Object>();
    }
}
