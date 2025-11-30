"""Book import for PBN importer."""

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
)
from pbn_api.client import PBNClient

from .authors import utworz_autorow
from .helpers import get_or_download_publication, importuj_openaccess
from .publishers import sciagnij_i_zapisz_wydawce


@transaction.atomic
def importuj_ksiazke(
    mongoId, default_jednostka: Jednostka, client: PBNClient, force=False
):
    """Importuje książkę z PBN do BPP jako Wydawnictwo_Zwarte.

    Args:
        mongoId: Identyfikator publikacji w MongoDB
        default_jednostka: Domyślna jednostka dla autorów
        client: Klient PBN API
        force: Jeśli True, tworzy nowy rekord nawet jeśli publikacja
               z tym pbn_uid_id już istnieje w BPP
    """
    pbn_publication = get_or_download_publication(mongoId, client)

    ret = pbn_publication.rekord_w_bpp

    if ret is not None and not force:
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

    utworz_autorow(ret, pbn_json, client, default_jednostka)

    # data['chapters'] -> rozdziały
    pbn_json.pop("chapters", None)

    return ret
