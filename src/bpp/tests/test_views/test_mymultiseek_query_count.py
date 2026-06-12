"""Test liczby zapytań strony wyników multiseek dla raportów tabelarycznych.

Dla report_type z EXTRA_TYPES widok potrzebuje i licznika rekordów
(paginator_count), i sum punktacji (sumy). Oba mają być policzone JEDNYM
skanem (jeden aggregate), a nie osobnym COUNT + osobnym SELECT SUM —
przy DISTINCT + join do bpp_autorzy_mat każdy skan jest drogi.
"""

import json
from decimal import Decimal

import pytest
from django.conf import settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import translation
from multiseek.logic import STARTS_WITH
from multiseek.views import MULTISEEK_SESSION_KEY

from bpp.tests.util import any_ciagle

TYTUL_PREFIX = "QCount multiseek"
TABLE_REPORT_TYPE = "1"


def _ustaw_filtr(client, report_type):
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
                    "value": TYTUL_PREFIX,
                    "prev_op": None,
                },
            ],
            "ordering": {},
            "report_type": report_type,
        }
    )
    session.save()


@pytest.mark.django_db
def test_multiseek_results_tabela_jeden_skan_agregatow(client, standard_data):
    any_ciagle(
        tytul_oryginalny=f"{TYTUL_PREFIX} alfa",
        rok=2024,
        impact_factor=Decimal("1.500"),
        punkty_kbn=Decimal("40.00"),
    )
    any_ciagle(
        tytul_oryginalny=f"{TYTUL_PREFIX} beta",
        rok=2023,
        impact_factor=Decimal("2.500"),
        punkty_kbn=Decimal("100.00"),
    )

    _ustaw_filtr(client, report_type=TABLE_REPORT_TYPE)

    with CaptureQueriesContext(connection) as ctx:
        res = client.get(reverse("multiseek:results"))

    assert res.status_code == 200
    assert res.context["paginator_count"] == 2
    assert res.context["sumy"]["impact_factor__sum"] == Decimal("4.000")
    assert res.context["sumy"]["punkty_kbn__sum"] == Decimal("140.00")

    agregaty = [
        q["sql"]
        for q in ctx.captured_queries
        if "bpp_rekord_mat" in q["sql"]
        and ("COUNT(" in q["sql"].upper() or "SUM(" in q["sql"].upper())
    ]
    assert len(agregaty) == 1, agregaty
