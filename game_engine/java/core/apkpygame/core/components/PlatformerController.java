package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.Input;
import apkpygame.core.physics2d.Body;

/**
 * Run and jump, on a Body with gravity. Left/right: arrow keys, A/D, or
 * TouchButton("left"/"right"); jump: space, up, W, or TouchButton("jump").
 *
 * Includes the two things that make a jump feel right: a short grace time
 * after leaving a ledge (coyote time) and a remembered early press (jump
 * buffer). Releasing jump early cuts the jump (variable height). Flips the
 * Sprite to face the direction, and reports a state for Animator:
 * idle, run, jump, fall.
 */
public final class PlatformerController extends Component {
    public double speed = 120, jump = 330;
    public double coyote = 0.1, buffer = 0.12;
    public String state = "idle";

    private double coyoteLeft, bufferLeft;
    private boolean cut;

    private static boolean jumpPressed(Input in) {
        return in.wasKeyPressed("jump") || in.wasKeyPressed("space") || in.wasKeyPressed("up")
                || in.wasKeyPressed("w");
    }

    private static boolean jumpHeld(Input in) {
        return in.isKeyDown("jump") || in.isKeyDown("space") || in.isKeyDown("up") || in.isKeyDown("w");
    }

    @Override protected void update(double dt) {
        Body b = entity().get(Body.class);
        if (b == null) return;
        Input in = game().input;
        double axis = in.axisX();
        b.vx = axis * speed;
        coyoteLeft = b.onFloor ? coyote : Math.max(0, coyoteLeft - dt);
        bufferLeft = jumpPressed(in) ? buffer : Math.max(0, bufferLeft - dt);
        if (bufferLeft > 0 && coyoteLeft > 0) {
            b.vy = -jump;
            bufferLeft = coyoteLeft = 0;
            cut = false;
        }
        if (b.vy < 0 && !cut && !jumpHeld(in)) {
            b.vy *= 0.5;
            cut = true;
        }
        Sprite s = entity().get(Sprite.class);
        if (s != null && axis != 0) s.flipX = axis < 0;
        if (!b.onFloor) state = b.vy < 0 ? "jump" : "fall";
        else state = Math.abs(b.vx) > 1 ? "run" : "idle";
    }
}
