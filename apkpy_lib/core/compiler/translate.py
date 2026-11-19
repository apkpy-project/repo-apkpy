"""From the source to every file of the Android project."""
import ast
import os
import re

from ..features import push as push_feature
from ..features import gradient_drawable as gradient_feature
from ..gradients import gradient_of as _gradient_of
from ..gradients import layers_of as _gradient_layers_of
from ..features import pager as pager_feature
from ..features import chart as chart_feature
from ..features import choice as choice_feature
from ... import choice_rules as _choice_rules
from ..features import field as field_feature
from ..features import shimmer as shimmer_feature
from ..features import web_page as web_page_feature
from ..features import draw_pad as draw_pad_feature
from ..features import keyboard as keyboard_feature
from ..features import code_editor as code_editor_feature
from ... import field_rules as _field_rules
from ..features import sheet as sheet_feature
from ..features import zoom as zoom_feature
from ..features import gestures as gestures_feature
from ..features import maps as maps_feature
from ..features import location_background as location_background_feature
from ..features import rich_content as rich_content_feature
from ..features import data as data_feature
from ..features import jobs as jobs_feature
from ..features import module_flow as module_flow_feature
from ..features import progress as progress_feature
from ..features import bluetooth as bluetooth_feature
from ..features import native as native_feature
from .. import dead_methods
from ..features import native_python as native_python_feature
from ..features import kit as kit_feature
from ..features import nfc as nfc_feature
from ..features import contacts as contacts_feature
from ..features import ble as ble_feature
from ..features import billing as billing_feature
from ..features import flashlight as flashlight_feature
from ..features import font_weight as font_weight_feature
from ..features import pending_views as pending_views_feature
from ..features import wallpaper as wallpaper_feature
from ..features import sensors as sensors_feature
from ..features import regex as regex_feature
from ..features import modules as modules_feature
from ..features import ui_functions as ui_functions_feature
from ..features import lambda_defaults as lambda_defaults_feature
from ..features import call_defaults as call_defaults_feature
from ..features import shared_containers as shared_containers_feature
from ..features import unpacking as unpacking_feature
from ..features import loop_else as loop_else_feature
from ..features import tuples as tuples_feature
from ..features import comprehensions as comprehensions_feature
from ..features import sort_key as sort_key_feature
from ..features import json_module as json_feature
from ..features import nested_functions as nested_feature
from ..features import errors as errors_feature
from ..features import basics as basics_feature
from ..features import auth_oidc as auth_oidc_feature
from ..features import item_assignment as item_feature
from ..features import classes as classes_feature
from ..features import signatures as signatures_feature
from ..features import module_constants as module_constants_feature
from ..features import java_names as java_names_feature
from ..features import sets as sets_feature
from ..features import counters as counters_feature
from ..features import function_values as function_values_feature
from ..features import use_before_def as use_before_def_feature
from ..features import notifications as notifications_feature
from ..features import camera as camera_feature
from ..features import camera_view as camera_view_feature
from ..style_parser import (
    parse_css, report_hex_order, report_unknown_arguments, report_unknown_properties,
)
from ...layout_engine import is_advanced_container
from ... import motion
from ... import theme as _theme
from ...theme import nav_look as _nav_look
from ...theme import (
    mini_player_colors, _mix_color, apply_theme, component_style, has_responsive_styles, _length_px,
    divider_spec, theme_from_ast,
)
from ...diagnostics import ApkpyError, format_exception
from .. import ast_compat
from .. import i18n as i18n_feature
from ..features import crash as crash_feature
from ..features import scan as scan_feature
from ..features import pinning as pinning_feature
from ..features import accessibility as accessibility_feature

from .state import (
    _APP_THEME, _ASSET_BASE_DIR, _BODY_KEYS, _BOUND_NAMES, _ELSEWHERE_EMPTY, _FIXED_NUMBER_LISTS,
    _FN_TARGETS, _GLOBALS, _I18N, _IMPORTED_NAMES, _KIND_RETURNS, _MODULE_KINDS, _MODULE_LISTS,
    _MODULE_STRUCT_TEXT, _MUTATED_LISTS, _NUMBERISH_NAMES, _NUMERIC_CONSTS, _NUMERIC_CONST_TEXT,
    _NUMERIC_RETURNS, _PARAM_KINDS, _PENDING_TARGETS, _RAW_LOOP_VARS, _SCREEN_GRADIENTS,
    _SHEET_LAYOUTS, _SINGLETON_CONSTS, _STATE_NAMES, _TRANSPILE_FONTS, _USES_CODE_EDITOR,
    _USES_CRASH, _USES_FLASHLIGHT, _USES_GRADIENT, _USES_SCAN, _USES_SENSORS, _USES_SHIMMER,
    _VIEW_COMPS, _VIEW_OWNERS, _WARM_WEB,
)
from .style import (
    _INVALID_ALIGNS_REPORTED, _INVALID_COLORS_REPORTED, _INVALID_TRANSFORMS_REPORTED,
    _THEMED_COLOR_TOKENS, _android_drawable_name, _app_bar_colors, _color_xml,
    _get_flex_orientation, _get_style_bg, _get_style_border_color, _get_style_fg,
    _get_style_focus_border_color, _get_style_pressed_color, _open_shadow_clipping,
    _parse_border_width, _parse_padding, _parse_radii, _parse_radius, _resolve_color,
)
from .resources_xml import (
    _UNKNOWN_ICONS_REPORTED, _emit_font_resources, _generate_anim_xml, _generate_app_bar_menu_xml,
    _generate_bottom_nav_menu_xml, _generate_bottom_nav_vector, _generate_button_icon_vector,
    _generate_divider_xml, _generate_drawable_xml, _generate_drawer_header_xml,
    _generate_drawer_item_background_xml, _generate_drawer_item_color_xml,
    _generate_drawer_item_style_xml, _generate_drawer_menu_xml, _generate_state_icon_vector,
    _safe_android_id, _validate_font_registry, _wrap_layout_in_drawer,
)
from .kinds import (
    _fixed_number_lists, _module_kinds, _module_struct_text, _param_kinds, _return_kinds,
)
from .statements import (
    _ITEM_COUNT, _ITEM_SHARED_JAVA, _ITEM_STACK, _cmds_contain_transition, _fn_cmds, _lines_json,
    _refuse_missing_service_function, _take_line_marks,
)
from .numeric import (
    _Unstar, _line_up_keywords, _numeric_body_names, _refuse_matmul, _refuse_mixed_params,
    _refuse_number_keys_read_back, _spread_boolean_first,
)
from .prescan import (
    _bound_names, _functions_used_as_values, _imported_names, _module_singletons, _prescan_globals,
)
from .runtime_java import _generate_reactive_state_java, _generate_values_java
from .manifest import _generate_manifest
from .media_java import _generate_auth_activity_java, _generate_media_service_java
from .layout_java import _generate_apkpy_layout_java
from .rows import _every_comp, _row_components
from .reader import MultiScreenTranspiler
from .layout_xml import _generate_layout_xml, _generate_list_row_xml, _screen_overlay_comps
from .audit import _audit_accessibility
from .worker_java import _generate_worker_java
from .activity_java import _generate_activity_java


def _report_unknown_call_arguments(tree):
    """Warn about keyword arguments the components do not take.

    The Previewer gets this for free -- Python raises TypeError on the call --
    so the hole only opens for someone who goes straight to ``apkpy build``.
    Walking the tree here rather than inside the visitor keeps it independent
    of which call forms the visitor happens to recognise: a component the
    generator ignores still gets its arguments checked.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        names = [kw.arg for kw in node.keywords if kw.arg]
        if names:
            report_unknown_arguments(
                node.func.id, names, getattr(node, 'lineno', 0),
            )


def _install_analysis_globals(analysis):
    """Point the module-level compilation state at ``analysis``.

    Three values reach the generators through module globals rather than
    arguments: the declared theme, the folder assets are resolved against and
    the font registry.  ``_prepare_android_analysis`` sets them, so a backend
    that reuses a prepared analysis has to set them too -- otherwise it
    generates one project's layout with whatever the *previous* compilation in
    this process left behind.  A Studio session with two projects open would
    build the first one with the second one's theme and artwork.
    """
    _APP_THEME[0] = analysis["declared_theme"]
    _ASSET_BASE_DIR[0] = analysis["asset_base_dir"]
    _TRANSPILE_FONTS[0] = analysis["transpiler"].fonts


def _prepare_android_analysis(python_code, source_name="writehere.py",
                              project_root=None):
    """Parse one ApkPy source file into the shared Android analysis model.

    This is deliberately separate from file generation.  ApkPy Studio consumes
    the same ``MultiScreenTranspiler`` result through AppIR, while the existing
    desktop compiler continues to turn it into Java/XML.  Keeping the parser,
    theme application, feature prescans and validation in one place prevents a
    mobile preview from accepting source which the final APK would reject.

    The returned mapping is internal: values such as the AST and transpiler are
    not JSON serializable.  ``apkpy_lib.core.app_ir`` is responsible for
    publishing the stable, JSON-safe representation.
    """
    # These registries used to be reset inside translate_python_to_android.
    # They are still per-compilation, but now every backend enters through this
    # function instead of maintaining its own subtly different reset list.
    _UNKNOWN_ICONS_REPORTED.clear()
    _INVALID_COLORS_REPORTED.clear()
    _INVALID_TRANSFORMS_REPORTED.clear()
    _INVALID_ALIGNS_REPORTED.clear()
    _TRANSPILE_FONTS[0] = None
    # A host that keeps the source somewhere other than the project -- Studio
    # writes the editor buffer to a cache file -- says where the artwork lives
    # with ``project_root``.  Without it the base folder is the source's own,
    # which is the desktop case.
    asset_base_dir = os.path.abspath(
        project_root if project_root else os.path.dirname(
            os.path.abspath(source_name))
    )
    _ASSET_BASE_DIR[0] = asset_base_dir
    _USES_GRADIENT[0] = False
    _USES_CODE_EDITOR[0] = False
    _USES_SHIMMER[0] = False
    _SCREEN_GRADIENTS[0] = {}

    style_match = re.search(
        r'style\s*=\s*"""(.*?)"""', python_code, re.DOTALL,
    )
    styles = {}
    keyframes = {}
    clean_code = python_code
    if style_match:
        styles, keyframes = parse_css(style_match.group(1))
        report_unknown_properties(styles, keyframes)
        report_hex_order(style_match.group(1))
        # CSS is not Python, but diagnostics must still point at the original
        # application's line numbers after this block is removed.
        clean_code = python_code.replace(
            style_match.group(0), "\n" * style_match.group(0).count("\n"), 1)

    tree = ast_compat.parse(clean_code, filename=source_name)
    # command=save above def save(): NameError in the Previewer and in any
    # Python, while the Java was written all the same. Stopped first (E1201).
    tree = use_before_def_feature.check(tree, source_name)
    # Helper modules sitting next to the application are spliced in here, so
    # every pass below still receives one module.
    tree = modules_feature.merge(tree, asset_base_dir)
    # default = "x", R = 6371, org = ...: a Java keyword, or a name the
    # generated Java uses itself (R.id, org.json). Renamed to default_ before
    # anything reads the module; javac stopped on them.
    tree = java_names_feature.rename(tree)
    _refuse_matmul(tree)
    # [*xs, 3], (*xs, 3), {*q}: the joined list they are, written out.
    tree = _Unstar().visit(tree)
    # progress(40) is chart(kind="progress", value=40), as in the Previewer:
    # from here on it is read as a chart.
    progress_feature.expand(tree)
    # A @native function written in Python becomes the native.java() block it
    # translates to, before anything else reads the module: from here on it
    # is a block like the ones written in Java.
    tree = native_python_feature.rewrite(tree, source_name)
    # haptics.tap(), speech.say(), browser.open() and the rest of the calls
    # that reach the phone: each becomes a call to a native block declared
    # here, so everything below reads them as it reads an app's own blocks.
    tree = kit_feature.rewrite(tree)
    # import json: one spelling (json.loads, json.dumps), calls with their
    # arguments written out worked out now by CPython's json, the rest refused
    # with a reason. What is left the generators translate (_json_module_java).
    tree = json_feature.desugar(tree)
    # N = len(NAMES), SQUARES = [i * i for i in range(5)] at the top of the
    # file: worked out now, with the same Python, into the literal Python
    # makes when the app starts. They used to vanish, and javac stopped on
    # the name that was never declared.
    tree = module_constants_feature.fold(tree)
    # l2 = l1 then l2.reverse(), def add(x, tags=[]), add(CART, "tea") with
    # cart.append() in add: one object under two names in CPython, two values
    # on the phone. Stopped here, on the code as it was written.
    tree = shared_containers_feature.check(tree)
    # set(), {1, 2}, s.add(x), a | b, a <= b, str(s): a set is kept as the
    # list of its items, in CPython's order; what only a set does becomes
    # _apkpy_set_* calls (features/sets.py). After the check above, which
    # reads s.add() as a change.
    tree = sets_feature.rewrite(tree)
    # Counter(words), defaultdict(list): the dict they are, with c[k] read as
    # c.get(k, 0), d[k] given its default on the line before, most_common()
    # and str() as _apkpy_counter_* calls (features/counters.py).
    tree = counters_feature.rewrite(tree)
    _refuse_number_keys_read_back(tree)
    # sorted(rows, key=lambda r: r["score"]), rows.sort(key=len), max(d, key=d.get):
    # the keys become a comprehension the passes below translate, and the
    # compiler orders the items by them. Before the classes, so obj.price in
    # a key is read like the field of any item of a list.
    tree = sort_key_feature.desugar(tree)
    # class Task: ... -- methods as functions of the module, objects in the
    # app's object store (ApkpyObjects), obj.x as reads and writes of it.
    # Before the passes below, which then read plain functions.
    # f(*items), cart.add(**options): named as written, before the classes
    # become functions of the module.
    signatures_feature.refuse_spread(tree)
    tree = classes_feature.desugar(tree)
    # def f(a, /, b, *, c=1): one plain list of parameters, as a Java method
    # has. Used *args / **kwargs and f(*items) stop here, at their line.
    tree = signatures_feature.normalise(tree)
    # A function that builds UI is a template: each module-level call is
    # replaced by its body, so the passes below read the module the
    # person would have written by hand -- what Python does when the
    # Previewer runs the function.
    tree = ui_functions_feature.expand(tree)
    # `lambda t=target: ...` keeps each turn's value, as in Python: the
    # default is written into the body now that the loop has been unrolled.
    tree = lambda_defaults_feature.bind(tree)
    # def inner(): inside a function, and name = lambda ...: moved out to the
    # module, with the outer names they read as arguments. Before the
    # defaults below, which then fill the moved functions' calls too.
    tree = nested_feature.desugar(tree)
    # f = double, [double, inc], apply(double, 3), f(x): a function as a
    # value is its name, and a call of a value goes through _apkpyCall.
    tree = function_values_feature.rewrite(tree)
    _FN_TARGETS[0] = function_values_feature.targets(tree)
    # try ... else becomes a flag, raise X from Y raises X.
    tree = errors_feature.desugar(tree)
    # for ... else / while ... else: a flag that each break of the loop
    # clears. Before the unpacking, which rewrites loops of its own.
    tree = loop_else_feature.desugar(tree)
    # q, r = divmod(a, b) as a // b and a % b; pow(a, b) as a ** b; assert
    # as an if that raises AssertionError. Before the unpacking, which would
    # otherwise read q and r out of a pair, as text.
    tree = basics_feature.desugar(tree)
    # greet("Ana") for def greet(name, greeting="Hello"): Java has no default
    # values, so each call is written out in full, keywords in their places.
    tree = call_defaults_feature.fill(tree)
    # [x.upper() for x in xs if x], {k: v for ...}, any(...), all(...): the
    # loops they stand for, before the unpacking below (for k, v in ...).
    tree = comprehensions_feature.desugar(tree)
    # pair = (1, 2): read as the list it is kept as, shown as (1, 2) by
    # str(), and refused where CPython refuses a change to it. Before the
    # unpacking, which reads the same names.
    tree = tuples_feature.mark(tree)
    # a, b = parts / for k, v in d.items() / enumerate / zip / a, b = b, a:
    # rewritten as the assignments and loops below already translate.
    tree = unpacking_feature.desugar(tree)
    # d["k"] = v, lista[i] = v, d["k"] += 1, del lista[0]: the name gets the
    # changed JSON; a list or dict of the module is read as `global`.
    tree = item_feature.desugar(tree)
    tree, regex_plan = regex_feature.prepare(tree)
    wallpaper_feature.validate_and_assets(tree, asset_base_dir)
    camera_feature.validate_callbacks(tree)
    nfc_feature.validate(tree)
    contacts_feature.validate(tree)
    camera_view_feature.validate_callbacks(tree)
    _report_unknown_call_arguments(tree)
    declared_theme = theme_from_ast(tree)
    _APP_THEME[0] = declared_theme
    styles = apply_theme(styles, declared_theme)
    transpiler = MultiScreenTranspiler(styles=styles)
    # A command inside a row= passes the row's item to a function that takes
    # one, and nothing to one that takes none.
    transpiler.function_arity = {
        node.name: len(node.args.args) for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)}
    jobs_feature.prescan(transpiler, tree)
    # native.java()/gradle()/manifest()/keep(): declared at module level and
    # called from a screen above the declaration, like a background job.
    native_feature.prescan(transpiler, tree)
    _MUTATED_LISTS[0] = {}   # o registo e por transpilacao, nao global
    _VIEW_OWNERS[0] = {}
    _PENDING_TARGETS[0] = {}
    _VIEW_COMPS[0] = {}
    _MODULE_LISTS[0] = {}
    _MODULE_STRUCT_TEXT[0] = {}
    _MODULE_KINDS[0] = {}
    _GLOBALS[0] = {}
    _KIND_RETURNS[0] = {}
    _PARAM_KINDS[0] = {}
    _FIXED_NUMBER_LISTS[0] = {}
    _NUMBERISH_NAMES[0] = set()
    _RAW_LOOP_VARS[0] = {}
    _ITEM_STACK[0] = []
    _ITEM_SHARED_JAVA[0] = {}
    _ITEM_COUNT[0] = 0
    _SINGLETON_CONSTS[0] = _module_singletons(tree)
    _IMPORTED_NAMES[0] = _imported_names(tree)
    _BOUND_NAMES[0] = _bound_names(tree)
    _STATE_NAMES[0] = set()
    _ELSEWHERE_EMPTY[0] = set()
    _I18N[0] = {'table': {}, 'default': ''}
    _USES_CRASH[0] = crash_feature.uses_crash(tree)
    _USES_SCAN[0] = scan_feature.uses_scan(tree)
    _USES_FLASHLIGHT[0] = flashlight_feature.reads_flashlight(tree)
    _USES_SENSORS[0] = sensors_feature.reads_sensors(tree)
    transpiler.prescan_pins(tree)
    transpiler.prescan_translations(tree)
    transpiler.prescan_drawer(tree)
    transpiler.prescan_overlays(tree)
    transpiler.prescan_mutated_lists(tree)
    transpiler.prescan_numeric_args(tree)
    transpiler.prescan_own_names(tree)
    transpiler.field_targets = field_feature.prescan(tree)
    transpiler.uses_zoom = zoom_feature.uses(tree)
    draw_pad_feature.prescan(tree)
    keyboard_feature.prescan(tree)
    _NUMERIC_CONSTS[0] = dict(transpiler.numeric_constants)
    _NUMERIC_CONST_TEXT[0] = dict(transpiler.numeric_constant_text)
    _NUMERIC_RETURNS[0] = dict(getattr(transpiler, 'numeric_returns', {}) or {})
    _GLOBALS[0] = _prescan_globals(
        tree, _numeric_body_names(tree), _NUMERIC_RETURNS[0],
        getattr(transpiler, 'numeric_params', {}))
    _NUMERIC_CONSTS[0].update(
        {name: kind for name, (_, kind) in _GLOBALS[0].items() if kind is not None})
    transpiler.value_called = _functions_used_as_values(tree)
    module_flow_feature.refuse_rebound_reads(tree)
    module_flow_feature.refuse_mixed_storage_reads(tree)
    transpiler.visit(tree)
    _STATE_NAMES[0] = set(getattr(transpiler, 'reactive_states', {}) or {})
    gestures_feature.mark_reorder_positions(transpiler)
    choice_feature.mark_list_params(transpiler)
    sheet_feature.apply_default_styles(transpiler.overlays, styles)
    zoom_feature.package_item_pictures(transpiler)
    # command=back, with no call and no lambda: every command= keeps a
    # function's name, so back() becomes a function of its own -- only when
    # the app names it and has no back of its own, so nothing else changes.
    _back_callers = {
        id(node.func) for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    if ('back' not in transpiler.own_function_names
            and 'back' not in transpiler.functions
            and any(isinstance(node, ast.Name) and node.id == 'back'
                    and isinstance(node.ctx, ast.Load) and id(node) not in _back_callers
                    for node in ast.walk(tree))):
        transpiler.functions['back'] = {
            'args': [], 'cmds': [{'type': 'navigate_back'}],
            'string_args': set(), 'returns_value': False,
        }
    # Um booleano entregue a outra funcao continua booleano: feito depois do
    # visit, quando os corpos ja estao lidos e as chamadas sao conhecidas.
    # `f(b=2, a=1)` volta a ser `f(a, b)`: as keywords eram deitadas fora e a
    # chamada saia sem argumento nenhum.
    _line_up_keywords(transpiler)
    _spread_boolean_first(transpiler)
    _MODULE_LISTS[0] = dict(getattr(transpiler, 'list_assignments', {}) or {})
    _MODULE_KINDS[0] = _module_kinds(transpiler, tree)
    _KIND_RETURNS[0] = _return_kinds(tree)
    _PARAM_KINDS[0] = _param_kinds(tree)
    _refuse_mixed_params(tree)
    if _PARAM_KINDS[0]:
        _KIND_RETURNS[0] = _return_kinds(tree)
        for _name, _kinds in _PARAM_KINDS[0].items():
            if _name in transpiler.functions:
                transpiler.functions[_name]['param_kinds'] = dict(_kinds)
    _FIXED_NUMBER_LISTS[0] = _fixed_number_lists(tree)
    _MODULE_STRUCT_TEXT[0] = _module_struct_text(
        tree,
        skip=(set(transpiler.mutated_lists) | set(transpiler.string_constants)
              | set(transpiler.numeric_constant_text)))
    _validate_font_registry(transpiler.fonts, asset_base_dir)
    _TRANSPILE_FONTS[0] = transpiler.fonts

    analysis = {
        "source": python_code,
        "source_name": source_name,
        "clean_source": clean_code,
        "regex_plan": regex_plan,
        "tree": tree,
        "styles": styles,
        "keyframes": keyframes,
        "declared_theme": declared_theme,
        "asset_base_dir": asset_base_dir,
        "transpiler": transpiler,
    }
    _install_analysis_globals(analysis)
    return analysis


def _keep_app_files_xml(output_files):
    """res/raw/apkpy_app_keep.xml: every picture and sound of the app's own
    that went into res/, kept by a release build.

    `apkpy release` shrinks resources, and the shrinker keeps only what the
    code names. A picture named in the app's data -- {"art": "art/cover.jpg"}
    in a list a row shows -- is found by name while the app runs, which the
    shrinker cannot follow: the signed Afterglow showed a row without its
    cover, where the debug build showed it (18-11-2026). Only files ApkPy
    copied from the app are listed: the rest it writes can still go."""
    kept = set()
    for name, value in output_files.items():
        if not (isinstance(value, tuple) and value and value[0] == "COPY_FILE"):
            continue
        parts = name.split("/")
        if len(parts) != 3 or parts[0] != "res":
            continue
        kind = parts[1].split("-")[0]
        if kind not in ("drawable", "raw", "mipmap"):
            continue
        kept.add("@%s/%s" % (kind, os.path.splitext(parts[2])[0].split(".")[0]))
    if not kept:
        return None
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<resources xmlns:tools="http://schemas.android.com/tools"\n'
            '    tools:keep="%s" />\n' % ",".join(sorted(kept)))


def translate_python_to_android(python_code, package="com.apkpy.app",
                                source_name="writehere.py", *,
                                project_root=None, _analysis=None):
    """
    Analisa código Python com múltiplos Screens e devolve um dicionário
    com todos os ficheiros gerados:

        {
          "java/Screen_loginActivity.java":     "...",
          "java/Screen_dashboardActivity.java": "...",
          "res/layout/activity_screen_login.xml": "...",
          "res/layout/activity_screen_dashboard.xml": "...",
          "res/anim/my_anim.xml": "...",
          "AndroidManifest.xml": "...",
        }

    Retorna None se não encontrar nenhum Screen no código.
    """
    try:
        # ``_analysis`` is an internal bridge for AppIR.  It lets the Studio
        # preview and the Java/XML backend consume the exact same compiler
        # pass instead of parsing a slightly different copy of the source.
        # Public callers continue to use the original three-argument API.
        if _analysis is None:
            analysis = _prepare_android_analysis(
                python_code, source_name, project_root,
            )
        else:
            # A prepared analysis carries the theme, the asset folder and the
            # fonts, but the generators read those from module globals which
            # still hold whatever compiled last in this process.
            analysis = _analysis
            _install_analysis_globals(analysis)
        tree = analysis["tree"]
        styles = analysis["styles"]
        keyframes = analysis["keyframes"]
        _declared_theme = analysis["declared_theme"]
        transpiler = analysis["transpiler"]

        if not transpiler.screens:
            return None  # sem Screens → modo legado

        screen_ids      = list(transpiler.screens.values())
        start_screen_id = transpiler.start_screen_id or screen_ids[0]
        output_files    = {}
        _notifications_enabled = notifications_feature.used(tree)
        _camera_enabled = camera_feature.used(tree) or camera_view_feature.used(tree)
        _nfc_enabled = nfc_feature.commands_use_nfc(transpiler.functions, transpiler.module_init_cmds)
        _contacts_enabled = contacts_feature.used(tree)
        if _contacts_enabled:
            output_files["java/ApkpyContacts.java"] = contacts_feature.shared_class_java(package)
        if _nfc_enabled:
            output_files["java/ApkpyNfc.java"] = nfc_feature.shared_class_java(package)
        if _camera_enabled:
            output_files.update(camera_feature.files(package))
        if camera_view_feature.used(tree):
            output_files.update(camera_view_feature.files(package))
        if _notifications_enabled:
            if "POST_NOTIFICATIONS" not in transpiler.declared_permissions:
                transpiler.declared_permissions.append("POST_NOTIFICATIONS")
            output_files.update(notifications_feature.files(
                tree, transpiler, package, analysis["asset_base_dir"], _generate_button_icon_vector))
        if analysis.get("regex_plan") and analysis["regex_plan"].patterns:
            output_files["java/ApkpyRegex.java"] = analysis["regex_plan"].java(package)
        if wallpaper_feature.uses_wallpaper(tree):
            output_files["java/ApkpyWallpaper.java"] = wallpaper_feature.shared_class_java(package)
            output_files.update(wallpaper_feature.validate_and_assets(tree, analysis["asset_base_dir"]))
        if transpiler.data_models and not transpiler.data_schema:
            _first_model = next(iter(transpiler.data_models.values()))
            raise ApkpyError(
                "db.model() declarations require one db.schema() declaration",
                code="C4003",
                line=_first_model.get("line", 0),
                received="%d model(s) declared, 0 schemas" % len(transpiler.data_models),
            )
        output_files.update(
            data_feature.generate_files(
                transpiler.data_schema, package, transpiler.data_observers,
            )
        )
        # As listas de modulo mutadas usam o mesmo armazem: uma so' por
        # processo, que e' o que a palavra "modulo" quer dizer em Python.
        # O handler de falhas vive fora dos ecras: um campo numa Activity morre
        # com ela, e o processo continua vivo depois de ela desaparecer.
        if _USES_CRASH[0]:
            output_files["java/ApkpyCrashHandler.java"] = (
                crash_feature.shared_class_java(package)
            )
        if transpiler.reactive_states or _MUTATED_LISTS[0] or _GLOBALS[0]:
            output_files["java/ApkpyReactiveState.java"] = (
                _generate_reactive_state_java(package)
            )
        output_files["java/ApkpyValues.java"] = _generate_values_java(package)
        if classes_feature.STATE['used']:
            output_files["java/ApkpyObjects.java"] = classes_feature.objects_java(package)
        # The Bluetooth link belongs to the app, not to a screen: a field on
        # one Activity dies with it, and a static would be per-class.
        if bluetooth_feature.commands_use_bluetooth(
                transpiler.functions, transpiler.module_init_cmds):
            output_files["java/ApkpyBluetooth.java"] = (
                bluetooth_feature.shared_class_java(package)
            )
        if ble_feature.commands_use_ble(
                transpiler.functions, transpiler.module_init_cmds):
            output_files["java/ApkpyBle.java"] = (
                ble_feature.shared_class_java(package)
            )
        if billing_feature.commands_use_billing(
                transpiler.functions, transpiler.module_init_cmds):
            output_files["java/ApkpyBilling.java"] = (
                billing_feature.shared_class_java(package)
            )
        # The torch outlives every screen: it belongs to the phone. A field on
        # one Activity would go out when that Activity did.
        # Asking about the light counts as using it: an app whose only mention
        # is `if flashlight.is_on():` still needs the class to ask.
        _uses_flashlight = bool(
            flashlight_feature.commands_use_flashlight(
                transpiler.functions, transpiler.module_init_cmds)
            or _USES_FLASHLIGHT[0]
        )
        if _uses_flashlight:
            output_files["java/ApkpyTorch.java"] = (
                flashlight_feature.shared_class_java(package)
            )

        # Every screen watches its window for bold the phone's font forgets.
        output_files["java/ApkpyWeight.java"] = (
            font_weight_feature.shared_class_java(package)
        )

        # The classes behind haptics, speech, browser and the other calls to
        # the phone -- only the ones this app uses.
        output_files.update(kit_feature.shared_files(package))

        # Which sensors the app actually watches, for the manifest. An app
        # that only shakes should not tell the store it wants a step counter.
        _sensors_in_app = sensors_feature.sensors_used(
            transpiler.functions, transpiler.module_init_cmds)

        def _uses_advanced_layout(items, viewport):
            for item in items:
                if item.get('comp_type') == 'container':
                    own_style = component_style(
                        styles, 'container', item.get('id'), viewport=viewport
                    )
                    children = item.get('children', [])
                    child_styles = [
                        component_style(
                            styles, child.get('comp_type'), child.get('id'),
                            variant=(child.get('variant')
                                     if child.get('comp_type') in ('button', 'label', 'card')
                                     else None),
                            viewport=viewport,
                        )
                        for child in children
                    ]
                    if is_advanced_container(
                        own_style, child_styles, responsive=bool(item.get('responsive'))
                    ):
                        return True
                if _uses_advanced_layout(item.get('children', []), viewport):
                    return True
            return False

        layout_viewports = ((411, 914), (914, 411), (800, 1100), (1100, 800))
        needs_advanced_layout = any(
            _uses_advanced_layout(
                transpiler.screen_components.get(sid, []), layout_viewport
            ) or _screen_overlay_comps(
                transpiler.screen_components.get(sid, []), styles, layout_viewport
            )
            for sid in screen_ids for layout_viewport in layout_viewports
        )
        if needs_advanced_layout:
            output_files["java/ApkpyLayout.java"] = _generate_apkpy_layout_java(package)

        def _has_pager(comps):
            return any(c.get('_pager') or _has_pager(c.get('children', [])) for c in comps)
        if any(_has_pager(transpiler.screen_components.get(sid, [])) for sid in screen_ids):
            output_files["java/ApkpyPager.java"] = pager_feature.generate_java(package)
        def _has_chart(comps):
            return any(c.get('comp_type') == 'chart' or _has_chart(c.get('children', []))
                       for c in comps)
        if any(_has_chart(transpiler.screen_components.get(sid, [])) for sid in screen_ids):
            output_files["java/ApkpyChart.java"] = chart_feature.generate_java(package)
        if any(web_page_feature.uses(transpiler.screen_components.get(sid, []))
               for sid in screen_ids):
            output_files[web_page_feature.JAVA_FILE] = web_page_feature.java_source(package)
        if any(draw_pad_feature.uses(transpiler.screen_components.get(sid, []))
               for sid in screen_ids):
            output_files[draw_pad_feature.JAVA_FILE] = draw_pad_feature.java_source(package)
            # save() names its file as files.write() does.
            from ..features.kit import java_source as _kit_java_source
            output_files["java/ApkpyKitRules.java"] = _kit_java_source("ApkpyKitRules", package)
        if any(choice_feature.uses_choice(transpiler.screen_components.get(sid, []))
               for sid in screen_ids):
            output_files["java/ApkpyChoice.java"] = choice_feature.java_source(package)
        if any(field_feature.uses_field(transpiler.screen_components.get(sid, []))
               for sid in screen_ids):
            output_files["java/ApkpyField.java"] = field_feature.java_source(package)
        if getattr(transpiler, 'uses_zoom', False):
            output_files["java/ApkpyZoom.java"] = zoom_feature.java_source(package)
        def _has_gestures(comps):
            return any(gestures_feature.uses_gestures(c) or _has_gestures(c.get('children', []))
                       for c in comps)
        if any(_has_gestures(transpiler.screen_components.get(sid, [])) for sid in screen_ids):
            output_files["java/ApkpyGestures.java"] = gestures_feature.java_source(package)
        
        # Gerar ficheiros de animação XML
        # Screen transitions. Emitted only for the kinds actually used, so an
        # app that never asks for one gains no res/anim at all.
        _used_transitions = set()
        for _cmds in [transpiler.module_init_cmds] + [
                _fn_cmds(_b) for _b in transpiler.functions.values()]:
            for _kind in ('slide', 'slide_up'):
                if _cmds_contain_transition(_cmds, _kind):
                    _used_transitions.add(_kind)
        # ``screen.on_click_navigate(button=, to=, transition=)`` does not
        # become a command inside a function -- it is a navigation entry -- so
        # scanning only the function bodies left the generated Java pointing at
        # R.anim resources that were never written.
        for _nav in transpiler.navigations:
            if _nav.get('transition') in ('slide', 'slide_up'):
                _used_transitions.add(_nav['transition'])
        _slide_ms = motion.duration('screen', styles.get('__theme__', {}).get('motion'))
        for _kind in sorted(_used_transitions):
            _axis = 'X' if _kind == 'slide' else 'Y'
            output_files[f"res/anim/apkpy_{_kind}_enter.xml"] = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<set xmlns:android="http://schemas.android.com/apk/res/android"\n'
                f'    android:interpolator="{motion.android_interpolator()}">\n'
                f'    <translate android:from{_axis}Delta="100%" android:to{_axis}Delta="0%"\n'
                f'        android:duration="{_slide_ms}" />\n'
                '</set>\n'
            )
            output_files[f"res/anim/apkpy_{_kind}_exit.xml"] = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<set xmlns:android="http://schemas.android.com/apk/res/android"\n'
                f'    android:interpolator="{motion.android_interpolator()}">\n'
                f'    <translate android:from{_axis}Delta="0%" android:to{_axis}Delta="-30%"\n'
                f'        android:duration="{_slide_ms}" />\n'
                '</set>\n'
            )

        for anim_name, frames in keyframes.items():
            safe_name = anim_name.lower().replace('-', '_')
            output_files[f"res/anim/{safe_name}.xml"] = _generate_anim_xml(frames)

        # ── Background services (service.every → androidx.work.Worker) ────────
        resolved_services = []
        for svc in transpiler.background_services:
            f_name = svc['function_name']
            f_info = transpiler.functions.get(f_name)
            if not f_info:
                _refuse_missing_service_function(svc, 'every')
            safe_id = re.sub(r'[^A-Za-z0-9_]', '_', svc['id'])
            if safe_id and safe_id[0].isdigit():
                safe_id = f"_{safe_id}"
            worker_class = f"{safe_id[:1].upper()}{safe_id[1:]}Worker"
            resolved_services.append({**svc, 'worker_class': worker_class})

            output_files[f"java/{worker_class}.java"] = _generate_worker_java(
                worker_class, f_info['cmds'], package,
                string_constants=transpiler.string_constants,
                functions_map=transpiler.functions,
                boolean_first_arg_callbacks=transpiler.boolean_first_arg_callbacks,
            )

        # ── One-time services (service.once → androidx.work.OneTimeWorkRequest) ──
        resolved_onetime = {}
        for svc in transpiler.onetime_services:
            f_name = svc['function_name']
            f_info = transpiler.functions.get(f_name)
            if not f_info:
                _refuse_missing_service_function(svc, 'once')
            safe_id = re.sub(r'[^A-Za-z0-9_]', '_', svc['id'])
            if safe_id and safe_id[0].isdigit():
                safe_id = f"_{safe_id}"
            worker_class = f"{safe_id[:1].upper()}{safe_id[1:]}Worker"
            resolved_onetime[svc['id']] = {**svc, 'worker_class': worker_class}

            output_files[f"java/{worker_class}.java"] = _generate_worker_java(
                worker_class, f_info['cmds'], package,
                string_constants=transpiler.string_constants,
                functions_map=transpiler.functions,
                boolean_first_arg_callbacks=transpiler.boolean_first_arg_callbacks,
            )

        # ── Persistent jobs (background_job → WorkManager OneTimeWorkRequest) ──
        _declared_jobs = list(transpiler.background_jobs.values())
        _job_vars = set(transpiler.background_jobs.keys())
        _emitted_jobs = []
        for _job in _declared_jobs:
            _run = transpiler.functions.get(_job['run'])
            if not _run:
                _known = ", ".join(sorted(transpiler.functions)) or "none"
                raise ApkpyError(
                    'background_job("%s", run=%s) - the function %s() was not '
                    'found in this file.' % (_job['name'], _job['run'], _job['run']),
                    code="J7002",
                    line=_job.get("line", 0),
                    received="run=%s" % _job['run'],
                    expected="a module-level def %s(): in this file" % _job['run'],
                )
            if any(item['name'] == _job['name'] for item in _emitted_jobs):
                continue
            _emitted_jobs.append(_job)
            output_files[f"java/{_job['worker_class']}.java"] = _generate_worker_java(
                _job['worker_class'], _run['cmds'], package,
                string_constants=transpiler.string_constants,
                functions_map=transpiler.functions,
                job=_job, job_vars=_job_vars,
                boolean_first_arg_callbacks=transpiler.boolean_first_arg_callbacks,
            )
        output_files.update(jobs_feature.generate_files(package, _emitted_jobs))

        def _register_screen_drawable(name, content, screen_id):
            # Android resources belong to the whole APK, not to one Activity.
            # Per-screen counters (or normalized IDs) can name different shapes
            # alike. Reuse identical resources; never overwrite a different one.
            base = name
            scope = re.sub(r'[^a-z0-9_]', '_', str(screen_id).lower())
            suffix = 0
            while (f"res/drawable/{name}.xml" in output_files
                   and output_files[f"res/drawable/{name}.xml"] != content):
                suffix += 1
                name = f"apkpy_{scope}_{base}_{suffix}"
            output_files[f"res/drawable/{name}.xml"] = content
            return name

        # A component changed from another screen reaches it through a
        # box the owning screen empties when it comes to the front.
        _VIEW_OWNERS[0], _PENDING_TARGETS[0] = pending_views_feature.plan(
            transpiler.screen_components, transpiler.functions,
            transpiler.module_init_cmds)
        _VIEW_COMPS[0] = pending_views_feature.components_by_name(
            transpiler.screen_components)
        if _PENDING_TARGETS[0]:
            output_files["java/ApkpyPending.java"] = (
                pending_views_feature.shared_class_java(package))

        for sid in screen_ids:
            components = transpiler.screen_components.get(sid, [])
            _shape_counter = [0]
            _icon_counter = [0]

            def _assign_state_drawables(comp, ctype, comp_id):
                """``answer:selected { ... }``: a drawable and a text colour
                for each state the stylesheet gives this id."""
                prefix = str(comp_id) + ':'
                states = sorted({str(k)[len(prefix):] for k in styles
                                 if isinstance(k, str) and k.startswith(prefix)
                                 and re.match(r'^[A-Za-z_][\w-]*$', str(k)[len(prefix):])})
                for state in states:
                    full = component_style(styles, ctype, comp_id, row_variant=state)
                    own = component_style(styles, ctype, comp_id, include_body=False,
                                          row_variant=state)
                    if ctype == 'label':
                        fg = _get_style_fg(own)
                        if fg:
                            comp.setdefault('_state_text', {})[state] = str(_resolve_color(fg))
                    bg = _get_style_bg(own)
                    bc = _get_style_border_color(full)
                    bw = _parse_border_width(full)
                    grad = _gradient_of(own)
                    radii = _parse_radii(full)
                    if not (bg or (bc and bw) or grad):
                        continue
                    pd = _parse_padding(full)
                    safe = re.sub(r'[^a-z0-9_]', '_', (str(comp_id) + '_' + state).lower())
                    if grad:
                        _USES_GRADIENT[0] = True
                        xml = gradient_feature.drawable_xml(package, gradient_feature.spec(
                            grad, lambda c: str(_resolve_color(c)), base=bg, radii=radii,
                            border=(bw, bc) if bc else None, padding=pd))
                    else:
                        xml = _generate_drawable_xml(
                            _resolve_color(bg) if bg else '#00000000', radii,
                            border_color=bc, border_width=bw, padding=pd)
                    comp.setdefault('_state_drawables', {})[state] = _register_screen_drawable(
                        safe + '_state_shape', xml, sid)

            def _assign_drawables(comp_list):
                for comp in comp_list:
                    comp_id = comp.get('id')
                    ctype = comp.get('comp_type')
                    if (ctype in ('button', 'inputs', 'input_field',
                                 'container', 'list_row', 'label')
                            and not comp.get('card_actions')):
                        s = component_style(
                            styles, ctype, comp_id,
                            variant=comp.get('variant') if ctype == 'button' else None,
                        )
                        radius = _parse_radius(s)
                        bg = _get_style_bg(s)
                        # Um label tem de usar o SEU fundo, nunca o herdado:
                        # a cascata dobra o `body` em todos os componentes, por
                        # isso sem isto cada rotulo passava a pintar o fundo da
                        # pagina por cima do cartao ou da linha onde esta'.
                        if ctype in ('container', 'card', 'label'):
                            # The page colour is the page's. The cascade folds
                            # ``body`` into every component, so once a
                            # container stopped carrying its own surface every
                            # grouping began painting the screen background
                            # over whatever it sat on. A box with nothing of
                            # its own is transparent.
                            bg = _get_style_bg(component_style(
                                styles, ctype, comp_id, include_body=False,
                                variant=(comp.get('variant')
                                         if ctype == 'card' else None),
                            ))
                        bc = _get_style_border_color(s)
                        bw = _parse_border_width(s)
                        pc = _get_style_pressed_color(s)
                        # Gera o drawable quando há radius, COR DE FUNDO, borda ou
                        # pressed-color — não só quando há radius. Senão um botão com
                        # background-color sem border-radius caía no botão cinzento
                        # default do Android (a cor de fundo não era aplicada).
                        # A transparent row wants the framework ripple, not a
                        # flat drawable that would swallow it -- the group it
                        # sits in already owns the shape.
                        if ctype == 'list_row' and not radius and (
                                not bg or _resolve_color(bg).lower().startswith(
                                    ('#00', 'transparent'))):
                            bg = None
                        # A gradient is the component's own, never body's
                        # (that one is the screen's).
                        _grad = _gradient_of(component_style(
                            styles, ctype, comp_id, include_body=False,
                            variant=comp.get('variant') if ctype in ('button', 'card') else None))
                        if radius > 0 or bg or pc or (bc and bw) or _grad:
                            _shape_counter[0] += 1
                            color = _resolve_color(bg) if bg else '#00000000'
                            fc = _get_style_focus_border_color(s)
                            pd = _parse_padding(s)
                            base = re.sub(r'[^a-z0-9_]', '_', str(comp_id or ctype).lower())
                            drawable_name = (f"{base}_shape" if comp_id else
                                             f"{base}_{_shape_counter[0]}_shape")
                            _grad_spec = gradient_feature.spec(
                                _grad, lambda c: str(_resolve_color(c)), base=bg,
                                radii=_parse_radii(s), border=(bw, bc) if bc else None,
                                padding=pd) if _grad else None
                            _grad_layers = _gradient_layers_of(component_style(
                                styles, ctype, comp_id, include_body=False,
                                variant=comp.get('variant') if ctype in ('button', 'card') else None))
                            if _grad_spec and len(_grad_layers) > 1 and ctype != 'button':
                                _USES_GRADIENT[0] = True
                                _layer_names = []
                                for _i, _sp in enumerate(gradient_feature.layer_specs(
                                        _grad_layers, lambda c: str(_resolve_color(c)), base=bg,
                                        radii=_parse_radii(s), border=(bw, bc) if bc else None,
                                        padding=pd)):
                                    _layer_names.append(_register_screen_drawable(
                                        '%s_l%d' % (drawable_name[:-len('_shape')], _i),
                                        gradient_feature.drawable_xml(package, _sp), sid))
                                drawable_xml = gradient_feature.layer_list_xml(_layer_names)
                            elif _grad_spec:
                                _USES_GRADIENT[0] = True
                                drawable_xml = gradient_feature.drawable_xml(
                                    package, _grad_spec,
                                    ripple=(_color_xml(pc) if pc else
                                            gradient_feature.default_ripple(_grad, _resolve_color)
                                            if ctype == 'button' else None))
                            else:
                                drawable_xml = _generate_drawable_xml(
                                    color, _parse_radii(s), border_color=bc, border_width=bw,
                                    pressed_color=pc, focus_color=fc, padding=pd
                                )
                            comp['_drawable'] = _register_screen_drawable(
                                drawable_name, drawable_xml, sid)
                            if field_feature.boxed(comp):
                                # What the field wears while it shows an error.
                                _wrong = _field_rules.colors(styles.get('__theme__', {}))['error']
                                comp['_error_drawable'] = _register_screen_drawable(
                                    drawable_name[:-len('_shape')] + '_error_shape',
                                    _generate_drawable_xml(
                                        color, _parse_radii(s), border_color=_wrong,
                                        border_width=_field_rules.stroke(bw),
                                        focus_color=_wrong, padding=pd),
                                    sid)
                        if comp_id and ctype in ('container', 'label'):
                            _assign_state_drawables(comp, ctype, comp_id)
                        if ctype == 'list_row':
                            safe_sid = re.sub(r'[^a-z0-9_]', '_', str(sid).lower())
                            for key, attr, color_key in (
                                ('icon', '_icon_drawable', 'icon-color'),
                                ('trailing_icon', '_trailing_icon_drawable',
                                 'trailing-color'),
                            ):
                                if not comp.get(key):
                                    continue
                                _icon_counter[0] += 1
                                icon_name = (
                                    f"ic_row_{safe_sid}_{_icon_counter[0]}"
                                )
                                comp[attr] = icon_name
                                output_files[f"res/drawable/{icon_name}.xml"] = (
                                    _generate_button_icon_vector(
                                        comp[key],
                                        s.get(color_key)
                                        or s.get('tint')
                                        or _get_style_fg(s)
                                        or '#212121',
                                    )
                                )
                        divider = divider_spec(s) if ctype == 'container' else None
                        if divider:
                            _shape_counter[0] += 1
                            base = re.sub(r'[^a-z0-9_]', '_',
                                          str(comp_id or 'group').lower())
                            drawable_name = (
                                f"{base}_{_shape_counter[0]}_divider"
                            )
                            comp['_divider_drawable'] = _register_screen_drawable(
                                drawable_name, _generate_divider_xml(
                                    divider, _get_flex_orientation(s) == 'horizontal'), sid)
                        if ctype == 'container' and comp.get('_tab') and comp.get('_tab_icon'):
                            _icon_counter[0] += 1
                            safe_sid = re.sub(r'[^a-z0-9_]', '_', str(sid).lower())
                            tab_icon_name = f"ic_tab_{safe_sid}_{_icon_counter[0]}"
                            comp['_tab_drawable'] = tab_icon_name
                            # White: the strip tints it, active or not.
                            output_files[f"res/drawable/{tab_icon_name}.xml"] = (
                                _generate_button_icon_vector(comp['_tab_icon'], '#FFFFFF'))
                        if ctype == 'button' and comp.get('icon'):
                            _icon_counter[0] += 1
                            safe_sid = re.sub(r'[^a-z0-9_]', '_', str(sid).lower())
                            icon_name = f"ic_btn_{safe_sid}_{_icon_counter[0]}"
                            comp['_icon_drawable'] = icon_name
                            _icon_colour = (s.get('icon-color') or s.get('tint')
                                            or _get_style_fg(s) or '#212121')
                            output_files[f"res/drawable/{icon_name}.xml"] = _generate_button_icon_vector(
                                comp['icon'],
                                # The same order list_row has always used.
                                _icon_colour
                            )
                            if comp.get('active') is not None:
                                # A row's active="{field}": the lit state, in the
                                # same active-color the Previewer paints.
                                comp['_active_icon_drawable'] = f"{icon_name}_active"
                                output_files[f"res/drawable/{icon_name}_active.xml"] = (
                                    _generate_button_icon_vector(
                                        comp.get('active_icon') or comp['icon'],
                                        s.get('active-color')
                                        or (styles.get('__theme__', {}) or {}).get('primary')
                                        or '#1DB954'))
                            _like_var = (transpiler.audio_like or {}).get('button')
                            # An icon and no words, or variant="icon" (which
                            # draws the icon alone whatever the text says).
                            _icon_only = (not str(comp.get('text') or '').strip()
                                          or comp.get('variant') == 'icon')
                            if (_like_var and _icon_only
                                    and _like_var == comp.get('_py_var')):
                                _lit = (s.get('active-color') or '#1DB954')
                                comp['_like_icons'] = {}
                                for _state, (_glyph, _colour) in {
                                        'liked': ('favorite', _lit),
                                        'unliked': ('favorite_border', _icon_colour)}.items():
                                    _drawable = f"{icon_name}_{_state}"
                                    output_files[f"res/drawable/{_drawable}.xml"] = (
                                        _generate_button_icon_vector(_glyph, _colour))
                                    comp['_like_icons'][_state] = _drawable
                            _ac_role = next((role for role, var in (transpiler.audio_controls or {}).items()
                                             if role in ('play_pause', 'shuffle', 'repeat')
                                             and var and var == comp.get('_py_var')), None)
                            if _ac_role and _icon_only:
                                # An icon button bound to audio.controls: its other
                                # states, as vectors, for the Activity to swap in.
                                _lit = (s.get('active-color')
                                        or (styles.get('__theme__', {}) or {}).get('primary')
                                        or '#1DB954')
                                _states = {
                                    'play_pause': {'play': ('play_arrow', _icon_colour),
                                                   'pause': ('pause', _icon_colour)},
                                    'shuffle': {'off': ('shuffle', _icon_colour),
                                                'on': ('shuffle', _lit)},
                                    'repeat': {'off': ('repeat', _icon_colour),
                                               'all': ('repeat', _lit),
                                               'one': ('repeat_one', _lit)},
                                }[_ac_role]
                                comp['_ac_icons'] = {}
                                for _state, (_glyph, _colour) in _states.items():
                                    _drawable = f"{icon_name}_{_state}"
                                    output_files[f"res/drawable/{_drawable}.xml"] = (
                                        _generate_button_icon_vector(_glyph, _colour))
                                    comp['_ac_icons'][_state] = _drawable
                    elif ctype == 'image' and comp.get('avatar') and comp.get('status'):
                        status_colors = {
                            'online': '#22C55E', 'away': '#F59E0B',
                            'busy': '#EF4444', 'offline': '#71717A',
                        }
                        status = str(comp.get('status')).lower()
                        color = status_colors.get(status, '#71717A')
                        safe_sid = re.sub(r'[^a-z0-9_]', '_', str(sid).lower())
                        _shape_counter[0] += 1
                        drawable_name = f'apkpy_avatar_status_{safe_sid}_{_shape_counter[0]}'
                        comp['_status_drawable'] = drawable_name
                        output_files[f'res/drawable/{drawable_name}.xml'] = _generate_drawable_xml(
                            color, 99,
                            border_color=styles.get('__theme__', {}).get('background', '#FFFFFF'),
                            border_width=2,
                        )
                    elif ctype == 'skeleton':
                        s = component_style(styles, 'skeleton', comp_id)
                        _shape_counter[0] += 1
                        safe_sid = re.sub(r'[^a-z0-9_]', '_', str(sid).lower())
                        drawable_name = f'apkpy_skeleton_{safe_sid}_{_shape_counter[0]}'
                        comp['_drawable'] = drawable_name
                        output_files[f'res/drawable/{drawable_name}.xml'] = _generate_drawable_xml(
                            _resolve_color(_get_style_bg(s) or '#E5E1E8'),
                            max(3, _parse_radius(s) or 8),
                        )
                    elif ctype in ('empty_state', 'error_state'):
                        _icon_counter[0] += 1
                        safe_sid = re.sub(r'[^a-z0-9_]', '_', str(sid).lower())
                        icon_name = f'ic_state_{safe_sid}_{_icon_counter[0]}'
                        state_style = component_style(styles, ctype, comp_id)
                        tokens = styles.get('__theme__', {})
                        icon_color = state_style.get('icon-color') or (
                            tokens.get('error', '#B3261E') if ctype == 'error_state'
                            else tokens.get('primary', '#6750A4')
                        )
                        comp['_state_icon_drawable'] = icon_name
                        output_files[f'res/drawable/{icon_name}.xml'] = _generate_state_icon_vector(
                            comp.get('icon'), icon_color,
                        )
                    # Recurse into container children
                    if comp.get('children'):
                        _assign_drawables(comp['children'])

            _assign_drawables(components)
            for _vc in _every_comp(components):
                if _vc.get('row'):
                    _assign_drawables([_vc['row']])
                # Chips and segments: their icons and the check, in white;
                # ApkpyChoice tints them for each state.
                if _vc.get('comp_type') in choice_feature.COMPONENTS:
                    _names = []
                    for _glyph in _vc.get('icons') or []:
                        if not _glyph:
                            _names.append(None)
                            continue
                        _icon_counter[0] += 1
                        safe_sid = re.sub(r'[^a-z0-9_]', '_', str(sid).lower())
                        _names.append(f"ic_choice_{safe_sid}_{_icon_counter[0]}")
                        output_files[f"res/drawable/{_names[-1]}.xml"] = (
                            _generate_button_icon_vector(_glyph, '#FFFFFF'))
                    _vc['_choice_drawables'] = _names
                    _vc['_check_drawable'] = 'ic_choice_check'
                    output_files["res/drawable/ic_choice_check.xml"] = (
                        _generate_button_icon_vector(_choice_rules.CHECK_ICON, '#FFFFFF'))
                # The white icons on the strips a swipe reveals.
                for _side_key in ('right', 'left'):
                    _side = (_vc.get('_gestures') or {}).get(_side_key)
                    if not _side:
                        continue
                    _icon_counter[0] += 1
                    safe_sid = re.sub(r'[^a-z0-9_]', '_', str(sid).lower())
                    _side['_drawable'] = f"ic_swipe_{safe_sid}_{_icon_counter[0]}"
                    output_files[f"res/drawable/{_side['_drawable']}.xml"] = (
                        _generate_button_icon_vector(_side['icon'], '#FFFFFF'))

            # A barra de navegação inferior só existe nos ecrãs que são tabs —
            # ecrãs fora do bottom_nav (ex: detalhe) não têm barra nem podem
            # referenciar R.id.nav_<sid>, que não existe no menu XML.
            _nav_for_screen = transpiler.bottom_nav if (
                transpiler.bottom_nav and sid in transpiler.bottom_nav['screen_ids']
            ) else None

            # O mini-player não aparece no ecrã que ele próprio abre (o Now
            # Playing em grande) — seria redundante (o leitor já está em cheio).
            _mp_for_screen = transpiler.mini_player if (
                transpiler.mini_player and transpiler.mini_player.get('open_sid') != sid
            ) else None

            _app_bar_for_screen = transpiler.screen_app_bars.get(sid)
            if _app_bar_for_screen:
                _safe_sid = _safe_android_id(sid, 'screen')
                _bar_style = component_style(
                    styles, _app_bar_for_screen.get('type'),
                    _app_bar_for_screen.get('id'),
                )
                _bar_fg = _app_bar_colors(styles, _bar_style)[1]
                _leading = _app_bar_for_screen.get('leading')
                if _leading:
                    _leading_drawable = f'ic_appbar_{_safe_sid}_navigation'
                    _leading['_drawable'] = _leading_drawable
                    output_files[f'res/drawable/{_leading_drawable}.xml'] = (
                        _generate_button_icon_vector(_leading.get('icon'), _bar_fg)
                    )
                if _app_bar_for_screen.get('actions'):
                    output_files[f'res/menu/app_bar_{_safe_sid}_menu.xml'] = (
                        _generate_app_bar_menu_xml(sid, _app_bar_for_screen)
                    )
                    for _item in _app_bar_for_screen['actions']:
                        output_files[f'res/drawable/{_item["_drawable"]}.xml'] = (
                            _generate_button_icon_vector(_item.get('icon'), _bar_fg)
                        )

            # Java Activity
            _WARM_WEB[0] = any(web_page_feature.uses(transpiler.screen_components.get(_s, []))
                               for _s in screen_ids)
            java_content = _generate_activity_java(
                sid, components, transpiler.navigations, start_screen_id, package, transpiler.functions, transpiler.declared_permissions, transpiler.permission_callbacks, styles,
                secure_screen=(transpiler.has_secure_screen
                               and (transpiler.secure_screens is None
                                    or sid in transpiler.secure_screens)),
                module_init_cmds=transpiler.module_init_cmds,
                string_constants=transpiler.string_constants,
                background_services=resolved_services,
                onetime_services=resolved_onetime,
                boolean_first_arg_callbacks=transpiler.boolean_first_arg_callbacks,
                scroll=transpiler.screen_scroll.get(sid, False),
                bottom_nav_info=_nav_for_screen,
                drawer_info=transpiler.drawer,
                now_playing=transpiler.now_playing,
                json_item_callbacks=transpiler.json_item_callbacks,
                audio_controls=transpiler.audio_controls,
                auth=transpiler.auth,
                mini_player=_mp_for_screen,
                audio_like=transpiler.audio_like,
                audio_liked_list=transpiler.audio_liked_list,
                audio_playlists_list=transpiler.audio_playlists_list,
                audio_playlist_editor=transpiler.audio_playlist_editor,
                app_bar_info=_app_bar_for_screen,
                overlays=transpiler.overlays,
                reactive_states=transpiler.reactive_states,
                lifecycle_info=transpiler.screen_lifecycles.get(sid),
                data_observers=transpiler.data_observers,
                job_observers=transpiler.job_observers,
            )
            output_files[f"java/Screen_{sid}Activity.java"] = java_content
            if _notifications_enabled:
                output_files[f"java/Screen_{sid}Activity.java"] = notifications_feature.integrate_activity(java_content)
            if _camera_enabled:
                output_files[f"java/Screen_{sid}Activity.java"] = camera_feature.integrate_activity(output_files[f"java/Screen_{sid}Activity.java"])
            if _contacts_enabled:
                output_files[f"java/Screen_{sid}Activity.java"] = contacts_feature.integrate_activity(output_files[f"java/Screen_{sid}Activity.java"])

            # XML Layout
            bg_image = transpiler.screen_bg_images.get(sid)
            screen_scroll = transpiler.screen_scroll.get(sid, False)
            xml_content = _generate_layout_xml(
                sid, components, bool(bg_image), styles, scroll=screen_scroll,
                bottom_nav_info=_nav_for_screen, mini_player_info=_mp_for_screen,
                viewport=(411, 914), package=package,
                app_bar_info=_app_bar_for_screen,
            )
            if transpiler.drawer:
                # The panel wraps the finished screen rather than being woven
                # into it: a DrawerLayout takes its content child first and its
                # panels after, so nothing about the layout generator changes.
                xml_content = _wrap_layout_in_drawer(
                    xml_content, transpiler.drawer,
                    component_style(styles, 'drawer', transpiler.drawer.get('id')),
                    styles.get('__theme__', {}),
                )
            xml_content = _open_shadow_clipping(xml_content)
            output_files[f"res/layout/activity_screen_{sid}.xml"] = xml_content
            for _grad_name, _grad_xml in _SCREEN_GRADIENTS[0].items():
                output_files[f"res/drawable/{_grad_name}.xml"] = _grad_xml
            for _sheet_name, _sheet_xml in _SHEET_LAYOUTS[0].items():
                output_files[f"res/layout/{sheet_feature.layout_name(sid, _sheet_name)}.xml"] = _sheet_xml
                _sheet_own = _get_style_bg(component_style(
                    styles, 'container', transpiler.overlays[_sheet_name]['sheet_id'],
                    include_body=False))
                output_files[f"res/drawable/{sheet_feature.background_name(sid, _sheet_name)}.xml"] = (
                    sheet_feature.background_xml(
                        _color_xml(_sheet_own) if _sheet_own else '@color/apkpy_surface'))
                output_files[f"res/drawable/{sheet_feature.HANDLE_DRAWABLE}.xml"] = sheet_feature.handle_xml()
            for _vc in _every_comp(components):
                if _vc.get('_row_xml') and _vc.get('_row_layout'):
                    output_files[f"res/layout/{_vc['_row_layout']}.xml"] = _vc['_row_xml']

            def _has_responsive_component(items):
                return any(
                    bool(item.get('responsive'))
                    or _has_responsive_component(item.get('children', []))
                    for item in items
                )

            def _component_selectors(items):
                aliases = {'input_field': 'inputs', 'list_view': 'list'}
                found = {'body', sid}
                for item in items:
                    kind = item.get('comp_type')
                    if kind:
                        found.add(kind)
                        found.add(aliases.get(kind, kind))
                    if item.get('id'):
                        found.add(str(item['id']))
                    found.update(_component_selectors(item.get('children', [])))
                return found

            responsive_selectors = _component_selectors(components)
            if has_responsive_styles(styles, responsive_selectors) or _has_responsive_component(components):
                variants = {
                    "res/layout-land": (914, 411),
                    "res/layout-sw600dp": (800, 1100),
                    "res/layout-sw600dp-land": (1100, 800),
                }
                for folder, viewport in variants.items():
                    output_files[f"{folder}/activity_screen_{sid}.xml"] = _generate_layout_xml(
                        sid, components, bool(bg_image), styles,
                        scroll=screen_scroll,
                        bottom_nav_info=_nav_for_screen,
                        mini_player_info=_mp_for_screen,
                        viewport=viewport, package=package,
                        app_bar_info=_app_bar_for_screen,
                    )
                    for _sheet_name, _sheet_xml in _SHEET_LAYOUTS[0].items():
                        output_files[f"{folder}/{sheet_feature.layout_name(sid, _sheet_name)}.xml"] = _sheet_xml

            if bg_image:
                ext = bg_image.split('.')[-1]
                output_files[f"res/drawable/screen_{sid}_bg.{ext}"] = ("COPY_FILE", bg_image)
            if (_app_bar_for_screen
                    and _app_bar_for_screen.get('type') == 'sliver_app_bar'
                    and _app_bar_for_screen.get('image')
                    and not _app_bar_for_screen.get('_is_remote')):
                _bar_image = str(_app_bar_for_screen['image'])
                _bar_base = os.path.splitext(os.path.basename(_bar_image))[0]
                _bar_safe = re.sub(r'[^a-z0-9_]', '_', _bar_base.lower())
                if _bar_safe and not _bar_safe[0].isalpha():
                    _bar_safe = 'img_' + _bar_safe
                _bar_ext = os.path.splitext(_bar_image)[-1].lower() or '.png'
                output_files[f'res/drawable/{_bar_safe}{_bar_ext}'] = (
                    'COPY_FILE', _bar_image,
                )

        # ── Processar assets de imagem (image()) ──────────────────────────────
        # Percorre todos os ecrãs e copia os ficheiros de imagem + gera image_shapes.xml
        def _uses_map_component(items):
            return any(
                item.get('comp_type') == 'map'
                or _uses_map_component(item.get('children', []))
                for item in items
            )

        if any(
                _uses_map_component(transpiler.screen_components.get(sid, []))
                for sid in screen_ids):
            output_files['java/ApkpyMapView.java'] = (
                maps_feature.generate_map_view_java(package)
            )

        def _uses_component_types(items, component_types):
            return any(
                item.get('comp_type') in component_types
                or _uses_component_types(item.get('children', []), component_types)
                for item in items
            )

        def _screen_has_row_markdown(items):
            """Uma linha de coleccao com fatia `markdown` chama o mesmo
            renderizador que o componente `markdown()`, por isso a classe tem
            de ir no APK -- senao e' um cannot-find-symbol no fim do build."""
            return any(
                (item.get('comp_type') == 'virtual_collection'
                 and (item.get('template') or {}).get('markdown'))
                or _screen_has_row_markdown(item.get('children', []))
                for item in items
            )

        if any(
                _uses_component_types(
                    transpiler.screen_components.get(sid, []),
                    {'markdown', 'rich_text'},
                )
                or _screen_has_row_markdown(
                    transpiler.screen_components.get(sid, []))
                for sid in screen_ids):
            output_files['java/ApkpyRichContentView.java'] = (
                rich_content_feature.generate_rich_content_view_java(package)
            )

        if any(
                _uses_component_types(
                    transpiler.screen_components.get(sid, []),
                    {'tree_view'},
                )
                for sid in screen_ids):
            output_files['java/ApkpyTreeView.java'] = (
                rich_content_feature.generate_tree_view_java(package)
            )

        shape_styles = []  # entradas para res/values/image_shapes.xml

        def _process_image_comps(comp_list):
            for comp in comp_list:
                if comp['comp_type'] == 'image':
                    # Main source, placeholder and fallback share the same
                    # drawable pipeline. URLs stay runtime-only.
                    for asset in (
                        comp.get('src'), comp.get('placeholder'), comp.get('fallback'),
                    ):
                        if not asset or str(asset).startswith(('http://', 'https://')):
                            continue
                        safe_name = _android_drawable_name(asset)
                        ext = os.path.splitext(str(asset))[-1].lower() or '.png'
                        output_files[f"res/drawable/{safe_name}{ext}"] = (
                            "COPY_FILE", asset,
                        )
                    # Recolher styles para ShapeableImageView (border-radius)
                    if comp.get('_shape_style_name') and comp.get('_shape_radius', 0) > 0:
                        shape_styles.append((comp['_shape_style_name'], comp['_shape_radius']))
                elif comp['comp_type'] == 'video':
                    poster = comp.get('poster')
                    if poster and not str(poster).startswith(('http://', 'https://')):
                        safe_name = _android_drawable_name(poster)
                        ext = os.path.splitext(str(poster))[-1].lower() or '.png'
                        output_files[f"res/drawable/{safe_name}{ext}"] = (
                            "COPY_FILE", poster,
                        )
                if comp.get('children'):
                    _process_image_comps(comp['children'])

        for sid in screen_ids:
            _process_image_comps(transpiler.screen_components.get(sid, []))
            # A row's pictures are shaped like any other (ShapeableImageView);
            # their files are packaged from the items (_package_row_pictures).
            for _vc in _every_comp(transpiler.screen_components.get(sid, [])):
                for _part in (_row_components(_vc['row']) if _vc.get('row') else ()):
                    if _part.get('comp_type') == 'image' and _part.get('_shape_style_name')                             and _part.get('_shape_radius', 0) > 0:
                        shape_styles.append((_part['_shape_style_name'], _part['_shape_radius']))
        def _card_covers(comp_list, found):
            # grid() and carousel() cards name their covers in item dicts. A
            # local one was never packaged, and the phone looked for it as a
            # file path: every cover of a shelf was blank.
            for comp in comp_list:
                if comp.get('comp_type') in ('grid', 'carousel', 'list_view'):
                    for item in comp.get('items', []) or []:
                        if isinstance(item, dict) and item.get('image'):
                            found.add(str(item['image']))
                if comp.get('children'):
                    _card_covers(comp['children'], found)
            return found

        _covers = set()
        for sid in screen_ids:
            _card_covers(transpiler.screen_components.get(sid, []), _covers)
        for asset in sorted(set(getattr(transpiler, 'set_src_assets', ()) or ()) | _covers):
            if str(asset).startswith(('http://', 'https://')) or os.path.isabs(str(asset)):
                continue
            safe_name = _android_drawable_name(asset)
            ext = os.path.splitext(str(asset))[-1].lower() or '.png'
            output_files.setdefault(f"res/drawable/{safe_name}{ext}", ("COPY_FILE", asset))
        for asset in sorted(getattr(transpiler, 'audio_assets', ()) or ()):
            if str(asset).startswith(('http://', 'https://')) or os.path.isabs(str(asset)):
                continue
            ext = os.path.splitext(str(asset))[-1].lower() or '.mp3'
            output_files.setdefault(
                f"res/raw/{_android_drawable_name(asset, 'audio')}{ext}", ("COPY_FILE", asset))

        # Gerar res/values/image_shapes.xml se houver ShapeableImageViews com border-radius
        if shape_styles:
            seen = set()
            shape_lines = [
                '<?xml version="1.0" encoding="utf-8"?>',
                '<resources>',
            ]
            for style_name, radius in shape_styles:
                if style_name not in seen:
                    seen.add(style_name)
                    shape_lines += [
                        f'    <style name="{style_name}" parent="">',
                        f'        <item name="cornerFamily">rounded</item>',
                        f'        <item name="cornerSize">{radius}dp</item>',
                        f'    </style>',
                    ]
            shape_lines.append('</resources>')
            output_files["res/values/image_shapes.xml"] = "\n".join(shape_lines)

        # Android 12+ reads dataExtractionRules; older releases read
        # fullBackupContent. Both are declared, and both say the same thing.
        output_files["res/xml/apkpy_backup_rules.xml"] = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<data-extraction-rules>\n'
            '    <cloud-backup>\n'
            '        <exclude domain="sharedpref" path="apkpy_storage.xml" />\n'
            '        <exclude domain="sharedpref" path="apkpy_auth.xml" />\n'
            '    </cloud-backup>\n'
            '    <device-transfer>\n'
            '        <exclude domain="sharedpref" path="apkpy_storage.xml" />\n'
            '        <exclude domain="sharedpref" path="apkpy_auth.xml" />\n'
            '    </device-transfer>\n'
            '</data-extraction-rules>\n'
        )
        output_files["res/xml/apkpy_backup_legacy.xml"] = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<full-backup-content>\n'
            '        <exclude domain="sharedpref" path="apkpy_storage.xml" />\n'
            '        <exclude domain="sharedpref" path="apkpy_auth.xml" />\n'
            '</full-backup-content>\n'
        )

        # camera.capture() partilha fotos com a app de câmara via FileProvider —
        # gerar res/xml/file_paths.xml a apontar para a mesma pasta usada em
        # getExternalFilesDir(Environment.DIRECTORY_PICTURES) no helper _cameraCapture.
        needs_file_provider = "CAMERA" in transpiler.declared_permissions
        if needs_file_provider:
            output_files["res/xml/file_paths.xml"] = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<paths xmlns:android="http://schemas.android.com/apk/res/android">\n'
                '    <external-files-path name="apkpy_photos" path="Pictures" />\n'
                '    <files-path name="apkpy_camera" path="apkpy_camera/" />\n'
                '</paths>\n'
            )

        # Export the normalized design tokens as Android resources as well. This
        # makes generated projects understandable and easy to extend manually.
        # Read off the light palette rather than restated here. The two copies
        # were identical and had to stay identical: a colour added to the theme
        # and forgotten here becomes a KeyError in _color_table for every app
        # that never declared a Theme, which is the half of the test suite that
        # would not have caught it.
        _theme_tokens = {
            **{k: str(v) for k, v in _theme._PALETTES['light'].items()},
            'mode': 'light',
            **styles.get('__theme__', {}),
        }
        # An app without an explicit Theme() still needs the pill tint, or it
        # falls back to primary and hides the icon it sits behind.
        _theme_tokens.setdefault('nav_indicator', _mix_color(
            _theme_tokens['surface'], _theme_tokens['primary'], 0.22))
        # Even projects without an explicit Theme need a complete Material
        # theme, because MaterialCardView/Toolbar enforce these attributes at
        # runtime (a successful Java build alone does not catch the crash).
        _color_keys = _THEMED_COLOR_TOKENS

        def _color_table(values):
            lines = ['<?xml version="1.0" encoding="utf-8"?>', '<resources>']
            for key in _color_keys:
                lines.append(
                    '    <color name="apkpy_%s">%s</color>'
                    % (key, _resolve_color(str(values[key])))
                )
            lines.append('</resources>')
            return '\n'.join(lines)

        # Two tables, one name each. `values/` answers in day mode and
        # `values-night/` in night mode, which is how Android has always done
        # this -- the switch costs nothing at run time because the resource
        # system does the work while the layout inflates.
        #
        # The author declares one appearance; the other is the same theme in
        # the opposite mode, keeping whatever colours they actually chose. An
        # orange primary stays orange in both; a background they never named
        # comes from the palette they never named it in.
        _declared = _APP_THEME[0]
        _is_dark = _theme_tokens.get('mode') == 'dark'
        _day_tokens = dict(_theme_tokens)
        _night_tokens = dict(_theme_tokens)
        if _declared is not None:
            _other = _declared.counterpart().tokens
            _other = dict(_other)
            _other.setdefault('nav_indicator', _mix_color(
                str(_other['surface']), str(_other['primary']), 0.22))
            if _is_dark:
                _day_tokens = _other
            else:
                _night_tokens = _other
        elif _is_dark:
            # No Theme() to ask, so the two tables are the same. An app that
            # never declared an appearance has not asked to switch either.
            _day_tokens = _theme_tokens

        output_files['res/values/apkpy_theme.xml'] = _color_table(_day_tokens)
        output_files['res/values-night/apkpy_theme.xml'] = _color_table(
            _night_tokens
        )

        # Typefaces: the files themselves plus the family that maps
        # weights onto them. Nothing is written when nobody called font().
        _emit_font_resources(transpiler.fonts, output_files)

        def _theme_style(light_bars):
            return '\n'.join([
            '<?xml version="1.0" encoding="utf-8"?>',
            '<resources>',
            '    <style name="Theme.App" parent="Theme.MaterialComponents.DayNight.NoActionBar">',
            '        <item name="colorPrimary">@color/apkpy_primary</item>',
            '        <item name="colorPrimaryVariant">@color/apkpy_primary</item>',
            '        <item name="colorOnPrimary">@color/apkpy_on_primary</item>',
            '        <item name="colorSecondary">@color/apkpy_secondary</item>',
            '        <item name="colorSecondaryVariant">@color/apkpy_secondary</item>',
            '        <item name="colorOnSecondary">@color/apkpy_text</item>',
            '        <item name="colorSurface">@color/apkpy_surface</item>',
            '        <item name="colorOnSurface">@color/apkpy_text</item>',
            '        <item name="android:colorBackground">@color/apkpy_background</item>',
            '        <item name="colorError">@color/apkpy_error</item>',
            '        <item name="android:windowBackground">@color/apkpy_background</item>',
            # Activities with an app bar draw that surface behind the status
            # icons; screens without one set their opaque colour in Java.
            '        <item name="android:statusBarColor">@android:color/transparent</item>',
            '        <item name="android:navigationBarColor">@color/apkpy_surface</item>',
            f'        <item name="android:windowLightStatusBar">{light_bars}</item>',
            f'        <item name="android:windowLightNavigationBar">{light_bars}</item>',
            '        <item name="windowActionModeOverlay">true</item>',
            '        <item name="android:windowNoTitle">true</item>',
            '    </style>',
            '</resources>',
        ])

        # The clock and the battery are drawn by the system, over whatever the
        # app puts behind them. Deciding light-on-dark at build time left them
        # invisible the moment the app switched, so the answer comes from the
        # same qualifier the colours do -- no Java, and no way for the two to
        # disagree.
        output_files['res/values/themes.xml'] = _theme_style('true')
        output_files['res/values-night/themes.xml'] = _theme_style('false')

        # Bottom navigation menu XML + vector icon drawables + color selector
        if transpiler.bottom_nav:
            output_files["res/menu/bottom_nav_menu.xml"] = _generate_bottom_nav_menu_xml(transpiler.bottom_nav)

            _nav_active_icons = (transpiler.bottom_nav.get('icons_active')
                                 or transpiler.bottom_nav['icons'])
            for sid, icon_name, active_name in zip(
                    transpiler.bottom_nav['screen_ids'],
                    transpiler.bottom_nav['icons'], _nav_active_icons):
                # Two drawables and a selector: state_checked is plain Android,
                # so the outline-to-filled swap does not depend on Material 3.
                output_files[f"res/drawable/ic_nav_{sid}.xml"] = (
                    _generate_bottom_nav_vector(icon_name, 'outlined'))
                output_files[f"res/drawable/ic_nav_{sid}_on.xml"] = (
                    _generate_bottom_nav_vector(active_name, 'filled'))
                output_files[f"res/drawable/ic_nav_sel_{sid}.xml"] = (
                    '<?xml version="1.0" encoding="utf-8"?>\n'
                    '<selector xmlns:android="http://schemas.android.com/apk/res/android">\n'
                    f'    <item android:state_checked="true" android:drawable="@drawable/ic_nav_{sid}_on" />\n'
                    f'    <item android:drawable="@drawable/ic_nav_{sid}" />\n'
                    '</selector>\n'
                )
            # From the tokens the app declared -- the ones the bar itself is
            # painted with -- not from the light palette the resources below
            # are filled with: that mix put a lilac pill and dark-grey labels
            # on a navy bar whenever there was no Theme().
            _nav_style = _nav_look(styles)
            _nav_bar, _nav_active, _nav_inactive, _nav_pill = (
                _nav_style['bar'], _nav_style['active'], _nav_style['inactive'], _nav_style['pill'])
            if _nav_style['floating']:
                output_files['res/drawable/apkpy_nav_bar.xml'] = _generate_drawable_xml(
                    _resolve_color(_nav_bar),
                    _parse_radii({'border-radius': '%gpx' % _nav_style['radius']}),
                    border_color=_nav_style['border'],
                    border_width=int(round(_nav_style['border_width'])),
                    padding=(0, 0, 0, 0))
            _nav_active = _resolve_color(_nav_active)
            _nav_inactive = _resolve_color(_nav_inactive)
            _nav_indicator = transpiler.bottom_nav.get('indicator', 'pill')
            if _nav_indicator == 'pill':
                # parent="" with explicit values: itemActiveIndicatorStyle is a
                # NavigationBarView attribute (Material 1.6+), but the Material 3
                # parent style resolves theme attributes this app does not have,
                # since the generated theme is Theme.MaterialComponents.
                output_files["res/values/apkpy_nav.xml"] = (
                    '<?xml version="1.0" encoding="utf-8"?>\n'
                    '<resources>\n'
                    '    <style name="ApkpyNavIndicator" parent="">\n'
                    # A tint of the surface, not full-strength primary: the
                    # checked icon is tinted primary too, so a solid primary
                    # pill swallowed the icon whole on the device.
                    f'        <item name="android:color">{_color_xml(_resolve_color(_nav_pill))}</item>\n'
                    '        <item name="android:width">64dp</item>\n'
                    '        <item name="android:height">32dp</item>\n'
                    '        <item name="marginHorizontal">8dp</item>\n'
                    '        <item name="shapeAppearance">@style/ApkpyNavIndicatorShape</item>\n'
                    '    </style>\n'
                    '    <style name="ApkpyNavIndicatorShape" parent="">\n'
                    '        <item name="cornerFamily">rounded</item>\n'
                    '        <item name="cornerSize">16dp</item>\n'
                    '    </style>\n'
                    '</resources>\n'
                )
            output_files["res/color/nav_item_color.xml"] = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<selector xmlns:android="http://schemas.android.com/apk/res/android">\n'
                f'    <item android:state_checked="true" android:color="{_color_xml(_nav_active)}" />\n'
                f'    <item android:color="{_color_xml(_nav_inactive)}" />\n'
                '</selector>\n'
            )

        # ── Navigation drawer resources ──────────────────────────────────────
        if transpiler.drawer:
            _drawer = transpiler.drawer
            _drawer_style = component_style(styles, 'drawer', _drawer.get('id'))
            _drawer_tokens = styles.get('__theme__', {})
            output_files['res/menu/apkpy_drawer_menu.xml'] = (
                _generate_drawer_menu_xml(_drawer)
            )
            if _drawer.get('header') or _drawer.get('subtitle'):
                output_files['res/layout/apkpy_drawer_header.xml'] = (
                    _generate_drawer_header_xml(
                        _drawer, _drawer_style, _drawer_tokens)
                )
            _item_tint = _resolve_color(
                _get_style_fg(_drawer_style)
                or _drawer_tokens.get('text', '#111111'))
            _item_active = _resolve_color(
                _drawer_style.get('active-color')
                or _drawer_tokens.get('primary', '#6750A4'))
            output_files['res/color/apkpy_drawer_item_color.xml'] = (
                _generate_drawer_item_color_xml(_item_active, _item_tint)
            )
            _drawer_surface = _resolve_color(
                _get_style_bg(_drawer_style)
                or _drawer_tokens.get('surface', '#FFFFFF'))
            _drawer_pill = _resolve_color(
                _drawer_style.get('indicator-color')
                or _mix_color(_drawer_surface, _item_active, 0.22))
            _drawer_radius = _parse_radius(_drawer_style) or 24
            output_files['res/drawable/apkpy_drawer_item_bg.xml'] = (
                _generate_drawer_item_background_xml(
                    _drawer_pill, _drawer_radius)
            )
            output_files['res/values/apkpy_drawer.xml'] = (
                _generate_drawer_item_style_xml(int(round(
                    _length_px(_drawer_style.get('item-size'), 15))))
            )
            for _sid, _icon in zip(_drawer['screen_ids'], _drawer['icons']):
                output_files[
                    'res/drawable/ic_drawer_%s.xml' % _safe_android_id(_sid, 'item')
                ] = _generate_button_icon_vector(_icon, _item_tint)

        # ── Foreground media service (audio.play_background) ──────────────────
        # Toca em segundo plano com o ecrã apagado + controlos no lockscreen.
        needs_push = push_feature.commands_use_push(
            transpiler.functions, transpiler.module_init_cmds
        )
        if needs_push:
            output_files["java/ApkpyFirebaseMessagingService.java"] = (
                push_feature.generate_service_java(
                    package,
                    (transpiler.push_config or {}).get("screen_id")
                    or start_screen_id,
                    transpiler.push_config,
                )
            )
            if _notifications_enabled:
                output_files["java/ApkpyFirebaseMessagingService.java"] = notifications_feature.integrate_push(
                    output_files["java/ApkpyFirebaseMessagingService.java"])

        def _cmds_have(cmds_list, type_name):
            for c in cmds_list or []:
                if isinstance(c, dict):
                    if c.get('type') == type_name:
                        return True
                    for body_key in _BODY_KEYS:
                        if c.get(body_key) and _cmds_have(c[body_key], type_name):
                            return True
            return False
        needs_media_service = any(
            any(_cmds_have(f_info.get('cmds', []), t)
                for t in ('audio_play_bg', 'audio_playlist', 'audio_next', 'audio_prev', 'audio_shuffle', 'audio_repeat',
                          'audio_add_to_playlist', 'audio_play_saved_playlist',
                          'audio_edit_playlist', 'audio_remove_from_playlist', 'audio_delete_playlist'))
            for f_info in transpiler.functions.values() if f_info
        )
        # A barra "now playing" lê a posição do ApkpyMediaService → garante que existe.
        if transpiler.now_playing:
            needs_media_service = True
        # Os botões de estado (audio.controls) sondam isPlaying()/shuffleOn()/repeatMode().
        if transpiler.audio_controls:
            needs_media_service = True
        # O mini-player fixo lê currentTitle()/currentArtist()/currentArt()/isPlaying().
        if transpiler.mini_player:
            needs_media_service = True
            # Its play/pause is a Material icon: the ⏸ and ▶ characters were
            # emoji on some phones. The colour is the one the bar's text uses.
            _mp_icon_colour = _resolve_color(mini_player_colors(
                styles.get('__theme__', {}) or {},
                component_style(styles, 'mini_player', transpiler.mini_player.get('id'),
                                include_body=False))[1])
            output_files["res/drawable/apkpy_mp_play.xml"] = (
                _generate_button_icon_vector('play_arrow', _mp_icon_colour))
            output_files["res/drawable/apkpy_mp_pause.xml"] = (
                _generate_button_icon_vector('pause', _mp_icon_colour))
        # O botão de like lê currentTitle()/currentArtist()/currentArt()/currentSrc().
        if transpiler.audio_like:
            needs_media_service = True
        # add_to_playlist lê a faixa atual do serviço; playlists_list só lê SharedPrefs.
        if transpiler.audio_playlists_list:
            needs_media_service = True
        # O editor de playlist gera helpers que (indiretamente) referem o serviço.
        if transpiler.audio_playlist_editor:
            needs_media_service = True
        if needs_media_service:
            output_files["java/ApkpyMediaService.java"] = _generate_media_service_java(package)

        needs_location_service = bool(
            getattr(transpiler, "needs_location_service", False)
            or location_background_feature.commands_use_background(
                transpiler.functions, transpiler.module_init_cmds
            )
        )
        if needs_location_service:
            output_files["java/ApkpyLocationService.java"] = (
                location_background_feature.generate_service_java(package)
            )

        # ── Login OAuth (auth.login) → Activity recetora do redirect ──────────
        if transpiler.auth:
            _then_sid = transpiler.auth.get('then_sid') or start_screen_id
            _then_class = f"Screen_{_then_sid}Activity"
            output_files["java/ApkpyAuthActivity.java"] = _generate_auth_activity_java(
                package, transpiler.auth, _then_class)

        # ── Linhas de lista ricas (list_view rich) → layout da linha ──────────
        def _any_rich_list(comp_list):
            for c in comp_list or []:
                if c.get('comp_type') == 'list_view' and c.get('rich'):
                    return True
                if c.get('children') and _any_rich_list(c['children']):
                    return True
            return False
        if any(_any_rich_list(transpiler.screen_components.get(sid, [])) for sid in screen_ids):
            output_files["res/layout/apkpy_list_row.xml"] = _generate_list_row_xml()

        # AndroidManifest
        output_files["AndroidManifest.xml"] = _generate_manifest(
            screen_ids, start_screen_id, package, transpiler.declared_permissions,
            needs_file_provider=needs_file_provider,
            bottom_nav_info=transpiler.bottom_nav,
            needs_media_service=needs_media_service,
            needs_push=needs_push,
            needs_location_service=needs_location_service,
            auth=transpiler.auth,
            pinned=bool(transpiler.pinned_hosts),
            needs_flash=_uses_flashlight,
            sensors_used=_sensors_in_app,
            orientations=kit_feature.manifest_orientations(
                screen_ids, transpiler.screen_orientation, transpiler.app_orientation),
        )
        if _notifications_enabled:
            output_files["AndroidManifest.xml"] = notifications_feature.integrate_manifest(
                output_files["AndroidManifest.xml"],
                reminders=notifications_feature.uses_reminders(tree),
                exact=notifications_feature.uses_exact(tree))
        if _camera_enabled:
            output_files["AndroidManifest.xml"] = camera_feature.integrate_manifest(output_files["AndroidManifest.xml"])
        if _nfc_enabled:
            output_files["AndroidManifest.xml"] = nfc_feature.integrate_manifest(output_files["AndroidManifest.xml"])

        # ── Idiomas ───────────────────────────────────────────────────────────
        # As marcas que o t() deixou nos layouts viram referencias a recursos, e
        # cada lingua ganha o seu res/values*/strings.xml. Feito aqui, no fim,
        # para ser UMA passagem sobre o XML ja escrito em vez de uma condicao
        # em cada um dos sitios que escrevem texto.
        # Dito uma vez, no fim, e sem parar o build: ver accessibility.report.
        accessibility_feature.report(
            _audit_accessibility(transpiler.screen_components, styles))

        if transpiler.pinned_hosts:
            output_files['res/xml/apkpy_network_security.xml'] = (
                pinning_feature.network_security_xml(transpiler.pinned_hosts))
        if transpiler.translations:
            default_tag = transpiler.default_language
            for tag, words in transpiler.translations.items():
                folder = ('res/values' if tag == default_tag
                          else 'res/' + i18n_feature.resource_dir(tag))
                output_files['%s/apkpy_strings.xml' % folder] = (
                    i18n_feature.strings_xml(words))

        for name in list(output_files):
            body = output_files[name]
            if not isinstance(body, str) or i18n_feature.MARK not in body:
                continue
            body = i18n_feature.apply_to_xml(body)
            stray = i18n_feature.stray_key(body)
            if stray:
                # A marca sobreviveu, logo o t() esta num sitio onde nao pode
                # virar @string/... -- por exemplo colado a outro texto. Sem
                # isto, o telemovel desenhava a propria referencia.
                raise ApkpyError(
                    'ApkPy cannot put t("%s") in the middle of another value.'
                    % stray,
                    code='U2034',
                    title='This translation cannot go here',
                    cause=(
                        'A translated word becomes a reference to a string '
                        'resource, and Android only reads a reference when it '
                        'is the whole value. Joined to other text it would be '
                        'drawn on screen exactly as written.'
                    ),
                    expected='t("%s") on its own' % stray,
                    received='text built around t("%s")' % stray,
                    suggestions=[
                        'Put the whole sentence in the table, with its own key.',
                        'Build the joined text inside a function instead, where '
                        'it is assembled while the app runs.',
                    ],
                    docs=i18n_feature.DOCS,
                )
            output_files[name] = body

        # ApkpyAuth.java whenever a file calls it: auth.login(), and also an
        # app that only reads auth.token() or auth.is_logged_in().
        if any(name.endswith('.java') and 'ApkpyAuth.' in body
               for name, body in output_files.items()):
            output_files['java/ApkpyAuth.java'] = auth_oidc_feature.generate_auth_java(
                package, transpiler.auth)

        # O que o native.gradle()/keep() pediu, para o CLI juntar ao projeto.
        _native_gradle = native_feature.gradle_text()
        if _native_gradle:
            output_files['native/gradle.txt'] = _native_gradle + '\n'
        _native_keep = native_feature.keep_text()
        if _native_keep:
            output_files['native/keep.pro'] = _native_keep
        if _USES_CODE_EDITOR[0]:
            output_files[code_editor_feature.JAVA_FILE] = code_editor_feature.java_source(package)
        if _USES_SHIMMER[0]:
            output_files[shimmer_feature.JAVA_FILE] = shimmer_feature.java_source(package)
        if _USES_GRADIENT[0]:
            output_files[gradient_feature.JAVA_FILE] = gradient_feature.java_class(package)
            output_files[gradient_feature.ATTRS_FILE] = gradient_feature.attrs_xml()
        # Every screen and every worker is written with the whole kit of
        # helpers and a callback for each function of the app: out with the
        # private ones it never reaches, before the marks are counted, so the
        # line map points at the Java that is left (06-11-2026).
        _generated_classes = ['java/Screen_%sActivity.java' % _sid for _sid in screen_ids]
        _generated_classes += ['java/%s.java' % _worker['worker_class'] for _worker in
                               list(resolved_services) + list(resolved_onetime.values())
                               + list(_emitted_jobs)]
        for _class_file in _generated_classes:
            if isinstance(output_files.get(_class_file), str):
                output_files[_class_file] = dead_methods.drop_unreached(output_files[_class_file])
        _lines_map = _take_line_marks(output_files, source_name)
        if _lines_map:
            output_files['apkpy/lines.json'] = _lines_json(
                _lines_map, source_name, python_code)
        _app_keep = _keep_app_files_xml(output_files)
        if _app_keep:
            output_files['res/raw/apkpy_app_keep.xml'] = _app_keep
        return output_files

    except Exception as e:
        return {
            "error.txt": format_exception(
                e, context="Android multi-screen compiler",
                source_code=python_code, filename=source_name,
            )
        }
