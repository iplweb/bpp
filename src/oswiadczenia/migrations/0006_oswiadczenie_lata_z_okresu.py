"""Treść oświadczenia w DBTemplate: „za lata 2022-2025” wpisane na sztywno
zastąpione latami okresu ewaluacji, do którego należy praca
(filtr ``lata_ewaluacji``). Szablony zmienione przez uczelnię są poprawiane
tylko, jeśli nadal zawierają ten literał."""

from django.db import migrations

TEMPLATE_NAME = "oswiadczenia/tresc_jednego_oswiadczenia.html"
LOAD = "{% load oswiadczenia_tags %}"
STARY = "za lata <strong>2022-2025</strong>"
NOWY = "za lata <strong>{{ object.rok|lata_ewaluacji }}</strong>"


def _wyczysc_cache(t):
    """Model historyczny nie wysyła sygnałów dbtemplates — bez tego serwer
    serwowałby starą treść z cache (Redis) aż do jej wygaśnięcia."""
    from dbtemplates.utils.cache import cache, get_cache_key

    if not cache:
        return
    for site in t.sites.all():
        cache.delete(get_cache_key(t.name, site=site))


def forward(apps, schema_editor):
    Template = apps.get_model("dbtemplates", "Template")
    for t in Template.objects.filter(name=TEMPLATE_NAME):
        if STARY not in t.content:
            continue
        t.content = t.content.replace(STARY, NOWY)
        if LOAD not in t.content:
            t.content = LOAD + t.content
        t.save(update_fields=["content"])
        _wyczysc_cache(t)


def reverse(apps, schema_editor):
    Template = apps.get_model("dbtemplates", "Template")
    for t in Template.objects.filter(name=TEMPLATE_NAME):
        if NOWY not in t.content:
            continue
        t.content = t.content.replace(NOWY, STARY)
        if t.content.startswith(LOAD):
            t.content = t.content[len(LOAD) :]
        t.save(update_fields=["content"])
        _wyczysc_cache(t)


class Migration(migrations.Migration):
    dependencies = [
        ("oswiadczenia", "0005_migrate_template_to_dbtemplate"),
        ("dbtemplates", "__first__"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
