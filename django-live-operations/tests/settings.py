"""
Minimal Django settings for django-live-operations test suite.
"""

SECRET_KEY = "test-secret-key-not-for-production"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "channels",
    "channels_broadcast",
    "live_operations",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            # tests/templates/ — provides base.html for LIVE_OPERATIONS default
            str(__file__).replace("settings.py", "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    }
]

LIVE_OPERATIONS = {
    "BASE_TEMPLATE": "base.html",
    "RUNNER": "eager",
    "THROTTLE_HZ": 10,
}

# Required by channels
ASGI_APPLICATION = "live_operations.routing_placeholder"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
