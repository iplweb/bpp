"""FD#521: edytor zapytań w formularzu „Źródła danych”.

Kolorowanie składni, przycisk „Formatuj” i podpowiadanie pól DjangoQL robi
``django-flexible-reports`` (>= 0.6.0). Po stronie BPP pilnujemy tego, co jest
nasze: że edytor dostaje schemat ``BppQLSchema`` (ten sam, którym źródło danych
jest walidowane) i że działa w naszym, nadpisanym formularzu źródła danych.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from flexible_reports.models import Datasource

from bpp.models.cache import Rekord

SCHEMAT = "admin:flexible_reports_datasource_query_editor_schema"
FORMATUJ = "admin:flexible_reports_datasource_query_editor_format"


def _rekord_ct():
    return ContentType.objects.get_for_model(Rekord)


@pytest.mark.django_db
def test_fd521_formularz_zrodla_danych_laduje_edytor(admin_client):
    html = admin_client.get(
        reverse("admin:flexible_reports_datasource_add")
    ).rendered_content

    assert 'class="flexible-reports-query"' in html
    assert "flexible_reports/js/query_editor" in html
    # Podpowiadanie pól DjangoQL — widżet z pakietu djangoql.
    assert "djangoql/js/completion" in html


@pytest.mark.django_db
def test_fd521_edytor_dziala_w_formularzu_edycji_z_powrotem_do_raportu(admin_client):
    # Formularz edycji ma w BPP własny szablon (odnośnik „Wróć do raportu”,
    # FD#448) — edytor musi się w nim załadować tak samo.
    ds = Datasource.objects.create(
        label="x", base_model=_rekord_ct(), dsl_query="rok = 2020"
    )
    html = admin_client.get(
        reverse("admin:flexible_reports_datasource_change", args=[ds.pk])
        + "?powrot=/nowe_raporty/"
    ).rendered_content

    assert 'class="flexible-reports-query"' in html
    assert "flexible_reports/js/query_editor" in html


@pytest.mark.django_db
def test_fd521_podpowiedzi_ze_schematu_bpp(admin_client):
    """Po wpisaniu ``charakter_formalny.`` edytor ma podpowiadać pola charakteru
    formalnego — czyli schemat dla Rekordu musi opisywać tę relację i model, na
    który ona wskazuje."""
    dane = admin_client.get(
        reverse(SCHEMAT), {"base_model": _rekord_ct().pk}
    ).json()["djangoql"]

    assert dane["current_model"] == "bpp.rekord"
    rekord = dane["models"]["bpp.rekord"]
    assert rekord["charakter_formalny"]["relation"] == "bpp.charakter_formalny"
    assert {"nazwa", "skrot"} <= set(dane["models"]["bpp.charakter_formalny"])
    # Picker ``__rel`` jest tylko w ``BppQLSchema`` — dowód, że edytor
    # podpowiada z naszego schematu, a nie z domyślnego schematu djangoql.
    assert "charakter_formalny__rel" in rekord


@pytest.mark.django_db
def test_fd521_podpowiedzi_nie_ujawniaja_pol_z_poswiadczeniami(admin_client):
    dane = admin_client.get(
        reverse(SCHEMAT), {"base_model": _rekord_ct().pk}
    ).json()["djangoql"]

    for pola in dane["models"].values():
        assert "password" not in pola


@pytest.mark.django_db
def test_fd521_formatuj_nie_zmienia_zapytania_bpp(admin_client):
    # Zapytanie w stylu BPP: picker ``__rel`` z nawiasem kwadratowym w
    # wartości, parametr szablonu i operator przyklejony do pola.
    zapytanie = (
        'charakter_formalny__rel = "Artykuł w czasopiśmie [5]" and rok>=2020 '
        'and (typ_kbn.skrot = "PO" or typ_kbn.skrot = "PW" '
        'or jezyk.skrot in ("pol.", "ang.")) '
        "and autorzy.autor = {{ obiekt.pk }}"
    )
    wynik = admin_client.post(
        reverse(FORMATUJ), {"q": zapytanie, "language": "djangoql"}
    ).json()["formatted"]

    assert wynik == (
        'charakter_formalny__rel = "Artykuł w czasopiśmie [5]"\n'
        "and rok>=2020\n"
        "and (\n"
        '    typ_kbn.skrot = "PO"\n'
        '    or typ_kbn.skrot = "PW"\n'
        '    or jezyk.skrot in ("pol.", "ang.")\n'
        ")\n"
        "and autorzy.autor = {{ obiekt.pk }}"
    )
    # To samo zapytanie co do znaku — różni się wyłącznie białymi znakami.
    assert "".join(wynik.split()) == "".join(zapytanie.split())


@pytest.mark.django_db
def test_fd521_formatuj_domyslne_zapytania_raportow(admin_client):
    """Zapytania seedowanych raportów (django-dsl, z ``{% if %}``
    i ``{% comment %}``) dają się sformatować i nie zmieniają przy tym treści."""
    from flexible_reports.query_format import significant_tokens

    from nowe_raporty.seeding import definicje as d

    zapytania = [zapytanie for _label, zapytanie in d.WSPOLNE_DATASOURCE.values()]
    zapytania += [zapytanie for _label, zapytanie in d.DATASOURCE_2X_BAZA.values()]
    assert zapytania

    for zapytanie in zapytania:
        odpowiedz = admin_client.post(
            reverse(FORMATUJ), {"q": zapytanie, "language": "dsl"}
        )
        assert odpowiedz.status_code == 200, zapytanie
        assert significant_tokens(
            odpowiedz.json()["formatted"], "dsl"
        ) == significant_tokens(zapytanie, "dsl")
