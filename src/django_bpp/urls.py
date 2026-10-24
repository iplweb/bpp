import posixpath

from django.apps import apps
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.http import Http404
from django.urls import include, path, re_path
from django.urls import re_path as url
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView
from django.views.i18n import JavaScriptCatalog
from django.views.static import serve as static_serve
from loginas.views import user_login

from bpp.forms import MyAuthenticationForm
from bpp.views import favicon, robots_txt, root
from bpp.views.admin import (
    PatentTozView,
    WydawnictwoCiagleTozView,
    WydawnictwoZwarteTozView,
)
from bpp.views.global_nav import global_nav_redir
from bpp.views.mymultiseek import (
    BppMultiseekSaveForm,
    MultiseekToDjangoQLView,
    MyMultiseekExport,
    MyMultiseekResults,
    bpp_load_form,
    bpp_remove_by_hand,
    bpp_remove_from_removed_by_hand,
)
from bpp.views.sentry_tester import (
    test_403_view,
    test_500_view,
    test_exception_view,
    tylko_superuser,
)
from django_bpp.freshdesk import widget_token_view
from django_bpp.grappelli_lookup import (
    BppAutocompleteLookup,
    BppM2MLookup,
    BppRelatedLookup,
)
from django_bpp.health import health_check
from django_bpp.views import HTMXAwareLoginView

admin.autodiscover()


def protected_media_serve(request, path, document_root=None):
    """Serve media files but block direct access to protected/ paths.

    Files in protected/ directory should only be accessible through authenticated
    views that use django-sendfile.

    Ścieżkę normalizujemy PRZED sprawdzeniem guardu — inaczej traversal typu
    ``public/../protected/tajne.pdf`` przechodzi (surowe ``startswith`` widzi
    ``public/``), a ``static_serve`` zwija ``..`` dopiero wewnątrz i serwuje
    plik z ``protected/``. ``normpath`` na pustej ścieżce daje ``"."``, więc
    dodatkowe ``lstrip("/")`` i porównanie do ``"protected"`` są bezpieczne.
    """
    norm = posixpath.normpath(path).lstrip("/")
    if norm == "protected" or norm.startswith("protected/"):
        raise Http404("Use the download endpoint")
    return static_serve(request, path, document_root)


urlpatterns = (
    [
        path(  # Krok 3 kreatora (PBN) — BPP-owy widok kroku silnika „pbn",
            # przed include silnika, żeby przykryć generyczny widok (FD#499)
            "setup/step/pbn/",
            include("bpp_setup_wizard.urls", namespace="bpp_setup_wizard"),
        ),
        path(  # Setup wizard URLs (engine from django-first-run-wizard;
            "setup/",
            include("first_run_wizard.urls", namespace="first_run_wizard"),
        ),
        path("formdefaults/", include("formdefaults.urls")),
        path("", include("oauth_mcp.urls")),
        path("mcp/", include("mcp_server.urls", namespace="mcp_server")),
        url(r"^favicon\.ico$", cache_page(60 * 60)(favicon)),
        path("test_403/", tylko_superuser(test_403_view)),
        path("test_500/", tylko_superuser(test_500_view)),
        path("test_exception/", tylko_superuser(test_exception_view)),
        # tinymce.urls (compressor/linklist/filebrowser) celowo NIE jest
        # montowane: widget HTMLField ładuje TinyMCE ze static, a
        # TINYMCE_COMPRESSOR/TINYMCE_FILEBROWSER są wyłączone.
        url(
            # Auth (redaktor + POST/CSRF) egzekwuje WprowadzanieDanychRequiredMixin
            # w samym TozView — bez owijki login_required (dawniej GET-mutacja).
            r"^admin/bpp/wydawnictwo_ciagle/toz/(?P<pk>[\d]+)/$",
            WydawnictwoCiagleTozView.as_view(),
            name="admin_bpp_wydawnictwo_ciagle_toz",
        ),
        url(
            r"^admin/bpp/wydawnictwo_zwarte/toz/(?P<pk>[\d]+)/$",
            WydawnictwoZwarteTozView.as_view(),
            name="admin_bpp_wydawnictwo_zwarte_toz",
        ),
        url(
            r"^admin/bpp/patent/toz/(?P<pk>[\d]+)/$",
            PatentTozView.as_view(),
            name="admin_bpp_patent_toz",
        ),
        # url(r'^admin/', include(admin.site.urls)),
        path("admin/", admin.site.urls),
        path(
            "admin-dashboard/",
            include("admin_dashboard.urls", namespace="admin_dashboard"),
        ),
        url(
            r"^integrator2/",
            include(("integrator2.urls", "integrator2"), namespace="integrator2"),
        ),
        path(
            "ewaluacja_liczba_n/",
            include(
                "ewaluacja_liczba_n.urls",
            ),
        ),
        path(
            "ewaluacja_metryki/",
            include(
                "ewaluacja_metryki.urls",
            ),
        ),
        path(
            "kompletnosc_polon/",
            include(
                "kompletnosc_polon.urls",
            ),
        ),
        path(
            "ewaluacja_optymalizacja/",
            include(
                "ewaluacja_optymalizacja.urls",
            ),
        ),
        path(
            "ewaluacja_optymalizuj_publikacje/",
            include(
                "ewaluacja_optymalizuj_publikacje.urls",
            ),
        ),
        path(
            "ewaluacja_dwudyscyplinowcy/",
            include(
                "ewaluacja_dwudyscyplinowcy.urls",
            ),
        ),
        url(
            r"^api/v1/",
            include(("api_v1.urls", "api_v1"), namespace="api_v1"),
        ),
        url(
            r"^api/v1/api-auth/",
            include("rest_framework.urls", namespace="rest_framework"),
        ),
        # Endpoint OAI-PMH z profilem OpenAIRE CRIS 1.2. Osobny od
        # `bpp:oai`, który serwuje oai_dc dla Primo — tamten zostaje bez
        # zmian, bo harvestują go biblioteki.
        path(
            "cerif-oai/",
            include(("cerif_export.urls", "cerif_export"), namespace="cerif_export"),
        ),
        path(
            "zglos_publikacje/",
            include(
                ("zglos_publikacje.urls", "zglos_publikacje"),
            ),
        ),
        path(
            "orcid/",
            include("orcid_integration.urls"),
        ),
        path(
            "pbn_api/",
            include("pbn_api.urls"),
        ),
        path(
            "pbn_export_queue/",
            include("pbn_export_queue.urls"),
        ),
        path(
            "pbn_import/",
            include("pbn_import.urls"),
        ),
        url(
            r"^import_pracownikow/",
            include(
                ("import_pracownikow.urls", "import_pracownikow"),
                namespace="import_pracownikow",
            ),
        ),
        url(
            r"^import_polon/",
            include(
                ("import_polon.urls", "import_polon"),
            ),
        ),
        url(
            r"^import_list_ministerialnych/",
            include(
                ("import_list_ministerialnych.urls", "import_list_ministerialnych"),
            ),
        ),
        url(
            r"^import_list_if/",
            include(
                ("import_list_if.urls", "import_list_if"),
                namespace="import_list_if",
            ),
        ),
        url(
            r"^import_dyscyplin/",
            include(
                ("import_dyscyplin.urls", "import_dyscyplin"),
                namespace="import_dyscyplin",
            ),
        ),
        url(
            r"^snapshot_odpiec/",
            include(
                "snapshot_odpiec.urls",
                namespace="snapshot_odpiec",
            ),
        ),
        url(
            r"^stan_systemu/",
            include(
                "stan_systemu.urls",
                namespace="stan_systemu",
            ),
        ),
        url(
            r"^nowe_raporty/",
            include(("nowe_raporty.urls", "nowe_raporty"), namespace="nowe_raporty"),
        ),
        path("raport_slotow/", include("raport_slotow.urls")),
        url(r"^bpp/", include(("bpp.urls", "bpp"), namespace="bpp")),
        url(r"^oswiadczenia/", include("oswiadczenia.urls", namespace="oswiadczenia")),
        path(
            "komparator_pbn/",
            include("komparator_pbn.urls", namespace="komparator_pbn"),
        ),
        path(
            "pbn_downloader_app/",
            include("pbn_downloader_app.urls", namespace="pbn_downloader_app"),
        ),
        path(
            "pbn-wysylka-oswiadczen/",
            include("pbn_wysylka_oswiadczen.urls", namespace="pbn_wysylka_oswiadczen"),
        ),
        path("rozbieznosci_dyscyplin/", include("rozbieznosci_dyscyplin.urls")),
        path("rozbieznosci/", include("rozbieznosci.urls")),
        path("komparator-pbn-udzialy/", include("komparator_pbn_udzialy.urls")),
        path("komparator-publikacji-pbn/", include("komparator_publikacji_pbn.urls")),
        path("komparator-zrodel-pbn/", include("pbn_komparator_zrodel.urls")),
        path(
            "deduplikator_autorow/",
            include(
                ("deduplikator_autorow.urls", "deduplikator_autorow"),
                namespace="deduplikator_autorow",
            ),
        ),
        path(
            "importer_autorow_pbn/",
            include(
                ("importer_autorow_pbn.urls", "importer_autorow_pbn"),
                namespace="importer_autorow_pbn",
            ),
        ),
        path(
            "przemapuj_prace_autora/",
            include(
                ("przemapuj_prace_autora.urls", "przemapuj_prace_autora"),
                namespace="przemapuj_prace_autora",
            ),
        ),
        path(
            "przemapuj-zrodla-pbn/",
            include(
                ("przemapuj_zrodla_pbn.urls", "przemapuj_zrodla_pbn"),
                namespace="przemapuj_zrodla_pbn",
            ),
        ),
        path(
            "przemapuj-zrodlo/",
            include(
                ("przemapuj_zrodlo.urls", "przemapuj_zrodlo"),
                namespace="przemapuj_zrodlo",
            ),
        ),
        path(
            "deduplikator-publikacji/",
            include(
                ("deduplikator_publikacji.urls", "deduplikator_publikacji"),
                namespace="deduplikator_publikacji",
            ),
        ),
        path(
            "deduplikator-zrodel/",
            include(
                ("deduplikator_zrodel.urls", "deduplikator_zrodel"),
                namespace="deduplikator_zrodel",
            ),
        ),
        # Centralny router django-liveops (live/cancel/restart dla KAŻDEJ
        # podklasy LiveOperation). op.get_absolute_url() reversuje
        # "liveops:live". Montowany raz.
        path("live/", include("liveops.urls")),
        path(
            "import_punktacji_zrodel/",
            include("import_punktacji_zrodel.urls"),
        ),
        path(
            "importer_publikacji/",
            include(
                (
                    "importer_publikacji.urls",
                    "importer_publikacji",
                ),
                namespace="importer_publikacji",
            ),
        ),
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
        # Musi byc w przestrzeni /multiseek/ (root urlconf), PRZED include
        # ("multiseek.urls"), bo formularz POST-uje relatywnie ./do-djangoql/.
        # Nazwa jest top-level (nie bpp:...), bo trasa nie jest w bpp.urls.
        url(
            r"^multiseek/do-djangoql/$",
            MultiseekToDjangoQLView.as_view(),
            name="multiseek-do-djangoql",
        ),
        url(
            r"^multiseek/export/(?P<export_format>[\w-]+)/$",
            csrf_exempt(
                MyMultiseekExport.as_view(
                    registry=settings.MULTISEEK_REGISTRY,
                    template_name="multiseek/results.html",
                )
            ),
            name="multiseek-export",
        ),
        # Nadpisania upstreamowych load_form/save_form (kontrola właściciela
        # zapisanego formularza) — MUSZĄ być PRZED include("multiseek.urls").
        url(
            r"^multiseek/load_form/(?P<search_form_pk>\d+)$",
            bpp_load_form,
            name="bpp-multiseek-load-form",
        ),
        url(
            r"^multiseek/save_form/$",
            BppMultiseekSaveForm.as_view(registry=settings.MULTISEEK_REGISTRY),
            name="bpp-multiseek-save-form",
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
        # Z admin_tools montujemy tylko dashboard (zapis preferencji). Trasy
        # zakładek menu (admin_tools.menu.urls) nie są podpięte — BPP nie
        # używa zakładek (patrz django_bpp.menu.CustomMenu).
        url(r"^admin_tools/dashboard/", include("admin_tools.dashboard.urls")),
        # Lookupy grappelli z kontrolą uprawnień — muszą być PRZED
        # ``grappelli.urls``, żeby przesłonić oryginalne widoki.
        url(
            r"^grappelli/lookup/related/$",
            BppRelatedLookup.as_view(),
            name="grp_related_lookup",
        ),
        url(
            r"^grappelli/lookup/m2m/$",
            BppM2MLookup.as_view(),
            name="grp_m2m_lookup",
        ),
        url(
            r"^grappelli/lookup/autocomplete/$",
            BppAutocompleteLookup.as_view(),
            name="grp_autocomplete_lookup",
        ),
        url(r"^grappelli/", include("grappelli.urls")),
        path("health/", health_check, name="health"),
        path(
            "freshdesk/widget-token/",
            widget_token_view,
            name="freshdesk_widget_token",
        ),
        url(r"^$", root, name="root"),
        url(
            r"^messages/",
            include(
                ("messages_extends.urls", "messages_extends"),
                namespace="messages_extends",
            ),
        ),
        url(
            r"^.*/jsi18n/$",
            JavaScriptCatalog.as_view(
                packages=[
                    "multiseek",
                ]
            ),
        ),
        url(r"session_security/", include("session_security.urls")),
        url(r"^login/user/(?P<user_id>.+)/$", user_login, name="loginas-user-login"),
        url(
            r"^robots\.txt$",
            cache_page(60 * 60 * 24)(robots_txt),
            name="robots_txt",
        ),
        # url(r'^sitemap\.xml$', cache_page(7*24*3600)(sitemaps_views.index), {
        #     'sitemaps': django_bpp_sitemaps,
        #     'sitemap_url_name': 'sitemaps'
        # }, name='sitemap'),
        # url(r'^sitemap-(?P<section>.+)\.xml$',
        #     cache_page(7*24*3600)(sitemaps_views.sitemap), {'sitemaps': django_bpp_sitemaps},
        #     name='sitemaps'),
        # url(r'^sitemap\.xml', include('static_sitemaps.urls')),
        *(
            [path("", include("static_sitemaps.urls"))]
            if getattr(settings, "ENABLE_SITEMAPS", True)
            else []
        ),
        url(r"", include("webmaster_verification.urls")),
        url(
            r"^global-nav-redir/(?P<param>.+)/$",
            global_nav_redir,
            name="global-nav-redir",
        ),
    ]
    + [
        re_path(
            r"^media/(?P<path>.*)$",
            protected_media_serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
)


if "microsoft_auth" in getattr(settings, "INSTALLED_APPS", []):
    urlpatterns += [
        path("microsoft/", include("microsoft_auth.urls", namespace="microsoft")),
    ]


# Logowanie OpenID Connect — addytywne, montowane tylko gdy apka aktywna.
# Trasy mozilla-django-oidc: oidc/authenticate/ (start), oidc/callback/ (powrót).
# Redirect URI do zarejestrowania w Keycloaku: https://<host>/oidc/callback/
if settings.OIDC_LOGIN_ENABLED:
    urlpatterns += [
        path("oidc/", include("mozilla_django_oidc.urls")),
        path(
            "oidc/",
            include(("oidc_integration.urls", "oidc_integration")),
        ),
    ]


if settings.DJANGO_BPP_ENABLE_PROMETHEUS:
    urlpatterns += [
        path("", include("django_prometheus.urls")),
    ]


if settings.DEBUG and settings.DEBUG_TOOLBAR:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()


if settings.OIDC_LOGIN_ENABLED:
    #
    # Logowanie instytucjonalne przez OIDC (Keycloak). settings.OIDC_LOGIN_ENABLED
    # jest prawdą tylko gdy OIDC jest skonfigurowane (app instalowany zawsze, ale
    # routing/backend gateowane po wykryciu configu). OIDC to jeden realm na
    # proces, więc
    # logowanie jest wybierane PER-UCZELNIA: InstitutionalLoginView odbija na
    # Keycloaka tylko dla domeny uczelni o skrócie == OIDC_LOGIN_SKROT, dla
    # pozostałych domen używa Microsoftu (jeśli włączony, globalnie) albo
    # formularza BPP. Może współistnieć z microsoft_auth w jednym procesie.
    # Formularz BPP osobno pod local_login_form. Logout świadomy OIDC.
    #
    from django_bpp.views import InstitutionalLoginView
    from oidc_integration.views import BppOIDCAwareLogoutView

    urlpatterns += [
        url(
            r"^accounts/login/local/$",
            HTMXAwareLoginView.as_view(authentication_form=MyAuthenticationForm),
            name="local_login_form",
        ),
        url(
            r"^accounts/login/$",
            InstitutionalLoginView.as_view(),
            name="login_form",
        ),
        url(
            r"^logout/$",
            login_required(BppOIDCAwareLogoutView.as_view()),
            name="logout",
        ),
    ]
elif apps.is_installed("microsoft_auth"):
    #
    # Logowanie instytucjonalne przez Microsoft (globalne, jak dotąd): domyślne
    # logowanie odbija na Microsoft, formularz BPP osobno pod local_login_form.
    #
    from django_bpp.views import MicrosoftLogoutView

    urlpatterns += [
        # Local login route - always available even with Microsoft auth
        url(
            r"^accounts/login/local/$",
            HTMXAwareLoginView.as_view(authentication_form=MyAuthenticationForm),
            name="local_login_form",
        ),
        # Default login redirects to Microsoft
        url(
            r"^accounts/login/$",
            RedirectView.as_view(
                pattern_name="microsoft_auth:to-auth-redirect",
                query_string=True,
            ),
            name="login_form",
        ),
        url(
            r"^logout/$",
            MicrosoftLogoutView.as_view(),
            name="logout",
        ),
    ]
else:
    #
    # Brak logowania instytucjonalnego — własne logowanie hasłem z front-endu.
    #
    urlpatterns += [
        url(
            r"^accounts/login/$",
            HTMXAwareLoginView.as_view(authentication_form=MyAuthenticationForm),
            name="login_form",
        ),
        url(r"^logout/$", login_required(LogoutView.as_view()), name="logout"),
    ]

if apps.is_installed("password_policies"):
    from password_policies.views import (
        PasswordChangeDoneView,
        PasswordResetCompleteView,
        PasswordResetConfirmView,
        PasswordResetDoneView,
    )

    from django_bpp.views import (
        RateLimitedPasswordResetFormView,
        SmartPasswordChangeView,
    )

    urlpatterns += [
        url(
            r"^password_change_done/$",
            PasswordChangeDoneView.as_view(),
            name="password_change_done",
        ),
        url(
            r"^password_change/$",
            SmartPasswordChangeView.as_view(),
            name="password_change",
        ),
        url(
            r"^password_reset/$",
            RateLimitedPasswordResetFormView.as_view(),
            name="password_reset",
        ),
        url(
            r"^password_reset_confirm/"
            r"([0-9A-Za-z_\-]+)/([0-9A-Za-z]{1,13})/([0-9A-Za-z-=_]{1,64})/$",
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
    ]

#
# Auto-login endpoint dla dev stack-u (run-site / django-dev-helpers).
# `autologin_urlpatterns()` zwraca pusta liste gdy DJANGO_DEV_HELPERS_ENABLED
# nie jest ustawione, wiec na produkcji URL nie istnieje. Token przekazywany
# jest przez run-site CLI w zmiennej DEV_HELPERS_AUTOLOGIN_TOKEN, weryfikowany
# w widoku przez hmac.compare_digest.
#
try:
    from django_dev_helpers.urls import autologin_urlpatterns

    urlpatterns += autologin_urlpatterns()
except ImportError:
    # django-dev-helpers nie jest dostepne w niektorych srodowiskach
    # (np. produkcyjny obraz nie ciagnie dev-deps). To oczekiwane — autologin
    # i tak ma sens tylko lokalnie.
    pass


handler404 = "bpp.views.handler404"
handler500 = "bpp.views.handler500"
handler403 = "bpp.views.handler403"
