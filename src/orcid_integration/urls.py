from django.urls import path

from . import views

app_name = "orcid_integration"

urlpatterns = [
    path("login/", views.orcid_login, name="login"),
    path("callback/", views.orcid_callback, name="callback"),
    path("polacz/", views.ORCIDLinkInitView.as_view(), name="polacz"),
]
