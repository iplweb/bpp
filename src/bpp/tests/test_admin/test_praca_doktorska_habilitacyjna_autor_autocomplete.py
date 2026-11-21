"""FD#445: author pickers in the doctoral/habilitation thesis admin must offer
ALL authors -- including people from a foreign unit and former employees --
otherwise editors cannot find them and create duplicate ``Autor`` profiles."""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.admin.praca_doktorska import Praca_DoktorskaForm
from bpp.admin.praca_habilitacyjna import Praca_HabilitacyjnaForm
from bpp.models import Autor_Jednostka


@pytest.mark.parametrize(
    "form_class,field_name",
    [
        (Praca_DoktorskaForm, "autor"),
        (Praca_DoktorskaForm, "promotor"),
        (Praca_HabilitacyjnaForm, "autor"),
    ],
)
def test_autor_widget_uses_full_autor_autocomplete(form_class, field_name):
    widget = form_class.base_fields[field_name].widget
    # DAL keeps the configured name in ``_url``; ``url`` is the reversed path.
    assert widget._url == "bpp:autor-autocomplete"
    assert widget.url == reverse("bpp:autor-autocomplete")


def _autocomplete_pks(admin_client, url, q):
    res = admin_client.get(url, data={"q": q})
    assert res.status_code == 200
    pks = set()
    for item in res.json()["results"]:
        for child in item.get("children", [item]):
            # Skip optgroup headers (id=None) and the "Create ..." option
            # (its id is the typed text, not a pk).
            if str(child.get("id") or "").isdigit():
                pks.add(int(child["id"]))
    return pks


@pytest.mark.django_db
@pytest.mark.parametrize(
    "form_class,field_name",
    [
        (Praca_DoktorskaForm, "autor"),
        (Praca_DoktorskaForm, "promotor"),
        (Praca_HabilitacyjnaForm, "autor"),
    ],
)
def test_autor_autocomplete_finds_former_and_foreign_authors(
    admin_client, uczelnia, jednostka, obca_jednostka, form_class, field_name
):
    # Hit exactly the endpoint the admin form widget points at.
    url = form_class.base_fields[field_name].widget.url

    byly_pracownik = baker.make("bpp.Autor", nazwisko="Fdczterystabyly", imiona="Jan")
    Autor_Jednostka.objects.create(
        autor=byly_pracownik,
        jednostka=jednostka,
        rozpoczal_prace=date.today() - timedelta(days=3650),
        zakonczyl_prace=date.today() - timedelta(days=365),
    )

    z_obcej = baker.make("bpp.Autor", nazwisko="Fdczterystaobcy", imiona="Anna")
    Autor_Jednostka.objects.create(autor=z_obcej, jednostka=obca_jednostka)

    assert byly_pracownik.pk in _autocomplete_pks(admin_client, url, "Fdczterystabyly")
    assert z_obcej.pk in _autocomplete_pks(admin_client, url, "Fdczterystaobcy")
