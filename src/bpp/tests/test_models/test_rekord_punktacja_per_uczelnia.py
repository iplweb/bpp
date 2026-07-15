"""Track 1 (audyt uczelnia 2026-06-04): tabela punktacji na stronie rekordu
pokazuje sloty/punkty TYLKO uczelni oglądającego.

``Rekord.punktacja_autora`` / ``punktacja_dyscypliny`` / ``ma_punktacje_sloty``
filtrowały tylko po ``rekord_id`` → publiczna strona rekordu (renderowana na
domenie jednej uczelni) pokazywała CPD/CPA wszystkich uczelni współautorskiego
rekordu. Widok ustawia ``rekord._uczelnia_ogladajacego``; metody zawężają
(CPD po ``uczelnia``, CPA po ``jednostka__uczelnia``).
"""

import pytest
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models import (
    Cache_Punktacja_Autora,
    Cache_Punktacja_Dyscypliny,
    Jednostka,
    Uczelnia,
    Wydzial,
)
from bpp.models.cache import Rekord
from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu


@pytest.fixture
def jednostka_drugiej_uczelni(db):
    site = baker.make(Site, domain="druga-rek.testserver", name="druga-rek")
    uczelnia2 = Uczelnia.objects.create(skrot="DRR", nazwa="Druga", site=site)
    wydzial = Wydzial.objects.create(uczelnia=uczelnia2, skrot="W2", nazwa="Wydz II")
    return Jednostka.objects.create(
        nazwa="Jedn II",
        skrot="JDR",
        parent=znajdz_lub_utworz_wezel_wydzialu(wydzial)[0],
        uczelnia=uczelnia2,
    )


@pytest.mark.django_db
def test_punktacja_rekordu_zaweza_do_uczelni_ogladajacego(
    autor_jan_kowalski, jednostka, jednostka_drugiej_uczelni, dyscyplina1
):
    uczelnia1 = jednostka.uczelnia
    uczelnia2 = jednostka_drugiej_uczelni.uczelnia
    rid = [1, 999]

    for ucz in (uczelnia1, uczelnia2):
        Cache_Punktacja_Dyscypliny.objects.create(
            rekord_id=rid,
            dyscyplina=dyscyplina1,
            uczelnia=ucz,
            pkd=50,
            slot=20,
            autorzy_z_dyscypliny=[autor_jan_kowalski.pk],
            zapisani_autorzy_z_dyscypliny=["x"],
        )
    for jedn in (jednostka, jednostka_drugiej_uczelni):
        Cache_Punktacja_Autora.objects.create(
            rekord_id=rid,
            autor=autor_jan_kowalski,
            jednostka=jedn,
            dyscyplina=dyscyplina1,
            pkdaut=50,
            slot=20,
        )

    rekord = Rekord()
    rekord.id = (1, 999)
    rekord._uczelnia_ogladajacego = uczelnia1

    cpd_uczelnie = set(
        rekord.punktacja_dyscypliny.values_list("uczelnia_id", flat=True)
    )
    cpa_uczelnie = set(
        rekord.punktacja_autora.values_list("jednostka__uczelnia_id", flat=True)
    )

    assert cpd_uczelnie == {uczelnia1.pk}
    assert cpa_uczelnie == {uczelnia1.pk}
    assert rekord.ma_punktacje_sloty is True


@pytest.mark.django_db
def test_punktacja_rekordu_bez_uczelni_globalnie(
    autor_jan_kowalski, jednostka, dyscyplina1
):
    """Bez ``_uczelnia_ogladajacego`` (np. admin) zachowanie globalne — brak
    regresji w kontekstach, które nie ustawiają uczelni oglądającego."""
    uczelnia1 = jednostka.uczelnia
    rid = [1, 998]
    Cache_Punktacja_Dyscypliny.objects.create(
        rekord_id=rid,
        dyscyplina=dyscyplina1,
        uczelnia=uczelnia1,
        pkd=50,
        slot=20,
        autorzy_z_dyscypliny=[autor_jan_kowalski.pk],
        zapisani_autorzy_z_dyscypliny=["x"],
    )

    rekord = Rekord()
    rekord.id = (1, 998)

    assert rekord.punktacja_dyscypliny.count() == 1
