from django.urls import path

from .views import (
    AktualizujPojedynczyView,
    AktualizujWszystkieDyscyplinyView,
    AktualizujWszystkieView,
    ExportDyscyplinyXlsxView,
    ExportXlsxView,
    PrzebudujRozbieznosciView,
    RozbieznosciDyscyplinListView,
    RozbieznosciZrodelListView,
    TaskStatusView,
)

app_name = "pbn_komparator_zrodel"

urlpatterns = [
    path("", RozbieznosciZrodelListView.as_view(), name="list"),
    path(
        "dyscypliny/", RozbieznosciDyscyplinListView.as_view(), name="dyscypliny_list"
    ),
    path(
        "dyscypliny/eksport-xlsx/",
        ExportDyscyplinyXlsxView.as_view(),
        name="dyscypliny_eksport_xlsx",
    ),
    path(
        "dyscypliny/aktualizuj-wszystkie/",
        AktualizujWszystkieDyscyplinyView.as_view(),
        name="aktualizuj_wszystkie_dyscypliny",
    ),
    path("przebuduj/", PrzebudujRozbieznosciView.as_view(), name="przebuduj"),
    path("aktualizuj/<int:pk>/", AktualizujPojedynczyView.as_view(), name="aktualizuj"),
    path(
        "aktualizuj-wszystkie/",
        AktualizujWszystkieView.as_view(),
        name="aktualizuj_wszystkie",
    ),
    path("task/<str:task_id>/", TaskStatusView.as_view(), name="task_status"),
    path("eksport-xlsx/", ExportXlsxView.as_view(), name="eksport_xlsx"),
]
