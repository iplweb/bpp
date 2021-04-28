import os

from django.conf import settings

PBN_CLIENT_DEFAULT_BASE_URL = "https://pbn-micro-alpha.opi.org.pl"


PBN_CLIENT_APP_ID = getattr(
    settings, "PBN_CLIENT_APP_ID", os.getenv("PBN_CLIENT_APP_ID")
)


PBN_CLIENT_APP_TOKEN = getattr(
    settings, "PBN_CLIENT_APP_TOKEN", os.getenv("PBN_CLIENT_APP_TOKEN")
)


PBN_CLIENT_BASE_URL = getattr(
    settings,
    "PBN_CLIENT_BASE_URL",
    os.getenv("PBN_CLIENT_BASE_URL", PBN_CLIENT_DEFAULT_BASE_URL),
)

PBN_CLIENT_USER_TOKEN = getattr(
    settings, "PBN_CLIENT_USER_TOKEN", os.getenv("PBN_CLIENT_USER_TOKEN")
)
