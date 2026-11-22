"""Admin kosza: uprawnienia akcji, PBN na stronie potwierdzenia, rekord
z kosza tylko do odczytu, wyszarzony „Usuń" dla rekordu z PBN UID (FD#539)."""

import pytest
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.models import Wydawnictwo_Ciagle
from pbn_export_queue.models import PBN_Export_Queue


def _z_pbn_uid(rekord):
    from pbn_api.models import Publication

    rekord.pbn_uid = baker.make(Publication)
    rekord.save()
    return rekord


@pytest.mark.django_db
def test_fd539_przycisk_usun_wyszarzony_z_wyjasnieniem(superuser_client):
    wc = _z_pbn_uid(baker.make(Wydawnictwo_Ciagle))
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=[wc.pk])

    tresc = superuser_client.get(url).content.decode("utf-8")

    assert 'aria-disabled="true"' in tresc
    assert "ma odpowiednik w PBN" in tresc
    assert reverse("admin:bpp_wydawnictwo_ciagle_delete", args=[wc.pk]) not in tresc


@pytest.mark.django_db
def test_akcja_kosza_pomija_rekord_z_pbn_uid(superuser_client):
    """Akcja masowa sprawdza uprawnienie PER REKORD (FD#539)."""
    wc = _z_pbn_uid(baker.make(Wydawnictwo_Ciagle))
    zwykly = baker.make(Wydawnictwo_Ciagle)

    superuser_client.post(
        reverse("admin:bpp_wydawnictwo_ciagle_changelist"),
        {
            "action": "usun_do_kosza",
            "_selected_action": [str(wc.pk), str(zwykly.pk)],
            "powod_potwierdzony": "1",
        },
    )

    assert Wydawnictwo_Ciagle.objects.filter(pk=wc.pk).exists()
    assert not Wydawnictwo_Ciagle.objects.filter(pk=zwykly.pk).exists()


@pytest.mark.django_db
def test_akcje_kosza_wymagaja_uprawnienia_delete(rf):
    """User z prawem zmiany, ale BEZ prawa usuwania, nie dostaje akcji
    kosza; bez prawa zmiany — nie dostaje „Przywróć"."""
    from django.contrib import admin
    from django.contrib.auth.models import Permission

    user = baker.make("bpp.BppUser", is_staff=True)

    def daj(*codenames):
        user.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label="bpp", codename__in=codenames
            )
        )
        # cache uprawnień Django
        for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            user.__dict__.pop(attr, None)

    model_admin = admin.site._registry[Wydawnictwo_Ciagle]
    request = rf.get("/")
    request.user = user

    daj("view_wydawnictwo_ciagle", "change_wydawnictwo_ciagle")
    akcje = model_admin.get_actions(request)
    assert "usun_do_kosza" not in akcje
    assert "przywroc_zaznaczone" not in akcje

    daj("view_wydawnictwo_ciagle", "delete_wydawnictwo_ciagle")
    akcje = model_admin.get_actions(request)
    assert "usun_do_kosza" in akcje
    assert "przywroc_zaznaczone" not in akcje

    daj(
        "view_wydawnictwo_ciagle",
        "change_wydawnictwo_ciagle",
        "delete_wydawnictwo_ciagle",
    )
    akcje = model_admin.get_actions(request)
    assert {"usun_do_kosza", "przywroc_zaznaczone"} <= set(akcje)
    assert "usun_trwale_zaznaczone" not in akcje


@pytest.mark.django_db
def test_potwierdzenie_odmawia_gdy_rekord_w_kolejce_pbn(
    superuser, superuser_client, bez_celery
):
    from pbn_export_queue.operacje import KOMUNIKAT_REKORD_W_KOLEJCE

    wc = baker.make(Wydawnictwo_Ciagle)
    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wc,
        zamowil=superuser,
        operacja=PBN_Export_Queue.Operacja.WYSYLKA,
        wysylke_zakonczono=None,
    )
    url = reverse("admin:bpp_wydawnictwo_ciagle_delete", args=[wc.pk])

    tresc = superuser_client.get(url).content.decode("utf-8")
    assert KOMUNIKAT_REKORD_W_KOLEJCE in tresc
    assert "Tak, przenieś do kosza" not in tresc

    # Ręcznie spreparowany POST też nie przechodzi.
    superuser_client.post(url, {"post": "yes"})
    assert Wydawnictwo_Ciagle.objects.filter(pk=wc.pk).exists()


@pytest.mark.django_db
def test_stan_pbn_przed_koszem_zglasza_wycofanie():
    """Strona potwierdzenia mówi „zostanie wycofany z PBN", gdy rekord ma
    PBN UID (w adminie takie rekordy są dziś nieusuwalne — FD#539 — ale
    przepływ jest gotowy na kolejkę usuwania z PBN)."""
    from bpp.admin.helpers.mixins import BppSoftDeleteAdminMixin

    wc = _z_pbn_uid(baker.make(Wydawnictwo_Ciagle))
    stan = BppSoftDeleteAdminMixin().stan_pbn_przed_koszem(wc)
    assert stan["wycofanie"] is True
    assert stan["blokada"] is None


@pytest.mark.django_db
def test_rekord_z_kosza_tylko_do_odczytu(superuser_client):
    wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Stary tytuł")
    wc.delete()
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=[wc.pk])

    resp = superuser_client.get(url)
    assert resp.status_code == 200
    assert "Rekord jest w koszu" in resp.content.decode("utf-8")

    superuser_client.post(url, {"tytul_oryginalny": "Nowy tytuł"})
    wc.refresh_from_db()
    assert wc.tytul_oryginalny == "Stary tytuł"


@pytest.mark.django_db
def test_usun_w_adminie_nie_zapisuje_deletion_tylko_change(
    superuser, superuser_client, bez_celery
):
    from django.contrib.admin.models import DELETION, LogEntry

    wc = baker.make(Wydawnictwo_Ciagle)
    url = reverse("admin:bpp_wydawnictwo_ciagle_delete", args=[wc.pk])
    superuser_client.post(url, {"post": "yes", "powod": "dubel"})

    wpisy = LogEntry.objects.filter(object_id=str(wc.pk))
    assert not wpisy.filter(action_flag=DELETION).exists()
    # FD#587: publikacje są w reversion — kosz to rewizja z powodem.
    assert [v.revision.comment for v in Version.objects.get_for_object(wc)] == [
        "Przeniesiono do kosza (powód: dubel)"
    ]
