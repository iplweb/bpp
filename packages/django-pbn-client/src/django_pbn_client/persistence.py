"""Atomic persistence and sequential download services for PBN objects."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from django.db import IntegrityError, transaction

logger = logging.getLogger(__name__)

Element = TypeVar("Element")
ProgressWrapper = Callable[
    [Iterable[Element], int | None, str],
    Iterable[Element],
]


def _update_changed_fields(instance, values):
    changed = False
    for field_name, value in values.items():
        if getattr(instance, field_name) != value:
            setattr(instance, field_name, value)
            changed = True

    if changed:
        # Deliberately save the complete model: BasePBNMongoDBModel.save()
        # recalculates fields named by pull_up_on_save.
        instance.save()
    return instance


@transaction.atomic
def upsert_pbn_object(element, model_class, client=None, **extra_fields):
    """Create or update one versioned PBN object atomically.

    ``client`` is accepted so this function can be used interchangeably with
    application-specific download callbacks. It is not needed for a generic
    model upsert.
    """
    del client

    values = {
        "status": element["status"],
        "verificationLevel": element["verificationLevel"],
        "verified": element["verified"],
        "versions": element["versions"],
        **extra_fields,
    }
    object_id = element["mongoId"]
    existing = model_class.objects.select_for_update().filter(pk=object_id)

    try:
        instance = existing.get()
    except model_class.DoesNotExist:
        try:
            # The savepoint is essential. If another worker wins the insert
            # race, its IntegrityError must not poison the enclosing atomic
            # block before we read and update the winning row.
            with transaction.atomic():
                return model_class.objects.create(pk=object_id, **values)
        except IntegrityError as create_error:
            try:
                instance = model_class.objects.select_for_update().get(pk=object_id)
            except model_class.DoesNotExist:
                raise create_error

    return _update_changed_fields(instance, values)


def get_total_count(elements) -> int | None:
    """Best-effort total used by download progress integrations."""
    total_elements = getattr(elements, "total_elements", None)
    if total_elements is not None:
        return total_elements

    length = getattr(elements, "__len__", None)
    if length is not None:
        try:
            return len(elements)
        except TypeError:
            logger.debug("Element collection rejected len()", exc_info=True)

    count = getattr(elements, "count", None)
    if count is None:
        return None
    if not callable(count):
        return count

    try:
        return count()
    except Exception:
        # Counting is optional and must not abort a data download. Keep the
        # traceback in standard logging for hosts that need diagnostics.
        logger.debug("Could not determine element count", exc_info=True)
        return None


def download_pbn_objects(
    elements,
    model_class,
    *,
    label="download_pbn_objects",
    save: Callable[..., Any] | None = None,
    client=None,
    progress: ProgressWrapper | None = None,
):
    """Persist every object from an iterable, optionally wrapping progress."""
    if save is None:
        save = upsert_pbn_object

    total = get_total_count(elements)
    iterable = progress(elements, total, label) if progress else elements
    for element in iterable:
        save(element, model_class, client=client)
