"""Rozdzielenie ``Autor.pokazuj`` na osobne flagi widoczności.

Stare ``pokazuj`` przechodzi do czterech flag (strona jednostki, ranking,
indeks, API) — nikt dziś ukryty nie staje się nigdzie widoczny.
``pokazuj_w_wyszukiwaniu`` i ``pokazuj_strone_autora`` startują jako True
(strona autora znów działa dla wszystkich; schowanie jej to świadoma decyzja
redakcji).
"""

from django.db import migrations, models

POLA_Z_POKAZUJ = (
    "pokazuj_na_stronie_jednostki",
    "pokazuj_w_rankingu",
    "pokazuj_w_indeksie",
    "pokazuj_w_api",
)


def przepisz_pokazuj(apps, schema_editor):
    Autor = apps.get_model("bpp", "Autor")
    Autor.objects.filter(pokazuj=False).update(**dict.fromkeys(POLA_Z_POKAZUJ, False))


def odtworz_pokazuj(apps, schema_editor):
    Autor = apps.get_model("bpp", "Autor")
    Autor.objects.update(pokazuj=True)
    Autor.objects.filter(
        pokazuj_na_stronie_jednostki=False, pokazuj_w_rankingu=False
    ).update(pokazuj=False)


def _pole(verbose_name, help_text):
    return models.BooleanField(verbose_name, default=True, help_text=help_text)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0499_autoreksporttask_zlecone_anonimowo"),
    ]

    operations = [
        migrations.AddField(
            model_name="autor",
            name="pokazuj_na_stronie_jednostki",
            field=_pole(
                "Pokazuj na stronie jednostki",
                "Pokazuj autora na liście autorów na stronach jednostek.",
            ),
        ),
        migrations.AddField(
            model_name="autor",
            name="pokazuj_w_rankingu",
            field=_pole("Pokazuj w rankingu", "Pokazuj autora w rankingu autorów."),
        ),
        migrations.AddField(
            model_name="autor",
            name="pokazuj_w_wyszukiwaniu",
            field=_pole(
                "Pokazuj w wyszukiwaniu",
                "Autor jest wyszukiwalny w publicznym wyszukiwaniu globalnym "
                "oraz w publicznych listach wyboru (autocomplete).",
            ),
        ),
        migrations.AddField(
            model_name="autor",
            name="pokazuj_w_indeksie",
            field=_pole(
                "Pokazuj w indeksie autorów",
                "Pokazuj autora na alfabetycznej liście autorów.",
            ),
        ),
        migrations.AddField(
            model_name="autor",
            name="pokazuj_w_api",
            field=_pole(
                "Pokazuj w API",
                "Udostępniaj dane autora przez API oraz eksport CERIF/OAI. "
                "Gdy odznaczone, API zwraca dla autora jedynie informację "
                "„dane ukryte”.",
            ),
        ),
        migrations.AddField(
            model_name="autor",
            name="pokazuj_strone_autora",
            field=_pole(
                "Pokazuj stronę autora",
                "Gdy odznaczone, publiczna strona autora nie istnieje (404), "
                "a jego nazwisko nie jest nigdzie linkowane. Wymaga wcześniejszego "
                "wyłączenia pokazywania w wyszukiwaniu i w indeksie.",
            ),
        ),
        migrations.RunPython(przepisz_pokazuj, odtworz_pokazuj),
    ]
