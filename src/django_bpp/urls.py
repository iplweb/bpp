# -*- encoding: utf-8 -*-

from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.urls import path
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.i18n import JavaScriptCatalog
from loginas.views import user_login
from password_policies.views import (
    PasswordChangeDoneView,
    PasswordChangeFormView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetFormView,
)

from bpp.forms import MyAuthenticationForm
from bpp.views import favicon, root
from bpp.views.admin import (
    PatentTozView,
    WydawnictwoCiagleTozView,
    WydawnictwoZwarteTozView,
)
from bpp.views.global_nav import global_nav_redir
from bpp.views.mymultiseek import (
    MyMultiseekResults,
    bpp_remove_by_hand,
    bpp_remove_from_removed_by_hand,
)
from django_bpp.forms import BppPasswordChangeForm

from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView

admin.autodiscover()


urlpatterns = (
    [
        url(r"^favicon\.ico$", cache_page(60 * 60)(favicon)),
        url(
            r"^admin/bpp/wydawnictwo_ciagle/toz/(?P<pk>[\d]+)/$",
            login_required(WydawnictwoCiagleTozView.as_view()),
            name="admin_bpp_wydawnictwo_ciagle_toz",
        ),
        url(
            r"^admin/bpp/wydawnictwo_zwarte/toz/(?P<pk>[\d]+)/$",
            login_required(WydawnictwoZwarteTozView.as_view()),
            name="admin_bpp_wydawnictwo_ciagle_toz",
        ),
        url(
            r"^admin/bpp/patent/toz/(?P<pk>[\d]+)/$",
            login_required(PatentTozView.as_view()),
            name="admin_bpp_wydawnictwo_ciagle_toz",
        ),
        # url(r'^admin/', include(admin.site.urls)),
        path("admin/", admin.site.urls),
        url(
            r"^integrator2/",
            include(("integrator2.urls", "integrator2"), namespace="integrator2"),
        ),
        url(r"^api/v1/", include(("api_v1.urls", "api_v1"), namespace="api_v1"),),
        url(
            r"^eksport_pbn/",
            include(("eksport_pbn.urls", "eksport_pbn"), namespace="eksport_pbn"),
        ),
        url(
            r"^import_dyscyplin/",
            include(
                ("import_dyscyplin.urls", "import_dyscyplin"),
                namespace="import_dyscyplin",
            ),
        ),
        url(
            r"^nowe_raporty/",
            include(("nowe_raporty.urls", "nowe_raporty"), namespace="nowe_raporty"),
        ),
        path("raport_slotow/", include("raport_slotow.urls")),
        url(r"^bpp/", include(("bpp.urls", "bpp"), namespace="bpp")),
        path("rozbieznosci_dyscyplin/", include("rozbieznosci_dyscyplin.urls")),
        url(
            r"^multiseek/results/$",
            csrf_exempt(
                MyMultiseekResults.as_view(
                    registry=settings.MULTISEEK_REGISTRY,
                    template_name="multiseek/results.html",
                )
            ),
            name="multiseek:results",
        ),
        url(
            r"^multiseek/",
            include(("multiseek.urls", "multiseek"), namespace="multiseek"),
        ),
        url(
            r"^multiseek/live-results/$",
            csrf_exempt(
                MyMultiseekResults.as_view(
                    registry=settings.MULTISEEK_REGISTRY,
                    template_name="multiseek/live-results.html",
                )
            ),
            name="live-results",
        ),
        url(
            r"^multiseek/remove-from-results/(?P<pk>\w+)$",
            bpp_remove_by_hand,
            name="remove_from_results",
        ),
        url(
            r"^multiseek/remove-from-removed-results/(?P<pk>\w+)$",
            bpp_remove_from_removed_by_hand,
            name="remove_from_removed_results",
        ),
        url(r"^admin_tools/", include("admin_tools.urls")),
        url(r"^grappelli/", include("grappelli.urls")),
        url(r"^$", root, name="root"),
        url(
            r"^accounts/login/$",
            LoginView.as_view(authentication_form=MyAuthenticationForm),
            name="login_form",
        ),
        url(
            r"^password_change_done/$",
            PasswordChangeDoneView.as_view(),
            name="password_change_done",
        ),
        url(
            r"^password_change/$",
            PasswordChangeFormView.as_view(form_class=BppPasswordChangeForm),
            name="password_change",
        ),
        url(
            r"^password_reset/$", PasswordResetFormView.as_view(), name="password_reset"
        ),
        url(
            r"^password_reset_confirm/"
            r"([0-9A-Za-z_\-]+)/([0-9A-Za-z]{1,13})/([0-9A-Za-z-=_]{1,32})/$",
            PasswordResetConfirmView.as_view(),
            name="password_reset_confirm",
        ),
        url(
            r"^password_reset_done/$",
            PasswordResetDoneView.as_view(),
            name="password_reset_done",
        ),
        url(
            r"^password_reset_complete/$",
            PasswordResetCompleteView.as_view(),
            name="password_reset_complete",
        ),
        url(r"^logout/$", LogoutView.as_view(), name="logout"),
        url(
            r"^messages/",
            include(
                ("messages_extends.urls", "messages_extends"),
                namespace="messages_extends",
            ),
        ),
        url(r"^.*/jsi18n/$", JavaScriptCatalog.as_view(packages=["multiseek",])),
        url(r"session_security/", include("session_security.urls")),
        url(r"^login/user/(?P<user_id>.+)/$", user_login, name="loginas-user-login"),
        url(r"^robots\.txt", include("robots.urls")),
        # url(r'^sitemap\.xml$', cache_page(7*24*3600)(sitemaps_views.index), {
        #     'sitemaps': django_bpp_sitemaps,
        #     'sitemap_url_name': 'sitemaps'
        # }, name='sitemap'),
        # url(r'^sitemap-(?P<section>.+)\.xml$',
        #     cache_page(7*24*3600)(sitemaps_views.sitemap), {'sitemaps': django_bpp_sitemaps},
        #     name='sitemaps'),
        # url(r'^sitemap\.xml', include('static_sitemaps.urls')),
        path("", include("static_sitemaps.urls")),
        url(r"", include("webmaster_verification.urls")),
        url(
            r"^global-nav-redir/(?P<param>.+)/$",
            global_nav_redir,
            name="global-nav-redir",
        ),
    ]
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
)


if settings.DEBUG and settings.DEBUG_TOOLBAR:
    import debug_toolbar

    urlpatterns += [
        url(r"^__debug__/", include(debug_toolbar.urls)),
    ]

handler404 = "bpp.views.handler404"
handler500 = "bpp.views.handler500"
handler403 = "bpp.views.handler403"
