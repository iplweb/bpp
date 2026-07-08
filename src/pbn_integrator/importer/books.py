"""Book import for PBN importer."""

import copy
import logging

from django.db import transaction

from bpp.models import (
    Jednostka,
    Jezyk,
    Wydawca,
    Wydawnictwo_Zwarte,
)
from pbn_api.client import PBNClient

from .authors import utworz_autorow
from .cache import (
    get_charakter_formalny_ksiazka,
    get_status_korekty_przed,
    get_typ_kbn_inne,
)
from .helpers import (
    get_or_download_publication,
    importuj_openaccess,
    pobierz_jezyk,
    ustaw_jezyk_oryginalny,
)
from .publishers import sciagnij_i_zapisz_wydawce

logger = logging.getLogger(__name__)


@transaction.atomic
def importuj_ksiazke(
    mongoId,
    default_jednostka: Jednostka,
    client: PBNClient,
    force=False,
    inconsistency_callback=None,
    domyslny_jezyk: Jezyk = None,
):
    """Importuje książkę z PBN do BPP jako Wydawnictwo_Zwarte.

    Args:
        mongoId: Identyfikator publikacji w MongoDB
        default_jednostka: Domyślna jednostka dla autorów
        client: Klient PBN API
        force: Jeśli True, tworzy nowy rekord nawet jeśli publikacja
               z tym pbn_uid_id już istnieje w BPP
        domyslny_jezyk: Język użyty, gdy PBN nie poda języka publikacji albo
               poda kod nieobecny w słowniku ``Jezyk`` (domyślnie: polski).
    """
    pbn_publication = get_or_download_publication(mongoId, client)

    # Bramka minimum-viable-record także dla KSIĄŻKI NADRZĘDNEJ rozdziału:
    # dispatch woła importuj_ksiazke(book_id) dla rodzica, który sam bywa
    # rekordem-widmem (versions=[]). Bez tego guardu ``current_version["object"]``
    # niżej wywala się ``TypeError`` na ``None`` i (w ścieżce bez per-rekordowego
    # try/except) zabija cały wsad.
    if pbn_publication.current_version is None:
        logger.warning(
            "Pomijam książkę PBN %s: brak wersji bieżącej (rekord-widmo).", mongoId
        )
        return None

    ret = pbn_publication.rekord_w_bpp

    if ret is not None and not force:
        return ret

    pbn_json = pbn_publication.current_version["object"]
    orig_pbn_json = copy.deepcopy(pbn_json)  # noqa
    rok = pbn_json.pop("year", None)

    # PBN bywa niekompletny — niektóre książki nie mają wydawcy. Pole ``wydawca``
    # jest nullable, więc zamiast wywalać import (KeyError) zapisujemy bez wydawcy.
    pbn_wydawca = pbn_json.pop("publisher", None)
    if pbn_wydawca is not None:
        pbn_wydawca_id = pbn_wydawca["id"]
        try:
            wydawca = Wydawca.objects.get(pbn_uid_id=pbn_wydawca_id)
        except Wydawca.DoesNotExist:
            wydawca = sciagnij_i_zapisz_wydawce(pbn_wydawca_id, client)
    else:
        wydawca = None

    jezyk = pobierz_jezyk(
        pbn_json.pop("mainLanguage", None), pbn_json.get("title"), domyslny_jezyk
    )
    ret = Wydawnictwo_Zwarte(
        tytul_oryginalny=pbn_json.pop("title"),
        isbn=pbn_json.pop("isbn", None) or "",
        rok=rok,
        strony=pbn_json.pop("pages", None) or "",
        public_www=pbn_json.pop("publicUri", None) or "",
        wydawca=wydawca,
        jezyk=jezyk,
        miejsce_i_rok=" ".join([pbn_json.pop("publicationPlace", ""), str(rok)]),
        pbn_uid=pbn_publication,
        charakter_formalny=get_charakter_formalny_ksiazka(),
        typ_kbn=get_typ_kbn_inne(),
        status_korekty=get_status_korekty_przed(),
    )

    importuj_openaccess(ret, pbn_json)
    ustaw_jezyk_oryginalny(ret, pbn_json)

    ret.save()

    utworz_autorow(ret, pbn_json, client, default_jednostka, inconsistency_callback)

    # data['chapters'] -> rozdziały
    pbn_json.pop("chapters", None)

    return ret
