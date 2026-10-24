from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import SAFE_METHODS


class StrictOAuth2Authentication(OAuth2Authentication):
    """OAuth2 auth, która NIE degraduje po cichu do anonima.

    Standardowe ``OAuth2Authentication`` przy nieważnym bearerze zwraca
    ``None`` → DRF spada na Session/Basic → ``AnonymousUser`` → endpoint
    ``AnonReadOnly`` oddaje 200 publiczne. Chcemy twardego 401, gdy klient
    JAWNIE przysłał ``Authorization: Bearer`` (spec §5.4a / B-1). Dodatkowo
    odrzucamy nieaktywnych użytkowników (spec §5.7 / W-D) oraz tokeny bez
    wymaganego zakresu ``read`` (uwaga reviewera #6).
    """

    #: Minimalny zakres wymagany do korzystania z autoryzowanego API.
    #: Egzekwowany w jednym miejscu (globalny chokepoint bearera), więc gdy
    #: dojdzie kolejny scope (np. ``write``), token bez ``read`` nie zostanie
    #: po cichu potraktowany jak pełnoprawny — deklarowany scope przestaje być
    #: pozorną izolacją.
    required_scopes = ["read"]

    #: Zakres, bez którego token nie może wykonywać metod innych niż
    #: bezpieczne. Dziś serwer nie wydaje takiego zakresu, więc każdy token
    #: OAuth jest read-only — niezależnie od tego, czy przyszedł w nagłówku,
    #: czy w ciele żądania (middleware widzi tylko nagłówek).
    write_scopes = ["write"]

    def authenticate(self, request):
        result = super().authenticate(request)
        header = request.META.get("HTTP_AUTHORIZATION", "")
        bearer_obecny = header.lower().startswith("bearer ")
        # Token w query stringu jest odrzucany przez DOT
        # (COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT) — wtedy ``result`` to
        # None. Zamiast cicho degradować do anonima, dajemy jawne 401, tak samo
        # jak dla nieważnego bearera w nagłówku.
        token_w_query = "access_token" in request.query_params
        if result is None:
            if bearer_obecny or token_w_query:
                raise AuthenticationFailed("Nieprawidłowy lub wygasły token.")
            return None
        user, token = result
        if not user or not user.is_active:
            raise AuthenticationFailed("Konto nieaktywne.")
        if not token or not token.allow_scopes(self.required_scopes):
            raise AuthenticationFailed("Token nie ma wymaganego zakresu 'read'.")
        if request.method not in SAFE_METHODS and not token.allow_scopes(
            self.write_scopes
        ):
            raise PermissionDenied("Zapis przez token OAuth jest wyłączony.")
        return user, token
