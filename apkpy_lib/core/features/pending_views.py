"""A component changed from another screen -- ``ApkpyPending``.

Each ``Screen`` is its own Activity, and an Activity only has its own views.
So ``total.set_value("Habits: 3")`` in a function running on the Home screen,
where ``total`` lives on Stats, used to be dropped from Home's Java without a
word: the Previewer updated the label, the phone never did. Found by an AI
agent writing a habit tracker, whose stats screen went stale.

Now the running screen leaves the value in a process-wide box addressed to
the screen that owns the component, and that screen applies it when it comes
to the front -- or at once, if it already is (an ``https`` answer arriving
after the person moved on). The last value written wins, as in the Previewer.

Module-level code is the exception. The Previewer runs it once; each Activity
runs it again in its own onCreate, where every screen already sets its own
components. A write it makes to another screen is muted: left in the box, it
would reset that screen -- a text somebody typed there -- every time a third
screen opened.

This covers ``set_value``, ``show()``/``hide()`` and ``set_items``: the rows
travel as the list would have stored them, normalised by the same emitters a
set_items on the list's own screen uses. The other feed operations
(``append_items``, ``merge_items``, ``update_item``...) still run on the
list's own screen.
"""

CLASS = "ApkpyPending"
VALUE = "value"
VISIBLE = "visible"
ITEMS = "items"
HAS_MORE = "has_more"

# (command type -> the kind of write it leaves in the box)
_KINDS = {"comp_set_value": VALUE, "comp_visibility": VISIBLE,
          "comp_set_items": ITEMS}


def _flat(components):
    for component in components or []:
        yield component
        yield from _flat(component.get("children"))


def _walk(value):
    """Every command dict below ``value``, whatever key holds it."""
    if isinstance(value, dict):
        yield value
        for inner in value.values():
            yield from _walk(inner)
    elif isinstance(value, (list, tuple)):
        for inner in value:
            yield from _walk(inner)


def components_by_name(screen_components):
    """Every component of every screen by its Python name: a screen writing
    to another screen's list needs to know what kind of list it is."""
    found = {}
    for components in (screen_components or {}).values():
        for component in _flat(components):
            name = component.get("_py_var")
            if name and name not in found:
                found[name] = component
    return found


def plan(screen_components, functions, module_init_cmds=()):
    """``(owners, targets)`` for one app.

    ``owners`` maps a component's Python name to the screen it lives on;
    ``targets`` maps a screen to ``{name: {kinds}}`` -- the components some
    code may write from elsewhere, which that screen must be ready to take.
    An app with one screen has nowhere else to write from: both are empty.
    """
    if len(screen_components or {}) < 2:
        return {}, {}
    owners = {}
    for screen, components in screen_components.items():
        for component in _flat(components):
            name = component.get("_py_var")
            if name and name not in owners:
                owners[name] = screen
    targets = {}
    sources = [info.get("cmds", []) for info in (functions or {}).values()
               if isinstance(info, dict)]
    sources.append(list(module_init_cmds or []))
    sources.append([c for comps in screen_components.values() for c in _flat(comps)])
    for source in sources:
        for command in _walk(source):
            kind = _KINDS.get(command.get("type"))
            name = command.get("py_var")
            if kind and name in owners:
                targets.setdefault(owners[name], {}).setdefault(name, set()).add(kind)
    return owners, targets


def put_line(indent, screen, name, kind, value_java):
    return (f'{indent}{CLASS}.put("{screen}", "{name}:{kind}", '
            f'String.valueOf({value_java}));')


def mute_line(indent, on):
    return f"{indent}{CLASS}.mute({'true' if on else 'false'});"


def take_expr(screen, name, kind):
    return f'{CLASS}.take("{screen}", "{name}:{kind}")'


def shared_class_java(package):
    return '''package %(package)s;

import android.os.Handler;
import android.os.Looper;

import java.util.HashMap;
import java.util.Map;

/**
 * Values written to a screen that is not in front.
 *
 * Each screen is its own Activity and only has its own views, so a function
 * running on one screen that sets a label on another leaves the value here,
 * addressed to the screen that owns the label. That screen takes it when it
 * comes to the front, or at once if it already is. The last write wins.
 */
public final class %(klass)s {

    private static final Map<String, Map<String, String>> WAITING = new HashMap<>();
    private static final Map<String, Runnable> IN_FRONT = new HashMap<>();
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static boolean muted;

    private %(klass)s() {}

    public static void put(String screen, String key, String value) {
        Runnable apply;
        synchronized (%(klass)s.class) {
            if (muted) return;
            Map<String, String> box = WAITING.get(screen);
            if (box == null) {
                box = new HashMap<>();
                WAITING.put(screen, box);
            }
            box.put(key, value);
            apply = IN_FRONT.get(screen);
        }
        if (apply != null) MAIN.post(apply);
    }

    public static synchronized String take(String screen, String key) {
        Map<String, String> box = WAITING.get(screen);
        return box == null ? null : box.remove(key);
    }

    /**
     * Module-level code is running again in a screen's onCreate: every screen
     * sets its own components there, so writes to other screens are not kept.
     */
    public static synchronized void mute(boolean on) {
        muted = on;
    }

    /** The screen is in front: anything written to it from now on is applied at once. */
    public static synchronized void inFront(String screen, Runnable apply) {
        IN_FRONT.put(screen, apply);
    }

    public static synchronized void behind(String screen, Runnable apply) {
        if (IN_FRONT.get(screen) == apply) IN_FRONT.remove(screen);
    }
}
''' % {"package": package, "klass": CLASS}
