from bpp.multiseek_registry import pivot


def test_parse_pivot_params_defaults_when_empty():
    row, col, metric = pivot.parse_pivot_params({})
    assert row.key == "rok"
    assert col is None
    assert metric.key == "liczba"


def test_parse_pivot_params_unknown_keys_fall_back():
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "xxx", "pivot_col": "yyy", "pivot_val": "zzz"}
    )
    assert row.key == "rok"
    assert col is None
    assert metric.key == "liczba"


def test_parse_pivot_params_column_must_allow_column():
    # "jednostka" jest tylko wierszem (allow_column=False) → col=None
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "rok", "pivot_col": "jednostka", "pivot_val": "liczba"}
    )
    assert col is None


def test_parse_pivot_params_column_equal_to_row_dropped():
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "rok", "pivot_col": "rok"}
    )
    assert col is None


def test_parse_pivot_params_valid_crosstab():
    row, col, metric = pivot.parse_pivot_params(
        {"pivot_row": "rok", "pivot_col": "charakter_ogolny", "pivot_val": "punkty_kbn"}
    )
    assert (row.key, col.key, metric.key) == ("rok", "charakter_ogolny", "punkty_kbn")
