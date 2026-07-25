from django.urls import path

from . import views

app_name = "kompletnosc_polon"

urlpatterns = [
    path("", views.ListaKompletnosciView.as_view(), name="lista"),
    path(
        "szczegoly/<slug:autor_slug>/",
        views.SzczegolyKompletnosciView.as_view(),
        name="szczegoly",
    ),
]
