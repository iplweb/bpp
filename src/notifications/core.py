# -*- encoding: utf-8 -*-

import json
from collections import namedtuple

import requests
from asgiref.sync import async_to_sync
from django.contrib.messages import DEFAULT_TAGS

Message = namedtuple(
    "Message", "text cssClass clickURL hideCloseOption closeURL closeText"
)
Message.__new__.__defaults__ = ("info", None, False, None, "&times;")

from channels.layers import get_channel_layer


def _send(channel_name, data):
    channel_layer = get_channel_layer()

    fun = channel_layer.group_send
    if channel_name.startswith("specific"):
        fun = channel_layer.send

    data["type"] = "chat_message"

    return async_to_sync(fun)(channel_name, data)


def send_notification(
    request_or_username, level, text, closeURL=None,
):
    username = request_or_username
    if hasattr(username, "user") and hasattr(username.user, "username"):
        username = request_or_username.user.username

    return _send(
        username,
        Message(
            text=text, cssClass=DEFAULT_TAGS.get(level), closeURL=closeURL
        )._asdict(),
    )


def send_redirect(specific_channel, redirect_url):
    """
    :param specific_channel: nazwa kanału django-channels
    :param redirect_url: URL do którego odesłać przeglądarkę użytkownika
    :return:
    """

    return _send(specific_channel, dict(url=redirect_url))
