from django.db import DEFAULT_DB_ALIAS, connections


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
