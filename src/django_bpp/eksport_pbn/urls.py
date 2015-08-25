from django.conf.urls import patterns, url, include
from django.contrib.auth.decorators import login_required

from django.conf import settings
from eksport_pbn.views import WyborWydzialu, Generuj, SerwujPlik
from integrator.views import FileUploadView, FileListView, AutorIntegrationFileDetail

urlpatterns = patterns(
    '',

    url(r'^(?P<wydzial>[0-9]+)/(?P<rok>[0-9]+)$',
        Generuj.as_view(), name='generuj'),

    url(r'^download/(?P<pk>[0-9]+)$',
        SerwujPlik.as_view(), name='pobierz'),

    url(r'^$',
        WyborWydzialu.as_view(), name='wybor_wydzialu'),

)
