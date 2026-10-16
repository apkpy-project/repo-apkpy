package __PACKAGE__;

import android.app.*;
import android.content.*;
import android.os.*;
import androidx.core.app.NotificationCompat;
import org.json.*;
import java.util.*;

/** One native publisher for Activities, Workers and Firebase messages. */
public final class ApkpyNotifications {
    private static final String PREFIX = "apkpy:notification:";
    private static final String SUMMARY = "apkpy:summary:";
    private static final String TOKEN = "apkpy_notification_token";
    private static final String DEFAULT_CHANNEL = "apkpy_default";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final java.util.concurrent.ExecutorService IMAGES = java.util.concurrent.Executors.newSingleThreadExecutor();
    private static final Map<String, Long> REVISIONS = new HashMap<>();
    private static long nextRevision;
    private static final Map<Activity, Dispatch> DISPATCH = new HashMap<>();
    private static Activity active;
    private static boolean attached;
    public interface Dispatch { void run(String name); }
    private ApkpyNotifications() { }
    private static SharedPreferences prefs(Context c) { return c.getSharedPreferences("apkpy_notifications", Context.MODE_PRIVATE); }
    private static NotificationManager manager(Context c) { return (NotificationManager)c.getSystemService(Context.NOTIFICATION_SERVICE); }
    private static String appName(Context c) { return c.getApplicationInfo().loadLabel(c.getPackageManager()).toString(); }
    public static JSONObject spec(String... pairs) {
        JSONObject s = new JSONObject();
        try { for (int i=0;i<pairs.length;i+=2) s.put(pairs[i], pairs[i+1]); }
        catch (JSONException e) { throw new IllegalArgumentException(e); }
        return s;
    }
    public static int importance(String value) {
        switch (value) { __IMPORTANCE__ }
        throw new IllegalArgumentException("Notification importance: min, low, default or high");
    }
    public static boolean allowed(Context c) {
        return (Build.VERSION.SDK_INT < 33 || androidx.core.content.ContextCompat.checkSelfPermission(c,
            android.Manifest.permission.POST_NOTIFICATIONS) == android.content.pm.PackageManager.PERMISSION_GRANTED)
            && androidx.core.app.NotificationManagerCompat.from(c).areNotificationsEnabled();
    }
    public static synchronized void channel(Context context, String id, String name, String level) {
        if (id == null || id.trim().isEmpty() || name == null || name.trim().isEmpty())
            throw new IllegalArgumentException("Notification channel id and name cannot be empty");
        int value = importance(level);
        SharedPreferences p = prefs(context);
        if (!p.contains("channel:" + id)) p.edit().putString("channel:" + id, level).apply();
        if (Build.VERSION.SDK_INT >= 26) {
            // Android preserves the original importance and the person's settings.
            manager(context).createNotificationChannel(new NotificationChannel(id, name, value));
        }
    }
    private static Class<?> route(String screen, Class<?> fallback) {
        switch (screen) { __ROUTES__ }
        return fallback == null ? __START__.class : fallback;
    }
    private static boolean isScreen(String screen) {
        switch (screen) { __SCREENS__ }
        return false;
    }
    private static String picturePath(String value) {
        switch (value) { __PICTURES__ }
        return value;
    }
    private static int icon(String name) {
        switch (name) { __ICONS__ }
        return R.drawable.apkpy_notification_notifications;
    }
    private static JSONArray array(JSONObject spec, String key) {
        String raw = spec.optString(key);
        if (raw.isEmpty()) return new JSONArray();
        try { return new JSONArray(raw); }
        catch (JSONException e) { throw new IllegalArgumentException("Notification " + key + " must be a list", e); }
    }
    private static boolean flag(JSONObject s, String key) { return "true".equalsIgnoreCase(s.optString(key)); }
    private static long revision(String tag) {
        long n = ++nextRevision;
        REVISIONS.put(tag, n); return n;
    }
    public static void post(Context c, JSONObject spec, Class<?> owner) { post(c, spec, owner, null); }
    public static synchronized void post(Context context, JSONObject original, Class<?> owner, Intent custom) {
        Context c = context.getApplicationContext();
        JSONObject s;
        try { s = new JSONObject(original.toString()); }
        catch (JSONException e) { throw new IllegalArgumentException(e); }
        String style = s.optString("style", "none"), picture = s.optString("picture");
        if (!Arrays.asList(__STYLES__).contains(style))
            throw new IllegalArgumentException("Invalid notification style: " + style);
        if (style.equals("big_picture") && picture.isEmpty()) throw new IllegalArgumentException("big_picture requires a picture");
        if (!picture.isEmpty() && !style.equals("big_picture")) throw new IllegalArgumentException("picture requires big_picture style");
        String progress = s.optString("progress");
        if (!progress.isEmpty() && !progress.equals("indeterminate")) {
            double n;
            try { n = Double.parseDouble(progress); } catch (Exception e) { throw new IllegalArgumentException("Invalid notification progress"); }
            if (!Double.isFinite(n) || n < 0 || n > 100) throw new IllegalArgumentException("Notification progress must be 0 to 100");
        }
        String channelId = s.optString("channel", DEFAULT_CHANNEL);
        if (channelId.equals(DEFAULT_CHANNEL)) channel(c, DEFAULT_CHANNEL, appName(c), "default");
        if (!prefs(c).contains("channel:" + channelId)) throw new IllegalArgumentException("Unknown notification channel: " + channelId);
        if (!allowed(c)) { android.util.Log.w("ApkPy", "Notification not_allowed"); return; }
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = manager(c).getNotificationChannel(channelId);
            if (channel == null || channel.getImportance() == NotificationManager.IMPORTANCE_NONE) {
                android.util.Log.w("ApkPy", "Notification channel missing or disabled: " + channelId); return;
            }
        }
        String tag = PREFIX + s.optString("id", "apkpy_notification");
        long rev = revision(tag);
        if (style.equals("big_picture")) {
            IMAGES.execute(() -> {
                android.graphics.Bitmap bitmap = null;
                try {
                    String path = picturePath(picture);
                    android.graphics.BitmapFactory.Options opts = new android.graphics.BitmapFactory.Options();
                    opts.inJustDecodeBounds = true;
                    try (java.io.InputStream in = imageStream(c,path)) { android.graphics.BitmapFactory.decodeStream(in,null,opts); }
                    if (opts.outWidth < 1 || opts.outHeight < 1) throw new java.io.IOException("Not an image");
                    opts.inSampleSize = 1;
                    while (Math.max(opts.outWidth,opts.outHeight)/opts.inSampleSize > 1024) opts.inSampleSize *= 2;
                    opts.inJustDecodeBounds = false;
                    try (java.io.InputStream in = imageStream(c,path)) { bitmap = android.graphics.BitmapFactory.decodeStream(in,null,opts); }
                    if (bitmap == null) throw new java.io.IOException("Cannot decode image");
                    synchronized (ApkpyNotifications.class) {
                        if (Long.valueOf(rev).equals(REVISIONS.get(tag))) publish(c,s,owner,custom,bitmap);
                    }
                } catch (Exception e) { android.util.Log.e("ApkPy","Notification invalid_picture: " + e.getMessage()); }
                finally {
                    synchronized (ApkpyNotifications.class) {
                        if (Long.valueOf(rev).equals(REVISIONS.get(tag))) REVISIONS.remove(tag);
                    }
                }
            });
        } else { REVISIONS.remove(tag); publish(c,s,owner,custom,null); }
    }
    private static java.io.InputStream imageStream(Context c, String path) throws java.io.IOException {
        if (path.startsWith("content:")) return c.getContentResolver().openInputStream(android.net.Uri.parse(path));
        if (path.startsWith("apkpy_notifications/")) return c.getAssets().open(path);
        if (path.startsWith("http:" ) || path.startsWith("https:")) throw new java.io.IOException("Use a local picture");
        return new java.io.FileInputStream(path);
    }
    private static void publish(Context c, JSONObject s, Class<?> owner, Intent custom, android.graphics.Bitmap picture) {
        String id = s.optString("id", "apkpy_notification"), tag = PREFIX + id;
        removeEvents(c, tag);
        String channelId = s.optString("channel",DEFAULT_CHANNEL), callback = s.optString("on_tap");
        Class<?> target = route(callback,owner);
        if (isScreen(callback)) callback = "";
        Intent open = custom == null ? new Intent(c,target) : new Intent(custom);
        open.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        NotificationCompat.Builder b = new NotificationCompat.Builder(c,channelId)
            .setSmallIcon(icon(s.optString("icon","notifications")))
            .setContentTitle(s.optString("title")).setContentText(s.optString("message"))
            .setOngoing(flag(s,"ongoing")).setAutoCancel(!flag(s,"ongoing"))
            .setOnlyAlertOnce(true)
            .setContentIntent(event(c,tag,flag(s,"ongoing") ? "ongoing_tap" : "tap",callback,target,open,false));
        String level = prefs(c).getString("channel:"+channelId,"default");
        b.setPriority(importance(level)-3); // MIN=1 -> -2, LOW=2 -> -1, DEFAULT=3 -> 0, HIGH=4 -> 1.
        String when = s.optString("when");
        if (!when.isEmpty()) b.setWhen((long)Double.parseDouble(when));
        String style = s.optString("style","none");
        if (style.equals("big_text")) b.setStyle(new NotificationCompat.BigTextStyle().bigText(s.optString("message")));
        if (style.equals("big_picture")) b.setStyle(new NotificationCompat.BigPictureStyle().bigPicture(picture));
        if (style.equals("inbox")) {
            NotificationCompat.InboxStyle inbox = new NotificationCompat.InboxStyle();
            JSONArray lines = array(s,"lines");
            for (int i=0;i<lines.length();i++) inbox.addLine(lines.optString(i));
            b.setStyle(inbox);
        }
        String progress = s.optString("progress");
        if (!progress.isEmpty()) b.setProgress(100, progress.equals("indeterminate") ? 0 : (int)Double.parseDouble(progress), progress.equals("indeterminate"));
        for (int i=0;i<__MAX_ACTIONS__;i++) {
            String action = s.optString("action_"+i+"_callback");
            if (!action.isEmpty()) b.addAction(0,s.optString("action_"+i+"_title"),
                event(c,tag,"action"+i,action,owner == null ? __START__.class : owner,new Intent(c,owner == null ? __START__.class : owner)
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP),false));
        }
        b.setDeleteIntent(event(c,tag,"dismiss",s.optString("on_dismiss"),owner == null ? __START__.class : owner,new Intent(c,DismissReceiver.class),true));
        String group = s.optString("group");
        if (!group.isEmpty()) b.setGroup(PREFIX+group).setGroupAlertBehavior(NotificationCompat.GROUP_ALERT_CHILDREN);
        try { manager(c).notify(tag,0,b.build()); summaries(c); }
        catch (SecurityException e) { removeEvents(c,tag); android.util.Log.w("ApkPy","Notification not_allowed",e); }
    }
    private static PendingIntent event(Context c,String tag,String slot,String callback,Class<?> target,Intent intent,boolean broadcast) {
        String token = UUID.randomUUID().toString();
        JSONObject e = spec("tag",tag,"slot",slot,"callback",callback,"target",target.getName());
        prefs(c).edit().putString("event:"+token,e.toString()).commit();
        intent.setData(android.net.Uri.parse("apkpy-notification://event/"+token));
        intent.putExtra(TOKEN,token);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        return broadcast ? PendingIntent.getBroadcast(c,0,intent,flags) : PendingIntent.getActivity(c,0,intent,flags);
    }
    private static synchronized JSONObject consume(Context c,Intent i) {
        if (i == null) return null;
        String token = i.getStringExtra(TOKEN);
        if (token == null) return null;
        i.removeExtra(TOKEN);
        String raw = prefs(c).getString("event:"+token,null);
        try {
            if (raw == null) return null;
            JSONObject event = new JSONObject(raw);
            // Actions remain reusable until their notification is updated or cancelled.
            if (!event.optString("slot").startsWith("action") && !event.optString("slot").equals("ongoing_tap")) prefs(c).edit().remove("event:"+token).commit();
            return event;
        } catch (JSONException e) { return null; }
    }
    private static void removeEvents(Context c,String tag) {
        SharedPreferences.Editor edit = prefs(c).edit();
        for (Map.Entry<String,?> entry : prefs(c).getAll().entrySet()) {
            if (!entry.getKey().startsWith("event:")) continue;
            try { if (new JSONObject(String.valueOf(entry.getValue())).optString("tag").equals(tag)) edit.remove(entry.getKey()); }
            catch (JSONException ignored) { }
        }
        edit.apply();
    }
    public static synchronized void cancel(Context c,String id) {
        String tag=PREFIX+id; REVISIONS.remove(tag); manager(c).cancel(tag,0); removeEvents(c,tag); summaries(c);
    }
    public static synchronized void cancelAll(Context c) {
        REVISIONS.clear();
        for (android.service.notification.StatusBarNotification n : manager(c).getActiveNotifications())
            if (n.getTag()!=null && (n.getTag().startsWith(PREFIX)||n.getTag().startsWith(SUMMARY))) { manager(c).cancel(n.getTag(),n.getId()); removeEvents(c,n.getTag()); }
    }
    private static void summaries(Context c) {
        Map<String,List<android.service.notification.StatusBarNotification>> groups = new HashMap<>();
        for (android.service.notification.StatusBarNotification n : manager(c).getActiveNotifications()) {
            String group=n.getNotification().getGroup();
            if (n.getTag()!=null && n.getTag().startsWith(PREFIX) && group!=null)
                groups.computeIfAbsent(group,k->new ArrayList<>()).add(n);
        }
        for (android.service.notification.StatusBarNotification n : manager(c).getActiveNotifications())
            if (n.getTag()!=null && n.getTag().startsWith(SUMMARY) && !groups.containsKey(n.getNotification().getGroup())) manager(c).cancel(n.getTag(),0);
        for (Map.Entry<String,List<android.service.notification.StatusBarNotification>> row : groups.entrySet()) {
            String tag=SUMMARY+row.getKey();
            if (row.getValue().size()<2) { manager(c).cancel(tag,0); continue; }
            Notification first=row.getValue().get(0).getNotification();
            String channelId=Build.VERSION.SDK_INT>=26 ? first.getChannelId() : DEFAULT_CHANNEL;
            NotificationCompat.InboxStyle inbox=new NotificationCompat.InboxStyle();
            for (android.service.notification.StatusBarNotification n : row.getValue()) inbox.addLine(n.getNotification().extras.getCharSequence(Notification.EXTRA_TITLE,""));
            manager(c).notify(tag,0,new NotificationCompat.Builder(c,channelId).setSmallIcon(icon("notifications"))
                .setContentTitle(appName(c)).setContentText(row.getValue().size()+" notifications")
                .setStyle(inbox).setGroup(row.getKey()).setGroupSummary(true).setOnlyAlertOnce(true)
                .setGroupAlertBehavior(NotificationCompat.GROUP_ALERT_CHILDREN).build());
        }
    }
    public static void attach(Activity a,Dispatch callback) {
        DISPATCH.put(a,callback);
        if (attached) return;
        attached=true;
        a.getApplication().registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks() {
            public void onActivityCreated(Activity a,Bundle b) { }
            public void onActivityStarted(Activity a) { }
            public void onActivityResumed(Activity a) { active=a; MAIN.post(()->{ open(a,a.getIntent()); drain(a); }); }
            public void onActivityPaused(Activity a) { if(active==a) active=null; }
            public void onActivityStopped(Activity a) { }
            public void onActivitySaveInstanceState(Activity a,Bundle b) { }
            public void onActivityDestroyed(Activity a) { DISPATCH.remove(a); if(active==a) active=null; }
        });
    }
    public static void open(Activity a,Intent intent) {
        JSONObject event=consume(a,intent);
        if(event==null) return;
        if (event.optString("slot").equals("tap")) {
            String tag = event.optString("tag");
            removeEvents(a, tag);
            for (android.service.notification.StatusBarNotification n : manager(a).getActiveNotifications())
                if (tag.equals(n.getTag()) && (n.getNotification().flags & Notification.FLAG_ONGOING_EVENT) == 0) {
                    manager(a).cancel(tag, 0); removeEvents(a, tag);
                }
        }
        String callback=event.optString("callback");
        if(!callback.isEmpty() && DISPATCH.containsKey(a)) DISPATCH.get(a).run(callback);
        summaries(a);
    }
    private static void drain(Activity a) {
        for (Map.Entry<String,?> entry : prefs(a).getAll().entrySet()) {
            if(!entry.getKey().startsWith("dismiss:")) continue;
            try {
                JSONObject event=new JSONObject(String.valueOf(entry.getValue()));
                if(event.optString("target").equals(a.getClass().getName()) && DISPATCH.containsKey(a)) {
                    prefs(a).edit().remove(entry.getKey()).commit();
                    DISPATCH.get(a).run(event.optString("callback"));
                }
            } catch (JSONException ignored) { }
        }
    }
    public static final class DismissReceiver extends BroadcastReceiver {
        @Override public void onReceive(Context c,Intent intent) {
            JSONObject event=consume(c,intent);
            if(event==null) return;
            synchronized (ApkpyNotifications.class) { removeEvents(c,event.optString("tag")); summaries(c); }
            if(!event.optString("callback").isEmpty()) {
                prefs(c).edit().putString("dismiss:"+UUID.randomUUID(),event.toString()).commit();
                if(active!=null) drain(active);
            }
        }
    }
}
