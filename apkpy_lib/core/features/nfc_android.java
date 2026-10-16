package __PACKAGE__;

/** Foreground NFC reader. Tag I/O never runs on the UI thread. */
public final class ApkpyNfc {
    public interface Listener { void onResult(boolean ok, String value); }
__REASONS__
    private static final java.util.Set<ApkpyNfc> LIVE = java.util.Collections.newSetFromMap(
            new java.util.WeakHashMap<ApkpyNfc, Boolean>());
    private final android.app.Activity activity;
    private final Object ioLock = new Object();
    private volatile boolean started, resumed, destroyed;
    private volatile int generation;
    private volatile Listener onTag, onError;
    private android.nfc.NfcAdapter adapter;
    private boolean enabled;
    private final java.util.concurrent.atomic.AtomicReference<Pending> pending =
            new java.util.concurrent.atomic.AtomicReference<>();
    private final java.util.concurrent.atomic.AtomicInteger writeRevision = new java.util.concurrent.atomic.AtomicInteger();
    private static final class Pending {
        final android.nfc.NdefMessage message;
        final Listener callback;
        final int revision;
        Pending(android.nfc.NdefMessage message, Listener callback, int revision) {
            this.message = message; this.callback = callback; this.revision = revision;
        }
    }

    public ApkpyNfc(android.app.Activity activity) {
        this.activity = activity;
        synchronized (LIVE) { LIVE.add(this); }
    }

    private String blocked() {
        try {
            adapter = android.nfc.NfcAdapter.getDefaultAdapter(activity);
            if (adapter == null) return UNSUPPORTED;
            return adapter.isEnabled() ? "" : OFF;
        } catch (Exception e) { log(e); return UNKNOWN; }
    }

    private static void log(Exception e) {
        android.util.Log.w("ApkpyNfc", "NFC operation failed", e);
    }

    private void result(Listener cb, boolean ok, String value) {
        activity.runOnUiThread(() -> {
            if (!destroyed && !activity.isFinishing() && !activity.isDestroyed() && cb != null)
                cb.onResult(ok, value);
        });
    }

    private void sessionResult(int revision, Listener cb, boolean ok, String value) {
        activity.runOnUiThread(() -> {
            if (!destroyed && resumed && started && generation == revision
                    && !activity.isFinishing() && !activity.isDestroyed() && cb != null)
                cb.onResult(ok, value);
        });
    }

    public void status(Listener cb) {
        String reason = blocked();
        result(cb, reason.isEmpty(), reason.isEmpty() ? "ready" : reason);
    }

    public void start(Listener tag, Listener error) {
        cancelWrite();
        disable();
        generation++;
        onTag = tag; onError = error;
        started = true;
        String reason = blocked();
        if (!reason.isEmpty()) {
            if (UNSUPPORTED.equals(reason)) started = false;
            result(onError, false, reason);
            return;
        }
        enable();
    }

    private void enable() {
        if (!started || !resumed || destroyed || enabled) return;
        String reason = blocked();
        if (!reason.isEmpty()) { result(onError, false, reason); return; }
        final int revision = generation;
        android.os.Bundle extras = new android.os.Bundle();
        extras.putInt(android.nfc.NfcAdapter.EXTRA_READER_PRESENCE_CHECK_DELAY, 250);
        try {
            adapter.enableReaderMode(activity, tag -> discovered(tag, revision),
                    android.nfc.NfcAdapter.FLAG_READER_NFC_A
                    | android.nfc.NfcAdapter.FLAG_READER_NFC_B
                    | android.nfc.NfcAdapter.FLAG_READER_NFC_F
                    | android.nfc.NfcAdapter.FLAG_READER_NFC_V
                    | android.nfc.NfcAdapter.FLAG_READER_NO_PLATFORM_SOUNDS, extras);
            enabled = true;
        } catch (Exception e) { log(e); result(onError, false, UNKNOWN); }
    }

    private void disable() {
        if (enabled && adapter != null) {
            try { adapter.disableReaderMode(activity); }
            catch (Exception e) { log(e); }
        }
        enabled = false;
    }

    public void resume() { resumed = true; enable(); }
    public void pause() { resumed = false; generation++; cancelWrite(); disable(); }
    public void stop() { started = false; generation++; cancelWrite(); disable(); onTag = null; onError = null; }
    public void close() {
        stop(); destroyed = true;
        synchronized (LIVE) { LIVE.remove(this); }
    }

    public static void stopAll() {
        new android.os.Handler(android.os.Looper.getMainLooper()).post(() -> {
            ApkpyNfc[] controllers;
            synchronized (LIVE) { controllers = LIVE.toArray(new ApkpyNfc[0]); }
            for (ApkpyNfc controller : controllers) controller.stop();
        });
    }

    public void write(String kind, String value, Listener callback) {
        cancelWrite();
        if (!started) { result(callback, false, NOT_STARTED); return; }
        String reason = blocked();
        if (!reason.isEmpty()) { result(callback, false, reason); return; }
        try {
            android.nfc.NdefRecord record = "text".equals(kind)
                    ? android.nfc.NdefRecord.createTextRecord("en", value)
                    : android.nfc.NdefRecord.createUri(value);
            pending.set(new Pending(new android.nfc.NdefMessage(new android.nfc.NdefRecord[]{record}),
                    callback, writeRevision.get()));
        } catch (Exception e) { log(e); result(callback, false, UNKNOWN); }
    }

    public void cancelWrite() { writeRevision.incrementAndGet(); pending.set(null); }

    public static void cancelAllWrites() {
        new android.os.Handler(android.os.Looper.getMainLooper()).post(() -> {
            synchronized (LIVE) { for (ApkpyNfc controller : LIVE) controller.cancelWrite(); }
        });
    }

    private void writeResult(int revision, Pending request, boolean ok, String value,
                             Listener tagCallback, String tagJson, Listener errorCallback, String readError) {
        activity.runOnUiThread(() -> {
            if (!current(revision) || writeRevision.get() != request.revision
                    || activity.isFinishing() || activity.isDestroyed()) return;
            if (request.callback != null) request.callback.onResult(ok, value);
            // A callback may stop the reader or navigate away.
            if (!current(revision)) return;
            if (tagJson != null && tagCallback != null) tagCallback.onResult(true, tagJson);
            if (readError != null && errorCallback != null) errorCallback.onResult(false, readError);
        });
    }

    public void settings() {
        String reason = blocked();
        if (UNSUPPORTED.equals(reason)) { result(onError, false, reason); return; }
        try { activity.startActivity(new android.content.Intent(android.provider.Settings.ACTION_NFC_SETTINGS)); }
        catch (Exception e) { log(e); result(onError, false, UNKNOWN); }
    }

    private boolean current(int revision) {
        return started && resumed && !destroyed && generation == revision;
    }

    private void discovered(android.nfc.Tag tag, int revision) {
        // Android invokes ReaderCallback on Binder, not the main looper.
        synchronized (ioLock) {
            if (!current(revision)) return;
            Listener tagCallback = onTag, errorCallback = onError;
            Pending request = pending.getAndSet(null);
            if (request != null) {
                writeTag(tag, revision, request, tagCallback, errorCallback);
                return;
            }
            try {
                sessionResult(revision, tagCallback, true, read(tag, false));
            } catch (android.nfc.TagLostException e) {
                sessionResult(revision, errorCallback, false, TAG_LOST);
            } catch (Exception e) {
                log(e); sessionResult(revision, errorCallback, false, UNKNOWN);
            }
        }
    }

    private void writeTag(android.nfc.Tag tag, int revision, Pending request,
                          Listener tagCallback, Listener errorCallback) {
        if (!current(revision) || writeRevision.get() != request.revision) return;
        android.nfc.tech.Ndef ndef = android.nfc.tech.Ndef.get(tag);
        android.nfc.tech.NdefFormatable formatable = android.nfc.tech.NdefFormatable.get(tag);
        String failure = null;
        if (ndef == null && formatable == null) failure = NO_NDEF;
        else if (ndef != null && !ndef.isWritable()) failure = READ_ONLY;
        else if (ndef != null && request.message.toByteArray().length > ndef.getMaxSize()) failure = TOO_SMALL;
        if (failure != null) {
            writeResult(revision, request, false, failure, null, null, null, null);
            return;
        }
        try {
            if (ndef != null) {
                try {
                    ndef.connect();
                    if (!current(revision) || writeRevision.get() != request.revision) return;
                    ndef.writeNdefMessage(request.message);
                } finally { try { ndef.close(); } catch (java.io.IOException e) { log(e); } }
            } else {
                try {
                    formatable.connect();
                    if (!current(revision) || writeRevision.get() != request.revision) return;
                    formatable.format(request.message);
                } finally { try { formatable.close(); } catch (java.io.IOException e) { log(e); } }
            }
        } catch (android.nfc.TagLostException e) {
            writeResult(revision, request, false, TAG_LOST, null, null, null, null); return;
        } catch (Exception e) {
            log(e); writeResult(revision, request, false, UNKNOWN, null, null, null, null); return;
        }
        // The write succeeded. A read-back failure must not report a failed write.
        try {
            String json;
            if (ndef != null) json = read(tag, true); // Never reuse pre-write cached data.
            else {
                // Tag's technology list is immutable. A formatted tag exposes Ndef only
                // on the next discovery: show the acknowledged message, unknown capacity.
                json = messageJson(tag, "NDEF", "yes", "", request.message);
            }
            writeResult(revision, request, true, "ok", tagCallback, json, null, null);
        } catch (android.nfc.TagLostException e) {
            writeResult(revision, request, true, "ok", null, null, errorCallback, TAG_LOST);
        } catch (Exception e) {
            log(e); writeResult(revision, request, true, "ok", null, null, errorCallback, UNKNOWN);
        }
    }

    private String read(android.nfc.Tag tag, boolean fresh) throws Exception {
        android.nfc.tech.Ndef ndef = android.nfc.tech.Ndef.get(tag);
        String kind = "UNKNOWN", writable = "no", size = "", used = "";
        android.nfc.NdefMessage message = null;
        if (ndef != null) {
            kind = "NDEF"; writable = ndef.isWritable() ? "yes" : "no";
            size = String.valueOf(ndef.getMaxSize());
            if (!fresh) message = ndef.getCachedNdefMessage();
            if (message == null) {
                try { ndef.connect(); message = ndef.getNdefMessage(); }
                finally { try { ndef.close(); } catch (java.io.IOException e) { log(e); } }
            }
            used = String.valueOf(message == null ? 0 : message.toByteArray().length);
        } else if (android.nfc.tech.NdefFormatable.get(tag) != null) {
            kind = "FORMATABLE"; writable = "yes"; used = "0";
        }
        return messageJson(tag, kind, writable, size, message, used);
    }

    private String messageJson(android.nfc.Tag tag, String kind, String writable,
                               String size, android.nfc.NdefMessage message) {
        return messageJson(tag, kind, writable, size, message,
                String.valueOf(message == null ? 0 : message.toByteArray().length));
    }

    private String messageJson(android.nfc.Tag tag, String kind, String writable,
                               String size, android.nfc.NdefMessage message, String used) {
        StringBuilder tech = new StringBuilder();
        for (String name : tag.getTechList()) {
            if (tech.length() > 0) tech.append(',');
            tech.append(name.substring(name.lastIndexOf('.') + 1));
        }
        android.nfc.NdefRecord[] nativeRecords = message == null
                ? new android.nfc.NdefRecord[0] : message.getRecords();
        Codec.Record[] records = new Codec.Record[nativeRecords.length];
        for (int i = 0; i < records.length; i++) {
            android.nfc.NdefRecord r = nativeRecords[i];
            records[i] = new Codec.Record(r.getTnf(), r.getType(), r.getPayload());
        }
        return Codec.tagJson(tag.getId(), kind, writable, size, used, tech.toString(), records);
    }

    // BEGIN PORTABLE CODEC -- compiled verbatim by the host-JDK parity tests.
    public static final class Codec {
        private static final String[] URI_PREFIXES = { __URI_PREFIXES__ };
        public static final class Record {
            final int tnf;
            final byte[] type, payload;
            public Record(int tnf, byte[] type, byte[] payload) {
                this.tnf = tnf; this.type = type; this.payload = payload;
            }
        }
        private static String readable(byte[] data, int offset, String encoding) {
            try {
                String s = java.nio.charset.Charset.forName(encoding).newDecoder()
                        .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                        .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT)
                        .decode(java.nio.ByteBuffer.wrap(data, offset, data.length - offset)).toString();
                for (int i = 0; i < s.length(); i++) {
                    char c = s.charAt(i);
                    if ((c < 32 || c >= 127 && c <= 159) && c != '\t' && c != '\r' && c != '\n') return "";
                }
                return s;
            } catch (Exception e) { return ""; }
        }
        private static String quote(String s) {
            StringBuilder b = new StringBuilder("\"");
            for (int i = 0; i < s.length(); i++) {
                char c = s.charAt(i);
                if (c == '\\' || c == '"') b.append('\\').append(c);
                else if (c < 32) b.append(String.format(java.util.Locale.ROOT, "\\u%04x", (int)c));
                else b.append(c);
            }
            return b.append('"').toString();
        }
        public static String tagJson(byte[] id, String kind, String writable, String size,
                                     String used, String tech, Record[] records) {
            String text = "", url = "";
            boolean haveText = false, haveUrl = false, haveType = false;
            for (Record r : records) {
                byte[] p = r.payload;
                if (r.tnf == 1 && java.util.Arrays.equals(r.type, new byte[]{'T'}) && !haveText) {
                    haveText = true;
                    if (p.length > 0) {
                        int offset = 1 + (p[0] & 63);
                        if (offset <= p.length) text = readable(p, offset, (p[0] & 128) != 0 ? "UTF-16" : "UTF-8");
                    }
                } else if (r.tnf == 1 && java.util.Arrays.equals(r.type, new byte[]{'U'}) && !haveUrl) {
                    haveUrl = true;
                    if (p.length > 0 && (p[0] & 255) < URI_PREFIXES.length) {
                        String suffix = readable(p, 1, "UTF-8");
                        if (!suffix.isEmpty() || p.length == 1) url = URI_PREFIXES[p[0] & 255] + suffix;
                    }
                } else if (r.tnf == 2 || r.tnf == 4) {
                    if (!haveType) {
                        String type = readable(r.type, 0, "UTF-8");
                        if (!type.isEmpty()) kind = type;
                        haveType = true;
                    }
                    if (!haveText) {
                        String candidate = readable(p, 0, "UTF-8");
                        if (!candidate.isEmpty() || p.length == 0) { text = candidate; haveText = true; }
                    }
                }
            }
            StringBuilder hex = new StringBuilder();
            for (byte b : id) hex.append(String.format(java.util.Locale.ROOT, "%02X", b & 255));
            return "{\"id\":" + quote(hex.toString()) + ",\"type\":" + quote(kind)
                    + ",\"text\":" + quote(text) + ",\"url\":" + quote(url)
                    + ",\"records\":" + records.length + ",\"writable\":" + quote(writable)
                    + ",\"size\":" + quote(size) + ",\"used\":" + quote(used)
                    + ",\"tech\":" + quote(tech) + "}";
        }
    }
    // END PORTABLE CODEC
}
