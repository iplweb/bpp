"""Generator par kandydatów w fazie general — in-memory bucket comparisons."""

import logging

from .analysis_meta import analiza_pary_meta

logger = logging.getLogger(__name__)

BUCKET_MAX_SIZE = 200
MIN_CONFIDENCE_TO_STORE = 50


def generate_pairs(
    buckets: dict[str, list[int]],
    meta: dict[int, dict],
    ignored_pks: set[int],
    notadup_pks: set[int],
    min_confidence: int = MIN_CONFIDENCE_TO_STORE,
):
    """Yield (pk_a, pk_b, score, reasons) gdzie pk_a < pk_b i score >= min_confidence.

    Args:
        buckets: {nazwisko_norm -> [pk1, pk2, ...]} z `build_buckets`.
        meta: {pk -> meta dict} z `build_autor_meta`.
        ignored_pks: PK do pominięcia jako pivot/kandydat (z IgnoredAuthor).
        notadup_pks: PK oznaczone jako NotADuplicate (też pomijane).
        min_confidence: próg score-u poniżej którego para nie jest emitowana.
    """
    seen_pairs: set[tuple[int, int]] = set()
    skipped_buckets = 0
    for bucket_name, pks in buckets.items():
        if len(pks) > BUCKET_MAX_SIZE:
            logger.warning(
                "Skipping oversized bucket '%s' (%d members)",
                bucket_name,
                len(pks),
            )
            skipped_buckets += 1
            continue
        active = [p for p in pks if p not in ignored_pks]
        for i, pk_a in enumerate(active):
            for pk_b in active[i + 1 :]:
                if pk_a == pk_b:
                    continue
                key = (min(pk_a, pk_b), max(pk_a, pk_b))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                if key[0] in notadup_pks or key[1] in notadup_pks:
                    continue
                score, reasons = analiza_pary_meta(meta[key[0]], meta[key[1]])
                if score >= min_confidence:
                    yield key[0], key[1], score, reasons
    if skipped_buckets:
        logger.info("Skipped %d oversized buckets in general phase", skipped_buckets)
