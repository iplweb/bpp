from django.urls import path

app_name = "import_polon"
from . import views

urlpatterns = [
    path("dane/", views.PokazImporty.as_view(), name="index"),
    path("dane/nowy/", views.UtworzImportPlikuPolon.as_view(), name="utworz-import"),
    path(
        "dane/<uuid:pk>/",
        views.ImportPolonRouterView.as_view(),
        name="importplikupolon-router",
    ),
    path(
        "dane/<uuid:pk>/details/",
        views.ImportPolonDetailsView.as_view(),
        name="importplikupolon-details",
    ),
    path(
        "dane/<uuid:pk>/regen/",
        views.RestartImportView.as_view(),
        name="importplikupolon-restart",
    ),
    path(
        "dane/<uuid:pk>/results/",
        views.ImportPolonResultsView.as_view(),
        name="importplikupolon-results",
    ),
    path("absencje/", views.PokazImporty.as_view(), name="index-absencji"),
    path(
        "absencje/nowy/",
        views.UtworzImportPlikuAbsencji.as_view(),
        name="utworz-import-absencji",
    ),
    path(
        "absencje/<uuid:pk>/",
        views.ImportAbsencjiRouterView.as_view(),
        name="importplikuabsencji-router",
    ),
    path(
        "absencje/<uuid:pk>/details/",
        views.ImportAbsencjiDetailsView.as_view(),
        name="importplikuabsencji-details",
    ),
    path(
        "absencje/<uuid:pk>/regen/",
        views.RestartImportAbsencjiView.as_view(),
        name="importplikuabsencji-restart",
    ),
    path(
        "absencje/<uuid:pk>/results/",
        views.ImportAbsencjiResultsView.as_view(),
        name="importplikuabsencji-results",
    ),
]
