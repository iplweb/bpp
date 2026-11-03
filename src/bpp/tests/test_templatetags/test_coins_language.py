from types import SimpleNamespace

from bpp.templatetags.prace import generate_coins


def _praca(jezyk):
    return SimpleNamespace(
        charakter_formalny=None,
        tytul_oryginalny="Tytuł",
        rok=2024,
        jezyk=jezyk,
    )


def test_generate_coins_jezyk_jest_kodowany():
    coins = generate_coins(_praca(SimpleNamespace(skrot='a"<b> &c')), [])

    assert "rft.language=a%22%3Cb%3E%20%26c" in coins
    assert '"<b>' not in coins


def test_generate_coins_jezyk_zwykly_bez_zmian():
    coins = generate_coins(_praca(SimpleNamespace(skrot="ang.")), [])

    assert "rft.language=ang." in coins
