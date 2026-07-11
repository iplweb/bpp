import json
import sqlite3

import pytest
from django.core.management import call_command
from model_bakery import baker


def _db(tmp_path, patents):
    p = tmp_path / "ppm.sqlite3"
    con = sqlite3.connect(p)
    con.execute(
        "CREATE TABLE records (type TEXT, source_id TEXT, source_url TEXT, "
        "parsed_json TEXT)"
    )
    for i, pj in enumerate(patents):
        con.execute(
            "INSERT INTO records (type, source_id, source_url, parsed_json) "
            "VALUES (?,?,?,?)",
            ("patent", f"TEST{i}", f"http://x/{i}", json.dumps(pj)),
        )
    con.commit()
    con.close()
    return str(p)


@pytest.mark.django_db
def test_scan_writes_both_csvs(tmp_path):
    baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    db = _db(
        tmp_path,
        [
            {
                "title": "T1",
                "inventors": ["Anna Wawruszak", "Jan Kovalski"],
                "application_number": "P.1",
                "application_date": "01-01-2023",
                "all_fields": {"Numer patentu/prawa": "Pat.1"},
            },
        ],
    )
    out_a = tmp_path / "autorzy.csv"
    out_p = tmp_path / "patenty.csv"
    call_command(
        "import_sqlite_scan",
        db,
        "--typ",
        "patent",
        "--out-autorzy",
        str(out_a),
        "--out-patenty",
        str(out_p),
    )
    a_text = out_a.read_text(encoding="utf-8")
    assert "Anna Wawruszak" in a_text and "Jan Kovalski" in a_text
    assert "DOKLADNE" in a_text  # Anna dopasowana
    assert "Pat.1" in out_p.read_text(encoding="utf-8")
