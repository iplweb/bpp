from django.views import View

from .mixins import EwaluacjaRequiredMixin


class PrzypnijDyscyplineView(EwaluacjaRequiredMixin, View):
    """Handle pinning a discipline for an author in a publication"""

    def post(self, request, content_type_id, object_id, autor_id, dyscyplina_id):
        from django.db import transaction
        from django.shortcuts import redirect

        from bpp.models.cache import Rekord
        from bpp.models.sloty.core import IPunktacjaCacher
        from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji

        with transaction.atomic():
            # Get the Rekord using tuple primary key
            try:
                rekord = Rekord.objects.get(pk=[content_type_id, object_id])
            except Rekord.DoesNotExist:
                raise Exception("Nie znaleziono rekordu publikacji") from None

            # Get the original publication and find the author assignment
            publikacja = rekord.original
            try:
                wa = publikacja.autorzy_set.get(
                    autor_id=autor_id, dyscyplina_naukowa_id=dyscyplina_id
                )
            except publikacja.autorzy_set.model.DoesNotExist:
                raise Exception(
                    "Nie znaleziono przypisania autora do publikacji"
                ) from None

            # Update przypieta status
            wa.przypieta = True
            wa.save()

            # Get FRESH publication instance without cached properties or related managers
            # rekord.original is @cached_property, and refresh_from_db() doesn't clear it
            # We need a completely fresh instance for rebuildEntries() to see new przypieta values
            fresh_rekord = Rekord.objects.get(pk=[content_type_id, object_id])
            fresh_publikacja = fresh_rekord.content_type.get_object_for_this_type(
                pk=fresh_rekord.object_id
            )

            # Rebuild cache punktacja with fresh publication instance
            cacher = IPunktacjaCacher(fresh_publikacja)
            cacher.removeEntries()
            cacher.rebuildEntries()

            # Recalculate evaluation metrics for all affected authors
            przelicz_metryki_dla_publikacji(publikacja)

        # Redirect back to the detail view
        # Get MetrykaAutora for the author and discipline to redirect to the correct detail page
        from django.urls import reverse

        from ..models import MetrykaAutora

        metryka = MetrykaAutora.objects.filter(
            autor_id=autor_id, dyscyplina_naukowa_id=dyscyplina_id
        ).first()

        if metryka:
            url = reverse(
                "ewaluacja_metryki:szczegoly",
                kwargs={
                    "autor_slug": metryka.autor.slug,
                    "dyscyplina_kod": metryka.dyscyplina_naukowa.kod,
                },
            )
            return redirect(url + "#prace-nazbierane")
        return redirect("ewaluacja_metryki:lista")


class OdepnijDyscyplineView(EwaluacjaRequiredMixin, View):
    """Handle unpinning a discipline for an author in a publication"""

    def post(self, request, content_type_id, object_id, autor_id, dyscyplina_id):
        from django.db import transaction
        from django.shortcuts import redirect

        from bpp.models.cache import Rekord
        from bpp.models.sloty.core import IPunktacjaCacher
        from ewaluacja_metryki.utils import przelicz_metryki_dla_publikacji

        with transaction.atomic():
            # Get the Rekord using tuple primary key
            try:
                rekord = Rekord.objects.get(pk=[content_type_id, object_id])
            except Rekord.DoesNotExist:
                raise Exception("Nie znaleziono rekordu publikacji") from None

            # Get the original publication and find the author assignment
            publikacja = rekord.original
            try:
                wa = publikacja.autorzy_set.get(
                    autor_id=autor_id, dyscyplina_naukowa_id=dyscyplina_id
                )
            except publikacja.autorzy_set.model.DoesNotExist:
                raise Exception(
                    "Nie znaleziono przypisania autora do publikacji"
                ) from None

            # Update przypieta status
            wa.przypieta = False
            wa.save()

            # Get FRESH publication instance without cached properties or related managers
            # rekord.original is @cached_property, and refresh_from_db() doesn't clear it
            # We need a completely fresh instance for rebuildEntries() to see new przypieta values
            fresh_rekord = Rekord.objects.get(pk=[content_type_id, object_id])
            fresh_publikacja = fresh_rekord.content_type.get_object_for_this_type(
                pk=fresh_rekord.object_id
            )

            # Rebuild cache punktacja with fresh publication instance
            cacher = IPunktacjaCacher(fresh_publikacja)
            cacher.removeEntries()
            cacher.rebuildEntries()

            # Recalculate evaluation metrics for all affected authors
            przelicz_metryki_dla_publikacji(publikacja)

        # Redirect back to the detail view
        # Get MetrykaAutora for the author and discipline to redirect to the correct detail page
        from django.urls import reverse

        from ..models import MetrykaAutora

        metryka = MetrykaAutora.objects.filter(
            autor_id=autor_id, dyscyplina_naukowa_id=dyscyplina_id
        ).first()

        if metryka:
            url = reverse(
                "ewaluacja_metryki:szczegoly",
                kwargs={
                    "autor_slug": metryka.autor.slug,
                    "dyscyplina_kod": metryka.dyscyplina_naukowa.kod,
                },
            )
            return redirect(url + "#prace-nazbierane")
        return redirect("ewaluacja_metryki:lista")
