"""Zgłoszenia publikacji w zbiorczym koszu BPP (jak publikacje i słowniki).

Filtr „♻️ Kosz", „Usuń do kosza" z powodem, „♻️ Przywróć" (akcja i przycisk),
zgłoszenie z kosza tylko do odczytu, trigger zamrożenia, zgłoszenia skasowane
starym mechanizmem widoczne w koszu, autorzy i załączniki ukryci razem
z rodzicem, strona publiczna nie pokazuje zgłoszeń z kosza.
"""

import uuid

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, connection, transaction
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker
from reversion.models import Version

from bpp.models.soft_delete import jest_bledem_kosza, operacja_kosza
from bpp.models.soft_delete_log import SoftDeleteLog
from zglos_publikacje.admin.filters import StanObslugiFilter
from zglos_publikacje.models import (
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Autor,
    Zgloszenie_Publikacji_Zalacznik,
)

CHANGELIST = "admin:zglos_publikacje_zgloszenie_publikacji_changelist"


def _url(nazwa, zgl):
    return reverse(
        f"admin:zglos_publikacje_zgloszenie_publikacji_{nazwa}", args=[zgl.pk]
    )


@pytest.fixture
def zgloszenie(db):
    zgl = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Zgłoszenie do kosza",
        email="autor@example.com",
        rok=2024,
        status=Zgloszenie_Publikacji.Statusy.NOWY,
        kod_do_edycji=uuid.uuid4(),
    )
    baker.make(Zgloszenie_Publikacji_Autor, rekord=zgl, rok=2024)
    baker.make(
        Zgloszenie_Publikacji_Zalacznik,
        zgloszenie=zgl,
        oryginalna_nazwa_pliku="plik.pdf",
    )
    return zgl


def _log(zgl, akcja):
    return SoftDeleteLog.objects.filter(
        content_type=ContentType.objects.get_for_model(Zgloszenie_Publikacji),
        object_id=zgl.pk,
        akcja=akcja,
    ).first()


@pytest.mark.django_db
def test_usun_w_adminie_przenosi_do_kosza_z_powodem(
    superuser, superuser_client, zgloszenie
):
    url = _url("delete", zgloszenie)
    resp = superuser_client.get(url)
    assert resp.status_code == 200
    assert "Usuń do kosza" in resp.content.decode()

    resp = superuser_client.post(url, {"post": "yes", "powod": "spam"})
    assert resp.status_code == 302

    assert not Zgloszenie_Publikacji.objects.filter(pk=zgloszenie.pk).exists()
    assert Zgloszenie_Publikacji.deleted_objects.filter(pk=zgloszenie.pk).exists()

    # Bez kaskady pakietu: autorzy i załączniki zostają (ukryci z rodzicem).
    assert Zgloszenie_Publikacji_Autor.all_objects.filter(rekord=zgloszenie).count()
    assert Zgloszenie_Publikacji_Zalacznik.all_objects.filter(
        zgloszenie=zgloszenie
    ).count()

    wpis = _log(zgloszenie, SoftDeleteLog.Akcja.DELETE)
    assert wpis is not None
    assert wpis.user_id == superuser.pk
    assert wpis.powod == "spam"

    # Ślad w historii obiektu — od FD#587 zgłoszenia są w reversion, więc
    # kosz to rewizja z powodem (a nie wpis ``LogEntry``).
    assert [v.revision.comment for v in Version.objects.get_for_object(zgloszenie)] == [
        "Przeniesiono do kosza (powód: spam)"
    ]


@pytest.mark.django_db
def test_po_usunieciu_wraca_na_liste_zgloszen(superuser_client, zgloszenie):
    """Edycja zgłoszeń jest wyłączona (``has_change_permission`` = False),
    a mimo to po „Usuń do kosza" wracamy na listę zgłoszeń, nie na stronę
    główną admina — razem z filtrami, z których przyszedł użytkownik."""
    filtry = "status__exact=1"
    url = (
        _url("delete", zgloszenie)
        + "?_changelist_filters="
        + filtry.replace("=", "%3D")
    )
    resp = superuser_client.post(url, {"post": "yes", "powod": "spam"})
    assert resp.status_code == 302
    assert resp["Location"] == reverse(CHANGELIST) + "?" + filtry


@pytest.mark.django_db
def test_filtr_kosza_ostatni_i_domyslnie_bez_kosza(superuser_client, zgloszenie):
    zywe = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Żywe zgłoszenie",
        status=Zgloszenie_Publikacji.Statusy.NOWY,
    )
    zgloszenie.delete(reason="test")

    resp = superuser_client.get(reverse(CHANGELIST))
    assert resp.status_code == 200
    filtry = resp.context["cl"].filter_specs
    assert filtry[-1].title == "♻️ Kosz"
    pks = {o.pk for o in resp.context["cl"].result_list}
    assert zywe.pk in pks
    assert zgloszenie.pk not in pks


@pytest.mark.django_db
def test_tylko_skasowane_pokazuje_caly_kosz_niezaleznie_od_statusu(
    superuser_client, zgloszenie
):
    """„🗑️ Tylko skasowane" pokazuje też spam i odrzucone — domyślne
    zawężenie „Do obsługi" schodzi z drogi, jak przy jawnym statusie."""
    spam = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Spam",
        status=Zgloszenie_Publikacji.Statusy.SPAM,
    )
    spam.delete(reason="spam")
    zgloszenie.delete(reason="test")
    baker.make(Zgloszenie_Publikacji, status=Zgloszenie_Publikacji.Statusy.NOWY)

    resp = superuser_client.get(reverse(CHANGELIST), {"is_deleted": "true"})
    assert resp.status_code == 200
    pks = {o.pk for o in resp.context["cl"].result_list}
    assert pks == {spam.pk, zgloszenie.pk}
    assert "is_deleted" in StanObslugiFilter.POLA_WYLACZAJACE_ZAWEZENIE


@pytest.mark.django_db
def test_akcja_przywroc_przywraca_z_autorami(superuser, superuser_client, zgloszenie):
    zgloszenie.delete(reason="test")
    assert not Zgloszenie_Publikacji_Autor.objects.filter(rekord=zgloszenie).exists()

    url = reverse(CHANGELIST) + "?is_deleted=true"
    resp = superuser_client.post(
        url,
        {"action": "przywroc_zaznaczone", "_selected_action": [str(zgloszenie.pk)]},
    )
    assert resp.status_code in (200, 302)

    assert Zgloszenie_Publikacji.objects.filter(pk=zgloszenie.pk).exists()
    assert Zgloszenie_Publikacji_Autor.objects.filter(rekord=zgloszenie).count() == 1
    assert Zgloszenie_Publikacji_Zalacznik.objects.filter(
        zgloszenie=zgloszenie
    ).exists()
    assert _log(zgloszenie, SoftDeleteLog.Akcja.RESTORE).user_id == superuser.pk


@pytest.mark.django_db
def test_akcja_usun_do_kosza_z_powodem(superuser_client, zgloszenie):
    resp = superuser_client.post(
        reverse(CHANGELIST),
        {
            "action": "usun_do_kosza",
            "_selected_action": [str(zgloszenie.pk)],
            "powod_potwierdzony": "1",
            "powod": "duplikat",
        },
    )
    assert resp.status_code in (200, 302)
    assert Zgloszenie_Publikacji.deleted_objects.filter(pk=zgloszenie.pk).exists()
    assert _log(zgloszenie, SoftDeleteLog.Akcja.DELETE).powod == "duplikat"


@pytest.mark.django_db
def test_strona_zgloszenia_z_kosza_tylko_do_odczytu_z_przyciskiem_przywroc(
    superuser_client, zgloszenie
):
    zgloszenie.delete(reason="test")

    resp = superuser_client.get(_url("change", zgloszenie))
    assert resp.status_code == 200
    tresc = resp.content.decode()
    assert "♻️ Przywróć" in tresc
    assert _url("przywroc", zgloszenie) in tresc
    # Akcje obsługi zgłoszenia znikają, dopóki jest w koszu.
    assert "Zwróć do autora" not in tresc
    assert "numer_zgloszenia" not in tresc
    assert "Użyj importera" not in tresc

    resp = superuser_client.post(_url("przywroc", zgloszenie))
    assert resp.status_code == 302
    assert Zgloszenie_Publikacji.objects.filter(pk=zgloszenie.pk).exists()

    tresc = superuser_client.get(_url("change", zgloszenie)).content.decode()
    assert "♻️ Przywróć" not in tresc
    assert "Zwróć do autora" in tresc


@pytest.mark.django_db
def test_zwroc_zgloszenia_z_kosza_daje_404(superuser_client, zgloszenie):
    zgloszenie.delete(reason="test")
    resp = superuser_client.get(
        reverse(
            "admin:zglos_publikacje_zgloszenie_publikacji_zwroc",
            args=[zgloszenie.pk],
        )
    )
    assert resp.status_code == 404


def _staff_z_uprawnieniami(client, *kody):
    user = baker.make("bpp.BppUser", is_staff=True, username="operator")
    ct = ContentType.objects.get_for_model(Zgloszenie_Publikacji)
    user.user_permissions.add(
        *Permission.objects.filter(content_type=ct, codename__in=kody)
    )
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_operator_z_change_i_delete_moze_przywracac(client, zgloszenie):
    """Formularz zgłoszenia nie jest edytowalny (``has_change_permission``
    zawsze ``False``), ale przywracanie wymaga — jak wszędzie — uprawnień
    ``delete`` + ``change`` użytkownika."""
    client = _staff_z_uprawnieniami(
        client,
        "view_zgloszenie_publikacji",
        "change_zgloszenie_publikacji",
        "delete_zgloszenie_publikacji",
    )
    zgloszenie.delete(reason="test")

    resp = client.get(reverse(CHANGELIST), {"is_deleted": "true"})
    assert b"przywroc_zaznaczone" in resp.content
    assert "♻️ Przywróć" in client.get(_url("change", zgloszenie)).content.decode()

    assert client.post(_url("przywroc", zgloszenie)).status_code == 302
    assert Zgloszenie_Publikacji.objects.filter(pk=zgloszenie.pk).exists()


@pytest.mark.django_db
def test_operator_bez_change_nie_przywraca(client, zgloszenie):
    client = _staff_z_uprawnieniami(
        client, "view_zgloszenie_publikacji", "delete_zgloszenie_publikacji"
    )
    zgloszenie.delete(reason="test")

    resp = client.get(reverse(CHANGELIST), {"is_deleted": "true"})
    assert resp.status_code == 200
    assert b"przywroc_zaznaczone" not in resp.content
    assert b"usun_do_kosza" in resp.content
    assert client.post(_url("przywroc", zgloszenie)).status_code == 403
    assert Zgloszenie_Publikacji.deleted_objects.filter(pk=zgloszenie.pk).exists()


@pytest.mark.django_db
def test_trigger_zamraza_zgloszenie_w_koszu(zgloszenie):
    nieaktualna = Zgloszenie_Publikacji.objects.get(pk=zgloszenie.pk)
    zgloszenie.delete(reason="test")

    nieaktualna.tytul_oryginalny = "wskrzeszenie"
    with pytest.raises(DatabaseError) as exc, transaction.atomic():
        nieaktualna.save()
    assert jest_bledem_kosza(exc.value)

    tabela = Zgloszenie_Publikacji._meta.db_table
    for sql in (
        f"UPDATE {tabela} SET status = 5 WHERE id = %s",
        f"DELETE FROM {tabela} WHERE id = %s",
    ):
        with pytest.raises(DatabaseError) as exc, transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(sql, [zgloszenie.pk])
        assert jest_bledem_kosza(exc.value)

    assert Zgloszenie_Publikacji.deleted_objects.filter(pk=zgloszenie.pk).exists()


@pytest.mark.django_db
def test_trigger_odrzuca_zmiane_deleted_at_poza_operacja_kosza(zgloszenie):
    tabela = Zgloszenie_Publikacji._meta.db_table
    with pytest.raises(DatabaseError) as exc, transaction.atomic():
        with connection.cursor() as cur:
            cur.execute(
                f"UPDATE {tabela} SET deleted_at = now() WHERE id = %s",
                [zgloszenie.pk],
            )
    assert jest_bledem_kosza(exc.value)


@pytest.mark.django_db
def test_zgloszenie_skasowane_starym_mechanizmem_jest_w_koszu(superuser_client):
    """Stary soft-delete (pakiet) ustawiał te same kolumny — taki wiersz
    od razu jest w nowym koszu i da się go przywrócić."""
    stare = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Skasowane w 2025",
        status=Zgloszenie_Publikacji.Statusy.ODRZUCONO,
    )
    with operacja_kosza(), connection.cursor() as cur:
        cur.execute(
            f"UPDATE {Zgloszenie_Publikacji._meta.db_table} "
            "SET deleted_at = %s, transaction_id = %s WHERE id = %s",
            [timezone.now(), uuid.uuid4(), stare.pk],
        )

    assert not Zgloszenie_Publikacji.objects.filter(pk=stare.pk).exists()
    resp = superuser_client.get(reverse(CHANGELIST), {"is_deleted": "true"})
    assert stare.pk in {o.pk for o in resp.context["cl"].result_list}

    superuser_client.post(_url("przywroc", stare))
    assert Zgloszenie_Publikacji.objects.filter(pk=stare.pk).exists()


@pytest.mark.django_db
def test_autorzy_i_zalaczniki_znikaja_i_wracaja_z_rodzicem(zgloszenie):
    zgloszenie.delete(reason="test")
    assert not Zgloszenie_Publikacji_Autor.objects.filter(rekord=zgloszenie).exists()
    assert Zgloszenie_Publikacji_Autor.all_objects.filter(rekord=zgloszenie).exists()
    assert not Zgloszenie_Publikacji_Zalacznik.objects.filter(
        zgloszenie=zgloszenie
    ).exists()
    assert Zgloszenie_Publikacji_Zalacznik.all_objects.filter(
        zgloszenie=zgloszenie
    ).exists()
    assert not hasattr(Zgloszenie_Publikacji_Autor, "deleted_objects")

    Zgloszenie_Publikacji.deleted_objects.get(pk=zgloszenie.pk).restore()
    assert Zgloszenie_Publikacji_Autor.objects.filter(rekord=zgloszenie).exists()
    assert Zgloszenie_Publikacji_Zalacznik.objects.filter(
        zgloszenie=zgloszenie
    ).exists()


@pytest.mark.django_db
def test_hard_delete_kaskaduje_dzieci(zgloszenie):
    pk = zgloszenie.pk
    zgloszenie.delete(reason="test")
    Zgloszenie_Publikacji.deleted_objects.get(pk=pk).hard_delete()
    assert not Zgloszenie_Publikacji.global_objects.filter(pk=pk).exists()
    assert not Zgloszenie_Publikacji_Autor.all_objects.filter(rekord_id=pk).exists()


@pytest.mark.django_db
def test_edycja_przez_kod_zgloszenia_z_kosza_daje_404(client, uczelnia, zgloszenie):
    url = reverse("zglos_publikacje:edycja_zgloszenia", args=[zgloszenie.kod_do_edycji])
    assert client.get(url).status_code == 200

    zgloszenie.delete(reason="test")
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_dodaj_publikacje_ze_zgloszenia_z_kosza_nie_wypelnia_danych(
    superuser_client, zgloszenie
):
    zgloszenie.delete(reason="test")
    resp = superuser_client.get(
        reverse("admin:bpp_wydawnictwo_ciagle_add"),
        {"numer_zgloszenia": zgloszenie.pk},
    )
    assert resp.status_code == 200
    assert "Zgłoszenie do kosza" not in resp.content.decode()


@pytest.mark.django_db
def test_importer_nie_bierze_dyscyplin_ze_zgloszenia_z_kosza(zgloszenie):
    from importer_publikacji.models import ImportSession
    from importer_publikacji.views.authors import _zgloszenie_dla_prefilla

    sesja = baker.make(ImportSession, zgloszenie=zgloszenie)
    assert _zgloszenie_dla_prefilla(sesja) == zgloszenie

    zgloszenie.delete(reason="test")
    sesja = ImportSession.objects.get(pk=sesja.pk)
    assert _zgloszenie_dla_prefilla(sesja) is None
