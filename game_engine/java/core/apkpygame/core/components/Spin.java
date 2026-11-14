package apkpygame.core.components;

import apkpygame.core.Component;

/** Turns the entity at a constant speed (degrees per second). */
public final class Spin extends Component {
    public double speed;

    public Spin(double degreesPerSecond) {
        speed = degreesPerSecond;
    }

    @Override protected void update(double dt) {
        entity().transform.rotation += speed * dt;
    }
}
