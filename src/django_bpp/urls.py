# -*- encoding: utf-8 -*-

from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import login
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

import autocomplete_light
from loginas.views import user_login
from multiseek.views import remove_by_hand, remove_from_removed_by_hand
from password_policies.views import PasswordChangeDoneView, PasswordChangeFormView
from bpp.forms import MyAuthenticationForm
from bpp.views.admin import WydawnictwoCiagleTozView, WydawnictwoZwarteTozView, \
    PatentTozView
from bpp.views.mymultiseek import MyMultiseekResults
from django_bpp.sitemaps import JednostkaSitemap, django_bpp_sitemaps

autocomplete_light.shortcuts.autodiscover()

from django.contrib import admin
from django.contrib.sitemaps import views as sitemaps_views

admin.autodiscover()


js_info_dict = {
    'packages': (
        'django.conf',
        'multiseek',
        'monitio'
    ),
}

import multiseek, loginas, django
from bpp.views import favicon, autorform_dependant_js, \
    navigation_autocomplete, user_navigation_autocomplete, root, \
    javascript_catalog

urlpatterns = [

    url(r'^favicon\.ico$', favicon),

    url(r'^dynjs/autorform_dependant.js$', autorform_dependant_js),

    #url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    url(r'^admin/bpp/wydawnictwo_ciagle/toz/(?P<pk>[\d]+)/$', login_required(WydawnictwoCiagleTozView.as_view()), name="admin:bpp_wydawnictwo_ciagle_toz"),
    url(r'^admin/bpp/wydawnictwo_zwarte/toz/(?P<pk>[\d]+)/$', login_required(WydawnictwoZwarteTozView.as_view()), name="admin:bpp_wydawnictwo_ciagle_toz"),
    url(r'^admin/bpp/patent/toz/(?P<pk>[\d]+)/$', login_required(PatentTozView.as_view()), name="admin:bpp_wydawnictwo_ciagle_toz"),

    url(r'^admin/', include(admin.site.urls)),

    url(r'^integrator2/', include('integrator2.urls', namespace='integrator2')),
    url(r'^eksport_pbn/', include('eksport_pbn.urls', namespace='eksport_pbn')),

    # mpasternak 17.01.2017 TODO: włączyć później
    # url(r'^egeria/', include('egeria.urls', namespace='egeria')),

    url(r'^bpp/', include('bpp.urls', namespace='bpp')),

    url(r'^multiseek/results/$',
        csrf_exempt(MyMultiseekResults.as_view(
            registry=settings.MULTISEEK_REGISTRY,
            template_name="multiseek/results.html"
        )), name="multiseek:results"),

    url(r'^multiseek/', include('multiseek.urls', namespace='multiseek')),

    url(r'^multiseek/live-results/$',
        csrf_exempt(MyMultiseekResults.as_view(
            registry=settings.MULTISEEK_REGISTRY,
            template_name="multiseek/live-results.html"
        )), name="live-results"),


    url(r'^multiseek/remove-from-results/(?P<pk>\w+)$',
        remove_by_hand,
        name="remove_from_results"),

    url(r'^multiseek/remove-from-removed-results/(?P<pk>\w+)$',
        remove_from_removed_by_hand,
        name="remove_from_removed_results"),

    url(r'^admin_tools/', include('admin_tools.urls')),
    url(r'^grappelli/', include('grappelli.urls')),

    url(r'^autocomplete/', include('autocomplete_light.urls'),
        name="autocomplete"),

    url(r'^navigation_autocomplete/$', navigation_autocomplete,
        name='navigation_autocomplete'),
    url(r'^user_navigation_autocomplete/$',
        user_navigation_autocomplete,
        name='user_navigation_autocomplete'),

    url(r'^$', root, name="root"),

    url(r'^accounts/login/$', login,
        name="login_form", kwargs={'authentication_form':MyAuthenticationForm}),
    url(r'^password_change_done/$',
        PasswordChangeDoneView.as_view(),
        name="password_change_done"),
    url(r'^password_change/$',
        PasswordChangeFormView.as_view(),
        name="password_change"),

    url(r'^logout/$', django.contrib.auth.views.logout, name="logout"),

    url(r'^messages/', include('messages_extends.urls',
                             namespace='messages_extends')),

    url(r'^.*/jsi18n/$', javascript_catalog, js_info_dict),

    url(r'session_security/', include('session_security.urls')),

    url(r'egeria/', include('egeria.urls')),

    url(r"^login/user/(?P<user_id>.+)/$", user_login, name="loginas-user-login"),

    url(r'^robots\.txt$', include('robots.urls')),

    url(r'^sitemap\.xml$', cache_page(7*24*3600)(sitemaps_views.index), {
        'sitemaps': django_bpp_sitemaps,
        'sitemap_url_name': 'sitemaps'
    }, name='sitemap'),
    url(r'^sitemap-(?P<section>.+)\.xml$',
        cache_page(7*24*3600)(sitemaps_views.sitemap), {'sitemaps': django_bpp_sitemaps},
        name='sitemaps'),

    url(r'', include('webmaster_verification.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


from django.conf import settings
from django.conf.urls import include, url


if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]