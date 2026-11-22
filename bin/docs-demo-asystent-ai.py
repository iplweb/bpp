"""Demo state for the screenshots of docs/uzytkownik/asystent-ai.md.

Run on the Witcher demo DB (docs/deweloper/zrzuty-ekranu.md):

    uv run python src/manage.py shell < bin/docs-demo-asystent-ai.py

- creates the superuser ``regis`` (the "Serwer MCP dla asystentów AI (/mcp)"
  fieldset of the Uczelnia admin form; the scenario switches MCP off there
  for one screenshot and back on),
- makes sure MCP is switched on for the demo university, so the /mcp/ page
  shows the connection instructions.
"""

from password_policies.models import PasswordHistory

from bpp.models import BppUser, Uczelnia

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

for uczelnia in Uczelnia.objects.all():
    uczelnia.mcp_wlaczone = True
    uczelnia.save(update_fields=["mcp_wlaczone"])

print("asystent-ai demo ready:", list(Uczelnia.objects.values_list("skrot", flat=True)))
