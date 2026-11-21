"""FD#561: ukryty autor nie może pokazywać się publicznie tam, gdzie
odpowiednia flaga widoczności mówi „nie pokazuj”.

Sprawdzamy każde publiczne miejsce z listą autorów: indeks autorów
(„Pokazuj w indeksie autorów”), strona jednostki — pracownicy, autorzy
publikacji i kierownik w nagłówku („Pokazuj na stronie jednostki”),
publiczny picker autorów („Pokazuj w wyszukiwaniu”) oraz unieważnianie
publicznego cache'a po masowej akcji „Ukryj wybranych autorów…”.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor, Autor_Jednostka, Funkcja_Autora
from fixtures.conftest_multisite import make_request_for_site

WIDOCZNY = "Widocznyfdpiecszesc"
UKRYTY = "Ukrytyfdpiecszesc"


def _autor(nazwisko, jednostka, **flagi):
    autor = baker.make(Autor, nazwisko=nazwisko, imiona="Jan", **flagi)
    Autor_Jednostka.objects.create(
        autor=autor, jednostka=jednostka, podstawowe_miejsce_pracy=True
    )
    return autor


def _kierownik():
    return Funkcja_Autora.objects.get_or_create(
        nazwa="kierownik", defaults={"skrot": "kier."}
    )[0]


# --- Strona jednostki -------------------------------------------------------


@pytest.mark.django_db
def test_strona_jednostki_pomija_ukrytego_pracownika(client, uczelnia, jednostka):
    _autor(WIDOCZNY, jednostka)
    _autor(UKRYTY, jednostka, pokazuj_na_stronie_jednostki=False)

    res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))

    tresc = res.content.decode()
    assert WIDOCZNY in tresc
    assert UKRYTY not in tresc


@pytest.mark.django_db
def test_strona_jednostki_pomija_ukrytego_kierownika(client, uczelnia, jednostka):
    """Regresja FD#561: kierownik z nagłówka strony jednostki ignorował
    „Pokazuj na stronie jednostki”."""
    ukryty = _autor(UKRYTY, jednostka, pokazuj_na_stronie_jednostki=False)
    Autor_Jednostka.objects.filter(autor=ukryty).update(funkcja=_kierownik())

    res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))

    tresc = res.content.decode()
    assert "Kierownik:" not in tresc
    assert UKRYTY not in tresc


@pytest.mark.django_db
def test_strona_jednostki_pokazuje_widocznego_kierownika(
    client, uczelnia, jednostka
):
    widoczny = _autor(WIDOCZNY, jednostka)
    Autor_Jednostka.objects.filter(autor=widoczny).update(funkcja=_kierownik())

    res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))

    assert f"Kierownik: {widoczny}" in res.content.decode()


@pytest.mark.django_db
def test_kierownik_innej_jednostki_nie_jest_kierownikiem_tej(
    jednostka, druga_jednostka
):
    """Funkcja „kierownik” musi dotyczyć przypisania do TEJ jednostki."""
    autor = _autor(WIDOCZNY, jednostka)
    Autor_Jednostka.objects.create(
        autor=autor, jednostka=druga_jednostka, funkcja=_kierownik()
    )

    assert jednostka.kierownik() is None
    assert druga_jednostka.kierownik() == autor


@pytest.mark.django_db
def test_kierownik_ukryty_pomijany_przez_model(jednostka):
    ukryty = _autor(UKRYTY, jednostka, pokazuj_na_stronie_jednostki=False)
    Autor_Jednostka.objects.filter(autor=ukryty).update(funkcja=_kierownik())

    assert jednostka.kierownik() is None


# --- Indeks autorów ---------------------------------------------------------


@pytest.mark.django_db
def test_indeks_autorow_pomija_ukrytego(client, uczelnia, jednostka):
    uczelnia.pokazuj_autorow_bez_prac_w_przegladaniu_danych = True
    uczelnia.save()
    _autor(WIDOCZNY, jednostka)
    _autor(UKRYTY, jednostka, pokazuj_w_indeksie=False)

    res = client.get(reverse("bpp:browse_autorzy"))

    tresc = res.content.decode()
    assert WIDOCZNY in tresc
    assert UKRYTY not in tresc


@pytest.mark.django_db
def test_indeks_autorow_wyszukiwanie_pomija_ukrytego(client, uczelnia, jednostka):
    uczelnia.pokazuj_autorow_bez_prac_w_przegladaniu_danych = True
    uczelnia.save()
    ukryty = _autor(UKRYTY, jednostka, pokazuj_w_indeksie=False)
    widoczny = _autor(UKRYTY + "bis", jednostka)

    res = client.get(reverse("bpp:browse_autorzy"), {"search": UKRYTY})

    # Fraza wraca w polu wyszukiwania, więc sprawdzamy wyniki, nie cały HTML.
    wyniki = list(res.context["object_list"])
    assert widoczny in wyniki
    assert ukryty not in wyniki
    assert ukryty.slug not in res.content.decode()


# --- Publiczny picker autorów (autocomplete) --------------------------------


def _pks_public_autocomplete(request):
    from bpp.views.autocomplete.authors import PublicAutorAutocomplete

    view = PublicAutorAutocomplete()
    view.request = request
    view.q = ""
    return set(view.get_queryset().values_list("pk", flat=True))


@pytest.mark.django_db
def test_public_autor_autocomplete_pomija_ukrytego_w_wyszukiwaniu(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, settings
):
    """Regresja FD#561 (multi-hosted): „Pokazuj w wyszukiwaniu” obejmuje
    publiczne listy wyboru, a zawężenie do uczelni oglądającego zostaje."""
    settings.ALLOWED_HOSTS = ["*"]
    widoczny = baker.make(Autor, aktualna_jednostka=jednostka_uczelnia1)
    ukryty = baker.make(
        Autor, aktualna_jednostka=jednostka_uczelnia1, pokazuj_w_wyszukiwaniu=False
    )

    pks = _pks_public_autocomplete(make_request_for_site(site1))

    assert widoczny.pk in pks
    assert ukryty.pk not in pks


@pytest.mark.django_db
def test_public_autor_autocomplete_redakcja_widzi_ukrytego(
    uczelnia1, site1, jednostka_uczelnia1, django_user_model, settings
):
    settings.ALLOWED_HOSTS = ["*"]
    ukryty = baker.make(
        Autor, aktualna_jednostka=jednostka_uczelnia1, pokazuj_w_wyszukiwaniu=False
    )
    redaktor = django_user_model.objects.create_user("redaktor", password="x")
    redaktor.groups.add(Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0])

    pks = _pks_public_autocomplete(make_request_for_site(site1, user=redaktor))

    assert ukryty.pk in pks


# --- Akcje masowe w adminie a publiczny cache -------------------------------


@pytest.fixture
def cache_locmem(settings):
    from django.core.cache import cache

    poprzednie = settings.CACHES
    settings.CACHES = {
        **poprzednie,
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-fd561",
        },
    }
    cache.clear()
    yield cache
    cache.clear()
    settings.CACHES = poprzednie


@pytest.mark.django_db
@pytest.mark.parametrize("akcja", ["ustaw_pokazuj_false", "ustaw_pokazuj_true"])
def test_akcja_ukryj_pokaz_uniewaznia_cache_publiczny(
    akcja, admin_user, cache_locmem, django_capture_on_commit_callbacks
):
    """Regresja FD#561: akcje „Ukryj/Pokaż wybranych autorów…” robią
    ``update()``, który nie wysyła sygnałów — publiczne strony (jednostka,
    indeks) zostawały w cache'u ze starą listą autorów do 10 minut."""
    from django.contrib.admin.sites import AdminSite
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.db import transaction
    from django.test import RequestFactory

    from bpp.admin import actions
    from bpp.admin.autor import AutorAdmin
    from bpp.views.cache_publiczny import _generacja

    autor = baker.make(
        Autor,
        pokazuj_na_stronie_jednostki=akcja == "ustaw_pokazuj_false",
        pokazuj_w_rankingu=akcja == "ustaw_pokazuj_false",
    )
    request = RequestFactory().get("/admin/bpp/autor/")
    request.user = admin_user
    request.session = {}
    request._messages = FallbackStorage(request)

    transaction.get_connection().run_on_commit.clear()
    przed = _generacja()
    with django_capture_on_commit_callbacks(execute=True):
        getattr(actions, akcja)(
            AutorAdmin(Autor, AdminSite()), request, Autor.objects.filter(pk=autor.pk)
        )

    assert _generacja() != przed
