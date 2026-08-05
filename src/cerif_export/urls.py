from django.urls import path

from cerif_export.views import OAICerifView

app_name = "cerif_export"

urlpatterns = [
    path("", OAICerifView.as_view(), name="oai"),
]
