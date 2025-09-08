import os

import django

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")

django.setup()
if __name__ == "__main__":
    import simplejson as json

    from ewaluacja_optymalizacja.utils import wszystkie_wersje_rekordow

    for elem in wszystkie_wersje_rekordow():
        print(json.dumps(elem))
        print("---")
