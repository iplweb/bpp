"""Deduplikacja ``PublikacjaInstytucji`` (krok 1 z 2).

``zapisz_publikacje_instytucji`` robił ``get_or_create`` po trójce
(``institutionId``, ``publicationId``, ``insPersonId``), na której nie było
żadnego unikalnego constraintu. Import PBN biegnie wielowątkowo, więc dwa
wątki na tej samej trójce **cicho** tworzyły dwa wiersze — bez wyjątku, bez
logu. Duplikaty narastały z każdym importem.

Zanim założymy constraint, trzeba zdeduplikować to, co już jest w bazie
produkcyjnej — inaczej ``AddConstraint`` wywali migrację.

Zasada wyboru „którego zostawić": **najniższy pk** — wiersz utworzony jako
pierwszy, deterministycznie wybrany. Pola niekluczowe (``snapshot``,
``publicationYear`` itd.) nie mają znaczenia: najbliższy import PBN i tak
nadpisze ocalały wiersz świeżymi danymi z serwera.

**Nic nie ma FK do ``PublikacjaInstytucji``** (sprawdzone: model nie jest
celem żadnego ``ForeignKey``/``ManyToMany`` w repo — jest liściem grafu,
odwołuje się do ``Scientist``/``Institution``/``Publication``/``Uczelnia``,
ale nikt nie odwołuje się do niego). Nie ma więc czego przepinać ani czego
osierocić — kasujemy duplikaty wprost.

Sam constraint zakłada dopiero migracja ``0079``. To NIE jest kosmetyka:
``DELETE`` na tabeli z FK zostawia w PostgreSQL oczekujące (deferred)
zdarzenia wyzwalaczy, a ``ALTER TABLE ... ADD CONSTRAINT`` w tej samej
transakcji wywala się wtedy na ``nie można ALTER TABLE ... ponieważ posiada
oczekujące zdarzenia wyzwalaczy``. Rozdzielenie na dwie migracje daje DDL
własną, czystą transakcję. (Wzorzec: ``0076`` + ``0077``.)
"""

import logging

from django.db import migrations, models

logger = logging.getLogger(__name__)

POLA_KLUCZA = ("institutionId_id", "publicationId_id", "insPersonId_id")


def deduplikuj(apps, schema_editor):
    PublikacjaInstytucji = apps.get_model("pbn_api", "PublikacjaInstytucji")

    duplikaty = (
        PublikacjaInstytucji.objects.values(*POLA_KLUCZA)
        .annotate(ile=models.Count("pk"))
        .filter(ile__gt=1)
        .order_by()
    )

    usunietych = 0
    for wpis in duplikaty:
        klucz = {pole: wpis[pole] for pole in POLA_KLUCZA}
        pk_i = list(
            PublikacjaInstytucji.objects.filter(**klucz)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        zostaje, do_usuniecia = pk_i[0], pk_i[1:]
        PublikacjaInstytucji.objects.filter(pk__in=do_usuniecia).delete()
        usunietych += len(do_usuniecia)
        logger.warning(
            "pbn_api.PublikacjaInstytucji: usunięto %s duplikat(ów) trójki %s, "
            "zostaje wiersz pk=%s",
            len(do_usuniecia),
            klucz,
            zostaje,
        )

    logger.warning(
        "Deduplikacja pbn_api.PublikacjaInstytucji zakończona: usunięto %s "
        "zduplikowanych wierszy.",
        usunietych,
    )


def deduplikuj_wstecz(apps, schema_editor):
    """Deduplikacji się nie cofa.

    Usunięte wiersze były duplikatami powstałymi z błędu — ich odtworzenie nie
    jest ani możliwe (nie mamy ich pk-ów), ani pożądane. Migracja wstecz
    zdejmuje tylko constraint (w ``0079``); dane pozostają zdeduplikowane.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0077_constrainty_uuid_dyscyplin"),
    ]

    operations = [
        migrations.RunPython(deduplikuj, deduplikuj_wstecz),
    ]
