import json
from unittest.mock import patch, MagicMock, Mock

import pytest
import requests
from requests.exceptions import SSLError, ConnectionError
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
from simplejson.errors import JSONDecodeError

from pbn_api.client import (
    RequestsTransport,
    OAuthMixin,
    PageableResource,
    PBNClientTransport,
    smart_content,
)
from pbn_api.exceptions import (
    AccessDeniedException,
    AuthenticationConfigurationError,
    AuthenticationResponseError,
    HttpException,
    PraceSerwisoweException,
)


# ==================== smart_content Tests ====================


def test_smart_content_with_string():
    """Test smart_content with string input - should return bytes as-is"""
    # smart_content tries to decode bytes; if already a string it will fail
    # but actual usage is with bytes only
    result = smart_content(b"test string")
    assert result == "test string"


def test_smart_content_with_utf8_bytes():
    """Test smart_content with UTF-8 encoded bytes"""
    result = smart_content("test string".encode("utf-8"))
    assert result == "test string"


def test_smart_content_with_unicode_bytes():
    """Test smart_content with Unicode characters"""
    text = "Testowy tekst z polskimi znakami: ąćęłńóśźż"
    result = smart_content(text.encode("utf-8"))
    assert result == text


def test_smart_content_with_invalid_utf8():
    """Test smart_content with invalid UTF-8 bytes returns original"""
    invalid_bytes = b"\x80\x81\x82"
    result = smart_content(invalid_bytes)
    assert result == invalid_bytes


# ==================== PBNClientTransport Tests ====================


def test_pbn_client_transport_initialization():
    """Test PBNClientTransport initialization"""
    transport = PBNClientTransport("app_id", "app_token", "https://example.com")

    assert transport.app_id == "app_id"
    assert transport.app_token == "app_token"
    assert transport.base_url == "https://example.com"
    assert transport.access_token is None


def test_pbn_client_transport_default_base_url():
    """Test PBNClientTransport uses default URL when None provided"""
    from pbn_api.const import DEFAULT_BASE_URL

    transport = PBNClientTransport("app_id", "app_token", None)

    assert transport.base_url == DEFAULT_BASE_URL


def test_pbn_client_transport_with_user_token():
    """Test PBNClientTransport with user token"""
    transport = PBNClientTransport(
        "app_id", "app_token", "https://example.com", "user_token_123"
    )

    assert transport.access_token == "user_token_123"


# ==================== OAuthMixin Tests ====================


def test_oauth_mixin_get_auth_url():
    """Test OAuthMixin.get_auth_url generates correct URL"""
    url = OAuthMixin.get_auth_url("https://pbn.example.com", "test_app")

    assert (
        "https://pbn.example.com/auth/pbn/api/registration/user/token/test_app" in url
    )


def test_oauth_mixin_get_auth_url_with_state():
    """Test OAuthMixin.get_auth_url includes state parameter"""
    url = OAuthMixin.get_auth_url(
        "https://pbn.example.com", "test_app", state="test_state"
    )

    assert "state=test_state" in url


def test_oauth_mixin_get_auth_url_state_url_encoded():
    """Test OAuthMixin.get_auth_url URL-encodes state parameter"""
    state = "state with spaces"
    url = OAuthMixin.get_auth_url("https://pbn.example.com", "test_app", state=state)

    assert "state=state%20with%20spaces" in url


@patch("requests.post")
def test_oauth_mixin_get_user_token_success(mock_post):
    """Test OAuthMixin.get_user_token successful token retrieval"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"X-User-Token": "user_token_123"}
    mock_post.return_value = mock_response

    token = OAuthMixin.get_user_token(
        "https://pbn.example.com", "app_id", "app_token", "ott_123"
    )

    assert token == "user_token_123"


@patch("requests.post")
def test_oauth_mixin_get_user_token_config_error(mock_post):
    """Test OAuthMixin.get_user_token raises error on bad token"""
    mock_response = MagicMock()
    mock_response.content = b"Mismatched X-APP-TOKEN: invalid"
    mock_response.json.side_effect = ValueError("No JSON")
    mock_post.return_value = mock_response

    with pytest.raises(AuthenticationConfigurationError):
        OAuthMixin.get_user_token(
            "https://pbn.example.com", "app_id", "bad_token", "ott_123"
        )


@patch("requests.post")
def test_oauth_mixin_get_user_token_response_error(mock_post):
    """Test OAuthMixin.get_user_token raises error on invalid response"""
    mock_response = MagicMock()
    mock_response.content = b"Some error message"
    mock_response.json.side_effect = ValueError("No JSON")
    mock_post.return_value = mock_response

    with pytest.raises(AuthenticationResponseError):
        OAuthMixin.get_user_token(
            "https://pbn.example.com", "app_id", "app_token", "ott_123"
        )


# ==================== PageableResource Tests ====================


def test_pageable_resource_initialization():
    """Test PageableResource initialization"""
    transport = MagicMock()
    res = {
        "content": [1, 2, 3],
        "number": 0,
        "totalElements": 10,
        "totalPages": 2,
    }

    resource = PageableResource(transport, res, "/api/test", {})

    assert resource.total_elements == 10
    assert resource.total_pages == 2
    assert resource.page_0 == [1, 2, 3]


def test_pageable_resource_count():
    """Test PageableResource.count()"""
    transport = MagicMock()
    res = {
        "content": [1, 2, 3],
        "number": 0,
        "totalElements": 15,
        "totalPages": 5,
    }

    resource = PageableResource(transport, res, "/api/test", {})

    assert resource.count() == 15


def test_pageable_resource_iteration():
    """Test PageableResource iteration"""
    transport = MagicMock()
    res = {
        "content": [1, 2, 3],
        "number": 0,
        "totalElements": 6,
        "totalPages": 2,
    }

    transport.get.return_value = {"content": [4, 5, 6]}

    resource = PageableResource(transport, res, "/api/test", {})

    items = list(resource)

    assert items == [1, 2, 3, 4, 5, 6]


def test_pageable_resource_missing_content_key():
    """Test PageableResource handles missing content key"""
    transport = MagicMock()
    res = {
        "number": 0,
        "totalElements": 0,
        "totalPages": 1,
    }

    resource = PageableResource(transport, res, "/api/test", {})

    assert resource.page_0 == []


# ==================== RequestsTransport Tests ====================


@patch("requests.get")
def test_requests_transport_get_success(mock_get):
    """Test RequestsTransport.get successful request"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"test": "data"}
    mock_get.return_value = mock_response

    transport = RequestsTransport("app_id", "app_token", "https://api.example.com")
    result = transport.get("/endpoint")

    assert result == {"test": "data"}


@patch("requests.get")
def test_requests_transport_get_includes_headers(mock_get):
    """Test RequestsTransport.get includes required headers"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_get.return_value = mock_response

    transport = RequestsTransport(
        "app_id", "app_token", "https://api.example.com", "user_token"
    )
    transport.get("/endpoint")

    call_kwargs = mock_get.call_args[1]
    headers = call_kwargs["headers"]

    assert headers["X-App-Id"] == "app_id"
    assert headers["X-App-Token"] == "app_token"
    assert headers["X-User-Token"] == "user_token"


@patch("requests.get")
def test_requests_transport_get_http_error(mock_get):
    """Test RequestsTransport.get raises HttpException on error status"""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.content = b"Internal Server Error"
    mock_get.return_value = mock_response

    transport = RequestsTransport("app_id", "app_token", "https://api.example.com")

    with pytest.raises(HttpException):
        transport.get("/endpoint")


@patch("requests.get")
def test_requests_transport_get_ssl_error_retry(mock_get):
    """Test RequestsTransport.get retries on SSL error"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"test": "data"}

    # First call fails with SSL error, second succeeds
    mock_get.side_effect = [SSLError("SSL Error"), mock_response]

    transport = RequestsTransport("app_id", "app_token", "https://api.example.com")

    with patch("time.sleep"):
        result = transport.get("/endpoint")

    assert result == {"test": "data"}


@patch("requests.get")
def test_requests_transport_get_connection_error_retry(mock_get):
    """Test RequestsTransport.get retries on connection error"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"test": "data"}

    # First call fails with connection error, second succeeds
    mock_get.side_effect = [ConnectionError("Connection Error"), mock_response]

    transport = RequestsTransport("app_id", "app_token", "https://api.example.com")

    with patch("time.sleep"):
        result = transport.get("/endpoint")

    assert result == {"test": "data"}


@patch("requests.get")
def test_requests_transport_get_access_denied_403(mock_get):
    """Test RequestsTransport.get handles 403 access denied"""
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"message": "Access Denied"}
    mock_get.return_value = mock_response

    transport = RequestsTransport(
        "app_id", "app_token", "https://api.example.com", "user_token"
    )

    with pytest.raises(AccessDeniedException):
        transport.get("/endpoint", fail_on_auth_missing=True)


@patch("requests.get")
def test_requests_transport_get_prace_serwisowe(mock_get):
    """Test RequestsTransport.get detects maintenance mode"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"prace serwisowe"
    # Use the exact exception types that the code catches
    mock_response.json.side_effect = JSONDecodeError("No JSON", "", 0)
    mock_get.return_value = mock_response

    transport = RequestsTransport("app_id", "app_token", "https://api.example.com")

    with pytest.raises(PraceSerwisoweException):
        transport.get("/endpoint")


@patch("requests.post")
def test_requests_transport_post_success(mock_post):
    """Test RequestsTransport.post successful request"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "123"}
    mock_post.return_value = mock_response

    transport = RequestsTransport(
        "app_id", "app_token", "https://api.example.com", "user_token"
    )
    result = transport.post("/endpoint", body={"test": "data"})

    assert result == {"id": "123"}


@patch("requests.post")
def test_requests_transport_post_includes_headers(mock_post):
    """Test RequestsTransport.post includes required headers"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_post.return_value = mock_response

    transport = RequestsTransport(
        "app_id", "app_token", "https://api.example.com", "user_token"
    )
    transport.post("/endpoint", body={})

    call_kwargs = mock_post.call_args[1]
    headers = call_kwargs["headers"]

    assert headers["X-App-Id"] == "app_id"
    assert headers["X-App-Token"] == "app_token"
    assert headers["X-User-Token"] == "user_token"


@patch("requests.delete")
def test_requests_transport_post_delete_method(mock_delete):
    """Test RequestsTransport.post uses DELETE method when delete=True"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_delete.return_value = mock_response

    transport = RequestsTransport(
        "app_id", "app_token", "https://api.example.com", "user_token"
    )
    transport.post("/endpoint", body={}, delete=True)

    mock_delete.assert_called_once()


@patch("requests.post")
def test_requests_transport_post_access_denied_403(mock_post):
    """Test RequestsTransport.post handles access denied"""
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"message": "Access Denied"}
    mock_post.return_value = mock_response

    transport = RequestsTransport(
        "app_id", "app_token", "https://api.example.com", "user_token"
    )

    with pytest.raises(AccessDeniedException):
        transport.post("/endpoint", body={})


@patch("requests.post")
def test_requests_transport_post_invalid_json_on_403(mock_post):
    """Test RequestsTransport.post handles invalid JSON on 403"""
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.content = b"Invalid JSON response"
    mock_response.json.side_effect = ValueError("No JSON")
    mock_post.return_value = mock_response

    transport = RequestsTransport(
        "app_id", "app_token", "https://api.example.com", "user_token"
    )

    with pytest.raises(HttpException):
        transport.post("/endpoint", body={})
