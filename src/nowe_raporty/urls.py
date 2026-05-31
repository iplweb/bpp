from django.urls import re_path as url
from django.views.generic.base import TemplateView

from .views import RaportFormView, RaportGenerujView

urlpatterns = [
    url(
        r"^index/$",
        TemplateView.as_view(template_name="nowe_raporty/index.html"),
        name="index",
    ),
    # Generyczne trasy data-driven (matchują slug DefinicjaRaportu).
    url(
        r"^(?P<slug>[\w-]+)/(?P<pk>\d+)/(?P<od_roku>\d+)/(?P<do_roku>\d+)/$",
        RaportGenerujView.as_view(),
        name="raport_generuj",
    ),
    url(
        r"^(?P<slug>[\w-]+)/(?P<od_roku>\d+)/(?P<do_roku>\d+)/$",
        RaportGenerujView.as_view(),
        name="raport_generuj_uczelnia",
    ),
    url(r"^(?P<slug>[\w-]+)/$", RaportFormView.as_view(), name="raport_form"),
]
