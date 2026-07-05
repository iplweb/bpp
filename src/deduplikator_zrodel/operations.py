"""Logika skanu duplikatów źródeł uruchamiana w tle przez django-liveops.

`perform_scan(operation, p)` jest czystą, testowalną funkcją: iteruje źródła-
seedy, znajduje kandydatów istniejącą logiką z `utils`, i zapisuje pary o
dodatnim score jako `SourceDuplicateCandidate` — raz na nieuporządkowaną parę.
`ScanZrodelForDuplicates.run()` deleguje tu.
"""

import logging

from django.db.models import Count
from django.utils import timezone

from bpp.models import Zrodlo

from .models import SourceDuplicateCandidate
from .utils import ocen_podobienstwo, znajdz_podobne_zrodla

logger = logging.getLogger(__name__)

# Co ile źródeł zapisywać `sources_scanned` do DB / odświeżać status (batch).
PROGRESS_BATCH = 25


def _fmt_duration(seconds):
    """Czytelny czas trwania: '2 min 30 s' / '45 s' / '1 h 05 min'."""
    seconds = int(max(seconds, 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"


def format_progress_status(scanned, total, found, *, started_on=None, now=None):
    """Tekstowy status skanu: liczniki + (gdy się da) szacowany czas końca.

    Czysta funkcja — ETA liczona z `started_on`/`now`; bez nich pokazuje tylko
    liczniki (np. na starcie, gdy nic jeszcze nie przeskanowano)."""
    parts = [
        f"Przeskanowano {scanned}/{total} źródeł",
        f"znaleziono {found} duplikatów",
    ]
    if scanned and total and started_on and now:
        elapsed = (now - started_on).total_seconds()
        if elapsed > 0:
            rate = scanned / elapsed
            remaining = max(total - scanned, 0)
            if rate > 0 and remaining:
                eta_seconds = remaining / rate
                finish = now + timezone.timedelta(seconds=eta_seconds)
                parts.append(f"pozostało ~{_fmt_duration(eta_seconds)}")
                parts.append(f"szac. zakończenie {timezone.localtime(finish):%H:%M:%S}")
    return " · ".join(parts)


def seed_queryset():
    """Źródła-seedy skanu: mają publikacje i ministerialne ID.

    Ten sam zakres co dzisiejsze `znajdz_pierwszego_zrodlo_z_duplikatami`
    (base_queryset) — zamierzony, nie regresja. Patrz spec §Ryzyka.
    """
    return (
        Zrodlo.objects.annotate(pub_count=Count("wydawnictwo_ciagle"))
        .filter(pub_count__gt=0, pbn_uid__mniswId__isnull=False)
        .select_related("pbn_uid")
    )


def _pub_count(zrodlo):
    """Liczba publikacji — z anotacji `pub_count` (seed/kandydat) lub zapytania."""
    value = getattr(zrodlo, "pub_count", None)
    if value is None:
        value = zrodlo.wydawnictwo_ciagle_set.count()
    return value


def _mnisw_rank(zrodlo):
    """1 gdy źródło jest „ministerialne" (efektywne MNiSW ID), inaczej 0.

    Używa DOKŁADNIE tej samej reguły co walidacja przemapowania
    (`PrzemapowaZrodloForm._mnisw_id`: mniswId obecne AND status != DELETED),
    żeby orientacja pary nie mogła zaproponować kierunku, który walidacja i
    tak odrzuci."""
    from przemapuj_zrodlo.forms import PrzemapowaZrodloForm

    return 1 if PrzemapowaZrodloForm._mnisw_id(zrodlo) is not None else 0


def _canonical(a, b):
    """(main, duplikat): main = źródło DOCELOWE przemapowania.

    Priorytet kluczy (malejąco):
      1. „ministerialność" (efektywne MNiSW ID) — źródło ministerialne NIE
         może być stroną przepinaną, bo remap źródła z MNiSW ID na cel bez
         tego samego MNiSW ID jest odrzucany. Więc gdy dokładnie jedno źródło
         pary jest ministerialne, ono zostaje `main` (celem).
      2. liczba publikacji (minimalizuje liczbę przenoszonych rekordów),
      3. remis → mniejszy pk zostaje główny.
    """
    a_key = (_mnisw_rank(a), _pub_count(a), -a.pk)
    b_key = (_mnisw_rank(b), _pub_count(b), -b.pk)
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

    p.status(format_progress_status(0, total, 0))

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
            p.status(
                format_progress_status(
                    scanned,
                    total,
                    found,
                    started_on=operation.started_on,
                    now=timezone.now(),
                )
            )

    operation.sources_scanned = scanned
    operation.duplicates_found = found
    operation.save(update_fields=["sources_scanned", "duplicates_found"])

    p.status(format_progress_status(scanned, total, found))
    p.result(context={"duplicates_found": found})
