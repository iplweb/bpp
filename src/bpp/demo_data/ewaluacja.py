"""Przeliczenia ewaluacyjne po wygenerowaniu demo data.

1. Cache punktacji/slotow (`Cache_Punktacja_Autora`/`_Dyscypliny`) dla prac
   demo — `rekord.przelicz_punkty_dyscyplin()` per rekord (bulk_create pominal
   denorm, wiec cache jest pusty).
2. Liczba N (`oblicz_liczby_n_dla_okresu`) i metryki (`generuj_metryki`) dla
   kazdego `OkresEwaluacji` nachodzacego na lata demo.

Plus sprzatanie: wiersze cache dla rekordow z manifestu (cache nie ma FK do
rekordu — klucz to krotka (content_type, pk) — wiec nie znika kaskadowo).
"""

from __future__ import annotations

from collections.abc import Iterable

from django.contrib.contenttypes.models import ContentType
from django.db import connection

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress


def okresy_dla_lat(od_roku: int, do_roku: int) -> list:
    """Okresy ewaluacji nachodzace na zakres lat [od_roku, do_roku]."""
    from ewaluacja_common.models import OkresEwaluacji

    return list(
        OkresEwaluacji.objects.filter(
            rok_od__lte=do_roku, rok_do__gte=od_roku
        ).order_by("rok_od")
    )


def przelicz_punkty_prac(
    prace: Iterable, *, desc: str, disable_progress: bool = False
) -> int:
    """`przelicz_punkty_dyscyplin()` per praca + zapis `cached_punkty_dyscyplin`.

    Zwraca liczbe prac, dla ktorych powstal cache punktacji."""
    prace = list(prace)
    if not prace:
        return 0
    model = type(prace[0])
    z_cache = 0
    for praca in make_progress(prace, desc=desc, disable=disable_progress):
        wynik = praca.przelicz_punkty_dyscyplin()
        # update() zamiast save(): nie odpalamy calego denorm/pre_save.
        model.objects.filter(pk=praca.pk).update(cached_punkty_dyscyplin=wynik)
        if wynik[0] or wynik[1]:
            z_cache += 1
    return z_cache


def przelicz_ewaluacje(
    *,
    uczelnia,
    prace_wc: Iterable,
    prace_wz: Iterable,
    od_roku: int,
    do_roku: int,
    manifest: Manifest,
    stdout,
    disable_progress: bool = False,
) -> dict:
    """Cache punktow → liczba N → metryki. Zwraca podsumowanie."""
    from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_okresu
    from ewaluacja_metryki.utils import generuj_metryki

    wc = przelicz_punkty_prac(
        prace_wc, desc="Punkty/sloty WC", disable_progress=disable_progress
    )
    wz = przelicz_punkty_prac(
        prace_wz, desc="Punkty/sloty WZ", disable_progress=disable_progress
    )
    stdout.write(f"[OK] Cache punktacji: {wc} prac ciągłych, {wz} zwartych.\n")

    okresy = okresy_dla_lat(od_roku, do_roku)
    for okres in okresy:
        stdout.write(f"[..] Liczba N i metryki dla okresu {okres}...\n")
        oblicz_liczby_n_dla_okresu(uczelnia, okres=okres)
        generuj_metryki(uczelnia=uczelnia, okres=okres)

    _zapisz_wyniki_autorow_w_manifescie(manifest)
    manifest.append(
        "ewaluacja",
        [],
        extra={"uczelnia": uczelnia.pk, "okresy": [o.pk for o in okresy]},
    )
    manifest.save()
    return {"wc": wc, "wz": wz, "okresy": okresy}


def _zapisz_wyniki_autorow_w_manifescie(manifest: Manifest) -> None:
    """Dopisuje do manifestu PK udzialow i metryk autorow demo."""
    from ewaluacja_liczba_n.models import (
        IloscUdzialowDlaAutoraZaCalosc,
        IloscUdzialowDlaAutoraZaRok,
    )
    from ewaluacja_metryki.models import MetrykaAutora

    autorzy = manifest.objects_for("bpp.Autor")
    for label, model in (
        ("ewaluacja_liczba_n.IloscUdzialowDlaAutoraZaRok", IloscUdzialowDlaAutoraZaRok),
        (
            "ewaluacja_liczba_n.IloscUdzialowDlaAutoraZaCalosc",
            IloscUdzialowDlaAutoraZaCalosc,
        ),
        ("ewaluacja_metryki.MetrykaAutora", MetrykaAutora),
    ):
        juz = set(manifest.objects_for(label))
        nowe = [
            pk
            for pk in model.objects.filter(autor_id__in=autorzy).values_list(
                "pk", flat=True
            )
            if pk not in juz
        ]
        manifest.append(label, nowe)


def usun_cache_punktacji(manifest: Manifest) -> int:
    """Kasuje Cache_Punktacja_Autora/_Dyscypliny dla prac demo z manifestu.

    Zwraca liczbe usunietych wierszy."""
    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
    from bpp.models.cache import Cache_Punktacja_Autora, Cache_Punktacja_Dyscypliny

    usunieto = 0
    for label, model in (
        ("bpp.Wydawnictwo_Ciagle", Wydawnictwo_Ciagle),
        ("bpp.Wydawnictwo_Zwarte", Wydawnictwo_Zwarte),
    ):
        pks = manifest.objects_for(label)
        if not pks:
            continue
        ct = ContentType.objects.get_for_model(model).pk
        for cache_model in (Cache_Punktacja_Autora, Cache_Punktacja_Dyscypliny):
            table = cache_model._meta.db_table
            with connection.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM {table} "  # noqa: S608 — nazwa tabeli z _meta
                    "WHERE rekord_id[1] = %s AND rekord_id[2] = ANY(%s)",
                    [ct, pks],
                )
                usunieto += cursor.rowcount
    return usunieto


def przelicz_liczbe_n_po_cleanup(manifest: Manifest, stdout) -> None:
    """Po cleanup na uczelni NIE stworzonej przez demo — przelicz liczbe N
    i metryki okresow, ktore demo przeliczylo (wyniki zawieraly dane demo).

    Gdy uczelnie stworzylo demo, jej wiersze liczby N znikaja kaskadowo."""
    from bpp.models import Uczelnia
    from ewaluacja_common.models import OkresEwaluacji
    from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_okresu
    from ewaluacja_metryki.utils import generuj_metryki

    extra = manifest.extra_for("ewaluacja")
    if not extra:
        return
    if manifest.extra_for("bpp.Uczelnia").get("created_by_demo"):
        return
    uczelnia = Uczelnia.objects.filter(pk=extra.get("uczelnia")).first()
    if uczelnia is None:
        return
    for okres in OkresEwaluacji.objects.filter(pk__in=extra.get("okresy", [])):
        stdout.write(f"[..] Przeliczam liczbę N i metryki dla okresu {okres}...\n")
        oblicz_liczby_n_dla_okresu(uczelnia, okres=okres)
        generuj_metryki(uczelnia=uczelnia, okres=okres)
