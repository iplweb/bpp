from django.conf.urls import patterns, url, include
from django.contrib.auth.decorators import login_required

from django.conf import settings
from eksport_pbn.views import WyborWydzialu, Generuj
from integrator.views import FileUploadView, FileListView, AutorIntegrationFileDetail

urlpatterns = patterns(
    '',

    url(r'^(?P<wydzial>[0-9]+)/(?P<rok>[0-9]+)$',
        login_required(Generuj.as_view()), name='generuj'),

    url(r'^$',
        login_required(WyborWydzialu.as_view()), name='wybor_wydzialu'),

)
