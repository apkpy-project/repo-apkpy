package __PACKAGE__;

import android.app.Activity;
import android.app.Application;
import android.app.Fragment;
import android.app.KeyguardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.TypedValue;
import android.view.ActionMode;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.KeyboardShortcutGroup;
import android.view.Menu;
import android.view.MenuItem;
import android.view.MotionEvent;
import android.view.SearchEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

/**
 * app_lock.* -- the app locks itself, and the phone's own lock opens it.
 *
 * The rule is the app's, not a screen's: once said it is kept in a
 * preferences file of its own, and every screen follows it -- after the app
 * was closed from the recent apps too, since ApkpyAppLockStart starts this
 * class with the process, before any screen. The app is locked as it comes
 * back after the minutes away, or once nobody has touched it for that long
 * while it is in front.
 *
 * Locked, every screen of the app is covered and the phone's own prompt asks
 * for a fingerprint, a face or the screen lock -- Android draws that, so no
 * app can fake it or read what is typed into it. A phone with no screen lock
 * at all has nothing to ask for: then nothing is locked, and the app is told.
 */
public final class ApkpyAppLock {

    private static final String PREFS = "apkpy_app_lock";
    private static final String MINUTES = "minutes";
    private static final String TITLE = "title";
    private static final String LEFT_AT = "left_at";
    private static final String LOCKED = "locked";
    private static final String COVER = "apkpy-app-lock";
    private static final int ASKED = 0x4170;

    // What the lock says; kit_rules.APP_LOCK_WORDS has the same words.
    static final String HEADING = "%s is locked";
    static final String LINE = "Use your fingerprint, face or screen lock to open it.";
    static final String BUTTON = "Unlock";

    private static Application app;
    private static SharedPreferences prefs;
    private static Handler main;
    private static int started;             // screens of the app on show, or behind a dialog
    private static boolean rebuilding;      // one was stopped only to be built again
    private static boolean justSaid;        // the rule was first said as the app opened
    private static boolean locked;
    private static boolean asking;          // the phone's prompt is up
    private static boolean promptOwed;      // locked, and nobody asked yet
    private static long touchedAt;          // SystemClock.elapsedRealtime()
    private static Activity front;
    private static final Map<Activity, View> COVERED = new WeakHashMap<>();
    private static final Map<Activity, Object> BACK = new WeakHashMap<>();
    private static final Map<Activity, Boolean> SHOWN = new WeakHashMap<>();

    private ApkpyAppLock() { }

    // ── the calls ──────────────────────────────────────────────────────────

    public static String after(Activity activity, String minutes, String title) {
        double read = ApkpyKitRules.appLockMinutes(minutes);
        if (read < 0.0) return "invalid";
        start(activity);
        boolean fresh = !prefs.contains(MINUTES);
        SharedPreferences.Editor edit = prefs.edit()
                .putString(MINUTES, String.valueOf(read))
                .putString(TITLE, ApkpyKitRules.trim(title));
        if (fresh && started == 0) {
            // Said as the app opens, for the first time: what the app was
            // doing before it had a rule is no reason to lock it now.
            justSaid = true;
        }
        edit.apply();
        touched();
        recents(activity);
        onMain(IDLE);
        return secure() ? "ok" : "no_lock";
    }

    public static String now(final Activity activity) {
        start(activity);
        if (!secure()) return "no_lock";
        onMain(new Runnable() {
            @Override public void run() {
                lock();
            }
        });
        return "ok";
    }

    public static String off(final Activity activity) {
        start(activity);
        prefs.edit().clear().apply();
        onMain(new Runnable() {
            @Override public void run() {
                if (locked) open();
                if (main != null) main.removeCallbacks(IDLE);
                recents(activity);
            }
        });
        return "ok";
    }

    public static String locked(Activity activity) {
        start(activity);
        return ApkpyKitRules.flag(locked);
    }

    // ── the app, watched from the moment its process starts ────────────────

    /** From ApkpyAppLockStart, as the process starts, and from every call. */
    public static synchronized void start(Context context) {
        if (app != null) return;
        app = (Application) context.getApplicationContext();
        prefs = app.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        main = new Handler(Looper.getMainLooper());
        locked = prefs.getBoolean(LOCKED, false) && secure();
        promptOwed = locked;
        app.registerActivityLifecycleCallbacks(WATCH);
    }

    private static boolean ruled() {
        return prefs != null && prefs.contains(MINUTES);
    }

    private static double minutes() {
        return ApkpyKitRules.appLockMinutes(prefs.getString(MINUTES, "-1"));
    }

    /** Whether the phone has a lock to open the app with. */
    private static boolean secure() {
        if (app == null) return false;
        KeyguardManager keyguard = (KeyguardManager) app.getSystemService(Context.KEYGUARD_SERVICE);
        return keyguard != null && keyguard.isDeviceSecure();
    }

    private static final Application.ActivityLifecycleCallbacks WATCH =
            new Application.ActivityLifecycleCallbacks() {
        @Override public void onActivityCreated(Activity activity, Bundle saved) { }

        @Override public void onActivityStarted(Activity activity) {
            SHOWN.put(activity, Boolean.TRUE);
            if (started == 0) cameBack();
            started++;
            if (locked) cover(activity);
        }

        @Override public void onActivityResumed(Activity activity) {
            front = activity;
            touches(activity);
            recents(activity);
            if (locked) {
                cover(activity);
                if (promptOwed && !asking) ask(activity);
            } else {
                idle();
            }
        }

        @Override public void onActivityPaused(Activity activity) {
            if (front == activity) front = null;
        }

        @Override public void onActivityStopped(Activity activity) {
            SHOWN.remove(activity);
            started = Math.max(0, started - 1);
            if (started > 0) return;
            if (activity.isChangingConfigurations()) {
                rebuilding = true;          // turned, or the theme changed: not away
                return;
            }
            if (asking) return;             // the phone's own lock screen is in front
            wentAway();
        }

        @Override public void onActivitySaveInstanceState(Activity activity, Bundle out) { }

        @Override public void onActivityDestroyed(Activity activity) {
            COVERED.remove(activity);
            BACK.remove(activity);
            if (front == activity) front = null;
        }
    };

    private static void cameBack() {
        if (rebuilding) {
            rebuilding = false;
            return;
        }
        if (justSaid) {
            justSaid = false;
            return;
        }
        touched();
        if (asking) return;
        if (locked) {
            promptOwed = true;                          // still locked: ask again
            return;
        }
        if (!ruled()) return;
        long leftAt = prefs.getLong(LEFT_AT, 0L);
        prefs.edit().putLong(LEFT_AT, 0L).apply();      // in front, from now
        if (ApkpyKitRules.appLockDue(leftAt, System.currentTimeMillis(), minutes())) lock();
    }

    private static void wentAway() {
        if (main != null) main.removeCallbacks(IDLE);
        if (!ruled()) return;
        prefs.edit().putLong(LEFT_AT, System.currentTimeMillis()).apply();
    }

    // ── untouched while in front ───────────────────────────────────────────

    private static void touched() {
        touchedAt = SystemClock.elapsedRealtime();
    }

    private static final Runnable IDLE = new Runnable() {
        @Override public void run() {
            idle();
        }
    };

    /** Lock once nobody has touched the app for the minutes, or look again then. */
    private static void idle() {
        if (main == null) return;
        main.removeCallbacks(IDLE);
        if (!ruled() || locked || started == 0) return;
        double minutes = minutes();
        if (minutes <= 0.0) return;                     // 0: only as it comes back
        long wait = (long) (minutes * 60000.0) - (SystemClock.elapsedRealtime() - touchedAt);
        if (wait <= 0L) {
            if (secure()) lock();
            return;
        }
        main.postDelayed(IDLE, wait);
    }

    /** Every touch and key of a screen's window, counted on its way in. */
    private static void touches(Activity activity) {
        Window window = activity.getWindow();
        Window.Callback current = window.getCallback();
        if (current instanceof Toucher || current == null) return;
        window.setCallback(new Toucher(activity, current));
    }

    // ── locked ─────────────────────────────────────────────────────────────

    private static void lock() {
        if (locked) return;
        if (!secure()) return;
        locked = true;
        promptOwed = true;
        if (prefs != null) prefs.edit().putBoolean(LOCKED, true).apply();
        if (main != null) main.removeCallbacks(IDLE);
        for (Activity each : new ArrayList<>(SHOWN.keySet())) {
            if (!each.isFinishing() && !each.isDestroyed()) cover(each);
        }
        if (front != null && !asking) ask(front);
    }

    private static void open() {
        locked = false;
        promptOwed = false;
        if (prefs != null) prefs.edit().putBoolean(LOCKED, false).putLong(LEFT_AT, 0L).apply();
        for (Activity each : new ArrayList<>(COVERED.keySet())) uncover(each);
        touched();
        idle();
    }

    private static void ask(final Activity activity) {
        if (asking || !locked) return;
        asking = true;
        promptOwed = false;
        String title = ApkpyKitRules.appLockTitle(prefs.getString(TITLE, ""), name(activity));
        if (Build.VERSION.SDK_INT >= 29) {
            BiometricPrompt.Builder builder = new BiometricPrompt.Builder(activity).setTitle(title);
            if (Build.VERSION.SDK_INT >= 30) {
                builder.setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK
                        | BiometricManager.Authenticators.DEVICE_CREDENTIAL);
            } else {
                builder.setDeviceCredentialAllowed(true);
            }
            try {
                builder.build().authenticate(new CancellationSignal(), activity.getMainExecutor(),
                        new BiometricPrompt.AuthenticationCallback() {
                    @Override public void onAuthenticationSucceeded(
                            BiometricPrompt.AuthenticationResult result) {
                        asking = false;
                        open();
                    }

                    @Override public void onAuthenticationError(int code, CharSequence said) {
                        asking = false;     // stays locked; the cover's button asks again
                    }
                });
            } catch (RuntimeException refused) {
                asking = false;
            }
            return;
        }
        // Android 7 to 9: the phone's own screen-lock check, as a screen of
        // its own, answered to a fragment that holds no view.
        KeyguardManager keyguard = (KeyguardManager) activity.getSystemService(Context.KEYGUARD_SERVICE);
        Intent check = keyguard == null ? null
                : keyguard.createConfirmDeviceCredentialIntent(title, null);
        if (check == null) {
            asking = false;
            return;
        }
        try {
            Asker asker = new Asker();
            activity.getFragmentManager().beginTransaction().add(asker, COVER).commitNow();
            asker.startActivityForResult(check, ASKED);
        } catch (RuntimeException refused) {
            asking = false;
        }
    }

    /** Receives the answer of the phone's lock screen, on Android 7 to 9. */
    public static final class Asker extends Fragment {
        @Override public void onActivityResult(int request, int result, Intent data) {
            if (request != ASKED) return;
            asking = false;
            if (result == Activity.RESULT_OK) open();
            try {
                getFragmentManager().beginTransaction().remove(this).commitAllowingStateLoss();
            } catch (RuntimeException gone) {
                // the screen went meanwhile
            }
        }
    }

    // ── the cover ──────────────────────────────────────────────────────────

    private static void cover(final Activity activity) {
        View had = COVERED.get(activity);
        ViewGroup decor = (ViewGroup) activity.getWindow().getDecorView();
        if (had != null && had.getParent() == decor) {
            had.bringToFront();
            return;
        }
        View cover = drawn(activity);
        decor.addView(cover, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        cover.bringToFront();
        COVERED.put(activity, cover);
        View content = activity.findViewById(android.R.id.content);
        if (content != null) {
            // What is under the cover is not read out by TalkBack either.
            content.setImportantForAccessibility(
                    View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
        }
        if (Build.VERSION.SDK_INT >= 33) {
            OnBackInvokedCallback leave = new OnBackInvokedCallback() {
                @Override public void onBackInvoked() {
                    activity.moveTaskToBack(true);
                }
            };
            activity.getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_OVERLAY, leave);
            BACK.put(activity, leave);
        }
    }

    private static void uncover(Activity activity) {
        View cover = COVERED.remove(activity);
        if (cover != null && cover.getParent() instanceof ViewGroup) {
            ((ViewGroup) cover.getParent()).removeView(cover);
        }
        View content = activity.findViewById(android.R.id.content);
        if (content != null) {
            content.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_AUTO);
        }
        Object leave = BACK.remove(activity);
        if (leave != null && Build.VERSION.SDK_INT >= 33) {
            activity.getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(
                    (OnBackInvokedCallback) leave);
        }
    }

    /** The app's name, a padlock and one button, in the app's own colours. */
    private static View drawn(final Activity activity) {
        int background = colour(activity, "apkpy_background", 0xFFFFFBFE);
        int text = colour(activity, "apkpy_text", 0xFF1D1B20);
        int muted = colour(activity, "apkpy_text_secondary", 0xFF49454F);
        int primary = colour(activity, "apkpy_primary", 0xFF6750A4);
        int onPrimary = colour(activity, "apkpy_on_primary", 0xFFFFFFFF);
        int tonal = colour(activity, "apkpy_nav_indicator", 0xFFE8DEF8);

        FrameLayout frame = new FrameLayout(activity);
        frame.setTag(COVER);
        frame.setBackgroundColor(background);
        frame.setClickable(true);       // nothing under it is touched
        frame.setFocusable(true);
        frame.setTranslationZ(dp(activity, 64));

        LinearLayout column = new LinearLayout(activity);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setGravity(Gravity.CENTER_HORIZONTAL);
        int side = dp(activity, 32);
        column.setPadding(side, 0, side, 0);

        Padlock padlock = new Padlock(activity, tonal, primary);
        column.addView(padlock, new LinearLayout.LayoutParams(dp(activity, 80), dp(activity, 80)));

        TextView heading = new TextView(activity);
        heading.setText(ApkpyKitRules.appLockHeading(name(activity)));
        heading.setTextColor(text);
        heading.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
        heading.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        heading.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams under = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        under.topMargin = dp(activity, 24);
        column.addView(heading, under);

        TextView line = new TextView(activity);
        line.setText(LINE);
        line.setTextColor(muted);
        line.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        line.setGravity(Gravity.CENTER);
        line.setMaxWidth(dp(activity, 280));
        LinearLayout.LayoutParams below = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        below.topMargin = dp(activity, 8);
        column.addView(line, below);

        TextView button = new TextView(activity);
        button.setText(BUTTON);
        button.setTextColor(onPrimary);
        button.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        button.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        button.setGravity(Gravity.CENTER);
        button.setMinHeight(dp(activity, 48));
        button.setMinWidth(dp(activity, 120));
        button.setPadding(dp(activity, 28), 0, dp(activity, 28), 0);
        GradientDrawable pill = new GradientDrawable();
        pill.setColor(primary);
        pill.setCornerRadius(dp(activity, 24));
        button.setBackground(pill);
        button.setClickable(true);
        button.setFocusable(true);
        button.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                ask(activity);
            }
        });
        LinearLayout.LayoutParams last = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        last.topMargin = dp(activity, 32);
        column.addView(button, last);

        frame.addView(column, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.CENTER));
        return frame;
    }

    /** A padlock on a tonal circle, drawn: the app has no image to bring. */
    private static final class Padlock extends View {
        private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final int tonal;
        private final int ink;
        private final RectF box = new RectF();

        Padlock(Context context, int tonal, int ink) {
            super(context);
            this.tonal = tonal;
            this.ink = ink;
            stroke.setStyle(Paint.Style.STROKE);
            stroke.setStrokeCap(Paint.Cap.ROUND);
            setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        }

        @Override protected void onDraw(Canvas canvas) {
            float w = getWidth();
            float h = getHeight();
            float cx = w / 2f;
            float cy = h / 2f;
            float r = Math.min(w, h) / 2f;
            fill.setColor(tonal);
            canvas.drawCircle(cx, cy, r, fill);
            float unit = r / 40f;
            // The shackle: an arch over the body.
            stroke.setColor(ink);
            stroke.setStrokeWidth(4.5f * unit);
            box.set(cx - 9f * unit, cy - 20f * unit, cx + 9f * unit, cy - 2f * unit);
            canvas.drawArc(box, 180f, 180f, false, stroke);
            canvas.drawLine(cx - 9f * unit, cy - 11f * unit, cx - 9f * unit, cy - 3f * unit, stroke);
            canvas.drawLine(cx + 9f * unit, cy - 11f * unit, cx + 9f * unit, cy - 3f * unit, stroke);
            // The body, and its keyhole in the circle's colour.
            fill.setColor(ink);
            box.set(cx - 15f * unit, cy - 4f * unit, cx + 15f * unit, cy + 20f * unit);
            canvas.drawRoundRect(box, 4f * unit, 4f * unit, fill);
            fill.setColor(tonal);
            canvas.drawCircle(cx, cy + 6f * unit, 3.5f * unit, fill);
            box.set(cx - 1.6f * unit, cy + 7f * unit, cx + 1.6f * unit, cy + 13f * unit);
            canvas.drawRoundRect(box, 1.6f * unit, 1.6f * unit, fill);
        }
    }

    /** Off the recent apps' picture, once the app has a rule (Android 13 on). */
    private static void recents(Activity activity) {
        if (Build.VERSION.SDK_INT >= 33) activity.setRecentsScreenshotEnabled(!ruled());
    }

    private static String name(Context context) {
        CharSequence label = context.getApplicationInfo().loadLabel(context.getPackageManager());
        return label == null ? "" : label.toString();
    }

    private static int colour(Context context, String name, int fallback) {
        int id = context.getResources().getIdentifier(name, "color", context.getPackageName());
        if (id == 0) return fallback;
        try {
            return context.getColor(id);
        } catch (RuntimeException missing) {
            return fallback;
        }
    }

    private static int dp(Context context, float value) {
        return Math.round(TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, value,
                context.getResources().getDisplayMetrics()));
    }

    private static void onMain(Runnable work) {
        if (Looper.myLooper() == Looper.getMainLooper()) work.run();
        else if (main != null) main.post(work);
    }

    // ── a screen's window, every touch counted ─────────────────────────────

    /** Hands everything to the window's own callback, and notes the touches
     *  and keys on their way. Back, while locked, leaves the app instead. */
    private static final class Toucher implements Window.Callback {
        private final Activity activity;
        private final Window.Callback inner;

        Toucher(Activity activity, Window.Callback inner) {
            this.activity = activity;
            this.inner = inner;
        }

        @Override public boolean dispatchKeyEvent(KeyEvent event) {
            if (locked && event.getKeyCode() == KeyEvent.KEYCODE_BACK) {
                if (event.getAction() == KeyEvent.ACTION_UP) activity.moveTaskToBack(true);
                return true;
            }
            touched();
            return inner.dispatchKeyEvent(event);
        }

        @Override public boolean dispatchTouchEvent(MotionEvent event) {
            touched();
            return inner.dispatchTouchEvent(event);
        }

        @Override public boolean dispatchKeyShortcutEvent(KeyEvent event) {
            return inner.dispatchKeyShortcutEvent(event);
        }

        @Override public boolean dispatchTrackballEvent(MotionEvent event) {
            return inner.dispatchTrackballEvent(event);
        }

        @Override public boolean dispatchGenericMotionEvent(MotionEvent event) {
            touched();
            return inner.dispatchGenericMotionEvent(event);
        }

        @Override public boolean dispatchPopulateAccessibilityEvent(AccessibilityEvent event) {
            return inner.dispatchPopulateAccessibilityEvent(event);
        }

        @Override public View onCreatePanelView(int featureId) {
            return inner.onCreatePanelView(featureId);
        }

        @Override public boolean onCreatePanelMenu(int featureId, Menu menu) {
            return inner.onCreatePanelMenu(featureId, menu);
        }

        @Override public boolean onPreparePanel(int featureId, View view, Menu menu) {
            return inner.onPreparePanel(featureId, view, menu);
        }

        @Override public boolean onMenuOpened(int featureId, Menu menu) {
            return inner.onMenuOpened(featureId, menu);
        }

        @Override public boolean onMenuItemSelected(int featureId, MenuItem item) {
            return inner.onMenuItemSelected(featureId, item);
        }

        @Override public void onWindowAttributesChanged(WindowManager.LayoutParams attrs) {
            inner.onWindowAttributesChanged(attrs);
        }

        @Override public void onContentChanged() {
            inner.onContentChanged();
        }

        @Override public void onWindowFocusChanged(boolean hasFocus) {
            inner.onWindowFocusChanged(hasFocus);
        }

        @Override public void onAttachedToWindow() {
            inner.onAttachedToWindow();
        }

        @Override public void onDetachedFromWindow() {
            inner.onDetachedFromWindow();
        }

        @Override public void onPanelClosed(int featureId, Menu menu) {
            inner.onPanelClosed(featureId, menu);
        }

        @Override public boolean onSearchRequested() {
            return inner.onSearchRequested();
        }

        @Override public boolean onSearchRequested(SearchEvent searchEvent) {
            return inner.onSearchRequested(searchEvent);
        }

        @Override public ActionMode onWindowStartingActionMode(ActionMode.Callback callback) {
            return inner.onWindowStartingActionMode(callback);
        }

        @Override public ActionMode onWindowStartingActionMode(ActionMode.Callback callback,
                                                               int type) {
            return inner.onWindowStartingActionMode(callback, type);
        }

        @Override public void onActionModeStarted(ActionMode mode) {
            inner.onActionModeStarted(mode);
        }

        @Override public void onActionModeFinished(ActionMode mode) {
            inner.onActionModeFinished(mode);
        }

        @Override public void onProvideKeyboardShortcuts(List<KeyboardShortcutGroup> data,
                                                         Menu menu, int deviceId) {
            inner.onProvideKeyboardShortcuts(data, menu, deviceId);
        }

        @Override public void onPointerCaptureChanged(boolean hasCapture) {
            inner.onPointerCaptureChanged(hasCapture);
        }
    }
}
