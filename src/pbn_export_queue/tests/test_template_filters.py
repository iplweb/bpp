import pytest

from pbn_export_queue.templatetags.pbn_queue_extras import format_pbn_error


@pytest.mark.django_db
def test_format_pbn_error_merytoryczny_hides_header():
    """MERYTORYCZNY errors should hide redundant header/message/description"""
    komunikat = """Traceback (most recent call last):
  File "/app/src/pbn_export_queue/models.py", line 358, in send_to_pbn
pbn_api.exceptions.HttpException: (400, '/api/v1/publications', '{"code":400,"message":"Bad Request","description":"Validation failed.","details":{"isbn":"Publikacja o identycznym ISBN już istnieje!"}}')
"""

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
    komunikat = """Traceback (most recent call last):
  File "/app/src/pbn_export_queue/models.py", line 358, in send_to_pbn
pbn_api.exceptions.HttpException: (500, '/api/v1/publications', '{"code":500,"message":"Internal Server Error"}')
"""

    result = format_pbn_error(komunikat, "TECH")

    # Should contain full header
    assert "HttpException: HTTP 500" in result
    assert "Wiadomość:" in result
    assert "Internal Server Error" in result


@pytest.mark.django_db
def test_format_pbn_error_no_rodzaj_bledu_shows_full_header():
    """When rodzaj_bledu is not provided, show full header (backward compatibility)"""
    komunikat = """Traceback (most recent call last):
  File "/app/src/pbn_export_queue/models.py", line 358, in send_to_pbn
pbn_api.exceptions.HttpException: (400, '/api/v1/publications', '{"code":400,"message":"Bad Request","description":"Validation failed.","details":{"doi":"Duplicate"}}')
"""

    result = format_pbn_error(komunikat)  # No rodzaj_bledu parameter

    # Should show full header (default behavior)
    assert "HttpException: HTTP 400" in result
    assert "Wiadomość:" in result
    assert "Opis:" in result


@pytest.mark.django_db
def test_format_pbn_error_escapes_html_in_fallback_line():
    """Treść błędu PBN w ścieżce fallback musi być escapowana (stored-XSS)."""
    result = format_pbn_error("<script>alert('xss')</script>")

    assert "<script>" not in result
    assert "&lt;script&gt;" in result


@pytest.mark.django_db
def test_format_pbn_error_escapes_html_in_description_and_details():
    """Pola description/details z payloadu PBN muszą być escapowane."""
    komunikat = (
        "pbn_api.exceptions.HttpException: (400, '/api/v1/publications', "
        '\'{"code":400,"description":"<script>alert(1)</script>",'
        '"details":{"isbn":"<img src=x onerror=alert(2)>"}}\')'
    )

    result = format_pbn_error(komunikat)

    assert "<script>" not in result
    assert "<img src=x" not in result
    assert "&lt;script&gt;" in result
    assert "&lt;img" in result


@pytest.mark.django_db
def test_format_pbn_error_escapes_simple_exception_message():
    """Prosty komunikat wyjątku również escapowany."""
    komunikat = "pbn_api.exceptions.StatementsMissing: </pre><script>alert(3)</script>"

    result = format_pbn_error(komunikat)

    assert "<script>" not in result
    assert "&lt;" in result


def test_render_html_widget_escapes_value():
    """Widget admina kolejki renderuje TextField jako HTML — musi escapować."""
    from pbn_export_queue.admin import RenderHTMLWidget

    out = RenderHTMLWidget().render(
        "field", "<script>alert(1)</script>\ndruga linia", renderer=None
    )

    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    # nowa linia dalej zamieniana na <br>
    assert "<br>" in out
