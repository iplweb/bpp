from django.core.exceptions import ObjectDoesNotExist


def object_or_something(model, attrname, default_pk=-1, default_attr="nazwa", default_value="--", **kwargs):
    """
    Funkcja do rozsądnego zwracania czegoś w przypadku, gdy obiekt powiązany
    (ForeignKey) może być None/NULL. W takich sytuacjach Django zwraca błąd.
    Załóżmy, że chcemy coś wysłać JSONem do klienta i nie interesuje nas wartość
    NULL, ale coś rozsądnego np z etykietą.

    Funkcja zwróci albo obiekt powiązany dla modelu 'model', określony przez
    atrybut 'attrname'... albo klasę stworzoną ad-hoc, z atrybutami określonymi
    przez paramtery.

    """

    try:
        res = getattr(model, attrname)
    except ObjectDoesNotExist:
        pass

    if res is not None:
        return res

    class Unexistent:
        pk = default_pk

    ret = Unexistent()
    if not kwargs and default_attr is not None:
        kwargs[default_attr] = default_value

    for key, value in kwargs.items():
        setattr(ret, key, value)

    return ret
