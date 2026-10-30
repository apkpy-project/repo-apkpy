package __PACKAGE__;

import android.app.Activity;
import android.content.Context;
import android.content.pm.PackageManager;
import android.health.connect.AggregateRecordsRequest;
import android.health.connect.AggregateRecordsResponse;
import android.health.connect.HealthConnectException;
import android.health.connect.HealthConnectManager;
import android.health.connect.TimeInstantRangeFilter;
import android.health.connect.datatypes.ActiveCaloriesBurnedRecord;
import android.health.connect.datatypes.AggregationType;
import android.health.connect.datatypes.DistanceRecord;
import android.health.connect.datatypes.ExerciseSessionRecord;
import android.health.connect.datatypes.FloorsClimbedRecord;
import android.health.connect.datatypes.HeartRateRecord;
import android.health.connect.datatypes.HydrationRecord;
import android.health.connect.datatypes.RestingHeartRateRecord;
import android.health.connect.datatypes.SleepSessionRecord;
import android.health.connect.datatypes.StepsRecord;
import android.health.connect.datatypes.TotalCaloriesBurnedRecord;
import android.health.connect.datatypes.WeightRecord;
import android.health.connect.datatypes.units.Energy;
import android.health.connect.datatypes.units.Length;
import android.health.connect.datatypes.units.Mass;
import android.health.connect.datatypes.units.Volume;
import android.os.Build;
import android.os.OutcomeReceiver;

import java.time.Instant;
import java.util.ArrayList;
import java.util.TimeZone;

/**
 * health.* -- what the phone's health records say.
 *
 * The records are Health Connect's: one store on the phone that a watch, a
 * scale and the fitness apps write into, and that an app may read with the
 * person's leave, one kind of record at a time. It is part of Android from
 * 14 on, which is where these calls work; before that available() is False.
 *
 * A reading is one number for a stretch of time -- the steps of a day, the
 * average heart rate of a week -- which Health Connect adds up itself, so
 * two apps that both counted the same walk are counted once.
 *
 * Nothing is read with the app in the background, and a fresh grant reaches
 * thirty days back; both are Health Connect's own rules.
 */
public final class ApkpyHealth {

    static final String POLICY = "__HEALTH_POLICY__";

    private ApkpyHealth() { }

    /** The permission Health Connect names for a kind, or "". */
    static String permission(String kind) {
__HEALTH_ARMS__
        return "";
    }

    static boolean has(Context context) {
        if (Build.VERSION.SDK_INT < 34) return false;
        try {
            return context.getSystemService("healthconnect") != null;
        } catch (Throwable unknown) {
            return false;
        }
    }

    private static boolean granted(Context context, String permission) {
        return !permission.isEmpty()
                && context.checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED;
    }

    public static String available(Activity activity) {
        return ApkpyKit.flag(has(activity));
    }

    public static String allowed(Activity activity, String kind) {
        return ApkpyKit.flag(has(activity)
                && granted(activity, permission(ApkpyKitRules.trim(kind))));
    }

    // apkpy:launcher -- left out of an app that never calls this
    /** Ask for every kind named, in Health Connect's own screen. */
    public static void ask(Activity activity, String kinds, final ApkpyKit.Done done) {
        if (!has(activity)) {
            ApkpyKit.answer(done, false, "unavailable");
            return;
        }
        ArrayList<String> wanted = new ArrayList<String>();
        for (String word : ApkpyKit.text(kinds).split(",")) {
            String permission = permission(ApkpyKitRules.trim(word));
            if (!permission.isEmpty() && !wanted.contains(permission)) wanted.add(permission);
        }
        if (wanted.isEmpty()) {
            ApkpyKit.answer(done, false, "denied");
            return;
        }
        ApkpyKitActivity.forPermissions(activity, wanted.toArray(new String[0]),
                new ApkpyKitActivity.Granted() {
                    @Override public void run(boolean granted, boolean blocked) {
                        ApkpyKit.answer(done, granted, granted ? "ok" : "denied");
                    }
                });
    }
    // apkpy:launcher-end

    /** One number for the time between start and end. */
    public static void read(Activity activity, String kind, String start, String end,
                            ApkpyKit.Done done) {
        String what = ApkpyKitRules.trim(kind);
        if (!has(activity)) {
            ApkpyKit.answer(done, false, "unavailable");
            return;
        }
        String permission = permission(what);
        long[] period = ApkpyKitRules.healthPeriod(
                start, end, System.currentTimeMillis(), TimeZone.getDefault());
        if (permission.isEmpty() || period == null) {
            ApkpyKit.answer(done, false, "invalid");
            return;
        }
        if (!granted(activity, permission)) {
            ApkpyKit.answer(done, false, "no_permission");
            return;
        }
        try {
            Records.read(activity.getApplicationContext(), what, period[0], period[1], done);
        } catch (SecurityException refused) {
            ApkpyKit.answer(done, false, "no_permission");
        } catch (Throwable broken) {
            ApkpyKit.answer(done, false, "failed");
        }
    }

    /** Apart, so a phone before Android 14 never has to look at it. */
    private static final class Records {

        private static AggregationType<?> type(String kind) {
            if ("steps".equals(kind)) return StepsRecord.STEPS_COUNT_TOTAL;
            if ("distance".equals(kind)) return DistanceRecord.DISTANCE_TOTAL;
            if ("active_calories".equals(kind)) {
                return ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL;
            }
            if ("calories".equals(kind)) return TotalCaloriesBurnedRecord.ENERGY_TOTAL;
            if ("heart_rate".equals(kind)) return HeartRateRecord.BPM_AVG;
            if ("resting_heart_rate".equals(kind)) return RestingHeartRateRecord.BPM_AVG;
            if ("sleep".equals(kind)) return SleepSessionRecord.SLEEP_DURATION_TOTAL;
            if ("weight".equals(kind)) return WeightRecord.WEIGHT_AVG;
            if ("floors".equals(kind)) return FloorsClimbedRecord.FLOORS_CLIMBED_TOTAL;
            if ("exercise".equals(kind)) return ExerciseSessionRecord.EXERCISE_DURATION_TOTAL;
            if ("hydration".equals(kind)) return HydrationRecord.VOLUME_TOTAL;
            return null;
        }

        /** The reading in the unit the table promises, or null for none. */
        private static Double number(String kind, Object value) {
            if (value == null) return null;
            if (value instanceof Length) return ((Length) value).getInMeters();
            // Health Connect counts in calories; a person counts in kilocalories.
            if (value instanceof Energy) return ((Energy) value).getInCalories() / 1000.0;
            if (value instanceof Mass) return ((Mass) value).getInGrams() / 1000.0;
            if (value instanceof Volume) return ((Volume) value).getInLiters();
            if (!(value instanceof Number)) return null;
            double plain = ((Number) value).doubleValue();
            // A length of time arrives in milliseconds and is answered in minutes.
            if ("sleep".equals(kind) || "exercise".equals(kind)) return plain / 60000.0;
            return plain;
        }

        private static boolean average(String kind) {
            return "heart_rate".equals(kind) || "resting_heart_rate".equals(kind)
                    || "weight".equals(kind);
        }

        static void read(Context app, String kind, long begin, long finish,
                         ApkpyKit.Done done) {
            AggregationType<?> type = type(kind);
            HealthConnectManager manager = app.getSystemService(HealthConnectManager.class);
            if (type == null || manager == null) {
                ApkpyKit.answer(done, false, type == null ? "invalid" : "unavailable");
                return;
            }
            ask(app, manager, kind, type, begin, finish, done);
        }

        private static <T> void ask(Context app, HealthConnectManager manager,
                                    final String kind, final AggregationType<T> type,
                                    long begin, long finish, final ApkpyKit.Done done) {
            AggregateRecordsRequest<T> request = new AggregateRecordsRequest.Builder<T>(
                    new TimeInstantRangeFilter.Builder()
                            .setStartTime(Instant.ofEpochMilli(begin))
                            .setEndTime(Instant.ofEpochMilli(finish))
                            .build())
                    .addAggregationType(type)
                    .build();
            manager.aggregate(request, app.getMainExecutor(),
                    new OutcomeReceiver<AggregateRecordsResponse<T>, HealthConnectException>() {
                        @Override public void onResult(AggregateRecordsResponse<T> response) {
                            Double found = number(kind, response.get(type));
                            if (found != null) {
                                ApkpyKit.answer(done, true,
                                        ApkpyKitRules.healthValue(kind, found));
                            } else if (average(kind)) {
                                // An average of nothing is no number at all.
                                ApkpyKit.answer(done, false, "no_data");
                            } else {
                                ApkpyKit.answer(done, true, "0");
                            }
                        }

                        @Override public void onError(HealthConnectException error) {
                            boolean refused = error != null && error.getErrorCode()
                                    == HealthConnectException.ERROR_SECURITY;
                            ApkpyKit.answer(done, false, refused ? "no_permission" : "failed");
                        }
                    });
        }
    }
}
