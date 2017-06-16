from django.conf.urls import url

from eksport_pbn.views import Generuj, SerwujPlik, ZamowEksportDoPBN

urlpatterns = [
    url(r'^(?P<wydzial>[0-9]+)/(?P<rok>[0-9]+)$',
        Generuj.as_view(), name='generuj'),

    url(r'^download/(?P<pk>[0-9]+)$',
        SerwujPlik.as_view(), name='pobierz'),

    # url(r'^$',
    #     WyborWydzialu.as_view(), name='wybor_wydzialu'),

    url(r'zamow/$', ZamowEksportDoPBN.as_view(), name='zamow')

]
