"""Repro FD#301 — zmiana samej opłaty za publikację nie wychodziła do PBN.

Scenariusz klienta (bpp.apoz.edu.pl): rekord został wcześniej wysłany do PBN
ścieżką repozytoryjną (uczelnia z ``pbn_wysylaj_bez_oswiadczen=True``). Payload
publikacji dla tej ścieżki **nie zawiera opłat** —
``convert_json_with_statements_to_no_statements`` usuwa klucz ``fee``. Operator
zmienił opłatę na bezkosztową i kliknął „wyślij do PBN"; dotąd system pokazywał
„Identyczne dane rekordu... Nie aktualizuję", bo porównanie payloadu publikacji
w ogóle nie widziało opłat.

Po naprawie: zmiana opłaty jest wykrywana osobnym śladem
``SentData.fee_sent`` i opłata leci osobnym endpointem institution-profile fee,
nawet gdy payload publikacji jest identyczny.
"""

import pytest

from pbn_api.exceptions import SameDataUploadedRecently
from pbn_api.models import SentData
from pbn_client.const import PBN_POST_PUBLICATION_FEE_URL

BEZKOSZTOWA_FEE = {
    "amount": 0,
    "costFreePublication": True,
    "other": False,
    "researchOrDevelopmentProjectsFinancialResources": False,
    "researchPotentialFinancialResources": False,
}


def _ustaw_sciezke_repozytoryjna(pub, uczelnia):
    """Konfiguruje pracę na ścieżkę repo (bez oświadczeń) — payload bez opłat."""
    uczelnia.pbn_wysylaj_bez_oswiadczen = True
    uczelnia.save()
    pub.autorzy_set.all().update(dyscyplina_naukowa=None)


@pytest.mark.django_db
def test_fd301_zmiana_oplaty_wychodzi_mimo_identycznego_payloadu(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication, uczelnia
):
    pub = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    _ustaw_sciezke_repozytoryjna(pub, uczelnia)

    # Rekord ma już odpowiednik w PBN i był wcześniej wysłany.
    pub.pbn_uid = pbn_publication
    pub.save()

    js, bez_oswiadczen = pbn_client._prepare_publication_json(
        pub, export_pk_zero=None, always_affiliate_to_uid=None
    )
    assert bez_oswiadczen is True
    # Sanity: payload repozytoryjny nie zawiera opłat.
    assert "fee" not in js

    SentData.objects.create_or_update_before_upload(pub, js, uczelnia=uczelnia)
    SentData.objects.mark_as_successful(
        pub, pbn_uid_id=pbn_publication.pk, uczelnia=uczelnia
    )

    # Operator zmienia opłatę na bezkosztową PO wysyłce. Payload publikacji
    # (repo) nadal identyczny — zmienia się tylko opłata.
    pub.opl_pub_cost_free = True
    pub.opl_pub_amount = None
    pub.save()

    fee_url = PBN_POST_PUBLICATION_FEE_URL.format(id=pbn_publication.pk)
    pbn_client.transport.return_values[fee_url] = {"success": True}

    # Nie powinno rzucić SameDataUploadedRecently — opłata się zmieniła.
    pbn_client.sync_publication(pub)

    # Opłata została wysłana osobnym endpointem institution-profile fee...
    assert fee_url in pbn_client.transport.input_values
    assert pbn_client.transport.input_values[fee_url]["body"] == BEZKOSZTOWA_FEE

    # ...a jej ślad został zapisany dla dedupu kolejnych wysyłek.
    sd = SentData.objects.get_for_rec(pub, uczelnia)
    assert sd.fee_sent == BEZKOSZTOWA_FEE
    assert sd.fee_uploaded_okay is True


@pytest.mark.django_db
def test_fd301_bez_zmiany_oplaty_dalej_komunikat_identyczne_dane(
    pbn_client, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication, uczelnia
):
    """Gdy ANI publikacja ANI opłata się nie zmieniły — zachowanie bez zmian:
    ``SameDataUploadedRecently`` (warstwa admina pokaże „Identyczne dane")."""
    pub = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    _ustaw_sciezke_repozytoryjna(pub, uczelnia)

    pub.pbn_uid = pbn_publication
    pub.opl_pub_cost_free = True
    pub.save()

    js, _ = pbn_client._prepare_publication_json(
        pub, export_pk_zero=None, always_affiliate_to_uid=None
    )
    SentData.objects.create_or_update_before_upload(pub, js, uczelnia=uczelnia)
    SentData.objects.mark_as_successful(
        pub, pbn_uid_id=pbn_publication.pk, uczelnia=uczelnia
    )
    # Opłata już wcześniej wysłana i bez zmian.
    SentData.objects.record_fee_sent(pub, BEZKOSZTOWA_FEE, uczelnia=uczelnia)

    fee_url = PBN_POST_PUBLICATION_FEE_URL.format(id=pbn_publication.pk)
    pbn_client.transport.return_values[fee_url] = {"success": True}

    with pytest.raises(SameDataUploadedRecently):
        pbn_client.sync_publication(pub)

    # Opłata NIE poszła ponownie (bez zmian).
    assert fee_url not in pbn_client.transport.input_values


@pytest.mark.django_db
def test_fd301_fee_upload_needed_dedup(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_publication, uczelnia
):
    """Jednostkowy dedup: ``fee_upload_needed`` po zapisaniu ``fee_sent``
    zwraca False dla identycznej opłaty, True dla zmienionej."""
    pub = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    pub.pbn_uid = pbn_publication
    pub.save()

    # Brak śladu → trzeba wysłać.
    assert SentData.objects.fee_upload_needed(pub, BEZKOSZTOWA_FEE, uczelnia) is True

    SentData.objects.record_fee_sent(pub, BEZKOSZTOWA_FEE, uczelnia=uczelnia)
    # Identyczna opłata → nie trzeba.
    assert SentData.objects.fee_upload_needed(pub, BEZKOSZTOWA_FEE, uczelnia) is False

    # Zmieniona opłata → znów trzeba.
    inna = dict(BEZKOSZTOWA_FEE, costFreePublication=False, amount="1500")
    assert SentData.objects.fee_upload_needed(pub, inna, uczelnia) is True
