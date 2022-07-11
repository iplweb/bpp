from django.urls import path

from . import views

urlpatterns = [
    path(
        "nowe_zgloszenie/",
        views.Zgloszenie_PublikacjiWizard.as_view(),
        name="nowe_zgloszenie",
    ),
    path("sukces/", views.Sukces.as_view()),
]
