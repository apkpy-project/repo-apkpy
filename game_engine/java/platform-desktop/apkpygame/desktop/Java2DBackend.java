package apkpygame.desktop;

import apkpygame.core.GameException;
import apkpygame.core.math.Color;
import apkpygame.core.render.DrawCommand;
import apkpygame.core.render.RenderBackend;
import apkpygame.core.render.Texture;

import java.awt.AlphaComposite;
import java.awt.BasicStroke;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.geom.AffineTransform;
import java.awt.geom.Ellipse2D;
import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import javax.imageio.ImageIO;

/**
 * Draws the render queue with Java2D (the desktop runner). 2.5D quads
 * (QUAD3D) go to the software Raster3D; its image is laid on the surface
 * before the first 2D command that follows them (the UI), or at the end.
 */
final class Java2DBackend implements RenderBackend {
    private final apkpygame.core.render.Raster3D raster = new apkpygame.core.render.Raster3D();
    private final Map<Texture, int[]> texels = new java.util.IdentityHashMap<Texture, int[]>();
    private BufferedImage layer3d;
    private boolean pending3d;
    private Graphics2D g;
    private AffineTransform base;
    private final AffineTransform at = new AffineTransform();
    private final Map<String, BufferedImage> regions = new HashMap<String, BufferedImage>();
    private final Font font = new Font(Font.SANS_SERIF, Font.PLAIN, 16);

    void setGraphics(Graphics2D graphics) {
        g = graphics;
        base = graphics.getTransform();    // includes the display scale on HiDPI screens
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
    }

    @Override public Texture loadTexture(String path, byte[] data) {
        BufferedImage image;
        try {
            image = ImageIO.read(new ByteArrayInputStream(data));
        } catch (IOException e) {
            image = null;
        }
        if (image == null) {
            throw new GameException("G3022", "'" + path + "' is not an image the desktop can read",
                    "Use PNG or JPEG.");
        }
        return new Texture(path, image.getWidth(), image.getHeight(), image);
    }

    @Override public Object loadFont(String path, byte[] data) {
        try {
            return Font.createFont(Font.TRUETYPE_FONT, new java.io.ByteArrayInputStream(data));
        } catch (java.awt.FontFormatException | java.io.IOException e) {
            return null;                                   // the system font: the build already read this file
        }
    }

    @Override public void begin(int surfaceWidth, int surfaceHeight, int clearColor) {
        raster.begin(surfaceWidth, surfaceHeight);
        pending3d = false;
        g.setTransform(base);
        g.setComposite(AlphaComposite.SrcOver);
        g.setColor(new java.awt.Color(clearColor, true));
        g.fillRect(0, 0, surfaceWidth, surfaceHeight);
    }

    @Override public void draw(DrawCommand c) {
        if (c.kind == DrawCommand.Kind.QUAD3D) {
            int[] t = c.texture == null ? null : texels(c.texture);
            raster.quad(c, t, c.texture == null ? 0 : c.texture.width, c.texture == null ? 0 : c.texture.height);
            pending3d = true;
            return;
        }
        if (pending3d) lay3d();
        g.setTransform(base);
        g.setClip(c.clipping ? new Rectangle2D.Double(c.clipX, c.clipY, c.clipW, c.clipH) : null);
        at.setTransform(c.matrix.a, c.matrix.b, c.matrix.c, c.matrix.d, c.matrix.tx, c.matrix.ty);
        g.transform(at);
        switch (c.kind) {
            case SPRITE: {
                BufferedImage image = c.texture.pixels != null ? painted(c) : region(c);
                g.setComposite(AlphaComposite.getInstance(AlphaComposite.SRC_OVER,
                        (float) Math.max(0, Math.min(1, c.alpha))));
                g.setRenderingHint(RenderingHints.KEY_INTERPOLATION, c.smooth
                        ? RenderingHints.VALUE_INTERPOLATION_BILINEAR
                        : RenderingHints.VALUE_INTERPOLATION_NEAREST_NEIGHBOR);
                AffineTransform place = AffineTransform.getTranslateInstance(c.x, c.y);
                place.scale(c.w / c.srcW, c.h / c.srcH);
                g.drawImage(image, place, null);
                g.setComposite(AlphaComposite.SrcOver);
                break;
            }
            case RECT:
            case CIRCLE: {
                g.setColor(new java.awt.Color(c.color, true));
                java.awt.Shape s = c.kind == DrawCommand.Kind.RECT
                        ? new Rectangle2D.Double(c.x, c.y, c.w, c.h)
                        : new Ellipse2D.Double(c.x, c.y, c.w, c.h);
                if (c.filled) {
                    g.fill(s);
                } else {
                    g.setStroke(new BasicStroke((float) c.stroke));
                    g.draw(s);
                }
                break;
            }
            case TEXT: {
                g.setColor(new java.awt.Color(c.color, true));
                g.setFont((c.face instanceof Font ? (Font) c.face : font).deriveFont((float) c.size));
                FontMetrics m = g.getFontMetrics();
                double width = m.stringWidth(c.text);
                double x = c.align < 0 ? c.x : c.align == 0 ? c.x - width / 2 : c.x - width;
                g.drawString(c.text, (float) x, (float) c.y);
                break;
            }
            default:
                break;
        }
    }

    /**
     * A Canvas: an image over the canvas's own pixels, so it is always what the game painted, with no copy.
     * (Java2D keeps no copy of an image made over an array it did not make.)
     */
    private BufferedImage painted(DrawCommand c) {
        Texture t = c.texture;
        if (t.live == null) {
            java.awt.image.DirectColorModel model = new java.awt.image.DirectColorModel(32,
                    0x00ff0000, 0x0000ff00, 0x000000ff, 0xff000000);
            java.awt.image.WritableRaster raster = java.awt.image.Raster.createPackedRaster(
                    new java.awt.image.DataBufferInt(t.pixels, t.pixels.length), t.width, t.height, t.width,
                    model.getMasks(), null);
            t.live = new BufferedImage(model, raster, false, null);
        }
        BufferedImage image = (BufferedImage) t.live;
        if (c.srcX == 0 && c.srcY == 0 && c.srcW == t.width && c.srcH == t.height) return image;
        return image.getSubimage(c.srcX, c.srcY, c.srcW, c.srcH);
    }

    /** The region, cut once and tinted once (multiply), then cached. */
    private BufferedImage region(DrawCommand c) {
        String key = c.texture.path + "#" + c.srcX + "," + c.srcY + "," + c.srcW + "," + c.srcH + "@" + c.color;
        BufferedImage hit = regions.get(key);
        if (hit != null) return hit;
        BufferedImage full = (BufferedImage) c.texture.handle;
        BufferedImage cut = new BufferedImage(c.srcW, c.srcH, BufferedImage.TYPE_INT_ARGB);
        Graphics2D cg = cut.createGraphics();
        cg.drawImage(full, -c.srcX, -c.srcY, null);
        cg.dispose();
        if (c.color != Color.WHITE) {
            int tr = Color.red(c.color), tg = Color.green(c.color), tb = Color.blue(c.color);
            for (int y = 0; y < cut.getHeight(); y++) {
                for (int x = 0; x < cut.getWidth(); x++) {
                    int p = cut.getRGB(x, y);
                    cut.setRGB(x, y, (p & 0xFF000000) | ((Color.red(p) * tr / 255) << 16)
                            | ((Color.green(p) * tg / 255) << 8) | (Color.blue(p) * tb / 255));
                }
            }
        }
        regions.put(key, cut);
        return cut;
    }

    @Override public void end() {
        if (pending3d) lay3d();
        g = null;
    }

    /** The 2.5D image so far, laid on the surface (transparent where nothing was drawn). */
    private void lay3d() {
        pending3d = false;
        if (!raster.used()) return;
        int w = raster.width(), h = raster.height();
        if (layer3d == null || layer3d.getWidth() != w || layer3d.getHeight() != h) {
            layer3d = new BufferedImage(w, h, BufferedImage.TYPE_INT_ARGB);
        }
        int[] dst = ((java.awt.image.DataBufferInt) layer3d.getRaster().getDataBuffer()).getData();
        System.arraycopy(raster.pixels(), 0, dst, 0, w * h);
        g.setTransform(base);
        g.setComposite(AlphaComposite.SrcOver);
        g.drawImage(layer3d, 0, 0, null);
    }

    /** A texture's pixels as ARGB, read once. */
    private int[] texels(Texture t) {
        if (t.pixels != null) return t.pixels;
        int[] hit = texels.get(t);
        if (hit == null) {
            BufferedImage image = (BufferedImage) t.handle;
            hit = image.getRGB(0, 0, t.width, t.height, null, 0, t.width);
            texels.put(t, hit);
        }
        return hit;
    }
}
