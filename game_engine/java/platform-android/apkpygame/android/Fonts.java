package apkpygame.android;

import android.graphics.Typeface;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;

/** Android makes a Typeface from a file: the font's bytes go through a temporary one. */
final class Fonts {
    private Fonts() { }

    static Typeface typeface(byte[] data) {
        File file = null;
        try {
            file = File.createTempFile("apkpygame", ".ttf");
            FileOutputStream out = new FileOutputStream(file);
            try {
                out.write(data);
            } finally {
                out.close();
            }
            return Typeface.createFromFile(file);
        } catch (IOException | RuntimeException e) {
            return null;                                   // the system font: the build already read this file
        } finally {
            if (file != null) file.delete();
        }
    }
}
