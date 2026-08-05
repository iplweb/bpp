import pytest
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


def _autor_ze_starą_jednostką():
    stara = baker.make(Jednostka, nazwa="Stara", skrot="ST")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    autor.dodaj_jednostke(stara)
    autor.refresh_from_db()
    assert autor.aktualna_jednostka_id == stara.pk
    return autor, stara


@pytest.mark.django_db
def test_commit_przepina_prace_opt_in(admin_user):
    autor, stara = _autor_ze_starą_jednostką()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara)
    wz = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Ksz", rok=2022)
    pz = baker.make(Wydawnictwo_Zwarte_Autor, rekord=wz, autor=autor, jednostka=stara)
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    pa.refresh_from_db()
    pz.refresh_from_db()
    assert pa.jednostka_id == nowa.pk
    assert pz.jednostka_id == nowa.pk

    prz = PrzemapoaniePracAutora.objects.get(autor=autor)
    assert prz.zrodlowy_import_id == imp.pk
    assert prz.jednostka_z_id == stara.pk
    assert prz.jednostka_do_id == nowa.pk
    assert p.result_context["przepieto_wierszy"] == 1
    assert p.result_context["przepieto_prac"] == 2

    row.refresh_from_db()
    assert row.log_zmian["przepiecie"]["pk"] == prz.pk
    assert row.log_zmian["przepiecie"]["prace_ciagle"] == 1
    assert row.log_zmian["przepiecie"]["prace_zwarte"] == 1


@pytest.mark.django_db
def test_commit_bez_roznicy_jednostki_nie_przepina(admin_user):
    autor, stara = _autor_ze_starą_jednostką()
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    # jednostka wiersza == aktualna (stara) → brak różnicy, nic do przepięcia
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=stara,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    assert not PrzemapoaniePracAutora.objects.filter(autor=autor).exists()
    assert p.result_context["przepieto_wierszy"] == 0


@pytest.mark.django_db
def test_commit_bez_flagi_nie_przepina(admin_user):
    autor, stara = _autor_ze_starą_jednostką()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara)
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
        przepnij_prace=False,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    assert not PrzemapoaniePracAutora.objects.filter(autor=autor).exists()
    assert p.result_context["przepieto_wierszy"] == 0


@pytest.mark.django_db
def test_commit_nie_przepina_gdy_stara_jednostka_jest_w_pliku(admin_user):
    # F1 „pułapka drugiego etatu”: plik ma wiersz A (etat = stara jednostka)
    # ORAZ wiersz B (różnica jednostki). Guard „para z pliku” MUSI pominąć
    # przepięcie A→B, bo etat A jest POTWIERDZONY w pliku (wiersz A).
    autor, stara = _autor_ze_starą_jednostką()
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara)
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    # wiersz A: potwierdza etat w starej jednostce (para (autor, stara) z pliku)
    ImportPracownikowRow.objects.create(
        parent=imp, autor=autor, jednostka=stara, zmiany_potrzebne=False
    )
    # wiersz B: różnica jednostki, opt-in przepięcia
    row_b = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    pa.refresh_from_db()
    assert pa.jednostka_id == stara.pk  # prace A NIETKNIĘTE (guard zadziałał)
    assert not PrzemapoaniePracAutora.objects.filter(autor=autor).exists()
    assert p.result_context["przepieto_wierszy"] == 0
    row_b.refresh_from_db()
    assert "przepiecie" not in (row_b.log_zmian or {})


@pytest.mark.django_db
def test_commit_duplikat_autora_przepina_raz(admin_user):
    # F3: dwa wiersze tego samego autora (stara → B, stara → C), brak wiersza
    # A w pliku (F1-guard nie łapie). Przepięcie wykonujemy RAZ (pierwszy po
    # pk), drugi wiersz dostaje ślad „duplikat” bez pustego rekordu.
    autor, stara = _autor_ze_starą_jednostką()
    jed_b = baker.make(Jednostka, nazwa="B", skrot="BB")
    jed_c = baker.make(Jednostka, nazwa="C", skrot="CC")
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara)
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZATWIERDZONY,
    )
    row_b = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jed_b,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )
    row_c = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jed_c,
        zmiany_potrzebne=False,
        przepnij_prace=True,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    # JEDNO przemapowanie; prace w jednej jednostce (pierwszy wiersz po pk)
    assert PrzemapoaniePracAutora.objects.filter(autor=autor).count() == 1
    prz = PrzemapoaniePracAutora.objects.get(autor=autor)
    pa.refresh_from_db()
    assert pa.jednostka_id == prz.jednostka_do_id
    assert prz.jednostka_do_id == jed_b.pk  # row_b ma mniejszy pk
    assert p.result_context["przepieto_wierszy"] == 1
    row_b.refresh_from_db()
    row_c.refresh_from_db()
    assert row_b.log_zmian["przepiecie"]["do"] == jed_b.skrot
    assert "przepiecie" not in (row_c.log_zmian or {})
    assert "przepiecie_pominiete" in row_c.log_zmian
