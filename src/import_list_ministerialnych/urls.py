from django.urls import path

app_name = "import_list_ministerialnych"
from . import views

urlpatterns = [
    path("", views.PokazImporty.as_view(), name="index"),
    path("nowy/", views.UtworzImportDyscyplinZrodel.as_view(), name="utworz-import"),
    # Strona live (postęp + wynik) NIE jest już tutaj — obsługuje ją centralny
    # namespace ``liveops`` (reverse "liveops:live"). Router/details/restart
    # z long_running zostały usunięte.
    path(
        "<uuid:pk>/results/",
        views.ImportDyscyplinZrodelResultsView.as_view(),
        name="importlistministerialnych-results",
    ),
    path(
        "<uuid:pk>/results/<int:row_pk>/",
        views.WierszImportuListyMinisterialnejDetailView.as_view(),
        name="importrow-detail",
    ),
]
