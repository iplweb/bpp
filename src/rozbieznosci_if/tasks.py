from celery import shared_task


@shared_task(bind=True)
def task_ustaw_if_ze_zrodla(self, pks, user_id=None):
    """
    Celery task to update impact_factor for publications from their source.

    Reports progress via Celery's update_state mechanism for UI polling.

    Args:
        pks: List of Wydawnictwo_Ciagle primary keys to update.
        user_id: Optional user ID for logging purposes.

    Returns:
        dict with 'updated', 'errors', and 'total' counts.
    """
    from bpp.models import BppUser, Wydawnictwo_Ciagle
    from rozbieznosci_if.models import RozbieznosciIfLog

    total = len(pks)
    updated = 0
    errors = 0

    # Get user object if user_id provided
    user = None
    if user_id:
        try:
            user = BppUser.objects.get(pk=user_id)
        except BppUser.DoesNotExist:
            pass

    for idx, pk in enumerate(pks, 1):
        try:
            wc = Wydawnictwo_Ciagle.objects.get(pk=pk)
            punktacja = wc.punktacja_zrodla()
            if punktacja and wc.impact_factor != punktacja.impact_factor:
                old_if = wc.impact_factor
                wc.impact_factor = punktacja.impact_factor
                wc.save()

                # Log the change
                RozbieznosciIfLog.objects.create(
                    rekord=wc,
                    zrodlo=wc.zrodlo,
                    if_before=old_if,
                    if_after=wc.impact_factor,
                    user=user,
                )

                updated += 1
        except Exception:
            errors += 1

        # Update progress every 5 items or at the end
        if idx % 5 == 0 or idx == total:
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": idx,
                    "total": total,
                    "updated": updated,
                    "errors": errors,
                    "progress": int((idx / total) * 100),
                },
            )

    return {"updated": updated, "errors": errors, "total": total}
