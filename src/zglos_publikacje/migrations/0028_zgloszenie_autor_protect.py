"""Domknięcie fazy 04 soft-delete: czwarty dziedzic abstraktu też dostaje PROTECT.

Faza 04 przestawiła ``autor`` na ``PROTECT`` w klasie abstrakcyjnej
``BazaModeluOdpowiedzialnosciAutorow`` (``bpp/models/abstract/authors.py``),
ale migracja stanu ``bpp/0501`` objęła wyłącznie modele z aplikacji ``bpp``:
``Patent_Autor``, ``Praca_Doktorska``, ``Wydawnictwo_Ciagle_Autor``,
``Wydawnictwo_Zwarte_Autor``. Handoff fazy 04 mówił „dziedziczą 3 modele
``*_Autor``" — dziedziczy CZWARTY, ``Zgloszenie_Publikacji_Autor``, i mieszka
w innej aplikacji. ``makemigrations`` zgłasza takie rozjazdy per-aplikacja,
więc szukanie dziedziczących tylko w ``bpp/`` było niewystarczające.

Ochrona sama w sobie DZIAŁAŁA już wcześniej: ``on_delete`` jest regułą
kolektora Django, żyjącą w Pythonie, więc pole zachowywało się jak
``PROTECT`` od chwili zmiany abstraktu. Brakowało wyłącznie księgowości
stanu — i to ona wywracała ``makemigrations --check``.

MIGRACJA JEST STATE-ONLY, z tego samego powodu co ``bpp/0501``: ``on_delete``
nie ma odpowiednika w schemacie (Django nie emituje ``ON DELETE`` w DDL,
kaskadę realizuje w ``Collector``), więc autogenerowany ``AlterField``
wygenerowałby DROP + ADD CONSTRAINT — ``ACCESS EXCLUSIVE`` na czas walidacji
klucza obcego, koszt realny, korzyść zerowa, bo powstałby constraint
identyczny z istniejącym.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0502_autor_soft_delete"),
        ("zglos_publikacje", "0027_zgloszenie_zaimportowane"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="zgloszenie_publikacji_autor",
                    name="autor",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="bpp.autor",
                    ),
                ),
            ],
        ),
    ]
