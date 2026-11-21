from django.urls import path, re_path
from django.views.generic import RedirectView

from . import views

app_name = "oswiadczenia"

urlpatterns = [
    # Wydruk oświadczeń — lata wg okresu ewaluacji wybranego na pasku okresu
    path("wydruk/", views.WydrukOswiadczenView.as_view(), name="wydruk"),
    path(
        "wydruk/export/",
        views.WydrukOswiadczenExportView.as_view(),
        name="wydruk-export",
    ),
    # Stary adres (zakładki użytkowników) — przekierowanie z query stringiem
    path(
        "wydruk-2022-25/",
        RedirectView.as_view(pattern_name="oswiadczenia:wydruk", query_string=True),
    ),
    # Background task views
    path(
        "wydruk/start-export/",
        views.StartExportTaskView.as_view(),
        name="start-export",
    ),
    path(
        "wydruk/task/<int:task_id>/",
        views.TaskStatusView.as_view(),
        name="task-status",
    ),
    path(
        "wydruk/download/<int:task_id>/",
        views.DownloadResultView.as_view(),
        name="download-result",
    ),
    # Existing views
    re_path(
        r"^pojedyncze/(?P<content_type_id>[\d]+)/(?P<object_id>[\d]+)/"
        r"(?P<autor_id>[\d]+)/(?P<dyscyplina_pracy_id>[\d]+)/$",
        views.OswiadczenieAutoraView.as_view(),
        name="jedno-oswiadczenie",
    ),
    re_path(
        r"^pojedyncze-alternatywna/(?P<content_type_id>[\d]+)/(?P<object_id>[\d]+)/"
        r"(?P<autor_id>[\d]+)/(?P<dyscyplina_pracy_id>[\d]+)/$",
        views.OswiadczenieAutoraAlternatywnaDyscyplinaView.as_view(),
        name="jedno-oswiadczenie-druga-dyscyplina",
    ),
    re_path(
        r"^wiele/(?P<content_type_id>[\d]+)/(?P<object_id>[\d]+)/$",
        views.OswiadczeniaPublikacji.as_view(),
        name="wiele-oswiadczen",
    ),
]
