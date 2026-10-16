"""Compiler support for ``biometrics.unlock(...)``.

The fingerprint or face check, as one call with one result.

Android draws this dialog itself: ``BiometricPrompt`` is a system surface, and
an app cannot restyle it. That fact shapes the whole feature. What an app *can*
choose is the title, the subtitle and the words on the cancel button, so those
are the whole API -- and they are the whole API on the desktop too, where the
Previewer draws a replica from the same three strings.

What the two runtimes must agree on exactly is the **result vocabulary**. A
scan can fail for seven distinct reasons, and an app that shows "try again" for
a missing sensor is worse than one that says nothing. Both sides resolve those
reasons from :data:`REASONS` here, so neither can invent a word the other does
not know.

``on_result`` receives ``(success, reason)``:

* ``(True, "ok")`` -- identity confirmed;
* ``(False, "<reason>")`` -- one of :data:`REASONS`, never an empty string.

A scan that simply does not match is **not** a result. Android keeps the prompt
open and lets the person try again, so the callback does not fire, and the
Previewer does the same.
"""

from __future__ import annotations

import ast

__all__ = [
    "COMMAND_TYPES", "REASONS", "PERMISSION", "GRADLE_DEPENDENCY",
    "SUCCESS", "DEFAULT_TITLE", "DEFAULT_CANCEL",
    "reason_for_error_code", "reason_for_status_code", "normalise_prompt",
    "is_call", "parse_call", "commands_use_biometrics", "emit_command",
    "callback_interface_java", "activity_runtime_java",
]


COMMAND_TYPES = frozenset({"biometrics_unlock"})

PERMISSION = "USE_BIOMETRIC"
GRADLE_DEPENDENCY = "androidx.biometric:biometric:1.1.0"

SUCCESS = "ok"

DEFAULT_TITLE = "Confirm it's you"
DEFAULT_CANCEL = "Cancel"

# Every word ``on_result`` can receive, and what each one means to a person
# holding the phone. An app should be able to branch on these without reading
# the Android docs.
REASONS = {
    "ok": "Identity confirmed.",
    "cancelled": "The person dismissed the prompt, or pressed the cancel button.",
    "no_hardware": "This device has no biometric sensor at all.",
    "not_enrolled": "There is a sensor, but no fingerprint or face is registered.",
    "unavailable": "The sensor exists and is enrolled, but cannot be used right now.",
    "lockout": "Too many failed attempts. The sensor is temporarily disabled.",
    "failed": "Authentication ended without success for another reason.",
}

# androidx.biometric.BiometricPrompt.ERROR_* -> our vocabulary.
#
# The numbers are the constants' values rather than their names because the
# generated Java compares an int, and writing the mapping twice -- once here
# and once in a switch -- is exactly how the two sides drift apart.
_ERROR_CODES = {
    1: "unavailable",    # ERROR_HW_UNAVAILABLE
    2: "failed",         # ERROR_UNABLE_TO_PROCESS
    3: "cancelled",      # ERROR_TIMEOUT -- the prompt closed on its own
    4: "failed",         # ERROR_NO_SPACE
    5: "cancelled",      # ERROR_CANCELED
    7: "lockout",        # ERROR_LOCKOUT
    8: "failed",         # ERROR_VENDOR
    9: "lockout",        # ERROR_LOCKOUT_PERMANENT
    10: "cancelled",     # ERROR_USER_CANCELED
    11: "not_enrolled",  # ERROR_NO_BIOMETRICS
    12: "no_hardware",   # ERROR_HW_NOT_PRESENT
    13: "cancelled",     # ERROR_NEGATIVE_BUTTON
    14: "not_enrolled",  # ERROR_NO_DEVICE_CREDENTIAL
    15: "unavailable",   # ERROR_SECURITY_UPDATE_REQUIRED
}

# androidx.biometric.BiometricManager.BIOMETRIC_* -> our vocabulary. Asked
# before the prompt is built, so an app on a device with no sensor gets a
# reason instead of a dialog that cannot succeed.
_STATUS_CODES = {
    1: "unavailable",    # BIOMETRIC_ERROR_HW_UNAVAILABLE
    11: "not_enrolled",  # BIOMETRIC_ERROR_NONE_ENROLLED
    12: "no_hardware",   # BIOMETRIC_ERROR_NO_HARDWARE
    15: "unavailable",   # BIOMETRIC_ERROR_SECURITY_UPDATE_REQUIRED
    -1: "unavailable",   # BIOMETRIC_STATUS_UNKNOWN
    -2: "no_hardware",   # BIOMETRIC_ERROR_UNSUPPORTED
}


def reason_for_error_code(code):
    """Map a ``BiometricPrompt.ERROR_*`` value to one of :data:`REASONS`."""
    return _ERROR_CODES.get(int(code), "failed")


def reason_for_status_code(code):
    """Map a ``BiometricManager.canAuthenticate`` value to one of :data:`REASONS`."""
    code = int(code)
    if code == 0:                       # BIOMETRIC_SUCCESS
        return SUCCESS
    return _STATUS_CODES.get(code, "unavailable")


def normalise_prompt(title=None, subtitle=None, cancel_text=None, allow_pin=False):
    """The three strings and the flag, resolved the same way on both runtimes.

    ``allow_pin`` drops the cancel button on purpose. ``PromptInfo.Builder``
    throws if a negative button and ``DEVICE_CREDENTIAL`` are both set, because
    the system supplies its own "Use PIN" affordance in that mode -- so the
    Previewer must not draw one either.
    """
    resolved_title = str(title).strip() if title else ""
    resolved_subtitle = str(subtitle).strip() if subtitle else ""
    resolved_cancel = str(cancel_text).strip() if cancel_text else ""
    return {
        "title": resolved_title or DEFAULT_TITLE,
        "subtitle": resolved_subtitle,
        "cancel_text": "" if allow_pin else (resolved_cancel or DEFAULT_CANCEL),
        "allow_pin": bool(allow_pin),
    }


# --- Parsing ---------------------------------------------------------------

def is_call(call):
    """True for ``biometrics.unlock(...)``."""
    func = getattr(call, "func", None)
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "unlock"
        and isinstance(func.value, ast.Name)
        and func.value.id == "biometrics"
    )


def _literal(transpiler, node, default=None):
    """A keyword's literal value, or ``default`` when it is not a constant."""
    if node is None:
        return default
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        # A module constant (TITLE = "Unlock") is folded here, the same way the
        # rest of the transpiler folds one. Anything else stays at its default:
        # the prompt's words end up in the APK, so they have to be knowable at
        # compile time.
        resolved = getattr(transpiler, "string_constants", {}).get(node.id)
        return default if resolved is None else resolved
    return default


def parse_call(transpiler, call):
    """``biometrics.unlock(...)`` -> the command dict the emitters read."""
    callback = transpiler._kw(call.keywords, "on_result")
    if callback:
        # The first argument is a real boolean on both sides, so `if ok:`
        # compiles to `if (ok)` rather than to a string comparison.
        transpiler.boolean_first_arg_callbacks.add(callback)
    if PERMISSION not in transpiler.declared_permissions:
        transpiler.declared_permissions.append(PERMISSION)

    keywords = call.keywords
    prompt = normalise_prompt(
        title=_literal(transpiler, transpiler._kw_node(keywords, "title")),
        subtitle=_literal(transpiler, transpiler._kw_node(keywords, "subtitle")),
        cancel_text=_literal(transpiler, transpiler._kw_node(keywords, "cancel_text")),
        allow_pin=bool(_literal(
            transpiler, transpiler._kw_node(keywords, "allow_pin"), False)),
    )
    command = {"type": "biometrics_unlock", "callback": callback}
    command.update(prompt)
    return command


def commands_use_biometrics(functions_map, module_init_cmds=None):
    """True when anything in the app asks for the prompt.

    Drives the ``has_biometrics`` gate, so an app that never mentions it emits
    no runtime, no interface and no permission.
    """
    def _uses(cmds):
        for cmd in cmds or []:
            if cmd.get("type") in COMMAND_TYPES:
                return True
        return False

    if _uses(module_init_cmds):
        return True
    for info in (functions_map or {}).values():
        if info and _uses(info.get("cmds", [])):
            return True
    return False


# --- Emission --------------------------------------------------------------

def _java_string(value):
    text = "" if value is None else str(value)
    escaped = (
        text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "")
            .replace("\t", "\\t")
    )
    return '"%s"' % escaped


def emit_command(lines, indent, command, val_to_java=None, functions_map=None):
    """Emit the call for one ``biometrics.unlock(...)``."""
    callback = command.get("callback")
    arguments = ", ".join((
        _java_string(command.get("title") or DEFAULT_TITLE),
        _java_string(command.get("subtitle") or ""),
        _java_string(command.get("cancel_text") or ""),
        "true" if command.get("allow_pin") else "false",
    ))
    if callback:
        lines.append(
            "%s_biometricUnlock(%s, (success, reason) -> pythonCallback_%s(success, reason));"
            % (indent, arguments, callback)
        )
    else:
        lines.append("%s_biometricUnlock(%s, null);" % (indent, arguments))


def callback_interface_java():
    return ("    private interface BiometricResultCallback "
            "{ void onResult(boolean success, String reason); }")


def activity_runtime_java():
    """The whole runtime: status check, prompt, and the two code maps."""
    error_arms = "\n".join(
        '            case %d: return "%s";' % (code, reason)
        for code, reason in sorted(_ERROR_CODES.items())
    )
    status_arms = "\n".join(
        '            case %d: return "%s";' % (code, reason)
        for code, reason in sorted(_STATUS_CODES.items())
    )
    return '''
    // Biometrics. The dialog belongs to the system -- an app chooses the words
    // on it and nothing else -- so everything here is about reporting *why* a
    // check ended, in the same vocabulary the Previewer uses.

    private static String _biometricErrorReason(int code) {
        switch (code) {
%(error_arms)s
            default: return "failed";
        }
    }

    private static String _biometricStatusReason(int code) {
        switch (code) {
            case 0: return "%(success)s";
%(status_arms)s
            default: return "unavailable";
        }
    }

    private void _biometricUnlock(String title, String subtitle, String cancelText,
                                  boolean allowPin, BiometricResultCallback cb) {
        int allowed = allowPin
                ? (androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_WEAK
                   | androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL)
                : androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_WEAK;

        // Ask before building the prompt: a device with no sensor should get a
        // reason it can act on, not a dialog that cannot succeed.
        int status = androidx.biometric.BiometricManager.from(this)
                .canAuthenticate(allowed);
        if (status != androidx.biometric.BiometricManager.BIOMETRIC_SUCCESS) {
            if (cb != null) cb.onResult(false, _biometricStatusReason(status));
            return;
        }

        androidx.biometric.BiometricPrompt.PromptInfo.Builder info =
                new androidx.biometric.BiometricPrompt.PromptInfo.Builder()
                        .setTitle(title);
        if (subtitle != null && subtitle.length() > 0) info.setSubtitle(subtitle);
        info.setAllowedAuthenticators(allowed);
        // setNegativeButtonText and DEVICE_CREDENTIAL cannot both be set: the
        // builder throws. In PIN mode the system draws its own way out.
        if (!allowPin && cancelText != null && cancelText.length() > 0) {
            info.setNegativeButtonText(cancelText);
        }

        androidx.biometric.BiometricPrompt prompt = new androidx.biometric.BiometricPrompt(
                this,
                androidx.core.content.ContextCompat.getMainExecutor(this),
                new androidx.biometric.BiometricPrompt.AuthenticationCallback() {
                    @Override
                    public void onAuthenticationSucceeded(
                            androidx.biometric.BiometricPrompt.AuthenticationResult result) {
                        if (cb != null) cb.onResult(true, "%(success)s");
                    }

                    @Override
                    public void onAuthenticationError(int code, CharSequence message) {
                        if (cb != null) cb.onResult(false, _biometricErrorReason(code));
                    }

                    // onAuthenticationFailed is deliberately not overridden. A
                    // finger that does not match is not an outcome: the prompt
                    // stays open and the person tries again, so firing the
                    // callback here would report a failure the person has not
                    // had yet.
                });
        prompt.authenticate(info.build());
    }
''' % {
        "error_arms": error_arms,
        "status_arms": status_arms,
        "success": SUCCESS,
    }
