"""onDestroy, the answer to a permission, onPause and onResume."""
from ...features import feeds as feeds_feature
from ...features import pending_views as pending_views_feature
from ..state import _PENDING_TARGETS
from ..manifest import _permission_symbol


class Lifecycle:
    """onDestroy, the answer to a permission, onPause and onResume."""

    def _write_destroy_and_permissions(self):
        """onDestroy and onRequestPermissionsResult."""
        lines = self.lines
        if (self._np_active or self._ac_active or self._mp_active or self._like_active or self.has_uploads or self.has_websocket or self.has_push or self.has_video or self.has_continuous_location or self.has_routes or self.has_background_location or self.lifecycle_info.get('on_destroy') or self.screen_data_observers or self.has_bluetooth or self.has_ble or self.has_nfc):
            lines.append("")
            lines.append("    @Override")
            lines.append("    protected void onDestroy() {")
            if self.has_nfc:
                lines.append("        _nfc.close();")
            if self._np_active:
                lines.append("        if (_npTick != null) _npHandler.removeCallbacks(_npTick);")
                lines.append("        if (_npAnim != null) _npAnim.cancel();")
            if self._ac_active:
                lines.append("        if (_acTick != null) _acHandler.removeCallbacks(_acTick);")
            if self._mp_active:
                lines.append("        if (_mpTick != null) _mpHandler.removeCallbacks(_mpTick);")
            if self._like_active:
                lines.append("        if (_likeTick != null) _likeHandler.removeCallbacks(_likeTick);")
            if self.has_uploads:
                lines.append("        for (java.util.concurrent.atomic.AtomicBoolean _token : _apkpyUploadCancels.values()) _token.set(true);")
                lines.append("        for (java.net.HttpURLConnection _connection : _apkpyUploadConnections.values()) _connection.disconnect();")
                lines.append("        _apkpyUploadConnections.clear();")
                lines.append("        _apkpyUploadCancels.clear();")
                lines.append("        _apkpyUploadExecutor.shutdownNow();")
            if self.has_websocket:
                lines.append("        _websocketCloseAll();")
                lines.append("        _apkpyWebSocketHandler.removeCallbacksAndMessages(null);")
            if self.has_push:
                lines.append("        _pushDispose();")
            if self.has_continuous_location:
                lines.append("        _locationStopAll();")
            if self.has_routes:
                lines.append("        _routeCancelAll();")
            if self.has_background_location:
                lines.append("        _locationBackgroundDispose();")
            if self.has_video:
                for _video in self._video_comps:
                    _vv = _video['_java_var']
                    lines.append(
                        f"        if ({_vv}ProgressTick != null) "
                        f"{_vv}Handler.removeCallbacks({_vv}ProgressTick);"
                    )
                    lines.append(
                        f"        if ({_vv} != null) {_vv}.setPlayer(null);"
                    )
                    lines.append(
                        f"        if ({_vv}Player != null) {{ "
                        f"{_vv}Player.release(); {_vv}Player = null; }}"
                    )
            for _observer in self.screen_data_observers:
                lines.append(
                    f"        if ({_observer['var']} != null) {_observer['var']}.close();"
                )
            # A radio link outlives the screen otherwise: rotate the phone and the
            # socket stays open with nothing reading it.
            if self.has_bluetooth:
                lines.append("        _btReleaseListener();")
            if self.has_ble:
                lines.append("        _bleReleaseListener();")
            _destroy_callback = self.lifecycle_info.get('on_destroy')
            if _destroy_callback and _destroy_callback in self.functions_map:
                lines.append(f"        pythonCallback_{_destroy_callback}();")
            lines.append("        super.onDestroy();")
            lines.append("    }")

        if self._np_active:
            lines.append("")
            lines.append("    private String _npFmt(int ms) {")
            lines.append("        if (ms < 0) ms = 0;")
            lines.append("        int _s = ms / 1000;")
            lines.append("        return (_s / 60) + \":\" + String.format(java.util.Locale.US, \"%02d\", _s % 60);")
            lines.append("    }")

        if self.declared_permissions:
            lines.append("")
            lines.append("    @Override")
            lines.append("    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {")
            lines.append("        super.onRequestPermissionsResult(requestCode, permissions, grantResults);")
            lines.append("        if (grantResults.length == 0) return;")
            lines.append("        boolean granted = (grantResults[0] == PackageManager.PERMISSION_GRANTED);")
            lines.append("        switch (requestCode) {")
            for perm in self.declared_permissions:
                if perm in self.permission_callbacks:
                    cb = self.permission_callbacks[perm]
                    lines.append(f"            case PERMISSION_REQ_{_permission_symbol(perm)}:")
                    lines.append(f"                pythonCallback_{cb}(granted);")
                    lines.append(f"                break;")
            lines.append("        }")
            lines.append("    }")

    def _write_pause_and_resume(self):
        """What other screens left for this one, onPause and onResume."""
        screen_id = self.screen_id
        lines = self.lines
        lifecycle_info = self.lifecycle_info
        functions_map = self.functions_map
        screen_data_observers = self.screen_data_observers
        reactive_states = self.reactive_states
        # Values other screens wrote to this one's components while it was not in
        # front (pending_views). Taken when it comes to the front, and at once
        # while it is.
        _pending_here = _PENDING_TARGETS[0].get(screen_id, {})
        if _pending_here:
            lines.append("")
            lines.append("    private final Runnable _apkpyApplyPendingRun = this::_apkpyApplyPending;")
            lines.append("")
            lines.append("    private void _apkpyApplyPending() {")
            for _pname in sorted(_pending_here):
                _pcomp = self._get_comp_from_py_var(_pname)
                _pjv = _pcomp.get('_java_var') if _pcomp else None
                if not _pjv:
                    continue
                _kinds = _pending_here[_pname]
                if pending_views_feature.VALUE in _kinds:
                    lines.append("        {")
                    lines.append("            String _p = " + pending_views_feature.take_expr(
                        screen_id, _pname, pending_views_feature.VALUE) + ";")
                    lines.append("            if (_p != null) {")
                    self._emit_set_value_by_id("                ", _pcomp, _pjv, "_p")
                    lines.append("            }")
                    lines.append("        }")
                if pending_views_feature.ITEMS in _kinds and _pcomp.get('comp_type') == 'chart':
                    lines.append("        {")
                    lines.append("            String _p = " + pending_views_feature.take_expr(
                        screen_id, _pname, pending_views_feature.ITEMS) + ";")
                    lines.append(f"            if (_p != null) ((ApkpyChart) findViewById(R.id.{_pjv})).setItems(_p);")
                    lines.append("        }")
                elif pending_views_feature.ITEMS in _kinds:
                    _pvirtual = _pcomp.get('comp_type') == 'virtual_collection'
                    lines.append("        {")
                    lines.append("            String _p = " + pending_views_feature.take_expr(
                        screen_id, _pname, pending_views_feature.ITEMS) + ";")
                    lines.append("            if (_p != null) {")
                    lines.append(f"                {_pjv}_items.clear();")
                    if _pvirtual and _pname in self._mutated_feed_pyvars:
                        lines.append(f"                {_pjv}Optimistic.clear();")
                        lines.append(f"                {_pjv}OptimisticKeys.clear();")
                    lines.append("                try {")
                    lines.append("                    org.json.JSONArray _pa = new org.json.JSONArray(_p);")
                    lines.append(f"                    for (int _pi = 0; _pi < _pa.length(); _pi++) {_pjv}_items.add(_pa.getString(_pi));")
                    lines.append("                } catch (Exception _pe) { }")
                    if _pvirtual:
                        lines.append(f"                {_pjv}Adapter.notifyDataSetChanged();")
                        if feeds_feature.is_paginated(_pcomp):
                            lines.append("                String _hm = " + pending_views_feature.take_expr(
                                screen_id, _pname, pending_views_feature.HAS_MORE) + ";")
                            lines.append(f"                _apkpyFinish{_pjv.title()}Load(_hm == null || Boolean.parseBoolean(_hm));")
                            lines.append(f"                {_pjv}.scrollToPosition(0);")
                            if _pcomp.get('on_end_reached'):
                                lines.append(f"                {_pjv}.post(() -> _apkpyMaybeLoad{_pjv.title()}Page());")
                    elif self.scroll:
                        lines.append(f"                update{_pjv[0].upper()}{_pjv[1:]}List();")
                    else:
                        lines.append(f"                {_pjv}Adapter.notifyDataSetChanged();")
                    lines.append("            }")
                    lines.append("        }")
                if pending_views_feature.VISIBLE in _kinds:
                    lines.append("        {")
                    lines.append("            String _p = " + pending_views_feature.take_expr(
                        screen_id, _pname, pending_views_feature.VISIBLE) + ";")
                    lines.append(f"            if (_p != null) findViewById(R.id.{_pjv}).setVisibility("
                                 "\"1\".equals(_p) ? android.view.View.VISIBLE : android.view.View.GONE);")
                    lines.append("        }")
            lines.append("    }")

        _pause_callback = lifecycle_info.get('on_pause')
        if _pending_here or self.has_nfc or self.has_video or self.has_continuous_location or self.has_sensors or self.has_wallpaper or (_pause_callback and _pause_callback in functions_map) or screen_data_observers:
            lines.append("")
            lines.append("    @Override")
            lines.append("    protected void onPause() {")
            if _pending_here:
                lines.append(f'        {pending_views_feature.CLASS}.behind("{screen_id}", _apkpyApplyPendingRun);')
            if self.has_nfc:
                lines.append("        _nfc.pause();")
            if self.has_video:
                for _video in self._video_comps:
                    _vv = _video['_java_var']
                    lines.append(
                        f"        if ({_vv}ProgressTick != null) "
                        f"{_vv}Handler.removeCallbacks({_vv}ProgressTick);"
                    )
                    lines.append(
                        f"        if ({_vv}Player != null) {{ "
                        f"{_vv}ResumeAfterPause = {_vv}Player.getPlayWhenReady(); "
                        f"{_vv}Player.pause(); }}"
                    )
            if self.has_continuous_location:
                lines.append("        _locationPauseAll();")
            if self.has_sensors:
                # Not tidiness: a listener left registered keeps the sensor
                # hub awake behind a screen nobody is looking at.
                lines.append("        _sensorsPauseAll();")
            for _wall_cb in self._wallpaper_callbacks:
                lines.append('        ApkpyWallpaper.paused(this, "%s");' % _wall_cb)
            for _observer in screen_data_observers:
                lines.append(
                    f"        if ({_observer['var']} != null) {_observer['var']}.pause();"
                )
            if _pause_callback and _pause_callback in functions_map:
                lines.append(f"        pythonCallback_{_pause_callback}();")
            lines.append("        super.onPause();")
            lines.append("    }")

        # onResume: restaura o tab correto + recarrega a lista de favoritos (que pode
        # ter mudado noutro ecrã — cada ecrã é uma Activity, e o bottom_nav reusa a
        # instância via REORDER_TO_FRONT, por isso o refresh tem de ser no onResume).
        if _pending_here or self.bottom_nav_info or self._liked_list_active or self._playlists_list_active or \
                self._playlist_editor_active or reactive_states or self.has_video or self.has_continuous_location or self.has_sensors or self.has_wallpaper or \
                lifecycle_info.get('on_resume') or screen_data_observers or \
                self.has_appearance_switch or self.has_nfc:
            lines.append("")
            lines.append("    @Override")
            lines.append("    protected void onResume() {")
            lines.append("        super.onResume();")
            if self.has_nfc:
                lines.append("        _nfc.resume();")
            if self.has_appearance_switch:
                # AppCompat recria as Activities que estao a correr, mas esta
                # podia estar parada no fundo da pilha quando o modo mudou:
                # voltava com as vistas da aparencia antiga, e via-se metade
                # da app trocada. Comparar com o que ficou guardado apanha-o.
                lines.append(
                    '        String _apkpyMode = _apkpyStorageGet('
                    f'"__apkpy_appearance", "{self._declared_appearance}");'
                )
                lines.append(
                    '        if (!_apkpyMode.equals(_apkpyAppearanceShown)) {'
                )
                lines.append('            _apkpyApplyAppearance(_apkpyMode);')
                lines.append('            recreate();')
                lines.append('            return;')
                lines.append('        }')
            if self.has_video:
                for _video in self._video_comps:
                    _vv = _video['_java_var']
                    lines.append(
                        f"        if ({_vv}ProgressTick != null) "
                        f"{_vv}Handler.post({_vv}ProgressTick);"
                    )
                    lines.append(
                        f"        if ({_vv}Player != null && "
                        f"{_vv}ResumeAfterPause) {{ {_vv}Player.play(); "
                        f"{_vv}ResumeAfterPause = false; }}"
                    )
            if self.has_continuous_location:
                lines.append("        _locationResumeAll();")
            if self.has_sensors:
                lines.append("        _sensorsResumeAll();")
            for _wall_cb in self._wallpaper_callbacks:
                # Applying a wallpaper changes the palette, which recreates
                # this Activity. Re-offering the callback is how the new one
                # collects an answer the old one never lived to hear.
                lines.append(
                    '        ApkpyWallpaper.resumed("%s", (_apkpyWallOk, _apkpyWallReason)'
                    ' -> pythonCallback_%s(_apkpyWallOk, _apkpyWallReason));'
                    % (_wall_cb, _wall_cb))
            for _observer in screen_data_observers:
                lines.append(
                    f"        if ({_observer['var']} != null) {_observer['var']}.resume();"
                )
            if self.bottom_nav_info:
                lines.append("        BottomNavigationView _bnav = findViewById(R.id.bottom_nav);")
                lines.append("        _navReady = false;")
                lines.append(f"        _bnav.setSelectedItemId(R.id.nav_{screen_id});")
                lines.append("        _navReady = true;")
            if self._liked_list_active:
                _ll_jv = self._get_jv_from_py_var(self.audio_liked_list)
                _ll_refresh = (f"update{_ll_jv[0].upper()}{_ll_jv[1:]}List();" if self.scroll
                               else f"{_ll_jv}Adapter.notifyDataSetChanged();")
                lines.append("        // Músicas guardadas (audio.liked_list): recarrega do storage.")
                lines.append(f"        if ({_ll_jv}_items != null) {{")
                lines.append(f"            {_ll_jv}_items.clear();")
                lines.append("            org.json.JSONArray _favArr = _apkpyLikedArray();")
                lines.append("            for (int _fi = 0; _fi < _favArr.length(); _fi++) {")
                lines.append("                org.json.JSONObject _fo = _favArr.optJSONObject(_fi);")
                lines.append(f"                if (_fo != null) {_ll_jv}_items.add(_fo.toString());")
                lines.append("            }")
                lines.append(f"            {_ll_refresh}")
                lines.append("        }")
            if self._playlists_list_active:
                lines.append("        // Playlists do utilizador (audio.playlists_list): recarrega do storage.")
                lines.append("        _apkpyRefreshPlaylistsList();")
            if self._playlist_editor_active:
                lines.append("        // Editor de playlist (audio.playlist_editor): recarrega as faixas em edição.")
                lines.append("        _apkpyRefreshPlaylistEditor();")
            if reactive_states:
                lines.append("        // Re-read process state after returning from another screen.")
                for _state_var in reactive_states:
                    lines.append(f"        {self._state_method_name(_state_var)}();")
            if _pending_here:
                # Before the screen's own on_resume: what it computes now is
                # newer than anything written while it was away.
                lines.append(f'        {pending_views_feature.CLASS}.inFront("{screen_id}", _apkpyApplyPendingRun);')
                lines.append("        _apkpyApplyPending();")
            _resume_callback = lifecycle_info.get('on_resume')
            if _resume_callback and _resume_callback in functions_map:
                lines.append(f"        pythonCallback_{_resume_callback}();")
                for _state_var in reactive_states:
                    lines.append(f"        {self._state_method_name(_state_var)}();")
            lines.append("    }")
