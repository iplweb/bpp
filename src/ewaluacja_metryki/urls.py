from django.urls import path, register_converter

from . import views


class LiczbaCalkowitaZeZnakiem:
    """Jak ``<int:…>``, ale przyjmuje też liczby ujemne — część baz ma
    jednostki z ujemnym pk (np. ``-1``), a ``<int:…>`` ich nie dopasuje
    i ``{% url %}`` w liście jednostek kończy się ``NoReverseMatch``."""

    regex = "-?[0-9]+"

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return str(value)


register_converter(LiczbaCalkowitaZeZnakiem, "signed_int")

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
        "jednostki/<signed_int:jednostka_pk>/",
        views.MetrykiJednostkiView.as_view(),
        name="metryki_jednostki",
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
