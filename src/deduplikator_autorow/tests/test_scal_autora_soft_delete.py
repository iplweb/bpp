"""Scalanie autorów a kosz (faza 03 soft-delete, pozycje 3.2–3.4 handoffu).

Scalanie należy do „kategorii B": przenosi rekordy duplikatu RAZEM Z KOSZEM,
żeby po usunięciu duplikatu nie zostały sieroty. To poprawne — ale odsłoniło
trzy miejsca, w których reszta kodu zakłada, że wiersz w koszu nie istnieje:

3.2. ``Praca_Habilitacyjna.autor`` było ``OneToOneField`` → twardy
     ``UNIQUE (autor_id)``, który kosza NIE zna.
3.3. Detekcja kolizji autorstw szła po menedżerze ŻYWYCH.
3.4. Kolejkowanie do PBN nie sprawdzało, czy publikacja jest w koszu.
"""

import pytest
from model_bakery import baker

from bpp.models import Praca_Habilitacyjna
from deduplikator_autorow.utils.merge import scal_autora


@pytest.fixture
def user(db):
    return baker.make("bpp.BppUser")


@pytest.fixture
def main_dup(autor_maker, tytuly, typy_odpowiedzialnosci, charaktery_formalne):
    # Słowniki z fixture'ów, nie z baseline: testy transakcyjne z tego samego
    # przebiegu potrafią wyczyścić dane referencyjne (patrz zapis habilitacji,
    # który sięga po Typ_Odpowiedzialnosci przy przebudowie cache'u).
    glowny = autor_maker(imiona="Jan", nazwisko="Kowalski")
    duplikat = autor_maker(imiona="Jan", nazwisko="Kowalski-Duplikat")
    return glowny, duplikat


# --- 3.2. Habilitacja: unique musi znać kosz -------------------------------


def test_scalanie_przenosi_habilitacje_z_kosza_gdy_glowny_ma_zywa(main_dup, user):
    """Habilitacja duplikatu W KOSZU nie może wywrócić całego scalania.

    ``UNIQUE (autor_id)`` z ``OneToOneField`` nie zna kosza: przeniesienie
    skasowanej habilitacji duplikatu na autora, który ma już żywą, wywalało
    ``IntegrityError`` — a ten leci przez ``except Exception`` w ``scal_autora``
    i cała operacja zwraca porażkę. Przed fazą 03 wiersz z kosza w ogóle nie był
    przenoszony, więc scalanie się udawało; po włączeniu transferu „razem
    z koszem" zaczęło padać.
    """
    glowny, duplikat = main_dup
    baker.make(Praca_Habilitacyjna, autor=glowny)
    hab_duplikatu = baker.make(Praca_Habilitacyjna, autor=duplikat)
    hab_duplikatu.delete()

    wynik = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert wynik["success"] is True, (
        f"scalanie padlo zamiast przeniesc habilitacje z kosza: {wynik.get('error')!r}"
    )
    hab_duplikatu.refresh_from_db()
    assert hab_duplikatu.autor_id == glowny.pk, (
        "habilitacja z kosza zostala przy usunietym duplikacie — sierota"
    )
    assert hab_duplikatu.deleted_at is not None, (
        "transfer nie moze przy okazji wskrzeszac rekordu z kosza"
    )


def test_dwie_zywe_habilitacje_daja_czytelny_komunikat_nie_integrityerror(
    main_dup, user
):
    """Prawdziwy konflikt ma być nazwany po imieniu.

    Gdy OBAJ autorzy mają ŻYWĄ pracę habilitacyjną, scalenie jest niemożliwe —
    ale operator ma się dowiedzieć DLACZEGO, zamiast dostać komunikat bazy
    o naruszeniu ograniczenia.
    """
    glowny, duplikat = main_dup
    baker.make(Praca_Habilitacyjna, autor=glowny)
    baker.make(Praca_Habilitacyjna, autor=duplikat)

    wynik = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert wynik["success"] is False
    assert "obaj mają pracę habilitacyjną" in wynik["error"], (
        f"komunikat nie tlumaczy przyczyny: {wynik['error']!r}"
    )
    assert "duplicate key" not in wynik["error"]
    assert "UNIQUE" not in wynik["error"]

    # Konflikt nie moze zostawic bazy w polowie scalonej.
    assert type(glowny).objects.filter(pk=duplikat.pk).exists(), (
        "duplikat zostal usuniety mimo nieudanego scalania"
    )


def test_habilitacja_duplikatu_przechodzi_gdy_glowny_nie_ma_zadnej(main_dup, user):
    """Kontrola: bez konfliktu transfer ma działać jak dotąd."""
    glowny, duplikat = main_dup
    habilitacja = baker.make(Praca_Habilitacyjna, autor=duplikat)

    wynik = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert wynik["success"] is True, wynik.get("error")
    habilitacja.refresh_from_db()
    assert habilitacja.autor_id == glowny.pk
