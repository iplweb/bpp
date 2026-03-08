"""Testy formularza SourceForm z widgetami autocomplete (dal)."""

import pytest
from dal import autocomplete
from model_bakery import baker

from bpp.models import Wydawca, Zrodlo
from importer_publikacji.forms import SourceForm
from importer_publikacji.models import ImportSession


@pytest.mark.django_db
def test_source_form_zrodlo_uses_autocomplete_widget():
    """Pole zrodlo powinno używać ModelSelect2."""
    form = SourceForm()
    widget = form.fields["zrodlo"].widget
    assert isinstance(widget, autocomplete.ModelSelect2)


@pytest.mark.django_db
def test_source_form_wydawca_uses_autocomplete_widget():
    """Pole wydawca powinno używać ModelSelect2."""
    form = SourceForm()
    widget = form.fields["wydawca"].widget
    assert isinstance(widget, autocomplete.ModelSelect2)


@pytest.mark.django_db
def test_source_form_zrodlo_autocomplete_url():
    """Widget zrodlo powinien wskazywać na admin-zrodlo-autocomplete."""
    from django.urls import reverse

    form = SourceForm()
    widget = form.fields["zrodlo"].widget
    expected = reverse("bpp:admin-zrodlo-autocomplete")
    assert widget.url == expected


@pytest.mark.django_db
def test_source_form_wydawca_autocomplete_url():
    """Widget wydawca powinien wskazywać na wydawca-autocomplete."""
    from django.urls import reverse

    form = SourceForm()
    widget = form.fields["wydawca"].widget
    expected = reverse("bpp:wydawca-autocomplete")
    assert widget.url == expected


@pytest.mark.django_db
def test_source_form_renders_autocomplete_attrs():
    """Wyrenderowany HTML powinien zawierać atrybuty dal."""
    form = SourceForm()
    html = form.as_p()
    assert "data-autocomplete-light-function" in html


@pytest.mark.django_db
def test_source_form_valid_with_zrodlo():
    """Formularz powinien być poprawny z wybranym źródłem."""
    zrodlo = baker.make(Zrodlo)
    form = SourceForm(data={
        "zrodlo": zrodlo.pk,
        "wydawca": "",
        "wydawca_opis": "",
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_source_form_valid_with_wydawca():
    """Formularz powinien być poprawny z wybranym wydawcą."""
    wydawca = baker.make(Wydawca)
    form = SourceForm(data={
        "zrodlo": "",
        "wydawca": wydawca.pk,
        "wydawca_opis": "",
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_source_form_valid_empty():
    """Formularz powinien być poprawny bez danych
    (walidacja wymagalności jest w widoku)."""
    form = SourceForm(data={
        "zrodlo": "",
        "wydawca": "",
        "wydawca_opis": "",
    })
    assert form.is_valid()


@pytest.mark.django_db
def test_source_form_initial_zrodlo():
    """Initial zrodlo powinno być ustawione w widgecie."""
    zrodlo = baker.make(Zrodlo)
    form = SourceForm(initial={"zrodlo": zrodlo.pk})
    html = str(form["zrodlo"])
    assert str(zrodlo.pk) in html


@pytest.mark.django_db
def test_source_form_initial_wydawca():
    """Initial wydawca powinno być ustawione w widgecie."""
    wydawca = baker.make(Wydawca)
    form = SourceForm(initial={"wydawca": wydawca.pk})
    html = str(form["wydawca"])
    assert str(wydawca.pk) in html


@pytest.mark.django_db
def test_source_form_media_includes_dal_js():
    """Media formularza powinno zawierać skrypty dal."""
    form = SourceForm()
    media_html = str(form.media)
    assert "autocomplete_light" in media_html


@pytest.mark.django_db
def test_source_step_renders_autocomplete(
    importer_client,
    importer_user,
    charaktery_formalne,
    typy_kbn,
    jezyki,
):
    """Krok 3 powinien renderować widgety autocomplete."""
    from django.urls import reverse

    from bpp.models import Charakter_Formalny, Jezyk, Typ_KBN

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={
            "doi": "10.1234/test",
            "title": "Test",
            "source_title": None,
            "source_abbreviation": None,
            "publisher": None,
        },
        charakter_formalny=Charakter_Formalny.objects.first(),
        typ_kbn=Typ_KBN.objects.first(),
        jezyk=Jezyk.objects.filter(widoczny=True).first(),
        status=ImportSession.Status.VERIFIED,
    )
    url = reverse(
        "importer_publikacji:source",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "data-autocomplete-light-function" in content


@pytest.mark.django_db
def test_source_step_post_with_zrodlo(
    importer_client,
    importer_user,
    charaktery_formalne,
    typy_kbn,
    jezyki,
):
    """POST z wybranym źródłem powinien przejść dalej."""
    from django.urls import reverse

    from bpp.models import Charakter_Formalny, Jezyk, Typ_KBN

    zrodlo = baker.make(Zrodlo)
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={
            "doi": "10.1234/test",
            "title": "Test",
            "authors": [],
            "source_title": "Some Journal",
            "source_abbreviation": None,
            "publisher": None,
            "year": 2024,
        },
        charakter_formalny=Charakter_Formalny.objects.first(),
        typ_kbn=Typ_KBN.objects.first(),
        jezyk=Jezyk.objects.filter(widoczny=True).first(),
        status=ImportSession.Status.VERIFIED,
        jest_wydawnictwem_zwartym=False,
    )
    url = reverse(
        "importer_publikacji:source",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(
        url,
        {"zrodlo": zrodlo.pk, "wydawca": "", "wydawca_opis": ""},
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.zrodlo == zrodlo
    assert session.status == ImportSession.Status.SOURCE_MATCHED


@pytest.mark.django_db
def test_source_step_post_with_wydawca(
    importer_client,
    importer_user,
    charaktery_formalne,
    typy_kbn,
    jezyki,
):
    """POST z wydawcą dla wydawnictwa zwartego."""
    from django.urls import reverse

    from bpp.models import Charakter_Formalny, Jezyk, Typ_KBN

    wydawca = baker.make(Wydawca)
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={
            "doi": "10.1234/test",
            "title": "Test",
            "authors": [],
            "source_title": None,
            "source_abbreviation": None,
            "publisher": "Some Publisher",
            "year": 2024,
        },
        charakter_formalny=Charakter_Formalny.objects.first(),
        typ_kbn=Typ_KBN.objects.first(),
        jezyk=Jezyk.objects.filter(widoczny=True).first(),
        status=ImportSession.Status.VERIFIED,
        jest_wydawnictwem_zwartym=True,
    )
    url = reverse(
        "importer_publikacji:source",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(
        url,
        {
            "zrodlo": "",
            "wydawca": wydawca.pk,
            "wydawca_opis": "",
        },
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.wydawca == wydawca
    assert session.status == ImportSession.Status.SOURCE_MATCHED
