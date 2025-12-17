from django.urls import path

from . import views

app_name = "pbn_downloader_app"

urlpatterns = [
    path("", views.PbnDownloaderMainView.as_view(), name="main"),
    path(
        "api/start-download/",
        views.StartPbnDownloadView.as_view(),
        name="start_download",
    ),
    path("api/task-status/", views.TaskStatusView.as_view(), name="task_status"),
    path("api/retry-task/", views.RetryTaskView.as_view(), name="retry_task"),
    path(
        "api/start-people-download/",
        views.StartPbnPeopleDownloadView.as_view(),
        name="start_people_download",
    ),
    path(
        "api/people-task-status/",
        views.PeopleTaskStatusView.as_view(),
        name="people_task_status",
    ),
    path(
        "api/retry-people-task/",
        views.RetryPeopleTaskView.as_view(),
        name="retry_people_task",
    ),
    path(
        "api/start-journals-download/",
        views.StartJournalsDownloadView.as_view(),
        name="start_journals_download",
    ),
    path(
        "api/journals-task-status/",
        views.JournalsTaskStatusView.as_view(),
        name="journals_task_status",
    ),
    path(
        "api/retry-journals-task/",
        views.RetryJournalsTaskView.as_view(),
        name="retry_journals_task",
    ),
    path(
        "api/cancel-task/",
        views.CancelTaskView.as_view(),
        name="cancel_task",
    ),
    path(
        "api/cancel-people-task/",
        views.CancelPeopleTaskView.as_view(),
        name="cancel_people_task",
    ),
    path(
        "api/cancel-journals-task/",
        views.CancelJournalsTaskView.as_view(),
        name="cancel_journals_task",
    ),
]
