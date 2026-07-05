"""Faza B / issue #438 — II-2: przepięcie 3 FK-konsumentów (app ``bpp``)
``Wydzial``→``Jednostka``: ``Kierunek_Studiow.wydzial``,
``Patent.wydzial``, ``Opi_2012_Afiliacja_Do_Wydzialu.wydzial``.

(Pozostałe 2 FK — ``import_dyscyplin.Import_Dyscyplin_Row.wydzial`` i
``zglos_publikacje.Obslugujacy_Zgloszenia_Wydzialow.wydzial`` — mieszkają w
innych appkach; ich migracje zależą od tej.)

Three-step per FK (BŁĄD #2 z review kolejności migracji — inaczej
IntegrityError/pending-trigger): ``AlterField wydzial → IntegerField``
(zrzuca stary constraint FK→Wydzial, zachowuje wartości = stare
``Wydzial.id``; ``db_column="wydzial_id"`` zostaje — nie ma fizycznego
rename kolumny) → ``RunPython`` remap ``wydzial`` (stary Wydzial pk) →
``Jednostka(legacy_wydzial_id=old).pk`` (węzeł-lustro; zbudowany raz jako
mapa, bez N+1) → ``AlterField wydzial → ForeignKey("bpp.Jednostka", …)``.

UWAGA: na etapie IntegerField ORM-owa nazwa lookupu/atrybutu to ``wydzial``
(NIE ``wydzial_id``!) — ``db_column`` zmienia tylko fizyczną nazwę kolumny
SQL, a ``attname`` zwykłego pola to nazwa pola. ``_id`` w atrybucie dostają
tylko FK/O2O. Ten sam wzorzec co ``remap_wydzial_to_root`` w
``0459_faza_b_ii1_retarget.py`` (tam też ``wydzial=...``, nie
``wydzial_id=...``).

Polityka „unmappable" (brak węzła-lustra dla użytego ``Wydzial``) — per
``on_delete`` docelowego FK:
  - ``Kierunek_Studiow`` (PROTECT, pole NOT NULL) — **fail loud**: RunPython
    rzuca ``RuntimeError`` PRZED jakąkolwiek modyfikacją, jeśli istnieje
    choć jeden niemapowalny ``wydzial_id`` (nie ma jak go zastąpić — PROTECT
    znaczy "to musi wskazywać coś realnego").
  - ``Patent`` (SET_NULL, pole nullable) — ustaw ``NULL`` + log.
  - ``Opi_2012_Afiliacja_Do_Wydzialu`` (CASCADE, pole NOT NULL) — nie ma jak
    ustawić NULL, więc **skip**: usuń niemapowalne wiersze + log (to
    tymczasowa tabela pomocnicza z importu XLS — bezpieczne do skasowania
    wierszy bez sensownego FK).
"""

import django.db.models.deletion
from django.db import migrations, models


def _mapa_legacy_wydzial(apps):
    """``legacy_wydzial_id`` (stary ``Wydzial.id``) → pk węzła-lustra
    ``Jednostka``. Budowana raz na wywołanie RunPython (bez N+1)."""
    Jednostka = apps.get_model("bpp", "Jednostka")
    return dict(
        Jednostka.objects.filter(legacy_wydzial_id__isnull=False).values_list(
            "legacy_wydzial_id", "id"
        )
    )


def _bezpieczny_remap_wydzial(Model, mapa):
    """Przepnij kolumnę ``wydzial`` (stare pk ``Wydzial``) na pk węzłów-luster
    ODPORNIE na nakładanie się przestrzeni pk.

    Naiwne ``for old,new in mapa: filter(wydzial=old).update(wydzial=new)``
    nadpisuje TĘ SAMĄ kolumnę, po której selektuje: gdy ``new`` (pk lustra)
    równa się innemu, PÓŹNIEJ przetwarzanemu ``old`` (pk wydziału) — realne,
    gdy max(Wydzial.pk) > max(Jednostka.pk) i lustra wpadają w zakres pk
    wydziałów — wiersz przepięty wcześniej zostaje przepięty DRUGI raz (cicha
    korupcja FK). Zamrażamy pk-i docelowych wierszy PRZED jakimkolwiek update
    i aktualizujemy po pk (na to odporne)."""
    plan = {
        old_id: list(
            Model.objects.filter(wydzial=old_id).values_list("pk", flat=True)
        )
        for old_id in mapa
    }
    for old_id, new_id in mapa.items():
        Model.objects.filter(pk__in=plan[old_id]).update(wydzial=new_id)


def remap_kierunek_studiow_wydzial(apps, schema_editor):
    """PROTECT + pole NOT NULL: brak węzła-lustra → fail loud (raise)."""
    Kierunek_Studiow = apps.get_model("bpp", "Kierunek_Studiow")
    mapa = _mapa_legacy_wydzial(apps)

    uzyte = list(Kierunek_Studiow.objects.values_list("wydzial", flat=True).distinct())
    brakujace = sorted({w for w in uzyte if w is not None and w not in mapa})
    if brakujace:
        raise RuntimeError(
            "[0460] Kierunek_Studiow.wydzial (PROTECT): brak węzła-lustra "
            f"Jednostka dla wydzial_id w {brakujace} — migracja przerwana "
            "(fail-loud, nie da się cicho zamienić FK chronionego PROTECT)."
        )

    _bezpieczny_remap_wydzial(Kierunek_Studiow, mapa)


def remap_patent_wydzial(apps, schema_editor):
    """SET_NULL, pole nullable: brak węzła-lustra → NULL + log."""
    Patent = apps.get_model("bpp", "Patent")
    mapa = _mapa_legacy_wydzial(apps)

    uzyte = list(
        Patent.objects.filter(wydzial__isnull=False)
        .values_list("wydzial", flat=True)
        .distinct()
    )
    brakujace = sorted({w for w in uzyte if w not in mapa})
    if brakujace:
        print(
            f"[0460] Patent.wydzial: brak węzła-lustra dla wydzial_id w "
            f"{brakujace} — ustawiam NULL."
        )
        Patent.objects.filter(wydzial__in=brakujace).update(wydzial=None)

    _bezpieczny_remap_wydzial(Patent, mapa)


def remap_opi_2012_afiliacja_wydzial(apps, schema_editor):
    """CASCADE, pole NOT NULL: brak węzła-lustra → skip (delete wiersza) + log."""
    Opi_2012_Afiliacja_Do_Wydzialu = apps.get_model(
        "bpp", "Opi_2012_Afiliacja_Do_Wydzialu"
    )
    mapa = _mapa_legacy_wydzial(apps)

    uzyte = list(
        Opi_2012_Afiliacja_Do_Wydzialu.objects.values_list(
            "wydzial", flat=True
        ).distinct()
    )
    brakujace = sorted({w for w in uzyte if w not in mapa})
    if brakujace:
        usuniete, _ = Opi_2012_Afiliacja_Do_Wydzialu.objects.filter(
            wydzial__in=brakujace
        ).delete()
        print(
            "[0460] Opi_2012_Afiliacja_Do_Wydzialu.wydzial: brak węzła-lustra "
            f"dla wydzial_id w {brakujace} — usunięto {usuniete} wiersz(y)."
        )

    _bezpieczny_remap_wydzial(Opi_2012_Afiliacja_Do_Wydzialu, mapa)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0459_faza_b_ii1_retarget"),
    ]

    operations = [
        # --- Kierunek_Studiow.wydzial (PROTECT) ---
        migrations.AlterField(
            model_name="kierunek_studiow",
            name="wydzial",
            field=models.IntegerField(db_column="wydzial_id"),
        ),
        migrations.RunPython(remap_kierunek_studiow_wydzial, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="kierunek_studiow",
            name="wydzial",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="bpp.jednostka"
            ),
        ),
        # --- Patent.wydzial (SET_NULL) ---
        migrations.AlterField(
            model_name="patent",
            name="wydzial",
            field=models.IntegerField(blank=True, null=True, db_column="wydzial_id"),
        ),
        migrations.RunPython(remap_patent_wydzial, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="patent",
            name="wydzial",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="bpp.jednostka",
            ),
        ),
        # --- Opi_2012_Afiliacja_Do_Wydzialu.wydzial (CASCADE) ---
        migrations.AlterField(
            model_name="opi_2012_afiliacja_do_wydzialu",
            name="wydzial",
            field=models.IntegerField(db_column="wydzial_id"),
        ),
        migrations.RunPython(
            remap_opi_2012_afiliacja_wydzial, migrations.RunPython.noop
        ),
        migrations.AlterField(
            model_name="opi_2012_afiliacja_do_wydzialu",
            name="wydzial",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="bpp.jednostka"
            ),
        ),
    ]
