#!/usr/bin/env python3.16

"""An example of the PEP 813 pretty print protocol.

In this branch the built-in containers have __pprint__() methods, and f-strings have the !p
conversion, so the example uses plain dicts, lists and frozensets and prints them with !p.  The
format spec of a !p conversion names the printer to use, as in f'{obj!p:{printer}}'.  The
vocabulary, describe() and the default printer live in the _pprint module.

The printer supports the width, indent, depth, compact, sort_dicts and expand options.  It leaves out
underscore_numbers.
"""

from _pprint import Expand, Printer


COMMA_SPACE = ', '


# The example: a dict whose keys are frozensets and whose values are dicts of string keys and list
# values.


def build_example():
    return {
        frozenset({'bass', 'guitar'}): {
            'fender': ['precision', 'jazz', 'mustang'],
            'music man': ['stingray', 'bongo', 'sterling'],
        },
        frozenset({'drums', 'cymbals', 'percussion', 'hand drums'}): {
            'ludwig': ['supraphonic', 'black beauty'],
            'zildjian': ['k custom', 'a custom', 'kerope'],
        },
        frozenset(): {},
    }


def main():
    data = build_example()
    cycle = ['loop']
    cycle.append(cycle)
    small = {'fender': ['precision', 'jazz']}

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
        print(f'{obj!p:{Printer(**options)}}')
        print()


if __name__ == '__main__':
    main()
