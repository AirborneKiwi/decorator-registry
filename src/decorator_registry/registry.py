import inspect
from dataclasses import dataclass
from typing import Any, Callable, Sequence, Tuple, Union, Optional, TypeVar, ParamSpec
from collections import defaultdict
from types import ModuleType
from functools import wraps

Decorator = Callable[[Callable], Callable]
RegistryKey = Union[Callable, Tuple[Union[str, type], str]]

P = ParamSpec("P")
R = TypeVar("R")

BeforeHook = Callable[..., None]                 # (self, *args, **kwargs) -> None
AfterHook  = Callable[..., None]                 # (self, result, *args, **kwargs) -> None
ErrorHook  = Callable[..., None]                 # (self, exc, *args, **kwargs) -> None
EnabledFn  = Callable[[], bool]                  # () -> bool

# ---- decorator/hook types

def before(
    *,
    enabled: EnabledFn,
    before_func: BeforeHook
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Generic decorator factory to execute before_func before_func actually calling func.

    - enabled(): if False, calls through with near-zero overhead.
    - before_func(): runs before the wrapped call
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(self, *args: P.args, **kwargs: P.kwargs) -> R:
            if not enabled():
                return func(self, *args, **kwargs)

            if before_func is not None:
                before_func(self, *args, **kwargs)

            res = func(self, *args, **kwargs)
            return res
        return wrapper
    return decorator


def after(
    *,
    enabled: EnabledFn,
    after_func: AfterHook
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Generic decorator factory to execute after_func after actually calling func.
    Will not catch exceptions!

    - enabled(): if False, calls through with near-zero overhead.
    - after_func(): runs before the wrapped call
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(self, *args: P.args, **kwargs: P.kwargs) -> R:
            if not enabled():
                return func(self, *args, **kwargs)

            res = func(self, *args, **kwargs)

            if after_func is not None:
                after_func(self, res, *args, **kwargs)
            return res
        return wrapper
    return decorator


def on_error(
        *,
        enabled: EnabledFn,
        on_error_func: ErrorHook
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Generic decorator factory to execute on_error_func when func raised an exception.

    - enabled(): if False, calls through with near-zero overhead and will not catch the exception.
    - on_error_func(): runs when the wrapped call raises an exception. When on_error_func returns anything other than None or False, it acts like a fallback result and passes.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(self, *args: P.args, **kwargs: P.kwargs) -> R:
            if not enabled():
                return func(self, *args, **kwargs)

            try:
                return func(self, *args, **kwargs)
            except Exception as exc:
                r = on_error_func(self, exc, *args, **kwargs) if on_error_func is not None else None
                if r is None or r is False:
                    raise  # preserves traceback
                return r  # type: ignore[return-value]
        return wrapper
    return decorator


# ---- grouping + stable identity ----

@dataclass(frozen=True)
class DecoratorSpec:
    decorator: Decorator
    group: str = "default"
    kind: str = "plain"          # "before" | "after" | "on_error" | "plain"
    origin: str = ""             # stable origin id, e.g. "pkg.mod.fn_qualname"

def _origin_id(fn: Callable) -> str:
    return f"{getattr(fn, '__module__', '<unknown>')}.{getattr(fn, '__qualname__', getattr(fn, '__name__', '<anon>'))}"

def _spec_token(spec: DecoratorSpec) -> tuple[str, str, str]:
    # (kind, group, origin) is stable across calls within the same codebase
    return (spec.kind, spec.group, spec.origin)

# ---- registries (Option A style) ----
plain_registry:  dict[Tuple[Union[str, type], str], list[DecoratorSpec]] = defaultdict(list)
before_registry: dict[Tuple[Union[str, type], str], list[DecoratorSpec]] = defaultdict(list)
after_registry:  dict[Tuple[Union[str, type], str], list[DecoratorSpec]] = defaultdict(list)
error_registry:  dict[Tuple[Union[str, type], str], list[DecoratorSpec]] = defaultdict(list)

# group -> enabled?
group_flags: dict[str, bool] = defaultdict(lambda: True)

def set_group_enabled(group: str, enabled: bool = True) -> None:
    group_flags[group] = bool(enabled)

def enable_group(group: str) -> None:
    set_group_enabled(group, True)

def disable_group(group: str) -> None:
    set_group_enabled(group, False)

# ---- helpers ----

def _normalize_key(k: RegistryKey) -> Tuple[Union[str, type], str]:
    if callable(k):
        parts = tuple(k.__qualname__.split("."))
        if len(parts) < 2:
            raise ValueError(f"Cannot infer (Class, method) from {k!r}")
        return (parts[-2], parts[-1])  # ("Context", "balance")
    return tuple(k)

def _apply_decorators(func: Callable, decorators: Sequence[Decorator]) -> Callable:
    # semantics: @d1 @d2 => f = d1(d2(f))
    wrapped = func
    for dec in reversed(list(decorators)):
        wrapped = dec(wrapped)
    return wrapped

# ---- registration ----

def register_decorator(k: RegistryKey, *, group: str = "default"):
    key = _normalize_key(k)
    def decorator(dec: Decorator) -> Decorator:
        plain_registry[key].append(
            DecoratorSpec(decorator=dec, group=group, kind="plain", origin=_origin_id(dec))
        )
        return dec
    return decorator

def register_before(k: RegistryKey, *, group: str = "default", enabled):
    key = _normalize_key(k)
    def deco(hook) -> Callable:
        before_registry[key].append(
            DecoratorSpec(
                decorator=before(enabled=enabled, before_func=hook),
                group=group,
                kind="before",
                origin=_origin_id(hook),
            )
        )
        return hook
    return deco

def register_before_many(targets, *, group, enabled):
    def deco(hook):
        for t in targets:
            register_before(t, group=group, enabled=enabled)(hook)
        return hook
    return deco

def register_after(k: RegistryKey, *, group: str = "default", enabled):
    key = _normalize_key(k)
    def deco(hook) -> Callable:
        after_registry[key].append(
            DecoratorSpec(
                decorator=after(enabled=enabled, after_func=hook),
                group=group,
                kind="after",
                origin=_origin_id(hook),
            )
        )
        return hook
    return deco

def register_after_many(targets, *, group, enabled):
    def deco(hook):
        for t in targets:
            register_after(t, group=group, enabled=enabled)(hook)
        return hook
    return deco

def register_on_error(k: RegistryKey, *, group: str = "default", enabled):
    key = _normalize_key(k)
    def deco(hook) -> Callable:
        error_registry[key].append(
            DecoratorSpec(
                decorator=on_error(enabled=enabled, on_error_func=hook),
                group=group,
                kind="on_error",
                origin=_origin_id(hook),
            )
        )
        return hook
    return deco


def register_on_error_many(targets, *, group, enabled):
    def deco(hook):
        for t in targets:
            register_on_error(t, group=group, enabled=enabled)(hook)
        return hook
    return deco


# ---- decoration ----

def decorate_from_registry(
    obj: Any,
    *,
    groups: Optional[Sequence[str]] = None,
    include_ungrouped: bool = True,
) -> Any:
    cls = obj if isinstance(obj, type) else obj.__class__
    cls_name_keys = {cls.__name__, cls.__qualname__}
    groups_set = set(groups) if groups is not None else None

    def group_allowed(g: str) -> bool:
        if groups_set is not None and g not in groups_set:
            return False
        if g == "default" and not include_ungrouped:
            return False
        return bool(group_flags.get(g, True))

    def collect_specs(key: tuple[Union[str, type], str]) -> list[DecoratorSpec]:
        # Fixed canonical order (outer -> inner):
        # before -> after -> on_error -> plain
        specs: list[DecoratorSpec] = []
        specs += [s for s in before_registry.get(key, []) if group_allowed(s.group)]
        specs += [s for s in after_registry.get(key, [])  if group_allowed(s.group)]
        specs += [s for s in error_registry.get(key, [])  if group_allowed(s.group)]
        specs += [s for s in plain_registry.get(key, [])  if group_allowed(s.group)]
        return specs

    def rebuild(base_func: Callable, specs: list[DecoratorSpec]) -> Callable:
        decorators = [s.decorator for s in specs]
        wrapped = _apply_decorators(base_func, decorators)
        # store stable marker + base for future rebuilds
        wrapped.__registry_original__ = base_func
        wrapped.__registry_applied_tokens__ = tuple(_spec_token(s) for s in specs)
        return wrapped

    def already_current(current_func: Callable, desired_tokens: tuple[tuple[str, str, str], ...]) -> bool:
        return getattr(current_func, "__registry_applied_tokens__", None) == desired_tokens

    for (target_cls, method_name) in set(
        list(before_registry.keys())
        + list(after_registry.keys())
        + list(error_registry.keys())
        + list(plain_registry.keys())
    ):
        # match class
        if isinstance(target_cls, type):
            matches = issubclass(cls, target_cls)
        else:
            matches = target_cls in cls_name_keys
        if not matches:
            continue

        key = (target_cls, method_name)
        specs = collect_specs(key)
        if not specs:
            continue
        desired_tokens = tuple(_spec_token(s) for s in specs)

        try:
            raw_attr = inspect.getattr_static(cls, method_name)
        except AttributeError:
            continue

        # ---- handle descriptors ----

        if isinstance(raw_attr, staticmethod):
            current = raw_attr.__func__
            if already_current(current, desired_tokens):
                continue
            base = getattr(current, "__registry_original__", current)
            wrapped = rebuild(base, specs)
            setattr(cls, method_name, staticmethod(wrapped))

        elif isinstance(raw_attr, classmethod):
            current = raw_attr.__func__
            if already_current(current, desired_tokens):
                continue
            base = getattr(current, "__registry_original__", current)
            wrapped = rebuild(base, specs)
            setattr(cls, method_name, classmethod(wrapped))

        elif isinstance(raw_attr, property):
            fget = raw_attr.fget
            if fget is None:
                continue
            if already_current(fget, desired_tokens):
                continue
            base = getattr(fget, "__registry_original__", fget)
            fget_wrapped = rebuild(base, specs)
            setattr(cls, method_name, property(fget_wrapped, raw_attr.fset, raw_attr.fdel, raw_attr.__doc__))

        else:
            current = raw_attr
            if not callable(current):
                continue
            if already_current(current, desired_tokens):
                continue
            base = getattr(current, "__registry_original__", current)
            wrapped = rebuild(base, specs)
            setattr(cls, method_name, wrapped)

    return obj

# ---- module application unchanged ----

def apply_decorators(*targets):
    for t in targets:
        if isinstance(t, ModuleType):
            _decorate_all_classes_in_module(t)
        else:
            decorate_from_registry(t)

def _decorate_all_classes_in_module(mod: ModuleType):
    for _, cls in inspect.getmembers(mod, inspect.isclass):
        if cls.__module__ == mod.__name__:
            decorate_from_registry(cls)

