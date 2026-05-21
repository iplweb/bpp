from django.urls import path

from . import views
from .autocomplete import (
    PublicWydawcaAutocomplete,
    PublicWydawnictwoNadrzedneAutocomplete,
)

urlpatterns = [
    path(
        "nowe_zgloszenie/",
        views.Zgloszenie_PublikacjiWizard.as_view(),
        name="nowe_zgloszenie",
    ),
    path(
        "edycja_zgloszenia/<uuid:kod_do_edycji>/",
        views.Zgloszenie_PublikacjiWizard.as_view(),
        name="edycja_zgloszenia",
    ),
    path("sukces/", views.Sukces.as_view()),
    # Autocomplete
    path(
        "public-wydawca-autocomplete/",
        PublicWydawcaAutocomplete.as_view(),
        name="public-wydawca-autocomplete",
    ),
    path(
        "public-wydawnictwo-nadrzedne-autocomplete/",
        PublicWydawnictwoNadrzedneAutocomplete.as_view(),
        name="public-wydawnictwo-nadrzedne-autocomplete",
    ),
]
