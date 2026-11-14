package apkpygame.desktop;

import apkpygame.core.Platform;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.nio.file.Files;
import java.util.HashSet;
import java.util.Set;
import javax.sound.sampled.AudioInputStream;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.Clip;
import javax.sound.sampled.FloatControl;
import javax.sound.sampled.LineEvent;
import javax.sound.sampled.LineListener;

/**
 * javax.sound, which reads WAV only: apkpygame build writes a WAV copy of
 * every sound and music track to audio-desktop/PATH.wav. A missing copy is a
 * warning, never an error: the game runs without that sound.
 */
final class JavaSoundAudio implements Platform.AudioDevice {
    private final File bundle;
    private final Platform.Logger logger;
    private final Set<String> warned = new HashSet<String>();
    private Clip music;
    private String musicPath;

    JavaSoundAudio(File bundle, Platform.Logger logger) {
        this.bundle = bundle;
        this.logger = logger;
    }

    private byte[] wav(String path) {
        File copy = new File(bundle, "audio-desktop/" + path + ".wav");
        File file = copy.isFile() ? copy : new File(bundle, path);
        try {
            if (!file.getName().toLowerCase().endsWith(".wav")) throw new java.io.IOException("not WAV");
            return Files.readAllBytes(file.toPath());
        } catch (java.io.IOException e) {
            if (warned.add(path)) {
                logger.warn("no desktop copy of " + path + " (run apkpygame build); playing without it");
            }
            return null;
        }
    }

    @Override public Object loadSound(String path) {
        return wav(path);
    }

    @Override public void play(Object sound, double volume) {
        if (!(sound instanceof byte[])) return;
        try {
            final Clip clip = clip((byte[]) sound, volume);
            clip.addLineListener(new LineListener() {
                @Override public void update(LineEvent e) {
                    if (e.getType() == LineEvent.Type.STOP) clip.close();
                }
            });
            clip.start();
        } catch (Exception e) {
            logger.warn("sound: " + e);
        }
    }

    private static Clip clip(byte[] data, double volume) throws Exception {
        AudioInputStream in = AudioSystem.getAudioInputStream(new ByteArrayInputStream(data));
        Clip clip = AudioSystem.getClip();
        clip.open(in);
        if (clip.isControlSupported(FloatControl.Type.MASTER_GAIN) && volume < 1) {
            FloatControl gain = (FloatControl) clip.getControl(FloatControl.Type.MASTER_GAIN);
            float db = (float) (20 * Math.log10(Math.max(volume, 0.0001)));
            gain.setValue(Math.max(gain.getMinimum(), db));
        }
        return clip;
    }

    @Override public void playMusic(String path, double volume, boolean loop) {
        if (path.equals(musicPath) && music != null) {
            if (!music.isRunning()) music.start();
            return;
        }
        stopMusic();
        byte[] data = wav(path);
        if (data == null) return;
        try {
            music = clip(data, volume);
            musicPath = path;
            if (loop) music.loop(Clip.LOOP_CONTINUOUSLY);
            else music.start();
        } catch (Exception e) {
            logger.warn("music: " + e);
        }
    }

    @Override public void stopMusic() {
        if (music != null) {
            music.stop();
            music.close();
            music = null;
        }
        musicPath = null;
    }

    @Override public void pause() {
        if (music != null) music.stop();
    }

    @Override public void resume() {
        if (music != null) music.start();
    }

    @Override public void release() {
        stopMusic();
    }
}
