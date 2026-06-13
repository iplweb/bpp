"""
Modele abstrakcyjne związane z wyszukiwaniem i danymi legacy.
"""

from django.contrib.postgres.fields import HStoreField
from django.contrib.postgres.search import SearchVectorField as VectorField
from django.db import models

# Rodzajniki obcinane z początku tytułu przy budowaniu klucza sortowania,
# per skrót języka. Domyślnie (m.in. polski) nic nie obcinamy — sam strip
# białych znaków. Dawniej tablica `GD` w triggerze plpython `trigger_tytul_sort`;
# po pożegnaniu z plpython3u klucz liczymy w warstwie modelu (patrz save()).
#
# PostgreSQL nie ma kolacji "ignoruj rodzajnik" (to katalogowe *nonfiling
# characters*, spoza Unicode Collation Algorithm), więc osobna kolumna-klucz
# `tytul_oryginalny_sort` to właściwy, standardowy wzorzec.
PRZEDROSTKI_DO_OBCIECIA = {
    "ang.": ["the ", "a "],
    "niem.": ["der ", "die ", "das "],
    "fr.": ["la ", "le ", "en "],
    "wł.": ["la ", "en "],
    "hiszp.": ["de ", "la ", "en "],
}

# Pola, których zmiana wymusza przeliczenie klucza sortu. Gdy save() dostaje
# update_fields rozłączne z tym zbiorem — klucz się nie zmienia, więc pomijamy
# (odpowiednik bramki "nic się nie zmieniło" z dawnego triggera).
_POLA_ZRODLOWE_TYTUL_SORT = frozenset({"tytul_oryginalny", "jezyk", "jezyk_id"})


def oblicz_tytul_oryginalny_sort(tytul_oryginalny, jezyk_skrot):
    """Klucz sortowania tytułu: lowercase + strip, obcięcie rodzajników
    właściwych dla języka, usunięcie cudzysłowów.

    Wierna kalka dawnego triggera DB `trigger_tytul_sort` (plpython3u)."""
    przedrostki = PRZEDROSTKI_DO_OBCIECIA.get(jezyk_skrot, [" ", "\t"])
    ret = (tytul_oryginalny or "").lower().strip()
    for przedrostek in przedrostki:
        while ret.startswith(przedrostek):
            ret = ret[len(przedrostek) :]
    return ret.replace("'", "").replace('"', "")


class ModelPrzeszukiwalny(models.Model):
    """Model zawierający pole pełnotekstowego przeszukiwania
    'search_index'"""

    search_index = VectorField()
    tytul_oryginalny_sort = models.TextField(db_index=True, default="")

    class Meta:
        abstract = True

    def save(self, *args, update_fields=None, **kwargs):
        # Liczymy tytul_oryginalny_sort w modelu (dawniej BEFORE-trigger
        # plpython `trigger_tytul_sort`). Gotcha update_fields: gdy zapis jest
        # częściowy i dotyka tytułu/języka — dorzucamy klucz do update_fields,
        # inaczej policzona wartość nie trafiłaby do bazy.
        if update_fields is None or _POLA_ZRODLOWE_TYTUL_SORT.intersection(
            update_fields
        ):
            self.tytul_oryginalny_sort = oblicz_tytul_oryginalny_sort(
                getattr(self, "tytul_oryginalny", "") or "",
                self._jezyk_skrot_dla_sortu(),
            )
            if update_fields is not None:
                update_fields = set(update_fields) | {"tytul_oryginalny_sort"}
        return super().save(*args, update_fields=update_fields, **kwargs)

    def _jezyk_skrot_dla_sortu(self):
        # Patent nie ma kolumny jezyk_id (język to stała cached_property),
        # więc — jak dawny trigger czytający TD["new"].get("jezyk_id") — gdy
        # brak jezyk_id przyjmujemy domyślnie polski (bez obcinania rodzajnika).
        jezyk_id = getattr(self, "jezyk_id", None)
        if jezyk_id is None:
            return "pol."
        return self.jezyk.skrot


class ModelZLegacyData(models.Model):
    """Model zawierający informacje zaimportowane z poprzedniego systemu,
    nie mające odpowiednika w nowych danych, jednakże pozostawione na
    rekordzie w taki sposób, aby w razie potrzeby w przyszłości można było
    z nich skorzystać"""

    legacy_data = HStoreField(blank=True, null=True)

    class Meta:
        abstract = True
