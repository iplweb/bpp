from collections import namedtuple
from hashlib import md5

from asgiref.sync import async_to_sync

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import DEFAULT_TAGS


def get_channel_name_for_user(user: User):
    return md5(
        str(user.pk).encode("utf-8") + str(user.username).encode("utf-8")
    ).hexdigest()


def convert_obj_to_channel_name(original):
    ctype = ContentType.objects.get_for_model(original)
    pk = original.pk
    return f"{ctype.app_label}.{ctype.model}-{pk}"


def get_obj_from_channel_name(name):
    app_label_model, pk = name.split("-", 1)
    app_label, model = app_label_model.split(".", 1)
    ctype = ContentType.objects.get(app_label=app_label, model=model)
    obj = ctype.get_object_for_this_type(pk=int(pk))
    return obj


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
    request_or_channel_name,
    level,
    text,
    closeURL=None,
):
    channel_name = request_or_channel_name
    if hasattr(request_or_channel_name, "user") and hasattr(
        request_or_channel_name.user, "username"
    ):
        channel_name = get_channel_name_for_user(request_or_channel_name.user)

    return _send(
        channel_name,
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
