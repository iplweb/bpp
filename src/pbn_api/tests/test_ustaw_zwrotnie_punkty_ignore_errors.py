"""Testy flagi ``--ignore-errors`` dla komend ustawiających punkty zwrotnie.

Rekord-sierota (np. książka bez ani jednego autora/redaktora) nie pasuje do
żadnej „szufladki" punktowej w ``ustaw_zwrotnie_punkty_zwartych`` i normalnie
wywala całą komendę ``NotImplementedError``-em po kilkunastu rekordach. Flaga
``--ignore-errors`` ma taki rekord wypisać i pominąć, lecąc dalej — zamiast
przerywać przetwarzanie pozostałych setek rekordów.
"""

import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp import const
from bpp.models import Charakter_Formalny, Wydawca, Wydawnictwo_Zwarte


def _ksiazka_bez_autorow(rok=2023):
    """Książka (charakter_sloty=KSIAZKA) bez żadnego autora ani redaktora.

    To dokładnie konfiguracja, która nie pasuje do żadnej gałęzi if/elif
    w komendzie (``ksiazka=True``, ``autorstwo=False``, ``redakcja=False``)
    i normalnie kończy się ``NotImplementedError``.
    """
    ksiazka = baker.make(
        Charakter_Formalny, charakter_sloty=const.CHARAKTER_SLOTY_KSIAZKA
    )
    return baker.make(
        Wydawnictwo_Zwarte,
        charakter_formalny=ksiazka,
        wydawca=baker.make(Wydawca),
        rok=rok,
        punkty_kbn=0,
    )


@pytest.mark.django_db
def test_zwartych_bez_flagi_wywala_sie_na_sierocie():
    """Status quo: bez flagi rekord-sierota przerywa całą komendę."""
    _ksiazka_bez_autorow()

    with pytest.raises(NotImplementedError):
        call_command("ustaw_zwrotnie_punkty_zwartych")


@pytest.mark.django_db
def test_zwartych_ignore_errors_pomija_sierote(capsys):
    """Z ``--ignore-errors`` rekord-sierota jest pomijany, komenda kończy OK."""
    rec = _ksiazka_bez_autorow()

    call_command("ustaw_zwrotnie_punkty_zwartych", ignore_errors=True)

    # Sierota pozostaje nietknięta (nie udało się przypisać punktów) — ale
    # komenda nie rzuciła wyjątkiem.
    rec.refresh_from_db()
    assert rec.punkty_kbn == 0

    out = capsys.readouterr().out
    # Sam komunikat błędu — z identyfikacją rekordu, BEZ tracebacku.
    assert "POMINIĘTO" in out
    assert "NIE ZAIMPLEMENTOWANO" in out
    assert "Traceback" not in out


@pytest.mark.django_db
def test_ciaglych_akceptuje_flage_ignore_errors():
    """Komenda-rodzeństwo również przyjmuje flagę (spójność interfejsu)."""
    # Pusty queryset wystarczy — sprawdzamy że parser zna flagę i nie wywala
    # się na „unrecognized argument".
    call_command("ustaw_zwrotnie_punkty_ciaglych", ignore_errors=True)
