from django.urls import path

from bpp_setup_wizard.views import DaneDemoPostepView, DaneDemoView, PbnSetupView

app_name = "bpp_setup_wizard"

# Włączane pod ``setup/step/`` PRZED adresami silnika — przykrywają jego
# generyczny widok kroku dla „pbn” i „dane_demo”.
urlpatterns = [
    path("pbn/", PbnSetupView.as_view(), name="pbn"),
    path("dane_demo/", DaneDemoView.as_view(), name="dane_demo"),
    path(
        "dane_demo/postep/",
        DaneDemoPostepView.as_view(),
        name="dane_demo_postep",
    ),
]
