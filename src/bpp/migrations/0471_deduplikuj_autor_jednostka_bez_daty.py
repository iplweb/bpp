"""Deduplikacja powiazan autor-jednostka bez daty rozpoczecia (krok 1 z 2).

``Wydawnictwo_*_Autor.save()`` (``bpp/models/abstract/authors.py``) robilo
check-then-create na parze ``(autor, jednostka)``, a deklarowany
``unique_together = [("autor", "jednostka", "rozpoczal_prace")]`` tej pary nie
chronil: ``rozpoczal_prace`` jest w tej sciezce NULL-em, a NULL-e w indeksie
unikalnym PostgreSQL sa wzajemnie rozroznialne. Dwa rownolegle zapisy prac
tego samego autora w tej samej jednostce (import, masowa edycja) tworzyly
zduplikowane powiazania.

Zanim ``0472`` zalozy czesciowy ``UniqueConstraint``, trzeba zdeduplikowac to,
co juz jest w bazie — inaczej ``ALTER TABLE ... ADD CONSTRAINT`` sie wywali.

Zasada wyboru "ktorego zostawic": **najnizszy pk**. To wiersz utworzony jako
pierwszy, wiec istniejace FK z duzym prawdopodobienstwem wskazuja wlasnie na
niego (minimum przepiec), a wybor jest deterministyczny. Wiersze-duplikaty i
tak roznia sie co najwyzej polami opisowymi (funkcja, stanowisko, wymiar
etatu) — na produkcji obserwowane duplikaty byly identyczne co do pola.

Do ``Autor_Jednostka`` wskazuja dwa FK, oba ``on_delete=CASCADE``:

* ``import_pracownikow.ImportPracownikowRow.autor_jednostka`` (nullable),
* ``import_pracownikow.ImportPracownikowOdpiecie.autor_jednostka``.

Gdybysmy po prostu skasowali duplikaty, CASCADE zabralby ze soba wiersze
i odpiecia historycznych importow pracownikow (utrata sladu audytowego).
Dlatego najpierw **przepinamy** je na ocalaly wiersz, a dopiero potem
kasujemy duplikaty. Dla ``ImportPracownikowOdpiecie`` przepiecie moze
wytworzyc dwa odpiecia tego samego powiazania w obrebie jednego importu —
takie nadmiarowe wiersze zwijamy do jednego (OR na flagach
``zaznaczone``/``wykonane``, zeby nie zgubic decyzji operatora).

Same constrainty zaklada dopiero migracja ``0472``. To NIE jest kosmetyka:
``DELETE`` na tabelach z FK zostawia w PostgreSQL oczekujace (deferred)
zdarzenia wyzwalaczy, a ``ALTER TABLE ... ADD CONSTRAINT`` w tej samej
transakcji wywala sie wtedy na "nie mozna ALTER TABLE ... poniewaz posiada
oczekujace zdarzenia wyzwalaczy". Rozdzielenie na dwie migracje daje DDL
wlasna, czysta transakcje.
"""

import logging

from django.db import migrations, models

logger = logging.getLogger(__name__)


def _grupy_duplikatow(Autor_Jednostka):
    """Listy pk-ow (posortowane rosnaco) dla kazdej zduplikowanej pary."""
    duplikaty = (
        Autor_Jednostka.objects.filter(rozpoczal_prace=None)
        .values("autor_id", "jednostka_id")
        .annotate(ile=models.Count("pk"))
        .filter(ile__gt=1)
        .order_by()
    )
    return [
        list(
            Autor_Jednostka.objects.filter(
                rozpoczal_prace=None,
                autor_id=wpis["autor_id"],
                jednostka_id=wpis["jednostka_id"],
            )
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        for wpis in duplikaty
    ]


def _scal_odpiecia(ImportPracownikowOdpiecie, zostaje):
    """Zwija odpiecia tego samego powiazania w obrebie jednego importu.

    Przepiecie z duplikatow na ``zostaje`` moze dac kilka odpiec wskazujacych
    to samo powiazanie w tym samym imporcie. Zostawiamy najstarsze (najnizszy
    pk), sumujac flagi logicznym OR, zeby nie zgubic decyzji operatora.
    """
    nadmiarowe = (
        ImportPracownikowOdpiecie.objects.filter(autor_jednostka_id=zostaje)
        .values("parent_id")
        .annotate(ile=models.Count("pk"))
        .filter(ile__gt=1)
        .order_by()
    )
    for wpis in nadmiarowe:
        grupa = list(
            ImportPracownikowOdpiecie.objects.filter(
                autor_jednostka_id=zostaje, parent_id=wpis["parent_id"]
            ).order_by("pk")
        )
        glowne, reszta = grupa[0], grupa[1:]
        glowne.zaznaczone = any(o.zaznaczone for o in grupa)
        glowne.wykonane = any(o.wykonane for o in grupa)
        glowne.save(update_fields=["zaznaczone", "wykonane"])
        ImportPracownikowOdpiecie.objects.filter(
            pk__in=[o.pk for o in reszta]
        ).delete()


def deduplikuj(apps, schema_editor):
    Autor_Jednostka = apps.get_model("bpp", "Autor_Jednostka")
    ImportPracownikowRow = apps.get_model(
        "import_pracownikow", "ImportPracownikowRow"
    )
    ImportPracownikowOdpiecie = apps.get_model(
        "import_pracownikow", "ImportPracownikowOdpiecie"
    )

    usuniete = 0
    for pk_i in _grupy_duplikatow(Autor_Jednostka):
        zostaje, do_scalenia = pk_i[0], pk_i[1:]

        ImportPracownikowRow.objects.filter(
            autor_jednostka_id__in=do_scalenia
        ).update(autor_jednostka_id=zostaje)
        ImportPracownikowOdpiecie.objects.filter(
            autor_jednostka_id__in=do_scalenia
        ).update(autor_jednostka_id=zostaje)
        _scal_odpiecia(ImportPracownikowOdpiecie, zostaje)

        Autor_Jednostka.objects.filter(pk__in=do_scalenia).delete()
        usuniete += len(do_scalenia)
        logger.warning(
            "bpp.Autor_Jednostka: scalono %s duplikat(ow) w wiersz pk=%s",
            len(do_scalenia),
            zostaje,
        )

    logger.warning(
        "Deduplikacja powiazan autor-jednostka bez daty rozpoczecia "
        "zakonczona: usunieto %s zduplikowanych wierszy.",
        usuniete,
    )


def deduplikuj_wstecz(apps, schema_editor):
    """Deduplikacji sie nie cofa.

    Usuniete wiersze byly duplikatami powstalymi z bledu — ich odtworzenie nie
    jest ani mozliwe (nie mamy ich pk-ow), ani pozadane. Migracja wstecz
    zdejmuje tylko constraint (w ``0472``); dane pozostaja zdeduplikowane.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0470_indeksy_gin_i_funkcyjne"),
        # ImportPracownikowOdpiecie (FK do Autor_Jednostka) pojawia sie w 0014;
        # bez tej zaleznosci apps.get_model(...) w RunPython nie zobaczylby go.
        ("import_pracownikow", "0014_utworz_nowego_odpiecie"),
    ]

    operations = [
        migrations.RunPython(deduplikuj, deduplikuj_wstecz),
    ]
