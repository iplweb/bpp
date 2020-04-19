from tempfile import NamedTemporaryFile

import openpyxl
import openpyxl.styles
from django.db import DEFAULT_DB_ALIAS, connections
from django.utils.itercompat import is_iterable
from django_tables2.export import ExportMixin, TableExport
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.filters import AutoFilter
from openpyxl.worksheet.table import Table, TableStyleInfo, TableColumn, TableFormula


def drop_table(table_name, using=DEFAULT_DB_ALIAS):
    connection = connections[using]
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS " + connection.ops.quote_name(table_name))


def _create_table_as(table_name, queryset, using=DEFAULT_DB_ALIAS, temporary=True):
    compiler = queryset.query.get_compiler(using=using)
    sql, params = compiler.as_sql()
    connection = connections[using]
    crt = "CREATE TABLE "
    if temporary:
        crt = "CREATE TEMPORARY TABLE "
    sql = crt + connection.ops.quote_name(table_name) + " AS " + sql
    drop_table(table_name, using=using)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


def create_temporary_table_as(table_name, queryset, using=DEFAULT_DB_ALIAS):
    return _create_table_as(table_name, queryset, using=using, temporary=True)


def create_table_as(table_name, queryset, using=DEFAULT_DB_ALIAS):
    return _create_table_as(table_name, queryset, using=using, temporary=False)


def insert_into(table_name, queryset, using=DEFAULT_DB_ALIAS):
    compiler = queryset.query.get_compiler(using=using)
    sql, params = compiler.as_sql()
    connection = connections[using]
    sql = "INSERT INTO " + connection.ops.quote_name(table_name) + " " + sql
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


def clone_temporary_table(source_table, target_table, using=DEFAULT_DB_ALIAS):
    connection = connections[using]
    sql = (
        "CREATE TEMPORARY TABLE "
        + connection.ops.quote_name(target_table)
        + " AS SELECT * FROM "
        + connection.ops.quote_name(source_table)
    )
    drop_table(target_table, using=using)
    with connection.cursor() as cursor:
        cursor.execute(sql)


class MyTableExport(TableExport):
    """
    Fix https://github.com/jazzband/tablib/issues/252
    """

    def is_valid_format(self, export_format):
        if export_format != "xlsx":
            return False
        return True

    def __init__(
        self, export_format, table, exclude_columns=None, export_description=None
    ):
        super(MyTableExport, self).__init__(
            export_format=export_format, table=table, exclude_columns=exclude_columns
        )
        self.table = table
        self.export_description = export_description

    def export(self):

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet 1"

        table_name = "Table1"

        # Write the header row and make cells bold
        tablib_dataset = self.dataset

        if self.export_description:
            for elem in self.export_description:
                if is_iterable(elem):
                    ws.append(elem)
                    if len(elem) == 2:
                        ws[ws.max_row][0].font = openpyxl.styles.Font(bold=True)
                        ws[ws.max_row][0].alignment = openpyxl.styles.Alignment(
                            horizontal="right"
                        )
                        ws[ws.max_row][1].alignment = openpyxl.styles.Alignment(
                            horizontal="left"
                        )
                else:
                    ws.append([elem])

            ws.append([])

        ws.append(tablib_dataset.headers)

        table_columns = tuple(
            TableColumn(id=h, name=header)
            for h, header in enumerate(tablib_dataset.headers, start=1)
        )

        # Sumowana kolumna po stronie XLSX tworzona jest w taki sposób, że jeżeli jakakolwiek
        # kolumna tabeli ma footer, to jest tam wstawiana suma za pomocą funkcji =SUBTOTAL(9, ...)
        #
        # W przypadku gdyby to nie wystarczało w przyszłości, to do django_tables2.TableColumn
        # należałoby dopisać kod funkcji XLSa.
        #
        # Do tego, pierwsza kolumna (o indeksie zerowym) uzywana jest dla napisu "Suma"

        footer_row = []
        for no, elem in enumerate(self.table.columns):
            if no == 0:
                footer_row.append("Suma")
                total_column = table_columns[0]
                total_column.totalsRowLabel = footer_row[0]
                continue

            if elem.has_footer():
                count_column = table_columns[no]
                count_column.totalsRowFunction = "sum"
                footer_row.append(f"=SUBTOTAL(109,{table_name}[{elem.header}])")
                continue

            footer_row.append("")

        for cell in ws[ws.max_row : ws.max_row]:
            cell.font = openpyxl.styles.Font(bold=True)

        first_table_row = ws.max_row
        for row in tablib_dataset:
            ws.append(row)
        ws.append(footer_row)

        if tablib_dataset:
            max_column = ws.max_column
            max_column_letter = get_column_letter(max_column)
            max_row = ws.max_row

            style = TableStyleInfo(
                name="TableStyleMedium9",
                showFirstColumn=False,
                showLastColumn=False,
                showRowStripes=True,
                showColumnStripes=True,
            )
            tab = Table(
                displayName=table_name,
                ref=f"A{first_table_row}:{max_column_letter}{max_row }",
                autoFilter=AutoFilter(
                    ref=f"A{first_table_row}:{max_column_letter}{max_row - 1}"
                ),
                totalsRowShown=True,
                totalsRowCount=1,
                tableStyleInfo=style,
                tableColumns=table_columns,
            )

            ws.add_table(tab)

        max_width = 75
        for ncol, col in enumerate(ws.columns):
            max_length = 0
            column = col[0].column_letter  # Get the column name
            # Since Openpyxl 2.6, the column name is  ".column_letter" as .column became the column number (1-based)
            for cell in col:
                try:  # Necessary to avoid error on empty cells
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except (ValueError, TypeError):
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
            export_description=self.get_export_description(),
        )

        return exporter.response(filename=self.get_export_filename(export_format))
