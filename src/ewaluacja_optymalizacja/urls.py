from django.urls import path

from . import views

app_name = "ewaluacja_optymalizacja"

urlpatterns = [
    path("", views.index, name="index"),
]
