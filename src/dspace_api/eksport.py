import traceback

from dspace_api.adapters import adapter_for
from dspace_api.client import DSpaceClient
from dspace_api.models import Mapowanie_DSpace, SentToDSpace
from dspace_api.selectors import uczelnie_rekordu


def eksportuj_rekord(rec):
    """Wachlarz: wyślij rekord do DSpace każdej afiliowanej, skonfigurowanej
    uczelni. Zwraca listę wyników per uczelnia (do raportu w UI/logu)."""
    wyniki = []
    for uczelnia in uczelnie_rekordu(rec):
        wyniki.append(_eksportuj_do_uczelni(rec, uczelnia))
    return wyniki


def _wynik(uczelnia, status, powod=""):
    return {"uczelnia": uczelnia, "status": status, "powod": powod}


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

    if not SentToDSpace.objects.check_if_upload_needed(rec, uczelnia, dc):
        return _wynik(uczelnia, "bez_zmian", "dane bez zmian")

    try:
        sent = SentToDSpace.objects.get_for_rec(rec, uczelnia)
        istnieje_uuid = sent.dspace_uuid
    except SentToDSpace.DoesNotExist:
        istnieje_uuid = None

    SentToDSpace.objects.create_or_update_before_upload(rec, uczelnia, dc)

    try:
        client = DSpaceClient(uczelnia)
        client.authenticate()
        if istnieje_uuid:
            client.patch_item(istnieje_uuid, dc)
            uuid, status = istnieje_uuid, "zaktualizowano"
        else:
            uuid = client.create_item(mapowanie.collection_uuid, dc)
            status = "wyslano"
        SentToDSpace.objects.mark_as_successful(rec, uczelnia, dspace_uuid=uuid)
        return _wynik(uczelnia, status)
    except Exception as e:
        SentToDSpace.objects.mark_as_failed(
            rec, uczelnia, exception=traceback.format_exc()
        )
        return _wynik(uczelnia, "blad", str(e))
