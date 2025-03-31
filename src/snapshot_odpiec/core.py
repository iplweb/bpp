from django.contrib.contenttypes.models import ContentType


def przypiecia_copy_from_database_queries(parent_obj):
    from snapshot_odpiec.models import WartoscSnapshotu

    from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

    snapshot_odpiec_wartoscsnapshotu = WartoscSnapshotu._meta.db_table

    for klass in Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor:
        content_type_id = ContentType.objects.get_for_model(klass).pk
        table_name = klass._meta.db_table

        query = f"""
        INSERT INTO
            {snapshot_odpiec_wartoscsnapshotu}
            (
                parent_id,
                content_type_id,
                object_id,
                przypieta
            )
        SELECT
            {parent_obj.pk}         AS parent_id,
            {content_type_id}       AS content_type_id,
            {table_name}.id         AS object_id,
            {table_name}.przypieta
        FROM
            {table_name}
        WHERE
            {table_name}.dyscyplina_naukowa_id IS NOT NULL
        """
        yield query


def przypiecia_apply_to_database_queries(parent_obj):
    from snapshot_odpiec.models import WartoscSnapshotu

    from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

    snapshot_odpiec_wartoscsnapshotu = WartoscSnapshotu._meta.db_table

    for klass in Wydawnictwo_Zwarte_Autor, Wydawnictwo_Ciagle_Autor:
        content_type_id = ContentType.objects.get_for_model(klass).pk
        table_name = klass._meta.db_table

        query = f"""
        UPDATE
            {table_name}
        SET
            przypieta = {snapshot_odpiec_wartoscsnapshotu}.przypieta
        FROM
            {snapshot_odpiec_wartoscsnapshotu}
        WHERE
            {snapshot_odpiec_wartoscsnapshotu}.parent_id = {parent_obj.pk}
            AND {snapshot_odpiec_wartoscsnapshotu}.content_type_id = {content_type_id}
            AND {snapshot_odpiec_wartoscsnapshotu}.object_id = {table_name}.id;
        """
        yield query
