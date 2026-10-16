# Feature code generators

New Android generators live here instead of adding their full implementation
to `core/compiler.py`. A feature module should expose small, explicit helpers
that the legacy compiler can call from a narrow integration point.

The old compiler remains untouched until a real feature needs its hook. This
avoids a risky refactor made only for file organisation.
