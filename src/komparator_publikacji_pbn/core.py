"""Przeliczanie komparatora publikacji PBN: wszystkie prace BPP powiązane
z PBN (``pbn_uid``) porównane z lokalną kopią danych PBN, wynik w tabeli
``RoznicaPublikacjiPBN``. Tylko odczyt lokalnej kopii — nic nie idzie do PBN.

Sama logika porównania pól zostaje w ``views.PublicationComparisonView``
(``_compare_publication``); tu decydujemy tylko, skąd i kiedy jest wołana.
"""

from django.db import transaction
from django.db.models import Max, Prefetch
from django.utils import timezone

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

from .models import KomparatorPublikacjiMeta, RoznicaPublikacjiPBN

#: Ile prac czytamy i zapisujemy naraz.
PACZKA = 500

#: Klucze obce pracy czytane przez porównanie pól — dociągane złączeniem,
#: żeby porównanie nie robiło zapytań na pracę.
_RELACJE = ("pbn_uid", "zrodlo", "wydawca", "konferencja", "jezyk", "seria_wydawnicza")

_MODELE = (
    (RoznicaPublikacjiPBN.TYP_CIAGLE, Wydawnictwo_Ciagle),
    (RoznicaPublikacjiPBN.TYP_ZWARTE, Wydawnictwo_Zwarte),
)


def _prace(model):
    """Prace powiązane z PBN z danymi potrzebnymi porównaniu: relacje
    złączeniem, autorzy i słowa kluczowe jednym zapytaniem na paczkę
    (``autorzy_set.count()`` w porównaniu liczy wtedy z pamięci)."""
    pola = {f.name for f in model._meta.get_fields()}
    autorzy = model._meta.get_field("autorzy_set").related_model
    return (
        model.objects.filter(pbn_uid_id__isnull=False)
        .select_related(*[r for r in _RELACJE if r in pola])
        .prefetch_related(
            Prefetch("autorzy_set", queryset=autorzy.objects.only("pk", "rekord_id")),
            "slowa_kluczowe",
        )
        .order_by("pk")
    )


def _paczki(model):
    """Kolejne paczki prac wg rosnącego PK (bez OFFSET)."""
    ostatni_pk = 0
    while True:
        paczka = list(_prace(model).filter(pk__gt=ostatni_pk)[:PACZKA])
        if not paczka:
            return
        yield paczka
        ostatni_pk = paczka[-1].pk


def roznice_pracy(komparator, praca, typ):
    """Różnice jednej pracy we wszystkich polach, z kluczem pola przy każdej
    (porównanie wołane osobno dla każdego pola — stąd wiadomo, którego pola
    dotyczy różnica, bez zgadywania po etykiecie)."""
    from .views import COMPARISON_FIELDS

    roznice = []
    for klucz in COMPARISON_FIELDS:
        wynik = komparator._compare_publication(praca, typ, [klucz])
        for roznica in wynik["differences"]:
            roznice.append({"key": klucz, **roznica})
    return roznice


def _wiersz(przebieg, typ, praca, roznice):
    return RoznicaPublikacjiPBN(
        przebieg=przebieg,
        typ=typ,
        rekord_id=praca.pk,
        pbn_uid_id=praca.pbn_uid_id,
        rok=praca.rok,
        tytul=praca.tytul_oryginalny or "",
        doi=getattr(praca, "doi", None) or "",
        isbn=getattr(praca, "isbn", None) or "",
        pola=list(dict.fromkeys(r["key"] for r in roznice)),
        roznice=roznice,
    )


def przelicz(progress_callback=None):
    """Porównaj wszystkie prace powiązane z PBN i podmień wyniki.

    Nowe wiersze dostają nowy numer przebiegu; widok do końca pokazuje
    poprzedni komplet, a przełączenie na nowy (i skasowanie starego) jest
    jedną transakcją na końcu.

    ``progress_callback(current, total, z_roznicami)`` — po każdej paczce.
    Zwraca ``{"processed", "with_differences"}``.
    """
    from .views import PublicationComparisonView

    meta = KomparatorPublikacjiMeta.get_instance()
    najwyzszy = RoznicaPublikacjiPBN.objects.aggregate(m=Max("przebieg"))["m"] or 0
    przebieg = max(meta.przebieg, najwyzszy) + 1
    # Resztki przerwanych przeliczeń (nie tykamy kompletu pokazywanego teraz).
    RoznicaPublikacjiPBN.objects.exclude(przebieg=meta.przebieg).delete()

    total = sum(
        model.objects.filter(pbn_uid_id__isnull=False).count()
        for _typ, model in _MODELE
    )
    komparator = PublicationComparisonView()
    przetworzone = z_roznicami = 0
    if progress_callback:
        progress_callback(0, total, 0)

    for typ, model in _MODELE:
        for paczka in _paczki(model):
            wiersze = []
            for praca in paczka:
                roznice = roznice_pracy(komparator, praca, typ)
                if roznice:
                    wiersze.append(_wiersz(przebieg, typ, praca, roznice))
            RoznicaPublikacjiPBN.objects.bulk_create(wiersze)
            przetworzone += len(paczka)
            z_roznicami += len(wiersze)
            if progress_callback:
                progress_callback(przetworzone, total, z_roznicami)

    with transaction.atomic():
        meta = KomparatorPublikacjiMeta.objects.select_for_update().get(pk=meta.pk)
        meta.przebieg = przebieg
        meta.status = KomparatorPublikacjiMeta.STATUS_COMPLETED
        meta.ostatnie_uruchomienie = timezone.now()
        meta.liczba_prac = przetworzone
        meta.liczba_z_roznicami = z_roznicami
        meta.ostatni_blad = ""
        meta.save()
        RoznicaPublikacjiPBN.objects.exclude(przebieg=przebieg).delete()

    return {"processed": przetworzone, "with_differences": z_roznicami}
