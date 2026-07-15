"""Auto-mapowanie kolumn dla plików typu IHIT (długie/nietypowe nagłówki)."""

from import_pracownikow.mapping import POLE_POMIN, zaproponuj_mapowanie


def test_afiliacja_na_nazwe_jednostki():
    assert zaproponuj_mapowanie(["afiliacja"])["afiliacja"] == "nazwa_jednostki"
    assert zaproponuj_mapowanie(["afiliacje"])["afiliacje"] == "nazwa_jednostki"


def test_drugie_na_drugie_imie():
    assert zaproponuj_mapowanie(["drugie"])["drugie"] == "drugie_imię"


def test_dlugi_naglowek_z_tytul_na_tytul_stopien():
    # realny nagłówek IHIT — zawiera „tytul" i „stopien" (oba → tytuł/stopień)
    h = "stopien_tytul_aktualny_na_dzien_wygenerowania_raportu"
    assert zaproponuj_mapowanie([h])[h] == "tytuł_stopień"


def test_naglowek_zawierajacy_tytul_z_diakrytykiem():
    assert zaproponuj_mapowanie(["tytuł_zawodowy"])["tytuł_zawodowy"] == "tytuł_stopień"


def test_niepasujacy_naglowek_nadal_pomin():
    h = "cokolwiek_zupelnie_innego"
    assert zaproponuj_mapowanie([h])[h] == POLE_POMIN


def test_dokladny_synonim_wygrywa_nad_podlancuchem():
    # „nazwisko" nie może zostać przechwycone przez fallback podłańcuchowy
    assert zaproponuj_mapowanie(["nazwisko"])["nazwisko"] == "nazwisko"
