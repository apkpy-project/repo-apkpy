package apkpygame.android;

import android.content.res.AssetFileDescriptor;
import android.content.res.AssetManager;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.media.SoundPool;

import apkpygame.core.Platform;

/**
 * SoundPool for sounds, MediaPlayer for music, both straight from the APK's
 * assets (stored uncompressed by apkpygame build, so openFd works).
 */
final class AndroidAudio implements Platform.AudioDevice {
    private static final AudioAttributes GAME = new AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_GAME)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build();

    private final AssetManager assets;
    private SoundPool pool;
    private MediaPlayer music;
    private String musicPath;
    private boolean paused;

    AndroidAudio(AssetManager assets) {
        this.assets = assets;
    }

    private SoundPool pool() {
        if (pool == null) pool = new SoundPool.Builder().setMaxStreams(8).setAudioAttributes(GAME).build();
        return pool;
    }

    @Override public Object loadSound(String path) {
        try {
            AssetFileDescriptor fd = assets.openFd(AndroidPlatform.BUNDLE + path);
            int id = pool().load(fd, 1);
            fd.close();
            return id;
        } catch (Exception e) {
            AndroidPlatform.LOGGER.error("sound " + path, e);
            return 0;
        }
    }

    @Override public void play(Object sound, double volume) {
        int id = sound instanceof Integer ? (Integer) sound : 0;
        if (id == 0 || pool == null) return;
        float v = (float) Math.max(0, Math.min(1, volume));
        pool.play(id, v, v, 1, 0, 1f);
    }

    @Override public void playMusic(String path, double volume, boolean loop) {
        if (path.equals(musicPath) && music != null) {
            if (!music.isPlaying() && !paused) music.start();
            return;
        }
        stopMusic();
        try {
            AssetFileDescriptor fd = assets.openFd(AndroidPlatform.BUNDLE + path);
            MediaPlayer p = new MediaPlayer();
            p.setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_GAME)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build());
            p.setDataSource(fd.getFileDescriptor(), fd.getStartOffset(), fd.getLength());
            fd.close();
            p.setLooping(loop);
            float v = (float) Math.max(0, Math.min(1, volume));
            p.setVolume(v, v);
            p.prepare();
            if (!paused) p.start();
            music = p;
            musicPath = path;
        } catch (Exception e) {
            AndroidPlatform.LOGGER.error("music " + path, e);
        }
    }

    @Override public void stopMusic() {
        if (music != null) {
            music.release();
            music = null;
        }
        musicPath = null;
    }

    @Override public void pause() {
        paused = true;
        if (music != null && music.isPlaying()) music.pause();
        if (pool != null) pool.autoPause();
    }

    @Override public void resume() {
        paused = false;
        if (music != null) music.start();
        if (pool != null) pool.autoResume();
    }

    @Override public void release() {
        stopMusic();
        if (pool != null) {
            pool.release();
            pool = null;
        }
    }
}
