package apkpygame.desktop;

import apkpygame.core.Entity;
import apkpygame.core.Game;
import apkpygame.core.GameException;
import apkpygame.core.GameHost;
import apkpygame.core.json.Json;
import apkpygame.testkit.Snapshot;

import java.awt.Canvas;
import java.awt.Dimension;
import java.awt.Graphics2D;
import java.awt.Toolkit;
import java.awt.event.KeyAdapter;
import java.awt.event.KeyEvent;
import java.awt.event.MouseAdapter;
import java.awt.event.MouseEvent;
import java.awt.event.WindowAdapter;
import java.awt.event.WindowEvent;
import java.awt.image.BufferStrategy;
import java.io.File;
import java.util.LinkedHashMap;
import java.util.Map;
import javax.swing.JFrame;
import javax.swing.SwingUtilities;

/**
 * The desktop runner: the same core as the phone, drawn with Java2D.
 *
 * <pre>
 * java -jar apkpygame-desktop.jar --bundle DIR [--scene NAME] [--args JSON]
 *      [--store FILE] [--headless STEPS] [--autoexit-ms MS] [--autoback-ms MS] [--parent-pipe]
 *      [--restore JOURNAL] [--embed WxH]
 *      [--screenshot PNG [--steps N] [--width W --height H]] [--replay STEP:KEY:down|up,... [--steps N]
 *      [--trace NAME_OR_TAG,...]]
 * </pre>
 *
 * Prints one line "APKPYGAME_RESULT {json}" when the game ends (protocol v1),
 * which is what the Previewer's preview= reads. --headless prints
 * "APKPYGAME_STATE {hash}" after STEPS fixed steps (the parity check).
 */
public final class Main {
    private final Game game;
    private final DesktopPlatform platform;
    private final Canvas canvas = new Canvas();
    private JFrame frame;
    private volatile boolean closing;
    /** open_app: the world waits in memory, as on the phone, for "resume" on stdin. */
    private volatile boolean suspended, suspendedOnce;
    private java.io.BufferedReader stdin;
    /** --parent-pipe: stdin is read all the time; its end means the Previewer is gone (killed by a hot reload). */
    private java.util.concurrent.BlockingQueue<String> lines;

    private Main(Game game, DesktopPlatform platform) {
        this.game = game;
        this.platform = platform;
    }

    public static void main(String[] argv) throws Exception {
        Map<String, String> a = options(argv);
        File bundle = new File(a.containsKey("bundle") ? a.get("bundle") : ".");
        String scene = a.get("scene");
        String args = a.containsKey("args") ? a.get("args") : "";
        if (a.containsKey("embed")) {
            // --embed WxH [--fps N]: no window; frames on stdout for the ApkPy Previewer (see Embed)
            String[] size = a.get("embed").split("x");
            File embedStore = new File(a.containsKey("store") ? a.get("store")
                    : new File(bundle.getAbsoluteFile().getParentFile(), "store.json").getPath());
            Embed.run(bundle, embedStore, scene, args, Integer.parseInt(size[0]), Integer.parseInt(size[1]),
                    a.containsKey("fps") ? Double.parseDouble(a.get("fps")) : 60,
                    a.containsKey("autoexit-ms") ? Long.parseLong(a.get("autoexit-ms")) : -1,
                    a.containsKey("autoback-ms") ? Long.parseLong(a.get("autoback-ms")) : -1);
            return;
        }
        if (a.containsKey("replay") && !a.containsKey("screenshot")) {
            replay(bundle, scene, args, a.get("replay"), Integer.parseInt(a.containsKey("steps") ? a.get("steps") : "3600"),
                    a.get("trace"));
            return;
        }
        if (a.containsKey("restore")) {
            // --restore JOURNAL: brings a suspended game back from its journal (the phone's
            // files/apkpygame/suspended.json) and prints its state: it must be the saved one
            byte[] journal = java.nio.file.Files.readAllBytes(new File(a.get("restore")).toPath());
            Game game = Game.restore(new DesktopPlatform(bundle, new File(bundle.getAbsoluteFile().getParentFile(),
                    "store.json"), false), new String(journal, "UTF-8"));
            System.out.println("APKPYGAME_STATE " + game.stateHash());
            return;
        }
        if (a.containsKey("headless")) {
            System.out.println("APKPYGAME_STATE " + Snapshot.run(DesktopPlatform.folder(bundle),
                    scene == null ? "" : scene, args, Integer.parseInt(a.get("headless"))));
            return;
        }
        File store = new File(a.containsKey("store") ? a.get("store")
                : new File(bundle.getAbsoluteFile().getParentFile(), "store.json").getPath());
        boolean screenshot = a.containsKey("screenshot");
        DesktopPlatform platform = new DesktopPlatform(bundle, store, !screenshot && !a.containsKey("mute"));
        if (screenshot) {
            // --screenshot PNG [--steps N] [--width W --height H]: N steps, one frame, no window
            Game game = Game.load(platform);
            game.start(scene, args);
            int steps = a.containsKey("steps") ? Integer.parseInt(a.get("steps")) : 60;
            // with --replay SCRIPT: a picture of any moment of a game
            java.util.Map<Long, java.util.List<String[]>> events = apkpygame.testkit.Replay.parse(a.get("replay"));
            if (a.containsKey("replay")) game.viewport.update((int) game.config.width, (int) game.config.height);
            for (int i = 0; i < steps && !game.isEnded(); i++) {
                apkpygame.testkit.Replay.apply(game, events, i);
                game.step();
            }
            int w = a.containsKey("width") ? Integer.parseInt(a.get("width")) : (int) game.config.width * 2;
            int h = a.containsKey("height") ? Integer.parseInt(a.get("height")) : (int) game.config.height * 2;
            java.awt.image.BufferedImage image = new java.awt.image.BufferedImage(w, h,
                    java.awt.image.BufferedImage.TYPE_INT_ARGB);
            Graphics2D g = image.createGraphics();
            platform.renderer.setGraphics(g);
            game.render(w, h);
            g.dispose();
            javax.imageio.ImageIO.write(image, "png", new File(a.get("screenshot")));
            System.out.println("APKPYGAME_STATE " + game.stateHash());
            return;
        }
        final Main main;
        try {
            Game game = Game.load(platform);
            game.start(scene, args);
            main = new Main(game, platform);
        } catch (GameException e) {
            System.err.println(e);
            result(errorJson(e));
            System.exit(2);
            return;
        }
        if (a.containsKey("parent-pipe")) main.watchParent();
        if (a.containsKey("autoexit-ms")) main.autoExit(Long.parseLong(a.get("autoexit-ms")));
        if (a.containsKey("autoback-ms")) main.autoBack(Long.parseLong(a.get("autoback-ms")));
        SwingUtilities.invokeAndWait(new Runnable() {
            @Override public void run() {
                main.open();
            }
        });
        main.loop();
    }

    private static Map<String, String> options(String[] argv) {
        Map<String, String> out = new LinkedHashMap<String, String>();
        for (int i = 0; i < argv.length; i++) {
            if (argv[i].startsWith("--")) {
                String key = argv[i].substring(2);
                String value = i + 1 < argv.length && !argv[i + 1].startsWith("--") ? argv[++i] : "true";
                out.put(key, value);
            }
        }
        return out;
    }

    /**
     * --replay "STEP:KEY:down,STEP:KEY:up,..." [--steps N]: plays the keys at those
     * fixed steps with no window, until the game ends or N steps. Prints the end,
     * the variables and the state hash. The engine is deterministic, so a replay
     * that wins here wins the same way on the phone.
     */
    static void replay(File bundle, String scene, String args, String script, int maxSteps, String trace) {
        apkpygame.testkit.Replay r = apkpygame.testkit.Replay.run(DesktopPlatform.folder(bundle), scene, args, script,
                maxSteps, trace);
        for (String line : r.trace) System.out.println("APKPYGAME_TRACE " + line);
        for (String e : r.events) {
            String[] p = e.split(" ", 2);
            System.out.println("APKPYGAME_EVENT step=" + p[0] + " vars=" + p[1]);
        }
        System.out.println("APKPYGAME_MAXX " + r.maxPlayerX);
        System.out.println("APKPYGAME_REPLAY steps=" + r.steps + " vars=" + r.vars);
        if (r.endJson != null) System.out.println("APKPYGAME_RESULT " + r.endJson);
        System.out.println("APKPYGAME_STATE " + r.hash);
        System.out.println("APKPYGAME_SUMMARY " + r.summary());
    }

    static void result(String json) {
        System.out.println("APKPYGAME_RESULT " + json);
        System.out.flush();
    }

    static String errorJson(GameException e) {
        Map<String, Object> error = new LinkedHashMap<String, Object>();
        error.put("code", e.code);
        error.put("message", e.getMessage());
        error.put("fix", e.fix);
        Map<String, Object> out = new LinkedHashMap<String, Object>();
        out.put("v", 1.0);
        out.put("action", "error");
        out.put("error", error);
        out.put("suspended", false);
        return Json.stringify(out);
    }

    private void open() {
        frame = new JFrame(game.config.name + "  (ApkPyGame " + Game.VERSION + ")");
        Dimension screen = Toolkit.getDefaultToolkit().getScreenSize();
        double scale = Math.min(1.0, screen.height * 0.85 / game.config.height);
        if (game.config.width * scale > screen.width * 0.9) scale = screen.width * 0.9 / game.config.width;
        canvas.setPreferredSize(new Dimension((int) (game.config.width * scale), (int) (game.config.height * scale)));
        canvas.setIgnoreRepaint(true);
        canvas.setFocusTraversalKeysEnabled(false);
        frame.add(canvas);
        frame.pack();
        frame.setLocationByPlatform(true);
        frame.setDefaultCloseOperation(JFrame.DO_NOTHING_ON_CLOSE);
        frame.addWindowListener(new WindowAdapter() {
            @Override public void windowClosing(WindowEvent e) {
                Map<String, Object> result = new LinkedHashMap<String, Object>();
                result.put("reason", "closed");
                synchronized (game) {
                    game.exit(result);
                }
            }
        });
        MouseAdapter mouse = new MouseAdapter() {
            @Override public void mousePressed(MouseEvent e) {
                game.input.pointerDown(0, e.getX(), e.getY());
            }

            @Override public void mouseDragged(MouseEvent e) {
                game.input.pointerMove(0, e.getX(), e.getY());
            }

            @Override public void mouseReleased(MouseEvent e) {
                game.input.pointerUp(0, e.getX(), e.getY());
            }
        };
        canvas.addMouseListener(mouse);
        canvas.addMouseMotionListener(mouse);
        canvas.addKeyListener(new KeyAdapter() {
            @Override public void keyPressed(KeyEvent e) {
                String k = keyName(e);
                if (k != null) game.input.keyDown(k);
                if (e.getKeyCode() == KeyEvent.VK_ESCAPE) {
                    synchronized (game) {
                        game.back();        // the scene's on_back, as Back on the phone
                    }
                }
            }

            @Override public void keyReleased(KeyEvent e) {
                String k = keyName(e);
                if (k != null) game.input.keyUp(k);
            }
        });
        frame.setVisible(true);
        canvas.createBufferStrategy(2);
        canvas.requestFocus();
        game.setHost(new GameHost() {
            @Override public void ended(String resultJson) {
                result(resultJson);
                if (resultJson.contains("\"suspended\":true")) suspended = suspendedOnce = true;
                else closing = true;
            }
        });
    }

    static String keyName(KeyEvent e) {
        switch (e.getKeyCode()) {
            case KeyEvent.VK_LEFT: return "left";
            case KeyEvent.VK_RIGHT: return "right";
            case KeyEvent.VK_UP: return "up";
            case KeyEvent.VK_DOWN: return "down";
            case KeyEvent.VK_SPACE: return "space";
            case KeyEvent.VK_ENTER: return "enter";
            case KeyEvent.VK_ESCAPE: return "escape";
            default:
                char ch = Character.toLowerCase(e.getKeyChar());
                if ((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9')) return String.valueOf(ch);
                return null;
        }
    }

    /** Tests: presses Back (the scene's on_back) once, after ms. */
    private void autoBack(final long ms) {
        Thread t = new Thread(new Runnable() {
            @Override public void run() {
                try {
                    Thread.sleep(ms);
                } catch (InterruptedException e) {
                    return;
                }
                synchronized (game) {
                    game.back();
                }
            }
        });
        t.setDaemon(true);
        t.start();
    }

    private void autoExit(final long ms) {
        Thread t = new Thread(new Runnable() {
            @Override public void run() {
                try {
                    Thread.sleep(ms);
                    while (suspended) Thread.sleep(50);     // a suspended game ends after it is resumed
                    Thread.sleep(suspendedOnce ? 300 : 0);
                } catch (InterruptedException e) {
                    return;
                }
                Map<String, Object> result = new LinkedHashMap<String, Object>();
                result.put("reason", "auto");
                result.put("steps", (double) game.steps());
                result.put("fps", (double) game.fps());
                synchronized (game) {
                    game.exit(result);
                }
            }
        });
        t.setDaemon(true);
        t.start();
    }

    /**
     * The game opened an ApkPy screen. The Previewer shows it, then writes
     * "resume" (game_resume) or "quit" (a new game_play) on our stdin.
     */
    private void watchParent() {
        lines = new java.util.concurrent.LinkedBlockingQueue<String>();
        Thread t = new Thread(new Runnable() {
            @Override public void run() {
                try {
                    java.io.BufferedReader in = new java.io.BufferedReader(new java.io.InputStreamReader(System.in, "UTF-8"));
                    for (String line; (line = in.readLine()) != null; ) lines.add(line);
                } catch (java.io.IOException ignored) {
                    // the parent went away
                }
                closing = true;                     // no Previewer any more: no window left behind
                lines.add("");
            }
        });
        t.setDaemon(true);
        t.start();
    }

    private void waitForResume() {
        SwingUtilities.invokeLater(new Runnable() {
            @Override public void run() {
                frame.setVisible(false);
            }
        });
        String line;
        try {
            if (lines != null) {
                line = lines.take();
            } else {
                if (stdin == null) stdin = new java.io.BufferedReader(new java.io.InputStreamReader(System.in, "UTF-8"));
                line = stdin.readLine();
            }
        } catch (InterruptedException e) {
            line = null;
        } catch (java.io.IOException e) {
            line = null;
        }
        if (line == null || !line.trim().equals("resume")) {
            closing = true;
            return;
        }
        synchronized (game) {
            game.resumeAfterOpen();
            suspended = false;
        }
        SwingUtilities.invokeLater(new Runnable() {
            @Override public void run() {
                frame.setVisible(true);
                canvas.requestFocus();
            }
        });
    }

    private void loop() {
        BufferStrategy strategy = canvas.getBufferStrategy();
        long last = System.nanoTime();
        while (!closing) {
            if (suspended) {
                waitForResume();
                last = System.nanoTime();
                continue;
            }
            long now = System.nanoTime();
            try {
                synchronized (game) {
                    game.advance((now - last) / 1e9);
                    if (closing) break;
                    Graphics2D g = (Graphics2D) strategy.getDrawGraphics();
                    platform.renderer.setGraphics(g);
                    game.render(canvas.getWidth(), canvas.getHeight());
                    g.dispose();
                }
                strategy.show();
                Toolkit.getDefaultToolkit().sync();
            } catch (GameException e) {
                System.err.println(e);
                result(errorJson(e));
                break;
            }
            last = now;
            long spent = System.nanoTime() - now;
            long sleep = 4_000_000L - spent;      // ~240 Hz cap; the display paces the rest
            if (sleep > 0) {
                try {
                    Thread.sleep(sleep / 1_000_000L, (int) (sleep % 1_000_000L));
                } catch (InterruptedException e) {
                    break;
                }
            }
        }
        platform.audio().release();
        frame.dispose();
        System.exit(0);
    }
}
