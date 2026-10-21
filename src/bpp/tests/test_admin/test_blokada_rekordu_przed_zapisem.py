"""Rollbar #5363: deadlock (ABBA) admin vs. denorm flush.

Zapis z admina musi zablokować wiersz rekordu (SELECT ... FOR UPDATE)
ZANIM dotknie tabel ``bpp_cache_punktacja_*`` -- tak samo jak flush denorm.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

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
    "rekord_z_dyscyplinami",
    ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"],
    indirect=True,
)
def test_admin_change_blokuje_rekord_przed_cache_punktacji(
    rekord_z_dyscyplinami, admin_app, uczelnia
):
    # Rekord z autorami w dyscyplinach, dla którego sloty DAJĄ się policzyć:
    # od odroczenia ``cached_punkty_dyscyplin`` (``OdroczPunktyDyscyplinMixin``)
    # cache w trakcie requestu przebudowuje wyłącznie ``save_related`` -- i to
    # tylko dla rekordów adaptowalnych. Na rekordzie nieadaptowalnym test
    # kolejności blokad przeszedłby „na pusto".
    obj = rekord_z_dyscyplinami
    nazwa = obj._meta.model_name
    db_table = type(obj)._meta.db_table

    page = admin_app.get(reverse(f"admin:bpp_{nazwa}_change", args=(obj.pk,)))
    form = page.forms[f"{nazwa}_form"]
    form["tytul_oryginalny"].value = "Zmieniony tytuł"

    with CaptureQueriesContext(connection) as ctx:
        res = form.submit()

    assert res.status_code == 302, res.text[:2000]
    obj.refresh_from_db()
    assert obj.tytul_oryginalny == "Zmieniony tytuł"

    queries = ctx.captured_queries
    blokada = _indeks_blokady(queries, db_table)
    assert blokada is not None, "brak SELECT ... FOR UPDATE na rekordzie"

    # Blokada musi być w ogóle przed jakimkolwiek UPDATE rekordu.
    update_rekordu = [
        i
        for i, q in enumerate(queries)
        if q["sql"].lstrip().startswith(f'UPDATE "{db_table}"')
    ]
    assert update_rekordu
    assert blokada < min(update_rekordu)

    zapisy_cache = _indeksy_cache(queries, tylko_zapis=True)
    if nazwa == "patent":
        # Patent nie jest adaptowalny: save_related nie rusza cache, a pre_save
        # denorma jest odroczony -- request nie pisze do cache wcale.
        assert not zapisy_cache
        return

    # Test nie może przejść „na pusto" -- zapis z admina MUSI ruszyć cache.
    assert zapisy_cache, "zapis nie dotknął bpp_cache_punktacja_*"

    wszystkie_cache = _indeksy_cache(queries)
    assert blokada < min(wszystkie_cache)
    # Cache przebudowany PO zapisie rodzica (save_related), nie w pre_save.
    assert min(zapisy_cache) > min(update_rekordu)


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
