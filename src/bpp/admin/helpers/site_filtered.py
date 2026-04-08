"""
Mixin do filtrowania danych w panelu admina na podstawie aktualnej uczelni.

W trybie multi-hosted zwykły admin widzi tylko dane swojej uczelni,
superuser widzi wszystko.
"""


class SiteFilteredAdminMixin:
    """Filtruje queryset w adminie do danych aktualnej uczelni.

    Klasy pochodne ustawiają ``uczelnia_field_path`` na ścieżkę FK
    do Uczelni, np. ``"uczelnia"`` lub ``"jednostka__uczelnia"``.

    Superuserzy widzą wszystkie dane (brak filtrowania).
    """

    uczelnia_field_path = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        uczelnia = getattr(request, "_uczelnia", None)
        if uczelnia and self.uczelnia_field_path:
            return qs.filter(**{self.uczelnia_field_path: uczelnia})
        return qs

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filtruje dropdown FK do obiektów z aktualnej uczelni."""
        if not request.user.is_superuser:
            uczelnia = getattr(request, "_uczelnia", None)
            if uczelnia and db_field.name == "wydzial":
                from bpp.models import Wydzial

                kwargs["queryset"] = Wydzial.objects.filter(uczelnia=uczelnia)
            elif uczelnia and db_field.name == "jednostka":
                from bpp.models import Jednostka

                kwargs["queryset"] = Jednostka.objects.filter(uczelnia=uczelnia)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
