from django.db import DEFAULT_DB_ALIAS, connections


def create_temporary_table_as(table_name, queryset, using=DEFAULT_DB_ALIAS):
    compiler = queryset.query.get_compiler(using=using)
    sql, params = compiler.as_sql()
    connection = connections[DEFAULT_DB_ALIAS]
    sql = "CREATE TEMPORARY TABLE " + connection.ops.quote_name(table_name) + " AS " + sql
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
