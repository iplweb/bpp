from django.urls import path

from .views import (
    AutorzyLiczbaNListView,
    ExportAutorzyLiczbaNView,
    ExportUdzialyZaCaloscView,
    LiczbaNIndexView,
    ObliczLiczbeNView,
    SaveSankcjeView,
    UdzialyZaCaloscListView,
    UstawProcentDyscyplinyDowolnyView,
    UstawProcentDyscyplinyNSlotyView,
    UstawRodzajAutoraView,
    UstawWymiarEtatuView,
    WeryfikujBazeView,
)

app_name = "ewaluacja_liczba_n"

urlpatterns = [
    path("", LiczbaNIndexView.as_view(), name="index"),
    path("oblicz/", ObliczLiczbeNView.as_view(), name="oblicz"),
    path("save-sankcje/", SaveSankcjeView.as_view(), name="save-sankcje"),
    path("autorzy/", AutorzyLiczbaNListView.as_view(), name="autorzy-list"),
    path("autorzy/export/", ExportAutorzyLiczbaNView.as_view(), name="autorzy-export"),
    path(
        "udzialy-za-calosc/",
        UdzialyZaCaloscListView.as_view(),
        name="udzialy-za-calosc-list",
    ),
    path(
        "udzialy-za-calosc/export/",
        ExportUdzialyZaCaloscView.as_view(),
        name="udzialy-za-calosc-export",
    ),
    path("weryfikuj-baze/", WeryfikujBazeView.as_view(), name="weryfikuj-baze"),
    path(
        "weryfikuj-baze/ustaw-wymiar-etatu/",
        UstawWymiarEtatuView.as_view(),
        name="ustaw-wymiar-etatu",
    ),
    path(
        "weryfikuj-baze/ustaw-procent-n-sloty/",
        UstawProcentDyscyplinyNSlotyView.as_view(),
        name="ustaw-procent-n-sloty",
    ),
    path(
        "weryfikuj-baze/ustaw-procent-dowolny/",
        UstawProcentDyscyplinyDowolnyView.as_view(),
        name="ustaw-procent-dowolny",
    ),
    path(
        "weryfikuj-baze/ustaw-rodzaj-autora/",
        UstawRodzajAutoraView.as_view(),
        name="ustaw-rodzaj-autora",
    ),
]
