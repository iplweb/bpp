import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from ewaluacja_optymalizacja.views import _get_discipline_pin_stats
from snapshot_odpiec.models import SnapshotOdpiec


@pytest.mark.django_db
def test_get_discipline_pin_stats_no_authors():
    """Test gdy nie ma autorów z Autor_Dyscyplina dla danej dyscypliny."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")

    stats = _get_discipline_pin_stats(dyscyplina)

    assert stats["pinned"] == 0
    assert stats["unpinned"] == 0
    assert stats["total"] == 0
    assert stats["pinned_pct"] == 0.0
    assert stats["unpinned_pct"] == 0.0


@pytest.mark.django_db
def test_get_discipline_pin_stats_with_pinned_and_unpinned():
    """Test obliczania statystyk z przypiętymi i odpiętymi rekordami."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    autor = baker.make("bpp.Autor")

    # Utwórz Autor_Dyscyplina w latach 2022-2025
    for rok in range(2022, 2026):
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina,
            subdyscyplina_naukowa=None,
        )

    # Utwórz publikacje
    for rok in range(2022, 2025):
        # Przypięte
        pub_pinned = baker.make(Wydawnictwo_Ciagle, rok=rok)
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=pub_pinned,
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            przypieta=True,
        )

        # Odpięte
        pub_unpinned = baker.make(Wydawnictwo_Ciagle, rok=rok)
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=pub_unpinned,
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            przypieta=False,
        )

    stats = _get_discipline_pin_stats(dyscyplina)

    assert stats["pinned"] == 3
    assert stats["unpinned"] == 3
    assert stats["total"] == 6
    assert stats["pinned_pct"] == 50.0
    assert stats["unpinned_pct"] == 50.0


@pytest.mark.django_db
def test_get_discipline_pin_stats_filters_by_year():
    """Test że funkcja filtruje tylko lata 2022-2025."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    autor = baker.make("bpp.Autor")

    # Utwórz Autor_Dyscyplina dla WSZYSTKICH lat (2021-2026)
    for rok in range(2021, 2027):
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina,
            subdyscyplina_naukowa=None,
        )

    # Utwórz publikacje poza zakresem (2021, 2026)
    for rok in [2021, 2026]:
        pub = baker.make(Wydawnictwo_Ciagle, rok=rok)
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=pub,
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            przypieta=False,
        )

    # Utwórz publikacje w zakresie (2022-2025)
    for rok in range(2022, 2026):
        pub = baker.make(Wydawnictwo_Ciagle, rok=rok)
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=pub,
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            przypieta=True,
        )

    stats = _get_discipline_pin_stats(dyscyplina)

    # Powinny być tylko publikacje z lat 2022-2025
    assert stats["total"] == 4
    assert stats["pinned"] == 4
    assert stats["unpinned"] == 0


@pytest.mark.django_db
def test_get_discipline_pin_stats_filters_by_autor_dyscyplina():
    """Test że funkcja uwzględnia tylko autorów z Autor_Dyscyplina."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    autor_with_ad = baker.make("bpp.Autor")
    autor_without_ad = baker.make("bpp.Autor")

    # Tylko autor_with_ad ma Autor_Dyscyplina dla lat 2022-2025
    for rok in range(2022, 2026):
        baker.make(
            Autor_Dyscyplina,
            autor=autor_with_ad,
            rok=rok,
            dyscyplina_naukowa=dyscyplina,
            subdyscyplina_naukowa=None,
        )

    # autor_without_ad ma Autor_Dyscyplina ale dla innego roku (2020)
    baker.make(
        Autor_Dyscyplina,
        autor=autor_without_ad,
        rok=2020,
        dyscyplina_naukowa=dyscyplina,
        subdyscyplina_naukowa=None,
    )

    # Obu autorzy mają publikacje w 2023
    # (ale autor_without_ad nie ma Autor_Dyscyplina dla 2023)
    pub1 = baker.make(Wydawnictwo_Ciagle, rok=2023)
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub1,
        autor=autor_with_ad,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
    )

    # Ta publikacja nie może być utworzona z dyscypliną dla autor_without_ad
    # bo nie ma Autor_Dyscyplina dla 2023 - więc utworzę bez dyscypliny
    pub2 = baker.make(Wydawnictwo_Ciagle, rok=2023)
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub2,
        autor=autor_without_ad,
        dyscyplina_naukowa=None,  # Bez dyscypliny
        przypieta=True,
    )

    stats = _get_discipline_pin_stats(dyscyplina)

    # Tylko publikacja autora_with_ad powinna być liczona
    assert stats["total"] == 1
    assert stats["pinned"] == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_reset_discipline_pins_creates_snapshot_and_resets(client, admin_user):
    """Test że reset tworzy snapshot i resetuje przypięcia."""
    from unittest.mock import patch

    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    autor = baker.make("bpp.Autor")

    # Utwórz Autor_Dyscyplina
    for rok in range(2022, 2026):
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina,
            subdyscyplina_naukowa=None,
        )

    # Utwórz odpięte publikacje
    odpięte_rekordy = []
    for rok in range(2022, 2025):
        pub = baker.make(Wydawnictwo_Ciagle, rok=rok)
        rekord = baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=pub,
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            przypieta=False,
        )
        odpięte_rekordy.append(rekord)

    # Sprawdź stan przed resetem
    assert all(not r.przypieta for r in odpięte_rekordy)
    snapshot_count_before = SnapshotOdpiec.objects.count()

    # Mock DirtyInstance.objects.count to return 30 first (dirty), then 0 (clean)
    # Mock sleep to avoid actual waiting
    with patch("denorm.models.DirtyInstance.objects.count") as mock_count:
        mock_count.side_effect = [30, 0]

        with patch("ewaluacja_optymalizacja.views.pins.sleep"):
            # Wykonaj reset
            client.force_login(admin_user)
            url = reverse(
                "ewaluacja_optymalizacja:reset-discipline-pins",
                kwargs={"pk": dyscyplina.pk},
            )
            response = client.get(url)

    # Sprawdź czy utworzono snapshot
    assert SnapshotOdpiec.objects.count() == snapshot_count_before + 1
    snapshot = SnapshotOdpiec.objects.latest("created_on")
    assert f"przed resetem przypięć - {dyscyplina.nazwa}" in snapshot.comment

    # Sprawdź czy rekordy zostały zresetowane
    for rekord in odpięte_rekordy:
        rekord.refresh_from_db()
        assert rekord.przypieta is True

    # Sprawdź redirect
    assert response.status_code == 302
    assert response.url == reverse("ewaluacja_optymalizacja:index")


@pytest.mark.django_db(transaction=True)
@pytest.mark.override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_reset_discipline_pins_no_unpinned_shows_warning(client, admin_user):
    """Test że reset bez odpiętych rekordów pokazuje warning."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    autor = baker.make("bpp.Autor")

    # Utwórz Autor_Dyscyplina
    for rok in range(2022, 2026):
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=dyscyplina,
            subdyscyplina_naukowa=None,
        )

    # Utwórz tylko przypięte publikacje
    pub = baker.make(Wydawnictwo_Ciagle, rok=2023)
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=pub,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
    )

    snapshot_count_before = SnapshotOdpiec.objects.count()

    from unittest.mock import patch

    with patch("denorm.models.DirtyInstance.objects.count") as mock_count:
        mock_count.side_effect = [30, 0]

        with patch("ewaluacja_optymalizacja.views.pins.sleep"):
            # Wykonaj reset
            client.force_login(admin_user)
            url = reverse(
                "ewaluacja_optymalizacja:reset-discipline-pins",
                kwargs={"pk": dyscyplina.pk},
            )
            response = client.get(url, follow=True)

    # Sprawdź czy NIE utworzono snapshotu
    assert SnapshotOdpiec.objects.count() == snapshot_count_before

    # Sprawdź komunikat
    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "nie ma odpiętych rekordów" in str(messages[0])
