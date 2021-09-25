from django.urls import path

from . import views

app_name = "rozbieznosci_dyscyplin"

urlpatterns = [
    path(
        "api/redirect-to-admin/<int:content_type_id>/<int:object_id>/",
        views.RedirectToAdmin.as_view(),
        name="redirect-to-admin",
    )
]
