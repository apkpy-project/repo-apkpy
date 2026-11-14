package apkpygame.core.physics2d;

/**
 * A set of longs with no boxing (open addressing, linear probing): the pairs
 * touching this step, kept from one step to the next without allocating.
 */
final class LongSet {
    private static final long EMPTY = Long.MIN_VALUE;
    private long[] slots = new long[64];
    private int size;

    LongSet() {
        java.util.Arrays.fill(slots, EMPTY);
    }

    boolean contains(long key) {
        int mask = slots.length - 1;
        for (int i = hash(key) & mask; ; i = (i + 1) & mask) {
            long v = slots[i];
            if (v == EMPTY) return false;
            if (v == key) return true;
        }
    }

    void add(long key) {
        if ((size + 1) * 2 > slots.length) grow();
        int mask = slots.length - 1;
        for (int i = hash(key) & mask; ; i = (i + 1) & mask) {
            long v = slots[i];
            if (v == key) return;
            if (v == EMPTY) {
                slots[i] = key;
                size++;
                return;
            }
        }
    }

    void clear() {
        if (size == 0) return;
        java.util.Arrays.fill(slots, EMPTY);
        size = 0;
    }

    int size() {
        return size;
    }

    private void grow() {
        long[] old = slots;
        slots = new long[old.length * 2];
        java.util.Arrays.fill(slots, EMPTY);
        size = 0;
        for (long v : old) if (v != EMPTY) add(v);
    }

    private static int hash(long key) {
        long h = key * 0x9E3779B97F4A7C15L;
        return (int) (h ^ (h >>> 32));
    }
}
