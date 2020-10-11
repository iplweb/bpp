from django.contrib.contenttypes.admin import GenericTabularInline

from bpp.models import Element_Repozytorium


class Element_RepozytoriumInline(GenericTabularInline):
    model = Element_Repozytorium
    extra = 0
