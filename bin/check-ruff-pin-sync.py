#!/usr/bin/env python
"""Pilnuje, żeby ruff był przypięty do tej samej wersji w DWÓCH miejscach.

Ruff żyje w tym repo pod dwoma pinami, które muszą być równe:

* ``pyproject.toml`` → ``"ruff==X.Y.Z"`` w extrze ``[dev]`` — to ruff,
  którego dostaje deweloper przez ``uv run ruff``.
* ``.pre-commit-config.yaml`` → ``rev: vX.Y.Z`` przy repo
  ``astral-sh/ruff-pre-commit`` — to ruff, którego uruchamia ``pre-commit``
  ORAZ job CI „Lint changed files" (odpala ``uvx pre-commit run ruff``).

To są fizycznie DWA RÓŻNE binaria: pre-commit nie używa ruffa z
``pyproject.toml``, tylko buduje własne izolowane środowisko z wheela
pobranego dla tagu spod ``rev:``. Gdy piny się rozjadą, ``uv run ruff
check`` i CI mogą dać sprzeczne wyniki — dokładnie to się już zdarzyło
(niższy ``rev`` przepuścił układ importów ``I001``, który ruff w CI
odrzucił; lokalnie niewidoczne aż do czerwonego Actions).

Dependabot tego sprzężenia nie widzi — ``.github/dependabot.yml`` śledzi
ekosystemy ``uv`` / ``github-actions`` / ``docker``, więc podbija wyłącznie
pin w ``pyproject.toml``. Bez tej bramki KAŻDY bump ruffa rozjeżdża piny,
a zasada jest pilnowana jedynie komentarzem w pliku.

Uruchamiany bez argumentów (``always_run`` / ``pass_filenames: false``)
z korzenia repo; zwraca kod !=0 gdy piny się różnią. Tylko stdlib —
działa w izolowanym venvie pre-commita i w CI bez ``uv sync``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PYPROJECT = Path("pyproject.toml")
PRECOMMIT = Path(".pre-commit-config.yaml")

# `"ruff==0.16.3"` w liście zależności — dowolne otoczenie cudzysłowów.
PYPROJECT_RE = re.compile(r"""["']ruff==([0-9][^"']*)["']""")

# Blok `- repo: https://github.com/astral-sh/ruff-pre-commit` i PIERWSZY
# `rev:` pod nim. Ograniczone do tego repo — w pliku jest wiele `rev:`.
PRECOMMIT_RE = re.compile(
    r"-\s*repo:\s*https://github\.com/astral-sh/ruff-pre-commit\b"
    r"(?:(?!-\s*repo:).)*?"
    r"\brev:\s*['\"]?v?([0-9][^\s'\"#]*)",
    re.DOTALL,
)


def _read(path: Path) -> str:
    if not path.is_file():
        sys.exit(f"BŁĄD: nie znaleziono {path} — uruchom z korzenia repo.")
    return path.read_text(encoding="utf-8")


def find_pyproject_pin(text: str) -> str:
    m = PYPROJECT_RE.search(text)
    if m is None:
        sys.exit(
            f"BŁĄD: nie znalazłem pinu `ruff==...` w {PYPROJECT}.\n"
            "Jeśli pin celowo zniknął, usuń też ten hook — inaczej bramka "
            "pilnuje zasady, której już nie ma."
        )
    return m.group(1)


def find_precommit_rev(text: str) -> str:
    m = PRECOMMIT_RE.search(text)
    if m is None:
        sys.exit(
            f"BŁĄD: nie znalazłem `rev:` dla astral-sh/ruff-pre-commit w {PRECOMMIT}."
        )
    return m.group(1)


def main() -> int:
    pin = find_pyproject_pin(_read(PYPROJECT))
    rev = find_precommit_rev(_read(PRECOMMIT))

    if pin == rev:
        return 0

    print(
        f"Piny ruffa się rozjechały:\n"
        f"  {PYPROJECT!s:<26} ruff=={pin}\n"
        f"  {PRECOMMIT!s:<26} rev: v{rev}\n"
        f"\n"
        f"To dwa różne binaria — pre-commit i CI używają `rev`, a "
        f"`uv run ruff` używa pinu z pyproject. Rozjazd = 'przechodzi "
        f"lokalnie, pada w CI'.\n"
        f"\n"
        f"Napraw, ustawiając OBA na tę samą wersję (zwykle nowszą, v{pin}):\n"
        f"  {PRECOMMIT}:  rev: v{pin}\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
