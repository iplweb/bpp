"""Szablon treści oświadczenia dla prac z okresu ewaluacji 2026–2030
(DBTemplate, edytowalny w panelu: Szablony). Treść jak dla 2022–2025, ale
z latami 2026-2030 i adnotacją „[stara podstawa prawna]” przy podstawie
prawnej — do uzupełnienia, gdy będzie obowiązujący tekst dla tego okresu.
Istniejący szablon o tej nazwie (np. dodany ręcznie przez uczelnię) zostaje
bez zmian."""

from django.db import migrations

TEMPLATE_NAME = "oswiadczenia/tresc_jednego_oswiadczenia_2026_2030.html"
#: Kopia treści z dnia migracji (migracja nie może zależeć od zmian pliku).
TEMPLATE_CONTENT = """{% load oswiadczenia_tags %}<h1>Oświadczenie upoważaniające podmiot do wykazania osiągnięć w ewaluacji jakości działalności naukowej</h1>
<hr>
<h2>{{ autor.nazwisko }} {{ autor.imiona }}</h2>
<p>ORCID: <strong>{{ autor.orcid }}</strong></p>
<p>Dyscypliny:</p>
<ul>
    <li>{{ dyscyplina_naukowa }}</li>
    {% if subdyscyplina_naukowa %}
        <li>{{ subdyscyplina_naukowa }}</li>
    {% endif %}
</ul>
<p>
    Ja, <strong>{{ autor.nazwisko }} {{ autor.imiona }}</strong>, zgodnie z art. 265 ust. 13 ustawy z dnia
    20 lipca 2018 r. – Prawo  o szkolnictwie
    wyższym i nauce (Dz. U. z 2021 r. poz. 478, z późn. zm.) [stara podstawa prawna] upoważniam do wykazania na potrzeby
    ewaluacji jakości działalności naukowej za lata <strong>2026-2030</strong> moich, wymienionych w niniejszym
    oświadczeniu osiągnięć przez <strong>{{ uczelnia.nazwa }}</strong> w dyscyplinie:
    <strong>{{ dyscyplina_pracy }}</strong>.
</p>
<p>
    Oświadczam, że osiągnięcia te powstały w związku z prowadzeniem przeze mnie działalności naukowej
    w tym podmiocie (nie dotyczy osiągnięć artystycznych).
</p>
<div width="10%" style="text-align: center; width:50%; float: right;">
    <p>{{ data_oswiadczenia|default:"" }}...........................................................</p>
    <p>(data i podpis)</p>
</div>
<div style="clear:both;"></div>
<strong>Dotyczy:</strong><br/>
{{ object.opis_bibliograficzny_cache|safe }}
"""


def forward(apps, schema_editor):
    Template = apps.get_model("dbtemplates", "Template")
    if Template.objects.filter(name=TEMPLATE_NAME).exists():
        return
    Template.objects.create(name=TEMPLATE_NAME, content=TEMPLATE_CONTENT)
    # Model historyczny nie wysyła sygnałów dbtemplates: usuń z cache
    # ewentualny wpis „brak szablonu” dla tej nazwy.
    from dbtemplates.utils.cache import cache, get_cache_notfound_key

    if cache:
        cache.delete(get_cache_notfound_key(TEMPLATE_NAME))


def reverse(apps, schema_editor):
    Template = apps.get_model("dbtemplates", "Template")
    Template.objects.filter(name=TEMPLATE_NAME, content=TEMPLATE_CONTENT).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("oswiadczenia", "0006_oswiadczenie_lata_z_okresu"),
        ("dbtemplates", "__first__"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
