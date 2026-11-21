"""Task 3c, krok 1/4: zwykły indeks na FK ``rekord`` w trzech ``*_Autor``.

Task 3c był pierwotnie JEDNĄ migracją (0511). Rozbity jest na cztery
(0511-0514), a każda ma ``atomic = False``. Powód:

- ``ADD CONSTRAINT ... EXCLUDE USING GIST`` bierze ``ACCESS EXCLUSIVE`` na
  tabeli (blokuje także ODCZYTY) i nie ma wariantu współbieżnego. W jednej
  transakcji WSZYSTKIE takie blokady — z trzech największych tabel through —
  wisiałyby aż do ``COMMIT``, czyli przez czas budowy wszystkich dziewięciu
  indeksów naraz. ``atomic = False`` sprawia, że każde ``ALTER TABLE``
  commituje się osobno i natychmiast oddaje blokadę.
- Rozbicie na pliki daje dodatkowo granulację odzyskiwania: przerwana
  migracja zostawia zapisane w ``django_migrations`` te kroki, które się
  udały.

KOLEJNOŚĆ jest dobrana tak, żeby NIE BYŁO OKNA bez ochrony unikalności:
najpierw wszystko, co DODAJE (0511 indeks FK, 0512 unique po typie,
0513 exclusion po kolejności), a dopiero na końcu (0514) to, co ZDEJMUJE
stare ``unique_together`` i legacy constraint z 0132. Przez chwilę
obowiązują oba komplety naraz — to bezpieczne, bo stare są ostrzejsze
(bezwarunkowe).

CENA ``atomic = False``: migracja przerwana w połowie NIE jest zapisana w
``django_migrations``, a część DDL już się wykonała — ponowny ``migrate``
wywali się na istniejącym obiekcie. Stąd rozbicie na małe kroki, każdy z
własnym wpisem.

Ten krok: przywrócenie zwykłego indeksu na FK ``rekord`` (``AlterField``
kasuje wcześniejsze ``db_index=False``). Dopóki ``unique_together`` dawało
PEŁNY (nie częściowy) indeks btree z ``rekord`` jako kolumną wiodącą,
``db_index=False`` na FK było uzasadnione — auto-indeks byłby redundantny.
Constrainty z 0512/0513 są CZĘŚCIOWE (``WHERE deleted_at IS NULL``), więc
nie pokrywają już zapytań po samym ``rekord`` bez tego predykatu: RI-check
Postgresa przy DELETE rodzica, kolektor kaskady Django (``_base_manager``,
bez filtra soft-delete) i ``global_objects``/``deleted_objects``
``.filter(rekord=…)``.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("bpp", "0510_soft_delete_autorzy_views"),
    ]

    operations = [
        migrations.AlterField(
            model_name="patent_autor",
            name="rekord",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="autorzy_set",
                to="bpp.patent",
            ),
        ),
        migrations.AlterField(
            model_name="wydawnictwo_ciagle_autor",
            name="rekord",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="autorzy_set",
                to="bpp.wydawnictwo_ciagle",
            ),
        ),
        migrations.AlterField(
            model_name="wydawnictwo_zwarte_autor",
            name="rekord",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="autorzy_set",
                to="bpp.wydawnictwo_zwarte",
            ),
        ),
    ]
