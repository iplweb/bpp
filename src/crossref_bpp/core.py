from django import models

from import_common.normalization import normalize_doi

from bpp.models import Rekord


class StatusPorownania(models.TextChoices):
    DOKLADNE = "ok", "dokładne (identyczne - mocne)"
    LUZNE = "luzne", "luźne (może być nieprawidłowe)"
    WYMAGA_INGERENCJI = (
        "user",
        "wymaga ręcznego wybrania (dwa lub więcej dokładne wyniki)",
    )
    BRAK = "brak", "brak porównania"
    BLAD = "blad", "błąd porównania - pusty lub niepoprawny parametr wejściowy"


class WynikPorownania:
    def __init__(
        self,
        status: StatusPorownania,
        opis: str = "",
        rekord: [
            [
                models.Model,
            ]
            | models.Model
            | None
        ] = None,
    ):
        self.status = status
        self.opis = opis
        self.rekord = rekord


class Komparator:
    @classmethod
    def porownaj(cls, atrybut, wartosc_z_crossref):
        atrybut = atrybut.replace("-", "_")
        fn = getattr(cls, f"porownaj_{atrybut}")
        if fn is None:
            return WynikPorownania(
                StatusPorownania.BLAD,
                "brak funkcji w oprogramowaniu dla porównania tego atrybutu",
            )
        return fn(wartosc_z_crossref)

    @classmethod
    def porownaj_DOI(cls, wartosc):
        doi = normalize_doi(wartosc)

        if not doi:
            return WynikPorownania(StatusPorownania.BLAD, "puste DOI")

        ile = Rekord.objects.filter(doi__ilike=doi).order_by("-ostatnio_zmieniony")[:10]

        if not ile.exists():
            return WynikPorownania(StatusPorownania.BRAK, "brak takiego DOI w bazie")

        if ile.count() == 1:
            return WynikPorownania(StatusPorownania.DOKLADNE, rekord=ile.first())

        # wiecej, jak jeden rekord
        return WynikPorownania(StatusPorownania.WYMAGA_INGERENCJI, rekord=ile)
