package apkpygame.core.math;

/**
 * A seeded random generator (SplitMix64). Written out here, not
 * java.util.Random, so the sequence is part of the engine and the same on
 * every platform and version: a seed gives the same game everywhere.
 */
public final class Rng {
    private long state;

    public Rng(long seed) {
        state = seed;
    }

    public long nextLong() {
        long z = (state += 0x9E3779B97F4A7C15L);
        z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
        z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
        return z ^ (z >>> 31);
    }

    /** In [0, 1). */
    public double next() {
        return (nextLong() >>> 11) * 0x1.0p-53;
    }

    /** In [min, max). */
    public double range(double min, double max) {
        return min + next() * (max - min);
    }

    /** In [0, bound). */
    public int nextInt(int bound) {
        return (int) ((nextLong() >>> 33) % bound);
    }
}
