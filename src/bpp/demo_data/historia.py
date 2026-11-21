"""Ślad w historii (admin „Historia") dla obiektów tworzonych przez
``create_demo_data`` i jego sprzątanie w ``cleanup_demo_data``.

Generatory używają ``bulk_create`` (bez ``save()`` i sygnałów), więc same
z siebie nie zostawiają żadnego wpisu ``LogEntry`` ani wersji reversion —
na stronie „Historia" rekordu demo nie było widać, skąd się wziął.
"""

from __future__ import annotations

from django.apps import apps
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType

from bpp.demo_data.manifest import Manifest

#: Modele, dla których zapisujemy wpis „utworzono" — rekordy z własną
#: stroną w adminie (i przyciskiem „Historia"), wraz z relacjami potrzebnymi
#: do ``__str__`` (``object_repr``), żeby nie pytać o nie per rekord.
#:
#: Świadomie pominięte: tabele powiązań autorów prac (``*_Autor``) i
#: streszczenia — edytuje się je w inline'ach publikacji, więc ich historia
#: to historia publikacji; punktacje/poziomy (inline'y źródła i wydawcy);
#: wyniki ewaluacji (liczba N, metryki) — to dane wyliczane, nadpisywane
#: przy każdym przeliczeniu.
MODELE_Z_HISTORIA = (
    ("bpp.Uczelnia", ()),
    ("bpp.Jednostka", ("uczelnia", "wydzial")),
    ("bpp.Autor", ("tytul",)),
    (
        "bpp.Autor_Dyscyplina",
        ("autor__tytul", "dyscyplina_naukowa", "subdyscyplina_naukowa"),
    ),
    ("bpp.Zrodlo", ()),
    ("bpp.Wydawca", ()),
    ("bpp.Wydawnictwo_Ciagle", ()),
    ("bpp.Wydawnictwo_Zwarte", ()),
    ("zglos_publikacje.Zgloszenie_Publikacji", ()),
    # Rzadsze typy rekordów (dodatek ``rzadkie_typy``):
    ("bpp.Praca_Doktorska", ("autor__tytul",)),
    ("bpp.Praca_Habilitacyjna", ("autor__tytul",)),
    ("bpp.Patent", ()),
    ("bpp.Konferencja", ()),
    ("bpp.Seria_Wydawnicza", ()),
    ("bpp.Grant", ()),
)


def komentarz_utworzenia(*, seed, motyw) -> str:
    seed_txt = f"seed={seed}" if seed is not None else "seed losowy"
    return (
        "Utworzono poleceniem create_demo_data "
        f"(dane demonstracyjne, motyw={motyw}, {seed_txt})"
    )


def _pks_z_historia(manifest: Manifest, label: str) -> list[int]:
    # Uczelnię demo logujemy tylko, jeśli generator ją stworzył — istniejącej
    # (prawdziwej) uczelni nie przypisujemy „utworzenia" przez demo.
    if label == "bpp.Uczelnia" and not manifest.extra_for(label).get("created_by_demo"):
        return []
    return manifest.objects_for(label)


def zapisz_historie_utworzenia(
    manifest: Manifest, *, user, komentarz: str, batch_size: int
) -> dict[str, int]:
    """Wpis ``LogEntry`` (ADDITION) dla każdego obiektu demo z
    ``MODELE_Z_HISTORIA``, a dla modeli wersjonowanych (reversion) — także
    wersja „utworzenia".

    ``LogEntry`` powstają hurtowo (``log_actions`` → ``bulk_create``), stała
    liczba zapytań na paczkę ``batch_size``. Wersje zapisujemy PRZED
    ``LogEntry``: strona „Historia" modeli wersjonowanych pokazuje wpisy
    ``LogEntry`` tylko sprzed najstarszej wersji, więc „utworzono" nie
    pojawi się tam dwa razy.

    Zwraca liczbę wpisów ``LogEntry`` na model (do podsumowania).
    """
    import reversion

    from bpp.wersjonowanie import zapisz_wersje_utworzenia

    podsumowanie = {}
    for label, select_related in MODELE_Z_HISTORIA:
        pks = _pks_z_historia(manifest, label)
        if not pks:
            continue
        model = apps.get_model(label)
        for start in range(0, len(pks), batch_size):
            chunk = pks[start : start + batch_size]
            if reversion.is_registered(model):
                zapisz_wersje_utworzenia(
                    model,
                    chunk,
                    user=user,
                    komentarz=komentarz,
                    select_related=select_related,
                )
            obiekty = list(
                model._default_manager.filter(pk__in=chunk)
                .select_related(*select_related)
                .order_by("pk")
            )
            if obiekty:
                LogEntry.objects.log_actions(
                    user.pk, obiekty, ADDITION, change_message=komentarz
                )
            podsumowanie[label] = podsumowanie.get(label, 0) + len(obiekty)
    return podsumowanie


def usun_historie(model, pks: list[int]) -> None:
    """Usuń wpisy ``LogEntry`` i wersje reversion obiektów ``model`` o
    kluczach ``pks`` (wołane po skasowaniu obiektów w cleanupie, żeby nie
    zostawała osierocona historia). Rewizje, które straciły ostatnią wersję,
    też znikają."""
    import reversion
    from reversion.models import Revision, Version

    object_ids = [str(pk) for pk in pks]
    ct = ContentType.objects.get_for_model(model, for_concrete_model=False)
    LogEntry.objects.filter(content_type=ct, object_id__in=object_ids).delete()

    if not reversion.is_registered(model):
        return
    wersje = Version.objects.get_for_model(model).filter(object_id__in=object_ids)
    revision_ids = set(wersje.values_list("revision_id", flat=True))
    if not revision_ids:
        return
    wersje.delete()
    Revision.objects.filter(pk__in=revision_ids, version__isnull=True).delete()
