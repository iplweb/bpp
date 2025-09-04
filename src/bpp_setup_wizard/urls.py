from django.urls import path

from .views import SetupStatusView, SetupWizardView, UczelniaSetupView

app_name = "bpp_setup_wizard"

urlpatterns = [
    path("", SetupWizardView.as_view(), name="setup"),
    path("uczelnia/", UczelniaSetupView.as_view(), name="uczelnia_setup"),
    path("status/", SetupStatusView.as_view(), name="status"),
]
