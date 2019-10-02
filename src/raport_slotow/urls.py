# -*- encoding: utf-8 -*-

from django.urls import path

from raport_slotow.views import WyborOsoby, RaportSlotow, WyborRoku, RaportSlotowUczelnia

app_name = 'raport_slotow'

urlpatterns = [

    path("raport-slotow-autor/", WyborOsoby.as_view(), name='index'),
    path(r'raport-slotow-autor/<slug:autor>/<int:od_roku>/<int:do_roku>/',
         RaportSlotow.as_view(),
         name='raport'),

    path("raport-slotow-uczelnia/", WyborRoku.as_view(), name='index-uczelnia'),
    path("raport-slotow-uczelnia/<int:od_roku>/<int:do_roku>/",
         RaportSlotowUczelnia.as_view(),
         name='raport-uczelnia'),

]
