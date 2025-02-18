from django import template

from bpp import jezyk_polski

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


for uid, wyraz, przypadek in jezyk_polski.deklinacja:
    #
    # Rejestruj tagi {% rzeczownik_wydział %}
    # oraz {% rzeczownik_wydział_m %}
    # i dla każdego innego przypadku.

    # Umożliwia to pisanie {% rzeczownik_wydziału %}
    # oraz {% rzeczownik_uczelni_d %} co pozwala potem tłumaczyć to na
    # bardziej poprawne formy.

    # Do rozważenia: zarejestrować też wersje z UIDem bo wersje 'wyrazowe'
    # mimo, iż czytelne w kodzie to są dwuznaczne.

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
