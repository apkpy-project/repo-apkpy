"""The Java methods that reach the phone: uploads, installed apps, pickers, location, pictures."""
from ...features import file_picker as file_picker_feature
from ...features import biometrics as biometrics_feature
from ...features import bluetooth as bluetooth_feature
from ...features import native as native_feature
from ...features import ble as ble_feature
from ...features import billing as billing_feature
from ...features import scan as scan_feature
from ..state import _SCAN_FORMATS, _USES_SCAN


class Device:
    """The Java methods that reach the phone: uploads, installed apps, pickers, location, pictures."""

    def _write_uploads(self):
        """Uploads, with their progress and their retries."""
        if self.has_uploads:
            _uploads_java = r'''
    // ── uploads.* : multipart streaming, progresso e cancelamento ───────────
    // O ficheiro nunca é carregado inteiro em RAM. Um pool pequeno impede que
    // muitos uploads concorrentes criem uma thread sem limite.
    private String _uploadSafe(String value) {
        if (value == null) return "";
        return value.replace("\"", "").replace("\r", "").replace("\n", "");
    }

    private byte[] _uploadUtf8(String value) {
        try {
            return String.valueOf(value).getBytes("UTF-8");
        } catch (Exception ignored) {
            return String.valueOf(value).getBytes();
        }
    }

    private String _uploadMime(String fileName, String explicitType) {
        String type = _uploadSafe(explicitType == null ? "" : explicitType.trim());
        if (!type.isEmpty()) return type;
        String guessed = java.net.URLConnection.guessContentTypeFromName(fileName);
        return guessed == null ? "application/octet-stream" : guessed;
    }

    private void _uploadCancel(String taskId) {
        String id = taskId == null ? "" : taskId;
        java.util.concurrent.atomic.AtomicBoolean token = _apkpyUploadCancels.get(id);
        if (token != null) token.set(true);
        java.net.HttpURLConnection connection = _apkpyUploadConnections.get(id);
        if (connection != null) connection.disconnect();
    }

    private void _uploadProgress(
            final UploadProgressCallback callback,
            final int percent, final long sent, final long total) {
        if (callback == null) return;
        runOnUiThread(new Runnable() {
            public void run() {
                if (!isDestroyed()) callback.onProgress(percent, sent, total);
            }
        });
    }

    private void _uploadMultipart(
            final String taskId,
            final String url,
            final String path,
            final String field,
            final java.util.Map<String, String> fields,
            final java.util.Map<String, String> headers,
            final String explicitContentType,
            final UploadProgressCallback progressCallback,
            final UploadResultCallback resultCallback) {
        final String id = (taskId == null || taskId.trim().isEmpty())
                ? "upload-" + System.nanoTime() : taskId;
        _uploadCancel(id);
        final java.util.concurrent.atomic.AtomicBoolean cancelled =
                new java.util.concurrent.atomic.AtomicBoolean(false);
        _apkpyUploadCancels.put(id, cancelled);

        _apkpyUploadExecutor.execute(new Runnable() {
            public void run() {
                java.net.HttpURLConnection connection = null;
                java.io.InputStream source = null;
                java.io.OutputStream output = null;
                boolean success = false;
                String responseText = "";
                try {
                    if (url == null || (!url.startsWith("https://")
                            && !url.startsWith("http://"))) {
                        throw new java.io.IOException(
                                "upload URL must use http:// or https://");
                    }
                    if (path == null || path.trim().isEmpty()) {
                        throw new java.io.FileNotFoundException(
                                "empty upload path");
                    }

                    String fileName = "upload.bin";
                    long fileSize = -1L;
                    String detectedType = "";
                    if (path.startsWith("content://")) {
                        android.net.Uri uri = android.net.Uri.parse(path);
                        android.database.Cursor cursor = null;
                        try {
                            cursor = getContentResolver().query(
                                    uri,
                                    new String[]{
                                            android.provider.OpenableColumns.DISPLAY_NAME,
                                            android.provider.OpenableColumns.SIZE
                                    },
                                    null, null, null);
                            if (cursor != null && cursor.moveToFirst()) {
                                int nameIndex = cursor.getColumnIndex(
                                        android.provider.OpenableColumns.DISPLAY_NAME);
                                int sizeIndex = cursor.getColumnIndex(
                                        android.provider.OpenableColumns.SIZE);
                                if (nameIndex >= 0 && !cursor.isNull(nameIndex)) {
                                    fileName = cursor.getString(nameIndex);
                                }
                                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) {
                                    fileSize = cursor.getLong(sizeIndex);
                                }
                            }
                        } finally {
                            if (cursor != null) cursor.close();
                        }
                        detectedType = getContentResolver().getType(uri);
                        source = getContentResolver().openInputStream(uri);
                    } else {
                        java.io.File file;
                        if (path.startsWith("file://")) {
                            file = new java.io.File(
                                    android.net.Uri.parse(path).getPath());
                        } else {
                            file = new java.io.File(path);
                        }
                        if (!file.isFile()) {
                            throw new java.io.FileNotFoundException(path);
                        }
                        fileName = file.getName();
                        fileSize = file.length();
                        source = new java.io.FileInputStream(file);
                    }
                    if (source == null) {
                        throw new java.io.FileNotFoundException(path);
                    }

                    fileName = _uploadSafe(fileName);
                    String mime = explicitContentType == null
                            || explicitContentType.trim().isEmpty()
                            ? _uploadMime(fileName, detectedType)
                            : _uploadMime(fileName, explicitContentType);
                    String boundary = "----ApkPy"
                            + java.util.UUID.randomUUID().toString()
                                    .replace("-", "");
                    java.io.ByteArrayOutputStream prefixBuffer =
                            new java.io.ByteArrayOutputStream();
                    if (fields != null) {
                        for (java.util.Map.Entry<String, String> entry
                                : fields.entrySet()) {
                            prefixBuffer.write(_uploadUtf8(
                                    "--" + boundary + "\r\n"
                                    + "Content-Disposition: form-data; name=\""
                                    + _uploadSafe(entry.getKey())
                                    + "\"\r\n\r\n"
                                    + String.valueOf(entry.getValue())
                                    + "\r\n"));
                        }
                    }
                    prefixBuffer.write(_uploadUtf8(
                            "--" + boundary + "\r\n"
                            + "Content-Disposition: form-data; name=\""
                            + _uploadSafe(
                                    field == null || field.isEmpty()
                                            ? "file" : field)
                            + "\"; filename=\"" + fileName + "\"\r\n"
                            + "Content-Type: " + mime + "\r\n\r\n"));
                    byte[] prefix = prefixBuffer.toByteArray();
                    byte[] suffix = _uploadUtf8(
                            "\r\n--" + boundary + "--\r\n");

                    connection = (java.net.HttpURLConnection)
                            new java.net.URL(url).openConnection();
                    connection.setRequestMethod("POST");
                    connection.setDoOutput(true);
                    connection.setConnectTimeout(15000);
                    connection.setReadTimeout(30000);
                    connection.setInstanceFollowRedirects(true);
                    connection.setRequestProperty("User-Agent", "ApkPyApp");
                    connection.setRequestProperty(
                            "Content-Type",
                            "multipart/form-data; boundary=" + boundary);
                    if (headers != null) {
                        for (java.util.Map.Entry<String, String> entry
                                : headers.entrySet()) {
                            String name = entry.getKey();
                            if (name == null
                                    || "content-type".equalsIgnoreCase(name)
                                    || "content-length".equalsIgnoreCase(name)) {
                                continue;
                            }
                            connection.setRequestProperty(
                                    name, String.valueOf(entry.getValue()));
                        }
                    }
                    if (fileSize >= 0L) {
                        connection.setFixedLengthStreamingMode(
                                (long) prefix.length + fileSize + suffix.length);
                    } else {
                        connection.setChunkedStreamingMode(65536);
                    }
                    _apkpyUploadConnections.put(id, connection);
                    if (cancelled.get()) {
                        throw new java.io.InterruptedIOException("cancelled");
                    }

                    output = new java.io.BufferedOutputStream(
                            connection.getOutputStream(), 65536);
                    output.write(prefix);
                    long sent = 0L;
                    int lastPercent = -1;
                    _uploadProgress(progressCallback, 0, 0L, fileSize);
                    byte[] buffer = new byte[65536];
                    int count;
                    while ((count = source.read(buffer)) != -1) {
                        if (cancelled.get()
                                || Thread.currentThread().isInterrupted()) {
                            throw new java.io.InterruptedIOException(
                                    "cancelled");
                        }
                        output.write(buffer, 0, count);
                        sent += count;
                        int percent = fileSize > 0L
                                ? (int) Math.min(
                                        100L, sent * 100L / fileSize)
                                : 0;
                        if (percent != lastPercent) {
                            lastPercent = percent;
                            _uploadProgress(
                                    progressCallback, percent, sent, fileSize);
                        }
                    }
                    if (cancelled.get()) {
                        throw new java.io.InterruptedIOException("cancelled");
                    }
                    output.write(suffix);
                    output.flush();
                    if (fileSize < 0L || lastPercent < 100) {
                        _uploadProgress(
                                progressCallback, 100, sent, fileSize);
                    }

                    int responseCode = connection.getResponseCode();
                    success = responseCode >= 200 && responseCode < 300;
                    java.io.InputStream responseStream = success
                            ? connection.getInputStream()
                            : connection.getErrorStream();
                    if (responseStream != null) {
                        java.io.BufferedReader reader =
                                new java.io.BufferedReader(
                                        new java.io.InputStreamReader(
                                                responseStream, "UTF-8"));
                        StringBuilder response = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null) {
                            response.append(line);
                        }
                        reader.close();
                        responseText = response.toString();
                    }
                    if (!success) {
                        responseText = "HTTP " + responseCode
                                + (responseText.isEmpty()
                                        ? "" : ": " + responseText);
                    }
                } catch (Exception error) {
                    success = false;
                    responseText = cancelled.get()
                            || error instanceof java.io.InterruptedIOException
                            ? "cancelled"
                            : String.valueOf(error.getMessage());
                } finally {
                    try {
                        if (output != null) output.close();
                    } catch (Exception ignored) {}
                    try {
                        if (source != null) source.close();
                    } catch (Exception ignored) {}
                    if (connection != null) connection.disconnect();
                    if (_apkpyUploadConnections.get(id) == connection) {
                        _apkpyUploadConnections.remove(id);
                    }
                    if (_apkpyUploadCancels.get(id) == cancelled) {
                        _apkpyUploadCancels.remove(id);
                    }
                }
                final boolean finalSuccess = success;
                final String finalResponse = responseText;
                runOnUiThread(new Runnable() {
                    public void run() {
                        if (!isDestroyed() && resultCallback != null) {
                            resultCallback.onResult(
                                    finalSuccess, finalResponse);
                        }
                    }
                });
            }
        });
    }'''
            for _ln in _uploads_java.split('\n'):
                self.lines.append(_ln)

    def _write_apps_and_pickers(self):
        """Installed apps, the camera, the file and gallery pickers, the app's own native blocks, Bluetooth."""
        lines = self.lines
        package = self.package
        if self.has_apps:
            # Inspeção de apps instaladas (PackageManager). Tudo numa thread (a
            # enumeração pode ser lenta) + callback na UI thread. Sem dependências.
            _apps_java = r'''
    // ── apps.* : inspeção de apps instaladas (PackageManager) ──────────────
    // Lista as apps instaladas → JSON [{name,package,version,system,apk,perms}],
    // ordenado por nome. Corre numa thread (pode ser lento) + callback na UI.
    private void _appsList(final java.util.function.Consumer<String> _cb) {
        new Thread(new Runnable() { public void run() {
            org.json.JSONArray _arr = new org.json.JSONArray();
            try {
                android.content.pm.PackageManager _pm = getPackageManager();
                java.util.List<android.content.pm.PackageInfo> _pkgs =
                    _pm.getInstalledPackages(android.content.pm.PackageManager.GET_PERMISSIONS);
                java.util.List<org.json.JSONObject> _rows = new java.util.ArrayList<>();
                for (android.content.pm.PackageInfo _pi : _pkgs) {
                    try {
                        android.content.pm.ApplicationInfo _ai = _pi.applicationInfo;
                        if (_ai == null) continue;
                        org.json.JSONObject _o = new org.json.JSONObject();
                        String _label = String.valueOf(_pm.getApplicationLabel(_ai));
                        boolean _sys = (_ai.flags & android.content.pm.ApplicationInfo.FLAG_SYSTEM) != 0;
                        int _np = _pi.requestedPermissions == null ? 0 : _pi.requestedPermissions.length;
                        _o.put("name", _label);
                        _o.put("package", _pi.packageName);
                        _o.put("version", _pi.versionName == null ? "" : _pi.versionName);
                        _o.put("system", _sys);
                        _o.put("apk", _ai.sourceDir == null ? "" : _ai.sourceDir);
                        _o.put("perms", _np);
                        _o.put("subtitle", _pi.packageName + "  ·  " + _np + " perms" + (_sys ? "  ·  sistema" : ""));
                        _rows.add(_o);
                    } catch (Exception _e2) {}
                }
                java.util.Collections.sort(_rows, new java.util.Comparator<org.json.JSONObject>() {
                    public int compare(org.json.JSONObject a, org.json.JSONObject b) {
                        return a.optString("name","").compareToIgnoreCase(b.optString("name",""));
                    }
                });
                for (org.json.JSONObject _o : _rows) _arr.put(_o);
            } catch (Exception _e) {}
            final String _json = _arr.toString();
            runOnUiThread(new Runnable() { public void run() { if (_cb != null) _cb.accept(_json); } });
        } }).start();
    }

    // Permissões que uma app pede → JSON ["android.permission.X", ...] (ordenado).
    private void _appsPermissions(final String _pkg, final java.util.function.Consumer<String> _cb) {
        new Thread(new Runnable() { public void run() {
            org.json.JSONArray _arr = new org.json.JSONArray();
            try {
                android.content.pm.PackageInfo _pi = getPackageManager()
                    .getPackageInfo(_pkg, android.content.pm.PackageManager.GET_PERMISSIONS);
                if (_pi.requestedPermissions != null) {
                    java.util.List<String> _ps = new java.util.ArrayList<>(java.util.Arrays.asList(_pi.requestedPermissions));
                    java.util.Collections.sort(_ps);
                    for (String _p : _ps) _arr.put(_p);
                }
            } catch (Exception _e) {}
            final String _json = _arr.toString();
            runOnUiThread(new Runnable() { public void run() { if (_cb != null) _cb.accept(_json); } });
        } }).start();
    }

    // Copia o APK de uma app para Download/ (pasta externa da app, sem permissão
    // de storage) → callback (sucesso, caminho). "APK Extractor".
    private void _appsExtract(final String _pkg, final PhotoResultCallback _cb) {
        new Thread(new Runnable() { public void run() {
            boolean _ok = false; String _path = "";
            java.io.InputStream _in = null; java.io.FileOutputStream _out = null;
            try {
                android.content.pm.ApplicationInfo _ai = getPackageManager().getApplicationInfo(_pkg, 0);
                java.io.File _dir = getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS);
                if (_dir != null && !_dir.exists()) _dir.mkdirs();
                java.io.File _dst = new java.io.File(_dir, _pkg + ".apk");
                _in = new java.io.FileInputStream(_ai.sourceDir);
                _out = new java.io.FileOutputStream(_dst);
                byte[] _buf = new byte[8192]; int _n;
                while ((_n = _in.read(_buf)) != -1) _out.write(_buf, 0, _n);
                _out.flush();
                _ok = true; _path = _dst.getAbsolutePath();
            } catch (Exception _e) { _ok = false; _path = ""; }
            finally {
                try { if (_out != null) _out.close(); } catch (Exception _e) {}
                try { if (_in != null) _in.close(); } catch (Exception _e) {}
            }
            final boolean _fok = _ok; final String _fpath = _path;
            runOnUiThread(new Runnable() { public void run() { if (_cb != null) _cb.onResult(_fok, _fpath); } });
        } }).start();
    }

    // SHA-256 do APK de uma app (impressão digital, p/ comparar com uma base de
    // ameaças) → callback (sucesso, hash-hex). Streaming (não carrega tudo em RAM).
    private void _appsHash(final String _pkg, final PhotoResultCallback _cb) {
        new Thread(new Runnable() { public void run() {
            boolean _ok = false; String _hex = "";
            java.io.InputStream _in = null;
            try {
                android.content.pm.ApplicationInfo _ai = getPackageManager().getApplicationInfo(_pkg, 0);
                java.security.MessageDigest _md = java.security.MessageDigest.getInstance("SHA-256");
                _in = new java.io.FileInputStream(_ai.sourceDir);
                byte[] _buf = new byte[8192]; int _n;
                while ((_n = _in.read(_buf)) != -1) _md.update(_buf, 0, _n);
                byte[] _d = _md.digest();
                StringBuilder _sb = new StringBuilder();
                for (byte _b : _d) _sb.append(String.format("%02x", _b));
                _hex = _sb.toString(); _ok = true;
            } catch (Exception _e) { _ok = false; _hex = ""; }
            finally { try { if (_in != null) _in.close(); } catch (Exception _e) {} }
            final boolean _fok = _ok; final String _fhex = _hex;
            runOnUiThread(new Runnable() { public void run() { if (_cb != null) _cb.onResult(_fok, _fhex); } });
        } }).start();
    }'''
            for _ln in _apps_java.split('\n'):
                lines.append(_ln)

        if self.has_camera_capture:
            lines.append("")
            lines.append("    private void _cameraCapture(PhotoResultCallback cb) {")
            lines.append("        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {")
            lines.append("            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.CAMERA}, PERMISSION_REQ_CAMERA);")
            lines.append("            if (cb != null) cb.onResult(false, \"\");")
            lines.append("            return;")
            lines.append("        }")
            lines.append("        try {")
            lines.append("            java.io.File photoFile = java.io.File.createTempFile(\"apkpy_photo_\", \".jpg\", getExternalFilesDir(android.os.Environment.DIRECTORY_PICTURES));")
            lines.append("            _cameraPhotoUri = FileProvider.getUriForFile(this, getPackageName() + \".fileprovider\", photoFile);")
            lines.append("            _pendingCameraCallback = cb;")
            lines.append("            _cameraLauncher.launch(_cameraPhotoUri);")
            lines.append("        } catch (Exception e) {")
            lines.append("            if (cb != null) cb.onResult(false, \"\");")
            lines.append("        }")
            lines.append("    }")

        if self.has_file_pick:
            lines.extend(file_picker_feature.activity_runtime_java().splitlines())

        if self.has_biometrics:
            lines.extend(biometrics_feature.activity_runtime_java().splitlines())

        if self.has_bluetooth:
            lines.extend(
                bluetooth_feature.activity_runtime_java(package).splitlines())

        # Os blocos que a app escreveu. Vao por ultimo, e so' quando existem.
        lines.extend(native_feature.activity_runtime_java(package))

        if self.has_ble:
            lines.extend(ble_feature.activity_runtime_java(package).splitlines())

        if self.has_billing:
            lines.extend(
                billing_feature.activity_runtime_java(package).splitlines())

        if _USES_SCAN[0]:
            lines.extend(
                scan_feature.activity_runtime_java(_SCAN_FORMATS[0]).splitlines())

        if self.has_gallery_pick:
            lines.append("")
            lines.append("    private void _galleryPick(PhotoResultCallback cb) {")
            lines.append("        _pendingGalleryCallback = cb;")
            lines.append("        _galleryLauncher.launch(\"image/*\");")
            lines.append("    }")

    def _write_location_and_images(self):
        """Location, pictures set and loaded while the app runs, rich rows, carousels and grids."""
        lines = self.lines
        if self.has_location:
            lines.append("")
            lines.append("    private void _getLocation(final LocationResultCallback cb) {")
            lines.append("        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {")
            lines.append("            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, PERMISSION_REQ_ACCESS_FINE_LOCATION);")
            lines.append("            if (cb != null) cb.onResult(false, \"\", \"\", \"\");")
            lines.append("            return;")
            lines.append("        }")
            lines.append("        try {")
            lines.append("            android.location.LocationManager lm = (android.location.LocationManager) getSystemService(Context.LOCATION_SERVICE);")
            lines.append("            android.location.Location loc = null;")
            lines.append("            if (lm != null) {")
            lines.append("                loc = lm.getLastKnownLocation(android.location.LocationManager.GPS_PROVIDER);")
            lines.append("                if (loc == null) loc = lm.getLastKnownLocation(android.location.LocationManager.NETWORK_PROVIDER);")
            lines.append("            }")
            lines.append("            if (loc == null) {")
            lines.append("                if (cb != null) cb.onResult(false, \"\", \"\", \"\");")
            lines.append("                return;")
            lines.append("            }")
            lines.append("            final double dlat = loc.getLatitude();")
            lines.append("            final double dlng = loc.getLongitude();")
            lines.append("            // Reverse geocoding (coordenadas → cidade) corre fora da UI thread")
            lines.append("            new Thread(() -> {")
            lines.append("                String city = \"\";")
            lines.append("                try {")
            lines.append("                    android.location.Geocoder geo = new android.location.Geocoder(this, java.util.Locale.getDefault());")
            lines.append("                    java.util.List<android.location.Address> addrs = geo.getFromLocation(dlat, dlng, 1);")
            lines.append("                    if (addrs != null && !addrs.isEmpty()) {")
            lines.append("                        android.location.Address a = addrs.get(0);")
            lines.append("                        if (a.getLocality() != null) city = a.getLocality();")
            lines.append("                        else if (a.getSubAdminArea() != null) city = a.getSubAdminArea();")
            lines.append("                        else if (a.getAdminArea() != null) city = a.getAdminArea();")
            lines.append("                    }")
            lines.append("                } catch (Exception e) { }")
            lines.append("                final String fcity = city;")
            lines.append("                runOnUiThread(() -> { if (cb != null) cb.onResult(true, String.valueOf(dlat), String.valueOf(dlng), fcity); });")
            lines.append("            }).start();")
            lines.append("        } catch (Exception e) {")
            lines.append("            if (cb != null) cb.onResult(false, \"\", \"\", \"\");")
            lines.append("        }")
            lines.append("    }")

        if self.has_remote_image:
            lines.append("")
            lines.append("    private void _loadRemoteImage(final int viewId, final String url) {")
            lines.append("        _loadRemoteImage(viewId, url, 0, 0, true, false);")
            lines.append("    }")

        if self.has_set_src:
            # A web address, a file on the phone (a photo just taken) or a picture
            # packaged with the app, named as the compiler named it.
            lines.append("")
            lines.append("    private void _apkpySetImage(int viewId, String source) {")
            lines.append("        android.view.View found = findViewById(viewId);")
            lines.append("        if (!(found instanceof android.widget.ImageView) || source == null) return;")
            lines.append("        android.widget.ImageView view = (android.widget.ImageView) found;")
            lines.append("        String value = source.trim();")
            lines.append("        if (value.startsWith(\"http://\") || value.startsWith(\"https://\")) { _loadRemoteImage(viewId, value); return; }")
            lines.append("        java.io.File file = new java.io.File(value);")
            lines.append("        if (file.isAbsolute() && file.exists()) {")
            lines.append("            android.graphics.BitmapFactory.Options bounds = new android.graphics.BitmapFactory.Options();")
            lines.append("            bounds.inJustDecodeBounds = true;")
            lines.append("            android.graphics.BitmapFactory.decodeFile(value, bounds);")
            lines.append("            int longest = Math.max(bounds.outWidth, bounds.outHeight), sample = 1;")
            lines.append("            while (longest / (sample * 2) >= 1600) sample *= 2;")
            lines.append("            android.graphics.BitmapFactory.Options load = new android.graphics.BitmapFactory.Options();")
            lines.append("            load.inSampleSize = sample;")
            lines.append("            view.setImageBitmap(android.graphics.BitmapFactory.decodeFile(value, load));")
            lines.append("            return;")
            lines.append("        }")
            lines.append("        String name = value.replaceAll(\".*[/\\\\\\\\]\", \"\").replaceAll(\"\\\\.[^.]*$\", \"\").toLowerCase().replaceAll(\"[^a-z0-9_]\", \"_\");")
            lines.append("        if (name.isEmpty()) return;")
            lines.append("        if (!Character.isLetter(name.charAt(0))) name = \"img_\" + name;")
            lines.append("        int res = getResources().getIdentifier(name, \"drawable\", getPackageName());")
            lines.append("        if (res != 0) view.setImageResource(res);")
            lines.append("    }")

        if self.has_image_tint:
            lines.append("")
            lines.append("    private void _apkpyApplyImageTint(android.widget.ImageView image, String colorValue) {")
            lines.append("        try {")
            lines.append("            int color = android.graphics.Color.parseColor(colorValue);")
            lines.append("            float red = android.graphics.Color.red(color) / 255f;")
            lines.append("            float green = android.graphics.Color.green(color) / 255f;")
            lines.append("            float blue = android.graphics.Color.blue(color) / 255f;")
            lines.append("            android.graphics.ColorMatrix matrix = new android.graphics.ColorMatrix(new float[]{")
            lines.append("                    0.299f * red, 0.587f * red, 0.114f * red, 0f, 0f,")
            lines.append("                    0.299f * green, 0.587f * green, 0.114f * green, 0f, 0f,")
            lines.append("                    0.299f * blue, 0.587f * blue, 0.114f * blue, 0f, 0f,")
            lines.append("                    0f, 0f, 0f, 1f, 0f")
            lines.append("            });")
            lines.append("            image.setColorFilter(new android.graphics.ColorMatrixColorFilter(matrix));")
            lines.append("        } catch (IllegalArgumentException ignored) { }")
            lines.append("    }")

        if self.has_remote_image:
            lines.append("")
            lines.append("    private void _loadRemoteImage(final int viewId, final String url, final int placeholderRes, final int fallbackRes, final boolean useCache, final boolean fadeIn) {")
            lines.append("        final android.widget.ImageView initial = findViewById(viewId);")
            lines.append("        if (initial == null || url == null || url.isEmpty()) return;")
            lines.append("        _apkpyImageRequests.put(viewId, url);")
            lines.append("        if (placeholderRes != 0) initial.setImageResource(placeholderRes);")
            if self.has_image_cache:
                lines.append("        android.graphics.Bitmap cached = useCache ? _apkpyImageCache.get(url) : null;")
                lines.append("        if (cached != null) {")
                lines.append("            _apkpyApplyRemoteBitmap(initial, viewId, url, cached, fadeIn);")
                lines.append("            return;")
                lines.append("        }")
            lines.append("        _apkpyImageExecutor.execute(() -> {")
            lines.append("            java.net.HttpURLConnection conn = null;")
            lines.append("            try {")
            lines.append("                conn = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();")
            lines.append("                conn.setConnectTimeout(10000);")
            lines.append("                conn.setReadTimeout(10000);")
            lines.append("                conn.setInstanceFollowRedirects(true);")
            lines.append("                conn.connect();")
            lines.append("                final android.graphics.Bitmap bitmap = android.graphics.BitmapFactory.decodeStream(conn.getInputStream());")
            lines.append("                if (bitmap == null) throw new java.io.IOException(\"Invalid image\");")
            if self.has_image_cache:
                lines.append("                if (useCache) _apkpyImageCache.put(url, bitmap);")
            lines.append("                runOnUiThread(() -> {")
            lines.append("                    android.widget.ImageView current = findViewById(viewId);")
            lines.append("                    if (current != null) _apkpyApplyRemoteBitmap(current, viewId, url, bitmap, fadeIn);")
            lines.append("                });")
            lines.append("            } catch (Exception ignored) {")
            lines.append("                if (fallbackRes != 0) runOnUiThread(() -> {")
            lines.append("                    android.widget.ImageView current = findViewById(viewId);")
            lines.append("                    if (current != null && url.equals(_apkpyImageRequests.get(viewId))) current.setImageResource(fallbackRes);")
            lines.append("                });")
            lines.append("            } finally {")
            lines.append("                if (conn != null) conn.disconnect();")
            lines.append("            }")
            lines.append("        });")
            lines.append("    }")
            lines.append("")
            lines.append("    private void _apkpyApplyRemoteBitmap(android.widget.ImageView image, int viewId, String url, android.graphics.Bitmap bitmap, boolean fadeIn) {")
            lines.append("        if (!url.equals(_apkpyImageRequests.get(viewId))) return;")
            lines.append("        float targetAlpha = image.getAlpha();")
            lines.append("        image.animate().cancel();")
            lines.append("        image.setImageBitmap(bitmap);")
            lines.append("        if (fadeIn) {")
            lines.append("            image.setAlpha(0f);")
            lines.append("            image.animate().alpha(targetAlpha).setDuration(220L).start();")
            lines.append("        }")
            lines.append("    }")

        if any(c['comp_type'] == 'list_view' and c.get('rich') for c in self.all_comps_flat) and not self.scroll:
            lines.append("")
            lines.append("    // Miniatura de uma linha rica de list_view — carga async + reciclagem-safe")
            lines.append("    // (só aplica o bitmap se a ImageView ainda for da mesma linha, via setTag).")
            lines.append("    private void _loadListThumb(final android.widget.ImageView iv, final String url) {")
            lines.append("        new Thread(() -> {")
            lines.append("            try {")
            lines.append("                android.graphics.Bitmap bmp;")
            lines.append("                if (url.startsWith(\"http://\") || url.startsWith(\"https://\")) {")
            lines.append("                    java.net.HttpURLConnection conn = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();")
            lines.append("                    conn.setConnectTimeout(10000);")
            lines.append("                    conn.setReadTimeout(10000);")
            lines.append("                    conn.setInstanceFollowRedirects(true);")
            lines.append("                    conn.connect();")
            lines.append("                    bmp = android.graphics.BitmapFactory.decodeStream(conn.getInputStream());")
            lines.append("                    conn.disconnect();")
            lines.append("                } else if (new java.io.File(url).isAbsolute()) {")
            lines.append("                    bmp = android.graphics.BitmapFactory.decodeFile(url);")
            lines.append("                } else {")
            lines.append("                    int _res = _apkpyBundled(url, \"drawable\");")
            lines.append("                    bmp = _res != 0 ? android.graphics.BitmapFactory.decodeResource(getResources(), _res) : null;")
            lines.append("                }")
            lines.append("                final android.graphics.Bitmap fbmp = bmp;")
            lines.append("                if (fbmp != null) {")
            lines.append("                    runOnUiThread(() -> { if (url.equals(iv.getTag())) iv.setImageBitmap(fbmp); });")
            lines.append("                }")
            lines.append("            } catch (Exception e) { }")
            lines.append("        }).start();")
            lines.append("    }")

        if self.has_virtual_collection:
            lines.append("")
            lines.append("    // Imagem de ViewHolder: o tag impede que uma resposta antiga")
            lines.append("    // seja aplicada depois de a célula ser reciclada para outro item.")
            lines.append("    private void _loadVirtualThumb(final android.widget.ImageView iv, final String url) {")
            lines.append("        if (url == null || url.isEmpty()) return;")
            lines.append("        new Thread(() -> {")
            lines.append("            java.net.HttpURLConnection connection = null;")
            lines.append("            try {")
            lines.append("                android.graphics.Bitmap bitmap;")
            lines.append("                if (url.startsWith(\"http://\") || url.startsWith(\"https://\")) {")
            lines.append("                    connection = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();")
            lines.append("                    connection.setConnectTimeout(10000); connection.setReadTimeout(10000);")
            lines.append("                    connection.setInstanceFollowRedirects(true); connection.connect();")
            lines.append("                    bitmap = android.graphics.BitmapFactory.decodeStream(connection.getInputStream());")
            lines.append("                } else {")
            lines.append("                    bitmap = android.graphics.BitmapFactory.decodeFile(url);")
            lines.append("                }")
            lines.append("                final android.graphics.Bitmap ready = bitmap;")
            lines.append("                if (ready != null) runOnUiThread(() -> {")
            lines.append("                    if (url.equals(iv.getTag())) iv.setImageBitmap(ready);")
            lines.append("                });")
            lines.append("            } catch (Exception ignored) {")
            lines.append("            } finally { if (connection != null) connection.disconnect(); }")
            lines.append("        }).start();")
            lines.append("    }")

        if self.has_carousel or self.has_grid:
            lines.append("")
            lines.append("    // Capa de um cartão de carousel/grid — carga async para a ImageView dada.")
            lines.append("    private void _loadCarThumb(final android.widget.ImageView iv, final String url) {")
            lines.append("        if (url == null || url.isEmpty()) return;")
            lines.append("        new Thread(() -> {")
            lines.append("            try {")
            lines.append("                android.graphics.Bitmap bmp;")
            lines.append("                if (url.startsWith(\"http://\") || url.startsWith(\"https://\")) {")
            lines.append("                    java.net.HttpURLConnection conn = (java.net.HttpURLConnection) new java.net.URL(url).openConnection();")
            lines.append("                    conn.setConnectTimeout(10000);")
            lines.append("                    conn.setReadTimeout(10000);")
            lines.append("                    conn.setInstanceFollowRedirects(true);")
            lines.append("                    conn.connect();")
            lines.append("                    bmp = android.graphics.BitmapFactory.decodeStream(conn.getInputStream());")
            lines.append("                    conn.disconnect();")
            lines.append("                } else if (new java.io.File(url).isAbsolute()) {")
            lines.append("                    bmp = android.graphics.BitmapFactory.decodeFile(url);")
            lines.append("                } else {")
            lines.append("                    int _res = _apkpyBundled(url, \"drawable\");")
            lines.append("                    bmp = _res != 0 ? android.graphics.BitmapFactory.decodeResource(getResources(), _res) : null;")
            lines.append("                }")
            lines.append("                final android.graphics.Bitmap fbmp = bmp;")
            lines.append("                if (fbmp != null) runOnUiThread(() -> iv.setImageBitmap(fbmp));")
            lines.append("            } catch (Exception e) { }")
            lines.append("        }).start();")
            lines.append("    }")
