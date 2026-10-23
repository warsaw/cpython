"""Default implementation of the ``!p`` pretty-print conversion.

The module first builds a document from the object's structure and ``__pprint__``
description, independently of any Printer settings. A Printer then turns that
document into layout instructions using its formatting options, and the
renderer chooses line breaks to produce the output. Layout instructions are an
intermediate tree of text, indentation, grouping, and possible line breaks;
the renderer resolves them into output lines.

It also includes __pprint__ for built in types.
"""

import enum
import collections as _collections
import sys
import types as _types

from collections.abc import Set
from dataclasses import dataclass
from itertools import chain
from string.templatelib import Interpolation as _Interpolation
from string.templatelib import Template as _Template


_EMPTY = ""
_NL = "\n"
_SPACE = " "

VALUES = sentinel("VALUES", repr="pprint.VALUES")
KWARGS = sentinel("KWARGS", repr="pprint.KWARGS")
ITEMS = sentinel("ITEMS", repr="pprint.ITEMS")
DELEGATE = sentinel("DELEGATE", repr="pprint.DELEGATE")
_MISSING = sentinel("_MISSING")


########################################################################
# Object descriptions and structural documents.  Nothing in this section
# knows about a printer object.  It's purely driven by the objects data
# and what their __pprint__ methods return.

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


@dataclass(frozen=True)
class BreakableString:
    """A string value that printers may split across output lines."""

    value: str


@dataclass(frozen=True)
class BreakableBytes:
    """A bytes value that printers may split across output lines."""

    value: bytes


class _ComparisonError:
    """Stand in for a keyword value whose comparison to its default failed."""

    def __init__(self, error):
        self._error = error

    def __repr__(self):
        return f"<error comparing to default: {type(self._error).__name__}>"


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


def decompose(obj):
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
        close = _EMPTY if layout.close is None else layout.close

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
class _ValueDocument:
    value: object


@dataclass(frozen=True)
class _BreakableStringDocument:
    value: str


@dataclass(frozen=True)
class _BreakableBytesDocument:
    value: bytes


@dataclass(frozen=True)
class _LazyDocument:
    value: object
    ancestors: tuple


@dataclass(frozen=True)
class _TextDocument:
    text: str
    source: object = None


@dataclass(frozen=True)
class _EntryDocument:
    key: object
    value: object
    key_source: object


@dataclass(frozen=True)
class _KeywordDocument:
    name: str
    value: object
    source: object


@dataclass(frozen=True)
class _ContainerDocument:
    source: object
    layout: Layout
    items: tuple


def _build_document(obj, ancestors=()):
    """Build a printer-independent document node for *obj*.

    Nested objects' descriptions are read when layout conversion reaches them.
    """
    ancestor_ids = {id(ancestor) for ancestor in ancestors}

    # Breakable values are protocol instructions, not objects to
    # decompose, so they need special handling.
    match obj:
        case BreakableString(value=value):
            return _BreakableStringDocument(value)
        case BreakableBytes(value=value):
            return _BreakableBytesDocument(value)

    header, items = decompose(obj)
    if header is None:
        return _ValueDocument(obj)
    if header is DELEGATE:
        if id(obj) in ancestor_ids:
            return _TextDocument("...", obj)
        return _build_document(items, ancestors + (obj,))

    if id(obj) in ancestor_ids:
        return _TextDocument(header.recursion, obj)
    ancestors = ancestors + (obj,)
    documents = []
    for item in items:
        match item:
            case Entry(key=key, value=value):
                documents.append(
                    _EntryDocument(
                        _LazyDocument(key, ancestors),
                        _LazyDocument(value, ancestors),
                        key,
                    )
                )
            case Keyword(name=name, value=value):
                documents.append(
                    _KeywordDocument(name, _LazyDocument(value, ancestors), item)
                )
            case _:
                documents.append(_LazyDocument(item, ancestors))
    return _ContainerDocument(obj, header, tuple(documents))

# End of object descriptions and structural documents.
########################################################################


########################################################################
# Printer formatting and rendering.
#
# A layout document is a tree of text and layout instructions. It represents
# the output before line breaks are chosen; the renderer turns it into lines.
@dataclass(frozen=True)
class _Text:
    text: str


@dataclass(frozen=True)
class _Line:
    """Flat text when a group fits, or a line break otherwise."""

    flat: str = _SPACE


@dataclass(frozen=True)
class _Concat:
    parts: tuple


@dataclass(frozen=True)
class _Nest:
    width: int
    doc: object


@dataclass(frozen=True)
class _Align:
    doc: object


@dataclass(frozen=True)
class _Group:
    doc: object


@dataclass(frozen=True)
class _IfBroken:
    broken: str
    flat: str = _EMPTY


@dataclass(frozen=True)
class _KeyValue:
    key: object
    value: object
    hang: int | None


_SOFTLINE = _Line(_EMPTY)
_COLON_SPACE = _Text(": ")


def _join(separator, docs):
    parts = []
    for index, doc in enumerate(docs):
        if index:
            parts.append(separator)
        parts.append(doc)
    return _Concat(tuple(parts))


class Expand(enum.Enum):
    """Policy for laying out containers that do not fit on one line."""

    NEVER = enum.auto()
    FIT = enum.auto()
    ALWAYS = enum.auto()

    def __repr__(self):
        return f"{type(self).__name__}.{self.name}"


@dataclass(frozen=True)
class _FormatOptions:
    indent: int
    width: int
    depth: int | None
    compact: bool
    sort_dicts: bool
    expand: Expand


class Printer:
    """Default printer. Calling an instance yields the formatted lines."""

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
        self._options = _FormatOptions(
            indent, width, depth, compact, sort_dicts, expand
        )

    def __call__(self, obj):
        """Yield the formatted lines for *obj*."""
        # Build the complete structural document before applying printer settings.
        document = _build_document(obj)
        layout_document = _layout_document(document, 0, self._options)
        yield from _render_lines(layout_document, self._options.width)


def _literal_parts(parts, indent):
    docs = [_Text(part) for part in parts]
    if len(docs) == 1:
        return docs[0]
    body = _join(_Line(), docs)
    return _Group(
        _Concat(
            (
                _Text("("),
                _Nest(indent, _Concat((_SOFTLINE, body))),
                _SOFTLINE,
                _Text(")"),
            )
        )
    )


def _string_document(obj, level, width, indent):
    if not obj:
        return _Text(repr(obj))
    import re

    width = max(1, width - level - indent)
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
        return _Text(repr(obj))
    return _literal_parts(chunks, indent)


def _bytes_document(obj, level, width, indent):
    if len(obj) <= 4:
        return _Text(repr(obj))
    width = max(1, width - level - indent)
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
        doc = _Text(repr(obj))
        if level == 0:
            return _Concat((_Text("("), doc, _Text(")")))
        return doc
    return _literal_parts(chunks, indent)


def _layout_document(document, level, options):
    """Apply printer options to a structural document and return layout instructions."""
    match document:
        case _LazyDocument(value=value, ancestors=ancestors):
            return _layout_document(
                _build_document(value, ancestors), level, options
            )
        case _TextDocument(text=text):
            return _Text(text)
        case _BreakableStringDocument(value=value):
            return _string_document(value, level, options.width, options.indent)
        case _BreakableBytesDocument(value=value):
            return _bytes_document(value, level, options.width, options.indent)
        case _ValueDocument(value=value):
            return _Text(repr(value))
        case _ContainerDocument(layout=header, items=items):
            if not items:
                return _Text(header.empty)
            if options.depth is not None and level >= options.depth:
                return _Text(f"{header.open}...{header.close}")

            if header.sortable and options.sort_dicts:
                items = _sorted_documents(items, level, options)
            parts = [_item_document(item, level + 1, options) for item in items]
            positional = not any(
                isinstance(item, (_EntryDocument, _KeywordDocument)) for item in items
            )
            return _container_document(header, parts, positional, level, options)
        case _:
            raise TypeError(f"unexpected document node: {document!r}")


def _document_source(document):
    match document:
        case _ValueDocument(value=value):
            return value
        case _BreakableStringDocument(value=value):
            return value
        case _BreakableBytesDocument(value=value):
            return value
        case _ContainerDocument(source=value):
            return value
        case _LazyDocument(value=value):
            return value
        case _EntryDocument(key_source=value):
            return value
        case _KeywordDocument(source=value):
            return value
        case _TextDocument(source=value):
            return value
        case _:
            raise TypeError(f"unexpected structural document: {document!r}")


def _document_sort_key(item):
    """Return an entry's key, or the item itself, for sorting."""
    return item.key if isinstance(item, _EntryDocument) else item


def _sorted_documents(items, level, options):
    if not any(
        isinstance(_document_source(_document_sort_key(item)), Set) for item in items
    ):
        try:
            return sorted(
                items,
                key=lambda item: _document_source(_document_sort_key(item)),
            )
        except TypeError:
            pass
    return sorted(
        items,
        key=lambda item: _flat_document(_document_sort_key(item), level + 1, options),
    )


def _flat_document(document, level, options):
    layout_document = _layout_document(document, level, options)
    return _NL.join(_render_lines(_Group(layout_document), sys.maxsize))


def _item_document(item, level, options):
    match item:
        case _EntryDocument(key=key, value=value):
            hang = options.indent if options.expand is Expand.NEVER else None
            return _KeyValue(
                _layout_document(key, level, options),
                _layout_document(value, level, options),
                hang,
            )
        case _KeywordDocument(name=name, value=value):
            return _Concat(
                (_Text(f"{name}="), _layout_document(value, level, options))
            )
        case _:
            return _layout_document(item, level, options)


def _container_document(header, parts, positional, level, options):
    close = header.single_close if len(parts) == 1 else header.close
    separator = _Text(header.sep)

    if options.expand is Expand.NEVER:
        if options.compact and positional:
            body = _join(_Concat((separator, _Group(_Line()))), parts)
            return _Concat((_Text(header.open), _Align(body), _Text(close)))
        body = _join(_Concat((separator, _Line())), parts)
        return _Group(_Concat((_Text(header.open), _Align(body), _Text(close))))

    body = _join(_Concat((separator, _Line())), parts)
    doc = _Concat(
        (
            _Text(header.open),
            _Nest(options.indent, _Concat((_SOFTLINE, body, _IfBroken(header.sep)))),
            _SOFTLINE,
            _IfBroken(header.close, flat=close),
        )
    )
    if options.expand is Expand.ALWAYS and level > 0:
        return doc
    return _Group(doc)


def _render_lines(doc, width):
    out = []
    column = 0
    # Each pending item is (indent, flat, node): nodes come from the layout
    # document, while indent and flat carry the rendering context. Compound
    # nodes add their children to this stack as they are traversed. The stack
    # can grow to O(N), where N is the number of layout nodes: a deep document
    # leaves pending nodes at each level, while a wide _Concat adds many at once.
    stack = [(0, False, doc)]
    while stack:
        indent, flat, node = stack.pop()
        match node:
            case _Text(text=text):
                parts = text.split(_NL)
                for part in parts[:-1]:
                    out.append(part)
                    yield _EMPTY.join(out)
                    out.clear()
                out.append(parts[-1])
                column = len(parts[-1]) if len(parts) > 1 else column + len(text)
            case _Line(flat=flat_text):
                if flat:
                    out.append(flat_text)
                    column += len(flat_text)
                else:
                    yield _EMPTY.join(out)
                    out.clear()
                    out.append(_SPACE * indent)
                    column = indent
            case _Concat(parts=parts):
                stack.extend((indent, flat, part) for part in reversed(parts))
            case _Nest(width=extra, doc=inner):
                stack.append((indent + extra, flat, inner))
            case _Align(doc=inner):
                stack.append((column, flat, inner))
            case _Group(doc=inner):
                fits = flat or _fits(width - column, (indent, True, inner), stack)
                stack.append((indent, fits, inner))
            case _IfBroken(broken=broken, flat=flat_text):
                text = flat_text if flat else broken
                out.append(text)
                column += len(text)
            case _KeyValue(key=key, value=value, hang=hang):
                if flat or hang is None:
                    stack.append((indent, flat, value))
                    stack.append((indent, flat, _COLON_SPACE))
                    stack.append((indent, flat, key))
                elif isinstance(key, _Text) or _fits(
                    width - column, (indent, True, _Concat((key, _Text(":")))), []
                ):
                    stack.append((indent, False, value))
                    stack.append((indent, False, _COLON_SPACE))
                    stack.append((indent, True, key))
                else:
                    hanging = column + hang
                    stack.append((hanging, False, value))
                    stack.append((hanging, False, _Line()))
                    stack.append((indent, False, _Text(":")))
                    stack.append((indent, False, key))
    yield _EMPTY.join(out)


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
            case _Text(text=text):
                remaining -= len(text)
            case _Line(flat=flat_text):
                if flat:
                    remaining -= len(flat_text)
                else:
                    return True
            case _Concat(parts=parts):
                local.extend((indent, flat, part) for part in reversed(parts))
            case _Nest(doc=inner) | _Align(doc=inner) | _Group(doc=inner):
                local.append((indent, flat, inner))
            case _IfBroken(broken=broken, flat=flat_text):
                remaining -= len(flat_text if flat else broken)
            case _KeyValue(key=key, value=value):
                local.append((indent, flat, _Concat((key, _COLON_SPACE, value))))
    return False

# End of printer formatting and rendering.
########################################################################

########################################################################
# __pprint__ implementations for built-in and internal types.

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


def _str_pprint(obj):
    yield DELEGATE
    yield BreakableString(obj)


def _bytes_pprint(obj):
    yield DELEGATE
    yield BreakableBytes(obj)


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


# End of __pprint__ implementations.
########################################################################

