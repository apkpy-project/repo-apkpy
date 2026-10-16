# -*- coding: utf-8 -*-
"""What the body of a background job can do -- said once, for both runtimes.

On the phone the body of a ``background_job`` (and of ``service.every`` and
``service.once``) is written into a WorkManager ``Worker``. A Worker has no
screen: it can run with the app closed, after a reboot, with nothing on the
display. The generator for it knew this, and dropped every call it could not
write -- without a word. ``if permissions.has("camera"): ...`` left a
``doWork()`` holding an empty ``try``; the app compiled, installed, ran the job
and did nothing. So did ``note.insert(...)``, ``files.download(...)`` and even
a plain call to one of your own functions.

Dropping was the wrong half of the decision. What a Worker can do, it now
does -- your functions, ``permissions.has()``, the data layer and
``files.download()``, answering before the next line. The calls that cannot
run there stop the build, and the Previewer refuses the same calls with the
same words when a job body reaches them -- otherwise the desk would keep
running code the phone refuses to build.

Two kinds of refusal, because they call for different fixes:

* :data:`SCREEN` -- the call needs a screen that is on display. No
  translation will ever make it work in a Worker; the fix is to move it.
* :data:`NOT_YET` -- the call could run in the background, but ApkPy only
  writes it into screens today. The fix is to do it on a screen for now.

Nothing here imports Tk or anything Android.
"""

import contextlib
import functools
import threading

SCREEN = "J7004"
NOT_YET = "J7005"
CODES = frozenset({SCREEN, NOT_YET})

DOCS = "https://repo-apkpy.pages.dev/background-jobs/"

# ── The families ────────────────────────────────────────────────────────────
#
# family -> (code, why this family cannot run in a job). Both sides refuse by
# family, so the reason a person reads is the same whichever side stopped them.
FAMILIES = {
    "component": (
        SCREEN,
        "A component lives on a screen, and while the job runs that screen "
        "may not exist at all.",
    ),
    "permission_request": (
        SCREEN,
        "Android draws the permission dialog over a screen, and a job has "
        "none to draw it on. Checking with permissions.has() does work "
        "inside a job.",
    ),
    "navigation": (
        SCREEN,
        "Android does not let background work open a screen: it would jump "
        "in front of whatever the person is doing.",
    ),
    "dialog": (
        SCREEN,
        "A dialog is drawn over a screen, and a job has none.",
    ),
    "data_observe": (
        SCREEN,
        "observe() keeps a screen up to date, so it belongs to the screen "
        "that shows the rows.",
    ),
    "audio": (
        SCREEN,
        "Playback belongs to a screen, or to the media service a screen "
        "starts; background work is not allowed to start that service.",
    ),
    "screen_api": (
        SCREEN,
        "This asks the person for something, or draws on the display, and "
        "both need a screen in front of them.",
    ),
    "other": (
        NOT_YET,
        "ApkPy writes the body of a job separately from the screens, and "
        "this call has only been written for screens so far.",
    ),
}

_SUGGESTIONS = {
    SCREEN: (
        "Report from the job with job.progress(percent, message), and show it "
        "on the screen with job.observe(on_change=..., screen=...).",
        "Do the screen work in the function that calls job.enqueue(), before "
        "enqueueing it.",
        "Hand the job what it needs with job.enqueue({...}) and read it "
        "inside with job.input(key).",
    ),
    NOT_YET: (
        "Do it on a screen for now, and hand the job what it needs with "
        "job.enqueue({...}) and job.input(key).",
        "Inside a job, storage, the data layer, files.download(), https, "
        "notifications and your own functions are translated.",
    ),
}

_TITLES = {
    SCREEN: "This call needs a screen, and a background job has none",
    NOT_YET: "This call is not translated inside a background job yet",
}


def refuse(family, what, line=0, path=""):
    """Stop, naming the call. Both runtimes end up here."""
    from .diagnostics import ApkpyError   # a neutral module, like this one

    code, why = FAMILIES.get(family, FAMILIES["other"])
    raise ApkpyError(
        "%s cannot run inside a background job" % what,
        code=code,
        title=_TITLES[code],
        cause=(
            "The body of a background job runs in a WorkManager Worker, which "
            "can run with the app closed and nothing on the display. " + why
        ),
        expected=("storage, the data layer, files.download(), https, "
                  "notifications, permissions.has() and plain Python"),
        received=what,
        suggestions=list(_SUGGESTIONS[code]),
        docs=DOCS,
        line=line,
        path=path,
    )


# ── The compiler's side ─────────────────────────────────────────────────────
#
# command type -> (family, how to say what the person wrote). The templates are
# filled from the command itself, so the refusal reads ``out.set_value()``
# rather than the name of an internal command.
_COMMANDS = {
    "comp_set_value": ("component", "{py_var}.set_value()"),
    "comp_get_value_assign": ("component", "{py_var}.get_value()"),
    "comp_set_items": ("component", "{py_var}.set_items()"),
    "request_permission": ("permission_request", "permissions.request()"),
    "navigate": ("navigation", "on_click_navigate({to_screen_id})"),
    "navigate_back": ("navigation", "back()"),
    "alert": ("dialog", "alert()"),
    "confirm": ("dialog", "confirm()"),
    "snackbar": ("dialog", "snackbar()"),
    "overlay_open": ("dialog", "opening a modal, sheet or menu"),
    "data_observer": ("data_observe", "observe()"),
    "camera_view_control": ("screen_api", "camera_view"),
}

# Families of commands, by prefix, for everything not named above.
_PREFIXES = (
    ("comp_", "component", "{py_var}.{suffix}()"),
    ("video_", "component", "{py_var}.{suffix}()"),
    ("map_", "component", "a map_view method"),
    ("drawer_", "dialog", "the drawer"),
    ("state_", "component", "a state() value"),
    ("audio_", "audio", "audio.{suffix}()"),
    ("sensor_", "screen_api", "sensors.{suffix}()"),
    ("biometrics_", "screen_api", "biometrics.{suffix}()"),
    ("billing_", "screen_api", "billing.{suffix}()"),
    ("gallery_", "screen_api", "gallery.{suffix}()"),
    ("files_pick", "screen_api", "files.pick()"),
    ("scan_", "screen_api", "scan.{suffix}()"),
    ("auth_", "screen_api", "auth.{suffix}()"),
    ("appearance_", "screen_api", "appearance.{suffix}()"),
    ("language_", "screen_api", "language.{suffix}()"),
    ("app_open_store", "screen_api", "app.open_store()"),
    ("apps_", "screen_api", "apps.{suffix}()"),
    ("upload_", "other", "uploads.{suffix}()"),
    ("websocket_", "other", "websocket.{suffix}()"),
    ("push_", "other", "push.{suffix}()"),
    ("location_", "other", "location.{suffix}()"),
    ("route_", "other", "routes.{suffix}()"),
    ("bluetooth_", "other", "bluetooth.{suffix}()"),
    ("ble_", "other", "ble.{suffix}()"),
    ("service_", "other", "service.{suffix}()"),
)


class _Blank(dict):
    """Fill a template without failing on a field the command does not carry."""

    def __missing__(self, key):
        return "..."


def describe_command(command):
    """(family, what the person wrote) for a command the Worker cannot write."""
    kind = str(command.get("type", ""))
    if kind in _COMMANDS:
        family, template = _COMMANDS[kind]
        suffix = ""
    else:
        family, template, suffix = "other", "", ""
        for prefix, prefix_family, prefix_template in _PREFIXES:
            if kind.startswith(prefix):
                family, template = prefix_family, prefix_template
                suffix = kind[len(prefix):]
                break
    if not template:
        template = kind.replace("_", ".", 1) + "()" if kind else "this call"
    if kind == "comp_visibility":
        suffix = "show" if command.get("visible") else "hide"
    fields = _Blank(command)
    fields["suffix"] = suffix or kind
    return family, template.format_map(fields)


def refuse_command(command):
    """The Worker met a command it has no way to write."""
    family, what = describe_command(command)
    refuse(family, what, line=command.get("lineno", 0),
           path=command.get("_apkpy_file", ""))


# ── The Previewer's side ────────────────────────────────────────────────────
#
# On the desk the body really runs, so the refusal happens when it reaches the
# call. A thread-local flag says "this thread is running a job body right now";
# the guarded entry points look at it.
_state = threading.local()


def inside_job():
    return getattr(_state, "depth", 0) > 0


@contextlib.contextmanager
def running_job():
    """Mark this thread as running a job body for the duration."""
    _state.depth = getattr(_state, "depth", 0) + 1
    try:
        yield
    finally:
        _state.depth -= 1


@contextlib.contextmanager
def outside_job():
    """A screen callback reached from inside a job -- an observer, delivered
    on the job's own thread when no interface pump is running. It belongs to
    the screen, so the guard must not see it as part of the body."""
    saved = getattr(_state, "depth", 0)
    _state.depth = 0
    try:
        yield
    finally:
        _state.depth = saved


def guard(family, what):
    """Refuse *what* when it is reached from inside a job body."""
    if inside_job():
        refuse(family, what)


def screen_only(family, what):
    """Decorate a Previewer entry point with :func:`guard`.

    *what* is the text to show, or a function of the call's arguments that
    returns it -- ``ComponentDef`` names the component it was called on.
    """
    def decorate(function):
        @functools.wraps(function)
        def guarded(*args, **kwargs):
            if inside_job():
                refuse(family, what(*args) if callable(what) else what)
            return function(*args, **kwargs)
        guarded._apkpy_job_family = family
        return guarded
    return decorate


def guard_methods(cls, family, names, what):
    """Apply :func:`screen_only` to each named method of *cls*.

    *what* receives the instance and the method name. A method inherited from
    a base class is guarded on *cls* itself, leaving the base untouched.
    """
    for name in names:
        method = getattr(cls, name, None)
        if not callable(method) or getattr(method, "_apkpy_job_family", None):
            continue
        setattr(cls, name, screen_only(
            family, functools.partial(_method_text, what, name))(method))


def _method_text(what, name, instance, *args):
    return what(instance, name)


# ── What the Previewer guards ───────────────────────────────────────────────
#
# (public name, family, verbs). A name is a class (its methods are guarded) or
# one of the API objects (its class is). Only the verbs the phone refuses are
# listed: files.path(), auth.token() or language.get() answer a value and stay
# open, and guarding them would open a divergence the other way round.
#
# The plain functions -- alert(), confirm(), snackbar(), on_click_navigate(),
# back() --
# call guard() in their own body instead, so an import straight from
# apkpy_lib.ui cannot slip past a wrapper.
_COMPONENT_VERBS = (
    "get_value", "set_value", "set_items", "append_items", "prepend_items",
    "update_item", "set_trailing", "set_subtitle", "stream", "stream_item",
    "remove_item", "merge_items", "scroll_to_end", "scroll_to_top",
    "scroll_to_item", "rollback", "commit", "finish_load", "refresh", "show",
    "hide", "set_src", "play", "pause", "stop", "seek", "set_source",
    "set_speed", "set_muted", "set_center", "set_follow_user", "set_location",
    "set_markers", "set_route", "get_route", "set_zoom", "clear_map_cache",
)
PREVIEW_GUARDS = (
    ("ComponentDef", "component", _COMPONENT_VERBS),
    ("ReactiveState", "component", ("set", "increment", "decrement", "toggle")),
    ("OverlayDef", "dialog", ("open", "close")),
    ("DrawerDef", "dialog", ("open", "close")),
    ("ModelDef", "data_observe", ("observe",)),
    ("permissions", "permission_request", ("request",)),
    ("files", "screen_api", ("pick",)),
    ("audio", "audio", (
        "play", "play_background", "play_playlist", "play_saved_playlist",
        "pause", "resume", "stop", "seek", "next", "previous", "shuffle",
        "repeat", "controls", "now_playing", "toggle_like", "like_button",
        "liked_list", "add_to_playlist", "remove_from_playlist",
        "edit_playlist", "delete_playlist", "playlists_list",
        "playlist_editor",
    )),
    ("gallery", "screen_api", ("pick",)),
    ("scan", "screen_api", ("code",)),
    ("biometrics", "screen_api", ("unlock",)),
    ("billing", "screen_api", ("buy", "consume", "owned", "prices",
                               "subscribe")),
    ("auth", "screen_api", ("login", "logout", "user")),
    ("appearance", "screen_api", ("set",)),
    ("language", "screen_api", ("set",)),
    ("app", "screen_api", ("open_store",)),
    ("apps", "screen_api", ("extract", "hash", "list", "permissions")),
    ("sensors", "screen_api", ("accelerometer", "compass", "gyroscope",
                               "light", "pressure", "proximity", "shake",
                               "steps", "stop")),
    ("uploads", "other", ("audio", "cancel", "file", "image", "multipart",
                          "video")),
    ("websocket", "other", ("close", "close_all", "connect", "send")),
    ("push", "other", ("get_token", "listen", "reset", "simulate",
                       "subscribe", "unsubscribe")),
    ("location", "other", ("get_current", "start_background_tracking",
                           "stop", "stop_all", "stop_background_tracking",
                           "watch")),
    ("routes", "other", ("calculate", "cancel", "cancel_all")),
    ("bluetooth", "other", ("connect", "devices", "disconnect", "send")),
    ("ble", "other", ("connect", "disconnect", "scan", "send")),
    ("crash", "other", ("clear",)),
    ("service", "other", ("cancel", "every", "once")),
)


def _preview_text(public_name):
    def text(instance, verb):
        kwargs = getattr(instance, "kwargs", None)
        if isinstance(kwargs, dict):          # a component: name it
            label = kwargs.get("comp_id") or kwargs.get("id") \
                or getattr(instance, "comp_type", "") or "component"
            return "%s.%s()" % (label, verb)
        if public_name == "ModelDef":
            return "%s.%s()" % (getattr(instance, "name", "model"), verb)
        if public_name[:1].isupper():         # any other class
            return "%s()" % verb
        return "%s.%s()" % (public_name, verb)
    return text


def install_preview_guards(*namespaces):
    """Guard every entry in :data:`PREVIEW_GUARDS` found in *namespaces*.

    Called once by ``apkpy_lib/__init__.py``, never in a compiler host.
    Installing twice is harmless: a guarded method is recognised and skipped.
    """
    for public_name, family, verbs in PREVIEW_GUARDS:
        target = None
        for namespace in namespaces:
            if public_name in namespace:
                target = namespace[public_name]
                break
        if target is None:
            continue
        cls = target if isinstance(target, type) else type(target)
        guard_methods(cls, family, verbs, _preview_text(public_name))


def is_refusal(error):
    return getattr(error, "code", "") in CODES


# ── The status a job reports ────────────────────────────────────────────────
#
# ``job.observe()`` hands the screen one document. The two runtimes build it
# from different things -- the Previewer from its own queue, the phone from
# the list of WorkInfo WorkManager keeps -- and they used to disagree: after a
# success the phone said progress 0 and no message, a retry was "enqueued",
# the first attempt was 0, and a failure long ago could outrank the success
# that followed it. So the rule is said here once, from *facts* both sides
# have, and ApkpyJobs.status() is its translation (tests/features/
# test_job_status.py compiles it and asks both the same questions).
#
# The facts:
#   running  -- the item running now: {"progress", "message", "attempt"}
#               (attempt counts from 1), or None.
#   pending  -- for each item waiting to run, how many attempts it has already
#               used: 0 for a fresh one, k for one waiting to retry. The phone
#               reads this as WorkInfo.getRunAttemptCount() of the ENQUEUED.
#   last     -- the last thing that finished: an event from finished() or
#               cancelled(), or None. It outlives the process on both sides.
#   offline  -- the Previewer's own "waiting for the network" (the phone
#               cannot tell a network hold from any other).

MIN_BACKOFF_SECONDS = 10           # WorkManager's own floor
MAX_BACKOFF_SECONDS = 5 * 60 * 60  # and ceiling


def backoff_seconds(policy, base, attempt):
    """How long WorkManager waits after the *attempt*-th failure.

    Its own formula: linear is base * attempt, exponential is
    base * 2^(attempt - 1), both kept between 10 s and 5 h.
    """
    attempt = max(1, int(attempt))
    if policy == "linear":
        delay = int(base) * attempt
    else:
        delay = int(base) * (2 ** (attempt - 1))
    return max(MIN_BACKOFF_SECONDS, min(MAX_BACKOFF_SECONDS, delay))


def retry_message(delay, attempt):
    return "Retrying in %d s (attempt %d)" % (int(delay), int(attempt))


def finished(ok, message, attempt):
    """The event a job leaves behind when its body returns for good."""
    return {"state": "success" if ok else "failed",
            "progress": 100 if ok else 0,
            "message": "" if message is None else str(message),
            "attempt": int(attempt)}


def cancelled():
    return {"state": "cancelled", "progress": 0, "message": "", "attempt": 0}


def status_document(running, pending, last=None, policy="exponential",
                    base=30, offline=False):
    """The status document, from the facts above."""
    pending = [int(item) for item in (pending or ())]
    document = {"running": 1 if running else 0, "pending": len(pending)}
    retries = [item for item in pending if item > 0]
    if running:
        document.update(state="running",
                        progress=max(0, min(100, int(running.get("progress", 0)))),
                        message=str(running.get("message", "")),
                        attempt=int(running.get("attempt", 1)))
    elif pending and offline:
        document.update(state="waiting_network", progress=0,
                        message="Waiting for a network connection",
                        attempt=max(pending))
    elif retries:
        attempt = max(retries)
        document.update(state="retry", progress=0, attempt=attempt,
                        message=retry_message(
                            backoff_seconds(policy, base, attempt), attempt))
    elif pending:
        document.update(state="enqueued", progress=0, message="", attempt=0)
    elif last:
        document.update(state=str(last.get("state", "idle")),
                        progress=int(last.get("progress", 0)),
                        message=str(last.get("message", "")),
                        attempt=int(last.get("attempt", 0)))
    else:
        document.update(state="idle", progress=0, message="", attempt=0)
    order = ("state", "progress", "message", "running", "pending", "attempt")
    return {key: document[key] for key in order}


__all__ = [
    "SCREEN", "NOT_YET", "CODES", "FAMILIES", "PREVIEW_GUARDS", "refuse",
    "describe_command", "refuse_command", "inside_job", "running_job",
    "outside_job", "guard", "screen_only", "guard_methods",
    "install_preview_guards", "is_refusal", "backoff_seconds",
    "retry_message", "finished", "cancelled", "status_document",
]
