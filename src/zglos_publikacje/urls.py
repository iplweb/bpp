from django.urls import path

from . import views

urlpatterns = [
    path("nowe_zgloszenie/", views.DodajZgloszenie_Publikacji.as_view()),
    path("sukces/", views.Sukces.as_view()),
]
