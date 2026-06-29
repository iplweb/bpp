from django.db.models import F

from bpp.models import Punktacja_Zrodla, Wydawnictwo_Ciagle
from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog

DEFAULT_SORT = "-ostatnio_zmieniony"


def get_valid_sort_fields(metryka):
    field = metryka.field_name
    annotated = f"punktacja_zrodla_{field}"
    return [
        "rok",
        "-rok",
        field,
        f"-{field}",
        annotated,
        f"-{annotated}",
        "ostatnio_zmieniony",
        "-ostatnio_zmieniony",
    ]


def get_base_queryset_for_metryka(metryka, pokaz_puste_zrodla=False):
    field = metryka.field_name
    annotated = f"punktacja_zrodla_{field}"
    src = f"zrodlo__punktacja_zrodla__{field}"

    # Warunki roku i pokaz_puste_zrodla muszą być w jednym filter() — to
    # gwarantuje wspólny JOIN i sprawdzenie zera/NULL DLA ROKU PRACY, a nie
    # dla dowolnego roku źródła (osobny exclude() tworzyłby niezależny NOT
    # EXISTS bez warunku roku, łapiąc wiersze z innych lat).
    join_conditions: dict = {"zrodlo__punktacja_zrodla__rok": F("rok")}
    if not pokaz_puste_zrodla:
        if metryka.is_quartile:
            join_conditions[f"{src}__isnull"] = False
        else:
            join_conditions[f"{src}__gt"] = 0

    qs = (
        Wydawnictwo_Ciagle.objects.exclude(zrodlo=None)
        .filter(**join_conditions)
        .exclude(**{src: F(field)})
        .exclude(
            pk__in=IgnorowanaRozbieznosc.objects.filter(
                metryka=metryka.slug
            ).values_list("rekord_id", flat=True)
        )
        .select_related("zrodlo")
        .annotate(**{annotated: F(src)})
    )

    return qs


def apply_filters(queryset, rok_od, rok_do, tytul=""):
    queryset = queryset.filter(rok__gte=rok_od, rok__lte=rok_do)
    if tytul:
        queryset = queryset.filter(tytul_oryginalny__icontains=tytul)
    return queryset


def apply_sorting(queryset, sort, metryka):
    if sort in get_valid_sort_fields(metryka):
        return queryset.order_by(sort)
    return queryset.order_by(DEFAULT_SORT)


def ustaw_ze_zrodla(pks, metryka, user_id=None):
    """Aktualizuje pole metryki z punktacji źródła. Zwraca (updated, errors)."""
    import rollbar

    from bpp.models import BppUser

    field = metryka.field_name
    updated = 0
    errors = 0

    user = None
    if user_id:
        try:
            user = BppUser.objects.get(pk=user_id)
        except BppUser.DoesNotExist:
            user = None

    for pk in pks:
        try:
            wc = Wydawnictwo_Ciagle.objects.get(pk=pk)
        except Wydawnictwo_Ciagle.DoesNotExist:
            errors += 1
            continue

        try:
            punktacja = wc.punktacja_zrodla()
        except Punktacja_Zrodla.DoesNotExist:
            continue

        if punktacja is None:
            continue

        try:
            old_value = getattr(wc, field)
            new_value = getattr(punktacja, field)
            if old_value == new_value:
                continue

            setattr(wc, field, new_value)
            wc.save()
            if metryka.recalculates_disciplines:
                wc.przelicz_punkty_dyscyplin()

            RozbieznoscLog.objects.create(
                metryka=metryka.slug,
                rekord=wc,
                zrodlo=wc.zrodlo,
                wartosc_przed=old_value,
                wartosc_po=new_value,
                user=user,
            )
            updated += 1
        except Exception:
            rollbar.report_exc_info()
            errors += 1

    return updated, errors
