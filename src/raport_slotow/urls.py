# -*- encoding: utf-8 -*-

from django.urls import path, register_converter

from raport_slotow.converters import DecimalPathConverter
from raport_slotow.views import (
    ListaRaportSlotowUczelnia,
    ParametryRaportSlotowEwaluacja,
    RaportSlotow,
    RaportSlotowEwaluacja,
    RaportSlotowZerowy,
    RouterRaportuSlotowUczelnia,
    SzczegolyRaportSlotowUczelnia,
    SzczegolyRaportSlotowUczelniaListaRekordow,
    UtworzRaportSlotowUczelnia,
    WyborOsoby,
    WygenerujPonownieRaportSlotowUczelnia,
)

register_converter(DecimalPathConverter, "decimal")

app_name = "raport_slotow"

urlpatterns = [
    path("raport-slotow-autor/", WyborOsoby.as_view(), name="index"),
    path(
        r"raport-slotow-autor/wyswietl/",
        RaportSlotow.as_view(),
        name="raport",
    ),
    path(
        "raport-slotow-uczelnia/",
        ListaRaportSlotowUczelnia.as_view(),
        name="lista-raport-slotow-uczelnia",
    ),
    path(
        "raport-slotow-uczelnia/new/",
        UtworzRaportSlotowUczelnia.as_view(),
        name="utworz-raport-slotow-uczelnia",
    ),
    path(
        "raport-slotow-uczelnia/<uuid:pk>/",
        RouterRaportuSlotowUczelnia.as_view(),
        name="raportslotowuczelnia-router",
    ),
    path(
        "raport-slotow-uczelnia/<uuid:pk>/details/",
        SzczegolyRaportSlotowUczelnia.as_view(),
        name="raportslotowuczelnia-details",
    ),
    path(
        "raport-slotow-uczelnia/<uuid:pk>/regen/",
        WygenerujPonownieRaportSlotowUczelnia.as_view(),
        name="raportslotowuczelnia-regen",
    ),
    path(
        "raport-slotow-uczelnia/<uuid:pk>/results/",
        SzczegolyRaportSlotowUczelniaListaRekordow.as_view(),
        name="raportslotowuczelnia-results",
    ),
    path(
        "raport-slotow-ewaluacja/",
        ParametryRaportSlotowEwaluacja.as_view(),
        name="index-ewaluacja",
    ),
    path(
        r"raport-slotow-ewaluacja/raport/",
        RaportSlotowEwaluacja.as_view(),
        name="raport-ewaluacja",
    ),
    path(
        "raport-slotow-zerowy/",
        RaportSlotowZerowy.as_view(),
        name="raport-slotow-zerowy",
    ),
    path(
        "raport-slotow-zerowy/5/",
        RaportSlotowZerowy.as_view(min_pk=5),
        name="raport-slotow-zerowy-bez-5",
    ),
]
