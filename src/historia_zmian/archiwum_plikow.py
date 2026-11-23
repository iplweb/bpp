"""„Wieczne pliki” (FD#587): pliki rekordów nigdy nie giną z systemu.

BPP nie kasuje plików z dysku. Plik może jednak stracić odwołanie w bazie:
wiersz z plikiem zostaje trwale usunięty (np. opróżnienie kosza, usunięcie
załącznika zgłoszenia, kaskada z rekordu nadrzędnego) albo plik w polu
zostaje podmieniony lub wyczyszczony. Bez śladu taki plik leżałby na dysku
jako sierota, której nikt nie znajdzie. Receivery z tego modułu zapisują
wtedy wpis w ``ArchiwalnyPlik`` (admin: „Archiwum plików”) — w tej samej
transakcji co zmiana, więc wycofana zmiana nie zostawia wpisu.

Usunięcie do kosza (soft delete) NIE trafia do archiwum: wiersz zostaje
w bazie i plik da się przywrócić razem z nim.

Granice: archiwum widzi zmiany przez ORM Django (``save()``/``delete()``,
także kaskady). ``QuerySet.update()``/``bulk_update()`` na polu pliku
i surowy SQL go omijają — kod BPP tak nie zmienia tych pól; migracja
danych, która miałaby to robić, musi sama dopisać wpisy do archiwum.
Samego dysku (i bazy) archiwum nie zastępuje — od tego są kopie zapasowe.

Nowy model z plikiem, który ma być chroniony: dopisz go do ``CHRONIONE_PLIKI``.
"""

from django.apps import apps
from django.db import transaction
from django.db.models.signals import post_delete, pre_delete, pre_save

#: model → (pole pliku, pole z oryginalną nazwą pliku albo ``None``)
CHRONIONE_PLIKI = {
    "bpp.Element_Repozytorium": ("plik", "nazwa_pliku"),
    "zglos_publikacje.Zgloszenie_Publikacji": ("plik", "oryginalna_nazwa_pliku"),
    "zglos_publikacje.Zgloszenie_Publikacji_Zalacznik": (
        "plik",
        "oryginalna_nazwa_pliku",
    ),
}


#: Opis zapamiętany w ``pre_delete`` — przy kaskadzie rekord nadrzędny bywa
#: w ``post_delete`` już usunięty, a w ``pre_delete`` jeszcze istnieje.
ATRYBUT_OPISU = "_bpp_opis_do_archiwum"


def _opis(instance):
    """Do czego należał plik — czytelnie, z rekordem nadrzędnym."""
    from bpp.models import Element_Repozytorium

    if isinstance(instance, Element_Repozytorium):
        rekord = instance.rekord  # GenericForeignKey: None, gdy brak rekordu
        opis = f"{instance.rodzaj}: {instance.nazwa_pliku}"
        return f"{opis} — {rekord}" if rekord is not None else opis
    return str(instance)


def _zarchiwizuj(instance, nazwa_pliku, oryginalna_nazwa, powod):
    from bpp.wersjonowanie import uzytkownik_historii

    from .models import ArchiwalnyPlik

    ArchiwalnyPlik.objects.create(
        plik=nazwa_pliku,
        oryginalna_nazwa_pliku=oryginalna_nazwa or "",
        powod=powod,
        rodzaj=str(instance._meta.verbose_name),
        model_zrodlowy=instance._meta.label_lower,
        id_zrodlowe=str(instance.pk),
        opis=getattr(instance, ATRYBUT_OPISU, None) or _opis(instance),
        kto=uzytkownik_historii(),
    )


def _pola(sender):
    return CHRONIONE_PLIKI[sender._meta.label]


def zapamietaj_opis(sender, instance, **kwargs):
    """``pre_delete``: zapamiętaj opis, póki rekord nadrzędny istnieje
    (kolektor wysyła wszystkie ``pre_delete`` przed pierwszym DELETE)."""
    if getattr(instance, _pola(sender)[0]):
        setattr(instance, ATRYBUT_OPISU, _opis(instance))


def archiwizuj_przy_usunieciu(sender, instance, **kwargs):
    """Trwałe usunięcie wiersza z plikiem. ``post_delete``, NIE
    ``pre_delete``: django-soft-delete wysyła ``pre_delete`` także przy
    przenoszeniu do kosza, a wtedy plik zostaje w bazie (w koszu)."""
    pole, pole_nazwy = _pola(sender)
    plik = getattr(instance, pole)
    if not plik:
        return
    from .models import ArchiwalnyPlik

    _zarchiwizuj(
        instance,
        plik.name,
        getattr(instance, pole_nazwy) if pole_nazwy else "",
        ArchiwalnyPlik.Powody.USUNIETO_WIERSZ,
    )


def archiwizuj_przy_podmianie(sender, instance, **kwargs):
    """Plik w polu podmieniony albo wyczyszczony — stary trafia do archiwum.
    Działa też przy zapisie surowym (przywrócenie wersji ze starszym
    plikiem odcina obecny)."""
    if instance.pk is None:
        return
    pole, pole_nazwy = _pola(sender)
    kolumny = [pole] + ([pole_nazwy] if pole_nazwy else [])
    qs = sender._base_manager.filter(pk=instance.pk)
    if transaction.get_connection().in_atomic_block:
        # Blokada wiersza do końca transakcji: dwa równoległe zapisy
        # (A→B i A→C) czytałyby inaczej oba „A” i plik B zostałby bez
        # śladu. Formularze admina zapisują w transakcji, więc tam działa
        # zawsze; poza transakcją (autocommit) FOR UPDATE jest niedozwolone.
        qs = qs.select_for_update()
    stary = qs.values_list(*kolumny).first()
    if stary is None or not stary[0]:
        return
    nowy = getattr(instance, pole)
    if (nowy.name if nowy else "") == stary[0]:
        return
    from .models import ArchiwalnyPlik

    _zarchiwizuj(
        instance,
        stary[0],
        stary[1] if pole_nazwy else "",
        ArchiwalnyPlik.Powody.PODMIENIONO
        if nowy
        else ArchiwalnyPlik.Powody.WYCZYSZCZONO,
    )


def podlacz():
    for etykieta in CHRONIONE_PLIKI:
        model = apps.get_model(etykieta)
        pre_delete.connect(
            zapamietaj_opis,
            sender=model,
            dispatch_uid=f"historia_zmian.archiwum_opis.{etykieta}",
        )
        post_delete.connect(
            archiwizuj_przy_usunieciu,
            sender=model,
            dispatch_uid=f"historia_zmian.archiwum_usuniecie.{etykieta}",
        )
        pre_save.connect(
            archiwizuj_przy_podmianie,
            sender=model,
            dispatch_uid=f"historia_zmian.archiwum_podmiana.{etykieta}",
        )
