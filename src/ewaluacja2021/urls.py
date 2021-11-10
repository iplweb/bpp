from django.urls import path

from ewaluacja2021 import views

app_name = "ewaluacja2021"

urlpatterns = [
    path("", views.ListaImportow.as_view(), name="lista-importow"),
    path("<int:pk>/", views.SzczegolyImportu.as_view(), name="szczegoly-importu"),
    path("new/", views.NowyImport.as_view(), name="nowy-imporrt"),
    path("3n/", views.ListaRaporto3N.as_view(), name="lista-raportow3n"),
    path(
        "3n/<int:pk>/", views.SzczegolyRaportu3N.as_view(), name="szczegoly-raportu3n"
    ),
    path(
        "3n/<int:pk>/plik/",
        views.PlikRaportu3N.as_view(),
        name="szczegoly-raportu-3n-plik",
    ),
    path(
        "3n/<int:pk>/wykres/",
        views.WykresRaportu3N.as_view(),
        name="szczegoly-raportu-3n-wykres",
    ),
    path("3n/new/", views.NowyRaport3N.as_view(), name="nowy-raport3n"),
]
