import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Funkcja_Autora,
    Licencja_OpenAccess,
)
from fixtures.conftest_publications import _wydawnictwo_ciagle_maker
from raport_slotow.tables import RaportEwaluacjaUpowaznieniaTable
from raport_slotow.views.upowaznienie_pbn import RaportEwaluacjaUpowaznienia

#: Ile rekordów dokładamy po pomiarze bazowym (patrz ``test_ewaluacja.py``).
DOKLADANE = 3


def test_tabela_upowaznien_nie_dziedziczy_kolumn_wydzialow():
    column_names = RaportEwaluacjaUpowaznieniaTable([]).columns.names()

    assert "aktualny_wydzial" not in column_names
    assert "afiliowany_wydzial" not in column_names


def test_raport_ewaluacja_upowaznienia(
    rekord_slotu,
    admin_client,
    rok,
    autor_jan_kowalski,
    dyscyplina1,
    wydawnictwo_ciagle_z_autorem,
):

    Autor_Dyscyplina.objects.create(
        rok=rok, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1
    )

    rekord_slotu.delete()
    wydawnictwo_ciagle_z_autorem.punkty_kbn = 500
    wydawnictwo_ciagle_z_autorem.save()

    af = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    af.afiliuje = False
    af.save()

    url = reverse(
        "raport_slotow:raport-ewaluacja-upowaznienia",
    )

    r = RaportEwaluacjaUpowaznienia()
    r.data = dict(od_roku=rok, do_roku=rok, _export="html")
    assert r.get_queryset().count() == 1

    admin_client.get(
        url,
        data={
            "od_roku": 2017,
            "do_roku": 2021,
            "_export": "xlsx",
        },
    )


@pytest.mark.parametrize("export", ["xlsx", "html"])
def test_raport_ewaluacja_upowaznienia_bez_n_plus_jeden(
    export,
    admin_client,
    rok,
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    jezyki,
    typy_odpowiedzialnosci,
):
    """Liczba zapytań raportu upoważnień nie rośnie z liczbą wierszy.

    Licencja OpenAccess, afiliowana jednostka i funkcja autora (kolumny
    dziedziczone z raportu ewaluacji) dawniej doczytywały się per wiersz.
    """
    Autor_Dyscyplina.objects.create(
        rok=rok, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1
    )
    funkcja = baker.make(Funkcja_Autora)
    licencja = baker.make(Licencja_OpenAccess, nazwa="Licencja testowa", skrot="TST")

    def fabryka():
        wydawnictwo = _wydawnictwo_ciagle_maker()
        wydawnictwo.openaccess_licencja = licencja
        wydawnictwo.punkty_kbn = 500
        wydawnictwo.save()
        wydawnictwo.dodaj_autora(
            autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1
        )
        wydawnictwo.autorzy_set.update(afiliuje=False)
        # ``aktualna_funkcja`` ustawia trigger z ``Autor_Jednostka`` — dopiero
        # po ``dodaj_autora`` nadpisujemy ją bezpośrednio w bazie.
        Autor.objects.filter(pk=autor_jan_kowalski.pk).update(
            aktualna_funkcja=funkcja
        )

    url = reverse("raport_slotow:raport-ewaluacja-upowaznienia")
    data = {"od_roku": rok, "do_roku": rok, "_export": export}

    def licz():
        with CaptureQueriesContext(connection) as ctx:
            res = admin_client.get(url, data=data)
        assert res.status_code == 200, res.content[:500]
        return len(ctx.captured_queries), ctx.captured_queries

    fabryka()
    licz()  # rozgrzewka (Site, Uczelnia, ContentType)
    bazowa, _ = licz()

    for _ in range(DOKLADANE):
        fabryka()

    r = RaportEwaluacjaUpowaznienia()
    r.data = dict(od_roku=rok, do_roku=rok, upowaznienie_pbn=None)
    assert r.get_queryset().count() == 1 + DOKLADANE

    po_dolozeniu, zapytania = licz()
    assert po_dolozeniu == bazowa, (
        f"N+1 w raporcie upoważnień ({export}): {bazowa} zapytań dla 1 wiersza, "
        f"{po_dolozeniu} dla {1 + DOKLADANE}:\n"
        + "\n".join(q["sql"] for q in zapytania)
    )
