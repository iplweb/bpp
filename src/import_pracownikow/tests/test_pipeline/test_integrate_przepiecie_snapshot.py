"""#514 F-2: niezmiennik przepięcia — snapshot ``stare_jednostki`` MUSI złapać
starą ``aktualna_jednostka`` PRZED tym, jak pętla integracji odpali trigger DB
``bpp_autor_ustaw_jednostka_aktualna`` (który przestawia ją na jednostkę z
pliku).

Wszystkie pozostałe testy przepięć używają ``zmiany_potrzebne=False`` — pętla
integracji ich NIE dotyka, więc trigger nigdy się nie odpala i snapshot ma
trywialnie tę samą wartość co stan bieżący. Ten test celowo integruje wiersz z
prawdziwym driftem (ustawienie ``podstawowe_miejsce_pracy`` na AJ w NOWEJ
jednostce), przez co trigger FAKTYCZNIE przestawia ``aktualna_jednostka`` na
nową jednostkę w trakcie pętli — i sprawdza, że przepięcie i tak użyło STAREJ
jednostki jako ``jednostka_z``. Gdyby snapshot był brany PO pętli, ``jednostka_z``
== ``jednostka_do`` (F5) → brak przepięcia.
"""

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj
from przemapuj_prace_autora.models import PrzemapoaniePracAutora


@pytest.mark.django_db
def test_snapshot_lapie_stara_jednostke_przed_triggerem(admin_user):
    stara = baker.make(Jednostka, nazwa="Stara", skrot="ST")
    nowa = baker.make(Jednostka, nazwa="Nowa", skrot="NW")
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    # AJ w starej = podstawowe → aktualna_jednostka = stara (trigger: podstawowe
    # bije wszystko). AJ w nowej istnieje, ale NIE podstawowe.
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=stara,
        podstawowe_miejsce_pracy=True,
    )
    aj_nowa = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=nowa,
        podstawowe_miejsce_pracy=False,
    )
    autor.refresh_from_db()
    assert autor.aktualna_jednostka_id == stara.pk

    # praca w starej jednostce — kandydat do przepięcia stara → nowa
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Art", rok=2023)
    pa = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=stara)

    imp = baker.make(
        ImportPracownikow, owner=admin_user, stan=ImportPracownikow.STAN_ZATWIERDZONY
    )
    # Wiersz REALNIE integrujący: ustawia podstawowe na AJ w nowej jednostce →
    # integrate() → ustaw_podstawowe_miejsce_pracy() → trigger przestawia
    # aktualna_jednostka autora na NOWĄ w trakcie pętli integracji.
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=nowa,
        autor_jednostka=aj_nowa,
        dane_znormalizowane={},
        diff_do_utworzenia={},
        podstawowe_miejsce_pracy=True,
        zmiany_potrzebne=True,
        przepnij_prace=True,
    )

    p = MockProgress(imp)
    integruj(imp, p)

    # Trigger FAKTYCZNIE się odpalił w pętli — aktualna przestawiona na nową.
    autor.refresh_from_db()
    assert autor.aktualna_jednostka_id == nowa.pk

    # Sedno niezmiennika: mimo że aktualna to teraz NOWA, przepięcie użyło
    # STAREJ jako jednostka_z (snapshot sprzed pętli). Gdyby snapshot był po
    # pętli, jednostka_z == nowa == jednostka_do → F5 pominięcie, brak rekordu.
    prz = PrzemapoaniePracAutora.objects.get(autor=autor)
    assert prz.jednostka_z_id == stara.pk
    assert prz.jednostka_do_id == nowa.pk
    pa.refresh_from_db()
    assert pa.jednostka_id == nowa.pk
    assert p.result_context["przepieto_wierszy"] == 1
    assert p.result_context["przepieto_prac"] == 1

    row.refresh_from_db()
    assert row.log_zmian["przepiecie"]["pk"] == prz.pk
