"""Repro dla FD#420 — metadane COinS (Z3988) na stronie rekordu.

`pierwsza_strona`/`ostatnia_strona` to metody, a `generate_coins` odwoływał
się do nich bez `()`, przez co do atrybutu `title` wyciekał repr bound-methody
(`<bound method ... of <Wydawnictwo_Ciagle: ...>>`). Repr zawiera znaki `"` i
`<`/`>`, które rozbijały atrybut HTML i psuły wygląd strony.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from bpp.templatetags.prace import generate_coins


@pytest.mark.django_db
def test_generate_coins_strony_nie_wyciekaja_jako_bound_method():
    praca = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Tytuł testowy",
        strony="4880-4881",
    )

    coins = generate_coins(praca, [])

    assert "bound method" not in coins
    assert "rft.spage=4880" in coins
    assert "rft.epage=4881" in coins


@pytest.mark.django_db
def test_generate_coins_pusta_strona_pomijana():
    praca = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Tytuł testowy",
        strony="",
    )

    coins = generate_coins(praca, [])

    assert "bound method" not in coins
    assert "rft.spage=" not in coins
    assert "rft.epage=" not in coins
