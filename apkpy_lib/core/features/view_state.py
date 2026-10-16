"""Opt mutable text into Android's per-Activity saved view hierarchy.

EditText, CompoundButton, Spinner and SeekBar already save their own values.
TextView/Button do not save text by default. Remember only texts actually
changed at runtime: freezing every label would also freeze old translations.
The ID set belongs to the Activity's Bundle, not a process-global store, so a
fresh screen cannot inherit another screen's values (even with identical IDs).
"""

BODY_KEYS = ("true_body", "false_body", "body", "handler", "final")
NATIVE_VALUE_INPUTS = frozenset({
    "text", "password", "search", "textarea", "number",
    "switch", "checkbox", "radio", "select", "range",
})


def needs_text_state(component):
    if component.get("comp_type") in ("chips", "segmented"):
        # ApkpyChoice saves its own selection, as a CompoundButton does.
        return False
    return not (component.get("comp_type") in ("inputs", "input_field")
                and component.get("input_type", "text") in NATIVE_VALUE_INPUTS)


def used_by(components, functions, module_commands=None):
    by_var = {c.get("_py_var"): c for c in components if c.get("_py_var")}

    def walk(commands):
        for command in commands or []:
            if not isinstance(command, dict):
                continue
            component = by_var.get(command.get("py_var"))
            if component is not None and (
                command.get("type") == "comp_set_row_field"
                or (command.get("type") == "comp_set_value"
                    and needs_text_state(component))
            ):
                return True
            if any(walk(command.get(key)) for key in BODY_KEYS):
                return True
        return False

    # Date/time pickers mutate TextViews without going through set_value().
    return any(c.get("comp_type") in ("inputs", "input_field")
               and c.get("input_type") in ("date", "time") for c in components) or (
        walk(module_commands) or any(walk(
            info.get("cmds") if isinstance(info, dict) else info
        ) for info in (functions or {}).values())
    )


def remember(lines, indent, component, java_var, field=None):
    if field is None and not needs_text_state(component):
        return
    if component.get("comp_type") == "chart":
        # A ring's value is a number the chart draws, not text to restore.
        return
    target = java_var
    if field is not None:
        target += "_" + field
    elif component.get("comp_type") == "list_row":
        target += "_title"
    lines.append(f"{indent}_apkpyRememberText(R.id.{target});")


ACTIVITY_MEMBERS = '''
    // Only runtime-mutated text is frozen. Android owns the actual text,
    // input, selection and checked-state snapshot, including process recovery.
    private final java.util.HashSet<Integer> _apkpyFrozenText = new java.util.HashSet<>();

    private void _apkpyRememberText(int id) {
        android.view.View view = findViewById(id);
        if (view instanceof android.widget.TextView) {
            ((android.widget.TextView) view).setFreezesText(true);
            _apkpyFrozenText.add(id);
        }
    }

    private void _apkpyRestoreTextPolicy(android.os.Bundle state) {
        if (state == null) return;
        java.util.ArrayList<Integer> ids = state.getIntegerArrayList("apkpy:frozenText");
        if (ids != null) for (Integer id : ids) _apkpyRememberText(id);
    }

    @Override
    protected void onSaveInstanceState(android.os.Bundle outState) {
        outState.putIntegerArrayList("apkpy:frozenText",
                new java.util.ArrayList<>(_apkpyFrozenText));
        super.onSaveInstanceState(outState);
    }
'''
