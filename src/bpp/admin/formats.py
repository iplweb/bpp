from import_export.formats.base_formats import XLSX
from tablib.formats import registry


class PrettyXLSX(XLSX):
    TABLIB_MODULE = "prettyxlsx"

    def get_title(self):
        return "prettyxlsx"


registry.register("prettyxlsx", "bpp.admin._prettyxlsx.PrettyXLSXFormat")
