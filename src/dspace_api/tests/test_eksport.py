from unittest import mock

import pytest
from model_bakery import baker


@pytest.fixture
def fernet_key(settings):
    from cryptography.fernet import Fernet

    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()


@pytest.mark.django_db
def test_wachlarz_jedna_skonfigurowana_druga_nie(fernet_key):
    from dspace_api.eksport import eksportuj_rekord
    from dspace_api.models import Mapowanie_DSpace

    u1 = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u1.dspace_api_endpoint = "https://repo1/server/api"
    u1.save()
    u2 = baker.make("bpp.Uczelnia", dspace_aktywny=False)  # nieaktywna

    j1 = baker.make("bpp.Jednostka", uczelnia=u1)
    j2 = baker.make("bpp.Jednostka", uczelnia=u2)
    charakter = baker.make("bpp.Charakter_Formalny")
    rec = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="T",
        rok=2024,
        charakter_formalny=charakter,
    )
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j1, kolejnosc=0)
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j2, kolejnosc=1)

    Mapowanie_DSpace.objects.create(
        uczelnia=u1,
        charakter_formalny=charakter,
        collection_uuid="66666666-6666-6666-6666-666666666666",
    )

    with mock.patch("dspace_api.eksport.DSpaceClient") as ClientCls:
        client = ClientCls.return_value
        client.create_item.return_value = (
            "77777777-7777-7777-7777-777777777777",
            "11089/77",
        )

        wyniki = eksportuj_rekord(rec)

    by_uczelnia = {w["uczelnia"]: w for w in wyniki}
    assert by_uczelnia[u1]["status"] == "wyslano"
    assert by_uczelnia[u2]["status"] == "pominieto"


@pytest.mark.django_db
def test_brak_mapowania_pomija_z_powodem(fernet_key):
    from dspace_api.eksport import eksportuj_rekord

    u = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    j = baker.make("bpp.Jednostka", uczelnia=u)
    rec = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="T", rok=2024)
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j, kolejnosc=0)

    wyniki = eksportuj_rekord(rec)
    assert wyniki[0]["status"] == "pominieto"
    assert "mapowani" in wyniki[0]["powod"].lower()


@pytest.mark.django_db
def test_reconcile_usuwa_bitstream_skasowanego_pliku(fernet_key):
    """Plik był wysłany; po soft-delete i re-wysyłce bitstream kasowany w DSpace."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from bpp.const import TRYB_DOSTEPU
    from bpp.models import Element_Repozytorium
    from dspace_api.eksport import eksportuj_rekord
    from dspace_api.models import Mapowanie_DSpace, SentToDSpace

    u = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    j = baker.make("bpp.Jednostka", uczelnia=u)
    charakter = baker.make("bpp.Charakter_Formalny")
    rec = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="T",
        rok=2024,
        charakter_formalny=charakter,
    )
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j, kolejnosc=0)
    Mapowanie_DSpace.objects.create(
        uczelnia=u,
        charakter_formalny=charakter,
        collection_uuid="66666666-6666-6666-6666-666666666666",
    )
    el = Element_Repozytorium.objects.create(
        rekord=rec,
        rodzaj="pdf",
        nazwa_pliku="a.pdf",
        tryb_dostepu=TRYB_DOSTEPU.JAWNY.value,
        plik=SimpleUploadedFile("a.pdf", b"%PDF a"),
    )

    # 1. pierwsza wysyłka — plik wgrany
    with mock.patch("dspace_api.eksport.DSpaceClient") as ClientCls:
        client = ClientCls.return_value
        client.create_item.return_value = (
            "11111111-1111-1111-1111-111111111111",
            "11089/11",
        )
        client.ensure_bundle.return_value = "bundle-1"
        client.create_bitstream.return_value = "bs-uuid-1"
        eksportuj_rekord(rec)

    sent = SentToDSpace.objects.get_for_rec(rec, u)
    assert sent.bitstreams == {str(el.id): "bs-uuid-1"}

    # 2. soft-delete pliku + re-wysyłka — bitstream kasowany w DSpace
    el.delete()
    with mock.patch("dspace_api.eksport.DSpaceClient") as ClientCls:
        client = ClientCls.return_value
        client.create_item.return_value = (
            "11111111-1111-1111-1111-111111111111",
            "11089/11",
        )
        wyniki = eksportuj_rekord(rec)  # noqa: F841
        client.delete_bitstream.assert_called_once_with("bs-uuid-1")

    sent.refresh_from_db()
    assert sent.bitstreams == {}


@pytest.mark.django_db
def test_reconcile_wgrywa_nowy_plik(fernet_key):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from bpp.const import TRYB_DOSTEPU
    from bpp.models import Element_Repozytorium
    from dspace_api.eksport import eksportuj_rekord
    from dspace_api.models import Mapowanie_DSpace, SentToDSpace

    u = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    j = baker.make("bpp.Jednostka", uczelnia=u)
    charakter = baker.make("bpp.Charakter_Formalny")
    rec = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="T",
        rok=2024,
        charakter_formalny=charakter,
    )
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j, kolejnosc=0)
    Mapowanie_DSpace.objects.create(
        uczelnia=u,
        charakter_formalny=charakter,
        collection_uuid="66666666-6666-6666-6666-666666666666",
    )

    with mock.patch("dspace_api.eksport.DSpaceClient") as ClientCls:
        client = ClientCls.return_value
        client.create_item.return_value = (
            "11111111-1111-1111-1111-111111111111",
            "11089/11",
        )
        client.ensure_bundle.return_value = "bundle-1"
        client.create_bitstream.return_value = "bs-uuid-9"
        eksportuj_rekord(rec)  # bez plików → brak bitstreamów
    assert SentToDSpace.objects.get_for_rec(rec, u).bitstreams == {}

    el = Element_Repozytorium.objects.create(
        rekord=rec,
        rodzaj="pdf",
        nazwa_pliku="b.pdf",
        tryb_dostepu=TRYB_DOSTEPU.JAWNY.value,
        plik=SimpleUploadedFile("b.pdf", b"%PDF b"),
    )
    with mock.patch("dspace_api.eksport.DSpaceClient") as ClientCls:
        client = ClientCls.return_value
        client.ensure_bundle.return_value = "bundle-1"
        client.create_bitstream.return_value = "bs-uuid-9"
        eksportuj_rekord(rec)  # re-wysyłka — nowy plik wgrany
        client.create_bitstream.assert_called_once()

    assert SentToDSpace.objects.get_for_rec(rec, u).bitstreams == {
        str(el.id): "bs-uuid-9"
    }


@pytest.mark.django_db
def test_reconcile_utrwala_mape_przy_czesciowej_awarii(fernet_key):
    """Gdy 2. upload padnie, 1. wgrany bitstream zostaje zapisany w mapie
    (nie zgubiony) — żeby następny sync go nie zdublował."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from bpp.const import TRYB_DOSTEPU
    from bpp.models import Element_Repozytorium
    from dspace_api.eksport import eksportuj_rekord
    from dspace_api.models import Mapowanie_DSpace, SentToDSpace

    u = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    j = baker.make("bpp.Jednostka", uczelnia=u)
    charakter = baker.make("bpp.Charakter_Formalny")
    rec = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="T",
        rok=2024,
        charakter_formalny=charakter,
    )
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j, kolejnosc=0)
    Mapowanie_DSpace.objects.create(
        uczelnia=u,
        charakter_formalny=charakter,
        collection_uuid="66666666-6666-6666-6666-666666666666",
    )
    el1 = Element_Repozytorium.objects.create(
        rekord=rec,
        rodzaj="pdf",
        nazwa_pliku="a.pdf",
        tryb_dostepu=TRYB_DOSTEPU.JAWNY.value,
        plik=SimpleUploadedFile("a.pdf", b"%PDF a"),
    )
    Element_Repozytorium.objects.create(
        rekord=rec,
        rodzaj="pdf",
        nazwa_pliku="b.pdf",
        tryb_dostepu=TRYB_DOSTEPU.JAWNY.value,
        plik=SimpleUploadedFile("b.pdf", b"%PDF b"),
    )

    # create_bitstream: 1. plik OK, 2. rzuca
    def fake_create_bitstream(bundle, element):
        if element.pk == el1.pk:
            return "bs-uuid-1"
        raise RuntimeError("DSpace padło na drugim pliku")

    with mock.patch("dspace_api.eksport.DSpaceClient") as ClientCls:
        client = ClientCls.return_value
        client.create_item.return_value = (
            "11111111-1111-1111-1111-111111111111",
            "11089/11",
        )
        client.ensure_bundle.return_value = "bundle-1"
        client.create_bitstream.side_effect = fake_create_bitstream
        wyniki = eksportuj_rekord(rec)

    assert wyniki[0]["status"] == "blad"
    sent = SentToDSpace.objects.get_for_rec(rec, u)
    # KLUCZOWE: 1. wgrany bitstream JEST w mapie (nie zgubiony)
    assert sent.bitstreams == {str(el1.pk): "bs-uuid-1"}


@pytest.mark.django_db
def test_handle_zapisany_przy_create(fernet_key):
    """Przy pierwszej wysyłce handle z odpowiedzi create_item ląduje w bazie."""
    from dspace_api.eksport import eksportuj_rekord
    from dspace_api.models import Mapowanie_DSpace, SentToDSpace

    u = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    j = baker.make("bpp.Jednostka", uczelnia=u)
    charakter = baker.make("bpp.Charakter_Formalny")
    rec = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="T",
        rok=2024,
        charakter_formalny=charakter,
    )
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j, kolejnosc=0)
    Mapowanie_DSpace.objects.create(
        uczelnia=u,
        charakter_formalny=charakter,
        collection_uuid="66666666-6666-6666-6666-666666666666",
    )

    with mock.patch("dspace_api.eksport.DSpaceClient") as ClientCls:
        client = ClientCls.return_value
        client.create_item.return_value = (
            "11111111-1111-1111-1111-111111111111",
            "11089/555",
        )
        eksportuj_rekord(rec)
        client.fetch_handle.assert_not_called()  # handle przyszedł z create

    assert SentToDSpace.objects.get_for_rec(rec, u).dspace_handle == "11089/555"


@pytest.mark.django_db
def test_handle_backfill_przy_aktualizacji_starego_rekordu(fernet_key):
    """Rekord wysłany zanim zapisywaliśmy handle (puste) — przy aktualizacji
    handle jest doczytywany przez fetch_handle."""
    from dspace_api.eksport import eksportuj_rekord
    from dspace_api.models import Mapowanie_DSpace, SentToDSpace

    u = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    j = baker.make("bpp.Jednostka", uczelnia=u)
    charakter = baker.make("bpp.Charakter_Formalny")
    rec = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="T",
        rok=2024,
        charakter_formalny=charakter,
    )
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j, kolejnosc=0)
    Mapowanie_DSpace.objects.create(
        uczelnia=u,
        charakter_formalny=charakter,
        collection_uuid="66666666-6666-6666-6666-666666666666",
    )
    # symuluj "stary" rekord: wysłany, ma uuid, ale puste handle
    SentToDSpace.objects.create_or_update_before_upload(rec, u, {"dc.title": []})
    SentToDSpace.objects.mark_as_successful(
        rec, u, dspace_uuid="11111111-1111-1111-1111-111111111111", dspace_handle=""
    )

    # zmiana danych → kolejna wysyłka pójdzie ścieżką update (patch_item)
    rec.tytul_oryginalny = "T2"
    rec.save()

    with mock.patch("dspace_api.eksport.DSpaceClient") as ClientCls:
        client = ClientCls.return_value
        client.fetch_handle.return_value = "11089/backfilled"
        eksportuj_rekord(rec)
        client.create_item.assert_not_called()  # to aktualizacja, nie create
        client.fetch_handle.assert_called_once()
        # dspace_uuid to pole UUIDField → arg jest obiektem UUID, nie stringiem
        assert (
            str(client.fetch_handle.call_args[0][0])
            == "11111111-1111-1111-1111-111111111111"
        )

    assert SentToDSpace.objects.get_for_rec(rec, u).dspace_handle == "11089/backfilled"
