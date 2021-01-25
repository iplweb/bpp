import pytest
from django.urls import reverse

from bpp.models import OpcjaWyswietlaniaField
from formdefaults.models import FormRepresentation
from raport_slotow.views import (
    ParametryRaportSlotowEwaluacja,
    UtworzRaportSlotowUczelnia,
    WyborOsoby,
)


@pytest.mark.parametrize(
    "url,klass",
    [
        ("raport_slotow:index", WyborOsoby),
        ("raport_slotow:utworz-raport-slotow-uczelnia", UtworzRaportSlotowUczelnia),
        ("raport_slotow:index-ewaluacja", ParametryRaportSlotowEwaluacja),
    ],
)
def test_form_defaults_napis_przed_po(uczelnia, admin_client, url, klass):
    NAPIS_PRZED = b"napis przed"
    NAPIS_PO = b"napis po"

    uczelnia.pokazuj_raport_slotow_autor = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    uczelnia.pokazuj_raport_slotow_uczelnia = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    uczelnia.save()

    res = admin_client.get(reverse(url))
    for n in NAPIS_PO, NAPIS_PRZED:
        assert n not in res.content

    form_class = klass().get_form_class()
    res = FormRepresentation.objects.get_or_create_for_instance(form_class())
    res.html_before = NAPIS_PRZED
    res.html_after = NAPIS_PO
    res.save()

    res = admin_client.get(reverse(url))
    for n in NAPIS_PO, NAPIS_PRZED:
        assert n in res.content
