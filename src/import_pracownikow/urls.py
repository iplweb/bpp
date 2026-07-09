from django.urls import path

from import_pracownikow import views

app_name = "import_pracownikow"

urlpatterns = [
    path("", views.ListaImportowView.as_view(), name="index"),
    path("new/", views.NowyImportView.as_view(), name="new"),
    path(
        "<uuid:pk>/mapowanie/",
        views.MapowanieView.as_view(),
        name="mapowanie",
    ),
    path(
        "<uuid:pk>/rezultaty/",
        views.ImportPracownikowResultsView.as_view(),
        name="importpracownikow-results",
    ),
    path(
        "<uuid:pk>/resetuj-podstawowe-miejsce-pracy/",
        views.ImportPracownikowResetujPodstawoweMiejscePracyView.as_view(),
        name="importpracownikow-resetuj-podstawowe-miejsce-pracy",
    ),
    path(
        "<uuid:pk>/zatwierdz/",
        views.ZatwierdzImportView.as_view(),
        name="zatwierdz",
    ),
    path(
        "<uuid:pk>/restart-analiza/",
        views.RestartAnalizaView.as_view(),
        name="restart-analiza",
    ),
    path(
        "<uuid:pk>/wiersz/<int:row_pk>/wybierz-kandydata/",
        views.WybierzKandydataView.as_view(),
        name="wybierz-kandydata",
    ),
]
