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

from bpp.models import Autor_Jednostka, Uczelnia
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
    zaproponuj_skrot,
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
from import_pracownikow.mapping import MIN_POINTS, TRY_NAMES, remapuj_wiersz
from import_pracownikow.models import (
    AutorForm,
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
    ImportPracownikowTytul,
)
from import_pracownikow.parsers.leksykony import zbuduj_parser_kontekst
from import_pracownikow.parsers.osoba import rozbij_osobe
from import_pracownikow.parsers.wartosci import (
    normalizuj_wartosci_wiersza,
    sklej_drugie_imie,
)
from import_pracownikow.pewnosc import (
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

    def reconciluj(self, nazwa_zrodlowa, tryb, auto_jednostka, auto_similarity):
        nazwa_zrodlowa = nazwa_zrodlowa[:512]
        dec = self.parent.jednostki_do_decyzji.filter(
            nazwa_zrodlowa__iexact=nazwa_zrodlowa
        ).first()
        if dec is None:
            dec = ImportPracownikowJednostka.objects.create(
                parent=self.parent,
                nazwa_zrodlowa=nazwa_zrodlowa,
                tryb=tryb,
                auto_jednostka=auto_jednostka,
                auto_similarity=auto_similarity,
                skrot_sugerowany=zaproponuj_skrot(nazwa_zrodlowa),
            )
        else:
            dec.tryb = tryb
            dec.auto_jednostka = auto_jednostka
            dec.auto_similarity = auto_similarity
            if not dec.skrot_sugerowany:
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


def _dane_znormalizowane_z_parserem(cleaned_data, rozbicie):
    """Kopia cleaned_data wzbogacona o pewność rozbicia parsera (§7): confidence
    rozbicia (high/medium/low) i alternatywy trzymamy WEWNĄTRZ JSON, nie w
    kolumnie ``confidence`` (ta jest statusem dopasowania AUTORA — §8)."""
    dane = copy(cleaned_data)
    if rozbicie is not None:
        dane["parser_confidence"] = rozbicie.confidence
        dane["parser_alternatywy"] = rozbicie.alternatywy
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
    """
    aj_qs = Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka)
    return (
        aj_qs.filter(zakonczyl_prace__isnull=True).order_by("-rozpoczal_prace").first()
        or aj_qs.order_by("-rozpoczal_prace").first()
    )


def _przetworz_wiersz(
    parent,
    elem,
    parser_ctx=None,
    *,
    reconciler=None,
    reconciler_tytulow=None,
    tworz_brakujace=True,
):
    dane_form = normalizuj_wartosci_wiersza(elem)
    rozbicie = _rozbij_osoba_sklejona(dane_form, parser_ctx)
    # Kolumna „Drugie imię" scalana z „Imię" w jedno Autor.imiona — PO rozbiciu
    # osoby sklejonej (parser uzupełnia puste „imię" z rozbicia), przed AutorForm.
    sklej_drugie_imie(dane_form)

    # Jednostka: klasyfikacja BEZ rzucania (brak/remis/pusta/za długa nazwa NIE
    # wywalają analizy). twardy → dopasowana wprost; zgadywanie/brak → odroczona
    # do decyzji (ekran weryfikacji + faza integracji). Pusta/za długa nazwa
    # (>512) → traktowana jak brak nazwy: wiersz pominięty, bez decyzji.
    nazwa_jed = str(dane_form.get("nazwa_jednostki") or "").strip()
    wydzial = str(dane_form.get("wydział") or "").strip() or None
    nazwa_do_klas = nazwa_jed if 0 < len(nazwa_jed) <= 512 else ""
    jednostka, jed_status, jed_sim = sklasyfikuj_jednostke(nazwa_do_klas, wydzial)
    jednostka_odroczona = jed_status != STATUS_JEDNOSTKA_TWARDY

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
                nazwa_do_klas, jed_status, jednostka, jed_sim
            )

    # AJ liczymy TYLKO dla jednostki twardo dopasowanej. Odroczona → jednostka
    # None na wierszu; AJ oraz diff["autor_jednostka"] policzy integracja PO
    # rozstrzygnięciu — inaczej get_or_create(jednostka_id=None) w
    # _materializuj_diff wywala cały task (IntegrityError).
    jednostka_na_wierszu = None if jednostka_odroczona else jednostka
    aj = None
    if autor is not None and jednostka_na_wierszu is not None:
        aj = _wybierz_autor_jednostka(autor, jednostka_na_wierszu)
        if aj is None:
            diff["autor_jednostka"] = {
                "autor": autor.pk,
                "jednostka": jednostka_na_wierszu.pk,
            }

    row_tytul, row_tytul_status, row_zrodlo_tytulu = _klasyfikuj_tytul_wiersza(
        parent, tytul_str, reconciler_tytulow
    )

    row = ImportPracownikowRow(
        parent=parent,
        dane_z_xls=elem,
        dane_znormalizowane=_dane_znormalizowane_z_parserem(
            autor_form.cleaned_data, rozbicie
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
        funkcja_autora=funkcja,
        grupa_pracownicza=grupa,
        wymiar_etatu=wymiar,
        podstawowe_miejsce_pracy=normalize_nullboleanfield(
            elem.get("podstawowe_miejsce_pracy")
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
    (``on_restart`` też je kasuje). Uczelnię ustala
    ``get_single_uczelnia_or_none`` (brak requestu w tle) — ``None`` pomija
    wykluczenie obcej jednostki. Zwraca liczbę utworzonych odpięć."""
    uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()
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
    for elem in p.track(list(zrodlo.data()), total=total, label="Wczytywanie"):
        if mapowanie:
            elem = remapuj_wiersz(elem, mapowanie)
        _przetworz_wiersz(
            parent,
            elem,
            parser_ctx,
            reconciler=reconciler,
            reconciler_tytulow=reconciler_tytulow,
            tworz_brakujace=parent.tworz_brakujace_jednostki,
        )
    # Decyzje o jednostkach/tytułach nieobecne w bieżącym pliku → sprzątamy
    # (przeżywają wybory usera dla nazw, które zostały — patrz reconcilery).
    reconciler.usun_stale()
    reconciler_tytulow.usun_stale()

    liczba_odpiec = _materializuj_odpiecia(parent)

    parent.stan = ImportPracownikow.STAN_PRZEANALIZOWANY
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
