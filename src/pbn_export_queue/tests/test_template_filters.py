import pytest

from pbn_export_queue.templatetags.pbn_queue_extras import format_pbn_error


@pytest.mark.django_db
def test_format_pbn_error_merytoryczny_hides_header():
    """MERYTORYCZNY errors should hide redundant header/message/description"""
    komunikat = '''Traceback (most recent call last):
  File "/app/src/pbn_export_queue/models.py", line 358, in send_to_pbn
pbn_api.exceptions.HttpException: (400, '/api/v1/publications', '{"code":400,"message":"Bad Request","description":"Validation failed.","details":{"isbn":"Publikacja o identycznym ISBN już istnieje!"}}')
'''

    result = format_pbn_error(komunikat, "MERYT")

    # Should NOT contain header/message/description
    assert "HttpException: HTTP 400" not in result
    assert "Wiadomość:" not in result
    assert "Opis: Validation failed" not in result

    # Should contain details
    assert "Szczegóły:" in result
    assert "isbn" in result
    assert "Publikacja o identycznym ISBN" in result

    # Should still show endpoint
    assert "Endpoint:" in result


@pytest.mark.django_db
def test_format_pbn_error_techniczny_shows_full_header():
    """TECHNICZNY errors should show full header information"""
    komunikat = '''Traceback (most recent call last):
  File "/app/src/pbn_export_queue/models.py", line 358, in send_to_pbn
pbn_api.exceptions.HttpException: (500, '/api/v1/publications', '{"code":500,"message":"Internal Server Error"}')
'''

    result = format_pbn_error(komunikat, "TECH")

    # Should contain full header
    assert "HttpException: HTTP 500" in result
    assert "Wiadomość:" in result
    assert "Internal Server Error" in result


@pytest.mark.django_db
def test_format_pbn_error_no_rodzaj_bledu_shows_full_header():
    """When rodzaj_bledu is not provided, show full header (backward compatibility)"""
    komunikat = '''Traceback (most recent call last):
  File "/app/src/pbn_export_queue/models.py", line 358, in send_to_pbn
pbn_api.exceptions.HttpException: (400, '/api/v1/publications', '{"code":400,"message":"Bad Request","description":"Validation failed.","details":{"doi":"Duplicate"}}')
'''

    result = format_pbn_error(komunikat)  # No rodzaj_bledu parameter

    # Should show full header (default behavior)
    assert "HttpException: HTTP 400" in result
    assert "Wiadomość:" in result
    assert "Opis:" in result
