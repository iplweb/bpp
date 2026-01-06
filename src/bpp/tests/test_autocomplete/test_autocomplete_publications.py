"""
Publication and navigation autocomplete tests.

This module contains tests for:
- Navigation autocomplete (admin and global)
- PBN Publication autocomplete
- PBN Journal autocomplete
- Konferencja (conference) autocomplete
"""

import pytest
from model_bakery import baker

from bpp.const import PBN_UID_LEN
from bpp.models.konferencja import Konferencja
from bpp.views.autocomplete import (
    AdminNavigationAutocomplete,
    GlobalNavigationAutocomplete,
)
from bpp.views.autocomplete.pbn_api import JournalAutocomplete, PublicationAutocomplete
from fixtures import pbn_journal_json, pbn_pageable_json, pbn_publication_json
from pbn_api.client import PBN_GET_PUBLICATION_BY_ID_URL, PBN_SEARCH_PUBLICATIONS_URL
from pbn_api.const import PBN_GET_JOURNAL_BY_ID
from pbn_api.models import Journal, Publication


@pytest.mark.django_db
def test_admin_konferencje():
    """Upewnij sie, ze konferencje wyskakuja w AdminAutoComplete."""
    k = baker.make(Konferencja, nazwa="test 54")
    a = AdminNavigationAutocomplete()
    a.q = "test 54"
    assert k in a.get_queryset()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "klass", [AdminNavigationAutocomplete, GlobalNavigationAutocomplete]
)
def test_NavigationAutocomplete_no_queries(
    django_assert_max_num_queries,
    klass,
    jednostka,
    zrodlo,
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    autor_jan_kowalski,
    autor_jan_nowak,
    rf,
    admin_user,
):
    """Test that navigation autocomplete uses a reasonable number of queries."""
    req = rf.get("/", data={"q": "Je"})
    req.user = admin_user
    with django_assert_max_num_queries(16):
        a = klass()
        a.request = req
        a.q = "Je"  # literka
        a.get(req)

    with django_assert_max_num_queries(16):
        a = klass()
        a.q = "T" * 24  # PBN UID
        a.request = req
        a.get(req)

    with django_assert_max_num_queries(16):
        a = klass()
        a.request = req
        a.q = "T" * 19  # orcid
        a.get(req)


@pytest.mark.django_db
def test_PublicationAutocomplete_get_create_option(rf, admin_user):
    """Test PBN Publication autocomplete create option for UID."""
    ac = PublicationAutocomplete()
    ac.request = rf.get("/")
    ac.request.user = admin_user
    ac.q = "1" * PBN_UID_LEN
    res = ac.get_create_option({"object_list": []}, "1" * PBN_UID_LEN)
    assert str(res[0]["text"]).find("Pobierz rekord o UID") >= 0


@pytest.mark.django_db
def test_PublicationAutocomplete_get_queryset():
    """Test PBN Publication autocomplete queryset by UID and title."""
    ac = PublicationAutocomplete()

    baker.make(
        Publication,
        pk="1" * PBN_UID_LEN,
        **pbn_publication_json(2020, title="Takie tam"),
    )

    ac.q = "1" * PBN_UID_LEN
    assert ac.get_queryset().exists()
    ac.q = "Takie tam"
    assert ac.get_queryset().exists()


@pytest.mark.django_db
def test_JournalAutocomplete_get_queryset():
    """Test PBN Journal autocomplete queryset by UID and title."""
    ac = JournalAutocomplete()

    baker.make(
        Journal,
        pk="1" * PBN_UID_LEN,
        **pbn_journal_json(title="Test"),
    )

    ac.q = "1" * PBN_UID_LEN
    assert ac.get_queryset().exists()
    ac.q = "Test"
    assert ac.get_queryset().exists()


@pytest.mark.django_db
def test_PublicationAutocomplete_create_object(
    pbn_uczelnia, pbn_client, rf, admin_user, pbn_serwer
):
    """Test PBN Publication autocomplete object creation from PBN API."""
    ac = PublicationAutocomplete()
    ac.request = rf.get("/")
    ac.request.user = admin_user

    ROK = 2020
    UID_REKORDU = "1" * PBN_UID_LEN
    ISBN = "123-123-123-123"

    pub1 = pbn_publication_json(ROK, mongoId=UID_REKORDU, isbn=ISBN)
    pbn_serwer.expect_request(PBN_SEARCH_PUBLICATIONS_URL).respond_with_json(
        pbn_pageable_json([pub1])
    )
    pbn_serwer.expect_request(
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=UID_REKORDU)
    ).respond_with_json(pub1)

    assert ac.create_object(UID_REKORDU)


@pytest.mark.django_db
def test_PublicationAutocomplete_post(
    pbn_uczelnia, pbn_client, rf, admin_user, pbn_serwer
):
    """Test PBN Publication autocomplete POST request handling."""
    ac = PublicationAutocomplete()

    ROK = 2020
    UID_REKORDU = "1" * PBN_UID_LEN
    ISBN = "123-123-123-123"

    pub1 = pbn_publication_json(ROK, mongoId=UID_REKORDU, isbn=ISBN)
    pbn_serwer.expect_request(PBN_SEARCH_PUBLICATIONS_URL).respond_with_json(
        pbn_pageable_json([pub1])
    )
    pbn_serwer.expect_request(
        PBN_GET_PUBLICATION_BY_ID_URL.format(id=UID_REKORDU)
    ).respond_with_json(pub1)

    ac.request = rf.post("/", data={"text": UID_REKORDU})
    ac.request.user = admin_user
    assert ac.create_object(UID_REKORDU)


@pytest.mark.django_db
def test_JournalAutocomplete_post(pbn_uczelnia, pbn_client, rf, admin_user, pbn_serwer):
    """Test PBN Journal autocomplete POST request handling."""
    ac = JournalAutocomplete()

    UID_REKORDU = "1" * PBN_UID_LEN
    ISSN = "4567-4567"

    pub1 = pbn_journal_json(mongoId=UID_REKORDU, issn=ISSN)
    pbn_serwer.expect_request(
        PBN_GET_JOURNAL_BY_ID.format(id=UID_REKORDU)
    ).respond_with_json(pub1)

    ac.request = rf.post("/", data={"text": UID_REKORDU})
    ac.request.user = admin_user
    assert ac.create_object(UID_REKORDU)
