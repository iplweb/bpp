from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class RekordPrzywroconyPrzezImport(models.Model):
    """Rejestr publikacji WSKRZESZONYCH z kosza przez import z PBN.

    PO CO TO ISTNIEJE. Plan fazy 03 zakładał pierwotnie, że import ma rekord
    w koszu POMIJAĆ (decyzja #14), bo auto-restore pozwala „wskrzeszać rzeczy
    skasowane celowo". Właściciel systemu rozstrzygnął inaczej — PBN jest dla
    tych publikacji źródłem prawdy, więc skoro rekord tam jest, ma wrócić
    także do BPP.

    Ryzyko wskazane w tamtej decyzji nie znika, tylko zmienia postać:
    z „nie róbmy tego" na „róbmy, ale zostawmy ślad". Ten model JEST tym
    śladem. Operator, który znajdzie w bazie publikację skasowaną przez siebie
    tydzień wcześniej, ma gdzie sprawdzić, że wróciła z importu, kiedy
    i z którego źródła — zamiast zakładać, że coś mu się przywidziało.

    Wpis powstaje WYŁĄCZNIE przy realnym wskrzeszeniu. Zwykły re-import
    żywego rekordu nie zostawia tu nic — inaczej rejestr zapełniłby się szumem
    i przestałby cokolwiek znaczyć.
    """

    content_type = models.ForeignKey(ContentType, models.CASCADE)
    object_id = models.PositiveIntegerField()
    #: Publikacja, która wróciła z kosza. GenericFK, bo import dotyka kilku
    #: modeli (wydawnictwa ciągłe, zwarte, prace doktorskie/habilitacyjne).
    rekord = GenericForeignKey("content_type", "object_id")

    przywrocono = models.DateTimeField(
        "Przywrócono",
        auto_now_add=True,
        db_index=True,
        help_text="Kiedy import wskrzesił ten rekord.",
    )
    pbn_uid = models.ForeignKey(
        "pbn_api.Publication",
        models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Publikacja w PBN",
        help_text="Rekord PBN, przez który import trafił na tę publikację.",
    )
    zrodlo_importu = models.CharField(
        "Źródło importu",
        max_length=50,
        help_text="Która ścieżka importu wskrzesiła rekord (articles / books / "
        "chapters).",
    )

    class Meta:
        verbose_name = "rekord przywrócony przez import"
        verbose_name_plural = "rekordy przywrócone przez import"
        ordering = ("-przywrocono",)
        indexes = [
            # Najczęstsze pytanie operatora brzmi „co wróciło ostatnio" —
            # stąd indeks po dacie malejąco razem z typem rekordu.
            models.Index(
                fields=["-przywrocono", "content_type"],
                name="pbnint_przywr_data_ct_idx",
            ),
            # Drugie pytanie, i jedyne zadawane WPROST o konkretną publikację:
            # „czy TEN rekord wrócił?". Indeks po dacie go nie obsługuje, a sam
            # `content_type_id` (indeks domyślny FK) zawęża do typu, nie do
            # wiersza — przy jednym typie publikacji to praktycznie skan całej
            # tabeli, która rośnie z każdym importem.
            models.Index(
                fields=["content_type", "object_id"],
                name="pbnint_przywr_ct_objid_idx",
            ),
        ]

    def __str__(self):
        return f"{self.rekord} (przywrócono: {self.przywrocono})"
