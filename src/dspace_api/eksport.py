import logging
import traceback

from dspace_api.adapters import adapter_for
from dspace_api.client import DSpaceClient
from dspace_api.models import Mapowanie_DSpace, SentToDSpace
from dspace_api.selectors import jawne_pliki_rekordu, uczelnie_rekordu

logger = logging.getLogger(__name__)


def eksportuj_rekord(rec):
    """Wachlarz: wyślij rekord do DSpace każdej afiliowanej, skonfigurowanej
    uczelni. Zwraca listę wyników per uczelnia (do raportu w UI/logu)."""
    wyniki = []
    for uczelnia in uczelnie_rekordu(rec):
        wyniki.append(_eksportuj_do_uczelni(rec, uczelnia))
    return wyniki


def _wynik(uczelnia, status, powod=""):
    return {"uczelnia": uczelnia, "status": status, "powod": powod}


def _reconcile_bitstreams(client, item_uuid, aktualne, biezace):
    """Uzgodnij bitstreamy. Mutuje `biezace` (mapa str(id)→uuid) W MIEJSCU,
    żeby stan był znany nawet przy częściowej awarii.
    - nowe pliki (aktualne − biezace) → upload,
    - usunięte (biezace − aktualne) → delete w DSpace, potem usuń z mapy
      (gdy delete padnie, klucz zostaje → następny sync ponowi)."""
    do_uploadu = set(aktualne) - set(biezace)
    if do_uploadu:
        bundle = client.ensure_bundle(item_uuid, "ORIGINAL")
        # deterministyczna kolejność (po id rosnąco) — żeby przy częściowej
        # awarii było jednoznaczne, co zdążyło się wgrać przed błędem
        for el_id in sorted(do_uploadu, key=int):
            biezace[el_id] = client.create_bitstream(bundle, aktualne[el_id])
    for el_id in sorted(set(biezace) - set(aktualne), key=int):
        client.delete_bitstream(biezace[el_id])
        del biezace[el_id]


def _backfill_handle(client, item_uuid, handle):
    """Handle to dodatek (link do repozytorium), nie krytyczny element synchro.
    Gdy go nie znamy (stary rekord / aktualizacja bez zapisanego handle),
    próbujemy go doczytać — ale błąd nie może wywrócić wysyłki."""
    if handle or not item_uuid:
        return handle
    try:
        return client.fetch_handle(item_uuid) or ""
    except Exception:
        logger.warning(
            "DSpace: nie udało się pobrać handle dla itemu %s", item_uuid, exc_info=True
        )
        return ""


def _eksportuj_do_uczelni(rec, uczelnia):
    if not uczelnia.dspace_aktywny or not uczelnia.dspace_api_endpoint:
        return _wynik(uczelnia, "pominieto", "brak/nieaktywna konfiguracja DSpace")

    try:
        mapowanie = Mapowanie_DSpace.objects.get(
            uczelnia=uczelnia, charakter_formalny=rec.charakter_formalny
        )
    except Mapowanie_DSpace.DoesNotExist:
        return _wynik(
            uczelnia,
            "pominieto",
            f"charakter '{rec.charakter_formalny}' bez mapowania DSpace",
        )
    except AttributeError:
        return _wynik(uczelnia, "pominieto", "rekord bez charakteru formalnego")

    dc = adapter_for(
        rec, domyslny_jezyk=uczelnia.dspace_domyslny_jezyk_dc or "pl"
    ).to_dspace_dict()
    aktualne = {str(el.id): el for el in jawne_pliki_rekordu(rec)}

    if not SentToDSpace.objects.check_if_upload_needed(
        rec, uczelnia, dc, bitstream_ids=list(aktualne)
    ):
        return _wynik(uczelnia, "bez_zmian", "dane bez zmian")

    try:
        sent = SentToDSpace.objects.get_for_rec(rec, uczelnia)
        istnieje_uuid = sent.dspace_uuid
        poprzednie = dict(sent.bitstreams)
        poprzedni_handle = sent.dspace_handle
    except SentToDSpace.DoesNotExist:
        istnieje_uuid = None
        poprzednie = {}
        poprzedni_handle = ""

    SentToDSpace.objects.create_or_update_before_upload(rec, uczelnia, dc)

    biezace = dict(poprzednie)
    try:
        client = DSpaceClient(uczelnia)
        client.authenticate()
        if istnieje_uuid:
            client.patch_item(istnieje_uuid, dc)
            item_uuid, status = istnieje_uuid, "zaktualizowano"
            handle = poprzedni_handle
        else:
            item_uuid, handle = client.create_item(mapowanie.collection_uuid, dc)
            status = "wyslano"
        handle = _backfill_handle(client, item_uuid, handle)
        _reconcile_bitstreams(client, item_uuid, aktualne, biezace)
        SentToDSpace.objects.mark_as_successful(
            rec,
            uczelnia,
            dspace_uuid=item_uuid,
            dspace_handle=handle,
            bitstreams=biezace,
        )
        return _wynik(uczelnia, status)
    except Exception as e:
        SentToDSpace.objects.mark_as_failed(
            rec, uczelnia, exception=traceback.format_exc(), bitstreams=biezace
        )
        return _wynik(uczelnia, "blad", str(e))
