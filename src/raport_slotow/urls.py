# -*- encoding: utf-8 -*-

from django.conf.urls import url
from django.urls import path
from django.views.generic.base import TemplateView

from nowe_raporty.views import GenerujRaportDlaJednostki, \
    GenerujRaportDlaWydzialu
from raport_slotow.views import WyborOsoby, RaportSlotow

app_name = 'raport_slotow'

urlpatterns = [

    path("index/", WyborOsoby.as_view(), name='index'),

    path(r'autor/<slug:autor>/<int:rok>/<slug:export>/',
        RaportSlotow.as_view(),
        name='raport'),

]
