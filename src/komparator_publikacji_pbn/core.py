"""Przeliczanie komparatora publikacji PBN: wszystkie prace BPP powiązane
z PBN (``pbn_uid``) porównane z lokalną kopią danych PBN, wynik w tabeli
``RoznicaPublikacjiPBN``. Tylko odczyt lokalnej kopii — nic nie idzie do PBN.

Sama logika porównania pól zostaje w ``views.PublicationComparisonView``
(``_compare_publication``); tu decydujemy tylko, skąd i kiedy jest wołana.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Max, Prefetch
from django.utils import timezone

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

from .models import KomparatorPublikacjiMeta, RoznicaPublikacjiPBN

logger = logging.getLogger(__name__)

#: Ile prac czytamy i zapisujemy naraz.
PACZKA = 500

#: Przeliczenie bez postępu przez tyle minut uznajemy za porzucone (worker
#: zabity, restart serwera). Paczka liczy się w ułamku sekundy, więc to także
#: zapas na czekanie zadania w kolejce.
PORZUCONE_PO_MINUTACH = 5

#: Tyle błędów porównania na przebieg trafia do logu z pełnym tracebackiem
#: (reszta jest tylko liczona — ten sam błąd potrafi dotyczyć tysięcy prac).
LIMIT_TRACEBACKOW = 20


class PrzeliczanieJuzTrwa(Exception):
    """Inne przeliczenie jest w toku i daje znaki życia."""


class PrzeliczaniePrzejete(Exception):
    """Ten przebieg uznano za porzucony i komparator zajął następny."""


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


def roznice_pracy(komparator, praca, typ, bledy=None, z_tracebackiem=True):
    """Różnice jednej pracy we wszystkich polach, z kluczem pola przy każdej
    (porównanie wołane osobno dla każdego pola — stąd wiadomo, którego pola
    dotyczy różnica, bez zgadywania po etykiecie).

    Błąd porównania jednego pola (dane z PBN bywają w nieprzewidzianym
    kształcie: słownik zamiast tekstu, liczba zamiast napisu) NIE przerywa
    przeliczenia tysięcy pozostałych prac: trafia do logu z tracebackiem
    i do listy ``bledy`` jako ``(klucz pola, opis)``. Bez ``bledy`` wyjątek
    leci dalej. ``z_tracebackiem=False`` — tylko policz (wołający pilnuje
    limitu tracebacków w logu i loguje podsumowanie).
    """
    from .views import COMPARISON_FIELDS

    roznice = []
    for klucz in COMPARISON_FIELDS:
        try:
            wynik = komparator._compare_publication(praca, typ, [klucz])
        except Exception as e:
            if bledy is None:
                raise
            if z_tracebackiem:
                logger.exception(
                    "Komparator publikacji PBN: błąd porównania pola %s pracy "
                    "%s pk=%s (PBN UID %s)",
                    klucz,
                    typ,
                    praca.pk,
                    praca.pbn_uid_id,
                )
            bledy.append((klucz, f"{type(e).__name__}: {e}"))
            continue
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


def _kasuj(queryset):
    """Skasuj wiersze wyników jednym ``DELETE``. Zwykłe ``delete()``
    ładowałoby całą tabelę do pamięci (globalny ``post_delete`` easyaudit
    wyłącza szybką ścieżkę). Nic nie wskazuje na tę tabelę kluczem obcym."""
    queryset._raw_delete(queryset.db)


def wyczysc_wyniki():
    """Skasuj wszystkie wyniki i wróć do stanu „nie przeliczano” (reset
    integracji PBN kasuje kopie publikacji, na które wskazują wyniki)."""
    _kasuj(RoznicaPublikacjiPBN.objects.all())
    KomparatorPublikacjiMeta.objects.filter(pk=1).update(
        status=KomparatorPublikacjiMeta.STATUS_IDLE,
        przebieg_w_toku=None,
        ostatnie_uruchomienie=None,
        liczba_prac=0,
        liczba_z_roznicami=0,
        liczba_bledow=0,
        przyklad_bledu="",
        ostatni_blad="",
    )


def przeliczanie_w_toku(meta, teraz=None):
    """Czy trwa przeliczenie, które daje znaki życia (nie porzucone)."""
    if meta.status != KomparatorPublikacjiMeta.STATUS_RUNNING:
        return False
    if meta.ostatni_postep is None:
        return False
    teraz = teraz or timezone.now()
    return meta.ostatni_postep > teraz - timedelta(minutes=PORZUCONE_PO_MINUTACH)


def przeliczanie_porzucone(meta):
    """Status „w trakcie”, ale bez postępu od dawna (np. worker zabity)."""
    return (
        meta.status == KomparatorPublikacjiMeta.STATUS_RUNNING
        and not przeliczanie_w_toku(meta)
    )


def _zacznij_przebieg():
    """Zajmij komparator dla nowego przebiegu (atomowo) i zwróć jego numer.

    ``PrzeliczanieJuzTrwa``, gdy inny przebieg jest właścicielem i daje znaki
    życia — dwa przeliczenia naraz kasowałyby sobie nawzajem wiersze.
    """
    with transaction.atomic():
        KomparatorPublikacjiMeta.get_instance()
        meta = KomparatorPublikacjiMeta.objects.select_for_update().get(pk=1)
        if meta.przebieg_w_toku is not None and przeliczanie_w_toku(meta):
            raise PrzeliczanieJuzTrwa(meta.przebieg_w_toku)
        najwyzszy = RoznicaPublikacjiPBN.objects.aggregate(m=Max("przebieg"))["m"]
        przebieg = max(meta.przebieg, najwyzszy or 0, meta.przebieg_w_toku or 0) + 1
        meta.przebieg_w_toku = przebieg
        meta.status = KomparatorPublikacjiMeta.STATUS_RUNNING
        meta.ostatni_postep = timezone.now()
        meta.rozpoczeto = meta.ostatni_postep
        meta.postep_biezacy = meta.postep_razem = 0
        meta.save(
            update_fields=[
                "przebieg_w_toku",
                "status",
                "ostatni_postep",
                "rozpoczeto",
                "postep_biezacy",
                "postep_razem",
            ]
        )
        # Resztki przerwanych przeliczeń (nie tykamy kompletu pokazywanego
        # teraz). Pod blokadą wiersza meta — nikt inny właśnie nie pisze.
        _kasuj(RoznicaPublikacjiPBN.objects.exclude(przebieg=meta.przebieg))
    return przebieg


def _zapisz_postep(przebieg, biezacy, razem):
    """Znak życia po paczce. ``PrzeliczaniePrzejete``, gdy przebieg nie jest
    już właścicielem (uznany za porzucony, ruszył następny)."""
    zmienione = KomparatorPublikacjiMeta.objects.filter(
        pk=1, przebieg_w_toku=przebieg
    ).update(ostatni_postep=timezone.now(), postep_biezacy=biezacy, postep_razem=razem)
    if not zmienione:
        _kasuj(RoznicaPublikacjiPBN.objects.filter(przebieg=przebieg))
        raise PrzeliczaniePrzejete(przebieg)


def oznacz_blad(przebieg, opis):
    """Przebieg zakończył się wyjątkiem: zwolnij komparator i zapisz błąd
    (tylko jeśli ten przebieg nadal jest właścicielem). Poprzednie wyniki
    zostają."""
    KomparatorPublikacjiMeta.objects.filter(pk=1, przebieg_w_toku=przebieg).update(
        status=KomparatorPublikacjiMeta.STATUS_ERROR,
        ostatni_blad=opis,
        przebieg_w_toku=None,
    )


def przelicz(progress_callback=None):
    """Porównaj wszystkie prace powiązane z PBN i podmień wyniki.

    Nowe wiersze dostają nowy numer przebiegu; widok do końca pokazuje
    poprzedni komplet, a przełączenie na nowy to jedna transakcja na końcu.
    Poprzedni komplet zostaje do następnego przeliczenia (trwające odczyty).
    Naraz działa jedno przeliczenie (``PrzeliczanieJuzTrwa``).

    ``progress_callback(current, total, z_roznicami)`` — po każdej paczce.
    Zwraca ``{"processed", "with_differences", "errors"}``.
    """
    from .views import PublicationComparisonView

    przebieg = _zacznij_przebieg()
    try:
        return _przelicz(przebieg, PublicationComparisonView(), progress_callback)
    except PrzeliczaniePrzejete:
        raise
    except Exception as e:
        oznacz_blad(przebieg, f"{type(e).__name__}: {e}")
        raise


def _porownaj_paczke(przebieg, komparator, typ, paczka, z_tracebackiem):
    """Porównaj paczkę prac i zapisz wiersze wyników. Zwraca ``(liczba
    wierszy, [opis pierwszego błędu każdej pracy, której pola nie dało się
    porównać])``."""
    wiersze, bledy_prac = [], []
    for praca in paczka:
        bledy = []
        roznice = roznice_pracy(
            komparator,
            praca,
            typ,
            bledy,
            z_tracebackiem=z_tracebackiem(len(bledy_prac)),
        )
        if bledy:
            klucz, opis = bledy[0]
            bledy_prac.append(f"{klucz}: {opis}"[:500])
        if roznice:
            wiersze.append(_wiersz(przebieg, typ, praca, roznice))
    RoznicaPublikacjiPBN.objects.bulk_create(wiersze)
    return len(wiersze), bledy_prac


def _opublikuj(przebieg, przetworzone, z_roznicami, bledy_prac):
    """Przełącz widok na wyniki ``przebieg`` — o ile ten przebieg nadal jest
    właścicielem komparatora."""
    with transaction.atomic():
        meta = KomparatorPublikacjiMeta.objects.select_for_update().get(pk=1)
        if meta.przebieg_w_toku != przebieg:
            _kasuj(RoznicaPublikacjiPBN.objects.filter(przebieg=przebieg))
            raise PrzeliczaniePrzejete(przebieg)
        meta.przebieg = przebieg
        meta.przebieg_w_toku = None
        meta.status = KomparatorPublikacjiMeta.STATUS_COMPLETED
        meta.ostatnie_uruchomienie = timezone.now()
        meta.liczba_prac = przetworzone
        meta.liczba_z_roznicami = z_roznicami
        meta.liczba_bledow = len(bledy_prac)
        meta.przyklad_bledu = bledy_prac[0] if bledy_prac else ""
        meta.ostatni_blad = ""
        meta.save(
            update_fields=[
                "przebieg",
                "przebieg_w_toku",
                "status",
                "ostatnie_uruchomienie",
                "liczba_prac",
                "liczba_z_roznicami",
                "liczba_bledow",
                "przyklad_bledu",
                "ostatni_blad",
            ]
        )
        # Poprzedniego kompletu tu NIE kasujemy: żądanie, które przed chwilą
        # odczytało stary numer przebiegu, ma jeszcze z czego czytać (inaczej
        # lista pokazałaby „brak różnic”, a eksport sam nagłówek). Sprząta go
        # początek następnego przeliczenia (``_zacznij_przebieg``).


def _przelicz(przebieg, komparator, progress_callback):
    total = sum(
        model.objects.filter(pbn_uid_id__isnull=False).count()
        for _typ, model in _MODELE
    )
    przetworzone = z_roznicami = 0
    bledy_prac = []
    _zapisz_postep(przebieg, 0, total)
    if progress_callback:
        progress_callback(0, total, 0)

    def z_tracebackiem(w_tej_paczce):
        # Limit tracebacków w logu liczony na cały przebieg.
        return len(bledy_prac) + w_tej_paczce < LIMIT_TRACEBACKOW

    for typ, model in _MODELE:
        for paczka in _paczki(model):
            nowe_wiersze, nowe_bledy = _porownaj_paczke(
                przebieg, komparator, typ, paczka, z_tracebackiem
            )
            przetworzone += len(paczka)
            z_roznicami += nowe_wiersze
            bledy_prac.extend(nowe_bledy)
            _zapisz_postep(przebieg, przetworzone, total)
            if progress_callback:
                progress_callback(przetworzone, total, z_roznicami)

    if bledy_prac:
        logger.warning(
            "Komparator publikacji PBN: %s prac nie dało się porównać w co "
            "najmniej jednym polu (pierwszy błąd: %s)",
            len(bledy_prac),
            bledy_prac[0],
        )

    _opublikuj(przebieg, przetworzone, z_roznicami, bledy_prac)
    return {
        "processed": przetworzone,
        "with_differences": z_roznicami,
        "errors": len(bledy_prac),
    }
