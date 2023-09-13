DELETED = "DELETED"
ACTIVE = "ACTIVE"

PBN_POST_PUBLICATIONS_URL = "/api/v1/publications"

PBN_POST_PUBLICATION_FEE_URL = "/api/v1/institutionProfile/publications/fees/{id}"

PBN_GET_LANGUAGES_URL = "/api/v1/dictionary/languages"
PBN_SEARCH_PUBLICATIONS_URL = "/api/v1/search/publications"

PBN_GET_JOURNAL_BY_ID = "/api/v1/journals/{id}"

DEFAULT_BASE_URL = "https://pbn-micro-alpha.opi.org.pl"

NEEDS_PBN_AUTH_MSG = (
    "W celu poprawnej autentykacji należy podać poprawny token użytkownika aplikacji."
)
PBN_DELETE_PUBLICATION_STATEMENT = (
    "/api/v1/institutionProfile/publications/{publicationId}"
)
PBN_GET_PUBLICATION_BY_ID_URL = "/api/v1/publications/id/{id}"

PBN_GET_INSTITUTION_STATEMENTS = (
    "/api/v1/institutionProfile/publications/page/statements"
)

PBN_GET_DISCIPLINES_URL = "/api/v2/dictionary/disciplines"
