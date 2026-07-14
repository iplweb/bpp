"""mask_secret nie ujawnia sekretów PBN w stdout/logach (uwaga reviewera #4).

Tryb verbose komend PBN wypisywał app token i user token jawnie — zostają
w terminalu, CI albo przechwyconych logach. Maskujemy do ostatnich 4 znaków.
"""

from pbn_client.utils import mask_secret


def test_mask_secret_zachowuje_tylko_ostatnie_4():
    assert mask_secret("abcdef123456") == "********3456"


def test_mask_secret_nie_ujawnia_wiekszosci():
    masked = mask_secret("supersecrettoken")
    assert "supersecret" not in masked
    assert masked.endswith("oken")


def test_mask_secret_krotki_caly_zamaskowany():
    # Krótszy niż liczba widocznych znaków — nic nie ujawniamy.
    assert mask_secret("abc") == "***"
    assert mask_secret("abcd") == "****"


def test_mask_secret_pusty_lub_none():
    assert mask_secret(None) == "(brak)"
    assert mask_secret("") == "(brak)"
