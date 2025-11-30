"""Helper utilities for PBN importer."""

import copy
from datetime import date

from bpp.models import (
    Czas_Udostepnienia_OpenAccess,
    Jezyk,
    Licencja_OpenAccess,
    ModelZOpenAccess,
    Rodzaj_Zrodla,
    Tryb_OpenAccess_Wydawnictwo_Zwarte,
    Wersja_Tekstu_OpenAccess,
    Zrodlo,
)
from pbn_api.models import Journal
from pbn_integrator.utils import zapisz_mongodb


def assert_dictionary_empty(dct, warn=False):
    if dct.keys():
        msg = f"some data still left in dictionary {dct=}"
        if warn:
            print("WARNING: ", msg)
            return

        raise AssertionError(msg)


def pbn_keywords_to_slowa_kluczowe(keywords, lang="pol"):
    slowa_kluczowe = keywords.get(lang, [])

    if isinstance(slowa_kluczowe, list):
        match len(slowa_kluczowe):
            case 1:
                slowa_kluczowe = slowa_kluczowe[0]
            case 0:
                return []
            case _:
                return set(slowa_kluczowe)

    # Mamy ciąg znaków z przecinkami albo średnikami...

    for separator in ",;":
        if slowa_kluczowe.find(separator) >= 0:
            break

    return set(slowa_kluczowe.split(separator))


def przetworz_slowa_kluczowe(pbn_keywords_pl, pbn_keywords_en, ret):
    """Process and add keywords (Polish and English) to the record."""
    if pbn_keywords_pl:
        if len(pbn_keywords_pl) == 1:
            # hotfix...
            if (
                "pasze pasze lecznicze substancje przeciwbakteryjne antybiotyki "
                "antybiotykooporność zdrowie publiczne urzędowa kontrola"
                in pbn_keywords_pl
            ):
                pbn_keywords_pl = {
                    "pasze",
                    "pasze lecznicze",
                    "substancje przeciwbakteryjne",
                    "antybiotyki",
                    "antybiotykooporność",
                    "zdrowie publiczne",
                    "urzędowa kontrola",
                }
        ret.slowa_kluczowe.add(*(pbn_keywords_pl))

    if pbn_keywords_en:
        if len(pbn_keywords_en) == 1:
            if (
                "animal feed medicated feed antibacterial substances antibiotics "
                "antimicrobial resistance public health official controll"
                in pbn_keywords_en
            ):
                pbn_keywords_en = {
                    "animal feed",
                    "medicated feed",
                    "antibacterial substances",
                    "antibiotics",
                    "antimicrobial resistance",
                    "public health",
                    "official control",
                }

        ret.slowa_kluczowe_eng = pbn_keywords_en


def pobierz_lub_utworz_zrodlo(pbn_zrodlo_id, client):
    """Get or create journal source (zrodlo)."""
    # Import here to avoid circular imports
    from .sources import dopisz_jedno_zrodlo

    if pbn_zrodlo_id is None:
        return Zrodlo.objects.get_or_create(
            nazwa="Brak źródła po stronie PBN",
            skrot="BPBN",
            rodzaj=Rodzaj_Zrodla.objects.get(nazwa="źródło nieindeksowane"),
        )[0]

    try:
        return Zrodlo.objects.get(pbn_uid_id=pbn_zrodlo_id)
    except Zrodlo.DoesNotExist:
        res = client.get_journal_by_id(pbn_zrodlo_id)
        pbn_journal = zapisz_mongodb(res, Journal, client)
        dopisz_jedno_zrodlo(pbn_journal)
        return Zrodlo.objects.get(pbn_uid_id=pbn_zrodlo_id)


def pobierz_jezyk(mainLanguage, pbn_json_title):
    """Get language object from PBN language code."""
    try:
        return Jezyk.objects.get(pbn_uid_id=mainLanguage)
    except Jezyk.DoesNotExist:
        try:
            return Jezyk.objects.get(skrot__startswith=mainLanguage)
        except Jezyk.DoesNotExist:
            print(f" &&& JEZYK NIE ISTNIEJE {mainLanguage=}")
            print(
                f" *** PRACA {pbn_json_title} zostanie utworzona z jezykiem "
                f"PIERWSZYM NA LISCIE"
            )
            return Jezyk.objects.all().first()


def przetworz_journal_issue(pbn_json, ret, zrodlo):
    """Process journalIssue data and add to annotations if needed."""
    journalIssue = pbn_json.pop("journalIssue", {})
    if not journalIssue:
        return

    orig_journalIssue = copy.deepcopy(journalIssue)
    if str(journalIssue.pop("year", str(ret.rok))) != str(ret.rok):
        print(
            f"CZY TO PROBLEM? year rozny od ret.rok {ret.rok=}, {orig_journalIssue=} "
            f"{ret.tytul_oryginalny} {zrodlo.nazwa}"
        )
    if str(journalIssue.pop("publishedYear", str(ret.rok))) != str(ret.rok):
        print(
            f"CZY TO PROBLEM? publishedYear rozny od ret.rok {ret.rok=}, "
            f"{orig_journalIssue=} {ret.tytul_oryginalny} {zrodlo.nazwa}"
        )
    if "number" in journalIssue or "volume" in journalIssue:
        ret.adnotacje += "JournalIssue: " + str(journalIssue) + "\n"
        ret.save(update_fields=["adnotacje"])
        journalIssue.pop("number", "")
        journalIssue.pop("volume", "")
    journalIssue.pop("doi", None)
    assert_dictionary_empty(journalIssue)


def przetworz_metadane_konferencji(pbn_json, ret):
    """Process conference, evaluation data, and related metadata."""
    conference = pbn_json.pop("conference", None)
    if conference:
        ret.adnotacje += "Conference: " + str(conference) + "\n"
        ret.save(update_fields=["adnotacje"])

    evaluationData = pbn_json.pop("evaluationData", None)
    if evaluationData:
        ret.adnotacje += "EvaluationData: " + str(evaluationData) + "\n"
        ret.save(update_fields=["adnotacje"])

    conferenceSeries = pbn_json.pop("conferenceSeries", None)
    if conferenceSeries:
        ret.adnotacje += "ConferenceSeries: " + str(conferenceSeries) + "\n"
        ret.save(update_fields=["adnotacje"])

    proceedings = pbn_json.pop("proceedings", None)
    if proceedings:
        ret.adnotacje += "Proceedings: " + str(proceedings) + "\n"
        ret.save(update_fields=["adnotacje"])


def importuj_streszczenia(pbn_json, ret, klasa_bazowa):
    """Import abstracts in multiple languages."""
    abstracts = pbn_json.pop("abstracts", {})

    for language, value in abstracts.items():
        try:
            jezyk = Jezyk.objects.get(pbn_uid_id=language)
        except Jezyk.DoesNotExist:
            try:
                jezyk = Jezyk.objects.get(skrot__startswith=language)
            except Jezyk.DoesNotExist:
                print(
                    f"NIE ZAIMPORTUJE STRESZCZENIA ZA {ret=} poniewaz jego jezyk to "
                    f"{language=} a nie mam go w tabeli Jezyki"
                )
                continue

        klasa_bazowa.objects.create(
            rekord=ret,
            jezyk_streszczenia=jezyk,
            streszczenie=value,
        )


def importuj_openaccess(
    ret: ModelZOpenAccess,
    pbn_json,
    klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Zwarte,
):
    oa_json = pbn_json.pop("openAccess", None)
    orig_oa_json = copy.deepcopy(oa_json)  # noqa
    if oa_json is not None:
        pbn_licencja = oa_json.pop("license").replace("_", "-")
        try:
            ret.openaccess_licencja = Licencja_OpenAccess.objects.get(
                skrot=pbn_licencja
            )
        except Licencja_OpenAccess.DoesNotExist as err:
            raise ValueError(f"W BPP nie istnieje licancja {pbn_licencja=}") from err
        ret.openaccess_tryb_dostepu = klasa_bazowa_tryb_dostepu.objects.get(
            skrot=oa_json.pop("mode")
        )
        ret.openaccess_czas_publikacji = Czas_Udostepnienia_OpenAccess.objects.get(
            skrot=oa_json.pop("releaseDateMode")
        )

        pbn_wersja_tekstu = oa_json.pop("textVersion")
        try:
            ret.openaccess_wersja_tekstu = Wersja_Tekstu_OpenAccess.objects.get(
                skrot=pbn_wersja_tekstu
            )
        except Wersja_Tekstu_OpenAccess.DoesNotExist as err:
            raise NotImplementedError(
                f"W BPP nie istnieje wersja tekstu openaccess {pbn_wersja_tekstu=}"
            ) from err

        months = oa_json.pop("months", None)
        if months:
            ret.openaccess_ilosc_miesiecy = months

        reldate = oa_json.pop("releaseDate", None)
        if reldate:
            reldate = reldate.split("T")[0]
            ret.openaccess_data_opublikowania = date.fromisoformat(reldate)

            oa_json.pop("releaseDateYear", None)
            oa_json.pop("releaseDateMonth", None)
        else:
            if "releaseDateYear" in oa_json and "releaseDateMonth" in oa_json:
                strMonth = {
                    "JANUARY": 1,
                    "FEBRUARY": 2,
                    "MARCH": 3,
                    "APRIL": 4,
                    "MAY": 5,
                    "JUNE": 6,
                    "JULY": 7,
                    "AUGUST": 8,
                    "SEPTEMBER": 9,
                    "OCTOBER": 10,
                    "NOVEMBER": 11,
                    "DECEMBER": 12,
                }

                assert ret.openaccess_data_opublikowania is None

                reldate_year = oa_json.pop("releaseDateYear")
                if reldate_year is None:
                    print("bez zartow BLAD DDATY")
                else:
                    ret.openaccess_data_opublikowania = date(
                        int(reldate_year),
                        strMonth.get(oa_json.pop("releaseDateMonth")),
                        1,
                    )

            if "releaseDateYear" in oa_json:  # sam rok
                ret.openaccess_data_opublikowania = date(
                    int(oa_json.pop("releaseDateYear")),
                    1,
                    1,
                )

        assert_dictionary_empty(oa_json)


def get_or_download_publication(mongoId, client):
    from pbn_api.models import Publication
    from pbn_integrator.utils import zapisz_mongodb

    try:
        pbn_publication = Publication.objects.get(pk=mongoId)
    except Publication.DoesNotExist:
        res = client.get_publication_by_id(mongoId)
        zapisz_mongodb(res, Publication)
        pbn_publication = Publication.objects.get(pk=mongoId)

    return pbn_publication
