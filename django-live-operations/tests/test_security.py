"""
Tests for live_operations.security — subscription token issuance.

Security properties verified:
- Token for user A / op A authorises exactly liveop.<op_a.pk>.
- Token for op A does NOT authorise op B's channel.
- Token issued for user A is rejected when presented by user B.
- Expired token is rejected.

Verification is delegated to channels_broadcast.security.verify_subscription_token
(the same function called by NotificationsConsumer at connect time).
"""
import time

import pytest
from channels_broadcast.security import (
    issue_subscription_token,
    verify_subscription_token,
)
from django.contrib.auth import get_user_model

from live_operations.security import TOKEN_TTL_SECONDS, make_subscription_token
from tests.models import DemoOp

User = get_user_model()


@pytest.fixture
def user_a(db):
    return User.objects.create_user("sec_user_a", password="x")


@pytest.fixture
def user_b(db):
    return User.objects.create_user("sec_user_b", password="x")


@pytest.fixture
def op_a(user_a):
    return DemoOp.objects.create(owner=user_a)


@pytest.fixture
def op_b(user_a):
    return DemoOp.objects.create(owner=user_a)


# ---- happy path --------------------------------------------------------


def test_token_authorises_correct_channel(user_a, op_a):
    """Token for user_a/op_a grants liveop.<op_a.pk>."""
    token = make_subscription_token(user_a, op_a)
    channels = verify_subscription_token(token, user_a)
    assert f"liveop.{op_a.pk}" in channels


def test_token_contains_only_one_channel(user_a, op_a):
    """Token grants exactly one channel (the operation's own)."""
    token = make_subscription_token(user_a, op_a)
    channels = verify_subscription_token(token, user_a)
    assert len(channels) == 1


def test_subscription_token_property_matches_make_token(user_a, op_a):
    """LiveOperation.subscription_token uses the same mechanism."""
    prop_token = op_a.subscription_token
    fn_token = make_subscription_token(user_a, op_a)
    # Both tokens must be accepted by the verifier (they may differ in
    # timestamp; assert both are valid rather than equal).
    assert verify_subscription_token(prop_token, user_a) == [
        f"liveop.{op_a.pk}"
    ]
    assert verify_subscription_token(fn_token, user_a) == [
        f"liveop.{op_a.pk}"
    ]


# ---- cross-operation rejection ----------------------------------------


def test_token_does_not_authorise_different_operation(user_a, op_a, op_b):
    """Token for op_a does NOT authorise op_b's channel."""
    token = make_subscription_token(user_a, op_a)
    channels = verify_subscription_token(token, user_a)
    assert f"liveop.{op_b.pk}" not in channels


# ---- cross-user rejection ---------------------------------------------


def test_token_rejected_for_wrong_user(user_a, user_b, op_a):
    """Token issued for user_a is rejected when presented by user_b."""
    token = make_subscription_token(user_a, op_a)
    channels = verify_subscription_token(token, user_b)
    assert channels == []


def test_token_rejected_for_anonymous(user_a, op_a):
    """Token issued to an authenticated user is rejected for anonymous."""
    from django.contrib.auth.models import AnonymousUser

    token = make_subscription_token(user_a, op_a)
    channels = verify_subscription_token(token, AnonymousUser())
    assert channels == []


# ---- expiry ------------------------------------------------------------


def test_expired_token_is_rejected(user_a, op_a):
    """Token with ttl=1 s is rejected after 1.1 s."""
    channel = op_a.get_channel_name()
    token = issue_subscription_token(user_a, [channel], ttl=1)
    time.sleep(1.1)
    channels = verify_subscription_token(token, user_a)
    assert channels == []


def test_default_ttl_is_large(user_a, op_a):
    """Default TOKEN_TTL_SECONDS is at least 1 hour (3600 s)."""
    assert TOKEN_TTL_SECONDS >= 3600


def test_ttl_overridable_via_live_operations_setting(user_a, op_a, settings):
    """TOKEN_TTL_SECONDS can be overridden via LIVE_OPERATIONS dict."""
    settings.LIVE_OPERATIONS = {"TOKEN_TTL_SECONDS": 60}
    token = make_subscription_token(user_a, op_a)
    # Token must still be valid immediately after issuance.
    channels = verify_subscription_token(token, user_a)
    assert f"liveop.{op_a.pk}" in channels

    # And it should expire after 1.1 s (ttl=60 would be valid; use ttl=1 test
    # to verify the custom value propagates — here we just assert the token was
    # issued with our custom ttl by checking it round-trips correctly).
    settings.LIVE_OPERATIONS = {"TOKEN_TTL_SECONDS": 1}
    short_token = make_subscription_token(user_a, op_a)
    time.sleep(1.1)
    expired_channels = verify_subscription_token(short_token, user_a)
    assert expired_channels == []
