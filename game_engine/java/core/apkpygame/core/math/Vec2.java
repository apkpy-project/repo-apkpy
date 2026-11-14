package apkpygame.core.math;

/** An immutable 2D vector (the user-facing type; the hot paths use plain doubles). */
public final class Vec2 {
    public static final Vec2 ZERO = new Vec2(0, 0);

    public final double x, y;

    public Vec2(double x, double y) {
        this.x = x;
        this.y = y;
    }

    public Vec2 add(Vec2 o) { return new Vec2(x + o.x, y + o.y); }
    public Vec2 sub(Vec2 o) { return new Vec2(x - o.x, y - o.y); }
    public Vec2 mul(double s) { return new Vec2(x * s, y * s); }
    public double dot(Vec2 o) { return x * o.x + y * o.y; }
    public double length() { return StrictMath.sqrt(x * x + y * y); }

    public Vec2 normalized() {
        double l = length();
        return l == 0 ? ZERO : new Vec2(x / l, y / l);
    }

    public double distanceTo(Vec2 o) {
        double dx = x - o.x, dy = y - o.y;
        return StrictMath.sqrt(dx * dx + dy * dy);
    }

    @Override public boolean equals(Object o) {
        return o instanceof Vec2 && ((Vec2) o).x == x && ((Vec2) o).y == y;
    }

    @Override public int hashCode() {
        long bits = Double.doubleToLongBits(x) * 31 + Double.doubleToLongBits(y);
        return (int) (bits ^ (bits >>> 32));
    }

    @Override public String toString() {
        return "Vec2(" + x + ", " + y + ")";
    }
}
