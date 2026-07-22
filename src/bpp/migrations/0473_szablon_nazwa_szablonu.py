from django.db import migrations, models


def backfill_nazwa(apps, schema_editor):
    Szablon = apps.get_model("bpp", "SzablonDlaOpisuBibliograficznego")
    Template = apps.get_model("dbtemplates", "Template")
    for row in Szablon.objects.all():
        if row.template_id:
            row.nazwa_szablonu = Template.objects.get(pk=row.template_id).name
            row.save(update_fields=["nazwa_szablonu"])


def purge_opis_dbtemplate(apps, schema_editor):
    # Konkretne klasy modeli (denorm rebuild jak w drop_dbtemplate). Import w
    # ciele funkcji — bezpieczny w tym punkcie migracji.
    from bpp.dbtemplates_sync import usun_dbtemplate_i_przebuduj
    from bpp.models.patent import Patent
    from bpp.models.praca_doktorska import Praca_Doktorska
    from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
    from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
    from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

    modele = [
        Wydawnictwo_Ciagle,
        Wydawnictwo_Zwarte,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Patent,
    ]
    Szablon = apps.get_model("bpp", "SzablonDlaOpisuBibliograficznego")
    nazwy = {n for n in Szablon.objects.values_list("nazwa_szablonu", flat=True) if n}
    for name in sorted(nazwy):
        # guard (dysk) + log + delete + czyszczenie cache + oznaczenie dirty.
        # flush=False -> async kolejka denorm dokończy (migracja nieblokująca).
        usun_dbtemplate_i_przebuduj(name, modele, flush=False, log=print)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("bpp", "0472_constraint_autor_jednostka_bez_daty"),
        ("dbtemplates", "0002_alter_template_creation_date_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="szablondlaopisubibliograficznego",
            name="nazwa_szablonu",
            field=models.CharField(
                default="opis_bibliograficzny.html",
                help_text=(
                    "Nazwa szablonu Django ładowanego z dysku, "
                    "np. opis_bibliograficzny.html"
                ),
                max_length=255,
            ),
        ),
        migrations.RunPython(backfill_nazwa, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="szablondlaopisubibliograficznego",
            name="template",
        ),
        migrations.RunPython(purge_opis_dbtemplate, migrations.RunPython.noop),
    ]
