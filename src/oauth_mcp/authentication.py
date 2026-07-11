from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework.exceptions import AuthenticationFailed


class StrictOAuth2Authentication(OAuth2Authentication):
    """OAuth2 auth, która NIE degraduje po cichu do anonima.

    Standardowe ``OAuth2Authentication`` przy nieważnym bearerze zwraca
    ``None`` → DRF spada na Session/Basic → ``AnonymousUser`` → endpoint
    ``AnonReadOnly`` oddaje 200 publiczne. Chcemy twardego 401, gdy klient
    JAWNIE przysłał ``Authorization: Bearer`` (spec §5.4a / B-1). Dodatkowo
    odrzucamy nieaktywnych użytkowników (spec §5.7 / W-D).
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        header = request.META.get("HTTP_AUTHORIZATION", "")
        bearer_obecny = header.lower().startswith("bearer ")
        if result is None:
            if bearer_obecny:
                raise AuthenticationFailed("Nieprawidłowy lub wygasły token.")
            return None
        user, token = result
        if not user or not user.is_active:
            raise AuthenticationFailed("Konto nieaktywne.")
        return user, token
