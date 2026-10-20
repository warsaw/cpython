"""Default implementation of the ``!p`` pretty-print conversion."""

from dataclasses import dataclass
from itertools import chain


ITEMS = sentinel("ITEMS", repr="pprint.ITEMS")
DELEGATE = sentinel("DELEGATE", repr="pprint.DELEGATE")
_MISSING = object()


@dataclass(frozen=True, kw_only=True)
class Layout:
    """Describe the layout used for an object's pretty-printed contents."""

    name: str | None = None
    open: str | None = None
    close: str | None = None
    sep: str = ","
    empty: str | None = None
    recursion: str = "..."
    sortable: bool = False


@dataclass(frozen=True)
class Entry:
    """A key/value pair in an object's pretty-printed contents."""

    key: object
    value: object


def _list_pprint(obj):
    yield Layout(open="[", close="]", recursion="[...]")
    yield from obj


def _dict_pprint(obj):
    yield Layout(open="{", close="}", recursion="{...}", sortable=True)
    yield ITEMS
    yield from obj.items()


def _lookup_pprint(obj):
    """Look up __pprint__ on the type, binding its descriptor to obj."""
    cls = type(obj)
    mro = cls.__mro__
    pprint_owner = next((base for base in mro if "__pprint__" in vars(base)), None)
    if pprint_owner is None:
        return _MISSING
    repr_owner = next(base for base in mro if "__repr__" in vars(base))
    if mro.index(pprint_owner) > mro.index(repr_owner):
        return _MISSING

    method = vars(pprint_owner)["__pprint__"]
    getter = getattr(type(method), "__get__", None)
    if getter is not None:
        return getter(method, obj, cls)
    return method


class Printer:
    """Default printer used by the ``!p`` conversion."""

    def __init__(self, indent=1, width=80, depth=None):
        self._indent = indent
        self._width = width
        self._depth = depth

    def __call__(self, obj):
        return self._format(obj, set(), 0)

    def _format(self, obj, active, level):
        method = _lookup_pprint(obj)
        if method is _MISSING:
            return repr(obj)

        stream = iter(method())
        first = next(stream, _MISSING)
        if first is DELEGATE:
            value = next(stream, _MISSING)
            if value is _MISSING:
                return repr(obj)
            if id(obj) in active:
                return "..."
            active.add(id(obj))
            try:
                return self._format(value, active, level)
            finally:
                active.remove(id(obj))

        if isinstance(first, Layout):
            layout = first
        else:
            layout = Layout()
            if first is not _MISSING:
                stream = chain((first,), stream)

        items = []
        section = None
        for item in stream:
            if item is ITEMS:
                section = ITEMS
            elif section is ITEMS and isinstance(item, tuple) and len(item) == 2:
                items.append(Entry(*item))
            else:
                items.append(item)

        if layout.open is None:
            name = type(obj).__name__ if layout.name is None else layout.name
            if items and all(isinstance(item, Entry) for item in items):
                open_, close = f"{name}({{", "})"
            else:
                open_, close = f"{name}(", ")"
        else:
            open_ = layout.open
            close = "" if layout.close is None else layout.close
        if not items:
            return open_ + close if layout.empty is None else layout.empty

        if id(obj) in active:
            return layout.recursion
        if self._depth is not None and level >= self._depth:
            return open_ + "..." + close

        if layout.sortable:
            try:
                items = sorted(items, key=lambda item: item.key if isinstance(item, Entry) else item)
            except TypeError:
                items = sorted(
                    items,
                    key=lambda item: repr(item.key if isinstance(item, Entry) else item),
                )

        active.add(id(obj))
        try:
            rendered = []
            for item in items:
                if isinstance(item, Entry):
                    rendered.append(
                        f"{self._format(item.key, active, level + self._indent)}: "
                        f"{self._format(item.value, active, level + self._indent)}"
                    )
                else:
                    rendered.append(self._format(item, active, level + self._indent))
        finally:
            active.remove(id(obj))

        flat = open_ + (layout.sep + " ").join(rendered) + close
        if all("\n" not in item for item in rendered) and len(flat) + level <= self._width:
            return flat

        body_indent = " " * (level + self._indent)
        lines = []
        for index, item in enumerate(rendered):
            item_lines = item.splitlines() or [""]
            item_lines[-1] += layout.sep if index < len(rendered) - 1 else ""
            lines.extend(body_indent + line for line in item_lines)
        return open_ + "\n" + "\n".join(lines) + "\n" + " " * level + close
