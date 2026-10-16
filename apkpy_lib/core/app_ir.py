"""Versioned, JSON-safe intermediate representation for ApkPy applications.

The desktop Previewer and the Android generator historically consumed two
different models.  ApkPy Studio needs a third backend, so duplicating the
parser again would guarantee preview/device drift.  This module turns the
existing, battle-tested ``MultiScreenTranspiler`` analysis into a stable wire
format which Android can render without importing Tkinter.

AppIR contains declarations, resolved styles, navigation and callback names.
It never contains live Python objects.  Runtime events and patches are separate
messages so a Studio preview can execute callbacks in another process.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


APP_IR_SCHEMA_VERSION = 1
DEFAULT_VIEWPORT = (411, 914)


@dataclass(frozen=True)
class CompileContext:
    """Inputs which make a compilation independent from process ``cwd``."""

    project_root: str
    source_name: str = "writehere.py"
    revision: int = 1
    viewport: Tuple[int, int] = DEFAULT_VIEWPORT
    config: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def for_source(
        cls,
        source_name: str,
        *,
        project_root: Optional[str] = None,
        revision: int = 1,
        viewport: Tuple[int, int] = DEFAULT_VIEWPORT,
        config: Optional[Mapping[str, Any]] = None,
    ) -> "CompileContext":
        absolute = os.path.abspath(source_name)
        return cls(
            project_root=os.path.abspath(project_root or os.path.dirname(absolute)),
            source_name=absolute,
            revision=max(0, int(revision)),
            viewport=(int(viewport[0]), int(viewport[1])),
            config=dict(config or {}),
        )


@dataclass(frozen=True)
class SourceLocation:
    file: str
    line: int
    column: int
    end_line: int = 0
    end_column: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "endLine": self.end_line or self.line,
            "endColumn": self.end_column or self.column,
        }


@dataclass(frozen=True)
class DiagnosticSpec:
    code: str
    severity: str
    stage: str
    message: str
    file: str = ""
    line: int = 0
    column: int = 0
    received_value: Any = None
    suggestion: str = ""
    component: str = ""
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return _json_safe({
            "code": self.code,
            "severity": self.severity,
            "stage": self.stage,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "receivedValue": self.received_value,
            "suggestion": self.suggestion,
            "component": self.component,
            "details": self.details,
        })


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    node_type: str
    props: Mapping[str, Any]
    style: Mapping[str, Any]
    events: Mapping[str, str]
    children: Sequence["NodeSpec"] = field(default_factory=tuple)
    source: Optional[SourceLocation] = None

    def to_dict(self) -> Dict[str, Any]:
        value = {
            "nodeId": self.node_id,
            "type": self.node_type,
            "props": _json_safe(self.props),
            "style": _json_safe(self.style),
            "events": _json_safe(self.events),
            "children": [child.to_dict() for child in self.children],
        }
        if self.source is not None:
            value["source"] = self.source.to_dict()
        return value


@dataclass(frozen=True)
class ScreenSpec:
    screen_id: str
    scroll: bool
    background_image: Optional[str]
    app_bar: Optional[Mapping[str, Any]]
    lifecycle: Mapping[str, Any]
    components: Sequence[NodeSpec]
    source: Optional[SourceLocation] = None

    def to_dict(self) -> Dict[str, Any]:
        value = {
            "id": self.screen_id,
            "scroll": bool(self.scroll),
            "backgroundImage": self.background_image,
            "appBar": _json_safe(self.app_bar),
            "lifecycle": _json_safe(self.lifecycle),
            "components": [component.to_dict() for component in self.components],
        }
        if self.source is not None:
            value["source"] = self.source.to_dict()
        return value


@dataclass(frozen=True)
class AppSnapshot:
    revision: int
    start_screen_id: str
    screens: Sequence[ScreenSpec]
    styles: Mapping[str, Any]
    theme: Mapping[str, Any]
    keyframes: Mapping[str, Any]
    navigation: Sequence[Mapping[str, Any]]
    bottom_navigation: Optional[Mapping[str, Any]]
    drawer: Optional[Mapping[str, Any]]
    mini_player: Optional[Mapping[str, Any]]
    overlays: Mapping[str, Any]
    permissions: Sequence[str]
    assets: Sequence[Mapping[str, Any]]
    fonts: Sequence[Mapping[str, Any]]
    feature_manifest: Mapping[str, Any]
    source_map: Mapping[str, Mapping[str, Any]]
    source_hash: str
    schema_version: int = APP_IR_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "revision": self.revision,
            "startScreenId": self.start_screen_id,
            "theme": _json_safe(self.theme),
            "styles": _json_safe(self.styles),
            "keyframes": _json_safe(self.keyframes),
            "screens": [screen.to_dict() for screen in self.screens],
            "navigation": _json_safe(self.navigation),
            "bottomNavigation": _json_safe(self.bottom_navigation),
            "drawer": _json_safe(self.drawer),
            "miniPlayer": _json_safe(self.mini_player),
            "overlays": _json_safe(self.overlays),
            "permissions": list(self.permissions),
            "assets": _json_safe(self.assets),
            "fonts": _json_safe(self.fonts),
            "featureManifest": _json_safe(self.feature_manifest),
            "sourceMap": _json_safe(self.source_map),
            "sourceHash": self.source_hash,
        }

    def to_json(self, *, indent: Optional[int] = None) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True,
            separators=None if indent else (",", ":"), indent=indent,
        )


@dataclass
class CompileResult:
    ir: Optional[AppSnapshot]
    diagnostics: List[DiagnosticSpec] = field(default_factory=list)
    # Internal bridge used by the Java/XML backend.  It is intentionally absent
    # from to_dict/to_json and must never cross a process boundary.
    analysis: Optional[Mapping[str, Any]] = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.ir is not None and not any(
            diagnostic.severity == "error" for diagnostic in self.diagnostics
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "ir": self.ir.to_dict() if self.ir is not None else None,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }

    def generate_android_files(
        self, *, package: str = "com.apkpy.app",
    ) -> Mapping[str, str]:
        """Generate Java/XML from the same analysis which produced AppIR.

        This bridge is intentionally strict: failed or deserialized results
        cannot generate an Android project.  A future generator may consume
        only the serialized AppIR, but during the migration this guarantees
        one AST/transpiler pass without changing the proven Java templates.
        """
        if not self.ok or self.ir is None or self.analysis is None:
            raise ValueError(
                "A successful in-process CompileResult is required before "
                "generating Android files."
            )
        from .compiler import translate_python_to_android

        generated = translate_python_to_android(
            self.analysis["source"],
            package=package,
            source_name=self.analysis["source_name"],
            _analysis=self.analysis,
        )
        return generated or {}


@dataclass(frozen=True)
class UiEvent:
    event_id: str
    node_id: str
    event_type: str
    payload: Mapping[str, Any]
    revision: int

    def to_dict(self) -> Dict[str, Any]:
        return _json_safe({
            "eventId": self.event_id,
            "nodeId": self.node_id,
            "type": self.event_type,
            "payload": self.payload,
            "revision": self.revision,
        })


@dataclass(frozen=True)
class Patch:
    revision: int
    sequence: int
    operations: Sequence[Mapping[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return _json_safe({
            "revision": self.revision,
            "sequence": self.sequence,
            "operations": self.operations,
        })


@dataclass(frozen=True)
class NativeRequest:
    request_id: str
    capability: str
    operation: str
    arguments: Mapping[str, Any]
    revision: int

    def to_dict(self) -> Dict[str, Any]:
        return _json_safe({
            "requestId": self.request_id,
            "capability": self.capability,
            "operation": self.operation,
            "arguments": self.arguments,
            "revision": self.revision,
        })


@dataclass(frozen=True)
class NativeResult:
    request_id: str
    success: bool
    value: Any = None
    error: Optional[Mapping[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return _json_safe({
            "requestId": self.request_id,
            "success": self.success,
            "value": self.value,
            "error": self.error,
        })


def compile_to_ir(
    source: str,
    *,
    project_root: Optional[str] = None,
    source_name: str = "writehere.py",
    config: Optional[Mapping[str, Any]] = None,
    revision: int = 1,
    viewport: Tuple[int, int] = DEFAULT_VIEWPORT,
) -> CompileResult:
    """Compile source into AppIR without importing or executing user code."""

    context = CompileContext.for_source(
        source_name,
        project_root=project_root,
        revision=revision,
        viewport=viewport,
        config=config,
    )
    try:
        # Lazy import avoids a compiler/app_ir cycle during module import.
        from .compiler import _prepare_android_analysis

        analysis = _prepare_android_analysis(
            source, context.source_name, context.project_root,
        )
        transpiler = analysis["transpiler"]
        if not transpiler.screens:
            return CompileResult(
                ir=None,
                diagnostics=[DiagnosticSpec(
                    code="IR1001",
                    severity="error",
                    stage="ir",
                    message="No ApkPy Screen declaration was found.",
                    file=context.source_name,
                    suggestion="Create Screen(id=...) and pass it to run(start_screen=...).",
                )],
                analysis=analysis,
            )
        snapshot = _snapshot_from_analysis(analysis, context)
        return CompileResult(ir=snapshot, analysis=analysis)
    except SyntaxError as error:
        return CompileResult(
            ir=None,
            diagnostics=[DiagnosticSpec(
                code="PY1001",
                severity="error",
                stage="parser",
                message=error.msg or "Invalid Python syntax.",
                file=context.source_name,
                line=int(error.lineno or 0),
                column=max(0, int(error.offset or 1) - 1),
                suggestion="Fix the highlighted Python syntax and run the preview again.",
                details=str(error),
            )],
        )
    except Exception as error:
        line = int(getattr(error, "line", 0) or 0)
        return CompileResult(
            ir=None,
            diagnostics=[DiagnosticSpec(
                code=str(getattr(error, "code", "IR1999")),
                severity="error",
                stage="ir",
                message=str(error),
                file=context.source_name,
                line=line,
                received_value=getattr(error, "received", None),
                suggestion=str(getattr(error, "suggestion", "")),
                details=type(error).__name__,
            )],
        )


def _snapshot_from_analysis(
    analysis: Mapping[str, Any], context: CompileContext,
) -> AppSnapshot:
    from ..theme import component_style

    transpiler = analysis["transpiler"]
    styles = analysis["styles"]
    tree = analysis["tree"]
    call_locations = _call_locations(tree, context.source_name)
    used_locations: set = set()
    source_map: Dict[str, Mapping[str, Any]] = {}
    screens: List[ScreenSpec] = []
    screen_ids = list(transpiler.screens.values())
    start_screen_id = transpiler.start_screen_id or screen_ids[0]

    for screen_id in screen_ids:
        screen_location = _screen_location(
            tree, context.source_name, screen_id,
        )
        nodes = _nodes_from_components(
            transpiler.screen_components.get(screen_id, []),
            screen_id=screen_id,
            path=(),
            styles=styles,
            viewport=context.viewport,
            source_name=context.source_name,
            call_locations=call_locations,
            used_locations=used_locations,
            source_map=source_map,
            component_style_fn=component_style,
        )
        if screen_location is not None:
            source_map["screen:" + screen_id] = screen_location.to_dict()
        screens.append(ScreenSpec(
            screen_id=screen_id,
            scroll=bool(transpiler.screen_scroll.get(screen_id, False)),
            background_image=transpiler.screen_bg_images.get(screen_id),
            app_bar=transpiler.screen_app_bars.get(screen_id),
            lifecycle=transpiler.screen_lifecycles.get(screen_id, {}),
            components=nodes,
            source=screen_location,
        ))

    theme = analysis.get("declared_theme")
    theme_payload = {}
    if theme is not None:
        theme_payload = {
            "mode": theme.mode,
            "tokens": dict(theme.tokens),
            "motion": theme.motion,
        }

    return AppSnapshot(
        revision=context.revision,
        start_screen_id=start_screen_id,
        screens=screens,
        styles=styles,
        theme=theme_payload,
        keyframes=analysis.get("keyframes", {}),
        navigation=transpiler.navigations,
        bottom_navigation=transpiler.bottom_nav,
        drawer=transpiler.drawer,
        mini_player=transpiler.mini_player,
        overlays=transpiler.overlays,
        permissions=tuple(transpiler.declared_permissions),
        assets=_collect_assets(transpiler),
        fonts=_collect_fonts(transpiler),
        feature_manifest=_feature_manifest(transpiler),
        source_map=source_map,
        source_hash=hashlib.sha256(
            analysis["source"].encode("utf-8")
        ).hexdigest(),
    )


def _nodes_from_components(
    components: Sequence[Mapping[str, Any]],
    *,
    screen_id: str,
    path: Tuple[int, ...],
    styles: Mapping[str, Any],
    viewport: Tuple[int, int],
    source_name: str,
    call_locations: Sequence[Mapping[str, Any]],
    used_locations: set,
    source_map: Dict[str, Mapping[str, Any]],
    component_style_fn,
) -> List[NodeSpec]:
    result: List[NodeSpec] = []
    for index, component in enumerate(components):
        node_path = path + (index,)
        component_type = str(component.get("comp_type", "component"))
        component_id = component.get("id") or component.get("comp_id")
        location = _match_component_location(
            component_type, component_id, call_locations, used_locations,
        )
        node_id = str(component_id or _stable_node_id(
            source_name, screen_id, node_path, location,
        ))
        variant = component.get("variant") if component_type in {
            "button", "label", "card", "skeleton",
        } else None
        try:
            resolved_style = component_style_fn(
                styles, component_type, component_id,
                variant=variant, viewport=viewport,
            )
        except TypeError:
            resolved_style = component_style_fn(
                styles, component_type, component_id,
                variant=variant,
            )

        events = _component_events(component, node_id)
        excluded = {
            "comp_type", "children", "command", "on_click", "on_change",
            "on_submit", "on_select", "on_long_click",
        }
        props = {
            key: value for key, value in component.items()
            if key not in excluded and not str(key).startswith("_")
        }
        children = _nodes_from_components(
            component.get("children", []),
            screen_id=screen_id,
            path=node_path,
            styles=styles,
            viewport=viewport,
            source_name=source_name,
            call_locations=call_locations,
            used_locations=used_locations,
            source_map=source_map,
            component_style_fn=component_style_fn,
        )
        if location is not None:
            source_map[node_id] = location.to_dict()
        result.append(NodeSpec(
            node_id=node_id,
            node_type=component_type,
            props=props,
            style=resolved_style,
            events=events,
            children=children,
            source=location,
        ))
    return result


def _component_events(
    component: Mapping[str, Any], node_id: str,
) -> Dict[str, str]:
    mapping = {
        "command": "click",
        "on_click": "click",
        "on_change": "change",
        "on_submit": "submit",
        "on_select": "select",
        "on_long_click": "longClick",
    }
    events: Dict[str, str] = {}
    for source_key, event_type in mapping.items():
        callback = component.get(source_key)
        if callback:
            callback_name = _callback_name(callback)
            events[event_type] = "%s:%s:%s" % (
                node_id, event_type, callback_name,
            )
    nav_target = component.get("nav_target") or component.get("to_screen_id")
    if nav_target:
        events["navigate"] = "%s:navigate:%s" % (node_id, nav_target)
    return events


def _callback_name(value: Any) -> str:
    if isinstance(value, str):
        return value
    if callable(value):
        return getattr(value, "__name__", type(value).__name__)
    if isinstance(value, ast.Name):
        return value.id
    return str(value)


def _stable_node_id(
    source_name: str,
    screen_id: str,
    path: Tuple[int, ...],
    location: Optional[SourceLocation],
) -> str:
    if location is not None:
        raw = "%s:%s:%s:%s:%s" % (
            source_name, screen_id, location.line, location.column,
            ".".join(map(str, path)),
        )
    else:
        raw = "%s:%s:%s" % (
            source_name, screen_id, ".".join(map(str, path)),
        )
    return "auto_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _call_locations(
    tree: ast.AST, source_name: str,
) -> List[Mapping[str, Any]]:
    calls: List[Mapping[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        if not name:
            continue
        component_id = None
        for keyword in node.keywords:
            if keyword.arg == "id" and isinstance(keyword.value, ast.Constant):
                component_id = keyword.value.value
                break
        calls.append({
            "name": name,
            "id": component_id,
            "node": node,
            "location": SourceLocation(
                file=source_name,
                line=int(getattr(node, "lineno", 0) or 0),
                column=int(getattr(node, "col_offset", 0) or 0),
                end_line=int(getattr(node, "end_lineno", 0) or 0),
                end_column=int(getattr(node, "end_col_offset", 0) or 0),
            ),
        })
    calls.sort(key=lambda item: (
        item["location"].line, item["location"].column,
    ))
    return calls


def _match_component_location(
    component_type: str,
    component_id: Any,
    call_locations: Sequence[Mapping[str, Any]],
    used_locations: set,
) -> Optional[SourceLocation]:
    aliases = {
        "input_field": {"input_field", "inputs"},
        "virtual_collection": {"virtual_collection"},
        "app_bar_action": {"action"},
    }
    names = aliases.get(component_type, {component_type})
    # An explicit ID is the strongest source-map signal.
    if component_id is not None:
        for index, item in enumerate(call_locations):
            if index in used_locations:
                continue
            if item["id"] == component_id:
                used_locations.add(index)
                return item["location"]
    for index, item in enumerate(call_locations):
        if index in used_locations:
            continue
        if item["name"] in names:
            used_locations.add(index)
            return item["location"]
    return None


def _screen_location(
    tree: ast.AST, source_name: str, screen_id: str,
) -> Optional[SourceLocation]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node.func) != "Screen":
            continue
        value = None
        for keyword in node.keywords:
            if keyword.arg == "id" and isinstance(keyword.value, ast.Constant):
                value = keyword.value.value
                break
        if value is None and node.args and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
        if value == screen_id:
            return SourceLocation(
                source_name,
                int(getattr(node, "lineno", 0) or 0),
                int(getattr(node, "col_offset", 0) or 0),
                int(getattr(node, "end_lineno", 0) or 0),
                int(getattr(node, "end_col_offset", 0) or 0),
            )
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _collect_assets(transpiler: Any) -> List[Mapping[str, Any]]:
    assets: Dict[str, Mapping[str, Any]] = {}

    def visit(items: Iterable[Mapping[str, Any]]) -> None:
        for item in items or []:
            for key in ("src", "image", "background_image", "fallback"):
                value = item.get(key)
                if isinstance(value, str) and value and not value.startswith((
                    "http://", "https://", "data:", "var(", "#",
                )):
                    assets.setdefault(value, {"path": value, "kind": key})
            visit(item.get("children", []))

    for items in transpiler.screen_components.values():
        visit(items)
    for value in transpiler.screen_bg_images.values():
        if isinstance(value, str) and value:
            assets.setdefault(value, {"path": value, "kind": "background"})
    return [assets[key] for key in sorted(assets)]


def _collect_fonts(transpiler: Any) -> List[Mapping[str, Any]]:
    registry = getattr(transpiler, "fonts", None)
    if registry is None:
        return []
    # FontRegistry intentionally keeps a small internal mapping.  Read it
    # defensively so AppIR doesn't make that private storage part of its API.
    for attribute in ("_fonts", "fonts", "_registry", "registry"):
        value = getattr(registry, attribute, None)
        if isinstance(value, Mapping):
            return [
                {"name": str(name), **_json_safe(spec)}
                if isinstance(spec, Mapping) else
                {"name": str(name), "value": _json_safe(spec)}
                for name, spec in sorted(value.items())
            ]
    return []


def _feature_manifest(transpiler: Any) -> Dict[str, Any]:
    component_types = set()

    def visit(items: Iterable[Mapping[str, Any]]) -> None:
        for item in items or []:
            component_types.add(str(item.get("comp_type", "component")))
            visit(item.get("children", []))

    for items in transpiler.screen_components.values():
        visit(items)
    return {
        "componentTypes": sorted(component_types),
        "reactiveState": bool(transpiler.reactive_states),
        "dataCore": bool(getattr(transpiler, "data_schema", None)),
        "dataRelations": bool(getattr(transpiler, "data_relations", None)),
        "dataObservers": bool(getattr(transpiler, "data_observers", None)),
        "backgroundJobs": bool(getattr(transpiler, "background_jobs", None)),
        "backgroundServices": bool(transpiler.background_services),
        "websocket": bool(getattr(transpiler, "_websocket_command_count", 0)),
        "push": bool(transpiler.push_config),
        "location": bool(getattr(transpiler, "needs_location_service", False)),
        "media": bool(
            transpiler.now_playing or transpiler.audio_controls
            or transpiler.mini_player or "video" in component_types
        ),
        "auth": bool(transpiler.auth),
        "drawer": bool(transpiler.drawer),
        "bottomNavigation": bool(transpiler.bottom_nav),
        "overlays": bool(transpiler.overlays),
    }


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, ast.AST):
        return {"$ast": ast.dump(value, annotate_fields=True, include_attributes=False)}
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        values = [_json_safe(item) for item in value]
        if isinstance(value, (set, frozenset)):
            values.sort(key=lambda item: json.dumps(item, sort_keys=True))
        return values
    if callable(value):
        return {"$callback": getattr(value, "__name__", type(value).__name__)}
    if hasattr(value, "id") and type(value).__name__ == "Screen":
        return {"$screen": str(value.id)}
    return str(value)


__all__ = [
    "APP_IR_SCHEMA_VERSION", "CompileContext", "SourceLocation",
    "DiagnosticSpec", "NodeSpec", "ScreenSpec", "AppSnapshot",
    "CompileResult", "UiEvent", "Patch", "NativeRequest", "NativeResult",
    "compile_to_ir",
]
