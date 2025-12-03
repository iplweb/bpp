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

    for a in range(100):
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
    assert r.get_queryset().count() == 100

    # UWAGA UWAGA UWAGA
    # Jeżeli nagle z jakichś powodów ten raport zacznie generować więcej zapytań, to proszę
    # się nad tym tematem POCHYLIC i nie zwiekszać tej wartosci max_num_queries...
    with django_assert_max_num_queries(13):
        admin_client.get(
            url,
            data={
                "od_roku": 2017,
                "do_roku": 2021,
                "_export": "xlsx",
            },
        )
