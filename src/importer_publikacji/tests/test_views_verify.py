"""Testy etapu Verify w wizardzie importera (`importer_publikacji:verify`).

Pokrywają: aktualizację statusu sesji po POST, zachowanie języka przy GET
(scenariusz „Kontynuuj"), oraz sugestię „Pobierz z CrossRef" gdy provider
inny niż CrossRef ma DOI.
"""

import pytest
from django.urls import reverse

from importer_publikacji.models import ImportSession


@pytest.mark.django_db
def test_verify_updates_session(
    importer_client,
    importer_user,
    charaktery_formalne,
    typy_kbn,
    jezyki,
):
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={
            "doi": None,
            "title": "Test",
        },
    )
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    from bpp.models import (
        Charakter_Formalny,
        Jezyk,
        Typ_KBN,
    )

    cf = Charakter_Formalny.objects.first()
    tk = Typ_KBN.objects.first()
    jez = Jezyk.objects.filter(widoczny=True).first()
    response = importer_client.post(
        url,
        {
            "charakter_formalny": (cf.pk if cf else ""),
            "typ_kbn": tk.pk if tk else "",
            "jezyk": jez.pk if jez else "",
            "jest_wydawnictwem_zwartym": "",
        },
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status == ImportSession.Status.VERIFIED


@pytest.mark.django_db
def test_verify_get_preserves_jezyk(
    importer_client,
    importer_user,
    jezyki,
):
    """GET na verify powinien zachować jezyk z sesji
    (scenariusz: Kontynuuj)."""
    from bpp.models import Jezyk

    jez = Jezyk.objects.filter(widoczny=True).first()
    assert jez is not None

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/lang-test",
        raw_data={},
        normalized_data={
            "title": "Test language",
            "doi": None,
        },
        jezyk=jez,
    )

    # Verify jezyk is saved in the DB
    session.refresh_from_db()
    assert session.jezyk_id == jez.pk

    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()

    # The select option for jezyk should be selected
    assert f'value="{jez.pk}" selected' in content


@pytest.mark.django_db
def test_verify_suggest_crossref_for_pbn_with_doi(
    importer_client,
    importer_user,
):
    """Verify step suggests CrossRef when non-CrossRef provider has DOI."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="PBN",
        identifier="pbn-123",
        raw_data={},
        normalized_data={
            "title": "Test PBN",
            "doi": "10.1234/pbn-test",
        },
    )
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Pobierz z CrossRef" in content
    assert "10.1234/pbn-test" in content


@pytest.mark.django_db
def test_verify_no_suggest_crossref_for_crossref(
    importer_client,
    importer_user,
):
    """No CrossRef suggestion when already using CrossRef provider."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/cr-test",
        raw_data={},
        normalized_data={
            "title": "Test CrossRef",
            "doi": "10.1234/cr-test",
        },
    )
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Pobierz z CrossRef" not in content


@pytest.mark.django_db
def test_verify_potential_duplicate_is_clickable(
    importer_client,
    importer_user,
):
    """Potencjalne duplikaty w BPP muszą być klikalne (link do pracy).

    Repro: dotąd lista renderowała sam ``{{ pub }}`` (tekst), więc nie
    dało się przejść do istniejącej pracy, żeby zweryfikować duplikat.
    """
    from model_bakery import baker

    from bpp.models import Wydawnictwo_Ciagle

    existing = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Istniejąca praca będąca duplikatem",
        doi="10.1234/dup-test",
    )

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/dup-test",
        raw_data={},
        normalized_data={
            "title": "Istniejąca praca będąca duplikatem",
            "doi": "10.1234/dup-test",
        },
    )
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()

    # Sekcja duplikatów w ogóle się pojawia
    assert "Potencjalne duplikaty w BPP" in content
    # Link do publicznej strony pracy
    assert f'href="{existing.get_absolute_url()}"' in content
    # Link do modułu redagowania (admin change)
    assert f"/admin/bpp/wydawnictwo_ciagle/{existing.pk}/change/" in content


@pytest.mark.django_db
def test_verify_no_suggest_crossref_without_doi(
    importer_client,
    importer_user,
):
    """No CrossRef suggestion when no DOI present."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="DSpace",
        identifier="http://example.com/123",
        raw_data={},
        normalized_data={
            "title": "Test DSpace",
        },
    )
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Pobierz z CrossRef" not in content
