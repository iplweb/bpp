import json
import mock
import pytest
from notifications import Message, send_notification
from django.contrib import messages


def test_namedtuple_default_values():
    x = Message('foobar')
    assert x.cssClass == 'info'
    assert x.hideCloseOption == False
    assert x.closeURL == None
    assert x.closeText == '&times;'

@mock.patch('requests.request')
def test_send_notifications_string_param(requests_request):
    send_notification('booya', 'info', 'test')
    assert requests_request.call_count == 1

@mock.patch('requests.request')
def test_send_notifications_request_param(requests_request):

    userMock = mock.Mock()
    userMock.configure_mock(username='usernameX')

    requestMock = mock.Mock()
    requestMock.configure_mock(user=userMock)

    send_notification(requestMock, 'info', 'test')
    assert requests_request.call_count == 1
    assert requests_request.call_args[0][1].endswith('-usernameX')

@mock.patch('requests.request')
def test_message_json(requests_request):
    send_notification('booya', messages.INFO, 'test')
    args, kwargs = requests_request.call_args
    ret = json.loads(kwargs['data'])
    assert ret['text'] == 'test'
    assert ret['cssClass'] == 'info'

def test_send_message_command():
    raise NotImplementedError

def test_send_notification_command():
    raise NotImplementedError