# -*- encoding: utf-8 -*-

from __future__ import print_function
from django.contrib.auth.models import Group

from django.core.management import BaseCommand
from django.db import transaction
from bpp.management.post_syncdb import bpp_post_syncdb
from bpp.models.profile import BppUser


class Command(BaseCommand):
    help = 'Tworzy grupy i uprawnienia dla serwisu - uruchamiaj po zmianach'

    @transaction.commit_on_success
    def handle(self, *args, **options):
        # Najpierw pobierz dane o grupach dla wszystkich użytkowników
        grp_dict = {}
        for u in BppUser.objects.all():
            grp_dict[u] = [grp.name for grp in u.groups.all()]

        bpp_post_syncdb(force=True)

        for u, grps in grp_dict.items():
            for gname in grps:
                u.groups.add(Group.objects.get(name=gname))


