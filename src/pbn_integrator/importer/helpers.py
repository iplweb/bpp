"""Helper utilities for PBN importer."""

import copy
import logging
from datetime import date

from bpp.models import (
    Czas_Udostepnienia_OpenAccess,
    Dyscyplina_Naukowa,
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

logger = logging.getLogger(__name__)

# taggit trzyma tagi w stockowym modelu Tag, gdzie name i slug to varchar(100).
# Słowa kluczowe z PBN bywają sklejone w jeden bardzo długi ciąg (brak
# separatorów) i przekraczają ten limit — wtedy INSERT do taggit_tag wywala cały
# import na DataError (StringDataRightTruncation). Zamiast tracić całą
# publikację, pomijamy za długie tagi (patrz: przetworz_slowa_kluczowe).
MAKSYMALNA_DLUGOSC_TAGU = 100


def _dopisz_do_adnotacji(ret, naglowek, wartosci):
    """Dopisuje znacznik + listę wartości do pola ``adnotacje`` rekordu.

    Adnotacje to wewnętrzny „śmietnik" na metadane, których nie ma gdzie indziej
    zapisać (analogicznie jak Conference / Proceedings / JournalIssue). Każda
    wartość ląduje w osobnej linii pod znacznikiem ``naglowek``, dzięki czemu da
    się je później znaleźć (grep) i poprawić ręcznie. Nie zapisuje rekordu —
    robi to wołający.
    """
    linie = "\n".join(f"  - {wartosc}" for wartosc in wartosci)
    ret.adnotacje = f"{ret.adnotacje or ''}{naglowek}:\n{linie}\n"


def _znajdz_jezyk(kod_jezyka):
    """Zwraca obiekt ``Jezyk`` dla kodu języka z PBN (np. ``deu``) albo ``None``.

    Kody w słownikach ``titles``/``abstracts``/``mainLanguage`` PBN to klucze
    główne modelu ``pbn_api.Language`` (``code``), czyli to samo, co
    ``Jezyk.pbn_uid_id``. Dopasowanie: najpierw po ``pbn_uid_id``, potem po
    ``skrot__startswith``.

    Oba lookupy znoszą BRUDNE DANE słownika ``Jezyk`` bez wywalania importu:

    - ``DoesNotExist`` (Rollbar #350) — kodu nie ma w słowniku; brak języka to
      nie błąd (surowy kod i tak zachowujemy w ``kod_jezyka_pbn``),
    - ``MultipleObjectsReturned`` (Rollbar #411) — w bazie są ZDUBLOWANE rekordy
      ``Jezyk`` (np. dwa wskazujące ten sam ``Language``, albo o skrócie z tym
      samym prefiksem). To realna wada danych do osobnego sprzątnięcia (dedup =
      osobny ticket), ale NIE może wywalać importu — degradujemy do ``None``.

    Pusty/``None`` kod od razu daje ``None`` (PBN nie podał języka).
    """
    if not kod_jezyka:
        return None

    for lookup in ({"pbn_uid_id": kod_jezyka}, {"skrot__startswith": kod_jezyka}):
        try:
            return Jezyk.objects.get(**lookup)
        except Jezyk.DoesNotExist:
            continue
        except Jezyk.MultipleObjectsReturned:
            logger.warning(
                "Zdublowane rekordy Jezyk dla %s — brudne dane słownika, "
                "degraduję do braku dopasowania (dedup: osobny ticket).",
                lookup,
            )
            return None
    return None


def assert_dictionary_empty(dct, warn=False):
    if dct.keys():
        msg = f"some data still left in dictionary {dct=}"
        if warn:
            logger.info(f"WARNING:  {msg}")
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


def _rozbij_sklejone_slowa_kluczowe(slowa, sklejone, rozbite):
    """Hotfix: pojedyncze „słowo kluczowe", które w PBN jest całą frazą sklejoną
    bez separatorów, rozbij na właściwy zbiór słów."""
    if len(slowa) == 1 and sklejone in slowa:
        return set(rozbite)
    return slowa


def _dodaj_slowa_kluczowe_pl(pbn_keywords_pl, ret):
    """Dodaje tagi PL, pomijając te dłuższe niż taggitowy limit varchar(100).

    Za długie tagi nie są tracone — lądują w ``adnotacje`` pod ``tagsTooLong``.
    """
    poprawne = [tag for tag in pbn_keywords_pl if len(tag) <= MAKSYMALNA_DLUGOSC_TAGU]
    za_dlugie = sorted(
        tag for tag in pbn_keywords_pl if len(tag) > MAKSYMALNA_DLUGOSC_TAGU
    )

    if poprawne:
        ret.slowa_kluczowe.add(*poprawne)

    if za_dlugie:
        logger.warning(
            "Pomijam %d za długich słów kluczowych (>%d znaków) dla %r — "
            "zapisuję je do adnotacji pod znacznikiem 'tagsTooLong'.",
            len(za_dlugie),
            MAKSYMALNA_DLUGOSC_TAGU,
            ret,
        )
        for tag in za_dlugie:
            logger.warning("tagsTooLong dla %r: %s", ret, tag)
        _dopisz_do_adnotacji(ret, "tagsTooLong", za_dlugie)
        if ret.pk:
            ret.save(update_fields=["adnotacje"])


def przetworz_slowa_kluczowe(pbn_keywords_pl, pbn_keywords_en, ret):
    """Process and add keywords (Polish and English) to the record.

    Tagi (słowa kluczowe PL) dłuższe niż ``MAKSYMALNA_DLUGOSC_TAGU`` nie mieszczą
    się w taggitowym ``Tag.name``/``Tag.slug`` (varchar(100)). Zamiast wywalać
    cały import na ``DataError``, pomijamy takie tagi, logujemy je i zapisujemy do
    pola ``adnotacje`` pod znacznikiem ``tagsTooLong`` — rekord się zaimportuje, a
    tagi zostaną widoczne do ręcznej korekty.
    """
    if pbn_keywords_pl:
        pbn_keywords_pl = _rozbij_sklejone_slowa_kluczowe(
            pbn_keywords_pl,
            "pasze pasze lecznicze substancje przeciwbakteryjne antybiotyki "
            "antybiotykooporność zdrowie publiczne urzędowa kontrola",
            [
                "pasze",
                "pasze lecznicze",
                "substancje przeciwbakteryjne",
                "antybiotyki",
                "antybiotykooporność",
                "zdrowie publiczne",
                "urzędowa kontrola",
            ],
        )
        _dodaj_slowa_kluczowe_pl(pbn_keywords_pl, ret)

    if pbn_keywords_en:
        pbn_keywords_en = _rozbij_sklejone_slowa_kluczowe(
            pbn_keywords_en,
            "animal feed medicated feed antibacterial substances antibiotics "
            "antimicrobial resistance public health official controll",
            [
                "animal feed",
                "medicated feed",
                "antibacterial substances",
                "antibiotics",
                "antimicrobial resistance",
                "public health",
                "official control",
            ],
        )
        ret.slowa_kluczowe_eng = pbn_keywords_en


def przetworz_tytuly(pbn_json, ret, klasa_tytulu):
    """Ustawia tytuł alternatywny (``tytul``) i zapisuje tytuły w innych językach.

    PBN trzyma tytuły wariantowe w słowniku ``titles`` (klucze to kody języków,
    np. ``eng``, ``pol``, ``deu``, ``rus``, ``lit``). Tytuł oryginalny siedzi już
    w ``tytul_oryginalny`` (z pola ``title``); do ``tytul`` (tytuł przetłumaczony)
    bierzemy angielski, a jak go nie ma — polski.

    Tytuły w POZOSTAŁYCH językach trafiają do osobnych wierszy ``klasa_tytulu``
    (analogicznie do streszczeń) — po jednym na język. Dzięki temu nic nie ginie,
    są edytowalne w adminie i powiązane ze słownikiem ``Jezyk``. ``klasa_tytulu``
    to konkretny model potomny (``Wydawnictwo_Ciagle_Tytul`` /
    ``Wydawnictwo_Zwarte_Tytul``), tak jak ``importuj_streszczenia`` dostaje swoją
    klasę bazową.

    Musi być wołane PO ``ret.save()`` — wiersze potomne potrzebują ``ret.pk``.
    """
    titles = pbn_json.pop("titles", None)
    if not titles:
        return

    for kod_jezyka in ("eng", "pol"):
        if kod_jezyka in titles:
            ret.tytul = titles.pop(kod_jezyka)
            ret.save(update_fields=["tytul"])
            break

    for kod_jezyka, tytul in titles.items():
        klasa_tytulu.objects.create(
            rekord=ret,
            jezyk=_znajdz_jezyk(kod_jezyka),
            kod_jezyka_pbn=kod_jezyka,
            tytul=tytul,
        )
    titles.clear()


def pobierz_lub_utworz_zrodlo(
    pbn_zrodlo_id, client, rodzaj_periodyk=None, dyscypliny_cache=None
):
    """Get or create journal source (zrodlo).

    Args:
        pbn_zrodlo_id: PBN journal ID
        client: PBN API client
        rodzaj_periodyk: Optional Rodzaj_Zrodla instance for "periodyk"
        dyscypliny_cache: Optional dict mapping discipline names to objects
    """
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

        # Create cache locally if not provided
        if rodzaj_periodyk is None:
            rodzaj_periodyk = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
        if dyscypliny_cache is None:
            dyscypliny_cache = {d.nazwa: d for d in Dyscyplina_Naukowa.objects.all()}

        dopisz_jedno_zrodlo(pbn_journal, rodzaj_periodyk, dyscypliny_cache)
        return Zrodlo.objects.get(pbn_uid_id=pbn_zrodlo_id)


def get_jezyk_polski():
    """Zwraca rekord języka polskiego — domyślny język importu z PBN.

    Pole ``jezyk`` w publikacjach jest NOT NULL, więc gdy PBN nie poda języka
    (albo poda kod, którego nie ma w słowniku ``Jezyk``), rekord i tak musi
    dostać jakiś język. Zamiast „pierwszego z brzegu" (kolejność w tabeli bywa
    przypadkowa) używamy deterministycznie polskiego.

    Kanoniczny polski to ``skrot='pol.'`` (patrz migracja 0022 i fixture'y);
    awaryjnie dopasowujemy po ``nazwa='polski'``. Brak polskiego w bazie to błąd
    konfiguracji instancji — zgłaszamy go jawnie, nie zwracamy cicho ``None``
    (FK i tak by tego nie przyjął).
    """
    jezyk = (
        Jezyk.objects.filter(skrot="pol.").first()
        or Jezyk.objects.filter(nazwa__iexact="polski").first()
    )
    if jezyk is None:
        raise Jezyk.DoesNotExist(
            "Brak języka polskiego w bazie (skrot='pol.' / nazwa='polski') — "
            "nie mam domyślnego języka dla importu PBN."
        )
    return jezyk


def pobierz_jezyk(mainLanguage, pbn_json_title=None, domyslny_jezyk=None):
    """Zwraca ``Jezyk`` dla kodu PBN; przy braku dopasowania — język domyślny.

    Dopasowanie po ``_znajdz_jezyk`` (``pbn_uid_id`` → ``skrot__startswith``,
    odporne na brak i na zdublowane rekordy ``Jezyk``); przy braku dopasowania —
    ``domyslny_jezyk``. ``mainLanguage`` bywa ``None`` (PBN nie podał pola) — wtedy
    od razu idziemy na domyślny. ``domyslny_jezyk`` to ``Jezyk`` wskazany przez
    wołającego (parametr importu); gdy ``None`` — polski (``get_jezyk_polski``).
    """
    jezyk = _znajdz_jezyk(mainLanguage)
    if jezyk is not None:
        return jezyk

    if domyslny_jezyk is None:
        domyslny_jezyk = get_jezyk_polski()

    logger.info(
        " &&& JEZYK NIE ISTNIEJE %r — PRACA %r dostanie jezyk domyslny %r",
        mainLanguage,
        pbn_json_title,
        domyslny_jezyk,
    )
    return domyslny_jezyk


def ustaw_jezyk_oryginalny(ret, pbn_json):
    """Mapuje ``originalLanguage`` z PBN na ``ret.jezyk_orig`` (round-trip eksportu).

    Adapter eksportu (``_build_language_data``) zapisuje ``originalLanguage`` z
    ``jezyk_orig`` rekordu (język oryginału dla tłumaczeń). Import musi ten klucz
    skonsumować — inaczej ``assert_dictionary_empty`` wywala cały import na
    leftoverze ``{'originalLanguage': ...}``.

    ``jezyk_orig`` jest nullable i dotyczy tylko tłumaczeń, więc gdy kodu nie ma
    w słowniku ``Jezyk`` zostawiamy ``None`` (NIE język domyślny — inaczej niż
    ``mainLanguage`` → ``jezyk``). Klucz konsumujemy zawsze, gdy jest obecny.
    """
    kod_jezyka = pbn_json.pop("originalLanguage", None)
    if kod_jezyka:
        ret.jezyk_orig = _znajdz_jezyk(kod_jezyka)


def przetworz_journal_issue(pbn_json, ret, zrodlo):
    """Process journalIssue data and add to annotations if needed."""
    journalIssue = pbn_json.pop("journalIssue", {})
    if not journalIssue:
        return

    orig_journalIssue = copy.deepcopy(journalIssue)
    if str(journalIssue.pop("year", str(ret.rok))) != str(ret.rok):
        logger.info(
            f"CZY TO PROBLEM? year rozny od ret.rok {ret.rok=}, {orig_journalIssue=} "
            f"{ret.tytul_oryginalny} {zrodlo.nazwa}"
        )
    if str(journalIssue.pop("publishedYear", str(ret.rok))) != str(ret.rok):
        logger.info(
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
        jezyk = _znajdz_jezyk(language)
        if jezyk is None:
            logger.info(
                "NIE ZAIMPORTUJE STRESZCZENIA ZA %r poniewaz jego jezyk to %r "
                "a nie mam go (jednoznacznie) w tabeli Jezyki",
                ret,
                language,
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
        # Blok openAccess z PBN bywa niekompletny — potrafi nie zawierać
        # license/mode/releaseDateMode/textVersion. Wszystkie docelowe pola FK
        # są nullable, więc brak klucza zostawia pole puste, a nie wywala import
        # KeyError-em. Wartość OBECNA, ale nieznana w słowniku BPP, to realna
        # luka konfiguracji — wtedy zgłaszamy błąd (jak dotychczas).
        pbn_licencja = oa_json.pop("license", None)
        if pbn_licencja:
            pbn_licencja = pbn_licencja.replace("_", "-")
            try:
                ret.openaccess_licencja = Licencja_OpenAccess.objects.get(
                    skrot=pbn_licencja
                )
            except Licencja_OpenAccess.DoesNotExist as err:
                raise ValueError(
                    f"W BPP nie istnieje licancja {pbn_licencja=}"
                ) from err

        pbn_tryb = oa_json.pop("mode", None)
        if pbn_tryb:
            ret.openaccess_tryb_dostepu = klasa_bazowa_tryb_dostepu.objects.get(
                skrot=pbn_tryb
            )

        pbn_czas = oa_json.pop("releaseDateMode", None)
        if pbn_czas:
            ret.openaccess_czas_publikacji = Czas_Udostepnienia_OpenAccess.objects.get(
                skrot=pbn_czas
            )

        pbn_wersja_tekstu = oa_json.pop("textVersion", None)
        if pbn_wersja_tekstu:
            try:
                ret.openaccess_wersja_tekstu = Wersja_Tekstu_OpenAccess.objects.get(
                    skrot=pbn_wersja_tekstu
                )
            except Wersja_Tekstu_OpenAccess.DoesNotExist as err:
                raise NotImplementedError(
                    f"W BPP nie istnieje wersja tekstu openaccess {pbn_wersja_tekstu=}"
                ) from err

        _importuj_openaccess_daty(ret, oa_json)
        assert_dictionary_empty(oa_json)


def _importuj_openaccess_daty(ret, oa_json):
    """Ustawia pola dat/miesięcy Open Access z (potencjalnie niekompletnego) bloku.

    Wydzielone z ``importuj_openaccess`` dla czytelności i utrzymania złożoności
    cyklomatycznej w ryzach. Klucze ``releaseDate*`` konsumujemy w miarę użycia,
    by ``assert_dictionary_empty`` nie wywalił importu na resztkach.
    """
    months = oa_json.pop("months", None)
    if months:
        ret.openaccess_ilosc_miesiecy = months

    reldate = oa_json.pop("releaseDate", None)
    if reldate:
        reldate = reldate.split("T")[0]
        ret.openaccess_data_opublikowania = date.fromisoformat(reldate)
        oa_json.pop("releaseDateYear", None)
        oa_json.pop("releaseDateMonth", None)
        return

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
            logger.info("bez zartow BLAD DDATY")
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
