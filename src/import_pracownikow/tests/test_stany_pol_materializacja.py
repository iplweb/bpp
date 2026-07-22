"""Materializacja ``stany_pol_snapshot`` — świeżość, backfill, audyt.

Filtr stanu pól na liście wyników działa w SQL na ``stany_pol_snapshot``, więc
nieświeże pole = po cichu kłamiący filtr. Te testy pilnują trzech rzeczy:

1. pole jest świeże po KAŻDEJ ścieżce mutującej pola czytane przez ekstraktory
   (integracja strukturalna przypisuje jednostkę/tytuł/stopień/stanowisko;
   widoki dopasowania zmieniają autora);
2. backfill wypełnia wyłącznie wiersze z ``NULL`` — niepusty snapshot jest
   zamrożonym zapisem audytowym i nadpisanie go skasowałoby ślad zmian;
3. zamrożona wartość audytowa nie zmieniła się względem zachowania sprzed
   materializacji.
"""

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowRow,
)
from import_pracownikow.pewnosc import STATUS_BRAK, STATUS_TWARDY
from import_pracownikow.pipeline.integrate import integruj


def _wiersz(imp, **kw):
    kw.setdefault("dane_znormalizowane", {"imię": "Jan", "nazwisko": "Kowalski"})
    kw.setdefault("dane_z_xls", {"__xls_loc_sheet__": 0, "__xls_loc_row__": 1})
    kw.setdefault("zmiany_potrzebne", False)
    return ImportPracownikowRow.objects.create(parent=imp, **kw)


@pytest.mark.django_db
def test_integracja_strukturalna_odswieza_stany_pol():
    """Po „Zapisz strukturę" snapshot odpowiada świeżo policzonym stanom.

    To jest test na klasę błędu, której NIE złapałaby parametryzacja po
    endpointach HTMX: jednostkę wierszowi przypisuje potok integracji, a nie
    widok weryfikacji jednostek (ten zapisuje wyłącznie obiekty decyzji).
    Wynikowy stan „struktura zintegrowana" jest nadal edytowalny, więc operator
    filtruje po stanach pól właśnie wtedy.
    """
    imp = baker.make(
        ImportPracownikow,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
        zakres_integracji=ImportPracownikow.ZAKRES_STRUKTURA,
    )
    docelowa = baker.make(Jednostka)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    autor.aktualna_jednostka = baker.make(Jednostka)  # INNA niż docelowa
    autor.save()
    dec = baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="Katedra Testowa",
        decyzja=ImportPracownikowJednostka.DECYZJA_MAPUJ,
        wybrana_jednostka=docelowa,
    )
    row = _wiersz(imp, autor=autor, zrodlo_jednostki=dec, confidence=STATUS_TWARDY)

    integruj(imp, MockProgress(imp))

    row.refresh_from_db()
    assert row.jednostka_id == docelowa.pk, "potok miał podłączyć jednostkę"
    assert row.stany_pol_snapshot is not None, (
        "integracja strukturalna nie zmaterializowała stanów pól — filtr na "
        "liście wyników kłamałby przez całą fazę osób"
    )
    assert row.stany_pol_snapshot == row.stany_pol_live()
    # Jednostka docelowa różni się od aktualnej autora → stan „zmienione".
    assert row.stany_pol_snapshot["jednostka"] == "zmienione"


@pytest.mark.django_db
def test_dopasowanie_autora_odswieza_stany_pol(admin_client, admin_user):
    """POST na `dopasuj-autora` zostawia świeży snapshot."""
    from django.urls import reverse

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    autor.aktualna_jednostka = baker.make(Jednostka)
    autor.save()
    row = _wiersz(imp, jednostka=jednostka, autor=None, confidence=STATUS_BRAK)
    row.stany_pol_snapshot = row.stany_pol_live()
    row.save(update_fields=["stany_pol_snapshot"])
    assert row.stany_pol_snapshot["tytul"] == "brak"  # bez autora

    admin_client.post(
        reverse(
            "import_pracownikow:dopasuj-autora",
            kwargs={"pk": imp.pk, "row_pk": row.pk},
        ),
        {"autor": autor.pk},
    )

    row.refresh_from_db()
    assert row.autor_id == autor.pk
    assert row.stany_pol_snapshot == row.stany_pol_live(), (
        "zmiana autora przestawia stany pól — snapshot musi zostać przeliczony"
    )


@pytest.mark.django_db
def test_backfill_wypelnia_puste_i_nie_rusza_zamrozonych(admin_client, admin_user):
    """Wejście na listę wyników uzupełnia NULL-e, ale NIE nadpisuje istniejących.

    Wariant (b) jest tu ważniejszy: snapshot niepusty bywa zamrożonym zapisem
    audytowym (stan sprzed integracji). Przeliczenie go po integracji dałoby
    „zgodne" tam, gdzie audyt ma pokazywać „zmienione".
    """
    from django.urls import reverse

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZINTEGROWANY,
        finished_successfully=True,
    )
    jednostka = baker.make(Jednostka)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    autor.aktualna_jednostka = jednostka  # zgodne → live dałoby „zgodne"
    autor.save()

    pusty = _wiersz(imp, jednostka=jednostka, autor=autor, confidence=STATUS_TWARDY)
    zamrozony = _wiersz(imp, jednostka=jednostka, autor=autor, confidence=STATUS_TWARDY)
    # Zamrożony ślad audytowy: „zmienione", choć live policzyłoby „zgodne".
    zamrozony.stany_pol_snapshot = {"jednostka": "zmienione"}
    zamrozony.save(update_fields=["stany_pol_snapshot"])

    admin_client.get(
        reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    )

    pusty.refresh_from_db()
    zamrozony.refresh_from_db()
    assert pusty.stany_pol_snapshot is not None, "backfill nie wypełnił NULL-a"
    assert pusty.stany_pol_snapshot["jednostka"] == "zgodne"
    assert zamrozony.stany_pol_snapshot == {"jednostka": "zmienione"}, (
        "backfill nadpisał zamrożony snapshot audytowy — utrata śladu zmian"
    )


@pytest.mark.django_db
def test_audyt_wiersza_utworz_nowego_bez_zmian():
    """Zamrożony snapshot dla „utwórz nowego" zachowuje zachowanie sprzed zmiany.

    Snapshot liczy się PO utworzeniu autora (`_przygotuj_nowego_autora`), ale
    PRZED materializacją odroczonego `Autor_Jednostka` — dlatego `funkcja` musi
    wyjść „brak". Asercja celuje w tę KONKRETNĄ wartość, nie w ogólne
    „policzone względem nowego autora": błędny wariant (przeliczenie po
    materializacji) też spełniałby ten słabszy warunek, a dawałby inny wynik.

    WARUNEK WSTĘPNY jest tu częścią testu: wiersz wchodzi do integracji z JUŻ
    wypełnionym snapshotem, bo tak wygląda rzeczywistość po materializacji
    (analiza wypełnia pole na końcu). Wartownik `SENTINEL` wyłapuje wariant,
    w którym zamrożenie idzie przez `stany_pol()` — ta metoda przy niepustym
    snapshocie zwraca go bez zmian, więc przypisanie byłoby no-opem i audyt
    utrwaliłby stan sprzed powstania autora.
    """
    imp = baker.make(
        ImportPracownikow,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
        zakres_integracji=ImportPracownikow.ZAKRES_PELNY,
    )
    jednostka = baker.make(Jednostka)
    row = _wiersz(
        imp,
        jednostka=jednostka,
        autor=None,
        confidence=STATUS_BRAK,
        utworz_nowego=True,
        zmiany_potrzebne=False,
        dane_znormalizowane={"imię": "Nowy", "nazwisko": "Pracownik"},
    )
    row.stany_pol_snapshot = {"jednostka": "SENTINEL"}
    row.save(update_fields=["stany_pol_snapshot"])

    integruj(imp, MockProgress(imp))

    row.refresh_from_db()
    assert row.autor_id is not None, "faza nowych autorów miała utworzyć autora"
    assert row.stany_pol_snapshot is not None
    assert "SENTINEL" not in row.stany_pol_snapshot.values(), (
        "zamrożenie audytu nie przeliczyło stanów — poszło przez stany_pol(), "
        "które przy niepustym snapshocie zwraca go bez zmian (no-op)"
    )
    assert row.stany_pol_snapshot["funkcja"] == "brak", (
        "snapshot audytowy policzony PO materializacji diffu — zamrożenie musi "
        "odzwierciedlać stan z podglądu (odroczone Autor_Jednostka = None)"
    )
