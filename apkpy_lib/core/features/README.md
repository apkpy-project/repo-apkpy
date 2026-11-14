# Feature code generators

New Android generators live here instead of adding their full implementation
to the compiler (`core/compiler/`). A feature module should expose small,
explicit helpers that the compiler can call from a narrow integration point.

The compiler is a package: the docstring of `core/compiler/__init__.py` lists
its modules and the order they depend on each other. A hook for a feature goes
in the module that already does that kind of work.
