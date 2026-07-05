"""Faza B / issue #438 — IV-1 (migracja 0462): jednorazowe przeliczenie
``Jednostka.aktualna`` z historii + ODKRYCIE (un-hide) węzłów-wydziałów +
zmiana default ``aktualna`` False→True.

Domyka F2 (atomowość releasu): PO tej migracji skonwertowane węzły-wydziały
stają się widoczne na zmigrowanej produkcji (wg źródłowego ``Wydzial.widoczny``).

Kroki:
  1. ``przelicz_aktualna`` — FINALNA logika (zduplikowana INLINE, bo migracje
     operują na modelach historycznych i NIE mogą wołać komendy). Musi dawać
     identyczny wynik co ``bpp.models.jednostka.przelicz_aktualna_wszystkich``.
     Idempotentne.
  2. ``odkryj_widoczna`` — dla węzłów ``legacy_wydzial_id IS NOT NULL`` ustaw
     ``widoczna = Wydzial.widoczny`` źródłowego wydziału.
  3. ``AlterField`` ``aktualna`` default False→True (state+schema; model już
     ma default=True).
  4. ``invalidate_cache`` — bulk ``.update()`` omija sygnał
     ``invalidate_uczelnia_cache_on_jednostka_change``, więc czyścimy raz.
"""

from datetime import date

from django.db import migrations, models
from django.db.models.functions import Coalesce


def przelicz_aktualna(apps, schema_editor):
    """Jednorazowe przeliczenie ``aktualna`` wg finalnej logiki. Logika
    zduplikowana z ``bpp.models.jednostka.wylicz_aktualna`` /
    ``przelicz_aktualna_wszystkich`` (modele historyczne → bez importu)."""
    Jednostka = apps.get_model("bpp", "Jednostka")
    Jednostka_Rodzic = apps.get_model("bpp", "Jednostka_Rodzic")

    # Najświeższy wpis (max coalesce(od, 0001-01-01)) per jednostka, jednym
    # DISTINCT ON — brak jednostki w mapie ⇒ brak wpisów.
    najswiezsze = dict(
        Jednostka_Rodzic.objects.annotate(_od=Coalesce("od", date(1, 1, 1)))
        .order_by("jednostka_id", "-_od")
        .distinct("jednostka_id")
        .values_list("jednostka_id", "do")
    )
    dzis = date.today()

    aktualne, nieaktualne = [], []
    for pk, override in Jednostka.objects.values_list("pk", "aktualna_override"):
        if override is not None:
            val = override
        elif pk not in najswiezsze:
            val = True  # brak wpisów → True (finalna logika, RÓŻNI się od interim)
        else:
            do = najswiezsze[pk]
            val = (do if do is not None else date(9999, 12, 31)) > dzis
        (aktualne if val else nieaktualne).append(pk)

    Jednostka.objects.filter(pk__in=aktualne).exclude(aktualna=True).update(
        aktualna=True
    )
    Jednostka.objects.filter(pk__in=nieaktualne).exclude(aktualna=False).update(
        aktualna=False
    )


def odkryj_widoczna(apps, schema_editor):
    """F2: węzły-wydziały (``legacy_wydzial_id IS NOT NULL``) dziedziczą
    widoczność ze źródłowego ``Wydzial.widoczny`` — widoczne wydziały →
    widoczne węzły, ukryte → ukryte."""
    Jednostka = apps.get_model("bpp", "Jednostka")
    Wydzial = apps.get_model("bpp", "Wydzial")

    widoczny = dict(Wydzial.objects.values_list("pk", "widoczny"))
    widoczne = [pk for pk, w in widoczny.items() if w]
    ukryte = [pk for pk, w in widoczny.items() if not w]

    Jednostka.objects.filter(legacy_wydzial_id__in=widoczne).update(widoczna=True)
    Jednostka.objects.filter(legacy_wydzial_id__in=ukryte).update(widoczna=False)


def ukryj_widoczna(apps, schema_editor):
    """Reverse: przywróć węzły-wydziały do stanu ukrytego (jak przy konwersji
    — ``struktura_konwersja`` / migracja ``0455`` tworzyły je ``widoczna=False``)."""
    Jednostka = apps.get_model("bpp", "Jednostka")
    Jednostka.objects.filter(legacy_wydzial_id__isnull=False).update(widoczna=False)


def invalidate_cache(apps, schema_editor):
    """Bulk ``.update()`` omija sygnał invalidujący cache strony głównej —
    czyścimy go raz (spójnie z ``invalidate_uczelnia_cache_on_jednostka_change``)."""
    from bpp.views.browse import get_uczelnia_context_data

    get_uczelnia_context_data.invalidate()


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0461_faza_b_iii1_usun_rodzaj_jednostki"),
    ]

    operations = [
        migrations.RunPython(przelicz_aktualna, migrations.RunPython.noop),
        migrations.RunPython(odkryj_widoczna, ukryj_widoczna),
        migrations.AlterField(
            model_name="jednostka",
            name="aktualna",
            field=models.BooleanField(
                default=True,
                help_text="""Jeżeli dana jednostka wchodzi w struktury wydziału
    (czyli jej obecność w strukturach wydziału nie została zakończona z określoną datą), to pole to będzie miało
    wartość 'PRAWDA'.""",
            ),
        ),
        migrations.RunPython(invalidate_cache, migrations.RunPython.noop),
    ]
