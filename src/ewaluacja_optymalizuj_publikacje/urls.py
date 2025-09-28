from django.urls import path

from .views import HistoriaOptymalizacjiView, OptymalizujPublikacjeView

app_name = "ewaluacja_optymalizuj_publikacje"

urlpatterns = [
    path("", OptymalizujPublikacjeView.as_view(), name="index"),
    path("<slug:slug>/", OptymalizujPublikacjeView.as_view(), name="optymalizuj"),
    path("<slug:slug>/historia/", HistoriaOptymalizacjiView.as_view(), name="historia"),
]
