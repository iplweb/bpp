import os

import pytest

from import_dbf.util import (
    addslashes,
    dbf2sql,
    exp_add_spacing,
    exp_parse_str,
    xls2dict,
    exp_split_poz_str,
)


def test_util_addslashes():
    assert addslashes(None) is None
    assert addslashes(1) == 1
    assert addslashes("foo'") == "foo''"


def test_util_import_dbf():
    dbf2sql(os.path.join(os.path.dirname(__file__), "test.dbf"))
    open(os.path.join(os.path.dirname(__file__), "test.dbf") + ".sql")


@pytest.mark.parametrize(
    "input, output",
    [
        (
            "#204$ #a$ Zachowania zdrowotne dzieci w wieku szkolnym - badania wstępne #b$ #c$ #d$ #e$ s.184-191 "
            "#f$ ryc., tab., bibliogr., streszcz.",
            {
                "id": 204,
                "a": "Zachowania zdrowotne dzieci w wieku szkolnym - badania wstępne",
                "b": "",
                "c": "",
                "d": "",
                "e": "s.184-191",
                "f": "ryc., tab., bibliogr., streszcz.",
            },
        ),
        (
            "#102$ #a$ Autologous hematopoietic stem cell transplant for progressive"
            " diffuse systemic sclerosis: procedural "
            "success and clinical outcome in 5-year follow-up #b$ #c$ #d$",
            {
                "id": 102,
                "a": "Autologous hematopoietic stem cell transplant for progressive diffuse systemic sclerosis: "
                "procedural success and clinical outcome in 5-year follow-up",
                "b": "",
                "c": "",
                "d": "",
            },
        ),
        (
            "#150$ #a$ Badania nad wpływem selenu na integralność chromatyny plemnikowej w przypadkach mężczyzn z "
            "upośledzoną płodnością #b$ #c$ #d$",
            {
                "id": 150,
                "a": "Badania nad wpływem selenu na integralność chromatyny plemnikowej w przypadkach mężczyzn "
                "z upośledzoną płodnością",
                "b": "",
                "c": "",
                "d": "",
            },
        ),
        (
            "#150$ #a$Neurologia #c$Howard L. Weiner, Lawrence P. Levitt	",
            {"id": 150, "a": "Neurologia", "c": "Howard L. Weiner, Lawrence P. Levitt"},
        ),
        (
            "#103$#a$ Abstracts of the 5-th World Congress on Heart Failure - Mechanisms and Managment. "
            "Washinfton, USA, 11-14 May, 1997",
            {
                "id": 103,
                "a": "Abstracts of the 5-th World Congress on Heart Failure - Mechanisms and Managment. "
                "Washinfton, USA, 11-14 May, 1997",
            },
        ),
    ],
)
def test_util_exp_parse_str(input, output):
    assert exp_parse_str(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (
            "#153$ #a$ 162 s. #b$ bibliogr. #c$\r\n#154$ #a$|0000004804#b$ #c$\r\n"
            "nr 154 #d$ #e$\r\n#155$ #a$ ISBN 978-83-66066-86-1#988$ #a$|0000\r\n"
            "006505#b$|0000006506#991$ #a$ 10.34616/23.19.146\r\n#995$ #a$ http\r\n"
            "s://www.bibliotekacyfrowa.pl/publication/108240\r\n               ",
            [
                "#153$ #a$ 162 s. #b$ bibliogr. #c$",
                "#154$ #a$|0000004804#b$ #c$nr 154 #d$ #e$",
                "#155$ #a$ ISBN 978-83-66066-86-1",
                "#988$ #a$|0000006505#b$|0000006506",
                "#991$ #a$ 10.34616/23.19.146",
                "#995$ #a$ https://www.bibliotekacyfrowa.pl/publication/108240               ",
            ],
        )
    ],
)
def test_util_exp_split_poz_str(input, output):
    assert output == list(exp_split_poz_str(input))


def test_util_exp_parse_str_raises():
    bad = (
        "#105$ Electrophysiological estimation of the peripheral nerves conduction "
        "parameters and the autonomic nervous system function in the course"
        " of amyotrophic lateral sclerosis #b$"
    )
    with pytest.raises(ValueError):
        exp_parse_str(bad)


def test_util_exp_add_spacing():
    assert exp_add_spacing(" te  st (fa. ) ") == " te st (fa.) "


def test_xls2dict():
    ret = list(xls2dict(os.path.join(os.path.dirname(__file__), "test_chf.xlsx")))
    assert ret[0]["skrot"] == "PAA"
