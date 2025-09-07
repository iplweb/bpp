from django.urls import path

from . import views

app_name = "ewaluacja_metryki"

urlpatterns = [
    path("", views.MetrykiListView.as_view(), name="lista"),
    path("szczegoly/<int:pk>/", views.MetrykaDetailView.as_view(), name="szczegoly"),
    path("statystyki/", views.StatystykiView.as_view(), name="statystyki"),
    path(
        "uruchom-generowanie/",
        views.UruchomGenerowanieView.as_view(),
        name="uruchom_generowanie",
    ),
    path(
        "status-generowania/",
        views.StatusGenerowaniaView.as_view(),
        name="status_generowania",
    ),
    path(
        "export-xlsx/<str:table_type>/",
        views.ExportStatystykiXLSX.as_view(),
        name="export_xlsx",
    ),
]
