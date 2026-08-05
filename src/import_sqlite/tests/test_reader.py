import json
import sqlite3

import pytest

from import_sqlite.reader import RawRecord, iter_records


def _make_db(tmp_path, rows):
    db = tmp_path / "ppm.sqlite3"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE records (type TEXT, source_id TEXT, source_url TEXT, "
        "raw_html TEXT, content_hash TEXT, fetched_at TEXT, parsed_json TEXT, "
        "parsed_at TEXT)"
    )
    for r in rows:
        con.execute(
            "INSERT INTO records (type, source_id, source_url, parsed_json) "
            "VALUES (?, ?, ?, ?)",
            r,
        )
    con.commit()
    con.close()
    return str(db)


def test_iter_records_yields_parsed(tmp_path):
    db = _make_db(
        tmp_path,
        [
            ("patent", "TEST1", "http://x/1", json.dumps({"title": "A"})),
            ("patent", "TEST2", "http://x/2", json.dumps({"title": "B"})),
        ],
    )
    out = list(iter_records(db, "patent"))
    assert out == [
        RawRecord("TEST1", "http://x/1", {"title": "A"}),
        RawRecord("TEST2", "http://x/2", {"title": "B"}),
    ]


def test_iter_records_filters_by_type(tmp_path):
    db = _make_db(
        tmp_path,
        [
            ("patent", "TEST1", "http://x/1", json.dumps({"title": "A"})),
            ("project", "TEST2", "http://x/2", json.dumps({"title": "B"})),
        ],
    )
    out = list(iter_records(db, "patent"))
    assert [r.source_id for r in out] == ["TEST1"]


def test_iter_records_skips_bad_json(tmp_path):
    db = _make_db(
        tmp_path,
        [
            ("patent", "TEST1", "http://x/1", "{not json"),
            ("patent", "TEST2", "http://x/2", json.dumps({"title": "B"})),
        ],
    )
    with pytest.warns(UserWarning):
        out = list(iter_records(db, "patent"))
    assert [r.source_id for r in out] == ["TEST2"]
