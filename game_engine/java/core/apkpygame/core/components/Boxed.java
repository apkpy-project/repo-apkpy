package apkpygame.core.components;

/** A component with a rectangle in the entity's space: where it can be tapped (see Area). */
public interface Boxed {
    double boxLeft();

    double boxTop();

    double boxWidth();

    double boxHeight();
}
