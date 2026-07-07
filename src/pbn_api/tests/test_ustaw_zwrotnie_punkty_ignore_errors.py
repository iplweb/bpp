"""Testy obsługi rekordów problematycznych w komendach ustawiających punkty.

Dwie różne klasy rekordów „nie do wpasowania" w szufladki punktowe:

1. **Brak punktowalnego autorstwa/redakcji** (np. książka bez ani jednego
   autora/redaktora — pusty ``autorzy_set``). To anomalia DANYCH: nie ma slotu
   autorskiego, więc nie ma czego punktować. Taki rekord jest pomijany i
   raportowany **ZAWSZE**, niezależnie od ``--ignore-errors`` — bez wywalania
   komendy.

2. **Prawdziwie nieobsłużona kombinacja typu** (np. referat z autorem — rekord
   MA punktowalne autorstwo, ale typ slotu nie jest obsłużony). To luka w
   LOGICE punktacji, nie w danych → nadal twardy ``NotImplementedError``, chyba
   że ``--ignore-errors`` każe ją pominąć.
"""

import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp import const
from bpp.models import (
    Charakter_Formalny,
    Typ_Odpowiedzialnosci,
    Wydawca,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)


def _ksiazka_bez_autorow(rok=2023):
    """Książka (charakter_sloty=KSIAZKA) bez żadnego autora ani redaktora.

    ``ksiazka=True``, ``autorstwo=False``, ``redakcja=False`` — pusty
    ``autorzy_set``. Brak punktowalnego autorstwa: pomijany ZAWSZE.
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


def _ksiazka_bez_wydawcy(rok=2023):
    """Książka (charakter_sloty=KSIAZKA) BEZ wydawcy (``wydawca=None``).

    Import PBN świadomie tworzy wydawnictwa zwarte bez wydawcy (PBN bywa
    niekompletny; ``wydawca`` jest nullable). Punktacja opiera się na
    ``wydawca.get_tier(rok)`` — bez wydawcy nie ma tieru (Rollbar #436:
    ``'NoneType' object has no attribute 'get_tier'``). Pomijany ZAWSZE.
    """
    ksiazka = baker.make(
        Charakter_Formalny, charakter_sloty=const.CHARAKTER_SLOTY_KSIAZKA
    )
    return baker.make(
        Wydawnictwo_Zwarte,
        charakter_formalny=ksiazka,
        wydawca=None,
        rok=rok,
        punkty_kbn=0,
    )


def _referat_z_autorem(rok=2023):
    """Referat (charakter_sloty=REFERAT) z autorem — typ slotu nieobsłużony.

    ``ksiazka=False``, ``rozdzial=False``, ``autorstwo=True``: rekord MA
    punktowalne autorstwo, ale żadna gałąź if/elif nie obsługuje referatu →
    prawdziwa luka w logice → ``NotImplementedError``.
    """
    referat = baker.make(
        Charakter_Formalny, charakter_sloty=const.CHARAKTER_SLOTY_REFERAT
    )
    rec = baker.make(
        Wydawnictwo_Zwarte,
        charakter_formalny=referat,
        wydawca=baker.make(Wydawca),
        rok=rok,
        punkty_kbn=0,
    )
    baker.make(
        Wydawnictwo_Zwarte_Autor,
        rekord=rec,
        typ_odpowiedzialnosci=baker.make(
            Typ_Odpowiedzialnosci, typ_ogolny=const.TO_AUTOR
        ),
    )
    return rec


@pytest.mark.django_db
def test_zwartych_bez_autorow_pomijany_zawsze_bez_flagi(capsys):
    """Książka bez autorów: pomijana i raportowana ZAWSZE, nawet bez flagi."""
    rec = _ksiazka_bez_autorow()

    # Bez --ignore-errors — i tak nie wywala komendy.
    call_command("ustaw_zwrotnie_punkty_zwartych")

    rec.refresh_from_db()
    assert rec.punkty_kbn == 0  # nietknięty — nie było czego punktować

    out = capsys.readouterr().out
    assert "POMINIĘTO" in out
    assert str(rec.pk) in out
    assert "Traceback" not in out


@pytest.mark.django_db
def test_zwartych_bez_autorow_pomijany_takze_z_flaga(capsys):
    """Z ``--ignore-errors`` zachowanie dla sieroty jest takie samo (pomijany)."""
    rec = _ksiazka_bez_autorow()

    call_command("ustaw_zwrotnie_punkty_zwartych", ignore_errors=True)

    rec.refresh_from_db()
    assert rec.punkty_kbn == 0

    out = capsys.readouterr().out
    assert "POMINIĘTO" in out
    assert "Traceback" not in out


@pytest.mark.django_db
def test_zwartych_bez_wydawcy_pomijany_zawsze_bez_flagi(capsys):
    """Książka bez wydawcy (#436): pomijana i raportowana ZAWSZE, bez wywalania."""
    rec = _ksiazka_bez_wydawcy()

    # Bez --ignore-errors — i tak nie wywala komendy na braku wydawcy.
    call_command("ustaw_zwrotnie_punkty_zwartych")

    rec.refresh_from_db()
    assert rec.punkty_kbn == 0  # nietknięty — brak podstawy do tieru wydawcy

    out = capsys.readouterr().out
    assert "POMINIĘTO" in out
    assert str(rec.pk) in out
    assert "Traceback" not in out


@pytest.mark.django_db
def test_zwartych_nieobsluzona_kombinacja_wywala_sie_bez_flagi():
    """Referat z autorem (luka w logice): bez flagi nadal ``NotImplementedError``."""
    _referat_z_autorem()

    with pytest.raises(NotImplementedError):
        call_command("ustaw_zwrotnie_punkty_zwartych")


@pytest.mark.django_db
def test_zwartych_ignore_errors_pomija_nieobsluzona_kombinacje(capsys):
    """Z ``--ignore-errors`` nawet prawdziwa luka logiki jest pomijana."""
    _referat_z_autorem()

    call_command("ustaw_zwrotnie_punkty_zwartych", ignore_errors=True)

    out = capsys.readouterr().out
    assert "POMINIĘTO" in out
    assert "NIE ZAIMPLEMENTOWANO" in out
    assert "Traceback" not in out


@pytest.mark.django_db
def test_ciaglych_akceptuje_flage_ignore_errors():
    """Komenda-rodzeństwo również przyjmuje flagę (spójność interfejsu)."""
    # Pusty queryset wystarczy — sprawdzamy że parser zna flagę i nie wywala
    # się na „unrecognized argument".
    call_command("ustaw_zwrotnie_punkty_ciaglych", ignore_errors=True)
