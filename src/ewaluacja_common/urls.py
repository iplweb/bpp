from django.urls import path

from ewaluacja_common.views import wybierz_okres

app_name = "ewaluacja_common"

urlpatterns = [
    path("wybierz-okres/", wybierz_okres, name="wybierz_okres"),
]
