"""Grupowe pobieranie odpowiedników z PBN dla zaznaczonych rekordów
(FD#516 — publikacje, FD#519 — autorzy).

Wykonywane w tle przez zadanie Celery; stan i raport trzyma model
``PobieranieOdpowiednikowPBN``. To wyłącznie ODCZYT z PBN: rekordy BPP
dostają identyfikator odpowiednika, do PBN nic nie jest wysyłane.

Zasada: ustawiamy tylko odpowiedniki jednoznaczne. Wszystko, co wymaga
decyzji człowieka, zostaje nietknięte i trafia do raportu z powodem.
"""

import logging
import sys
import traceback
from datetime import timedelta

from django.apps import apps
from django.db import IntegrityError, transaction
from django.utils import timezone
from pbn_client.const import DELETED

from bpp.views.api.pbn_odpowiednik import (
    BLEDY_POLACZENIA,
    BRAK,
    DO_WYBORU,
    PODPOWIEDZ_INNY_CHARAKTER,
    PUSTE,
    SerwerPBN,
    rodzaj_rekordu,
    znajdz_odpowiednik_publikacji,
)
from bpp.wersjonowanie import zmiana_rekordu
from bpp.zglaszanie_bledow import capture_exception
from pbn_api.models import Publication

logger = logging.getLogger(__name__)

#: Najwięcej rekordów w jednym zleceniu. Każdy rekord bez trafienia
#: w lokalnej kopii to 1–4 zapytania do serwera PBN, wykonywane po kolei.
MAKS_REKORDOW = 500

#: Po tylu błędach połączenia z rzędu przestajemy odpytywać serwer PBN —
#: reszta zlecenia korzysta wyłącznie z lokalnej kopii danych.
MAKS_BLEDOW_Z_RZEDU = 5

#: Co ile rekordów zapisywać postęp i dotychczasowy raport.
ZAPIS_POSTEPU_CO = 10

G_USTAWIONO = "ustawiono"
G_DO_WYBORU = "do_wyboru"
G_ZAJETY = "zajety"
G_NIE_ZNALEZIONO = "nie_znaleziono"
G_PUSTE = "puste"
G_BLAD = "blad"
G_MIALY = "mialy"

#: (klucz, emoji, nagłówek w raporcie) — w kolejności wyświetlania.
GRUPY = [
    (G_USTAWIONO, "✅", "Znaleziono i ustawiono odpowiednik"),
    (
        G_DO_WYBORU,
        "👉",
        "Do ręcznego wyboru — kilku kandydatów albo dopasowanie niepewne "
        "(niczego nie ustawiono)",
    ),
    (
        G_ZAJETY,
        "⚠️",
        "Znaleziony odpowiednik jest już przypisany do innego rekordu "
        "(możliwy duplikat; niczego nie ustawiono)",
    ),
    (G_NIE_ZNALEZIONO, "❌", "Nie znaleziono odpowiednika"),
    (G_PUSTE, "✏️", "Brak danych do wyszukania — uzupełnij rekord"),
    (G_BLAD, "🔌", "Błąd połączenia z PBN — spróbuj ponownie"),
    (G_MIALY, "➖", "Pominięto — rekord ma już odpowiednik"),
]

#: Po tylu minutach bez zapisanego postępu zlecenie uznajemy za przerwane
#: (np. restart workera) — można je wtedy ponowić.
PRZERWANE_PO_MINUTACH = 15

#: Czas oczekiwania na serwer PBN w zadaniu w tle (połączenie, odpowiedź)
#: i łączny limit jednego wyszukiwania z dociąganiem szczegółów.
TIMEOUT_PBN_W_TLE = (10, 60)
LIMIT_LACZNY_W_TLE = 120


def _wpis(obj, grupa, opis="", pbn_uid=""):
    return {
        "pk": obj.pk,
        "rekord": str(obj)[:300],
        "grupa": grupa,
        "opis": opis,
        "pbn_uid": pbn_uid or "",
    }


def _modele_z_odpowiednikiem_publikacji():
    from bpp.models.abstract import ModelZPBN_UID

    return [
        model
        for model in apps.get_models()
        if issubclass(model, ModelZPBN_UID) and not model._meta.abstract
    ]


def _kto_ma_odpowiednik(uid, obj):
    """Opis innego rekordu BPP (także z kosza), który ma już ten PBN UID."""
    for model in _modele_z_odpowiednikiem_publikacji():
        qs = model._base_manager.filter(pbn_uid_id=uid)
        if model is type(obj):
            qs = qs.exclude(pk=obj.pk)
        inny = qs.first()
        if inny is not None:
            return f"{model._meta.verbose_name} „{str(inny)[:120]}” (ID {inny.pk})"
    return ""


def _opis_kandydatow(uidy):
    publikacje = Publication.objects.in_bulk(uidy)
    return "; ".join(
        f"{publikacje[uid].title} ({publikacje[uid].year}) [PBN UID {uid}]"
        for uid in uidy
        if uid in publikacje
    )


#: Pola rekordu, na których opiera się dopasowanie. Zmiana któregokolwiek
#: w trakcie zlecenia unieważnia znaleziony odpowiednik.
POLA_DOPASOWANIA = (
    "doi",
    "www",
    "public_www",
    "isbn",
    "e_isbn",
    "tytul_oryginalny",
    "charakter_formalny_id",
    "wydawnictwo_nadrzedne_id",
)


def _dane_dopasowania(obj):
    return tuple(getattr(obj, pole, None) or None for pole in POLA_DOPASOWANIA)


def _ustaw_odpowiednik_publikacji(obj, uid, po_czym, uzytkownik):
    """Zapisz PBN UID z wpisem w historii rekordu. Zwraca wpis raportu.

    Wszystko w jednej transakcji, pod dwiema blokadami:

    * wiersza rekordu PBN — serializuje przypisanie tego samego UID
      (unikalność ``pbn_uid`` działa osobno w każdej tabeli, więc bez tego
      ten sam UID mogłyby równocześnie dostać wydawnictwo ciągłe i zwarte),
    * wiersza rekordu BPP — z ponownym sprawdzeniem, czy nadal nie ma
      odpowiednika i czy pola użyte do dopasowania się nie zmieniły.
    """
    model = type(obj)
    try:
        with transaction.atomic():
            status_pbn = (
                Publication.objects.select_for_update()
                .filter(pk=uid)
                .values_list("status", flat=True)
                .first()
            )
            if status_pbn is None or status_pbn == DELETED:
                return _wpis(
                    obj,
                    G_DO_WYBORU,
                    f"po: {po_czym}; rekord PBN został w międzyczasie usunięty",
                    uid,
                )
            zajety = _kto_ma_odpowiednik(uid, obj)
            if zajety:
                return _wpis(obj, G_ZAJETY, f"po: {po_czym}; ma go już {zajety}", uid)
            swiezy = model.objects.select_for_update().get(pk=obj.pk)
            if swiezy.pbn_uid_id:
                return _wpis(obj, G_MIALY, "odpowiednik ustawiono w międzyczasie")
            if _dane_dopasowania(swiezy) != _dane_dopasowania(obj):
                return _wpis(
                    obj,
                    G_DO_WYBORU,
                    "rekord zmieniono w trakcie wyszukiwania (DOI, adres WWW, "
                    "ISBN, tytuł albo charakter) — niczego nie zapisano; zleć "
                    "wyszukiwanie ponownie",
                    uid,
                )
            with zmiana_rekordu(
                uzytkownik,
                swiezy,
                f"PBN UID ustawiony automatycznie (grupowo) po: {po_czym}",
            ):
                swiezy.pbn_uid_id = uid
                swiezy.save()
    except IntegrityError:
        # Ktoś równolegle przypisał ten sam odpowiednik innemu rekordowi.
        return _wpis(obj, G_ZAJETY, f"po: {po_czym}; przypisany w międzyczasie", uid)
    return _wpis(obj, G_USTAWIONO, f"po: {po_czym}", uid)


def _rodzaj(obj):
    """Rodzaj rekordu BPP w kategoriach PBN (artykuł / książka / rozdział)."""
    charakter = getattr(obj, "charakter_formalny", None)
    return rodzaj_rekordu(
        getattr(charakter, "charakter_ogolny", "") or "",
        bool(getattr(obj, "wydawnictwo_nadrzedne_id", None)),
        model="ciagle" if obj._meta.model_name == "wydawnictwo_ciagle" else None,
    )


def przetworz_publikacje(obj, serwer, uzytkownik):
    """Ustal i (gdy jednoznaczny) ustaw odpowiednik jednej publikacji.
    Zwraca wpis raportu. Błędy połączenia z PBN propaguje."""
    if obj.pbn_uid_id:
        return _wpis(obj, G_MIALY, pbn_uid=obj.pbn_uid_id)
    wynik = znajdz_odpowiednik_publikacji(
        doi=getattr(obj, "doi", ""),
        www=getattr(obj, "www", ""),
        public_www=getattr(obj, "public_www", ""),
        isbn=getattr(obj, "isbn", ""),
        e_isbn=getattr(obj, "e_isbn", ""),
        tytul=obj.tytul_oryginalny,
        rodzaj=_rodzaj(obj),
        klient=serwer,
    )
    if wynik.status == PUSTE:
        return _wpis(obj, G_PUSTE, "brak DOI, adresu WWW i ISBN")
    sprawdzono = "sprawdzono: " + ", ".join(wynik.sprawdzono)
    if wynik.bez_serwera:
        sprawdzono += " — tylko w lokalnej kopii danych z PBN"
    if wynik.status == BRAK:
        return _wpis(obj, G_NIE_ZNALEZIONO, sprawdzono)
    if wynik.status == DO_WYBORU:
        opis = f"po: {wynik.po_czym} — kandydaci: {_opis_kandydatow(wynik.uidy)}"
        if wynik.tylko_brak_rodzaju:
            opis += f". {PODPOWIEDZ_INNY_CHARAKTER}"
        return _wpis(obj, G_DO_WYBORU, opis)
    return _ustaw_odpowiednik_publikacji(obj, wynik.uid, wynik.po_czym, uzytkownik)


def _wykonaj_publikacje(zlecenie, serwer):
    model = zlecenie.content_type.model_class()
    obiekty = model.objects.select_related("charakter_formalny").in_bulk(
        zlecenie.identyfikatory
    )
    # Wznowione zlecenie: rekordy z raportu sprzed przerwania zostają.
    zrobione = {wpis["pk"] for wpis in zlecenie.wyniki}
    bledy_z_rzedu = 0
    for nr, pk in enumerate(zlecenie.identyfikatory, start=1):
        obj = obiekty.get(pk)
        if obj is not None and pk not in zrobione:
            try:
                zlecenie.wyniki.append(
                    przetworz_publikacje(obj, serwer, zlecenie.zlecil)
                )
                bledy_z_rzedu = 0
            except BLEDY_POLACZENIA as e:
                logger.warning("Błąd PBN przy rekordzie %s: %r", pk, e)
                zlecenie.wyniki.append(_wpis(obj, G_BLAD, str(e)[:300]))
                bledy_z_rzedu += 1
                if bledy_z_rzedu >= MAKS_BLEDOW_Z_RZEDU:
                    serwer.wylacz()
        zlecenie.przetworzono = nr
        if nr % ZAPIS_POSTEPU_CO == 0:
            zlecenie.save(update_fields=["przetworzono", "wyniki", "aktywnosc"])


def _wpis_autora(propozycja):
    from pbn_integrator.utils.dopasowanie_autorow import (
        BRAK_DOWODU,
        MOZLIWY_DUPLIKAT,
    )

    autor = propozycja.autor
    opis = "; ".join([*propozycja.zrodla, *propozycja.uwagi])
    if propozycja.zapisano:
        return _wpis(autor, G_USTAWIONO, opis, propozycja.scientist_id)
    if propozycja.poziom == MOZLIWY_DUPLIKAT:
        return _wpis(autor, G_ZAJETY, opis, propozycja.scientist_id)
    if propozycja.poziom == BRAK_DOWODU and not propozycja.uwagi:
        return _wpis(
            autor,
            G_NIE_ZNALEZIONO,
            "sprawdzono: ORCID, imię i nazwisko, publikacje powiązane z PBN",
        )
    return _wpis(
        autor,
        G_DO_WYBORU,
        f"{propozycja.poziom}: {opis}" if opis else propozycja.poziom,
        propozycja.scientist_id,
    )


def _wykonaj_autorow(zlecenie, serwer):
    from bpp.models import Autor
    from pbn_integrator.utils.dopasowanie_autorow import (
        OsobyInstytucji,
        zapisz_propozycje,
        zbadaj_autorow,
    )
    from pbn_integrator.utils.odpowiednik_autora import uzupelnij_kopie_po_orcid

    autorzy = Autor.objects.in_bulk(zlecenie.identyfikatory)
    autorzy = [autorzy[pk] for pk in zlecenie.identyfikatory if pk in autorzy]
    do_zbadania = []
    for autor in autorzy:
        if autor.pbn_uid_id:
            zlecenie.wyniki.append(_wpis(autor, G_MIALY, pbn_uid=autor.pbn_uid_id))
        else:
            do_zbadania.append(autor)

    osoby_instytucji = OsobyInstytucji(zlecenie.uczelnia)
    bledy = {}
    bledy_z_rzedu = 0
    for nr, autor in enumerate(do_zbadania, start=1):
        # ORCID nieznany lokalnie — zapytaj serwer PBN i dociągnij osobę.
        try:
            uzupelnij_kopie_po_orcid(autor, osoby_instytucji, serwer)
            bledy_z_rzedu = 0
        except BLEDY_POLACZENIA as e:
            logger.warning("Błąd PBN przy autorze %s: %r", autor.pk, e)
            bledy[autor.pk] = str(e)[:300]
            bledy_z_rzedu += 1
            if bledy_z_rzedu >= MAKS_BLEDOW_Z_RZEDU:
                serwer.wylacz()
        zlecenie.przetworzono = len(autorzy) - len(do_zbadania) + nr // 2
        if nr % ZAPIS_POSTEPU_CO == 0:
            zlecenie.save(update_fields=["przetworzono", "aktywnosc"])

    propozycje = zbadaj_autorow(
        do_zbadania, uczelnia=zlecenie.uczelnia, osoby_instytucji=osoby_instytucji
    )
    zapisz_propozycje(propozycje, zlecenie.zlecil)
    for propozycja in propozycje:
        wpis = _wpis_autora(propozycja)
        blad = bledy.get(propozycja.autor.pk)
        if blad and wpis["grupa"] == G_NIE_ZNALEZIONO:
            wpis = _wpis(propozycja.autor, G_BLAD, f"szukanie po ORCID: {blad}")
        zlecenie.wyniki.append(wpis)
    zlecenie.przetworzono = len(zlecenie.identyfikatory)


def podsumowanie(zlecenie):
    """Lista ``(klucz, emoji, nagłówek, wpisy)`` niepustych grup raportu."""
    po_grupie = {}
    for wpis in zlecenie.wyniki:
        po_grupie.setdefault(wpis["grupa"], []).append(wpis)
    return [
        (klucz, emoji, naglowek, po_grupie[klucz])
        for klucz, emoji, naglowek in GRUPY
        if klucz in po_grupie
    ]


def _powiadom(zlecenie):
    """Trwały komunikat dla zlecającego — zobaczy go przy następnej stronie.

    Sam tekst, bez znaczników: szablony komunikatów escapują treść."""
    import messages_extends
    from messages_extends.models import Message

    liczby = {klucz: len(wpisy) for klucz, _, _, wpisy in podsumowanie(zlecenie)}
    gdzie = (
        "Raport: moduł redagowania → Wprowadzanie danych → „Pobieranie "
        f"odpowiedników z PBN” (zlecenie nr {zlecenie.pk})."
    )
    if zlecenie.blad:
        tekst = "Pobieranie odpowiedników z PBN zakończyło się błędem."
        poziom = messages_extends.ERROR_PERSISTENT
    else:
        tekst = (
            "Zakończono pobieranie odpowiedników z PBN: ustawiono "
            f"{liczby.get(G_USTAWIONO, 0)} z {zlecenie.liczba_rekordow}."
        )
        poziom = messages_extends.SUCCESS_PERSISTENT
    Message.objects.create(
        user=zlecenie.zlecil, level=poziom, message=f"{tekst} {gdzie}", extra_tags=""
    )


def przejmij(pk):
    """Atomowo oznacz zlecenie jako rozpoczęte. Zwraca zlecenie albo
    ``None``, gdy ktoś inny już je wykonuje/wykonał (zadanie doręczone
    drugi raz)."""
    from pbn_integrator.models import PobieranieOdpowiednikowPBN

    teraz = timezone.now()
    przejete = PobieranieOdpowiednikowPBN.objects.filter(
        pk=pk, rozpoczeto__isnull=True
    ).update(rozpoczeto=teraz, aktywnosc=teraz)
    if not przejete:
        return None
    return PobieranieOdpowiednikowPBN.objects.get(pk=pk)


def ponow(zlecenie):
    """Przywróć PRZERWANE zlecenie do kolejki. Atomowo — dwa kliknięcia
    nie uruchomią go dwa razy. Zwraca ``True``, gdy zlecono ponowienie.

    Dotychczasowy raport zostaje: wznowione zadanie pomija rekordy, które
    już w nim są, i dopisuje pozostałe."""
    from pbn_integrator.models import PobieranieOdpowiednikowPBN
    from pbn_integrator.tasks import pobierz_odpowiedniki_z_pbn

    granica = timezone.now() - timedelta(minutes=PRZERWANE_PO_MINUTACH)
    cofniete = PobieranieOdpowiednikowPBN.objects.filter(
        pk=zlecenie.pk, zakonczono__isnull=True, aktywnosc__lt=granica
    ).update(rozpoczeto=None, aktywnosc=timezone.now())
    if not cofniete:
        return False
    transaction.on_commit(lambda: pobierz_odpowiedniki_z_pbn.delay(zlecenie.pk))
    return True


def wykonaj(zlecenie):
    """Wykonaj PRZEJĘTE zlecenie (``przejmij``). Wołać POZA transakcją
    (postęp ma być widoczny)."""
    from pbn_integrator.models import PobieranieOdpowiednikowPBN

    if zlecenie.rozpoczeto is None:
        zlecenie.rozpoczeto = timezone.now()
    if zlecenie.rodzaj == PobieranieOdpowiednikowPBN.Rodzaj.AUTORZY:
        # Autorzy są oceniani razem (jedna osoba PBN nie może trafić do
        # dwóch autorów), więc ich raport powstaje w całości na końcu —
        # po wznowieniu liczymy go od nowa. Zapisane już odpowiedniki
        # zostają: ci autorzy trafią do „mają już odpowiednik”.
        zlecenie.wyniki = []
    zlecenie.save(update_fields=["rozpoczeto", "wyniki", "aktywnosc"])

    uczelnia = zlecenie.uczelnia
    token = getattr(zlecenie.zlecil, "pbn_token", "")
    serwer = SerwerPBN(
        (lambda: uczelnia.pbn_client(token)) if uczelnia is not None else None,
        timeout=TIMEOUT_PBN_W_TLE,
        limit_laczny=LIMIT_LACZNY_W_TLE,
    )
    try:
        if zlecenie.rodzaj == PobieranieOdpowiednikowPBN.Rodzaj.AUTORZY:
            _wykonaj_autorow(zlecenie, serwer)
        else:
            _wykonaj_publikacje(zlecenie, serwer)
    except Exception:
        # Zlecenie nie może zostać „w toku” na zawsze: zapisujemy błąd
        # w raporcie i zgłaszamy go do monitoringu.
        capture_exception(sys.exc_info())
        zlecenie.blad = traceback.format_exc()[-8000:]
    zlecenie.zakonczono = timezone.now()
    zlecenie.save()
    _powiadom(zlecenie)
    return zlecenie
