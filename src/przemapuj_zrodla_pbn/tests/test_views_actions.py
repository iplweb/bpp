"""
Testy widoków akcji (usuwanie, przemapowanie) w aplikacji przemapuj_zrodla_pbn.

Ten moduł zawiera testy dla:
- UsunZrodloView - widok usuwania źródła ze statusem DELETED w PBN
"""

import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
def test_usun_zrodlo_view_requires_login(client):
    """Test czy widok usuwania wymaga zalogowania"""
    journal = baker.make(
        "pbn_api.Journal", status="DELETED", title="", issn="", eissn="", websiteLink=""
    )
    zrodlo = baker.make("bpp.Zrodlo", pbn_uid=journal)

    url = reverse("przemapuj_zrodla_pbn:usun_zrodlo", kwargs={"zrodlo_id": zrodlo.pk})
    response = client.get(url)

    # Powinno przekierować na login
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_usun_zrodlo_view_get_shows_confirmation_page(client, django_user_model):
    """Test czy widok GET usuwania pokazuje stronę potwierdzenia"""
    user = baker.make(django_user_model)
    client.force_login(user)

    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Gazeta do Usunięcia",
        issn="",
        eissn="",
        websiteLink="",
    )
    zrodlo = baker.make(
        "bpp.Zrodlo", nazwa="Gazeta do Usunięcia", pbn_uid=journal_deleted
    )

    url = reverse("przemapuj_zrodla_pbn:usun_zrodlo", kwargs={"zrodlo_id": zrodlo.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert "Usuń źródło" in response.content.decode()
    assert "Gazeta do Usunięcia" in response.content.decode()
    assert "NIEODWRACALNA" in response.content.decode()


@pytest.mark.django_db
def test_usun_zrodlo_view_rejects_non_deleted_source(client, django_user_model):
    """Test czy widok odrzuca próbę usunięcia źródła które nie jest DELETED w PBN"""
    from bpp.models import Zrodlo

    user = baker.make(django_user_model)
    client.force_login(user)

    journal_active = baker.make(
        "pbn_api.Journal",
        status="ACTIVE",
        title="Aktywna Gazeta",
        issn="",
        eissn="",
        websiteLink="",
    )
    zrodlo = baker.make("bpp.Zrodlo", nazwa="Aktywna Gazeta", pbn_uid=journal_active)

    url = reverse("przemapuj_zrodla_pbn:usun_zrodlo", kwargs={"zrodlo_id": zrodlo.pk})
    response = client.post(url)

    # Powinno przekierować z błędem
    assert response.status_code == 302
    # Źródło NIE powinno być usunięte
    assert Zrodlo.objects.filter(pk=zrodlo.pk).exists()


@pytest.mark.django_db
def test_usun_zrodlo_view_rejects_source_with_records(client, django_user_model):
    """Test czy widok odrzuca próbę usunięcia źródła które ma rekordy"""
    from bpp.models import Zrodlo

    user = baker.make(django_user_model)
    client.force_login(user)

    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Gazeta z Rekordami",
        issn="",
        eissn="",
        websiteLink="",
    )
    zrodlo = baker.make(
        "bpp.Zrodlo", nazwa="Gazeta z Rekordami", pbn_uid=journal_deleted
    )

    # Utwórz rekord powiązany ze źródłem
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodla_pbn:usun_zrodlo", kwargs={"zrodlo_id": zrodlo.pk})
    response = client.post(url)

    # Powinno przekierować z błędem
    assert response.status_code == 302
    # Źródło NIE powinno być usunięte
    assert Zrodlo.objects.filter(pk=zrodlo.pk).exists()


@pytest.mark.django_db
def test_usun_zrodlo_view_post_deletes_source_successfully(client, django_user_model):
    """Test czy widok POST usuwa źródło bez rekordów i zapisuje log"""
    from przemapuj_zrodla_pbn.models import PrzeMapowanieZrodla

    user = baker.make(django_user_model)
    client.force_login(user)

    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Gazeta do Usunięcia",
        issn="",
        eissn="",
        websiteLink="",
    )
    zrodlo = baker.make(
        "bpp.Zrodlo", nazwa="Gazeta do Usunięcia", pbn_uid=journal_deleted
    )
    zrodlo_id = zrodlo.pk

    url = reverse("przemapuj_zrodla_pbn:usun_zrodlo", kwargs={"zrodlo_id": zrodlo_id})
    response = client.post(url)

    # Powinno przekierować na listę
    assert response.status_code == 302
    assert response.url == reverse("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")

    # Źródło powinno być usunięte z bazy
    from bpp.models import Zrodlo

    assert not Zrodlo.objects.filter(pk=zrodlo_id).exists()

    # Powinien być utworzony wpis w historii
    log = PrzeMapowanieZrodla.objects.filter(
        typ_operacji=PrzeMapowanieZrodla.TYP_USUNIECIE
    ).first()

    assert log is not None
    assert log.zrodlo_skasowane_pbn_uid == journal_deleted
    assert log.zrodlo_nowe is None
    assert log.liczba_rekordow == 0
    assert log.utworzono_przez == user
