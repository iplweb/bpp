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
            "rok": "2023",
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


def _verify_form_data(cf, tk, jez, **extra):
    """Zbuduj payload POST dla formularza weryfikacji."""
    data = {
        "charakter_formalny": cf.pk if cf else "",
        "typ_kbn": tk.pk if tk else "",
        "jezyk": jez.pk if jez else "",
        "jest_wydawnictwem_zwartym": "",
    }
    data.update(extra)
    return data


@pytest.mark.django_db
def test_verify_wymaga_roku_gdy_brak_w_danych(
    importer_client,
    importer_user,
    charaktery_formalne,
    typy_kbn,
    jezyki,
):
    """Sesja bez roku w normalized_data: POST bez 'rok' → formularz nieważny,
    status nie zmienia się na VERIFIED (rok jest wymagany)."""
    from bpp.models import Charakter_Formalny, Jezyk, Typ_KBN

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1007/0-306-46843-3_60",
        raw_data={},
        normalized_data={"title": "Bez roku", "doi": None},
    )
    cf = Charakter_Formalny.objects.first()
    tk = Typ_KBN.objects.first()
    jez = Jezyk.objects.filter(widoczny=True).first()
    url = reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})

    response = importer_client.post(url, _verify_form_data(cf, tk, jez))

    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status != ImportSession.Status.VERIFIED
    assert session.normalized_data.get("year") in (None, "")


@pytest.mark.django_db
def test_verify_zapisuje_reczny_rok(
    importer_client,
    importer_user,
    charaktery_formalne,
    typy_kbn,
    jezyki,
):
    """POST z 'rok' zapisuje go do normalized_data['year'] jako int i
    przechodzi do kolejnego kroku (status VERIFIED)."""
    from bpp.models import Charakter_Formalny, Jezyk, Typ_KBN

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1007/0-306-46843-3_60",
        raw_data={},
        normalized_data={"title": "Bez roku", "doi": None},
    )
    cf = Charakter_Formalny.objects.first()
    tk = Typ_KBN.objects.first()
    jez = Jezyk.objects.filter(widoczny=True).first()
    url = reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})

    response = importer_client.post(url, _verify_form_data(cf, tk, jez, rok="2004"))

    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status == ImportSession.Status.VERIFIED
    assert session.normalized_data.get("year") == 2004


@pytest.mark.django_db
def test_verify_context_prefill_roku(importer_user, jezyki):
    """_verify_context prefilluje pole 'rok' wartością z normalized_data."""
    from django.test import RequestFactory

    from importer_publikacji.views import _verify_context

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/rok",
        raw_data={},
        normalized_data={"title": "Z rokiem", "year": 2019},
    )
    request = RequestFactory().get("/")
    request.user = importer_user

    ctx = _verify_context(request, session)

    assert ctx["form"].initial.get("rok") == 2019


@pytest.mark.django_db
def test_verify_koryguje_bledny_rok(
    importer_client,
    importer_user,
    charaktery_formalne,
    typy_kbn,
    jezyki,
):
    """POST z innym 'rok' nadpisuje istniejący rok w normalized_data —
    operator może poprawić błędny rok, nie tylko uzupełnić brakujący."""
    from bpp.models import Charakter_Formalny, Jezyk, Typ_KBN

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/zly-rok",
        raw_data={},
        normalized_data={"title": "Zły rok", "year": 2000, "doi": None},
    )
    cf = Charakter_Formalny.objects.first()
    tk = Typ_KBN.objects.first()
    jez = Jezyk.objects.filter(widoczny=True).first()
    url = reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})

    response = importer_client.post(url, _verify_form_data(cf, tk, jez, rok="2004"))

    assert response.status_code == 200
    session.refresh_from_db()
    assert session.normalized_data.get("year") == 2004
