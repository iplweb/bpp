# -*- encoding: utf-8 -*-

import json
from collections import namedtuple

import requests
from django.contrib.messages import DEFAULT_TAGS
from django.http.response import HttpResponseRedirect

from .conf import settings


def get_pub_path(username):
    path = getattr(settings, "NOTIFICATIONS_PUB_PATH")
    prefix = getattr(settings, "NOTIFICATIONS_PUB_PREFIX")
    return path % dict(username=username, prefix=prefix)


Message = namedtuple("Message", "text cssClass clickURL hideCloseOption closeURL closeText")
Message.__new__.__defaults__ = (      'info',  None,    False,          None,    '&times;')

def send_notification(request_or_username, level, text, get_pub_path=get_pub_path, verbose=False, closeURL=None, ignore_proxy_settings=False):

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

    data = json.dumps(
        Message(text=text,
                cssClass=DEFAULT_TAGS.get(level),
                closeURL=closeURL
                )._asdict())

    if verbose:
        print("Posting to %r data %r" % (url, data))

    session = requests.Session()
    if ignore_proxy_settings:
        session.trust_env = False

    res = session.post(url=url, data=data)
    if verbose:
        print("Result: ", res)
        print(res.content)


def send_redirect(username, redirect_url,  messageCookieId, ignore_proxy_settings=False):
    """

    :param request_or_username: request lub nazwa użytkownika, który ma zostać poinformowany
    :param redirect_url: URL do którego strona ma przejść
    :param messageCookieId: unikalny identyfikator sesji użytkownika, do którego należy wysłać kmounikat
    :param ignore_proxy_settings: parametr dla biblioteki requests, ignoruj ustawienia proxy
    :return:
    """

    proto = getattr(settings, "NOTIFICATIONS_PROTOCOL")
    host = getattr(settings, "NOTIFICATIONS_HOST")
    port = getattr(settings, "NOTIFICATIONS_PORT")

    path = get_pub_path(username)

    if port is not None:
        port = ":%s" % port

    url = "%s://%s%s%s" % (proto, host, port or "", path)

    data=json.dumps(dict(url=redirect_url, cookieId=messageCookieId))

    session = requests.Session()
    if ignore_proxy_settings:
        session.trust_env = False

    return session.post(url=url, data=data)

