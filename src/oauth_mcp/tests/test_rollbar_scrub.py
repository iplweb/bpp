"""Rollbar musi maskować sekrety OAuth (uwaga reviewera #3).

/o/token/ i /o/revoke_token/ to widoki DOT. DOT oznacza jako wrażliwe tylko
``password`` i ``client_secret``; pyrollbar domyślnie NIE scrubuje
``refresh_token``, ``code``, ``code_verifier`` ani ``token``. Nieoczekiwany
wyjątek 500 podczas wymiany/odświeżenia/rewokacji wysłałby aktywny sekret do
Rollbara. pyrollbar dopasowuje po DOKŁADNEJ nazwie klucza (nie po sufiksie) i
PODMIENIA domyślną listę, gdy podamy własną — więc lista musi zawierać zarówno
domyślne pola, jak i te specyficzne dla OAuth.
"""

from django.conf import settings


def test_rollbar_scrubuje_sekrety_oauth():
    scrub = {f.lower() for f in settings.ROLLBAR.get("scrub_fields", [])}
    for field in (
        "refresh_token",
        "code",
        "code_verifier",
        "token",
        "access_token",
        "client_secret",
        "authorization",
        "password",
    ):
        assert field in scrub, f"Rollbar nie scrubuje pola {field!r}"
