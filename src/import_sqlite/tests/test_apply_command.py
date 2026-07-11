import json
import sqlite3

import pytest
from django.core.management import call_command
from model_bakery import baker

_HEADER = (
    "nazwisko_zrodlowe,given,family,wystapien,status,"
    "kandydat_1,kandydat_2,kandydat_3,decyzja\n"
)


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
            ("patent", f"UML{i}", f"http://x/{i}", json.dumps(pj)),
        )
    con.commit()
    con.close()
    return str(p)


def _one_patent_db(tmp_path):
    return _db(
        tmp_path,
        [
            {
                "title": "T1",
                "inventors": ["Anna Wawruszak"],
                "application_number": "P.1",
                "application_date": "01-01-2023",
                "all_fields": {"Numer patentu/prawa": "Pat.1"},
            },
        ],
    )


@pytest.fixture
def uczelnia_setup(db, status_korekty):
    u = baker.make("bpp.Uczelnia", nazwa="UML", skrot="UML")
    obca = baker.make(
        "bpp.Jednostka", nazwa="Obca", uczelnia=u, skupia_pracownikow=False
    )
    u.obca_jednostka = obca
    u.save()
    return u


@pytest.mark.django_db
def test_apply_creates_patent_from_csv(
    tmp_path, uczelnia_setup, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    a = baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    db = _one_patent_db(tmp_path)
    autorzy = tmp_path / "autorzy.csv"
    autorzy.write_text(
        _HEADER + f"Anna Wawruszak,Anna,Wawruszak,1,DOKLADNE,,,,{a.pk}\n",
        encoding="utf-8",
    )
    call_command(
        "import_sqlite_apply",
        db,
        "--typ",
        "patent",
        "--autorzy",
        str(autorzy),
        "--out-patenty",
        str(tmp_path / "out.csv"),
    )
    assert Patent.objects.filter(numer_prawa_wylacznego="Pat.1").count() == 1


@pytest.mark.django_db
def test_apply_dry_run_persists_nothing(
    tmp_path, uczelnia_setup, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    a = baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    db = _one_patent_db(tmp_path)
    autorzy = tmp_path / "autorzy.csv"
    autorzy.write_text(
        _HEADER + f"Anna Wawruszak,Anna,Wawruszak,1,DOKLADNE,,,,{a.pk}\n",
        encoding="utf-8",
    )
    call_command(
        "import_sqlite_apply",
        db,
        "--typ",
        "patent",
        "--autorzy",
        str(autorzy),
        "--dry-run",
        "--out-patenty",
        str(tmp_path / "out.csv"),
    )
    assert not Patent.objects.filter(numer_prawa_wylacznego="Pat.1").exists()


@pytest.mark.django_db
def test_apply_rejects_nonexistent_pk(
    tmp_path, uczelnia_setup, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from django.core.management.base import CommandError

    db = _one_patent_db(tmp_path)
    autorzy = tmp_path / "autorzy.csv"
    autorzy.write_text(
        _HEADER + "Anna Wawruszak,Anna,Wawruszak,1,DOKLADNE,,,,99999999\n",
        encoding="utf-8",
    )
    with pytest.raises(CommandError):
        call_command(
            "import_sqlite_apply",
            db,
            "--typ",
            "patent",
            "--autorzy",
            str(autorzy),
            "--out-patenty",
            str(tmp_path / "out.csv"),
        )
