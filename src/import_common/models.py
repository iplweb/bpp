class ImportRowMixin:
    def nr_arkusza(self):
        return self.dane_z_xls.get("__xls_loc_sheet__")

    def nr_wiersza(self):
        return self.dane_z_xls.get("__xls_loc_row__")
