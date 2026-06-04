# Usuniecie nieuzywanych indeksow na tabelach pbn_api_* (idx_scan=0 na produkcji).
# Indeksy hand-named, tworzone przez RunSQL (np. 0066) lub recznie na produkcji —
# poza stanem modeli Django (zaden model pbn_api nie ma Meta.indexes), wiec raw DROP
# nie powoduje driftu. CONCURRENTLY IF EXISTS = nieblokujace i idempotentne.
# Zachowane: PK, unique, oraz UZYWANE gin trgm upper() do autocomplete (idx_scan>0).
from django.db import migrations

# (nazwa, oryginalna definicja do odtworzenia w reverse)
INDEXES = [
    (
        "pbn_api_inst_addrcity_idx",
        'CREATE INDEX pbn_api_inst_addrcity_idx ON public.pbn_api_institution USING btree ("addressCity")',
    ),
    (
        "pbn_api_inst_addrnum_idx",
        'CREATE INDEX pbn_api_inst_addrnum_idx ON public.pbn_api_institution USING btree ("addressStreetNumber")',
    ),
    (
        "pbn_api_inst_addrpost_idx",
        'CREATE INDEX pbn_api_inst_addrpost_idx ON public.pbn_api_institution USING btree ("addressPostalCode")',
    ),
    (
        "pbn_api_inst_addrstr_idx",
        'CREATE INDEX pbn_api_inst_addrstr_idx ON public.pbn_api_institution USING btree ("addressStreet")',
    ),
    (
        "pbn_api_inst_name_idx",
        "CREATE INDEX pbn_api_inst_name_idx ON public.pbn_api_institution USING btree (name)",
    ),
    (
        "pbn_api_inst_polonuid_idx",
        'CREATE INDEX pbn_api_inst_polonuid_idx ON public.pbn_api_institution USING btree ("polonUid")',
    ),
    (
        "pbn_api_institu_addresscity_idx",
        'CREATE INDEX pbn_api_institu_addresscity_idx ON public.pbn_api_institution USING gin (upper("addressCity") gin_trgm_ops)',
    ),
    (
        "pbn_api_institu_addresspostalcode_idx",
        'CREATE INDEX pbn_api_institu_addresspostalcode_idx ON public.pbn_api_institution USING gin (upper("addressPostalCode") gin_trgm_ops)',
    ),
    (
        "pbn_api_institu_addressstreet_idx",
        'CREATE INDEX pbn_api_institu_addressstreet_idx ON public.pbn_api_institution USING gin (upper("addressStreet") gin_trgm_ops)',
    ),
    (
        "pbn_api_institu_mongoid_idx",
        'CREATE INDEX pbn_api_institu_mongoid_idx ON public.pbn_api_institution USING gin (upper(("mongoId")::text) gin_trgm_ops)',
    ),
    (
        "pbn_api_institu_name_idx",
        "CREATE INDEX pbn_api_institu_name_idx ON public.pbn_api_institution USING gin (upper(name) gin_trgm_ops)",
    ),
    (
        "pbn_api_institu_polonuid_idx",
        'CREATE INDEX pbn_api_institu_polonuid_idx ON public.pbn_api_institution USING gin (upper("polonUid") gin_trgm_ops)',
    ),
    (
        "pbn_api_jour_website_idx",
        'CREATE INDEX pbn_api_jour_website_idx ON public.pbn_api_journal USING btree ("websiteLink")',
    ),
    (
        "pbn_api_journal_eissn_idx",
        "CREATE INDEX pbn_api_journal_eissn_idx ON public.pbn_api_journal USING gin (upper(eissn) gin_trgm_ops)",
    ),
    (
        "pbn_api_journal_issn_idx",
        "CREATE INDEX pbn_api_journal_issn_idx ON public.pbn_api_journal USING gin (upper(issn) gin_trgm_ops)",
    ),
    (
        "pbn_api_journal_mniswid_idx",
        'CREATE INDEX pbn_api_journal_mniswid_idx ON public.pbn_api_journal USING gin (upper(("mniswId")::text) gin_trgm_ops)',
    ),
    (
        "pbn_api_journal_mongoid_idx",
        'CREATE INDEX pbn_api_journal_mongoid_idx ON public.pbn_api_journal USING gin (upper(("mongoId")::text) gin_trgm_ops)',
    ),
    (
        "pbn_api_pub_uri_idx",
        'CREATE INDEX pbn_api_pub_uri_idx ON public.pbn_api_publication USING btree ("publicUri")',
    ),
    (
        "pbn_api_publ_name_idx",
        'CREATE INDEX pbn_api_publ_name_idx ON public.pbn_api_publisher USING btree ("publisherName")',
    ),
    (
        "pbn_api_publish_mniswid_idx",
        'CREATE INDEX pbn_api_publish_mniswid_idx ON public.pbn_api_publisher USING gin (upper(("mniswId")::text) gin_trgm_ops)',
    ),
    (
        "pbn_api_publish_mongoid_idx",
        'CREATE INDEX pbn_api_publish_mongoid_idx ON public.pbn_api_publisher USING gin (upper(("mongoId")::text) gin_trgm_ops)',
    ),
    (
        "pbn_api_publish_publishername_idx",
        'CREATE INDEX pbn_api_publish_publishername_idx ON public.pbn_api_publisher USING gin (upper("publisherName") gin_trgm_ops)',
    ),
    (
        "pbn_api_sci_lastname_idx",
        'CREATE INDEX pbn_api_sci_lastname_idx ON public.pbn_api_scientist USING btree ("lastName")',
    ),
    (
        "pbn_api_sci_name_idx",
        "CREATE INDEX pbn_api_sci_name_idx ON public.pbn_api_scientist USING btree (name)",
    ),
    (
        "pbn_api_sci_orcid_idx",
        "CREATE INDEX pbn_api_sci_orcid_idx ON public.pbn_api_scientist USING btree (orcid)",
    ),
    (
        "pbn_api_sci_pbnid_idx",
        'CREATE INDEX pbn_api_sci_pbnid_idx ON public.pbn_api_scientist USING btree ("pbnId")',
    ),
    (
        "pbn_api_sci_qual_idx",
        "CREATE INDEX pbn_api_sci_qual_idx ON public.pbn_api_scientist USING btree (qualifications)",
    ),
    (
        "pbn_api_scienti_mongoid_idx",
        'CREATE INDEX pbn_api_scienti_mongoid_idx ON public.pbn_api_scientist USING gin (upper(("mongoId")::text) gin_trgm_ops)',
    ),
]


def _drop(name):
    return f'DROP INDEX CONCURRENTLY IF EXISTS "{name}";'


def _recreate(defsql):
    if not defsql:
        return "SELECT 1;"  # brak definicji (indeks tylko na prod) — reverse no-op
    return (
        defsql.replace("CREATE INDEX ", "CREATE INDEX CONCURRENTLY IF NOT EXISTS ", 1)
        + ";"
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("pbn_api", "0069_sentdata_api_url")]

    operations = [
        migrations.RunSQL(_drop(name), _recreate(defsql)) for name, defsql in INDEXES
    ]
