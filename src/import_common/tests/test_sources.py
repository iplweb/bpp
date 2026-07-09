from import_common.sources import XLSXSource, wykryj_format


def test_wykryj_format_xlsx_po_magic_bytes(test1_xlsx):
    # XLSX = archiwum ZIP, zaczyna się od b"PK"
    assert wykryj_format(test1_xlsx) == "xlsx"


def test_wykryj_format_csv_gdy_nie_zip(tmp_path):
    p = tmp_path / "dane.csv"
    p.write_text("Nazwisko;Imię\nKowalski;Jan\n", encoding="utf-8")
    assert wykryj_format(str(p)) == "csv"


def test_xlsxsource_deleguje_do_xlsimportfile(default_xlsx):
    src = XLSXSource(default_xlsx)
    # count() i data() zwracają to samo, co XLSImportFile
    assert src.count() >= 0
    wiersze = list(src.data())
    assert len(wiersze) == src.count()
    if wiersze:
        # kontrakt kluczy lokalizacyjnych
        assert "__xls_loc_sheet__" in wiersze[0]
        assert "__xls_loc_row__" in wiersze[0]
