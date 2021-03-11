from .normalization import normalize_exception_reason


class ImproperFileException(Exception):
    pass


class BadNoOfSheetsException(Exception):
    pass


class HeaderNotFoundException(Exception):
    pass


class InputDataError(Exception):
    pass


class XLSParseError(Exception):
    def __init__(self, elem, form, reason):
        self.elem = elem
        self.form = form
        self.reason = reason

    def __str__(self):
        errors = getattr(self.form, "errors")
        if errors:
            errors = errors.as_json()

        return (
            f"Błąd w pliku XLS: "
            f"arkusz nr {self.elem.get('__xls_loc_sheet__')}, "
            f"wiersz nr {self.elem.get('__xls_loc_row__') + 1}, "
            f"etap: {self.reason}, "
            f"błędy: {errors}. "
            f"Oryginalne dane z XLS : {self.elem}"
        )


class XLSMatchError(Exception):
    def __init__(self, elem, object, reason):
        self.elem = elem
        self.object = object
        self.reason = reason

    def __str__(self):
        return (
            f"Nie można zmatchować danych z plikiem XLS: "
            f"arkusz nr {self.elem.get('__xls_loc_sheet__')}, "
            f"wiersz nr {self.elem.get('__xls_loc_row__') + 1}, "
            f"obiekt: {self.object}, "
            f"przyczyna: {self.reason}. "
            f"Oryginalne dane z XLS : {self.elem}"
        )


class BPPDatabaseMismatch(Exception):
    def __init__(self, elem, object, reason):
        self.elem = elem
        self.object = object
        self.reason = reason

    def __str__(self):
        return (
            f"Dane po stronie BPP uniemożliwiają jednoznaczne uzgodnienie rekordu: "
            f"skoroszyt nr {self.elem.get('__xls_loc_sheet__')}, "
            f"wiersz nr {self.elem.get('__xls_loc_row__') + 1}, "
            f"obiekt: {self.object}, "
            f"przyczyna: {self.reason}. "
            f"Oryginalne dane z XLS : {self.elem}"
        )


class BPPDatabaseError(Exception):
    def __init__(self, elem, object, reason):
        self.elem = elem
        self.object = object
        self.reason = reason

    def __str__(self):
        return (
            f"Wystąpił błąd bazy danych po stronie BPP przy próbie integracji danych: "
            f"skoroszyt nr {self.elem.get('__xls_loc_sheet__')}, "
            f"wiersz nr {self.elem.get('__xls_loc_row__') + 1}, "
            f"obiekt: {self.object}, "
            f"przyczyna: {normalize_exception_reason(self.reason)}. "
            f"Oryginalne dane z XLS : {self.elem}"
        )
