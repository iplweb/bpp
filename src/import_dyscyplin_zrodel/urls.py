from django.urls import path

from import_dyscyplin_zrodel.views import (
    ImportDyscyplinZrodelDetailsView,
    ImportDyscyplinZrodelResultsView,
    ImportDyscyplinZrodelRouterView,
    ListaImportowView,
    NowyImportView,
    RestartImportView,
)

app_name = "import_dyscyplin_zrodel"

urlpatterns = [
    path("", ListaImportowView.as_view(), name="index"),
    path("new/", NowyImportView.as_view(), name="new"),
    path(
        "<uuid:pk>/",
        ImportDyscyplinZrodelRouterView.as_view(),
        name="ImportDyscyplinZrodel-router",
    ),
    path(
        "<uuid:pk>/detale/",
        ImportDyscyplinZrodelDetailsView.as_view(),
        name="ImportDyscyplinZrodel-details",
    ),
    path(
        "<uuid:pk>/rezultaty/",
        ImportDyscyplinZrodelResultsView.as_view(),
        name="ImportDyscyplinZrodel-results",
    ),
    path(
        "<uuid:pk>/regen/",
        RestartImportView.as_view(),
        name="restart",
    ),
]
