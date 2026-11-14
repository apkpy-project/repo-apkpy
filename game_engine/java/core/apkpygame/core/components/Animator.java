package apkpygame.core.components;

import apkpygame.core.Component;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Frame animation of the entity's Sprite: each animation is a list of
 * regions of the sprite's image (a sheet or an atlas, resolved at build), a
 * speed (fps) and loop. With {@code auto}, it plays the animation named like
 * the PlatformerController's state (idle, run, jump, fall) when there is one.
 */
public final class Animator extends Component {
    public static final class Animation {
        public final int[][] frames;
        public final double fps;
        public final boolean loop;

        public Animation(int[][] frames, double fps, boolean loop) {
            this.frames = frames;
            this.fps = fps;
            this.loop = loop;
        }
    }

    public final Map<String, Animation> animations = new LinkedHashMap<String, Animation>();
    public String current = "";
    public boolean auto = true;
    private double time;

    public void play(String name) {
        if (!name.equals(current) && animations.containsKey(name)) {
            current = name;
            time = 0;
        }
    }

    @Override protected void start() {
        if (current.isEmpty() && !animations.isEmpty()) current = animations.keySet().iterator().next();
    }

    @Override protected void update(double dt) {
        if (auto) {
            PlatformerController pc = entity().get(PlatformerController.class);
            if (pc != null) play(pc.state);
        }
        Animation a = animations.get(current);
        Sprite s = entity().get(Sprite.class);
        if (a == null || s == null || a.frames.length == 0) return;
        time += dt;
        int i = (int) Math.floor(time * a.fps);
        i = a.loop ? i % a.frames.length : Math.min(i, a.frames.length - 1);
        int[] r = a.frames[i];
        s.setRegion(r[0], r[1], r[2], r[3]);
    }
}
