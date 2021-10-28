from django.urls import path

from ewaluacja2021 import views

app_name = "ewaluacja2021"

urlpatterns = [
    path("", views.ListaImportow.as_view(), name="lista-importow"),
    path("<int:pk>/", views.SzczegolyImportu.as_view(), name="szczegoly-importu"),
    path("new/", views.NowyImport.as_view(), name="nowy-imporrt"),
]
