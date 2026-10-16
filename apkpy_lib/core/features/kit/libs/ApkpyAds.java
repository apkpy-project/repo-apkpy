package __PACKAGE__;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.widget.FrameLayout;

import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdListener;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.AdSize;
import com.google.android.gms.ads.AdView;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.OnUserEarnedRewardListener;
import com.google.android.gms.ads.interstitial.InterstitialAd;
import com.google.android.gms.ads.interstitial.InterstitialAdLoadCallback;
import com.google.android.gms.ads.rewarded.RewardItem;
import com.google.android.gms.ads.rewarded.RewardedAd;
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback;
import com.google.android.ump.ConsentForm;
import com.google.android.ump.ConsentInformation;
import com.google.android.ump.ConsentRequestParameters;
import com.google.android.ump.FormError;
import com.google.android.ump.UserMessagingPlatform;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;

/**
 * ads.* -- Google AdMob.
 *
 * Three kinds of ad. A banner has a place on a screen and stays there. An
 * interstitial takes the whole screen at a pause in the app. A rewarded ad
 * is one the person chooses to watch, and is paid for with whatever the app
 * promised.
 *
 * Before the first ad of any kind, the person is asked what the law where
 * they live says they must be asked -- Google's own form, shown only where
 * it is required -- and no ad is requested until that is settled. An app
 * does not have to remember to do it.
 *
 * A full-screen ad takes a moment to arrive. One that was fetched ahead with
 * prepare() opens the instant it is asked for; one that was not is fetched
 * then, and shown only if it arrives while the person is still where they
 * were -- an ad that takes the screen ten seconds after the pause it was
 * meant for is worse than no ad. It is kept for the next time instead.
 */
public final class ApkpyAds {

    /** How long an ad that was not fetched ahead may take and still be shown. */
    private static final long WAIT_INTERSTITIAL = 5000L;
    private static final long WAIT_REWARDED = 15000L;

    private static final HashMap<String, InterstitialAd> INTERSTITIALS =
            new HashMap<String, InterstitialAd>();
    private static final HashMap<String, RewardedAd> REWARDED = new HashMap<String, RewardedAd>();
    private static final HashSet<String> LOADING = new HashSet<String>();

    /** What is waiting for the library to have started. */
    private static final ArrayList<Runnable> WAITING = new ArrayList<Runnable>();
    private static int sStart;          // 0 not started, 1 starting, 2 started
    private static boolean sAsked;
    /** Who is waiting to hear how the question of consent ended. */
    private static final ArrayList<Settled> SETTLING = new ArrayList<Settled>();
    private static boolean sSettling;

    private ApkpyAds() { }

    /**
     * Why an ad did not come. Nothing is said on the screen -- an ad that is
     * missing is not the person's problem -- so it is said here, where
     * whoever is building the app reads it: adb logcat -s ApkPy
     */
    private static void note(String what, String why) {
        android.util.Log.w("ApkPy", "ads: " + what + (why == null ? "" : ": " + why));
    }

    // ── consent, and starting the library ────────────────────────────────────

    private interface Settled {
        void run(boolean mayAsk);
    }

    private static ConsentInformation consentOf(Context context) {
        return UserMessagingPlatform.getConsentInformation(context.getApplicationContext());
    }

    /**
     * Ask what has to be asked, once for the life of the process, and say
     * whether ads may be requested. No connection is not a no: the answer
     * the person gave last time still stands.
     *
     * A screen that shows a banner and fetches two ads ahead gets here three
     * times at once. The question is put once, and the others wait for its
     * answer: each asking for itself put Google's form up once apiece.
     */
    private static void settle(final Activity activity, Settled waiting) {
        final ConsentInformation consent = consentOf(activity);
        if (sAsked) {
            waiting.run(consent.canRequestAds());
            return;
        }
        SETTLING.add(waiting);
        if (sSettling) return;
        sSettling = true;
        final Settled then = new Settled() {
            @Override public void run(boolean mayAsk) {
                sSettling = false;
                ArrayList<Settled> all = new ArrayList<Settled>(SETTLING);
                SETTLING.clear();
                for (Settled each : all) each.run(mayAsk);
            }
        };
        try {
            consent.requestConsentInfoUpdate(activity,
                    new ConsentRequestParameters.Builder().build(),
                    new ConsentInformation.OnConsentInfoUpdateSuccessListener() {
                        @Override public void onConsentInfoUpdateSuccess() {
                            if (activity.isFinishing() || activity.isDestroyed()) {
                                then.run(consent.canRequestAds());
                                return;
                            }
                            UserMessagingPlatform.loadAndShowConsentFormIfRequired(activity,
                                    new ConsentForm.OnConsentFormDismissedListener() {
                                        @Override public void onConsentFormDismissed(
                                                FormError problem) {
                                            sAsked = problem == null;
                                            if (problem != null) {
                                                note("the consent form could not be shown",
                                                        problem.getMessage());
                                            }
                                            then.run(consent.canRequestAds());
                                        }
                                    });
                        }
                    },
                    new ConsentInformation.OnConsentInfoUpdateFailureListener() {
                        @Override public void onConsentInfoUpdateFailure(FormError problem) {
                            note("consent could not be checked",
                                    problem == null ? null : problem.getMessage());
                            then.run(consent.canRequestAds());
                        }
                    });
        } catch (Throwable broken) {
            then.run(consent.canRequestAds());
        }
    }

    /**
     * Run work once the library has started. Starting it reads from disk, so
     * Google asks for it off the thread that draws -- and for nothing to be
     * requested until that has returned.
     */
    private static void started(Context context, Runnable work) {
        if (sStart == 2) {
            work.run();
            return;
        }
        WAITING.add(work);
        if (sStart == 1) return;
        sStart = 1;
        final Context app = context.getApplicationContext();
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    MobileAds.initialize(app);
                } catch (Throwable broken) {
                    // Each request reports its own failure.
                }
                ApkpyKit.main(new Runnable() {
                    @Override public void run() {
                        sStart = 2;
                        ArrayList<Runnable> all = new ArrayList<Runnable>(WAITING);
                        WAITING.clear();
                        for (Runnable each : all) each.run();
                    }
                });
            }
        }, "apkpy-ads").start();
    }

    /** Run work once ads may be requested; refused runs when they may not. */
    private static void ready(final Activity activity, final Runnable work,
                              final Runnable refused) {
        ApkpyKit.main(new Runnable() {
            @Override public void run() {
                settle(activity, new Settled() {
                    @Override public void run(boolean mayAsk) {
                        if (!mayAsk) {
                            if (refused != null) refused.run();
                            return;
                        }
                        started(activity, work);
                    }
                });
            }
        });
    }

    public static void consent(final Activity activity, final ApkpyKit.Done done) {
        ApkpyKit.main(new Runnable() {
            @Override public void run() {
                sAsked = false;
                settle(activity, new Settled() {
                    @Override public void run(boolean mayAsk) {
                        if (mayAsk) {
                            started(activity, new Runnable() {
                                @Override public void run() { }
                            });
                        }
                        ApkpyKit.answer(done, mayAsk, mayAsk ? "ok" : "failed");
                    }
                });
            }
        });
    }

    public static String needsPrivacyOptions(Activity activity) {
        try {
            return ApkpyKit.flag(consentOf(activity).getPrivacyOptionsRequirementStatus()
                    == ConsentInformation.PrivacyOptionsRequirementStatus.REQUIRED);
        } catch (Throwable unknown) {
            return ApkpyKit.flag(false);
        }
    }

    public static void privacyOptions(final Activity activity, final ApkpyKit.Done done) {
        ApkpyKit.main(new Runnable() {
            @Override public void run() {
                try {
                    UserMessagingPlatform.showPrivacyOptionsForm(activity,
                            new ConsentForm.OnConsentFormDismissedListener() {
                                @Override public void onConsentFormDismissed(FormError problem) {
                                    ApkpyKit.answer(done, problem == null,
                                            problem == null ? "ok" : "failed");
                                }
                            });
                } catch (Throwable broken) {
                    ApkpyKit.answer(done, false, "failed");
                }
            }
        });
    }

    private static String word(LoadAdError problem) {
        int code = problem == null ? -1 : problem.getCode();
        String why = problem == null ? null : code + " " + problem.getMessage();
        if (code == AdRequest.ERROR_CODE_INTERNAL_ERROR) {
            // The error a phone gives when it cannot reach Google's ad hosts
            // at all, and it names nothing.
            why += " (a private DNS or a VPN that filters ads on this phone does this)";
        }
        note("no ad", why);
        if (code == AdRequest.ERROR_CODE_NETWORK_ERROR) return "network";
        if (code == AdRequest.ERROR_CODE_NO_FILL
                || code == AdRequest.ERROR_CODE_MEDIATION_NO_FILL) return "no_fill";
        if (code == AdRequest.ERROR_CODE_INVALID_REQUEST) return "invalid";
        return "failed";
    }

    private static boolean inFront(Activity activity) {
        return !activity.isFinishing() && !activity.isDestroyed() && activity.hasWindowFocus();
    }

    // ── the banner ───────────────────────────────────────────────────────────

    private static final String SLOT = "apkpy.ads.banner";

    public static String banner(final Activity activity, String unit, String position) {
        final String id = ApkpyKitRules.adUnit(unit, "banner");
        if (id.isEmpty()) return "invalid";
        final boolean top = "top".equals(ApkpyKitRules.trim(position));
        ApkpyKit.main(new Runnable() {
            @Override public void run() {
                place(activity, id, top);
            }
        });
        return "ok";
    }

    public static String hideBanner(final Activity activity) {
        ApkpyKit.main(new Runnable() {
            @Override public void run() {
                Slot slot = slotOf(activity);
                if (slot != null) slot.close();
            }
        });
        return "ok";
    }

    private static Slot slotOf(Activity activity) {
        ViewGroup content = activity.findViewById(android.R.id.content);
        View found = content == null ? null : content.findViewWithTag(SLOT);
        return found instanceof Slot ? (Slot) found : null;
    }

    private static void place(final Activity activity, String id, boolean top) {
        if (activity.isFinishing() || activity.isDestroyed()) return;
        ViewGroup content = activity.findViewById(android.R.id.content);
        if (content == null || content.getChildCount() == 0) return;
        Slot old = slotOf(activity);
        if (old != null) old.close();

        DisplayMetrics metrics = activity.getResources().getDisplayMetrics();
        int widthPx = content.getWidth() > 0 ? content.getWidth() : metrics.widthPixels;
        AdSize size = AdSize.getCurrentOrientationAnchoredAdaptiveBannerAdSize(
                activity, Math.max(1, (int) (widthPx / metrics.density)));
        final AdView view = new AdView(activity);
        view.setAdUnitId(id);
        view.setAdSize(size);
        final Slot slot = new Slot(activity, content, view, size.getHeightInPixels(activity), top);
        view.setAdListener(new AdListener() {
            @Override public void onAdFailedToLoad(LoadAdError problem) {
                // No ad this time: the screen gets its room back.
                word(problem);
                slot.shut();
            }
        });
        ready(activity, new Runnable() {
            @Override public void run() {
                if (slot.mClosed) return;
                try {
                    view.loadAd(new AdRequest.Builder().build());
                } catch (Throwable broken) {
                    slot.shut();
                }
            }
        }, new Runnable() {
            @Override public void run() {
                note("no banner", "the question of consent is not settled");
                slot.shut();
            }
        });
    }

    /**
     * The banner's place on a screen.
     *
     * It is laid over the edge of the screen, and the screen is made that
     * much shorter so nothing of the app is under it. The room is taken the
     * moment the banner is asked for, at the height the ad will have: a
     * screen that jumps when the ad arrives puts the ad under a finger that
     * was aiming at something else.
     *
     * The app's screen keeps its own room for the system bar at its edge;
     * that strip ends up behind the ad, and this draws the same strip again
     * beyond it, in the screen's colour, so the ad sits clear of the gesture
     * bar or the clock.
     */
    private static final class Slot extends FrameLayout
            implements Application.ActivityLifecycleCallbacks, View.OnLayoutChangeListener {

        private final Activity mActivity;
        private final ViewGroup mContent;
        private final View mScreen;
        private final AdView mAd;
        private final int mHeight;
        private final boolean mTop;
        private boolean mOpen = true;
        boolean mClosed;
        private final Runnable mFit = new Runnable() {
            @Override public void run() {
                fit();
            }
        };

        Slot(Activity activity, ViewGroup content, AdView ad, int height, boolean top) {
            super(activity);
            mActivity = activity;
            mContent = content;
            mScreen = content.getChildAt(0);
            mAd = ad;
            mHeight = height;
            mTop = top;
            setTag(SLOT);
            int ground = ground();
            setBackgroundColor(ground);
            addView(ad, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, height, Gravity.CENTER_HORIZONTAL));
            // A hairline where the app ends and the ad begins.
            View line = new View(activity);
            line.setBackgroundColor(dark(ground) ? 0x24FFFFFF : 0x1F000000);
            int hair = Math.max(1, Math.round(
                    activity.getResources().getDisplayMetrics().density * 0.75f));
            addView(line, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, hair, top ? Gravity.BOTTOM : Gravity.TOP));
            content.addView(this, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                    top ? Gravity.TOP : Gravity.BOTTOM));
            content.addOnLayoutChangeListener(this);
            activity.getApplication().registerActivityLifecycleCallbacks(this);
            fit();
        }

        /** The colour of the screen where the banner goes. */
        private int ground() {
            if (!mTop) {
                // Under a bar of tabs the banner continues the bar.
                int bar = mActivity.getResources().getIdentifier(
                        "bottom_nav", "id", mActivity.getPackageName());
                View tabs = bar == 0 ? null : mActivity.findViewById(bar);
                if (tabs != null && tabs.getVisibility() == View.VISIBLE
                        && tabs.getBackground() instanceof ColorDrawable) {
                    return ((ColorDrawable) tabs.getBackground()).getColor() | 0xFF000000;
                }
            }
            if (mScreen != null && mScreen.getBackground() instanceof ColorDrawable) {
                int own = ((ColorDrawable) mScreen.getBackground()).getColor();
                if (Color.alpha(own) == 255) return own;
            }
            TypedValue found = new TypedValue();
            if (mActivity.getTheme().resolveAttribute(android.R.attr.colorBackground, found, true)
                    && found.type >= TypedValue.TYPE_FIRST_COLOR_INT
                    && found.type <= TypedValue.TYPE_LAST_COLOR_INT) {
                return found.data | 0xFF000000;
            }
            return Color.WHITE;
        }

        private static boolean dark(int color) {
            return (0.299 * Color.red(color) + 0.587 * Color.green(color)
                    + 0.114 * Color.blue(color)) / 255.0 < 0.5;
        }

        // Both arrive in the middle of a layout pass, and what fit() moves
        // would start another: it waits for this one to end.
        private void refit() {
            removeCallbacks(mFit);
            post(mFit);
        }

        @Override
        public WindowInsets onApplyWindowInsets(WindowInsets insets) {
            refit();
            return insets;
        }

        @Override
        public void onLayoutChange(View view, int left, int top, int right, int bottom,
                                   int oldLeft, int oldTop, int oldRight, int oldBottom) {
            if (bottom - top != oldBottom - oldTop || top != oldTop) refit();
        }

        /** Put the banner clear of the system bar, and the screen clear of the banner. */
        @SuppressWarnings("deprecation")
        void fit() {
            if (mClosed) return;
            int bar = 0;
            boolean typing = false;
            WindowInsets insets = mContent.getRootWindowInsets();
            if (insets != null) {
                if (Build.VERSION.SDK_INT >= 30) {
                    android.graphics.Insets bars = insets.getInsets(
                            WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                    bar = mTop ? bars.top : bars.bottom;
                    typing = insets.isVisible(WindowInsets.Type.ime());
                } else {
                    bar = mTop ? insets.getSystemWindowInsetTop()
                            : insets.getSystemWindowInsetBottom();
                }
            }
            // How much of that bar is over this frame: all of it when the app
            // draws edge to edge, none when the system keeps the bar apart.
            int[] at = new int[2];
            mContent.getLocationInWindow(at);
            int window = mContent.getRootView().getHeight();
            int under = mTop ? bar - at[1] : at[1] + mContent.getHeight() - (window - bar);
            under = mContent.getHeight() == 0 ? 0 : Math.max(0, Math.min(bar, under));
            if (getPaddingTop() != (mTop ? under : 0) || getPaddingBottom() != (mTop ? 0 : under)) {
                setPadding(0, mTop ? under : 0, 0, mTop ? 0 : under);
            }
            // A keyboard has the bottom of the screen; the banner waits.
            boolean shown = mOpen && !typing;
            int visible = shown ? View.VISIBLE : mOpen ? View.INVISIBLE : View.GONE;
            if (getVisibility() != visible) setVisibility(visible);
            room(shown ? mHeight : 0);
        }

        private void room(int height) {
            if (mScreen == null
                    || !(mScreen.getLayoutParams() instanceof ViewGroup.MarginLayoutParams)) {
                return;
            }
            ViewGroup.MarginLayoutParams params =
                    (ViewGroup.MarginLayoutParams) mScreen.getLayoutParams();
            if ((mTop ? params.topMargin : params.bottomMargin) == height) return;
            if (mTop) params.topMargin = height;
            else params.bottomMargin = height;
            mScreen.setLayoutParams(params);
        }

        /** No ad to show: give the room back, and keep the place. */
        void shut() {
            mOpen = false;
            fit();
        }

        void close() {
            if (mClosed) return;
            mOpen = false;
            room(0);
            mClosed = true;
            mContent.removeOnLayoutChangeListener(this);
            mActivity.getApplication().unregisterActivityLifecycleCallbacks(this);
            try {
                mAd.destroy();
            } catch (Throwable ignored) {
                // Already gone.
            }
            if (getParent() instanceof ViewGroup) ((ViewGroup) getParent()).removeView(this);
        }

        @Override public void onActivityResumed(Activity activity) {
            if (activity == mActivity && !mClosed) mAd.resume();
        }

        @Override public void onActivityPaused(Activity activity) {
            if (activity == mActivity && !mClosed) mAd.pause();
        }

        @Override public void onActivityDestroyed(Activity activity) {
            if (activity == mActivity) close();
        }

        @Override public void onActivityCreated(Activity activity, Bundle state) { }
        @Override public void onActivityStarted(Activity activity) { }
        @Override public void onActivityStopped(Activity activity) { }
        @Override public void onActivitySaveInstanceState(Activity activity, Bundle state) { }
    }

    // ── full-screen ads ──────────────────────────────────────────────────────

    private interface Arrived<T> {
        void run(T ad, String problem);
    }

    private static void loadInterstitial(Context context, final String id,
                                         final Arrived<InterstitialAd> then) {
        final Context app = context.getApplicationContext();
        if (!LOADING.add("i" + id)) {
            if (then != null) then.run(null, "not_ready");
            return;
        }
        try {
            InterstitialAd.load(app, id, new AdRequest.Builder().build(),
                    new InterstitialAdLoadCallback() {
                        @Override public void onAdLoaded(InterstitialAd ad) {
                            LOADING.remove("i" + id);
                            if (then != null) then.run(ad, "");
                            else INTERSTITIALS.put(id, ad);
                        }

                        @Override public void onAdFailedToLoad(LoadAdError problem) {
                            LOADING.remove("i" + id);
                            if (then != null) then.run(null, word(problem));
                        }
                    });
        } catch (Throwable broken) {
            LOADING.remove("i" + id);
            if (then != null) then.run(null, "failed");
        }
    }

    private static void loadRewarded(Context context, final String id,
                                     final Arrived<RewardedAd> then) {
        final Context app = context.getApplicationContext();
        if (!LOADING.add("r" + id)) {
            if (then != null) then.run(null, "not_ready");
            return;
        }
        try {
            RewardedAd.load(app, id, new AdRequest.Builder().build(),
                    new RewardedAdLoadCallback() {
                        @Override public void onAdLoaded(RewardedAd ad) {
                            LOADING.remove("r" + id);
                            if (then != null) then.run(ad, "");
                            else REWARDED.put(id, ad);
                        }

                        @Override public void onAdFailedToLoad(LoadAdError problem) {
                            LOADING.remove("r" + id);
                            if (then != null) then.run(null, word(problem));
                        }
                    });
        } catch (Throwable broken) {
            LOADING.remove("r" + id);
            if (then != null) then.run(null, "failed");
        }
    }

    /** Fetch ahead whichever of the two is named and not already here. */
    public static String prepare(final Activity activity, String interstitial, String rewarded) {
        boolean first = !ApkpyKitRules.trim(interstitial).isEmpty();
        boolean second = !ApkpyKitRules.trim(rewarded).isEmpty();
        final String one = first ? ApkpyKitRules.adUnit(interstitial, "interstitial") : "";
        final String two = second ? ApkpyKitRules.adUnit(rewarded, "rewarded") : "";
        if ((first && one.isEmpty()) || (second && two.isEmpty())) return "invalid";
        ready(activity, new Runnable() {
            @Override public void run() {
                if (!one.isEmpty() && !INTERSTITIALS.containsKey(one)) {
                    loadInterstitial(activity, one, null);
                }
                if (!two.isEmpty() && !REWARDED.containsKey(two)) {
                    loadRewarded(activity, two, null);
                }
            }
        }, null);
        return "ok";
    }

    public static void interstitial(final Activity activity, String unit,
                                    final ApkpyKit.Done done) {
        final String id = ApkpyKitRules.adUnit(unit, "interstitial");
        if (id.isEmpty()) {
            ApkpyKit.answer(done, false, "invalid");
            return;
        }
        ready(activity, new Runnable() {
            @Override public void run() {
                InterstitialAd held = INTERSTITIALS.remove(id);
                if (held != null) {
                    show(activity, id, held, done);
                    return;
                }
                final long asked = SystemClock.elapsedRealtime();
                loadInterstitial(activity, id, new Arrived<InterstitialAd>() {
                    @Override public void run(InterstitialAd ad, String problem) {
                        if (ad == null) {
                            ApkpyKit.answer(done, false, problem);
                        } else if (SystemClock.elapsedRealtime() - asked > WAIT_INTERSTITIAL
                                || !inFront(activity)) {
                            INTERSTITIALS.put(id, ad);
                            ApkpyKit.answer(done, false, "not_ready");
                        } else {
                            show(activity, id, ad, done);
                        }
                    }
                });
            }
        }, new Runnable() {
            @Override public void run() {
                ApkpyKit.answer(done, false, "failed");
            }
        });
    }

    private static void show(final Activity activity, final String id, InterstitialAd ad,
                             final ApkpyKit.Done done) {
        ad.setFullScreenContentCallback(new FullScreenContentCallback() {
            @Override public void onAdDismissedFullScreenContent() {
                ApkpyKit.answer(done, true, "closed");
                // The next pause in the app finds one waiting.
                loadInterstitial(activity, id, null);
            }

            @Override public void onAdFailedToShowFullScreenContent(AdError problem) {
                ApkpyKit.answer(done, false, "failed");
            }
        });
        try {
            ad.show(activity);
        } catch (Throwable broken) {
            ApkpyKit.answer(done, false, "failed");
        }
    }

    public static void rewarded(final Activity activity, String unit, final ApkpyKit.Done done) {
        final String id = ApkpyKitRules.adUnit(unit, "rewarded");
        if (id.isEmpty()) {
            ApkpyKit.answer(done, false, "invalid");
            return;
        }
        ready(activity, new Runnable() {
            @Override public void run() {
                RewardedAd held = REWARDED.remove(id);
                if (held != null) {
                    show(activity, id, held, done);
                    return;
                }
                final long asked = SystemClock.elapsedRealtime();
                loadRewarded(activity, id, new Arrived<RewardedAd>() {
                    @Override public void run(RewardedAd ad, String problem) {
                        if (ad == null) {
                            ApkpyKit.answer(done, false, problem);
                        } else if (SystemClock.elapsedRealtime() - asked > WAIT_REWARDED
                                || !inFront(activity)) {
                            REWARDED.put(id, ad);
                            ApkpyKit.answer(done, false, "not_ready");
                        } else {
                            show(activity, id, ad, done);
                        }
                    }
                });
            }
        }, new Runnable() {
            @Override public void run() {
                ApkpyKit.answer(done, false, "failed");
            }
        });
    }

    private static void show(final Activity activity, final String id, RewardedAd ad,
                             final ApkpyKit.Done done) {
        // What was earned, or null: the reward is told while the ad is still
        // up, and the app hears once the person is back in it.
        final String[] earned = { null };
        ad.setFullScreenContentCallback(new FullScreenContentCallback() {
            @Override public void onAdDismissedFullScreenContent() {
                if (earned[0] != null) ApkpyKit.answer(done, true, earned[0]);
                else ApkpyKit.answer(done, false, "skipped");
                loadRewarded(activity, id, null);
            }

            @Override public void onAdFailedToShowFullScreenContent(AdError problem) {
                ApkpyKit.answer(done, false, "failed");
            }
        });
        try {
            ad.show(activity, new OnUserEarnedRewardListener() {
                @Override public void onUserEarnedReward(RewardItem reward) {
                    earned[0] = String.valueOf(reward == null ? 1 : reward.getAmount());
                }
            });
        } catch (Throwable broken) {
            ApkpyKit.answer(done, false, "failed");
        }
    }
}
