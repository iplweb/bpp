"""Co najwyżej jeden `StatusGenerowania` z `uczelnia IS NULL` (krok 2 z 2).

Deduplikacja jest w `0010` — osobna migracja, bo `DELETE` na tabelach z FK
zostawia w PostgreSQL oczekujące zdarzenia wyzwalaczy i `ALTER TABLE ... ADD
CONSTRAINT` w tej samej transakcji się wywala.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    # Bez krawędzi do `bpp` — autodetektor dopisywał tu czoło grafu `bpp`
    # (0470), ale constraint dotyczy wyłącznie kolumny `uczelnia_id` w tabeli
    # `ewaluacja_metryki_statusgenerowania`. Ta kolumna i FK do `bpp.Uczelnia`
    # powstają w 0007, które zależy od `("bpp", "0428_cpd_uczelnia_not_null")`;
    # ta krawędź jest tu dziedziczona łańcuchem 0010 → 0009 → 0008 → 0007.
    dependencies = [
        ("ewaluacja_metryki", "0010_dedup_statusgenerowania_bez_uczelni"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="statusgenerowania",
            constraint=models.UniqueConstraint(
                models.ExpressionWrapper(
                    models.Q(("uczelnia__isnull", True)),
                    output_field=models.BooleanField(),
                ),
                condition=models.Q(("uczelnia__isnull", True)),
                name="ewaluacja_metryki_status_jeden_wiersz_bez_uczelni",
            ),
        ),
    ]
