# -*- coding: utf-8 -*-
"""Compiler support for ``flashlight`` -- the torch on the back of the phone.

    from apkpy_lib import button, flashlight

    button("Torch", id="torch", screen=home,
           command=lambda: flashlight.toggle())

**No permission.** ``CameraManager.setTorchMode`` is not camera access: the app
never opens a camera device, never receives a frame, and so never asks for
CAMERA. An app whose only camera-shaped feature is the torch keeps a clean
store listing, which is the whole reason this is not built on top of a preview.

**The torch belongs to the phone, not to the app.** Anything can change it --
the person pulling down the quick settings, another app, the camera opening.
So the state is not remembered, it is *watched*: a ``TorchCallback`` follows
the real light and :func:`is_on` reports what is actually lit. An app that
tracked a boolean of its own would say "on" about a torch somebody else had
already put out.

Registering that callback is also how the app learns the state it *starts* in,
and the answer comes back through the callback rather than from the call --
measured at ~34ms on a phone, which is long after ``onCreate`` has finished.
So the first question about the torch waits briefly for that first answer;
without it, a screen asking "is it on?" as it opens would say "off" about a
torch that was already lit. Every question after the first is instant.

**It stays on when you leave.** ``setTorchMode`` is the system torch, and the
system torch does not go out because a screen was closed -- which is right for
a torch and surprising for anything else. It goes out when the app's process
ends, because the camera service drops the torch when its client dies. If an
app wants it out on the way out, it says so: ``flashlight.off()``.

``on_result`` is optional and receives ``(ok, reason)`` -- one of
:data:`REASONS`, never an empty string.
"""

from __future__ import annotations

import ast

__all__ = [
    "COMMAND_TYPES", "REASONS", "OK", "CLASS_NAME", "VERBS", "VALUE_VERBS",
    "reason_for_access_code", "is_call", "is_value_call", "parse_call",
    "commands_use_flashlight", "emit_command", "value_java", "condition_java",
    "shared_class_java", "manifest_features",
]


CLASS_NAME = "ApkpyTorch"

# The three that *do* something, and the two that only answer. Kept apart
# because the first group becomes a statement and the second an expression,
# and a verb in the wrong group is the silent-empty-string bug.
VERBS = ("on", "off", "toggle")
VALUE_VERBS = ("is_on", "available")

COMMAND_TYPES = frozenset({"flashlight_set"})

OK = "ok"

# Every word ``on_result`` can receive, and what each one means to somebody
# holding the phone. Both runtimes read them from here, so neither can invent
# a word the other has never heard of.
REASONS = {
    "ok": "The torch is now in the state that was asked for.",
    "no_flash": "This phone has no flash unit at all.",
    "in_use": "Another app is holding the camera, so the torch cannot change.",
    "disabled": "The camera is switched off by device policy (a managed phone).",
    "unavailable": "The system refused for another reason.",
}

# android.hardware.camera2.CameraAccessException.* -> our vocabulary. The
# numbers are the constants' values rather than their names, because the
# generated Java switches on an int and writing the map twice is how the two
# sides drift.
_ACCESS_CODES = {
    1: "disabled",     # CAMERA_DISABLED -- device policy
    2: "unavailable",  # CAMERA_DISCONNECTED
    3: "unavailable",  # CAMERA_ERROR
    4: "in_use",       # CAMERA_IN_USE
    5: "in_use",       # MAX_CAMERAS_IN_USE
}


def reason_for_access_code(code):
    """Map a ``CameraAccessException`` reason to one of :data:`REASONS`."""
    return _ACCESS_CODES.get(int(code), "unavailable")


# --- Parsing ---------------------------------------------------------------

def _named(call, names):
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and func.attr in names
        and isinstance(func.value, ast.Name)
        and func.value.id == "flashlight"
    )


def is_call(call):
    """True for ``flashlight.on/off/toggle(...)`` -- the verbs that act."""
    return _named(call, VERBS)


def is_value_call(node):
    """True for ``flashlight.is_on()`` / ``flashlight.available()``."""
    return isinstance(node, ast.Call) and _named(node, VALUE_VERBS)


def parse_call(transpiler, call):
    """``flashlight.on()`` and friends -> the command dict the emitters read."""
    callback = transpiler._kw(call.keywords, "on_result")
    if callback:
        # ok is a real boolean on both sides, so `if ok:` compiles to `if (ok)`
        # rather than to a comparison against the text "True".
        transpiler.boolean_first_arg_callbacks.add(callback)
    return {
        "type": "flashlight_set",
        "verb": call.func.attr,
        "callback": callback,
    }


def commands_use_flashlight(functions_map, module_init_cmds=None):
    """True when anything in the app asks the torch to change.

    Drives the ``has_flashlight`` gate, so an app that never mentions it emits
    no shared class, no callback in onCreate and no ``uses-feature``.
    """
    def _uses(cmds):
        for cmd in cmds or []:
            if isinstance(cmd, dict) and cmd.get("type") in COMMAND_TYPES:
                return True
        return False

    if _uses(module_init_cmds):
        return True
    for info in (functions_map or {}).values():
        if info and _uses(info.get("cmds", [])):
            return True
    return False


def reads_flashlight(tree):
    """True when the source ever *asks* about the torch.

    ``is_on()`` and ``available()`` are expressions, so they never become
    commands and ``commands_use_flashlight`` cannot see them. Without this an
    app whose only mention of the torch is ``if flashlight.is_on():`` would
    compile to a call on a class that was never written.
    """
    for node in ast.walk(tree):
        if is_value_call(node):
            return True
    return False


# --- Emission --------------------------------------------------------------

def _context(scope):
    """The Context expression for this scope.

    Both an Activity and a Worker answer ``getApplicationContext()``, and the
    *application* context is the right one on purpose: the watcher outlives
    every screen, and holding an Activity in a static field is a leak.
    """
    return "getApplicationContext()"


def emit_command(lines, indent, command, val_to_java=None, functions_map=None,
                 scope="activity"):
    """Emit one ``flashlight.on/off/toggle(...)``."""
    verb = command.get("verb")
    context = _context(scope)
    if verb == "toggle":
        call = "%s.toggle(%s)" % (CLASS_NAME, context)
    else:
        call = "%s.set(%s, %s)" % (
            CLASS_NAME, context, "true" if verb == "on" else "false")

    callback = command.get("callback")
    if not callback:
        lines.append("%s%s;" % (indent, call))
        return
    # The reason is computed once -- asking twice would ask the camera service
    # twice and could answer differently the second time -- and it is held in a
    # braced block so the name can be the same every time. A name made unique
    # from a hash would change between builds, which is not a property the
    # generated Java should have.
    lines.append("%s{" % indent)
    lines.append("%s    String _torchReason = %s;" % (indent, call))
    lines.append('%s    pythonCallback_%s(_torchReason.equals("%s"), _torchReason);'
                 % (indent, callback, OK))
    lines.append("%s}" % indent)


def value_java(node, scope="activity"):
    """``flashlight.is_on()`` / ``available()`` as a value -- "true"/"false".

    A string, because every value in a generated app is a string. The boolean
    form lives in :func:`condition_java`.
    """
    if not is_value_call(node):
        return None
    return "(%s ? \"True\" : \"False\")" % condition_java(node, scope)


def condition_java(node, scope="activity"):
    """``flashlight.is_on()`` / ``available()`` as a real Java boolean."""
    if not is_value_call(node):
        return None
    method = "isOn" if node.func.attr == "is_on" else "available"
    return "%s.%s(%s)" % (CLASS_NAME, method, _context(scope))


def manifest_features():
    """The ``<uses-feature>`` lines for an app that lights the torch.

    Both are ``required="false"`` deliberately. Declaring the flash is the
    honest description of what the app touches, but requiring it would let the
    Play Store hide the app from every phone without one -- and an app whose
    torch button is one feature among twenty should still install there and
    answer ``no_flash``.

    ``camera.flash`` implies ``camera``, so the implied one is spelled out
    rather than left to inherit a requirement nobody wrote down.
    """
    return [
        '    <uses-feature android:name="android.hardware.camera" '
        'android:required="false" />',
        '    <uses-feature android:name="android.hardware.camera.flash" '
        'android:required="false" />',
    ]


def shared_class_java(package):
    """``ApkpyTorch`` -- one torch per process, watched rather than remembered.

    It is a class of its own rather than a method on an Activity for the same
    reason the Bluetooth link is: a field on one screen dies with that screen,
    and the torch does not. Navigating from one screen to the next must not
    put the light out.
    """
    access_arms = "\n".join(
        '            case %d: return "%s";' % (code, reason)
        for code, reason in sorted(_ACCESS_CODES.items())
    )
    return '''package %(package)s;

import android.content.Context;
import android.hardware.camera2.CameraAccessException;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;

/**
 * flashlight.* -- the torch, which belongs to the phone and not to this app.
 *
 * No permission is involved: setTorchMode is not camera access. The app never
 * opens a camera device, so CAMERA never has to be asked for or declared.
 */
public final class %(klass)s {

    public static final String OK = "%(ok)s";
    public static final String NO_FLASH = "no_flash";
    public static final String UNAVAILABLE = "unavailable";

    // Whether the light is actually lit. Written only by the callback below,
    // which hears about every change including the ones this app did not make.
    private static volatile boolean sOn = false;
    private static boolean sWatching = false;
    private static String sCameraId = null;
    private static boolean sLooked = false;
    private static android.os.Handler sWatchHandler = null;

    // Registering asks Android for the torch's current state, and the answer
    // comes back through the callback rather than from the call -- measured at
    // ~34ms on a phone. onCreate is long over by then, so a screen that asks
    // "is it on?" as it opens would read the field's default and say "off"
    // about a torch that is lit. The first such question waits for the answer;
    // every one after it is already there.
    private static final java.util.concurrent.CountDownLatch sFirstReport =
            new java.util.concurrent.CountDownLatch(1);
    private static volatile boolean sSettled = false;
    private static final long FIRST_REPORT_MS = 300;

    private %(klass)s() { }

    private static CameraManager manager(Context context) {
        if (context == null) return null;
        try {
            return (CameraManager) context.getApplicationContext()
                    .getSystemService(Context.CAMERA_SERVICE);
        } catch (Throwable t) {
            return null;
        }
    }

    /**
     * The id of the camera that carries a flash unit, or null.
     *
     * The back one wins. A front-facing "flash" is the screen going white,
     * which is not a torch and would be a surprise pointed at somebody's face.
     * Looked up once: the camera list does not change while the app runs.
     */
    private static synchronized String cameraId(Context context) {
        if (sLooked) return sCameraId;
        CameraManager cm = manager(context);
        if (cm == null) return null;
        sLooked = true;
        try {
            String fallback = null;
            for (String id : cm.getCameraIdList()) {
                CameraCharacteristics traits = cm.getCameraCharacteristics(id);
                Boolean hasFlash = traits.get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                if (hasFlash == null || !hasFlash) continue;
                Integer facing = traits.get(CameraCharacteristics.LENS_FACING);
                if (facing != null && facing == CameraCharacteristics.LENS_FACING_BACK) {
                    sCameraId = id;
                    return sCameraId;
                }
                if (fallback == null) fallback = id;
            }
            sCameraId = fallback;
        } catch (Throwable t) {
            sCameraId = null;
        }
        return sCameraId;
    }

    /**
     * Start following the real torch. Registering asks Android for the current
     * state of every torch it knows about; the answer arrives through the
     * callback a moment later.
     *
     * The callback runs on a thread of its own, NOT on the main thread. That
     * is what makes the wait in isOn() possible: a main-thread handler could
     * never deliver while the main thread was waiting for it.
     */
    public static synchronized void watch(final Context context) {
        if (sWatching) return;
        CameraManager cm = manager(context);
        if (cm == null) return;
        final Context app = context.getApplicationContext();
        try {
            if (sWatchHandler == null) {
                android.os.HandlerThread thread =
                        new android.os.HandlerThread("ApkpyTorch");
                thread.start();
                sWatchHandler = new android.os.Handler(thread.getLooper());
            }
            cm.registerTorchCallback(new CameraManager.TorchCallback() {
                @Override
                public void onTorchModeChanged(String cameraId, boolean enabled) {
                    String ours = cameraId(app);
                    if (ours == null || ours.equals(cameraId)) {
                        sOn = enabled;
                        sFirstReport.countDown();
                    }
                }

                @Override
                public void onTorchModeUnavailable(String cameraId) {
                    // The camera was taken by something else. The light is out
                    // whether or not this app asked for that.
                    String ours = cameraId(app);
                    if (ours == null || ours.equals(cameraId)) {
                        sOn = false;
                        sFirstReport.countDown();
                    }
                }
            }, sWatchHandler);
            sWatching = true;
        } catch (Throwable t) {
            // Never registered, so sOn stays whatever set() last managed. That
            // is worse than the callback and better than crashing.
            sSettled = true;
        }
    }

    /**
     * Wait, once and briefly, for Android's first word on the torch.
     *
     * Deliberately not synchronized: watch() holds the class monitor and the
     * callback needs it too, so waiting inside it would deadlock the very
     * answer being waited for.
     */
    private static void settle(Context context) {
        if (sSettled) return;
        sSettled = true;
        // Nothing will ever report about a phone with no flash unit, so there
        // is nothing to wait for.
        if (cameraId(context) == null) return;
        try {
            sFirstReport.await(FIRST_REPORT_MS,
                               java.util.concurrent.TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static String reasonFor(int code) {
        switch (code) {
%(access_arms)s
            default: return UNAVAILABLE;
        }
    }

    /** Does this phone have a torch at all? */
    public static boolean available(Context context) {
        if (context == null) return false;
        try {
            if (!context.getApplicationContext().getPackageManager()
                    .hasSystemFeature(
                        android.content.pm.PackageManager.FEATURE_CAMERA_FLASH)) {
                return false;
            }
        } catch (Throwable t) {
            return false;
        }
        return cameraId(context) != null;
    }

    /** Is the light on right now -- including when somebody else lit it? */
    public static boolean isOn(Context context) {
        watch(context);
        settle(context);
        return sOn;
    }

    /** Turn it on or off. Answers OK, or the word for why not. */
    public static String set(Context context, boolean on) {
        CameraManager cm = manager(context);
        if (cm == null) return UNAVAILABLE;
        String id = cameraId(context);
        if (id == null) return NO_FLASH;
        watch(context);
        // Setting a state we are about to overwrite needs no wait.
        sSettled = true;
        try {
            cm.setTorchMode(id, on);
            // The callback will confirm this, but not before this method
            // returns -- and a toggle right after an on must not undo itself.
            sOn = on;
            return OK;
        } catch (CameraAccessException e) {
            return reasonFor(e.getReason());
        } catch (Throwable t) {
            return UNAVAILABLE;
        }
    }

    /**
     * The other way round from whatever it is now.
     *
     * Through isOn() on purpose: a toggle that trusted a state nobody had
     * confirmed would turn an already-lit torch on again, and the person would
     * press the button and see nothing happen.
     */
    public static String toggle(Context context) {
        return set(context, !isOn(context));
    }
}
''' % {
        "package": package,
        "klass": CLASS_NAME,
        "ok": OK,
        "access_arms": access_arms,
    }
