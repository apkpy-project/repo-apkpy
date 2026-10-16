package __PACKAGE__;

import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/**
 * files.read(), files.write() and files.append() -- text kept in the app's
 * own folder.
 *
 * The folder is getFilesDir(): private to the app, the same one
 * files.path(), files.exists() and files.download() already use, and gone
 * when the app is uninstalled. Nothing here needs a permission.
 *
 * Text is UTF-8 and is kept exactly as it was given: no line ending is
 * changed on the way in or on the way out.
 */
public final class ApkpyFiles {

    private ApkpyFiles() { }

    /** The file a name means, or null when it is not the name of one. */
    private static File place(Context context, String name) {
        File folder = context.getFilesDir();
        String given = ApkpyKitRules.trim(name);
        // files.path("notes.txt") and the callback of files.download() answer
        // the whole path; it means the same file as the bare name.
        String root = folder.getAbsolutePath() + File.separator;
        if (given.startsWith(root)) given = given.substring(root.length());
        String clean = ApkpyKitRules.fileName(given);
        return clean.isEmpty() ? null : new File(folder, clean);
    }

    /** The text of the file; "" when there is none, or it cannot be read. */
    public static String read(Context context, String name) {
        File file = place(context, name);
        if (file == null || !file.isFile()) return "";
        FileInputStream in = null;
        try {
            in = new FileInputStream(file);
            ByteArrayOutputStream held = new ByteArrayOutputStream();
            byte[] buffer = new byte[16 * 1024];
            int count;
            while ((count = in.read(buffer)) > 0) held.write(buffer, 0, count);
            String text = new String(held.toByteArray(), StandardCharsets.UTF_8);
            // A file saved by a desktop editor may open with a byte-order
            // mark, which is not part of what it says.
            return text.startsWith("﻿") ? text.substring(1) : text;
        } catch (Throwable unreadable) {
            // Out of memory included: a file too large to hold is not text
            // to put on a screen.
            return "";
        } finally {
            try { if (in != null) in.close(); } catch (Throwable ignored) { }
        }
    }

    /** Keep this text as the file, in place of what was there. */
    public static String write(Context context, String name, String text) {
        return put(context, name, text, false);
    }

    /** Add this text to the end of the file, making it if need be. */
    public static String append(Context context, String name, String text) {
        return put(context, name, text, true);
    }

    private static String put(Context context, String name, String text, boolean add) {
        File file = place(context, name);
        if (file == null) return "invalid";
        byte[] bytes = ApkpyKit.text(text).getBytes(StandardCharsets.UTF_8);
        File folder = file.getParentFile();
        if (folder != null && !folder.isDirectory() && !folder.mkdirs()) return "failed";
        // A file is replaced whole or not at all: the text goes into a spare
        // beside it, and the spare takes its name once it is on the disk. An
        // app closed halfway is left with the file it had.
        File spare = add ? file : new File(folder, ".apkpy-" + file.getName() + ".tmp");
        boolean ok = false;
        FileOutputStream out = null;
        try {
            out = new FileOutputStream(spare, add);
            out.write(bytes);
            out.flush();
            if (!add) out.getFD().sync();
            ok = true;
        } catch (Throwable refused) {
            ok = false;
        } finally {
            try { if (out != null) out.close(); } catch (Throwable ignored) { ok = false; }
        }
        if (ok && !add) ok = spare.renameTo(file);
        if (!ok && !add) spare.delete();
        return ok ? "ok" : "failed";
    }
}
