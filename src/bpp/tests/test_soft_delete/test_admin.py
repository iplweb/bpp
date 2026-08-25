"""Faza 07: kosz w adminie — filtr, przywracanie, trwałe usuwanie, powód.

KONTRAKT PARAMETRU FILTRA: ``?is_deleted=true`` pokazuje WYŁĄCZNIE kosz,
``?is_deleted=all`` żywe razem z koszem, brak parametru — tylko żywe. Ta
sama semantyka, co w pakietowym ``SoftDeleteFilter`` (``'true'`` mapuje
tam na ``deleted_at__isnull=False``), więc parametr w URL-u nie kłamie.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_changelist_domyslnie_ukrywa_kosz(superuser_client):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url)
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Żywa praca" in content
    assert "Praca w koszu" not in content


@pytest.mark.django_db
def test_filtr_pokazuje_wylacznie_kosz(superuser_client):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url, {"is_deleted": "true"})
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Praca w koszu" in content
    assert "Żywa praca" not in content


@pytest.mark.django_db
def test_filtr_wszystkie_pokazuje_zywe_i_kosz(superuser_client):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url, {"is_deleted": "all"})
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Praca w koszu" in content
    assert "Żywa praca" in content


@pytest.mark.django_db
def test_changeform_otwiera_skasowany_rekord(superuser_client):
    """Bez ``global_objects`` w ``get_queryset`` admin dawałby 302/404 —
    a bez otwarcia rekordu nie ma jak go przywrócić ani obejrzeć."""
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=[skasowany.pk])
    resp = superuser_client.get(url)

    assert resp.status_code == 200


def _log(model, pk, akcja):
    """Najnowszy wpis ``SoftDeleteLog`` dla konkretnego rekordu.

    Filtr po ``content_type`` jest istotny: ``object_id`` nie jest unikalne
    globalnie, a kaskada fazy 02 loguje przy okazji wiersze ``*_Autor``,
    ktore z latwoscia trafiaja na te sama wartosc ``pk``.
    """
    from django.contrib.contenttypes.models import ContentType

    from bpp.models import SoftDeleteLog

    return (
        SoftDeleteLog.objects.filter(
            content_type=ContentType.objects.get_for_model(model),
            object_id=pk,
            akcja=akcja,
        )
        .order_by("-timestamp", "-pk")
        .first()
    )


@pytest.mark.django_db
def test_delete_w_adminie_soft_deletuje_i_zapisuje_usera(superuser, superuser_client):
    """Przycisk „Usuń" na changeformie = kosz, nie fizyczne skasowanie."""
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Do kosza")
    pk = obj.pk
    url = reverse("admin:bpp_wydawnictwo_ciagle_delete", args=[pk])

    assert superuser_client.get(url).status_code == 200

    resp = superuser_client.post(url, {"post": "yes"})
    assert resp.status_code == 302

    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    assert Wydawnictwo_Ciagle.global_objects.get(pk=pk).deleted_at is not None

    wpis = _log(Wydawnictwo_Ciagle, pk, "delete")
    assert wpis is not None
    assert wpis.user_id == superuser.pk


@pytest.mark.django_db
def test_akcja_przywroc_dziala_i_zapisuje_usera(superuser, superuser_client):
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Wraca z kosza")
    pk = obj.pk
    obj.delete(reason="test")
    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()

    # Akcja dziala na tym, co widac na liscie — a kosz widac dopiero pod
    # filtrem. Django POST-uje formularz akcji na biezacy URL RAZEM z
    # query stringiem, wiec tak wyglada realny przeplyw operatora.
    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist") + "?is_deleted=true"
    resp = superuser_client.post(
        url,
        {"action": "przywroc_zaznaczone", "_selected_action": [str(pk)]},
    )
    assert resp.status_code in (200, 302)

    assert Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    assert Wydawnictwo_Ciagle.global_objects.get(pk=pk).deleted_at is None

    wpis = _log(Wydawnictwo_Ciagle, pk, "restore")
    assert wpis is not None
    assert wpis.user_id == superuser.pk


@pytest.mark.django_db
def test_usun_trwale_dostepne_dla_superusera(superuser, superuser_client):
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Do trwałego usunięcia")
    pk = obj.pk
    obj.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist") + "?is_deleted=true"
    assert b"usun_trwale_zaznaczone" in superuser_client.get(url).content

    resp = superuser_client.post(
        url,
        {"action": "usun_trwale_zaznaczone", "_selected_action": [str(pk)]},
    )
    assert resp.status_code in (200, 302)
    assert not Wydawnictwo_Ciagle.global_objects.filter(pk=pk).exists()

    # Rekord zniknal fizycznie, wiec wpis audytu jest jedynym sladem, ze
    # istnial — i ma nosic, KTO go skasowal.
    wpis = _log(Wydawnictwo_Ciagle, pk, "hard_delete")
    assert wpis is not None
    assert wpis.user_id == superuser.pk


@pytest.mark.django_db
def test_usun_trwale_niedostepne_dla_staff(staff_client):
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Próba przez staff")
    pk = obj.pk
    obj.delete(reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist") + "?is_deleted=true"
    assert b"usun_trwale_zaznaczone" not in staff_client.get(url).content

    # Wymuszony POST tez nie usuwa trwale — akcji nie ma w get_actions,
    # wiec Django odrzuca ja jako niedozwolony wybor.
    resp = staff_client.post(
        url,
        {"action": "usun_trwale_zaznaczone", "_selected_action": [str(pk)]},
    )
    assert resp.status_code in (200, 302, 403)
    assert Wydawnictwo_Ciagle.global_objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_usun_trwale_pomija_rekordy_spoza_kosza(superuser_client):
    """Trwale kasujemy WYLACZNIE z kosza.

    ``Cache_Punktacja_*`` nie ma FK do publikacji, wiec sprzata ja dopiero
    receiver ``post_soft_delete``. Twarde skasowanie rekordu zywego
    zostawiloby wiersze punktacji wskazujace na nieistniejacy rekord.
    """
    zywy = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywy, nie do kosza")
    pk = zywy.pk

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist") + "?is_deleted=all"
    resp = superuser_client.post(
        url,
        {"action": "usun_trwale_zaznaczone", "_selected_action": [str(pk)]},
        follow=True,
    )
    assert resp.status_code == 200
    assert Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    assert "Pominięto rekordów spoza kosza: 1" in resp.content.decode("utf-8")
