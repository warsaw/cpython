import collections
import types
import unittest

from _pprint import Printer, describe


class PprintProtocolTests(unittest.TestCase):
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
                self.assertIsNotNone(describe(obj)[0])
                self.assertIsInstance(Printer()(obj), str)

    def test_string_and_bytes_wrap(self):
        text = "one two three four five six seven eight nine ten eleven twelve"
        self.assertIn("\n", Printer(width=20)(text))
        self.assertTrue(Printer()(b"some bytes").startswith("("))

    def test_printer_lines(self):
        printer = Printer(width=20)
        obj = {"first": [1, 2, 3], "second": [4, 5, 6]}
        lines = printer.pprint_lines(obj)
        self.assertEqual("\n".join(lines), printer(obj))


if __name__ == "__main__":
    unittest.main()
