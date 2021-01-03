# -*- encoding: utf-8 -*-
from django.core.mail import mail_admins
from django.core.management import BaseCommand
from django.db import transaction

from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = "Wysyła testowego maila do administratorów (test ustawień serwera)"

    @transaction.atomic
    def handle(self, *args, **options):
        site = Site.objects.first()
        mail_admins(
            "Test ustawień serwera pocztowego",
            f"Jeżeli widzisz ten komunikat, oznacza to, że serwer BPP {site.name} jest w stanie poprawnie "
            "wysyłać pocztę do swoich użytkowników",
        )
