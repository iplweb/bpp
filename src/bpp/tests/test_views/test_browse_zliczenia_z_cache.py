"""Zliczenia stron przeglądania (``paginator.count``, literki) idą z cache'a.

Kontekst pomiarowy (baza UML, 68 tys. autorów, 122 tys. rekordów): wejście
na ``/bpp/autorzy/`` kosztowało 409 ms, z czego 337 ms to DWA zapytania,
które nie produkują treści strony — ``COUNT(*)`` paginatora (163 ms) i
``SELECT DISTINCT substr(nazwisko,1,1)`` dla rządka literek (174 ms).
Właściwa strona 50 autorów to 35 ms. Oba zliczenia są identyczne dla
każdego odwiedzającego i zmieniają się tylko przy edycji autorów, a
``Autor`` jest w ``BppConfig.MODELE_INWALIDUJACE_CACHE_PUBLICZNY``, więc
znacznik generacji z ``cache_publiczny`` unieważnia je natychmiast.

Testy celowo używają ZALOGOWANEGO klienta: anonim dostałby całą stronę z
``cache_publiczny`` i drugie wejście nie weszłoby nawet do widoku, więc
nie mierzyłoby tego, co trzeba. Zalogowany omija cache stron i to jemu ten
cache zliczeń realnie skraca oczekiwanie.
"""

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor

# ``settings/test.py`` dziedziczy CACHES["default"] = DummyCache z local.py —
# bez podmiany na LocMem te testy nie mierzyłyby niczego.
LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-browse-zliczenia",
    }
}


@pytest.fixture
def cache_locmem(settings):
    poprzednie = settings.CACHES
    settings.CACHES = {**poprzednie, **LOCMEM}
    cache.clear()
    yield cache
    cache.clear()
    settings.CACHES = poprzednie


@pytest.fixture(autouse=True)
def _zezwol_na_hosty_testowe(settings):
    settings.ALLOWED_HOSTS = ["*"]


def zapytania_zliczajace(ctx):
    """``COUNT(*)`` paginatora po tabeli autorów."""
    return [
        q["sql"]
        for q in ctx.captured_queries
        if "COUNT(*)" in q["sql"].upper() and "bpp_autor" in q["sql"]
    ]


def zapytania_o_literki(ctx):
    """``SELECT DISTINCT substr(...)`` budujące rządek literek."""
    return [q["sql"] for q in ctx.captured_queries if "SUBSTRING" in q["sql"].upper()]


@pytest.fixture
def czysta_kolejka_on_commit(db):
    """Wyczyść unieważnienia zaplanowane przez fixture'y tworzące modele.

    Zamawiaj JAKO OSTATNI — patrz identyczny fixture w
    ``test_cache_publiczny.py``.
    """
    from django.db import transaction

    transaction.get_connection().run_on_commit.clear()
    yield


@pytest.fixture
def autorzy(db):
    baker.make(Autor, nazwisko="Abacki", imiona="Jan", pokazuj=True)
    baker.make(Autor, nazwisko="Babacki", imiona="Ewa", pokazuj=True)
    baker.make(Autor, nazwisko="Cabacki", imiona="Zoja", pokazuj=True)


@pytest.mark.django_db
def test_distinct_literek_nie_wciaga_kolumny_sortujacej(autorzy, uczelnia):
    """``DISTINCT`` ma deduplikować po literce, nie po parze (sort, literka).

    ``Autor.Meta.ordering = ["sort"]`` sprawia, że Django dokłada kolumnę
    sortującą do ``SELECT DISTINCT`` — wtedy DISTINCT nie deduplikuje
    niczego sensownego i baza zwraca tyle wierszy, ilu autorów, zamiast
    tylu, ile liter.
    """
    from bpp.views.browse import get_available_letters

    with CaptureQueriesContext(connection) as ctx:
        get_available_letters(Autor.objects.filter(pokazuj=True), "nazwisko")

    (sql,) = zapytania_o_literki(ctx)
    assert "sort" not in sql.lower(), (
        "Kolumna sortująca wyciekła do SELECT DISTINCT — DISTINCT "
        f"deduplikuje po (sort, literka), nie po literce. SQL: {sql}"
    )


@pytest.mark.django_db
def test_drugie_wejscie_nie_powtarza_countu_ani_zapytania_o_literki(
    autorzy, uczelnia, cache_locmem, logged_in_client
):
    """Zliczenia liczą się raz; kolejne wejścia biorą je z cache'a."""
    url = reverse("bpp:browse_autorzy")

    with CaptureQueriesContext(connection) as pierwsze:
        assert logged_in_client.get(url).status_code == 200
    assert len(zapytania_zliczajace(pierwsze)) == 1
    assert len(zapytania_o_literki(pierwsze)) == 1

    with CaptureQueriesContext(connection) as drugie:
        assert logged_in_client.get(url).status_code == 200

    assert zapytania_zliczajace(drugie) == [], (
        "COUNT(*) paginatora policzył się drugi raz — na bazie UML to "
        "163 ms zmarnowane na liczbę, która się nie zmieniła."
    )
    assert zapytania_o_literki(drugie) == [], (
        "Zapytanie o literki poszło drugi raz — na bazie UML to 174 ms "
        "zmarnowane na rządek pigułek, który się nie zmienił."
    )


@pytest.mark.django_db
def test_zapis_autora_uniewaznia_zapamietane_zliczenia(
    autorzy,
    uczelnia,
    cache_locmem,
    logged_in_client,
    django_capture_on_commit_callbacks,
    czysta_kolejka_on_commit,
):
    """Nowy autor z nową literą pojawia się natychmiast, nie po TTL.

    Unieważnienie leci przez ``transaction.on_commit``, a pod
    ``django_db`` transakcja testu nigdy nie commituje — stąd
    ``django_capture_on_commit_callbacks``. Ten sam wzorzec co w
    ``test_cache_publiczny.py``.
    """
    url = reverse("bpp:browse_autorzy")

    pierwsza = logged_in_client.get(url)
    assert pierwsza.context["paginator"].count == 3
    assert "Z" not in pierwsza.context["available_letters"]

    with django_capture_on_commit_callbacks(execute=True):
        baker.make(Autor, nazwisko="Zabacki", imiona="Olga", pokazuj=True)

    druga = logged_in_client.get(url)
    assert druga.context["paginator"].count == 4, (
        "Licznik autorów nie odświeżył się po zapisie — sygnał "
        "post_save modelu Autor ma bumpować generację cache'a."
    )
    assert "Z" in druga.context["available_letters"], (
        "Nowa litera nie pojawiła się w rządku po zapisie autora."
    )


@pytest.mark.django_db
def test_zapamietane_zliczenia_nie_wyciekaja_miedzy_literami(
    autorzy, uczelnia, cache_locmem, logged_in_client
):
    """Każda litera ma własny licznik — nie współdzielą wpisu w cache'u."""
    wszyscy = logged_in_client.get(reverse("bpp:browse_autorzy"))
    assert wszyscy.context["paginator"].count == 3

    litera_a = logged_in_client.get(
        reverse("bpp:browse_autorzy_literka", kwargs={"literka": "A"})
    )
    assert litera_a.context["paginator"].count == 1, (
        "Strona litery A dostała licznik policzony dla 'wszyscy' — "
        "klucz cache'a nie rozróżnia wybranej litery."
    )


@pytest.mark.django_db
def test_bez_hosta_liczymy_swiezo_zamiast_zgadywac_klucz(autorzy, uczelnia):
    """Nie da się ustalić hosta → licz świeżo, ale NIE zapamiętuj.

    Host izoluje uczelnie w kluczu cache'a. Gdyby przy jego braku podstawić
    stałą (np. pusty string), wszystkie uczelnie trafiłyby do jednego
    wpisu i licznik jednej pokazałby się na stronie drugiej. Bezpieczny
    wariant to policzyć bez zapamiętywania.

    Nie jest to przypadek teoretyczny: widoki bywają wołane z obiektem
    request niebędącym ``HttpRequest`` (patrz ``FakeRequest`` w
    ``test_views_browse.py``).
    """
    from bpp.views.browse import zliczenie_z_cache

    class RequestBezHosta:
        pass

    wywolania = []

    def oblicz():
        wywolania.append(1)
        return 42

    request = RequestBezHosta()
    assert zliczenie_z_cache(request, "cokolwiek", oblicz) == 42
    assert zliczenie_z_cache(request, "cokolwiek", oblicz) == 42
    assert len(wywolania) == 2, (
        "Wartość została zapamiętana mimo nieznanego hosta — to ryzyko "
        "pokazania licznika jednej uczelni na stronie drugiej."
    )


@pytest.mark.django_db
def test_zapamietany_count_nie_wycieka_miedzy_wyszukiwaniami(
    autorzy, uczelnia, cache_locmem, logged_in_client
):
    """Dwa różne wyszukiwania nie mogą dzielić jednego licznika."""
    url = reverse("bpp:browse_autorzy")

    pierwsze = logged_in_client.get(url, {"search": "Abacki"})
    drugie = logged_in_client.get(url, {"search": "Babacki"})

    assert pierwsze.context["paginator"].count == 1
    assert drugie.context["paginator"].count == 1
    assert [a.nazwisko for a in pierwsze.context["object_list"]] == ["Abacki"]
    assert [a.nazwisko for a in drugie.context["object_list"]] == ["Babacki"], (
        "Drugie wyszukiwanie zwróciło wynik pierwszego — klucz cache'a "
        "nie rozróżnia frazy szukanej."
    )
