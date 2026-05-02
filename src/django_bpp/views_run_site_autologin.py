"""Auto-login endpoint dla `manage.py run_site`.

Endpoint jest montowany w ``django_bpp.urls`` TYLKO gdy ustawiona jest
zmienna środowiskowa ``DJANGO_BPP_RUN_SITE_AUTOLOGIN_TOKEN``. Bez niej
URL nie istnieje (wczesne odcięcie od produkcji). Widok dodatkowo
weryfikuje obecność tej zmiennej jako defense in depth.

Token przekazywany jest w query stringu (``?token=...``); porównanie
przez ``hmac.compare_digest``. Po dopasowaniu loguje użytkownika
``admin``, dodaje flash message i przekierowuje na stronę główną.
"""

from __future__ import annotations

import hmac
import os

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.http import Http404, HttpRequest, HttpResponseRedirect

AUTOLOGIN_ENV_VAR = "DJANGO_BPP_RUN_SITE_AUTOLOGIN_TOKEN"
AUTOLOGIN_URL_PATH = "__run_site_autologin__/"
_AUTOLOGIN_USERNAME = "admin"
_AUTOLOGIN_REDIRECT = "/"
_AUTOLOGIN_BACKEND = "django.contrib.auth.backends.ModelBackend"
_AUTOLOGIN_FLASH = "Zalogowano automatycznie (polecenie run_site) jako admin / admin"

# 1 rok — tyle samo co cookielaw default (max-age=31536000 w
# templates/cookielaw/rejectable.html). W trybie run_site nie ma sensu
# pokazywać banneru zgody, bo to lokalny dev-stack jednego dewelopera.
_COOKIELAW_MAX_AGE_SECONDS = 365 * 24 * 60 * 60


def run_site_autologin(request: HttpRequest):
    expected = os.environ.get(AUTOLOGIN_ENV_VAR)
    if not expected:
        raise Http404()

    provided = request.GET.get("token") or ""
    if not hmac.compare_digest(expected, provided):
        raise Http404()

    User = get_user_model()
    try:
        user = User.objects.get(username=_AUTOLOGIN_USERNAME)
    except User.DoesNotExist as exc:
        raise Http404() from exc

    login(request, user, backend=_AUTOLOGIN_BACKEND)
    messages.success(request, _AUTOLOGIN_FLASH)
    response = HttpResponseRedirect(_AUTOLOGIN_REDIRECT)
    response.set_cookie(
        "cookielaw_accepted",
        "1",
        max_age=_COOKIELAW_MAX_AGE_SECONDS,
        samesite="Lax",
        path="/",
    )
    return response
