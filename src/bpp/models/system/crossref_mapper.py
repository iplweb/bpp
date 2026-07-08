from django.db import models


class Crossref_Mapper(models.Model):
    class CHARAKTER_CROSSREF(models.IntegerChoices):
        JOURNAL_ARTICLE = 1, "journal-article"
        PROCEEDINGS_ARTICLE = 2, "proceedings-article"
        BOOK = 3, "book"
        BOOK_CHAPTER = 4, "book-chapter"
        EDITED_BOOK = 5, "edited-book"
        PROCEEDINGS = 6, "proceedings"
        MONOGRAPH = 7, "monograph"
        REFERENCE_BOOK = 8, "reference-book"
        BOOK_SERIES = 9, "book-series"
        BOOK_SET = 10, "book-set"
        BOOK_SECTION = 11, "book-section"
        BOOK_PART = 12, "book-part"
        DISSERTATION = 13, "dissertation"
        POSTED_CONTENT = 14, "posted-content"
        PEER_REVIEW = 15, "peer-review"
        OTHER = 16, "other"

    # Typy CrossRef, które w BPP są wydawnictwami zwartymi (książki,
    # rozdziały, monografie, dysertacje). Reszta to wydawnictwa ciągłe
    # (artykuły). Jedno źródło prawdy dla domyślnej wartości pola
    # ``jest_wydawnictwem_zwartym`` — używane przy leniwym tworzeniu
    # mapperów (``get_or_create(defaults=...)``) oraz w migracji seedującej.
    BOOK_TYPES = frozenset(
        {
            CHARAKTER_CROSSREF.BOOK,
            CHARAKTER_CROSSREF.BOOK_CHAPTER,
            CHARAKTER_CROSSREF.EDITED_BOOK,
            CHARAKTER_CROSSREF.MONOGRAPH,
            CHARAKTER_CROSSREF.REFERENCE_BOOK,
            CHARAKTER_CROSSREF.BOOK_SERIES,
            CHARAKTER_CROSSREF.BOOK_SET,
            CHARAKTER_CROSSREF.BOOK_SECTION,
            CHARAKTER_CROSSREF.BOOK_PART,
            CHARAKTER_CROSSREF.DISSERTATION,
        }
    )

    charakter_crossref = models.PositiveSmallIntegerField(
        "Charakter w CrossRef",
        choices=CHARAKTER_CROSSREF.choices,
        unique=True,
    )

    charakter_formalny_bpp = models.ForeignKey(
        "bpp.Charakter_Formalny", on_delete=models.CASCADE, null=True, blank=True
    )

    jest_wydawnictwem_zwartym = models.BooleanField(
        "Jest wydawnictwem zwartym",
        default=False,
        help_text="Zaznacz, jeśli prace tego typu powinny być dodawane jako "
        "wydawnictwa zwarte (książki, rozdziały). "
        "W przeciwnym razie będą traktowane jako wydawnictwa ciągłe (artykuły).",
    )

    class Meta:
        verbose_name = "mapowanie typu CrossRef na BPP"
        verbose_name_plural = "mapowania typów CrossRef na BPP"

    def __str__(self):
        v = "[brak zamapowania]"
        if self.charakter_formalny_bpp_id is not None:
            v = self.charakter_formalny_bpp.nazwa

        return f"{self.CHARAKTER_CROSSREF(self.charakter_crossref).label} -> {v}"

    @staticmethod
    def default_jest_wydawnictwem_zwartym(charakter_crossref) -> bool:
        """Czy dany typ CrossRef domyślnie jest wydawnictwem zwartym."""
        return charakter_crossref in Crossref_Mapper.BOOK_TYPES
