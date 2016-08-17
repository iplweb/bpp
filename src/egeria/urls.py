# -*- encoding: utf-8 -*-
from django.conf.urls import patterns, url

from egeria.views import EgeriaImportCreateView, EgeriaImportListView, EgeriaImportDetailView, Diff_Tytul_CreateListView

urlpatterns = patterns(
    '',

    url(r'^new/$', EgeriaImportCreateView.as_view(), name="new"),
    url(r'^detail/(?P<pk>\d+)/$', EgeriaImportDetailView.as_view(), name="detail"),

    url(r'^detail/(?P<pk>\d+)/diff_tytul_create/$',
        Diff_Tytul_CreateListView.as_view(),
        name="diff_tytul_create"),

    url(r'^$', EgeriaImportListView.as_view(), name="main")

)