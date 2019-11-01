import os

import pytest

from import_dbf.util import addslashes, import_dbf, exp_parse_str, exp_add_spacing


def test_util_addslashes():
    assert addslashes(None) == None
    assert addslashes(1) == 1
    assert addslashes("foo'") == "foo''"


def test_util_import_dbf():
    import_dbf(os.path.join(os.path.dirname(__file__), "test.dbf"))


@pytest.mark.parametrize(
    "input, output",

    [("#204$ #a$ Zachowania zdrowotne dzieci w wieku szkolnym - badania wstępne #b$ #c$ #d$ #e$ s.184-191 "
      "#f$ ryc., tab., bibliogr., streszcz.",
      {'id': 204,
       'a': 'Zachowania zdrowotne dzieci w wieku szkolnym - badania wstępne',
       'b': '',
       'c': '',
       'd': '',
       'e': 's.184-191',
       'f': 'ryc., tab., bibliogr., streszcz.', }
      ),

     ("#102$ #a$ Autologous hematopoietic stem cell transplant for progressive diffuse systemic sclerosis: procedural "
      "success and clinical outcome in 5-year follow-up #b$ #c$ #d$",
      {'id': 102,
       'a': 'Autologous hematopoietic stem cell transplant for progressive diffuse systemic sclerosis: procedural success and clinical outcome in 5-year follow-up',
       'b': '',
       'c': '',
       'd': ''}
      ),

     ('#150$ #a$ Badania nad wpływem selenu na integralność chromatyny plemnikowej w przypadkach mężczyzn z '
      'upośledzoną płodnością #b$ #c$ #d$',
      {'id': 150,
       'a': 'Badania nad wpływem selenu na integralność chromatyny plemnikowej w przypadkach mężczyzn z upośledzoną płodnością',
       'b': '',
       'c': '',
       'd': ''}
      ),

     ('#150$ #a$Neurologia #c$Howard L. Weiner, Lawrence P. Levitt	',
      {'id': 150,
       'a': 'Neurologia',
       'c': 'Howard L. Weiner, Lawrence P. Levitt'}),

     (
     '#103$#a$ Abstracts of the 5-th World Congress on Heart Failure - Mechanisms and Managment. Washinfton, USA, 11-14 May, 1997',
     {'id': 103,
      'a': 'Abstracts of the 5-th World Congress on Heart Failure - Mechanisms and Managment. Washinfton, USA, 11-14 May, 1997'}),

     ]
)
def test_util_exp_parse_str(input, output):
    assert exp_parse_str(input) == output


def test_util_exp_parse_str_raises():
    bad = '#105$ Electrophysiological estimation of the peripheral nerves conduction parameters and the autonomic nervous system function in the course of amyotrophic lateral sclerosis #b$'
    with pytest.raises(ValueError):
        exp_parse_str(bad)


def test_util_exp_add_spacing():
    assert exp_add_spacing("te.st.this.(act.)") == "te. st. this. (act.)"

