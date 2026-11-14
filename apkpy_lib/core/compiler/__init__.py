"""The Android compiler: an app written with apkpy_lib, read as Python and written as an Android project.

The code is in the modules of this package. Each one only needs the ones listed before it:

    state          What one build knows about the app while it is being written.
    style          CSS as Android has it: colours, sizes, padding, corners, shadows, type.
    resources_xml  The files under res/ that are not layouts: drawables, fonts, icons, menus.
    kinds          What a piece of the source holds, as far as it says: text, a number, a list.
    expressions    A Python expression, written as a Java one.
    statements     A Python statement, written as Java: loops, try, raise, print, appends.
    numeric        Numbers that stay numbers: an int or a float, and the calls the build refuses.
    prescan        The module's own names, read first: globals, constants, functions as values.
    runtime_java   The Java that travels with the app: JSON, values, errors, crypto.
    legacy         The first transpiler, for an app of one screen: the body of a MainActivity.
    manifest       AndroidManifest.xml.
    media_java     The Java of the background audio service and of the sign-in return.
    layout_java    ApkpyLayout.java, the view group for the layouts Android's own do not give.
    rows           virtual_collection(row=...): a row drawn with the app's own components.
    reader         The source, read: screens, components and functions, as commands to write from.
    layout_xml     A screen's layout file.
    audit          What the build says about contrast and labels before the app reaches a phone.
    worker_java    The Java of what runs with the app closed: services and background jobs.
    activity_java  A screen's Activity.
    translate      From the source to every file of the Android project.

``translate_python_to_android`` is the way in. The other names below are the ones the rest of ApkPy and its
tests take from ``apkpy_lib.core.compiler``; everything else is asked of the module that holds it.
"""
from .state import _APP_THEME, _ASSET_BASE_DIR
from .style import (
    _ANDROID_GRAVITY, _THEMED_COLOR_TOKENS, _body_text_size, _column_gravity, _parse_padding,
    _parse_typography_xml, _resolve_color,
)
from .resources_xml import (
    _drawer_item_id, _generate_divider_xml, _generate_drawable_xml, _generate_drawer_item_color_xml,
    _generate_drawer_menu_xml, _generate_font_family_xml, _icon_path_data, _material_icon_path,
    motion,
)
from .kinds import _param_kinds
from .expressions import (
    _HTTPS_READ_TIMEOUT_MS, _MATH_CALLS, _MATH_CONSTANTS, _MATH_INT_CALLS, _https_body_java,
    _https_timeout_java, _json_node_to_java, _list_row_java_literal, _track_json_struct,
)
from .statements import _ERROR_ALIASES, _PY_ERRORS
from .legacy import translate_python_to_java
from .manifest import _generate_manifest, _permission_symbol
from .reader import MultiScreenTranspiler
from .layout_xml import _generate_layout_xml
from .audit import _audit_accessibility
from .translate import _prepare_android_analysis, translate_python_to_android
