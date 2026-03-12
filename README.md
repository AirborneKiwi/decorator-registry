# decorator-registry

A small Python utility that lets you **register decorators (and before/after/on_error hooks)** for class methods in a central registry, then **apply them deterministically** (same order every time) with **group-based enable/disable**.

This is useful for instrumentation/logging/telemetry, invariant checks, TeX snapshotting, etc., without cluttering your core classes with lots of `@decorator` lines.

## Features

- Register **plain decorators** or **hooks** (`before`, `after`, `on_error`) against specific methods.
- **Deterministic application order** (outer → inner): `before → after → on_error → plain`.
- **Group flags** to enable/disable whole bundles of instrumentation.
- Works with `staticmethod`, `classmethod`, and `property`.
- **Idempotent**: repeated `apply_decorators()` won’t double-wrap (uses a stable marker).

## Install

### From GitHub (recommended while developing)

```bash
pip install "decorator-registry @ git+https://github.com/AirborneKiwi/decorator-registry.git@main"
```

Pin a tag once you create releases:

```bash
pip install "decorator-registry @ git+https://github.com/AirborneKiwi/decorator-registry.git@v0.1.0"
```

## Quickstart

### 1) In your project: import and apply decorators

```python
import my_module_with_classes as core
import my_decorators_module as decorators

# decorators module registers hooks at import time
# now patch classes (or whole module)
from decorator_registry import apply_decorators
apply_decorators(core)
```

### 2) Define decorators/hooks in a separate module

```python
from decorator_registry import register_before, register_after, enable_group, disable_group

ENABLED = True
decorator_group = __file__

def _enabled() -> bool:
    return ENABLED

# Example: log around Context.balance defined by a tuple of strings
@register_before(("Context", "balance"), group=decorator_group, enabled=_enabled)
def _balance_before(self, *a, **k):
    print(">>> BALANCE")
    print(self.format_phase_table_console())

# or directly with the function
@register_after(Context.balance, group=decorator_group, enabled=_enabled)
def _balance_after(self, _res, *a, **k):
    print(self.format_phase_table_console())
    print("<<< BALANCE")

# Enable/disable this group globally
disable_group(decorator_group)   # no-op (not applied)
enable_group(decorator_group)    # applied again on next apply_decorators(...)
```

> Tip: If you prefer, you can register against method objects (e.g. `Context.balance`) if your registry normalizes keys by `__qualname__`.

## API overview

- `register_before(target, group=..., enabled=...)`
- `register_after(target, group=..., enabled=...)`
- `register_on_error(target, group=..., enabled=...)`
- `register_decorator(target, group=...)` (plain decorators)
- `decorate_from_registry(obj_or_class, groups=None, include_ungrouped=True)`
- `apply_decorators(*targets)` where each target is a class or module
- `enable_group(name)`, `disable_group(name)`, `set_group_enabled(name, bool)`

## Development

```bash
python -m pip install -U pip
python -m pip install -e .
python -m pytest -q
```

## License

This module is published free to use and change for anyone under the MIT licence.
