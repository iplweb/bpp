"""Track 1 (audyt uczelnia 2026-06-04): publiczny ``LataAutocomplete`` zawęża
lata do uczelni oglądającego (jak ``LataView`` w R3a).

Było ``Rekord.objects.all()`` globalnie — picker lat na domenie U1 podpowiadał
lata z rekordów wszystkich uczelni.
"""

import pytest
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Jednostka,
    Uczelnia,
    Wydawnictwo_Ciagle,
)
from bpp.views.autocomplete.simple import LataAutocomplete


@pytest.fixture
def jednostka_drugiej_uczelni(db):
    site = baker.make(Site, domain="druga-lata.testserver", name="druga-lata")
    uczelnia2 = Uczelnia.objects.create(skrot="DRL", nazwa="Druga", site=site)
    wydzial = Jednostka.objects.create(
        uczelnia=uczelnia2, skrot="W2", nazwa="Wydz II", parent=None
    )
    return Jednostka.objects.create(
        nazwa="Jedn II",
        skrot="JDL",
        parent=wydzial,
        uczelnia=uczelnia2,
    )


@pytest.mark.django_db
def test_lata_autocomplete_zaweza_do_uczelni(
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    jednostka_drugiej_uczelni,
    dyscyplina1,
    denorms,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    rf,
):
    uczelnia1 = jednostka.uczelnia

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=2020, dyscyplina_naukowa=dyscyplina1
    )
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, rok=2021, dyscyplina_naukowa=dyscyplina1
    )
    wc1 = baker.make(Wydawnictwo_Ciagle, rok=2020, punkty_kbn=5)
    wc1.dodaj_autora(autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1)
    wc2 = baker.make(Wydawnictwo_Ciagle, rok=2021, punkty_kbn=5)
    wc2.dodaj_autora(
        autor_jan_nowak, jednostka_drugiej_uczelni, dyscyplina_naukowa=dyscyplina1
    )
    denorms.flush()

    request = rf.get("/")
    request._uczelnia = uczelnia1

    view = LataAutocomplete()
    view.q = ""
    view.request = request

    lata = set(view.get_queryset())

    assert 2020 in lata  # U1
    assert 2021 not in lata  # U2 — nie przecieka


@pytest.mark.django_db
def test_lata_autocomplete_single_install_bez_zmian(
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    denorms,
    typy_odpowiedzialnosci,
    charaktery_formalne,
    rf,
):
    """Invariant: przy jednej uczelni picker działa jak dawniej."""
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=2020, dyscyplina_naukowa=dyscyplina1
    )
    wc = baker.make(Wydawnictwo_Ciagle, rok=2020, punkty_kbn=5)
    wc.dodaj_autora(autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1)
    denorms.flush()

    request = rf.get("/")
    request._uczelnia = jednostka.uczelnia

    view = LataAutocomplete()
    view.q = ""
    view.request = request

    assert 2020 in set(view.get_queryset())
