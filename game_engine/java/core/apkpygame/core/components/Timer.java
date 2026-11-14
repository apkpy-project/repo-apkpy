package apkpygame.core.components;

import apkpygame.core.Actions;
import apkpygame.core.Component;

import java.util.ArrayList;
import java.util.List;

/** Runs actions every {@code every} seconds (or once, with repeat=false), after an optional delay. */
public final class Timer extends Component {
    public double every = 1, delay;
    public boolean repeat = true;
    public final List<Actions.Action> actions = new ArrayList<Actions.Action>();
    private double wait;
    private boolean done;

    @Override protected void start() {
        wait = delay + every;
    }

    @Override protected void update(double dt) {
        if (done) return;
        wait -= dt;
        if (wait > 0) return;
        Actions.runAll(actions, game(), entity(), null);
        if (repeat) wait += every;
        else done = true;
    }
}
