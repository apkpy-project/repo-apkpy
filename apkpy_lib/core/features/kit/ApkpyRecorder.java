package __PACKAGE__;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.pm.PackageManager;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.SystemClock;

import java.io.File;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * recorder.* -- the microphone, recorded into a file of the app.
 *
 * One recording at a time, and it belongs to the app rather than to a screen:
 * moving from one screen to the next does not stop it. start() asks for the
 * microphone the first time, in Android's own dialog. stop() answers the path
 * of an .m4a file (AAC) in the app's folder, which audio.play() plays,
 * uploads.audio() sends and files.save_copy() hands to the person.
 *
 * Android only lets an app hear the microphone while it is on screen. A
 * recording left running when the person leaves the app keeps its file, with
 * silence for the time away.
 */
public final class ApkpyRecorder {

    private static MediaRecorder sRecorder;
    private static File sFile;
    private static long sSince;

    private ApkpyRecorder() { }

    /** Start. done: (true, "ok") once it is recording, or (false, why not). */
    public static void start(final Activity activity, final ApkpyKit.Done done) {
        final Context app = activity.getApplicationContext();
        synchronized (ApkpyRecorder.class) {
            if (sRecorder != null) {
                ApkpyKit.answer(done, false, "busy");
                return;
            }
        }
        if (!app.getPackageManager().hasSystemFeature(PackageManager.FEATURE_MICROPHONE)) {
            ApkpyKit.answer(done, false, "no_microphone");
            return;
        }
        ApkpyKitActivity.forPermission(activity, Manifest.permission.RECORD_AUDIO,
                new ApkpyKitActivity.Granted() {
                    @Override public void run(boolean granted, boolean blocked) {
                        if (!granted) {
                            ApkpyKit.answer(done, false,
                                    blocked ? "permission_blocked" : "permission_denied");
                            return;
                        }
                        String word = begin(app);
                        ApkpyKit.answer(done, word.equals("ok"), word);
                    }
                });
    }

    /** "ok" once it is recording, or the word for why not. */
    private static synchronized String begin(Context app) {
        if (sRecorder != null) return "busy";
        File folder = new File(app.getFilesDir(), "recordings");
        if (!folder.isDirectory() && !folder.mkdirs()) return "failed";
        String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
        File file = new File(folder, "recording-" + stamp + ".m4a");
        for (int copy = 2; file.exists(); copy++) {
            file = new File(folder, "recording-" + stamp + "-" + copy + ".m4a");
        }
        MediaRecorder recorder = null;
        try {
            recorder = Build.VERSION.SDK_INT >= 31 ? new MediaRecorder(app) : new MediaRecorder();
            recorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            recorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            recorder.setAudioSamplingRate(44100);
            recorder.setAudioEncodingBitRate(96000);
            recorder.setAudioChannels(1);
            recorder.setOutputFile(file.getAbsolutePath());
            recorder.prepare();
            recorder.start();
        } catch (Throwable refused) {
            // Another app holding the microphone, or a call in progress.
            try { if (recorder != null) recorder.release(); } catch (Throwable ignored) { }
            file.delete();
            return "failed";
        }
        sRecorder = recorder;
        sFile = file;
        sSince = SystemClock.elapsedRealtime();
        return "ok";
    }

    /** Stop, and answer the file's path -- "" when nothing was being recorded. */
    public static synchronized String stop(Activity activity) {
        if (sRecorder == null) return "";
        MediaRecorder recorder = sRecorder;
        File file = sFile;
        sRecorder = null;
        sFile = null;
        boolean kept = true;
        try {
            recorder.stop();
        } catch (RuntimeException tooShort) {
            // What stop() throws when it is called before a single frame was
            // written: there is no recording, and the empty file is not one.
            kept = false;
        }
        try { recorder.release(); } catch (Throwable ignored) { }
        if (!kept || file == null || file.length() == 0) {
            if (file != null) file.delete();
            return "";
        }
        return file.getAbsolutePath();
    }

    public static synchronized String isRecording(Activity activity) {
        return ApkpyKit.flag(sRecorder != null);
    }

    /** How long it has been recording, in whole seconds; "0" when it is not. */
    public static synchronized String seconds(Activity activity) {
        if (sRecorder == null) return "0";
        return String.valueOf((SystemClock.elapsedRealtime() - sSince) / 1000L);
    }
}
