from django.urls import path

from import_list_if.views import (
    ImportListIfDetailsView,
    ImportListIfResultsView,
    ImportListIfRouterView,
    ListaImportowView,
    NowyImportView,
    RestartImportView,
)

app_name = "import_list_if"

urlpatterns = [
    path("", ListaImportowView.as_view(), name="index"),
    path("new/", NowyImportView.as_view(), name="new"),
    path(
        "<uuid:pk>/",
        ImportListIfRouterView.as_view(),
        name="importlistif-router",
    ),
    path(
        "<uuid:pk>/detale/",
        ImportListIfDetailsView.as_view(),
        name="importlistif-details",
    ),
    path(
        "<uuid:pk>/rezultaty/",
        ImportListIfResultsView.as_view(),
        name="importlistif-results",
    ),
    path(
        "<uuid:pk>/regen/",
        RestartImportView.as_view(),
        name="restart",
    ),
]
