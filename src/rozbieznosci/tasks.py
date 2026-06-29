from celery import shared_task


@shared_task(bind=True)
def task_ustaw_ze_zrodla(self, pks, metryka_slug, user_id=None):
    """Aktualizuje metrykę z punktacji źródła. Progres przez update_state."""
    from rozbieznosci.core import ustaw_ze_zrodla
    from rozbieznosci.metryki import METRYKI_BY_SLUG

    metryka = METRYKI_BY_SLUG[metryka_slug]
    total = len(pks)
    updated = 0
    errors = 0

    for idx, pk in enumerate(pks, 1):
        u, e = ustaw_ze_zrodla([pk], metryka, user_id=user_id)
        updated += u
        errors += e
        if idx % 5 == 0 or idx == total:
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": idx,
                    "total": total,
                    "updated": updated,
                    "errors": errors,
                    "progress": int((idx / total) * 100) if total else 100,
                },
            )

    return {"updated": updated, "errors": errors, "total": total}
