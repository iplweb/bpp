from django.db import migrations


class Migration(migrations.Migration):
    # CREATE INDEX CONCURRENTLY nie może działać w bloku transakcji —
    # stąd atomic = False. CONCURRENTLY: tabela mat bywa duża, a zwykły
    # CREATE INDEX trzymałby write-lock na czas budowy (triggery cache
    # piszą do niej przy każdej edycji publikacji).
    atomic = False

    dependencies = [
        ("bpp", "0429_cache_trigger_v3"),
    ]

    operations = [
        migrations.RunSQL(
            # PracaViewBySlug (kanoniczny publiczny URL rekordu) robi
            # Rekord.objects.get(slug=...) — bez indeksu to Seq Scan
            # po całej, szerokiej tabeli przy każdym wejściu na stronę
            # rekordu. Kolumna slug istnieje od 0253, indeksu nigdy
            # nie było (audyt: spec-optymalizacje-wydajnosci-2026-06).
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS bpp_rekord_mat_slug_idx "
            "ON bpp_rekord_mat (slug)",
            "DROP INDEX CONCURRENTLY IF EXISTS bpp_rekord_mat_slug_idx",
        ),
    ]
