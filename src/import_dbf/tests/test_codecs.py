from import_dbf.codecs import custom_decode


def test_custom_decode():
    assert custom_decode(b"Sparber\x81-Sauer", "strict") == ("Sparber-Sauer", 13)
