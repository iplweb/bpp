from django.db import migrations

#: Wariant szablonu opisu bibliograficznego, zainstalowany do dbtemplates
#: migracją 0295. Migracja 0473 sprzątała dbtemplates tylko dla nazw
#: wskazywanych przez SzablonDlaOpisuBibliograficznego.nazwa_szablonu;
#: ta nazwa nie była wskazywana (domyślną jest opis_bibliograficzny.html),
#: więc jej wiersz przetrwał jako sierota. Dopóki istnieje, loader
#: dbtemplates — stojący przed plikowym — serwuje treść z bazy i edycje
#: pliku w repozytorium nie mają żadnego efektu.
NAZWA = "browse/praca_tabela.html"


def purge_wariant_dbtemplate(apps, schema_editor):
    # Konkretne klasy modeli (denorm rebuild jak w 0473 i drop_dbtemplate).
    # Import w ciele funkcji — bezpieczny w tym punkcie migracji.
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

    # Guard dysk-existence + log + delete + czyszczenie cache + dirty.
    # flush=False → asynchroniczna kolejka denorm dokończy przeliczanie
    # (migracja nieblokująca, jak 0473).
    usun_dbtemplate_i_przebuduj(NAZWA, modele, flush=False, log=print)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("bpp", "0487_api_v1_przelaczniki"),
        ("dbtemplates", "0002_alter_template_creation_date_and_more"),
    ]

    operations = [
        migrations.RunPython(purge_wariant_dbtemplate, migrations.RunPython.noop),
    ]
