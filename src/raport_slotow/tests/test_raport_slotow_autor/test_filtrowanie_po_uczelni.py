"""Testy filtrowania RaportSlotowAutor po uczelni oglądającego (Task 7).

Scenariusz: jeden autor z wpisami cache w DWÓCH uczelniach.
Widok podpięty pod uczelnię U1 powinien zwracać wyłącznie wiersze
z uczelnia_id == U1.
"""

import pytest
from model_bakery import baker

from bpp.models import Cache_Punktacja_Autora_Query_View
from raport_slotow import const
from raport_slotow.tests.conftest import _rekord_slotu_maker
from raport_slotow.views.autor import RaportSlotow


def _build_request(uczelnia, user, rf):
    """Fake GET request z ustawioną _uczelnia i user."""
    req = rf.get("/")
    req._uczelnia = uczelnia
    req.user = user
    return req


def _make_view(autor, request, rok):
    """Tworzy i konfiguruje instancję RaportSlotow bez przechodzenia przez get()."""
    view = RaportSlotow()
    view.request = request
    view.kwargs = {
        "od_roku": rok,
        "do_roku": rok,
        "dzialanie": const.DZIALANIE_WSZYSTKO,
        "minimalny_pk": None,
        "slot": None,
    }
    view.autor = autor
    return view


@pytest.mark.django_db
def test_get_tables_zwraca_tylko_wiersze_wlasnej_uczelni(
    autor_jan_kowalski,
    jednostka,
    jednostka_drugiej_uczelni,
    dyscyplina1,
    wydawnictwo_ciagle_z_autorem,
    wydawnictwo_ciagle,
    rok,
    rf,
):
    """Widok pod uczelnią U1 nie pokazuje rekordów cache z U2."""
    uczelnia1 = jednostka.uczelnia
    uczelnia2 = jednostka_drugiej_uczelni.uczelnia

    # Utwórz rekord cache dla autora w uczelni U1
    _rekord_slotu_maker(
        autor_jan_kowalski,
        jednostka,
        dyscyplina1,
        wydawnictwo_ciagle_z_autorem,
        rok,
    )

    # Utwórz drugi rekord cache dla tego samego autora w uczelni U2
    _rekord_slotu_maker(
        autor_jan_kowalski,
        jednostka_drugiej_uczelni,
        dyscyplina1,
        wydawnictwo_ciagle,
        rok,
    )

    # Upewnij się, że oba wiersze widoku faktycznie istnieją w DB
    all_rows = Cache_Punktacja_Autora_Query_View.objects.filter(
        autor=autor_jan_kowalski
    )
    assert all_rows.count() == 2, (
        f"Oczekiwano 2 wierszy w widoku, znaleziono {all_rows.count()}"
    )

    uczelnia_ids_in_view = set(
        all_rows.values_list("uczelnia_id", flat=True)
    )
    assert uczelnia1.pk in uczelnia_ids_in_view
    assert uczelnia2.pk in uczelnia_ids_in_view

    # Zbuduj request dla uczelni U1
    user = baker.make("bpp.BppUser", is_superuser=False)
    request = _build_request(uczelnia1, user, rf)

    view = _make_view(autor_jan_kowalski, request, rok)
    tables = view.get_tables()

    # Zbierz wszystkie wiersze ze zwróconych tabel.
    # django_tables2 opakowuje queryset w TableQuerysetData;
    # surowy queryset siedzi pod .data.data (atrybut wewnętrzny).
    returned_uczelnia_ids = set()
    for table in tables:
        qs = table.data.data
        returned_uczelnia_ids.update(qs.values_list("uczelnia_id", flat=True))

    assert returned_uczelnia_ids == {uczelnia1.pk}, (
        f"Widok zwrócił wiersze z uczelni: {returned_uczelnia_ids!r}, "
        f"oczekiwano tylko {uczelnia1.pk!r}"
    )
