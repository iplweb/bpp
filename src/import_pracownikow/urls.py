from django.urls import path

from import_pracownikow.views import (
    DetaleImportView,
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
        DetaleImportView.as_view(),
        name="detale",
    ),
    path(
        "<uuid:pk>/regen/",
        RestartImportView.as_view(),
        name="restart",
    ),
]
