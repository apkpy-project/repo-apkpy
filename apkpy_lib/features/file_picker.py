"""Pick any file, and ``upload_button`` -- desktop Previewer runtime.

Mirrors what ``apkpy_lib.core.features.file_picker`` generates for Android:

* the same ``types=`` vocabulary, resolved by the same shared normaliser, so
  the two runtimes can never disagree about what ``"pdf"`` means;
* the same result contract ``(success, path, name, size, mime)``, with the same
  cancellation tuple ``(False, "", "", "0", "")``;
* ``upload_button`` builds an ordinary ``button`` so themes, variants and icons
  behave identically.

``path`` is a real filesystem path here and a ``content://`` Uri on Android, so
it is documented as an opaque handle: read ``name``/``size``/``mime`` instead of
parsing it.
"""

from __future__ import annotations

import mimetypes
import os

from ..core.features.file_picker import normalise_types

__all__ = ["pick", "upload_button"]

# Matches the Android side, where a cancelled pick reports "0" rather than an
# empty string, so application code can convert it without a guard.
_CANCELLED = (False, "", "", "0", "")


def _describe(path):
    """Return ``(path, name, size, mime)`` for a chosen local file."""
    absolute = os.path.abspath(path)
    name = os.path.basename(absolute)
    try:
        size = str(os.path.getsize(absolute))
    except OSError:
        size = "0"
    # Android reports "" when the provider does not know the type; keeping the
    # same honesty here means uploads.multipart still substitutes
    # application/octet-stream at send time, on both runtimes.
    mime = mimetypes.guess_type(name)[0] or ""
    return absolute, name, size, mime


def pick(on_result=None, types=None, title="Choose a file"):
    """Open the desktop file dialog and report the chosen file.

    ``on_result`` receives ``(success, path, name, size, mime)``.
    """
    _, filetypes = normalise_types(types)
    try:
        from tkinter import filedialog

        selected = filedialog.askopenfilename(title=title, filetypes=filetypes)
    except Exception:
        selected = ""
    if not on_result:
        return selected or ""
    if not selected:
        on_result(*_CANCELLED)
        return ""
    path, name, size, mime = _describe(selected)
    on_result(True, path, name, size, mime)
    return path


def upload_button(text="Upload", url="", types=None, task_id=None, field="file",
                  fields=None, headers=None, content_type=None, on_file=None,
                  on_cancel=None, on_progress=None, on_result=None, id=None,
                  screen=None, parent=None, variant=None, icon=None,
                  title="Choose a file"):
    """A button that picks a file and uploads it.

    Sugar over ``files.pick`` + ``uploads.file``: identical behaviour, one call.
    Drop to the two primitives when the upload has to be conditional -- for
    example rejecting a file above a size limit.
    """
    from ..ui import button as _button, uploads as _uploads

    # A stable task id makes a second tap restart the upload rather than race a
    # duplicate, and makes uploads.cancel(...) usable.
    task = str(task_id or id or text or "upload")

    def _run():
        def _chosen(success, path, name, size, mime):
            if not success:
                if on_cancel:
                    on_cancel()
                return
            if on_file:
                on_file(path, name, size, mime)
            _uploads.multipart(
                task, url, path, field=field, fields=fields, headers=headers,
                content_type=content_type, on_progress=on_progress,
                on_result=on_result,
            )

        pick(on_result=_chosen, types=types, title=title)

    return _button(
        text, command=_run, id=id, screen=screen, parent=parent,
        variant=variant, icon=icon,
    )
