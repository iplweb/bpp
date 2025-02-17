from django import template

register = template.Library()


@register.simple_tag(name="rzeczownik", takes_context=True)
def rzeczownik(context, uid, przypadek, *args, **kwargs):
    assert przypadek in [
        "m",
        "d",
        "c",
        "b",
        "n",
        "ms",
        "w",
    ], f"nieprawidłowy przypadek dla deklinacji {przypadek=}"
    from bpp.models import Rzeczownik

    rzeczownik = Rzeczownik.objects.get(uid=uid.upper())
    return getattr(rzeczownik, przypadek)


for uid, wyraz, przypadek in [
    ("WYDZIAL", "wydział", "m"),
    ("WYDZIAL", "wydziału", "d"),
    ("WYDZIAL", "wydziałowi", "c"),
    ("WYDZIAL", "wydział", "b"),
    ("WYDZIAL", "wydziałem", "n"),
    ("WYDZIAL", "wydziale", "ms"),
    ("WYDZIAL", "wydział", "w"),
    ("UCZELNIA", "uczelnia", "m"),
    ("UCZELNIA", "uczelni", "d"),
    ("UCZELNIA", "uczelni", "c"),
    ("UCZELNIA", "uczelni", "b"),
    ("UCZELNIA", "uczelnią", "n"),
    ("UCZELNIA", "uczelni", "ms"),
    ("UCZELNIA", "uczelnio", "w"),
    ("JEDNOSTKA", "jednostka", "m"),
    ("JEDNOSTKA", "jednostki", "d"),
    ("JEDNOSTKA", "jednostce", "c"),
    ("JEDNOSTKA", "jednostkę", "b"),
    ("JEDNOSTKA", "jednostką", "n"),
    ("JEDNOSTKA", "jednostce", "ms"),
    ("JEDNOSTKA", "jednostko", "w"),
    ("JEDNOSTKA_PL", "jednostki", "m"),
    ("JEDNOSTKA_PL", "jednostek", "d"),
    ("JEDNOSTKA_PL", "jednostkom", "c"),
    ("JEDNOSTKA_PL", "jednostki", "b"),
    ("JEDNOSTKA_PL", "jednostkami", "n"),
    ("JEDNOSTKA_PL", "jednostkach", "ms"),
    ("JEDNOSTKA_PL", "jednostki", "w"),
]:

    @register.simple_tag(name="rzeczownik_" + wyraz)
    def konkretny_rzeczownik(przypadek=przypadek, uid=uid, wyraz=wyraz):
        from bpp.models import Rzeczownik

        try:
            return getattr(Rzeczownik.objects.get(uid=uid), przypadek)
        except Rzeczownik.DoesNotExist:
            return wyraz

    @register.simple_tag(name="rzeczownik_" + wyraz + "_" + przypadek)
    def konkretny_rzeczownik_z_przypadkiem(przypadek=przypadek, uid=uid, wyraz=wyraz):
        from bpp.models import Rzeczownik

        try:
            return getattr(Rzeczownik.objects.get(uid=uid), przypadek)
        except Rzeczownik.DoesNotExist:
            return wyraz
