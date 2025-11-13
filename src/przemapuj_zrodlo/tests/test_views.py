import pytest
from django.urls import reverse
from model_bakery import baker

from przemapuj_zrodlo.models import PrzemapowaZrodla


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_access_denied_anonymous(client):
    """Test dostępu - użytkownik anonimowy."""
    zrodlo = baker.make("bpp.Zrodlo")
    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    response = client.get(url)

    # Powinien przekierować do strony logowania lub pokazać błąd
    assert response.status_code in [302, 403]


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_access_denied_non_admin(client, normal_django_user):
    """Test dostępu - użytkownik bez grupy wprowadzanie danych."""
    from django.contrib.auth.models import Group

    from bpp.const import GR_WPROWADZANIE_DANYCH

    # Upewnij się że użytkownik NIE ma grupy wprowadzanie danych i nie jest superuserem
    wprowadzanie_group = Group.objects.filter(name=GR_WPROWADZANIE_DANYCH).first()
    if wprowadzanie_group:
        normal_django_user.groups.remove(wprowadzanie_group)
    normal_django_user.is_superuser = False
    normal_django_user.save()

    client.force_login(normal_django_user)

    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    response = client.get(url)

    # Powinien przekierować z komunikatem o braku uprawnień
    assert response.status_code == 302


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_access_granted_superuser(superuser_client):
    """Test dostępu - superuser bez grupy wprowadzanie danych."""
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    response = superuser_client.get(url)

    # Superuser powinien mieć dostęp
    assert response.status_code == 200
    assert "form" in response.context


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_empty_source(client_with_group):
    """Test widoku dla źródła bez publikacji - przekierowanie."""
    zrodlo = baker.make("bpp.Zrodlo")
    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    response = client_with_group.get(url)

    # Powinien przekierować z komunikatem
    assert response.status_code == 302


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_get(client_with_group):
    """Test wyświetlenia formularza przemapowania."""
    zrodlo = baker.make("bpp.Zrodlo")
    # Dodaj publikację do źródła
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    response = client_with_group.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert "zrodlo_zrodlowe" in response.context
    assert "liczba_publikacji" in response.context


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_post_success(client_with_group, user_with_group):
    """Test wykonania przemapowania."""
    zrodlo = baker.make("bpp.Zrodlo", nazwa="Źródło A")
    zrodlo_docelowe = baker.make("bpp.Zrodlo", nazwa="Źródło B")

    # Dodaj publikacje do źródła źródłowego
    pub1 = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, tytul_oryginalny="Test 1", rok=2020
    )
    pub2 = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, tytul_oryginalny="Test 2", rok=2021
    )

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    response = client_with_group.post(
        url,
        {
            "zrodlo_docelowe": zrodlo_docelowe.pk,
            "potwierdzenie": True,
        },
    )

    # Sprawdź przekierowanie
    assert response.status_code == 302

    # Sprawdź czy publikacje zostały przemapowane
    pub1.refresh_from_db()
    pub2.refresh_from_db()
    assert pub1.zrodlo == zrodlo_docelowe
    assert pub2.zrodlo == zrodlo_docelowe

    # Sprawdź czy utworzono rekord przemapowania
    przemapowanie = PrzemapowaZrodla.objects.get()
    assert przemapowanie.zrodlo_z == zrodlo
    assert przemapowanie.zrodlo_do == zrodlo_docelowe
    assert przemapowanie.liczba_publikacji == 2
    assert przemapowanie.utworzono_przez == user_with_group


@pytest.mark.django_db
def test_cofnij_przemapowanie_view(client_with_group, user_with_group):
    """Test cofnięcia przemapowania."""
    zrodlo = baker.make("bpp.Zrodlo", nazwa="Źródło A")
    zrodlo_docelowe = baker.make("bpp.Zrodlo", nazwa="Źródło B")

    # Utwórz publikacje w źródle docelowym (jakby już były przemapowane)
    pub1 = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=zrodlo_docelowe,
        tytul_oryginalny="Test 1",
        rok=2020,
    )
    pub2 = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        zrodlo=zrodlo_docelowe,
        tytul_oryginalny="Test 2",
        rok=2021,
    )

    # Utwórz przemapowanie
    przemapowanie = PrzemapowaZrodla.objects.create(
        zrodlo_z=zrodlo,
        zrodlo_do=zrodlo_docelowe,
        liczba_publikacji=2,
        publikacje_historia=[
            {"id": pub1.pk, "tytul": "Test 1", "rok": 2020},
            {"id": pub2.pk, "tytul": "Test 2", "rok": 2021},
        ],
        utworzono_przez=user_with_group,
    )

    # Cofnij przemapowanie
    url = reverse("przemapuj_zrodlo:cofnij", args=[przemapowanie.pk])
    response = client_with_group.post(url)

    # Sprawdź przekierowanie
    assert response.status_code == 302

    # Sprawdź czy publikacje zostały cofnięte
    pub1.refresh_from_db()
    pub2.refresh_from_db()
    assert pub1.zrodlo == zrodlo
    assert pub2.zrodlo == zrodlo

    # Sprawdź czy przemapowanie zostało oznaczone jako cofnięte
    przemapowanie.refresh_from_db()
    assert przemapowanie.jest_cofniete
    assert przemapowanie.cofnieto_przez == user_with_group


@pytest.mark.django_db
def test_cofnij_przemapowanie_already_reverted(client_with_group, user_with_group):
    """Test cofnięcia przemapowania które już zostało cofnięte."""
    from django.utils import timezone

    zrodlo = baker.make("bpp.Zrodlo")
    zrodlo_docelowe = baker.make("bpp.Zrodlo")

    # Utwórz przemapowanie już cofnięte
    przemapowanie = PrzemapowaZrodla.objects.create(
        zrodlo_z=zrodlo,
        zrodlo_do=zrodlo_docelowe,
        liczba_publikacji=2,
        publikacje_historia=[],
        utworzono_przez=user_with_group,
        cofnieto=timezone.now(),
        cofnieto_przez=user_with_group,
    )

    url = reverse("przemapuj_zrodlo:cofnij", args=[przemapowanie.pk])
    response = client_with_group.post(url)

    # Powinien przekierować z komunikatem że już cofnięte
    assert response.status_code == 302


@pytest.mark.django_db
def test_przemapuj_zrodlo_blocked_for_mnisw_source(client_with_group):
    """Test blokady przemapowania dla źródła z MNISW ID (na liście ministerstwa)."""
    from pbn_api.models import Journal

    # Utwórz źródło z Journal który ma MNISW ID i status != DELETED
    journal = Journal.objects.create(
        mongoId="test_journal_12345",
        status="CURRENT",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Test Journal with MNISW",
                    "mniswId": 12345,
                },
            }
        ],
        mniswId=12345,
        title="Test Journal with MNISW",
    )
    zrodlo = baker.make("bpp.Zrodlo", pbn_uid=journal)
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    response = client_with_group.get(url)

    # Powinien przekierować z komunikatem o blokadzie
    assert response.status_code == 302
    assert response.url == reverse("bpp:browse_zrodlo", args=[zrodlo.slug])


@pytest.mark.django_db
def test_przemapuj_zrodlo_allowed_for_deleted_mnisw_source(client_with_group):
    """Test że usunięte źródło z MNISW ID można przemapować."""
    from pbn_api.models import Journal

    # Utwórz źródło z Journal który ma MNISW ID ale status == DELETED
    journal = baker.make(
        Journal,
        mniswId=12345,
        status="DELETED",
        title="Test Journal Deleted",
    )
    zrodlo = baker.make("bpp.Zrodlo", pbn_uid=journal)
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo)

    url = reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo.slug])
    response = client_with_group.get(url)

    # Powinien wyświetlić formularz (200 OK)
    assert response.status_code == 200
    assert "form" in response.context
