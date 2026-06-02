"""Testy tolerancyjnego ManifestStaticFilesStorage (issue #269).

`ManifestStaticFilesStorage` hashuje każdy `{% static %}` z osobna
(`name.<content-hash>.ext`) i przepisuje odwołania `url(...)` /
`sourceMappingURL` wewnątrz CSS/JS na wersje hashowane — cache-bustuje cały
long-tail statyków. Vanilla wersja jednak przerywa `collectstatic` na
pierwszym nierozwiązywalnym odwołaniu (target, którego nie ma w zebranych
statykach — vendored sprite'y grappelli/jqueryui, sourcemapy foundation).
Tolerancyjna subklasa łapie ten `ValueError` i zostawia odwołanie pod nazwą
oryginalną zamiast wywalać build.
"""

import pytest
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from django.core.files.base import ContentFile
from django.test import override_settings

from django_bpp.storage import TolerantManifestStaticFilesStorage


def test_manifest_strict_is_disabled():
    # Runtime: brakujący wpis w manifeście ma zwracać nazwę nie-hashowaną
    # zamiast rzucać "Missing staticfiles manifest entry" (chroni dev/testy
    # bez collectstatic oraz 132 vendored-refy serwowane pod starą nazwą).
    assert TolerantManifestStaticFilesStorage.manifest_strict is False


def test_unresolvable_reference_keeps_original_name():
    # hashed_name() z content=None sprawdza istnienie pliku; gdy targetu nie
    # ma, vanilla rzuca ValueError i przerywa collectstatic. Subklasa zwraca
    # nazwę oryginalną (build-time tolerancja — to jest sedno issue #269).
    storage = TolerantManifestStaticFilesStorage()
    missing = "django_bpp/__tdd_nonexistent_probe__.map"
    assert storage.hashed_name(missing) == missing


def test_resolvable_content_is_still_hashed():
    # Happy-path: gdy treść jest dostępna, hashed_name deleguje do super i
    # zwraca nazwę z content-hashem (sanity — nie zepsuliśmy hashowania).
    storage = TolerantManifestStaticFilesStorage()
    hashed = storage.hashed_name("app.js", content=ContentFile(b"console.log(1);"))
    assert hashed != "app.js"
    assert hashed.startswith("app.")
    assert hashed.endswith(".js")


@override_settings(DEBUG=False)
def test_missing_manifest_entry_falls_back_instead_of_raising():
    # Runtime safety (DEBUG=False, hashing aktywne): wpis spoza manifestu.
    # Vanilla (manifest_strict=True) rzuca "Missing staticfiles manifest
    # entry" — to był objaw, którego baliśmy się w produkcji/testach. Nasza
    # subklasa (manifest_strict=False) zwraca URL nie-hashowany. Kontrast z
    # vanilla dowodzi, że test nie jest pusty (manifest_strict naprawdę działa).
    probe = "bpp/js/__nonexistent_runtime_probe__.js"
    with pytest.raises(ValueError):
        ManifestStaticFilesStorage().url(probe)
    assert TolerantManifestStaticFilesStorage().url(probe) == "/static/" + probe


@override_settings(DEBUG=False)
def test_existing_file_without_manifest_is_not_hashed_on_the_fly(tmp_path):
    # Regression (bug: testy padały lokalnie, przechodziły na CI). Gdy
    # STATIC_ROOT zawiera plik fizyczny, ale NIE ma manifestu
    # (`staticfiles.json`) — typowy stan lokalny ze starym `staticroot`
    # sprzed wprowadzenia Manifestu — vanilla `ManifestFilesMixin.stored_name`
    # z `manifest_strict=False` liczy content-hash w locie i zwraca
    # `foo.<hash>.css`. Plik z tą nazwą NIE istnieje na dysku (stary
    # collectstatic wyprodukował tylko nie-hashowaną kopię), więc
    # django-compressor i webtest dostają `could not be found` / 404.
    #
    # Bez manifestu (jedyne źródło prawdy dla hashy jest puste) musimy
    # serwować nazwę ORYGINALNĄ — realny plik zaserwuje finder / runserver /
    # whitenoise. Kontrast z `ManifestStaticFilesStorage` (poniżej) dowodzi,
    # że to nasza subklasa, nie domyślne zachowanie Django, daje ten wynik.
    (tmp_path / "foo.css").write_text("body{color:red}")
    storage = TolerantManifestStaticFilesStorage(location=str(tmp_path))
    assert storage.hashed_files == {}  # brak manifestu

    # Vanilla z manifest_strict=False (nasza konfiguracja) fabrykuje martwą
    # nazwę hashowaną (foo.<hash>.css) — to jest dokładnie bug:
    vanilla = ManifestStaticFilesStorage(location=str(tmp_path))
    vanilla.manifest_strict = False
    assert vanilla.stored_name("foo.css") != "foo.css"

    # Subklasa zwraca nazwę oryginalną — i runtime'owy url() też:
    assert storage.stored_name("foo.css") == "foo.css"
    assert storage.url("foo.css") == "/static/foo.css"


@override_settings(DEBUG=False)
def test_present_manifest_still_hashes(tmp_path):
    # Strona przeciwna do regresji: gdy manifest ISTNIEJE (produkcja, `.baked`
    # po collectstatic), cache-busting długiego ogona musi działać 1:1 jak w
    # vanilla — `stored_name` deleguje do super i zwraca nazwę z manifestu.
    # Override z `not self.hashed_files` jest wąski i NIE dotyka tej ścieżki.
    storage = TolerantManifestStaticFilesStorage(location=str(tmp_path))
    storage.hashed_files = {"foo.css": "foo.deadbeef0123.css"}
    assert storage.stored_name("foo.css") == "foo.deadbeef0123.css"
    assert storage.url("foo.css") == "/static/foo.deadbeef0123.css"


@override_settings(DEBUG=True)
def test_url_in_debug_returns_unhashed_without_manifest():
    # Keystone "jedna klasa storage wszędzie": w DEBUG `HashedFilesMixin.url()`
    # robi short-circuit i zwraca nazwę nie-hashowaną BEZ zaglądania do
    # manifestu — dlatego dev/runserver działa bez collectstatic i bez crasha.
    probe = "bpp/js/__nonexistent_debug_probe__.js"
    assert TolerantManifestStaticFilesStorage().url(probe) == "/static/" + probe
