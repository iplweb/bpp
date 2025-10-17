from django.urls import path

from . import views

app_name = "przemapuj_zrodla_pbn"

urlpatterns = [
    path("", views.lista_skasowanych_zrodel, name="lista_skasowanych_zrodel"),
    path("<int:zrodlo_id>/", views.przemapuj_zrodlo, name="przemapuj_zrodlo"),
    path("<int:zrodlo_id>/usun/", views.usun_zrodlo, name="usun_zrodlo"),
]
