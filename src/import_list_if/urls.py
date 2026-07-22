from django.urls import path

from import_list_if.views import (
    ImportListIfResultsView,
    ListaImportowView,
    NowyImportView,
)

app_name = "import_list_if"

urlpatterns = [
    path("", ListaImportowView.as_view(), name="index"),
    path("new/", NowyImportView.as_view(), name="new"),
    # Strona live (postęp + wynik) NIE jest tutaj — obsługuje ją centralny
    # namespace ``liveops`` (reverse "liveops:live" przez get_absolute_url).
    # Router/detale/regen z long_running zostały usunięte.
    path(
        "<uuid:pk>/rezultaty/",
        ImportListIfResultsView.as_view(),
        name="importlistif-results",
    ),
]
