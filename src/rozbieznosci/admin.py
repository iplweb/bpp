from django.contrib import admin

from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog


@admin.register(IgnorowanaRozbieznosc)
class IgnorowanaRozbieznoscAdmin(admin.ModelAdmin):
    list_display = ["metryka", "rekord", "created_on"]
    list_filter = ["metryka", "created_on"]
    search_fields = ["rekord__tytul_oryginalny"]


@admin.register(RozbieznoscLog)
class RozbieznoscLogAdmin(admin.ModelAdmin):
    list_display = [
        "metryka",
        "rekord",
        "zrodlo",
        "wartosc_przed",
        "wartosc_po",
        "user",
        "created_on",
    ]
    list_filter = ["metryka", "created_on", "user"]
    search_fields = ["rekord__tytul_oryginalny", "zrodlo__nazwa"]
    readonly_fields = [
        "metryka",
        "rekord",
        "zrodlo",
        "wartosc_przed",
        "wartosc_po",
        "user",
        "created_on",
    ]
    date_hierarchy = "created_on"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # NIE twarde ``False``. Django admin pyta tą samą metodą o dwie różne
        # rzeczy: (a) czy pokazać "usuń" tutaj i (b) czy wolno skasować ten
        # wpis KASKADOWO, przy kasowaniu publikacji-rodzica (patrz
        # ``django.contrib.admin.utils.get_deleted_objects``). Twarde ``False``
        # blokowało więc skasowanie publikacji KAŻDEMU, również superuserowi,
        # komunikatem o braku uprawnień do "logu zmiany punktacji".
        # Log pozostaje niemodyfikowalny (brak add/change); skasować go może
        # ten, kto ma standardowe uprawnienie ``delete_rozbieznosclog``.
        return super().has_delete_permission(request, obj)
