package __PACKAGE__;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Locale;

/**
 * speech.* -- the phone reading aloud, and writing down what it hears.
 *
 * Reading aloud is the text-to-speech engine the phone already has. There is
 * one voice per app, not one per screen: it belongs to the process, starts the
 * first time something is said (which takes a moment, so what was asked for is
 * kept until it is ready) and goes on speaking when the screen changes.
 *
 * Listening opens the phone's own microphone sheet. It is the recogniser's
 * screen and the recogniser's permission, so this app asks for none.
 */
public final class ApkpySpeech {

    private static final int NONE = 0, STARTING = 1, READY = 2, FAILED = 3;
    private static final int CHUNK = 3500;

    private static TextToSpeech sVoice;
    private static int sState = NONE;
    private static int sNext = 1;
    // What was asked for while the engine was still starting, and who asked.
    private static final ArrayList<Runnable> sWhenReady = new ArrayList<Runnable>();
    private static final ArrayList<ApkpyKit.Done> sAsked = new ArrayList<ApkpyKit.Done>();
    // utterance id -> who is waiting for it to end. Only the last piece of a
    // long text has somebody waiting.
    private static final HashMap<String, ApkpyKit.Done> sWaiting =
            new HashMap<String, ApkpyKit.Done>();
    private static final java.util.HashSet<String> sSpeaking = new java.util.HashSet<String>();

    private ApkpySpeech() { }

    private static synchronized void ended(String id, boolean ok, String word) {
        sSpeaking.remove(id);
        ApkpyKit.Done done = sWaiting.remove(id);
        ApkpyKit.answer(done, ok, word);
    }

    private static synchronized void start(Context context) {
        if (sState != NONE) return;
        sState = STARTING;
        final Context app = context.getApplicationContext();
        sVoice = new TextToSpeech(app, new TextToSpeech.OnInitListener() {
            @Override public void onInit(int status) {
                ArrayList<Runnable> waiting;
                synchronized (ApkpySpeech.class) {
                    sState = status == TextToSpeech.SUCCESS ? READY : FAILED;
                    if (sState == READY) {
                        sVoice.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                            @Override public void onStart(String id) { }
                            @Override public void onDone(String id) { ended(id, true, "ok"); }
                            @Override public void onError(String id) { ended(id, false, "failed"); }
                            @Override public void onError(String id, int code) { ended(id, false, "failed"); }
                            @Override public void onStop(String id, boolean interrupted) {
                                ended(id, false, "stopped");
                            }
                        });
                    }
                    waiting = new ArrayList<Runnable>(sWhenReady);
                    sWhenReady.clear();
                    sAsked.clear();
                }
                for (Runnable work : waiting) work.run();
            }
        });
    }

    /** Read text aloud. done: (true, "ok") at the end, or (false, why not). */
    public static void say(Activity activity, final String text, final String language,
                           final String rate, final String pitch, final ApkpyKit.Done done) {
        final String words = ApkpyKit.text(text);
        if (words.trim().isEmpty()) {
            ApkpyKit.answer(done, true, "ok");
            return;
        }
        Runnable work = new Runnable() {
            @Override public void run() { speak(words, language, rate, pitch, done); }
        };
        synchronized (ApkpySpeech.class) {
            if (sState == NONE) start(activity);
            if (sState == STARTING) {
                // Like a sentence that replaces the one being read: only the
                // last thing asked for is said once the engine is up.
                for (ApkpyKit.Done earlier : sAsked) ApkpyKit.answer(earlier, false, "stopped");
                sWhenReady.clear();
                sAsked.clear();
                sWhenReady.add(work);
                sAsked.add(done);
                return;
            }
        }
        work.run();
    }

    private static void speak(String words, String language, String rate, String pitch,
                              ApkpyKit.Done done) {
        ArrayList<String> ids = new ArrayList<String>();
        synchronized (ApkpySpeech.class) {
            if (sState != READY || sVoice == null) {
                ApkpyKit.answer(done, false, "no_engine");
                return;
            }
            String tag = ApkpyKit.text(language).trim();
            try {
                if (tag.isEmpty()) {
                    // A language chosen for the sentence before must not stay
                    // for this one.
                    if (sVoice.getDefaultVoice() != null) sVoice.setVoice(sVoice.getDefaultVoice());
                } else {
                    int result = sVoice.setLanguage(Locale.forLanguageTag(tag.replace('_', '-')));
                    if (result == TextToSpeech.LANG_MISSING_DATA
                            || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                        ApkpyKit.answer(done, false, "language_unavailable");
                        return;
                    }
                }
            } catch (Throwable odd) {
                // An engine that cannot change voice still speaks in its own.
            }
            sVoice.setSpeechRate((float) ApkpyKit.clamp(
                    ApkpyKit.number(rate, 1.0), __MIN_RATE__, __MAX_RATE__));
            sVoice.setPitch((float) ApkpyKit.clamp(
                    ApkpyKit.number(pitch, 1.0), __MIN_PITCH__, __MAX_PITCH__));

            // An engine takes a few thousand characters at a time, so a long
            // text is handed over in pieces cut at a space. The first piece
            // replaces whatever was being said; the rest queue behind it.
            int limit = Math.min(CHUNK, Math.max(200, TextToSpeech.getMaxSpeechInputLength() - 1));
            int at = 0;
            boolean first = true;
            while (at < words.length()) {
                int end = Math.min(words.length(), at + limit);
                if (end < words.length()) {
                    int space = words.lastIndexOf(' ', end);
                    if (space > at) end = space;
                }
                String piece = words.substring(at, end);
                at = end;
                String id = "apkpy-" + (sNext++);
                boolean last = at >= words.length();
                if (last && done != null) sWaiting.put(id, done);
                sSpeaking.add(id);
                ids.add(id);
                int queued = sVoice.speak(piece,
                        first ? TextToSpeech.QUEUE_FLUSH : TextToSpeech.QUEUE_ADD,
                        new Bundle(), id);
                first = false;
                if (queued != TextToSpeech.SUCCESS) {
                    for (String made : ids) { sSpeaking.remove(made); sWaiting.remove(made); }
                    ApkpyKit.answer(done, false, "failed");
                    return;
                }
            }
        }
    }

    public static synchronized String stop(Activity activity) {
        for (ApkpyKit.Done asked : sAsked) ApkpyKit.answer(asked, false, "stopped");
        sWhenReady.clear();
        sAsked.clear();
        if (sVoice != null && sState == READY) {
            try { sVoice.stop(); } catch (Throwable ignored) { }
        }
        return "ok";
    }

    public static synchronized String isSpeaking(Activity activity) {
        boolean busy = !sWhenReady.isEmpty() || !sSpeaking.isEmpty();
        return ApkpyKit.flag(busy);
    }

    private static Intent recogniser(String prompt, String language) {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        if (!ApkpyKit.text(prompt).trim().isEmpty()) {
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, prompt);
        }
        String tag = ApkpyKit.text(language).trim().replace('_', '-');
        if (!tag.isEmpty()) intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, tag);
        return intent;
    }

    /** Whether some app on this phone turns speech into text. */
    public static String canListen(Activity activity) {
        try {
            return ApkpyKit.flag(recogniser("", "")
                    .resolveActivity(activity.getPackageManager()) != null);
        } catch (Throwable unknown) {
            return ApkpyKit.flag(false);
        }
    }

    /** Open the microphone. done: (true, the words) or (false, why not). */
    public static void listen(Activity activity, String prompt, String language,
                              final ApkpyKit.Done done) {
        ApkpyKitActivity.forResult(activity, recogniser(prompt, language),
                new ApkpyKitActivity.Result() {
                    @Override public void run(int resultCode, Intent data) {
                        if (resultCode == ApkpyKitActivity.NO_APP) {
                            ApkpyKit.answer(done, false, "no_recogniser");
                            return;
                        }
                        if (resultCode != Activity.RESULT_OK || data == null) {
                            ApkpyKit.answer(done, false, "cancelled");
                            return;
                        }
                        ArrayList<String> heard =
                                data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
                        String words = heard == null || heard.isEmpty()
                                ? "" : ApkpyKit.text(heard.get(0)).trim();
                        if (words.isEmpty()) ApkpyKit.answer(done, false, "nothing_heard");
                        else ApkpyKit.answer(done, true, words);
                    }
                });
    }
}
