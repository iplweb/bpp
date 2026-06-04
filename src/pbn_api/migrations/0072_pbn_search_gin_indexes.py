# Funkcjonalne wyszukiwanie "odpowiednik w PBN": gin trgm upper() na kolumnach
# przeszukiwanych przez icontains/istartswith w autocomplete i admin search.
#
# CREATE INDEX CONCURRENTLY IF NOT EXISTS -> idempotentne i nieblokujace:
#  - scientist (lastName/name/orcid) i journal (title): juz istnialy RECZNIE na
#    produkcji (poza kodem) -> ta migracja formalizuje je (swiezy install tez je
#    dostanie; noop tam gdzie sa),
#  - institution (name/addressCity): przywraca indeksy bledne usuniete w #315
#    (idx_scan=0 mylilo - sa potrzebne do BitmapOr dla rzadkich terminow),
#  - publisher (publisherName), journal (websiteLink), publication (title/doi):
#    nowe - wczesniej te wyszukiwania robily Seq Scan.
#
# Dzieki temu kazda galaz OR autocomplete jest indeksowalna (gin dla nazw, PK/
# btree dla =mongoId/=mniswId/exact) -> Postgres robi BitmapOr zamiast Seq Scan.
from django.db import migrations

# (nazwa indeksu, tabela, wyrazenie kolumny)
GIN_INDEXES = [
    ("pbn_api_scienti_lastname_idx", "pbn_api_scientist", 'upper("lastName")'),
    ("pbn_api_scienti_name_idx", "pbn_api_scientist", "upper(name)"),
    ("pbn_api_scienti_orcid_idx", "pbn_api_scientist", "upper(orcid)"),
    ("pbn_api_journal_title_idx", "pbn_api_journal", "upper(title)"),
    ("pbn_api_journal_websitelink_trgm", "pbn_api_journal", 'upper("websiteLink")'),
    ("pbn_api_institu_name_idx", "pbn_api_institution", "upper(name)"),
    ("pbn_api_institu_addresscity_idx", "pbn_api_institution", 'upper("addressCity")'),
    (
        "pbn_api_publisher_publishername_trgm",
        "pbn_api_publisher",
        'upper("publisherName")',
    ),
    ("pbn_api_publication_title_trgm", "pbn_api_publication", "upper(title)"),
    ("pbn_api_publication_doi_trgm", "pbn_api_publication", "upper(doi)"),
]


def _create(name, table, expr):
    return (
        f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{name}" '
        f"ON {table} USING gin ({expr} gin_trgm_ops);"
    )


def _drop(name):
    return f'DROP INDEX CONCURRENTLY IF EXISTS "{name}";'


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("pbn_api", "0071_alter_institution_addresspostalcode_and_more"),
    ]

    operations = [
        migrations.RunSQL(_create(name, table, expr), _drop(name))
        for name, table, expr in GIN_INDEXES
    ]
