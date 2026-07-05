"""Smoke-test dokładności tłumaczenia NL->DjangoQL na realnym modelu.

Wymaga ``ANTHROPIC_API_KEY`` (realne wywołanie SDK, koszt + czas sieciowy) —
pomijany domyślnie i wykluczony z CI (patrz ``[tool.pytest.ini_options]``
w pyproject.toml, `norecursedirs`/`addopts` albo dedykowany marker, jeśli CI
selekcjonuje po ścieżkach).

Docelowo 30-50 par pytanie->fragment DSL; tu smoke set (kilka
reprezentatywnych przypadków) — pełny zestaw accuracy wymaga ręcznej
kuracji przez osobę znającą dane demo/testowe.
"""

import os

import pytest

from ai_search import translator

ANTHROPIC = bool(os.environ.get("ANTHROPIC_API_KEY"))
pytestmark = pytest.mark.skipif(not ANTHROPIC, reason="brak ANTHROPIC_API_KEY")

CASES = [
    ("rekord", "publikacje z 2024 roku", "rok"),
    ("rekord", "prace bez źródła", "None"),
    ("autor", "autorzy z ORCID", "orcid"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("model_key,pytanie,expect_fragment", CASES)
def test_translates_reasonably(model_key, pytanie, expect_fragment):
    res = translator.translate(pytanie, model_key)
    assert res.query is not None
    assert expect_fragment in res.query
