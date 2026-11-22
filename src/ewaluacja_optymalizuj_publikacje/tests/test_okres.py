"""Widok optymalizacji publikacji czyta metryki z okresu ewaluacji, do którego
należy rok publikacji — gdy autor ma metryki w dwóch okresach."""

from decimal import Decimal

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Jednostka,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from ewaluacja_metryki.models import MetrykaAutora


def _metryka(autor, dyscyplina, jednostka, okres, punkty):
    return baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        okres=okres,
        punkty_nazbierane=Decimal(punkty),
        slot_nazbierany=Decimal("1.0"),
        slot_maksymalny=Decimal("4.0"),
        slot_wszystkie=Decimal("1.0"),
        punkty_wszystkie=Decimal(punkty),
        _fill_optional=False,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("rok,oczekiwany", [(2023, "2022"), (2027, "2026")])
def test_optymalizuj_publikacje_metryka_z_okresu_roku_publikacji(
    admin_client, denorms, rodzaj_autora_n, okres_2022, okres_2026, rok, oczekiwany
):
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="Dwuokresowy", imiona="Jan")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka", kod="1.6")
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=rok,
        rodzaj_autora=rodzaj_autora_n,
    )

    metryki = {
        "2022": _metryka(autor, dyscyplina, jednostka, okres_2022, "100.00"),
        "2026": _metryka(autor, dyscyplina, jednostka, okres_2026, "300.00"),
    }

    wydawnictwo = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Praca", rok=rok, punkty_kbn=100
    )
    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
        afiliuje=True,
        typ_odpowiedzialnosci=typ_odp,
    )
    denorms.flush()
    wydawnictwo.refresh_from_db()

    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    res = admin_client.get(url)
    assert res.status_code == 200

    (grupa,) = res.context["autorzy_po_dyscyplinach"]
    (autor_data,) = grupa["autorzy"]
    oczekiwana = metryki[oczekiwany]
    assert autor_data["metryka_id"] == oczekiwana.pk
    assert autor_data["metryka"]["punkty_nazbierane"] == (oczekiwana.punkty_nazbierane)
