from collections import namedtuple
import json

from django.contrib.messages import DEFAULT_TAGS
import requests

from .conf import settings

def get_pub_path(username):
    path = getattr(settings, "NOTIFICATIONS_PUB_PATH")
    prefix = getattr(settings, "NOTIFICATIONS_PUB_PREFIX")
    return path % dict(username=username, prefix=prefix)


Message = namedtuple("Message", "text cssClass clickURL hideCloseOption closeURL closeText")
Message.__new__.__defaults__ = (      'info',  None,    False,          None,    '&times;')

def send_notification(request_or_username, level, text, get_pub_path=get_pub_path, verbose=False, closeURL=None):

    proto = getattr(settings, "NOTIFICATIONS_PROTOCOL")
    host = getattr(settings, "NOTIFICATIONS_HOST")
    port = getattr(settings, "NOTIFICATIONS_PORT")

    username = request_or_username
    if hasattr(username, 'user') and hasattr(username.user, 'username'):
        username = request_or_username.user.username

    path = get_pub_path(username)

    if port is not None:
        port = ":%s" % port

    url = "%s://%s%s%s" % (proto, host, port or "", path)

    data=json.dumps(Message(text=text, cssClass=DEFAULT_TAGS.get(level), closeURL=closeURL).__dict__)

    if verbose:
        print "Posting to %r data %r" % (url, data)
    requests.request("POST", url, data=data)
