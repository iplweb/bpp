from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker
from oauth2_provider.models import get_access_token_model, get_application_model


@pytest.fixture
def access_token(db, django_user_model):
    def _make(scope="read", is_active=True):
        AccessToken = get_access_token_model()
        Application = get_application_model()
        user = baker.make(django_user_model, is_active=is_active)
        app = Application.objects.create(
            user=user,
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://claude.ai/callback",
            name="test-mcp",
        )
        tok = AccessToken.objects.create(
            user=user,
            application=app,
            token="tok-" + str(user.pk),
            expires=timezone.now() + timedelta(hours=1),
            scope=scope,
        )
        return user, tok

    return _make
