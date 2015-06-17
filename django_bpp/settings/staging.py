from .production import *

COMPRESS_OFFLINE = True

# host dla HTMLu oraz linii polecen, reszta dla linii polecen (bo HTML sie autokonfiguruje...)
NOTIFICATIONS_HOST = 'staging-bpp.local'
NOTIFICATIONS_PORT = None
NOTIFICATIONS_PROTOCOL = 'http'

TEMPLATE_LOADERS = (
    ('django.template.loaders.cached.Loader', (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )),
)

HTML_MINIFY = True