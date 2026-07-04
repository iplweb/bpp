from django.urls import path

from import_punktacji_zrodel.views import (
    DetailsView,
    ListaImportowView,
    NowyImportView,
    RestartImportView,
    ResultsView,
    RouterView,
    ZatwierdzImportView,
)

app_name = "import_punktacji_zrodel"

urlpatterns = [
    path("", ListaImportowView.as_view(), name="index"),
    path("new/", NowyImportView.as_view(), name="new"),
    path(
        "<uuid:pk>/",
        RouterView.as_view(),
        name="importpunktacjizrodel-router",
    ),
    path(
        "<uuid:pk>/detale/",
        DetailsView.as_view(),
        name="importpunktacjizrodel-details",
    ),
    path(
        "<uuid:pk>/rezultaty/",
        ResultsView.as_view(),
        name="importpunktacjizrodel-results",
    ),
    path("<uuid:pk>/regen/", RestartImportView.as_view(), name="restart"),
    path(
        "<uuid:pk>/zatwierdz/",
        ZatwierdzImportView.as_view(),
        name="zatwierdz",
    ),
]
