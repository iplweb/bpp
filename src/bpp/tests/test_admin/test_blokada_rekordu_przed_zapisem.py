"""Rollbar #5363: deadlock (ABBA) admin vs. denorm flush.

Zapis z admina musi zablokować wiersz rekordu (SELECT ... FOR UPDATE)
ZANIM dotknie tabel ``bpp_cache_punktacja_*`` -- tak samo jak flush denorm.
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from bpp.models.cache.punktacja import (
    Cache_Punktacja_Autora,
    Cache_Punktacja_Dyscypliny,
)

TABELE_CACHE = (
    Cache_Punktacja_Autora._meta.db_table,
    Cache_Punktacja_Dyscypliny._meta.db_table,
)


def _indeks_blokady(queries, db_table):
    for i, q in enumerate(queries):
        sql = q["sql"]
        if "FOR UPDATE" in sql and f'FROM "{db_table}"' in sql:
            return i
    return None


def _indeksy_cache(queries, tylko_zapis=False):
    ret = []
    for i, q in enumerate(queries):
        sql = q["sql"]
        if not any(t in sql for t in TABELE_CACHE):
            continue
        if tylko_zapis and not sql.lstrip().upper().startswith(("DELETE", "INSERT")):
            continue
        ret.append(i)
    return ret


@pytest.mark.parametrize(
    "fixture_name,url_name,form_id",
    [
        (
            "wydawnictwo_ciagle_z_autorem",
            "admin:bpp_wydawnictwo_ciagle_change",
            "wydawnictwo_ciagle_form",
        ),
        (
            "wydawnictwo_zwarte_z_autorem",
            "admin:bpp_wydawnictwo_zwarte_change",
            "wydawnictwo_zwarte_form",
        ),
        ("patent", "admin:bpp_patent_change", "patent_form"),
    ],
)
def test_admin_change_blokuje_rekord_przed_cache_punktacji(
    request,
    admin_app,
    uczelnia,
    charaktery_formalne,
    fixture_name,
    url_name,
    form_id,
):
    obj = request.getfixturevalue(fixture_name)
    db_table = type(obj)._meta.db_table

    # Zasiej wiersze cache dla rekordu: removeEntries() musi je realnie
    # skasować (pusty .delete() przez Collector kończy się na SELECT, bez
    # DELETE) -- inaczej test kolejności blokad przeszedłby „na pusto".
    rekord_id = [ContentType.objects.get_for_model(obj).pk, obj.pk]
    baker.make(
        Cache_Punktacja_Dyscypliny,
        rekord_id=rekord_id,
        uczelnia=uczelnia,
        pkd=1,
        slot=1,
    )
    baker.make(Cache_Punktacja_Autora, rekord_id=rekord_id, pkdaut=1, slot=1)

    page = admin_app.get(reverse(url_name, args=(obj.pk,)))
    form = page.forms[form_id]
    form["tytul_oryginalny"].value = "Zmieniony tytuł"

    with CaptureQueriesContext(connection) as ctx:
        res = form.submit()

    assert res.status_code == 302, res.text[:2000]
    obj.refresh_from_db()
    assert obj.tytul_oryginalny == "Zmieniony tytuł"

    queries = ctx.captured_queries
    blokada = _indeks_blokady(queries, db_table)
    assert blokada is not None, "brak SELECT ... FOR UPDATE na rekordzie"

    zapisy_cache = _indeksy_cache(queries, tylko_zapis=True)
    # Test nie może przejść „na pusto" -- zapis z admina MUSI ruszyć cache.
    assert zapisy_cache, "zapis nie dotknął bpp_cache_punktacja_*"

    wszystkie_cache = _indeksy_cache(queries)
    assert blokada < min(wszystkie_cache)

    # Blokada musi być w ogóle przed jakimkolwiek UPDATE rekordu.
    update_rekordu = [
        i
        for i, q in enumerate(queries)
        if q["sql"].lstrip().startswith(f'UPDATE "{db_table}"')
    ]
    assert update_rekordu
    assert blokada < min(update_rekordu)


def test_admin_add_nie_blokuje(admin_app, uczelnia, charaktery_formalne):
    from bpp.models import Wydawnictwo_Ciagle

    page = admin_app.get(reverse("admin:bpp_wydawnictwo_ciagle_add"))
    with CaptureQueriesContext(connection) as ctx:
        # Formularz pusty -> błędy walidacji, ale to nadal POST na add view.
        page.forms["wydawnictwo_ciagle_form"].submit()

    tabela = Wydawnictwo_Ciagle._meta.db_table
    assert _indeks_blokady(ctx.captured_queries, tabela) is None


def test_admin_change_smieciowe_id_bez_500(csrf_exempt_django_admin_app, uczelnia):
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=("nie-liczba",))
    res = csrf_exempt_django_admin_app.post(url, {}, expect_errors=True)
    # Standardowe zachowanie Django dla nieistniejącego obiektu: redirect.
    assert res.status_code == 302
