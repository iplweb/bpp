from django.urls import path

from rozbieznosci.views import RozbieznosciView

app_name = "rozbieznosci"

urlpatterns = [
    path("<slug:metryka>/", RozbieznosciView.as_view(), name="index"),
]
