from django.urls import path

from .views import CofnijPrzemapowaView, PrzemapujZrodloView

app_name = "przemapuj_zrodlo"

urlpatterns = [
    path("<slug:slug>/", PrzemapujZrodloView.as_view(), name="przemapuj"),
    path("cofnij/<int:pk>/", CofnijPrzemapowaView.as_view(), name="cofnij"),
]
