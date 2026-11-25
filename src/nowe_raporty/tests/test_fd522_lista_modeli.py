"""FD#522: krótka lista modeli w polu „Podstawowy model” źródła danych."""

from importlib.util import find_spec

import pytest
from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from flexible_reports.models import Datasource

from bpp.models import Autor, Wydawnictwo_Zwarte
from bpp.models.cache import Autorzy, Rekord

wymaga_pakietu = pytest.mark.skipif(
    find_spec("flexible_reports.base_models") is None,
    reason="wymaga django-flexible-reports >= 0.6.0 (FLEXIBLE_REPORTS_BASE_MODELS)",
)


def _ct(model):
    return ContentType.objects.get_for_model(model, for_concrete_model=False)


def _modele_w_formularzu(odpowiedz):
    pole = odpowiedz.context["adminform"].form.fields["base_model"]
    return [ct.model_class() for ct in pole.queryset]


def test_fd522_ustawienie_wskazuje_istniejace_modele():
    # Niezależne od wersji pakietu: literówka w ustawieniu ma wyjść w testach,
    # a nie dopiero jako błąd 500 formularza źródła danych.
    modele = [apps.get_model(m) for m in settings.FLEXIBLE_REPORTS_BASE_MODELS]
    assert modele == [Rekord, Autorzy, Autor]


@wymaga_pakietu
@pytest.mark.django_db
def test_fd522_nowe_zrodlo_danych_ma_krotka_liste_i_domyslny_rekord(admin_client):
    odpowiedz = admin_client.get(reverse("admin:flexible_reports_datasource_add"))

    assert _modele_w_formularzu(odpowiedz) == [Rekord, Autorzy, Autor]
    form = odpowiedz.context["adminform"].form
    assert form["base_model"].initial == _ct(Rekord).pk


@wymaga_pakietu
@pytest.mark.django_db
def test_fd522_istniejace_zrodlo_z_innym_modelem_daje_sie_edytowac(admin_client):
    # Źródło danych klienta zapisane przed wprowadzeniem krótkiej listy.
    stary = _ct(Wydawnictwo_Zwarte)
    ds = Datasource.objects.create(
        label="stare", base_model=stary, dsl_query='tytul_oryginalny = "x"'
    )
    url = reverse("admin:flexible_reports_datasource_change", args=[ds.pk])

    odpowiedz = admin_client.get(url)
    # Jego model jest na liście (po modelach z ustawienia) i jest wybrany.
    assert _modele_w_formularzu(odpowiedz) == [
        Rekord,
        Autorzy,
        Autor,
        Wydawnictwo_Zwarte,
    ]
    assert odpowiedz.context["adminform"].form["base_model"].initial == stary.pk

    odpowiedz = admin_client.post(
        url,
        {
            "label": "stare, po zmianie",
            "base_model": stary.pk,
            "query_language": "dsl",
            "dsl_query": 'tytul_oryginalny = "y"',
            "sample_context": "{}",
            "distinct": "on",
        },
    )
    assert odpowiedz.status_code == 302, odpowiedz.rendered_content
    ds.refresh_from_db()
    assert ds.label == "stare, po zmianie"
    assert ds.base_model == stary


@wymaga_pakietu
@pytest.mark.django_db
def test_fd522_nowego_zrodla_nie_da_sie_zalozyc_na_modelu_spoza_listy(admin_client):
    odpowiedz = admin_client.post(
        reverse("admin:flexible_reports_datasource_add"),
        {
            "label": "nowe",
            "base_model": _ct(Wydawnictwo_Zwarte).pk,
            "query_language": "dsl",
            "dsl_query": 'tytul_oryginalny = "x"',
            "sample_context": "{}",
            "distinct": "on",
        },
    )
    assert odpowiedz.status_code == 200
    assert "base_model" in odpowiedz.context["adminform"].form.errors
    assert not Datasource.objects.filter(label="nowe").exists()


@wymaga_pakietu
@pytest.mark.django_db
def test_fd522_zrodlo_z_modelem_spoza_listy_nadal_filtruje(wydawnictwo_zwarte):
    # Lista to filtr formularza — zapisane źródła danych działają jak dotąd.
    ds = Datasource.objects.create(
        label="stare",
        base_model=_ct(Wydawnictwo_Zwarte),
        dsl_query=f'tytul_oryginalny = "{wydawnictwo_zwarte.tytul_oryginalny}"',
    )
    ds.full_clean()
    assert list(ds.filter_queryset(Wydawnictwo_Zwarte.objects.all())) == [
        wydawnictwo_zwarte
    ]
