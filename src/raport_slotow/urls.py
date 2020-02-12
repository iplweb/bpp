# -*- encoding: utf-8 -*-

from django.urls import path

from raport_slotow.views import (
    WyborOsoby,
    RaportSlotow,
    ParametryRaportSlotowUczelnia,
    RaportSlotowUczelnia,
    RaportSlotowZerowy,
)

app_name = "raport_slotow"

urlpatterns = [
    path("raport-slotow-autor/", WyborOsoby.as_view(), name="index"),
    path(
        r"raport-slotow-autor/<slug:autor>/<int:od_roku>/<int:do_roku>/",
        RaportSlotow.as_view(),
        name="raport",
    ),
    path(
        "raport-slotow-uczelnia/",
        ParametryRaportSlotowUczelnia.as_view(),
        name="index-uczelnia",
    ),
    path(
        "raport-slotow-uczelnia/raport/",
        RaportSlotowUczelnia.as_view(),
        name="raport-uczelnia",
    ),
    path(
        "raport-slotow-zerowy/",
        RaportSlotowZerowy.as_view(),
        name="raport-slotow-zerowy",
    ),
]
