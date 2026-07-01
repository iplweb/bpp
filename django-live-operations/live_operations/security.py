"""
Subscription token for live_operations channels.

Uses channels_broadcast.security.issue_subscription_token so the token
format is identical to what channels_broadcast's consumer verifies.
Token binds a user to the channel ``liveop.<pk>`` (default TTL: 300 s).

Security model (§8):
- Token encodes {user_pk, [channel], ttl}, signed with Django's
  TimestampSigner (SECRET_KEY + salt).
- channels_broadcast verifies: signature, user match, and expiry on every
  WebSocket connect.
- A token for user A is rejected when presented by user B — user.pk is
  embedded in the payload and checked against scope["user"].pk at connect
  time.
- A token for op A does NOT authorise op B's channel — the channel list is
  also embedded and verified.
"""
from channels_broadcast.security import issue_subscription_token

# 24 h default; override via LIVE_OPERATIONS["TOKEN_TTL_SECONDS"]
TOKEN_TTL_SECONDS = 86400


def make_subscription_token(user, operation) -> str:
    """Return a signed token authorising *user* to subscribe to *operation*'s channel.

    The token is accepted by channels_broadcast's consumer via
    ``?subscription_token=<token>``. It encodes
    ``{user_pk, ["liveop.<pk>"], ttl}`` and is signed with Django's
    ``TimestampSigner`` (same salt as channels_broadcast).

    TTL defaults to 86400 s (24 h); override with
    ``LIVE_OPERATIONS = {"TOKEN_TTL_SECONDS": N}``.

    Verification is delegated entirely to
    ``channels_broadcast.security.verify_subscription_token`` which is
    called by ``NotificationsConsumer._token_channels_from_query`` on every
    WebSocket connect — no separate verify step needed here.
    """
    from live_operations.conf import get_setting

    ttl = get_setting("TOKEN_TTL_SECONDS", TOKEN_TTL_SECONDS)
    channel = operation.get_channel_name()
    return issue_subscription_token(user, [channel], ttl=ttl)
