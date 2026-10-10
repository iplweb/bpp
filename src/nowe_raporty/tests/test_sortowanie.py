"""Wybór porządku sortowania raportu (FD467).

Raport ma domyślnie kolejność zapisaną w ``ColumnOrder`` tabeli (rok malejąco,
potem opis). Zgłoszenie FD467 prosi o spis uporządkowany wg nazwisk autorów —
stąd wybór w formularzu, przekazywany querystringiem do widoku generującego.
"""

import pytest
from model_bakery import baker

from nowe_raporty import sortowanie
from nowe_raporty.forms import form_class_dla
from nowe_raporty.models import DefinicjaRaportu
from nowe_raporty.seeding import seed_default_reports
from nowe_raporty.views import RaportGenerujView, _redirect_do_generuj

from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle


@pytest.fixture
def prace_dwoch_autorow(typy_odpowiedzialnosci, denorms):
    """Dwie prace w jednej jednostce: Zielińskiego i Abackiego.

    Nazwiska dobrane tak, żeby porządek alfabetyczny był ODWROTNY do kolejności
    wstawiania — inaczej test przechodziłby także bez sortowania.

    ``denorms.flush()`` jest konieczny: ``opis_bibliograficzny_autorzy_cache``
    to pole denormalizowane, więc bez przeliczenia zostaje puste i sortowanie
    po nim nie miałoby czego porównywać.
    """
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autorzy = []
    for nazwisko, imiona in (("Zieliński", "Jan"), ("Abacki", "Adam")):
        autor = baker.make(Autor, nazwisko=nazwisko, imiona=imiona)
        praca = baker.make(Wydawnictwo_Ciagle, rok=2020, punkty_kbn=10)
        praca.dodaj_autora(autor, jednostka, zapisany_jako=nazwisko)
        autorzy.append(autor)
    denorms.flush()
    return jednostka, autorzy


def _widok(definicja, obiekt, request):
    v = RaportGenerujView()
    v.kwargs = dict(slug=definicja.slug, od_roku=2020, do_roku=2020)
    v.object = obiekt
    v.request = request
    return v


@pytest.mark.django_db
def test_sortowanie_po_autorach_ustawia_order_by_raportu(rf, prace_dwoch_autorow):
    jednostka, _autorzy = prace_dwoch_autorow
    seed_default_reports()
    definicja = DefinicjaRaportu.objects.get(slug="raport-jednostek")

    v = _widok(
        definicja,
        jednostka,
        rf.get("/", data={"sortowanie": sortowanie.WG_AUTOROW}),
    )
    ret = v.get_context_data()

    assert ret["report"].order_by == sortowanie.WG_AUTOROW_POLA


@pytest.mark.django_db
def test_bez_parametru_raport_zachowuje_kolejnosc_z_columnorder(
    rf, prace_dwoch_autorow
):
    # Regresja dla istniejących instalacji: brak parametru nie może nadpisywać
    # sortowania zapisanego w tabeli.
    jednostka, _autorzy = prace_dwoch_autorow
    seed_default_reports()
    definicja = DefinicjaRaportu.objects.get(slug="raport-jednostek")

    v = _widok(definicja, jednostka, rf.get("/"))
    ret = v.get_context_data()

    assert not ret["report"].order_by


@pytest.mark.django_db
def test_rekord_sortuje_sie_po_nazwisku_pierwszego_autora(prace_dwoch_autorow):
    # Założenie, na którym stoi cała funkcja: PostgreSQL porównuje ArrayField
    # element po elemencie, więc ORDER BY po opis_bibliograficzny_autorzy_cache
    # daje porządek wg nazwiska PIERWSZEGO autora.
    jednostka, _autorzy = prace_dwoch_autorow

    posortowane = Rekord.objects.prace_jednostki(jednostka).order_by(
        "opis_bibliograficzny_autorzy_cache"
    )

    nazwiska = [r.opis_bibliograficzny_autorzy_cache[0] for r in posortowane]
    assert nazwiska == ["Abacki Adam", "Zieliński Jan"]


@pytest.mark.django_db
def test_formularz_domyslnie_nie_zmienia_sortowania(prace_dwoch_autorow):
    jednostka, _autorzy = prace_dwoch_autorow
    seed_default_reports()
    definicja = DefinicjaRaportu.objects.get(slug="raport-jednostek")

    form = form_class_dla(definicja)()

    assert form.fields["sortowanie"].initial == sortowanie.DOMYSLNE


@pytest.mark.django_db
def test_formularz_przekazuje_wybor_sortowania_do_url(prace_dwoch_autorow):
    # Wybór musi przeżyć skok formularz -> redirect -> widok generujący, bo to
    # querystring jest jedynym nośnikiem parametrów raportu (tak samo niesie
    # ``_export``, więc eksport do DOCX/XLSX dostaje ten sam porządek).
    jednostka, _autorzy = prace_dwoch_autorow
    seed_default_reports()
    definicja = DefinicjaRaportu.objects.get(slug="raport-jednostek")

    form = form_class_dla(definicja)(
        data={
            "obiekt": jednostka.pk,
            "od_roku": 2020,
            "do_roku": 2020,
            "_export": "html",
            "sortowanie": sortowanie.WG_AUTOROW,
        }
    )
    assert form.is_valid(), form.errors

    response = _redirect_do_generuj(form.cleaned_data, form.POLA_PRZEKAZYWANE)

    assert f"sortowanie={sortowanie.WG_AUTOROW}" in response.url
