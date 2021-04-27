# -*- encoding: utf-8 -*-
from pbn_api.exceptions import IntegracjaWylaczonaException
from pbn_api.integrator import (
    integruj_autorow_z_uczelni,
    integruj_instytucje,
    integruj_jezyki,
    integruj_kraje,
    integruj_publikacje,
    integruj_uczelnie,
    integruj_wydawcow,
    integruj_zrodla,
    pobierz_instytucje,
    pobierz_konferencje,
    pobierz_prace_po_doi,
    pobierz_wydawcow,
    pobierz_zrodla,
)
from pbn_api.management.commands.util import PBNBaseCommand

from bpp.models import Uczelnia


class Command(PBNBaseCommand):
    def handle(self, app_id, app_token, base_url, user_token, *args, **options):
        uczelnia = Uczelnia.objects.get_default()
        if uczelnia is not None:
            if not uczelnia.pbn_integracja:
                raise IntegracjaWylaczonaException()
        client = self.get_client(app_id, app_token, base_url, user_token)

        integruj_jezyki(client)

        pobierz_zrodla(client)
        integruj_zrodla()

        # pobierz_ludzi_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)
        # pobierz_ludzi robi to samo co integruj_autorow_z_uczelni
        integruj_autorow_z_uczelni(client, Uczelnia.objects.default.pbn_uid_id)

        integruj_kraje(client)

        pobierz_wydawcow(client)
        integruj_wydawcow()

        pobierz_konferencje(client)

        pobierz_instytucje(client)
        integruj_uczelnie()
        integruj_instytucje()

        pobierz_prace_po_doi(client)
        # pobierz_prace(client)
        integruj_publikacje()
