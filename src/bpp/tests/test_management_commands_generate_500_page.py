"""Testy dla `generate_500_page` w trybie multi-hosted (per-domena).

Command renderuje statyczną stronę 500 dla nginx. W instalacji multi-hosted
(jedna baza, wiele `Site`/`Uczelnia` mapowanych po domenie) potrzebujemy
osobnej strony 500 per domena — `$STATIC_ROOT/500/<domena>.html` — plus
generyczny fallback `$STATIC_ROOT/500.html`.
"""

import pytest
from django.contrib.sites.models import Site
from django.core.management import call_command

from bpp.models import Uczelnia


def _make_uczelnia(domain, skrot, nazwa):
    site = Site.objects.create(domain=domain, name=nazwa)
    return Uczelnia.objects.create(skrot=skrot, nazwa=nazwa, site=site)


@pytest.mark.django_db
def test_generate_500_page_writes_per_domain_files(settings, tmp_path):
    """Każda domena dostaje własną stronę 500 z brandingiem swojej uczelni."""
    settings.STATIC_ROOT = str(tmp_path)
    _make_uczelnia("alfa.example.test", "ALFAUNIQ", "Alfa Uczelnia")
    _make_uczelnia("beta.example.test", "BETAUNIQ", "Beta Uczelnia")

    call_command("generate_500_page")

    html_alfa = (tmp_path / "500" / "alfa.example.test.html").read_text("utf-8")
    html_beta = (tmp_path / "500" / "beta.example.test.html").read_text("utf-8")

    # Górny pasek base.html renderuje {{ uczelnia.skrot }} — każda strona
    # musi nieść skrót SWOJEJ uczelni i nie zawierać skrótu drugiej.
    assert "ALFAUNIQ" in html_alfa and "BETAUNIQ" not in html_alfa
    assert "BETAUNIQ" in html_beta and "ALFAUNIQ" not in html_beta


@pytest.mark.django_db
def test_generate_500_page_writes_generic_fallback(settings, tmp_path):
    """Generyczny `$STATIC_ROOT/500.html` powstaje (fallback dla nginx)."""
    settings.STATIC_ROOT = str(tmp_path)
    _make_uczelnia("alfa.example.test", "ALFAUNIQ", "Alfa Uczelnia")
    _make_uczelnia("beta.example.test", "BETAUNIQ", "Beta Uczelnia")

    call_command("generate_500_page")

    generic = tmp_path / "500.html"
    assert generic.exists()
    assert "Wystąpił błąd serwera" in generic.read_text("utf-8")


@pytest.mark.django_db
def test_generate_500_page_robust_against_disallowed_host(settings, tmp_path):
    """Command nie wywala się DisallowedHost gdy `testserver` nie jest w
    ALLOWED_HOSTS — fałszywy request nigdy nie używa hosta `testserver`."""
    settings.STATIC_ROOT = str(tmp_path)
    settings.ALLOWED_HOSTS = ["alfa.example.test"]  # bez "testserver"
    _make_uczelnia("alfa.example.test", "ALFAUNIQ", "Alfa Uczelnia")

    # Nie może rzucić django.core.exceptions.DisallowedHost.
    call_command("generate_500_page")

    assert (tmp_path / "500" / "alfa.example.test.html").exists()


@pytest.mark.django_db
def test_generate_500_page_succeeds_with_no_uczelnia(settings, tmp_path):
    """Świeża instalacja: ZERO obiektów Uczelnia — generacja musi się udać
    (neutralna strona), bez wyjątku. Entrypoint woła to po `migrate` na pustej
    bazie, zanim setup wizard utworzy uczelnię."""
    settings.STATIC_ROOT = str(tmp_path)
    assert not Uczelnia.objects.exists()

    call_command("generate_500_page")

    generic = tmp_path / "500.html"
    assert generic.exists()
    # Neutralna „niezdefiniowana uczelnia" — strona renderuje się poprawnie.
    assert "Wystąpił błąd serwera" in generic.read_text("utf-8")
