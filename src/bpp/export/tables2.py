"""Eksport tabel django-tables2 z sanityzacją komórek arkusza."""

from django_tables2.export.export import TableExport


class BezpiecznyTableExport(TableExport):
    """``TableExport``, który dla formatów arkuszowych zapisuje tekst
    zaczynający się od =, +, -, @, Tab, CR, LF jako tekst, nie formułę.

    Użycie w widoku z ``django_tables2.export.views.ExportMixin``::

        export_class = BezpiecznyTableExport
    """

    FORMATY_ARKUSZOWE = frozenset(
        {
            TableExport.CSV,
            TableExport.ODS,
            TableExport.TSV,
            TableExport.XLS,
            TableExport.XLSX,
        }
    )

    def table_to_dataset(self, table, exclude_columns, dataset_kwargs=None):
        dataset = super().table_to_dataset(table, exclude_columns, dataset_kwargs)
        if self.format in self.FORMATY_ARKUSZOWE:
            from bpp.util import sanitize_tablib_dataset

            sanitize_tablib_dataset(dataset)
        return dataset
