"""Widget wsparcia Freshdesk (Freshworks): token JWT dla zalogowanych.

Freshdesk uwierzytelnia użytkownika w widgecie tokenem JWT (HS256) podpisanym
wspólnym sekretem konta (Admin > Security > Widget settings). Payload:
``name``, ``email``, ``exp`` (Unix timestamp, maks. 2 godziny w przód).
https://support.freshdesk.com/support/solutions/articles/50000000978

Token wydajemy z endpointu zamiast wklejać go w HTML strony — ten sam adres
obsługuje pierwsze uwierzytelnienie i odnawianie (callback widgetu), a token
nie ląduje w cache'ach ani w źródle strony.
"""

import time

import jwt
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

#: Skrypt widgetu z CDN-u Freshworks (centrum danych EU).
WIDGET_SCRIPT_URL = "https://euc-widget.freshworks.com/widgets/{}.js"

#: Freshdesk odrzuca tokeny ważne dłużej niż 2 godziny.
TOKEN_TTL_SECONDS = 3600


def jwt_enabled():
    return bool(settings.FRESHDESK_WIDGET_JWT_SECRET)


def widget_user_name(user):
    return user.get_full_name() or user.get_username()


def widget_token(user, now=None):
    """Token JWT dla ``user`` albo ``None``, gdy JWT wyłączony / brak e-maila."""
    if not jwt_enabled() or not user.email:
        return None
    if now is None:
        now = time.time()
    payload = {
        "name": widget_user_name(user),
        "email": user.email,
        "exp": int(now) + TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, settings.FRESHDESK_WIDGET_JWT_SECRET, algorithm="HS256")


@never_cache
@require_GET
def widget_token_view(request):
    # Bez login_required: fetch() poszedłby za 302 i dostał HTML logowania.
    if not request.user.is_authenticated:
        return JsonResponse({"error": "not authenticated"}, status=403)
    token = widget_token(request.user)
    if token is None:
        return JsonResponse({"error": "widget JWT unavailable"}, status=404)
    return JsonResponse({"freshworks_widget_auth_token": token})
