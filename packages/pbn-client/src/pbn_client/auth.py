"""OAuth authentication mixin for PBN API."""

from urllib.parse import parse_qs, urlparse

import requests

from pbn_client.conf import settings as pbn_settings
from pbn_client.exceptions import (
    AuthenticationConfigurationError,
    AuthenticationResponseError,
)


class OAuthMixin:
    """Mixin providing OAuth authentication functionality."""

    @classmethod
    def get_auth_url(klass, base_url, app_id, state=None):
        url = f"{base_url}/auth/pbn/api/registration/user/token/{app_id}"
        if state:
            from urllib.parse import quote

            url += f"?state={quote(state)}"
        return url

    @classmethod
    def get_user_token(
        klass,
        base_url,
        app_id,
        app_token,
        one_time_token,
        *,
        timeout=None,
    ):
        headers = {
            "X-App-Id": app_id,
            "X-App-Token": app_token,
        }
        body = {"oneTimeToken": one_time_token}
        url = f"{base_url}/auth/pbn/api/user/token"
        response = requests.post(
            url=url,
            json=body,
            headers=headers,
            timeout=(
                pbn_settings.PBN_CLIENT_HTTP_TIMEOUT
                if timeout is None
                else pbn_settings.parse_timeout(timeout)
            ),
        )
        try:
            response.json()
        except ValueError as e:
            if response.content.startswith(b"Mismatched X-APP-TOKEN: "):
                raise AuthenticationConfigurationError(
                    "Token aplikacji PBN nieprawidłowy. Poproś administratora "
                    "o skonfigurowanie prawidłowego tokena aplikacji PBN w "
                    "ustawieniach obiektu Uczelnia. "
                ) from e

            raise AuthenticationResponseError(response.content) from e

        return response.json().get("X-User-Token")

    def authorize(self, base_url, app_id, app_token):
        if self.access_token:
            return True

        self.access_token = pbn_settings.PBN_CLIENT_USER_TOKEN
        if self.access_token:
            return True

        auth_url = OAuthMixin.get_auth_url(base_url, app_id)

        print(
            f"""I have launched a web browser with {auth_url} ,\nplease log-in,
             then paste the redirected URL below. \n"""
        )
        import webbrowser

        webbrowser.open(auth_url)
        redirect_response = input("Paste the full redirect URL here:")
        one_time_token = parse_qs(urlparse(redirect_response).query).get("ott")[0]

        # NIE wypisujemy one_time_token ani access_token — to aktywne sekrety,
        # które zostawałyby w terminalu/CI/przechwyconych logach (uwaga #4).
        self.access_token = OAuthMixin.get_user_token(
            base_url,
            app_id,
            app_token,
            one_time_token,
            timeout=getattr(self, "timeout", None),
        )

        return True
