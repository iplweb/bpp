from django_tables2 import Column


class DecimalColumn(Column):
    pass


class SummingColumn(Column):
    def render_footer(self, bound_column, table):
        return sum(bound_column.accessor.resolve(row) for row in table.data)
