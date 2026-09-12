"""Task 3c, krok 2/4: warunkowy ``UniqueConstraint`` (rekord, autor, typ).

Rozbicie migracji i ``atomic = False`` — patrz docstring 0490.

``unique_together`` widziałby też wiersze soft-deleted (fizycznie wciąż są w
tabeli) i blokowałby wzorzec „skasuj i wstaw od nowa" (re-import, korekta
kolejności, edycja inline). Warunkowy ``UniqueConstraint``
(``condition=deleted_at__isnull``) pilnuje unikalności TYLKO wśród żywych
wierszy. Stare ``unique_together`` zdejmuje dopiero 0493 — tu jeszcze
obowiązuje, więc nie ma okna bez ochrony.

Drugiej pary z ``unique_together`` — ``(rekord, autor, kolejnosc)`` — NIE
odtwarzamy: ``ExclusionConstraint`` po ``(rekord, kolejnosc)`` z 0492 jest
ściśle silniejszy (nie patrzy na autora), więc taki unique byłby w 100%
redundantny — trzeci indeks do zbudowania w oknie serwisowym i stały narzut
na najgorętszej ścieżce zapisu.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("bpp", "0490_autor_indeks_fk_rekord"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="patent_autor",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("rekord", "autor", "typ_odpowiedzialnosci"),
                name="pat_autor_uniq_rekord_autor_typ",
            ),
        ),
        migrations.AddConstraint(
            model_name="wydawnictwo_ciagle_autor",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("rekord", "autor", "typ_odpowiedzialnosci"),
                name="wc_autor_uniq_rekord_autor_typ",
            ),
        ),
        migrations.AddConstraint(
            model_name="wydawnictwo_zwarte_autor",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("rekord", "autor", "typ_odpowiedzialnosci"),
                name="wz_autor_uniq_rekord_autor_typ",
            ),
        ),
    ]
