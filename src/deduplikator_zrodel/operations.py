"""Logika skanu duplikatów źródeł uruchamiana w tle przez django-liveops.

`perform_scan(operation, p)` jest czystą, testowalną funkcją: iteruje źródła-
seedy, znajduje kandydatów istniejącą logiką z `utils`, i zapisuje pary o
dodatnim score jako `SourceDuplicateCandidate` — raz na nieuporządkowaną parę.
`ScanZrodelForDuplicates.run()` deleguje tu.
"""

import logging

from django.db.models import Count

from bpp.models import Zrodlo

from .models import SourceDuplicateCandidate
from .utils import ocen_podobienstwo, znajdz_podobne_zrodla

logger = logging.getLogger(__name__)

# Co ile źródeł zapisywać `sources_scanned` do DB (batch — nie po każdym).
PROGRESS_BATCH = 25


def seed_queryset():
    """Źródła-seedy skanu: mają publikacje i ministerialne ID.

    Ten sam zakres co dzisiejsze `znajdz_pierwszego_zrodlo_z_duplikatami`
    (base_queryset) — zamierzony, nie regresja. Patrz spec §Ryzyka.
    """
    return Zrodlo.objects.annotate(pub_count=Count("wydawnictwo_ciagle")).filter(
        pub_count__gt=0, pbn_uid__mniswId__isnull=False
    )


def _pub_count(zrodlo):
    """Liczba publikacji — z anotacji `pub_count` (seed/kandydat) lub zapytania."""
    value = getattr(zrodlo, "pub_count", None)
    if value is None:
        value = zrodlo.wydawnictwo_ciagle_set.count()
    return value


def _canonical(a, b):
    """(main, duplikat): main = źródło o większej liczbie publikacji;
    remis → mniejszy pk zostaje główny."""
    a_key = (_pub_count(a), -a.pk)
    b_key = (_pub_count(b), -b.pk)
    return (a, b) if a_key >= b_key else (b, a)


def perform_scan(operation, p):
    """Przeskanuj bazę i zapisz `SourceDuplicateCandidate` dla `operation`."""
    seeds = seed_queryset()
    total = seeds.count()

    operation.total_sources = total
    operation.sources_scanned = 0
    operation.duplicates_found = 0
    operation.save(
        update_fields=["total_sources", "sources_scanned", "duplicates_found"]
    )

    # Idempotencja przy restarcie: usuń kandydatów poprzedniego biegu.
    operation.candidates.all().delete()

    seen = set()
    found = 0
    scanned = 0

    for zrodlo in p.track(seeds.iterator(), total=total, label="Skanowanie źródeł"):
        for kandydat in znajdz_podobne_zrodla(zrodlo):
            score = ocen_podobienstwo(zrodlo, kandydat)
            if score <= 0:
                continue

            key = (min(zrodlo.pk, kandydat.pk), max(zrodlo.pk, kandydat.pk))
            if key in seen:
                continue
            seen.add(key)

            main, dup = _canonical(zrodlo, kandydat)
            SourceDuplicateCandidate.objects.create(
                scan=operation,
                main_zrodlo=main,
                duplicate_zrodlo=dup,
                confidence_score=score,
                main_nazwa=main.nazwa or "",
                duplicate_nazwa=dup.nazwa or "",
                main_pub_count=_pub_count(main),
                duplicate_pub_count=_pub_count(dup),
            )
            found += 1

        scanned += 1
        if scanned % PROGRESS_BATCH == 0:
            operation.sources_scanned = scanned
            operation.save(update_fields=["sources_scanned"])

    operation.sources_scanned = scanned
    operation.duplicates_found = found
    operation.save(update_fields=["sources_scanned", "duplicates_found"])

    p.result(context={"duplicates_found": found})
