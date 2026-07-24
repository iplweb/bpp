#!/usr/bin/env python
"""Wykrywa wieloliniowe komentarze Django ``{# ... #}``.

Django tokenizuje komentarze regexpem ``{#.*?#}`` BEZ flagi ``re.DOTALL``
(patrz ``django.template.base.tag_re``), więc ``.*?`` nigdy nie przekracza
znaku nowej linii. ``{#`` które nie ma zamykającego ``#}`` w tej samej
linii NIE zostaje rozpoznane jako komentarz — jego treść wycieka jako
zwykły tekst do wyrenderowanego HTML-u.

Ten hook flaguje każdą linię, która otwiera komentarz ``{#`` bez zamknięcia
``#}`` w tej samej linii. Rozwiązanie: każdą linię komentarza domknąć
osobnym ``{# ... #}`` albo użyć bloku ``{% comment %}...{% endcomment %}``.

Wywoływany przez pre-commit z listą plików w argv; zwraca kod !=0 gdy
znajdzie problem.
"""

from __future__ import annotations

import re
import sys

# ``{#`` które NIE jest częścią ``{{#`` (składnia Mustache/Handlebars,
# np. ``{{#clickURL}}`` w szablonach powiadomień) — negatywny lookbehind
# na pojedynczy ``{``.
OPEN_RE = re.compile(r"(?<!\{)\{#")


def find_unterminated_comment_lines(text: str) -> list[int]:
    """Zwraca 1-indeksowane numery linii z niezamkniętym ``{#``."""
    bad: list[int] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        pos = 0
        while True:
            m = OPEN_RE.search(line, pos)
            if m is None:
                break
            close = line.find("#}", m.end())
            if close == -1:
                bad.append(lineno)
                break  # jeden błąd na linię wystarczy
            pos = close + 2
    return bad


def main(argv: list[str]) -> int:
    problems: list[tuple[str, int]] = []
    for path in argv:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"{path}: nie można odczytać pliku: {exc}", file=sys.stderr)
            return 2
        for lineno in find_unterminated_comment_lines(text):
            problems.append((path, lineno))

    if not problems:
        return 0

    print(
        "Wieloliniowy komentarz Django `{# ... #}` — treść WYCIEKNIE do "
        "wyrenderowanego HTML-u.\n"
        "Napraw: każdą linię domknij osobnym `{# ... #}`, albo użyj "
        "`{% comment %}...{% endcomment %}`.\n",
        file=sys.stderr,
    )
    for path, lineno in problems:
        print(f"  {path}:{lineno}: niezamknięte `{{#` w tej linii", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
