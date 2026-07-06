from decimal import Decimal

from django.db.models import Exists, F, OuterRef, Q, Subquery

from bpp.models import Punktacja_Zrodla, Wydawnictwo_Ciagle
from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog

DEFAULT_SORT = "-ostatnio_zmieniony"

# Tryby filtrowania wg stanu źródła.
#   STANDARD       — tylko rozbieżności, gdzie źródło ma znaczącą wartość,
#   ROWNIEZ_ZEROWE — j.w. + rekordy ze źródłem 0/None/bez wpisu za rok,
#   WYLACZNIE_ZEROWE — wyłącznie rekordy ze źródłem 0/None/bez wpisu za rok.
TRYB_STANDARD = "standard"
TRYB_ROWNIEZ_ZEROWE = "rowniez"
TRYB_WYLACZNIE_ZEROWE = "wylacznie"
TRYBY_ZRODLA = (TRYB_STANDARD, TRYB_ROWNIEZ_ZEROWE, TRYB_WYLACZNIE_ZEROWE)
DEFAULT_TRYB_ZRODLA = TRYB_STANDARD


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


def get_base_queryset_for_metryka(metryka, tryb_zrodla=DEFAULT_TRYB_ZRODLA):
    field = metryka.field_name
    annotated = f"punktacja_zrodla_{field}"

    # Subquery zwraca wartość pola z Punktacja_Zrodla dla roku pracy (rok-zgodna).
    # zrodlo_ma_wpis (Exists) rozróżnia "brak wiersza PS za rok pracy" od "wiersz
    # jest, ale pole NULL" — Subquery zwraca NULL w obu przypadkach.  Anotacja
    # (bez wiodącego "_") jest też czytelna w szablonie do oznaczenia rekordów
    # bez wpisu źródła.
    ps_dla_roku = Punktacja_Zrodla.objects.filter(
        zrodlo=OuterRef("zrodlo"), rok=OuterRef("rok")
    )

    # "Znacząca wartość" zależy od typu metryki:
    #   kwartyl (nullable): wartość ustawiona ⟺ NOT NULL,
    #   IF/MNiSW (non-null, default 0): wartość znacząca ⟺ != 0.
    if metryka.is_quartile:
        praca_ma_wartosc = Q(**{f"{field}__isnull": False})
        zrodlo_ma_wartosc = Q(**{f"{annotated}__isnull": False})
        zrodlo_puste = Q(**{f"{annotated}__isnull": True})
    else:
        praca_ma_wartosc = ~Q(**{field: 0})
        zrodlo_ma_wartosc = ~Q(**{annotated: 0})
        zrodlo_puste = Q(**{annotated: 0})

    # Źródło MA wpis za rok pracy, ale wartości się różnią.
    #   IS DISTINCT FROM semantics: rozbieżność ⟺ dokładnie jedna strona NULL,
    #   ALBO obie non-NULL i różne.  (NULL, NULL) = brak rozbieżności — dlatego
    #   nie używamy samego `Q(annotated__isnull=True)`.
    rozbieznosc_z_wpisem = Q(zrodlo_ma_wpis=True) & (
        (Q(**{f"{annotated}__isnull": True}) & Q(**{f"{field}__isnull": False}))
        | (Q(**{f"{annotated}__isnull": False}) & Q(**{f"{field}__isnull": True}))
        | ~Q(**{annotated: F(field)})  # oba non-NULL: różne wartości
    )
    # Źródło NIE MA wpisu za rok pracy, a praca ma znaczącą wartość.
    brak_wpisu = Q(zrodlo_ma_wpis=False) & praca_ma_wartosc

    # Kategorie rozbieżności:
    #   z_wartoscia  — źródło ma znaczącą wartość, różną od pracy (tryb standardowy),
    #   zerowe       — źródło 0/None (wpis jest) ALBO bez wpisu, a praca ma wartość.
    z_wartoscia = rozbieznosc_z_wpisem & zrodlo_ma_wartosc
    zerowe = (rozbieznosc_z_wpisem & zrodlo_puste) | brak_wpisu

    qs = (
        Wydawnictwo_Ciagle.objects.exclude(zrodlo=None)
        .annotate(**{annotated: Subquery(ps_dla_roku.values(field)[:1])})
        .annotate(zrodlo_ma_wpis=Exists(ps_dla_roku))
        .exclude(
            pk__in=IgnorowanaRozbieznosc.objects.filter(
                metryka=metryka.slug
            ).values_list("rekord_id", flat=True)
        )
        .select_related("zrodlo")
    )

    if tryb_zrodla == TRYB_WYLACZNIE_ZEROWE:
        qs = qs.filter(zerowe)
    elif tryb_zrodla == TRYB_ROWNIEZ_ZEROWE:
        qs = qs.filter(z_wartoscia | zerowe)
    else:  # TRYB_STANDARD
        qs = qs.filter(z_wartoscia)

    return qs


def apply_filters(queryset, rok_od, rok_do, tytul="", charaktery=None):
    queryset = queryset.filter(rok__gte=rok_od, rok__lte=rok_do)
    if tytul:
        queryset = queryset.filter(tytul_oryginalny__icontains=tytul)
    # Pusta lista charakterów = brak zawężenia (pokazuj wszystkie).
    if charaktery:
        queryset = queryset.filter(charakter_formalny__in=charaktery)
    return queryset


def apply_sorting(queryset, sort, metryka):
    if sort in get_valid_sort_fields(metryka):
        return queryset.order_by(sort)
    return queryset.order_by(DEFAULT_SORT)


def _wartosc_do_ustawienia(metryka, punktacja, kasuj_przy_pustym):
    """Zwraca ``(new_value, pomin)`` dla pojedynczego rekordu.

    Gdy źródło nie ma znaczącej wartości (kwartyl ``None`` / IF/MNiSW ``0`` /
    brak wiersza ``Punktacja_Zrodla``): przy ``kasuj_przy_pustym=False`` zwraca
    ``pomin=True`` (nie ruszamy pracy), przy ``True`` — "pustą" wartość do
    wyczyszczenia w pracy (kwartyl → ``None``, IF/MNiSW → ``0``).
    """
    field = metryka.field_name
    # punktacja_zrodla() zwraca None (nie rzuca) gdy brak PS dla roku
    new_value = getattr(punktacja, field) if punktacja is not None else None

    if metryka.is_quartile:
        zrodlo_puste = new_value is None
    else:
        zrodlo_puste = not new_value  # 0 / 0.000 / None

    if zrodlo_puste:
        if not kasuj_przy_pustym:
            return None, True
        new_value = None if metryka.is_quartile else Decimal("0.000")
    return new_value, False


def ustaw_ze_zrodla(pks, metryka, user_id=None, kasuj_przy_pustym=False):
    """Aktualizuje pole metryki z punktacji źródła. Zwraca (updated, errors).

    Gdy źródło nie ma znaczącej wartości za rok pracy (kwartyl ``None`` /
    IF/MNiSW ``0`` / brak wiersza ``Punktacja_Zrodla``):

    * ``kasuj_przy_pustym=False`` (domyślnie) — rekord jest pomijany, NIE
      kasujemy wartości w pracy (bezpieczny domyślny wariant),
    * ``kasuj_przy_pustym=True`` — wartość w pracy jest czyszczona
      (kwartyl → ``None``, IF/MNiSW → ``0``).
    """
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

        new_value, pomin = _wartosc_do_ustawienia(
            metryka, wc.punktacja_zrodla(), kasuj_przy_pustym
        )
        if pomin:
            continue

        try:
            old_value = getattr(wc, field)
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
