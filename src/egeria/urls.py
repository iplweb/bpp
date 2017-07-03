# -*- encoding: utf-8 -*-
from django.conf.urls import url

from egeria.views import EgeriaImportCreateView, EgeriaImportListView, Diff_Tytul_CreateListView, \
    Diff_Tytul_DeleteListView, ResetImportStateView, Diff_Funkcja_Autora_CreateListView, \
    Diff_Funkcja_Autora_DeleteListView, Diff_Wydzial_DeleteListView, Diff_Wydzial_CreateListView, \
    Diff_Jednostka_CreateListView, Diff_Jednostka_UpdateListView, Diff_Jednostka_DeleteListView, \
    Diff_Autor_CreateListView, Diff_Autor_UpdateListView, Diff_Autor_DeleteListView, ResultsView

urlpatterns = (

    url(r'^new/$', EgeriaImportCreateView.as_view(), name="new"),

    url(r'^detail/(?P<pk>\d+)/reset_import_state/$', ResetImportStateView.as_view(), name="reset_import_state"),
    url(r'^detail/(?P<pk>\d+)/diff_tytul_create/$', Diff_Tytul_CreateListView.as_view(), name="diff_tytul_create"),
    url(r'^detail/(?P<pk>\d+)/diff_tytul_delete/$', Diff_Tytul_DeleteListView.as_view(), name="diff_tytul_delete"),

    url(r'^detail/(?P<pk>\d+)/diff_funkcja_create/$', Diff_Funkcja_Autora_CreateListView.as_view(),
        name="diff_funkcja_create"),
    url(r'^detail/(?P<pk>\d+)/diff_funkcja_delete/$', Diff_Funkcja_Autora_DeleteListView.as_view(),
        name="diff_funkcja_delete"),

    url(r'^detail/(?P<pk>\d+)/diff_wydzial_create/$', Diff_Wydzial_CreateListView.as_view(),
        name="diff_wydzial_create"),
    url(r'^detail/(?P<pk>\d+)/diff_wydzial_delete/$', Diff_Wydzial_DeleteListView.as_view(),
        name="diff_wydzial_delete"),

    url(r'^detail/(?P<pk>\d+)/diff_jednostka_create/$', Diff_Jednostka_CreateListView.as_view(),
        name="diff_jednostka_create"),
    url(r'^detail/(?P<pk>\d+)/diff_jednostka_update/$', Diff_Jednostka_UpdateListView.as_view(),
        name="diff_jednostka_update"),
    url(r'^detail/(?P<pk>\d+)/diff_jednostka_delete/$', Diff_Jednostka_DeleteListView.as_view(),
        name="diff_jednostka_delete"),

    url(r'^detail/(?P<pk>\d+)/diff_autor_create/$', Diff_Autor_CreateListView.as_view(), name="diff_autor_create"),
    url(r'^detail/(?P<pk>\d+)/diff_autor_update/$', Diff_Autor_UpdateListView.as_view(), name="diff_autor_update"),
    url(r'^detail/(?P<pk>\d+)/diff_autor_delete/$', Diff_Autor_DeleteListView.as_view(), name="diff_autor_delete"),

    url(r'^detail/(?P<pk>\d+)/results/$', ResultsView.as_view(), name="results"),

    url(r'^$', EgeriaImportListView.as_view(), name="main")

)
