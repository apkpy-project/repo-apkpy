package apkpygame.desktop;

import apkpygame.core.Game;
import apkpygame.core.GameException;
import apkpygame.core.GameHost;

import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.awt.image.DataBufferByte;
import java.io.BufferedReader;
import java.io.DataOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;

/**
 * The game with no window of its own: frames go out on stdout, input comes in
 * on stdin. The ApkPy Previewer (Tk) shows the frames inside its own window,
 * where the phone's screen is, and forwards the mouse and keys.
 *
 * <pre>
 * stdout, binary messages:  'F' int w, int h, w*h*3 bytes (BGR)   a frame
 *                           'R' int n, n bytes (UTF-8)            how the game ended (protocol v1)
 * stdin, text lines:        down ID X Y | move ID X Y | up ID X Y  (surface pixels)
 *                           key down NAME | key up NAME | back | resize W H | resume | quit
 * </pre>
 */
final class Embed {
    /** The Previewer stands for a 1080p phone: pixel-art scales round as they do on one (see Viewport). */
    static final int PHONE_SHORT_SIDE = 1080;

    private final Game game;
    private final DesktopPlatform platform;
    private final DataOutputStream out;
    private volatile int width, height;
    private volatile boolean suspended, suspendedOnce, closing;
    private final Object lock = new Object();

    private Embed(Game game, DesktopPlatform platform, int width, int height) {
        this.game = game;
        this.platform = platform;
        this.width = width;
        this.height = height;
        this.out = new DataOutputStream(new java.io.BufferedOutputStream(System.out, 1 << 20));
    }

    static void run(File bundle, File store, String scene, String args, int width, int height, double fps,
                    long autoExitMs, long autoBackMs) {
        DesktopPlatform platform = new DesktopPlatform(bundle, store, true, PHONE_SHORT_SIDE);
        final Embed embed;
        try {
            Game game = Game.load(platform);
            game.start(scene, args);
            embed = new Embed(game, platform, width, height);
        } catch (GameException e) {
            System.err.println(e);
            new Embed(null, platform, 1, 1).message(Main.errorJson(e));
            return;
        }
        if (autoBackMs >= 0) embed.later(autoBackMs, false);
        if (autoExitMs >= 0) embed.later(autoExitMs, true);
        embed.loop(fps);
    }

    /** Tests only (--autoback-ms / --autoexit-ms): Back once, or the end of the game, after ms of play. */
    private void later(final long ms, final boolean exit) {
        Thread t = new Thread(new Runnable() {
            @Override public void run() {
                try {
                    Thread.sleep(ms);
                    if (exit) {
                        while (suspended) Thread.sleep(50);     // a suspended game ends after it is resumed
                        Thread.sleep(suspendedOnce ? 300 : 0);
                    }
                } catch (InterruptedException e) {
                    return;
                }
                synchronized (game) {
                    if (!exit) {
                        game.back();
                        return;
                    }
                    java.util.Map<String, Object> result = new java.util.LinkedHashMap<String, Object>();
                    result.put("reason", "auto");
                    result.put("steps", (double) game.steps());
                    result.put("fps", (double) game.fps());
                    game.exit(result);
                }
            }
        });
        t.setDaemon(true);
        t.start();
    }

    private void message(String json) {
        try {
            byte[] b = json.getBytes("UTF-8");
            synchronized (out) {
                out.writeByte('R');
                out.writeInt(b.length);
                out.write(b);
                out.flush();
            }
        } catch (IOException e) {
            closing = true;
        }
    }

    private void readInput() {
        Thread t = new Thread(new Runnable() {
            @Override public void run() {
                BufferedReader in;
                try {
                    in = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
                    String line;
                    while ((line = in.readLine()) != null) command(line.trim().split(" "));
                } catch (IOException ignored) {
                    // the Previewer went away
                }
                closing = true;
                synchronized (lock) {
                    lock.notifyAll();
                }
            }
        });
        t.setDaemon(true);
        t.start();
    }

    private void command(String[] c) {
        if (c.length == 0) return;
        if (c[0].equals("down") || c[0].equals("move") || c[0].equals("up")) {
            int id = Integer.parseInt(c[1]);
            double x = Double.parseDouble(c[2]), y = Double.parseDouble(c[3]);
            if (c[0].equals("down")) game.input.pointerDown(id, x, y);
            else if (c[0].equals("move")) game.input.pointerMove(id, x, y);
            else game.input.pointerUp(id, x, y);
        } else if (c[0].equals("key") && c.length == 3) {
            if (c[1].equals("down")) game.input.keyDown(c[2]);
            else game.input.keyUp(c[2]);
        } else if (c[0].equals("back")) {
            synchronized (game) {
                game.back();
            }
        } else if (c[0].equals("resize") && c.length == 3) {
            width = Integer.parseInt(c[1]);
            height = Integer.parseInt(c[2]);
        } else if (c[0].equals("resume")) {
            synchronized (game) {
                game.resumeAfterOpen();
                suspended = false;
            }
            synchronized (lock) {
                lock.notifyAll();
            }
        } else if (c[0].equals("quit")) {
            closing = true;
            synchronized (lock) {
                lock.notifyAll();
            }
        }
    }

    private void loop(double fps) {
        game.setHost(new GameHost() {
            @Override public void ended(String json) {
                message(json);
                if (json.contains("\"suspended\":true")) suspended = suspendedOnce = true;
                else closing = true;
            }
        });
        readInput();
        long frameNanos = (long) (1e9 / fps);
        long last = System.nanoTime();
        BufferedImage image = null;
        while (!closing) {
            if (suspended) {
                platform.audio().pause();
                synchronized (lock) {
                    while (suspended && !closing) {
                        try {
                            lock.wait(100);
                        } catch (InterruptedException e) {
                            return;
                        }
                    }
                }
                platform.audio().resume();
                last = System.nanoTime();
                continue;
            }
            long now = System.nanoTime();
            int w = width, h = height;
            if (image == null || image.getWidth() != w || image.getHeight() != h) {
                image = new BufferedImage(w, h, BufferedImage.TYPE_3BYTE_BGR);
            }
            try {
                synchronized (game) {
                    game.advance((now - last) / 1e9);
                    if (closing || suspended) {
                        last = now;
                        continue;
                    }
                    Graphics2D g = image.createGraphics();
                    platform.renderer.setGraphics(g);
                    game.render(w, h);
                    g.dispose();
                }
                byte[] pixels = ((DataBufferByte) image.getRaster().getDataBuffer()).getData();
                synchronized (out) {
                    out.writeByte('F');
                    out.writeInt(w);
                    out.writeInt(h);
                    out.write(pixels);
                    out.flush();
                }
            } catch (GameException e) {
                message(Main.errorJson(e));
                break;
            } catch (IOException e) {
                break;
            }
            last = now;
            long sleep = frameNanos - (System.nanoTime() - now);
            if (sleep > 0) {
                try {
                    Thread.sleep(sleep / 1000000L, (int) (sleep % 1000000L));
                } catch (InterruptedException e) {
                    break;
                }
            }
        }
        platform.audio().release();
        System.exit(0);
    }
}
