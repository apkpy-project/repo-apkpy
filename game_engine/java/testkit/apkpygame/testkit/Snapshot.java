package apkpygame.testkit;

import apkpygame.core.Game;
import apkpygame.core.Platform;

/**
 * Runs a scene for N fixed steps with no window and answers the state hash.
 * The same call on the JVM and on the phone must give the same text: that
 * is the proof that the game logic does not depend on where it runs.
 */
public final class Snapshot {
    private Snapshot() { }

    public static String run(Platform.AssetSource assets, String scene, String argsJson, int steps) {
        Game game = Game.load(new HeadlessPlatform(assets));
        game.start(scene, argsJson);
        for (int i = 0; i < steps; i++) game.step();
        return game.stateHash();
    }
}
