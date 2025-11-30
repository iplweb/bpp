"""Testy dla widoków author_works i author_works_exports."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Dyscyplina_Naukowa
from ewaluacja_metryki.models import MetrykaAutora
from ewaluacja_optymalizacja.models import OptimizationRun


@pytest.mark.django_db
def test_author_works_detail_accessible(client, admin_user):
    """View returns 200 for valid data."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    autor = baker.make("bpp.Autor")
    run = baker.make(
        OptimizationRun,
        dyscyplina_naukowa=dyscyplina,
        status="completed",
    )
    baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        prace_nazbierane=[],
        prace_wszystkie=[],
    )

    client.force_login(admin_user)
    url = reverse(
        "ewaluacja_optymalizacja:author-works-detail",
        kwargs={"run_pk": run.pk, "autor_pk": autor.pk},
    )
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_author_works_detail_404_no_run(client, admin_user):
    """Returns 404 for non-existent run."""
    autor = baker.make("bpp.Autor")

    client.force_login(admin_user)
    url = reverse(
        "ewaluacja_optymalizacja:author-works-detail",
        kwargs={"run_pk": 99999, "autor_pk": autor.pk},
    )
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_author_works_detail_404_no_autor(client, admin_user):
    """Returns 404 for non-existent autor."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    run = baker.make(
        OptimizationRun,
        dyscyplina_naukowa=dyscyplina,
        status="completed",
    )

    client.force_login(admin_user)
    url = reverse(
        "ewaluacja_optymalizacja:author-works-detail",
        kwargs={"run_pk": run.pk, "autor_pk": 99999},
    )
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_author_works_detail_404_no_metryka(client, admin_user):
    """Returns 404 when metryka doesn't exist."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    autor = baker.make("bpp.Autor")
    run = baker.make(
        OptimizationRun,
        dyscyplina_naukowa=dyscyplina,
        status="completed",
    )
    # No MetrykaAutora created

    client.force_login(admin_user)
    url = reverse(
        "ewaluacja_optymalizacja:author-works-detail",
        kwargs={"run_pk": run.pk, "autor_pk": autor.pk},
    )
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_export_nazbierane_xlsx_content_type(client, admin_user):
    """Export returns correct XLSX content type."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    autor = baker.make("bpp.Autor")
    run = baker.make(
        OptimizationRun,
        dyscyplina_naukowa=dyscyplina,
        status="completed",
    )
    baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        prace_nazbierane=[],
        prace_wszystkie=[],
    )

    client.force_login(admin_user)
    url = reverse(
        "ewaluacja_optymalizacja:export-prace-nazbierane-xlsx",
        kwargs={"run_pk": run.pk, "autor_pk": autor.pk},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert (
        response["Content-Type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@pytest.mark.django_db
def test_export_all_works_xlsx_content_type(client, admin_user):
    """Combined export returns XLSX."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    autor = baker.make("bpp.Autor")
    run = baker.make(
        OptimizationRun,
        dyscyplina_naukowa=dyscyplina,
        status="completed",
    )
    baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        prace_nazbierane=[],
        prace_wszystkie=[],
        slot_maksymalny=4,
        slot_nazbierany=2,
        punkty_nazbierane=100,
        slot_wszystkie=3,
        punkty_wszystkie=150,
    )

    client.force_login(admin_user)
    url = reverse(
        "ewaluacja_optymalizacja:export-all-works-xlsx",
        kwargs={"run_pk": run.pk, "autor_pk": autor.pk},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert (
        response["Content-Type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@pytest.mark.django_db
def test_author_works_requires_login(client):
    """Unauthenticated request redirects to login."""
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Testowa", kod="1.1")
    autor = baker.make("bpp.Autor")
    run = baker.make(
        OptimizationRun,
        dyscyplina_naukowa=dyscyplina,
        status="completed",
    )

    url = reverse(
        "ewaluacja_optymalizacja:author-works-detail",
        kwargs={"run_pk": run.pk, "autor_pk": autor.pk},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url
