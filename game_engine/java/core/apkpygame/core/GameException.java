package apkpygame.core;

/**
 * A runtime error with a code (G3xxx), what went wrong and how to fix it,
 * in the style of ApkPy's own errors.
 */
public final class GameException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    public final String code;
    public final String fix;

    public GameException(String code, String message, String fix) {
        super(message);
        this.code = code;
        this.fix = fix;
    }

    public GameException(String code, String message, String fix, Throwable cause) {
        super(message, cause);
        this.code = code;
        this.fix = fix;
    }

    @Override public String toString() {
        return "APKPY " + code + ": " + getMessage() + (fix == null ? "" : "\n  How to fix: " + fix);
    }
}
