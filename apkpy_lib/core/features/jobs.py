"""AST collection and Android code generation for ApkPy persistent jobs.

``background_job(...)`` becomes a WorkManager ``OneTimeWorkRequest`` pipeline:
a queue persisted in WorkManager's own database (so it survives process death
and reboots), constraints, automatic backoff, unique-work policies,
cancellation and observable progress.

Projects that never call ``background_job`` receive none of the classes below.
"""

from __future__ import annotations

import ast
import re


COMMAND_TYPES = {"job_enqueue", "job_cancel", "job_progress", "job_outcome"}

JOB_METHODS = {"enqueue", "cancel", "progress", "retry", "fail"}

RETRY_POLICIES = {"exponential": "EXPONENTIAL", "linear": "LINEAR"}
# "append" maps to APPEND_OR_REPLACE on purpose: plain APPEND cancels the new
# work when the previous item failed or was cancelled, which would quietly
# break the offline queue after the first failure.
CONFLICT_POLICIES = {
    "append": "APPEND_OR_REPLACE",
    "keep": "KEEP",
    "replace": "REPLACE",
}

PROGRESS_KEY = "apkpy_progress"
MESSAGE_KEY = "apkpy_message"

_MIN_BACKOFF_SECONDS = 10


def initialize(transpiler):
    transpiler.background_jobs = {}
    transpiler.job_observers = []


# ── parsing helpers ─────────────────────────────────────────────────────────

def _kw_node(call, name):
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _literal(transpiler, node, default=None):
    """Resolve a literal, following module-level string constants.

    During :func:`prescan` the transpiler has not collected ``string_constants``
    yet, so the constants gathered by the prescan itself are consulted first.
    """
    if node is None:
        return default
    if isinstance(node, ast.Name):
        constants = dict(getattr(transpiler, "_job_constants", None) or {})
        constants.update(getattr(transpiler, "string_constants", None) or {})
        if node.id in constants:
            return constants[node.id]
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return default


def safe_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(name or "job")).strip("_")
    return cleaned or "job"


def worker_class_name(name):
    parts = [part for part in safe_name(name).split("_") if part]
    camel = "".join(part[:1].upper() + part[1:] for part in parts) or "Job"
    return "%sJobWorker" % camel


def _job_for_node(transpiler, node):
    """Return the job declared as ``node`` (an ``ast.Name``), or None."""
    if isinstance(node, ast.Name):
        return getattr(transpiler, "background_jobs", {}).get(node.id)
    return None


def parse_assignment(transpiler, var_name, call):
    """Handle ``sync = background_job("sync_notes", run=fn, ...)``."""
    func = getattr(call, "func", None)
    if not (isinstance(func, ast.Name) and func.id == "background_job"):
        return False

    name_node = call.args[0] if call.args else _kw_node(call, "name")
    job_name = _literal(transpiler, name_node, var_name) or var_name

    run_node = _kw_node(call, "run")
    run_name = run_node.id if isinstance(run_node, ast.Name) else None
    if run_name is None:
        raise ValueError(
            'background_job("%s", run=...) needs a named function to run in '
            "the background." % job_name
        )

    retry = str(_literal(transpiler, _kw_node(call, "retry"), "exponential")).lower()
    conflict = str(
        _literal(transpiler, _kw_node(call, "on_conflict"), "append")
    ).lower()
    if retry not in RETRY_POLICIES:
        raise ValueError(
            'background_job(retry=...) must be "exponential" or "linear" — '
            "received %r" % retry
        )
    if conflict not in CONFLICT_POLICIES:
        raise ValueError(
            'background_job(on_conflict=...) must be "append", "keep" or '
            '"replace" — received %r' % conflict
        )

    requires_unmetered = bool(_literal(transpiler, _kw_node(call, "requires_unmetered"), False))
    try:
        retry_seconds = int(_literal(transpiler, _kw_node(call, "retry_seconds"), 30) or 30)
    except (TypeError, ValueError):
        retry_seconds = 30

    transpiler.background_jobs[var_name] = {
        "var": var_name,
        "name": job_name,
        "safe": safe_name(job_name),
        "run": run_name,
        "worker_class": worker_class_name(job_name),
        "requires_network": bool(
            _literal(transpiler, _kw_node(call, "requires_network"), False)
        ) or requires_unmetered,
        "requires_unmetered": requires_unmetered,
        "requires_charging": bool(
            _literal(transpiler, _kw_node(call, "requires_charging"), False)
        ),
        "requires_battery_not_low": bool(
            _literal(transpiler, _kw_node(call, "requires_battery_not_low"), False)
        ),
        "retry": retry,
        "retry_seconds": max(_MIN_BACKOFF_SECONDS, retry_seconds),
        "unique": bool(_literal(transpiler, _kw_node(call, "unique"), True)),
        "on_conflict": conflict,
        # The line of the declaration in writehere.py, so a failure later in
        # generation can point the diagnostic at the user's own code.
        "line": int(getattr(call, "lineno", 0) or 0),
    }
    # Enqueueing needs a live network only when the job asks for it; the
    # constraint itself is enforced by WorkManager, but the manifest still has
    # to allow the work to reach the network.
    if (transpiler.background_jobs[var_name]["requires_network"]
            and "INTERNET" not in transpiler.declared_permissions):
        transpiler.declared_permissions.append("INTERNET")
    return True


def prescan(transpiler, tree):
    """Register every ``background_job(...)`` before the module is visited.

    Python forces the run function to be written *above* the declaration
    (``run=sync_notes`` needs the name to exist), but the parser needs the job
    to exist before it can recognise ``sync.progress(...)`` inside that
    function.  Without this pass those calls would be dropped in silence — the
    classic ApkPy failure where the Previewer works and the APK does nothing.

    Running :func:`parse_assignment` again during the normal ``visit_Assign``
    is harmless: it re-registers identical data.
    """
    constants = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            constants.setdefault(node.targets[0].id, node.value.value)
    transpiler._job_constants = constants

    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)):
            parse_assignment(transpiler, node.targets[0].id, node.value)


def is_command_call(transpiler, call):
    """True for ``job.enqueue(...)`` / ``cancel`` / ``progress`` / ... ."""
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and _job_for_node(transpiler, func.value) is not None
        and func.attr in JOB_METHODS
    )


def is_observe_call(transpiler, call):
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and _job_for_node(transpiler, func.value) is not None
        and func.attr == "observe"
    )


def parse_observe(transpiler, call):
    """Handle the module-level binding ``job.observe(on_change=cb, screen=s)``."""
    if not is_observe_call(transpiler, call):
        return False
    job = _job_for_node(transpiler, call.func.value)
    change_node = _kw_node(call, "on_change") or (call.args[0] if call.args else None)
    callback = transpiler._register_result_callback(
        change_node, False, "job_%s_observe" % job["safe"]
    )
    if not callback:
        return True
    screen_var = transpiler._kw(call.keywords, "screen")
    transpiler.job_observers.append({
        "job": job["name"],
        "callback": callback,
        "screen_id": transpiler.screens.get(screen_var) if screen_var else None,
    })
    return True


def parse_command(transpiler, call):
    """Turn a job method call into a command dict, or return None."""
    if not is_command_call(transpiler, call):
        return None
    job = _job_for_node(transpiler, call.func.value)
    method = call.func.attr

    if method == "enqueue":
        data_node = call.args[0] if call.args else _kw_node(call, "data")
        if isinstance(data_node, ast.Name):
            data_node = getattr(transpiler, "dict_assignments", {}).get(
                data_node.id, data_node
            )
        return {"type": "job_enqueue", "job": job["name"], "safe": job["safe"],
                "data_node": data_node if isinstance(data_node, ast.Dict) else None}
    if method == "cancel":
        return {"type": "job_cancel", "job": job["name"], "safe": job["safe"]}
    if method == "progress":
        percent_node = call.args[0] if call.args else _kw_node(call, "percent")
        message_node = (
            call.args[1] if len(call.args) > 1 else _kw_node(call, "message")
        )
        return {"type": "job_progress", "job": job["name"], "safe": job["safe"],
                "percent_node": percent_node, "message_node": message_node}
    # retry() / fail()
    return {"type": "job_outcome", "job": job["name"], "safe": job["safe"],
            "outcome": "retry" if method == "retry" else "fail"}


def value_expression(node, val_to_java, job_vars):
    """Translate ``job.input("key")`` / ``job.attempt()`` used inline.

    Takes the set of declared job variable names rather than the transpiler:
    the Worker generator runs after parsing and has no transpiler reference.
    """
    func = getattr(node, "func", None)
    if not (
        isinstance(node, ast.Call) and isinstance(func, ast.Attribute)
        and func.attr in ("input", "attempt")
        and isinstance(func.value, ast.Name)
        and func.value.id in (job_vars or ())
    ):
        return None
    if func.attr == "attempt":
        # WorkManager counts attempts from zero; the Previewer counts from one,
        # so the value crossing to Python is normalised here.
        return "String.valueOf(getRunAttemptCount() + 1)"
    key_node = node.args[0] if node.args else _kw_node(node, "key")
    key = "" if key_node is None else val_to_java(key_node)
    return "_jobInput(String.valueOf(%s))" % (key or '""')


# ── code generation ─────────────────────────────────────────────────────────

def commands_use_jobs(functions_map, module_init_cmds=None):
    """True when any parsed command in this app touches a job."""
    def _scan(cmds):
        for command in cmds or []:
            if not isinstance(command, dict):
                continue
            if command.get("type") in COMMAND_TYPES:
                return True
            for key in ("true_body", "false_body", "body"):
                if command.get(key) and _scan(command[key]):
                    return True
        return False

    if _scan(module_init_cmds):
        return True
    for info in (functions_map or {}).values():
        if _scan(info.get("cmds", [])):
            return True
    return False


def emit_command(lines, indent, command, val_to_java, context="activity"):
    """Emit one job command. ``context`` is "activity" or "worker"."""
    kind = command["type"]

    if kind == "job_enqueue":
        data_node = command.get("data_node")
        if data_node is not None and data_node.keys:
            data_var = "_jobData_%s" % command["safe"]
            lines.append(
                f"{indent}androidx.work.Data.Builder {data_var} = "
                "new androidx.work.Data.Builder();"
            )
            for key_node, value_node in zip(data_node.keys, data_node.values):
                lines.append(
                    f"{indent}{data_var}.putString(String.valueOf("
                    f"{val_to_java(key_node)}), String.valueOf({val_to_java(value_node)}));"
                )
            payload = f"{data_var}.build()"
        else:
            payload = "null"
        lines.append(
            f"{indent}ApkpyJobs.enqueue_{command['safe']}"
            f"(getApplicationContext(), {payload});"
        )
        return

    if kind == "job_cancel":
        lines.append(
            f"{indent}ApkpyJobs.cancel(getApplicationContext(), "
            f"\"{command['job']}\");"
        )
        return

    if kind == "job_progress":
        if context != "worker":
            # Progress is reported by the work itself; an Activity has no
            # attempt to report against.
            return
        percent = (
            val_to_java(command["percent_node"])
            if command.get("percent_node") is not None else '"0"'
        )
        message = (
            val_to_java(command["message_node"])
            if command.get("message_node") is not None else '""'
        )
        lines.append(
            f"{indent}_jobProgress(String.valueOf({percent}), "
            f"String.valueOf({message}));"
        )
        return

    if kind == "job_outcome":
        if context != "worker":
            return
        lines.append(f"{indent}_apkpyJobOutcome = \"{command['outcome']}\";")


def emit_observers(lines, indent, observers, class_name):
    """Wire ``job.observe(...)`` to WorkManager's LiveData in ``onCreate``."""
    if not observers:
        return
    lines.append(f"{indent}// ── Observable job progress (WorkManager) ──────────────")
    for observer in observers:
        lines.append(
            f"{indent}androidx.work.WorkManager.getInstance(getApplicationContext())"
        )
        lines.append(
            f"{indent}        .getWorkInfosByTagLiveData(\"{observer['job']}\")"
        )
        lines.append(
            f"{indent}        .observe({class_name}.this, new androidx.lifecycle.Observer"
            "<java.util.List<androidx.work.WorkInfo>>() {"
        )
        lines.append(f"{indent}    @Override")
        lines.append(
            f"{indent}    public void onChanged(java.util.List<androidx.work.WorkInfo> _infos) {{"
        )
        lines.append(
            f"{indent}        pythonCallback_{observer['callback']}(ApkpyJobs.status("
            f"getApplicationContext(), \"{observer['job']}\", _infos));"
        )
        lines.append(f"{indent}    }}")
        lines.append(f"{indent}}});")
    lines.append("")


# ── worker extensions ───────────────────────────────────────────────────────

def worker_fields():
    return [
        "    // Outcome of this attempt: job.retry() / job.fail() set it and the",
        "    // body keeps running, exactly like the Previewer.",
        '    private String _apkpyJobOutcome = "success";',
    ]


def _input_helper():
    return '''
    private String _jobInput(String key) {
        String value = getInputData().getString(key);
        return value == null ? "" : value;
    }
'''.strip("\n").splitlines()


def _progress_helper():
    return '''
    private void _jobProgress(String percent, String message) {
        int value;
        try {
            value = (int) Double.parseDouble(percent);
        } catch (Exception e) {
            value = 0;
        }
        if (value < 0) value = 0;
        if (value > 100) value = 100;
        _apkpyJobMessage = message == null ? "" : message;
        setProgressAsync(new androidx.work.Data.Builder()
                .putInt(ApkpyJobs.PROGRESS, value)
                .putString(ApkpyJobs.MESSAGE, _apkpyJobMessage)
                .build());
    }
'''.strip("\n").splitlines()


def _finish_helper(job_name):
    return ('''
    // What the job said last. WorkManager clears the progress when the work
    // ends, so the Worker leaves its last word where ApkpyJobs.status() reads
    // it -- the same last event the Previewer keeps.
    private String _apkpyJobMessage = "";

    private Result _jobFinish(boolean ok) {
        ApkpyJobs.record(getApplicationContext(), "__JOB__", ok ? "success" : "failed",
                ok ? 100 : 0, _apkpyJobMessage, getRunAttemptCount() + 1);
        return ok ? Result.success() : Result.failure();
    }
'''.replace("__JOB__", job_name).strip("\n").splitlines())


def worker_helpers(body, job=None):
    """Only the helpers this job's body actually calls.

    ``body`` is the Java already generated for ``doWork()``.
    """
    text = "\n".join(body)
    helpers = []
    if job and "_jobFinish(" in text:
        helpers.extend(_finish_helper(job["name"]))
        helpers.append("")
    if "_jobInput(" in text:
        helpers.extend(_input_helper())
        helpers.append("")
    if "_jobProgress(" in text:
        helpers.extend(_progress_helper())
        helpers.append("")
    return helpers[:-1] if helpers else []


def commands_set_outcome(cmds, functions_map=None):
    """True when this job calls job.retry() / job.fail(), directly or through
    one of the functions it invokes.

    Checked on the parsed commands rather than on the generated Java, because
    the outcome field has to be declared before the body is emitted.
    """
    functions_map = functions_map or {}
    seen = set()

    def _scan(commands):
        for command in commands or []:
            if not isinstance(command, dict):
                continue
            if command.get("type") == "job_outcome":
                return True
            name = command.get("callback") or (
                command.get("name") if command.get("type") == "function_call" else None
            )
            if name and name not in seen and name in functions_map:
                seen.add(name)
                if _scan(functions_map[name].get("cmds", [])):
                    return True
            for key in ("true_body", "false_body", "body"):
                if command.get(key) and _scan(command[key]):
                    return True
        return False

    return _scan(cmds)


def worker_return_expression():
    """The value an early ``return`` inside doWork() must produce."""
    return (
        '"retry".equals(_apkpyJobOutcome) ? Result.retry() '
        ': _jobFinish(!"fail".equals(_apkpyJobOutcome))'
    )


def worker_result_lines(indent="        "):
    return [
        f'{indent}if ("retry".equals(_apkpyJobOutcome)) return Result.retry();',
        f'{indent}return _jobFinish(!"fail".equals(_apkpyJobOutcome));',
    ]


# ── ApkpyJobs.java ──────────────────────────────────────────────────────────

_RUNTIME_HEADER = '''package __PACKAGE__;

import android.content.Context;

import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.Data;
import androidx.work.ExistingWorkPolicy;
import androidx.work.ListenableWorker;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkInfo;
import androidx.work.WorkManager;

import org.json.JSONObject;

import java.util.List;
import java.util.concurrent.TimeUnit;

/** Persistent background jobs generated from background_job(...). */
public final class ApkpyJobs {

    public static final String PROGRESS = "__PROGRESS_KEY__";
    public static final String MESSAGE = "__MESSAGE_KEY__";

    private ApkpyJobs() {
    }

    private static void enqueue(Context context, String name,
                                Class<? extends ListenableWorker> worker, Data input,
                                Constraints constraints, BackoffPolicy backoff,
                                long backoffSeconds, boolean unique,
                                ExistingWorkPolicy policy) {
        OneTimeWorkRequest.Builder builder = new OneTimeWorkRequest.Builder(worker)
                .addTag(name)
                .setBackoffCriteria(backoff, backoffSeconds, TimeUnit.SECONDS);
        if (input != null) {
            builder.setInputData(input);
        }
        if (constraints != null) {
            builder.setConstraints(constraints);
        }
        OneTimeWorkRequest request = builder.build();
        WorkManager manager = WorkManager.getInstance(context.getApplicationContext());
        if (unique) {
            manager.enqueueUniqueWork(name, policy, request);
        } else {
            manager.enqueue(request);
        }
    }

    /** Where each job's last word is kept. WorkManager clears a finished
     *  job's progress, and the screen still has to read what it said. */
    static final String EVENTS = "apkpy_jobs";

    /** Drop the queue and abandon anything already running for this job. */
    public static void cancel(Context context, String name) {
        record(context, name, "cancelled", 0, "", 0);
        WorkManager manager = WorkManager.getInstance(context.getApplicationContext());
        manager.cancelUniqueWork(name);
        manager.cancelAllWorkByTag(name);
    }

    /** Keep a job's last event: success/failed from its Worker, cancelled here. */
    static void record(Context context, String name, String state, int progress,
                       String message, int attempt) {
        JSONObject event = new JSONObject();
        try {
            event.put("state", state);
            event.put("progress", progress);
            event.put("message", message == null ? "" : message);
            event.put("attempt", attempt);
        } catch (Exception ignored) {
        }
        // commit(), not apply(): the WorkInfo change that follows wakes the
        // observer, and it has to find this already written.
        context.getApplicationContext().getSharedPreferences(EVENTS, Context.MODE_PRIVATE)
                .edit().putString(name, event.toString()).commit();
    }

    /** The status document of one job, as the screen's observer receives it. */
    public static String status(Context context, String name, List<WorkInfo> infos) {
        String last = context.getApplicationContext()
                .getSharedPreferences(EVENTS, Context.MODE_PRIVATE).getString(name, "");
        return status(infos, last, backoffBase(name), backoffLinear(name));
    }

    // The rule of apkpy_lib/job_rules.status_document, over WorkManager's
    // view: a RUNNING WorkInfo is the running item (its run attempt count is
    // already the 1-based attempt), an ENQUEUED or BLOCKED one is pending with
    // the attempts it has used, and the last event is what finished.
    static String status(List<WorkInfo> infos, String last, long base, boolean linear) {
        int running = 0;
        int pending = 0;
        int retryAttempt = 0;
        int progress = 0;
        int attempt = 0;
        String message = "";
        if (infos != null) {
            for (WorkInfo info : infos) {
                if (info == null) {
                    continue;
                }
                WorkInfo.State state = info.getState();
                if (state == WorkInfo.State.RUNNING) {
                    running++;
                    Data reported = info.getProgress();
                    progress = Math.max(0, Math.min(100, reported.getInt(PROGRESS, 0)));
                    String reportedMessage = reported.getString(MESSAGE);
                    message = reportedMessage == null ? "" : reportedMessage;
                    attempt = Math.max(attempt, info.getRunAttemptCount());
                } else if (state == WorkInfo.State.ENQUEUED
                        || state == WorkInfo.State.BLOCKED) {
                    pending++;
                    retryAttempt = Math.max(retryAttempt, info.getRunAttemptCount());
                }
            }
        }
        String state;
        if (running > 0) {
            state = "running";
        } else if (retryAttempt > 0) {
            state = "retry";
            progress = 0;
            attempt = retryAttempt;
            message = retryMessage(backoffSeconds(linear, base, retryAttempt), retryAttempt);
        } else if (pending > 0) {
            state = "enqueued";
            progress = 0;
            message = "";
            attempt = 0;
        } else {
            JSONObject event = null;
            try {
                event = last == null || last.isEmpty() ? null : new JSONObject(last);
            } catch (Exception ignored) {
            }
            state = event == null ? "idle" : event.optString("state", "idle");
            progress = event == null ? 0 : event.optInt("progress", 0);
            message = event == null ? "" : event.optString("message", "");
            attempt = event == null ? 0 : event.optInt("attempt", 0);
        }
        JSONObject document = new JSONObject();
        try {
            document.put("state", state);
            document.put("progress", progress);
            document.put("message", message);
            document.put("running", running);
            document.put("pending", pending);
            document.put("attempt", attempt);
        } catch (Exception ignored) {
        }
        return document.toString();
    }

    /** WorkManager's own backoff: linear base * n, exponential base * 2^(n-1). */
    static long backoffSeconds(boolean linear, long base, int attempt) {
        int tries = Math.max(1, attempt);
        double delay = linear ? (double) base * tries : (double) base * Math.pow(2, tries - 1);
        return (long) Math.max(10, Math.min(5 * 60 * 60, delay));
    }

    static String retryMessage(long delay, int attempt) {
        return "Retrying in " + delay + " s (attempt " + attempt + ")";
    }
'''


def _constraints_lines(job, indent="        "):
    """Emit a Constraints builder, or None when the job has no constraints."""
    clauses = []
    if job["requires_unmetered"]:
        clauses.append(".setRequiredNetworkType(NetworkType.UNMETERED)")
    elif job["requires_network"]:
        clauses.append(".setRequiredNetworkType(NetworkType.CONNECTED)")
    if job["requires_charging"]:
        clauses.append(".setRequiresCharging(true)")
    if job["requires_battery_not_low"]:
        clauses.append(".setRequiresBatteryNotLow(true)")
    if not clauses:
        return None
    lines = [f"{indent}Constraints constraints = new Constraints.Builder()"]
    for clause in clauses:
        lines.append(f"{indent}        {clause}")
    lines.append(f"{indent}        .build();")
    return lines


def generate_files(package, jobs):
    """Return {"java/ApkpyJobs.java": source} for the declared jobs."""
    if not jobs:
        return {}

    lines = (
        _RUNTIME_HEADER
        .replace("__PACKAGE__", package)
        .replace("__PROGRESS_KEY__", PROGRESS_KEY)
        .replace("__MESSAGE_KEY__", MESSAGE_KEY)
        .splitlines()
    )

    seen = set()
    for job in jobs:
        if job["safe"] in seen:
            continue
        seen.add(job["safe"])
        constraints = _constraints_lines(job)
        lines.append("")
        lines.append(
            "    public static void enqueue_%s(Context context, Data input) {"
            % job["safe"]
        )
        if constraints:
            lines.extend(constraints)
        lines.append(
            '        enqueue(context, "%s", %s.class, input, %s,'
            % (job["name"], job["worker_class"], "constraints" if constraints else "null")
        )
        lines.append(
            "                BackoffPolicy.%s, %dL, %s, ExistingWorkPolicy.%s);"
            % (
                RETRY_POLICIES[job["retry"]],
                job["retry_seconds"],
                "true" if job["unique"] else "false",
                CONFLICT_POLICIES[job["on_conflict"]],
            )
        )
        lines.append("    }")

    # The backoff each job was declared with, for the retry message.
    lines.append("")
    lines.append("    static long backoffBase(String name) {")
    for job in jobs:
        lines.append('        if ("%s".equals(name)) return %dL;' % (job["name"], job["retry_seconds"]))
    lines.append("        return %dL;" % _MIN_BACKOFF_SECONDS)
    lines.append("    }")
    lines.append("")
    lines.append("    static boolean backoffLinear(String name) {")
    for job in jobs:
        if job["retry"] == "linear":
            lines.append('        if ("%s".equals(name)) return true;' % job["name"])
    lines.append("        return false;")
    lines.append("    }")

    lines.append("}")
    return {"java/ApkpyJobs.java": "\n".join(lines)}


__all__ = [
    "COMMAND_TYPES", "initialize", "prescan", "parse_assignment", "parse_command",
    "parse_observe", "is_command_call", "is_observe_call", "value_expression",
    "emit_command", "emit_observers", "commands_use_jobs", "commands_set_outcome",
    "generate_files",
    "worker_class_name", "worker_fields", "worker_helpers",
    "worker_result_lines",
]
