package apkpygame.core.components;

import apkpygame.core.Actions;
import apkpygame.core.Component;
import apkpygame.core.Entity;

import java.util.ArrayList;
import java.util.List;

/**
 * Runs actions when this entity's Collider starts touching another one with
 * {@code tag} ("" = any), coming from {@code side}: "top" (the other came from
 * above: a stomp), "bottom", "sides", or "any". In the actions, target="other"
 * is the entity touched.
 */
public final class OnCollide extends Component {
    public String tag = "";
    public String side = "any";
    public final List<Actions.Action> actions = new ArrayList<Actions.Action>();

    /** Called by the physics. */
    public void contact(Entity other, String from) {
        if (!entity().active) return;
        if (!tag.isEmpty() && !other.hasTag(tag)) return;
        if (!side.equals("any") && !side.equals(from)) return;
        Actions.runAll(actions, game(), entity(), other);
    }
}
