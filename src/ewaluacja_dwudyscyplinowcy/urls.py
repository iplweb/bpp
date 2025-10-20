from django.urls import path

from . import views

app_name = "ewaluacja_dwudyscyplinowcy"

urlpatterns = [
    path("", views.index, name="index"),
]
