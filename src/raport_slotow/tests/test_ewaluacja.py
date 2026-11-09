import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from fixtures.conftest_publications import _wydawnictwo_ciagle_maker
from raport_slotow.tests.conftest import _rekord_slotu_maker
from raport_slotow.views import ewaluacja

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Funkcja_Autora,
    Licencja_OpenAccess,
)


#: Ile rekordów dokładamy po pomiarze bazowym. Raport bez N+1 wykonuje tyle
#: samo zapytań dla 1 co dla ``1 + DOKLADANE`` wierszy.
DOKLADANE = 3


def _licz_zapytania(client, url, data):
    with CaptureQueriesContext(connection) as ctx:
        res = client.get(url, data=data)
    assert res.status_code == 200, res.content[:500]
    return len(ctx.captured_queries), ctx.captured_queries


@pytest.mark.parametrize("export", ["xlsx", "html"])
def test_raport_ewaluacja_bez_n_plus_jeden(
    export,
    admin_client,
    rok,
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    jezyki,
    typy_odpowiedzialnosci,
):
    """Liczba zapytań raportu nie rośnie z liczbą wierszy (brak N+1).

    Nie sprawdzamy bezwzględnej liczby zapytań (zmienia się przy każdej
    refaktoryzacji middleware), tylko jej niezmienność wobec liczby wierszy.
    Rekordy mają ustawioną licencję OpenAccess, a autor ``system_kadrowy_id``
    i funkcję — kolumny licencji i systemu kadrowego dawniej doczytywały się
    leniwie per wiersz.
    """
    Autor_Dyscyplina.objects.create(
        rok=rok, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1
    )
    autor_jan_kowalski.system_kadrowy_id = 12345
    autor_jan_kowalski.save()

    licencja = baker.make(Licencja_OpenAccess, nazwa="Licencja testowa", skrot="TST")
    funkcja = baker.make(Funkcja_Autora)

    def fabryka():
        wydawnictwo = _wydawnictwo_ciagle_maker()
        wydawnictwo.openaccess_licencja = licencja
        wydawnictwo.save()
        wydawnictwo.dodaj_autora(autor_jan_kowalski, jednostka)
        _rekord_slotu_maker(
            autor_jan_kowalski, jednostka, dyscyplina1, wydawnictwo, rok
        )
        # ``aktualna_funkcja`` ustawia trigger z ``Autor_Jednostka`` — dopiero
        # po ``dodaj_autora`` nadpisujemy ją bezpośrednio w bazie.
        Autor.objects.filter(pk=autor_jan_kowalski.pk).update(
            aktualna_funkcja=funkcja
        )

    url = reverse("raport_slotow:raport-ewaluacja")
    data = {"od_roku": rok, "do_roku": rok, "_export": export}

    fabryka()
    _licz_zapytania(admin_client, url, data)  # rozgrzewka (Site, Uczelnia, CT)
    bazowa, _ = _licz_zapytania(admin_client, url, data)

    for _ in range(DOKLADANE):
        fabryka()

    r = ewaluacja.RaportSlotowEwaluacja()
    r.data = dict(od_roku=rok, do_roku=rok, upowaznienie_pbn=None)
    assert r.get_queryset().count() == 1 + DOKLADANE

    po_dolozeniu, zapytania = _licz_zapytania(admin_client, url, data)
    assert po_dolozeniu == bazowa, (
        f"N+1 w raporcie ewaluacji ({export}): {bazowa} zapytań dla 1 wiersza, "
        f"{po_dolozeniu} dla {1 + DOKLADANE}:\n"
        + "\n".join(q["sql"] for q in zapytania)
    )
