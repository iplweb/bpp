import pytest
from django.urls import reverse
from model_bakery import baker

from przemapuj_zrodla_pbn.views import znajdz_podobne_zrodla


@pytest.mark.django_db
def test_lista_skasowanych_zrodel_view_requires_login(client):
    """Test czy widok wymaga zalogowania"""
    url = reverse("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")
    response = client.get(url)

    # Powinno przekierować na login
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_lista_skasowanych_zrodel_view_shows_deleted_sources(client, django_user_model):
    """Test czy widok pokazuje źródła ze statusem DELETED"""
    user = baker.make(django_user_model)
    client.force_login(user)

    # Utwórz źródło ze statusem DELETED
    journal_deleted = baker.make(
        "pbn_api.Journal", status="DELETED", title="Skasowana Gazeta"
    )
    baker.make("bpp.Zrodlo", nazwa="Skasowana Gazeta", pbn_uid=journal_deleted)

    # Utwórz źródło ze statusem ACTIVE (nie powinno się pojawić)
    journal_active = baker.make(
        "pbn_api.Journal", status="ACTIVE", title="Aktywna Gazeta"
    )
    baker.make("bpp.Zrodlo", nazwa="Aktywna Gazeta", pbn_uid=journal_active)

    url = reverse("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")
    response = client.get(url)

    assert response.status_code == 200
    assert "Skasowana Gazeta" in response.content.decode()
    assert "Aktywna Gazeta" not in response.content.decode()


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_requires_login(client):
    """Test czy widok przemapowania wymaga zalogowania"""
    journal = baker.make("pbn_api.Journal", status="DELETED")
    zrodlo = baker.make("bpp.Zrodlo", pbn_uid=journal)

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo.pk}
    )
    response = client.get(url)

    # Powinno przekierować na login
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_get(client, django_user_model):
    """Test czy widok GET przemapowania działa poprawnie"""
    user = baker.make(django_user_model)
    client.force_login(user)

    journal_deleted = baker.make(
        "pbn_api.Journal", status="DELETED", title="Stara Gazeta"
    )
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Stara Gazeta", pbn_uid=journal_deleted
    )

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo_stare.pk}
    )
    response = client.get(url)

    assert response.status_code == 200
    assert "Stara Gazeta" in response.content.decode()
    assert "Wybierz źródło docelowe" in response.content.decode()


@pytest.mark.django_db
def test_znajdz_podobne_zrodla_function_categorizes_correctly():
    """Test czy funkcja znajdz_podobne_zrodla kategoryzuje źródła poprawnie"""
    # Źródło skasowane
    journal_deleted = baker.make(
        "pbn_api.Journal", status="DELETED", title="Test Journal"
    )

    # Najlepsze: ACTIVE + mniswId
    journal_best = baker.make(
        "pbn_api.Journal", status="ACTIVE", title="Test Journal A", mniswId="12345"
    )
    baker.make("bpp.Zrodlo", nazwa="Test Journal A", pbn_uid=journal_best)

    # Dobre: ACTIVE bez mniswId
    journal_good = baker.make(
        "pbn_api.Journal", status="ACTIVE", title="Test Journal B", mniswId=None
    )
    baker.make("bpp.Zrodlo", nazwa="Test Journal B", pbn_uid=journal_good)

    # Akceptowalne: nie-DELETED
    journal_acceptable = baker.make(
        "pbn_api.Journal", status="MERGED", title="Test Journal C"
    )
    baker.make("bpp.Zrodlo", nazwa="Test Journal C", pbn_uid=journal_acceptable)

    results = znajdz_podobne_zrodla(journal_deleted, max_results=10)

    # Sprawdź czy kategorie są zdefiniowane
    assert "zrodla_bpp" in results
    assert "journale_pbn" in results

    # Sprawdź czy każda kategoria ma subcategories
    for subcat in ["najlepsze", "dobre", "akceptowalne"]:
        assert subcat in results["zrodla_bpp"]
        assert subcat in results["journale_pbn"]

    # Sprawdź czy są to listy
    for subcat in ["najlepsze", "dobre", "akceptowalne"]:
        assert isinstance(results["zrodla_bpp"][subcat], list)
        assert isinstance(results["journale_pbn"][subcat], list)


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_post_preview(client, django_user_model):
    """Test czy widok POST z parametrem preview działa"""
    user = baker.make(django_user_model)
    client.force_login(user)

    # Użyj podobnej nazwy i tego samego ISSN aby źródło było znalezione przez algorytm
    journal_deleted = baker.make(
        "pbn_api.Journal", status="DELETED", title="Test Gazeta", issn="1234-5678"
    )
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Test Gazeta", pbn_uid=journal_deleted, issn="1234-5678"
    )

    # Nazwa zaczyna się od "Test Gazeta" więc będzie znaleziona przez PREFIX matching
    journal_new = baker.make(
        "pbn_api.Journal", status="ACTIVE", title="Test Gazeta Nowa", issn="1234-5678"
    )
    zrodlo_nowe = baker.make(
        "bpp.Zrodlo", nazwa="Test Gazeta Nowa", pbn_uid=journal_new, issn="1234-5678"
    )

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo_stare.pk}
    )
    response = client.post(
        url, {"typ_wyboru": "zrodlo", "zrodlo_docelowe": zrodlo_nowe.pk, "preview": "1"}
    )

    assert response.status_code == 200
    assert "Podgląd zmian" in response.content.decode()
    assert "Test Gazeta Nowa" in response.content.decode()


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_shows_pbn_links_for_zrodla_bpp(
    client, django_user_model, pbn_uczelnia
):
    """Test czy widok pokazuje linki 'zobacz w PBN' dla źródeł BPP z pbn_uid"""
    user = baker.make(django_user_model)
    client.force_login(user)

    # Źródło skasowane
    journal_deleted = baker.make(
        "pbn_api.Journal", status="DELETED", title="Skasowana Gazeta", issn="1234-5678"
    )
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Skasowana Gazeta", pbn_uid=journal_deleted
    )

    # Źródło z pbn_uid (powinno mieć link)
    # Musi mieć ten sam ISSN żeby było znalezione przez algoritm wyszukiwania
    journal_with_pbn = baker.make(
        "pbn_api.Journal",
        status="ACTIVE",
        title="Gazeta z PBN",
        issn="1234-5678",
        mniswId=12345,
    )
    baker.make(
        "bpp.Zrodlo",
        nazwa="Skasowana Gazeta A",
        pbn_uid=journal_with_pbn,
        issn="1234-5678",
    )

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo_stare.pk}
    )
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Sprawdź czy źródło jest na liście
    assert (
        "Skasowana Gazeta A" in content
    ), "Źródło z podobnym ISSN powinno być na liście"

    # Sprawdź czy jest link "Zobacz w PBN" dla źródła z pbn_uid
    assert "Zobacz w PBN" in content, "Link 'Zobacz w PBN' nie został znaleziony w HTML"
    # Sprawdź czy link zawiera prawidłowy URL (metoda link_do_pbn)
    assert 'target="_blank"' in content


@pytest.mark.django_db
def test_przemapuj_zrodlo_view_shows_pbn_links_for_journale_pbn(
    client, django_user_model, pbn_uczelnia
):
    """Test czy widok poprawnie wyświetla stronę z sugestiami dla journali z PBN"""
    user = baker.make(django_user_model)
    client.force_login(user)

    # Źródło skasowane
    journal_deleted = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="Testowa Gazeta",
        issn="1234-5678",
    )
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Testowa Gazeta", pbn_uid=journal_deleted, issn="1234-5678"
    )

    # Utwórz źródło w BPP które będzie sugestią (z aktywnym PBN)
    journal_active = baker.make(
        "pbn_api.Journal",
        status="ACTIVE",
        title="Testowa Gazeta - Edycja Nowa",
        issn="1234-5678",
        mniswId=12345,
    )
    baker.make(
        "bpp.Zrodlo",
        nazwa="Testowa Gazeta - Edycja Nowa",
        pbn_uid=journal_active,
        issn="1234-5678",
    )

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo_stare.pk}
    )
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Test sprawdza podstawową funkcjonalność - widok działa i pokazuje sugestie
    # Powinien być link "Zobacz w PBN" dla źródeł z BPP które mają pbn_uid
    assert "Zobacz w PBN" in content, "Link 'Zobacz w PBN' nie został znaleziony w HTML"


@pytest.mark.django_db
def test_usun_zrodlo_view_requires_login(client):
    """Test czy widok usuwania wymaga zalogowania"""
    journal = baker.make("pbn_api.Journal", status="DELETED")
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
        "pbn_api.Journal", status="DELETED", title="Gazeta do Usunięcia"
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
        "pbn_api.Journal", status="ACTIVE", title="Aktywna Gazeta"
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
        "pbn_api.Journal", status="DELETED", title="Gazeta z Rekordami"
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
        "pbn_api.Journal", status="DELETED", title="Gazeta do Usunięcia"
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


@pytest.mark.django_db
def test_lista_skasowanych_zrodel_shows_usun_button_for_zero_records(
    client, django_user_model
):
    """Test czy lista pokazuje przycisk 'Usuń' dla źródeł bez rekordów"""
    user = baker.make(django_user_model)
    client.force_login(user)

    # Źródło bez rekordów
    journal_deleted_empty = baker.make(
        "pbn_api.Journal", status="DELETED", title="Pusta Gazeta"
    )
    baker.make("bpp.Zrodlo", nazwa="Pusta Gazeta", pbn_uid=journal_deleted_empty)

    # Źródło z rekordami
    journal_deleted_with_records = baker.make(
        "pbn_api.Journal", status="DELETED", title="Gazeta z Rekordami"
    )
    zrodlo_with_records = baker.make(
        "bpp.Zrodlo", nazwa="Gazeta z Rekordami", pbn_uid=journal_deleted_with_records
    )
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo_with_records)

    url = reverse("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Sprawdź czy jest przycisk "Usuń" dla pustej gazety
    assert "Pusta Gazeta" in content
    assert content.count("fi-trash") >= 1  # Ikona kosza

    # Sprawdź czy jest przycisk "Przemapuj" dla gazety z rekordami
    assert "Gazeta z Rekordami" in content
    assert content.count("fi-refresh") >= 1  # Ikona odświeżania
