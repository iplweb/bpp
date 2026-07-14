"""E2E Fazy 5: przepięcie prac w commit + cofnięcie przez widok."""

import pytest
from django.urls import reverse
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import (
    Autor,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj
from przemapuj_prace_autora.models import PrzemapoaniePracAutora


@pytest.mark.django_db
def test_e2e_przepiecie_i_cofniecie(admin_client, admin_user):
    stara = baker.make(Jednostka, nazwa="Stara", skrot="ST")
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    autor.dodaj_jednostke(stara)
    autor.refresh_from_db()
    assert autor.aktualna_jednostka_id == stara.pk

    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara)
    wz = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Ksz", rok=2022)
    pz = baker.make(Wydawnictwo_Zwarte_Autor, rekord=wz, autor=autor, jednostka=stara)

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )

    # commit → przepięcie
    integruj(imp, MockProgress(imp))
    pa.refresh_from_db()
    pz.refresh_from_db()
    assert pa.jednostka_id == nowa.pk
    assert pz.jednostka_id == nowa.pk
    prz = PrzemapoaniePracAutora.objects.get(zrodlowy_import=imp)

    # cofnięcie przez widok
    url = reverse("przemapuj_prace_autora:cofnij_przemapowanie", kwargs={"pk": prz.pk})
    resp = admin_client.post(url)
    assert resp.status_code == 302

    pa.refresh_from_db()
    pz.refresh_from_db()
    assert pa.jednostka_id == stara.pk
    assert pz.jednostka_id == stara.pk
    # audyt przetrwał
    assert PrzemapoaniePracAutora.objects.filter(pk=prz.pk).exists()


@pytest.mark.django_db
def test_e2e_integracja_zapisuje_zamrozony_snapshot_po_imporcie(admin_user):
    # Immutable snapshot at finalization: pełna integracja osób (zakres
    # domyślny — ZAKRES_PELNY) musi na końcu zapisać `plik_po_imporcie`
    # (patrz integrate.integruj -> eksport.zapisz_snapshot_po_imporcie).
    jednostka = baker.make(Jednostka, nazwa="Klinika E2E", skrot="KE2E")
    autor = baker.make(Autor, nazwisko="Zamrozony", imiona="Jan")

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
        mapowanie_kolumn={
            "Nazwisko": "nazwisko",
            "Imię": "imię",
            "Jednostka": "nazwa_jednostki",
        },
    )
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        zmiany_potrzebne=False,
    )

    integruj(imp, MockProgress(imp))
    imp.refresh_from_db()

    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY
    assert imp.plik_po_imporcie


@pytest.mark.django_db
def test_e2e_blad_snapshotu_nie_przerywa_integracji(admin_user, monkeypatch):
    # Hook w integrate.integruj() woła zapisz_snapshot_po_imporcie() LENIWYM
    # importem wewnątrz try/except (loguje + kontynuuje). Awaria generacji
    # snapshotu (np. storage padnie) NIE może cofnąć/przerwać już-wykonanej
    # integracji osób — patrz komentarz nad tym try/except w integrate.py.
    def _raise(_import_obj):
        raise RuntimeError("symulowana awaria generacji snapshotu")

    # Leniwy import w integrate.py rozwiązuje symbol na module
    # import_pracownikow.eksport w chwili wywołania — patchujemy TAM, nie
    # w integrate (które go w ogóle nie importuje na poziomie modułu).
    monkeypatch.setattr(
        "import_pracownikow.eksport.zapisz_snapshot_po_imporcie", _raise
    )

    jednostka = baker.make(Jednostka, nazwa="Klinika Awaria", skrot="KA")
    autor = baker.make(Autor, nazwisko="Awaryjny", imiona="Jan")

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
        mapowanie_kolumn={
            "Nazwisko": "nazwisko",
            "Imię": "imię",
            "Jednostka": "nazwa_jednostki",
        },
    )
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        zmiany_potrzebne=False,
    )

    integruj(imp, MockProgress(imp))
    imp.refresh_from_db()

    # Integracja dobiegła końca mimo awarii generacji snapshotu...
    assert imp.stan == ImportPracownikow.STAN_ZINTEGROWANY
    # ...ale snapshot się nie zmaterializował (widok pobierania degraduje
    # wtedy do budowy pliku w locie — patrz PobierzPoImporcieView).
    assert not imp.plik_po_imporcie
