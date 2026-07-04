from django.urls import path

from .views import CofnijPrzemapowaView, PrzemapujZrodloView, ZrodloInfoView

app_name = "przemapuj_zrodlo"

urlpatterns = [
    # Ścieżki dwuczłonowe muszą być PRZED `<slug:slug>/`, żeby konwerter slug
    # (jeden segment) ich nie przechwycił.
    path("info/<int:pk>/", ZrodloInfoView.as_view(), name="info"),
    path("cofnij/<int:pk>/", CofnijPrzemapowaView.as_view(), name="cofnij"),
    path("<slug:slug>/", PrzemapujZrodloView.as_view(), name="przemapuj"),
]
