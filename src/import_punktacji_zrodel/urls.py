from django.urls import path

from import_punktacji_zrodel.views import (
    ListaImportowView,
    NiedopasowaneCsvView,
    NowyImportScopusView,
    NowyImportView,
    ResultsView,
    WybierzZrodloView,
    ZatwierdzImportView,
)

app_name = "import_punktacji_zrodel"

urlpatterns = [
    path("", ListaImportowView.as_view(), name="index"),
    path("new/", NowyImportView.as_view(), name="new"),
    path("new-scopus/", NowyImportScopusView.as_view(), name="new-scopus"),
    # Strona live (postęp + wynik) NIE jest już tutaj — obsługuje ją centralny
    # namespace ``liveops`` (reverse "liveops:live" przez get_absolute_url).
    # Router/detale/regen z long_running zostały usunięte.
    path(
        "<uuid:pk>/rezultaty/",
        ResultsView.as_view(),
        name="importpunktacjizrodel-results",
    ),
    path(
        "<uuid:pk>/zatwierdz/",
        ZatwierdzImportView.as_view(),
        name="zatwierdz",
    ),
    path(
        "<uuid:pk>/wiersz/<int:wiersz_pk>/wybierz/",
        WybierzZrodloView.as_view(),
        name="wybierz-zrodlo",
    ),
    path(
        "<uuid:pk>/niedopasowane.csv",
        NiedopasowaneCsvView.as_view(),
        name="niedopasowane-csv",
    ),
]
