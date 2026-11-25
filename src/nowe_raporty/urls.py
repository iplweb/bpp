from django.urls import re_path as url
from django.views.generic.base import TemplateView

from .views import RaportFormView, RaportGenerujView

# ``[0-9]{1,10}``, nie ``\d+``: w Pythonie ``\d`` łapie też cyfry Unicode
# („²", „١٢"), a nieograniczona długość przepuszcza do ORM ciągi, na których
# ``int()`` rzuca ValueError (= 500). Taki adres ma dać 404. 10 cyfr = zakres
# kolumny ``integer`` w PostgreSQL.
LICZBA = "[0-9]{1,10}"

urlpatterns = [
    url(
        r"^index/$",
        TemplateView.as_view(template_name="nowe_raporty/index.html"),
        name="index",
    ),
    # Generyczne trasy data-driven (matchują slug DefinicjaRaportu).
    url(
        rf"^(?P<slug>[\w-]+)/(?P<pk>{LICZBA})/"
        rf"(?P<od_roku>{LICZBA})/(?P<do_roku>{LICZBA})/$",
        RaportGenerujView.as_view(),
        name="raport_generuj",
    ),
    url(
        rf"^(?P<slug>[\w-]+)/(?P<od_roku>{LICZBA})/(?P<do_roku>{LICZBA})/$",
        RaportGenerujView.as_view(),
        name="raport_generuj_uczelnia",
    ),
    url(r"^(?P<slug>[\w-]+)/$", RaportFormView.as_view(), name="raport_form"),
]
