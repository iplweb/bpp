"""Testy charakteryzujące widok ``przemapuj_prace``.

Pinują bieżące zachowanie PRZED refaktorem (zdjęcie ``# noqa: C901``).
Pokrywają wszystkie gałęzie: GET, POST/preview, POST/confirm (valid +
invalid + wyjątek w transakcji) oraz POST bez znanego przycisku.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Jednostka,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Zrodlo,
)

from .models import PrzemapoaniePracAutora

User = get_user_model()


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="charadmin", password="testpass", is_staff=True, is_superuser=True
    )


@pytest.fixture
def kl(admin_user):
    client = Client()
    client.login(username="charadmin", password="testpass")
    return client


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia, nazwa="Char Univ")


@pytest.fixture
def jed_a(uczelnia):
    return baker.make(Jednostka, nazwa="AAA Jed", skrot="AAA", uczelnia=uczelnia)


@pytest.fixture
def jed_b(uczelnia):
    return baker.make(Jednostka, nazwa="BBB Jed", skrot="BBB", uczelnia=uczelnia)


@pytest.fixture
def jed_c(uczelnia):
    return baker.make(Jednostka, nazwa="CCC Jed", skrot="CCC", uczelnia=uczelnia)


@pytest.fixture
def autor(jed_b):
    return baker.make(Autor, imiona="Jan", nazwisko="Char", aktualna_jednostka=jed_b)


@pytest.fixture
def zrodlo(db):
    return baker.make(Zrodlo, nazwa="Char Journal", skrot="CJ")


def _url(autor):
    return reverse(
        "przemapuj_prace_autora:przemapuj_prace", kwargs={"autor_id": autor.pk}
    )


@pytest.fixture
def autor_with_mixed_works(autor, jed_a, jed_b, jed_c, zrodlo):
    """Autor z pracami ciągłymi (2 w A, 1 w B) i zwartymi (1 w A, 1 w C)."""
    for tytul in ("C1", "C2"):
        wc = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=tytul, zrodlo=zrodlo)
        baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, autor=autor, jednostka=jed_a)
    wc3 = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="C3", zrodlo=zrodlo)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc3, autor=autor, jednostka=jed_b)

    wz1 = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Z1")
    baker.make(Wydawnictwo_Zwarte_Autor, rekord=wz1, autor=autor, jednostka=jed_a)
    wz2 = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Z2")
    baker.make(Wydawnictwo_Zwarte_Autor, rekord=wz2, autor=autor, jednostka=jed_c)
    return autor


@pytest.mark.django_db
def test_get_renders_unbound_form_and_stats(
    kl, autor_with_mixed_works, jed_a, jed_b, jed_c
):
    response = kl.get(_url(autor_with_mixed_works))
    assert response.status_code == 200
    ctx = response.context
    assert ctx["preview"] is False
    assert ctx["autor"] == autor_with_mixed_works
    assert ctx["form"].is_bound is False
    assert "historia" in ctx

    stats = {s["id"]: s for s in ctx["jednostki_stats"]}
    assert stats[jed_a.id]["prace_ciagle"] == 2
    assert stats[jed_a.id]["prace_zwarte"] == 1
    assert stats[jed_a.id]["razem"] == 3
    assert stats[jed_b.id]["prace_ciagle"] == 1
    assert stats[jed_b.id]["prace_zwarte"] == 0
    assert stats[jed_b.id]["razem"] == 1
    assert stats[jed_c.id]["prace_ciagle"] == 0
    assert stats[jed_c.id]["prace_zwarte"] == 1
    # Posortowane po nazwie
    nazwy = [s["nazwa"] for s in ctx["jednostki_stats"]]
    assert nazwy == sorted(nazwy)


@pytest.mark.django_db
def test_post_preview_valid(kl, autor_with_mixed_works, jed_a, jed_b):
    response = kl.post(
        _url(autor_with_mixed_works),
        {"jednostka_z": jed_a.pk, "jednostka_do": jed_b.pk, "preview": "1"},
    )
    assert response.status_code == 200
    ctx = response.context
    assert ctx["preview"] is True
    assert ctx["jednostka_z"] == jed_a
    assert ctx["jednostka_do"] == jed_b
    assert ctx["liczba_prac_ciaglych"] == 2
    assert ctx["liczba_prac_zwartych"] == 1
    assert ctx["total_count"] == 3
    assert len(list(ctx["prace_ciagle"])) == 2
    assert len(list(ctx["prace_zwarte"])) == 1


@pytest.mark.django_db
def test_post_confirm_valid_redirects_and_logs(
    kl, autor_with_mixed_works, jed_a, jed_b
):
    response = kl.post(
        _url(autor_with_mixed_works),
        {"jednostka_z": jed_a.pk, "jednostka_do": jed_b.pk, "confirm": "1"},
    )
    assert response.status_code == 302
    assert response.url == _url(autor_with_mixed_works)

    log = PrzemapoaniePracAutora.objects.get(autor=autor_with_mixed_works)
    assert log.liczba_prac_ciaglych == 2
    assert log.liczba_prac_zwartych == 1
    assert log.jednostka_z == jed_a
    assert log.jednostka_do == jed_b
    # Prace zostały faktycznie przeniesione
    assert (
        Wydawnictwo_Ciagle_Autor.objects.filter(
            autor=autor_with_mixed_works, jednostka=jed_b
        ).count()
        == 3
    )


@pytest.mark.django_db
def test_post_confirm_invalid_form_same_unit(kl, autor_with_mixed_works, jed_a):
    """jednostka_z == jednostka_do → form invalid, brak logu, render 200."""
    response = kl.post(
        _url(autor_with_mixed_works),
        {"jednostka_z": jed_a.pk, "jednostka_do": jed_a.pk, "confirm": "1"},
    )
    assert response.status_code == 200
    assert response.context["preview"] is False
    assert not PrzemapoaniePracAutora.objects.filter(
        autor=autor_with_mixed_works
    ).exists()


@pytest.mark.django_db
def test_post_preview_invalid_form(kl, autor_with_mixed_works, jed_a):
    response = kl.post(
        _url(autor_with_mixed_works),
        {"jednostka_z": jed_a.pk, "jednostka_do": jed_a.pk, "preview": "1"},
    )
    assert response.status_code == 200
    assert response.context["preview"] is False


@pytest.mark.django_db
def test_post_without_known_button(kl, autor_with_mixed_works, jed_a, jed_b):
    """POST bez 'confirm' ani 'preview' → spada do dolnego renderu (200)."""
    response = kl.post(
        _url(autor_with_mixed_works),
        {"jednostka_z": jed_a.pk, "jednostka_do": jed_b.pk},
    )
    assert response.status_code == 200
    assert response.context["preview"] is False
    assert not PrzemapoaniePracAutora.objects.filter(
        autor=autor_with_mixed_works
    ).exists()


@pytest.mark.django_db
def test_post_confirm_exception_shows_error(
    kl, autor_with_mixed_works, jed_a, jed_b, monkeypatch
):
    """Wyjątek w transakcji → messages.error + render 200 (bez redirectu)."""

    def boom(*args, **kwargs):
        raise RuntimeError("wybuch")

    monkeypatch.setattr(
        "przemapuj_prace_autora.views.PrzemapoaniePracAutora.objects.create",
        boom,
    )
    response = kl.post(
        _url(autor_with_mixed_works),
        {"jednostka_z": jed_a.pk, "jednostka_do": jed_b.pk, "confirm": "1"},
        follow=False,
    )
    assert response.status_code == 200
    assert response.context["preview"] is False
    msgs = [m.message for m in response.context["messages"]]
    assert any("Wystąpił błąd podczas przemapowania prac" in m for m in msgs)
    # Transakcja wycofana — log nie powstał
    assert not PrzemapoaniePracAutora.objects.filter(
        autor=autor_with_mixed_works
    ).exists()
