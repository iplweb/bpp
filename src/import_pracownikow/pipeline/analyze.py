"""Faza analizy (dry-run) importu pracowników.

``analizuj`` iteruje wiersze pliku XLS, matchuje jednostkę i autora istniejącym
API (``import_common.core``), ale **nie tworzy** brakujących słowników
(Funkcja_Autora / Grupa_Pracownicza / Wymiar_Etatu) ani powiązania
``Autor_Jednostka`` — to jest dry-run, więc nic nie jest zapisywane do domeny.
Brakujące dopasowania trafiają do ``row.diff_do_utworzenia`` (FK zostają
``None``), a właściwe utworzenie odbywa się dopiero w fazie integracji
(``import_pracownikow.pipeline.integrate``).
"""

from copy import copy

from django.core.exceptions import ObjectDoesNotExist

from bpp.models import Autor_Jednostka, Wydzial
from import_common.core import (
    matchuj_autora,
    matchuj_funkcja_autora,
    matchuj_grupa_pracownicza,
    matchuj_wymiar_etatu,
)
from import_common.core.autor import znajdz_kandydatow_autora
from import_common.core.jednostka import (
    STATUS_JEDNOSTKA_TWARDY,
    sklasyfikuj_jednostke,
    sklasyfikuj_jednostke_niepelna,
    zaproponuj_skrot,
)
from import_common.core.stanowisko import (
    STATUS_STANOWISKO_BRAK,
    STATUS_STANOWISKO_TWARDY,
    STATUS_STANOWISKO_ZGADYWANIE,
    sklasyfikuj_stanowisko,
    zaproponuj_skrot_stanowiska,
)
from import_common.core.stopien import (
    STATUS_STOPIEN_BRAK,
    STATUS_STOPIEN_TWARDY,
    STATUS_STOPIEN_ZGADYWANIE,
    sklasyfikuj_stopien,
    zaproponuj_skrot_stopnia,
)
from import_common.core.tytul import (
    STATUS_TYTUL_BRAK,
    STATUS_TYTUL_TWARDY,
    STATUS_TYTUL_ZGADYWANIE,
    sklasyfikuj_tytul,
    zaproponuj_skrot_tytulu,
)
from import_common.exceptions import XLSMatchError, XLSParseError
from import_common.normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_nullboleanfield,
    normalize_wymiar_etatu,
)
from import_common.sources import otworz_zrodlo
from import_pracownikow.dedup import kanoniczny_autor
from import_pracownikow.mapping import MIN_POINTS, TRY_NAMES, remapuj_wiersz
from import_pracownikow.models import (
    AutorForm,
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
    ImportPracownikowStanowisko,
    ImportPracownikowStopien,
    ImportPracownikowTytul,
)
from import_pracownikow.okresy import rozwiaz_okres_zatrudnienia
from import_pracownikow.parsers.jednostka_zlozona import parsuj_komorke
from import_pracownikow.parsers.leksykony import zbuduj_parser_kontekst
from import_pracownikow.parsers.osoba import rozbij_osobe
from import_pracownikow.parsers.wartosci import (
    normalizuj_wartosci_wiersza,
    oczysc_email,
    rozbij_nazwisko_imie,
    scal_wymiar_etatu,
    sklej_drugie_imie,
)
from import_pracownikow.pewnosc import (
    STATUS_DEDUP,
    STATUS_TWARDY,
    STATUS_WIELU,
    oblicz_status_pewnosci,
    wybierz_autora_z_kandydatow,
)


def _matchuj_slownik_lub_odroc(matcher, wartosc, normalizer, diff, klucz):
    """Zwraca dopasowany obiekt albo ``None``.

    Gdy słownik nie istnieje w bazie, NIE tworzy go (dry-run) — zapisuje
    znormalizowaną wartość do ``diff`` pod ``klucz``, żeby faza integracji
    wiedziała co utworzyć.
    """
    if not wartosc:
        return None
    try:
        return matcher(wartosc)
    except ObjectDoesNotExist:
        diff[klucz] = normalizer(wartosc)
        return None


class _ReconcilerJednostek:
    """Utrzymuje decyzje ``ImportPracownikowJednostka`` przez (re)analizę.

    ``reconciluj`` robi get_or_create po nazwie **case-insensitive** (dedup
    wariantów wielkości liter), przy każdym runie ODŚWIEŻA pola liczone przez
    analizę (``tryb``/``auto_jednostka``/``auto_similarity``/``skrot_sugerowany``),
    a ZACHOWUJE wybory użytkownika (``decyzja``/``wybrany_parent``/
    ``wybrana_jednostka``). ``usun_stale`` kasuje decyzje tego importu, których
    nie dotknięto w bieżącym runie (nazwa zniknęła z pliku) — inaczej wisiałyby
    w podsumowaniu na zawsze."""

    def __init__(self, parent):
        self.parent = parent
        self.dotkniete = set()

    def reconciluj(
        self,
        nazwa_zrodlowa,
        tryb,
        auto_jednostka,
        auto_similarity,
        skrot_hint=None,
    ):
        nazwa_zrodlowa = nazwa_zrodlowa[:512]
        dec = self.parent.jednostki_do_decyzji.filter(
            nazwa_zrodlowa__iexact=nazwa_zrodlowa
        ).first()
        skrot = (skrot_hint or "").strip()[:128]
        if dec is None:
            dec = ImportPracownikowJednostka.objects.create(
                parent=self.parent,
                nazwa_zrodlowa=nazwa_zrodlowa,
                tryb=tryb,
                auto_jednostka=auto_jednostka,
                auto_similarity=auto_similarity,
                skrot_sugerowany=skrot or zaproponuj_skrot(nazwa_zrodlowa),
            )
        else:
            dec.tryb = tryb
            dec.auto_jednostka = auto_jednostka
            dec.auto_similarity = auto_similarity
            # skrot_hint (z komórki) nadpisuje ZAWSZE; bez hintu — dawne
            # zachowanie (uzupełnij tylko gdy puste).
            if skrot:
                dec.skrot_sugerowany = skrot
            elif not dec.skrot_sugerowany:
                dec.skrot_sugerowany = zaproponuj_skrot(nazwa_zrodlowa)
            dec.save(
                update_fields=[
                    "tryb",
                    "auto_jednostka",
                    "auto_similarity",
                    "skrot_sugerowany",
                ]
            )
        self.dotkniete.add(dec.pk)
        return dec

    def usun_stale(self):
        self.parent.jednostki_do_decyzji.exclude(pk__in=self.dotkniete).delete()


# Status klasyfikacji tytułu (``import_common.core.tytul``) → tryb decyzji
# (``ImportPracownikowTytul``). Wartości są dziś identyczne, ale mapujemy jawnie,
# żeby ewentualny rozjazd słownictwa nie przeciekł do bazy po cichu.
_STATUS_NA_TRYB_TYTUL = {
    STATUS_TYTUL_ZGADYWANIE: ImportPracownikowTytul.TRYB_ZGADYWANIE,
    STATUS_TYTUL_BRAK: ImportPracownikowTytul.TRYB_BRAK,
}


class _ReconcilerTytulow:
    """Utrzymuje decyzje ``ImportPracownikowTytul`` przez (re)analizę.

    Mirror ``_ReconcilerJednostek`` (uproszczony — tytuł nie ma drzewa ani
    wydziału). ``reconciluj`` robi get_or_create po nazwie **case-insensitive**
    (dedup wariantów wielkości liter / kropek na poziomie SQL ``iexact``), przy
    każdym runie ODŚWIEŻA pola liczone przez analizę (``tryb``/``auto_tytul``/
    ``auto_similarity``), a ZACHOWUJE wybory użytkownika (``decyzja``/
    ``wybrany_tytul``/``nazwa_do_utworzenia``/``skrot_do_utworzenia``).
    ``usun_stale`` kasuje decyzje tego importu, których nie dotknięto w bieżącym
    runie (string tytułu zniknął z pliku) — inaczej wisiałyby w podsumowaniu na
    zawsze."""

    def __init__(self, parent):
        self.parent = parent
        self.dotkniete = set()

    def reconciluj(self, nazwa_zrodlowa, tryb, auto_tytul, sim):
        nazwa_zrodlowa = nazwa_zrodlowa[:512]
        tryb_model = _STATUS_NA_TRYB_TYTUL[tryb]
        dec = self.parent.tytuly_do_decyzji.filter(
            nazwa_zrodlowa__iexact=nazwa_zrodlowa
        ).first()
        if dec is None:
            dec = ImportPracownikowTytul.objects.create(
                parent=self.parent,
                nazwa_zrodlowa=nazwa_zrodlowa,
                tryb=tryb_model,
                auto_tytul=auto_tytul,
                auto_similarity=sim,
                nazwa_do_utworzenia=nazwa_zrodlowa[:512],
                skrot_do_utworzenia=zaproponuj_skrot_tytulu(nazwa_zrodlowa),
            )
        else:
            # Tylko pola LICZONE — wybory usera (``decyzja``/``wybrany_tytul``/
            # ``nazwa_do_utworzenia``/``skrot_do_utworzenia``) zostają nietknięte.
            dec.tryb = tryb_model
            dec.auto_tytul = auto_tytul
            dec.auto_similarity = sim
            dec.save(update_fields=["tryb", "auto_tytul", "auto_similarity"])
        self.dotkniete.add(dec.pk)
        return dec

    def usun_stale(self):
        self.parent.tytuly_do_decyzji.exclude(pk__in=self.dotkniete).delete()


_STATUS_NA_TRYB_STOPIEN = {
    STATUS_STOPIEN_ZGADYWANIE: ImportPracownikowStopien.TRYB_ZGADYWANIE,
    STATUS_STOPIEN_BRAK: ImportPracownikowStopien.TRYB_BRAK,
}
_STATUS_NA_TRYB_STANOWISKO = {
    STATUS_STANOWISKO_ZGADYWANIE: ImportPracownikowStanowisko.TRYB_ZGADYWANIE,
    STATUS_STANOWISKO_BRAK: ImportPracownikowStanowisko.TRYB_BRAK,
}


class _ReconcilerStopni:
    """Mirror ``_ReconcilerTytulow`` dla ``ImportPracownikowStopien``."""

    def __init__(self, parent):
        self.parent = parent
        self.dotkniete = set()

    def reconciluj(self, nazwa_zrodlowa, tryb, auto_stopien, sim):
        nazwa_zrodlowa = nazwa_zrodlowa[:512]
        tryb_model = _STATUS_NA_TRYB_STOPIEN[tryb]
        dec = self.parent.stopnie_do_decyzji.filter(
            nazwa_zrodlowa__iexact=nazwa_zrodlowa
        ).first()
        if dec is None:
            dec = ImportPracownikowStopien.objects.create(
                parent=self.parent,
                nazwa_zrodlowa=nazwa_zrodlowa,
                tryb=tryb_model,
                auto_stopien=auto_stopien,
                auto_similarity=sim,
                nazwa_do_utworzenia=nazwa_zrodlowa[:512],
                skrot_do_utworzenia=zaproponuj_skrot_stopnia(nazwa_zrodlowa),
            )
        else:
            dec.tryb = tryb_model
            dec.auto_stopien = auto_stopien
            dec.auto_similarity = sim
            dec.save(update_fields=["tryb", "auto_stopien", "auto_similarity"])
        self.dotkniete.add(dec.pk)
        return dec

    def usun_stale(self):
        self.parent.stopnie_do_decyzji.exclude(pk__in=self.dotkniete).delete()


class _ReconcilerStanowisk:
    """Mirror ``_ReconcilerStopni`` dla ``ImportPracownikowStanowisko``."""

    def __init__(self, parent):
        self.parent = parent
        self.dotkniete = set()

    def reconciluj(self, nazwa_zrodlowa, tryb, auto_stanowisko, sim):
        nazwa_zrodlowa = nazwa_zrodlowa[:512]
        tryb_model = _STATUS_NA_TRYB_STANOWISKO[tryb]
        dec = self.parent.stanowiska_do_decyzji.filter(
            nazwa_zrodlowa__iexact=nazwa_zrodlowa
        ).first()
        if dec is None:
            dec = ImportPracownikowStanowisko.objects.create(
                parent=self.parent,
                nazwa_zrodlowa=nazwa_zrodlowa,
                tryb=tryb_model,
                auto_stanowisko=auto_stanowisko,
                auto_similarity=sim,
                nazwa_do_utworzenia=nazwa_zrodlowa[:512],
                skrot_do_utworzenia=zaproponuj_skrot_stanowiska(nazwa_zrodlowa),
            )
        else:
            dec.tryb = tryb_model
            dec.auto_stanowisko = auto_stanowisko
            dec.auto_similarity = sim
            dec.save(update_fields=["tryb", "auto_stanowisko", "auto_similarity"])
        self.dotkniete.add(dec.pk)
        return dec

    def usun_stale(self):
        self.parent.stanowiska_do_decyzji.exclude(pk__in=self.dotkniete).delete()


def _klasyfikuj_tytul_wiersza(parent, tytul_str, reconciler_tytulow):
    """Klasyfikuje tytuł wiersza — mirror ``sklasyfikuj_jednostke``-flow.

    Zwraca ``(tytul|None, status|None, decyzja|None)``:

    - pusty ``tytul_str`` → ``(None, None, None)`` (bez decyzji, bez statusu —
      nie liczony na kafelku);
    - ``twardy`` → ``(tytul, "twardy", None)`` (na wiersz wprost, bez decyzji);
    - ``zgadywanie`` lub (``brak`` + ``tworz_brakujace_tytuly``) → decyzja
      ``ImportPracownikowTytul`` (dedup po nazwie), tytuł odroczony (None) do
      integracji — ``(None, status, decyzja)``;
    - ``brak`` przy wyłączonym tworzeniu → ``(None, "brak", None)``.
    """
    if not tytul_str:
        return None, None, None
    tytul_obj, tyt_status, tyt_sim = sklasyfikuj_tytul(tytul_str)
    if tyt_status == STATUS_TYTUL_TWARDY:
        return tytul_obj, tyt_status, None
    tworzy_decyzje = tyt_status == STATUS_TYTUL_ZGADYWANIE or (
        tyt_status == STATUS_TYTUL_BRAK and parent.tworz_brakujace_tytuly
    )
    if tworzy_decyzje:
        decyzja = None
        if reconciler_tytulow is not None:
            decyzja = reconciler_tytulow.reconciluj(
                tytul_str, tyt_status, tytul_obj, tyt_sim
            )
        return None, tyt_status, decyzja
    return None, STATUS_TYTUL_BRAK, None


def _klasyfikuj_stopien_wiersza(parent, stopien_str, reconciler_stopni):
    """Mirror ``_klasyfikuj_tytul_wiersza`` dla stopni służbowych. Gated
    ``parent.tworz_brakujace_stopnie``. Zwraca ``(stopien|None, status|None,
    decyzja|None)``."""
    if not stopien_str:
        return None, None, None
    obj, status, sim = sklasyfikuj_stopien(stopien_str)
    if status == STATUS_STOPIEN_TWARDY:
        return obj, status, None
    tworzy = status == STATUS_STOPIEN_ZGADYWANIE or (
        status == STATUS_STOPIEN_BRAK and parent.tworz_brakujace_stopnie
    )
    if tworzy:
        decyzja = None
        if reconciler_stopni is not None:
            decyzja = reconciler_stopni.reconciluj(stopien_str, status, obj, sim)
        return None, status, decyzja
    return None, STATUS_STOPIEN_BRAK, None


def _klasyfikuj_stanowisko_wiersza(parent, stanowisko_str, reconciler_stanowisk):
    """Mirror ``_klasyfikuj_stopien_wiersza`` dla stanowisk dydaktycznych.
    Gated ``parent.tworz_brakujace_stanowiska``."""
    if not stanowisko_str:
        return None, None, None
    obj, status, sim = sklasyfikuj_stanowisko(stanowisko_str)
    if status == STATUS_STANOWISKO_TWARDY:
        return obj, status, None
    tworzy = status == STATUS_STANOWISKO_ZGADYWANIE or (
        status == STATUS_STANOWISKO_BRAK and parent.tworz_brakujace_stanowiska
    )
    if tworzy:
        decyzja = None
        if reconciler_stanowisk is not None:
            decyzja = reconciler_stanowisk.reconciluj(stanowisko_str, status, obj, sim)
        return None, status, decyzja
    return None, STATUS_STANOWISKO_BRAK, None


def _lagodna_walidacja_wiersza(dane_form):
    """Łagodna walidacja pól wiersza PRZED ``AutorForm.full_clean`` (§11) — dziś
    e-mail. Mutuje ``dane_form`` in-place (czyści niepoprawne wartości) i zwraca
    listę ostrzeżeń do zapisania w ``dane_znormalizowane["ostrzeżenia"]``.
    Wyodrębnione z ``_przetworz_wiersz`` (utrzymuje jego złożoność w ryzach)."""
    ostrzezenia = []
    ostrz_email = oczysc_email(dane_form)
    if ostrz_email:
        ostrzezenia.append(ostrz_email)
    return ostrzezenia


def _waliduj_dlugosci_pol(elem, dane_form):
    """Czytelny (PL) błąd PRZED ``AutorForm.is_valid`` gdy któraś wartość
    przekracza ``max_length`` pola formularza — zamiast surowego angielskiego
    komunikatu Django („Ensure this value has at most 200 characters"). Limity
    czytane wprost z ``AutorForm`` (jedno źródło prawdy), etykiety z
    ``POLA_DOCELOWE``. Fail-fast (odrzucamy plik — spójne z resztą walidacji
    analizy); ``elem`` niesie kontekst arkusza/wiersza do komunikatu. Inne błędy
    walidacji (nie-długościowe) lecą dalej normalnie przez ``AutorForm``."""
    from import_pracownikow.mapping import POLA_DOCELOWE

    etykiety = dict(POLA_DOCELOWE)
    for nazwa, pole in AutorForm.base_fields.items():
        limit = getattr(pole, "max_length", None)
        if not limit:
            continue
        wartosc = dane_form.get(nazwa)
        if wartosc in (None, ""):
            continue
        dlugosc = len(str(wartosc))
        if dlugosc > limit:
            raise XLSMatchError(
                elem,
                etykiety.get(nazwa, nazwa),
                f"wartość ma {dlugosc} znaków, przekracza maksimum {limit} "
                f"znaków — skróć wartość w pliku XLS",
            )


def _dane_znormalizowane_z_parserem(cleaned_data, rozbicie, ostrzezenia=None):
    """Kopia cleaned_data wzbogacona o pewność rozbicia parsera (§7): confidence
    rozbicia (high/medium/low) i alternatywy trzymamy WEWNĄTRZ JSON, nie w
    kolumnie ``confidence`` (ta jest statusem dopasowania AUTORA — §8).
    ``ostrzeżenia`` (np. o odrzuconym e-mailu) dokładamy pod własnym kluczem —
    tam czyta je audyt i porównywarka."""
    dane = copy(cleaned_data)
    if rozbicie is not None:
        dane["parser_confidence"] = rozbicie.confidence
        dane["parser_alternatywy"] = rozbicie.alternatywy
    if ostrzezenia:
        dane["ostrzeżenia"] = ostrzezenia
    return dane


def _rozbij_osoba_sklejona(dane_form, parser_ctx):
    """Gdy jest ``parser_ctx`` i wiersz ma ``osoba_sklejona``, rozbija ją
    parserem (§7) i zasila brakujące imię/nazwisko/tytuł w ``dane_form``
    in-place. Zwraca wynik rozbicia (do zapisania confidence/alternatywy w
    ``dane_znormalizowane``) albo ``None``, gdy rozbicie nie zaszło."""
    if parser_ctx is None or not dane_form.get("osoba_sklejona"):
        return None
    rozbicie = rozbij_osobe(
        str(dane_form["osoba_sklejona"]),
        tytuly=parser_ctx.tytuly,
        imiona_znane=parser_ctx.imiona_znane,
        probuj_match=parser_ctx.probuj_match,
    )
    if not dane_form.get("nazwisko"):
        dane_form["nazwisko"] = rozbicie.nazwisko
    if not dane_form.get("imię"):
        dane_form["imię"] = rozbicie.imiona
    if rozbicie.tytul and not dane_form.get("tytuł_stopień"):
        dane_form["tytuł_stopień"] = rozbicie.tytul
    return rozbicie


def _dopasuj_autora_i_status(data, jednostka, tytul_str):
    """Zwraca (autor, status, kandydaci). ID-path (priorytet) dopasowuje
    WYŁĄCZNIE po identyfikatorach: ``imiona/nazwisko/jednostka/tytul_str`` są
    PRZEKAZANE JAKO None, żeby ``matchuj_autora`` nie odpalił swoich fallbacków
    nazwiskowych/jednostkowych (autor.py:577-600). Inaczej remis top-tier byłby
    rozstrzygnięty jednostką/tytułem i błędnie oznaczony jako ``twardy`` —
    łamiąc §8 (jednostka/tytuł to tylko tie-breakery preselekcji, nie status).
    Gdy ID nie rozstrzyga (None) — SPADAMY do ścieżki kandydatów. Poza ID —
    status WPROST z ``znajdz_kandydatow_autora``; ``autor`` tylko dla
    twardy/zgadywanie (przez wspólny ``wybierz_autora_z_kandydatow``)."""
    ma_id = any(
        data.get(k) not in (None, "")
        for k in ("bpp_id", "orcid", "pbn_uuid", "numer", "pbn_id")
    )
    if ma_id:
        autor_po_id = matchuj_autora(
            imiona=None,
            nazwisko=None,
            jednostka=None,
            bpp_id=data.get("bpp_id"),
            pbn_uid_id=data.get("pbn_uuid"),
            system_kadrowy_id=data.get("numer"),
            pbn_id=data.get("pbn_id"),
            orcid=data.get("orcid"),
            tytul_str=None,
        )
        if autor_po_id is not None:
            return autor_po_id, STATUS_TWARDY, []

    kandydaci = znajdz_kandydatow_autora(data.get("imię"), data.get("nazwisko"))
    status = oblicz_status_pewnosci(kandydaci, match_po_id=False)
    autor = wybierz_autora_z_kandydatow(kandydaci, status)
    # Poz. 7: gdy auto-dopasowano do rekordu-DUPLIKATU, przekieruj zatrudnienie
    # na rekord ORYGINALNY (z API instytucjonalnego PBN) — bez scalania. Tylko
    # dla ścieżki nazwiskowej z auto-wybranym autorem (twardy/zgadywanie);
    # ID-path (wyżej) to świadomy wskaźnik operatora, nie ruszamy. STATUS_WIELU/
    # BRAK mają autor=None → decyzję podejmuje operator, też nie przekierowujemy.
    if autor is not None:
        oryginal = kanoniczny_autor(autor)
        if oryginal.pk != autor.pk:
            autor = oryginal
            status = STATUS_DEDUP
    return autor, status, kandydaci


def _wybierz_autor_jednostka(autor, jednostka):
    """Wybiera ``Autor_Jednostka`` (autor, jednostka) do aktualizacji w commicie.

    Multi-etat / historia zatrudnienia: autor może mieć >1 AJ w TEJ SAMEJ
    jednostce (``unique_together`` to ``(autor, jednostka, rozpoczal_prace)``).
    Ten AJ jest w commicie aktualizowany (daty/funkcja/etat/podstawowe), więc
    ``.first()`` bez porządku (losowy wybór) mógł trafić w HISTORYCZNY rekord i
    nadpisać zamknięte zatrudnienie — korupcja (#508 F6). Deterministycznie
    preferujemy AKTYWNY etat (bez ``zakonczyl_prace``), najnowszy startem; w
    ostateczności najnowszy AJ. Zwraca ``None``, gdy autor nie ma AJ w jednostce.

    Deleguje do ``okresy._wybierz_aktywny_najswiezszy`` (gałąź „pusty plik_od"
    resolvera §7) na JEDNEJ pobranej liście — jedno źródło reguły wyboru.
    """
    from import_pracownikow.okresy import _wybierz_aktywny_najswiezszy

    return _wybierz_aktywny_najswiezszy(
        list(Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka))
    )


def _zrodlo_jednostki_wiersza(dane_form):
    """Rozstrzyga, skąd wziąć nazwę jednostki i jak ją sklasyfikować (spec §6/§7).

    Zwraca ``(nazwa_do_klas, wydzial, jednostka, jed_status, jed_sim,
    skrot_hint)``. Trzy tory (priorytet):

    1. ``komórka_złożona`` → ``parsuj_komorke``: nazwa = czysta nazwa z parsera,
       ``skrot_hint`` = skrót z pliku (zasili ``Jednostka.skrot`` przy tworzeniu),
       oddział rozwiązany przez ``Wydzial.skrot`` → jego NAZWA jako wydzial-hint
       (``matchuj_wydzial`` robi tylko ``nazwa__iexact``; §7 finding #6).
       Klasyfikacja zwykłym ``sklasyfikuj_jednostke`` po skrócie/nazwie.
    2. ``nazwa_jednostki_niepelna`` (i brak ``nazwa_jednostki``) →
       ``sklasyfikuj_jednostke_niepelna`` (icontains/trigram, zawsze do
       weryfikacji). ``skrot_hint`` = None.
    3. zwykła ``nazwa_jednostki`` → dotychczasowy ``sklasyfikuj_jednostke``.

    Pusta/za długa (>512) nazwa → traktowana jak brak (wiersz pominięty).
    """
    wydzial = str(dane_form.get("wydział") or "").strip() or None
    skrot_hint = None

    komorka = str(dane_form.get("komórka_złożona") or "").strip()
    niepelna = str(dane_form.get("nazwa_jednostki_niepelna") or "").strip()
    zwykla = str(dane_form.get("nazwa_jednostki") or "").strip()

    if komorka:
        wynik = parsuj_komorke(komorka)
        nazwa = wynik["nazwa"]
        skrot_hint = wynik["skrot"]
        oddzial = wynik["oddzial"]
        if oddzial:
            w = Wydzial.objects.filter(skrot=oddzial).first()
            if w is not None:
                wydzial = w.nazwa
        nazwa_do_klas = nazwa if 0 < len(nazwa) <= 512 else ""
        jednostka, jed_status, jed_sim = sklasyfikuj_jednostke(nazwa_do_klas, wydzial)
        return nazwa_do_klas, wydzial, jednostka, jed_status, jed_sim, skrot_hint

    if niepelna and not zwykla:
        nazwa_do_klas = niepelna if 0 < len(niepelna) <= 512 else ""
        jednostka, jed_status, jed_sim = sklasyfikuj_jednostke_niepelna(
            nazwa_do_klas, wydzial
        )
        return nazwa_do_klas, wydzial, jednostka, jed_status, jed_sim, None

    nazwa_do_klas = zwykla if 0 < len(zwykla) <= 512 else ""
    jednostka, jed_status, jed_sim = sklasyfikuj_jednostke(nazwa_do_klas, wydzial)
    return nazwa_do_klas, wydzial, jednostka, jed_status, jed_sim, None


def _przetworz_wiersz(
    parent,
    elem,
    parser_ctx=None,
    *,
    reconciler=None,
    reconciler_tytulow=None,
    reconciler_stopni=None,
    reconciler_stanowisk=None,
    tworz_brakujace=True,
):
    dane_form = normalizuj_wartosci_wiersza(elem)
    # Dwie kolumny „Wymiar etatu" (tekst + ułamek) → jeden kanoniczny string
    # pod „wymiar_etatu" PRZED AutorForm; rozbieżność → XLSMatchError (§4).
    scal_wymiar_etatu(dane_form)
    # E-mail: łagodna walidacja PRZED AutorForm.full_clean (§11) — zły adres nie
    # może unieważnić formularza (analiza fail-fast: jeden XLSParseError ubija
    # cały run). Ostrzeżenie trafia do dane_znormalizowane["ostrzeżenia"].
    ostrzezenia = _lagodna_walidacja_wiersza(dane_form)
    rozbicie = _rozbij_osoba_sklejona(dane_form, parser_ctx)
    # „Nazwisko Imię" (nazwisko-first) → nazwisko/imię (no-op gdy brak klucza).
    rozbij_nazwisko_imie(dane_form)
    # Kolumna „Drugie imię" scalana z „Imię" w jedno Autor.imiona — PO rozbiciu
    # osoby sklejonej (parser uzupełnia puste „imię" z rozbicia), przed AutorForm.
    sklej_drugie_imie(dane_form)

    # Jednostka: klasyfikacja BEZ rzucania (brak/remis/pusta/za długa nazwa NIE
    # wywalają analizy). twardy → dopasowana wprost; zgadywanie/brak → odroczona
    # do decyzji (ekran weryfikacji + faza integracji). Rozgałęzienie źródła
    # (komórka złożona / niepełna nazwa / zwykła nazwa) w _zrodlo_jednostki_wiersza.
    (
        nazwa_do_klas,
        wydzial,
        jednostka,
        jed_status,
        jed_sim,
        skrot_hint,
    ) = _zrodlo_jednostki_wiersza(dane_form)
    jednostka_odroczona = jed_status != STATUS_JEDNOSTKA_TWARDY

    # Czytelny (PL) błąd długości przed AutorForm — zamiast surowego angielskiego
    # max_length Django. Operator dostaje arkusz/wiersz/pole/limit.
    _waliduj_dlugosci_pol(elem, dane_form)

    autor_form = AutorForm(data=dane_form)
    autor_form.full_clean()
    if not autor_form.is_valid():
        raise XLSParseError(elem, autor_form, "weryfikacja danych autora")
    data = autor_form.cleaned_data
    tytul_str = data.get("tytuł_stopień")

    diff = {}
    funkcja = _matchuj_slownik_lub_odroc(
        matchuj_funkcja_autora,
        data.get("stanowisko"),
        normalize_funkcja_autora,
        diff,
        "funkcja_autora",
    )
    grupa = _matchuj_slownik_lub_odroc(
        matchuj_grupa_pracownicza,
        data.get("grupa_pracownicza"),
        normalize_grupa_pracownicza,
        diff,
        "grupa_pracownicza",
    )
    wymiar = _matchuj_slownik_lub_odroc(
        matchuj_wymiar_etatu,
        data.get("wymiar_etatu"),
        normalize_wymiar_etatu,
        diff,
        "wymiar_etatu",
    )

    autor, status, kandydaci = _dopasuj_autora_i_status(data, jednostka, tytul_str)
    if (
        data.get("bpp_id") is not None
        and autor is not None
        and data.get("bpp_id") != autor.pk
    ):
        raise XLSMatchError(
            elem,
            "autor",
            "BPP ID zmatchowanego autora i BPP ID w pliku XLS nie zgadzają się",
        )

    # Decyzja o jednostce (dedup po nazwie) — tylko dla ODROCZONYCH z nazwą.
    # zgadywanie zawsze (auto-match do istniejącej), brak tylko gdy włączono
    # tworzenie brakujących. Bez decyzji (pusta/za długa nazwa albo toggle off) →
    # wiersz pominięty z jednostką None.
    decyzja_jednostki = None
    if jednostka_odroczona and nazwa_do_klas and reconciler is not None:
        if jed_status == ImportPracownikowJednostka.TRYB_ZGADYWANIE or (
            jed_status == ImportPracownikowJednostka.TRYB_BRAK and tworz_brakujace
        ):
            decyzja_jednostki = reconciler.reconciluj(
                nazwa_do_klas,
                jed_status,
                jednostka,
                jed_sim,
                skrot_hint=skrot_hint,
            )

    # AJ liczymy TYLKO dla jednostki twardo dopasowanej. Odroczona → jednostka
    # None na wierszu; AJ oraz diff["autor_jednostka"] policzy integracja PO
    # rozstrzygnięciu — inaczej create z jednostka_id=None w _materializuj_diff
    # wywala cały task (IntegrityError). Resolver okresu (§7) rozstrzyga po
    # „dacie od": ten sam okres → istniejący AJ; inna → NOWY okres (nowy AJ).
    jednostka_na_wierszu = None if jednostka_odroczona else jednostka
    aj = None
    if autor is not None and jednostka_na_wierszu is not None:
        aj_lista = list(
            Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka_na_wierszu)
        )
        # ExcelDateField.to_python → date|None (kontrakt resolvera: nigdy str).
        plik_od = data.get("data_zatrudnienia") or None
        rodzaj, wartosc = rozwiaz_okres_zatrudnienia(
            autor, jednostka_na_wierszu, plik_od, aj_lista=aj_lista
        )
        if rodzaj == "istniejacy":
            aj = wartosc
        else:
            diff["autor_jednostka"] = {
                "autor": autor.pk,
                "jednostka": jednostka_na_wierszu.pk,
                "rozpoczal_prace": wartosc.isoformat() if wartosc else None,
                # nowy_okres = tworzymy DODATKOWY okres obok istniejącego (nie
                # pierwsze powiązanie) → do licznika/opisu (§10).
                "nowy_okres": bool(aj_lista),
            }

    row_tytul, row_tytul_status, row_zrodlo_tytulu = _klasyfikuj_tytul_wiersza(
        parent, tytul_str, reconciler_tytulow
    )
    row_stopien, row_stopien_status, row_zrodlo_stopnia = _klasyfikuj_stopien_wiersza(
        parent, data.get("stopień_służbowy"), reconciler_stopni
    )
    (
        row_stanowisko,
        row_stanowisko_status,
        row_zrodlo_stanowiska,
    ) = _klasyfikuj_stanowisko_wiersza(
        parent, data.get("stanowisko_dydaktyczne"), reconciler_stanowisk
    )

    row = ImportPracownikowRow(
        parent=parent,
        dane_z_xls=elem,
        # dane_znormalizowane zawiera też `email` (nowe pole AutorForm) —
        # zapisywany do porównywarki (Plan 4) i do zapisu przy tworzeniu autora
        # (integrate; e-mail = no-overwrite dla istniejących, spec §11.2).
        # Ostrzeżenia (np. o odrzuconym e-mailu) dokładamy obok danych autora —
        # tam czyta je audyt i porównywarka (Row.ostrzezenie_email).
        dane_znormalizowane=_dane_znormalizowane_z_parserem(
            autor_form.cleaned_data, rozbicie, ostrzezenia
        ),
        autor=autor,
        confidence=status,
        jednostka=jednostka_na_wierszu,
        jednostka_status=jed_status,
        zrodlo_jednostki=decyzja_jednostki,
        autor_jednostka=aj,
        tytul=row_tytul,
        tytul_status=row_tytul_status,
        zrodlo_tytulu=row_zrodlo_tytulu,
        stopien=row_stopien,
        stopien_status=row_stopien_status,
        zrodlo_stopnia=row_zrodlo_stopnia,
        stanowisko_dydaktyczne=row_stanowisko,
        stanowisko_dydaktyczne_status=row_stanowisko_status,
        zrodlo_stanowiska_dydaktycznego=row_zrodlo_stanowiska,
        funkcja_autora=funkcja,
        grupa_pracownicza=grupa,
        wymiar_etatu=wymiar,
        podstawowe_miejsce_pracy=normalize_nullboleanfield(
            elem.get("podstawowe_miejsce_pracy")
        ),
        # Item 9: globalny opt-in „przepnij wszystkie prace" pre-zaznacza flagę
        # tylko dla wierszy z autorem i rozstrzygniętą jednostką (dla reszty
        # nie ma czego przepinać). Faza integracji i tak filtruje kwalifikację
        # (F1/F2/F3), a user może korygować per wiersz przed zapisem osób.
        przepnij_prace=(
            parent.przepnij_wszystkie_prace
            and autor is not None
            and jednostka_na_wierszu is not None
        ),
        diff_do_utworzenia=diff,
        zmiany_potrzebne=False,
    )
    if jednostka_odroczona or autor is None:
        # jednostka nierozstrzygnięta albo brak/wielu autora → nic do integracji
        # dopóki nie rozstrzygnie tego integracja/użytkownik.
        row.zmiany_potrzebne = False
    elif aj is not None:
        # bool(diff): wiersz z odroczonym create'em słownika MUSI trafić do
        # integracji, nawet gdy guard is-not-None wyzerował check.
        row.zmiany_potrzebne = bool(diff) or row.check_if_integration_needed()
    else:
        row.zmiany_potrzebne = True
    row.save()

    if status == STATUS_WIELU:
        ImportPracownikowRowKandydat.zapisz_dla(row, kandydaci)


def _materializuj_odpiecia(parent):
    """Tworzy wiersze ``ImportPracownikowOdpiecie`` (zaznaczone=False) dla
    powiązań spoza pliku (§9). Delete-first → idempotentne względem re-analizy
    (``on_restart`` też je kasuje). Uczelnię ustala ``uczelnia_do_integracji``
    (uczelnia importu z requestu; fallback: jedyna w systemie) — w multi-hosted
    (>1 uczelnia) inaczej byłoby ``None`` i wykluczenie obcej jednostki nie
    działałoby. ``None`` (nieustalona) pomija wykluczenie. Zwraca liczbę odpięć."""
    uczelnia = parent.uczelnia_do_integracji()
    parent.odpiecia.all().delete()
    ImportPracownikowOdpiecie.objects.bulk_create(
        [
            ImportPracownikowOdpiecie(parent=parent, autor_jednostka=aj)
            for aj in parent.autorzy_spoza_pliku_set(uczelnia=uczelnia)
        ]
    )
    return parent.odpiecia.count()


def analizuj(parent, p):
    zrodlo = otworz_zrodlo(
        parent.plik_xls.path, try_names=TRY_NAMES, min_points=MIN_POINTS
    )
    total = zrodlo.count()
    if total == 0:
        raise ValueError("Plik nie zawiera danych do importu (0 wierszy).")

    mapowanie = parent.mapowanie_kolumn or {}
    parser_ctx = zbuduj_parser_kontekst()
    reconciler = _ReconcilerJednostek(parent)
    reconciler_tytulow = _ReconcilerTytulow(parent)
    reconciler_stopni = _ReconcilerStopni(parent)
    reconciler_stanowisk = _ReconcilerStanowisk(parent)
    for elem in p.track(list(zrodlo.data()), total=total, label="Wczytywanie"):
        if mapowanie:
            elem = remapuj_wiersz(elem, mapowanie)
        _przetworz_wiersz(
            parent,
            elem,
            parser_ctx,
            reconciler=reconciler,
            reconciler_tytulow=reconciler_tytulow,
            reconciler_stopni=reconciler_stopni,
            reconciler_stanowisk=reconciler_stanowisk,
            tworz_brakujace=parent.tworz_brakujace_jednostki,
        )
    # Decyzje o jednostkach/tytułach/słownikach nieobecne w bieżącym pliku →
    # sprzątamy (przeżywają wybory usera dla nazw, które zostały — reconcilery).
    reconciler.usun_stale()
    reconciler_tytulow.usun_stale()
    reconciler_stopni.usun_stale()
    reconciler_stanowisk.usun_stale()

    liczba_odpiec = _materializuj_odpiecia(parent)

    # Skrót Krok 1 → Krok 2: jeśli WSZYSTKIE jednostki i tytuły z pliku są już
    # w bazie (twarde dopasowania → zero decyzji do rozstrzygnięcia), zapis
    # struktury nic by nie utworzył. Pomijamy Krok 1 i lądujemy od razu w fazie
    # osób (struktura_zintegrowana). Wiersze mają już ustawione jednostkę/tytuł
    # (twarde matche z analizy), a bramka tytułów jest pusta — import osób może
    # ruszyć bez cichego tworzenia czegokolwiek. Gdy jest cokolwiek do
    # rozstrzygnięcia — normalny Krok 1 (przeanalizowany).
    struktura_bez_decyzji = (
        not parent.jednostki_do_decyzji.exists()
        and not parent.tytuly_do_decyzji.exists()
        and not parent.stopnie_do_decyzji.exists()
        and not parent.stanowiska_do_decyzji.exists()
    )
    parent.stan = (
        ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
        if struktura_bez_decyzji
        else ImportPracownikow.STAN_PRZEANALIZOWANY
    )
    parent.save(update_fields=["stan"])

    wiersze = parent.get_details_set()
    p.result(
        {
            "total": wiersze.count(),
            "zmiany_potrzebne": parent.zmiany_potrzebne_set.count(),
            "odpiecia": liczba_odpiec,
            "jednostki_do_utworzenia": parent.jednostki_do_decyzji.filter(
                tryb=ImportPracownikowJednostka.TRYB_BRAK
            ).count(),
            "jednostki_auto": parent.jednostki_do_decyzji.filter(
                tryb=ImportPracownikowJednostka.TRYB_ZGADYWANIE
            ).count(),
            "pominieto_brak_jednostki": parent.importpracownikowrow_set.filter(
                jednostka__isnull=True, zrodlo_jednostki__isnull=True
            ).count(),
            "byl_dry_run": True,
            "stan": parent.stan,
        }
    )
