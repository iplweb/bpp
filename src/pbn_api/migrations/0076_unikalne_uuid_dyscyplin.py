"""Deduplikacja słowników/dyscyplin PBN (krok 1 z 2).

``PBNClient.download_disciplines`` robił ``update_or_create`` po polach, na
których nie było unikalnego constraintu. Dwa równoległe importy tworzyły
duplikat, a od tego momentu każdy kolejny ``update_or_create`` rzucał
``MultipleObjectsReturned`` — import dyscyplin blokował się nieodwracalnie.

Zanim założymy constraint, trzeba zdeduplikować to, co już jest w bazie
produkcyjnej — inaczej ``AddConstraint``/``AlterField`` wywali migrację.

Zasada wyboru „którego zostawić": **najniższy pk**. Uzasadnienie:

* to wiersz utworzony jako pierwszy, więc istniejące FK (``TlumaczDyscyplin``,
  ``Discipline.parent_group``) z dużym prawdopodobieństwem wskazują właśnie na
  niego → minimum przepięć i minimum zmian w danych,
* jest deterministyczny (``last_updated_on`` to ``auto_now``, więc przy
  duplikatach z tego samego przebiegu importu bywa identyczny co do
  mikrosekundy i nie rozstrzyga),
* wartości pól i tak nie mają znaczenia — najbliższy import PBN nadpisze
  ocalały wiersz świeżymi danymi ze słownika.

Same constrainty zakłada dopiero migracja ``0077``. To NIE jest kosmetyka:
``DELETE`` na tabelach z FK zostawia w PostgreSQL oczekujące (deferred)
zdarzenia wyzwalaczy, a ``ALTER TABLE ... ADD CONSTRAINT`` w tej samej
transakcji wywala się wtedy na ``nie można ALTER TABLE ... ponieważ posiada
oczekujące zdarzenia wyzwalaczy``. Rozdzielenie na dwie migracje daje DDL
własną, czystą transakcję.
"""

import logging

from django.db import migrations, models

logger = logging.getLogger(__name__)


def _grupy_duplikatow(model, pola):
    """Zwraca listę list pk-ów: po jednej liście na każdy zduplikowany klucz."""
    duplikaty = (
        model.objects.values(*pola)
        .annotate(ile=models.Count("pk"))
        .filter(ile__gt=1)
        .order_by()
    )
    return [
        list(
            model.objects.filter(**{pole: wpis[pole] for pole in pola})
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        for wpis in duplikaty
    ]


def deduplikuj(apps, schema_editor):
    DisciplineGroup = apps.get_model("pbn_api", "DisciplineGroup")
    Discipline = apps.get_model("pbn_api", "Discipline")
    TlumaczDyscyplin = apps.get_model("pbn_api", "TlumaczDyscyplin")

    # --- Krok 1: słowniki dyscyplin (unikalny sam ``uuid``) ---------------
    scalone_grupy = 0
    for pk_i in _grupy_duplikatow(DisciplineGroup, ["uuid"]):
        zostaje, do_scalenia = pk_i[0], pk_i[1:]
        Discipline.objects.filter(parent_group_id__in=do_scalenia).update(
            parent_group_id=zostaje
        )
        DisciplineGroup.objects.filter(pk__in=do_scalenia).delete()
        scalone_grupy += len(do_scalenia)
        logger.warning(
            "pbn_api.DisciplineGroup: scalono %s duplikat(ów) w wiersz pk=%s",
            len(do_scalenia),
            zostaje,
        )

    # --- Krok 2: dyscypliny (unikalna para słownik + uuid) ----------------
    # Krok 1 mógł dopiero co wygenerować nowe kolizje, przepinając dyscypliny
    # z kasowanych słowników na ocalały — dlatego liczymy je tutaj, PO nim.
    scalone_dyscypliny = 0
    for pk_i in _grupy_duplikatow(Discipline, ["parent_group_id", "uuid"]):
        zostaje, do_scalenia = pk_i[0], pk_i[1:]
        for pole in ("pbn_2017_2021", "pbn_2022_2023", "pbn_2024_now"):
            TlumaczDyscyplin.objects.filter(
                **{f"{pole}_id__in": do_scalenia}
            ).update(**{f"{pole}_id": zostaje})
        Discipline.objects.filter(pk__in=do_scalenia).delete()
        scalone_dyscypliny += len(do_scalenia)
        logger.warning(
            "pbn_api.Discipline: scalono %s duplikat(ów) w wiersz pk=%s",
            len(do_scalenia),
            zostaje,
        )

    logger.warning(
        "Deduplikacja PBN zakończona: usunięto %s zduplikowanych słowników "
        "i %s zduplikowanych dyscyplin.",
        scalone_grupy,
        scalone_dyscypliny,
    )


def deduplikuj_wstecz(apps, schema_editor):
    """Deduplikacji się nie cofa.

    Usunięte wiersze były duplikatami powstałymi z błędu — ich odtworzenie nie
    jest ani możliwe (nie mamy ich pk-ów), ani pożądane. Migracja wstecz zdejmuje
    tylko constrainty (w ``0077``); dane pozostają zdeduplikowane.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("pbn_api", "0075_sentdata_fee_sent_sentdata_fee_uploaded_okay"),
    ]

    operations = [
        migrations.RunPython(deduplikuj, deduplikuj_wstecz),
    ]
