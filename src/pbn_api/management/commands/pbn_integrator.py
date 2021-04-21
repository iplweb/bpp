# -*- encoding: utf-8 -*-
from pbn_api.integrator import (
    integruj_autorow_z_uczelni,
    integruj_jezyki,
    integruj_kraje,
    integruj_publikacje,
    integruj_wydawcow,
    integruj_zrodla,
    pobierz_instytucje,
    pobierz_konferencje,
    pobierz_ludzi_z_uczelni,
    pobierz_prace_po_doi,
    pobierz_wydawcow,
    pobierz_zrodla,
)
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Uczelnia


class Command(PBNBaseCommand):
    def handle(self, app_id, app_token, base_url, *args, **options):
        client = self.get_client(app_id, app_token, base_url)

        pobierz_zrodla(client)
        pobierz_wydawcow(client)
        pobierz_konferencje(client)

        integruj_jezyki(client)
        integruj_kraje(client)

        pobierz_ludzi_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)
        pobierz_instytucje(client)
        pobierz_prace_po_doi(client)

        integruj_autorow_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)
        integruj_zrodla()
        integruj_wydawcow()
        integruj_publikacje()
