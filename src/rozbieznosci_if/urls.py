from django.urls import path

from rozbieznosci_if.views import RozbieznosciView

app_name = "rozbieznosci_if"

urlpatterns = [
    path("index/", RozbieznosciView.as_view(), name="index"),
]
