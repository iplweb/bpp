"""Trasy własne integracji OIDC (poza trasami mozilla-django-oidc).

Montowane w ``django_bpp.urls`` przez
``include(("oidc_integration.urls", "oidc_integration"))`` pod bramką
``settings.OIDC_LOGIN_ENABLED`` — dzięki ``app_name`` działa
``reverse("oidc_integration:polacz")``.
"""

from django.urls import path

from oidc_integration.views import SSOLinkInitView

app_name = "oidc_integration"

urlpatterns = [
    path("polacz/", SSOLinkInitView.as_view(), name="polacz"),
]
