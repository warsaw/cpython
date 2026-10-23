import collections
import types
import unittest
from dataclasses import dataclass
from typing import NamedTuple

from _pprint import KWARGS, Layout, Printer, decompose


class PprintProtocolTests(unittest.TestCase):
    def test_namedtuple_descriptions(self):
        Point = collections.namedtuple("Point", "x y")

        class TypedPoint(NamedTuple):
            x: int
            y: int

        points = (
            (Point(1, 2), "Point(x=1, y=2)"),
            (TypedPoint(1, 2), "TypedPoint(x=1, y=2)"),
        )
        for point, expected in points:
            with self.subTest(type=type(point).__name__):
                self.assertEqual("\n".join(Printer()(point)), expected)

    def test_builtin_and_collection_descriptions(self):
        class View(collections.abc.MappingView):
            __slots__ = ()

        template = t"{1}"
        objects = [
            {},
            [],
            frozendict({1: 2}),
            collections.OrderedDict(a=1),
            {1: 2}.keys(),
            {1: 2}.values(),
            {1: 2}.items(),
            View({1: 2}),
            (1, 2),
            {1, 2},
            frozenset({1, 2}),
            "a long string that can wrap across lines when pretty printed",
            b"some bytes",
            bytearray(b"some bytes"),
            types.MappingProxyType({1: 2}),
            types.SimpleNamespace(a=1),
            collections.defaultdict(list, {1: 2}),
            collections.Counter("aba"),
            collections.ChainMap({1: 2}),
            collections.deque([1, 2], maxlen=3),
            collections.UserDict({1: 2}),
            collections.UserList([1, 2]),
            collections.UserString("text"),
            template,
            template.interpolations[0],
        ]

        for obj in objects:
            with self.subTest(type=type(obj).__name__):
                self.assertTrue(callable(getattr(type(obj), "__pprint__", None)))
                self.assertIsNotNone(decompose(obj)[0])
                self.assertIsInstance("\n".join(Printer()(obj)), str)

    def test_string_and_bytes_wrap(self):
        text = "one two three four five six seven eight nine ten eleven twelve"
        self.assertIn("\n", "\n".join(Printer(width=20)(text)))
        self.assertTrue("\n".join(Printer()(b"some bytes")).startswith("("))

    def test_printer_call_yields_lines(self):
        printer = Printer(width=20)
        obj = {"first": [1, 2, 3], "second": [4, 5, 6]}
        lines = printer(obj)
        self.assertEqual("\n".join(lines), "\n".join(printer(obj)))

    def test_layout_hints(self):
        default_hints = Layout().hints
        self.assertEqual(default_hints, {})
        with self.assertRaises(TypeError):
            default_hints["html.role"] = "table"

        hints = {"html.role": "table"}

        @dataclass
        class Table:
            headers: list[str]
            rows: list[list[object]]

            def __pprint__(self):
                yield Layout(hints=hints)
                yield KWARGS
                yield "headers", self.headers
                yield "rows", self.rows

        table = Table(["Bass", "Strings"], [["Precision", 4], ["Stingray", 5]])
        layout, _ = decompose(table)
        self.assertIs(layout.hints, hints)
        self.assertEqual(
            "\n".join(Printer()(table)),
            "Table(headers=['Bass', 'Strings'], rows=[['Precision', 4], ['Stingray', 5]])",
        )


if __name__ == "__main__":
    unittest.main()
