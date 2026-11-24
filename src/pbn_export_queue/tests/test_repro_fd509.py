"""FD#509 w kolejce eksportu: praca z autorem bez odpowiednika w PBN i bez ORCID.

Wpis ma się skończyć BŁĘDEM MERYTORYCZNYM (do poprawienia przez redaktora —
nie sukcesem i nie ponawianiem w kółko), nic nie idzie do PBN, a po
uzupełnieniu danych autora ponowna wysyłka przechodzi.
"""

from unittest.mock import patch

import pytest
from django.urls import reverse
from model_bakery import baker
from pbn_client.const import (
    PBN_GET_INSTITUTION_PUBLICATIONS_V2,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)

from bpp.models import Uczelnia
from fixtures.pbn_api import (
    MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA,
    MOCK_RETURNED_MONGODB_DATA,
    pbn_pageable_json,
)
from pbn_export_queue.models import PBN_Export_Queue, RodzajBledu, SendStatus
from pbn_export_queue.templatetags.pbn_queue_extras import format_pbn_error
from pbn_export_queue.views.utils import (
    extract_pbn_error_from_komunikat,
    parse_pbn_api_error,
)

ORCID = "0000-0002-1825-0097"


@pytest.fixture
def praca_z_autorem_bez_identyfikatorow(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uczelnia
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = praca.autorzy_set.get()
    wa.afiliuje = True
    wa.przypieta = True
    wa.save()

    jednostka = wa.jednostka
    jednostka.skupia_pracownikow = True
    jednostka.save()

    autor = wa.autor
    autor.pbn_uid = None
    autor.orcid = None
    autor.save()

    # Najgroźniejszy wariant: uczelnia wysyła prace bez oświadczeń, więc stary
    # kod wysyłał taką pracę ścieżką repozytoryjną i raportował sukces.
    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = True
    pbn_uczelnia.save()
    return praca


@pytest.fixture
def pbn_przyjmie_wszystko(pbn_client):
    rv = pbn_client.transport.return_values
    rv[PBN_POST_PUBLICATIONS_URL] = {"objectId": "123"}
    rv[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [{"id": "123"}]
    rv[PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")] = MOCK_RETURNED_MONGODB_DATA
    rv[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = MOCK_RETURNED_MONGODB_DATA
    rv[PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"] = (
        pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)
    )
    rv[PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"] = (
        pbn_pageable_json([])
    )
    rv[PBN_POST_INSTITUTION_STATEMENTS_URL] = {"status": "ok"}
    # Kolejka czyta uczelnię z bazy (inny obiekt niż w fiksturze), więc
    # klienta podmieniamy na poziomie klasy.
    with patch.object(Uczelnia, "pbn_client", lambda self, *a, **kw: pbn_client):
        yield pbn_client


@pytest.fixture
def wpis(praca_z_autorem_bez_identyfikatorow, admin_user, pbn_uczelnia):
    admin_user.pbn_token = "token"
    admin_user.save()
    return baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=praca_z_autorem_bez_identyfikatorow,
        zamowil=admin_user,
        uczelnia=pbn_uczelnia,
        wysylke_zakonczono=None,
        zakonczono_pomyslnie=None,
    )


@pytest.mark.django_db
def test_fd509_kolejka_blad_merytoryczny_nic_nie_wyslano(
    wpis, praca_z_autorem_bez_identyfikatorow, pbn_przyjmie_wszystko
):
    """NIE przechodzi na starym kodzie (tam: FINISHED_OKAY, POST do PBN)."""
    autor = praca_z_autorem_bez_identyfikatorow.autorzy_set.get().autor

    wynik = wpis.send_to_pbn()

    assert pbn_przyjmie_wszystko.transport.input_values == {}
    assert wynik == SendStatus.FINISHED_ERROR
    wpis.refresh_from_db()
    assert wpis.zakonczono_pomyslnie is False
    assert wpis.wysylke_zakonczono is not None
    assert wpis.wykluczone is False
    assert wpis.rodzaj_bledu == RodzajBledu.MERYTORYCZNY
    assert wpis.retry_after_user_authorised is None
    assert str(autor) in wpis.komunikat
    assert "Odpowiednik w PBN" in wpis.komunikat

    # Lista kolejki i strona wpisu pokazują czytelny powód, a nie „komunikat
    # za długi" ani surowy traceback.
    na_liscie = format_pbn_error(wpis.komunikat, wpis.rodzaj_bledu)
    assert str(autor) in na_liscie
    blad = parse_pbn_api_error(extract_pbn_error_from_komunikat(wpis.komunikat))
    assert str(autor) in blad["error_message"]


@pytest.mark.django_db
def test_fd509_kolejka_strona_wpisu_linkuje_do_autorow(
    wpis, praca_z_autorem_bez_identyfikatorow, pbn_przyjmie_wszystko, client
):
    autor = praca_z_autorem_bez_identyfikatorow.autorzy_set.get().autor
    wpis.send_to_pbn()

    client.force_login(wpis.zamowil)
    url = reverse("pbn_export_queue:export-queue-detail", args=[wpis.pk])
    tresc = client.get(url).content.decode()

    assert 'id="autorzy-bez-identyfikatora"' in tresc
    assert reverse("admin:bpp_autor_change", args=(autor.pk,)) in tresc

    # Po uzupełnieniu ORCID lista znika — widać, że można wysłać ponownie.
    autor.orcid = ORCID
    autor.save()
    tresc = client.get(url).content.decode()
    assert 'id="autorzy-bez-identyfikatora"' not in tresc


@pytest.mark.django_db
def test_fd509_kolejka_po_poprawieniu_autora_ponowna_wysylka_przechodzi(
    wpis, praca_z_autorem_bez_identyfikatorow, pbn_przyjmie_wszystko
):
    assert wpis.send_to_pbn() == SendStatus.FINISHED_ERROR

    autor = praca_z_autorem_bez_identyfikatorow.autorzy_set.get().autor
    autor.orcid = ORCID
    autor.save()

    wpis.prepare_for_resend(user=wpis.zamowil)
    wynik = wpis.send_to_pbn()

    assert wynik == SendStatus.FINISHED_OKAY
    wpis.refresh_from_db()
    assert wpis.zakonczono_pomyslnie is True
    wyslane = pbn_przyjmie_wszystko.transport.input_values
    oswiadczenia = wyslane[PBN_POST_PUBLICATIONS_URL]["body"]["statements"]
    assert [s["personOrcidId"] for s in oswiadczenia] == [ORCID]
    assert PBN_POST_PUBLICATION_NO_STATEMENTS_URL not in wyslane


@pytest.mark.django_db
def test_fd509_kolejka_opcja_wlaczona_sukces_z_ostrzezeniem(
    wpis,
    praca_z_autorem_bez_identyfikatorow,
    pbn_przyjmie_wszystko,
    pbn_uczelnia,
    client,
):
    """Uczelnia pozwala wysyłać mimo braku identyfikatora: wpis kończy się
    sukcesem, ale komunikat i strona wpisu mówią, że oświadczenia są niepełne."""
    autor = praca_z_autorem_bez_identyfikatorow.autorzy_set.get().autor
    # Ten sam obiekt uczelni trzyma zamockowany klient PBN (``.uczelnia``),
    # więc ustawiamy na nim, a wpis kolejki odświeżamy z bazy.
    pbn_uczelnia.pbn_wysylaj_bez_identyfikatora_autora = True
    pbn_uczelnia.save()
    wpis.refresh_from_db()

    wynik = wpis.send_to_pbn()

    assert wynik == SendStatus.FINISHED_OKAY
    wpis.refresh_from_db()
    assert wpis.zakonczono_pomyslnie is True
    assert "NIEPEŁNE" in wpis.komunikat
    assert "Z 1 autorów" in wpis.komunikat
    assert "trafiło 0 oświadczeń" in wpis.komunikat
    assert str(autor) in wpis.komunikat

    client.force_login(wpis.zamowil)
    url = reverse("pbn_export_queue:export-queue-detail", args=[wpis.pk])
    tresc = client.get(url).content.decode()
    assert 'id="autorzy-pominieci-w-oswiadczeniach"' in tresc
    assert 'id="autorzy-bez-identyfikatora"' not in tresc
    assert reverse("admin:bpp_autor_change", args=(autor.pk,)) in tresc

    # Po uzupełnieniu ORCID ostrzeżenie znika (liczone na żywo).
    autor.orcid = ORCID
    autor.save()
    tresc = client.get(url).content.decode()
    assert 'id="autorzy-pominieci-w-oswiadczeniach"' not in tresc
