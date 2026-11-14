package apkpygame.core.render;

import apkpygame.core.GameException;

import java.io.ByteArrayOutputStream;
import java.util.zip.DataFormatException;
import java.util.zip.Inflater;

/**
 * A PNG file as ARGB pixels, read in plain Java (java.util.zip only). A Canvas starts from these pixels and
 * stamps them, and they must be the same numbers on the PC, on the phone and in a replay with no window: the
 * platforms' own decoders do not promise that (Android keeps translucent pixels premultiplied, which loses
 * a little of their colour).
 *
 * Every PNG an image editor saves: grey, grey with alpha, RGB, RGBA and palette, 1 to 16 bits, with tRNS.
 * Not interlaced (Adam7), which editors leave off unless asked.
 */
public final class Png {
    public final int width, height;
    public final int[] argb;

    private Png(int width, int height, int[] argb) {
        this.width = width;
        this.height = height;
        this.argb = argb;
    }

    public static Png decode(String path, byte[] data) {
        try {
            return read(data);
        } catch (RuntimeException | DataFormatException e) {
            throw unreadable(path, e.getMessage());
        }
    }

    private static GameException unreadable(String path, String why) {
        return new GameException("G3025", "'" + path + "' is not a PNG a Canvas can read (" + why + ")",
                "Save it as a PNG, not interlaced.");
    }

    private static final byte[] SIGNATURE = {(byte) 137, 80, 78, 71, 13, 10, 26, 10};

    private static Png read(byte[] d) throws DataFormatException {
        for (int i = 0; i < 8; i++) {
            if (d.length < 8 || d[i] != SIGNATURE[i]) throw new IllegalArgumentException("not a PNG file");
        }
        int at = 8;
        int width = 0, height = 0, depth = 0, type = -1;
        byte[] palette = null;
        byte[] paletteAlpha = null;
        int[] key = null;                                        // tRNS of grey (1 value) or RGB (3), full depth
        ByteArrayOutputStream idat = new ByteArrayOutputStream();
        while (at + 8 <= d.length) {
            int length = int32(d, at);
            String chunk = new String(d, at + 4, 4, java.nio.charset.StandardCharsets.US_ASCII);
            int body = at + 8;
            if (length < 0 || body + length > d.length) throw new IllegalArgumentException("cut short");
            if (chunk.equals("IHDR")) {
                width = int32(d, body);
                height = int32(d, body + 4);
                depth = d[body + 8] & 255;
                type = d[body + 9] & 255;
                if ((d[body + 12] & 255) != 0) throw new IllegalArgumentException("interlaced");
            } else if (chunk.equals("PLTE")) {
                palette = java.util.Arrays.copyOfRange(d, body, body + length);
            } else if (chunk.equals("tRNS")) {
                if (type == 3) {
                    paletteAlpha = java.util.Arrays.copyOfRange(d, body, body + length);
                } else {
                    key = new int[length / 2];
                    for (int i = 0; i < key.length; i++) key[i] = ((d[body + 2 * i] & 255) << 8) | (d[body + 2 * i + 1] & 255);
                }
            } else if (chunk.equals("IDAT")) {
                idat.write(d, body, length);
            } else if (chunk.equals("IEND")) {
                break;
            }
            at = body + length + 4;                              // the CRC is not checked: the build copied the file
        }
        if (width <= 0 || height <= 0 || type < 0) throw new IllegalArgumentException("no IHDR");
        int channels = type == 0 || type == 3 ? 1 : type == 2 ? 3 : type == 4 ? 2 : type == 6 ? 4 : 0;
        if (channels == 0) throw new IllegalArgumentException("colour type " + type);
        if (type == 3 && palette == null) throw new IllegalArgumentException("no palette");
        if (depth != 1 && depth != 2 && depth != 4 && depth != 8 && depth != 16) {
            throw new IllegalArgumentException("bit depth " + depth);
        }
        int rowBytes = (width * channels * depth + 7) / 8;
        int step = Math.max(1, channels * depth / 8);            // bytes from a pixel to the one on its left
        byte[] raw = new byte[height * (rowBytes + 1)];
        Inflater inflater = new Inflater();
        inflater.setInput(idat.toByteArray());
        int got = 0;
        while (got < raw.length && !inflater.finished()) {
            int n = inflater.inflate(raw, got, raw.length - got);
            if (n == 0 && (inflater.needsInput() || inflater.needsDictionary())) break;
            got += n;
        }
        inflater.end();
        if (got < raw.length) throw new IllegalArgumentException("cut short");

        int[] out = new int[width * height];
        byte[] row = new byte[rowBytes];
        byte[] above = new byte[rowBytes];
        for (int y = 0; y < height; y++) {
            int start = y * (rowBytes + 1);
            int filter = raw[start] & 255;
            for (int i = 0; i < rowBytes; i++) {
                int x = raw[start + 1 + i] & 255;
                int a = i >= step ? row[i - step] & 255 : 0;
                int b = above[i] & 255;
                int c = i >= step ? above[i - step] & 255 : 0;
                switch (filter) {
                    case 0: break;
                    case 1: x += a; break;
                    case 2: x += b; break;
                    case 3: x += (a + b) >> 1; break;
                    case 4: x += paeth(a, b, c); break;
                    default: throw new IllegalArgumentException("filter " + filter);
                }
                row[i] = (byte) x;
            }
            for (int px = 0; px < width; px++) out[y * width + px] = pixel(row, px, type, depth, palette, paletteAlpha, key);
            byte[] swap = above;
            above = row;
            row = swap;
        }
        return new Png(width, height, out);
    }

    private static int pixel(byte[] row, int x, int type, int depth, byte[] palette, byte[] paletteAlpha, int[] key) {
        if (type == 3) {
            int i = sample(row, x, 0, 1, depth);
            if (3 * i + 2 >= palette.length) throw new IllegalArgumentException("palette index " + i);
            int alpha = paletteAlpha != null && i < paletteAlpha.length ? paletteAlpha[i] & 255 : 255;
            return (alpha << 24) | ((palette[3 * i] & 255) << 16) | ((palette[3 * i + 1] & 255) << 8)
                    | (palette[3 * i + 2] & 255);
        }
        if (type == 0 || type == 4) {
            int channels = type == 0 ? 1 : 2;
            int grey = sample(row, x, 0, channels, depth);
            int alpha = type == 4 ? eight(sample(row, x, 1, channels, depth), depth)
                    : key != null && key.length >= 1 && grey == key[0] ? 0 : 255;
            int g = eight(grey, depth);
            return (alpha << 24) | (g << 16) | (g << 8) | g;
        }
        int channels = type == 2 ? 3 : 4;
        int r = sample(row, x, 0, channels, depth), g = sample(row, x, 1, channels, depth),
                b = sample(row, x, 2, channels, depth);
        int alpha = type == 6 ? eight(sample(row, x, 3, channels, depth), depth)
                : key != null && key.length >= 3 && r == key[0] && g == key[1] && b == key[2] ? 0 : 255;
        return (alpha << 24) | (eight(r, depth) << 16) | (eight(g, depth) << 8) | eight(b, depth);
    }

    /** Channel {@code c} of pixel {@code x}, at the file's depth. */
    private static int sample(byte[] row, int x, int c, int channels, int depth) {
        if (depth == 8) return row[x * channels + c] & 255;
        if (depth == 16) {
            int i = 2 * (x * channels + c);
            return ((row[i] & 255) << 8) | (row[i + 1] & 255);
        }
        int bit = (x * channels + c) * depth;                    // 1, 2, 4: grey or palette, packed from the left
        return ((row[bit >> 3] & 255) >> (8 - depth - (bit & 7))) & ((1 << depth) - 1);
    }

    /** A sample at the file's depth, as 0..255 (16 bits keep their high byte, as every decoder does). */
    private static int eight(int value, int depth) {
        if (depth == 8) return value;
        if (depth == 16) return value >> 8;
        return value * 255 / ((1 << depth) - 1);
    }

    private static int paeth(int a, int b, int c) {
        int p = a + b - c;
        int pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        if (pa <= pb && pa <= pc) return a;
        return pb <= pc ? b : c;
    }

    private static int int32(byte[] d, int at) {
        return ((d[at] & 255) << 24) | ((d[at + 1] & 255) << 16) | ((d[at + 2] & 255) << 8) | (d[at + 3] & 255);
    }
}
