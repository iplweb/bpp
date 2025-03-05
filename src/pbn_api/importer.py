import copy
from datetime import date

from django.core.management import call_command
from django.db import DataError, transaction
from tqdm import tqdm

from pbn_api.client import PBNClient
from pbn_api.integrator import (
    integruj_zrodla,
    pobierz_i_zapisz_dane_jednej_osoby,
    utworz_wpis_dla_jednego_autora,
    zapisz_mongodb,
)
from pbn_api.models import Journal, Publication, Publisher

from bpp import const
from bpp.models import (
    Autor,
    Charakter_Formalny,
    Czas_Udostepnienia_OpenAccess,
    Dyscyplina_Naukowa,
    Jednostka,
    Jezyk,
    Licencja_OpenAccess,
    ModelZOpenAccess,
    Punktacja_Zrodla,
    Rekord,
    Rodzaj_Zrodla,
    Status_Korekty,
    Tryb_OpenAccess_Wydawnictwo_Ciagle,
    Tryb_OpenAccess_Wydawnictwo_Zwarte,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Uczelnia,
    Wersja_Tekstu_OpenAccess,
    Wydawca,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Streszczenie,
    Zrodlo,
)
from bpp.util import pbar


def dopisz_jedno_zrodlo(pbn_journal):
    assert pbn_journal.rekord_w_bpp() is None

    cv = pbn_journal.current_version["object"]

    rodzaj_periodyk = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
    zrodlo = Zrodlo.objects.create(
        nazwa=cv.get("title"),
        skrot=cv.get("title"),
        issn=cv.get("issn"),
        e_issn=cv.get("eissn"),
        pbn_uid=pbn_journal,
        rodzaj=rodzaj_periodyk,
    )
    for rok, value in cv.get("points", {}).items():
        if value.get("accepted"):
            zrodlo.punktacja_zrodla_set.create(rok=rok, punkty_kbn=value.get("points"))

    for discipline in cv.get("disciplines", []):
        nazwa_dyscypliny = discipline.get("name")
        try:
            dyscyplina_naukowa = Dyscyplina_Naukowa.objects.get(nazwa=nazwa_dyscypliny)
        except Dyscyplina_Naukowa.DoesNotExist:
            raise DataError(f"Brak dyscypliny o nazwie {nazwa_dyscypliny}")

        for rok in range(const.PBN_MIN_ROK, const.PBN_MAX_ROK):
            zrodlo.dyscyplina_zrodla_set.get_or_create(
                rok=rok,
                dyscyplina=dyscyplina_naukowa,
            )


def importuj_zrodla():
    integruj_zrodla()

    # Dodaj do tabeli Źródła wszystkie źródła MNISW z PBNu, których tam jeszcze nie ma.

    for pbn_journal in pbar(
        query=Journal.objects.filter(status="ACTIVE").exclude(
            pk__in=Zrodlo.objects.values_list("pbn_uid_id", flat=True)
        ),
        label="Dopisywanie źródeł MNISW...",
    ):
        dopisz_jedno_zrodlo(pbn_journal)


def importuj_jednego_wydawce(publisher, verbosity=1):
    poziom_to_points_map = {2: 200, 1: 80}
    points_to_poziom_map = {200: 2, 80: 1}
    needs_recalc = set()

    def get_poziom_bpp(pbn_side):
        poziom_bpp = points_to_poziom_map.get(pbn_side["points"])
        if not poziom_bpp:
            raise NotImplementedError(
                f"Brak odpowiednika poziomu {pbn_side['points']} w mappingu"
            )
        return poziom_bpp

    if not publisher.wydawca_set.exists():
        # Nie ma takiego wydawcy w bazie BPP, spróbuj go zmatchować:

        nw = publisher.matchuj_wydawce()
        if nw is not None:
            if publisher.publisherName != nw.nazwa:
                print(
                    f"0 ZWERYFIKUJ FONETYCZNE DOPASOWANIE: {publisher.publisherName} do {nw.nazwa}"
                )
            nw.pbn_uid = publisher
            nw.save()

    if not publisher.wydawca_set.exists():
        # Nie ma takiego wydawcy w bazie, utwórz go:

        nowy_wydawca = Wydawca.objects.create(
            nazwa=publisher.publisherName, pbn_uid=publisher
        )
        if verbosity > 1:
            print(f"1 Tworze nowego wydawce z MNISWID, {publisher.publisherName}")

        for rok in const.PBN_LATA:
            points = publisher.points.get(str(rok))

            if not points:
                # Brak punktów w PBNie za dany rok
                continue

            if not points["accepted"]:
                raise NotImplementedError(
                    f"Accepted = False dla {publisher} {rok}, co dalej?"
                )

            poziom = points_to_poziom_map.get(points["points"])
            assert poziom, f"Brak odpowiednika dla {points['points']}"

            nowy_wydawca.poziom_wydawcy_set.create(rok=rok, poziom=poziom)

        return True

    # Jest już taki wydawca i ma ustawiony match z PBN. Sprawdzimy mu jego poziomy:
    for wydawca in publisher.wydawca_set.all():
        # Nie pracujemy na aliasach
        wydawca = wydawca.get_toplevel()

        for rok in const.PBN_LATA:
            pbn_side = publisher.points.get(str(rok))

            wydawca_side = wydawca.poziom_wydawcy_set.filter(rok=rok).first()

            if pbn_side is not None:
                if not pbn_side["accepted"]:
                    raise NotImplementedError(
                        f"Accepted = False dla {publisher} {rok}, co dalej?"
                    )

                if wydawca_side is None:
                    # Nie ma poziomu po naszej stronie dla tego rkou ,dodamy go:
                    poziom_bpp = get_poziom_bpp(pbn_side)

                    if verbosity > 1:
                        print(
                            f"2 Wydawca {wydawca}: dodaje poziom {poziom_bpp} za {rok} "
                        )

                    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=poziom_bpp)
                    needs_recalc.add((wydawca, rok))
                    continue

                # Są obydwa poziomy: Publisher (PBN) i Wydawca (BPP)
                # porównaj, czy są ok:

                wydawca_side_poziom_translated = poziom_to_points_map.get(
                    wydawca_side.poziom
                )

                if pbn_side["points"] != wydawca_side_poziom_translated:
                    if verbosity > 1:
                        print(
                            f"5 Poziomy sie roznia dla {publisher} {rok}, ustawiam poziom z PBNu?"
                        )
                        wydawca_side.poziom = get_poziom_bpp(pbn_side)
                        needs_recalc.add((wydawca, rok))

                        wydawca_side.save()
                        continue

            else:
                # pbn_side is None
                if wydawca_side is not None:
                    print(
                        f"4 PBN nie ma poziomu a wydawca ma, co robic? {publisher} {rok}"
                    )

                # wydawca_side is None, są równe zatem, nic nie robimy


def importuj_wydawcow(verbosity=1):
    needs_mapping = False

    with transaction.atomic():
        for publisher in pbar(Publisher.objects.official()):
            if importuj_jednego_wydawce(publisher):
                needs_mapping = True

    # To uruchamiamy poza transakcją - jeżeli były zmiany
    if needs_mapping:
        call_command("zamapuj_wydawcow")


def assert_dictionary_empty(dct, warn=False):
    if dct.keys():
        msg = f"some data still left in dictionary {dct=}"
        if warn:
            print("WARNING: ", msg)
            return

        raise AssertionError(msg)


def importuj_streszczenia(pbn_json, ret, klasa_bazowa=Wydawnictwo_Ciagle_Streszczenie):
    abstracts = pbn_json.pop("abstracts", {})

    for language, value in abstracts.items():
        klasa_bazowa.objects.create(
            rekord=ret,
            jezyk_streszczenia=Jezyk.objects.get(pbn_uid_id=language),
            streszczenie=value,
        )


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


@transaction.atomic
def importuj_artykul(mongoId, default_jednostka: Jednostka, client: PBNClient):
    try:
        pbn_publication = Publication.objects.get(pk=mongoId)
    except Publication.DoesNotExist:
        raise NotImplementedError(f"Publikacja {mongoId=} nie istnieje")

    ret = pbn_publication.rekord_w_bpp
    if ret is not None:
        return ret

    pbn_json = pbn_publication.current_version["object"]
    orig_pbn_json = copy.deepcopy(pbn_json)  # noqa

    pbn_zrodlo_id = pbn_json.pop("journal", {}).get("id", None)

    if pbn_zrodlo_id is None:
        zrodlo = Zrodlo.objects.get_or_create(
            nazwa="Brak źródła po stronie PBN",
            skrot="BPBN",
            rodzaj=Rodzaj_Zrodla.objects.get(nazwa="źródło nieindeksowane"),
        )[0]
    try:
        zrodlo = Zrodlo.objects.get(pbn_uid_id=pbn_zrodlo_id)
    except Zrodlo.DoesNotExist:
        res = client.get_journal_by_id(pbn_zrodlo_id)
        pbn_journal = zapisz_mongodb(res, Journal, client)
        dopisz_jedno_zrodlo(pbn_journal)
        zrodlo = Zrodlo.objects.get(pbn_uid_id=pbn_zrodlo_id)

    ret = Wydawnictwo_Ciagle(
        tytul_oryginalny=pbn_json.pop("title"),
        rok=pbn_json.pop("year"),
        public_www=pbn_json.pop("publicUri", None),
        jezyk=Jezyk.objects.get(pbn_uid_id=pbn_json.pop("mainLanguage")),
        strony=pbn_json.pop("pagesFromTo", None),
        tom=pbn_json.pop("volume", None),
        nr_zeszytu=pbn_json.pop("issue", None),
        doi=pbn_json.pop("doi", None),
        issn=zrodlo.issn,
        e_issn=zrodlo.e_issn,
        charakter_formalny=Charakter_Formalny.objects.get(
            nazwa="Artykuł w czasopismie"
        ),
        status_korekty=Status_Korekty.objects.get(nazwa="przed korektą"),
        zrodlo=zrodlo,
        pbn_uid=pbn_publication,
        typ_kbn=Typ_KBN.objects.get(nazwa="inne"),
    )
    importuj_openaccess(
        ret, pbn_json, klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Ciagle
    )
    try:
        ret.punkty_kbn = zrodlo.punktacja_zrodla_set.get(rok=ret.rok).punkty_kbn
    except Punktacja_Zrodla.DoesNotExist:
        print(
            f"Dla rekordu {ret=}, zrodlo {zrodlo=} nie ma punktacji za rok {ret.rok=}"
        )

    ret.save()

    utworz_autorow(ret, pbn_json, client, default_jednostka)

    pbn_json.pop("type")

    journalIssue = pbn_json.pop("journalIssue", {})
    if journalIssue:
        orig_journalIssue = copy.deepcopy(journalIssue)
        if str(journalIssue.pop("year", str(ret.rok))) != str(ret.rok):
            print(
                f"CZY TO PROBLEM? year rozny od ret.rok {ret.rok=}, {orig_journalIssue=} "
                f"{ret.tytul_oryginalny} {zrodlo.nazwa}"
            )
        if str(journalIssue.pop("publishedYear", str(ret.rok))) != str(ret.rok):
            print(
                f"CZY TO PROBLEM? publishedYear rozny od ret.rok {ret.rok=}, {orig_journalIssue=} "
                f"{ret.tytul_oryginalny} {zrodlo.nazwa}"
            )
        if "number" in journalIssue or "volume" in journalIssue:
            ret.adnotacje += "JournalIssue: " + str(journalIssue) + "\n"
            ret.save(update_fields=["adnotacje"])
            journalIssue.pop("number", "")
            journalIssue.pop("volume", "")
        journalIssue.pop("doi", None)
        assert_dictionary_empty(journalIssue)

    pbn_keywords = pbn_json.pop("keywords", {})
    pbn_keywords_pl = pbn_keywords_to_slowa_kluczowe(pbn_keywords, "pol")
    if pbn_keywords_pl:
        if len(pbn_keywords_pl) == 1:

            # hotfix...

            if (
                "pasze pasze lecznicze substancje przeciwbakteryjne antybiotyki antybiotykooporność zdrowie publiczne "
                "urzędowa kontrola" in pbn_keywords_pl
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

    pbn_keywords_en = pbn_keywords_to_slowa_kluczowe(pbn_keywords, "eng")
    if pbn_keywords_en:
        if len(pbn_keywords_en) == 1:
            if (
                "animal feed medicated feed antibacterial substances antibiotics antimicrobial resistance public "
                "health official controll" in pbn_keywords_en
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

    importuj_streszczenia(pbn_json, ret)

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

    if "titles" in pbn_json:
        titles = pbn_json.pop("titles")
        try:
            ret.tytul = titles.pop("eng")
        except KeyError:
            ret.tytul = titles.pop("pol")

        assert_dictionary_empty(titles)

    assert_dictionary_empty(pbn_json)
    return ret


def utworz_autorow(ret, pbn_json, client, default_jednostka):
    wyliczona_kolejnosc = 0

    afiliacje = pbn_json.pop("affiliations", {})

    pbn_kolejnosci = pbn_json.pop("orderList", {})

    typ_odpowiedzialnosci_autor = Typ_Odpowiedzialnosci.objects.get(nazwa="autor")
    typ_odpowiedzialnosci_redaktor = Typ_Odpowiedzialnosci.objects.get(nazwa="redaktor")

    for (
        pbn_typ_odpowiedzialnosci,
        pbn_klucz_slownika_autorow,
        typ_odpowiedzialnosci,
    ) in [
        ("EDITOR", "editors", typ_odpowiedzialnosci_redaktor),
        ("AUTHOR", "authors", typ_odpowiedzialnosci_autor),
    ]:
        for pbn_uid_autora, pbn_autor in pbn_json.pop(
            pbn_klucz_slownika_autorow, {}
        ).items():
            try:
                autor = Autor.objects.get(pbn_uid_id=pbn_uid_autora)
            except Autor.DoesNotExist:
                pbn_scientist = pobierz_i_zapisz_dane_jednej_osoby(
                    client=client, personId=pbn_uid_autora
                )

                if (
                    pbn_scientist.orcid
                    and Autor.objects.filter(orcid=pbn_scientist.orcid).exists()
                ):
                    print(
                        f"UWAGA Wiecej niz jeden autor w PBNie ma TEN SAM ORCID: {pbn_scientist.orcid=}"
                    )
                    print("ID autorow: ", pbn_scientist.pk, pbn_uid_autora)

                    autor = Autor.objects.get(orcid=pbn_scientist.orcid)
                else:
                    autor = utworz_wpis_dla_jednego_autora(pbn_scientist)

            jednostka = Uczelnia.objects.default.obca_jednostka
            afiliuje = False

            ta_afiliacja = afiliacje.pop(autor.pbn_uid_id, None)
            if ta_afiliacja is not None:
                if isinstance(ta_afiliacja, list) and len(ta_afiliacja) == 1:
                    ta_afiliacja = ta_afiliacja[0]
                else:
                    jest_nasz = False
                    typ_autora = ta_afiliacja[0]["type"]
                    if (
                        ta_afiliacja[0]["institutionId"]
                        == Uczelnia.objects.default.pbn_uid_id
                    ):
                        jest_nasz = True
                    for elem in ta_afiliacja[1:]:
                        if elem["type"] != typ_autora:
                            print(
                                f"UWAGA: autor w afiliacji {ret=} -- jako kilka roznych typow {ta_afiliacja=}"
                            )
                            continue

                        if elem["institutionId"] == Uczelnia.objects.default.pbn_uid_id:
                            jest_nasz = True

                    ta_afiliacja = {
                        "type": typ_autora,
                        "institutionId": (
                            Uczelnia.objects.default.pbn_uid_id if jest_nasz else "123"
                        ),
                    }

                pbn_typ_odpowiedzialnosci = ta_afiliacja.pop("type")
                if pbn_typ_odpowiedzialnosci == "AUTHOR":
                    typ_odpowiedzialnosci = typ_odpowiedzialnosci_autor
                elif pbn_typ_odpowiedzialnosci == "EDITOR":
                    typ_odpowiedzialnosci = typ_odpowiedzialnosci_redaktor
                else:
                    raise NotImplementedError(f"{pbn_typ_odpowiedzialnosci=}")

                pbn_institution_id = ta_afiliacja.pop("institutionId")

                if pbn_institution_id == Uczelnia.objects.default.pbn_uid_id:
                    jednostka = default_jednostka
                    afiliuje = True

                assert_dictionary_empty(ta_afiliacja)

            try:
                kolejnosc = pbn_kolejnosci.get(pbn_typ_odpowiedzialnosci, []).index(
                    autor.pbn_uid_id
                )
            except ValueError:
                kolejnosc = wyliczona_kolejnosc

            while ret.autorzy_set.filter(kolejnosc=kolejnosc).exists():
                kolejnosc += 1

            ret.autorzy_set.update_or_create(
                autor=autor,
                typ_odpowiedzialnosci=typ_odpowiedzialnosci,
                defaults=dict(
                    jednostka=jednostka,
                    kolejnosc=kolejnosc,
                    zapisany_jako=" ".join(
                        [pbn_autor.pop("lastName"), pbn_autor.pop("name")]
                    ),
                    afiliuje=afiliuje,
                ),
            )

            wyliczona_kolejnosc += 1

            assert_dictionary_empty(pbn_autor)

    assert_dictionary_empty(afiliacje, warn=True)


@transaction.atomic
def importuj_rozdzial(
    mongoId,
    default_jednostka: Jednostka,
    client: PBNClient,
):
    try:
        pbn_publication = Publication.objects.get(pk=mongoId)
    except Publication.DoesNotExist:
        raise NotImplementedError(f"Publikacja {mongoId=} nie istnieje")

    ret = pbn_publication.rekord_w_bpp

    if ret is not None:
        return ret

    pbn_json = pbn_publication.current_version["object"]
    orig_pbn_json = copy.deepcopy(pbn_json)  # noqa
    pbn_book_id = pbn_json.pop("book")["id"]
    try:
        wydawnictwo_nadrzedne = Wydawnictwo_Zwarte.objects.get(pbn_uid_id=pbn_book_id)
    except Wydawnictwo_Zwarte.DoesNotExist:
        wydawnictwo_nadrzedne = importuj_ksiazke(pbn_book_id, default_jednostka, client)

    rok = wydawnictwo_nadrzedne.rok

    try:
        pbn_chapter_json = wydawnictwo_nadrzedne.pbn_uid.current_version["object"].get(
            "chapters", {}
        )[mongoId]
    except KeyError:
        print(
            f"Brak informacji o rozdziale dla wyd nadrzednego {wydawnictwo_nadrzedne=}, rozdzial {pbn_publication=}"
        )
        pbn_chapter_json = {}
    pbn_chapter_json.pop("title", None)
    pbn_chapter_json.pop("titles", None)
    pbn_chapter_json.pop("type", None)

    if "abstracts" in pbn_chapter_json and "abstracts" in pbn_json:
        print(
            "ROZDZIAL I NADRZENED MA STRESZCZENIA, ale importuje tu rozdzial wiec ignoruje streszczenie nadrzednego"
        )
        pbn_json.pop("abstracts")

    pbn_wydawca_id = pbn_json.pop("publisher")["id"]
    try:
        wydawca = Wydawca.objects.get(pbn_uid_id=pbn_wydawca_id)
    except Wydawca.DoesNotExist:
        wydawca = sciagnij_i_zapisz_wydawce(pbn_wydawca_id, client)

    ret = Wydawnictwo_Zwarte(
        tytul_oryginalny=pbn_json.pop("title"),
        isbn=wydawnictwo_nadrzedne.isbn,
        rok=rok,
        strony=pbn_json.pop("pagesFromTo", pbn_chapter_json.pop("pagesFromTo", None)),
        public_www=pbn_chapter_json.pop("publicUri", pbn_json.pop("publicUri", None)),
        wydawca=wydawca,
        jezyk=Jezyk.objects.get(
            pbn_uid=pbn_json.pop(
                "mainLanguage", pbn_chapter_json.pop("mainLanguage", None)
            )
        ),
        doi=pbn_json.pop("doi", pbn_chapter_json.pop("doi", None)),
        # miejsce_i_rok=" ".join([pbn_json.pop("publicationPlace", ""), str(rok)]),
        pbn_uid=pbn_publication,
        charakter_formalny=Charakter_Formalny.objects.get(nazwa="Rozdział książki"),
        typ_kbn=Typ_KBN.objects.get(nazwa="inne"),
        status_korekty=Status_Korekty.objects.get(nazwa="przed korektą"),
    )

    if "titles" in pbn_json:
        titles = pbn_json.pop("titles")
        try:
            ret.tytul = titles.pop("eng")
        except KeyError:
            ret.tytul = titles.pop("pol")

        assert_dictionary_empty(titles)

    ret.save()

    # importuj_streszczenia(pbn_chapter_json, ret, Wydawnictwo_Zwarte_Streszczenie)
    importuj_streszczenia(pbn_chapter_json, ret, Wydawnictwo_Zwarte_Streszczenie)
    pbn_json.pop("abstracts", None)

    pbn_json.pop("keywords", None)
    pbn_keywords = pbn_chapter_json.pop("keywords", {})
    pbn_keywords_pl = pbn_keywords_to_slowa_kluczowe(pbn_keywords, "pol")
    if pbn_keywords_pl:
        ret.slowa_kluczowe.add(*(pbn_keywords_pl))

    pbn_keywords_en = pbn_keywords_to_slowa_kluczowe(pbn_keywords, "eng")
    if pbn_keywords_en:
        ret.slowa_kluczowe_eng = pbn_keywords_en

    assert_dictionary_empty(pbn_chapter_json)

    utworz_autorow(ret, pbn_json, client, default_jednostka)
    pbn_json.pop("type")
    assert_dictionary_empty(pbn_json)
    # afiliacje -> zawsze na instytucję... można zignorować
    # Box({'5e70923e878c28a0473924e9': [{'type': 'EDITOR', 'institutionId': '5e70918b878c28a04737debe'}]})

    # data['chapters'] -> rozdziały
    # Box({'5ec0070dad49b31cceda287a': {'doi': '', 'type': 'CHAPTER', 'title': 'Specjacja ...
    #  'mainLanguage': 'pol'}, '5ec0070dad49b31cceda287c': {'doi': '', 'type': 'CHAPTER', 'title': ...

    return ret


def importuj_openaccess(
    ret: ModelZOpenAccess,
    pbn_json,
    klasa_bazowa_tryb_dostepu=Tryb_OpenAccess_Wydawnictwo_Zwarte,
):
    oa_json = pbn_json.pop("openAccess", None)
    orig_oa_json = copy.deepcopy(oa_json)  # noqa
    if oa_json is not None:
        # ipdb> x.openAccess
        # Box({'mode': 'PUBLISHER_WEBSITE', 'license': 'OTHER', 'releaseDate': '2019-12-16T00:00:00.000Z',
        # 'textVersion': 'OTHER', 'releaseDateMode': 'AT_PUBLICATION'})
        pbn_licencja = oa_json.pop("license").replace("_", "-")
        try:
            ret.openaccess_licencja = Licencja_OpenAccess.objects.get(
                skrot=pbn_licencja
            )
        except Licencja_OpenAccess.DoesNotExist:
            raise ValueError(f"W BPP nie istnieje licancja {pbn_licencja=}")
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
        except Wersja_Tekstu_OpenAccess.DoesNotExist:
            raise NotImplementedError(
                f"W BPP nie istnieje wersja tekstu openaccess {pbn_wersja_tekstu=}"
            )

        months = oa_json.pop("months", None)
        if months:
            ret.openaccess_ilosc_miesiecy = months

        reldate = oa_json.pop("releaseDate", None)
        if reldate:
            reldate = reldate.split("T")[0]
            ret.openaccess_data_opublikowania = reldate

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


def sciagnij_i_zapisz_wydawce(pbn_wydawca_id, client):
    res = client.get_publisher_by_id(pbn_wydawca_id)
    publisher = zapisz_mongodb(res, Publisher)
    importuj_jednego_wydawce(publisher)
    return Wydawca.objects.get(pbn_uid_id=pbn_wydawca_id)


# def importuj_autorow(pbn_orderList, pbn_json, afiliacje, ret):
#     kolejnosc = 0
#
#     if not pbn_orderList and (pbn_json["editors"] or pbn_json["authors"]):
#         pbn_orderList = []
#         if pbn_json.get("editors"):
#             pbn_orderList = ["EDITOR"]
#         if pbn_json.get("authors"):
#             pbn_orderList = ["AUTHOR"]
#
#     for pbn_rodzaj_autora in pbn_orderList:
#         # data['orderList'] -> kolejnosc
#         # Box({'EDITOR': ['5e70923e878c28a0473924asdf', '5e70926c878c28a0473955zz', ...
#         # data['editors'] -> redaktorzy
#         # Box({'5e7091f9878c28a04738dasd': {'name': 'IZABELA', 'lastName': 'X'}, ...
#         match pbn_rodzaj_autora:
#             case "EDITOR":
#                 klucz_json_obiektu = "editors"
#             case "AUTHOR":
#                 klucz_json_obiektu = "authors"
#             case _:
#                 raise NotImplementedError(
#                     f"Nie wiem, jak obsłużyć {pbn_rodzaj_autora=}"
#                 )
#
#         for pbn_uid_autora, pbn_autor in pbn_json.pop(klucz_json_obiektu).items():
#             try:
#                 autor = Autor.objects.get(pbn_uid_id=pbn_uid_autora)
#             except Autor.DoesNotExist:
#                 pbn_scientist = pobierz_i_zapisz_dane_jednej_osoby(
#                     client=client, personId=pbn_uid_autora
#                 )
#
#                 if (
#                     pbn_scientist.orcid
#                     and Autor.objects.filter(orcid=pbn_scientist.orcid).exists()
#                 ):
#                     print(
#                         f"UWAGA Wiecej niz jeden autor w PBNie ma TEN SAM ORCID: {pbn_scientist.orcid=}"
#                     )
#                     print("ID autorow: ", pbn_scientist.pk, pbn_uid_autora)
#
#                     autor = Autor.objects.get(orcid=pbn_scientist.orcid)
#                 else:
#                     autor = utworz_wpis_dla_jednego_autora(pbn_scientist)
#
#             jednostka = Uczelnia.objects.default.obca_jednostka
#             afiliuje = False
#
#             if pbn_rodzaj_autora == "AUTHOR":
#                 typ_odpowiedzialnosci_nazwa = "autor"
#             elif pbn_rodzaj_autora == "EDITOR":
#                 typ_odpowiedzialnosci_nazwa = "redaktor"
#
#             ta_afiliacja = afiliacje.pop(autor.pbn_uid_id, None)
#
#             if ta_afiliacja is not None:
#
#                 # Weź tylko afiliacje dla obecnie analizowanego typu (autorzy, redaktorzy)
#                 fnd = False
#                 for _ in ta_afiliacja:
#                     if _.get("type") == pbn_rodzaj_autora:
#                         ta_afiliacja = _
#                         fnd = True
#                         break
#
#                 assert (
#                     fnd
#                 ), f"Nie znaleziono w ['affiliations'] kluicza dla obecnego {pbn_rodzaj_autora=}"
#
#                 typ = ta_afiliacja.pop("type")
#                 if typ == "AUTHOR":
#                     typ_odpowiedzialnosci_nazwa = "autor"
#                 elif typ == "EDITOR":
#                     typ_odpowiedzialnosci_nazwa = "redaktor"
#                 else:
#                     raise NotImplementedError(f"Nie wiem {typ=}")
#
#                 pbn_institution_id = ta_afiliacja.pop("institutionId")
#                 if pbn_institution_id == Uczelnia.objects.get_default().pbn_uid_id:
#                     print(
#                         f"Publikacja {pbn_publication=} ma afiliację na obce uczelnie {ta_afiliacja=}"
#                     )
#                     continue
#
#                 assert_dictionary_empty(ta_afiliacja)
#
#                 if pbn_institution_id == Uczelnia.objects.default.pbn_uid_id:
#                     jednostka = default_jednostka
#                     afiliuje = True
#
#             ret.autorzy_set.create(
#                 autor=autor,
#                 jednostka=jednostka,
#                 typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(
#                     nazwa=typ_odpowiedzialnosci_nazwa
#                 ),
#                 kolejnosc=kolejnosc,
#                 zapisany_jako=" ".join(
#                     [pbn_autor.pop("lastName"), pbn_autor.pop("name")]
#                 ),
#                 afiliuje=afiliuje,
#             )
#             kolejnosc += 1
#
#             assert_dictionary_empty(pbn_autor)
#


@transaction.atomic
def importuj_ksiazke(mongoId, default_jednostka: Jednostka, client: PBNClient):
    try:
        pbn_publication = Publication.objects.get(pk=mongoId)
    except Publication.DoesNotExist:
        res = client.get_publication_by_id(mongoId)
        zapisz_mongodb(res, Publication)
        pbn_publication = Publication.objects.get(pk=mongoId)

    ret = pbn_publication.rekord_w_bpp

    if ret is not None:
        return ret

    pbn_json = pbn_publication.current_version["object"]
    orig_pbn_json = copy.deepcopy(pbn_json)  # noqa
    rok = pbn_json.pop("year", None)

    pbn_wydawca_id = pbn_json.pop("publisher")["id"]
    try:
        wydawca = Wydawca.objects.get(pbn_uid_id=pbn_wydawca_id)
    except Wydawca.DoesNotExist:
        wydawca = sciagnij_i_zapisz_wydawce(pbn_wydawca_id, client)

    jezyk = Jezyk.objects.get(pbn_uid_id=pbn_json.pop("mainLanguage"))
    ret = Wydawnictwo_Zwarte(
        tytul_oryginalny=pbn_json.pop("title"),
        isbn=pbn_json.pop("isbn", None),
        rok=rok,
        strony=pbn_json.pop("pages", None),
        public_www=pbn_json.pop("publicUri", None),
        wydawca=wydawca,
        jezyk=jezyk,
        miejsce_i_rok=" ".join([pbn_json.pop("publicationPlace", ""), str(rok)]),
        pbn_uid=pbn_publication,
        charakter_formalny=Charakter_Formalny.objects.get(nazwa="Książka"),
        typ_kbn=Typ_KBN.objects.get(nazwa="inne"),
        status_korekty=Status_Korekty.objects.get(nazwa="przed korektą"),
    )

    importuj_openaccess(ret, pbn_json)

    ret.save()

    # pbn_orderList = pbn_json.pop("orderList", {})
    # afiliacje = pbn_json.pop("affiliations", {})

    # importuj_autorow(pbn_orderList, pbn_json, afiliacje, ret)
    utworz_autorow(ret, pbn_json, client, default_jednostka)

    # afiliacje -> zawsze na instytucję... można zignorować
    # Box({'5e70923e878c28a0473924e9': [{'type': 'EDITOR', 'institutionId': '5e70918b878c28a04737debe'}]})

    # data['chapters'] -> rozdziały
    # Box({'5ec0070dad49b31cceda287a': {'doi': '', 'type': 'CHAPTER', 'title': 'Specjacja ...
    #  'mainLanguage': 'pol'}, '5ec0070dad49b31cceda287c': {'doi': '', 'type': 'CHAPTER', 'title': ...

    pbn_json.pop("chapters", None)

    return ret


def importuj_publikacje_instytucji(
    client: PBNClient, default_jednostka: Jednostka, pbn_uid_id=None
):
    niechciane = list(Rekord.objects.values_list("pbn_uid_id", flat=True))
    chciane = Publication.objects.all().exclude(pk__in=niechciane)

    if pbn_uid_id:
        chciane = chciane.filter(pk=pbn_uid_id)

    for pbn_publication in tqdm(chciane):
        cv = pbn_publication.current_version

        # XXX: TODO:traktowac slownik 'authors' czy 'affiliations' jako ORDERED DICT
        match cv["object"].pop("type"):
            case "BOOK":
                ret = importuj_ksiazke(
                    pbn_publication.pk,
                    default_jednostka=default_jednostka,
                    client=client,
                )
            case "EDITED_BOOK":
                ret = importuj_ksiazke(
                    pbn_publication.pk,
                    default_jednostka=default_jednostka,
                    client=client,
                )
            case "CHAPTER":
                ret = importuj_ksiazke(
                    cv["object"]["book"]["id"],
                    default_jednostka=default_jednostka,
                    client=client,
                )

                ret = importuj_rozdzial(
                    pbn_publication.pk,
                    default_jednostka=default_jednostka,
                    client=client,
                )

            case "ARTICLE":
                # maybe = client.get_publication_by_id(pbn_publication.pk)
                ret = importuj_artykul(
                    pbn_publication.pk,
                    default_jednostka=default_jednostka,
                    client=client,
                )
            case _:
                raise NotImplementedError(f"Nie obsluze {cv['object']['type']}")

        if pbn_uid_id:
            return ret
