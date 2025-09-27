from django.urls import path

from . import views

app_name = "przemapuj_prace_autora"

urlpatterns = [
    path("", views.wybierz_autora, name="wybierz_autora"),
    path("autor/<int:autor_id>/", views.przemapuj_prace, name="przemapuj_prace"),
]
