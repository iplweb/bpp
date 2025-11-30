"""Book chapter import for PBN importer."""

import copy

from django.db import transaction

from bpp.models import (
    Charakter_Formalny,
    Jednostka,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Wydawca,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Streszczenie,
)
from pbn_api.client import PBNClient
from pbn_api.models import Publication

from .authors import utworz_autorow
from .books import importuj_ksiazke
from .helpers import (
    assert_dictionary_empty,
    importuj_streszczenia,
    pbn_keywords_to_slowa_kluczowe,
    przetworz_slowa_kluczowe,
)
from .publishers import sciagnij_i_zapisz_wydawce


@transaction.atomic
def importuj_rozdzial(
    mongoId,
    default_jednostka: Jednostka,
    client: PBNClient,
    force=False,
):
    """Importuje rozdział z PBN do BPP jako Wydawnictwo_Zwarte z wydawnictwem nadrzędnym.

    Args:
        mongoId: Identyfikator publikacji w MongoDB
        default_jednostka: Domyślna jednostka dla autorów
        client: Klient PBN API
        force: Jeśli True, tworzy nowy rekord nawet jeśli publikacja
               z tym pbn_uid_id już istnieje w BPP
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
    pbn_book_id = pbn_json.pop("book")["id"]
    try:
        wydawnictwo_nadrzedne = Wydawnictwo_Zwarte.objects.get(pbn_uid_id=pbn_book_id)
    except Wydawnictwo_Zwarte.DoesNotExist:
        wydawnictwo_nadrzedne = importuj_ksiazke(
            pbn_book_id, default_jednostka, client, force=force
        )

    rok = wydawnictwo_nadrzedne.rok

    try:
        pbn_chapter_json = wydawnictwo_nadrzedne.pbn_uid.current_version["object"].get(
            "chapters", {}
        )[mongoId]
    except KeyError:
        print(
            f"Brak informacji o rozdziale dla wyd nadrzednego "
            f"{wydawnictwo_nadrzedne=}, rozdzial {pbn_publication=}"
        )
        pbn_chapter_json = {}
    pbn_chapter_json.pop("title", None)
    pbn_chapter_json.pop("titles", None)
    pbn_chapter_json.pop("type", None)

    if "abstracts" in pbn_chapter_json and "abstracts" in pbn_json:
        print(
            "ROZDZIAL I NADRZENED MA STRESZCZENIA, ale importuje tu rozdzial "
            "wiec ignoruje streszczenie nadrzednego"
        )
        pbn_json.pop("abstracts")

    pbn_wydawca_id = pbn_json.pop("publisher")["id"]
    try:
        wydawca = Wydawca.objects.get(pbn_uid_id=pbn_wydawca_id)
    except Wydawca.DoesNotExist:
        wydawca = sciagnij_i_zapisz_wydawce(pbn_wydawca_id, client)

    if not isinstance(wydawnictwo_nadrzedne, Wydawnictwo_Zwarte):
        wydawnictwo_nadrzedne = wydawnictwo_nadrzedne.original

    ret = Wydawnictwo_Zwarte(
        tytul_oryginalny=pbn_json.pop("title"),
        isbn=wydawnictwo_nadrzedne.isbn,
        rok=rok,
        strony=pbn_json.pop("pagesFromTo", pbn_chapter_json.pop("pagesFromTo", None)),
        public_www=pbn_chapter_json.pop("publicUri", pbn_json.pop("publicUri", None)),
        wydawca=wydawca,
        wydawnictwo_nadrzedne=wydawnictwo_nadrzedne,
        jezyk=Jezyk.objects.get(
            pbn_uid=pbn_json.pop(
                "mainLanguage", pbn_chapter_json.pop("mainLanguage", None)
            )
        ),
        doi=pbn_json.pop("doi", pbn_chapter_json.pop("doi", None)),
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

    importuj_streszczenia(pbn_chapter_json, ret, Wydawnictwo_Zwarte_Streszczenie)
    pbn_json.pop("abstracts", None)

    pbn_json.pop("keywords", None)
    pbn_keywords = pbn_chapter_json.pop("keywords", {})
    pbn_keywords_pl = pbn_keywords_to_slowa_kluczowe(pbn_keywords, "pol")
    pbn_keywords_en = pbn_keywords_to_slowa_kluczowe(pbn_keywords, "eng")
    przetworz_slowa_kluczowe(pbn_keywords_pl, pbn_keywords_en, ret)

    assert_dictionary_empty(pbn_chapter_json)

    utworz_autorow(ret, pbn_json, client, default_jednostka)
    pbn_json.pop("type")
    assert_dictionary_empty(pbn_json)

    return ret
