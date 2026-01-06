"""
Author-related autocomplete tests.

This module contains tests for:
- Author autocomplete functionality
- Discipline assignment autocomplete
- Status korekty autocomplete
- Author creation via autocomplete
"""

import json

import pytest

from bpp.models import Autor_Dyscyplina
from bpp.models.autor import Autor
from bpp.views.autocomplete import (
    AutorAutocomplete,
    PublicStatusKorektyAutocomplete,
)


@pytest.mark.uruchom_tylko_bez_microsoft_auth
def test_dyscyplina_naukowa_przypisanie_autocomplete(
    app, autor_jan_kowalski, dyscyplina1, dyscyplina2, rok
):
    """Test discipline assignment autocomplete with various states."""
    from django.urls import reverse

    res = app.get(reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"))
    assert res.json["results"][0]["text"] == "Podaj autora"

    f = json.dumps({"autor": str(autor_jan_kowalski.id)})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "Podaj rok"

    f = json.dumps({"autor": str(autor_jan_kowalski.id), "rok": "fa"})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "Nieprawidłowy rok"

    f = json.dumps({"autor": str(autor_jan_kowalski.id), "rok": -10})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "Nieprawidłowy rok"

    f = json.dumps({"autor": str(autor_jan_kowalski.id), "rok": rok})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == f"Brak przypisania dla roku {rok}"

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina2,
        subdyscyplina_naukowa=dyscyplina1,
    )

    f = json.dumps({"autor": str(autor_jan_kowalski.id), "rok": rok})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "druga dyscyplina"

    f = json.dumps({"autor": str(autor_jan_kowalski.id), "rok": rok})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"),
        {"forward": f, "q": "memetyka"},
    )
    assert res.json["results"][0]["text"] == "memetyka stosowana"


@pytest.mark.uruchom_tylko_bez_microsoft_auth
def test_dyscyplina_naukowa_przypisanie_autocomplete_brak_autora(
    app,
):
    """Test discipline assignment autocomplete when author is missing."""
    from django.urls import reverse

    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"),
        params={"forward": '{"autor": "", "rok": "2022"}'},
    )
    assert res.status_code == 200
    assert res.json["results"][0]["text"] == "Podaj autora"


@pytest.mark.uruchom_tylko_bez_microsoft_auth
def test_dyscyplina_naukowa_przypisanie_autocomplete_brak_drugiej(
    app, autor_jan_kowalski, dyscyplina1, dyscyplina2, rok
):
    """Test discipline assignment autocomplete when second discipline is missing."""
    from django.urls import reverse

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina2,
    )

    f = json.dumps({"autor": str(autor_jan_kowalski.id), "rok": str(rok)})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "druga dyscyplina"


@pytest.mark.django_db
def test_AutorAutocomplete_create_bug_1():
    """Test author creation via autocomplete with various input formats."""
    assert Autor.objects.count() == 0

    def autocomplete(s):
        a = AutorAutocomplete()
        a.q = s
        res = a.create_object(s)
        return res

    res = autocomplete("  fubar")

    assert res.pk == -1
    assert Autor.objects.count() == 0

    res = autocomplete("  fubar baz quux")
    assert res.pk != -1
    assert Autor.objects.count() == 1
    assert Autor.objects.first().nazwisko == "Fubar"
    assert Autor.objects.first().imiona == "Baz Quux"


@pytest.mark.django_db
def test_Status_KorektyAutocomplete(statusy_korekt):
    """Test status korekty autocomplete filtering."""
    s = PublicStatusKorektyAutocomplete()
    s.q = None
    assert len(s.get_queryset()) == len(statusy_korekt)

    s = PublicStatusKorektyAutocomplete()
    s.q = "przed"
    assert len(s.get_queryset()) == 1
