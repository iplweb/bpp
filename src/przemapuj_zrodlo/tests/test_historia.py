"""Przemapowanie źródła (i jego cofnięcie) zapisuje historię każdej pracy."""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Zrodlo


def _wpisy(praca):
    return LogEntry.objects.filter(
        content_type__model="wydawnictwo_ciagle", object_id=str(praca.pk)
    ).order_by("pk")


@pytest.mark.django_db
def test_przemapowanie_i_cofniecie_zrodla_w_historii_prac(admin_client, admin_user):
    zrodlo_z = baker.make(Zrodlo, nazwa="Stare czasopismo", pbn_uid=None)
    zrodlo_do = baker.make(Zrodlo, nazwa="Nowe czasopismo", pbn_uid=None)
    prace = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo_z, _quantity=2)

    resp = admin_client.post(
        reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo_z.slug]),
        {"zrodlo_docelowe": zrodlo_do.pk, "potwierdzenie": "on"},
    )
    assert resp.status_code == 302
    for praca in prace:
        wpis = _wpisy(praca).get()
        assert wpis.action_flag == CHANGE
        assert wpis.user == admin_user
        # Nazwa i identyfikator obu źródeł — dwa źródła mogą nazywać się
        # tak samo (scalanie duplikatów).
        assert f"„Stare czasopismo” (ID {zrodlo_z.pk})" in wpis.change_message
        assert f"„Nowe czasopismo” (ID {zrodlo_do.pk})" in wpis.change_message

    from przemapuj_zrodlo.models import PrzemapowaZrodla

    przemapowanie = PrzemapowaZrodla.objects.get()
    admin_client.post(reverse("przemapuj_zrodlo:cofnij", args=[przemapowanie.pk]))
    for praca in prace:
        assert Wydawnictwo_Ciagle.objects.get(pk=praca.pk).zrodlo == zrodlo_z
        wpisy = list(_wpisy(praca))
        assert len(wpisy) == 2
        assert wpisy[1].change_message.startswith("Cofnięto przemapowanie")
        assert f"(ID {zrodlo_z.pk})" in wpisy[1].change_message
        assert f"(ID {zrodlo_do.pk})" in wpisy[1].change_message


@pytest.mark.django_db
def test_strona_przemapowania_linkuje_do_publikacji(admin_client):
    """Na stronie operacji w logu przemapowań jest lista publikacji
    z linkami do edycji i historii oraz do gotowej listy (FD#508)."""
    from przemapuj_zrodlo.models import PrzemapowaZrodla

    zrodlo_z = baker.make(Zrodlo, nazwa="Stare czasopismo", pbn_uid=None)
    zrodlo_do = baker.make(Zrodlo, nazwa="Nowe czasopismo", pbn_uid=None)
    prace = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo_z, _quantity=2)
    usunieta = baker.make(
        Wydawnictwo_Ciagle, zrodlo=zrodlo_z, tytul_oryginalny="Praca skasowana"
    )
    admin_client.post(
        reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo_z.slug]),
        {"zrodlo_docelowe": zrodlo_do.pk, "potwierdzenie": "on"},
    )
    przemapowanie = PrzemapowaZrodla.objects.get()
    usunieta_pk = usunieta.pk
    usunieta.hard_delete()

    resp = admin_client.get(
        reverse(
            "admin:przemapuj_zrodlo_przemapowazrodla_change",
            args=[przemapowanie.pk],
        )
    )

    assert resp.status_code == 200
    tresc = resp.content.decode()
    for praca in prace:
        assert reverse("admin:bpp_wydawnictwo_ciagle_history", args=[praca.pk]) in tresc
    # Publikacja skasowana po przemapowaniu zostaje na liście, bez linków.
    assert "Praca skasowana" in tresc
    assert (
        reverse("admin:bpp_wydawnictwo_ciagle_change", args=[usunieta_pk]) not in tresc
    )

    lista = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    ids = ",".join(str(p.pk) for p in sorted(prace, key=lambda p: p.pk))
    assert f"{lista}?id__in={ids}" in tresc
    resp = admin_client.get(lista, {"id__in": ids})
    assert resp.status_code == 200
    assert set(resp.context["cl"].queryset) == set(prace)
