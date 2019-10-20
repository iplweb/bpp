from tempfile import NamedTemporaryFile

from django.db import DEFAULT_DB_ALIAS, connections
from django.utils.itercompat import is_iterable
from django_tables2.export import TableExport, ExportMixin
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


def drop_table(table_name, using=DEFAULT_DB_ALIAS):
    connection = connections[using]
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS " + connection.ops.quote_name(table_name))


def create_temporary_table_as(table_name, queryset, using=DEFAULT_DB_ALIAS):
    compiler = queryset.query.get_compiler(using=using)
    sql, params = compiler.as_sql()
    connection = connections[using]
    sql = "CREATE TEMPORARY TABLE " + connection.ops.quote_name(table_name) + " AS " + sql
    drop_table(table_name, using=using)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


def insert_into(table_name, queryset, using=DEFAULT_DB_ALIAS):
    compiler = queryset.query.get_compiler(using=using)
    sql, params = compiler.as_sql()
    connection = connections[using]
    sql = "INSERT INTO " + connection.ops.quote_name(table_name) + " " + sql
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


def clone_temporary_table(source_table, target_table, using=DEFAULT_DB_ALIAS):
    connection = connections[using]
    sql = "CREATE TEMPORARY TABLE " + connection.ops.quote_name(
        target_table) + " AS SELECT * FROM " + connection.ops.quote_name(source_table)
    drop_table(target_table, using=using)
    with connection.cursor() as cursor:
        cursor.execute(sql)


import openpyxl, openpyxl.styles


class MyTableExport(TableExport):
    """
    Fix https://github.com/jazzband/tablib/issues/252
    """

    def is_valid_format(self, export_format):
        if export_format != 'xlsx':
            return False
        return True

    def __init__(self, export_format, table, exclude_columns=None, export_description=None):
        super(MyTableExport, self).__init__(export_format=export_format, table=table, exclude_columns=exclude_columns)
        self.export_description = export_description

    def export(self):

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet 1"

        # Write the header row and make cells bold
        tablib_dataset = self.dataset

        if self.export_description:
            for elem in self.export_description:
                if is_iterable(elem):
                    ws.append(elem)
                    if len(elem) == 2:
                        ws[ws.max_row][0].font = openpyxl.styles.Font(bold=True)
                        ws[ws.max_row][0].alignment = openpyxl.styles.Alignment(horizontal='right')
                        ws[ws.max_row][1].alignment = openpyxl.styles.Alignment(horizontal='left')
                else:
                    ws.append([elem])

            ws.append([])

        ws.append(tablib_dataset.headers)
        for cell in ws[ws.max_row:ws.max_row]:
            cell.font = openpyxl.styles.Font(bold=True)

        first_table_row = ws.max_row
        for row in tablib_dataset:
            ws.append(row)
        last_table_row = ws.max_row

        literka = get_column_letter(len(row))
        tab = Table(displayName="Table1", ref="A%i:%s%i" % (first_table_row, literka, last_table_row))
        style = TableStyleInfo(name="TableStyleMedium9", showFirstColumn=False,
                               showLastColumn=False, showRowStripes=True, showColumnStripes=True)
        tab.tableStyleInfo = style
        ws.add_table(tab)

        max_width = 75
        for ncol, col in enumerate(ws.columns):
            max_length = 0
            column = col[0].column  # Get the column name
            # Since Openpyxl 2.6, the column name is  ".column_letter" as .column became the column number (1-based)
            for cell in col:
                try:  # Necessary to avoid error on empty cells
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.1
            if adjusted_width > max_width:
                adjusted_width = max_width
            ws.column_dimensions[column].width = adjusted_width

        with NamedTemporaryFile() as tmp:
            wb.save(tmp.name)
            tmp.seek(0)
            return tmp.read()


class MyExportMixin(ExportMixin):
    def get_export_description(self):
        """Nadpisz tą funkcję, aby wygenerować pola opisowe na potrzeby XLS, np.
        'metkę' z parametrami raportu. Powinna zwrócić listę ciągów znaków, które zostaną
        wstawione przed tabelę, jeden pod drugim. """
        return

    def create_export(self, export_format):
        exporter = MyTableExport(
            export_format=export_format,
            table=self.get_table(**self.get_table_kwargs()),
            exclude_columns=self.exclude_columns,
            export_description=self.get_export_description()
        )

        return exporter.response(filename=self.get_export_filename(export_format))
