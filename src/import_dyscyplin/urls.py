from django.conf.urls import url

from import_dyscyplin.views import CreateImport_Dyscyplin, DetailImport_Dyscyplin, UruchomPrzetwarzanieImport_Dyscyplin, \
    ListImport_Dyscyplin, UsunImport_Dyscyplin

urlpatterns = [
    url(
        r'^$',
        ListImport_Dyscyplin.as_view(),
        name='index'
    ),

    url(
        r'^create/$',
        CreateImport_Dyscyplin.as_view(),
        name='create'
    ),

    url(
        r'^detail/(?P<pk>\d+)/$',
        DetailImport_Dyscyplin.as_view(),
        name='detail'
    ),
    
    url(
        r'^api/przetwarzaj/(?P<pk>\d+)/$',
        UruchomPrzetwarzanieImport_Dyscyplin.as_view(),
        name='przetwarzaj'
    ),

    url(
        r'^api/usun/(?P<pk>\d+)/$',
        UsunImport_Dyscyplin.as_view(),
        name='usun'
    ),

]
