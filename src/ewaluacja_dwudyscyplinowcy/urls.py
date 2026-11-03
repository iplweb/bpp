from django.urls import path

from bpp.permissions import wymagaj_wprowadzania_danych_dla_urlpatterns

from . import views

app_name = "ewaluacja_dwudyscyplinowcy"

urlpatterns = [
    path("", views.index, name="index"),
]

# Lista obejmuje WSZYSTKICH autorów z dwiema dyscyplinami i ich publikacje —
# te same uprawnienia co ewaluacja_optymalizacja (skąd prowadzi link): grupa
# „wprowadzanie danych" lub superuser, bramkowane na poziomie URLconf.
wymagaj_wprowadzania_danych_dla_urlpatterns(urlpatterns)
