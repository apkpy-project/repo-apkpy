package apkpygame.core;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;

/**
 * Save slots as files in a folder (SLOT.json). A write never leaves a slot
 * half written, even if the process dies in the middle: the text goes to
 * SLOT.json.tmp, the old file is moved to SLOT.json.bak, the new one takes
 * its place, and the .bak is deleted. A read that finds no SLOT.json but a
 * .bak (the process died between the two renames) reads the .bak.
 * Plain java.io, so it also runs on Androids without java.nio.file.
 */
public final class FileSaves implements Platform.SaveStore {
    private final File folder;
    private final Platform.Logger log;

    public FileSaves(File folder, Platform.Logger log) {
        this.folder = folder;
        this.log = log;
    }

    @Override public String read(String slot) {
        File file = file(slot, ".json");
        File bak = file(slot, ".json.bak");
        File from = file.isFile() ? file : bak.isFile() ? bak : null;
        if (from == null) return null;
        try {
            InputStream in = new FileInputStream(from);
            try {
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                byte[] buf = new byte[8192];
                for (int n; (n = in.read(buf)) > 0; ) out.write(buf, 0, n);
                return new String(out.toByteArray(), "UTF-8");
            } finally {
                in.close();
            }
        } catch (IOException e) {
            log.error("could not read the save " + slot, e);
            return null;
        }
    }

    @Override public void write(String slot, String text) {
        File file = file(slot, ".json");
        File tmp = file(slot, ".json.tmp");
        File bak = file(slot, ".json.bak");
        try {
            folder.mkdirs();
            FileOutputStream out = new FileOutputStream(tmp);
            try {
                out.write(text.getBytes("UTF-8"));
                out.getFD().sync();
            } finally {
                out.close();
            }
            bak.delete();
            if (file.isFile() && !file.renameTo(bak)) throw new IOException("could not move " + file);
            if (!tmp.renameTo(file)) throw new IOException("could not move " + tmp);
            bak.delete();
        } catch (IOException e) {
            log.error("could not write the save " + slot, e);
        }
    }

    @Override public void delete(String slot) {
        file(slot, ".json").delete();
        file(slot, ".json.bak").delete();
        file(slot, ".json.tmp").delete();
    }

    private File file(String slot, String ext) {
        return new File(folder, slot + ext);
    }
}
