# decorator-registry

A small Python utility for registering decorators and hooks for class methods in a central registry, then applying them later in a deterministic way.

It is useful when you want logging, tracing, timing, validation, fallback handling, feature flags, or other cross-cutting behavior without scattering many `@decorator` lines across your core classes.

## What it does

You can register behavior for methods in four forms:

- `before`: run code before the target method
- `after`: run code after the target method returns successfully
- `on_error`: run code if the target method raises
- `plain`: apply a normal decorator

Decorators and hooks are collected in registries and then applied later with `apply_decorators(...)` or `decorate_from_registry(...)`.

## Why use it

This library is useful when you want to keep business logic clean and move instrumentation elsewhere.

Typical use cases:

- logging and tracing
- metrics and timing
- validation and policy checks
- error fallback behavior
- debug-only or feature-flagged hooks
- applying the same hook to many methods at once

Instead of writing:

```python
class Calculator:
    @trace
    @timeit
    @audit
    def add(self, a, b):
        return a + b
```

you can keep the class clean:

```python
class Calculator:
    def add(self, a, b):
        return a + b
```

and register all behavior in a separate module.

---

## Features

- Register hooks centrally instead of decorating methods inline
- Deterministic wrapping order:
  - `before`
  - `after`
  - `on_error`
  - plain decorators
- Group-based enable/disable
- Idempotent application: calling `apply_decorators(...)` repeatedly does not double-wrap methods
- Supports:
  - instance methods
  - `@staticmethod`
  - `@classmethod`
  - `@property`
- Supports applying to:
  - individual instances
  - classes
  - all classes in a module

---

## Installation

### From GitHub

```bash
pip install "decorator-registry @ git+https://github.com/AirborneKiwi/decorator-registry.git@main"
```

Once you create releases, pin a tag instead of `main`:

```bash
pip install "decorator-registry @ git+https://github.com/AirborneKiwi/decorator-registry.git@v1.0"
```

---

## Basic idea

The workflow is always the same:

1. Define your classes normally
2. Register hooks or decorators somewhere else
3. Apply the registry to a class, instance, or module
4. Use the decorated objects as usual

---

## Quickstart

### 1. Define your core class

```python
# core.py
class Calculator:
    def add(self, a, b):
        return a + b
```

### 2. Register hooks in another module

```python
# instrumentation.py
from decorator_registry import register_before, register_after

def always_on() -> bool:
    return True

@register_before(("Calculator", "add"), enabled=always_on)
def log_before(self, *args, **kwargs):
    print("calling add with:", args, kwargs)

@register_after(("Calculator", "add"), enabled=always_on)
def log_after(self, result, *args, **kwargs):
    print("add returned:", result)
```

### 3. Apply decorators

```python
# main.py
import core
import instrumentation  # important: registers hooks on import

from decorator_registry import apply_decorators

apply_decorators(core)

calc = core.Calculator()
print(calc.add(2, 3))
```

### Output

```text
calling add with: (2, 3) {}
add returned: 5
5
```

---

## Registration targets

You can register against a method in two ways.

### By tuple key

```python
@register_before(("Calculator", "add"), enabled=lambda: True)
def hook(self, *args, **kwargs):
    ...
```

This is the simplest and most explicit form.

Tuple targets are matched by class name and method name:

```python
("Calculator", "add")
```

### By method object

```python
from core import Calculator

@register_after(Calculator.add, enabled=lambda: True)
def hook(self, result, *args, **kwargs):
    ...
```

This works when the class is already available where you register the hook.

Use this form when you want tighter coupling to the actual method object instead of string-based lookup.

---

## Hook types

## `before`

Runs before the wrapped method.

```python
from decorator_registry import register_before

class Calculator:
    def add(self, a, b):
        return a + b

@register_before(("Calculator", "add"), enabled=lambda: True)
def before_add(self, *args, **kwargs):
    print("about to add:", args, kwargs)
```

Example:

```python
from decorator_registry import apply_decorators

apply_decorators(Calculator)

calc = Calculator()
print(calc.add(1, 2))
```

Output:

```text
about to add: (1, 2) {}
3
```

---

## `after`

Runs after the wrapped method and receives the result.

```python
from decorator_registry import register_after

class Calculator:
    def add(self, a, b):
        return a + b

@register_after(("Calculator", "add"), enabled=lambda: True)
def after_add(self, result, *args, **kwargs):
    print("result was:", result)
```

Example:

```python
from decorator_registry import apply_decorators

apply_decorators(Calculator)

calc = Calculator()
calc.add(2, 5)
```

Output:

```text
result was: 7
```

---

## `on_error`

Runs if the wrapped method raises an exception.

If the error hook returns `None` or `False`, the original exception is re-raised.

If it returns anything else, that value is used as a fallback result.

```python
from decorator_registry import register_on_error

class Divider:
    def div(self, a, b):
        return a / b

@register_on_error(("Divider", "div"), enabled=lambda: True)
def handle_division_error(self, exc, *args, **kwargs):
    print("caught:", exc)
    return float("inf")
```

Usage:

```python
from decorator_registry import apply_decorators

apply_decorators(Divider)

d = Divider()
print(d.div(10, 2))
print(d.div(10, 0))
```

Output:

```text
5.0
caught: division by zero
inf
```

### Re-raise instead of fallback

```python
@register_on_error(("Divider", "div"), enabled=lambda: True)
def log_only(self, exc, *args, **kwargs):
    print("error:", exc)
    return None
```

Because the hook returns `None`, the original exception is raised again.

---

## Plain decorators

Use `register_decorator(...)` to register a normal decorator.

```python
from functools import wraps
from decorator_registry import register_decorator

def trace(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"TRACE: {func.__qualname__}")
        return func(*args, **kwargs)
    return wrapper

@register_decorator(("Calculator", "add"))
def traced(func):
    return trace(func)
```

Example:

```python
class Calculator:
    def add(self, a, b):
        return a + b

from decorator_registry import apply_decorators

apply_decorators(Calculator)

calc = Calculator()
print(calc.add(3, 4))
```

Output:

```text
TRACE: Calculator.add
7
```

---

## Applying decorators

## Apply to a single instance

```python
calc = Calculator()
apply_decorators(calc)
```

This is useful when you only want to modify one object, or when methods were added dynamically and you want to decorate after the object exists.

## Apply to a class

```python
apply_decorators(Calculator)
```

This updates the class so all instances use the decorated methods.

## Apply to all classes in a module

```python
import my_module
apply_decorators(my_module)
```

When a module is passed, all classes defined in that module are scanned and decorated.

---

## Grouping and feature flags

Each registration can belong to a group. Groups let you enable or disable bundles of behavior.

```python
from decorator_registry import register_after, enable_group, disable_group

GROUP = "logging"

def enabled() -> bool:
    return True

class Calculator:
    def add(self, a, b):
        return a + b

@register_after(("Calculator", "add"), group=GROUP, enabled=enabled)
def log_result(self, result, *args, **kwargs):
    print("result =", result)
```

### Disable the group

```python
disable_group("logging")
apply_decorators(Calculator)
```

### Enable it again

```python
enable_group("logging")
apply_decorators(Calculator)
```

### Important distinction: group state vs `enabled=...`

There are two levels of control:

#### 1. Group enablement

Group state is checked when decorators are applied.

If you change group enablement, call `apply_decorators(...)` again so methods are rebuilt with the new active set.

#### 2. The `enabled=` callback

The `enabled` callback is checked at call time.

That means you can toggle hook behavior dynamically without re-applying decorators.

Example:

```python
DEBUG = False

def debug_enabled():
    return DEBUG

@register_before(("Calculator", "add"), enabled=debug_enabled)
def debug_log(self, *args, **kwargs):
    print("DEBUG:", args, kwargs)
```

Now:

```python
apply_decorators(Calculator)

calc = Calculator()

DEBUG = False
calc.add(1, 2)   # no debug output

DEBUG = True
calc.add(1, 2)   # debug output appears
```

---

## Applying the same hook to many methods

Use the `_many` helpers to attach the same hook to several methods.

```python
from decorator_registry import register_before_many, apply_decorators

class Service:
    def start(self):
        print("start")

    def stop(self):
        print("stop")

@register_before_many(
    [("Service", "start"), ("Service", "stop")],
    group="audit",
    enabled=lambda: True,
)
def audit(self, *args, **kwargs):
    print("audit:", type(self).__name__)
```

Usage:

```python
apply_decorators(Service)

svc = Service()
svc.start()
svc.stop()
```

Output:

```text
audit: Service
start
audit: Service
stop
```

Equivalent helpers exist for:

- `register_before_many(...)`
- `register_after_many(...)`
- `register_on_error_many(...)`

---

## Supported descriptors

The registry supports more than regular instance methods.

## `@staticmethod`

```python
from decorator_registry import register_after, apply_decorators

class MathTools:
    @staticmethod
    def twice(x):
        return x * 2

@register_after(("MathTools", "twice"), enabled=lambda: True)
def after_twice(_self, result, *args, **kwargs):
    print("twice ->", result)

apply_decorators(MathTools)

print(MathTools.twice(5))
```

Output:

```text
twice -> 10
10
```

Note that for a staticmethod there is no meaningful instance, so the first hook argument is just the first positional value passed by the wrapper.

## `@classmethod`

```python
from decorator_registry import register_after, apply_decorators

class User:
    count = 0

    @classmethod
    def create(cls):
        cls.count += 1
        return cls()

@register_after(("User", "create"), enabled=lambda: True)
def after_create(cls, result, *args, **kwargs):
    print("created:", result)
    print("count:", cls.count)

apply_decorators(User)

User.create()
```

Output:

```text
created: <__main__.User object at ...>
count: 1
```

## `@property`

You can attach hooks to a property's getter.

```python
from decorator_registry import register_after, apply_decorators

class Temperature:
    def __init__(self, c):
        self._c = c

    @property
    def fahrenheit(self):
        return self._c * 9 / 5 + 32

@register_after(("Temperature", "fahrenheit"), enabled=lambda: True)
def after_fahrenheit(self, result, *args, **kwargs):
    print("fahrenheit =", result)

apply_decorators(Temperature)

t = Temperature(25)
print(t.fahrenheit)
```

Output:

```text
fahrenheit = 77.0
77.0
```

---

## Detailed example: timing + logging + fallback on one method

This example shows how multiple hook types interact on the same target.

```python
import time
from decorator_registry import (
    register_before,
    register_after,
    register_on_error,
    apply_decorators,
)

class APIClient:
    def fetch(self, item_id):
        if item_id == 0:
            raise ValueError("invalid item id")
        return {"id": item_id, "name": "example"}

def always_on():
    return True

@register_before(("APIClient", "fetch"), enabled=always_on)
def before_fetch(self, *args, **kwargs):
    self._start = time.perf_counter()
    print("fetch starting:", args, kwargs)

@register_after(("APIClient", "fetch"), enabled=always_on)
def after_fetch(self, result, *args, **kwargs):
    elapsed = time.perf_counter() - self._start
    print(f"fetch succeeded in {elapsed:.6f}s -> {result}")

@register_on_error(("APIClient", "fetch"), enabled=always_on)
def fetch_fallback(self, exc, *args, **kwargs):
    elapsed = time.perf_counter() - self._start
    print(f"fetch failed in {elapsed:.6f}s -> {exc}")
    return {"id": None, "name": None, "error": str(exc)}

apply_decorators(APIClient)

client = APIClient()
print(client.fetch(42))
print(client.fetch(0))
```

Possible output:

```text
fetch starting: (42,) {}
fetch succeeded in 0.000012s -> {'id': 42, 'name': 'example'}
{'id': 42, 'name': 'example'}
fetch starting: (0,) {}
fetch failed in 0.000008s -> invalid item id
{'id': None, 'name': None, 'error': 'invalid item id'}
```

---

## Dynamic methods example

One useful pattern is decorating methods that are added to a class dynamically at runtime.

The important rule is:

> Register the hook first or later, but only call `apply_decorators(...)` after the target method actually exists.

Example:

```python
from decorator_registry import apply_decorators, register_after


class DynamicMethodCls:
    def __init__(self, field_name: str):
        self._field_name = field_name
        setattr(self, f"_{field_name}", None)

        # Dynamically add methods to the class
        setattr(
            DynamicMethodCls,
            f"set_{field_name}",
            lambda obj, value: setattr(obj, f"_{field_name}", value),
        )
        setattr(
            DynamicMethodCls,
            f"get_{field_name}",
            lambda obj: getattr(obj, f"_{field_name}"),
        )

    def __str__(self):
        return f"{self._field_name} = {getattr(self, f'_{self._field_name}') }"


obj = DynamicMethodCls("a")

print(obj)          # a = None
obj.set_a(3)
print(obj)          # a = 3


@register_after(("DynamicMethodCls", "set_a"), enabled=lambda: True)
def after_set_a(obj, result, *args, **kwargs):
    print("after set_a")
    print("object:", obj)
    print("args:", args)
    print("kwargs:", kwargs)


apply_decorators(obj)

obj.set_a(5)
print(obj)
```

Output:

```text
a = None
a = 3
after set_a
object: a = 5
args: (5,)
kwargs: {}
a = 5
```

### Why this works

`set_a` does not exist until the instance is created, because it is added dynamically inside `__init__`.

That means the correct order is:

1. create the object so the dynamic method exists
2. register the hook
3. apply decorators

You can also apply directly to the class after the dynamic method has been attached to the class.

---

## Deterministic order

Decorators are applied in this fixed outer-to-inner order:

1. `before`
2. `after`
3. `on_error`
4. plain decorators

This means behavior stays predictable even when registrations come from multiple places.

### Why the order matters

Suppose you register all four kinds for the same method.

- `before` runs first
- then the wrapped call proceeds
- `after` sees the successful result
- `on_error` handles exceptions from the wrapped call
- plain decorators are applied as the innermost registered wrappers

This gives the system a stable composition model.

---

## Real project layout

A typical structure looks like this:

```text
my_project/
├── core.py
├── instrumentation.py
└── main.py
```

### `core.py`

```python
class Worker:
    def run(self, value):
        return value * 2
```

### `instrumentation.py`

```python
from decorator_registry import register_before, register_after

def enabled():
    return True

@register_before(("Worker", "run"), group="debug", enabled=enabled)
def before_run(self, *args, **kwargs):
    print("running with", args, kwargs)

@register_after(("Worker", "run"), group="debug", enabled=enabled)
def after_run(self, result, *args, **kwargs):
    print("got", result)
```

### `main.py`

```python
import core
import instrumentation

from decorator_registry import apply_decorators

apply_decorators(core)

w = core.Worker()
print(w.run(4))
```

Output:

```text
running with (4,) {}
got 8
8
```

---

## API overview

## Registration

```python
register_before(target, *, group="default", enabled=...)
register_after(target, *, group="default", enabled=...)
register_on_error(target, *, group="default", enabled=...)
register_decorator(target, *, group="default")
```

## Multi-target registration

```python
register_before_many(targets, *, group, enabled)
register_after_many(targets, *, group, enabled)
register_on_error_many(targets, *, group, enabled)
```

## Application

```python
decorate_from_registry(obj_or_class, *, groups=None, include_ungrouped=True)
apply_decorators(*targets)
```

## Group control

```python
enable_group(name)
disable_group(name)
set_group_enabled(name, enabled=True)
```

---

## Notes and limitations

- Tuple targets use class-name matching, for example `("MyClass", "method")`
- Method-object targets derive identity from `__qualname__`
- If you dynamically add methods to a class at runtime, call `apply_decorators(...)` only after the method exists
- Re-applying is safe and does not stack duplicate wrappers
- `on_error` only handles exceptions when its own `enabled()` returns `True`
- `after` hooks only run on successful return; they do not run if the target raises
- Properties are handled via their getter (`fget`)

---

## Development

```bash
python -m pip install -U pip
python -m pip install -e .
python -m pytest -q
```
