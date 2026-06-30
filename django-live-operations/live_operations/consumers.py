"""
LiveOperationConsumer — extends channels_broadcast NotificationsConsumer
with snapshot-on-connect for live operations.

On connect:
1. Base class verifies auth, subscribes to token-authorised channels,
   and accepts the WebSocket connection.
2. We check that at least one ``liveop.*`` channel was authorised. If
   not (bad/wrong-user token), we close the connection.
3. For each authorised ``liveop.*`` channel we look up the concrete
   LiveOperation subclass instance and call ``send_snapshot()`` so the
   client immediately sees current state.

receive() silently absorbs ``ack_message`` frames — our envelope
(``{"liveop_html": …}``) never carries a top-level ``id``, so the
channels_broadcast client never sends ACKs for our messages; any ACK
arriving is stray and harmless.
"""
from __future__ import annotations

import json
import logging

from channels_broadcast.consumers import NotificationsConsumer

logger = logging.getLogger(__name__)


class LiveOperationConsumer(NotificationsConsumer):
    """NotificationsConsumer + snapshot-on-connect for liveop.* channels."""

    def connect(self) -> None:
        super().connect()

        liveop_channels = [
            c for c in self.channels if c.startswith("liveop.")
        ]
        if not liveop_channels:
            # No authorised liveop channel — token invalid/mismatched user.
            self.close()
            return

        for channel in liveop_channels:
            pk_str = channel[len("liveop."):]
            operation = _find_operation(pk_str)
            if operation is None:
                logger.warning(
                    "LiveOperationConsumer: no operation found for channel %s",
                    channel,
                )
                continue
            try:
                operation.send_snapshot()
            except Exception:
                logger.exception(
                    "LiveOperationConsumer: send_snapshot failed for channel %s",
                    channel,
                )

    def receive(self, text_data: str) -> None:
        """Silently absorb ack_message frames; ignore everything else."""
        try:
            data = json.loads(text_data)
        except (ValueError, TypeError):
            return
        if data.get("type") == "ack_message":
            # Stray ACK — we never issue Notification objects, so there is
            # nothing to acknowledge. Absorb silently.
            return
        # No other client→server messages defined in this protocol.


def _find_operation(pk_str: str):
    """Look up any concrete LiveOperation subclass instance by pk.

    Iterates over all installed models that subclass LiveOperation and
    returns the first match. Returns None if not found.
    """
    from django.apps import apps

    from live_operations.models import LiveOperation

    for model in apps.get_models():
        if model is LiveOperation:
            continue
        if not issubclass(model, LiveOperation):
            continue
        try:
            return model.objects.get(pk=pk_str)
        except model.DoesNotExist:
            continue
        except Exception:
            logger.debug(
                "_find_operation: error querying %s for pk=%s",
                model,
                pk_str,
                exc_info=True,
            )
            continue
    return None
