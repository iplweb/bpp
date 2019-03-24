from django.conf.urls import url

from import_dyscyplin.views import CreateImport_Dyscyplin, DetailImport_Dyscyplin, UruchomPrzetwarzanieImport_Dyscyplin, \
    ListImport_Dyscyplin, UsunImport_Dyscyplin, API_Do_IntegracjiView, API_Nie_Do_IntegracjiView, API_Zintegrowane, \
    UruchomIntegracjeImport_DyscyplinView, KolumnyImport_Dyscyplin, UruchomTworzenieKolumnImport_Dyscyplin

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
        r'^okresl-kolumny/(?P<pk>\d+)/$',
        KolumnyImport_Dyscyplin.as_view(),
        name='okresl_kolumny'
    ),

    url(
        r'^api/stworz-kolumny/(?P<pk>\d+)/$',
        UruchomTworzenieKolumnImport_Dyscyplin.as_view(),
        name='stworz_kolumny'
    ),

    url(
        r'^api/przetwarzaj/(?P<pk>\d+)/$',
        UruchomPrzetwarzanieImport_Dyscyplin.as_view(),
        name='przetwarzaj'
    ),

    url(
        r'^api/integruj/(?P<pk>\d+)/$',
        UruchomIntegracjeImport_DyscyplinView.as_view(),
        name='integruj'
    ),

    url(
        r'^api/usun/(?P<pk>\d+)/$',
        UsunImport_Dyscyplin.as_view(),
        name='usun'
    ),

    url(
        r'^api/do_integracji/(?P<pk>\d+)/$',
        API_Do_IntegracjiView.as_view(),
        name='api_do_integracji'
    ),

    url(
        r'^api/nie_do_integracji/(?P<pk>\d+)/$',
        API_Nie_Do_IntegracjiView.as_view(),
        name='api_nie_do_integracji'
    ),
    url(
        r'^api/zintegrowane/(?P<pk>\d+)/$',
        API_Zintegrowane.as_view(),
        name='api_zintegrowane'
    ),

]
