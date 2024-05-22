from typing import Any, List, Union

from django.db import models
from queryset_sequence import QuerySetSequence

from crossref_bpp.utils import json_format_with_wrap, perform_trigram_search
from import_common.core import (
    matchuj_autora,
    matchuj_wydawce,
    normalize_zrodlo_nazwa_for_db_lookup,
    normalize_zrodlo_skrot_for_db_lookup,
    normalized_db_title,
    normalized_db_zrodlo_nazwa,
    normalized_db_zrodlo_skrot,
)
from import_common.normalization import (
    normalize_doi,
    normalize_first_name,
    normalize_issn,
    normalize_last_name,
    normalize_orcid,
    normalize_publisher,
)

from django.utils.datastructures import CaseInsensitiveMapping
from django.utils.functional import cached_property

from bpp.models import (
    Autor,
    Charakter_Formalny,
    Jezyk,
    Licencja_OpenAccess,
    Rekord,
    Wydawca,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Zrodlo,
)


class StatusPorownania(models.TextChoices):
    DOKLADNE = "ok", "dokładne (identyczne dane po obu stronach)"
    LUZNE = "luzne", "luźne (może być nieprawidłowe)"
    WYMAGA_INGERENCJI = (
        "user",
        "wymaga ręcznego wybrania (dwa lub więcej dokładne wyniki)",
    )
    BRAK = "brak", "brak porównania"
    BLAD = "blad", "błąd porównania - pusty lub niepoprawny parametr wejściowy"


class WynikPorownania:
    def __init__(
        self,
        status: StatusPorownania,
        opis: str = "",
        rekordy: [
            Union[
                List[
                    models.Model,
                ],
                None,
            ]
        ] = None,
    ):
        self.status = status
        self.opis = opis
        self.rekordy = rekordy

    @cached_property
    def rekord_po_stronie_bpp(self):
        """Zwróć pierwszy rekord z self.rekordy jeżeli wynik porównania jest dokładny lub luźny"""
        ile_rekordow = 0
        if hasattr(
            self.rekordy,
            "exists",
        ):
            ile_rekordow = self.rekordy.count()
            pierwszy_rekord = self.rekordy.first()
        elif hasattr(self.rekordy, "__len__"):
            ile_rekordow = len(self.rekordy)
            pierwszy_rekord = self.rekordy[0]

        if (
            self.status in (StatusPorownania.DOKLADNE, StatusPorownania.LUZNE)
            and ile_rekordow == 1
        ):
            return pierwszy_rekord


NIEPRAWIDLOWY_FORMAT_DANYCH = WynikPorownania(
    StatusPorownania.BLAD, "nieprawidłowy format danych"
)
BRAK_DOPASOWANIA = WynikPorownania(StatusPorownania.BLAD, "brak dopasowania")


class Komparator:
    class atrybuty:
        do_porownania_rekordu = [
            "DOI",
            "alternative-id",
            "title",
        ]

        do_zmatchowania = do_porownania_rekordu + [
            "ISSN",
            "issn-type",
            "ISBN",
            "isbn-type",
            "publisher-location",
            "edition-number",
            "link",
            "short-container-title",
            "container-title",
            "type",
            "language",
            "license",
            "publisher",
            "URL",
            "resource",
            "author",
        ]

        do_skopiowania = [
            "abstract",
            "issue",
            "page",
            "subject",
            "volume",
        ]

        ignorowane = [
            "content-domain",
            "created",
            "deposited",
            "indexed",
            "is-referenced-by-count",
            "issued",
            "journal-issue",
            "member",
            "original-title",
            "published",
            "published-online",
            "reference",
            "reference-count",
            "references-count",
            "relation",
            "short-title",
            "source",
            "subtitle",
            "prefix",
            "score",
        ]

        wszystkie = do_skopiowania + do_zmatchowania + ignorowane

    @classmethod
    def porownaj(cls, atrybut: str, wartosc_z_crossref: Any):
        atrybut = atrybut.replace("-", "_")
        fn = getattr(cls, f"porownaj_{atrybut}", None)
        if fn is None:
            return WynikPorownania(
                StatusPorownania.BLAD,
                "brak funkcji w oprogramowaniu BPP do porównania tego atrybutu",
            )
        return fn(wartosc_z_crossref)

    @classmethod
    def znajdz(cls, *args, **kwargs):
        return Rekord.objects.filter(*args, **kwargs).order_by("-ostatnio_zmieniony")[
            :10
        ]

    @classmethod
    def znajdz_w_tabelach(cls, *args, **kwargs):
        qs1 = Wydawnictwo_Zwarte.objects.filter(*args, **kwargs).order_by(
            "-ostatnio_zmieniony"
        )
        qs2 = Wydawnictwo_Ciagle.objects.filter(*args, **kwargs).order_by(
            "-ostatnio_zmieniony"
        )
        return QuerySetSequence(qs1, qs2).order_by("-ostatnio_zmieniony")[:10]

    @classmethod
    def porownaj_DOI(cls, wartosc):
        doi = normalize_doi(wartosc)

        if not doi:
            return WynikPorownania(StatusPorownania.BLAD, "puste DOI")

        ile = cls.znajdz(doi__iexact=doi)

        if not ile.exists():
            return WynikPorownania(StatusPorownania.BRAK, "brak takiego DOI w bazie")

        if ile.count() == 1:
            return WynikPorownania(
                StatusPorownania.DOKLADNE,
                "w BPP jest dokładnie jeden taki rekord o takim DOI",
                rekordy=ile,
            )

        # wiecej, jak jeden rekord
        return WynikPorownania(
            StatusPorownania.WYMAGA_INGERENCJI,
            "więcej, nż jeden rekord w BPP o takim DOI",
            rekordy=ile,
        )

    porownaj_alternative_id = porownaj_DOI

    @classmethod
    def porownaj_ISSN(cls, wartosc):
        issn = normalize_issn(wartosc)
        if issn is None:
            return WynikPorownania(StatusPorownania.BLAD, "niepirawidłowy ISSN")

        for fld in "issn", "e_issn":
            kw = {f"{fld}__icontains": issn}

            ile = cls.znajdz_w_tabelach(**kw)

            if not ile.exists():
                continue

            if ile.count() == 1:
                return WynikPorownania(
                    StatusPorownania.DOKLADNE,
                    "w BPP jest dokładnie jeden taki rekord o takim ISSN lub E-ISSN",
                    rekordy=ile,
                )

            # wiecej, jak jeden rekord
            return WynikPorownania(
                StatusPorownania.WYMAGA_INGERENCJI,
                "więcej, nż jeden rekord w BPP o takim ISSN lub E-ISSN",
                rekordy=ile,
            )

        return WynikPorownania(
            StatusPorownania.BRAK, "brak rekordów o takim ISSN lub E-ISSN w BPP"
        )

    @classmethod
    def porownaj_issn_type(cls, wartosc):
        return cls.porownaj_ISSN(wartosc.get("value"))

    @classmethod
    def porownaj_URL(cls, wartosc):
        if (
            wartosc is None
            or not isinstance(wartosc, str)
            or not wartosc
            or not wartosc.strip()
        ):
            return WynikPorownania(StatusPorownania.BLAD, "nieprawidłowy URL")

        if (
            wartosc.lower().find("dx.doi.org/") > -1
            or wartosc.lower().find("doi.org/") > -1
        ):
            return WynikPorownania(
                StatusPorownania.BLAD,
                "URL wyglada na zakodowany numer DOI, nie wykonuję porównania",
            )

        for fld in "www", "public_www":
            kw = {f"{fld}__icontains": wartosc}

            ile = cls.znajdz_w_tabelach(**kw)

            if not ile.exists():
                continue

            if ile.count() == 1:
                return WynikPorownania(
                    StatusPorownania.DOKLADNE,
                    "w BPP jest dokładnie jeden taki rekord o takim adresie WWW",
                    rekordy=ile,
                )

            # wiecej, jak jeden rekord
            return WynikPorownania(
                StatusPorownania.WYMAGA_INGERENCJI,
                "więcej, nż jeden rekord w BPP o takim adresie WWW",
                rekordy=ile,
            )

        return WynikPorownania(
            StatusPorownania.BRAK, "brak rekordów o takiej stronie WWW w BPP"
        )

    @classmethod
    def porownaj_link(cls, wartosc):
        return cls.porownaj_URL(wartosc.get("URL"))

    @classmethod
    def porownaj_resource(cls, wartosc):
        return cls.porownaj_link(wartosc.get("primary"))

    @classmethod
    def porownaj_author(cls, wartosc):
        if wartosc is None or not isinstance(wartosc, dict):
            return NIEPRAWIDLOWY_FORMAT_DANYCH

        wartosc = CaseInsensitiveMapping(wartosc)

        orcid = normalize_orcid(wartosc.get("orcid"))
        if orcid:
            ret = None
            try:
                ret = Autor.objects.get(orcid__iexact=orcid)
            except Autor.DoesNotExist:
                pass
            if ret:
                return WynikPorownania(
                    StatusPorownania.DOKLADNE, "dopasowanie po ORCID", rekordy=[ret]
                )

        nazwisko = normalize_last_name(wartosc.get("family"))
        imiona = normalize_first_name(wartosc.get("given"))
        if nazwisko and imiona:
            ret = matchuj_autora(imiona, nazwisko)
            if ret:
                return WynikPorownania(
                    StatusPorownania.LUZNE,
                    "znaleziono dokładnie jednego autora po imieniu i nazwisku",
                    rekordy=[
                        ret,
                    ],
                )

            # Brak jednego autora, ale moze jest wielu? Funkcja matchuj_autora nie zwraca
            # takich danych:

            q = Autor.objects.filter(
                nazwisko__icontains=nazwisko, imiona__icontains=imiona
            )

            if q.exists():
                addendum = ""
                MAX_AUT = 10
                if q.count() >= MAX_AUT:
                    addendum = (
                        f" - w sumie {q.count()} rekordow, pokazuje pierwsze {MAX_AUT}"
                    )

                msg = "kilku autorów - luźne porównanie po imieniu i nazwisku"
                status = StatusPorownania.WYMAGA_INGERENCJI
                if q.count() == 1:
                    msg = "jeden autor - luźne porównanie po imieniu i nazwisku"
                    status = StatusPorownania.LUZNE

                return WynikPorownania(
                    status,
                    f"{msg}{addendum}",
                    rekordy=q[:MAX_AUT],
                )

        return BRAK_DOPASOWANIA

    @classmethod
    def porownaj_short_container_title(cls, wartosc):
        poszukiwania = [wartosc]
        if wartosc.lower().startswith("the "):
            poszukiwania.append(wartosc[4:])

        for ciag in poszukiwania:
            tgrm = perform_trigram_search(
                Zrodlo.objects.exclude(skrot="").exclude(skrot=None),
                normalized_db_zrodlo_skrot,
                normalize_zrodlo_skrot_for_db_lookup(ciag),
            )
            if tgrm:
                return WynikPorownania(
                    StatusPorownania.LUZNE,
                    "luźne porównanie tytułu wg funkcji podobieństwa trygramów",
                    rekordy=tgrm,
                )

        return BRAK_DOPASOWANIA

    @classmethod
    def porownaj_container_title(cls, wartosc):
        poszukiwania = [wartosc]
        if wartosc.lower().startswith("the "):
            poszukiwania.append(wartosc[4:])

        for ciag in poszukiwania:
            tgrm = perform_trigram_search(
                Zrodlo.objects.exclude(nazwa="").exclude(nazwa=None),
                normalized_db_zrodlo_nazwa,
                normalize_zrodlo_nazwa_for_db_lookup(ciag),
            )
            if tgrm:
                return WynikPorownania(
                    StatusPorownania.LUZNE,
                    "luźne porównanie tytułu wg funkcji podobieństwa trygramów",
                    rekordy=tgrm,
                )

        return BRAK_DOPASOWANIA

    @classmethod
    def porownaj_publisher(cls, wartosc):
        wartosc = normalize_publisher(wartosc)
        if wartosc is None:
            return NIEPRAWIDLOWY_FORMAT_DANYCH

        wartosci = [
            wartosc,
        ]
        if wartosc.find("/") > -1:
            a, b = wartosc.split("/", 1)
            wartosci.append(a)
            wartosci.append(b)

        mozliwe_wartosci = set()

        for wartosc in wartosci:
            ret = matchuj_wydawce(wartosc, similarity=0.65)

            if ret is None:
                t = Wydawca.objects.filter(nazwa__istartswith=wartosc).filter()
                if t.count() == 1:
                    mozliwe_wartosci.add(t)
                continue

            return WynikPorownania(
                StatusPorownania.LUZNE,
                "luźne dopasowanie po nazwie",
                rekordy=[
                    ret,
                ],
            )

        if mozliwe_wartosci:
            if len(mozliwe_wartosci) == 1:
                return WynikPorownania(
                    StatusPorownania.LUZNE,
                    "luźne dopasowanie po początku nazwy",
                    rekordy=list(mozliwe_wartosci),
                )

            return WynikPorownania(
                StatusPorownania.WYMAGA_INGERENCJI,
                "ekstremalnie luźne dopasowanie po początku nazwy, pasuje do kilku wydawców",
                rekordy=list(mozliwe_wartosci),
            )

        if ret is None:
            return BRAK_DOPASOWANIA

    @classmethod
    def porownaj_title(cls, wartosc):
        ret = Rekord.objects.filter(tytul_oryginalny__istartswith=wartosc)
        if not ret.exists():
            last_chance = perform_trigram_search(
                Rekord.objects.all(), normalized_db_title, wartosc.lower().strip()
            )
            if last_chance:
                return WynikPorownania(
                    StatusPorownania.LUZNE,
                    "luźne porównanie tytułu wg funkcji podobieństwa trygramów",
                    rekordy=last_chance,
                )

            return BRAK_DOPASOWANIA

        count = ret.count()

        if count == 1:
            return WynikPorownania(
                StatusPorownania.LUZNE,
                "znaleziono 1 pracę z tytułem zaczynającym się podobnie",
                rekordy=list(ret),
            )

        w = "rekordów"
        if count <= 4:
            w = "rekordy"
        return WynikPorownania(
            StatusPorownania.WYMAGA_INGERENCJI,
            f"znaleziono {count} {w} z tytułem zaczynającym się podobnie",
            rekordy=list(ret),
        )

    @classmethod
    def porownaj_type(cls, wartosc):
        if wartosc not in Charakter_Formalny.CHARAKTER_CROSSREF.labels:
            return WynikPorownania(
                StatusPorownania.BLAD,
                f'w systemie BPP nie zdefiniowano wartosci dla typu charakteru formalnego "{wartosc}",'
                f" prosimy o zgłoszenie tej sytuacji autorowi programu. ",
            )

        try:
            c = Charakter_Formalny.objects.get(
                charakter_crossref=getattr(
                    Charakter_Formalny.CHARAKTER_CROSSREF,
                    wartosc.upper().replace("-", "_"),
                )
            )
            return WynikPorownania(
                StatusPorownania.DOKLADNE, "określony charakter formalny", rekordy=[c]
            )
        except Charakter_Formalny.DoesNotExist:
            return WynikPorownania(
                StatusPorownania.BLAD,
                f'w systemie BPP nie zdefiniowano wartosci dla typu charakteru formalnego "{wartosc}",'
                f" wejdz w Dane Systemowe -> Charaktery formalne i wybierz typ charakteru crossref "
                f"dla któregoś z charakteru. ",
            )

    @classmethod
    def porownaj_license(cls, wartosc):
        if wartosc.get("URL"):
            url = wartosc.get("URL", "")
            try:
                skrot = "CC-" + (
                    url.split("creativecommons.org/licenses/")[1].split("/")[0].upper()
                )
            except (IndexError, TypeError, ValueError):
                return WynikPorownania(
                    StatusPorownania.BLAD,
                    f"system BPP nie umie dopasować rodzaju licencji dla {url}, proszę zgłosić"
                    f" ten fakt do autora oprogramowania. ",
                )
            try:
                licencja = Licencja_OpenAccess.objects.get(skrot=skrot)
            except Licencja_OpenAccess.DoesNotExist:
                return WynikPorownania(
                    StatusPorownania.BLAD,
                    f"w systemie BPP nie znaleziono licencji ze skrótem {skrot}, proszę o dopisanie",
                )

            return WynikPorownania(
                StatusPorownania.DOKLADNE,
                "okreslony rodzaj licencji",
                rekordy=[licencja],
            )

    @classmethod
    def porownaj_language(cls, wartosc):
        if wartosc not in Jezyk.SKROT_CROSSREF.values:
            return WynikPorownania(
                StatusPorownania.BLAD,
                f'w systemie BPP nie zdefiniowano wartosci dla typu jezyka "{wartosc}",'
                f" prosimy o zgłoszenie tej sytuacji autorowi programu. ",
            )

        try:
            c = Jezyk.objects.get(skrot_crossref=wartosc)
            return WynikPorownania(
                StatusPorownania.DOKLADNE, "określony jezyk", rekordy=[c]
            )
        except Jezyk.DoesNotExist:
            return WynikPorownania(
                StatusPorownania.BLAD,
                f'w systemie BPP nie zdefiniowano wartosci dla typu jezyka "{wartosc}",'
                f" wejdz w Dane Systemowe -> Języki i wybierz typ charakteru crossref "
                f"dla któregoś z języków. ",
            )

    @classmethod
    def utworz_dane_porownania(cls, json_data):
        dane_porownania = []

        def porownaj_jeden_parametr(atrybut, wartosc_z_crossref, atrybut_label=None):
            rezultat = Komparator.porownaj(atrybut, wartosc_z_crossref)

            if "ORCID" in wartosc_z_crossref:
                wartosc_z_crossref["ORCID"] = normalize_orcid(
                    wartosc_z_crossref["ORCID"]
                )
            dane_porownania.append(
                {
                    "atrybut": atrybut_label or atrybut,
                    "orig_atrybut": atrybut,
                    "wartosc_z_crossref_print": json_format_with_wrap(
                        wartosc_z_crossref
                    ),
                    "wartosc_z_crossref": wartosc_z_crossref,
                    "rezultat": rezultat,
                }
            )

        for atrybut in cls.atrybuty.do_zmatchowania:
            wartosc_z_crossref = json_data.get(atrybut)

            if wartosc_z_crossref is None or not wartosc_z_crossref:
                continue

            if isinstance(wartosc_z_crossref, (list, tuple)):
                if len(wartosc_z_crossref) == 0:
                    continue

                if len(wartosc_z_crossref) > 1:
                    for no, elem in enumerate(wartosc_z_crossref):
                        porownaj_jeden_parametr(
                            atrybut, elem, atrybut_label=f"{atrybut}.{no}"
                        )
                else:
                    porownaj_jeden_parametr(
                        atrybut,
                        wartosc_z_crossref[0],
                    )
            else:
                porownaj_jeden_parametr(atrybut, wartosc_z_crossref)

        return dane_porownania

    @classmethod
    def _dane(cls, json_data, atrybuty, key_in_atrybuty=True):
        return [
            (key, {"original": item, "print": json_format_with_wrap(item)})
            for key, item in sorted(json_data.items())
            if (key in atrybuty) == key_in_atrybuty
        ]

    @classmethod
    def dane_do_skopiowania(cls, json_data):
        return cls._dane(json_data, Komparator.atrybuty.do_skopiowania)

    @classmethod
    def dane_ignorowane(cls, json_data):
        return cls._dane(json_data, Komparator.atrybuty.ignorowane)

    @classmethod
    def dane_obce(cls, json_data):
        return cls._dane(
            json_data, Komparator.atrybuty.wszystkie, key_in_atrybuty=False
        )

    @classmethod
    def czy_rekord_ma_odpowiednik_w_bpp(cls, dane_porownania_dict):
        if dane_porownania_dict is None or not dane_porownania_dict:
            return

        for atrybut in Komparator.atrybuty.do_porownania_rekordu:
            wynik_porownania = dane_porownania_dict.get(atrybut)

            if wynik_porownania is None:
                continue

            if (
                wynik_porownania.get("rezultat")
                and wynik_porownania.get("rezultat").rekord_po_stronie_bpp
            ):
                return wynik_porownania.get("rezultat").rekord_po_stronie_bpp
