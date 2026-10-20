"""Default implementation of the ``!p`` pretty-print conversion."""

import enum
import collections as _collections
import sys
import types as _types

from collections.abc import Set
from dataclasses import dataclass
from itertools import chain
from string.templatelib import Interpolation as _Interpolation
from string.templatelib import Template as _Template


COMMA_SPACE = ", "
EMPTY = ""
NL = "\n"
SPACE = " "

VALUES = sentinel("VALUES", repr="pprint.VALUES")
KWARGS = sentinel("KWARGS", repr="pprint.KWARGS")
ITEMS = sentinel("ITEMS", repr="pprint.ITEMS")
DELEGATE = sentinel("DELEGATE", repr="pprint.DELEGATE")
_MISSING = sentinel("_MISSING")


@dataclass(frozen=True, kw_only=True)
class Layout:
    """Describe an object's brackets, separator, and recursion marker."""

    name: str | None = None
    open: str | None = None
    close: str | None = None
    sep: str = ","
    empty: str | None = None
    single_close: str | None = None
    recursion: str = "..."
    sortable: bool = False


@dataclass(frozen=True)
class Keyword:
    """A keyword item, printed as name=value."""

    name: str
    value: object
    default: object = _MISSING


@dataclass(frozen=True)
class Entry:
    """A key/value item, printed as key: value."""

    key: object
    value: object


class _ComparisonError:
    """Stand in for a keyword value whose comparison to its default failed."""

    def __init__(self, error):
        self._error = error

    def __repr__(self):
        return f"<error comparing to default: {type(self._error).__name__}>"


def _list_pprint(obj):
    yield Layout(open="[", close="]", recursion="[...]")
    yield from obj


def _dict_pprint(obj):
    yield Layout(open="{", close="}", recursion="{...}", sortable=True)
    yield ITEMS
    yield from obj.items()


def _frozendict_pprint(obj):
    name = type(obj).__name__
    yield Layout(
        open=f"{name}({{", close="})", empty=f"{name}()", sortable=True
    )
    yield ITEMS
    yield from obj.items()


def _ordered_dict_pprint(obj):
    name = type(obj).__name__
    yield Layout(open=f"{name}([", close="])", empty=f"{name}()")
    yield from obj.items()


def _dict_view_pprint(obj):
    name = type(obj).__name__
    yield Layout(open=f"{name}([", close="])", sortable=True)
    yield from obj


def _mapping_view_pprint(obj):
    yield Layout(open=f"{type(obj).__name__}(", close=")")
    yield obj._mapping


def _tuple_pprint(obj):
    yield Layout(open="(", close=")", single_close=",)")
    yield from obj


def _set_pprint(obj):
    if type(obj) is set:
        yield Layout(open="{", close="}", empty="set()", sortable=True)
    else:
        name = type(obj).__name__
        yield Layout(
            open=f"{name}({{", close="})", empty=f"{name}()", sortable=True
        )
    yield from obj


def _frozen_set_pprint(obj):
    name = type(obj).__name__
    yield Layout(
        open=f"{name}({{", close="})", empty=f"{name}()", sortable=True
    )
    yield from obj


@dataclass(frozen=True)
class _Literal:
    text: str


def _str_pprint(obj):
    yield DELEGATE
    yield _Literal(repr(obj))


def _bytes_pprint(obj):
    yield DELEGATE
    yield _Literal(repr(obj))


def _bytearray_pprint(obj):
    yield Layout(open="bytearray(", close=")")
    yield bytes(obj)


def _mappingproxy_pprint(obj):
    yield Layout(open="mappingproxy(", close=")")
    yield dict(obj)


def _namespace_pprint(obj):
    name = "namespace" if type(obj) is _types.SimpleNamespace else type(obj).__name__
    yield Layout(open=f"{name}(", close=")")
    yield KWARGS
    yield from obj.__dict__.items()


def _defaultdict_pprint(obj):
    yield Layout(open=f"{type(obj).__name__}(", close=")")
    yield obj.default_factory
    yield dict(obj)


def _counter_pprint(obj):
    name = type(obj).__name__
    yield Layout(open=f"{name}({{", close="})", empty=f"{name}()")
    yield ITEMS
    yield from obj.most_common()


def _chainmap_pprint(obj):
    yield Layout(open=f"{type(obj).__name__}(", close=")", empty=repr(obj))
    yield from obj.maps


def _deque_pprint(obj):
    close = "])" if obj.maxlen is None else f"], maxlen={obj.maxlen!r})"
    yield Layout(open=f"{type(obj).__name__}([", close=close)
    yield from obj


def _user_container_pprint(obj):
    yield DELEGATE
    yield obj.data


def _template_pprint(obj):
    name = type(obj).__name__
    yield Layout(open=f"{name}(", close=")")
    yield KWARGS
    yield "strings", obj.strings
    yield "interpolations", obj.interpolations


def _interpolation_pprint(obj):
    yield Layout(open=f"{type(obj).__name__}(", close=")")
    yield KWARGS
    yield "value", obj.value
    yield "expression", obj.expression
    yield "conversion", obj.conversion
    yield "format_spec", obj.format_spec


def _find_pprint(cls):
    """Return the __pprint__ method that applies to instances of cls, or None."""
    mro = cls.__mro__
    pprint_owner = next((base for base in mro if "__pprint__" in vars(base)), None)
    if pprint_owner is None:
        return None
    repr_owner = next(base for base in mro if "__repr__" in vars(base))
    if mro.index(pprint_owner) <= mro.index(repr_owner):
        return vars(pprint_owner)["__pprint__"]
    return None


def _apply_default(keyword):
    """Hide a keyword if its value equals its declared default."""
    if keyword.default is _MISSING:
        return keyword
    try:
        same = bool(keyword.value == keyword.default)
    except Exception as error:
        return Keyword(keyword.name, _ComparisonError(error))
    return None if same else keyword


def describe(obj):
    """Read one level of an object's pretty-print description stream."""
    method = _find_pprint(type(obj))
    if method is None:
        return None, ()
    stream = iter(method(obj))

    first = next(stream, _MISSING)
    if first is DELEGATE:
        value = next(stream, _MISSING)
        return (DELEGATE, value) if value is not _MISSING else (None, ())

    if isinstance(first, Layout):
        layout = first
    else:
        layout = Layout()
        if first is not _MISSING:
            stream = chain((first,), stream)

    items = []
    section = VALUES
    for item in stream:
        if item is VALUES or item is KWARGS or item is ITEMS:
            section = item
            continue

        match item:
            case tuple((str() as name, value)) if section is KWARGS:
                item = Keyword(name, value)
            case tuple((str() as name, value, default)) if section is KWARGS:
                item = Keyword(name, value, default)
            case tuple((key, value)) if section is ITEMS:
                item = Entry(key, value)

        if isinstance(item, Keyword):
            item = _apply_default(item)
            if item is None:
                continue
        items.append(item)

    name = type(obj).__name__ if layout.name is None else layout.name
    if layout.open is None:
        keyed = len(items) > 0 and all(isinstance(item, Entry) for item in items)
        if keyed:
            open_, close = f"{name}({{", "})"
        else:
            open_, close = f"{name}(", ")"
    else:
        open_ = layout.open
        close = EMPTY if layout.close is None else layout.close

    filled = Layout(
        name=name,
        open=open_,
        close=close,
        sep=layout.sep,
        empty=open_ + close if layout.empty is None else layout.empty,
        single_close=close if layout.single_close is None else layout.single_close,
        recursion=layout.recursion,
        sortable=layout.sortable,
    )
    return filled, items


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Line:
    """Flat text when a group fits, or a line break otherwise."""

    flat: str = SPACE


@dataclass(frozen=True)
class Concat:
    parts: tuple


@dataclass(frozen=True)
class Nest:
    width: int
    doc: object


@dataclass(frozen=True)
class Align:
    doc: object


@dataclass(frozen=True)
class Group:
    doc: object


@dataclass(frozen=True)
class IfBroken:
    broken: str
    flat: str = EMPTY


@dataclass(frozen=True)
class KeyValue:
    key: object
    value: object
    hang: int | None


SOFTLINE = Line(EMPTY)
COLON_SPACE = Text(": ")


def _join(separator, docs):
    parts = []
    for index, doc in enumerate(docs):
        if index:
            parts.append(separator)
        parts.append(doc)
    return Concat(tuple(parts))


class Expand(enum.Enum):
    """Policy for laying out containers that do not fit on one line."""

    NEVER = enum.auto()
    FIT = enum.auto()
    ALWAYS = enum.auto()

    def __repr__(self):
        return f"{type(self).__name__}.{self.name}"


def _natural_key(item):
    return item.key if isinstance(item, Entry) else item


class Printer:
    """Default printer. Instances are callable as printer(obj)."""

    def __init__(
        self,
        indent=4,
        width=78,
        depth=None,
        *,
        compact=False,
        sort_dicts=True,
        expand=Expand.FIT,
    ):
        self._indent = indent
        self._width = width
        self._depth = depth
        self._compact = compact
        self._sort_dicts = sort_dicts
        self._expand = expand

    def __call__(self, obj):
        return _render(self._doc(obj, set(), 0), self._width)

    def _literal_parts(self, parts, level):
        docs = [Text(part) for part in parts]
        if len(docs) == 1:
            return docs[0]
        body = _join(Line(), docs)
        return Group(
            Concat(
                (
                    Text("("),
                    Nest(self._indent, Concat((SOFTLINE, body))),
                    SOFTLINE,
                    Text(")"),
                )
            )
        )

    def _string_doc(self, obj, level):
        if not obj:
            return Text(repr(obj))
        import re

        width = max(1, self._width - level - self._indent)
        chunks = []
        for line in obj.splitlines(True):
            if len(repr(line)) <= width:
                chunks.append(repr(line))
                continue
            pieces = re.findall(r"\S*\s*", line)
            if pieces and not pieces[-1]:
                pieces.pop()
            current = ""
            for part in pieces:
                candidate = current + part
                if current and len(repr(candidate)) > width:
                    chunks.append(repr(current))
                    current = part
                else:
                    current = candidate
            if current:
                chunks.append(repr(current))
        if len(chunks) <= 1:
            return Text(repr(obj))
        return self._literal_parts(chunks, level)

    def _bytes_doc(self, obj, level):
        if len(obj) <= 4:
            return Text(repr(obj))
        width = max(1, self._width - level - self._indent)
        chunks = []
        current = b""
        for index in range(0, len(obj), 4):
            part = obj[index:index + 4]
            candidate = current + part
            if len(repr(candidate)) > width and current:
                chunks.append(repr(current))
                current = part
            else:
                current = candidate
        if current:
            chunks.append(repr(current))
        if len(chunks) == 1:
            doc = Text(repr(obj))
            if level == 0:
                return Concat((Text("("), doc, Text(")")))
            return doc
        return self._literal_parts(chunks, level)

    def _doc(self, obj, active, level):
        if isinstance(obj, _Literal):
            return Text(obj.text)
        pprint_owner = next(
            (base for base in type(obj).__mro__ if "__pprint__" in vars(base)), None
        )
        if pprint_owner is str and _find_pprint(type(obj)) is not None:
            return self._string_doc(obj, level)
        if pprint_owner is bytes and _find_pprint(type(obj)) is not None:
            return self._bytes_doc(obj, level)
        header, items = describe(obj)
        if header is None:
            return Text(repr(obj))
        if header is DELEGATE:
            if id(obj) in active:
                return Text("...")
            active.add(id(obj))
            try:
                return self._doc(items, active, level)
            finally:
                active.discard(id(obj))

        if id(obj) in active:
            return Text(header.recursion)
        if not items:
            return Text(header.empty)
        if self._depth is not None and level >= self._depth:
            return Text(f"{header.open}...{header.close}")

        if header.sortable and self._sort_dicts:
            items = self._sorted(items, active, level)

        active.add(id(obj))
        try:
            parts = [self._item_doc(item, active, level + 1) for item in items]
        finally:
            active.remove(id(obj))

        positional = not any(isinstance(item, (Entry, Keyword)) for item in items)
        return self._container_doc(header, parts, positional, level)

    def _sorted(self, items, active, level):
        if not any(isinstance(_natural_key(item), Set) for item in items):
            try:
                return sorted(items, key=_natural_key)
            except TypeError:
                pass
        return sorted(items, key=lambda item: self._flat(_natural_key(item), active, level + 1))

    def _flat(self, obj, active, level):
        return _render(Group(self._doc(obj, active, level)), sys.maxsize)

    def _item_doc(self, item, active, level):
        match item:
            case Entry(key=key, value=value):
                hang = self._indent if self._expand is Expand.NEVER else None
                return KeyValue(
                    self._doc(key, active, level), self._doc(value, active, level), hang
                )
            case Keyword(name=name, value=value):
                return Concat((Text(f"{name}="), self._doc(value, active, level)))
            case _:
                return self._doc(item, active, level)

    def _container_doc(self, header, parts, positional, level):
        close = header.single_close if len(parts) == 1 else header.close
        separator = Text(header.sep)

        if self._expand is Expand.NEVER:
            if self._compact and positional:
                body = _join(Concat((separator, Group(Line()))), parts)
                return Concat((Text(header.open), Align(body), Text(close)))
            body = _join(Concat((separator, Line())), parts)
            return Group(Concat((Text(header.open), Align(body), Text(close))))

        body = _join(Concat((separator, Line())), parts)
        doc = Concat(
            (
                Text(header.open),
                Nest(self._indent, Concat((SOFTLINE, body, IfBroken(header.sep)))),
                SOFTLINE,
                IfBroken(header.close, flat=close),
            )
        )
        if self._expand is Expand.ALWAYS and level > 0:
            return doc
        return Group(doc)


def _render(doc, width):
    out = []
    column = 0
    stack = [(0, False, doc)]
    while stack:
        indent, flat, node = stack.pop()
        match node:
            case Text(text=text):
                out.append(text)
                column += len(text)
            case Line(flat=flat_text):
                if flat:
                    out.append(flat_text)
                    column += len(flat_text)
                else:
                    out.append(NL + SPACE * indent)
                    column = indent
            case Concat(parts=parts):
                stack.extend((indent, flat, part) for part in reversed(parts))
            case Nest(width=extra, doc=inner):
                stack.append((indent + extra, flat, inner))
            case Align(doc=inner):
                stack.append((column, flat, inner))
            case Group(doc=inner):
                fits = flat or _fits(width - column, (indent, True, inner), stack)
                stack.append((indent, fits, inner))
            case IfBroken(broken=broken, flat=flat_text):
                text = flat_text if flat else broken
                out.append(text)
                column += len(text)
            case KeyValue(key=key, value=value, hang=hang):
                if flat or hang is None:
                    stack.append((indent, flat, value))
                    stack.append((indent, flat, COLON_SPACE))
                    stack.append((indent, flat, key))
                elif isinstance(key, Text) or _fits(
                    width - column, (indent, True, Concat((key, Text(":")))), []
                ):
                    stack.append((indent, False, value))
                    stack.append((indent, False, COLON_SPACE))
                    stack.append((indent, True, key))
                else:
                    hanging = column + hang
                    stack.append((hanging, False, value))
                    stack.append((hanging, False, Line()))
                    stack.append((indent, False, Text(":")))
                    stack.append((indent, False, key))
    return EMPTY.join(out)


def _fits(remaining, first, rest):
    local = [first]
    index = len(rest)
    while remaining >= 0:
        if local:
            indent, flat, node = local.pop()
        elif index:
            index -= 1
            indent, flat, node = rest[index]
        else:
            return True

        match node:
            case Text(text=text):
                remaining -= len(text)
            case Line(flat=flat_text):
                if flat:
                    remaining -= len(flat_text)
                else:
                    return True
            case Concat(parts=parts):
                local.extend((indent, flat, part) for part in reversed(parts))
            case Nest(doc=inner) | Align(doc=inner) | Group(doc=inner):
                local.append((indent, flat, inner))
            case IfBroken(broken=broken, flat=flat_text):
                remaining -= len(flat_text if flat else broken)
            case KeyValue(key=key, value=value):
                local.append((indent, flat, Concat((key, COLON_SPACE, value))))
    return False
