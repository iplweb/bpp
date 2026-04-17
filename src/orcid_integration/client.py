from requests_oauthlib import OAuth2Session


class OrcidClient:
    """ORCID Public API OAuth 2.0 client."""

    SCOPE = ["/authenticate"]

    def __init__(self, client_id, client_secret, base_url, redirect_uri):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.redirect_uri = redirect_uri
        self.authorization_url = f"{base_url}/oauth/authorize"
        self.token_url = f"{base_url}/oauth/token"

    def get_authorization_url(self, state=None):
        """Return (url, state) for the OAuth authorization redirect."""
        session = OAuth2Session(
            self.client_id,
            redirect_uri=self.redirect_uri,
            scope=self.SCOPE,
        )
        url, state = session.authorization_url(self.authorization_url, state=state)
        return url, state

    def fetch_token(self, authorization_response_url):
        """Exchange the authorization code for a token.

        Returns a dict with at least ``orcid``, ``name``,
        and ``access_token`` keys (provided by ORCID's token
        endpoint).
        """
        session = OAuth2Session(
            self.client_id,
            redirect_uri=self.redirect_uri,
            scope=self.SCOPE,
        )
        token = session.fetch_token(
            self.token_url,
            authorization_response=authorization_response_url,
            client_secret=self.client_secret,
        )
        return token
