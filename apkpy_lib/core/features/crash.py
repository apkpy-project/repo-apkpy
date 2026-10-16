# -*- coding: utf-8 -*-
"""Compiler support for ``crash`` -- knowing that the app fell over.

    from apkpy_lib import crash, https, lifecycle

    def on_start():
        report = crash.last()
        if report:
            https.post("https://example.com/crashes",
                       json={"trace": report}, on_result=sent)
            crash.clear()

    lifecycle(home, on_mount=on_start)

**Why this is not a service.** ApkPy does not pick a crash vendor for you, and
does not invent an endpoint: it keeps the last report where the app can read
it on the next launch, and what happens then is the app's decision -- post it
somewhere, show it, ignore it. Everything needed to send it already exists.

**Chaining is not optional.** The handler passes the throwable on to whatever
handler was already installed. Android's own is what shows "the app has
stopped" and kills the process; swallowing the crash leaves a frozen window
that never comes back, which is worse than the crash was.

**A plain file, not the encrypted store.** ``storage`` goes through the
Keystore, and a handler that needs working crypto is a handler that loses the
report exactly when the crypto is what broke. The trade is that a stack trace
sits unencrypted in the app's private directory -- readable by the app and by
nobody else without root.
"""

FILE_NAME = 'apkpy_crash.txt'


def shared_class_java(package):
    """``ApkpyCrashHandler.java`` -- one handler for the whole process.

    A field on an Activity dies with it and a static on one screen's class is
    invisible to the next, which is the same reason the Bluetooth link has a
    class of its own. The application Context is held rather than an Activity
    Context: the handler outlives every screen by design.
    """
    return '''package %(package)s;

import android.content.Context;

import java.io.File;
import java.io.PrintWriter;
import java.io.StringWriter;

/** Writes the last crash where the next launch can find it. */
public final class ApkpyCrashHandler implements Thread.UncaughtExceptionHandler {

    public static final String FILE = "%(file)s";

    private final Context context;
    private final Thread.UncaughtExceptionHandler previous;

    private ApkpyCrashHandler(Context context, Thread.UncaughtExceptionHandler previous) {
        this.context = context;
        this.previous = previous;
    }

    /** Installs once per process; calling it from every screen is harmless. */
    public static void install(Context context) {
        Thread.UncaughtExceptionHandler current =
                Thread.getDefaultUncaughtExceptionHandler();
        if (current instanceof ApkpyCrashHandler) {
            return;
        }
        Thread.setDefaultUncaughtExceptionHandler(
                new ApkpyCrashHandler(context.getApplicationContext(), current));
    }

    @Override
    public void uncaughtException(Thread thread, Throwable error) {
        // Throwable, not Exception: an OutOfMemoryError while writing the
        // report must not stop the app from dying properly.
        try {
            write(context, describe(thread, error));
        } catch (Throwable ignored) {
        }
        if (previous != null) {
            previous.uncaughtException(thread, error);
        } else {
            android.os.Process.killProcess(android.os.Process.myPid());
        }
    }

    private static String describe(Thread thread, Throwable error) {
        StringWriter text = new StringWriter();
        PrintWriter out = new PrintWriter(text);
        out.println("when: " + new java.util.Date().toString());
        out.println("thread: " + (thread == null ? "?" : thread.getName()));
        out.println("android: " + android.os.Build.VERSION.RELEASE
                + " (api " + android.os.Build.VERSION.SDK_INT + ")");
        out.println("device: " + android.os.Build.MANUFACTURER
                + " " + android.os.Build.MODEL);
        out.println();
        error.printStackTrace(out);
        out.flush();
        return text.toString();
    }

    private static void write(Context context, String report) throws Exception {
        File file = new File(context.getFilesDir(), FILE);
        java.io.FileOutputStream stream = new java.io.FileOutputStream(file);
        try {
            stream.write(report.getBytes("UTF-8"));
        } finally {
            stream.close();
        }
    }

    /** The report from the previous run, or "" when the app closed cleanly. */
    public static String last(Context context) {
        File file = new File(context.getFilesDir(), FILE);
        if (!file.exists()) {
            return "";
        }
        java.io.FileInputStream stream = null;
        try {
            stream = new java.io.FileInputStream(file);
            java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
            byte[] chunk = new byte[4096];
            int read;
            while ((read = stream.read(chunk)) > 0) {
                buffer.write(chunk, 0, read);
            }
            return buffer.toString("UTF-8");
        } catch (Exception problem) {
            return "";
        } finally {
            try {
                if (stream != null) {
                    stream.close();
                }
            } catch (Exception ignored) {
            }
        }
    }

    public static void clear(Context context) {
        new File(context.getFilesDir(), FILE).delete();
    }
}
''' % {'package': package, 'file': FILE_NAME}


def uses_crash(tree):
    """Whether the module reads or clears a crash report, read from the source.

    Taken from the syntax rather than from parsed commands because
    ``crash.last()`` is a *value* -- it appears inside an assignment, not as a
    command of its own -- and a check that only walked commands would miss the
    common case and leave the handler uninstalled.
    """
    import ast

    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'crash'
                and node.func.attr in ('last', 'clear')):
            return True
    return False
