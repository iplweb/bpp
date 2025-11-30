"""OAuth authentication mixin for PBN API."""

from urllib.parse import parse_qs, urlparse

import requests

from pbn_api.exceptions import (
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
    def get_user_token(klass, base_url, app_id, app_token, one_time_token):
        headers = {
            "X-App-Id": app_id,
            "X-App-Token": app_token,
        }
        body = {"oneTimeToken": one_time_token}
        url = f"{base_url}/auth/pbn/api/user/token"
        response = requests.post(url=url, json=body, headers=headers)
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
        from pbn_api.conf import settings

        if self.access_token:
            return True

        self.access_token = getattr(settings, "PBN_CLIENT_USER_TOKEN", None)
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
        print("ONE TIME TOKEN", one_time_token)

        self.access_token = OAuthMixin.get_user_token(
            base_url, app_id, app_token, one_time_token
        )

        print("ACCESS TOKEN", self.access_token)
        return True
