from import_pracownikow.mapping import zaproponuj_mapowanie


def test_stopien_z_tytulem_to_sluzbowy():
    m = zaproponuj_mapowanie(["tytuł", "stopień"])
    assert m["tytuł"] == "tytuł_stopień"
    assert m["stopień"] == "stopień_służbowy"


def test_sam_stopien_to_tytul_naukowy():
    m = zaproponuj_mapowanie(["stopień"])
    assert m["stopień"] == "tytuł_stopień"


def test_jawny_synonim_sluzbowy_bez_wzgledu_na_tytul():
    m = zaproponuj_mapowanie(["stopień_służbowy"])
    assert m["stopień_służbowy"] == "stopień_służbowy"
