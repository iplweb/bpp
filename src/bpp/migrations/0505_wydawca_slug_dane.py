from django.db import migrations

MAX_LENGTH = 512


def wypelnij_slugi(apps, schema_editor):
    """Slug dla każdego istniejącego wydawcy (także aliasów).

    Deterministycznie: kolejność po pk, ta sama funkcja co ``AutoSlugField``
    (``slugify_wydawca`` — nigdy same cyfry), kolizje rozwiązane jak
    w autoslug: ``-2``, ``-3``, … z przycięciem bazy do ``max_length``."""
    from bpp.util.text import slugify_wydawca

    Wydawca = apps.get_model("bpp", "Wydawca")
    zajete = set()
    do_zapisu = []
    for wydawca in Wydawca.objects.order_by("pk").only("pk", "nazwa"):
        baza = slugify_wydawca(wydawca.nazwa)[:MAX_LENGTH] or "wydawca"
        slug = baza
        index = 1
        while slug in zajete:
            index += 1
            ogon = f"-{index}"
            slug = baza[: MAX_LENGTH - len(ogon)] + ogon
        zajete.add(slug)
        wydawca.slug = slug
        do_zapisu.append(wydawca)
    Wydawca.objects.bulk_update(do_zapisu, ["slug"], batch_size=500)


class Migration(migrations.Migration):
    """Krok 2/3: wypełnienie slugów istniejących wydawców."""

    dependencies = [
        ("bpp", "0504_wydawca_slug"),
    ]

    operations = [
        migrations.RunPython(wypelnij_slugi, migrations.RunPython.noop),
    ]
