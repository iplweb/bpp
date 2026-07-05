from django.db import migrations, models


def ensure_uczelnia_site_not_null(apps, schema_editor):
    """Zagwarantuj, że każda Uczelnia ma przypisany Site przed AlterField NOT NULL.

    Dla typowego deploymentu single-tenant (1 Uczelnia, 1 Site) to no-op po
    migracji 0412_link_uczelnia_to_site, ale są scenariusze, których 0412
    nie pokrywa (silently skip):

    - Brak Site w bazie → utwórz domyślny Site i przypisz osamotnionej Uczelni.
    - Dokładnie 1 Uczelnia bez Site i 1 Site → przypisz.
    - Wieloznaczne (>1 Uczelnia bez Site lub >1 Site z niejasnym mapowaniem) →
      raise z czytelną instrukcją; admin musi przypisać ręcznie przed migracją.
    """
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    Site = apps.get_model("sites", "Site")

    bez_site = list(Uczelnia.objects.filter(site__isnull=True))
    if not bez_site:
        return

    sites = list(Site.objects.all())

    if len(bez_site) == 1:
        if len(sites) == 0:
            site = Site.objects.create(domain="example.com", name="example.com")
        elif len(sites) == 1:
            site = sites[0]
        else:
            raise RuntimeError(
                "Migracja bpp.0417: nie mogę jednoznacznie przypisać Site do "
                f"Uczelni '{bez_site[0].nazwa}' (pk={bez_site[0].pk}). "
                f"W bazie istnieje {len(sites)} obiektów Site. Przypisz Site "
                "ręcznie (np. w Django shell: "
                "`u = Uczelnia.objects.get(pk=...); u.site_id = <SITE_PK>; "
                "u.save()`) i ponownie uruchom migrate."
            )

        u = bez_site[0]
        u.site = site
        u.save(update_fields=["site"])
        return

    raise RuntimeError(
        "Migracja bpp.0417: znaleziono więcej niż jedną Uczelnię bez "
        "przypisanego Site:\n"
        + "\n".join(f"  - pk={u.pk} nazwa={u.nazwa!r}" for u in bez_site)
        + "\nPrzypisz Site dla każdej Uczelni ręcznie przed uruchomieniem "
        "migrate (Django shell albo Django admin)."
    )


def reverse_noop(apps, schema_editor):
    """Forward-only: nie cofamy linkowania."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0416_merge_20260428_1806"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(ensure_uczelnia_site_not_null, reverse_noop),
        migrations.AlterField(
            model_name="uczelnia",
            name="site",
            field=models.OneToOneField(
                help_text=(
                    "Powiązanie z obiektem Site (domena internetowa tej uczelni)."
                ),
                on_delete=models.PROTECT,
                related_name="uczelnia",
                to="sites.site",
                verbose_name="Strona (domena)",
            ),
        ),
    ]
