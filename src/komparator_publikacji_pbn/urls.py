from django.urls import path

from . import views

app_name = "komparator_publikacji_pbn"

urlpatterns = [
    path("", views.PublicationComparisonView.as_view(), name="comparison_list"),
]
