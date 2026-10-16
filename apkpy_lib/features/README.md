# New feature modules

This package is the boundary for new ApkPy functionality. Existing code stays
where it is; this convention applies only to features added from now on.

For a feature named `maps`, keep its implementation split as follows:

```text
apkpy_lib/features/maps.py              Preview/runtime API
apkpy_lib/core/features/maps.py         Android parser/code generator
tests/features/test_maps.py             Focused tests
```

Only the small public export and compiler hook should touch existing files.
The implementation, templates and feature-specific helpers belong to the new
modules. Generated Android files are outputs, never the source of truth.

Rules:

1. Do not move working legacy code just to satisfy this layout.
2. Do not import application or playground files from a feature module.
3. Keep Previewer and Android behaviour behind the same public API.
4. Load optional dependencies only when the feature is used.
5. Give each feature focused parser, preview and generated-Java tests.
