from django.urls import path

app_name = "import_list_ministerialnych"
from . import views

urlpatterns = [
    path("", views.PokazImporty.as_view(), name="index"),
    path("nowy/", views.UtworzImportDyscyplinZrodel.as_view(), name="utworz-import"),
    path(
        "<uuid:pk>/",
        views.ImportDyscyplinZrodelRouterView.as_view(),
        name="importlistministerialnych-router",
    ),
    path(
        "<uuid:pk>/details/",
        views.ImportDyscyplinZrodelDetailsView.as_view(),
        name="importlistministerialnych-details",
    ),
    path(
        "<uuid:pk>/regen/",
        views.RestartImportView.as_view(),
        name="importlistministerialnych-restart",
    ),
    path(
        "<uuid:pk>/results/",
        views.ImportDyscyplinZrodelResultsView.as_view(),
        name="importlistministerialnych-results",
    ),
]
