"""Book chapter import for PBN importer."""

import copy
import logging

from django.db import transaction

from bpp.models import (
    Jednostka,
    Jezyk,
    Wydawca,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Streszczenie,
    Wydawnictwo_Zwarte_Tytul,
)
from pbn_api.client import PBNClient
from pbn_api.models import Publication

from .authors import utworz_autorow
from .books import importuj_ksiazke
from .cache import (
    get_charakter_formalny_rozdzial,
    get_status_korekty_przed,
    get_typ_kbn_inne,
)
from .helpers import (
    importuj_streszczenia,
    pbn_keywords_to_slowa_kluczowe,
    pobierz_jezyk,
    przetworz_slowa_kluczowe,
    przetworz_tytuly,
    skonsumuj_nieobsluzone_klucze,
)
from .publishers import sciagnij_i_zapisz_wydawce

logger = logging.getLogger(__name__)


def _chapter_json_z_nadrzednego(wydawnictwo_nadrzedne, mongoId):
    """Zwraca sub-słownik rozdziału z ``chapters`` wyd. nadrzędnego albo ``{}``.

    Wyd. nadrzędne bywa dopasowane do istniejącego rekordu BPP bez powiązania z
    PBN (fuzzy match → ``pbn_uid is None``) albo bez wersji bieżącej — wtedy nie
    ma skąd wziąć metadanych rozdziału. To NIE błąd rozdziału (Rollbar #419:
    ``'NoneType' object has no attribute 'current_version'``), więc zamiast
    wywalać import zwracamy pusty słownik — rozdział wejdzie z metadanych
    własnych.
    """
    parent_pbn = getattr(wydawnictwo_nadrzedne, "pbn_uid", None)
    parent_cv = getattr(parent_pbn, "current_version", None)
    if parent_cv is None:
        return {}
    try:
        return parent_cv["object"].get("chapters", {})[mongoId]
    except KeyError:
        logger.info(
            "Brak informacji o rozdziale %s dla wyd nadrzednego %r",
            mongoId,
            wydawnictwo_nadrzedne,
        )
        return {}


@transaction.atomic
def importuj_rozdzial(
    mongoId,
    default_jednostka: Jednostka,
    client: PBNClient,
    force=False,
    inconsistency_callback=None,
    domyslny_jezyk: Jezyk = None,
):
    """Importuje rozdział z PBN do BPP jako Wydawnictwo_Zwarte z wydawnictwem nadrzędnym.

    Args:
        mongoId: Identyfikator publikacji w MongoDB
        default_jednostka: Domyślna jednostka dla autorów
        client: Klient PBN API
        force: Jeśli True, tworzy nowy rekord nawet jeśli publikacja
               z tym pbn_uid_id już istnieje w BPP
        domyslny_jezyk: Język użyty, gdy PBN nie poda języka rozdziału albo
               poda kod nieobecny w słowniku ``Jezyk`` (domyślnie: polski).
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
            pbn_book_id,
            default_jednostka,
            client,
            force=force,
            inconsistency_callback=inconsistency_callback,
        )

    if wydawnictwo_nadrzedne is None or isinstance(wydawnictwo_nadrzedne, str):
        # importuj_ksiazke zwraca None dla widma nadrzędnego (jego własny guard)
        # albo STRING, gdy ``rekord_w_bpp`` trafił na zdublowane rekordy BPP
        # (Rekord.MultipleObjectsReturned → join tytułów). W obu wypadkach książki
        # nadrzędnej nie da się jednoznacznie powiązać — pomijamy rozdział zamiast
        # wywalać się na ``.rok`` / dereferencji ``None`` (dokończenie #419).
        logger.warning(
            "Pomijam rozdział PBN %s: książka nadrzędna %s nierozstrzygalna (%s).",
            mongoId,
            pbn_book_id,
            "brak/widmo" if wydawnictwo_nadrzedne is None else "wiele dopasowań w BPP",
        )
        return None

    rok = wydawnictwo_nadrzedne.rok

    pbn_chapter_json = _chapter_json_z_nadrzednego(wydawnictwo_nadrzedne, mongoId)
    pbn_chapter_json.pop("title", None)
    pbn_chapter_json.pop("titles", None)
    pbn_chapter_json.pop("type", None)
    # Sub-słownik rozdziału w ``chapters`` nadrzędnego duplikuje metadane, które
    # bierzemy skądinąd: ``year`` (rok z wyd. nadrzędnego), ``originalLanguage``
    # (język bierzemy z ``mainLanguage``). Konsumujemy je, by tripwire
    # ``assert_dictionary_empty`` nie wywalił importu na redundantnych kluczach.
    pbn_chapter_json.pop("year", None)
    pbn_chapter_json.pop("originalLanguage", None)

    if "abstracts" in pbn_chapter_json and "abstracts" in pbn_json:
        print(
            "ROZDZIAL I NADRZENED MA STRESZCZENIA, ale importuje tu rozdzial "
            "wiec ignoruje streszczenie nadrzednego"
        )
        pbn_json.pop("abstracts")

    # Jak w książkach: brak wydawcy w PBN nie może wywalić importu (pole nullable).
    pbn_wydawca = pbn_json.pop("publisher", None)
    if pbn_wydawca is not None:
        pbn_wydawca_id = pbn_wydawca["id"]
        try:
            wydawca = Wydawca.objects.get(pbn_uid_id=pbn_wydawca_id)
        except Wydawca.DoesNotExist:
            wydawca = sciagnij_i_zapisz_wydawce(pbn_wydawca_id, client)
    else:
        wydawca = None

    if not isinstance(wydawnictwo_nadrzedne, Wydawnictwo_Zwarte):
        wydawnictwo_nadrzedne = wydawnictwo_nadrzedne.original

    ret = Wydawnictwo_Zwarte(
        tytul_oryginalny=pbn_json.pop("title"),
        isbn=wydawnictwo_nadrzedne.isbn,
        rok=rok,
        strony=pbn_json.pop("pagesFromTo", pbn_chapter_json.pop("pagesFromTo", None))
        or "",
        public_www=pbn_chapter_json.pop("publicUri", pbn_json.pop("publicUri", None))
        or "",
        wydawca=wydawca,
        wydawnictwo_nadrzedne=wydawnictwo_nadrzedne,
        jezyk=pobierz_jezyk(
            pbn_json.pop("mainLanguage", pbn_chapter_json.pop("mainLanguage", None)),
            pbn_json.get("title"),
            domyslny_jezyk,
        ),
        doi=pbn_json.pop("doi", pbn_chapter_json.pop("doi", None)),
        pbn_uid=pbn_publication,
        charakter_formalny=get_charakter_formalny_rozdzial(),
        typ_kbn=get_typ_kbn_inne(),
        status_korekty=get_status_korekty_przed(),
    )

    ret.save()

    przetworz_tytuly(pbn_json, ret, Wydawnictwo_Zwarte_Tytul)

    importuj_streszczenia(pbn_chapter_json, ret, Wydawnictwo_Zwarte_Streszczenie)
    pbn_json.pop("abstracts", None)

    pbn_json.pop("keywords", None)
    pbn_keywords = pbn_chapter_json.pop("keywords", {})
    pbn_keywords_pl = pbn_keywords_to_slowa_kluczowe(pbn_keywords, "pol")
    pbn_keywords_en = pbn_keywords_to_slowa_kluczowe(pbn_keywords, "eng")
    przetworz_slowa_kluczowe(pbn_keywords_pl, pbn_keywords_en, ret)

    skonsumuj_nieobsluzone_klucze(
        pbn_chapter_json, ret, kontekst="rozdział (sub-dict nadrzędnego)"
    )

    utworz_autorow(ret, pbn_json, client, default_jednostka, inconsistency_callback)
    pbn_json.pop("type", None)
    skonsumuj_nieobsluzone_klucze(pbn_json, ret, kontekst="rozdział")

    return ret
