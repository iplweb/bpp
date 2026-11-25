from django.urls import path

from . import views

app_name = "komparator_publikacji_pbn"

urlpatterns = [
    path("", views.PublicationComparisonView.as_view(), name="comparison_list"),
    path("przelicz/", views.PrzeliczView.as_view(), name="przelicz"),
    path(
        "status/<str:task_id>/",
        views.TaskStatusView.as_view(),
        name="task_status",
    ),
]
