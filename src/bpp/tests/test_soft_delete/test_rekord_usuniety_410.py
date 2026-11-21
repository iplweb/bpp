"""Public URL of a trashed record -> HTTP 410 Gone (``bpp.rekord_usuniety``).

A record that was moved to the trash answers 410 with a generic page that
shows NONE of its data. A URL that never existed, or a record purged from
the trash, keeps the plain 404. Restoring the record brings the page back.
"""

import pytest
from denorm import denorms
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Wydawca, Wydawnictwo_Ciagle, Zrodlo

TEKST_410 = "Ten rekord został usunięty z bibliografii"


def _sprawdz_strone_410(res, *zakazane):
    assert res.status_code == 410
    tresc = res.content.decode("utf-8")
    assert TEKST_410 in tresc
    assert '<meta name="robots" content="noindex"/>' in tresc
    assert res["X-Robots-Tag"] == "noindex"
    for tekst in zakazane:
        assert tekst not in tresc, tekst
    return tresc


@pytest.fixture
def praca(wydawnictwo_ciagle):
    wydawnictwo_ciagle.tytul_oryginalny = "Tajny tytul usunietej pracy"
    wydawnictwo_ciagle.save()
    denorms.flush()
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.slug
    return wydawnictwo_ciagle


def _url_slug(praca):
    return reverse("bpp:browse_praca_by_slug", args=(praca.slug,))


@pytest.mark.django_db
def test_publikacja_zywa_200(client, praca):
    res = client.get(_url_slug(praca))
    assert res.status_code == 200
    assert "Tajny tytul usunietej pracy" in res.content.decode("utf-8")


@pytest.mark.django_db
def test_publikacja_w_koszu_po_slugu_410_bez_tresci(client, praca, bez_celery):
    praca.delete()

    res = client.get(_url_slug(praca))

    # Sam slug pojawia się wyłącznie w ``?next=`` linków logowania (to
    # adres, który oglądający już ma) — sprawdzamy brak treści rekordu.
    tresc = _sprawdz_strone_410(res, "Tajny tytul usunietej pracy")
    assert "Publikacja, której szukasz" in tresc
    assert 'property="og:url"' not in tresc


@pytest.mark.django_db
def test_publikacja_w_koszu_po_modelu_i_pk_410(client, praca, bez_celery):
    praca.delete()

    res = client.get(reverse("bpp:browse_praca", args=("wydawnictwo_ciagle", praca.pk)))
    _sprawdz_strone_410(res, "Tajny tytul usunietej pracy")

    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    res = client.get(reverse("bpp:browse_praca", args=(ct.pk, praca.pk)))
    _sprawdz_strone_410(res, "Tajny tytul usunietej pracy")


@pytest.mark.django_db
def test_publikacja_w_koszu_stary_url_410(client, praca, bez_celery):
    praca.delete()

    res = client.get(
        reverse("bpp:browse_praca_old", args=("wydawnictwo_ciagle", praca.pk)),
        follow=True,
    )

    _sprawdz_strone_410(res, "Tajny tytul usunietej pracy")


@pytest.mark.django_db
def test_publikacja_w_koszu_slug_z_numerami_na_koncu_410(client, praca, bez_celery):
    """Stary format linku ``cokolwiek-<content_type_id>-<pk>``."""
    praca.delete()
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)

    res = client.get(
        reverse("bpp:browse_praca_by_slug", args=(f"stary-link-{ct.pk}-{praca.pk}",))
    )

    _sprawdz_strone_410(res, "Tajny tytul usunietej pracy")


@pytest.mark.django_db
def test_publikacja_przywrocona_znowu_200(client, praca, bez_celery):
    praca.delete()
    assert client.get(_url_slug(praca)).status_code == 410

    Wydawnictwo_Ciagle.global_objects.get(pk=praca.pk).restore()

    res = client.get(_url_slug(praca))
    assert res.status_code == 200
    assert "Tajny tytul usunietej pracy" in res.content.decode("utf-8")


@pytest.mark.django_db
def test_publikacja_usunieta_trwale_404(client, praca, bez_celery):
    praca.delete()
    Wydawnictwo_Ciagle.global_objects.get(pk=praca.pk).hard_delete()

    assert client.get(_url_slug(praca)).status_code == 404


@pytest.mark.django_db
def test_nieistniejacy_slug_404(client, praca):
    res = client.get(reverse("bpp:browse_praca_by_slug", args=("nigdy-nie-istnial",)))
    assert res.status_code == 404

    res = client.get(reverse("bpp:browse_praca", args=("wydawnictwo_ciagle", 999999)))
    assert res.status_code == 404


@pytest.mark.django_db
def test_cache_publiczny_nie_trzyma_200_po_koszu(client, praca, bez_celery):
    """Anonim dostał 200 (zapisane w cache publicznym); po koszu -> 410."""
    assert client.get(_url_slug(praca)).status_code == 200

    praca.delete()

    _sprawdz_strone_410(client.get(_url_slug(praca)), "Tajny tytul usunietej pracy")


@pytest.mark.django_db
def test_autor_w_koszu_410(client):
    autor = baker.make(Autor, imiona="Tajemniczy", nazwisko="Koszowski")
    zywy = client.get(reverse("bpp:browse_autor", args=(autor.slug,)))
    assert zywy.status_code == 200

    autor.delete()

    for arg in (autor.slug, autor.pk):
        res = client.get(reverse("bpp:browse_autor", args=(arg,)))
        tresc = _sprawdz_strone_410(res, "Koszowski", "Tajemniczy")
        assert "Autor, którego szukasz" in tresc

    res = client.get(reverse("bpp:browse_autor_powiazania", args=(autor.pk,)))
    _sprawdz_strone_410(res, "Koszowski")

    Autor.global_objects.get(pk=autor.pk).restore()
    res = client.get(reverse("bpp:browse_autor", args=(autor.slug,)))
    assert res.status_code == 200


@pytest.mark.django_db
def test_autor_nieistniejacy_404(client):
    res = client.get(reverse("bpp:browse_autor", args=("nie-ma-takiego",)))
    assert res.status_code == 404


@pytest.mark.django_db
def test_autor_ze_schowana_strona_w_koszu_zostaje_404(client):
    """Schowana strona autora to dla anonima 404 — kosz nie może tego
    zdradzić 410-tką."""
    autor = baker.make(
        Autor,
        nazwisko="Schowany",
        pokazuj_strone_autora=False,
        pokazuj_w_wyszukiwaniu=False,
        pokazuj_w_indeksie=False,
    )
    autor.delete()

    res = client.get(reverse("bpp:browse_autor", args=(autor.slug,)))
    assert res.status_code == 404


@pytest.mark.django_db
def test_zrodlo_w_koszu_410(client):
    zrodlo = baker.make(Zrodlo, nazwa="Tajne Czasopismo Koszowe")
    zrodlo.delete()

    res = client.get(reverse("bpp:browse_zrodlo", args=(zrodlo.slug,)))

    tresc = _sprawdz_strone_410(res, "Tajne Czasopismo Koszowe")
    assert "Źródło, którego szukasz" in tresc


@pytest.mark.django_db
def test_wydawca_w_koszu_410(client):
    wydawca = Wydawca.objects.create(nazwa="Tajne Wydawnictwo Koszowe")
    wydawca.delete()

    for url in (
        reverse("bpp:browse_wydawca", args=(wydawca.slug,)),
        reverse("bpp:browse_wydawca_pk", args=(wydawca.pk,)),
    ):
        tresc = _sprawdz_strone_410(client.get(url), "Tajne Wydawnictwo Koszowe")
        assert "Wydawca, którego szukasz" in tresc


@pytest.mark.django_db
def test_uczelnia_w_koszu_410(client):
    from bpp.models import Uczelnia

    uczelnia = baker.make(Uczelnia, nazwa="Tajna Uczelnia Koszowa", skrot="TUK")
    uczelnia.delete()

    res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))

    tresc = _sprawdz_strone_410(res, "Tajna Uczelnia Koszowa")
    assert "Uczelnia, której szukasz" in tresc
