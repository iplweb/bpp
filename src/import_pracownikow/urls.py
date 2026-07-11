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
        "<uuid:pk>/przeglad/",
        views.PodgladImportuView.as_view(),
        name="przeglad",
    ),
    path(
        "<uuid:pk>/rezultaty/",
        views.ImportPracownikowResultsView.as_view(),
        name="importpracownikow-results",
    ),
    path(
        "<uuid:pk>/odpiecia/",
        views.OdpieciaView.as_view(),
        name="odpiecia",
    ),
    path(
        "<uuid:pk>/audyt/",
        views.LogZmianView.as_view(),
        name="audyt",
    ),
    path(
        "<uuid:pk>/jednostki/",
        views.WeryfikacjaJednostekView.as_view(),
        name="jednostki",
    ),
    path(
        "<uuid:pk>/tytuly/",
        views.WeryfikacjaTytulowView.as_view(),
        name="tytuly",
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
        "<uuid:pk>/wiersz/<int:row_pk>/dopasuj-autora/",
        views.DopasujAutoraView.as_view(),
        name="dopasuj-autora",
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
    path(
        "<uuid:pk>/wiersz/<int:row_pk>/przepnij-prace/",
        views.PrzepnijPraceView.as_view(),
        name="przepnij-prace",
    ),
    path(
        "<uuid:pk>/przepnij-prace/zaznacz-wszystkie/",
        views.ZaznaczWszystkiePrzepieciaView.as_view(),
        name="zaznacz-przepiecia",
    ),
]
