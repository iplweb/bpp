"""Demo state for the screenshots of docs/api/index.md and
docs/administrator/rest-api.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-api-index.py

- creates the superuser ``regis`` (the "REST API (/api/v1/)" fieldset of the
  Uczelnia admin form is shown to superusers only),
- generates one "raport slotów - uczelnia" owned by ``filippa`` (group
  "generowanie raportów"), so /api/v1/raport_slotow_uczelnia_wiersz/ has
  rows. The report runs synchronously here, so no Celery worker is needed.
"""

import io
from decimal import Decimal

from liveops.progress import TextProgress
from liveops.runner import task_run
from password_policies.models import PasswordHistory

from bpp.models import BppUser
from raport_slotow.models.uczelnia import RaportSlotowUczelnia

# --- superuser ----------------------------------------------------------------
admin, _ = BppUser.objects.get_or_create(
    username="regis",
    defaults=dict(
        email="regis@example.com", first_name="Regis", last_name="z Toussaint"
    ),
)
admin.set_password(admin.username)  # demo DB only: password == login
admin.is_staff = True
admin.is_superuser = True
admin.save()
if not PasswordHistory.objects.filter(user=admin).exists():
    PasswordHistory.objects.create(user=admin, password=admin.password)

# --- slot report owned by the "generowanie raportów" account ------------------
filippa = BppUser.objects.get(username="filippa")
RaportSlotowUczelnia.objects.filter(owner=filippa).delete()
raport = RaportSlotowUczelnia.objects.create(
    owner=filippa,
    od_roku=2022,
    do_roku=2025,
    akcja=RaportSlotowUczelnia.Akcje.SLOTY,
    slot=Decimal("1"),
)
# Run in this process: no Celery worker and no channel layer needed.
task_run(raport, TextProgress(raport, io.StringIO()))
raport.refresh_from_db()
print(
    "raport",
    raport.pk,
    "finished:",
    raport.finished_successfully,
    "rows:",
    raport.raportslotowuczelniawiersz_set.count(),
)
