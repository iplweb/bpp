"""Wariant opisu bibliograficznego ``browse/praca_tabela.html`` a link do PBN.

``opis_bibliograficzny()`` renderuje szablon wskazany przez
``SzablonDlaOpisuBibliograficznego`` kontekstem ``dict(praca=..., links=...)``
— BEZ requestu, więc BEZ ``uczelnia`` (context processory nie biegną).

To pole minowe dla wszystkiego, co w tym szablonie odwołuje się do
``uczelnia``: Django rozwija argumenty filtrów zachłannie, a ``{% with %}``
— w odróżnieniu od ``{% if %}`` — NIE łapie ``VariableDoesNotExist``.
Efekt: generowanie opisu (i denormalizacja) wywala się wyjątkiem.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Zwarte
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)


@pytest.mark.django_db
def test_opis_bibliograficzny_wariant_praca_tabela_z_pbn_uid():
    """Rekord z PBN UID + wariant ``praca_tabela.html`` = opis ma się wyrenderować."""
    from pbn_api.models import Publication

    publication = baker.make(Publication)
    praca = baker.make(Wydawnictwo_Zwarte, pbn_uid=publication)

    # Wariant ustawiamy PO zapisie rekordu: denorm woła opis_bibliograficzny()
    # w pre_save na jeszcze-niezapisanej instancji, a ten szablon odwołuje się
    # do relacji (``praca.streszczenia.exists``), więc na bezkluczowym obiekcie
    # poleciałby ValueError — to osobna, wcześniejsza sprawa niż PBN.
    SzablonDlaOpisuBibliograficznego.objects.update_or_create(
        model=None, defaults={"nazwa_szablonu": "browse/praca_tabela.html"}
    )

    opis = praca.opis_bibliograficzny()

    assert praca.tytul_oryginalny in opis
    # Bez uczelni w kontekście nie da się zbudować adresu PBN — ma zostać
    # sam identyfikator, a NIE napis "None" w atrybucie linku.
    assert "None" not in opis
