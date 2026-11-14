package apkpygame.core.components;

import apkpygame.core.Actions;
import apkpygame.core.Component;

import java.util.ArrayList;
import java.util.List;

/** Destroys the entity after {@code seconds}, running {@code actions} first (bullets, effects, power-ups). */
public final class Lifetime extends Component {
    public double seconds = 1;
    public final List<Actions.Action> actions = new ArrayList<Actions.Action>();
    private double age;

    @Override protected void update(double dt) {
        age += dt;
        if (age >= seconds) {
            Actions.runAll(actions, game(), entity(), null);
            entity().destroy();
        }
    }
}
