from import_pracownikow.parsers.wartosci import oczysc_email


def test_poprawny_email_przechodzi_i_normalizuje():
    dane = {"email": "  Jan.Kowalski@Example.COM "}
    ostrz = oczysc_email(dane)
    assert dane["email"] == "jan.kowalski@example.com"
    assert ostrz is None


def test_niepoprawny_email_czyszczony_i_ostrzega():
    dane = {"email": "to-nie-jest-email"}
    ostrz = oczysc_email(dane)
    assert dane["email"] == ""
    assert ostrz is not None
    assert "e-mail" in ostrz.lower()
    assert "to-nie-jest-email" in ostrz


def test_pusty_email_bez_ostrzezenia():
    dane = {"email": ""}
    assert oczysc_email(dane) is None
    assert dane["email"] == ""


def test_brak_klucza_no_op():
    dane = {"nazwisko": "Kowalski"}
    assert oczysc_email(dane) is None
    assert "email" not in dane


def test_wartosc_nietekstowa_nie_wywala():
    # openpyxl potrafi dać komórkę liczbową — str() + walidacja, bez wyjątku
    dane = {"email": 12345}
    ostrz = oczysc_email(dane)
    assert dane["email"] == ""
    assert ostrz is not None


def test_zbyt_dlugi_email_odrzucony():
    # Autor.email = EmailField(max_length=128) — dłuższy adres odrzucamy, żeby
    # nie wywalić Autor.objects.create
    dane = {"email": "a" * 120 + "@example.com"}  # 132 znaki
    ostrz = oczysc_email(dane)
    assert dane["email"] == ""
    assert ostrz is not None
    assert "e-mail" in ostrz.lower()
