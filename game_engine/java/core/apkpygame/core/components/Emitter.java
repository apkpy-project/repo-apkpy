package apkpygame.core.components;

import apkpygame.core.Component;
import apkpygame.core.math.Color;
import apkpygame.core.math.Mat3;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderQueue;
import apkpygame.core.render.Texture;

/**
 * Particles (sparks, smoke, explosions): {@code burst} at once when it starts,
 * then {@code rate} per second for {@code duration} seconds (0: forever).
 * Each one flies at a random speed and angle (degrees, 0 = right, 90 = down),
 * falls with {@code gravity}, shrinks or grows, changes colour and fades out.
 * Squares, or the image if one is given. Particles live in the emitter's space.
 * Not entities: hundreds cost little.
 */
public final class Emitter extends Component {
    public double rate, duration;
    public int burst;
    public double lifeMin = 0.4, lifeMax = 0.8, speedMin = 40, speedMax = 120, angleMin = 0, angleMax = 360;
    public double gravity, sizeStart = 6, sizeEnd = 1;
    public int color = Color.WHITE, colorEnd = Color.WHITE;
    public int layer = 5;
    public Texture texture;
    public int max = 512;

    private double[] x, y, vx, vy, age, life;
    private int count;
    private double time, owed;

    @Override protected void start() {
        x = new double[max];
        y = new double[max];
        vx = new double[max];
        vy = new double[max];
        age = new double[max];
        life = new double[max];
        for (int i = 0; i < burst; i++) emit();
    }

    private void emit() {
        if (count >= max) return;
        double a = StrictMath.toRadians(game().random.range(angleMin, angleMax));
        double s = game().random.range(speedMin, speedMax);
        x[count] = 0;
        y[count] = 0;
        vx[count] = StrictMath.cos(a) * s;
        vy[count] = StrictMath.sin(a) * s;
        age[count] = 0;
        life[count] = game().random.range(lifeMin, lifeMax);
        count++;
    }

    @Override protected void update(double dt) {
        time += dt;
        if (rate > 0 && (duration <= 0 || time <= duration)) {
            owed += rate * dt;
            while (owed >= 1) {
                emit();
                owed -= 1;
            }
        }
        for (int i = count - 1; i >= 0; i--) {
            age[i] += dt;
            if (age[i] >= life[i]) {
                count--;
                x[i] = x[count]; y[i] = y[count]; vx[i] = vx[count]; vy[i] = vy[count];
                age[i] = age[count]; life[i] = life[count];
                continue;
            }
            vy[i] += gravity * dt;
            x[i] += vx[i] * dt;
            y[i] += vy[i] * dt;
        }
    }

    /** How many particles are alive (tests). */
    public int alive() {
        return count;
    }

    @Override protected void render(RenderQueue queue, Mat3 world) {
        for (int i = 0; i < count; i++) {
            double u = age[i] / life[i];
            double size = sizeStart + (sizeEnd - sizeStart) * u;
            DrawCommand c = queue.add(texture != null ? DrawCommand.Kind.SPRITE : DrawCommand.Kind.RECT);
            c.layer = layer;
            c.matrix.set(world);
            c.x = x[i] - size / 2;
            c.y = y[i] - size / 2;
            c.w = c.h = size;
            int col = mix(color, colorEnd, u);
            if (texture != null) {
                c.texture = texture;
                c.srcW = texture.width;
                c.srcH = texture.height;
                c.color = col | 0xFF000000;
                c.alpha = (1 - u) * Color.alpha(col) / 255.0;
            } else {
                c.color = Color.withAlpha(col, 1 - u);
            }
        }
    }

    private static int mix(int a, int b, double u) {
        int r = (int) (Color.red(a) + (Color.red(b) - Color.red(a)) * u);
        int g = (int) (Color.green(a) + (Color.green(b) - Color.green(a)) * u);
        int bl = (int) (Color.blue(a) + (Color.blue(b) - Color.blue(a)) * u);
        int al = (int) (Color.alpha(a) + (Color.alpha(b) - Color.alpha(a)) * u);
        return (al << 24) | (r << 16) | (g << 8) | bl;
    }
}
