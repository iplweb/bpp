from django.urls import path, re_path

from . import views

app_name = "oswiadczenia"

urlpatterns = [
    # New views for 2022-2025 declarations
    path(
        "wydruk-2022-25/",
        views.WydrukOswiadczen2022View.as_view(),
        name="wydruk-2022-25",
    ),
    path(
        "wydruk-2022-25/export/",
        views.WydrukOswiadczenExportView.as_view(),
        name="wydruk-2022-25-export",
    ),
    # Background task views
    path(
        "wydruk-2022-25/start-export/",
        views.StartExportTaskView.as_view(),
        name="start-export",
    ),
    path(
        "wydruk-2022-25/task/<int:task_id>/",
        views.TaskStatusView.as_view(),
        name="task-status",
    ),
    path(
        "wydruk-2022-25/download/<int:task_id>/",
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
