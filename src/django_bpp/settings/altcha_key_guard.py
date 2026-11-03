"""Predykat placeholdera ``ALTCHA_HMAC_KEY`` (fail-closed w ``production.py``).

Klucz HMAC podpisuje wyzwania CAPTCHA formularza zgłoszeń publikacji. Gdy
CAPTCHA jest włączona, a klucz to wartość jawnie znana (sentinel z
``base.py``, ``.env.docker`` bez zmian, wartość build-owa), weryfikacja
CAPTCHA nie daje żadnej ochrony. Produkcja w takiej konfiguracji nie
wstaje (``ImproperlyConfigured``); w dev wystarcza system-check Warning
(``zglos_publikacje/checks.py``), który korzysta z tego samego predykatu.

Czysta funkcja (bez importu ``settings``) — testowalna bez środowiska
produkcyjnego.
"""


def altcha_klucz_niebezpieczny_placeholder(klucz, *, unset_sentinel):
    """Czy ``klucz`` to placeholder, którego nie wolno użyć z włączoną CAPTCHA.

    :param klucz: wartość ``ALTCHA_HMAC_KEY``.
    :param unset_sentinel: default z ``base.py`` (``ALTCHA_HMAC_KEY_UNSET``).
    """
    if not klucz:
        return True
    if klucz == unset_sentinel:
        return True
    # .env.docker placeholder ("ZMIEN...") oraz build-time dummy.
    return "ZMIEN" in klucz or "build-time" in klucz
