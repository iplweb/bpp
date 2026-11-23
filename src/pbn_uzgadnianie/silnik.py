"""Silnik operacji „Uzgodnij z PBN” (FD#477).

Etapy:

1. ``zakres.zbuduj_zakres`` — pobranie danych z PBN (profil instytucji,
   publikacje z wybranych lat, oświadczenia); zmienia TYLKO kopię danych
   PBN. To OSOBNY przebieg (tryb „pobranie”), uruchamiany świadomie:
   podgląd i wykonanie pracują na pobranych wcześniej danych i pokazują,
   z kiedy one są (``swiezosc``) — same niczego nie pobierają.
2. i 3. ``_zastosuj`` — dla każdej pracy decyzja według stałych reguł
   i od razu jej wykonanie (jedna praca = jedna transakcja).
4. raport: lista wpisów w ``UzgodnienieZPBN.wynik``.

Reguły (jedyne zmiany, jakie operacja robi w rekordach BPP):

* praca z profilu bez rekordu w BPP i bez podobnego rekordu → UTWORZENIE
  rekordu importerem ``pbn_integrator`` z wersji przypiętej na profilu,
  z dyscyplinami autorów z oświadczeń instytucji (ściśle — ``dyscypliny``);
* praca z profilu, której odpowiednik w BPP (bez PBN UID) da się wskazać
  PEWNIE — zgodny DOI albo ISBN książki — → POWIĄZANIE (ustawienie PBN UID).

Wszystko inne trafia wyłącznie do raportu: różnice pól, niepewne
dopasowania, konflikty, prace skasowane w PBN, rekordy BPP bez odpowiednika.
Istniejących rekordów nie nadpisujemy, niczego nie kasujemy i niczego nie
wysyłamy do PBN.

Podgląd wykonuje DOKŁADNIE ten sam kod co wykonanie, ale w transakcji,
która na końcu jest wycofywana — dlatego pokazuje to, co wykonanie zrobi.
"""

import logging
import sys

from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import DatabaseError, transaction
from django.utils import timezone
from pbn_client.const import DELETED

from bpp import const
from bpp.models import Rekord, Zrodlo
from bpp.wersjonowanie import jako_uzytkownik, zmiana_rekordu
from bpp.zglaszanie_bledow import capture_exception
from import_common.core import matchuj_publikacje
from pbn_api.exceptions import HttpException
from pbn_api.models import Publication, SentData
from pbn_import.utils.institution_import import znajdz_lub_utworz_jednostke_domyslna
from pbn_integrator.importer import importuj_publikacje_po_pbn_uid_id
from pbn_integrator.importer.helpers import importuj_z_wersji
from pbn_integrator.kosz import pomin_jesli_w_koszu

from . import zakres as zakres_mod
from .dyscypliny import roznice_dyscyplin, zastosuj_do_nowego_rekordu
from .models import UzgodnienieZPBN
from .odpowiedniki import (
    PO_DOI,
    PO_ISBN,
    identyfikatory,
    indeks_niepowiazanych_publikacji_pbn,
    indeks_rekordow_bpp_z_pbn,
    rekordy_bpp_uczelni,
)
from .porownanie import isbn_z_pbn, liczba_osob, liczba_osob_w_bpp, porownaj
from .wersje import wybierz_wersje
from .zakres import Anulowano

logger = logging.getLogger(__name__)

# Kategorie wpisów raportu.
UTWORZONO = "utworzono"
POWIAZANO = "powiazano"
ZGODNE = "zgodne"
ROZNI_SIE = "rozni_sie"
DO_DECYZJI = "do_decyzji"
KONFLIKT = "konflikt"
POMINIETO = "pominieto"
BLAD = "blad"
SKASOWANA_W_PBN = "skasowana_w_pbn"
TYLKO_W_BPP = "tylko_w_bpp"
DUPLIKAT_W_BPP = "duplikat_w_bpp"
W_PBN_NIEPOWIAZANA = "w_pbn_niepowiazana"
NIE_SPRAWDZONO = "nie_sprawdzono"
POZA_PROFILEM = "poza_profilem"
NA_PROFILU_INNEJ_UCZELNI = "na_profilu_innej_uczelni"

KATEGORIE = {
    UTWORZONO: "Utworzono rekord w BPP",
    POWIAZANO: "Powiązano istniejący rekord BPP z pracą w PBN",
    ROZNI_SIE: "Praca jest po obu stronach, dane się różnią",
    DO_DECYZJI: "Do decyzji: w BPP jest podobny rekord (dopasowanie niepewne)",
    KONFLIKT: "Konflikt powiązań",
    POMINIETO: "Pominięto (z podanym powodem)",
    BLAD: "Błąd przy przetwarzaniu pracy",
    SKASOWANA_W_PBN: "Praca skasowana w PBN",
    DUPLIKAT_W_BPP: "Rekord BPP bez powiązania z PBN — prawdopodobny duplikat "
    "rekordu powiązanego z PBN",
    W_PBN_NIEPOWIAZANA: "Rekord BPP bez powiązania z PBN — praca jest w PBN, "
    "ale nie jest powiązana z rekordem",
    TYLKO_W_BPP: "Rekord BPP bez powiązania z PBN — nie ma go w PBN "
    "(kandydat do wysłania)",
    NIE_SPRAWDZONO: "Rekord BPP bez powiązania z PBN — nie da się sprawdzić "
    "automatycznie (brak DOI/ISBN)",
    NA_PROFILU_INNEJ_UCZELNI: "Rekord BPP powiązany z pracą, która jest na "
    "profilu innej uczelni tej instalacji",
    POZA_PROFILEM: "Rekord BPP powiązany z pracą, której nie ma na żadnym "
    "znanym profilu instytucji w PBN",
    ZGODNE: "Praca jest po obu stronach, bez różnic",
}

#: Kategorie oznaczające zmianę w rekordach BPP.
ZMIENIAJACE = (UTWORZONO, POWIAZANO)

OBSLUGIWANE_TYPY = ("ARTICLE", "BOOK", "EDITED_BOOK", "CHAPTER")

#: Wyjątki, po których pomijamy JEDNĄ pracę (z tracebackiem w logu, zgłoszeniem
#: do monitoringu i wpisem w raporcie), a przebieg leci dalej. Importer czyta
#: dane, których kształtu PBN nie gwarantuje — stąd błędy danych (brak klucza,
#: zły typ), błędy PBN i błędy bazy.
BLEDY_JEDNEJ_PRACY = (
    HttpException,
    OSError,  # sieć: zerwane połączenie, przekroczony czas odpowiedzi PBN
    DatabaseError,
    ObjectDoesNotExist,
    MultipleObjectsReturned,
    LookupError,
    ValueError,
    TypeError,
    AttributeError,
    AssertionError,
    NotImplementedError,
)


class _Wycofaj(Exception):
    """Wycofuje transakcję pracy/podglądu — sterowanie, nie błąd."""


class _NiezgodniAutorzy(Exception):
    """Import utworzył rekord z innym składem osób niż w PBN — wycofujemy."""


class _IstniejePodobny(Exception):
    """Importer nie utworzył rekordu, bo sam dopasował istniejący."""

    def __init__(self, rekord):
        super().__init__()
        self.rekord = rekord


class NadzorcaNic:
    """Brak raportowania postępu i brak anulowania (testy, wywołania wprost)."""

    def etap(self, opis, procent):
        pass

    def sprawdz_anulowanie(self):
        pass

    def zamknij(self):
        pass


class NadzorcaBazy(NadzorcaNic):
    """Postęp i anulowanie przez OSOBNE połączenie z bazą.

    Podgląd biegnie w jednej długiej transakcji (wycofywanej na końcu);
    zapis postępu głównym połączeniem byłby niewidoczny dla strony stanu,
    a przebieg wyglądałby na martwy. Osobne połączenie zatwierdza od razu.

    UWAGA: w trakcie przebiegu wiersza ``UzgodnienieZPBN`` nie wolno zapisywać
    głównym połączeniem wewnątrz otwartej transakcji — zapis stąd czekałby
    wtedy na blokadę wiersza bez końca.
    """

    def __init__(self, uzgodnienie_id):
        from django.db import DEFAULT_DB_ALIAS, connections

        self.uzgodnienie_id = uzgodnienie_id
        self.polaczenie = connections.create_connection(DEFAULT_DB_ALIAS)
        self.tabela = UzgodnienieZPBN._meta.db_table
        self._ostatni = None

    def etap(self, opis, procent):
        stan = (opis[:200], max(0, min(99, int(procent))))
        if stan == self._ostatni:
            return
        self._ostatni = stan
        with self.polaczenie.cursor() as kursor:
            kursor.execute(
                f"UPDATE {self.tabela} SET etap = %s, postep = %s, "  # noqa: S608
                "ostatnia_aktualizacja = now() WHERE id = %s",
                [*stan, self.uzgodnienie_id],
            )

    def sprawdz_anulowanie(self):
        with self.polaczenie.cursor() as kursor:
            kursor.execute(
                f"SELECT anuluj FROM {self.tabela} WHERE id = %s",  # noqa: S608
                [self.uzgodnienie_id],
            )
            wiersz = kursor.fetchone()
        if wiersz and wiersz[0]:
            raise Anulowano()

    def zamknij(self):
        self.polaczenie.close()


# --------------------------------------------------------------------------
# Dopasowanie pracy z PBN do istniejącego rekordu BPP
# --------------------------------------------------------------------------


def _rok(obiekt):
    return obiekt.get("year") or (obiekt.get("book") or {}).get("year")


def znajdz_odpowiednik(obiekt):
    """Rekord BPP odpowiadający pracy z PBN → ``(rekord, pewne, opis)``.

    PEWNE dopasowanie — tylko ono pozwala na automatyczne powiązanie:

    * zgodny DOI przy tym samym roku (i podobnym tytule),
    * dla książki: zgodny ISBN przy tym samym roku (i podobnym tytule),
      a rekord BPP sam jest książką (nie rozdziałem).

    NIEPEWNE — każde inne trafienie dotychczasowego dopasowania importera
    (podobny tytuł w tym samym roku/źródle, adres WWW): nie wiążemy i nie
    tworzymy, wpis idzie do decyzji redaktora.
    """
    tytul, rok, typ = obiekt.get("title"), _rok(obiekt), obiekt.get("type")
    if not tytul or not rok:
        return None, False, ""

    doi = obiekt.get("doi")
    if doi:
        rekord = matchuj_publikacje(
            Rekord,
            title=tytul,
            year=rok,
            doi=doi,
            matchuj_po_tytule=False,
            doi_matchuj_tylko_nadrzedne=typ != "CHAPTER",
        )
        if rekord is not None:
            return rekord, True, "zgodny DOI"

    isbn = isbn_z_pbn(obiekt)
    if isbn and typ in ("BOOK", "EDITED_BOOK"):
        rekord = matchuj_publikacje(
            Rekord,
            title=tytul,
            year=rok,
            isbn=isbn,
            matchuj_po_tytule=False,
            isbn_matchuj_tylko_nadrzedne=False,
        )
        if (
            rekord is not None
            and rekord.rok == rok
            and getattr(rekord, "wydawnictwo_nadrzedne_id", None) is None
        ):
            return rekord, True, "zgodny ISBN"

    zrodlo = None
    zrodlo_pbn_id = (obiekt.get("journal") or {}).get("id")
    if zrodlo_pbn_id:
        zrodlo = Zrodlo.objects.filter(pbn_uid_id=zrodlo_pbn_id).first()
    rekord = matchuj_publikacje(
        Rekord,
        title=tytul,
        year=rok,
        doi=doi,
        public_uri=obiekt.get("publicUri"),
        isbn=isbn,
        zrodlo=zrodlo,
    )
    if rekord is not None:
        return rekord, False, "podobny tytuł / adres WWW / ISBN"
    return None, False, ""


# --------------------------------------------------------------------------
# Wpisy raportu
# --------------------------------------------------------------------------


def _opis_bpp(rekord):
    """Pola wpisu opisujące rekord BPP (``Rekord`` albo model źródłowy)."""
    if rekord is None:
        return {}
    if isinstance(rekord, Rekord):
        content_type_id, pk = rekord.pk
        model = rekord.content_type.model
    else:
        from django.contrib.contenttypes.models import ContentType

        content_type_id = ContentType.objects.get_for_model(type(rekord)).pk
        pk, model = rekord.pk, rekord._meta.model_name
    return {
        "bpp_model": model,
        "bpp_pk": pk,
        "bpp_content_type_id": content_type_id,
        "bpp_tytul": str(rekord.tytul_oryginalny),
        "bpp_rok": rekord.rok,
    }


def _wpis(kategoria, pub=None, obiekt=None, rekord=None, **reszta):
    wpis = {"kategoria": kategoria}
    if pub is not None:
        wpis["pbn_uid"] = pub.pk
    if obiekt:
        wpis.update(
            pbn_tytul=obiekt.get("title") or "",
            pbn_rok=_rok(obiekt),
            pbn_typ=obiekt.get("type") or "",
            pbn_doi=obiekt.get("doi") or "",
        )
    elif pub is not None:
        wpis.update(pbn_tytul=pub.title or "", pbn_rok=pub.year)
    wpis.update(_opis_bpp(rekord))
    wpis.update({k: v for k, v in reszta.items() if v not in (None, "", [])})
    return wpis


# --------------------------------------------------------------------------
# Jedna praca z profilu instytucji
# --------------------------------------------------------------------------


class _Przebieg:
    """Stan jednego przebiegu etapów 2–3 (wspólny dla podglądu i wykonania)."""

    def __init__(self, uzgodnienie, client, nadzorca):
        self.uzgodnienie = uzgodnienie
        self.uczelnia = uzgodnienie.uczelnia
        self.client = client
        self.nadzorca = nadzorca
        self.profil = uzgodnienie.zakres["profil"]
        self.oswiadczenia = uzgodnienie.zakres.get("oswiadczenia") or {}
        #: Wyniki wyszukiwania po DOI/ISBN; ``None`` = pobranie ich nie robiło.
        self.szukane = uzgodnienie.zakres.get("szukane")
        self.wpisy = []

    def _default_jednostka(self):
        # Celowo BEZ zapamiętywania między pracami: jednostka bywa tworzona
        # tutaj, a więc w transakcji jednej pracy — gdy ta praca się wycofa,
        # zapamiętany obiekt wskazywałby na nieistniejący wiersz.
        return znajdz_lub_utworz_jednostke_domyslna(self.uczelnia)[0]

    def _wybierz(self, pub):
        wpis_profilu = self.profil.get(pub.pk) or {}
        return wybierz_wersje(pub, wpis_profilu.get("wersje"))

    def _wybieracz_dla_importera(self, pub):
        return self._wybierz(pub).wersja

    # -- reguły ------------------------------------------------------------

    def przetworz(self, pbn_uid):
        """Decyzja + wykonanie dla jednej pracy. Zwraca wpis raportu."""
        pub = Publication.objects.filter(pk=pbn_uid).first()
        if pub is None:
            return {
                "kategoria": POMINIETO,
                "pbn_uid": pbn_uid,
                "powod": "Nie udało się pobrać tej pracy z PBN.",
            }

        wybrana = self._wybierz(pub)
        obiekt = wybrana.obiekt
        wspolne = {"wersja": wybrana.zrodlo}
        if wybrana.jest_nowsza_biezaca:
            wspolne["uwaga"] = (
                "W PBN jest nowsza wersja tej pracy niż przypięta na profilu "
                "instytucji — użyto przypiętej."
            )

        rekordy = list(Rekord.objects.filter(pbn_uid_id=pub.pk)[:3])

        if pub.status == DELETED:
            return _wpis(
                SKASOWANA_W_PBN,
                pub,
                obiekt,
                rekordy[0] if rekordy else None,
                powod="Praca jest na profilu instytucji, ale w PBN ma status "
                "„skasowana”. Nic nie zmieniono.",
            )

        if len(rekordy) > 1:
            return _wpis(
                KONFLIKT,
                pub,
                obiekt,
                rekordy[0],
                powod="Więcej niż jeden rekord BPP ma ten sam PBN UID — "
                "to duplikaty do scalenia.",
                **wspolne,
            )

        if not obiekt or not obiekt.get("type"):
            return _wpis(
                POMINIETO,
                pub,
                None,
                rekordy[0] if rekordy else None,
                powod="Praca w PBN jest niekompletna (brak danych wersji).",
                **wspolne,
            )

        if rekordy:
            oryginal = rekordy[0].original
            roznice = porownaj(oryginal, obiekt) + roznice_dyscyplin(
                oryginal, self.oswiadczenia.get(pub.pk)
            )
            return _wpis(
                ROZNI_SIE if roznice else ZGODNE,
                pub,
                obiekt,
                rekordy[0],
                roznice=roznice,
                **wspolne,
            )

        return self._brak_rekordu_w_bpp(pub, obiekt, wspolne)

    def _brak_rekordu_w_bpp(self, pub, obiekt, wspolne):
        if pomin_jesli_w_koszu(pub, "uzgodnienie-z-pbn"):
            return _wpis(
                POMINIETO,
                pub,
                obiekt,
                powod="Rekord tej pracy jest w koszu BPP — rekordów z kosza "
                "nie przywracamy automatycznie.",
                **wspolne,
            )

        if obiekt["type"] not in OBSLUGIWANE_TYPY:
            return _wpis(
                POMINIETO,
                pub,
                obiekt,
                powod=f"Typ pracy „{obiekt['type']}” nie jest importowany z PBN.",
                **wspolne,
            )

        kandydat, pewne, jak = znajdz_odpowiednik(obiekt)
        if kandydat is not None and not pewne:
            return _wpis(
                DO_DECYZJI,
                pub,
                obiekt,
                kandydat,
                dopasowanie=jak,
                powod="W BPP jest podobny rekord, ale bez zgodnego DOI/ISBN. "
                "Nie utworzono nowego rekordu (ryzyko duplikatu) i nie "
                "powiązano istniejącego (ryzyko pomyłki).",
                **wspolne,
            )
        if kandydat is not None and kandydat.pbn_uid_id:
            return _wpis(
                KONFLIKT,
                pub,
                obiekt,
                kandydat,
                dopasowanie=jak,
                powod=f"Pasujący rekord BPP jest już powiązany z inną pracą "
                f"w PBN ({kandydat.pbn_uid_id}) — możliwy duplikat w PBN.",
                **wspolne,
            )
        if kandydat is not None:
            return self._powiaz(pub, obiekt, kandydat, jak, wspolne)

        if not liczba_osob(obiekt, "authors") and not liczba_osob(obiekt, "editors"):
            return _wpis(
                POMINIETO,
                pub,
                obiekt,
                powod="W PBN praca nie ma ani autorów, ani redaktorów — "
                "nie tworzymy rekordu bez osób.",
                **wspolne,
            )
        return self._utworz(pub, obiekt, wspolne)

    def _powiaz(self, pub, obiekt, kandydat, jak, wspolne):
        oryginal = kandydat.original
        komentarz = f"Uzgodnienie z PBN: powiązano z pracą {pub.pk} ({jak})."
        with zmiana_rekordu(None, oryginal, komentarz):
            oryginal.pbn_uid_id = pub.pk
            oryginal.save(update_fields=["pbn_uid_id"])
        roznice = porownaj(oryginal, obiekt) + roznice_dyscyplin(
            oryginal, self.oswiadczenia.get(pub.pk)
        )
        return _wpis(
            POWIAZANO,
            pub,
            obiekt,
            oryginal,
            dopasowanie=jak,
            roznice=roznice,
            **wspolne,
        )

    def _utworz(self, pub, obiekt, wspolne):
        ksiazka_id = (obiekt.get("book") or {}).get("id")
        ksiazka_byla = bool(
            ksiazka_id and Rekord.objects.filter(pbn_uid_id=ksiazka_id).exists()
        )
        try:
            with transaction.atomic(), importuj_z_wersji(self._wybieracz_dla_importera):
                rekord = importuj_publikacje_po_pbn_uid_id(
                    pub.pk,
                    client=self.client,
                    default_jednostka=self._default_jednostka(),
                )
                if rekord is None or isinstance(rekord, str):
                    raise _Wycofaj()
                if getattr(rekord, "pbn_uid_id", None) != pub.pk or isinstance(
                    rekord, Rekord
                ):
                    # Importer dopasowuje po danych wersji BIEŻĄCEJ; my wyżej
                    # po wersji przypiętej. Gdy on znalazł istniejący rekord,
                    # nic nie utworzył — to przypadek do decyzji redaktora.
                    raise _IstniejePodobny(rekord)
                self._sprawdz_osoby(rekord, obiekt)
                dyscypliny = zastosuj_do_nowego_rekordu(
                    rekord, self.oswiadczenia.get(pub.pk)
                )
        except _IstniejePodobny as e:
            return _wpis(
                DO_DECYZJI,
                pub,
                obiekt,
                e.rekord,
                dopasowanie="podobny rekord wskazany przez importer",
                powod="W BPP jest podobny rekord. Nie utworzono nowego rekordu "
                "(ryzyko duplikatu) i nie powiązano istniejącego.",
                **wspolne,
            )
        except _Wycofaj:
            return _wpis(
                POMINIETO,
                pub,
                obiekt,
                powod="Importer pominął tę pracę (dane w PBN niekompletne albo "
                "nie da się ustalić książki nadrzędnej). Szczegóły w logu.",
                **wspolne,
            )
        except _NiezgodniAutorzy as e:
            return _wpis(
                POMINIETO,
                pub,
                obiekt,
                powod=f"Nie utworzono rekordu: {e} Zaimportuj tę pracę "
                "pojedynczo importerem publikacji i sprawdź osoby.",
                **wspolne,
            )

        uwagi = [wspolne.get("uwaga")]
        if ksiazka_id and not ksiazka_byla:
            uwagi.append(
                f"Utworzono też książkę nadrzędną (PBN {ksiazka_id}) — "
                "rozdział musi być do niej przypięty."
            )
        wspolne = {**wspolne, "uwaga": " ".join(u for u in uwagi if u)}
        return _wpis(UTWORZONO, pub, obiekt, rekord, dyscypliny=dyscypliny, **wspolne)

    @staticmethod
    def _sprawdz_osoby(rekord, obiekt):
        """Bezpiecznik (FD#535): skład osób rekordu = skład osób w PBN.

        Import bywał zawodny przy redaktorach (redaktor zapisany jako autor)
        i tworzył prace bez osób. Rekordu, którego role osób nie zgadzają się
        z PBN co do liczby, nie zostawiamy w bazie.
        """
        for klucz, typ_ogolny, nazwa in (
            ("authors", const.TO_AUTOR, "autorów"),
            ("editors", const.TO_REDAKTOR, "redaktorów"),
        ):
            w_pbn = liczba_osob(obiekt, klucz)
            w_bpp = liczba_osob_w_bpp(rekord, typ_ogolny)
            if w_pbn != w_bpp:
                raise _NiezgodniAutorzy(
                    f"po imporcie rekord miałby {w_bpp} {nazwa}, a w PBN jest "
                    f"ich {w_pbn}."
                )

    # -- rekordy BPP bez odpowiednika w PBN ---------------------------------

    def rekordy_bpp_bez_odpowiednika(self):
        """Rekordy BPP z zakresu lat, których nie ma na profilu instytucji.

        Tylko rekordy, które na profilu być powinny: z afiliowanym autorem
        z jednostki tej uczelni i o charakterze formalnym wysyłanym do PBN.
        """
        u = self.uzgodnienie
        rekordy = list(rekordy_bpp_uczelni(self.uczelnia, u.rok_od, u.rok_do))
        skasowane = set(
            Publication.objects.filter(
                pk__in=[r.pbn_uid_id for r in rekordy if r.pbn_uid_id], status=DELETED
            ).values_list("pk", flat=True)
        )
        bez_pbn = [r for r in rekordy if not r.pbn_uid_id]
        kontekst = self._kontekst_bez_powiazania(bez_pbn) if bez_pbn else None
        inne_uczelnie = self._profile_innych_uczelni(
            [
                r.pbn_uid_id
                for r in rekordy
                if r.pbn_uid_id and r.pbn_uid_id not in self.profil
            ]
        )

        for rekord in rekordy:
            if not rekord.pbn_uid_id:
                yield self._bez_powiazania(rekord, kontekst)
            elif rekord.pbn_uid_id in self.profil:
                continue
            elif rekord.pbn_uid_id in skasowane:
                yield _wpis(
                    SKASOWANA_W_PBN,
                    rekord=rekord,
                    pbn_uid=rekord.pbn_uid_id,
                    powod="Rekord BPP jest powiązany z pracą skasowaną w PBN.",
                )
            elif rekord.pbn_uid_id in inne_uczelnie:
                skroty = ", ".join(sorted(inne_uczelnie[rekord.pbn_uid_id]))
                yield _wpis(
                    NA_PROFILU_INNEJ_UCZELNI,
                    rekord=rekord,
                    pbn_uid=rekord.pbn_uid_id,
                    inna_uczelnia=skroty,
                    powod=f"Praca jest na profilu innej uczelni tej instalacji: "
                    f"{skroty}. Rekord ma też afiliowanego autora tej uczelni, "
                    f"więc praca powinna być także na jej profilu w PBN.",
                )
            else:
                yield _wpis(
                    POZA_PROFILEM,
                    rekord=rekord,
                    pbn_uid=rekord.pbn_uid_id,
                    powod="Pracy nie ma na profilu tej uczelni ani — według "
                    "lokalnej kopii danych PBN — na profilu żadnej innej uczelni "
                    "tej instalacji.",
                )

    def _kontekst_bez_powiazania(self, bez_pbn):
        """Wszystko, czego trzeba do sklasyfikowania rekordów bez PBN UID —
        zebrane stałą liczbą zapytań, niezależnie od liczby rekordów."""
        u = self.uzgodnienie
        znalezione = set()
        for rekord in bez_pbn:
            for klucz in identyfikatory(rekord):
                znalezione.update(
                    ((self.szukane or {}).get(klucz) or {}).get("uids", [])
                )
        wysylki = {}
        for wysylka in SentData.objects.filter(
            object_id__in=[r.pk[1] for r in bez_pbn]
        ).order_by("submitted_at"):
            if wysylka.uczelnia_id in (None, self.uczelnia.pk):
                wysylki[(wysylka.content_type_id, wysylka.object_id)] = wysylka
        return {
            "blizniaki": indeks_rekordow_bpp_z_pbn(u.rok_od, u.rok_do),
            "w_kopii": indeks_niepowiazanych_publikacji_pbn(u.rok_od, u.rok_do),
            "publikacje": Publication.objects.in_bulk(znalezione),
            "powiazane": {
                r.pbn_uid_id: r
                for r in Rekord.objects.filter(pbn_uid_id__in=znalezione)
            },
            "wysylki": wysylki,
        }

    def _bez_powiazania(self, rekord, kontekst):
        """Rekord BPP bez PBN UID → jedna z czterech podgrup raportu."""
        doi, tytul, rok = rekord.doi, rekord.tytul_oryginalny, rekord.rok

        # a) drugi rekord BPP tej samej pracy, już powiązany z PBN
        blizniak, jak = kontekst["blizniaki"].znajdz(doi, tytul, rok)
        if blizniak is not None:
            return self._wpis_duplikatu(rekord, blizniak, jak)

        # b) praca znaleziona w PBN po DOI/ISBN
        klucze = identyfikatory(rekord)
        for klucz in klucze:
            for pbn_uid in ((self.szukane or {}).get(klucz) or {}).get("uids", []):
                jak = f"{PO_DOI if klucz.startswith('doi:') else PO_ISBN} (w PBN)"
                if pbn_uid in kontekst["powiazane"]:
                    return self._wpis_duplikatu(
                        rekord, kontekst["powiazane"][pbn_uid], jak
                    )
                pub = kontekst["publikacje"].get(pbn_uid)
                return self._wpis_w_pbn(
                    rekord,
                    {
                        "pbn_uid": pbn_uid,
                        "tytul": pub.title if pub else "",
                        "rok": pub.year if pub else None,
                        "doi": pub.doi if pub else "",
                    },
                    jak,
                    pewne=True,
                )

        # b) praca jest w lokalnej kopii danych PBN
        praca, jak = kontekst["w_kopii"].znajdz(doi, tytul, rok)
        if praca is not None:
            return self._wpis_w_pbn(rekord, praca, jak, pewne=jak == PO_DOI)

        # d) nie ma po czym zapytać PBN
        if not klucze:
            return _wpis(
                NIE_SPRAWDZONO,
                rekord=rekord,
                powod="Rekord nie ma DOI ani ISBN, więc nie da się zapytać PBN "
                "o tę pracę; w pobranych danych PBN nie ma też pracy o tym "
                "tytule i roku. Sprawdź ręcznie.",
            )
        niesprawdzone = [k for k in klucze if k not in (self.szukane or {})]
        if niesprawdzone:
            return _wpis(
                NIE_SPRAWDZONO,
                rekord=rekord,
                powod="Nie udało się zapytać PBN o tę pracę ("
                + ", ".join(niesprawdzone)
                + ") — pobierz dane z PBN ponownie.",
            )

        # c) PBN nie ma pracy o tym DOI/ISBN
        return _wpis(
            TYLKO_W_BPP,
            rekord=rekord,
            dopasowanie="PBN nie ma pracy o: " + ", ".join(klucze),
            wysylka=self._historia_wysylki(rekord, kontekst["wysylki"]),
        )

    @staticmethod
    def _wpis_duplikatu(rekord, blizniak, jak):
        return _wpis(
            DUPLIKAT_W_BPP,
            rekord=rekord,
            pbn_uid=blizniak.pbn_uid_id,
            dopasowanie=jak,
            blizniak=_opis_bpp(blizniak),
            powod="W BPP jest drugi rekord tej pracy, powiązany z PBN. "
            "Niczego nie scalono — sprawdź oba rekordy i scal je ręcznie.",
        )

    def _wpis_w_pbn(self, rekord, praca, jak, pewne):
        na_profilu = praca["pbn_uid"] in self.profil
        gdzie = (
            "Praca JEST na profilu instytucji w PBN."
            if na_profilu
            else "Pracy NIE MA na profilu instytucji w PBN."
        )
        if pewne:
            propozycja = "Propozycja: wpisz w rekordzie ten PBN UID"
        else:
            jak += " — dopasowanie niepewne"
            propozycja = (
                "Propozycja: sprawdź, czy to ta sama praca; jeśli tak — wpisz "
                "w rekordzie ten PBN UID"
            )
        if not na_profilu:
            propozycja += " i dodaj pracę w PBN do profilu instytucji"
        return _wpis(
            W_PBN_NIEPOWIAZANA,
            rekord=rekord,
            pbn_uid=praca["pbn_uid"],
            pbn_tytul=praca["tytul"] or "",
            pbn_rok=praca["rok"],
            pbn_doi=praca["doi"] or "",
            dopasowanie=jak,
            na_profilu=na_profilu,
            powod=f"{gdzie} {propozycja}. Niczego nie powiązano automatycznie.",
        )

    @staticmethod
    def _historia_wysylki(rekord, wysylki):
        """Co wiadomo o wysyłce tego rekordu z BPP do PBN (tekst do raportu)."""
        wysylka = wysylki.get(tuple(rekord.pk))
        if wysylka is None:
            return "nigdy nie wysyłany z BPP do PBN"
        kiedy = (
            f"{timezone.localtime(wysylka.submitted_at):%d.%m.%Y}"
            if wysylka.submitted_at
            else "data nieznana"
        )
        if wysylka.submitted_successfully:
            return (
                f"wysłany {kiedy} (wysyłka udana), a mimo to rekord nie ma PBN UID "
                "— sprawdź w kolejce eksportu"
            )
        powod = " ".join((wysylka.exception or wysylka.api_response_status).split())
        return f"wysyłka nieudana {kiedy}" + (f": {powod[:200]}" if powod else "")

    def _profile_innych_uczelni(self, pbn_uids):
        """``{pbn_uid: {skróty uczelni}}`` — prace z profili INNYCH uczelni
        tej instalacji, według lokalnej kopii danych PBN (dwa zapytania)."""
        if not pbn_uids:
            return {}
        from bpp.models import Uczelnia
        from pbn_api.models import PublikacjaInstytucji

        skroty = dict(
            Uczelnia.objects.exclude(pk=self.uczelnia.pk)
            .exclude(pbn_uid_id=None)
            .values_list("pbn_uid_id", "skrot")
        )
        if not skroty:
            return {}
        wynik = {}
        for pbn_uid, instytucja in (
            PublikacjaInstytucji.objects.filter(
                publicationId_id__in=pbn_uids, institutionId_id__in=list(skroty)
            )
            .values_list("publicationId_id", "institutionId_id")
            .distinct()
        ):
            wynik.setdefault(pbn_uid, set()).add(skroty[instytucja])
        return wynik

    # -- pętla --------------------------------------------------------------

    def uruchom(self):
        zakres = self.uzgodnienie.zakres
        do_zrobienia = zakres["w_zakresie"]
        ile = len(do_zrobienia) or 1

        for nr, pbn_uid in enumerate(do_zrobienia, 1):
            self.nadzorca.sprawdz_anulowanie()
            self.nadzorca.etap(
                f"Uzgadnianie prac ({nr}/{len(do_zrobienia)})", 40 + 50 * nr // ile
            )
            try:
                with transaction.atomic():
                    wpis = self.przetworz(pbn_uid)
            except BLEDY_JEDNEJ_PRACY as e:
                logger.exception("Uzgodnienie z PBN: błąd dla pracy %s", pbn_uid)
                capture_exception(
                    sys.exc_info(),
                    extra={"pbn_uid": pbn_uid, "uzgodnienie": self.uzgodnienie.pk},
                )
                wpis = {
                    "kategoria": BLAD,
                    "pbn_uid": pbn_uid,
                    "powod": f"{type(e).__name__}: {e}",
                }
            self.wpisy.append(wpis)

        for pbn_uid in zakres.get("bez_roku", []):
            self.wpisy.append(
                {
                    "kategoria": POMINIETO,
                    "pbn_uid": pbn_uid,
                    "powod": "Nie udało się ustalić roku pracy — nie wiadomo, "
                    "czy należy do wybranego zakresu lat.",
                }
            )
        for blad in zakres.get("bledy_pobierania", []):
            self.wpisy.append(
                {
                    "kategoria": BLAD,
                    "pbn_uid": blad.get("pbn_uid") or "",
                    "powod": f"Pobieranie z PBN ({blad['etap']}): {blad['opis']}",
                }
            )

        self.nadzorca.etap("Sprawdzanie rekordów BPP bez odpowiednika w PBN", 92)
        self.wpisy.extend(self.rekordy_bpp_bez_odpowiednika())
        return self.wpisy


def podsumuj(wpisy):
    licznik = dict.fromkeys(KATEGORIE, 0)
    for wpis in wpisy:
        licznik[wpis["kategoria"]] += 1
    return licznik


def _zastosuj(przebieg):
    """Etapy 2–3. Podgląd: cała praca w transakcji, która jest wycofywana."""
    if not przebieg.uzgodnienie.to_podglad:
        return przebieg.uruchom()
    try:
        with transaction.atomic():
            przebieg.uruchom()
            raise _Wycofaj()
    except _Wycofaj:
        pass
    return przebieg.wpisy


def _poprzednie_pobranie(uzgodnienie):
    """Co nowe pobranie bierze z wcześniejszego, zamiast pytać PBN ponownie.

    * wskazane wprost (``na_podstawie``) — także lista prac z profilu
      (użytkownik zdecydował, że świeża lista wystarczy);
    * w każdym razie — świeże wyniki wyszukiwania po DOI/ISBN.
    """
    zrodlo = uzgodnienie.na_podstawie
    if zrodlo is not None:
        return {**zrodlo.zakres, "uzyj_profilu": True}
    ostatnie = UzgodnienieZPBN.ostatnie_pobranie(uzgodnienie.uczelnia)
    if ostatnie is None:
        return None
    return {"szukane": ostatnie.zakres.get("szukane")}


def uzgodnij(uzgodnienie, client, nadzorca=None):
    """Wykonuje cały przebieg i zapisuje wynik w ``uzgodnienie``.

    Nie łapie wyjątków przebiegu (poza anulowaniem) — robi to wołający
    (zadanie w tle / komenda), który oznacza przebieg jako błędny; częściowy
    raport jest wtedy w ``uzgodnienie.wpisy_czesciowe``.
    """
    nadzorca = nadzorca or NadzorcaNic()
    uzgodnienie.wpisy_czesciowe = []
    uzgodnienie.status = UzgodnienieZPBN.Status.W_TOKU
    uzgodnienie.rozpoczeto = timezone.now()
    uzgodnienie.save(update_fields=["status", "rozpoczeto", "ostatnia_aktualizacja"])

    try:
        zrodlo = uzgodnienie.na_podstawie
        if uzgodnienie.to_pobranie or zrodlo is None:
            uzgodnienie.zakres = zakres_mod.zbuduj_zakres(
                client,
                uzgodnienie.uczelnia,
                uzgodnienie.rok_od,
                uzgodnienie.rok_do,
                nadzorca,
                poprzedni=_poprzednie_pobranie(uzgodnienie),
            )
        elif zrodlo.to_pobranie:
            # Praca na danych pobranych wcześniej — bez pobierania.
            uzgodnienie.zakres = zakres_mod.zawez_zakres(
                zrodlo.zakres, uzgodnienie.rok_od, uzgodnienie.rok_do
            )
        else:
            # „Wykonaj ten podgląd”: dokładnie ten sam zakres.
            uzgodnienie.zakres = zrodlo.zakres

        if uzgodnienie.to_pobranie:
            wpisy = []
        else:
            przebieg = _Przebieg(uzgodnienie, client, nadzorca)
            uzgodnienie.wpisy_czesciowe = przebieg.wpisy
            with jako_uzytkownik(uzgodnienie.user):
                wpisy = _zastosuj(przebieg)
    except Anulowano:
        zapisz_przerwany(
            uzgodnienie,
            UzgodnienieZPBN.Status.ANULOWANE,
            "Anulowano na życzenie użytkownika",
        )
        return uzgodnienie

    uzgodnienie.wynik = wpisy
    uzgodnienie.podsumowanie = podsumuj(wpisy)
    uzgodnienie.status = UzgodnienieZPBN.Status.ZAKONCZONE
    uzgodnienie.etap = "Zakończono"
    uzgodnienie.postep = 100
    uzgodnienie.zakonczono = timezone.now()
    uzgodnienie.save()
    return uzgodnienie


def zapisz_przerwany(uzgodnienie, status, etap, blad=""):
    """Zamyka przebieg przerwany (anulowanie / błąd).

    Wykonanie zatwierdza każdą pracę osobno, więc to, co zrobiono przed
    przerwaniem, ZOSTAJE w bazie — dlatego zapisujemy częściowy raport.
    Podgląd został w całości wycofany, więc raportu nie ma.
    """
    wpisy = [] if uzgodnienie.to_podglad else list(uzgodnienie.wpisy_czesciowe)
    uzgodnienie.wynik = wpisy
    uzgodnienie.podsumowanie = podsumuj(wpisy)
    uzgodnienie.status = status
    uzgodnienie.etap = etap
    uzgodnienie.blad = blad
    uzgodnienie.zakonczono = timezone.now()
    uzgodnienie.save()
