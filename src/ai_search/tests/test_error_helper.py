from bpp.djangoql_helpers import _error_location, _format_error_text


class _Exc(Exception):
    def __init__(self, msg, line=None, column=None, value=None):
        super().__init__(msg)
        self.line = line
        self.column = column
        self.value = value


def test_error_location_from_line_column():
    exc = _Exc("blad", line=1, column=5)
    assert _error_location(exc, "rok = 20x") == (1, 5, "to_end")


def test_error_location_from_value_token():
    exc = _Exc("nieznane pole", value="nazwiskoo")
    line, col, mark = _error_location(exc, 'nazwiskoo ~ "x"')
    assert (line, mark) == (1, "token")


def test_format_error_plain():
    assert _format_error_text(_Exc("ups")) == "ups"
