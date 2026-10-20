#!/usr/bin/env python3.15

"""A pure-Python prototype of the PEP 813 pretty print protocol.

The built-in containers don't have __pprint__() methods yet, so this file stands in for them with
subclasses that add nothing but a __pprint__() method.  Everything else (the vocabulary, describe() and
the printer) is what the pprint module would provide.  It needs Python 3.15 or newer, for the sentinel
builtin.

The printer supports the width, indent, depth, compact, sort_dicts and expand options.  It leaves out
underscore_numbers and splitting long strings across lines.
"""

import enum
import sys

from collections.abc import Set
from dataclasses import dataclass
from itertools import chain


COMMA_SPACE = ', '
EMPTY = ''
NL = '\n'
SPACE = ' '


# The protocol vocabulary.  These would be public names in pprint.

VALUES = sentinel('VALUES', repr='pprint.VALUES')
KWARGS = sentinel('KWARGS', repr='pprint.KWARGS')
ITEMS = sentinel('ITEMS', repr='pprint.ITEMS')
DELEGATE = sentinel('DELEGATE', repr='pprint.DELEGATE')

_MISSING = sentinel('_MISSING')


@dataclass(frozen=True, kw_only=True)
class Layout:
    """The header, describing the brackets and name around the items."""

    name: str | None = None
    open: str | None = None
    close: str | None = None
    sep: str = ','
    empty: str | None = None
    single_close: str | None = None
    recursion: str = '...'
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
    """A stand-in for a keyword value whose comparison to its default raised an exception.

    It has no __pprint__() method, so the printer prints it with its repr().
    """

    def __init__(self, error):
        self._error = error

    def __repr__(self):
        return f'<error comparing to default: {type(self._error).__name__}>'


def _find_pprint(cls):
    """Return the __pprint__() method that applies to instances of cls, or None."""
    mro = cls.__mro__
    pprint_owner = next((base for base in mro if '__pprint__' in vars(base)), None)
    if pprint_owner is None:
        return None

    # An inherited __pprint__() is used only if its class comes no later in the MRO than the class
    # that provides __repr__().  So a subclass that overrides __repr__() keeps its own repr().
    repr_owner = next(base for base in mro if '__repr__' in vars(base))
    if mro.index(pprint_owner) <= mro.index(repr_owner):
        return vars(pprint_owner)['__pprint__']
    return None


def _apply_default(keyword):
    """Return the keyword to show, or None if it is equal to its default and should be hidden."""
    if keyword.default is _MISSING:
        return keyword

    # The comparison, or taking its truth value, can raise.  A NumPy array is the classic case.  Show
    # the field so the failure is visible, but not the value, since we can't tell whether it would
    # have been hidden.
    try:
        same = bool(keyword.value == keyword.default)
    except Exception as error:
        return Keyword(keyword.name, _ComparisonError(error))

    if same:
        return None
    return keyword


def describe(obj):
    """Read one level of an object's description stream.

    Return (None, ()) for a leaf, and (DELEGATE, value) for an object that delegates to value.
    Otherwise return (layout, items), where layout has every field filled in and each item is a
    plain value, a Keyword or an Entry.  This never recurses into the items.
    """
    method = _find_pprint(type(obj))
    if method is None:
        return None, ()

    stream = iter(method(obj))
    first = next(stream, _MISSING)
    if first is DELEGATE:
        value = next(stream, _MISSING)
        # A DELEGATE that is the only item leaves the object to be printed with repr().  Items after
        # the delegated value are ignored.
        if value is _MISSING:
            return None, ()
        return DELEGATE, value

    if isinstance(first, Layout):
        layout = first
    else:
        layout = Layout()
        if first is not _MISSING:
            stream = chain([first], stream)

    # The stream is read permissively.  Section markers may come in any order, and an item that
    # doesn't fit its section is read as a value.
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

    # The default brackets are Name(...), or Name({...}) when every item is a key/value item.
    name = type(obj).__name__ if layout.name is None else layout.name
    if layout.open is None:
        keyed = len(items) > 0 and all(isinstance(item, Entry) for item in items)
        if keyed:
            open_, close = f'{name}({{', '})'
        else:
            open_, close = f'{name}(', ')'
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


# Stand-ins for the built-in types.  Each adds only a __pprint__() method, which wins over the base
# type's __repr__() under the MRO rule.  The brackets match each subclass's own repr(), which for
# dict and list subclasses doesn't include the class name.


class PrettyDict(dict):
    def __pprint__(self):
        yield Layout(open='{', close='}', recursion='{...}', sortable=True)
        yield ITEMS
        yield from self.items()


class PrettyList(list):
    def __pprint__(self):
        yield Layout(open='[', close=']', recursion='[...]')
        yield from self


class PrettyFrozenSet(frozenset):
    def __pprint__(self):
        name = type(self).__name__
        yield Layout(open=f'{name}({{', close='})', empty=f'{name}()', sortable=True)
        yield from self


# The document algebra.  This is private to the printer, and the protocol doesn't depend on it.


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Line:
    """A space, or other flat text, when its group fits on the line, and a line break when not."""

    flat: str = SPACE


@dataclass(frozen=True)
class Concat:
    parts: tuple


@dataclass(frozen=True)
class Nest:
    """Indent the line breaks inside doc by width more than the enclosing indentation."""

    width: int
    doc: object


@dataclass(frozen=True)
class Align:
    """Indent the line breaks inside doc to the column where doc starts."""

    doc: object


@dataclass(frozen=True)
class Group:
    """Lay doc out flat if it fits on the rest of the line, and broken otherwise."""

    doc: object


@dataclass(frozen=True)
class IfBroken:
    """Text that depends on whether the enclosing group is broken."""

    broken: str
    flat: str = EMPTY


@dataclass(frozen=True)
class KeyValue:
    """A key/value item.

    When hang is None, as in expand mode, the value always follows its key.  Otherwise a value whose
    key wraps starts on a new line, indented by hang from the start of the key.
    """

    key: object
    value: object
    hang: int | None


SOFTLINE = Line(EMPTY)
COLON_SPACE = Text(': ')


def _join(separator, docs):
    parts = []
    for index, doc in enumerate(docs):
        if index > 0:
            parts.append(separator)
        parts.append(doc)
    return Concat(tuple(parts))


# The printer.


def _natural_key(item):
    return item.key if isinstance(item, Entry) else item


class Expand(enum.Enum):
    """How a container that doesn't fit on one line is laid out.

    NEVER keeps the items after the open bracket and aligns them under it, as PrettyPrinter does by
    default.  FIT puts each item on its own line, indented, with a trailing separator and the close
    bracket on a line of its own, as ruff and black do.  Each container still stays on one line if it
    fits.  ALWAYS uses the same layout as FIT, but once a container breaks, every non-empty container
    inside it breaks too.  An object that fits on one line is printed on one line in every mode.
    """

    NEVER = enum.auto()
    FIT = enum.auto()
    ALWAYS = enum.auto()

    def __repr__(self):
        return f'{type(self).__name__}.{self.name}'


class Printer:
    """The default printer.  Its instances are printers, called as printer(obj)."""

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
        # The defaults differ from PrettyPrinter's, to stay within PEP 8's line length and come close
        # to the output of ruff and black.
        self._indent = indent
        self._width = width
        self._depth = depth
        self._compact = compact
        self._sort_dicts = sort_dicts
        self._expand = expand

    def __call__(self, obj):
        return _render(self._doc(obj, set(), 0), self._width)

    def _doc(self, obj, active, level):
        # The active set holds the ids of the objects being printed further up, to detect cycles.
        header, items = describe(obj)
        if header is None:
            return Text(repr(obj))

        if header is DELEGATE:
            if id(obj) in active:
                return Text('...')
            active.add(id(obj))
            try:
                return self._doc(items, active, level)
            finally:
                active.discard(id(obj))

        if id(obj) in active:
            return Text(header.recursion)
        if len(items) == 0:
            return Text(header.empty)
        if self._depth is not None and level >= self._depth:
            return Text(f'{header.open}...{header.close}')

        if header.sortable and self._sort_dicts:
            items = self._sorted(items, active, level)

        active.add(id(obj))
        try:
            parts = [self._item_doc(item, active, level + 1) for item in items]
        finally:
            active.discard(id(obj))

        positional = not any(isinstance(item, (Entry, Keyword)) for item in items)
        return self._container_doc(header, parts, positional, level)

    def _sorted(self, items, active, level):
        # Sets compare by inclusion rather than by order, so sorting them in their natural order gives
        # an arbitrary result.  They, and items that can't be compared at all, are sorted by their
        # one-line pretty printed form.  Unlike repr(), that doesn't depend on hash order, since a
        # set's own items are sorted too.
        if not any(isinstance(_natural_key(item), Set) for item in items):
            try:
                return sorted(items, key=_natural_key)
            except TypeError:
                pass
        return sorted(items, key=lambda item: self._flat(_natural_key(item), active, level + 1))

    def _flat(self, obj, active, level):
        # In ALWAYS mode a nested container has no group of its own, so give it one here.
        return _render(Group(self._doc(obj, active, level)), sys.maxsize)

    def _item_doc(self, item, active, level):
        # A key and its value are both one level deeper than their container.
        match item:
            case Entry(key=key, value=value):
                hang = self._indent if self._expand is Expand.NEVER else None
                return KeyValue(
                    self._doc(key, active, level), self._doc(value, active, level), hang
                )
            case Keyword(name=name, value=value):
                return Concat((Text(f'{name}='), self._doc(value, active, level)))
            case _:
                return self._doc(item, active, level)

    def _container_doc(self, header, parts, positional, level):
        close = header.single_close if len(parts) == 1 else header.close
        separator = Text(header.sep)

        if self._expand is Expand.NEVER:
            if self._compact and positional:
                # Waddle's fill: each gap decides on its own whether to break.
                body = _join(Concat((separator, Group(Line()))), parts)
                return Concat((Text(header.open), Align(body), Text(close)))

            body = _join(Concat((separator, Line())), parts)
            return Group(Concat((Text(header.open), Align(body), Text(close))))

        # A broken body always gets a trailing separator, so a single-element tuple needs its ",)"
        # only when it stays flat.
        body = _join(Concat((separator, Line())), parts)
        doc = Concat(
            (
                Text(header.open),
                Nest(self._indent, Concat((SOFTLINE, body, IfBroken(header.sep)))),
                SOFTLINE,
                IfBroken(header.close, flat=close),
            )
        )

        # In ALWAYS mode only the outermost container is a group, so it alone decides whether the
        # object fits on one line.  The containers inside it take on its decision.
        if self._expand is Expand.ALWAYS and level > 0:
            return doc
        return Group(doc)

        if self._compact and positional:
            # Waddle's fill: each gap decides on its own whether to break.
            body = _join(Concat((separator, Group(Line()))), parts)
            return Concat((Text(header.open), Align(body), Text(close)))

        body = _join(Concat((separator, Line())), parts)
        return Group(Concat((Text(header.open), Align(body), Text(close))))


# The renderer, in the style of Wadler and Leijen.


def _render(doc, width):
    out = []
    column = 0
    # Pending work, popped from the end: (indent, flat, doc).
    stack = [(0, False, doc)]
    while len(stack) > 0:
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
            case IfBroken(broken=broken, flat=flat_text):
                text = flat_text if flat else broken
                out.append(text)
                column += len(text)
            case Group(doc=inner):
                fits = flat or _fits(width - column, (indent, True, inner), stack)
                stack.append((indent, fits, inner))
            case KeyValue(key=key, value=value, hang=hang):
                if flat or hang is None:
                    stack.append((indent, flat, value))
                    stack.append((indent, flat, COLON_SPACE))
                    stack.append((indent, flat, key))
                elif isinstance(key, Text) or _fits(
                    width - column, (indent, True, Concat((key, Text(':')))), []
                ):
                    # Hold a key that fits, or can't wrap, on one line, so that a long value can't
                    # make it wrap.
                    stack.append((indent, False, value))
                    stack.append((indent, False, COLON_SPACE))
                    stack.append((indent, True, key))
                else:
                    # Placed after a wrapped key's last line, the value would start far to the
                    # right.  Start it on a new line instead, one level in from the start of the key.
                    hanging = column + hang
                    stack.append((hanging, False, value))
                    stack.append((hanging, False, Line()))
                    stack.append((indent, False, Text(':')))
                    stack.append((indent, False, key))
    return EMPTY.join(out)


def _fits(remaining, first, rest):
    # Does everything up to the next real line break fit in `remaining` columns?
    #
    # Oppen's bounded-lookahead point: never copy `rest`.  Expand pieces onto a small local stack and
    # only reach back into `rest` when that runs dry.  Every step either consumes a column or unwraps
    # a node, and the scan stops at the first real line break or once `remaining` goes negative.  So
    # the work is bounded by the line width, not by the size of the document.
    local = [first]
    index = len(rest)
    while remaining >= 0:
        if len(local) > 0:
            indent, flat, node = local.pop()
        elif index > 0:
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


# The example: a dict whose keys are frozensets and whose values are dicts of string keys and list
# values.


def build_example():
    return PrettyDict(
        {
            PrettyFrozenSet({'bass', 'guitar'}): PrettyDict(
                {
                    'fender': PrettyList(['precision', 'jazz', 'mustang']),
                    'music man': PrettyList(['stingray', 'bongo', 'sterling']),
                }
            ),
            PrettyFrozenSet({'drums', 'cymbals', 'percussion', 'hand drums'}): PrettyDict(
                {
                    'ludwig': PrettyList(['supraphonic', 'black beauty']),
                    'zildjian': PrettyList(['k custom', 'a custom', 'kerope']),
                }
            ),
            PrettyFrozenSet(): PrettyDict(),
        }
    )


def main():
    data = build_example()
    cycle = PrettyList(['loop'])
    cycle.append(cycle)
    small = PrettyDict({'fender': PrettyList(['precision', 'jazz'])})

    demos = [
        (data, {}),
        (data, {'width': 40, 'indent': 1, 'expand': Expand.NEVER}),
        (data, {'width': 40, 'expand': Expand.NEVER}),
        (data, {'width': 40, 'indent': 1}),
        (data, {'width': 40}),
        (data, {'expand': Expand.ALWAYS}),
        (small, {'expand': Expand.ALWAYS}),
        (data, {'depth': 2}),
        (data, {'sort_dicts': False}),
        (cycle, {}),
    ]
    for obj, options in demos:
        label = COMMA_SPACE.join(f'{name}={value!r}' for name, value in options.items())
        print(f'--- Printer({label})')
        print(Printer(**options)(obj))
        print()


if __name__ == '__main__':
    main()
