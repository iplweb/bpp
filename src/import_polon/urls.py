from django.urls import path

app_name = "import_polon"
from . import views

urlpatterns = [
    path("", views.PokazImporty.as_view(), name="index"),
    path("nowy/", views.UtworzImportPlikuPolon.as_view(), name="utworz-import"),
    path(
        "<uuid:pk>/",
        views.ImportPolonRouterView.as_view(),
        name="importplikupolon-router",
    ),
    path(
        "<uuid:pk>/details/",
        views.ImportPolonDetailsView.as_view(),
        name="importplikupolon-details",
    ),
    path(
        "<uuid:pk>/regen/",
        views.RestartImportView.as_view(),
        name="importplikupolon-restart",
    ),
    path(
        "<uuid:pk>/results/",
        views.ImportPolonResultsView.as_view(),
        name="importplikupolon-results",
    ),
]
