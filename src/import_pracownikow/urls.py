from django.urls import path

from import_pracownikow.views import (
    ImportPracownikowDetailsView,
    ImportPracownikowResultsView,
    ImportPracownikowRouterView,
    ListaImportowView,
    NowyImportView,
    RestartImportView,
)

app_name = "import_pracownikow"

urlpatterns = [
    path("", ListaImportowView.as_view(), name="index"),
    path("new/", NowyImportView.as_view(), name="new"),
    path(
        "<uuid:pk>/",
        ImportPracownikowRouterView.as_view(),
        name="importpracownikow-router",
    ),
    path(
        "<uuid:pk>/details/",
        ImportPracownikowDetailsView.as_view(),
        name="importpracownikow-details",
    ),
    path(
        "<uuid:pk>/results/",
        ImportPracownikowResultsView.as_view(),
        name="importpracownikow-results",
    ),
    path(
        "<uuid:pk>/regen/",
        RestartImportView.as_view(),
        name="importpracownikow-restart",
    ),
]
