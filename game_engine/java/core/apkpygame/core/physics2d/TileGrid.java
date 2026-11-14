package apkpygame.core.physics2d;

/**
 * The solid cells of a tilemap, for the physics. Columns outside the map are
 * walls (so the player cannot leave it sideways); rows above are open sky and
 * rows below are a pit (falling out is a game rule, not a wall).
 */
public final class TileGrid {
    public final double originX, originY, tileW, tileH;
    public final int cols, rows;
    private final boolean[] solid;

    public TileGrid(double originX, double originY, double tileW, double tileH, int cols, int rows, boolean[] solid) {
        this.originX = originX;
        this.originY = originY;
        this.tileW = tileW;
        this.tileH = tileH;
        this.cols = cols;
        this.rows = rows;
        this.solid = solid;
    }

    public boolean solidAt(int col, int row) {
        if (col < 0 || col >= cols) return true;
        if (row < 0 || row >= rows) return false;
        return solid[row * cols + col];
    }

    public int col(double x) {
        return (int) Math.floor((x - originX) / tileW);
    }

    public int row(double y) {
        return (int) Math.floor((y - originY) / tileH);
    }

    public double width() {
        return cols * tileW;
    }

    public double height() {
        return rows * tileH;
    }
}
