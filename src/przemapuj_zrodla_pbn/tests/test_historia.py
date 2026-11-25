"""Przemapowanie i usunięcie źródła skasowanego w PBN zostawia ślad
w historii rekordów (FD#508)."""

import pytest
from django.contrib.admin.models import CHANGE, DELETION, LogEntry
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Zrodlo
from przemapuj_zrodla_pbn.models import PrzeMapowanieZrodla


def _journal(**kwargs):
    defaults = {
        "title": "",
        "issn": "",
        "eissn": "",
        "websiteLink": "",
        "mniswId": None,
    }
    defaults.update(kwargs)
    return baker.make("pbn_api.Journal", **defaults)


def _wpisy(model, pk):
    return LogEntry.objects.filter(
        content_type__model=model, object_id=str(pk)
    ).order_by("pk")


@pytest.fixture
def przemapowanie_pbn(client, redaktor):
    """Wykonaj przemapowanie źródła skasowanego w PBN na aktywne."""
    client.force_login(redaktor)
    skasowany = _journal(status="DELETED", title="Stara", issn="1234-5678")
    zrodlo_stare = baker.make(
        Zrodlo, nazwa="Stara gazeta", pbn_uid=skasowany, issn="1234-5678"
    )
    aktywny = _journal(
        status="ACTIVE", title="Stara Nowa", issn="1234-5678", mniswId=999
    )
    zrodlo_nowe = baker.make(
        Zrodlo, nazwa="Nowa gazeta", pbn_uid=aktywny, issn="1234-5678"
    )
    prace = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo_stare, _quantity=2)
    obca = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo_nowe)

    resp = client.post(
        reverse(
            "przemapuj_zrodla_pbn:przemapuj_zrodlo",
            kwargs={"zrodlo_id": zrodlo_stare.pk},
        ),
        {"typ_wyboru": "zrodlo", "zrodlo_docelowe": zrodlo_nowe.pk, "confirm": "1"},
    )
    assert resp.status_code == 302
    return {
        "skasowany": skasowany,
        "prace": prace,
        "obca": obca,
        "operacja": PrzeMapowanieZrodla.objects.get(),
    }


@pytest.mark.django_db
def test_przemapowanie_zrodla_pbn_w_historii_kazdej_pracy(przemapowanie_pbn, redaktor):
    operacja = przemapowanie_pbn["operacja"]
    for praca in przemapowanie_pbn["prace"]:
        wpis = _wpisy("wydawnictwo_ciagle", praca.pk).get()
        assert wpis.action_flag == CHANGE
        assert wpis.user == redaktor
        assert "Stara gazeta" in wpis.change_message
        assert "Nowa gazeta" in wpis.change_message
        # UID skasowanego czasopisma i numer operacji — po nim redaktor
        # trafia do logu przemapowań.
        assert f"UID {przemapowanie_pbn['skasowany'].pk}" in wpis.change_message
        assert f"nr {operacja.pk}" in wpis.change_message


@pytest.mark.django_db
def test_przemapowanie_zrodla_pbn_nie_rusza_historii_innych_prac(przemapowanie_pbn):
    obca = przemapowanie_pbn["obca"]
    assert not _wpisy("wydawnictwo_ciagle", obca.pk).exists()


@pytest.mark.django_db
def test_usuniecie_zrodla_skasowanego_w_pbn_w_historii(client, redaktor):
    client.force_login(redaktor)
    zrodlo = baker.make(
        Zrodlo, nazwa="Do usunięcia", pbn_uid=_journal(status="DELETED")
    )
    pk = zrodlo.pk

    resp = client.post(
        reverse("przemapuj_zrodla_pbn:usun_zrodlo", kwargs={"zrodlo_id": pk})
    )

    assert resp.status_code == 302
    assert not Zrodlo.objects.filter(pk=pk).exists()
    wpis = _wpisy("zrodlo", pk).get()
    assert wpis.action_flag == DELETION
    assert wpis.user == redaktor


@pytest.mark.django_db
def test_strona_operacji_linkuje_do_przemapowanych_rekordow(
    przemapowanie_pbn, admin_client
):
    operacja = przemapowanie_pbn["operacja"]
    prace = przemapowanie_pbn["prace"]

    resp = admin_client.get(
        reverse(
            "admin:przemapuj_zrodla_pbn_przemapowaniezrodla_change",
            args=[operacja.pk],
        )
    )

    assert resp.status_code == 200
    tresc = resp.content.decode()
    for praca in prace:
        assert reverse("admin:bpp_wydawnictwo_ciagle_change", args=[praca.pk]) in tresc
        assert reverse("admin:bpp_wydawnictwo_ciagle_history", args=[praca.pk]) in tresc

    # Link „pokaż wszystkie” prowadzi do listy dokładnie tych rekordów.
    lista = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    ids = ",".join(str(p.pk) for p in sorted(prace, key=lambda p: p.pk))
    assert f"{lista}?id__in={ids}" in tresc
    resp = admin_client.get(lista, {"id__in": ids})
    assert resp.status_code == 200
    assert set(resp.context["cl"].queryset) == set(prace)


@pytest.mark.django_db
def test_strona_historia_pracy_pokazuje_przemapowanie(przemapowanie_pbn, admin_client):
    """To, co widzi redaktor: strona „Historia” przemapowanej pracy."""
    operacja = przemapowanie_pbn["operacja"]
    praca = przemapowanie_pbn["prace"][0]

    resp = admin_client.get(
        reverse("admin:bpp_wydawnictwo_ciagle_history", args=[praca.pk])
    )

    assert resp.status_code == 200
    tresc = resp.content.decode()
    assert "Przemapowano źródło skasowane w PBN" in tresc
    assert f"przemapowanie źródeł PBN nr {operacja.pk}" in tresc
    assert "redaktor-przemapuj" in tresc
