from django.urls import reverse

from fixtures.conftest_publications import _wydawnictwo_ciagle_maker
from raport_slotow.tests.conftest import _rekord_slotu_maker
from raport_slotow.views import ewaluacja

from bpp.models import Autor_Dyscyplina


def test_raport_ewaluacja_no_queries(
    django_assert_max_num_queries,
    admin_client,
    rok,
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    jezyki,
    typy_odpowiedzialnosci,
):
    Autor_Dyscyplina.objects.create(
        rok=rok, autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1
    )

    # 20 rekordów wystarcza: N+1 dałoby >= 20 dodatkowych zapytań przy limicie 16.
    # UWAGA: zapytanie niżej filtruje lata 2017-2021, a rekordy są z ``rok``
    # (bieżący), więc eksport XLSX jest pusty. Przy ``od_roku=do_roku=rok``
    # widok robi 2 zapytania na wiersz (``Rekord.openaccess_licencja_id``
    # i ``Autor.system_kadrowy_id`` doczytywane leniwie) i ten test pada.
    for a in range(20):
        wydawnictwo = _wydawnictwo_ciagle_maker()
        wydawnictwo.dodaj_autora(autor_jan_kowalski, jednostka)

        _rekord_slotu_maker(
            autor_jan_kowalski, jednostka, dyscyplina1, wydawnictwo, rok
        )

    url = reverse(
        "raport_slotow:raport-ewaluacja",
    )

    r = ewaluacja.RaportSlotowEwaluacja()
    r.data = dict(od_roku=rok, do_roku=rok, _export="html")
    assert r.get_queryset().count() == 20

    # UWAGA UWAGA UWAGA
    # Jeżeli nagle z jakichś powodów ten raport zacznie generować więcej zapytań, to proszę
    # się nad tym tematem POCHYLIC i nie zwiekszać tej wartosci max_num_queries...
    # Wyjątek: +3 z SiteResolutionMiddleware (Site.get + site.uczelnia + cache lookup)
    # — koszt strukturalny multi-hosting'u, nie logiki raportu.
    with django_assert_max_num_queries(16):
        admin_client.get(
            url,
            data={
                "od_roku": 2017,
                "do_roku": 2021,
                "_export": "xlsx",
            },
        )
