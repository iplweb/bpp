"""Regression tests dla bpp.views.mymultiseek."""

import csv
import io
import json
from decimal import Decimal

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import translation
from model_bakery import baker
from multiseek.logic import STARTS_WITH
from multiseek.views import MULTISEEK_SESSION_KEY, MULTISEEK_SESSION_KEY_REMOVED

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.cache import Rekord
from bpp.tests.util import any_ciagle
from bpp.views.mymultiseek import (
    MULTISEEK_DEFAULT_REPORT_TITLE,
    MULTISEEK_EXPORT_HEADERS,
    MULTISEEK_EXPORT_MAX_ROWS,
    MULTISEEK_EXPORT_XLSX_HEADERS,
    MULTISEEK_REPORT_TITLE_SESSION_KEY,
    XLSX_WORKSHEET_TITLE_MAX_LENGTH,
)

EXPORT_TITLE_PREFIX = "Eksport Multiseek"
TABLE_REPORT_TYPE = "1"


def _set_multiseek_title_filter(
    client,
    title_prefix=EXPORT_TITLE_PREFIX,
    report_type="0",
):
    with translation.override(settings.LANGUAGE_CODE):
        operator = str(STARTS_WITH)

    session = client.session
    session[MULTISEEK_SESSION_KEY] = json.dumps(
        {
            "form_data": [
                None,
                {
                    "field": "Tytuł pracy",
                    "operator": operator,
                    "value": title_prefix,
                    "prev_op": None,
                },
            ],
            "ordering": {},
            "report_type": report_type,
        }
    )
    session.save()


def _set_multiseek_report_title(client, title):
    session = client.session
    session[MULTISEEK_REPORT_TITLE_SESSION_KEY] = title
    session.save()


@pytest.fixture
def multiseek_export_rekord(standard_data, denorms, autor_jan_kowalski, jednostka):
    uczelnia = jednostka.uczelnia
    uczelnia.pbn_api_root = "https://pbn.example.org"
    uczelnia.save(update_fields=["pbn_api_root"])
    pbn_publication = baker.make(
        "pbn_api.Publication",
        mongoId="507f1f77bcf86cd799439011",
    )
    wydawnictwo = any_ciagle(
        tytul_oryginalny=f"{EXPORT_TITLE_PREFIX} - alfa",
        rok=2024,
        impact_factor=Decimal("1.230"),
        punkty_kbn=Decimal("42.00"),
        pbn_uid=pbn_publication,
    )
    wydawnictwo.dodaj_autora(
        autor_jan_kowalski,
        jednostka,
        zapisany_jako="Kowalski Jan",
    )
    denorms.flush()
    return Rekord.objects.get_original(wydawnictwo)


@pytest.fixture
def multiseek_export_pair(standard_data, denorms):
    first = any_ciagle(tytul_oryginalny=f"{EXPORT_TITLE_PREFIX} - alfa", rok=2024)
    second = any_ciagle(tytul_oryginalny=f"{EXPORT_TITLE_PREFIX} - beta", rok=2023)
    denorms.flush()
    return (
        Rekord.objects.get_original(first),
        Rekord.objects.get_original(second),
    )


@pytest.mark.django_db
def test_remove_from_removed_after_json_session_roundtrip(client):
    """Drugie wywołanie remove_from_results nie może zwrócić 500.

    JSONSerializer zamienia tuple → list przy zapisie sesji. Upstream
    multiseek.manually_add_or_remove robi set(data) na odczycie, co
    failuje na listach (unhashable). Poprzednio to powodowało HTTP 500
    przy drugim klinięciu "Wyrzuć" (oryginalna regresja Django 5.2 PW).

    Symulacja: wrzucamy do sesji listę [[3, 1]] (post-JSON format),
    wołamy endpoint i oczekujemy 200.
    """
    session = client.session
    session[MULTISEEK_SESSION_KEY_REMOVED] = [[3, 1]]  # post-JSON roundtrip
    session.save()

    response = client.get(reverse("remove_from_removed_results", kwargs={"pk": "3_1"}))
    assert response.status_code == 200

    # Po wywołaniu session ma zostać bez tego id (usunięte)
    session = client.session
    assert session.get(MULTISEEK_SESSION_KEY_REMOVED) == []


@pytest.mark.django_db
def test_remove_by_hand_twice_does_not_500(client):
    """Dwa kolejne wywołania remove_from_results nie 500-ują.

    Po pierwszym wywołaniu sesja ma [[id1, id2]] (JSON-serialized tuple).
    Drugie wywołanie musi poprawnie odczytać i znormalizować.
    """
    url = reverse("remove_from_results", kwargs={"pk": "3_7"})
    assert client.get(url).status_code == 200
    # Drugie wywołanie (to samo pk) — niech nie wybuchnie
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_multiseek_export_requires_login(client):
    response = client.get(reverse("multiseek-export", kwargs={"export_format": "csv"}))
    assert response.status_code == 302
    assert settings.LOGIN_URL in response["Location"]


@pytest.mark.django_db
def test_multiseek_export_csv(logged_in_client, multiseek_export_rekord):
    _set_multiseek_title_filter(logged_in_client)

    response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "csv"})
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert (
        f'filename="eksport-{MULTISEEK_DEFAULT_REPORT_TITLE}.csv"'
        in response["Content-Disposition"]
    )

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
    assert rows[0] == list(MULTISEEK_EXPORT_HEADERS)
    assert rows[1] == [
        multiseek_export_rekord.tytul_oryginalny,
        "Kowalski Jan",
        "2024",
        "1.230",
        "42.00",
        str(tuple(multiseek_export_rekord.pk)),
        "wydawnictwo ciągłe",
        str(multiseek_export_rekord.object_id),
        "507f1f77bcf86cd799439011",
        f"http://testserver{multiseek_export_rekord.get_absolute_url()}",
        "http://testserver/admin/bpp/wydawnictwo_ciagle/"
        f"{multiseek_export_rekord.object_id}/change/",
        "https://pbn.example.org/core/#/publication/view/"
        "507f1f77bcf86cd799439011/current",
    ]


@pytest.mark.django_db
def test_multiseek_export_filename_uses_report_title(
    logged_in_client,
    multiseek_export_rekord,
):
    _set_multiseek_title_filter(logged_in_client)
    _set_multiseek_report_title(logged_in_client, "Raport<br/>autorski")

    response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "csv"})
    )

    assert response.status_code == 200
    assert 'filename="eksport-Raport autorski.csv"' in response["Content-Disposition"]


@pytest.mark.django_db
def test_multiseek_export_csv_sanitizes_formula_like_values(
    logged_in_client,
    standard_data,
    denorms,
):
    title = "=Eksport Multiseek formula"
    any_ciagle(tytul_oryginalny=title)
    denorms.flush()
    _set_multiseek_title_filter(logged_in_client, title_prefix="=Eksport")

    response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "csv"})
    )

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8"))))
    assert rows[0]["tytul_oryginalny"] == "'" + title


@pytest.mark.django_db
def test_multiseek_export_csv_works_for_table_report_type(
    logged_in_client,
    multiseek_export_rekord,
):
    _set_multiseek_title_filter(logged_in_client, report_type=TABLE_REPORT_TYPE)

    response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "csv"})
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_multiseek_export_xlsx(logged_in_client, multiseek_export_rekord):
    _set_multiseek_title_filter(logged_in_client)

    response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "xlsx"})
    )

    assert response.status_code == 200
    assert response["Content-Type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert (
        f'filename="eksport-{MULTISEEK_DEFAULT_REPORT_TITLE}.xlsx"'
        in response["Content-Disposition"]
    )

    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(response.content))
    worksheet = workbook.active
    assert worksheet.title == MULTISEEK_DEFAULT_REPORT_TITLE
    rows = list(worksheet.iter_rows(values_only=True))
    assert rows[0] == MULTISEEK_EXPORT_XLSX_HEADERS
    assert rows[1] == (
        multiseek_export_rekord.tytul_oryginalny,
        "Kowalski Jan",
        2024,
        1.23,
        42,
        str(tuple(multiseek_export_rekord.pk)),
        "wydawnictwo ciągłe",
        multiseek_export_rekord.object_id,
        "507f1f77bcf86cd799439011",
        '=HYPERLINK("'
        f"http://testserver{multiseek_export_rekord.get_absolute_url()}"
        '", "[link]")',
        '=HYPERLINK("http://testserver/admin/bpp/wydawnictwo_ciagle/'
        f'{multiseek_export_rekord.object_id}/change/", "[link]")',
        '=HYPERLINK("https://pbn.example.org/core/#/publication/view/'
        '507f1f77bcf86cd799439011/current", "[link]")',
    )
    assert worksheet.freeze_panes == "B1"
    assert worksheet["D2"].data_type == "n"
    assert worksheet["E2"].data_type == "n"
    assert worksheet["D2"].number_format == "0.000"
    assert worksheet["E2"].number_format == "0.00"


@pytest.mark.django_db
def test_multiseek_export_xlsx_sheet_title_uses_limited_report_title(
    logged_in_client,
    multiseek_export_rekord,
):
    _set_multiseek_title_filter(logged_in_client)
    _set_multiseek_report_title(
        logged_in_client,
        "Raport: A/B*C? \x07[bardzo bardzo bardzo długi]",
    )

    response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "xlsx"})
    )

    assert response.status_code == 200

    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(response.content))
    worksheet_title = workbook.active.title
    assert worksheet_title.startswith("Raport A B C")
    assert len(worksheet_title) == XLSX_WORKSHEET_TITLE_MAX_LENGTH
    assert not set(r"[]:*?/\\").intersection(worksheet_title)
    assert "\x07" not in worksheet_title


@pytest.mark.django_db
def test_multiseek_export_removed_records(
    logged_in_client,
    multiseek_export_pair,
):
    visible, removed = multiseek_export_pair
    _set_multiseek_title_filter(logged_in_client)
    session = logged_in_client.session
    session[MULTISEEK_SESSION_KEY_REMOVED] = [removed.pk]
    session.save()

    normal_response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "csv"})
    )
    removed_response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "csv"})
        + "?print-removed=1"
    )

    normal_rows = list(
        csv.DictReader(io.StringIO(normal_response.content.decode("utf-8")))
    )
    removed_rows = list(
        csv.DictReader(io.StringIO(removed_response.content.decode("utf-8")))
    )
    assert [row["bpp_id"] for row in normal_rows] == [str(tuple(visible.pk))]
    assert [row["bpp_id"] for row in removed_rows] == [str(tuple(removed.pk))]


@pytest.mark.django_db
def test_multiseek_export_enforces_row_limit(
    logged_in_client,
    multiseek_export_pair,
    monkeypatch,
):
    _set_multiseek_title_filter(logged_in_client)
    monkeypatch.setattr("bpp.views.mymultiseek.MULTISEEK_EXPORT_MAX_ROWS", 1)

    response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "csv"})
    )

    assert response.status_code == 400
    assert "maksymalnie 1 rekordów" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_multiseek_export_links_hidden_over_limit(
    logged_in_client,
    multiseek_export_pair,
    monkeypatch,
):
    _set_multiseek_title_filter(logged_in_client)
    monkeypatch.setattr("bpp.views.mymultiseek.MULTISEEK_EXPORT_MAX_ROWS", 1)

    response = logged_in_client.get(reverse("live-results"))

    assert response.status_code == 200
    assert (
        reverse("multiseek-export", kwargs={"export_format": "csv"}).encode()
        not in response.content
    )
    assert (
        reverse("multiseek-export", kwargs={"export_format": "xlsx"}).encode()
        not in response.content
    )


def test_multiseek_export_max_rows_is_5000():
    assert MULTISEEK_EXPORT_MAX_ROWS == 5000


@pytest.mark.django_db
def test_multiseek_export_unknown_format(logged_in_client):
    response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "pdf"})
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_multiseek_export_does_not_match_unfiltered_records(
    logged_in_client,
    multiseek_export_rekord,
):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Poza eksportem")
    _set_multiseek_title_filter(logged_in_client)

    response = logged_in_client.get(
        reverse("multiseek-export", kwargs={"export_format": "csv"})
    )

    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8"))))
    assert [row["bpp_id"] for row in rows] == [str(tuple(multiseek_export_rekord.pk))]
