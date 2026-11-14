"""The Java of the background audio service and of the sign-in return."""
from ..features import auth_oidc as auth_oidc_feature


_MEDIA_SERVICE_TEMPLATE = r'''package __PKG__;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.MediaMetadata;
import android.media.MediaPlayer;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.os.IBinder;

/** Serviço de reprodução em segundo plano (foreground media service) gerado pela
 *  apkpy quando a app usa audio.play_background(...). Mantém a música a tocar com
 *  o ecrã apagado e mostra controlos play/pause/stop na notificação e no lockscreen. */
public class ApkpyMediaService extends Service {
    private static final String CHANNEL_ID = "apkpy_media";
    private static final int NOTIF_ID = 1;

    private MediaPlayer mp;
    private MediaSession session;
    private String title = "";
    private String artist = "";
    // Arranque a frio (1ª faixa após abrir a app): DNS/TLS frio faz o prepareAsync
    // falhar à primeira. Em vez de derrubar o serviço, damos UMA retentativa da
    // MESMA faixa (nunca avançamos p/ a próxima — isso é que dava skip-storm).
    private String lastStartSrc = "";
    private int prepareRetries = 0;
    // Espelho estático do leitor SÓ para a Activity ler posição/estado (mesmo
    // processo). O leitor real é de INSTÂNCIA: cada instância do serviço liberta o
    // SEU mp no onDestroy — um static partilhado deixava uma instância a morrer
    // libertar o leitor de outra que acabou de arrancar (música cortada/laggy).
    private static MediaPlayer sMp;
    // Flag de sincronização: o leitor SÓ pode ser consultado (posição/duração/estado)
    // quando está PREPARED. A Activity faz polling de durationMs()/currentPositionMs()
    // a cada segundo; chamá-los enquanto o leitor está IDLE/INITIALIZED (durante um
    // (re)prepare) dispara o erro interno -38 → que o onError apanhava como falha →
    // novo startPlayback → loop play/pause infinito. Esta flag corta isso na raiz.
    private static boolean sIsPrepared = false;
    public static int currentPositionMs() { try { return (sIsPrepared && sMp != null) ? sMp.getCurrentPosition() : 0; } catch (Exception e) { return 0; } }
    public static int durationMs() { try { return (sIsPrepared && sMp != null) ? sMp.getDuration() : 0; } catch (Exception e) { return 0; } }
    public static boolean isPlaying() { try { return sIsPrepared && sMp != null && sMp.isPlaying(); } catch (Exception e) { return false; } }
    private static boolean sShuffle = false;
    public static boolean shuffleOn() { return sShuffle; }
    private static int sRepeat = 0;
    public static int repeatMode() { return sRepeat; }
    // Estado de playlist; plIndex == -1 → faixa única (play_background).
    private org.json.JSONArray plSrcs, plTitles, plArtists, plArts;
    private int plIndex = -1;
    // The last queue, for as long as the app's process lives. A queue that
    // ends calls stopSelf(), and play then reached a new service with nothing
    // to play: the button did nothing after the last track.
    private static org.json.JSONArray sPlSrcs, sPlTitles, sPlArtists, sPlArts;
    private static int sPlIndex = -1;
    // Ordem de reprodução (shuffle) + modo de repeat (0=off, 1=tudo, 2=uma).
    private int[] plOrder;
    private int plPos = 0;
    private boolean shuffleOn = false;
    private int repeatMode = 0;
    // Capa do álbum (URL + bitmap) para a notificação e o lockscreen.
    private String artUrl = "";
    private android.graphics.Bitmap artBmp;
    private static String sArt = "";
    public static String currentArt() { return sArt; }
    // Título/artista da faixa atual (mini-player + título na app).
    private static String sTitle = "";
    private static String sArtist = "";
    private static String sSrc = "";
    public static String currentTitle() { return sTitle; }
    public static String currentArtist() { return sArtist; }
    // Fonte (URL/ficheiro) da faixa atual — usada pelo like/guardar (audio.like_button).
    public static String currentSrc() { return sSrc; }
    private final android.os.Handler uiHandler = new android.os.Handler(android.os.Looper.getMainLooper());

    // Audio focus: pausar em chamadas/outra app, baixar volume em notificações.
    private AudioManager audioManager;
    private AudioFocusRequest focusRequest;
    private boolean resumeOnFocusGain = false;
    private final AudioManager.OnAudioFocusChangeListener focusListener =
            new AudioManager.OnAudioFocusChangeListener() {
        @Override public void onAudioFocusChange(int change) { handleFocusChange(change); }
    };

    @Override
    public IBinder onBind(Intent intent) { return null; }

    @Override
    public void onCreate() {
        super.onCreate();
        session = new MediaSession(this, "ApkpyMedia");
        session.setCallback(new MediaSession.Callback() {
            @Override public void onPlay() { doResume(); }
            @Override public void onPause() { doPause(); }
            @Override public void onStop() { doStop(); }
            @Override public void onSeekTo(long pos) { try { if (mp != null) mp.seekTo((int) pos); } catch (Exception e) {} }
            @Override public void onSkipToNext() { skip(1); }
            @Override public void onSkipToPrevious() { skip(-1); }
        });
        session.setActive(true);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent != null ? intent.getAction() : null;
        if (action == null) return START_NOT_STICKY;
        if ("apkpy.PLAY".equals(action)) {
            String src = intent.getStringExtra("src");
            title = intent.getStringExtra("title");
            artist = intent.getStringExtra("artist");
            if (title == null) title = "";
            if (artist == null) artist = "";
            sTitle = title; sArtist = artist;
            sSrc = src == null ? "" : src;
            // Tap-to-play: se esta faixa já faz parte da playlist carregada, alinha
            // o índice para que ⏮⏭ continuem a fila a partir daqui; senão, avulsa.
            plIndex = -1;
            if (plSrcs != null && src != null) {
                for (int _i = 0; _i < plSrcs.length(); _i++) {
                    if (src.equals(plSrcs.optString(_i, ""))) { plIndex = _i; break; }
                }
            }
            if (plIndex >= 0) buildOrderKeepCurrent();
            String _art = intent.getStringExtra("art");
            setArt(_art == null ? "" : _art);
            startForeground(NOTIF_ID, buildNotification(true));
            prepareRetries = 0;   // toque do utilizador → orçamento de retry fresco
            startPlayback(src);
        } else if ("apkpy.PAUSE".equals(action)) {
            doPause();
        } else if ("apkpy.RESUME".equals(action)) {
            doResume();
        } else if ("apkpy.STOP".equals(action)) {
            doStop();
        } else if ("apkpy.SEEK".equals(action)) {
            try { if (mp != null) mp.seekTo(intent.getIntExtra("ms", 0)); } catch (Exception e) {}
        } else if ("apkpy.PLAYLIST".equals(action)) {
            try {
                plSrcs = new org.json.JSONArray(intent.getStringExtra("sources"));
                plTitles = new org.json.JSONArray(intent.getStringExtra("titles"));
                plArtists = new org.json.JSONArray(intent.getStringExtra("artists"));
                plArts = new org.json.JSONArray(intent.getStringExtra("arts"));
            } catch (Exception e) {
                plSrcs = new org.json.JSONArray();
                plTitles = new org.json.JSONArray();
                plArtists = new org.json.JSONArray();
                plArts = new org.json.JSONArray();
            }
            plIndex = resolveStartIndex(intent.getStringExtra("start"));
            if (plSrcs.length() == 0) plIndex = -1;
            else if (plIndex < 0 || plIndex >= plSrcs.length()) plIndex = 0;
            shuffleOn = sShuffle; repeatMode = sRepeat;   // what the buttons show
            buildOrderKeepCurrent();
            sPlSrcs = plSrcs; sPlTitles = plTitles; sPlArtists = plArtists; sPlArts = plArts;
            startForeground(NOTIF_ID, buildNotification(true));
            playCurrent();
        } else if ("apkpy.NEXT".equals(action)) {
            skip(1);
        } else if ("apkpy.PREV".equals(action)) {
            skip(-1);
        } else if ("apkpy.SHUFFLE".equals(action)) {
            sShuffle = !sShuffle;
            shuffleOn = sShuffle;
            buildOrderKeepCurrent();
        } else if ("apkpy.REPEAT".equals(action)) {
            sRepeat = (sRepeat + 1) % 3;
            repeatMode = sRepeat;
        }
        return START_NOT_STICKY;
    }

    private void playCurrent() {
        if (plSrcs == null || plIndex < 0 || plIndex >= plSrcs.length()) return;
        prepareRetries = 0;   // nova faixa (fila/tap) → orçamento de retry fresco
        sPlIndex = plIndex;
        title = plTitles != null ? plTitles.optString(plIndex, "") : "";
        artist = plArtists != null ? plArtists.optString(plIndex, "") : "";
        sTitle = title; sArtist = artist;
        sSrc = plSrcs.optString(plIndex, "");
        setArt(plArts != null ? plArts.optString(plIndex, "") : "");
        startPlayback(plSrcs.optString(plIndex, ""));
    }

    // Carrega a capa do álbum a partir do URL (numa thread) p/ a notificação/lockscreen.
    private void setArt(String url) {
        if (url == null) url = "";
        sArt = url;
        if (url.equals(artUrl)) return;   // mesma capa → não recarrega
        artUrl = url;
        artBmp = null;                     // limpa a anterior (evita mostrar a capa errada)
        if (url.isEmpty()) return;
        final String _u = url;
        new Thread(() -> {
            try {
                java.net.HttpURLConnection conn = (java.net.HttpURLConnection) new java.net.URL(_u).openConnection();
                conn.setConnectTimeout(10000);
                conn.setReadTimeout(10000);
                conn.setInstanceFollowRedirects(true);
                conn.connect();
                final android.graphics.Bitmap bmp = android.graphics.BitmapFactory.decodeStream(conn.getInputStream());
                conn.disconnect();
                if (bmp != null) {
                    uiHandler.post(() -> {
                        if (!_u.equals(artUrl)) return;   // a faixa já mudou entretanto
                        artBmp = bmp;
                        boolean playing = (sIsPrepared && mp != null && mp.isPlaying());
                        updateState(playing ? PlaybackState.STATE_PLAYING : PlaybackState.STATE_PAUSED);
                        try {
                            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
                            nm.notify(NOTIF_ID, buildNotification(playing));
                        } catch (Exception e) {}
                    });
                }
            } catch (Exception e) {}
        }).start();
    }

    // Constrói a ordem de reprodução (sequencial ou baralhada), mantendo a faixa
    // atual na sua posição — toggle do shuffle não interrompe o que está a tocar.
    private void buildOrderKeepCurrent() {
        int n = (plSrcs != null) ? plSrcs.length() : 0;
        plOrder = new int[n];
        for (int k = 0; k < n; k++) plOrder[k] = k;
        if (shuffleOn && n > 1) {
            java.util.Random rnd = new java.util.Random();
            for (int k = n - 1; k > 0; k--) {
                int j = rnd.nextInt(k + 1);
                int t = plOrder[k]; plOrder[k] = plOrder[j]; plOrder[j] = t;
            }
        }
        plPos = 0;
        for (int k = 0; k < n; k++) if (plOrder[k] == plIndex) { plPos = k; break; }
    }

    // start da fila: aceita um índice ("0","1",…) OU o src de uma faixa — neste
    // caso procura-o na fila (tap-to-play num carrossel arranca a fila nessa faixa).
    private int resolveStartIndex(String raw) {
        if (raw == null || raw.isEmpty()) return 0;
        try { return Integer.parseInt(raw.trim()); } catch (Exception e) {}
        if (plSrcs != null) {
            for (int i = 0; i < plSrcs.length(); i++) {
                if (raw.equals(plSrcs.optString(i, ""))) return i;
            }
        }
        return 0;
    }

    // next/previous manuais: andam sempre na ordem, com volta (independente do repeat).
    private void skip(int delta) {
        if (plSrcs == null || plOrder == null || plOrder.length == 0) return;
        int n = plOrder.length;
        plPos = ((plPos + delta) % n + n) % n;
        plIndex = plOrder[plPos];
        playCurrent();
    }

    // Auto-advance (fim da faixa): respeita o repeat (off=pára no fim, all=dá a volta).
    private void advance() {
        if (plSrcs == null || plOrder == null || plOrder.length == 0) { doStop(); return; }
        int n = plOrder.length;
        if (plPos + 1 >= n) {
            if (repeatMode == 1) plPos = 0;   // repeat-tudo → volta ao início
            else { doStop(); return; }        // repeat-off → pára no fim da fila
        } else {
            plPos += 1;
        }
        plIndex = plOrder[plPos];
        playCurrent();
    }

    private boolean requestFocus() {
        if (audioManager == null) audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);
        if (audioManager == null) return true;
        int result;
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            focusRequest = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                    .setAudioAttributes(new AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_MEDIA)
                            .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                            .build())
                    .setOnAudioFocusChangeListener(focusListener)
                    .setWillPauseWhenDucked(false)
                    .build();
            result = audioManager.requestAudioFocus(focusRequest);
        } else {
            result = audioManager.requestAudioFocus(focusListener,
                    AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN);
        }
        return result == AudioManager.AUDIOFOCUS_REQUEST_GRANTED;
    }

    private void abandonFocus() {
        if (audioManager == null) return;
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            if (focusRequest != null) audioManager.abandonAudioFocusRequest(focusRequest);
        } else {
            audioManager.abandonAudioFocus(focusListener);
        }
    }

    private void handleFocusChange(int change) {
        switch (change) {
            case AudioManager.AUDIOFOCUS_LOSS:
                // Perda permanente (outra app de música assumiu) → pausa e fica.
                resumeOnFocusGain = false;
                doPause();
                break;
            case AudioManager.AUDIOFOCUS_LOSS_TRANSIENT:
                // Perda temporária (ex.: chamada) → pausa e retoma quando voltar.
                resumeOnFocusGain = (mp != null && mp.isPlaying());
                doPause();
                break;
            case AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK:
                // Notificação curta → baixa o volume em vez de pausar (ducking).
                try { if (mp != null) mp.setVolume(0.2f, 0.2f); } catch (Exception e) {}
                break;
            case AudioManager.AUDIOFOCUS_GAIN:
                // Recuperou o foco → restaura o volume e retoma se tinha pausado.
                try { if (mp != null) mp.setVolume(1.0f, 1.0f); } catch (Exception e) {}
                if (resumeOnFocusGain) { resumeOnFocusGain = false; doResume(); }
                break;
        }
    }

    private int bundledRaw(String source) {
        if (source == null || source.startsWith("http://") || source.startsWith("https://")) return 0;
        if (new java.io.File(source).isAbsolute()) return 0;
        String name = source.trim();
        name = name.substring(Math.max(name.lastIndexOf('/'), name.lastIndexOf(92)) + 1);
        int dot = name.lastIndexOf('.');
        if (dot > 0) name = name.substring(0, dot);
        name = name.toLowerCase(java.util.Locale.ROOT).replaceAll("[^a-z0-9_]", "_");
        if (name.isEmpty()) return 0;
        if (!Character.isLetter(name.charAt(0))) name = "img_" + name;
        return getResources().getIdentifier(name, "raw", getPackageName());
    }

    private void startPlayback(String src) {
        try {
            lastStartSrc = src == null ? "" : src;
            sIsPrepared = false;   // (re)preparando → a UI não pode ler posição/duração
            requestFocus();
            if (mp == null) {
                mp = new MediaPlayer();
            } else {
                try { mp.stop(); } catch (Exception e) {}   // parar um player já em erro
                mp.reset();                                  // pode falhar; não abortar o reset
            }
            // CRÍTICO: o reset() limpa os AudioAttributes e o volume. Reaplicar SEMPRE
            // (após new OU reset), senão um retry "carrega" mas fica em SILÊNCIO total.
            mp.setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build());
            mp.setVolume(1.0f, 1.0f);
            // A file packaged with the app (res/raw, named as the compiler
            // names it) or a web address / a file on the phone.
            int bundled = bundledRaw(src);
            if (bundled != 0) {
                mp.setDataSource(this, android.net.Uri.parse(
                        "android.resource://" + getPackageName() + "/" + bundled));
            } else {
                mp.setDataSource(src);
            }
            mp.setOnPreparedListener(new MediaPlayer.OnPreparedListener() {
                public void onPrepared(MediaPlayer m) {
                    sIsPrepared = true;   // pronto → a UI já pode ler posição/duração
                    prepareRetries = 0;   // arrancou bem → repõe o orçamento de retry
                    m.start();
                    updateState(PlaybackState.STATE_PLAYING);
                    startForeground(NOTIF_ID, buildNotification(true));
                }
            });
            mp.setOnCompletionListener(new MediaPlayer.OnCompletionListener() {
                public void onCompletion(MediaPlayer m) {
                    if (plIndex >= 0 && plSrcs != null && plSrcs.length() > 0) {
                        if (repeatMode == 2) playCurrent();   // repeat-uma → repete a faixa
                        else advance();                        // off/tudo → próxima (ou pára)
                    } else doStop();
                }
            });
            // Faixa que FALHA. CONSUMIMOS o erro (return true → o onCompletion NÃO
            // dispara). Arranque a frio (1ª faixa) falha por DNS/TLS frio → damos UMA
            // retentativa da MESMA faixa (já com a rede quente). Nunca avançamos p/ a
            // próxima — era isso que dava skip-storm/sobreposição. Esgotado o retry, pára.
            mp.setOnErrorListener(new MediaPlayer.OnErrorListener() {
                public boolean onError(MediaPlayer m, int what, int extra) {
                    sIsPrepared = false;
                    // -38 = erro de FLUXO (IllegalState, ex.: getDuration() antes de
                    // preparar), NÃO uma falha de media. Ignora-o (sem retry, sem stop):
                    // era isto que, com o retry, fazia o loop play/pause infinito.
                    if (extra == -38 || what == -38) return true;
                    final String _retrySrc = lastStartSrc;
                    if (_retrySrc != null && !_retrySrc.isEmpty() && prepareRetries < 1) {
                        prepareRetries++;
                        uiHandler.postDelayed(new Runnable() {
                            public void run() { try { startPlayback(_retrySrc); } catch (Exception e) {} }
                        }, 700);
                        return true;
                    }
                    doStop();
                    return true;
                }
            });
            sMp = mp;
            // Sinaliza "a carregar" ao SO/notificação → evita um pause automático por
            // timeout de resposta enquanto a faixa ainda bufferiza pela rede.
            updateState(PlaybackState.STATE_BUFFERING);
            mp.prepareAsync();
        } catch (Exception e) {}
    }

    private void doPause() {
        try { if (mp != null && mp.isPlaying()) mp.pause(); } catch (Exception e) {}
        updateState(PlaybackState.STATE_PAUSED);
        try {
            NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
            nm.notify(NOTIF_ID, buildNotification(false));
        } catch (Exception e) {}
        // Paused, the service is no longer in the foreground: the notification
        // stays and can be swiped away (which stops the player, see the delete
        // intent). doResume() puts it back in the foreground.
        try { stopForeground(false); } catch (Exception e) {}
    }

    private void doResume() {
        // Nada carregado (parou/falhou) → não finge que está a tocar (senão a
        // notificação dizia "playing" sem som e o botão play parecia avariado).
        if (mp == null) {
            // The queue ended: play the track on screen again, as a player does.
            if (plSrcs == null && sPlSrcs != null && sPlSrcs.length() > 0) {
                plSrcs = sPlSrcs; plTitles = sPlTitles; plArtists = sPlArtists; plArts = sPlArts;
                plIndex = sPlIndex >= 0 && sPlIndex < sPlSrcs.length() ? sPlIndex : 0;
                shuffleOn = sShuffle; repeatMode = sRepeat;
                buildOrderKeepCurrent();
            }
            if (plSrcs != null && plIndex >= 0 && plIndex < plSrcs.length()) {
                startForeground(NOTIF_ID, buildNotification(true));
                playCurrent();
            }
            return;
        }
        requestFocus();
        try { mp.start(); } catch (Exception e) {}
        updateState(PlaybackState.STATE_PLAYING);
        startForeground(NOTIF_ID, buildNotification(true));
    }

    private void doStop() {
        sIsPrepared = false;
        try { if (mp != null) { if (sMp == mp) sMp = null; mp.stop(); mp.release(); mp = null; } } catch (Exception e) {}
        sArt = ""; artUrl = ""; artBmp = null;
        abandonFocus();
        updateState(PlaybackState.STATE_STOPPED);
        stopForeground(true);
        stopSelf();
    }

    private void updateState(int state) {
        try {
            long actions = PlaybackState.ACTION_PLAY | PlaybackState.ACTION_PAUSE
                    | PlaybackState.ACTION_PLAY_PAUSE | PlaybackState.ACTION_STOP
                    | PlaybackState.ACTION_SEEK_TO
                    | PlaybackState.ACTION_SKIP_TO_NEXT | PlaybackState.ACTION_SKIP_TO_PREVIOUS;
            int pos = 0;
            try { if (sIsPrepared && mp != null) pos = mp.getCurrentPosition(); } catch (Exception e) {}
            session.setPlaybackState(new PlaybackState.Builder()
                    .setActions(actions)
                    .setState(state, pos, 1.0f)
                    .build());
            MediaMetadata.Builder _md = new MediaMetadata.Builder()
                    .putString(MediaMetadata.METADATA_KEY_TITLE, title)
                    .putString(MediaMetadata.METADATA_KEY_ARTIST, artist);
            if (artBmp != null) _md.putBitmap(MediaMetadata.METADATA_KEY_ALBUM_ART, artBmp);
            session.setMetadata(_md.build());
        } catch (Exception e) {}
    }

    private PendingIntent actionIntent(String action) {
        Intent i = new Intent(this, ApkpyMediaService.class);
        i.setAction(action);
        return PendingIntent.getService(this, action.hashCode(), i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private Notification buildNotification(boolean playing) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O
                && nm.getNotificationChannel(CHANNEL_ID) == null) {
            nm.createNotificationChannel(new NotificationChannel(
                    CHANNEL_ID, "Playback", NotificationManager.IMPORTANCE_LOW));
        }
        Notification.Builder b;
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            b = new Notification.Builder(this, CHANNEL_ID);
        } else {
            b = new Notification.Builder(this);
        }
        b.setContentTitle((title == null || title.isEmpty()) ? "Playing" : title);
        b.setContentText(artist == null ? "" : artist);
        b.setSmallIcon(android.R.drawable.ic_media_play);
        if (artBmp != null) b.setLargeIcon(artBmp);
        b.setVisibility(Notification.VISIBILITY_PUBLIC);
        b.setOngoing(playing);
        // Swiping the paused notification away stops the player and ends the
        // media session -- which is also what the media island of some phones
        // (HyperOS) is drawn from.
        b.setDeleteIntent(actionIntent("apkpy.STOP"));
        boolean hasPlaylist = plIndex >= 0;
        if (hasPlaylist) {
            b.addAction(android.R.drawable.ic_media_previous, "Prev", actionIntent("apkpy.PREV"));
        }
        if (playing) {
            b.addAction(android.R.drawable.ic_media_pause, "Pause", actionIntent("apkpy.PAUSE"));
        } else {
            b.addAction(android.R.drawable.ic_media_play, "Play", actionIntent("apkpy.RESUME"));
        }
        if (hasPlaylist) {
            b.addAction(android.R.drawable.ic_media_next, "Next", actionIntent("apkpy.NEXT"));
        }
        b.addAction(android.R.drawable.ic_menu_close_clear_cancel, "Stop", actionIntent("apkpy.STOP"));
        Notification.MediaStyle style = new Notification.MediaStyle()
                .setMediaSession(session.getSessionToken());
        if (hasPlaylist) {
            style.setShowActionsInCompactView(0, 1, 2);
        } else {
            style.setShowActionsInCompactView(0);
        }
        b.setStyle(style);
        return b.build();
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        // The app was swiped away from recents. Music that is playing keeps
        // playing, as in any music app; a paused player goes with the app.
        // It stayed: notification, session and the Xiaomi media island were
        // still there with the app closed.
        boolean playing = false;
        try { playing = mp != null && mp.isPlaying(); } catch (Exception e) {}
        if (!playing) doStop();
        super.onTaskRemoved(rootIntent);
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        try { abandonFocus(); } catch (Exception e) {}
        // Liberta SÓ o leitor desta instância; só limpa o espelho estático se ele
        // ainda aponta para este mp (senão uma instância a morrer apagaria o leitor
        // de outra que acabou de arrancar).
        try { if (mp != null) { if (sMp == mp) sMp = null; mp.release(); mp = null; } } catch (Exception e) {}
        try { if (session != null) session.release(); } catch (Exception e) {}
    }
}
'''


def _generate_media_service_java(package="com.apkpy.app"):
    """Gera ApkpyMediaService.java — foreground media service (framework Android,
    sem dependência androidx.media): MediaPlayer + MediaSession + notificação
    MediaStyle com play/pause/stop. Emitido quando a app usa audio.play_background()."""
    return _MEDIA_SERVICE_TEMPLATE.replace("__PKG__", package)


def _generate_auth_activity_java(package, auth, then_class):
    """ApkpyAuthActivity.java -- receives the OAuth redirect (deep link) and
    hands it to ApkpyAuth (features/auth_oidc.py), which checks the state,
    trades the code for tokens and keeps them; then the app goes on to the
    ``then`` screen."""
    return auth_oidc_feature.generate_auth_activity_java(package, then_class)
