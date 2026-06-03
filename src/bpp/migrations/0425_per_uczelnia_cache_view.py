from django.db import migrations

DROP = "DROP VIEW IF EXISTS bpp_cache_punktacja_autora_view;"

# Join uwzględnia uczelnię: wiersz autora (jego jednostka → uczelnia) łączy się
# WYŁĄCZNIE z agregatem dyscypliny SWOJEJ uczelni. Brak gałęzi `IS NULL` —
# backfill (RunPython niżej) gwarantuje, że po tej migracji żaden wiersz
# Cache_Punktacja_Dyscypliny nie ma uczelnia_id NULL (single-install dostaje ID
# domyślnej uczelni; multi-install z wierszami bez uczelni → migracja failuje).
CREATE_NEW = """
CREATE VIEW bpp_cache_punktacja_autora_view AS
SELECT a.id,
       a.rekord_id,
       a.pkdaut,
       a.slot,
       a.autor_id,
       a.dyscyplina_id,
       a.jednostka_id,
       d.autorzy_z_dyscypliny,
       d.zapisani_autorzy_z_dyscypliny
FROM bpp_cache_punktacja_autora a
JOIN bpp_jednostka j ON j.id = a.jednostka_id
JOIN bpp_cache_punktacja_dyscypliny d
  ON a.rekord_id = d.rekord_id
 AND a.dyscyplina_id = d.dyscyplina_id
 AND d.uczelnia_id = j.uczelnia_id;
"""

CREATE_OLD = """
CREATE VIEW bpp_cache_punktacja_autora_view AS
SELECT bpp_cache_punktacja_autora.id,
       bpp_cache_punktacja_autora.rekord_id,
       bpp_cache_punktacja_autora.pkdaut,
       bpp_cache_punktacja_autora.slot,
       bpp_cache_punktacja_autora.autor_id,
       bpp_cache_punktacja_autora.dyscyplina_id,
       bpp_cache_punktacja_autora.jednostka_id,
       bpp_cache_punktacja_dyscypliny.autorzy_z_dyscypliny,
       bpp_cache_punktacja_dyscypliny.zapisani_autorzy_z_dyscypliny
FROM bpp_cache_punktacja_autora,
     bpp_cache_punktacja_dyscypliny
WHERE bpp_cache_punktacja_autora.rekord_id = bpp_cache_punktacja_dyscypliny.rekord_id
  AND bpp_cache_punktacja_autora.dyscyplina_id = bpp_cache_punktacja_dyscypliny.dyscyplina_id;
"""


def backfill_uczelnia(apps, schema_editor):
    """Wypełnij `uczelnia_id` w istniejących (legacy) wierszach
    Cache_Punktacja_Dyscypliny powstałych przed dodaniem kolumny.

    - Single-install (dokładnie jedna Uczelnia): wszystkie jednostki — a więc
      i autorzy — należą do tej jednej uczelni, a partycja dzielnika k/m jest
      wtedy no-opem, więc legacy liczby (pkd/slot) są już poprawne; brakuje tylko
      tagu uczelni. Wpisujemy ID tej (domyślnej) uczelni.
    - Multi-install z wierszami bez uczelni: NIE zgadujemy. `slot`/`pkdaut` zależą
      od dzielnika liczonego osobno per uczelnia, więc starego (niepartycjonowanego)
      wyniku nie da się przypisać do konkretnej uczelni. Migracja failuje — admin
      ma najpierw przeliczyć cache per-uczelnia (pełny denorm rebuild) albo usunąć
      stary cache i zaaplikować migrację na czystych danych.
    - Świeża instalacja (brak wierszy bez uczelni) — no-op, przechodzi zawsze.
    """
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    Cache_Punktacja_Dyscypliny = apps.get_model("bpp", "Cache_Punktacja_Dyscypliny")

    null_qs = Cache_Punktacja_Dyscypliny.objects.filter(uczelnia__isnull=True)
    if not null_qs.exists():
        return

    uczelnie = list(Uczelnia.objects.all()[:2])
    if len(uczelnie) == 1:
        null_qs.update(uczelnia=uczelnie[0])
        return

    raise RuntimeError(
        "Migracja per-uczelnia (0425): w bazie istnieją wiersze "
        "Cache_Punktacja_Dyscypliny bez przypisanej uczelni, a w systemie jest "
        f"{len(uczelnie)} uczelni — nie można zdeterministycznie przypisać uczelni "
        "(slot/pkd liczone są osobnym dzielnikiem per uczelnia). Przelicz cache "
        "per-uczelnia PRZED tą migracją (pełny denorm rebuild), albo usuń stary "
        "cache punktacji i zaaplikuj migrację na czystych danych."
    )


def backfill_uczelnia_reverse(apps, schema_editor):
    # Backfill jest jednokierunkowy: przy rollbacku nie zerujemy `uczelnia_id`
    # (kolumna i tak znika przy odwróceniu migracji 0424).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0424_cache_punktacja_dyscypliny_uczelnia_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_uczelnia, backfill_uczelnia_reverse),
        migrations.RunSQL(sql=DROP + CREATE_NEW, reverse_sql=DROP + CREATE_OLD),
    ]
