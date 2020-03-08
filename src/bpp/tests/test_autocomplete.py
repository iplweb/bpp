# -*- encoding: utf-8 -*-
import json

import pytest
from django.urls import reverse
from model_mommy import mommy

from bpp.models import Autor_Dyscyplina
from bpp.models.autor import Autor
from bpp.models.konferencja import Konferencja
from bpp.views.autocomplete import (
    AdminNavigationAutocomplete,
    AutorAutocomplete,
    PublicAutorAutocomplete,
)

VALUES = [
    "Zi%C4%99ba+%5C",
    "Zi%C4%99ba+%5C \\",
    'fa\\"fa',
    "'",
    "fa ' fa",
    " ' fa",
    " fa '",
    "fa\\'fa",
    "Zięba \\",
    "Test ; test",
    "test (test)",
    "test & test",
    "test &",
    "& test",
    "; test",
    "test ;",
    ":*",
    ":",
    ":* :* *: *:",
    "",
    "\\",
    "123 \\ 123",
    "\\ 123",
    "123 \\",
    "|K",
]
AUTOCOMPLETES = [
    "bpp:public-autor-autocomplete",
    "bpp:jednostka-widoczna-autocomplete",
    "bpp:dyscyplina-autocomplete",
]


@pytest.mark.django_db
@pytest.mark.parametrize("autocomplete_name", AUTOCOMPLETES)
@pytest.mark.parametrize("qstr", VALUES)
def test_autocomplete_bug_1(autocomplete_name, qstr, client):
    res = client.get(reverse(autocomplete_name), data={"q": qstr})
    assert res.status_code == 200


@pytest.mark.django_db
def test_admin_konferencje():
    "Upewnij się, że konferencje wyskakują w AdminAutoComplete"
    k = mommy.make(Konferencja, nazwa="test 54")
    a = AdminNavigationAutocomplete()
    a.q = "test 54"
    assert k in a.get_queryset()


@pytest.mark.django_db
def test_public_autor_autocomplete_bug_1():
    a = PublicAutorAutocomplete()
    a.q = "a (b)"
    assert list(a.get_queryset()) is not None

    a.q = "a\tb"
    assert list(a.get_queryset()) is not None


def test_dyscyplina_naukowa_przypisanie_autocomplete(
    app, autor_jan_kowalski, dyscyplina1, dyscyplina2, rok
):
    res = app.get(reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"))
    assert res.json["results"][0]["text"] == "Podaj autora"

    f = json.dumps({"autor": autor_jan_kowalski.id})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "Podaj rok"

    f = json.dumps({"autor": autor_jan_kowalski.id, "rok": "fa"})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "Nieprawidłowy rok"

    f = json.dumps({"autor": autor_jan_kowalski.id, "rok": -10})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "Nieprawidłowy rok"

    f = json.dumps({"autor": autor_jan_kowalski.id, "rok": rok})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "Brak przypisania dla roku %i" % rok

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina2,
        subdyscyplina_naukowa=dyscyplina1,
    )

    f = json.dumps({"autor": autor_jan_kowalski.id, "rok": rok})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "druga dyscyplina"

    f = json.dumps({"autor": autor_jan_kowalski.id, "rok": rok})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"),
        {"forward": f, "q": "memetyka"},
    )
    assert res.json["results"][0]["text"] == "memetyka stosowana"


def test_dyscyplina_naukowa_przypisanie_autocomplete_brak_drugiej(
    app, autor_jan_kowalski, dyscyplina1, dyscyplina2, rok
):

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok, dyscyplina_naukowa=dyscyplina2,
    )

    f = json.dumps({"autor": autor_jan_kowalski.id, "rok": rok})
    res = app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": f}
    )
    assert res.json["results"][0]["text"] == "druga dyscyplina"


def test_wydawca_autocomplete(admin_client):
    res = admin_client.get(reverse("bpp:wydawca-autocomplete"))
    assert res.status_code == 200


def test_tsquery_bug1(admin_client):
    # Tak, ktoś kiedyś wkleił taki oto ciąg znaków w wyszukiwanie.
    res = admin_client.get(
        "/bpp/public-autor-autocomplete/?q=Nazwa%20raportu%3A%09raport%20slot%C3%B3w"
        "%20-%20autor%09%09%09%09%09%09%20Autor%3A%09Krawiec%20Marcela%09%09%09%09%09"
        "%09%20Dyscyplina%3A%09rolnictwo%20i%20ogrodnictwo%20(4.2)%09%09%09%09%09%09"
        "%20Od%20roku%3A%092019%09%09%09%09%09%09%20Do%20roku%3A%092020%09%09%09%09%09"
        "%09%20Wygenerowano%3A%092020-02-14%207%3A19%3A44%09%09%09%09%09%09%20Wersja%20"
        "oprogramowania%20BPP%09202002.15%09%09%09%09%09%09%20%09%09%09%09%09%09%09%20"
        "Tytu%C5%82%20oryginalny%09Autorzy%09Rok%09%C5%B9r%C3%B3d%C5%82o%09Dyscyplina%09"
        "Punkty%20PK%09Punkty%20dla%20autora%09Slot%20Impact%20of%20seed%20light%20"
        "stimulation%20on%20the%20mechanical%20strength%20and%20photosynthetic%20pigments"
        "%20content%20in%20the%20scorzonera%20leaves%09Anna%20Ciupak%2C%20Agata%20"
        "Dziwulska-Hunek%2C%20Marcela%20Krawiec%2C%20Bo%C5%BCena%20G%C5%82adyszewska"
        "%092019%09Acta%20Agrophysica%09rolnictwo%20i%20ogrodnictwo%20(4.2)%0920%095"
        "%090%2C25%20EFFECT%20OF%20NATURAL%20FERTILIZATION%20AND%20CALCIUM%20CARBONATE"
        "%20ON%20YIELDING%20AND%20BIOLOGICAL%20VALUE%20OF%20THYME%20(%3Ci%3EThymus%20"
        "vulgaris%3C%2Fi%3E%20L.)%09Katarzyna%20Dzida%2C%20Zenia%20Micha%C5%82oj%C4%87"
        "%2C%20Zbigniew%20Jarosz%2C%20Karolina%20Pitura%2C%20Natalia%20Skubij%2C%20Daniel"
        "%20Skubij%2C%20Marcela%20Krawiec%092019%09Acta%20Scientiarum%20Polonorum-Hortorum"
        "%20Cultus%09rolnictwo%20i%20ogrodnictwo%20(4.2)%0970%0911%2C8322%090%2C169%20"
        "CHEMICAL%20%20AND%20%20NONCHEMICAL%20%20CONTROL%20%20OF%20%20WEEDS%20%20IN%20"
        "%20THE%20%20CULTIVATION%20%20OF%20%20LEMON%20%20BALM%20%20FOR%20%20SEEDS%09Marcela"
        "%20Krawiec%2C%20Andrzej%20Borowy%2C%20Katarzyna%20Dzida%092019%09Acta%20Scientiarum"
        "%20Polonorum-Hortorum%20Cultus%09rolnictwo%20i%20ogrodnictwo%20(4.2)%0970%0923"
        "%2C3333%090%2C3333"
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_AutorAutocomplete_create_bug_1():
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
