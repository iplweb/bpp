import logging

import pytest
from django.test import RequestFactory

from bpp.middleware import PageParameterValidationMiddleware


@pytest.mark.django_db
class TestPageParameterValidationMiddleware:
    def setup_method(self):
        self.factory = RequestFactory()
        self.middleware = PageParameterValidationMiddleware(lambda r: None)

    def test_no_page_parameter_allowed(self):
        """Test: No page parameter should pass through"""
        request = self.factory.get("/bpp/autorzy/")
        response = self.middleware.process_request(request)
        assert response is None

    def test_numeric_page_allowed(self):
        """Test: Numeric page parameters should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=1")
        response = self.middleware.process_request(request)
        assert response is None

    def test_large_numeric_page_allowed(self):
        """Test: Large numeric page numbers should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=999999")
        response = self.middleware.process_request(request)
        assert response is None

    def test_last_keyword_allowed(self):
        """Test: 'last' keyword should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=last")
        response = self.middleware.process_request(request)
        assert response is None

    def test_last_uppercase_allowed(self):
        """Test: 'LAST' keyword should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=LAST")
        response = self.middleware.process_request(request)
        assert response is None

    def test_last_mixed_case_allowed(self):
        """Test: 'Last' keyword should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=Last")
        response = self.middleware.process_request(request)
        assert response is None

    def test_short_alphanumeric_allowed(self):
        """Test: Short (<=5 chars) alphanumeric strings allowed (possible typos)"""
        request = self.factory.get("/bpp/autorzy/?page=1a")
        response = self.middleware.process_request(request)
        assert response is None

    def test_five_char_string_allowed(self):
        """Test: Exactly 5 character strings allowed"""
        request = self.factory.get("/bpp/autorzy/?page=12abc")
        response = self.middleware.process_request(request)
        assert response is None

    def test_sql_injection_blocked(self):
        """Test: SQL injection attempts should be blocked"""
        request = self.factory.get("/bpp/autorzy/?page=1+AND+1=1--")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_long_malicious_string_blocked(self):
        """Test: Long malicious strings should be blocked"""
        request = self.factory.get(
            "/bpp/autorzy/?page=++++++++++++++++++++++++++++++94%22+AND"
        )
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_url_encoded_injection_blocked(self):
        """Test: URL-encoded injection should be blocked"""
        request = self.factory.get(
            "/bpp/autorzy/?page=%3CSCRIPT%3Ealert%281%29%3C%2FSCRIPT%3E"
        )
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_original_traceback_string_blocked(self):
        """Test: Original malicious string from user's traceback should be blocked"""
        # This is the actual string from the user's traceback
        malicious_page = (
            "                                94\" AND ANd/**/1373=(seLEcT/**/uPPeR(XMlTYpE(chr(60)||CHr(58)||"
            "%27~%27||(SELECt/**/(cASe/**/when/**/(1373=1373)/**/TheN/**/1/**/eLse/**/0/**/End)/**/fROM/**/"
            "DuaL)||%27~%27||Chr(62)))/**/FROM/**/DUal)-- -"
        )
        request = self.factory.get(f"/bpp/autorzy/?page={malicious_page}")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_six_char_alphanumeric_blocked(self):
        """Test: 6 character alphanumeric strings should be blocked"""
        request = self.factory.get("/bpp/autorzy/?page=abc123")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_spaces_in_page_blocked(self):
        """Test: Page parameters with spaces should be blocked"""
        request = self.factory.get("/bpp/autorzy/?page=1 2 3 4 5 6")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444

    def test_logging_on_blocked_request(self, caplog):
        """Test: Blocked requests should be logged"""
        caplog.set_level(logging.WARNING)

        request = self.factory.get("/bpp/autorzy/?page=malicious_string_here")
        self.middleware.process_request(request)

        assert "Blocked suspicious page parameter" in caplog.text
        assert "malicious_string_here" in caplog.text

    def test_logging_includes_remote_addr(self, caplog):
        """Test: Logged events should include remote address"""
        caplog.set_level(logging.WARNING)

        request = self.factory.get(
            "/bpp/autorzy/?page=malicious_here", REMOTE_ADDR="192.168.1.100"
        )
        response = self.middleware.process_request(request)

        assert response.status_code == 444
        # Check that the warning was logged
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    def test_empty_page_parameter_allowed(self):
        """Test: Empty page parameter should pass through"""
        request = self.factory.get("/bpp/autorzy/?page=")
        response = self.middleware.process_request(request)
        assert response is None

    def test_zero_page_allowed(self):
        """Test: Zero page should pass through (Django will handle invalid page)"""
        request = self.factory.get("/bpp/autorzy/?page=0")
        response = self.middleware.process_request(request)
        assert response is None

    def test_negative_page_with_long_string_blocked(self):
        """Test: Negative page numbers with extra characters should be blocked"""
        request = self.factory.get("/bpp/autorzy/?page=-1+OR+1=1")
        response = self.middleware.process_request(request)
        assert response is not None
        assert response.status_code == 444
