"""Core parsers and Android code generators used by ApkPy.

This package deliberately has no Tk dependency.  Android hosts can import the
AppIR protocol without loading the desktop Previewer backend.

The AppIR names are resolved on first use rather than on import.  Importing a
submodule imports its package first, so a plain ``apkpy_lib.core.compiler``
used to drag the whole Studio protocol in behind it -- paid by every CLI run
and every Previewer start, for a module the desktop never touches.
"""

_APP_IR_NAMES = (
    "APP_IR_SCHEMA_VERSION",
    "AppSnapshot",
    "CompileContext",
    "CompileResult",
    "DiagnosticSpec",
    "NativeRequest",
    "NativeResult",
    "NodeSpec",
    "Patch",
    "ScreenSpec",
    "SourceLocation",
    "UiEvent",
    "compile_to_ir",
)

__all__ = list(_APP_IR_NAMES) + ["write_android_project_zip"]


def __getattr__(name):
    if name in _APP_IR_NAMES:
        from . import app_ir
        return getattr(app_ir, name)
    if name == "write_android_project_zip":
        from .android_project import write_android_project_zip
        return write_android_project_zip
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


def __dir__():
    return sorted(__all__)
