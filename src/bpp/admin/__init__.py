from django import forms
from multiseek.models import SearchForm

from ..models import (
    BppUser,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jezyk,
    Rodzaj_Zrodla,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Tytul,
    Wymiar_Etatu,
    Zrodlo_Informacji,
)
from ..models.nagroda import OrganPrzyznajacyNagrody
from ..models.system import Charakter_PBN
from .autor import AutorAdmin  # noqa
from .autor_dyscyplina import Autor_DyscyplinaAdmin  # noqa
from .charakter_formalny import Charakter_FormalnyAdmin  # noqa
from .core import (
    BaseBppAdminMixin,
    PreventDeletionAdmin,
    RestrictDeletionToAdministracjaGroupAdmin,
    RestrictDeletionToAdministracjaGroupMixin,
)
from .dyscyplina_naukowa import Dyscyplina_NaukowaAdmin  # noqa
from .jednostka import JednostkaAdmin  # NOQA
from .kierunek_studiow import Kierunek_StudiowAdmin  # noqa
from .konferencja import KonferencjaAdmin  # noqa
from .patent import Patent_Admin  # noqa
from .praca_doktorska import Praca_DoktorskaAdmin  # noqa
from .praca_habilitacyjna import Praca_HabilitacyjnaAdmin  # noqa
from .seria_wydawnicza import Seria_WydawniczaAdmin  # noqa
from .szablondlaopisubibliograficznego import SzablonDlaOpisuBibliograficznego  # noqa
from .uczelnia import UczelniaAdmin  # NOQA
from .wydawca import WydawcaAdmin  # noqa
from .wydawnictwo_ciagle import Wydawnictwo_CiagleAdmin  # noqa
from .wydawnictwo_ciagle_autor import Wydawnictwo_Ciagle_Autor_Admin  # noqa
from .wydawnictwo_zwarte import (  # noqa
    Wydawnictwo_ZwarteAdmin,
    Wydawnictwo_ZwarteAdmin_Baza,
)
from .wydawnictwo_zwarte_autor import Wydawnictwo_Zwarte_Autor_Admin  # noqa
from .wydzial import WydzialAdmin  # noqa

from django.contrib import admin
from django.contrib.auth.forms import UserCreationForm

from .bppmultiseekvisibility import BppMulitiseekVisibilityAdmin  # noqa
from bpp.models import Rodzaj_Prawa_Patentowego, Zewnetrzna_Baza_Danych

# Proste tabele
from bpp.models.openaccess import (
    Czas_Udostepnienia_OpenAccess,
    Licencja_OpenAccess,
    Tryb_OpenAccess_Wydawnictwo_Ciagle,
    Tryb_OpenAccess_Wydawnictwo_Zwarte,
    Wersja_Tekstu_OpenAccess,
)


class JezykAdmin(RestrictDeletionToAdministracjaGroupAdmin):
    list_display = ["nazwa", "skrot", "pbn_uid", "skrot_crossref"]


class Funkcja_AutoraAdmin(RestrictDeletionToAdministracjaGroupAdmin):
    list_display = ["nazwa", "skrot", "pokazuj_za_nazwiskiem"]


admin.site.register(Jezyk, JezykAdmin)
admin.site.register(Funkcja_Autora, Funkcja_AutoraAdmin)
admin.site.register(Rodzaj_Zrodla, PreventDeletionAdmin)
admin.site.register(Status_Korekty, PreventDeletionAdmin)
admin.site.register(Zrodlo_Informacji, PreventDeletionAdmin)
admin.site.register(Rodzaj_Prawa_Patentowego, PreventDeletionAdmin)

admin.site.register(OrganPrzyznajacyNagrody, PreventDeletionAdmin)

admin.site.register(Grupa_Pracownicza, PreventDeletionAdmin)
admin.site.register(Wymiar_Etatu, PreventDeletionAdmin)


@admin.register(Zewnetrzna_Baza_Danych)
class Zewnetrzna_Baza_DanychAdmin(
    RestrictDeletionToAdministracjaGroupAdmin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = ["nazwa", "skrot"]


class Charakter_PBNAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = [
        "identyfikator",
        "wlasciwy_dla",
        "opis",
        "charaktery_formalne",
        "typy_kbn",
    ]
    readonly_fields = ["identyfikator", "wlasciwy_dla", "opis", "help_text"]

    def charaktery_formalne(self, rec):
        return ", ".join(
            [f"{x.nazwa} ({x.skrot})" for x in rec.charakter_formalny_set.all()]
        )

    def typy_kbn(self, rec):
        return ", ".join([f"{x.nazwa} ({x.skrot})" for x in rec.typ_kbn_set.all()])


admin.site.register(Charakter_PBN, Charakter_PBNAdmin)


class NazwaISkrotAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = ["skrot", "nazwa"]
    search_fields = ["skrot", "nazwa"]


admin.site.register(Tytul, NazwaISkrotAdmin)


class Typ_KBNAdmin(
    RestrictDeletionToAdministracjaGroupAdmin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = ["nazwa", "skrot", "artykul_pbn", "charakter_pbn"]


admin.site.register(Typ_KBN, Typ_KBNAdmin)


class Typ_OdpowiedzialnosciAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = ["nazwa", "skrot", "typ_ogolny"]


class Tryb_OpenAccess_Wydawnictwo_CiagleAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = ["nazwa", "skrot"]


admin.site.register(
    Tryb_OpenAccess_Wydawnictwo_Ciagle, Tryb_OpenAccess_Wydawnictwo_CiagleAdmin
)


class Tryb_OpenAccess_Wydawnictwo_ZwarteAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = ["nazwa", "skrot"]


admin.site.register(
    Tryb_OpenAccess_Wydawnictwo_Zwarte, Tryb_OpenAccess_Wydawnictwo_ZwarteAdmin
)


class Czas_Udostepnienia_OpenAccessAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = ["nazwa", "skrot"]


admin.site.register(Czas_Udostepnienia_OpenAccess, Czas_Udostepnienia_OpenAccessAdmin)


class Licencja_OpenAccessAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = ["nazwa", "skrot"]


admin.site.register(Licencja_OpenAccess, Licencja_OpenAccessAdmin)


class Wersja_Tekstu_OpenAccessAdmin(
    RestrictDeletionToAdministracjaGroupMixin, BaseBppAdminMixin, admin.ModelAdmin
):
    list_display = ["nazwa", "skrot"]


admin.site.register(Wersja_Tekstu_OpenAccess, Wersja_Tekstu_OpenAccessAdmin)

admin.site.register(Typ_Odpowiedzialnosci, Typ_OdpowiedzialnosciAdmin)

# Bibliografia


from django.contrib.auth.admin import UserAdmin


class BppUserCreationForm(UserCreationForm):
    class Meta:
        model = BppUser
        fields = "__all__"

    def clean_username(self):
        # Since User.username is unique, this check is redundant,
        # but it sets a nicer error message than the ORM. See #13147.
        username = self.cleaned_data["username"]
        try:
            BppUser._default_manager.get(username=username)
        except BppUser.DoesNotExist:
            return username
        raise forms.ValidationError(
            self.error_messages["duplicate_username"],
            code="duplicate_username",
        )


class BppUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "is_superuser",
        "lista_grup",
    )

    add_form = BppUserCreationForm

    # change_form_template = 'loginas/change_form.html'

    def has_delete_permission(self, request, obj=None):
        if obj is not None:
            # Nie pozwól na usunięcie obecnego konta
            if obj == request.user:
                return False

            # Sprawdź przy kasowaniu konta 'admin' czy są jeszcze jakieś konta z
            # uprawnieniem admina, jeżeli nie, to nie pozwól na to:
            if not BppUser.objects.exclude(pk=obj.pk).exists():
                return False

        return super().has_delete_permission(request, obj)

    def lista_grup(self, row):
        return ", ".join([x.name for x in row.groups.all()])


admin.site.register(BppUser, BppUserAdmin)


class SearchFormAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "public"]
    fields = ["name", "owner", "public", "data"]
    readonly_fields = ["data"]


SearchForm._meta.verbose_name = "formularz wyszukiwania"
SearchForm._meta.verbose_name_plural = "formularze wyszukiwania"

admin.site.register(SearchForm, SearchFormAdmin)

from .templates import TemplateAdmin  # noqa
from .zrodlo import ZrodloAdmin  # noqa
