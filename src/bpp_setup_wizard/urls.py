from django.urls import path

from bpp_setup_wizard.views import PbnSetupView

app_name = "bpp_setup_wizard"

urlpatterns = [
    path("", PbnSetupView.as_view(), name="pbn"),
]
