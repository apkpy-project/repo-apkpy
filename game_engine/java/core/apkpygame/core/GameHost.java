package apkpygame.core;

/**
 * Where a game's end goes: the Android GameActivity hands it to the ApkPy
 * screen that opened the game; the desktop runner prints it for the Previewer.
 *
 * The JSON follows protocol v1:
 * {"v":1,"action":"exit"|"open"|"none"|"error", ...}
 */
public interface GameHost {
    void ended(String resultJson);
}
