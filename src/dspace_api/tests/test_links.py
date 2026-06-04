import pytest
from model_bakery import baker


@pytest.fixture
def fernet_key(settings):
    from cryptography.fernet import Fernet

    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()


@pytest.mark.django_db
def test_public_url_obcina_server_api(fernet_key):
    from dspace_api.links import public_url_for_sent
    from dspace_api.models import SentToDSpace

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.example.org/server/api"
    u.save()
    rec = baker.make("bpp.Wydawnictwo_Ciagle")

    SentToDSpace.objects.create_or_update_before_upload(rec, u, {"x": 1})
    SentToDSpace.objects.mark_as_successful(rec, u, dspace_handle="11089/123")
    sent = SentToDSpace.objects.get_for_rec(rec, u)

    assert public_url_for_sent(sent) == "https://repo.example.org/handle/11089/123"


@pytest.mark.django_db
def test_public_url_brak_handle_zwraca_none(fernet_key):
    from dspace_api.links import public_url_for_sent
    from dspace_api.models import SentToDSpace

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.example.org/server/api"
    u.save()
    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    SentToDSpace.objects.create_or_update_before_upload(rec, u, {"x": 1})
    SentToDSpace.objects.mark_as_successful(rec, u, dspace_handle="")
    sent = SentToDSpace.objects.get_for_rec(rec, u)

    assert public_url_for_sent(sent) is None


@pytest.mark.django_db
def test_public_url_brak_endpointu_zwraca_none(fernet_key):
    from dspace_api.links import public_url_for_sent
    from dspace_api.models import SentToDSpace

    u = baker.make("bpp.Uczelnia")  # bez dspace_api_endpoint
    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    SentToDSpace.objects.create_or_update_before_upload(rec, u, {"x": 1})
    SentToDSpace.objects.mark_as_successful(rec, u, dspace_handle="11089/1")
    sent = SentToDSpace.objects.get_for_rec(rec, u)

    assert public_url_for_sent(sent) is None


@pytest.mark.django_db
def test_public_links_for_rec_tylko_udane_z_handle(fernet_key):
    from dspace_api.links import public_links_for_rec
    from dspace_api.models import SentToDSpace

    rec = baker.make("bpp.Wydawnictwo_Ciagle")

    u_ok = baker.make("bpp.Uczelnia")
    u_ok.dspace_api_endpoint = "https://a.example/server/api"
    u_ok.save()
    SentToDSpace.objects.create_or_update_before_upload(rec, u_ok, {"x": 1})
    SentToDSpace.objects.mark_as_successful(rec, u_ok, dspace_handle="11089/aa")

    # druga uczelnia: wysłano, ale bez handle → nie linkujemy
    u_nohandle = baker.make("bpp.Uczelnia")
    u_nohandle.dspace_api_endpoint = "https://b.example/server/api"
    u_nohandle.save()
    SentToDSpace.objects.create_or_update_before_upload(rec, u_nohandle, {"x": 1})
    SentToDSpace.objects.mark_as_successful(rec, u_nohandle, dspace_handle="")

    # trzecia uczelnia: nieudana wysyłka z handle → nie linkujemy
    u_failed = baker.make("bpp.Uczelnia")
    u_failed.dspace_api_endpoint = "https://c.example/server/api"
    u_failed.save()
    SentToDSpace.objects.create_or_update_before_upload(rec, u_failed, {"x": 1})
    SentToDSpace.objects.mark_as_failed(rec, u_failed)
    sd = SentToDSpace.objects.get_for_rec(rec, u_failed)
    sd.dspace_handle = "11089/cc"
    sd.save()

    links = public_links_for_rec(rec)
    assert links == [(u_ok, "https://a.example/handle/11089/aa")]


@pytest.mark.django_db
def test_publiczna_strona_rekordu_pokazuje_link(
    client, wydawnictwo_ciagle, denorms, fernet_key
):
    """Link 'Repozytorium DSpace' renderuje się na publicznej stronie rekordu
    (karta 'Linki zewnętrzne') — sprawdza też, że `{% dspace_repo_links %}`
    ładuje się bez błędu składni szablonu."""
    from django.contrib.contenttypes.models import ContentType
    from django.urls import reverse

    from dspace_api.models import SentToDSpace

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.example/server/api"
    u.save()
    SentToDSpace.objects.create_or_update_before_upload(wydawnictwo_ciagle, u, {"x": 1})
    SentToDSpace.objects.mark_as_successful(
        wydawnictwo_ciagle, u, dspace_handle="11089/pub"
    )

    ct = ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle")
    res = client.get(
        reverse("bpp:browse_praca", args=(ct.pk, wydawnictwo_ciagle.pk)),
        follow=True,
    )
    assert res.status_code == 200
    assert b"https://repo.example/handle/11089/pub" in res.content
    assert b"Repozytorium DSpace" in res.content
