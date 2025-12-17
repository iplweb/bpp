from django.db import migrations

# Template content embedded directly (for reproducibility)
TEMPLATE_CONTENT = """<h1>Oświadczenie upoważaniające podmiot do wykazania osiągnięć w ewaluacji jakości działalności naukowej</h1>
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
    wyższym i nauce (Dz. U. z 2021 r. poz. 478, z późn. zm.) upoważniam do wykazania na potrzeby
    ewaluacji jakości działalności naukowej za lata <strong>2022-2025</strong> moich, wymienionych w niniejszym
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

TEMPLATE_NAME = "oswiadczenia/tresc_jednego_oswiadczenia.html"
TEMPLATE_NAME_BAK = "oswiadczenia/tresc_jednego_oswiadczenia.html.bak"


def forward(apps, schema_editor):
    """Rename existing DBTemplate to .bak and create new one with file content"""
    Template = apps.get_model("dbtemplates", "Template")

    # If a DBTemplate with this name exists, rename it to .bak
    Template.objects.filter(name=TEMPLATE_NAME).update(name=TEMPLATE_NAME_BAK)

    # Create the new DBTemplate entry with file content
    Template.objects.create(
        name=TEMPLATE_NAME,
        content=TEMPLATE_CONTENT,
    )


def reverse(apps, schema_editor):
    """Delete new DBTemplate and restore the .bak one"""
    Template = apps.get_model("dbtemplates", "Template")

    # Delete the new DBTemplate entry
    Template.objects.filter(name=TEMPLATE_NAME).delete()

    # Restore the .bak DBTemplate back to original name
    Template.objects.filter(name=TEMPLATE_NAME_BAK).update(name=TEMPLATE_NAME)


class Migration(migrations.Migration):
    dependencies = [
        ("oswiadczenia", "0004_add_przypieta_filter"),
        ("dbtemplates", "__first__"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
