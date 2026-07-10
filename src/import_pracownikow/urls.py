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
    path(
        "<uuid:pk>/wiersz/<int:row_pk>/edytuj/",
        views.EdytujWierszView.as_view(),
        name="edytuj-wiersz",
    ),
    path(
        "<uuid:pk>/odpiecie/<int:odp_pk>/przelacz/",
        views.PrzelaczOdpiecieView.as_view(),
        name="przelacz-odpiecie",
    ),
    path(
        "<uuid:pk>/wiersz/<int:row_pk>/utworz-nowego/",
        views.PrzelaczUtworzNowegoView.as_view(),
        name="utworz-nowego",
    ),
]
