from django.urls import path

from . import views

app_name = "ewaluacja_metryki"

urlpatterns = [
    path("", views.MetrykiListView.as_view(), name="lista"),
    path(
        "szczegoly/<slug:autor_slug>/<str:dyscyplina_kod>/",
        views.MetrykaDetailView.as_view(),
        name="szczegoly",
    ),
    path(
        "przypnij/<int:content_type_id>/<int:object_id>/<int:autor_id>/<int:dyscyplina_id>/",
        views.PrzypnijDyscyplineView.as_view(),
        name="przypnij",
    ),
    path(
        "odepnij/<int:content_type_id>/<int:object_id>/<int:autor_id>/<int:dyscyplina_id>/",
        views.OdepnijDyscyplineView.as_view(),
        name="odepnij",
    ),
    path("statystyki/", views.StatystykiView.as_view(), name="statystyki"),
    path(
        "jednostki/",
        views.MetrykiJednostekListaView.as_view(),
        name="metryki_jednostek",
    ),
    path(
        "jednostki/<int:pk>/",
        views.MetrykiJednostkiView.as_view(),
        name="metryki_jednostki",
    ),
    path(
        "wydzialy/",
        views.MetrykiWydzialowListaView.as_view(),
        name="metryki_wydzialow",
    ),
    path(
        "wydzialy/<int:pk>/",
        views.MetrykiWydzialuView.as_view(),
        name="metryki_wydzialu",
    ),
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
        "status-partial/",
        views.StatusGenerowaniaPartialView.as_view(),
        name="status_partial",
    ),
    path(
        "export-xlsx/<str:table_type>/",
        views.ExportStatystykiXLSX.as_view(),
        name="export_xlsx",
    ),
    path(
        "export-lista-xlsx/",
        views.ExportListaXLSX.as_view(),
        name="export_lista_xlsx",
    ),
]
