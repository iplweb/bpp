from .production import *

COMPRESS_OFFLINE = True

# host dla HTMLu oraz linii polecen, reszta dla linii polecen (bo HTML sie autokonfiguruje...)
NOTIFICATIONS_HOST = 'staging-bpp.local'
NOTIFICATIONS_PORT = None
NOTIFICATIONS_PROTOCOL = 'http'
