from tempfile import NamedTemporaryFile

from django.db import DEFAULT_DB_ALIAS, connections
from django_tables2.export import TableExport, ExportMixin


def drop_table(table_name, using=DEFAULT_DB_ALIAS):
    connection = connections[DEFAULT_DB_ALIAS]
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS " + connection.ops.quote_name(table_name))


def create_temporary_table_as(table_name, queryset, using=DEFAULT_DB_ALIAS):
    compiler = queryset.query.get_compiler(using=using)
    sql, params = compiler.as_sql()
    connection = connections[DEFAULT_DB_ALIAS]
    sql = "CREATE TEMPORARY TABLE " + connection.ops.quote_name(table_name) + " AS " + sql
    drop_table(table_name, using=DEFAULT_DB_ALIAS)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


import openpyxl, openpyxl.styles


class MyTableExport(TableExport):
    """
    Fix https://github.com/jazzband/tablib/issues/252
    """

    def export(self):

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet 1"

        # Write the header row and make cells bold
        tablib_dataset = self.dataset

        ws.append(tablib_dataset.headers)
        for cell in ws[1:1]:
            cell.font = openpyxl.styles.Font(bold=True)

        for row in tablib_dataset:
            ws.append(row)

        for col in ws.columns:
            max_length = 0
            column = col[0].column  # Get the column name
            # Since Openpyxl 2.6, the column name is  ".column_letter" as .column became the column number (1-based)
            for cell in col:
                try:  # Necessary to avoid error on empty cells
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2
            ws.column_dimensions[column].width = adjusted_width

        with NamedTemporaryFile() as tmp:
            wb.save(tmp.name)
            tmp.seek(0)
            return tmp.read()


class MyExportMixin(ExportMixin):
    def create_export(self, export_format):
        exporter = MyTableExport(
            export_format=export_format,
            table=self.get_table(**self.get_table_kwargs()),
            exclude_columns=self.exclude_columns
        )

        return exporter.response(filename=self.get_export_filename(export_format))
