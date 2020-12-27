from bpp.models import Uczelnia


class UkryjStatusyKorektyMixin:
    def get_queryset(self):
        queryset = super(UkryjStatusyKorektyMixin, self).get_queryset()

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia:
            ukryte_statusy = uczelnia.ukryte_statusy("api")
            if ukryte_statusy:
                queryset = queryset.exclude(status_korekty_id__in=ukryte_statusy)

        return queryset
