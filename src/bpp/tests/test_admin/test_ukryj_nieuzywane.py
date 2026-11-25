"""Słowniki: filtr „używane w rekordach” i akcja „Ukryj nieużywane”."""

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.urls import reverse
from model_bakery import baker

from bpp.admin.nieuzywane import (
    KOMUNIKAT_UKRYTO_NIEUZYWANE,
    nieuzywane,
    relacje_wskazujace,
    uzywane,
)
from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Typ_KBN,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.system import Charakter_PBN


def _jezyk(skrot):
    return baker.make(Jezyk, nazwa=f"język {skrot}", skrot=skrot, widoczny=True)


@pytest.mark.django_db
def test_jezyk_uzywany_przez_dowolne_pole_publikacji():
    glowny = _jezyk("t-gl")
    alternatywny = _jezyk("t-alt")
    wolny = _jezyk("t-wolny")
    baker.make(Wydawnictwo_Ciagle, jezyk=glowny)
    baker.make(Wydawnictwo_Zwarte, jezyk_alt=alternatywny)

    qs = Jezyk.objects.filter(pk__in=[glowny.pk, alternatywny.pk, wolny.pk])
    assert set(uzywane(qs)) == {glowny, alternatywny}
    assert set(nieuzywane(qs)) == {wolny}


def test_relacje_pomijaja_rodzica_w_drzewie_charakterow():
    modele = {rel.related_model for rel in relacje_wskazujace(Charakter_Formalny)}
    assert Charakter_Formalny not in modele
    assert Wydawnictwo_Ciagle in modele


@pytest.mark.django_db
def test_charakter_pbn_uzywany_przez_m2m_lub_fk():
    uzywany = baker.make(Charakter_PBN, identyfikator="t-uzywany")
    wolny = baker.make(Charakter_PBN, identyfikator="t-wolny")
    baker.make(Typ_KBN, skrot="t-kbn", nazwa="t-kbn", charakter_pbn=uzywany)

    qs = Charakter_PBN.objects.filter(pk__in=[uzywany.pk, wolny.pk])
    assert set(nieuzywane(qs)) == {wolny}


@pytest.mark.django_db
def test_filtr_w_changeliscie(admin_client):
    uzywany = _jezyk("t-uz")
    wolny = _jezyk("t-wo")
    baker.make(Wydawnictwo_Ciagle, jezyk=uzywany)
    url = reverse("admin:bpp_jezyk_changelist")

    res = admin_client.get(url, {"uzywane": "nie", "q": "t-"})
    assert res.status_code == 200
    assert list(res.context["cl"].result_list) == [wolny]

    res = admin_client.get(url, {"uzywane": "tak", "q": "t-"})
    assert list(res.context["cl"].result_list) == [uzywany]


@pytest.mark.django_db
def test_akcja_ukrywa_tylko_nieuzywane_jezyki(admin_client):
    uzywany = _jezyk("t-uz")
    wolny = _jezyk("t-wo")
    baker.make(Wydawnictwo_Ciagle, jezyk=uzywany)

    res = admin_client.post(
        reverse("admin:bpp_jezyk_changelist"),
        {
            "action": "ukryj_nieuzywane",
            "_selected_action": [uzywany.pk, wolny.pk],
            "potwierdzam": "1",
        },
        follow=True,
    )

    assert res.status_code == 200
    uzywany.refresh_from_db()
    wolny.refresh_from_db()
    assert uzywany.widoczny is True
    assert wolny.widoczny is False
    tresc = [str(m) for m in res.context["messages"]]
    assert any("Ukryto 1" in t and "Pominięto 1" in t for t in tresc), tresc
    assert LogEntry.objects.filter(
        object_id=str(wolny.pk),
        action_flag=CHANGE,
        change_message=KOMUNIKAT_UKRYTO_NIEUZYWANE,
    ).exists()


@pytest.mark.django_db
def test_akcja_ustawia_ukryty_dla_charakteru_formalnego(admin_client):
    uzywany = baker.make(Charakter_Formalny, skrot="t-uz", nazwa="t-uz", ukryty=False)
    wolny = baker.make(Charakter_Formalny, skrot="t-wo", nazwa="t-wo", ukryty=False)
    baker.make(Wydawnictwo_Zwarte, charakter_formalny=uzywany)

    admin_client.post(
        reverse("admin:bpp_charakter_formalny_changelist"),
        {
            "action": "ukryj_nieuzywane",
            "_selected_action": [uzywany.pk, wolny.pk],
            "potwierdzam": "1",
        },
    )

    uzywany.refresh_from_db()
    wolny.refresh_from_db()
    assert uzywany.ukryty is False
    assert wolny.ukryty is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "nazwa",
    ["bpp_jezyk", "bpp_charakter_formalny", "bpp_typ_kbn", "bpp_charakter_pbn"],
)
def test_changelist_z_filtrem_nieuzywane_dziala(admin_client, nazwa):
    res = admin_client.get(reverse(f"admin:{nazwa}_changelist"), {"uzywane": "nie"})
    assert res.status_code == 200
    for akcja in (
        b"ukryj_wszystkie_nieuzywane",
        b"ukryj_nieuzywane",
        b"ukryj_zaznaczone",
        b"pokaz_zaznaczone",
    ):
        assert b'value="' + akcja + b'"' in res.content
    # Usuwanie dalej tylko dla grupy „administracja”.
    assert b'value="delete_selected"' not in res.content


def _post_akcji(client, akcja, pks):
    return client.post(
        reverse("admin:bpp_jezyk_changelist"),
        {"action": akcja, "_selected_action": pks},
        follow=True,
    )


@pytest.mark.django_db
def test_ukryj_i_pokaz_zaznaczone(admin_client):
    uzywany = _jezyk("t-uz")
    wolny = _jezyk("t-wo")
    baker.make(Wydawnictwo_Ciagle, jezyk=uzywany)

    res = _post_akcji(admin_client, "ukryj_zaznaczone", [uzywany.pk, wolny.pk])
    uzywany.refresh_from_db()
    wolny.refresh_from_db()
    assert (uzywany.widoczny, wolny.widoczny) == (False, False)
    tresc = " ".join(str(m) for m in res.context["messages"])
    assert "Ukryto 2" in tresc and "1 z zaznaczonych jest używana" in tresc

    _post_akcji(admin_client, "pokaz_zaznaczone", [uzywany.pk, wolny.pk])
    uzywany.refresh_from_db()
    wolny.refresh_from_db()
    assert (uzywany.widoczny, wolny.widoczny) == (True, True)


@pytest.mark.django_db
def test_pokaz_zaznaczone_charakter_formalny(admin_client):
    ch = baker.make(Charakter_Formalny, skrot="t-ch", nazwa="t-ch", ukryty=True)
    admin_client.post(
        reverse("admin:bpp_charakter_formalny_changelist"),
        {"action": "pokaz_zaznaczone", "_selected_action": [ch.pk]},
    )
    ch.refresh_from_db()
    assert ch.ukryty is False
