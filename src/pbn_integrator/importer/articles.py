"""Journal article import for PBN importer."""

import copy

from django.db import transaction

from bpp.models import (
    Charakter_Formalny,
    Jednostka,
    Punktacja_Zrodla,
    Status_Korekty,
    Tryb_OpenAccess_Wydawnictwo_Ciagle,
    Typ_KBN,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Streszczenie,
)
from pbn_api.client import PBNClient
from pbn_api.models import Publication

from .authors import utworz_autorow
from .helpers import (
    assert_dictionary_empty,
    importuj_openaccess,
    importuj_streszczenia,
    pbn_keywords_to_slowa_kluczowe,
    pobierz_jezyk,
    pobierz_lub_utworz_zrodlo,
    przetworz_journal_issue,
    przetworz_metadane_konferencji,
    przetworz_slowa_kluczowe,
)


@transaction.atomic
def importuj_artykul(
    mongoId,
    default_jednostka: Jednostka,
    client: PBNClient,
    force=False,
    rodzaj_periodyk=None,
    dyscypliny_cache=None,
):
    """Importuje artykuł z PBN do BPP jako Wydawnictwo_Ciagle.

    Args:
        mongoId: Identyfikator publikacji w MongoDB
        default_jednostka: Domyślna jednostka dla autorów
        client: Klient PBN API
        force: Jeśli True, tworzy nowy rekord nawet jeśli publikacja
               z tym pbn_uid_id już istnieje w BPP
        rodzaj_periodyk: Optional Rodzaj_Zrodla instance for "periodyk"
        dyscypliny_cache: Optional dict mapping discipline names to objects
    """
    try:
        pbn_publication = Publication.objects.get(pk=mongoId)
    except Publication.DoesNotExist as err:
        raise NotImplementedError(f"Publikacja {mongoId=} nie istnieje") from err

    ret = pbn_publication.rekord_w_bpp
    if ret is not None and not force:
        return ret

    pbn_json = pbn_publication.current_version["object"]
    orig_pbn_json = copy.deepcopy(pbn_json)  # noqa

    pbn_zrodlo_id = pbn_json.pop("journal", {}).get("id", None)
    zrodlo = pobierz_lub_utworz_zrodlo(
        pbn_zrodlo_id, client, rodzaj_periodyk, dyscypliny_cache
    )

    mainLanguage = pbn_json.pop("mainLanguage")
    jezyk = pobierz_jezyk(mainLanguage, pbn_json.get("title"))

    ret = Wydawnictwo_Ciagle(
        tytul_oryginalny=pbn_json.pop("title"),
        rok=pbn_json.pop("year"),
        public_www=pbn_json.pop("publicUri", None) or "",
        jezyk=jezyk,
        strony=pbn_json.pop("pagesFromTo", None) or "",
        tom=pbn_json.pop("volume", None) or "",
        nr_zeszytu=pbn_json.pop("issue", None) or "",
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

    przetworz_journal_issue(pbn_json, ret, zrodlo)

    pbn_keywords = pbn_json.pop("keywords", {})
    pbn_keywords_pl = pbn_keywords_to_slowa_kluczowe(pbn_keywords, "pol")
    pbn_keywords_en = pbn_keywords_to_slowa_kluczowe(pbn_keywords, "eng")
    przetworz_slowa_kluczowe(pbn_keywords_pl, pbn_keywords_en, ret)

    importuj_streszczenia(pbn_json, ret, Wydawnictwo_Ciagle_Streszczenie)

    przetworz_metadane_konferencji(pbn_json, ret)

    if "titles" in pbn_json:
        titles = pbn_json.pop("titles")
        try:
            ret.tytul = titles.pop("eng")
        except KeyError:
            ret.tytul = titles.pop("pol")

        assert_dictionary_empty(titles)

    assert_dictionary_empty(pbn_json)
    return ret
