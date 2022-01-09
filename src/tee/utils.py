from io import StringIO
from operator import neg
from typing import Iterable


class TeeIO(StringIO):
    def __init__(self, original, *args, **kw):
        super().__init__(*args, **kw)
        self.original = original

    def write(self, *args, **kw):
        try:
            self.original.write(*args, **kw)
        finally:
            return super().write(*args, **kw)

    def writelines(self, __lines: Iterable[str]) -> None:
        try:
            self.original.writelines(__lines)
        finally:
            return super().writelines(__lines)


def last_n_lines(s, nlines):
    if s is None:
        return
    lines = s.split("\n")
    prefix = ""
    if len(lines) > nlines:
        prefix = "[...]\n"
    return prefix + "\n".join(lines[neg(nlines) :])
