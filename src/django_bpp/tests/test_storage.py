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


@override_settings(DEBUG=True)
def test_url_in_debug_returns_unhashed_without_manifest():
    # Keystone "jedna klasa storage wszędzie": w DEBUG `HashedFilesMixin.url()`
    # robi short-circuit i zwraca nazwę nie-hashowaną BEZ zaglądania do
    # manifestu — dlatego dev/runserver działa bez collectstatic i bez crasha.
    probe = "bpp/js/__nonexistent_debug_probe__.js"
    assert TolerantManifestStaticFilesStorage().url(probe) == "/static/" + probe
