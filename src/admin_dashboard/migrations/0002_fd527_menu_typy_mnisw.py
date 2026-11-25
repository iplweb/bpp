"""FD#527: kafel „najczęściej używane” — „Typy KBN” → „Typy MNiSW”.

Kliknięcia w menu zapisują etykietę pozycji w chwili kliknięcia, więc po
zmianie nazwy pozycji „Dane systemowe” → „Typy MNiSW” panel dalej pokazywał
dawną nazwę. Każde kliknięcie to osobny wiersz (bez liczników i bez
unikalności), a zestawienie grupuje je po etykiecie — wystarczy więc
ujednolicić etykietę, a dawne i nowe kliknięcia zliczą się razem.
"""

from django.db import migrations

ADRES = "/admin/bpp/typ_kbn/"
NOWA = "Typy MNiSW"


def naprzod(apps, schema_editor):
    MenuClick = apps.get_model("admin_dashboard", "MenuClick")
    MenuClick.objects.filter(menu_url=ADRES).exclude(menu_label=NOWA).update(
        menu_label=NOWA
    )


class Migration(migrations.Migration):
    dependencies = [
        ("admin_dashboard", "0001_initial"),
    ]

    # Wstecz nic: dawnej etykiety poszczególnych kliknięć nie da się odtworzyć,
    # a i tak wskazują ten sam adres.
    operations = [migrations.RunPython(naprzod, migrations.RunPython.noop)]
