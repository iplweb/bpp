from django.urls import path

from .views import (
    ImporterAutorowPBNView,
    create_all_unmatched_scientists,
    ignore_scientist,
    link_all_scientists,
    link_scientist,
)

app_name = "importer_autorow_pbn"

urlpatterns = [
    path("", ImporterAutorowPBNView.as_view(), name="main"),
    path("ignore/<str:scientist_id>/", ignore_scientist, name="ignore_scientist"),
    path("link/<str:scientist_id>/", link_scientist, name="link_scientist"),
    path("link-all/", link_all_scientists, name="link_all_scientists"),
    path(
        "create-all-unmatched/",
        create_all_unmatched_scientists,
        name="create_all_unmatched",
    ),
]
