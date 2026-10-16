package __PACKAGE__;

import android.Manifest;
import android.app.Activity;
import android.content.ContentUris;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.ContactsContract;
import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.lifecycle.DefaultLifecycleObserver;
import androidx.lifecycle.LifecycleOwner;
import org.json.JSONArray;
import org.json.JSONObject;

/** User-mediated writes; scoped picker; explicit permission for address-book reads. */
public final class ApkpyContacts implements DefaultLifecycleObserver {
    public interface Result { void call(String callback, boolean ok, String value); }
    private final ComponentActivity owner;
    private final Result dispatch;
    private final java.util.concurrent.ExecutorService io = java.util.concurrent.Executors.newSingleThreadExecutor();
    private final ActivityResultLauncher<Intent> picker;
    private final ActivityResultLauncher<String> permission;
    private final android.os.CancellationSignal cancellation = new android.os.CancellationSignal();
    private Bundle pending;
    private boolean resumed, closed;

    public ApkpyContacts(ComponentActivity owner, Result dispatch) {
        this.owner = owner; this.dispatch = dispatch;
        picker = owner.registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), r -> {
            if (pending == null || !"external".equals(pending.getString("phase"))) return;
            String verb = pending.getString("verb", "");
            Uri uri = r.getData() == null ? null : r.getData().getData();
            if ("pick".equals(verb)) {
                if (r.getResultCode() != Activity.RESULT_OK || uri == null) { finish(false, "cancelled"); return; }
                pending.putString("selected", uri.toString());
                pending.putString("phase", "read");
                executeRead();
            } else {
                // OEM editors do not consistently return saved data (or RESULT_OK).
                // Returning from an editor is NOT proof that a contact was saved.
                try {
                    JSONObject out = new JSONObject();
                    out.put("status", "editor_returned");
                    out.put("result_code", r.getResultCode() == Activity.RESULT_OK ? "ok" : "cancelled");
                    out.put("uri", uri == null ? "" : uri.toString());
                    finish(true, out.toString());
                } catch (Exception e) { failure(e); }
            }
        });
        permission = owner.registerForActivityResult(new ActivityResultContracts.RequestPermission(), granted -> {
            if (pending == null || !"permission".equals(pending.getString("phase"))) return;
            if (granted) { pending.putString("phase", "read"); executeRead(); }
            else finish(false, owner.shouldShowRequestPermissionRationale(Manifest.permission.READ_CONTACTS)
                    ? "permission_denied" : "permission_blocked");
        });
        owner.getLifecycle().addObserver(this);
    }

    public void call(String verb, Bundle options, String callback) {
        if (closed || owner.isFinishing()) return;
        if (pending != null) { dispatch.call(callback, false, "busy"); return; }
        pending = new Bundle(options);
        pending.putString("verb", verb); pending.putString("callback", callback);
        pending.putString("phase", "queued");
        if (resumed) begin();
    }

    private void begin() {
        if (pending == null || closed) return;
        String verb = pending.getString("verb", "");
        try {
            if ("list".equals(verb)) {
                int limit = Integer.parseInt(pending.getString("limit", "50"));
                int offset = Integer.parseInt(pending.getString("offset", "0"));
                if (limit < 1 || limit > 100 || offset < 0 || offset > 100000) throw new IllegalArgumentException();
            }
            if ("get".equals(verb) || "edit".equals(verb)) contactUri(pending.getString("id", ""));
            if ("list".equals(verb) || "get".equals(verb)) {
                if (androidx.core.content.ContextCompat.checkSelfPermission(owner, Manifest.permission.READ_CONTACTS) != PackageManager.PERMISSION_GRANTED) {
                    android.content.SharedPreferences prefs = owner.getSharedPreferences("apkpy_contacts", 0);
                    if (prefs.getBoolean("asked_read", false) && !owner.shouldShowRequestPermissionRationale(Manifest.permission.READ_CONTACTS)) {
                        finish(false, "permission_blocked"); return;
                    }
                    prefs.edit().putBoolean("asked_read", true).apply();
                    pending.putString("phase", "permission");
                    permission.launch(Manifest.permission.READ_CONTACTS);
                    return;
                }
                pending.putString("phase", "read"); executeRead(); return;
            }
            if ("settings".equals(verb)) {
                owner.startActivity(new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.parse("package:" + owner.getPackageName())));
                finish(true, "opened"); return;
            }
            Intent intent;
            if ("pick".equals(verb)) {
                String kind = pending.getString("kind", "phone");
                if (!"phone".equals(kind) && !"email".equals(kind)) throw new IllegalArgumentException();
                intent = new Intent(Intent.ACTION_PICK);
                intent.setType("phone".equals(kind) ? ContactsContract.CommonDataKinds.Phone.CONTENT_TYPE : ContactsContract.CommonDataKinds.Email.CONTENT_TYPE);
            } else if ("create".equals(verb)) {
                intent = new Intent(Intent.ACTION_INSERT, ContactsContract.RawContacts.CONTENT_URI);
                intent.setType(ContactsContract.RawContacts.CONTENT_TYPE);
                intent.putExtra(ContactsContract.Intents.Insert.NAME, pending.getString("name", ""));
                intent.putExtra(ContactsContract.Intents.Insert.PHONE, pending.getString("phone", ""));
                intent.putExtra(ContactsContract.Intents.Insert.EMAIL, pending.getString("email", ""));
                intent.putExtra("finishActivityOnSaveCompleted", true);
            } else if ("edit".equals(verb)) {
                intent = new Intent(Intent.ACTION_EDIT);
                intent.setDataAndType(contactUri(pending.getString("id", "")), ContactsContract.Contacts.CONTENT_ITEM_TYPE);
                intent.putExtra("finishActivityOnSaveCompleted", true);
            } else throw new IllegalArgumentException();
            pending.putString("phase", "external");
            picker.launch(intent);
        } catch (android.content.ActivityNotFoundException e) { finish(false, "unsupported"); }
        catch (IllegalArgumentException e) { finish(false, "invalid"); }
        catch (SecurityException e) { finish(false, "permission_denied"); }
        catch (Exception e) { failure(e); }
    }

    private static Uri contactUri(String id) {
        if (id.matches("[0-9]+")) return ContentUris.withAppendedId(ContactsContract.Contacts.CONTENT_URI, Long.parseLong(id));
        Uri u = Uri.parse(id);
        if (!"content".equals(u.getScheme()) || !ContactsContract.AUTHORITY.equals(u.getAuthority()) || u.getQuery() != null || u.getFragment() != null)
            throw new IllegalArgumentException();
        java.util.List<String> p = u.getPathSegments();
        if (p.size() < 2 || !"contacts".equals(p.get(0)) || !("lookup".equals(p.get(1)) || p.size() == 2 && p.get(1).matches("[0-9]+")))
            throw new IllegalArgumentException();
        if ("lookup".equals(p.get(1)) && p.size() < 3) throw new IllegalArgumentException();
        return u;
    }

    private void executeRead() {
        if (pending == null || closed) return;
        final Bundle job = new Bundle(pending);
        pending.putString("phase", "running");
        io.execute(() -> {
            try {
                String verb = job.getString("verb", "");
                String value;
                if ("pick".equals(verb)) value = readPicked(job).toString();
                else {
                    JSONArray rows = readContacts(job);
                    if ("get".equals(verb) && rows.length() == 0) { resultFromIo(false, "not_found"); return; }
                    value = "get".equals(verb) ? rows.getJSONObject(0).toString() : rows.toString();
                }
                resultFromIo(true, value);
            } catch (SecurityException e) { resultFromIo(false, "permission_denied"); }
            catch (java.io.FileNotFoundException e) { resultFromIo(false, "not_found"); }
            catch (IllegalArgumentException e) { resultFromIo(false, "invalid"); }
            catch (Exception e) { if (!closed) android.util.Log.w("ApkpyContacts", "Contact read failed: " + e.getClass().getSimpleName()); resultFromIo(false, "unknown"); }
        });
    }

    private Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) {
        return owner.getContentResolver().query(uri, projection, selection, args, order, cancellation);
    }

    private static String text(Cursor c, String column) {
        int i = c.getColumnIndex(column); return i < 0 || c.isNull(i) ? "" : c.getString(i);
    }
    private static JSONObject row(String id, String key, String name) throws Exception {
        JSONObject o = new JSONObject();
        o.put("id", id); o.put("name", name);
        Uri lookup = key.isEmpty() || id.isEmpty() ? null : ContactsContract.Contacts.getLookupUri(Long.parseLong(id), key);
        o.put("uri", lookup == null ? "" : lookup.toString());
        o.put("phone", ""); o.put("email", ""); o.put("phones", new JSONArray()); o.put("emails", new JSONArray());
        return o;
    }
    private static void detail(JSONObject o, String kind, String value) throws Exception {
        if (value.isEmpty()) return;
        JSONArray array = o.getJSONArray(kind + "s");
        for (int i = 0; i < array.length(); i++) if (value.equals(array.getString(i))) return;
        array.put(value);
        if (o.getString(kind).isEmpty()) o.put(kind, value);
    }

    private JSONObject readPicked(Bundle job) throws Exception {
        Uri u = Uri.parse(job.getString("selected", ""));
        if (!"content".equals(u.getScheme()) || !ContactsContract.AUTHORITY.equals(u.getAuthority())) throw new IllegalArgumentException();
        String[] projection = {ContactsContract.Data.CONTACT_ID, ContactsContract.Data.LOOKUP_KEY,
                ContactsContract.Data.DISPLAY_NAME_PRIMARY, ContactsContract.Data.DATA1};
        try (Cursor c = query(u, projection, null, null, null)) {
            if (c == null || !c.moveToFirst()) throw new java.io.FileNotFoundException();
            JSONObject out = row(text(c, ContactsContract.Data.CONTACT_ID), text(c, ContactsContract.Data.LOOKUP_KEY), text(c, ContactsContract.Data.DISPLAY_NAME_PRIMARY));
            detail(out, job.getString("kind", "phone"), text(c, ContactsContract.Data.DATA1));
            return out;
        }
    }

    private JSONArray readContacts(Bundle job) throws Exception {
        boolean single = "get".equals(job.getString("verb"));
        int limit = single ? 1 : Integer.parseInt(job.getString("limit", "50"));
        int offset = single ? 0 : Integer.parseInt(job.getString("offset", "0"));
        Uri uri = single ? contactUri(job.getString("id", "")) : ContactsContract.Contacts.CONTENT_URI;
        String search = job.getString("query", "");
        String selection = !single && !search.isEmpty() ? ContactsContract.Contacts.DISPLAY_NAME_PRIMARY + " LIKE ? ESCAPE '\\'" : null;
        String[] args = selection == null ? null : new String[]{"%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"};
        String[] projection = {ContactsContract.Contacts._ID, ContactsContract.Contacts.LOOKUP_KEY, ContactsContract.Contacts.DISPLAY_NAME_PRIMARY};
        java.util.LinkedHashMap<String, JSONObject> rows = new java.util.LinkedHashMap<>();
        try (Cursor c = query(uri, projection, selection, args, ContactsContract.Contacts.DISPLAY_NAME_PRIMARY + " COLLATE NOCASE ASC, " + ContactsContract.Contacts._ID + " ASC")) {
            if (c != null && c.moveToPosition(offset)) do {
                String id = text(c, ContactsContract.Contacts._ID);
                rows.put(id, row(id, text(c, ContactsContract.Contacts.LOOKUP_KEY), text(c, ContactsContract.Contacts.DISPLAY_NAME_PRIMARY)));
            } while (rows.size() < limit && c.moveToNext());
        }
        if (!rows.isEmpty()) {
            java.util.ArrayList<String> bindings = new java.util.ArrayList<>(rows.keySet());
            String placeholders = android.text.TextUtils.join(",", java.util.Collections.nCopies(rows.size(), "?"));
            bindings.add(ContactsContract.CommonDataKinds.Phone.CONTENT_ITEM_TYPE);
            bindings.add(ContactsContract.CommonDataKinds.Email.CONTENT_ITEM_TYPE);
            String where = ContactsContract.Data.CONTACT_ID + " IN (" + placeholders + ") AND " + ContactsContract.Data.MIMETYPE + " IN (?,?)";
            String[] cols = {ContactsContract.Data.CONTACT_ID, ContactsContract.Data.MIMETYPE, ContactsContract.Data.DATA1};
            try (Cursor c = query(ContactsContract.Data.CONTENT_URI, cols, where, bindings.toArray(new String[0]), ContactsContract.Data.IS_SUPER_PRIMARY + " DESC, " + ContactsContract.Data._ID + " ASC")) {
                if (c != null) while (c.moveToNext()) {
                    JSONObject out = rows.get(text(c, ContactsContract.Data.CONTACT_ID));
                    if (out != null) detail(out, ContactsContract.CommonDataKinds.Phone.CONTENT_ITEM_TYPE.equals(text(c, ContactsContract.Data.MIMETYPE)) ? "phone" : "email", text(c, ContactsContract.Data.DATA1));
                }
            }
        }
        JSONArray out = new JSONArray(); for (JSONObject o : rows.values()) out.put(o); return out;
    }

    private void resultFromIo(boolean ok, String value) { owner.runOnUiThread(() -> { if (!closed) finish(ok, value); }); }
    private void failure(Exception e) { android.util.Log.w("ApkpyContacts", "Contacts failed: " + e.getClass().getSimpleName()); finish(false, "unknown"); }
    private void finish(boolean ok, String value) {
        if (pending == null || closed) return;
        pending.putString("phase", "ready"); pending.putBoolean("ok", ok); pending.putString("result", value);
        if (resumed) deliver();
    }
    private void deliver() {
        Bundle result = pending; pending = null;
        if (result != null && !owner.isFinishing() && !closed)
            dispatch.call(result.getString("callback", ""), result.getBoolean("ok"), result.getString("result", ""));
    }
    @Override public void onResume(LifecycleOwner ignored) {
        resumed = true;
        if (pending == null) return;
        String phase = pending.getString("phase", "");
        if ("queued".equals(phase)) begin();
        else if ("read".equals(phase)) executeRead();
        else if ("ready".equals(phase)) deliver();
    }
    @Override public void onPause(LifecycleOwner ignored) { resumed = false; }
    @Override public void onDestroy(LifecycleOwner ignored) { closed = true; cancellation.cancel(); pending = null; io.shutdownNow(); }
    public void save(Bundle out) { if (pending != null) out.putBundle("apkpy:contacts", new Bundle(pending)); }
    public void restore(Bundle state) {
        if (state != null) pending = state.getBundle("apkpy:contacts");
        if (pending != null && "running".equals(pending.getString("phase"))) pending.putString("phase", "read");
    }
}
